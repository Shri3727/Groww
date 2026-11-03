#!/usr/bin/env python3
"""Smoke-test retrieval / ask for sample factual queries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.app.orchestrator import ask
from src.retrieve.search import retrieve

DEFAULT_QUERIES = [
    "Expense ratio of HDFC Large Cap Fund Direct Growth",
    "Exit load of HDFC Mid Cap Fund",
    "Minimum SIP for HDFC Flexi Cap",
    "HDFC ELSS lock-in or tax saver",
    "Fund benchmark of HDFC Large Cap",
]


def main() -> int:
    custom = " ".join(sys.argv[1:]).strip()
    queries = [custom] if custom else DEFAULT_QUERIES

    for q in queries:
        print("=" * 72)
        print(f"Q: {q}")
        result = retrieve(q, persist=True)
        print(f"retrieval_id: {result['query_id']} hits={len(result['hits'])}")
        for hit in result["hits"][:3]:
            print(f"  - {hit['score']:.3f} {hit['page_id']} :: {hit['text'][:120].replace(chr(10), ' ')}")
        answer = ask(q)
        print(f"A: {answer['answer'][:300]}")
        print(f"citation: {answer.get('citation_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
