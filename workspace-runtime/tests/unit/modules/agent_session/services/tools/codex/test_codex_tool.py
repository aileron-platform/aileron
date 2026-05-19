from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from codex_app_server.generated.v2_all import (
    AgentMessageThreadItem,
    CommandExecutionOutputDeltaNotification,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    ErrorNotification,
    FileChangePatchUpdatedNotification,
    FileChangeThreadItem,
    FileUpdateChange,
    ImageGenerationThreadItem,
    ItemCompletedNotification,
    ItemStartedNotification,
    PatchApplyStatus,
    PlanDeltaNotification,
    ReasoningSummaryTextDeltaNotification,
    TurnError,
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
from app.modules.agent_session.services.tools.codex.notification_mapper import (
    ImageGenerationEnd,
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
        self.status_notices = []

    async def on_message_created(self, message):
        self.messages.append(message)

    async def on_thinking_start(self, message_id):
        self.thinking.append(("start", message_id))

    async def on_thinking_chunk(self, message_id, delta):
        self.thinking.append(("chunk", message_id, delta))

    async def on_thinking_end(self, message_id):
        self.thinking.append(("end", message_id))

    async def on_status_notice(self, notice):
        self.status_notices.append(notice)


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
        self.turn_calls = []

    async def turn(self, *_args, **_kwargs):
        self.turn_calls.append((_args, _kwargs))
        return self._handle


class FakeManager:
    def __init__(self, state) -> None:
        self.state = state

    async def get_or_create(self, *_args, **_kwargs):
        return self.state

    async def get_state(self, *_args, **_kwargs):
        return self.state


class RecoveringManager:
    def __init__(self, states) -> None:
        self.states = list(states)
        self.get_or_create_calls = 0
        self.closed_sessions = []

    async def get_or_create(self, *_args, **_kwargs):
        state = self.states[min(self.get_or_create_calls, len(self.states) - 1)]
        self.get_or_create_calls += 1
        return state

    async def close_session(self, session_id) -> None:
        self.closed_sessions.append(session_id)


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
        AsyncMock(
            return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")
        ),
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
async def test_execute_task_recovers_from_stale_codex_process_broken_pipe(monkeypatch) -> None:
    class BrokenThread:
        async def turn(self, *_args, **_kwargs):
            raise BrokenPipeError(32, "Broken pipe")

    notifications = [
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=AgentMessageThreadItem(
                    id="msg-1",
                    text="final response",
                    type="agentMessage",
                ),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
    ]
    recovered_handle = FakeHandle(notifications)
    recovered_state = SessionState(
        codex=SimpleNamespace(thread_start=AsyncMock(return_value=FakeThread(recovered_handle))),
        dispatcher=CodexSessionApprovalDispatcher(),
    )
    stale_state = SessionState(
        codex=SimpleNamespace(),
        dispatcher=CodexSessionApprovalDispatcher(),
        thread=BrokenThread(),
    )
    manager = RecoveringManager([stale_state, recovered_state])
    tool = CodexTool(manager)

    monkeypatch.setattr(module, "global_tool_decision_manager", FakeDecisionManager())
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(
            return_value=(
                SimpleNamespace(sdk_session_id="thread-1"),
                None,
                "/workspace",
            )
        ),
    )
    monkeypatch.setattr(
        tool,
        "_persist_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool, "_save_sdk_session_id", AsyncMock())
    async def finalize_text(
        _session_id,
        _task_id,
        _event,
        _text_message_ids,
        assistant_message_ids,
        _streaming_callbacks,
    ):
        assistant_message_ids.append("assistant-1")

    monkeypatch.setattr(tool, "_finalize_text_message", finalize_text)

    result = await tool.execute_task("session-1", "prompt")

    assert manager.closed_sessions == ["session-1"]
    assert manager.get_or_create_calls == 2
    assert result.user_message_id == "user-1"
    assert result.assistant_message_ids == ["assistant-1"]
    assert stale_state.dispatcher._current is None
    assert recovered_state.active_turn is None


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
async def test_execute_task_persists_image_generation_and_skips_empty_final_text(monkeypatch) -> None:
    notifications = [
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=ImageGenerationThreadItem.model_validate(
                    {
                        "id": "image-1",
                        "type": "imageGeneration",
                        "status": "completed",
                        "result": "result-data",
                        "savedPath": "/tmp/image.png",
                    }
                ),
                threadId="thread-1",
                turnId="turn-1",
            ),
        ),
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=AgentMessageThreadItem(
                    id="msg-1",
                    text="",
                    type="agentMessage",
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
    persisted_images = []
    finalized_text = AsyncMock()

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

    async def persist_image(**kwargs):
        persisted_images.append(kwargs)
        return {"message_id": "assistant-image-1"}

    monkeypatch.setattr(tool, "_persist_image_generation_message", persist_image)
    monkeypatch.setattr(tool, "_finalize_text_message", finalized_text)

    result = await tool.execute_task("session-1", "prompt")

    assert result.assistant_message_ids == ["assistant-image-1"]
    assert persisted_images[0]["event"].item_id == "image-1"
    assert result.raw_sdk_response["generated_images"] == [
        {
            "item_id": "image-1",
            "status": "completed",
            "saved_path": "/tmp/image.png",
            "revised_prompt": None,
        }
    ]
    finalized_text.assert_not_called()


@pytest.mark.asyncio
async def test_persist_image_generation_message_uses_base64_source(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"image-bytes")
    tool = CodexTool(FakeManager(SimpleNamespace()))
    persisted_blocks = []

    async def persist_blocks(session_id, task_id, blocks):
        persisted_blocks.append(
            {"session_id": session_id, "task_id": task_id, "blocks": blocks}
        )
        return {"message_id": "assistant-image-1", "content_blocks": blocks}

    monkeypatch.setattr(tool, "_persist_assistant_blocks", persist_blocks)

    message = await tool._persist_image_generation_message(
        session_id="session-1",
        task_id="task-1",
        event=ImageGenerationEnd(
            item_id="image-1",
            status="completed",
            result="",
            saved_path=str(image_path),
            revised_prompt=None,
        ),
    )

    assert message["message_id"] == "assistant-image-1"
    assert persisted_blocks == [
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "blocks": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "aW1hZ2UtYnl0ZXM=",
                        "path": str(image_path),
                    },
                }
            ],
        }
    ]


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
async def test_execute_task_keeps_streaming_when_codex_reports_retrying_error(
    monkeypatch,
) -> None:
    notifications = [
        _notification(
            "turn/error",
            ErrorNotification(
                error=TurnError(message="Reconnecting... 3/5"),
                threadId="thread-1",
                turnId="turn-1",
                willRetry=True,
            ),
        ),
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=AgentMessageThreadItem(
                    id="msg-1",
                    text="final response",
                    type="agentMessage",
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
    finalized_text = AsyncMock(return_value="assistant-text-1")

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
    monkeypatch.setattr(tool, "_finalize_text_message", finalized_text)

    result = await tool.execute_task("session-1", "prompt")

    assert result.user_message_id == "user-1"
    finalized_text.assert_awaited_once()
    assert state.active_turn is None


@pytest.mark.asyncio
async def test_execute_task_emits_status_notice_for_codex_reconnect(
    monkeypatch,
) -> None:
    notifications = [
        _notification(
            "turn/error",
            ErrorNotification(
                error=TurnError(message="Reconnecting... 2/5"),
                threadId="thread-1",
                turnId="turn-1",
                willRetry=True,
            ),
        ),
        _notification(
            "item/completed",
            ItemCompletedNotification(
                item=AgentMessageThreadItem(
                    id="msg-1",
                    text="final response",
                    type="agentMessage",
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
    callbacks = FakeCallbacks()

    monkeypatch.setattr(module, "global_tool_decision_manager", FakeDecisionManager())
    monkeypatch.setattr(
        tool,
        "_load_session_context",
        AsyncMock(
            return_value=(SimpleNamespace(sdk_session_id=None), None, "/workspace")
        ),
    )
    monkeypatch.setattr(
        tool,
        "_persist_user_message",
        AsyncMock(return_value={"message_id": "user-1"}),
    )
    monkeypatch.setattr(tool, "_save_sdk_session_id", AsyncMock())
    monkeypatch.setattr(tool, "_finalize_text_message", AsyncMock())

    await tool.execute_task(
        "session-1",
        "prompt",
        task_id="task-1",
        streaming_callbacks=callbacks,
    )

    assert callbacks.status_notices == [
        {
            "message_key": "workspace.chat.status.codexReconnecting",
            "severity": "warning",
            "params": {
                "attempt": 2,
                "max_attempts": 5,
            },
        }
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


@pytest.mark.asyncio
async def test_execute_task_wraps_string_prompt_in_text_input(monkeypatch) -> None:
    handle = FakeHandle([])
    thread = FakeThread(handle)
    state = SessionState(
        codex=SimpleNamespace(thread_start=AsyncMock(return_value=thread)),
        dispatcher=CodexSessionApprovalDispatcher(),
    )
    tool = CodexTool(FakeManager(state))

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

    await tool.execute_task("session-1", "prompt")

    assert len(thread.turn_calls) == 1
    args, kwargs = thread.turn_calls[0]
    assert kwargs == {}
    assert len(args) == 1
    assert len(args[0]) == 1
    assert type(args[0][0]).__name__ == "TextInput"
    assert args[0][0].text == "prompt"
