"""啟動時自動套用 scripts/migrations/*.sql 的輕量 migration runner。

設計原則:
- create_tables() 負責建基礎 schema(依 SQLAlchemy model),此處只補 model
  變動後需要的 ALTER/CREATE。
- 用 schema_migrations 表追蹤已跑過的檔名,idempotent。
- 檔名字典序套用(慣例:YYYYMMDD_xxx.sql)。
- *_rollback.sql 不自動執行。
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
    """執行尚未套用的 migrations,回傳這次新套用的檔名列表。"""
    if engine.dialect.name == "sqlite":
        # SQL 檔是為 Postgres 寫的,SQLite(測試用 in-memory)直接跳過。
        logger.info("SQLite 引擎偵測到,略過 scripts/migrations 套用")
        return []

    _ensure_tracking_table(engine)
    already = _applied_filenames(engine)
    pending = [p for p in _discover_migrations() if p.name not in already]

    if not pending:
        logger.info("schema_migrations: 無待套用項目")
        return []

    applied: list[str] = []
    for path in pending:
        sql = path.read_text(encoding="utf-8")
        logger.info("套用 migration: %s", path.name)
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                {"f": path.name},
            )
        applied.append(path.name)

    logger.info("schema_migrations: 已套用 %d 個 migrations", len(applied))
    return applied
