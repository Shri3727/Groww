"""Phase 1: scrape allowlisted Groww pages into data/raw/."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.config import allowlisted_urls, load_settings, resolve_path

IST = ZoneInfo("Asia/Kolkata")


def _now_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def _extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    content = "\n".join(lines)
    return title, content


def _fetch_url(url: str, *, timeout: int, user_agent: str, retries: int) -> tuple[int, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    last_error: Exception | None = None
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.status_code, response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def load_source(source: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    allowed = allowlisted_urls(settings)
    url = source["url"]
    if url not in allowed:
        raise ValueError(f"URL not in allowlist: {url}")

    scrape_cfg = settings.get("scraping", {})
    timeout = int(scrape_cfg.get("timeout_seconds", 30))
    retries = int(scrape_cfg.get("retry_count", 1))
    user_agent = scrape_cfg.get(
        "user_agent",
        "Mozilla/5.0 (compatible; NextLeapFAQ/1.0)",
    )

    status, html = _fetch_url(url, timeout=timeout, user_agent=user_agent, retries=retries)
    title, content = _extract_text(html)

    return {
        "page_id": source["id"],
        "name": source.get("name"),
        "page_type": source.get("page_type"),
        "url": url,
        "fetched_at": _now_iso(),
        "title": title,
        "content": content,
        "http_status": status,
        "content_length": len(content),
    }


def save_raw_document(doc: dict[str, Any], raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"{doc['page_id']}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return out_path


def run_load(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = settings or load_settings()
    raw_dir = resolve_path(cfg.get("paths", {}).get("raw_dir", "data/raw"))
    delay = float(cfg.get("scraping", {}).get("delay_seconds", 1.0))

    results: list[dict[str, Any]] = []
    sources = cfg["sources"]

    for index, source in enumerate(sources):
        page_id = source["id"]
        print(f"[load] ({index + 1}/{len(sources)}) fetching {page_id} ...")
        try:
            doc = load_source(source, cfg)
            path = save_raw_document(doc, raw_dir)
            print(
                f"[load] saved {path.name} "
                f"(chars={doc['content_length']}, status={doc['http_status']})"
            )
            results.append({"page_id": page_id, "ok": True, "path": str(path), "doc": doc})
        except Exception as exc:  # noqa: BLE001 - continue other pages
            error_doc = {
                "page_id": page_id,
                "name": source.get("name"),
                "page_type": source.get("page_type"),
                "url": source["url"],
                "fetched_at": _now_iso(),
                "title": "",
                "content": "",
                "http_status": None,
                "content_length": 0,
                "error": str(exc),
            }
            path = save_raw_document(error_doc, raw_dir)
            print(f"[load] ERROR {page_id}: {exc} (wrote {path.name})")
            results.append({"page_id": page_id, "ok": False, "path": str(path), "error": str(exc)})

        if index < len(sources) - 1 and delay > 0:
            time.sleep(delay)

    ok_count = sum(1 for r in results if r["ok"] and r.get("doc", {}).get("content_length", 0) > 0)
    print(f"[load] done: {ok_count}/{len(sources)} pages with content")
    return results


if __name__ == "__main__":
    run_load()
