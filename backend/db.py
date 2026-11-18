"""
db.py - One small database layer that works with SQLite (local development)
and PostgreSQL (Neon, production). The rest of the code writes plain SQL with
"?" placeholders and never needs to know which one is underneath.

Everything in the schema is deliberately portable: TEXT ids (uuid), ISO text
timestamps, INTEGER flags, DOUBLE PRECISION numbers.
"""

import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import config

_url = config.DATABASE_URL


def configure(url: str) -> None:
    """Point the app at a different database (used by the tests)."""
    global _url
    _url = url
    reset_pool()


def is_postgres() -> bool:
    return _url.startswith(("postgres://", "postgresql://"))


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")


def _sqlite_path() -> str:
    path = re.sub(r"^sqlite:///", "", _url)
    return path or ":memory:"


class Conn:
    """Thin wrapper giving both drivers the same few methods."""

    def __init__(self, raw, pg: bool):
        self.raw = raw
        self.pg = pg

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.pg else sql

    def query(self, sql: str, params=()) -> list[dict]:
        cur = self.raw.cursor()
        cur.execute(self._sql(sql), tuple(params))
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def one(self, sql: str, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params=()) -> int:
        cur = self.raw.cursor()
        cur.execute(self._sql(sql), tuple(params))
        count = cur.rowcount
        cur.close()
        return count

    def executemany(self, sql: str, rows) -> None:
        cur = self.raw.cursor()
        cur.executemany(self._sql(sql), rows)
        cur.close()


# Opening a Postgres connection (TLS + login) costs hundreds of milliseconds on a hosted database
# such as Neon, and one page load runs several queries. So connections are kept and reused.
_POOL: list[tuple[object, float]] = []   # (raw connection, time it was last used)
_POOL_LOCK = threading.Lock()
_POOL_MAX = 8
_STALE_AFTER = 45  # seconds idle before a connection is tested again (hosts close idle ones)


def _pg_connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(_url, row_factory=dict_row, connect_timeout=15)


def _pg_borrow():
    while True:
        with _POOL_LOCK:
            item = _POOL.pop() if _POOL else None
        if item is None:
            return _pg_connect()
        raw, last_used = item
        try:
            if raw.closed:
                continue
            if time.time() - last_used > _STALE_AFTER:
                raw.execute("SELECT 1")
                raw.rollback()
            return raw
        except Exception:
            try:
                raw.close()
            except Exception:
                pass


def _pg_return(raw, healthy: bool) -> None:
    if healthy and not raw.closed:
        with _POOL_LOCK:
            if len(_POOL) < _POOL_MAX:
                _POOL.append((raw, time.time()))
                return
    try:
        raw.close()
    except Exception:
        pass


def reset_pool() -> None:
    """Close every kept connection (used by the tests when the database changes)."""
    with _POOL_LOCK:
        items, _POOL[:] = list(_POOL), []
    for raw, _ in items:
        try:
            raw.close()
        except Exception:
            pass


@contextmanager
def connection():
    """Borrow a connection, commit on success, roll back on error, then hand it back."""
    if is_postgres():
        raw = _pg_borrow()
        conn = Conn(raw, True)
        healthy = True
        try:
            yield conn
            raw.commit()
        except Exception:
            healthy = False
            try:
                raw.rollback()
                healthy = True  # an ordinary SQL error leaves the connection usable
            except Exception:
                pass
            raise
        finally:
            _pg_return(raw, healthy)
        return

    raw = sqlite3.connect(_sqlite_path(), timeout=30)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    conn = Conn(raw, False)
    try:
        yield conn
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        last_login_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS profiles (
        user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        business_name TEXT,
        business_type TEXT,
        customer_mix TEXT,
        city TEXT,
        state TEXT,
        pincode TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sales (
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        product TEXT NOT NULL,
        category TEXT,
        quantity DOUBLE PRECISION NOT NULL,
        price DOUBLE PRECISION NOT NULL,
        customer_id TEXT,
        region TEXT,
        is_outlier INTEGER NOT NULL DEFAULT 0,
        revenue DOUBLE PRECISION NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sales_user ON sales(user_id)",
    """CREATE TABLE IF NOT EXISTS uploads (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        filename TEXT,
        mode TEXT,
        rows_received INTEGER,
        rows_saved INTEGER,
        report TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_uploads_user ON uploads(user_id)",
    """CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        trace TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id)",
    """CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, created_at)",
]


def init_schema() -> None:
    with connection() as conn:
        for statement in SCHEMA:
            conn.execute(statement)
