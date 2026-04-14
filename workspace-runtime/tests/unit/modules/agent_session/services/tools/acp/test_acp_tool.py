from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.services.tools.acp import acp_tool as tool_module
from app.modules.agent_session.services.tools.base.types import ToolType


class FakeCallbacks:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.emitted: list[tuple[str, dict]] = []

    async def on_message_created(self, message) -> None:
        self.created.append(message)

    def emit_event(self, name: str, payload: dict) -> None:
        self.emitted.append((name, payload))


def _make_message_repo() -> SimpleNamespace:
    return SimpleNamespace(
        find_by_session=AsyncMock(return_value=[]),
    )


def _make_session_repo() -> SimpleNamespace:
    return SimpleNamespace(
        find_by_id=AsyncMock(),
        to_entity=lambda model: model,
        update=AsyncMock(),
    )


def _patch_db_layer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message_repo: SimpleNamespace,
    session_repo: SimpleNamespace,
) -> None:
    """Patch async_session_scope plus repository/service factories so AcpTool
    sees the same mock objects regardless of how many short-lived sessions it
    opens.
    """

    @asynccontextmanager
    async def fake_scope():
        yield Mock()

    monkeypatch.setattr(tool_module, "async_session_scope", fake_scope)
    monkeypatch.setattr(tool_module, "MessageRepository", lambda db: message_repo)
    monkeypatch.setattr(tool_module, "AgentSessionRepository", lambda db: session_repo)
    monkeypatch.setattr(tool_module, "MessageService", lambda db: SimpleNamespace())


def _make_tool() -> tuple[tool_module.AcpTool, SimpleNamespace, SimpleNamespace]:
    workspace_service = SimpleNamespace(get_workspace=AsyncMock())
    connection_manager = SimpleNamespace(get_or_create=AsyncMock(), get_existing=lambda session_id: None)
    tool = tool_module.AcpTool(
        tool_type=ToolType.CODEX,
        workspace_service=workspace_service,
        connection_manager=connection_manager,
    )
    return tool, workspace_service, connection_manager


@pytest.mark.asyncio
async def test_execute_task_builds_messages_and_result(monkeypatch: pytest.MonkeyPatch) -> None:
    tool, workspace_service, connection_manager = _make_tool()
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    callbacks = FakeCallbacks()
    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(workspace_id="ws-1", sdk_session_id=None))
    workspace_service.get_workspace = AsyncMock(
        return_value=SimpleNamespace(
            acp_cli_args=["--foo"],
            env_vars=[SimpleNamespace(key="A", value="1")],
            workspace_path="/workspace/demo",
        )
    )

    connection = SimpleNamespace(
        connection=SimpleNamespace(
            prompt=AsyncMock(return_value=SimpleNamespace(stop_reason="cancelled", model_dump=lambda **kwargs: {"stopReason": "cancelled"}))
        ),
        client_impl=SimpleNamespace(
            set_task_context=Mock(),
            finalize_streaming=AsyncMock(),
            get_current_content=lambda: ("assistant text", "thinking text"),
            get_tool_executions=lambda: [
                {
                    "tool_call_id": "tool-1",
                    "title": "Bash",
                    "tool_input": {"command": "ls"},
                    "tool_result": {"ok": True},
                    "is_error": False,
                },
                {
                    "title": "Read",
                    "content": "fallback result",
                    "status": "completed",
                },
            ],
        ),
    )
    connection_manager.get_or_create = AsyncMock(return_value=connection)
    tool._ensure_sdk_session = AsyncMock(return_value="sdk-1")

    monkeypatch.setattr(
        tool_module,
        "create_user_message",
        AsyncMock(return_value={"message_id": "user-1", "content_blocks": [{"type": "text", "text": "hi"}]}),
    )
    monkeypatch.setattr(
        tool_module,
        "create_assistant_message",
        AsyncMock(return_value={"message_id": "assistant-1", "content_blocks": [{"type": "text", "text": "assistant text"}]}),
    )

    result = await tool.execute_task("session-1", "hi", task_id="task-1", streaming_callbacks=callbacks)

    assert result.user_message_id == "user-1"
    assert result.assistant_message_ids == ["assistant-1"]
    assert result.agent_session_id == "sdk-1"
    assert result.was_stopped is True
    assert result.raw_sdk_response == {"stopReason": "cancelled"}
    connection_manager.get_or_create.assert_awaited_once()
    connection.client_impl.set_task_context.assert_called_once()
    connection.connection.prompt.assert_awaited_once()
    connection.client_impl.finalize_streaming.assert_awaited_once()
    assistant_call = tool_module.create_assistant_message.await_args.kwargs
    assert assistant_call["metadata"]["stop_reason"] == "cancelled"
    assert assistant_call["content"][0]["type"] == "tool_use"
    assert assistant_call["content"][1]["type"] == "tool_result"
    assert assistant_call["content"][-2] == {"type": "thinking", "thinking": "thinking text"}
    assert assistant_call["content"][-1] == {"type": "text", "text": "assistant text"}
    assert callbacks.created[0]["message_id"] == "user-1"
    assert callbacks.created[1]["message_id"] == "assistant-1"


@pytest.mark.asyncio
async def test_execute_task_validates_session_and_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    tool, workspace_service, _ = _make_tool()
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    monkeypatch.setattr(tool_module, "create_user_message", AsyncMock(return_value={"message_id": "user-1"}))

    session_repo.find_by_id = AsyncMock(return_value=None)
    with pytest.raises(ValueError, match="Session not found: session-1"):
        await tool.execute_task("session-1", "hi")

    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(workspace_id="ws-1", sdk_session_id=None))
    workspace_service.get_workspace = AsyncMock(return_value=None)
    with pytest.raises(ValueError, match="Workspace not found: ws-1"):
        await tool.execute_task("session-1", "hi")


@pytest.mark.asyncio
async def test_ensure_sdk_session_and_persist_behaviors(monkeypatch: pytest.MonkeyPatch) -> None:
    tool, _, _ = _make_tool()
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    connection = SimpleNamespace(
        sdk_session_id=None,
        connection=SimpleNamespace(
            load_session=AsyncMock(),
            new_session=AsyncMock(return_value=SimpleNamespace(session_id="new-sdk")),
        ),
    )

    existing = await tool._ensure_sdk_session(connection, "session-1", "existing-sdk", "/workspace")
    assert existing == "existing-sdk"
    connection.connection.load_session.assert_awaited_once()

    connection.sdk_session_id = None
    connection.connection.load_session = AsyncMock(side_effect=RuntimeError("load failed"))
    original_persist = tool._persist_sdk_session_id
    persist_mock = AsyncMock()
    tool._persist_sdk_session_id = persist_mock
    created = await tool._ensure_sdk_session(connection, "session-1", "bad-sdk", "/workspace")
    assert created == "new-sdk"
    persist_mock.assert_awaited_once_with("session-1", "new-sdk")
    tool._persist_sdk_session_id = original_persist

    connection.sdk_session_id = "cached-sdk"
    assert await tool._ensure_sdk_session(connection, "session-1", None, "/workspace") == "cached-sdk"

    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(data='{"x":1}'))
    await tool._persist_sdk_session_id("session-1", "sdk-1")
    payload = session_repo.update.await_args.args[1]
    assert json.loads(payload["data"])["sdk_session_id"] == "sdk-1"
    assert isinstance(payload["updated_at"], datetime)

    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace(data="{bad"))
    await tool._persist_sdk_session_id("session-1", "sdk-2")
    assert json.loads(session_repo.update.await_args.args[1]["data"]) == {"sdk_session_id": "sdk-2"}

    session_repo.find_by_id = AsyncMock(return_value=None)
    session_repo.update.reset_mock()
    await tool._persist_sdk_session_id("missing", "sdk-3")
    session_repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_task_check_installed_and_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    tool, _, connection_manager = _make_tool()
    connection = SimpleNamespace(connection=SimpleNamespace(cancel=AsyncMock()), sdk_session_id="sdk-1")
    connection_manager.get_existing = lambda session_id: connection

    monkeypatch.setattr(tool_module.shutil, "which", lambda command: "/usr/bin/codex" if command == "codex" else None)

    assert tool.tool_type == ToolType.CODEX
    assert tool.name == "codex"
    assert tool.get_capabilities().supports_session_create is True
    assert await tool.check_installed() is True
    assert await tool.stop_task("session-1") == {"success": True}
    connection.connection.cancel.assert_awaited_once_with(session_id="sdk-1")

    connection_manager.get_existing = lambda session_id: SimpleNamespace(connection=SimpleNamespace(cancel=AsyncMock()), sdk_session_id=None)
    assert await tool.stop_task("session-2") == {"success": True}
