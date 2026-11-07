"""Load project settings from config/settings.yaml and optional .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


def get_repo_root() -> Path:
    return REPO_ROOT


def resolve_path(relative: str | Path) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


@lru_cache(maxsize=1)
def load_settings(settings_path: str | None = None) -> dict[str, Any]:
    load_dotenv(REPO_ROOT / ".env")
    path = Path(settings_path) if settings_path else DEFAULT_SETTINGS_PATH
    if not path.is_absolute():
        path = REPO_ROOT / path
    with path.open("r", encoding="utf-8") as fh:
        settings = yaml.safe_load(fh) or {}

    sources = settings.get("sources") or []
    if len(sources) != 5:
        raise ValueError(f"Expected exactly 5 allowlisted sources, found {len(sources)}")

    return settings


def allowlisted_urls(settings: dict[str, Any] | None = None) -> set[str]:
    cfg = settings or load_settings()
    return {source["url"] for source in cfg["sources"]}


def get_llm_model(settings: dict[str, Any] | None = None) -> str | None:
    cfg = settings or load_settings()
    env_key = cfg.get("llm", {}).get("model_env", "LLM_MODEL")
    return os.getenv(env_key)
