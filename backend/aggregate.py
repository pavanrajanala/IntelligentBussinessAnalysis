"""
aggregate.py - Fixed, deterministic calculations behind the dashboard.

No AI here. Each function takes a cleaned DataFrame (one user's sales, flagged
outliers already removed) and returns plain numbers.
"""

import pandas as pd


def _month(df: pd.DataFrame) -> pd.Series:
    return df["date"].dt.to_period("M").astype(str)


def monthly_revenue(df: pd.DataFrame) -> pd.Series:
    return df.groupby(_month(df))["revenue"].sum().sort_index()


def revenue_trend(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return monthly_revenue(df).round(2).rename_axis("month").reset_index().to_dict(orient="records")


def top_products(df: pd.DataFrame, n: int = 5) -> list[dict]:
    if df.empty:
        return []
    n = max(1, min(int(n), 50))
    top = df.groupby("product")["revenue"].sum().sort_values(ascending=False).head(n).round(2)
    return top.reset_index().to_dict(orient="records")


def category_breakdown(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    out = df.groupby("category")["revenue"].sum().sort_values(ascending=False).round(2)
    return out.reset_index().to_dict(orient="records")


def kpi_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total_revenue": 0, "total_orders": 0, "avg_order_value": 0, "growth_pct": None, "latest_month": None}
    total_revenue = float(df["revenue"].sum())
    total_orders = int(len(df))
    monthly = monthly_revenue(df)
    growth = None
    if len(monthly) >= 2 and monthly.iloc[-2] > 0:
        growth = round(((monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2]) * 100, 1)
    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "avg_order_value": round(total_revenue / total_orders, 2),
        "growth_pct": growth,
        "latest_month": monthly.index[-1],
    }


def declining_products(df: pd.DataFrame, threshold_pct: float = -15.0) -> list[dict]:
    """Products whose latest month revenue is at least |threshold_pct| below their first month."""
    if df.empty:
        return []
    df = df.assign(month=_month(df))
    results = []
    for product, group in df.groupby("product"):
        monthly = group.groupby("month")["revenue"].sum().sort_index()
        if len(monthly) < 2 or monthly.iloc[0] == 0:
            continue
        pct = ((monthly.iloc[-1] - monthly.iloc[0]) / monthly.iloc[0]) * 100
        if pct <= threshold_pct:
            results.append({
                "product": product,
                "pct_change": round(float(pct), 1),
                "first_month_revenue": round(float(monthly.iloc[0]), 2),
                "latest_month_revenue": round(float(monthly.iloc[-1]), 2),
            })
    return sorted(results, key=lambda x: x["pct_change"])


def overview(df: pd.DataFrame, top_n: int = 6) -> dict:
    """Everything the Overview page needs, from one read of the data."""
    return {
        "kpi": kpi_summary(df),
        "trend": revenue_trend(df),
        "top": top_products(df, top_n),
        "categories": category_breakdown(df),
        "declining": declining_products(df),
    }
