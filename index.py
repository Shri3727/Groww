"""Vercel FastAPI entrypoint at the project root so sibling packages are bundled."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.main import app

__all__ = ["app"]
