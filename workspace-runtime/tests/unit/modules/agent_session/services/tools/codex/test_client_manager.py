from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.services.tools.codex.client_manager import (
    CodexAuthenticationRequiredError,
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

    monkeypatch.delenv("CODEX_SYNCED_KEYS", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("CODEX_MODEL", raising=False)
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
    monkeypatch.setattr(manager, "_ensure_codex_auth", AsyncMock())

    state = await manager.get_or_create("session-1", "/workspace", sdk_session_id="sdk-1")

    assert state.thread.id == "thread-1"
    assert created_configs[0].codex_bin == "/home/developer/.npm-global/bin/codex"
    assert created_configs[0].cwd == "/workspace"
    assert created_configs[0].env == {
        "CODEX_HOME": "/home/developer/.codex",
        "AILERON_CODEX_SESSION_STATE_DIR": "/home/developer/.codex-sessions/session-1",
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
    monkeypatch.setattr(manager, "_ensure_codex_auth", AsyncMock())
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
    monkeypatch.setattr(manager, "_ensure_codex_auth", AsyncMock())

    slow = asyncio.create_task(manager.get_or_create("session-a", "/workspace", "slow"))
    await asyncio.sleep(0)
    fast = await asyncio.wait_for(
        manager.get_or_create("session-b", "/workspace", "fast"),
        timeout=0.05,
    )
    assert fast.thread.id == "fast"
    await slow


@pytest.mark.asyncio
async def test_ensure_codex_auth_uses_existing_account(monkeypatch) -> None:
    manager = CodexClientManager()
    codex = SimpleNamespace()
    monkeypatch.setattr(
        manager,
        "_read_account",
        AsyncMock(return_value=SimpleNamespace(account=SimpleNamespace(root=object()))),
    )
    monkeypatch.setattr(manager, "_load_fallback_token_payload", lambda: None)

    await manager._ensure_codex_auth(codex)

    manager._read_account.assert_awaited_once_with(codex)


@pytest.mark.asyncio
async def test_ensure_codex_auth_injects_fallback_tokens(monkeypatch) -> None:
    manager = CodexClientManager()
    requests = []
    async def fake_request(method, params, **_kwargs):
        requests.append((method, params))

    codex = SimpleNamespace(
        _client=SimpleNamespace(
            request=AsyncMock(side_effect=fake_request)
        )
    )
    monkeypatch.setattr(
        manager,
        "_read_account",
        AsyncMock(side_effect=[
            SimpleNamespace(account=None),
            SimpleNamespace(account=SimpleNamespace(root=object())),
        ]),
    )
    monkeypatch.setattr(
        manager,
        "_load_fallback_token_payload",
        lambda: {
            "type": "chatgptAuthTokens",
            "accessToken": "token",
            "chatgptAccountId": "acct",
            "chatgptPlanType": "plus",
        },
    )

    assert await manager._ensure_codex_auth(codex) is True

    assert requests == [
        (
            "account/login/start",
            {
                "type": "chatgptAuthTokens",
                "accessToken": "token",
                "chatgptAccountId": "acct",
                "chatgptPlanType": "plus",
            },
        )
    ]


@pytest.mark.asyncio
async def test_ensure_codex_auth_returns_false_without_persisted_login(monkeypatch) -> None:
    manager = CodexClientManager()
    codex = SimpleNamespace()
    monkeypatch.setattr(
        manager,
        "_read_account",
        AsyncMock(return_value=SimpleNamespace(account=None)),
    )
    monkeypatch.setattr(manager, "_load_fallback_token_payload", lambda: None)

    assert await manager._ensure_codex_auth(codex) is False


@pytest.mark.asyncio
async def test_ensure_codex_auth_accepts_synced_api_key(monkeypatch) -> None:
    manager = CodexClientManager()
    codex = SimpleNamespace()
    read_account = AsyncMock()
    monkeypatch.setenv("CODEX_AUTH_METHOD", "apikey")
    monkeypatch.setenv("CODEX_SYNCED_KEYS", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(manager, "_read_account", read_account)

    assert await manager._ensure_codex_auth(codex) is True
    read_account.assert_not_awaited()


def test_build_codex_env_includes_synced_environment_variables(monkeypatch) -> None:
    manager = CodexClientManager()
    monkeypatch.setenv("CODEX_SYNCED_KEYS", "OPENAI_API_KEY,OPENAI_BASE_URL")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.3-codex")

    env = manager._build_codex_env("session-1")

    assert env == {
        "CODEX_HOME": "/home/developer/.codex",
        "AILERON_CODEX_SESSION_STATE_DIR": "/home/developer/.codex-sessions/session-1",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_BASE_URL": "https://api.example.test",
        "CODEX_MODEL": "gpt-5.3-codex",
    }


@pytest.mark.asyncio
async def test_get_or_create_raises_authentication_required_without_login(monkeypatch) -> None:
    import app.modules.agent_session.services.tools.codex.client_manager as module

    class FakeCodex:
        def __init__(self, config):
            self.config = config
            self._client = SimpleNamespace(_sync=SimpleNamespace(_approval_handler=None))
            self.close = AsyncMock()

    manager = CodexClientManager()
    monkeypatch.setattr(module, "AsyncCodex", FakeCodex)
    monkeypatch.setattr(module, "assert_sdk_structure", lambda: None)
    monkeypatch.setattr(manager, "_log_server_version", AsyncMock())
    monkeypatch.setattr(manager, "_ensure_codex_auth", AsyncMock(return_value=False))

    with pytest.raises(CodexAuthenticationRequiredError):
        await manager.get_or_create("session-1", "/workspace")
