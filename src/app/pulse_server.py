"""Lightweight server for the product-pulse workflow.

The full FAQ app also mounts these routes. Use this module when the
embedding stack is not installed.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from src.app.pulse_routes import router

app = FastAPI(title="Groww weekly product pulse", version="0.1.0")
app.include_router(router)


@app.get("/")
def home():
    return RedirectResponse("/pulse")
