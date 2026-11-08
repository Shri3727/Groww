"""Vercel-safe retrieval: keyword/IDF over committed chunk JSONL (no torch/Chroma)."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any
from src.config import load_settings
from src.ingest.chunk import load_all_chunks
from src.runtime import ist_tz

IST = ist_tz()
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = {
    "what",
    "is",
    "the",
    "of",
    "for",
    "and",
    "how",
    "to",
    "a",
    "an",
    "in",
    "on",
    "do",
    "i",
    "my",
    "please",
    "tell",
    "me",
}


def _tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOP and len(t) > 1]


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    chunks = load_all_chunks()
    df: dict[str, int] = {}
    docs: list[dict[str, Any]] = []
    for chunk in chunks:
        toks = _tokens(" ".join(filter(None, [chunk.get("name"), chunk.get("section"), chunk.get("text")])))
        counts: dict[str, int] = {}
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        for t in counts:
            df[t] = df.get(t, 0) + 1
        docs.append({"chunk": chunk, "tf": counts, "len": max(len(toks), 1)})
    return {"docs": docs, "df": df, "n": max(len(docs), 1)}


def retrieve_lexical(
    query: str,
    *,
    settings: dict[str, Any] | None = None,
    top_k: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    cfg = settings or load_settings()
    k = int(top_k or cfg.get("retrieval", {}).get("top_k", 4))
    q_tokens = _tokens(query)
    q_lower = (query or "").lower()
    idx = _index()
    n = idx["n"]
    scored: list[tuple[float, dict[str, Any]]] = []

    for doc in idx["docs"]:
        chunk = doc["chunk"]
        tf = doc["tf"]
        score = 0.0
        for t in q_tokens:
            if t not in tf:
                continue
            idf = math.log((n + 1) / (idx["df"].get(t, 0) + 1)) + 1.0
            score += (tf[t] / doc["len"]) * idf
        name = (chunk.get("name") or "").lower()
        page_id = (chunk.get("page_id") or "").lower()
        section = (chunk.get("section") or "").lower()
        if "large cap" in q_lower and ("large cap" in name or "large_cap" in page_id):
            score += 0.8
        if ("flexi" in q_lower or "flexicap" in q_lower) and ("flexi" in name or "flexi" in page_id):
            score += 0.8
        if ("elss" in q_lower or "tax saver" in q_lower or "lock" in q_lower) and (
            "elss" in name or "elss" in page_id
        ):
            score += 0.8
        if "mid cap" in q_lower and ("mid cap" in name or "mid_cap" in page_id):
            score += 0.8
        for key in ("expense", "exit", "sip", "benchmark", "riskometer", "lock"):
            if key in q_lower and key in section:
                score += 0.4
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k]
    max_score = top[0][0] if top else 1.0
    hits = []
    for raw, chunk in top:
        hits.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "text": chunk.get("text") or "",
                "score": round(raw / max_score, 4) if max_score else 0.0,
                "distance": None,
                "source_url": chunk.get("source_url") or "",
                "scraped_at": chunk.get("scraped_at") or "",
                "page_id": chunk.get("page_id") or "",
                "section": chunk.get("section") or None,
                "name": chunk.get("name") or None,
            }
        )

    query_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    return {
        "query_id": query_id,
        "query": query,
        "top_k": k,
        "embedding_model": "lexical-idf",
        "collection": "chunks_jsonl",
        "hits": hits,
        "citation_url": hits[0]["source_url"] if hits else None,
        "created_at": datetime.now(IST).isoformat(timespec="seconds"),
    }
