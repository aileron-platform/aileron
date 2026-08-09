"""Workspace Runtime database session utilities."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import get_settings

_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _get_database_url() -> str:
    """Get database connection string."""
    database_url = (
        get_settings()
        .AILERON_RUNTIME_STATE_DATABASE_URL_FILE.get_secret_value()
    )
    if not database_url:
        raise RuntimeError("Runtime state database URL is not configured")
    return database_url


def _get_async_database_url(database_url: str) -> str:
    """Require the workspace-scoped PostgreSQL connection contract."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise RuntimeError("Runtime state database must use PostgreSQL")


def get_async_engine() -> AsyncEngine:
    """Create or return cached asynchronous SQLAlchemy engine."""
    global _async_engine
    if _async_engine is not None:
        return _async_engine

    database_url = _get_async_database_url(_get_database_url())
    _async_engine = create_async_engine(database_url, pool_pre_ping=True)
    return _async_engine


def get_async_session_local() -> async_sessionmaker[AsyncSession]:
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


async def dispose_async_engine() -> None:
    """Dispose the cached async engine and session factory."""
    global _async_engine, _AsyncSessionLocal
    engine = _async_engine
    _async_engine = None
    _AsyncSessionLocal = None
    if engine is not None:
        await engine.dispose()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide asynchronous database session with automatic transaction management.

    Does not wrap the yielded session in `session.begin()`: callers that need
    a change committed before the request finishes (e.g. to make it visible to
    a background task) can call `session.commit()` directly and keep using the
    session afterwards. `session.begin()` would close on that manual commit
    and raise InvalidRequestError on any further use within the same request.
    """
    async_session = get_async_session_local()
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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
    "dispose_async_engine",
    "get_async_db",
    "get_async_engine",
    "get_async_session_local",
]
