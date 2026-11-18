"""
forecast.py - "What should I order next month?"

How it works (plain statistics, no black box, easy to explain in a viva):
  1. Monthly units sold per product (flagged outliers excluded).
  2. A baseline for each product: a weighted average of its last 3 full months
     (recent months count more), plus its recent trend (a straight-line fit over up to
     6 months), damped so a short streak does not run away.
  3. A seasonal and festival multiplier for the target month (see seasonal.py),
     for the shop's own state. If there are 13+ months of history, the shop's own
     same-month pattern from last year is blended in as well.
  4. A safety buffer on top (10%, or 20% when a festival is near), rounded up.

The result is a suggested order per product, with the reasons written in plain words.
"""

import calendar
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

import seasonal

TREND_DAMPING = 0.8
MAX_TREND_SHARE = 0.4  # trend may move the baseline by at most 40%
BUFFER = 0.10
FESTIVAL_BUFFER = 0.20


def _month_floor(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return date(y, m + 1, 1)


def _month_label(d: date) -> str:
    return f"{calendar.month_name[d.month]} {d.year}"


def _units_series(group: pd.DataFrame, first: pd.Period, last: pd.Period) -> pd.Series:
    """Units per month from the product's first sale to the last complete month (gaps are zeros)."""
    monthly = group.groupby(group["date"].dt.to_period("M"))["quantity"].sum()
    start = max(first, monthly.index.min())
    full = pd.period_range(start, last, freq="M")
    return monthly.reindex(full, fill_value=0.0)


def _baseline(series: pd.Series, horizon: int) -> tuple[float, float, float]:
    """Returns (level, monthly_trend, projected_base) for `horizon` months past the last data month."""
    values = series.to_numpy(dtype=float)
    n = len(values)
    if n == 1:
        return values[0], 0.0, values[0]
    recent = values[-3:][::-1]  # newest first
    weights = np.array([0.5, 0.3, 0.2][: len(recent)])
    level = float(np.dot(recent, weights / weights.sum()))
    window = values[-6:]
    slope = float(np.polyfit(np.arange(len(window)), window, 1)[0]) if len(window) >= 3 else float(window[-1] - window[0]) / 2
    steps = sum(TREND_DAMPING**k for k in range(1, horizon + 1))
    move = slope * steps
    cap = level * MAX_TREND_SHARE
    move = max(-cap, min(cap, move))
    return level, slope, max(level + move, 0.0)


def _confidence(series: pd.Series) -> str:
    values = series.to_numpy(dtype=float)
    n = len(values)
    mean = values.mean() if n else 0
    cv = float(values.std() / mean) if mean > 0 else 9
    if n >= 6 and cv < 0.35:
        return "High"
    if n >= 3 and cv < 0.7:
        return "Medium"
    return "Low"


def predict_next_month(df: pd.DataFrame, profile: dict, today: date | None = None, top: int | None = None) -> dict:
    """
    df: cleaned sales rows for one user (outliers already removed).
    Returns a dict ready for the API / the order-list page.
    """
    today = today or seasonal.today_india()
    state = profile.get("state") or ""
    if df is None or df.empty:
        return {"found": False, "message": "No sales data has been uploaded yet."}

    df = df.copy()
    last_date = df["date"].max()
    last_period = last_date.to_period("M")
    warnings: list[str] = []

    # Drop the last month from the fit if it is clearly incomplete (data stops early in the month).
    dim = calendar.monthrange(last_date.year, last_date.month)[1]
    if last_date.day < dim - 3 and df["date"].dt.to_period("M").nunique() > 1:
        df = df[df["date"].dt.to_period("M") < last_period]
        last_period = last_period - 1
        warnings.append(f"The last month in your data ends on {last_date.day} {last_date.strftime('%b')}, so it was left out as incomplete.")

    last_month_start = date(last_period.year, last_period.month, 1)
    target = _add_months(_month_floor(today), 1)
    if target <= last_month_start:  # data is ahead of the calendar (e.g. future-dated sample)
        target = _add_months(last_month_start, 1)
    horizon = (target.year - last_month_start.year) * 12 + target.month - last_month_start.month
    if horizon > 3:
        warnings.append(f"Your data ends in {_month_label(last_month_start)}, {horizon} months before {_month_label(target)}. Upload recent sales for a sharper forecast.")

    data_months = df["date"].dt.to_period("M").nunique()
    span_months = (last_period - df["date"].min().to_period("M")).n + 1
    first_period = df["date"].min().to_period("M")
    same_month_last_year = target.replace(year=target.year - 1)
    use_own_season = span_months >= 13

    rows = []
    for (product, category), group in df.groupby(["product", "category"]):
        series = _units_series(group, first_period, last_period)
        if series.sum() <= 0:
            continue
        level, slope, base = _baseline(series, horizon)
        tags = seasonal.classify_product(product, category)
        mult, reasons = seasonal.demand_multiplier(tags, target, state)

        if use_own_season:
            period = pd.Period(same_month_last_year, freq="M")
            if period in series.index and series.mean() > 0:
                own = float(np.clip(series[period] / series.mean(), 0.6, 1.6))
                mult = (mult + own) / 2
                reasons.append(f"Your own sales in {_month_label(same_month_last_year)} were {round((own - 1) * 100):+d}% vs your average")

        forecast = base * mult
        last_units = float(series.iloc[-1])
        has_festival = any(r for r in reasons if "sell about" in r and ("on " in r))
        buffer = FESTIVAL_BUFFER if has_festival else BUFFER
        suggested = math.ceil(forecast * (1 + buffer)) if forecast > 0 else 0

        why = []
        if len(series) >= 3 and level > 0:
            rel = slope / level
            if rel > 0.04:
                why.append(f"Selling more each month (about {slope:.0f} extra units a month)")
            elif rel < -0.04:
                why.append(f"Selling less each month (about {abs(slope):.0f} fewer units a month)")
            else:
                why.append("Steady sales")
        elif len(series) < 3:
            why.append(f"Only {len(series)} month{'s' if len(series) > 1 else ''} of history, so this is a rough guess")
        why.extend(reasons)

        change = (forecast - last_units) / last_units * 100 if last_units > 0 else None
        if change is None:
            action = "Order more" if forecast > 0 else "Keep the same"
        elif change >= 10:
            action = "Order more"
        elif change <= -12:
            action = "Order less"
        else:
            action = "Keep the same"

        recent_prices = group[group["date"].dt.to_period("M") == last_period]["price"]
        price = float(recent_prices.median()) if not recent_prices.empty else float(group["price"].iloc[-1])

        rows.append({
            "product": product,
            "category": category,
            "last_month_units": round(last_units),
            "average_units": round(float(series.mean())),
            "forecast_units": round(forecast),
            "change_pct": None if change is None else round(change),
            "suggested_order": int(suggested),
            "action": action,
            "confidence": _confidence(series),
            "unit_price": round(price, 2),
            "forecast_revenue": round(forecast * price),
            "why": why[:4],
        })

    if not rows:
        return {"found": False, "message": "Not enough sales history to forecast."}

    rows.sort(key=lambda r: r["forecast_revenue"], reverse=True)
    if top:
        rows = rows[:top]

    season = seasonal.season_for(target.month, state)
    return {
        "found": True,
        "target_month": target.strftime("%Y-%m"),
        "target_label": _month_label(target),
        "based_on_months": int(data_months),
        "season": season,
        "total_forecast_revenue": int(sum(r["forecast_revenue"] for r in rows)),
        "products": rows,
        "warnings": warnings,
        "method": "Weighted average of recent months, plus trend, season and nearby festivals.",
    }
