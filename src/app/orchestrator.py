"""Ask path: guardrails → retrieve → grounded excerpt (or refuse)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any
from src.config import get_repo_root, load_settings, resolve_path
from src.guardrails.checks import (
    GROWW_HELP,
    check,
    closest_allowlisted_url,
    educational_url,
)
from src.retrieve.search import retrieve
from src.runtime import can_persist, ist_tz, retrieval_backend

IST = ist_tz()

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
    "What is the lock-in / tax-saver detail for HDFC ELSS Tax Saver Fund?",
    "What is the exit load of HDFC Mid Cap Fund Direct Growth?",
]


def _load_disclaimer() -> str:
    path = get_repo_root() / "deliverables" / "disclaimer.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return (
        "Facts-only assistant based on official Groww public pages for selected HDFC Mutual Fund "
        "schemes. This is not investment advice. Do not share PAN, Aadhaar, account numbers, OTPs, "
        "emails, or phone numbers."
    )


DISCLAIMER = _load_disclaimer()


def _last_updated(hits: list[dict[str, Any]]) -> str | None:
    dates = []
    for h in hits:
        raw = h.get("scraped_at") or ""
        if raw:
            dates.append(raw[:10])
    return max(dates) if dates else None


def _trim_to_three_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p for p in parts if p][:3]
    return " ".join(kept)


def _pick_best_hit(query: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer factual value chunks over glossary-only definitions when possible."""
    if not hits:
        raise ValueError("no hits")
    q = query.lower()
    wants_value = any(
        k in q
        for k in ("expense", "exit load", "sip", "lock", "benchmark", "riskometer", "minimum")
    )

    def rank(hit: dict[str, Any]) -> tuple:
        text = hit.get("text") or ""
        low = text.lower()
        has_number = bool(re.search(r"\d", text))
        looks_glossary = "a fee payable" in low or "understand terms" in low
        section = (hit.get("section") or "").lower()
        section_match = 1 if section and section.split()[0] in q else 0
        return (
            1 if wants_value and has_number and not looks_glossary else 0,
            section_match,
            float(hit.get("score") or 0),
        )

    return max(hits, key=rank)


def _excerpt_answer(query: str, hits: list[dict[str, Any]]) -> str:
    """Build a short facts-only answer from the best retrieved chunk."""
    top = _pick_best_hit(query, hits)["text"]
    keywords = [
        w
        for w in re.findall(r"[A-Za-z]{3,}", query.lower())
        if w
        not in {
            "what",
            "is",
            "the",
            "of",
            "for",
            "and",
            "how",
            "to",
            "fund",
            "hdfc",
            "direct",
            "growth",
            "plan",
        }
    ]
    lines = [ln.strip() for ln in top.splitlines() if ln.strip()]
    picked: list[str] = []
    for ln in lines:
        low = ln.lower()
        if keywords and any(k in low for k in keywords[:6]):
            picked.append(ln)
        elif re.search(r"\d", ln) and len(picked) < 4:
            picked.append(ln)
        if len(picked) >= 4:
            break
    if not picked:
        picked = lines[:6]

    body = " ".join(picked)
    body = _trim_to_three_sentences(body)
    if len(body) > 420:
        body = body[:417].rstrip() + "..."
    return body


def _is_grounded(hits: list[dict[str, Any]], min_score: float) -> bool:
    if not hits:
        return False
    return float(hits[0].get("score") or 0) >= min_score


def _gap_message(query: str, url: str) -> str:
    return (
        "I could not find that fact in the indexed Groww pages for the selected HDFC schemes. "
        f"Please check the official page: {url}"
    )


def _persist_generation(payload: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    if not can_persist():
        return payload
    out_dir = resolve_path(cfg.get("paths", {}).get("generation_dir", "data/generation"))
    out_dir.mkdir(parents=True, exist_ok=True)
    query_id = payload.get("query_id") or uuid.uuid4().hex
    payload["query_id"] = query_id
    disk = {k: v for k, v in payload.items() if k != "hits"}
    # Keep hits out of PII refuses; include hit ids only when present
    if payload.get("reason") == "pii":
        disk["query"] = payload.get("query")  # already redacted
        disk["hits"] = []
    else:
        disk["hits"] = payload.get("hits") or []
    out_path = out_dir / f"{query_id}.json"
    out_path.write_text(json.dumps(disk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["generation_artifact"] = str(out_path)
    return payload


def ask(question: str, *, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = settings or load_settings()
    guard = check(question, settings=cfg)
    query_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    safe_query = guard.redacted_query if guard.redacted_query is not None else (question or "")

    if guard.action == "refuse":
        citation = guard.educational_url
        answer = (guard.message or "").rstrip()
        if citation and "http" not in answer:
            answer = f"{answer} Source: {citation}."
        payload = {
            "query_id": query_id,
            "query": safe_query,
            "answer": answer,
            "citation_url": citation,
            "last_updated_from_sources": None,
            "refused": True,
            "reason": guard.reason,
            "hits": [],
        }
        return _persist_generation(payload, cfg)

    q = (question or "").strip()
    if re.search(r"capital[-\s]?gains?|download .{0,40}statement|account statement|cas statement", q, re.I):
        citation = GROWW_HELP
        payload = {
            "query_id": query_id,
            "query": safe_query,
            "answer": (
                "Capital-gains and account statements are downloaded from Groww Reports/Statements after login; "
                "do not share PAN, folio, or OTPs here. For consolidated account statements also see AMFI. "
                f"Source: {citation}. Last updated from sources: 2026-11-01."
            ),
            "citation_url": citation,
            "last_updated_from_sources": "2026-11-01",
            "refused": False,
            "reason": "how_to_statement",
            "hits": [],
        }
        return _persist_generation(payload, cfg)

    try:
        retrieval = retrieve(q, settings=cfg, persist=can_persist())
    except Exception as exc:  # noqa: BLE001
        url = educational_url(cfg)
        payload = {
            "query_id": query_id,
            "query": safe_query,
            "answer": (
                "I could not look up that fact right now and will not invent an answer. "
                f"Please try again later or open the official page: {url}"
            ),
            "citation_url": url,
            "last_updated_from_sources": None,
            "refused": True,
            "reason": "backend_error",
            "error": str(exc),
            "hits": [],
        }
        return _persist_generation(payload, cfg)

    hits = retrieval.get("hits") or []
    score_key = "lexical_min_score" if retrieval_backend(cfg) == "lexical" else "min_score"
    min_score = float(cfg.get("retrieval", {}).get(score_key, 0.45 if score_key == "min_score" else 0.12))
    query_id = retrieval.get("query_id") or query_id

    if not _is_grounded(hits, min_score):
        url = closest_allowlisted_url(q, cfg)
        payload = {
            "query_id": query_id,
            "query": safe_query,
            "answer": _gap_message(q, url),
            "citation_url": url,
            "last_updated_from_sources": _last_updated(hits),
            "refused": False,
            "reason": "ungrounded",
            "hits": hits,
            "retrieval_artifact": retrieval.get("artifact_path"),
        }
        return _persist_generation(payload, cfg)

    best = _pick_best_hit(q, hits)
    citation = best.get("source_url") or retrieval.get("citation_url")
    last_updated = _last_updated(hits)
    answer = _excerpt_answer(q, hits)
    if citation and "Source:" not in answer:
        answer = f"{answer} Source: {citation}."
    if last_updated:
        answer = f"{answer} Last updated from sources: {last_updated}."

    payload = {
        "query_id": query_id,
        "query": safe_query,
        "answer": answer,
        "citation_url": citation,
        "last_updated_from_sources": last_updated,
        "refused": False,
        "reason": None,
        "hits": hits,
        "retrieval_artifact": retrieval.get("artifact_path"),
    }
    return _persist_generation(payload, cfg)
