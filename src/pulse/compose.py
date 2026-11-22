"""Weekly pulse and fee explainer grounded in the review analysis."""

from __future__ import annotations

LAST_CHECKED = "22 Nov 2026"

SOURCE_LINKS = [
    "https://groww.in/pricing",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/sx-demat-account/how-much-does-groww-charge-for-stocks-1",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/sx-margin/what-are-dp-charges-depository-participant-charges-1",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/searchable/when-are-dp-charges-levied",
    "https://groww.in/help/stocks,-f&o,-ipo-&-mtf/discoverable/what-are-the-different-charges-mentioned-in-the-report",
]

EXPLANATION_BULLETS = [
    "Account maintenance charges on Groww are ₹0.",
    "Equity brokerage is ₹20 or 0.1% of the executed order value, whichever is lower. The minimum brokerage is ₹5.",
    "Brokerage is charged per executed equity order. It is not the only amount that can be debited on a trade.",
    "A delivery sell also has DP (depository participant) charges: depository ₹3.50 (₹3.25 for women) plus Groww ₹16.50 when the sell value is ₹100 or more. Groww’s ₹16.50 is ₹0 when the sell value is under ₹100.",
    "GST at 18% applies on brokerage, DP charges, exchange transaction charges, and the other fee lines listed on the Groww pricing page.",
    "STT, stamp duty, exchange transaction charges, and SEBI turnover charges are statutory or exchange charges. The contract note is the record of the exact breakup.",
]


def _words(text: str) -> int:
    return len(text.split())


def weekly_pulse(report: dict) -> str:
    by_id = {theme["id"]: theme for theme in report["themes"]}
    quotes = report["quotes"]
    praise = by_id["short_positive"]["count"]
    support = by_id["support_resolution"]["count"]
    reliability = by_id["app_reliability"]["count"]
    pricing = by_id["pricing_confusion"]["count"]
    orders = by_id["orders_and_withdrawals"]["count"]
    total = report["review_count"]

    text = f"""Weekly product pulse — Groww app
Window: 30 Aug 2026 to 22 Nov 2026. Source: {total} Google Play reviews.

Summary
Top themes: short positive sentiment ({praise} of {total}), app reliability ({reliability}), and support and resolution ({support}). Pricing and charges is the next issue theme ({pricing}). Orders and withdrawals is fifth ({orders}).

Supporting quotes
- "{quotes[0]['text']}" ({quotes[0]['review_id']}, {quotes[0]['date']})
- "{quotes[1]['text']}" ({quotes[1]['review_id']}, {quotes[1]['date']})
- "{quotes[2]['text']}" ({quotes[2]['review_id']}, {quotes[2]['date']})

Key observation
Users who mention money usually say brokerage or charges. Account maintenance is ₹0, so the headline looks free. On an equity sell the debit can also include DP charges, GST, and statutory charges. That gap is the recurring fee confusion in this window.

Actions for product
1. On the sell confirm screen, show brokerage, DP charges, GST, and statutory charges before the user confirms.
2. Keep "₹0 account maintenance" separate from "₹20 or 0.1% equity brokerage" on the order screen.
3. Publish one support snippet for "why is the debit higher than ₹20?" using the fee explainer.
"""
    count = _words(text)
    if count > 250:
        raise ValueError(f"Weekly pulse is {count} words; limit is 250")
    return text.strip() + "\n"


def fee_explainer() -> dict:
    return {
        "fee_name": "Equity brokerage and the separate charges on a sell",
        "bullets": list(EXPLANATION_BULLETS),
        "source_links": SOURCE_LINKS[:2],
        "source_list": list(SOURCE_LINKS),
        "last_checked": LAST_CHECKED,
    }


def build_package(report: dict) -> dict:
    pulse = weekly_pulse(report)
    fee = fee_explainer()
    return {
        "date": "2026-11-22",
        "review_count": report["review_count"],
        "window": report["window"],
        "themes": report["themes"],
        "top_themes": [theme["label"] for theme in report["top_themes"]],
        "quotes": report["quotes"],
        "fee_term_counts": report["fee_term_counts"],
        "identified_fee_issue": report["identified_fee_issue"],
        "weekly_pulse": pulse,
        "weekly_pulse_words": _words(pulse),
        "explanation_bullets": fee["bullets"],
        "source_links": fee["source_links"],
        "source_list": fee["source_list"],
        "last_checked": fee["last_checked"],
        "fee_name": fee["fee_name"],
    }
