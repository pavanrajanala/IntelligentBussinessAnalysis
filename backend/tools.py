"""
tools.py - The agent's "actions". Each function does ONE real analysis task on
ONE user's data. The LLM (agent.py) decides which to call; the numbers always
come from here, never from the model's memory.

Every tool takes user_id first. agent.py supplies it, so the model can never
ask for another shop's data.
"""

import datetime
import difflib
import os
import time

import pandas as pd

import forecast
import repo
import seasonal
from clean import normalize_text

MAX_SWITCH_DETAILS = 15


def _data(user_id: str) -> pd.DataFrame:
    """This user's sales without flagged outliers."""
    return repo.read_sales(user_id, exclude_outliers=True)


def _no_data() -> dict:
    return {"found": False, "message": "No sales data has been uploaded yet."}


def _resolve_product(df: pd.DataFrame, name: str):
    """
    Match what the user typed to a real product name. Returns (product_or_None, suggestions).
    Handles case, spacing, partial names ("colgate" -> "Colgate Total") and small typos.
    """
    products = sorted(df["product"].unique())
    wanted = normalize_text(name)
    if wanted in products:
        return wanted, []
    contains = [p for p in products if wanted.lower() in p.lower() or p.lower() in wanted.lower()]
    if len(contains) == 1:
        return contains[0], []
    close = difflib.get_close_matches(wanted, products, n=3, cutoff=0.6)
    if len(close) == 1 or (close and not contains):
        return close[0], []
    return None, (contains or close or products[:8])[:8]


def _not_found(name: str, suggestions: list) -> dict:
    return {"product": name, "found": False, "message": f"No sales data found for '{name}'.", "available_products": suggestions}


def get_sales_trend(user_id: str, product: str) -> dict:
    """Monthly quantity and revenue for one product, plus the overall direction."""
    df = _data(user_id)
    if df.empty:
        return _no_data()
    resolved, suggestions = _resolve_product(df, product)
    if resolved is None:
        return _not_found(product, suggestions)

    product_df = df[df["product"] == resolved].copy()
    product_df["month"] = product_df["date"].dt.to_period("M").astype(str)
    monthly = (
        product_df.groupby("month")
        .agg(units_sold=("quantity", "sum"), revenue_rupees=("revenue", "sum"), orders=("quantity", "count"))
        .sort_index().round(2).reset_index()
    )
    direction, pct = "not enough data", None
    if len(monthly) >= 2 and monthly.iloc[0]["revenue_rupees"] > 0:
        first, last = monthly.iloc[0], monthly.iloc[-1]
        pct = round(((last["revenue_rupees"] - first["revenue_rupees"]) / first["revenue_rupees"]) * 100, 1)
        direction = "increasing" if pct > 0 else "decreasing" if pct < 0 else "flat"
    return {
        "product": resolved,
        "category": product_df["category"].iloc[0],
        "found": True,
        "monthly_breakdown": monthly.to_dict(orient="records"),
        "trend_direction": direction,
        "pct_change_first_to_last_month": pct,
    }


def find_customer_switching(user_id: str, product: str) -> dict:
    """Customers who bought `product` in the first half of the data but not the second, and what they bought instead."""
    df = _data(user_id)
    if df.empty:
        return _no_data()
    resolved, suggestions = _resolve_product(df, product)
    if resolved is None:
        return _not_found(product, suggestions)
    if df["customer_id"].nunique() <= 1:
        return {"found": False, "message": "The uploaded data has no customer ids, so customer switching cannot be checked."}

    product_df = df[df["product"] == resolved]
    category = product_df["category"].iloc[0]
    midpoint = df["date"].min() + (df["date"].max() - df["date"].min()) / 2
    early = set(product_df[product_df["date"] <= midpoint]["customer_id"])
    late = set(product_df[product_df["date"] > midpoint]["customer_id"])
    stopped = early - late

    details, counts = [], {}
    for cust in sorted(stopped):
        other = df[(df["customer_id"] == cust) & (df["category"] == category) & (df["product"] != resolved) & (df["date"] > midpoint)]
        if not other.empty:
            to = other["product"].value_counts().idxmax()
            details.append({"customer_id": cust, "switched_to": to})
            counts[to] = counts.get(to, 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "product": resolved,
        "found": True,
        "category": category,
        "split_date": midpoint.strftime("%Y-%m-%d"),
        "total_customers_ever": int(product_df["customer_id"].nunique()),
        "customers_who_stopped": len(stopped),
        "customers_who_switched": len(details),
        "top_switched_to": [{"product": p, "customers": c} for p, c in top],
        "switch_details": details[:MAX_SWITCH_DETAILS],
    }


_NEWS_CACHE: dict[str, tuple[float, dict]] = {}
NEWS_CACHE_SECONDS = 6 * 60 * 60  # the same brand is not searched again for six hours (saves Tavily credits)


def check_external_news(user_id: str, product: str) -> dict:
    """
    Real web search about a brand (bans, recalls, price changes, controversies), returned as a short
    summary plus a few sources. Only offered to the model when the user turned news on.
    Needs TAVILY_API_KEY (free tier at tavily.com).
    """
    import requests

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return {"found": False, "message": "Web news search is not set up (no TAVILY_API_KEY)."}
    cache_key = (product or "").strip().lower()
    hit = _NEWS_CACHE.get(cache_key)
    if hit and time.time() - hit[0] < NEWS_CACHE_SECONDS:
        return hit[1]
    year = datetime.date.today().year
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "query": f"{product} India news {year} sales demand price recall controversy",
                "max_results": 4,
                "search_depth": "basic",
                "include_answer": "basic",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"found": False, "message": f"News search failed: {e}"}

    results = data.get("results", [])
    if not results:
        return {"found": False, "message": f"No recent news found for '{product}'."}

    def domain(url: str) -> str:
        return (url or "").split("//")[-1].split("/")[0].replace("www.", "")

    out = {
        "found": True,
        "search_summary": data.get("answer"),
        "articles": [
            {"title": r.get("title"), "source": domain(r.get("url")), "snippet": (r.get("content") or "")[:450], "url": r.get("url")}
            for r in results[:4]
        ],
    }
    _NEWS_CACHE[cache_key] = (time.time(), out)
    return out


def get_category_performance(user_id: str) -> dict:
    df = _data(user_id)
    if df.empty:
        return _no_data()
    grouped = df.groupby("category")["revenue"].sum().sort_values(ascending=False).round(2)
    return {"found": True, "category_revenue_rupees": grouped.reset_index().to_dict(orient="records")}


def get_top_products(user_id: str, n: int = 5, ascending: bool = False) -> dict:
    df = _data(user_id)
    if df.empty:
        return _no_data()
    n = max(1, min(int(n), 50))
    grouped = df.groupby("product")["revenue"].sum().sort_values(ascending=bool(ascending)).round(2)
    return {
        "found": True,
        "products_revenue_rupees": grouped.head(n).reset_index().to_dict(orient="records"),
        "order": "lowest first" if ascending else "highest first",
    }


def compare_periods(user_id: str) -> dict:
    df = _data(user_id)
    if df.empty:
        return _no_data()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    monthly = df.groupby("month").agg(revenue=("revenue", "sum"), orders=("quantity", "count")).sort_index()
    if len(monthly) < 2:
        return {"found": False, "message": "Not enough months of data to compare."}
    prev, curr = monthly.iloc[-2], monthly.iloc[-1]
    change = round(((curr["revenue"] - prev["revenue"]) / prev["revenue"]) * 100, 1) if prev["revenue"] else None
    return {
        "found": True,
        "previous_month": {"month": monthly.index[-2], "revenue_rupees": round(float(prev["revenue"]), 2), "orders": int(prev["orders"])},
        "current_month": {"month": monthly.index[-1], "revenue_rupees": round(float(curr["revenue"]), 2), "orders": int(curr["orders"])},
        "revenue_change_pct": change,
    }


def forecast_next_month(user_id: str, top: int = 8) -> dict:
    """What to order next month: forecast units and a suggested order quantity per product."""
    df = _data(user_id)
    result = forecast.predict_next_month(df, repo.get_profile(user_id))
    if not result.get("found"):
        return result
    top = max(1, min(int(top), 20))
    rows = sorted(result["products"], key=lambda r: abs(r["suggested_order"] - r["last_month_units"]), reverse=True)[:top]
    return {
        "found": True,
        "month": result["target_label"],
        "season": result["season"]["name"],
        "products": [
            {k: r[k] for k in ("product", "last_month_units", "forecast_units", "suggested_order", "action", "confidence", "why")}
            for r in rows
        ],
        "warnings": result["warnings"],
    }


def festival_outlook(user_id: str) -> dict:
    """Upcoming festivals and the season for the shop's state, with what to stock."""
    df = _data(user_id)
    outlook = seasonal.build_outlook(df, repo.get_profile(user_id))
    outlook["upcoming"] = [
        {
            "name": f["name"], "date": f["date"], "days_away": f["days_away"], "stock_by": f["stock_by"],
            "stock_up": [{"group": i["group"], "boost_pct": i["boost_pct"], "your_products": i["your_products"], "ideas": i["ideas"]} for i in f["items"][:4]],
        }
        for f in outlook["upcoming"][:4]
    ]
    return {"found": True, **{k: outlook[k] for k in ("today", "state", "season", "next_month_season", "upcoming", "tips")}}
