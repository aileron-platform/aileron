"""Database connection and configuration"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _create_engine() -> Engine:
    """Create database engine, special handling for SQLite"""

    database_url = settings.DATABASE_URL
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        database_url,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


# Create database engine
engine = _create_engine()

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base
Base = declarative_base()

REMOVED_COLUMNS: dict[str, set[str]] = {
    "workspaces": {"port_mappings"},
}


def get_db() -> Generator[Session, None, None]:
    """GetDatabase session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create database tables"""
    from app.db import models  # noqa: F401 - Ensure models are loaded

    try:
        Base.metadata.create_all(bind=engine)
        drop_removed_columns(engine)
        logger.info("Database tables created successfully")
    except Exception as exc:  # pragma: no cover - Real errors need to be raised
        logger.error("Database table creation failed: %s", exc)
        raise


def drop_removed_columns(target_engine: Engine) -> list[str]:
    """Drop columns that were intentionally removed from the current schema."""

    inspector = inspect(target_engine)
    dropped: list[str] = []
    preparer = target_engine.dialect.identifier_preparer

    with target_engine.begin() as conn:
        for table_name, removed_columns in REMOVED_COLUMNS.items():
            if not inspector.has_table(table_name):
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name in sorted(removed_columns & existing_columns):
                table_identifier = preparer.quote(table_name)
                column_identifier = preparer.quote(column_name)
                conn.exec_driver_sql(
                    f"ALTER TABLE {table_identifier} DROP COLUMN {column_identifier}"
                )
                dropped.append(f"{table_name}.{column_name}")

    if dropped:
        logger.info("Dropped removed database columns: %s", ", ".join(dropped))

    return dropped
