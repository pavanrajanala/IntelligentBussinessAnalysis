"""
clean.py - Automatic cleaning pipeline for uploaded sales CSVs.

None of this is AI. It is a fixed set of rules that run the same way every
time. "Automatic" here means the code always runs on upload, with no model
deciding what to do. Every rule reports what it changed, so the dashboard can
show proof that cleaning actually did something.

Expected columns (names are matched loosely, see COLUMN_ALIASES):
    required: date, product, quantity, price
    optional: category, customer_id, region
"""

import re

import pandas as pd

REQUIRED_COLUMNS = ["date", "product", "quantity", "price"]
OPTIONAL_TEXT_COLUMNS = {"category": "Uncategorized", "customer_id": "Unknown", "region": "Unknown"}

# Different people name the same column differently. Map the common variants
# onto the names the rest of the code expects.
COLUMN_ALIASES = {
    "date": ["date", "order_date", "sale_date", "transaction_date", "invoice_date", "day"],
    "product": ["product", "product_name", "item", "item_name", "sku_name"],
    "category": ["category", "product_category", "segment", "department"],
    "quantity": ["quantity", "qty", "units", "units_sold", "quantity_sold"],
    "price": ["price", "unit_price", "rate", "selling_price", "price_per_unit"],
    "customer_id": ["customer_id", "customer", "customer_name", "cust_id", "client_id"],
    "region": ["region", "city", "state", "zone", "area"],
}

# A row is flagged as an outlier when its quantity is more than this many
# times the product's median quantity (with a floor so tiny medians do not
# make every normal order look suspicious).
OUTLIER_MULTIPLIER = 10
OUTLIER_FLOOR = 20


def normalize_text(value) -> str:
    """Same text normalisation for data and for questions typed by the user."""
    return re.sub(r"\s+", " ", str(value)).strip().title()


def load_csv(filepath: str) -> pd.DataFrame:
    """Step 0: read the raw file. Tries UTF-8 first, then Excel-style encodings."""
    last_error = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(filepath, encoding=encoding)
        except UnicodeDecodeError as e:
            last_error = e
        except pd.errors.EmptyDataError:
            raise ValueError("The file is empty.")
    raise ValueError(f"Could not read the file: {last_error}")


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case the headers and rename known aliases to canonical names."""
    df = df.copy()
    df.columns = [re.sub(r"[\s\-]+", "_", str(c).strip().lower()) for c in df.columns]

    rename = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns and alias not in rename:
                rename[alias] = canonical
                break
    return df.rename(columns=rename)


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark rows whose quantity is far above that product's normal quantity.
    Median is robust to a few extreme values, unlike percentile thresholds.
    Re-run whenever data is combined (new uploads change the medians).
    """
    df = df.copy()
    median_qty = df.groupby("product")["quantity"].transform("median")
    threshold = (median_qty * OUTLIER_MULTIPLIER).clip(lower=OUTLIER_FLOOR)
    df["is_outlier"] = df["quantity"] > threshold
    return df


def clean_sales_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Run every cleaning rule in sequence.

    Returns (cleaned dataframe, report dict). Raises ValueError with a
    readable message if the file cannot be used at all.
    """
    report: dict = {"original_row_count": int(len(df))}
    warnings: list[str] = []

    if df.empty:
        raise ValueError("The file has no rows.")

    df = _standardise_columns(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found: {', '.join(df.columns)}. "
            f"Required: {', '.join(REQUIRED_COLUMNS)}."
        )

    # Optional columns: create them if absent so every later step can rely on them.
    for col, default in OPTIONAL_TEXT_COLUMNS.items():
        if col not in df.columns:
            df[col] = default
            warnings.append(f"Column '{col}' not found, filled with '{default}'.")

    # Only keep the columns we understand, in a predictable order.
    df = df[["date", "product", "category", "quantity", "price", "customer_id", "region"]].copy()

    # Rule 1: normalise text ("colgate " and "COLGATE" become "Colgate").
    # Missing text is replaced by a default instead of becoming the string "Nan".
    for col in ["product", "category", "customer_id", "region"]:
        default = OPTIONAL_TEXT_COLUMNS.get(col)
        blank = df[col].isna() | (df[col].astype(str).str.strip() == "")
        df[col] = df[col].astype(str).map(normalize_text)
        if default is not None:
            df.loc[blank, col] = default
        else:
            df.loc[blank, col] = pd.NA
    rows_before = len(df)
    df = df.dropna(subset=["product"])
    report["rows_missing_product_dropped"] = int(rows_before - len(df))

    # Rule 2: parse dates. Indian files are usually day-first (05/03/2026 = 5 March).
    # ISO dates (2026-09-12) are unambiguous and must be read as-is; only
    # the remaining formats (05/03/2026, 5 Mar 2026) are read day-first.
    raw_dates = df["date"].astype(str).str.strip()
    parsed = pd.to_datetime(raw_dates, errors="coerce", format="ISO8601")
    leftover = parsed.isna()
    if leftover.any():
        parsed[leftover] = pd.to_datetime(raw_dates[leftover], errors="coerce", dayfirst=True, format="mixed")
    df["date"] = parsed
    bad_dates = int(df["date"].isna().sum())
    report["rows_with_unparseable_dates"] = bad_dates
    df = df.dropna(subset=["date"])

    # Rule 3: force numbers to be numbers ("1,200" or "abc" would otherwise break maths).
    for col in ["quantity", "price"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")

    # Rule 4: rows with no usable price cannot produce revenue, so drop them.
    rows_before = len(df)
    df = df[df["price"].notna() & (df["price"] > 0)]
    report["rows_with_invalid_price_dropped"] = int(rows_before - len(df))

    # Rule 5: negative or zero quantities are returns / data-entry errors.
    rows_before = len(df)
    df = df[df["quantity"].isna() | (df["quantity"] > 0)]
    report["rows_with_invalid_quantity_dropped"] = int(rows_before - len(df))

    # Rule 6: fill missing quantity with the median quantity of that product
    # (more realistic than one global average), falling back to the global median.
    missing_qty = int(df["quantity"].isna().sum())
    report["rows_with_missing_quantity_filled"] = missing_qty
    df["quantity"] = df.groupby("product")["quantity"].transform(lambda x: x.fillna(x.median()))
    df["quantity"] = df["quantity"].fillna(df["quantity"].median())
    df = df.dropna(subset=["quantity"])  # nothing at all was usable

    # Rule 7: remove exact duplicate rows.
    rows_before = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = int(rows_before - len(df))

    if df.empty:
        raise ValueError("No usable rows were left after cleaning. Check the date, quantity and price columns.")

    # Rule 8: flag outliers instead of silently trusting or deleting them.
    df = flag_outliers(df)
    report["outliers_flagged"] = int(df["is_outlier"].sum())

    # Rule 9: revenue per row, used everywhere downstream.
    df["revenue"] = (df["quantity"] * df["price"]).round(2)

    df = df.sort_values("date").reset_index(drop=True)

    report["final_row_count"] = int(len(df))
    report["date_range"] = {"start": df["date"].min().strftime("%Y-%m-%d"), "end": df["date"].max().strftime("%Y-%m-%d")}
    report["products"] = int(df["product"].nunique())
    report["customers"] = int(df["customer_id"].nunique())
    report["warnings"] = warnings

    return df, report


if __name__ == "__main__":
    # Run directly to test cleaning on its own:  python clean.py
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_sales.csv")
    raw = load_csv(path)
    cleaned, report = clean_sales_data(raw)
    print("CLEANING REPORT")
    for k, v in report.items():
        print(f"  {k}: {v}")
    print("\nOUTLIERS FLAGGED")
    print(cleaned[cleaned["is_outlier"]])
