"""Idempotent schema migrations.

`Base.metadata.create_all()` creates missing tables but never alters existing
ones, so a new column on a live table needs an explicit step. This is a
stop-gap: a project that ships schema changes regularly wants Alembic.

    venv/Scripts/python.exe scripts/migrate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine, is_configured  # noqa: E402
from app.db_models import Base  # noqa: E402

# (table, column, DDL type + default). Each is applied only if absent.
COLUMNS: list[tuple[str, str, str]] = [
    ("saved_leads", "is_manual", "BOOLEAN NOT NULL DEFAULT FALSE"),
]


def main() -> int:
    if not is_configured():
        print("DATABASE_URL is not set — nothing to migrate")
        return 1

    engine = get_engine()
    Base.metadata.create_all(engine)  # new tables
    inspector = inspect(engine)

    applied = 0
    with engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if table not in inspector.get_table_names():
                print(f"  skip {table}.{column} — table absent")
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                print(f"  ok   {table}.{column} already present")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            print(f"  ADD  {table}.{column} {ddl}")
            applied += 1

    print(f"\n{applied} change(s) applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
