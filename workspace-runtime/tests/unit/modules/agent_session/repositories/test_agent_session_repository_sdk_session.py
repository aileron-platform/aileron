from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository


def _make_repo() -> AgentSessionRepository:
    repo = AgentSessionRepository(SimpleNamespace())
    repo.update = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_set_sdk_session_id_preserves_existing_data() -> None:
    repo = _make_repo()
    repo.find_by_id = AsyncMock(return_value=SimpleNamespace(data='{"other":"value"}'))

    await repo.set_sdk_session_id("session-12345678", "sdk-1")

    payload = repo.update.await_args.args[1]
    assert json.loads(payload["data"]) == {"other": "value", "sdk_session_id": "sdk-1"}


@pytest.mark.asyncio
async def test_set_sdk_session_id_handles_missing_data() -> None:
    repo = _make_repo()
    repo.find_by_id = AsyncMock(return_value=SimpleNamespace(data=None))

    await repo.set_sdk_session_id("session-12345678", "sdk-1")

    payload = repo.update.await_args.args[1]
    assert json.loads(payload["data"]) == {"sdk_session_id": "sdk-1"}


@pytest.mark.asyncio
async def test_set_sdk_session_id_handles_malformed_data() -> None:
    repo = _make_repo()
    repo.find_by_id = AsyncMock(return_value=SimpleNamespace(data="{bad"))

    await repo.set_sdk_session_id("session-12345678", "sdk-1")

    payload = repo.update.await_args.args[1]
    assert json.loads(payload["data"]) == {"sdk_session_id": "sdk-1"}


@pytest.mark.asyncio
async def test_set_sdk_session_id_unknown_session_is_noop(caplog: pytest.LogCaptureFixture) -> None:
    repo = _make_repo()
    repo.find_by_id = AsyncMock(return_value=None)

    await repo.set_sdk_session_id("session-12345678", "sdk-1")

    repo.update.assert_not_awaited()
    assert "session-" in caplog.text
