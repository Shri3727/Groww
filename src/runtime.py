"""Environment helpers for local vs Vercel."""

from __future__ import annotations

import os
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo


def ist_tz():
    try:
        return ZoneInfo("Asia/Kolkata")
    except Exception:
        return timezone(timedelta(hours=5, minutes=30))


def is_vercel() -> bool:
    return os.getenv("VERCEL") == "1" or os.getenv("NOW_REGION") is not None


def retrieval_backend(settings: dict | None = None) -> str:
    explicit = os.getenv("RETRIEVAL_BACKEND", "").strip().lower()
    if explicit in {"lexical", "chroma"}:
        return explicit
    if is_vercel():
        return "lexical"
    if settings:
        configured = str(settings.get("retrieval", {}).get("backend", "chroma")).lower()
        if configured in {"lexical", "chroma"}:
            return configured
    return "chroma"


def can_persist() -> bool:
    return not is_vercel()
