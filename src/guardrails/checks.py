"""Deterministic pre-generation guardrails (PII, advice, returns, scope)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from src.config import load_settings

# PAN: 5 letters, 4 digits, 1 letter
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b")
OTP_RE = re.compile(r"\b(?:otp|one[-\s]?time(?:\s+password)?)\b.{0,12}\b\d{4,8}\b", re.IGNORECASE)
ACCOUNT_RE = re.compile(r"\b(?:account|a/?c|folio)(?:\s*(?:no|number|#))?\s*[:\-]?\s*\d{8,}\b", re.IGNORECASE)

ADVICE_RE = re.compile(
    r"\b("
    r"should i (?:buy|sell|invest|exit|hold)|"
    r"shall i (?:buy|sell|invest)|"
    r"recommend|"
    r"best fund for me|"
    r"which fund (?:should|do) i|"
    r"where should i invest|"
    r"portfolio allocation|"
    r"is it a good (?:time|idea) to (?:buy|sell|invest)|"
    r"can i buy|"
    r"worth (?:buying|investing)"
    r")\b",
    re.IGNORECASE,
)

RETURNS_RE = re.compile(
    r"\b("
    r"compare (?:the )?returns?|"
    r"which (?:fund|one|scheme) (?:has|gave|had|performed) (?:better|higher|more)|"
    r"better returns?|"
    r"higher returns?|"
    r"beat(?:s)? the benchmark|"
    r"xirr|"
    r"which gave higher|"
    r"compute (?:my )?returns?"
    r")\b",
    re.IGNORECASE,
)

OUT_OF_SCOPE_RE = re.compile(
    r"\b("
    r"parag parikh|ppfas|"
    r"sbi (?:small|bluechip|magnum)|"
    r"nippon|"
    r"quant (?:small|mid|flexi)|"
    r"motilal oswal|"
    r"mirae|"
    r"axis (?:bluechip|small)|"
    r"icici prudential (?:bluechip|value)|"
    r"tata digital|"
    r"uti nifty|"
    r"kotak emerging"
    r")\b",
    re.IGNORECASE,
)

GIBBERISH_RE = re.compile(r"^[^\w]+$")
WORD_RE = re.compile(r"[A-Za-z]{3,}")


@dataclass
class GuardResult:
    action: str  # allow | refuse
    reason: Optional[str] = None
    message: Optional[str] = None
    educational_url: Optional[str] = None
    redacted_query: Optional[str] = None


SEBI_INVESTOR_EDU = "https://investor.sebi.gov.in/"
HDFC_FACTSHEETS = "https://www.hdfcfund.com/mutual-funds/factsheets"
GROWW_HELP = "https://groww.in/help"


def educational_url(settings: dict[str, Any] | None = None) -> str:
    cfg = settings or load_settings()
    for source in cfg.get("sources") or []:
        if source.get("page_type") == "amc":
            return source["url"]
    sources = cfg.get("sources") or []
    return sources[0]["url"] if sources else "https://groww.in/mutual-funds/amc/hdfc-mutual-funds"


def closest_allowlisted_url(query: str, settings: dict[str, Any] | None = None) -> str:
    cfg = settings or load_settings()
    q = (query or "").lower()
    keywords = (
        ("elss", "hdfc_elss"),
        ("tax saver", "hdfc_elss"),
        ("large cap", "hdfc_large_cap"),
        ("flexi", "hdfc_flexi_cap"),
        ("mid cap", "hdfc_mid_cap"),
        ("midcap", "hdfc_mid_cap"),
    )
    wanted = None
    for needle, page_id in keywords:
        if needle in q:
            wanted = page_id
            break
    for source in cfg.get("sources") or []:
        if wanted and source.get("id") == wanted:
            return source["url"]
    return educational_url(cfg)


def redact_pii(text: str) -> str:
    redacted = PAN_RE.sub("[REDACTED_PAN]", text)
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = AADHAAR_RE.sub("[REDACTED_AADHAAR]", redacted)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = OTP_RE.sub("[REDACTED_OTP]", redacted)
    redacted = ACCOUNT_RE.sub("[REDACTED_ACCOUNT]", redacted)
    return redacted


def contains_pii(text: str) -> bool:
    return bool(
        PAN_RE.search(text)
        or AADHAAR_RE.search(text)
        or EMAIL_RE.search(text)
        or PHONE_RE.search(text)
        or OTP_RE.search(text)
        or ACCOUNT_RE.search(text)
    )


_FACT_HINTS = (
    "hdfc",
    "expense",
    "sip",
    "exit",
    "elss",
    "fund",
    "benchmark",
    "lock",
    "groww",
    "statement",
    "nav",
    "riskometer",
    "mutual",
)


def _is_gibberish(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    low = stripped.lower()
    if any(hint in low for hint in _FACT_HINTS):
        return False
    if GIBBERISH_RE.match(stripped):
        return True
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    words = WORD_RE.findall(stripped)
    if not words and len(stripped) >= 4:
        return True
    if len(stripped) < 8 and not words:
        return True
    if len(stripped) >= 8 and len(letters) <= 2:
        return True
    if len(words) <= 1 and len(letters) >= 6:
        return True
    return False


def check(question: str, *, settings: dict[str, Any] | None = None) -> GuardResult:
    cfg = settings or load_settings()
    q = question or ""
    edu = educational_url(cfg)
    redacted = redact_pii(q)

    if not q.strip():
        return GuardResult(
            action="refuse",
            reason="empty",
            message="Please rephrase with a factual question about the listed HDFC schemes. Facts-only. No investment advice.",
            educational_url=edu,
            redacted_query=redacted,
        )

    if contains_pii(q):
        return GuardResult(
            action="refuse",
            reason="pii",
            message=(
                "I cannot accept or store personal details such as PAN, Aadhaar, account numbers, "
                "OTPs, emails, or phone numbers. Ask a scheme fact (expense ratio, SIP, exit load) instead."
            ),
            educational_url=edu,
            redacted_query=redacted,
        )

    if ADVICE_RE.search(q):
        return GuardResult(
            action="refuse",
            reason="advice",
            message=(
                "I cannot recommend buying, selling, or allocating a portfolio. "
                "This assistant shares facts only. For investor education see SEBI."
            ),
            educational_url=SEBI_INVESTOR_EDU,
            redacted_query=redacted,
        )

    if RETURNS_RE.search(q):
        return GuardResult(
            action="refuse",
            reason="returns",
            message=(
                "I do not compute or compare fund returns. "
                "Please use the official HDFC Mutual Fund factsheet for published figures."
            ),
            educational_url=HDFC_FACTSHEETS,
            redacted_query=redacted,
        )

    if OUT_OF_SCOPE_RE.search(q) and "hdfc" not in q.lower():
        url = closest_allowlisted_url(q, cfg)
        return GuardResult(
            action="refuse",
            reason="out_of_scope",
            message=(
                "That fund is not in this prototype corpus (HDFC AMC + four HDFC schemes on Groww). "
                "I can only answer facts from the indexed official pages."
            ),
            educational_url=url,
            redacted_query=redacted,
        )

    if _is_gibberish(q):
        return GuardResult(
            action="refuse",
            reason="gibberish",
            message="I could not understand that. Please rephrase a factual question about the listed HDFC schemes.",
            educational_url=edu,
            redacted_query=redacted,
        )

    return GuardResult(action="allow", redacted_query=redacted)
