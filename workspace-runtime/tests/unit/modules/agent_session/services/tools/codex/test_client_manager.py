from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.services.tools.codex.client_manager import (
    CodexClientManager,
    CodexSessionApprovalDispatcher,
)


def test_dispatcher_fallback_and_switching() -> None:
    dispatcher = CodexSessionApprovalDispatcher()
    assert dispatcher("item/commandExecution/requestApproval", {}) == {
        "decision": "decline"
    }
    assert dispatcher("item/permissions/requestApproval", {}) == {
        "permissions": {},
        "scope": "turn",
    }

    handler = SimpleNamespace(sync_approval_callback=lambda method, params: {"ok": method})
    dispatcher.set_current(handler)
    assert dispatcher("x", {}) == {"ok": "x"}


@pytest.mark.asyncio
async def test_get_or_create_constructs_config_and_resumes(monkeypatch) -> None:
    import app.modules.agent_session.services.tools.codex.client_manager as module

    created_configs = []

    class FakeCodex:
        def __init__(self, config):
            created_configs.append(config)
            self._client = SimpleNamespace(_sync=SimpleNamespace(_approval_handler=None))
            self.thread_resume = AsyncMock(return_value=SimpleNamespace(id="thread-1"))
            self.close = AsyncMock()

    manager = CodexClientManager()
    monkeypatch.setattr(module, "AsyncCodex", FakeCodex)
    monkeypatch.setattr(module, "assert_sdk_structure", lambda: None)
    monkeypatch.setattr(manager, "_log_server_version", AsyncMock())

    state = await manager.get_or_create("session-1", "/workspace", sdk_session_id="sdk-1")

    assert state.thread.id == "thread-1"
    assert created_configs[0].codex_bin == "/home/developer/.npm-global/bin/codex"
    assert created_configs[0].cwd == "/workspace"
    assert created_configs[0].env == {
        "CODEX_HOME": "/home/developer/.codex-sessions/session-1"
    }
    assert state.codex._client._sync._approval_handler is state.dispatcher


@pytest.mark.asyncio
async def test_get_or_create_clears_stale_sdk_session_id(monkeypatch) -> None:
    import app.modules.agent_session.services.tools.codex.client_manager as module

    cleared = []

    class FakeCodex:
        def __init__(self, config):
            self.config = config
            self._client = SimpleNamespace(_sync=SimpleNamespace(_approval_handler=None))
            self.close = AsyncMock()

        async def thread_resume(self, *_args, **_kwargs):
            raise RuntimeError("stale thread")

    async def fake_clear(session_id):
        cleared.append(session_id)

    manager = CodexClientManager()
    monkeypatch.setattr(module, "AsyncCodex", FakeCodex)
    monkeypatch.setattr(module, "assert_sdk_structure", lambda: None)
    monkeypatch.setattr(manager, "_log_server_version", AsyncMock())
    monkeypatch.setattr(manager, "_clear_persisted_thread_id", fake_clear)

    state = await manager.get_or_create("session-1", "/workspace", sdk_session_id="stale")

    assert state.thread is None
    assert cleared == ["session-1"]


@pytest.mark.asyncio
async def test_concurrent_distinct_session_init_does_not_block(monkeypatch) -> None:
    import app.modules.agent_session.services.tools.codex.client_manager as module

    class FakeCodex:
        def __init__(self, config):
            self.config = config
            self._client = SimpleNamespace(_sync=SimpleNamespace(_approval_handler=None))
            self.close = AsyncMock()

        async def thread_resume(self, thread_id, **kwargs):
            if thread_id == "slow":
                await asyncio.sleep(0.1)
            return SimpleNamespace(id=thread_id)

    manager = CodexClientManager()
    monkeypatch.setattr(module, "AsyncCodex", FakeCodex)
    monkeypatch.setattr(module, "assert_sdk_structure", lambda: None)
    monkeypatch.setattr(manager, "_log_server_version", AsyncMock())

    slow = asyncio.create_task(manager.get_or_create("session-a", "/workspace", "slow"))
    await asyncio.sleep(0)
    fast = await asyncio.wait_for(
        manager.get_or_create("session-b", "/workspace", "fast"),
        timeout=0.05,
    )
    assert fast.thread.id == "fast"
    await slow
