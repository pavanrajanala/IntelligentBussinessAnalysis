"""
tool_schemas.py - Describes each tool to the LLM (name, purpose, arguments)
and maps tool names to the real Python functions in tools.py.
"""

from tools import (
    check_external_news,
    compare_periods,
    festival_outlook,
    find_customer_switching,
    forecast_next_month,
    get_category_performance,
    get_sales_trend,
    get_top_products,
)


def _tool(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
        },
    }


PRODUCT = {"product": {"type": "string", "description": "Product name as the user wrote it, e.g. 'Colgate'"}}

ALL_TOOLS = [
    _tool("get_sales_trend",
          "Monthly sales trend (units, revenue in rupees, orders) for one product, and whether it is increasing or decreasing.",
          PRODUCT, ["product"]),
    _tool("find_customer_switching",
          "Find customers who stopped buying a product and which product in the same category they bought instead. Use for WHY a product is declining.",
          PRODUCT, ["product"]),
    _tool("get_top_products",
          "Rank products by total revenue. ascending=false gives best sellers (default). ascending=true gives the lowest-selling / worst / least popular products.",
          {"n": {"type": "integer", "description": "How many products. Default 5."},
           "ascending": {"type": "boolean", "description": "true = lowest sellers first."}}),
    _tool("get_category_performance", "Revenue per category, ranked. Use for which category earns the most or least."),
    _tool("compare_periods", "Compare the latest month with the previous month: revenue, orders and percent change."),
    _tool("forecast_next_month",
          "Predict next month's demand and say what to order more or less of. Use for questions about ordering, stocking, restocking or next month's sales.",
          {"top": {"type": "integer", "description": "How many products to return. Default 8."}}),
    _tool("festival_outlook",
          "Upcoming festivals and the season for the shop's location, with what to stock for them. Use for festival, season, weather or 'what should I stock' questions.",
          {}),
    _tool("check_external_news",
          "Search the web for real recent news about a brand. Returns a short summary and sources.",
          PRODUCT, ["product"]),
]

TOOL_FUNCTIONS = {
    "get_sales_trend": get_sales_trend,
    "find_customer_switching": find_customer_switching,
    "get_top_products": get_top_products,
    "get_category_performance": get_category_performance,
    "compare_periods": compare_periods,
    "forecast_next_month": forecast_next_month,
    "festival_outlook": festival_outlook,
    "check_external_news": check_external_news,
}


def get_tools(allow_news: bool) -> list:
    """The web-news tool is only offered when the user asked for it (checkbox, or the question is about news)."""
    return [t for t in ALL_TOOLS if allow_news or t["function"]["name"] != "check_external_news"]
