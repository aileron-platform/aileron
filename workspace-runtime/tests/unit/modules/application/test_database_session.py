"""Workspace Runtime database session integration with the shared module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aileron_runtime_database_connection import (
    AsyncpgRuntimeConnectionAdapter,
    SecretFileRuntimeConnectionSource,
)

from app.database import session


@pytest.fixture(autouse=True)
async def _reset_engine() -> None:
    await session.dispose_async_engine()
    yield
    await session.dispose_async_engine()


def test_get_async_engine_opens_the_canonical_connection_file(monkeypatch) -> None:
    connection_file = Path("/run/secrets/aileron/runtime-database-connection")
    engine = MagicMock()
    engine.dispose = AsyncMock()
    open_connection = MagicMock(return_value=engine)
    monkeypatch.setattr(
        session,
        "get_settings",
        lambda: SimpleNamespace(
            AILERON_RUNTIME_DATABASE_CONNECTION_FILE=connection_file
        ),
    )
    monkeypatch.setattr(
        session._runtime_database_connections,
        "open",
        open_connection,
    )

    assert session.get_async_engine() is engine
    assert session.get_async_engine() is engine
    open_connection.assert_called_once()
    call = open_connection.call_args.kwargs
    assert call["source"] == SecretFileRuntimeConnectionSource(connection_file)
    assert isinstance(call["adapter"], AsyncpgRuntimeConnectionAdapter)


@pytest.mark.asyncio
async def test_dispose_async_engine_clears_the_cached_connection(monkeypatch) -> None:
    engine = MagicMock()
    engine.dispose = MagicMock(return_value=_completed())
    session._async_engine = engine
    session._AsyncSessionLocal = MagicMock()

    await session.dispose_async_engine()

    assert session._async_engine is None
    assert session._AsyncSessionLocal is None
    engine.dispose.assert_called_once_with()


async def _completed() -> None:
    return None
