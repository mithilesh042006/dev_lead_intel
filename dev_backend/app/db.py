"""Database engine and session management (spec §28).

Persistence is optional. With DATABASE_URL empty the pipeline runs exactly as
before and still writes CSV — only the "save session" feature turns off. That
keeps the Phase 1 CLI usable without a database, and means a Neon outage
degrades the app rather than breaking it.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def normalize_url(url: str) -> str:
    """Neon hands out a libpq URL; SQLAlchemy needs an explicit driver.

    `channel_binding` is a libpq connection parameter that psycopg accepts, so
    it is left on the URL untouched.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def is_configured() -> bool:
    return bool(settings.database_url)


def get_engine() -> Engine:
    global _engine, _SessionFactory
    if _engine is None:
        if not is_configured():
            raise RuntimeError("DATABASE_URL is not set (see .env.example)")
        _engine = create_engine(
            normalize_url(settings.database_url),
            # Neon closes idle connections; without pre-ping the first query
            # after a quiet period fails on a stale pooled connection.
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_recycle=300,
        )
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope. Commits on success, rolls back on any exception."""
    get_engine()
    assert _SessionFactory is not None
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> bool:
    """Create tables if they do not exist. Safe to call on every startup."""
    if not is_configured():
        log.info("DATABASE_URL not set — session saving is disabled")
        return False
    from app.db_models import Base

    try:
        Base.metadata.create_all(get_engine())
        log.info("database ready")
        return True
    except Exception as exc:
        # A database that is unreachable at boot must not stop the API from
        # serving searches.
        log.error("database unavailable, session saving disabled: %s", exc)
        return False
