"""
repo.py - Everything that reads or writes the database: users, shop profiles,
sales (one private set per user), upload history, chat history and usage events.
"""

import json

import pandas as pd

import config
import db
import threading
import time

# ---------- Small in-process caches ----------
# One page load asks for the same user, profile and sales several times. Each lookup on a hosted
# database is a network round trip, so recent results are kept for a few seconds and dropped the moment
# this process changes the data. (If you run several server workers, a change made by one worker is
# seen by the others within the time limit below.)
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_VERSIONS: dict = {}
USER_TTL = 10      # seconds
PROFILE_TTL = 30
SALES_TTL = 30


def _cache_get(key, ttl):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def _cache_put(key, value):
    with _CACHE_LOCK:
        if len(_CACHE) > 2000:
            _CACHE.clear()
        _CACHE[key] = (time.time(), value)
    return value


def _forget(user_id, *kinds):
    with _CACHE_LOCK:
        for kind in kinds:
            _CACHE.pop((kind, user_id), None)
        _VERSIONS[user_id] = _VERSIONS.get(user_id, 0) + 1


def data_version(user_id: str) -> int:
    """Changes whenever this user's sales or profile change; used to cache computed pages."""
    return _VERSIONS.get(user_id, 0)


SALES_COLUMNS = ["date", "product", "category", "quantity", "price", "customer_id", "region", "is_outlier", "revenue"]


# ---------- Users ----------

def create_user(email: str, name: str, password_hash: str) -> dict:
    role = "admin" if email.lower() in config.ADMIN_EMAILS else "user"
    user = {
        "id": db.new_id(),
        "email": email.lower(),
        "name": name,
        "password_hash": password_hash,
        "role": role,
        "is_active": 1,
        "created_at": db.now_iso(),
        "last_login_at": None,
    }
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, password_hash, role, is_active, created_at, last_login_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user["id"], user["email"], user["name"], user["password_hash"], role, 1, user["created_at"], None),
        )
    return user


def get_user_by_email(email: str):
    with db.connection() as conn:
        return conn.one("SELECT * FROM users WHERE email = ?", (email.lower(),))


def get_user(user_id: str):
    hit = _cache_get(("user", user_id), USER_TTL)
    if hit is not None:
        return dict(hit)
    with db.connection() as conn:
        row = conn.one("SELECT * FROM users WHERE id = ?", (user_id,))
    if row:
        _cache_put(("user", user_id), row)
    return dict(row) if row else None


def touch_login(user_id: str) -> None:
    with db.connection() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (db.now_iso(), user_id))


def set_role(user_id: str, role: str) -> None:
    with db.connection() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    _forget(user_id, "user")


def set_active(user_id: str, active: bool) -> None:
    with db.connection() as conn:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id))
    _forget(user_id, "user")


def delete_user(user_id: str) -> None:
    """Removes the account and, through ON DELETE CASCADE, all of its data."""
    with db.connection() as conn:
        # SQLite and Postgres both cascade; delete explicitly too so it works even if FKs are off.
        for table in ("sales", "uploads", "chat_messages", "profiles"):
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE events SET user_id = NULL WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    _forget(user_id, "user", "profile", "sales", "sales_clean", "summary")


# ---------- Profiles ----------

def save_profile(user_id: str, p: dict) -> None:
    values = (
        p.get("business_name"),
        p.get("business_type"),
        json.dumps(p.get("customer_mix") or []),
        p.get("city"),
        p.get("state"),
        p.get("pincode"),
        p.get("latitude"),
        p.get("longitude"),
        db.now_iso(),
    )
    with db.connection() as conn:
        updated = conn.execute(
            "UPDATE profiles SET business_name=?, business_type=?, customer_mix=?, city=?, state=?, pincode=?, "
            "latitude=?, longitude=?, updated_at=? WHERE user_id=?",
            values + (user_id,),
        )
        if not updated:
            conn.execute(
                "INSERT INTO profiles (business_name, business_type, customer_mix, city, state, pincode, "
                "latitude, longitude, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values + (user_id,),
            )
    _forget(user_id, "profile")


def get_profile(user_id: str) -> dict:
    hit = _cache_get(("profile", user_id), PROFILE_TTL)
    if hit is not None:
        return {**hit, "customer_mix": list(hit["customer_mix"])}
    with db.connection() as conn:
        row = conn.one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    if not row:
        return {"customer_mix": []}
    row["customer_mix"] = json.loads(row["customer_mix"] or "[]")
    _cache_put(("profile", user_id), row)
    return {**row, "customer_mix": list(row["customer_mix"])}


# ---------- Sales (private per user) ----------

def read_sales(user_id: str, exclude_outliers: bool = False) -> pd.DataFrame:
    key = ("sales_clean" if exclude_outliers else "sales", user_id)
    hit = _cache_get(key, SALES_TTL)
    if hit is not None:
        return hit.copy()
    df = _read_sales_from_db(user_id, exclude_outliers)
    _cache_put(key, df)
    return df.copy()


def _read_sales_from_db(user_id: str, exclude_outliers: bool) -> pd.DataFrame:
    with db.connection() as conn:
        rows = conn.query(
            "SELECT date, product, category, quantity, price, customer_id, region, is_outlier, revenue "
            "FROM sales WHERE user_id = ?",
            (user_id,),
        )
    if not rows:
        return pd.DataFrame(columns=SALES_COLUMNS)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["is_outlier"] = df["is_outlier"].astype(bool)
    for col in ("quantity", "price", "revenue"):
        df[col] = df[col].astype(float)
    if exclude_outliers:
        df = df[~df["is_outlier"]].reset_index(drop=True)
    return df


def save_sales(user_id: str, df: pd.DataFrame, mode: str = "replace") -> int:
    """
    mode="replace": throw away this user's old rows and store df.
    mode="append" : combine with the stored rows (exact duplicates dropped, outliers re-checked).
    Returns the number of rows stored for the user afterwards.
    """
    from clean import flag_outliers

    if mode == "append":
        old = _read_sales_from_db(user_id, False)  # always the stored truth, never the cache
        if not old.empty:
            df = pd.concat([old, df[SALES_COLUMNS]], ignore_index=True)
            df = df.drop_duplicates(subset=["date", "product", "category", "quantity", "price", "customer_id", "region"])
            df = flag_outliers(df)
            df["revenue"] = (df["quantity"] * df["price"]).round(2)

    out = df[SALES_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        (user_id, r.date, r.product, r.category, float(r.quantity), float(r.price), r.customer_id, r.region,
         int(bool(r.is_outlier)), float(r.revenue))
        for r in out.itertuples(index=False)
    ]
    with db.connection() as conn:
        conn.execute("DELETE FROM sales WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO sales (user_id, date, product, category, quantity, price, customer_id, region, is_outlier, revenue) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    _forget(user_id, "sales", "sales_clean", "summary")
    return len(rows)


def clear_sales(user_id: str) -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM sales WHERE user_id = ?", (user_id,))
    _forget(user_id, "sales", "sales_clean", "summary")


def data_summary(user_id: str) -> dict:
    hit = _cache_get(("summary", user_id), SALES_TTL)
    if hit is not None:
        return dict(hit)
    result = _data_summary_from_db(user_id)
    _cache_put(("summary", user_id), result)
    return dict(result)


def _data_summary_from_db(user_id: str) -> dict:
    with db.connection() as conn:
        row = conn.one(
            "SELECT COUNT(*) AS rows, COUNT(DISTINCT product) AS products, COUNT(DISTINCT category) AS categories, "
            "COUNT(DISTINCT customer_id) AS customers, MIN(date) AS date_start, MAX(date) AS date_end, "
            "SUM(is_outlier) AS outliers FROM sales WHERE user_id = ?",
            (user_id,),
        )
    if not row or not row["rows"]:
        return {"has_data": False}
    return {
        "has_data": True,
        "rows": int(row["rows"]),
        "products": int(row["products"]),
        "categories": int(row["categories"]),
        "customers": int(row["customers"]),
        "date_start": str(row["date_start"])[:10],
        "date_end": str(row["date_end"])[:10],
        "outliers_flagged": int(row["outliers"] or 0),
    }


# ---------- Upload history ----------

def log_upload(user_id: str, filename: str, mode: str, rows_received: int, rows_saved: int, report: dict) -> None:
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO uploads (id, user_id, filename, mode, rows_received, rows_saved, report, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (db.new_id(), user_id, filename, mode, rows_received, rows_saved, json.dumps(report), db.now_iso()),
        )


def list_uploads(user_id: str, limit: int = 20) -> list[dict]:
    with db.connection() as conn:
        rows = conn.query(
            "SELECT id, filename, mode, rows_received, rows_saved, report, created_at FROM uploads "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
    for r in rows:
        r["report"] = json.loads(r["report"] or "{}")
    return rows


# ---------- Chat history ----------

def add_chat(user_id: str, role: str, content: str, trace=None) -> None:
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, trace, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (db.new_id(), user_id, role, content, json.dumps(trace) if trace else None, db.now_iso()),
        )


def recent_chat(user_id: str, limit: int = 50) -> list[dict]:
    with db.connection() as conn:
        rows = conn.query(
            "SELECT role, content, trace, created_at FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
    rows.reverse()
    for r in rows:
        r["trace"] = json.loads(r["trace"]) if r["trace"] else None
    return rows


def clear_chat(user_id: str) -> None:
    with db.connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))


# ---------- Usage events (for the admin page) ----------

def log_event(user_id, kind: str) -> None:
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO events (id, user_id, kind, created_at) VALUES (?, ?, ?, ?)",
            (db.new_id(), user_id, kind, db.now_iso()),
        )
