from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.domain.enums import PermissionMode
from app.modules.agent_session.services.tools.claude import query_builder as qb_module


def _make_session_repo_patch(monkeypatch: pytest.MonkeyPatch, session_repo: Mock) -> None:
    """Patch async_session_scope and AgentSessionRepository so QueryBuilder uses the mock repo."""

    @asynccontextmanager
    async def fake_scope():
        yield Mock()

    monkeypatch.setattr(qb_module, "async_session_scope", fake_scope)
    monkeypatch.setattr(qb_module, "AgentSessionRepository", lambda db: session_repo)


def test_to_sdk_permission_mode_passthrough() -> None:
    assert qb_module.to_sdk_permission_mode(None) is None
    assert qb_module.to_sdk_permission_mode(PermissionMode.DEFAULT) == PermissionMode.DEFAULT.value
    assert qb_module.to_sdk_permission_mode(PermissionMode.ACCEPT_EDITS) == PermissionMode.ACCEPT_EDITS.value
    assert qb_module.to_sdk_permission_mode(PermissionMode.DONT_ASK) == PermissionMode.DONT_ASK.value
    assert qb_module.to_sdk_permission_mode(PermissionMode.AUTO) == PermissionMode.AUTO.value


@pytest.mark.asyncio
async def test_setup_query_builds_expected_options(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = Mock()
    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace())
    session_repo.to_entity.return_value = SimpleNamespace(
        sdk_session_id="sdk-1",
        custom_context={
            "workspace_path": "/tmp/ws",
            "allowed_tools": [],
            "disallowedTools": ["rm"],
            "mcpServers": {"a": {"command": "node"}},
            "maxTurns": 55,
        },
        permission_config=SimpleNamespace(mode=PermissionMode.BYPASS_PERMISSIONS),
        model_settings=SimpleNamespace(
            model="claude-test",
            thinking_mode="manual",
            manual_thinking_tokens=128,
        ),
    )
    _make_session_repo_patch(monkeypatch, session_repo)

    captured: dict = {}

    class FakeOptions:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.kwargs = kwargs

    monkeypatch.setattr(qb_module, "ClaudeAgentOptions", FakeOptions)
    builder = qb_module.QueryBuilder(api_key="key")

    result = await builder.setup_query(
        "session-1",
        "hello",
        qb_module.QueryOptions(
            resume=True,
            can_use_tool=lambda *_: True,
            permission_mode=PermissionMode.DEFAULT,
        ),
    )

    assert isinstance(result, FakeOptions)
    assert captured["cwd"] == "/tmp/ws"
    assert captured["resume"] == "sdk-1"
    assert captured["model"] == "claude-test"
    assert captured["permission_mode"] == PermissionMode.DEFAULT.value
    assert captured["allowed_tools"] == []
    assert captured["disallowed_tools"] == ["rm"]
    assert captured["mcp_servers"] == {"a": {"command": "node"}}
    assert captured["max_turns"] == 55
    assert captured["max_thinking_tokens"] == 128
    assert captured["include_partial_messages"] is False


@pytest.mark.asyncio
async def test_setup_query_uses_session_defaults_and_missing_session_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_repo = Mock()
    session_repo.find_by_id = AsyncMock(side_effect=[None, SimpleNamespace()])
    session_repo.to_entity.return_value = SimpleNamespace(
        sdk_session_id="sdk-2",
        custom_context={},
        permission_config=SimpleNamespace(mode=PermissionMode.ACCEPT_EDITS),
        model_settings=SimpleNamespace(model="claude-default", thinking_mode=None, manual_thinking_tokens=None),
    )
    _make_session_repo_patch(monkeypatch, session_repo)

    class FakeOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(qb_module, "ClaudeAgentOptions", FakeOptions)
    builder = qb_module.QueryBuilder()

    with pytest.raises(ValueError, match="Session session-missing not found"):
        await builder.setup_query("session-missing", "hi", qb_module.QueryOptions())

    result = await builder.setup_query("session-2", "hi", qb_module.QueryOptions(resume=False))
    assert result.kwargs["cwd"] == "/workspace"
    assert result.kwargs["permission_mode"] == PermissionMode.ACCEPT_EDITS.value
    assert result.kwargs["max_turns"] == qb_module.DEFAULT_MAX_TURNS
    assert "resume" not in result.kwargs
    assert result.kwargs["include_partial_messages"] is True
