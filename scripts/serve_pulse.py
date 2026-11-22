"""Serve /pulse without FastAPI. Uses the same page and approval rules."""

from __future__ import annotations

import json
import sys
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stub_fastapi() -> None:
    fastapi = types.ModuleType("fastapi")

    class APIRouter:
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

    class HTTPException(Exception):
        def __init__(self, status_code: int = 500, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.APIRouter = APIRouter
    fastapi.HTTPException = HTTPException
    responses = types.ModuleType("fastapi.responses")
    responses.HTMLResponse = str
    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    pydantic.BaseModel = BaseModel
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses
    sys.modules["pydantic"] = pydantic


_stub_fastapi()
from src.app.pulse_routes import _render, current_package  # noqa: E402
from src.pulse.store import commit_approved  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/pulse"):
            page = _render(current_package()).encode("utf-8")
            self._send(200, page, "text/html; charset=utf-8")
            return
        if path == "/api/pulse":
            body = json.dumps(current_package(), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/api/pulse/approve":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if not payload.get("approved"):
            body = json.dumps({"detail": "Approval is required before logging."}).encode("utf-8")
            self._send(400, body, "application/json; charset=utf-8")
            return
        paths = commit_approved(current_package())
        body = json.dumps({"ok": True, "sent": False, **paths}, ensure_ascii=False).encode("utf-8")
        self._send(200, body, "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        print(f"[pulse] {self.address_string()} {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Pulse page: http://127.0.0.1:8000/pulse")
    server.serve_forever()


if __name__ == "__main__":
    main()
