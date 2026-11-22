"""Cluster Groww Play Store reviews into at most five themes."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

REVIEWS_CSV = Path(__file__).resolve().parents[2] / "data" / "reviews" / "groww_reviews.csv"

# Exclusive priority. A review is counted once, in the first matching theme.
# Withdrawals sit with orders so the set stays at five themes.
THEMES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "pricing_confusion",
        "Pricing and charges",
        re.compile(
            r"charg|brokerage|\bfees?\b|\bdp\b|cdsl|\bgst\b|\bamc\b|hidden|commission|pricing",
            re.I,
        ),
    ),
    (
        "support_resolution",
        "Support and resolution",
        re.compile(
            r"support|customer care|no response|not respond|ticket|helpline|customer service|complaint",
            re.I,
        ),
    ),
    (
        "app_reliability",
        "App reliability",
        re.compile(
            r"crash|lag|glitch|bug|slow|freeze|not working|login|otp|\bupdate\b|error|hang|stuck",
            re.I,
        ),
    ),
    (
        "orders_and_withdrawals",
        "Orders and withdrawals",
        re.compile(
            r"\border|execution|chart|intraday|f&o|fno|option|gtt|square off|withdraw|payout|not credited|add money",
            re.I,
        ),
    ),
    (
        "short_positive",
        "Short positive sentiment",
        re.compile(r".", re.S),
    ),
]

FEE_TERMS = [
    ("brokerage", re.compile(r"brokerage", re.I)),
    ("dp_or_cdsl", re.compile(r"\bdp\b|cdsl", re.I)),
    ("gst", re.compile(r"\bgst\b", re.I)),
    ("amc", re.compile(r"\bamc\b", re.I)),
    ("generic_charges", re.compile(r"charg|\bfees?\b|hidden", re.I)),
]


def load_reviews(path: Path | None = None) -> list[dict[str, str]]:
    csv_path = path or REVIEWS_CSV
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def assign_theme(text: str) -> tuple[str, str]:
    for theme_id, label, pattern in THEMES:
        if pattern.search(text or ""):
            return theme_id, label
    return "short_positive", "Short positive sentiment"


# Mid-length reviews that state the issue in the user's own words.
PREFERRED_QUOTES = {
    "app_reliability": "GP2432",
    "support_resolution": "GP2583",
    "pricing_confusion": "GP2713",
}


def _pick_quote(rows: list[dict[str, str]], theme_id: str) -> dict[str, str]:
    preferred = PREFERRED_QUOTES.get(theme_id)
    chosen = next((row for row in rows if row["review_id"] == preferred), None)
    if chosen is None or chosen["theme_id"] != theme_id:
        pool = [
            row
            for row in rows
            if row["theme_id"] == theme_id and 12 <= len(row["text"].split()) <= 28
        ]
        if not pool:
            raise ValueError(f"No quote found for theme {theme_id}")
        chosen = sorted(pool, key=lambda row: row["review_id"])[0]
    return {
        "review_id": chosen["review_id"],
        "date": chosen["date"],
        "theme_id": theme_id,
        "text": chosen["text"].strip(),
    }


def analyze(path: Path | None = None) -> dict:
    reviews = load_reviews(path)
    tagged: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    fee_hits: Counter[str] = Counter()

    for row in reviews:
        theme_id, label = assign_theme(row.get("text") or "")
        labels[theme_id] = label
        counts[theme_id] += 1
        tagged.append({**row, "theme_id": theme_id, "theme_label": label})
        if theme_id == "pricing_confusion":
            text = row.get("text") or ""
            for name, pattern in FEE_TERMS:
                if pattern.search(text):
                    fee_hits[name] += 1

    ranked = [
        {
            "id": theme_id,
            "label": labels[theme_id],
            "count": counts[theme_id],
        }
        for theme_id, _ in counts.most_common()
    ]
    top3 = ranked[:3]
    quote_themes = ["app_reliability", "support_resolution", "pricing_confusion"]
    quotes = [_pick_quote(tagged, theme_id) for theme_id in quote_themes]

    return {
        "review_count": len(reviews),
        "window": {"start": "2026-08-30", "end": "2026-11-22"},
        "source": "Google Play reviews pasted by the user",
        "themes": ranked,
        "top_themes": top3,
        "quotes": quotes,
        "fee_term_counts": dict(fee_hits),
        "identified_fee_issue": (
            "Equity brokerage is being read as the full cost of a trade. "
            "Reviews that mention money most often say brokerage or charges, "
            "and several say the amount taken on a sell is higher than the charge they expected."
        ),
    }
