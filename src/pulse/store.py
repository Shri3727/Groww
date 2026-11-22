"""Approval-gated log: notes append and an email draft. Nothing is sent."""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
NOTES_PATH = _ROOT / "deliverables" / "pulse" / "notes.md"
EMAIL_PATH = _ROOT / "deliverables" / "pulse" / "email_draft.txt"
PULSE_PATH = _ROOT / "deliverables" / "pulse" / "weekly_product_pulse.md"
SOURCES_PATH = _ROOT / "deliverables" / "pulse" / "sources.md"


def email_draft(package: dict) -> str:
    bullets = "\n".join(f"- {line}" for line in package["explanation_bullets"])
    links = "\n".join(package["source_links"])
    return f"""Subject: Weekly Product Pulse + Customer Clarification — Equity brokerage and sell-side charges

Weekly product pulse
{package['weekly_pulse'].strip()}

Fee explanation (reusable support snippet)
{bullets}

Last checked: {package['last_checked']}
{links}

This is a draft. It was not sent.
"""


def notes_entry(package: dict) -> str:
    payload = {
        "date": package["date"],
        "top_themes": package["top_themes"],
        "weekly_pulse": package["weekly_pulse"].strip(),
        "identified_fee_issue": package["identified_fee_issue"],
        "explanation_bullets": package["explanation_bullets"],
        "source_links": package["source_links"],
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"\n\n## {package['date']}\n\n```json\n{body}\n```\n"


def write_pulse_preview(package: dict) -> Path:
    PULSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PULSE_PATH.write_text(package["weekly_pulse"], encoding="utf-8")
    lines = ["# Sources", ""]
    for url in package["source_list"]:
        lines.append(f"- {url}")
    lines.append("")
    lines.append(f"Last checked: {package['last_checked']}")
    lines.append("")
    SOURCES_PATH.write_text("\n".join(lines), encoding="utf-8")
    return PULSE_PATH


def commit_approved(package: dict) -> dict[str, str]:
    """Append the notes entry and write the email draft. Call only after approval."""
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not NOTES_PATH.exists():
        NOTES_PATH.write_text("# Product pulse notes\n", encoding="utf-8")
    with NOTES_PATH.open("a", encoding="utf-8") as handle:
        handle.write(notes_entry(package))
    EMAIL_PATH.write_text(email_draft(package), encoding="utf-8")
    write_pulse_preview(package)
    return {"notes": str(NOTES_PATH), "email_draft": str(EMAIL_PATH)}
