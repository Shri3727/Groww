#!/usr/bin/env python3
"""Ingestion CLI: load → chunk → embed/upsert."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import load_settings
from src.ingest.chunk import run_chunk
from src.ingest.load import run_load
from src.ingest.upsert import run_embed_and_upsert


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ingestion phases")
    parser.add_argument(
        "--phase",
        choices=["load", "chunk", "embed", "all"],
        required=True,
        help="Ingestion phase to run (embed includes Chroma upsert)",
    )
    args = parser.parse_args()

    settings = load_settings()
    print(f"[ingest] sources={len(settings['sources'])}")

    if args.phase in {"load", "all"}:
        results = run_load(settings)
        failed = [r for r in results if not r.get("ok")]
        if failed:
            print(f"[ingest] load finished with {len(failed)} failure(s)")
            if args.phase == "load":
                return 1

    if args.phase in {"chunk", "all"}:
        run_chunk(settings)

    if args.phase in {"embed", "all"}:
        run_embed_and_upsert(settings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
