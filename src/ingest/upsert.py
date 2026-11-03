"""Phase 3: embed chunks and upsert into ChromaDB."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import chromadb

from src.config import load_settings, resolve_path
from src.ingest.chunk import load_all_chunks
from src.ingest.embed import embed_texts, get_configured_model_name

IST = ZoneInfo("Asia/Kolkata")


def get_chroma_collection(settings: dict[str, Any] | None = None, *, reset: bool = False):
    cfg = settings or load_settings()
    vdb = cfg.get("vector_db", {})
    persist_dir = str(resolve_path(vdb.get("persist_dir", "chroma")))
    collection_name = vdb.get("collection", "mf_faq")

    client = chromadb.PersistentClient(path=persist_dir)
    if reset:
        try:
            client.delete_collection(collection_name)
            print(f"[upsert] deleted existing collection: {collection_name}")
        except Exception:  # noqa: BLE001
            pass
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def run_embed_and_upsert(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = settings or load_settings()
    chunks = load_all_chunks(cfg)
    if not chunks:
        raise FileNotFoundError("No chunks found. Run --phase chunk first.")

    model_name = get_configured_model_name(cfg)
    # Store clean chunk text as the document; embed a richer string for retrieval.
    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    embed_inputs = []
    for c in chunks:
        parts = [p for p in (c.get("name"), c.get("section"), c.get("text")) if p]
        embed_inputs.append("\n".join(parts))

    print(f"[embed] embedding {len(texts)} chunks with {model_name}")
    vectors = embed_texts(embed_inputs, model_name=model_name, settings=cfg)
    dim = len(vectors[0]) if vectors else 0

    embeddings_dir = resolve_path(cfg.get("paths", {}).get("embeddings_dir", "data/embeddings"))
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "model": model_name,
        "dim": dim,
        "count": len(ids),
        "built_at": datetime.now(IST).isoformat(timespec="seconds"),
        "items": [{"chunk_id": cid, "dim": dim} for cid in ids],
    }
    manifest_path = embeddings_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[embed] wrote {manifest_path}")

    print("[upsert] writing to ChromaDB ...")
    _, collection = get_chroma_collection(cfg, reset=True)

    metadatas = []
    for c in chunks:
        meta = {
            "source_url": c.get("source_url") or "",
            "scraped_at": c.get("scraped_at") or "",
            "page_id": c.get("page_id") or "",
            "strategy_id": c.get("strategy_id") or "",
            "page_type": c.get("page_type") or "",
            "name": c.get("name") or "",
            "section": c.get("section") or "",
        }
        metadatas.append(meta)

    # Chroma has batch limits; upsert in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        sl = slice(i, i + batch_size)
        collection.upsert(
            ids=ids[sl],
            documents=texts[sl],
            embeddings=vectors[sl],
            metadatas=metadatas[sl],
        )

    count = collection.count()
    summary = {
        "collection": cfg.get("vector_db", {}).get("collection", "mf_faq"),
        "count": count,
        "embedding_model": model_name,
        "persist_dir": str(resolve_path(cfg.get("vector_db", {}).get("persist_dir", "chroma"))),
        "dim": dim,
        "built_at": datetime.now(IST).isoformat(timespec="seconds"),
    }
    meta_dir = resolve_path(cfg.get("paths", {}).get("vector_meta_dir", "data/vector_meta"))
    meta_dir.mkdir(parents=True, exist_ok=True)
    summary_path = meta_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"[upsert] collection count={count}; wrote {summary_path}")
    return summary
