"""
admin.py - Usage statistics for the admin page.

Privacy rule: admins see account details and how much the service is used
(counts, dates, shop type, city). They never see anyone's sales rows or chat text.
"""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

import db


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%S")


def _daily(rows: list[dict], key: str, days: int) -> list[dict]:
    """Fill missing days with zero so charts have a continuous x-axis."""
    counts = {r["d"]: int(r["n"]) for r in rows}
    today = datetime.now(timezone.utc).date()
    out = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append({"date": d, key: counts.get(d, 0)})
    return out


def stats() -> dict:
    with db.connection() as conn:
        one = lambda sql, p=(): conn.one(sql, p)["n"] or 0  # noqa: E731

        total_users = one("SELECT COUNT(*) AS n FROM users WHERE role = 'user'")
        admins = one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")
        suspended = one("SELECT COUNT(*) AS n FROM users WHERE is_active = 0")
        new_7 = one("SELECT COUNT(*) AS n FROM users WHERE role = 'user' AND created_at >= ?", (_days_ago(7),))
        new_30 = one("SELECT COUNT(*) AS n FROM users WHERE role = 'user' AND created_at >= ?", (_days_ago(30),))
        active_7 = one(
            "SELECT COUNT(DISTINCT user_id) AS n FROM events WHERE user_id IS NOT NULL AND created_at >= ?", (_days_ago(7),)
        )
        active_30 = one(
            "SELECT COUNT(DISTINCT user_id) AS n FROM events WHERE user_id IS NOT NULL AND created_at >= ?", (_days_ago(30),)
        )
        with_data = one("SELECT COUNT(DISTINCT user_id) AS n FROM sales")
        sales_rows = one("SELECT COUNT(*) AS n FROM sales")
        uploads = one("SELECT COUNT(*) AS n FROM uploads")
        chats = one("SELECT COUNT(*) AS n FROM events WHERE kind = 'chat'")
        news = one("SELECT COUNT(*) AS n FROM events WHERE kind = 'news'")
        chats_7 = one("SELECT COUNT(*) AS n FROM events WHERE kind = 'chat' AND created_at >= ?", (_days_ago(7),))

        signups = conn.query(
            "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM users WHERE role = 'user' AND created_at >= ? GROUP BY 1",
            (_days_ago(30),),
        )
        questions = conn.query(
            "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM events WHERE kind = 'chat' AND created_at >= ? GROUP BY 1",
            (_days_ago(30),),
        )
        profiles = conn.query(
            "SELECT p.business_type, p.state, p.city, p.customer_mix FROM profiles p JOIN users u ON u.id = p.user_id WHERE u.role = 'user'"
        )

    types = Counter(p["business_type"] or "Not given" for p in profiles)
    states = Counter(p["state"] or "Not given" for p in profiles)
    mix = Counter()
    for p in profiles:
        for m in json.loads(p["customer_mix"] or "[]"):
            mix[m] += 1

    return {
        "totals": {
            "customers": total_users,
            "admins": admins,
            "suspended": suspended,
            "new_7_days": new_7,
            "new_30_days": new_30,
            "active_7_days": active_7,
            "active_30_days": active_30,
            "customers_with_data": with_data,
            "sales_rows": sales_rows,
            "uploads": uploads,
            "questions_asked": chats,
            "questions_7_days": chats_7,
            "news_searches": news,
        },
        "signups_per_day": _daily(signups, "signups", 30),
        "questions_per_day": _daily(questions, "questions", 30),
        "business_types": [{"label": k, "count": v} for k, v in types.most_common()],
        "states": [{"label": k, "count": v} for k, v in states.most_common(10)],
        "customer_mix": [{"label": k, "count": v} for k, v in mix.most_common()],
    }


def list_users(query: str = "", limit: int = 200) -> list[dict]:
    """Account list with per-user usage counts (counts only, never content)."""
    with db.connection() as conn:
        users = conn.query(
            "SELECT u.id, u.name, u.email, u.role, u.is_active, u.created_at, u.last_login_at, "
            "p.business_name, p.business_type, p.city, p.state "
            "FROM users u LEFT JOIN profiles p ON p.user_id = u.id ORDER BY u.created_at DESC"
        )
        rows = {r["user_id"]: r["n"] for r in conn.query("SELECT user_id, COUNT(*) AS n FROM sales GROUP BY user_id")}
        ups = {r["user_id"]: r["n"] for r in conn.query("SELECT user_id, COUNT(*) AS n FROM uploads GROUP BY user_id")}
        qs = {
            r["user_id"]: r["n"]
            for r in conn.query("SELECT user_id, COUNT(*) AS n FROM events WHERE kind = 'chat' AND user_id IS NOT NULL GROUP BY user_id")
        }
    q = query.strip().lower()
    out = []
    for u in users:
        hay = " ".join(str(u.get(k) or "") for k in ("name", "email", "business_name", "city", "state")).lower()
        if q and q not in hay:
            continue
        out.append({
            **u,
            "is_active": bool(u["is_active"]),
            "sales_rows": int(rows.get(u["id"], 0)),
            "uploads": int(ups.get(u["id"], 0)),
            "questions": int(qs.get(u["id"], 0)),
        })
        if len(out) >= limit:
            break
    return out
