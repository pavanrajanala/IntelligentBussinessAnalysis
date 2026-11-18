"""
database.py - Permanent storage for cleaned sales data.

clean.py's output only lives in memory while a request runs. This file saves
it into a SQLite file so the dashboard, aggregate.py and tools.py all read the
SAME data later, without re-uploading or re-cleaning.
"""

import os
import sqlite3
from contextlib import closing

import pandas as pd

DB_PATH = os.environ.get("SALES_DB_PATH") or os.path.join(os.path.dirname(__file__), "sales.db")
TABLE_NAME = "sales"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def save_cleaned_data(df: pd.DataFrame, replace: bool = True) -> int:
    """
    Save a cleaned dataframe. replace=True wipes the old table first, so a new
    upload always starts fresh instead of piling up duplicate test data.
    """
    mode = "replace" if replace else "append"
    with closing(get_connection()) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists=mode, index=False)
        conn.commit()
    return len(df)


def read_sales() -> pd.DataFrame:
    """Read all sales back out. Returns an empty DataFrame if nothing was uploaded yet."""
    with closing(get_connection()) as conn:
        try:
            df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn, parse_dates=["date"])
        except (pd.errors.DatabaseError, sqlite3.OperationalError):
            return pd.DataFrame()
    if not df.empty and "is_outlier" in df.columns:
        df["is_outlier"] = df["is_outlier"].astype(bool)
    return df


def table_exists() -> bool:
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE_NAME,)
        ).fetchone()
    if row is None:
        return False
    with closing(get_connection()) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    return count > 0


def get_data_summary() -> dict:
    """Small description of what is currently stored (shown in the UI header)."""
    df = read_sales()
    if df.empty:
        return {"has_data": False}
    return {
        "has_data": True,
        "rows": int(len(df)),
        "products": int(df["product"].nunique()),
        "categories": int(df["category"].nunique()),
        "customers": int(df["customer_id"].nunique()),
        "date_start": df["date"].min().strftime("%Y-%m-%d"),
        "date_end": df["date"].max().strftime("%Y-%m-%d"),
        "outliers_flagged": int(df["is_outlier"].sum()) if "is_outlier" in df.columns else 0,
    }


if __name__ == "__main__":
    from clean import clean_sales_data, load_csv

    raw = load_csv(os.path.join(os.path.dirname(__file__), "..", "data", "sample_sales.csv"))
    cleaned, _ = clean_sales_data(raw)
    saved = save_cleaned_data(cleaned)
    print(f"Saved {saved} rows to {DB_PATH}")
    from_db = read_sales()
    print(f"Read back {len(from_db)} rows. Match: {saved == len(from_db)}")
    print(get_data_summary())
