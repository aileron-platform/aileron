"""Workspace Runtime database session utilities."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aileron_runtime_database_connection import (
    AsyncpgRuntimeConnectionAdapter,
    RuntimeDatabaseConnections,
    SecretFileRuntimeConnectionSource,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.config.settings import get_settings

_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None
_runtime_database_connections = RuntimeDatabaseConnections()


def get_async_engine() -> AsyncEngine:
    """Create or return cached asynchronous SQLAlchemy engine."""
    global _async_engine
    if _async_engine is not None:
        return _async_engine

    settings = get_settings()
    _async_engine = _runtime_database_connections.open(
        source=SecretFileRuntimeConnectionSource(
            settings.AILERON_RUNTIME_DATABASE_CONNECTION_FILE
        ),
        adapter=AsyncpgRuntimeConnectionAdapter(),
    )
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
