"""FastAPI application (spec §22, §26).

    venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

Interactive docs at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import init_db, is_configured

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
for _noisy in ("httpx", "httpcore", "google_genai", "apify_client"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

app = FastAPI(
    title="AI Lead Intelligence API",
    description="Phase 2 API over the Phase 1 lead pipeline.",
    version="0.1.0",
)

# §37 — the browser never sees an API key; all provider calls happen server-side.
# Origins are explicit rather than "*" so this stays correct when deployed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

# Create tables on boot. A database that is unreachable logs and disables
# saving rather than preventing the API from serving searches.
DB_READY = init_db()

app.include_router(router)


@app.get("/api/health")
def health() -> dict:
    """Reports configuration without leaking secrets — only whether they exist."""
    return {
        "status": "ok",
        "model": settings.llm_model,
        "apify_configured": bool(settings.apify_api_token),
        "gemini_configured": bool(settings.gemini_api_key),
        "cache_enabled": settings.cache_enabled,
        "database_configured": is_configured(),
        "database_ready": DB_READY,
        "max_places_per_search": settings.max_places_per_search,
        "max_reviews_per_place": settings.max_reviews_per_place,
    }
