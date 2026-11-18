"""
seasonal.py - Season, festival and shop-type knowledge.

Three jobs:
  1. classify_product(): put a product into demand groups ("sweets", "cold_beverages"...)
     using keywords in its name and category, so festival rules can find it.
  2. demand_multiplier(): how much a product's demand is expected to rise or fall in a
     given month (season + festivals near that month, for the shop's state).
  3. build_outlook(): the "what is coming up and what should I stock" view.

Festival dates live in data/festivals.json so they can be updated without touching code.
"""

import calendar
import json
import re
from datetime import date, datetime, timedelta, timezone

import config

IST = timezone(timedelta(hours=5, minutes=30))


def today_india() -> date:
    return datetime.now(IST).date()


# ---------- Product groups ----------

TAG_LABELS = {
    "sweets": "Sweets and chocolates",
    "dry_fruits": "Dry fruits",
    "snacks": "Snacks and biscuits",
    "cold_beverages": "Cold drinks, water and juices",
    "hot_beverages": "Tea and coffee",
    "staples": "Rice, atta, dal and spices",
    "oil_ghee": "Oil and ghee",
    "personal_care": "Personal care",
    "skin_winter": "Moisturisers and lip care",
    "oral_care": "Oral care",
    "home_care": "Cleaning and home care",
    "puja": "Puja items",
    "stationery": "Stationery",
    "baby": "Baby care",
    "health": "Health and hygiene",
    "monsoon": "Rain and mosquito protection",
    "sun": "Sun protection",
    "ready_food": "Noodles and ready foods",
    "dairy": "Milk, curd and butter",
    "bakery": "Bread, cakes and bakery",
}

TAG_KEYWORDS = {
    "sweets": ["sweet", "mithai", "chocolate", "candy", "ladoo", "laddu", "jaggery", "gud", "halwa", "gulab", "cadbury",
               "dairy milk", "kitkat", "5 star", "munch", "perk", "toffee", "eclairs", "soan"],
    "dry_fruits": ["dry fruit", "almond", "badam", "cashew", "kaju", "raisin", "pista", "dates", "walnut", "makhana"],
    "snacks": ["snack", "chips", "namkeen", "kurkure", "lays", "biscuit", "cookie", "bhujia", "popcorn", "parle",
               "wafer", "bingo", "haldiram", "britannia", "oreo", "good day", "marie", "mixture"],
    "cold_beverages": ["cold drink", "soft drink", "soda", "juice", "cola", "pepsi", "coke", "sprite", "thums", "frooti",
                       "maaza", "lassi", "buttermilk", "water", "bisleri", "sharbat", "glucose", "electral", "ors ",
                       "ice cream", "kulfi", "limca", "fanta", "slice", "tang", "rooh afza", "squash"],
    "hot_beverages": ["tea", "coffee", "chai", "bru", "red label", "horlicks", "boost", "cocoa", "bournvita", "nescafe",
                      "taj mahal", "tata tea", "brooke bond", "wagh bakri"],
    "staples": ["rice", "atta", "flour", "wheat", "dal", "pulses", "sugar", "salt", "masala", "spice", "besan", "maida",
                "sooji", "poha", "rava", "sabudana", "toor", "moong", "chana", "rajma", "jeera", "turmeric", "haldi",
                "chilli", "tamarind"],
    "oil_ghee": ["oil", "ghee", "vanaspati", "fortune", "saffola", "dalda"],
    "personal_care": ["soap", "shampoo", "dove", "lux", "lotion", "face wash", "deodorant", "perfume", "talc", "fairness",
                      "beauty", "cosmetic", "lipstick", "himalaya", "ponds", "nivea", "lifebuoy", "dettol soap",
                      "hair oil", "parachute", "kajal", "bindi", "mehendi", "razor", "sanitary", "whisper",
                      "face cream", "hand cream", "fairness cream"],
    "skin_winter": ["moisturi", "cold cream", "lip balm", "vaseline", "body lotion", "petroleum"],
    "oral_care": ["toothpaste", "colgate", "pepsodent", "closeup", "sensodyne", "toothbrush", "mouthwash", "oral"],
    "home_care": ["detergent", "surf", "rin ", "vim", "harpic", "floor cleaner", "lizol", "phenyl", "broom", "mop",
                  "cleaner", "dishwash", "colin", "ariel", "tide", "wheel", "ghadi", "home care"],
    "puja": ["agarbatti", "incense", "camphor", "kapoor", "diya", "candle", "matchbox", "puja", "wick", "rangoli",
             "flower", "kumkum", "sindoor", "coconut", "gulal", "holi colour", "cycle"],
    "stationery": ["notebook", "pen", "pencil", "stationery", "eraser", "geometry", "school bag", "register", "marker",
                   "classmate", "camlin", "paper"],
    "baby": ["diaper", "baby", "cerelac", "pampers", "johnson"],
    "health": ["sanitizer", "mask", "medicine", "vitamin", "bandage", "dettol", "savlon", "vicks", "crocin", "balm",
               "health", "pharma", "tablet", "syrup", "himalaya"],
    "monsoon": ["umbrella", "raincoat", "repellent", "all out", "good knight", "mosquito", "odomos", "hit "],
    "sun": ["sunscreen", "sunglass", "sun cap", "cooler", "sun block"],
    "ready_food": ["noodle", "maggi", "pasta", "soup", "ready to eat", "yippee", "instant", "oats", "cornflakes", "chings"],
    "dairy": ["milk", "curd", "paneer", "butter", "cheese", "amul", "dahi"],
    "bakery": ["bread", "bun", "cake", "rusk", "pav", "pastry", "plum cake"],
}


# A keyword must start at the beginning of a word ("oil" matches "oil" and "oils"
# but not "toilet"), so short words do not cause false matches.
_TAG_PATTERNS = {
    tag: re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w.strip()) for w in words) + ")")
    for tag, words in TAG_KEYWORDS.items()
}


def classify_product(product: str, category: str = "") -> set[str]:
    """Return every demand group a product belongs to (a product can be in several)."""
    text = f"{product} {category}".lower()
    return {tag for tag, pattern in _TAG_PATTERNS.items() if pattern.search(text)}


# ---------- Seasons ----------

SOUTH_EAST_COAST = {"Tamil Nadu", "Puducherry"}
MILD_WINTER_STATES = {"Tamil Nadu", "Puducherry", "Kerala", "Karnataka", "Andhra Pradesh", "Telangana", "Goa",
                      "Andaman and Nicobar Islands", "Lakshadweep"}


def season_for(month: int, state: str = "") -> dict:
    """The season name and a one-line stocking note for a month, adjusted for the shop's state."""
    if state in SOUTH_EAST_COAST:
        if month in (10, 11, 12):
            return {"name": "Northeast monsoon", "note": "Rainy days push tea, coffee, snacks and instant food. Keep umbrellas and mosquito repellents handy."}
        if month in (1, 2):
            return {"name": "Mild winter", "note": "Cool mornings. Hot drinks and moisturisers sell a little more."}
        return {"name": "Hot season", "note": "Cold drinks, water, curd, lassi and ice cream sell the most."}
    if month in (3, 4, 5):
        return {"name": "Summer", "note": "Cold drinks, water, juices, glucose, ice cream and sun protection sell the most."}
    if month in (6, 7, 8, 9):
        return {"name": "Monsoon", "note": "Tea, coffee, snacks, noodles and mosquito protection sell more. Cold drinks slow down."}
    if month == 10:
        return {"name": "Festive season", "note": "Weather cools and festival shopping begins."}
    return {"name": "Winter", "note": "Tea, coffee, dry fruits, ghee, moisturisers and lip care sell more. Cold drinks slow down."}


def season_boosts(month: int, state: str = "") -> dict[str, float]:
    name = season_for(month, state)["name"]
    if name == "Summer" or name == "Hot season":
        base = {"cold_beverages": 1.4 if month in (4, 5) else 1.25, "dairy": 1.15, "sun": 1.3, "hot_beverages": 0.85}
    elif name == "Monsoon":
        base = {"hot_beverages": 1.15, "ready_food": 1.2, "snacks": 1.1, "monsoon": 1.5, "health": 1.1, "cold_beverages": 0.85}
    elif name == "Northeast monsoon":
        base = {"hot_beverages": 1.15, "ready_food": 1.2, "snacks": 1.1, "monsoon": 1.5, "cold_beverages": 0.85}
    elif name == "Winter":
        base = {"hot_beverages": 1.2, "skin_winter": 1.4, "dry_fruits": 1.2, "oil_ghee": 1.1, "cold_beverages": 0.7}
        if state in MILD_WINTER_STATES:  # soften for warmer states
            base = {k: 1 + (v - 1) * 0.4 for k, v in base.items()}
    elif name == "Mild winter":
        base = {"hot_beverages": 1.1, "skin_winter": 1.15}
    else:
        base = {}
    if month in (6, 7):
        base["stationery"] = 1.6  # school reopening
    if month == 4:
        base["stationery"] = 1.3
    return base


# ---------- Festivals ----------

_festival_cache = None


def load_festivals() -> list[dict]:
    global _festival_cache
    if _festival_cache is None:
        with open(config.FESTIVALS_FILE, encoding="utf-8") as f:
            data = json.load(f)["festivals"]
        for fest in data:
            fest["date_obj"] = date.fromisoformat(fest["date"])
        _festival_cache = sorted(data, key=lambda x: x["date_obj"])
    return _festival_cache


def festival_applies(fest: dict, state: str) -> bool:
    regions = fest["regions"]
    return regions == "all" or not state or state in regions


def festivals_between(start: date, end: date, state: str = "") -> list[dict]:
    return [f for f in load_festivals() if start <= f["date_obj"] <= end and festival_applies(f, state)]


def demand_multiplier(tags: set[str], month_start: date, state: str = "") -> tuple[float, list[str]]:
    """
    Expected demand change for a product with these tags during the month starting
    month_start. A festival counts if it falls in the month, or its stock-up window
    (lead days) reaches into the month. Returns (multiplier, plain-English reasons).
    """
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
    factor = 1.0
    reasons: list[str] = []

    sb = season_boosts(month_start.month, state)
    season = season_for(month_start.month, state)["name"]
    for tag in tags:
        f = sb.get(tag)
        if f and abs(f - 1) >= 0.05:
            factor *= f
            reasons.append(f"{season}: {TAG_LABELS[tag].lower()} {'sell about' if f > 1 else 'usually sell'} "
                           f"{abs(round((f - 1) * 100))}% {'more' if f > 1 else 'less'}")

    best = 1.0
    best_reason = ""
    for fest in load_festivals():
        if not festival_applies(fest, state):
            continue
        window_start = fest["date_obj"] - timedelta(days=fest["lead_days"])
        if window_start <= month_end and fest["date_obj"] >= month_start:
            for tag in tags:
                f = fest["boost"].get(tag)
                if f and f > best:
                    best = f
                    when = f"{fest['date_obj'].day} {fest['date_obj'].strftime('%b')}"
                    best_reason = f"{fest['name']} on {when}: {TAG_LABELS[tag].lower()} sell about {round((f - 1) * 100)}% more"
    if best > 1:
        factor *= best
        reasons.append(best_reason)

    return min(max(factor, 0.6), 1.8), reasons


# ---------- Outlook for the shop ----------

BUSINESS_TYPES = [
    "Kirana / general store",
    "Supermarket",
    "Convenience store",
    "Pharmacy / medical store",
    "Bakery and sweets",
    "Cafe / tea stall",
    "Restaurant / dhaba",
    "Stationery and gifts",
    "Fruits and vegetables",
    "Wholesale / distributor",
    "Other",
]

CUSTOMER_TYPES = {
    "families": "Families",
    "students": "Students",
    "office": "Office workers",
    "tourists": "Tourists and travellers",
    "seniors": "Senior citizens",
    "walkin": "Mixed walk-in customers",
}

CUSTOMER_IDEAS = {
    "students": ("snacks", "Many of your customers are students: keep noodles, biscuits, energy drinks and stationery in front."),
    "office": ("ready_food", "Office workers buy quick items: ready foods, tea and coffee sachets, snacks and water."),
    "families": ("staples", "Families buy in larger quantities: staples, cleaning and personal care sell steadily."),
    "tourists": ("cold_beverages", "Travellers want water, cold drinks, snacks, sun protection and phone accessories."),
    "seniors": ("health", "Senior citizens buy health and hygiene items, glucose, tea and milk products regularly."),
    "walkin": ("snacks", "Mixed walk-in customers favour impulse items near the counter: chocolates, snacks and cold drinks."),
}

BUSINESS_FOCUS = {
    "Pharmacy / medical store": ["health", "baby", "personal_care", "skin_winter"],
    "Bakery and sweets": ["sweets", "bakery", "dry_fruits", "dairy"],
    "Cafe / tea stall": ["hot_beverages", "snacks", "bakery", "dairy"],
    "Restaurant / dhaba": ["staples", "oil_ghee", "dairy"],
    "Stationery and gifts": ["stationery", "sweets", "puja"],
}


def your_products_for(df, tag: str, limit: int = 4) -> list[str]:
    """The shop's own best-selling products that belong to a demand group."""
    if df is None or df.empty:
        return []
    cache = df.attrs.setdefault("_tags", {})
    totals = df.groupby(["product", "category"])["quantity"].sum().sort_values(ascending=False)
    found = []
    for (product, category), _ in totals.items():
        key = (product, category)
        if key not in cache:
            cache[key] = classify_product(product, category)
        if tag in cache[key]:
            found.append(product)
        if len(found) >= limit:
            break
    return found


def build_outlook(df, profile: dict, today: date | None = None, horizon_days: int = 75) -> dict:
    """What season is it, which festivals are close, and what should this shop stock for them."""
    today = today or today_india()
    state = profile.get("state") or ""
    season = season_for(today.month, state)
    next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    next_season = season_for(next_month_start.month, state)

    upcoming = []
    for fest in festivals_between(today, today + timedelta(days=horizon_days), state):
        days_away = (fest["date_obj"] - today).days
        stock_by = fest["date_obj"] - timedelta(days=fest["lead_days"])
        items = []
        for tag, factor in sorted(fest["boost"].items(), key=lambda kv: -kv[1]):
            if factor < 1.15:
                continue
            mine = your_products_for(df, tag)
            items.append({
                "group": TAG_LABELS[tag],
                "boost_pct": round((factor - 1) * 100),
                "your_products": mine,
                "ideas": [] if mine else fest["ideas"].get(tag, []),
            })
        # Ideas for groups not covered by the boost list, shown as "worth adding".
        extra = []
        for tag, ideas in fest["ideas"].items():
            if ideas and not any(i["group"] == TAG_LABELS.get(tag) for i in items):
                extra.extend(ideas)
        upcoming.append({
            "name": fest["name"],
            "date": fest["date"],
            "days_away": days_away,
            "stock_by": stock_by.isoformat(),
            "stock_now": stock_by <= today,
            "approx": fest["approx"],
            "note": fest["note"],
            "items": items[:5],
            "other_ideas": extra[:4],
        })

    tips = []
    for key in profile.get("customer_mix") or []:
        idea = CUSTOMER_IDEAS.get(key)
        if idea:
            tips.append(idea[1])
    focus = BUSINESS_FOCUS.get(profile.get("business_type") or "")
    if focus:
        tips.append("For a " + (profile.get("business_type") or "").lower() + ", the groups to watch are "
                    + ", ".join(TAG_LABELS[t].lower() for t in focus) + ".")

    return {
        "today": today.isoformat(),
        "state": state,
        "season": season,
        "next_month_season": next_season,
        "upcoming": upcoming,
        "tips": tips[:4],
    }


INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
    "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
