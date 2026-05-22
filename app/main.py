"""HireAI GenAI service - mounts all 3 module routers.

Owned by G4. Module owners (G1/G2/G3) only edit their own
modules/<name>/routes.py file.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.cost import project_total, summarize_day
from app.modules.copilot.routes import router as copilot_router
from app.modules.explain.routes import router as explain_router
from app.modules.parser.routes import router as parser_router

_settings = get_settings()
logging.basicConfig(level=_settings.log_level)

app = FastAPI(
    title="HireAI GenAI",
    description="Resume parsing, AI Copilot, and Explainable AI services.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parser_router)
app.include_router(copilot_router)
app.include_router(explain_router)


@app.get("/healthz", tags=["infra"])
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", tags=["infra"])
def readyz() -> dict:
    """Reports whether Redis and OpenAI client are reachable."""
    from app.core.cache import _get_client
    redis_ok = _get_client() is not None
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "up" if redis_ok else "down (using memory fallback)",
    }


@app.get("/admin/cost/today", tags=["infra"])
def cost_today() -> dict:
    from datetime import date
    return summarize_day(date.today().isoformat())


@app.get("/admin/cost/total", tags=["infra"])
def cost_total() -> dict:
    return {
        "project_total_usd": project_total(),
        "project_cap_usd": _settings.project_spend_cap_usd,
    }
