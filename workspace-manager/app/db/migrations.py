"""Lightweight migration runner that automatically applies scripts/migrations/*.sql at startup.

Design principles:
- create_tables() is responsible for building the base schema (per SQLAlchemy model),
  this only supplements ALTER/CREATE needed after model changes.
- Use the schema_migrations table to track which files have been run, idempotent.
- Apply files in lexicographic order (convention: YYYYMMDD_xxx.sql).
- *_rollback.sql files are not automatically executed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "migrations"


def _ensure_tracking_table(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        ddl = (
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
    else:
        ddl = (
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename text PRIMARY KEY, "
            "applied_at timestamp with time zone NOT NULL DEFAULT now())"
        )
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _applied_filenames(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT filename FROM schema_migrations"))
        return {row[0] for row in rows}


def _discover_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    return sorted(
        p
        for p in MIGRATIONS_DIR.glob("*.sql")
        if not p.stem.endswith("_rollback")
    )


def apply_pending_migrations(engine: Engine) -> list[str]:
    """Execute pending migrations, return list of newly applied file names."""
    if engine.dialect.name == "sqlite":
        # SQL files are written for Postgres, skip for SQLite (test in-memory)
        logger.info("SQLite engine detected, skipping scripts/migrations application")
        return []

    _ensure_tracking_table(engine)
    already = _applied_filenames(engine)
    pending = [p for p in _discover_migrations() if p.name not in already]

    if not pending:
        logger.info("schema_migrations: no pending items")
        return []

    applied: list[str] = []
    for path in pending:
        sql = path.read_text(encoding="utf-8")
        logger.info("Applying migration: %s", path.name)
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": path.name},
            )
        applied.append(path.name)

    logger.info("schema_migrations: applied %d migrations", len(applied))
    return applied
