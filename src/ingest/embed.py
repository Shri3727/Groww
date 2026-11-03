"""Shared embedding helper (ingestion + query)."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from src.config import load_settings


@lru_cache(maxsize=2)
def get_embedder(model_name: str):
    from sentence_transformers import SentenceTransformer

    print(f"[embed] loading model: {model_name}")
    return SentenceTransformer(model_name)


def get_configured_model_name(settings: dict | None = None) -> str:
    cfg = settings or load_settings()
    return cfg.get("embedding", {}).get("model", "sentence-transformers/all-MiniLM-L6-v2")


def embed_texts(
    texts: Sequence[str],
    *,
    model_name: str | None = None,
    settings: dict | None = None,
    batch_size: int = 32,
) -> list[list[float]]:
    name = model_name or get_configured_model_name(settings)
    model = get_embedder(name)
    vectors = model.encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=len(texts) > 16,
        normalize_embeddings=True,
    )
    return [vec.tolist() for vec in vectors]
