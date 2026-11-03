"""Phase 2: chunk raw pages into inspectable JSONL artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.config import load_settings, resolve_path

STRATEGY_ID_HEADING = "heading_aware_v1"
STRATEGY_ID_FIXED = "fixed_size_v1"

# Lines / blocks that are Groww chrome, not scheme facts
_NOISE_PREFIXES = (
    "stocks",
    "invest in stocks",
    "f&o",
    "trade in futures",
    "download the app",
    "vaishnavi tech park",
    "© 2016",
    "version:",
    "share market",
    "top gainers",
    "top losers",
    "most traded",
    "others:",
    "contact us",
    "help & support",
    "mutual funds\n:",
)

_SECTION_HEADERS = [
    r"expense ratio",
    r"exit load",
    r"min\.?\s*for\s*sip",
    r"minimum (?:sip|investments?|investment)",
    r"fund size(?:\s*\(aum\))?",
    r"fund benchmark",
    r"scheme information document",
    r"investment objective",
    r"about",
    r"fund management",
    r"holdings",
    r"returns and rankings",
    r"tax(?:ation| implication)?",
    r"stamp duty",
    r"risk(?:ometer)?",
    r"lock[- ]?in",
    r"understand terms",
    r"exit load, stamp duty and tax",
]

_HEADER_RE = re.compile(
    r"^(?:" + "|".join(_SECTION_HEADERS) + r")\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _clean_content(text: str) -> str:
    """Drop obvious global nav/footer noise while keeping fund facts."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Drop leading chrome until we hit a fund signal
    start = 0
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(
            key in low
            for key in (
                "min. for sip",
                "expense ratio",
                "nav:",
                "fund size",
                "hdfc large cap",
                "hdfc flexi",
                "hdfc mid cap",
                "hdfc elss",
                "hdfc mutual fund",
                "exit load",
            )
        ):
            start = max(0, i - 2)
            break

    # Drop trailing sitemap/footer-ish content
    end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        low = lines[i].lower()
        if low.startswith("home") and i < len(lines) - 1 and lines[i + 1].strip() == ">":
            end = i
            break
        if low.startswith("vaishnavi tech park") or low.startswith("© 2016"):
            end = i
            break

    cleaned = lines[start:end]
    # Remove repeated ultra-short junk menu tokens when clustered
    filtered: list[str] = []
    for ln in cleaned:
        low = ln.lower()
        if low in {"stocks", "f&o", "etf", "ipo", "mtf", "credit", "more", "see all", "compare"}:
            continue
        if any(low.startswith(p) for p in _NOISE_PREFIXES):
            continue
        filtered.append(ln)
    return "\n".join(filtered)


def _split_heading_aware(text: str, max_size: int) -> list[tuple[str | None, str]]:
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    # Preamble before first header
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if not block:
            continue
        header = match.group(0).strip()
        if len(block) <= max_size:
            sections.append((header, block))
        else:
            # Oversized section → fixed-size pieces, keep header on each
            pieces = _split_fixed(block, max_size, overlap=64)
            for piece in pieces:
                sections.append((header, piece))
    return sections


def _split_fixed(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("chunk size must be > 0")
    overlap = max(0, min(overlap, size - 1))
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = end - overlap
    return chunks


def chunk_document(doc: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    chunk_cfg = settings.get("chunking", {})
    strategy = chunk_cfg.get("strategy", "heading_aware")
    size = int(chunk_cfg.get("size", 512))
    overlap = int(chunk_cfg.get("overlap", 64))

    cleaned = _clean_content(doc.get("content") or "")
    if not cleaned.strip():
        cleaned = (doc.get("content") or "").strip()

    if strategy == "fixed_size":
        pieces = [(None, p) for p in _split_fixed(cleaned, size, overlap)]
        strategy_id = STRATEGY_ID_FIXED
    else:
        pieces = _split_heading_aware(cleaned, max_size=size)
        # Also split any remaining oversized preamble with fixed size
        normalized: list[tuple[str | None, str]] = []
        for section, text in pieces:
            if len(text) > size * 2 and section is None:
                for part in _split_fixed(text, size, overlap):
                    normalized.append((None, part))
            else:
                normalized.append((section, text))
        pieces = normalized
        strategy_id = STRATEGY_ID_HEADING

    chunks: list[dict[str, Any]] = []
    page_id = doc["page_id"]
    for i, (section, text) in enumerate(pieces):
        text = text.strip()
        if len(text) < 40:
            continue
        chunks.append(
            {
                "chunk_id": f"{page_id}_{i:04d}",
                "page_id": page_id,
                "source_url": doc["url"],
                "scraped_at": doc.get("fetched_at"),
                "strategy_id": strategy_id,
                "section": section,
                "text": text,
                "page_type": doc.get("page_type"),
                "name": doc.get("name"),
            }
        )
    return chunks


def run_chunk(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = settings or load_settings()
    raw_dir = resolve_path(cfg.get("paths", {}).get("raw_dir", "data/raw"))
    chunks_dir = resolve_path(cfg.get("paths", {}).get("chunks_dir", "data/chunks"))
    chunks_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict[str, Any]] = []
    per_page: dict[str, int] = {}

    raw_files = sorted(raw_dir.glob("*.json"))
    if not raw_files:
        raise FileNotFoundError(f"No raw files in {raw_dir}. Run --phase load first.")

    for path in raw_files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not doc.get("content"):
            print(f"[chunk] skip {path.name}: empty content")
            continue
        chunks = chunk_document(doc, cfg)
        out = chunks_dir / f"{doc['page_id']}_chunks.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for ch in chunks:
                fh.write(json.dumps(ch, ensure_ascii=False) + "\n")
        per_page[doc["page_id"]] = len(chunks)
        all_chunks.extend(chunks)
        print(f"[chunk] {doc['page_id']}: {len(chunks)} chunks → {out.name}")

    aggregate = chunks_dir / "all_chunks.jsonl"
    with aggregate.open("w", encoding="utf-8") as fh:
        for ch in all_chunks:
            fh.write(json.dumps(ch, ensure_ascii=False) + "\n")

    strategy = cfg.get("chunking", {}).get("strategy", "heading_aware")
    strategy_note = chunks_dir / "_strategy.md"
    strategy_note.write_text(
        f"# Chunking strategy\n\n"
        f"- Active: `{strategy}`\n"
        f"- IDs: `{STRATEGY_ID_HEADING}` / `{STRATEGY_ID_FIXED}`\n"
        f"- Size: {cfg.get('chunking', {}).get('size', 512)}, "
        f"overlap: {cfg.get('chunking', {}).get('overlap', 64)}\n"
        f"- Cleaning: strip Groww nav/footer chrome; split on fact section headers "
        f"(expense ratio, exit load, SIP, benchmark, etc.).\n"
        f"- Total chunks: {len(all_chunks)}\n",
        encoding="utf-8",
    )

    print(f"[chunk] done: {len(all_chunks)} chunks across {len(per_page)} pages")
    return {"total": len(all_chunks), "per_page": per_page, "aggregate": str(aggregate)}


def load_all_chunks(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = settings or load_settings()
    chunks_dir = resolve_path(cfg.get("paths", {}).get("chunks_dir", "data/chunks"))
    aggregate = chunks_dir / "all_chunks.jsonl"
    if aggregate.exists():
        chunks = []
        with aggregate.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
        return chunks

    chunks = []
    for path in sorted(chunks_dir.glob("*_chunks.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
    return chunks
