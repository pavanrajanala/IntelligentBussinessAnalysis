"""
agent.py - The agentic loop.

    1. Send the question (plus the last few messages for context) and the allowed tools to the model.
    2. The model replies with either a final answer or a request to run tools.
    3. Run the requested Python tool(s) for THIS user only.
    4. Send the results back. Repeat until the model answers (or the safety limit hits).
    5. Return the answer, a short trace of the tools used, and any news sources.

Two rules are enforced in code, not just asked of the model:
  - Money is always shown in rupees (see _rupees).
  - The web-news tool is only available when the user turned news on, or the question is about news.
"""

import json
import os
import re
import time

import config  # noqa: F401  (loads backend/.env)
from tool_schemas import TOOL_FUNCTIONS, get_tools

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Safety limits
MAX_ITERATIONS = 6
MAX_RETRIES_PER_CALL = 3
MAX_QUESTION_CHARS = 1000
HISTORY_MESSAGES = 6

NEWS_WORDS = re.compile(
    r"\b(news|headline|external|outside|market trend|controvers\w*|banned?|recall\w*|lawsuit|scandal|boycott|rumou?rs?|"
    r"viral|online|on the web|internet|competitor news|why .* (in the news|trending))\b",
    re.I,
)

SYSTEM_PROMPT = """You are a business analyst assistant for a small shop owner in India.

Rules:
- Only state numbers that came from tool results. Never invent business-specific facts. Call a tool before answering any question about sales, products, ordering, festivals or season.
- If a tool says found=false or the data is not enough, say so plainly. If a product name was not found, mention the available product names the tool returned.
- Money is ALWAYS in Indian rupees. Write amounts with the ₹ symbol (for example ₹12,500). Never use $, USD, Rs. or INR. Quantities are units, not rupees.
- "Why is X declining" questions: use get_sales_trend and find_customer_switching (internal data) first. {news_rule}
- Questions about what to order or stock next month: use forecast_next_month. Questions about festivals, season or weather: use festival_outlook. Give a short list of products with quantities and one reason each.
- Reply in plain text only. Never use markdown symbols such as ** or # or backticks. Short sentences, or lines starting with a dash, are fine.
- Keep answers under about 150 words, grounded in the actual numbers returned.
"""

NEWS_ON = (
    "The user has turned on web news, so you may call check_external_news if internal data does not fully explain "
    "the decline. Summarise what you find in 2 or 3 plain sentences in your own words. Do not paste web links or "
    "article titles into the answer; mention the source names in brackets, for example (Economic Times). "
    "The app shows the source links separately. If no external cause is found, say so."
)
NEWS_OFF = (
    "Web news is switched off for this question, so do not look for external causes. If internal data does not "
    "explain the change, say that, and add one short sentence suggesting the user tick 'Include web news' to check "
    "for outside reasons."
)


def wants_news(question: str) -> bool:
    return bool(NEWS_WORDS.search(question or ""))


def _make_client():
    """Create the Groq client (OpenAI-compatible). Separate function so tests can replace it."""
    from openai import OpenAI

    return OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url=GROQ_BASE_URL)


# ---------- Cleaning up the model's text ----------

_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_MONEY_BEFORE = re.compile(rf"(?<![A-Za-z])(?:US\$|USD|\$|Rs\.?|INR|₹)\s?{_NUM}", re.I)
_MONEY_AFTER = re.compile(rf"{_NUM}\s?(?:INR|Rs\.?|rupees?|dollars?|USD)(?![A-Za-z])", re.I)


def _rupees(text: str) -> str:
    """Force every money amount into the form ₹12,500, whatever symbol the model used."""
    text = _MONEY_BEFORE.sub(lambda m: "₹" + m.group(1), text)
    text = _MONEY_AFTER.sub(lambda m: "₹" + m.group(1), text)
    return re.sub(r"\bdollars?\b", "rupees", text, flags=re.I)


def _plain_text(text: str) -> str:
    """The UI shows plain text, so strip any markdown and fix currency."""
    if not text:
        return ""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*[*]\s+", "- ", text, flags=re.M)
    text = re.sub(r"https?://\S+", "", text)  # sources are shown separately as links
    text = re.sub(r"[ \t]+\n", "\n", text)
    return _rupees(text).strip()


def _assistant_message(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
            for tc in message.tool_calls
        ],
    }


def _call_model(client, messages, tools):
    last_error = None
    for attempt in range(MAX_RETRIES_PER_CALL):
        try:
            kwargs = {"model": MODEL, "messages": messages, "temperature": 0.2}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            return client.chat.completions.create(**kwargs), None
        except Exception as e:
            last_error = e
            print(f"Groq request failed (attempt {attempt + 1}/{MAX_RETRIES_PER_CALL}): {e}")
            if attempt < MAX_RETRIES_PER_CALL - 1:
                time.sleep(1.5 * (attempt + 1))
    return None, last_error


def _run_tool(user_id: str, name: str, raw_arguments: str, allowed: set):
    """Parse arguments and run one tool. Always returns (args, result); never raises."""
    try:
        args = json.loads(raw_arguments) if raw_arguments and raw_arguments.strip() else {}
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        return {}, {"error": f"Invalid tool arguments: {e}"}

    args.pop("user_id", None)  # the model must never choose whose data to read
    if name not in TOOL_FUNCTIONS or name not in allowed:
        return args, {"error": f"Tool not available: {name}"}
    try:
        return args, TOOL_FUNCTIONS[name](user_id, **args)
    except Exception as e:
        return args, {"error": f"Tool '{name}' failed: {e}"}


def run_agent(user_id: str, user_question: str, history: list | None = None, allow_news: bool = False) -> dict:
    """
    Returns {"answer", "trace": [{tool, arguments, error?}], "sources": [{title, source, url}],
             "used_news": bool, "iterations_used": int}
    """
    empty = {"trace": [], "sources": [], "used_news": False}
    if not os.getenv("GROQ_API_KEY"):
        return {**empty, "answer": "The assistant is not set up yet: GROQ_API_KEY was not found. Add it to backend/.env and restart the server.", "iterations_used": 0}

    question = (user_question or "").strip()[:MAX_QUESTION_CHARS]
    news_enabled = bool(allow_news) or wants_news(question)
    tools = get_tools(news_enabled)
    allowed = {t["function"]["name"] for t in tools}

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(news_rule=NEWS_ON if news_enabled else NEWS_OFF)}]
    for m in (history or [])[-HISTORY_MESSAGES:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:1500]})
    messages.append({"role": "user", "content": question})

    client = _make_client()
    trace: list[dict] = []
    sources: list[dict] = []
    used_news = False

    for iteration in range(MAX_ITERATIONS):
        last_turn = iteration == MAX_ITERATIONS - 1  # on the last turn tools are withheld so it must answer
        response, error = _call_model(client, messages, None if last_turn else tools)
        if response is None:
            return {**empty, "trace": trace, "answer": f"The AI service did not respond. Please try again in a moment.\n(Details: {error})", "iterations_used": iteration + 1}

        message = response.choices[0].message
        if message.tool_calls:
            messages.append(_assistant_message(message))
            for tc in message.tool_calls:
                name = tc.function.name
                args, result = _run_tool(user_id, name, tc.function.arguments, allowed)
                step = {"tool": name, "arguments": args}
                if isinstance(result, dict) and result.get("error"):
                    step["error"] = True
                trace.append(step)
                if name == "check_external_news":
                    used_news = True
                    for a in (result.get("articles") or [])[:3] if isinstance(result, dict) else []:
                        if a.get("url") and not any(s["url"] == a["url"] for s in sources):
                            sources.append({"title": a.get("title"), "source": a.get("source"), "url": a["url"]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
            continue

        answer = _plain_text(message.content or "") or "I could not produce an answer for that. Try rephrasing the question."
        return {"answer": answer, "trace": trace, "sources": sources, "used_news": used_news, "iterations_used": iteration + 1}

    return {**empty, "trace": trace, "answer": "I could not reach an answer in time. Try rephrasing the question.", "iterations_used": MAX_ITERATIONS}
