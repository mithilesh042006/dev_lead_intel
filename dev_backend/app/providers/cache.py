"""Disk cache for raw provider responses.

This is the single most important cost control in the project: during development
the pipeline gets re-run constantly while tuning prompts, scoring and CSV output.
Without this, every run burns Apify credits on places that have not changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from app.config import settings


def _key(namespace: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]
    return f"{namespace}__{digest}"


def _path(namespace: str, payload: Any) -> Path:
    return settings.cache_dir / f"{_key(namespace, payload)}.json"


def get(namespace: str, payload: Any) -> Optional[Any]:
    if not settings.cache_enabled:
        return None
    p = _path(namespace, payload)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def put(namespace: str, payload: Any, value: Any) -> None:
    if not settings.cache_enabled:
        return
    p = _path(namespace, payload)
    try:
        p.write_text(
            json.dumps(value, ensure_ascii=False, default=str, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def describe(namespace: str, payload: Any) -> str:
    return _path(namespace, payload).name
