"""Shared embedding helper (ingestion + query)."""

from __future__ import annotations

import os
import threading
from typing import Sequence

from src.config import load_settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

_lock = threading.Lock()
_model = None
_loaded_name: str | None = None


def get_configured_model_name(settings: dict | None = None) -> str:
    cfg = settings or load_settings()
    return cfg.get("embedding", {}).get("model", "sentence-transformers/all-MiniLM-L6-v2")


def get_embedder(model_name: str):
    global _model, _loaded_name
    with _lock:
        if _model is not None and _loaded_name == model_name:
            return _model
        from sentence_transformers import SentenceTransformer

        print(f"[embed] loading model once on cpu: {model_name}")
        _model = SentenceTransformer(model_name, device="cpu")
        _loaded_name = model_name
        print("[embed] model ready")
        return _model


def warmup(settings: dict | None = None) -> str:
    name = get_configured_model_name(settings)
    get_embedder(name)
    return name


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
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
        device="cpu",
    )
    return [vec.tolist() for vec in vectors]
