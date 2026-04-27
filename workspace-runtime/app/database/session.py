"""Workspace Runtime database session utilities."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_engine = None
_SessionLocal = None
_async_engine = None
_AsyncSessionLocal = None


def _get_database_url() -> str:
    """Get database connection string."""
    database_url = get_settings().DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    return database_url


def _get_async_database_url(database_url: str) -> str:
    """Convert synchronous database URL to SQLAlchemy async URL."""
    if database_url.startswith("postgresql+asyncpg://") or database_url.startswith(
        "sqlite+aiosqlite://"
    ):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return database_url


def get_engine():
    """Create or return cached synchronous SQLAlchemy engine."""
    global _engine
    if _engine is not None:
        return _engine

    database_url = _get_database_url()

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=connect_args)
    return _engine


def get_session_local():
    """Create or return cached SessionLocal."""
    global _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_async_engine():
    """Create or return cached asynchronous SQLAlchemy engine."""
    global _async_engine
    if _async_engine is not None:
        return _async_engine

    database_url = _get_async_database_url(_get_database_url())
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _async_engine = create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    return _async_engine


def get_async_session_local():
    """Create or return cached AsyncSession factory."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is not None:
        return _AsyncSessionLocal

    _AsyncSessionLocal = async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )
    return _AsyncSessionLocal


def get_db() -> Generator[Session, None, None]:
    """Provide synchronous database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide session context manager with automatic commit/rollback."""
    session = get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide asynchronous database session with automatic transaction management."""
    async_session = get_async_session_local()
    async with async_session() as session:
        async with session.begin():
            yield session


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Provide asynchronous session context manager with automatic commit/rollback."""
    async_session = get_async_session_local()
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = [
    "async_session_scope",
    "get_async_db",
    "get_async_engine",
    "get_async_session_local",
    "get_db",
    "get_engine",
    "get_session_local",
    "session_scope",
]
