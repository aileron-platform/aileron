"""Database connection and configuration"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
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
        logger.info("Database tables created successfully")
    except Exception as exc:  # pragma: no cover - Real errors need to be raised
        logger.error("Database table creation failed: %s", exc)
        raise
