"""Retrieve top-k chunks: Chroma locally, lexical on Vercel."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
from src.config import load_settings, resolve_path
from src.runtime import can_persist, ist_tz, retrieval_backend

IST = ist_tz()


def _distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, 1.0 - float(distance))


def retrieve(
    query: str,
    *,
    settings: dict[str, Any] | None = None,
    top_k: int | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    cfg = settings or load_settings()
    backend = retrieval_backend(cfg)
    if backend == "lexical":
        from src.retrieve.lexical import retrieve_lexical

        payload = retrieve_lexical(query, settings=cfg, top_k=top_k, persist=False)
        return payload

    k = int(top_k or cfg.get("retrieval", {}).get("top_k", 4))
    from src.ingest.embed import embed_texts, get_configured_model_name
    from src.ingest.upsert import get_chroma_collection

    model_name = get_configured_model_name(cfg)
    collection_name = cfg.get("vector_db", {}).get("collection", "mf_faq")

    query_vec = embed_texts([query], model_name=model_name, settings=cfg)[0]
    _, collection = get_chroma_collection(cfg, reset=False)

    result = collection.query(
        query_embeddings=[query_vec],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict[str, Any]] = []
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    for i, chunk_id in enumerate(ids):
        meta = metas[i] or {}
        hits.append(
            {
                "chunk_id": chunk_id,
                "text": docs[i] or "",
                "score": round(_distance_to_score(dists[i] if i < len(dists) else None), 4),
                "distance": dists[i] if i < len(dists) else None,
                "source_url": meta.get("source_url", ""),
                "scraped_at": meta.get("scraped_at", ""),
                "page_id": meta.get("page_id", ""),
                "section": meta.get("section") or None,
                "name": meta.get("name") or None,
            }
        )

    query_id = datetime.now(IST).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    payload = {
        "query_id": query_id,
        "query": query,
        "top_k": k,
        "embedding_model": model_name,
        "collection": collection_name,
        "hits": hits,
        "citation_url": hits[0]["source_url"] if hits else None,
        "created_at": datetime.now(IST).isoformat(timespec="seconds"),
    }

    if persist and can_persist():
        out_dir = resolve_path(cfg.get("paths", {}).get("retrieval_dir", "data/retrieval"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{query_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        payload["artifact_path"] = str(out_path)

    return payload


def pick_citation(hits: list[dict[str, Any]]) -> str | None:
    if not hits:
        return None
    return hits[0].get("source_url") or None
