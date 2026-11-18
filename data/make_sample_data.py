"""
Generates data/sample_sales.csv: realistic FMCG sales for a small Indian retailer.

Built-in story (so the demo has something to discover):
  - Colgate sales fall from May onwards because half its regular customers
    switch to Pepsodent.
  - Tata Tea and Lays grow steadily.
  - The file also contains deliberate "dirty" rows (messy names, duplicates,
    missing quantities, a bad date, an extreme order) so the cleaning report
    has real work to show.

Run:  python make_sample_data.py
"""

import csv
import os
import random
from datetime import date

random.seed(42)

PRODUCTS = {
    # name: (category, price)
    "Colgate": ("Oral Care", 95),
    "Pepsodent": ("Oral Care", 88),
    "Closeup": ("Oral Care", 92),
    "Sensodyne": ("Oral Care", 165),
    "Tata Tea": ("Beverages", 140),
    "Red Label": ("Beverages", 125),
    "Bru Coffee": ("Beverages", 210),
    "Lays": ("Snacks", 20),
    "Kurkure": ("Snacks", 20),
    "Parle-G": ("Snacks", 10),
    "Dove": ("Personal Care", 62),
    "Lux": ("Personal Care", 38),
}
REGIONS = ["Chennai", "Coimbatore", "Madurai", "Trichy"]
CUSTOMERS = [f"C{str(i).zfill(3)}" for i in range(1, 61)]
MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9]  # Jan to Sep 2026
YEAR = 2026

# Customers 1-30 are the "regular Colgate buyers".
COLGATE_LOYALISTS = set(CUSTOMERS[:30])
SWITCHERS = set(CUSTOMERS[:15])  # half of them leave Colgate from May


def month_rows(month):
    rows = []
    for cust in CUSTOMERS:
        region = REGIONS[int(cust[1:]) % len(REGIONS)]
        # Each customer places 3-6 orders a month.
        for _ in range(random.randint(3, 6)):
            day = random.randint(1, 28)
            d = date(YEAR, month, day)

            if cust in COLGATE_LOYALISTS and random.random() < 0.55:
                product = "Colgate"
                if cust in SWITCHERS and month >= 5:
                    product = "Pepsodent"
            else:
                weights = {p: 1.0 for p in PRODUCTS}
                weights["Tata Tea"] += 0.25 * month  # growing
                weights["Lays"] += 0.2 * month  # growing
                weights["Colgate"] = 0.3 if month >= 5 else 0.7
                product = random.choices(list(weights), weights=list(weights.values()))[0]

            category, price = PRODUCTS[product]
            qty = random.randint(1, 6) if price > 50 else random.randint(3, 15)
            rows.append([d.isoformat(), product, category, qty, price, cust, region])
    return rows


def main():
    rows = []
    for m in MONTHS:
        rows.extend(month_rows(m))
    random.shuffle(rows)

    # ----- deliberate dirt for the cleaning pipeline -----
    dirty = []
    for r in rows:
        dirty.append(list(r))

    # messy names / spacing
    for i in random.sample(range(len(dirty)), 25):
        dirty[i][1] = random.choice([dirty[i][1].lower(), dirty[i][1].upper(), f" {dirty[i][1]} "])
    # missing quantities
    for i in random.sample(range(len(dirty)), 12):
        dirty[i][3] = ""
    # exact duplicates
    for i in random.sample(range(len(dirty)), 10):
        dirty.append(list(dirty[i]))
    # unparseable date
    dirty[5][0] = "not a date"
    # extreme order (a typo like 500 instead of 5)
    dirty[17][3] = 500

    out = os.path.join(os.path.dirname(__file__), "sample_sales.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "product", "category", "quantity", "price", "customer_id", "region"])
        w.writerows(dirty)
    print(f"Wrote {len(dirty)} rows to {out}")


if __name__ == "__main__":
    main()
