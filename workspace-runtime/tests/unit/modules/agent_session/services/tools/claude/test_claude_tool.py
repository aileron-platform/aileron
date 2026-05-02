from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.domain.enums import MessageRole, PermissionMode
from app.modules.agent_session.services.tools.base.types import (
    CompleteEvent,
    PartialEvent,
    ResultEvent,
    ThinkingCompleteEvent,
    ThinkingPartialEvent,
    ToolAuthenticationError,
    TokenUsage,
    ToolType,
)
from app.modules.agent_session.services.tools.claude import claude_tool as tool_module


class FakeCallbacks:
    def __init__(self) -> None:
        self.created: list[object] = []
        self.stream_started: list[str] = []
        self.stream_chunks: list[tuple[str, str]] = []
        self.stream_ended: list[str] = []
        self.thinking_started: list[tuple[str, object]] = []
        self.thinking_chunks: list[tuple[str, str]] = []
        self.thinking_ended: list[str] = []
        self.emitted: list[tuple[str, dict]] = []

    async def on_message_created(self, message) -> None:
        self.created.append(message)

    async def on_stream_start(self, message_id: str) -> None:
        self.stream_started.append(message_id)

    async def on_stream_chunk(self, message_id: str, text: str) -> None:
        self.stream_chunks.append((message_id, text))

    async def on_stream_end(self, message_id: str) -> None:
        self.stream_ended.append(message_id)

    async def on_thinking_start(self, message_id: str, metadata=None) -> None:
        self.thinking_started.append((message_id, metadata))

    async def on_thinking_chunk(self, message_id: str, text: str) -> None:
        self.thinking_chunks.append((message_id, text))

    async def on_thinking_end(self, message_id: str) -> None:
        self.thinking_ended.append(message_id)

    def emit_event(self, name: str, payload: dict) -> None:
        self.emitted.append((name, payload))


def make_message_model(
    message_id: str,
    role: MessageRole,
    content,
    *,
    task_id: str | None = "task-1",
    index: int = 1,
    data: str | None = None,
):
    return SimpleNamespace(
        id=message_id,
        session_id="session-1",
        task_id=task_id,
        type=role,
        role=role,
        index=index,
        content=content,
        metadata={"source": "claude-sdk"},
        created_at=datetime.now(UTC),
        data=data,
    )


def _make_message_repo() -> SimpleNamespace:
    return SimpleNamespace(
        find_by_session=AsyncMock(return_value=[object()]),
        find_by_id=AsyncMock(),
        update=AsyncMock(),
        to_entity=lambda model: model,
    )


def _make_session_repo() -> SimpleNamespace:
    return SimpleNamespace(
        find_by_id=AsyncMock(),
        update=AsyncMock(),
        set_sdk_session_id=AsyncMock(),
        to_entity=lambda model: model,
    )


def _patch_db_layer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message_repo: SimpleNamespace,
    session_repo: SimpleNamespace,
) -> None:
    """Patch async_session_scope plus repository/service factories so the tool
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


@pytest.mark.asyncio
async def test_execute_task_orchestrates_streaming_messages_and_updates_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = tool_module.ClaudeTool(api_key="key")
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    callbacks = FakeCallbacks()
    session_entity = SimpleNamespace(
        permission_config=SimpleNamespace(mode=PermissionMode.DEFAULT),
        data='{"existing": true}',
    )
    session_repo.find_by_id = AsyncMock(
        side_effect=[SimpleNamespace(data=session_entity.data), SimpleNamespace(data=session_entity.data)]
    )
    session_repo.to_entity = lambda _: session_entity

    register_calls: list[tuple[str, object]] = []
    unregister_calls: list[str] = []
    resolve_calls: list[tuple[str, dict]] = []

    class FakePermissionHooks:
        def __init__(self, session_id: str, task_id: str, emit_event, permission_mode=None):
            self.session_id = session_id
            self.task_id = task_id
            self.emit_event = emit_event
            self.permission_mode = permission_mode
            self.can_use_tool = AsyncMock(return_value=None)

    fake_manager = SimpleNamespace(
        register_hooks=lambda session_id, hooks: register_calls.append((session_id, hooks)),
        unregister_hooks=lambda session_id: unregister_calls.append(session_id),
        resolve_decision=lambda session_id, decision: resolve_calls.append((session_id, decision)) or True,
    )

    monkeypatch.setattr(tool_module, "PermissionHooks", FakePermissionHooks)
    monkeypatch.setattr(tool_module, "global_tool_decision_manager", fake_manager)
    monkeypatch.setattr(
        tool_module,
        "create_user_message",
        AsyncMock(return_value={"message_id": "user-1", "role": "user", "content_blocks": [{"type": "text", "text": "hi"}]}),
    )
    monkeypatch.setattr(tool_module, "create_assistant_message", AsyncMock(return_value={"message_id": "assistant-1"}))
    monkeypatch.setattr(tool_module, "create_tool_result_message", AsyncMock(return_value={"message_id": "tool-result-1"}))
    monkeypatch.setattr(tool_module, "create_system_message", AsyncMock(return_value={"message_id": "system-1"}))

    message_models = {
        "assistant-1": make_message_model(
            "assistant-1",
            MessageRole.ASSISTANT,
            [{"type": "text", "text": "done"}],
            data='{"metadata": {"source": "claude-sdk"}}',
        ),
        "tool-result-1": make_message_model(
            "tool-result-1",
            MessageRole.USER,
            [{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok", "is_error": False}],
        ),
        "system-1": make_message_model(
            "system-1",
            MessageRole.SYSTEM,
            [{"type": "system", "subtype": "meta", "data": {"x": 1}}],
        ),
    }
    message_repo.find_by_id = AsyncMock(side_effect=lambda message_id: message_models.get(message_id))

    events = [
        ThinkingPartialEvent(thinking_chunk="thinking"),
        ThinkingCompleteEvent(),
        PartialEvent(text="hello", resolved_model="claude-x"),
        CompleteEvent(
            role=MessageRole.ASSISTANT,
            content=[{"type": "text", "text": "done"}],
            tool_uses=[{"id": "tool-1", "name": "Read", "input": {}}],
            resolved_model="claude-x",
        ),
        CompleteEvent(
            role=MessageRole.USER,
            content=[{"type": "tool_result", "tool_use_id": "tool-1", "content": "ok", "is_error": False}],
        ),
        CompleteEvent(
            role=MessageRole.SYSTEM,
            content=[{"type": "system", "subtype": "meta", "data": {"x": 1}}],
        ),
        ResultEvent(
            raw_sdk_message={"session_id": "sdk-1"},
            token_usage=TokenUsage(input=10, output=20, cache_read=1, cache_creation=2),
        ),
    ]

    async def fake_stream(**kwargs):
        for event in events:
            yield event

    tool.prompt_service.prompt_session_streaming = fake_stream
    tool.prompt_service.cleanup_client = AsyncMock()

    result = await tool.execute_task("session-1", "hi", task_id="task-1", streaming_callbacks=callbacks)

    assert result.user_message_id == "user-1"
    assert result.assistant_message_ids == ["assistant-1"]
    assert result.agent_session_id == "sdk-1"
    assert result.model == "claude-x"
    assert result.was_stopped is False
    assert result.token_usage.input == 10
    assert register_calls and register_calls[0][0] == "session-1"
    assert unregister_calls == ["session-1"]
    tool.prompt_service.cleanup_client.assert_awaited_once_with("session-1")
    assert callbacks.created[0]["message_id"] == "user-1"
    assert callbacks.created[1]["message_id"] == "assistant-1"
    assert callbacks.created[2]["message_id"] == "tool-result-1"
    assert callbacks.created[3]["message_id"] == "system-1"
    assert len(callbacks.stream_started) == 1
    assert len(callbacks.stream_ended) == 1
    assert callbacks.stream_chunks[0][1] == "hello"
    assert len(callbacks.thinking_started) == 1
    assert len(callbacks.thinking_ended) >= 1
    session_repo.set_sdk_session_id.assert_awaited_once_with("session-1", "sdk-1")
    message_repo.update.assert_awaited_once()
    assert '"cache_creation": 2' in message_repo.update.await_args.args[1]["data"]
    assert "session-1" not in tool.abort_events
    assert tool.resolve_permission_decision("session-1", {"request_id": "r1", "allow": True}) is True
    assert resolve_calls == [("session-1", {"request_id": "r1", "allow": True})]


@pytest.mark.asyncio
async def test_execute_task_handles_stopped_event_and_skips_permission_hooks_without_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = tool_module.ClaudeTool(api_key="key")
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    session_entity = SimpleNamespace(permission_config=SimpleNamespace(mode=PermissionMode.BYPASS_PERMISSIONS), data="{}")
    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace())
    session_repo.to_entity = lambda _: session_entity

    monkeypatch.setattr(
        tool_module,
        "create_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )

    async def fake_stream(**kwargs):
        yield SimpleNamespace(type="stopped")

    tool.prompt_service.prompt_session_streaming = fake_stream
    tool.prompt_service.cleanup_client = AsyncMock()

    result = await tool.execute_task("session-1", "stop now", task_id="task-1", streaming_callbacks=None)

    assert result.was_stopped is True
    assert result.assistant_message_ids == []
    tool.prompt_service.cleanup_client.assert_awaited_once_with("session-1")
    assert "session-1" not in tool.abort_events


@pytest.mark.asyncio
async def test_execute_task_converts_auth_retry_without_response_to_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = tool_module.ClaudeTool(api_key="key")
    message_repo = _make_message_repo()
    session_repo = _make_session_repo()
    _patch_db_layer(monkeypatch, message_repo=message_repo, session_repo=session_repo)

    session_entity = SimpleNamespace(permission_config=SimpleNamespace(mode=PermissionMode.BYPASS_PERMISSIONS), data="{}")
    session_repo.find_by_id = AsyncMock(return_value=SimpleNamespace())
    session_repo.to_entity = lambda _: session_entity

    monkeypatch.setattr(
        tool_module,
        "create_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool_module, "create_system_message", AsyncMock(return_value="system-1"))

    async def fake_stream(**kwargs):
        yield CompleteEvent(
            role=MessageRole.SYSTEM,
            content=[{
                "type": "system",
                "subtype": "api_retry",
                "data": {"error_status": 401, "error": "authentication_failed"},
            }],
        )
        yield SimpleNamespace(type="stopped")

    tool.prompt_service.prompt_session_streaming = fake_stream
    tool.prompt_service.cleanup_client = AsyncMock()

    with pytest.raises(ToolAuthenticationError) as exc_info:
        await tool.execute_task("session-1", "hi", task_id="task-1", streaming_callbacks=None)

    assert exc_info.value.error_code == "AUTHENTICATION_FAILED"
    assert exc_info.value.message_key == "workspace.chat.errors.authenticationFailed"
    tool.prompt_service.cleanup_client.assert_awaited_once_with("session-1")
    assert "session-1" not in tool.abort_events
    tool_module.create_system_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_task() -> None:
    tool = tool_module.ClaudeTool(api_key="key")

    tool.abort_events["session-1"] = AsyncMock()
    tool.abort_events["session-1"].set = lambda: setattr(tool.abort_events["session-1"], "was_set", True)
    client = SimpleNamespace(interrupt=AsyncMock())
    tool.prompt_service.active_clients["session-1"] = client

    stopped = await tool.stop_task("session-1", "task-1")
    warning = await tool.stop_task("missing", "task-1")

    client_error = SimpleNamespace(interrupt=AsyncMock(side_effect=RuntimeError("boom")))
    tool.prompt_service.active_clients["session-2"] = client_error
    with_warning = await tool.stop_task("session-2", "task-2")

    assert stopped == {"success": True}
    assert warning["success"] is True and "No active client" in warning["warning"]
    assert with_warning == {"success": True, "warning": "boom"}
