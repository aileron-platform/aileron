from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from codex_app_server.generated.v2_all import (
    CommandExecutionOutputDeltaNotification,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    FileChangePatchUpdatedNotification,
    FileChangeThreadItem,
    FileUpdateChange,
    ItemCompletedNotification,
    ItemStartedNotification,
    PatchApplyStatus,
    PlanDeltaNotification,
    ReasoningSummaryTextDeltaNotification,
)

import app.modules.agent_session.services.tools.codex.codex_tool as module
from app.modules.agent_session.services.tools.codex.client_manager import (
    CodexAuthenticationRequiredError,
    CodexSessionApprovalDispatcher,
    SessionState,
)
from app.modules.agent_session.services.tools.codex.codex_tool import (
    CodexAuthenticationError,
    CodexExecutionError,
    CodexTool,
)


class FakeDecisionManager:
    def __init__(self) -> None:
        self.registered = []
        self.unregistered = []

    def register_hooks(self, session_id, handler) -> None:
        self.registered.append((session_id, handler))

    def unregister_hooks(self, session_id) -> None:
        self.unregistered.append(session_id)


class FakeCallbacks:
    def __init__(self) -> None:
        self.messages = []
        self.thinking = []

    async def on_message_created(self, message):
        self.messages.append(message)

    async def on_thinking_start(self, message_id):
        self.thinking.append(("start", message_id))

    async def on_thinking_chunk(self, message_id, delta):
        self.thinking.append(("chunk", message_id, delta))

    async def on_thinking_end(self, message_id):
        self.thinking.append(("end", message_id))


class FakeHandle:
    def __init__(self, notifications) -> None:
        self._notifications = notifications
        self.interrupt = AsyncMock()

    async def stream(self):
        for notification in self._notifications:
            yield notification


class FakeThread:
    def __init__(self, handle) -> None:
        self.id = "thread-1"
        self._handle = handle

    async def turn(self, *_args, **_kwargs):
        return self._handle


class FakeManager:
    def __init__(self, state) -> None:
        self.state = state

    async def get_or_create(self, *_args, **_kwargs):
        return self.state

    async def get_state(self, *_args, **_kwargs):
        return self.state


class FailingAuthManager:
    async def get_or_create(self, *_args, **_kwargs):
        raise CodexAuthenticationRequiredError("not logged in")


def _notification(method: str, payload):
    return SimpleNamespace(method=method, payload=payload)


def _command_item(**updates):
    data = {
        "id": "cmd-1",
        "type": "commandExecution",
        "command": "printf hi",
        "commandActions": [],
        "cwd": "/workspace",
        "status": CommandExecutionStatus.in_progress,
    }
    data.update(updates)
    return CommandExecutionThreadItem(**data)


def _change(path: str, diff: str) -> FileUpdateChange:
    return FileUpdateChange.model_validate(
        {"path": path, "diff": diff, "kind": {"type": "update"}}
    )


@pytest.mark.asyncio
async def test_execute_task_rejects_same_session_active_turn(monkeypatch) -> None:
    state = SessionState(
        codex=SimpleNamespace(),
        dispatcher=CodexSessionApprovalDispatcher(),
        active_turn=SimpleNamespace(),
    )
    tool = CodexTool(FakeManager(state))
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")),
    )

    with pytest.raises(CodexExecutionError):
        await tool.execute_task("session-1", "prompt")


@pytest.mark.asyncio
async def test_execute_task_maps_authentication_required_to_i18n_error(monkeypatch) -> None:
    tool = CodexTool(FailingAuthManager())
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")),
    )

    with pytest.raises(CodexAuthenticationError) as exc_info:
        await tool.execute_task("session-1", "prompt")

    assert exc_info.value.error_code == "CODEX_AUTHENTICATION_FAILED"
    assert exc_info.value.message_key == "workspace.chat.errors.codexAuthenticationFailed"


@pytest.mark.asyncio
async def test_execute_task_uses_command_delta_when_final_output_empty(monkeypatch) -> None:
    notifications = [
        _notification(
            "item/started",
            ItemStartedNotification(
                item=_command_item(),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/commandExecution/outputDelta",
            CommandExecutionOutputDeltaNotification(
                itemId="cmd-1",
                delta="buffered output",
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=_command_item(
                    status=CommandExecutionStatus.completed,
                    aggregated_output="",
                    exit_code=0,
                ),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
    ]
    handle = FakeHandle(notifications)
    state = SessionState(
        codex=SimpleNamespace(thread_start=AsyncMock(return_value=FakeThread(handle))),
        dispatcher=CodexSessionApprovalDispatcher(),
    )
    tool = CodexTool(FakeManager(state))
    persisted_results = []
    decision_manager = FakeDecisionManager()

    monkeypatch.setattr(module, "global_tool_decision_manager", decision_manager)
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")),
    )
    monkeypatch.setattr(
        tool,
        "_persist_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool, "_save_sdk_session_id", AsyncMock())
    monkeypatch.setattr(
        tool,
        "_persist_tool_use_message",
        AsyncMock(return_value={"message_id": "assistant-tool-1"}),
    )

    async def persist_result(**kwargs):
        persisted_results.append(kwargs)
        return {"message_id": "result-1"}

    monkeypatch.setattr(tool, "_persist_tool_result_message", persist_result)

    result = await tool.execute_task("session-1", "prompt")

    assert result.user_message_id == "user-1"
    assert result.assistant_message_ids == ["assistant-tool-1"]
    assert persisted_results[0]["content"] == "buffered output"
    assert persisted_results[0]["is_error"] is False
    assert state.active_turn is None
    assert state.dispatcher._current is None
    assert decision_manager.unregistered == ["session-1"]


@pytest.mark.asyncio
async def test_execute_task_streams_thinking_and_retains_plan(monkeypatch) -> None:
    notifications = [
        _notification(
            "item/reasoning/summaryTextDelta",
            ReasoningSummaryTextDeltaNotification(
                itemId="think-1",
                summaryIndex=0,
                delta="reasoning",
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/plan/delta",
            PlanDeltaNotification(
                itemId="plan-1",
                delta="plan text",
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
    ]
    handle = FakeHandle(notifications)
    state = SessionState(
        codex=SimpleNamespace(thread_start=AsyncMock(return_value=FakeThread(handle))),
        dispatcher=CodexSessionApprovalDispatcher(),
    )
    tool = CodexTool(FakeManager(state))
    callbacks = FakeCallbacks()

    monkeypatch.setattr(module, "global_tool_decision_manager", FakeDecisionManager())
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")),
    )
    monkeypatch.setattr(
        tool,
        "_persist_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool, "_save_sdk_session_id", AsyncMock())

    result = await tool.execute_task(
        "session-1",
        "prompt",
        streaming_callbacks=callbacks,
    )

    assert result.raw_sdk_response["plan"] == "plan text"
    assert callbacks.thinking == [
        ("start", "codex-thinking:think-1"),
        ("chunk", "codex-thinking:think-1", "reasoning"),
        ("end", "codex-thinking:think-1"),
    ]


@pytest.mark.asyncio
async def test_execute_task_uses_latest_file_patch_when_final_changes_empty(monkeypatch) -> None:
    initial_change = _change("a.py", "old")
    latest_change = _change("a.py", "new")
    notifications = [
        _notification(
            "item/started",
            ItemStartedNotification(
                item=FileChangeThreadItem(
                    id="file-1",
                    type="fileChange",
                    changes=[initial_change],
                    status=PatchApplyStatus.in_progress,
                ),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/fileChange/patchUpdated",
            FileChangePatchUpdatedNotification(
                itemId="file-1",
                changes=[latest_change],
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=FileChangeThreadItem(
                    id="file-1",
                    type="fileChange",
                    changes=[],
                    status=PatchApplyStatus.completed,
                ),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
    ]
    handle = FakeHandle(notifications)
    state = SessionState(
        codex=SimpleNamespace(thread_start=AsyncMock(return_value=FakeThread(handle))),
        dispatcher=CodexSessionApprovalDispatcher(),
    )
    tool = CodexTool(FakeManager(state))
    persisted_results = []

    monkeypatch.setattr(module, "global_tool_decision_manager", FakeDecisionManager())
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")),
    )
    monkeypatch.setattr(
        tool,
        "_persist_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool, "_save_sdk_session_id", AsyncMock())
    monkeypatch.setattr(
        tool,
        "_persist_file_change_use_message",
        AsyncMock(return_value={"message_id": "assistant-file-1"}),
    )

    async def persist_file_result(**kwargs):
        persisted_results.append(kwargs)
        return {"message_id": "result-1"}

    monkeypatch.setattr(tool, "_persist_file_change_result_message", persist_file_result)

    result = await tool.execute_task("session-1", "prompt")

    assert result.assistant_message_ids == ["assistant-file-1"]
    assert persisted_results[0]["changes"] == [latest_change]
