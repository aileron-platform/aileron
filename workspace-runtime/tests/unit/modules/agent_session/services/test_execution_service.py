from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.domain.enums import AgenticTool
from app.modules.agent_session.services.execution_service import (
    ExecutionService,
    ExecutionServiceError,
    WebSocketStreamingCallbacks,
)
from app.modules.agent_session.websocket.events import EventType


@pytest.mark.asyncio
async def test_websocket_streaming_callbacks_emit_expected_events() -> None:
    emitter = AsyncMock()
    callbacks = WebSocketStreamingCallbacks(emitter=emitter, session_id="session-1", task_id="task-1")

    await callbacks.on_stream_start("msg-1")
    await callbacks.on_stream_chunk("msg-1", "chunk")
    await callbacks.on_stream_end("msg-1")
    await callbacks.on_thinking_start("msg-1")
    await callbacks.on_thinking_chunk("msg-1", "thinking")
    await callbacks.on_thinking_end("msg-1")
    await callbacks.on_message_created({"message_id": "msg-1", "content": "hello"})

    assert emitter.emit.await_count == 7
    emitted_event = emitter.emit.await_args_list[0].args[0]
    assert emitted_event.type == EventType.STREAMING_START


@pytest.mark.asyncio
async def test_message_created_can_arrive_before_task_completed() -> None:
    emitted_types: list[EventType] = []

    class FakeEmitter:
        async def emit(self, event) -> None:
            emitted_types.append(event.type)

        async def emit_task_completed(self, session_id: str, task_id: str, **_: object) -> None:
            emitted_types.append(EventType.TASK_COMPLETED)

    emitter = FakeEmitter()
    callbacks = WebSocketStreamingCallbacks(emitter=emitter, session_id="session-1", task_id="task-1")

    await callbacks.on_stream_start("msg-1")
    await callbacks.on_message_created({"message_id": "msg-1", "content": "partial"})
    await callbacks.on_stream_end("msg-1")
    await emitter.emit_task_completed("session-1", "task-1")

    assert emitted_types == [
        EventType.STREAMING_START,
        EventType.MESSAGES_CREATED,
        EventType.STREAMING_END,
        EventType.TASK_COMPLETED,
    ]


def test_emit_event_handles_special_generic_and_unknown_events(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted_events: list = []

    class FakeEmitter:
        async def emit(self, event) -> None:
            emitted_events.append(event)

    emitter = FakeEmitter()
    callbacks = WebSocketStreamingCallbacks(emitter=emitter, session_id="session-1", task_id="task-1")

    class FakeLoop:
        def is_running(self) -> bool:
            return False

        def run_until_complete(self, coro):
            asyncio.run(coro)

    monkeypatch.setattr("app.modules.agent_session.services.execution_service.asyncio.get_event_loop", lambda: FakeLoop())

    callbacks.emit_event("tool-decision:approved", {"request_id": "req-1", "scope": "session"})
    callbacks.emit_event("task:completed", {"ok": True})
    callbacks.emit_event("unknown-event", {"ignored": True})

    assert [event.type for event in emitted_events] == [
        EventType.TOOL_DECISION_APPROVED,
        EventType.TASK_COMPLETED,
    ]


def test_emit_event_falls_back_to_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    emitter = AsyncMock()
    callbacks = WebSocketStreamingCallbacks(emitter=emitter, session_id="session-1", task_id="task-1")
    run_mock = Mock()

    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.asyncio.get_event_loop",
        Mock(side_effect=RuntimeError("no loop")),
    )
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.asyncio.run", run_mock)

    callbacks.emit_event("tool-decision:denied", {"request_id": "req-1", "reason": "no"})

    run_mock.assert_called_once()


def test_execution_service_lock_management_and_context_window() -> None:
    ExecutionService._queue_processing_locks = {}
    ExecutionService._session_execution_locks = {}

    assert ExecutionService.cleanup_session_lock("missing") is False

    ExecutionService._queue_processing_locks["active"] = asyncio.Lock()
    ExecutionService._queue_processing_locks["stale"] = asyncio.Lock()
    assert ExecutionService.get_lock_count() == 2
    assert ExecutionService.cleanup_session_lock("active") is True
    assert ExecutionService.get_lock_count() == 1
    assert ExecutionService.cleanup_stale_locks({"other"}) == 1
    assert ExecutionService.get_lock_count() == 0

    lock = ExecutionService._get_execution_lock("session-1")
    assert lock is ExecutionService._get_execution_lock("session-1")
    ExecutionService.cleanup_execution_lock("session-1")
    assert "session-1" not in ExecutionService._session_execution_locks

    assert ExecutionService._compute_context_window(None) is None
    assert ExecutionService._compute_context_window(
        {"type": "claude", "response": {"usage": {"input_tokens": 10, "output_tokens": 5}}}
    ) == 15
    assert ExecutionService._compute_context_window(
        {"type": "codex", "response": {"turn": {"usage": {"total_tokens": 11}}}}
    ) == 11
    assert ExecutionService._compute_context_window(
        {"type": "gemini", "response": {"usageMetadata": {"totalTokenCount": 9}}}
    ) == 9
    assert ExecutionService._compute_context_window(
        {"type": "opencode", "response": {"usage": {"prompt_tokens": 4, "completion_tokens": 3}}}
    ) == 7
    assert ExecutionService._compute_context_window({"type": "claude", "response": None}) is None


@pytest.mark.asyncio
async def test_stop_task_uses_explicit_and_inferred_tool_type() -> None:
    service = object.__new__(ExecutionService)
    service.emitter = AsyncMock()
    service.session_service = AsyncMock()
    tool = AsyncMock()
    tool.stop_task.return_value = {"stopped": True}
    service.get_tool = Mock(return_value=tool)

    result = await ExecutionService.stop_task(service, "session-1", "task-1", tool_type="codex")

    assert result == {"stopped": True}
    service.emitter.emit_task_stop_ack.assert_awaited_once_with(session_id="session-1", task_id="task-1")
    service.get_tool.assert_called_once_with("codex")

    service = object.__new__(ExecutionService)
    service.emitter = AsyncMock()
    service.session_service = AsyncMock()
    service.session_service.get_session.return_value = SimpleNamespace(agentic_tool=AgenticTool.GEMINI)
    tool = AsyncMock()
    tool.stop_task.return_value = {"stopped": True}
    service.get_tool = Mock(return_value=tool)

    await ExecutionService.stop_task(service, "session-2", "task-2")
    service.get_tool.assert_called_once_with("gemini")

    service.session_service.get_session.return_value = None
    with pytest.raises(ExecutionServiceError, match="Session not found"):
        await ExecutionService.stop_task(service, "missing", "task-3")


@pytest.mark.asyncio
async def test_publish_automation_completed_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = object.__new__(ExecutionService)
    service.session_service = AsyncMock()
    service.session_service.get_session.return_value = SimpleNamespace(workspace_id="ws-1", message_count=3)
    publisher = AsyncMock()
    monkeypatch.setattr("app.core.redis_publisher.get_redis_publisher", Mock(return_value=publisher))

    await ExecutionService._publish_automation_completed(
        service,
        execution_id="exec-1",
        session_id="session-1",
        status="completed",
        has_error=False,
    )

    publisher.publish_execution_completed.assert_awaited_once_with(
        execution_id="exec-1",
        session_id="session-1",
        workspace_id="ws-1",
        status="completed",
        total_messages=3,
        has_error=False,
        error_message=None,
    )

    service.session_service.get_session.side_effect = RuntimeError("broken")
    await ExecutionService._publish_automation_completed(
        service,
        execution_id="exec-2",
        session_id="session-2",
        status="failed",
        has_error=True,
        error_message="boom",
    )


@pytest.mark.asyncio
async def test_get_tool_and_execute_prompt_queue_paths() -> None:
    service = object.__new__(ExecutionService)
    service.tools = {"claude-code": AsyncMock()}
    service.message_service = AsyncMock()
    service.emitter = AsyncMock()
    service._active_executions = {}

    assert service.get_tool("claude-code") is service.tools["claude-code"]
    with pytest.raises(ValueError, match="Unknown tool type"):
        service.get_tool("missing")

    lock = ExecutionService._get_execution_lock("queued-session")
    await lock.acquire()
    try:
        queued_message = SimpleNamespace(id="msg-1", queue_position=2)
        service.message_service.count_queued_messages = AsyncMock(return_value=1)
        service.message_service.create_queued_message = AsyncMock(return_value=queued_message)

        result = await ExecutionService.execute_prompt(service, "queued-session", "hello")

        assert result["status"] == "queued"
        assert result["queue_position"] == 2
        emitted_event = service.emitter.emit.await_args.args[0]
        assert emitted_event.type == EventType.MESSAGES_QUEUED
    finally:
        lock.release()
        ExecutionService.cleanup_execution_lock("queued-session")

    lock = ExecutionService._get_execution_lock("full-session")
    await lock.acquire()
    try:
        service.message_service.count_queued_messages = AsyncMock(return_value=ExecutionService.MAX_QUEUE_SIZE)
        with pytest.raises(ExecutionServiceError, match="Queue is full"):
            await ExecutionService.execute_prompt(service, "full-session", "hello")
    finally:
        lock.release()
        ExecutionService.cleanup_execution_lock("full-session")


@pytest.mark.asyncio
async def test_execute_prompt_uses_internal_when_lock_is_free() -> None:
    service = object.__new__(ExecutionService)
    service._active_executions = {}
    service._execute_prompt_internal = AsyncMock(return_value={"status": "running"})

    result = await ExecutionService.execute_prompt(service, "session-1", "run now", stream=False)

    assert result == {"status": "running"}
    service._execute_prompt_internal.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_prompt_internal_handles_missing_session_and_active_task_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    service = object.__new__(ExecutionService)
    service.session_service = AsyncMock()
    service.task_service = AsyncMock()
    service.message_service = AsyncMock()
    service.emitter = AsyncMock()
    service._active_executions = {}

    service.session_service.get_session.return_value = None
    with pytest.raises(ExecutionServiceError, match="Session not found"):
        await ExecutionService._execute_prompt_internal(service, "missing", "prompt")

    service.session_service.get_session.return_value = SimpleNamespace(agentic_tool=AgenticTool.CLAUDE_CODE)
    service.task_service.get_active_tasks = AsyncMock(return_value=[SimpleNamespace(id="task-running")])
    service.message_service.count_queued_messages = AsyncMock(return_value=0)
    service.message_service.create_queued_message = AsyncMock(return_value=SimpleNamespace(id="msg-2", queue_position=1))

    result = await ExecutionService._execute_prompt_internal(service, "session-1", "queued prompt")

    assert result["status"] == "queued"
    emitted_event = service.emitter.emit.await_args.args[0]
    assert emitted_event.type == EventType.MESSAGES_QUEUED

    service.message_service.count_queued_messages = AsyncMock(return_value=ExecutionService.MAX_QUEUE_SIZE)
    with pytest.raises(ExecutionServiceError, match="Queue is full"):
        await ExecutionService._execute_prompt_internal(service, "session-1", "overflow")


@pytest.mark.asyncio
async def test_execute_prompt_internal_starts_task_and_tracks_background_job(monkeypatch: pytest.MonkeyPatch) -> None:
    service = object.__new__(ExecutionService)
    service.session_service = AsyncMock()
    service.task_service = AsyncMock()
    service.message_service = AsyncMock()
    service.emitter = AsyncMock()
    service._active_executions = {}

    session = SimpleNamespace(agentic_tool=AgenticTool.GEMINI)
    task = SimpleNamespace(id="task-1")
    service.session_service.get_session.return_value = session
    service.task_service.get_active_tasks = AsyncMock(return_value=[])

    committed_task_service = AsyncMock()
    committed_task_service.create_task = AsyncMock(return_value=task)
    committed_task_service.start_task = AsyncMock()

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock()

    monkeypatch.setattr("app.modules.agent_session.services.execution_service.async_session_scope", fake_scope)
    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.TaskService",
        lambda db, emitter=None: committed_task_service,
    )

    created_tasks: list[str] = []

    def fake_create_task(coro):
        created_tasks.append(type(coro).__name__)
        coro.close()
        return Mock(name="bg-task")

    monkeypatch.setattr("app.modules.agent_session.services.execution_service.asyncio.create_task", fake_create_task)

    result = await ExecutionService._execute_prompt_internal(service, "session-1", "real prompt", stream=True)

    assert result == {"success": True, "task_id": "task-1", "status": "running", "streaming": True}
    committed_task_service.create_task.assert_awaited_once_with(
        session_id="session-1",
        full_prompt="real prompt",
        created_by="anonymous",
    )
    committed_task_service.start_task.assert_awaited_once_with("task-1")
    service.emitter.emit_task_started.assert_awaited_once()
    assert service._active_executions["task-1"]._extract_mock_name() == "bg-task"
    assert created_tasks


@pytest.mark.asyncio
async def test_execute_in_background_success_stopped_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = object.__new__(ExecutionService)
    service.emitter = AsyncMock()
    service._active_executions = {"task-1": Mock()}
    cleanup_tool = AsyncMock()
    cleanup_tool.prompt_service = AsyncMock()
    cleanup_tool.prompt_service.cleanup_client = AsyncMock()
    service.get_tool = Mock(return_value=cleanup_tool)

    task_service = AsyncMock()
    session_service = AsyncMock()
    message_service = AsyncMock()
    message_repo = AsyncMock()
    session_repo = AsyncMock()

    @asynccontextmanager
    async def fake_scope():
        yield AsyncMock(commit=AsyncMock())

    monkeypatch.setattr("app.modules.agent_session.services.execution_service.async_session_scope", fake_scope)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.TaskService", lambda db: task_service)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.AgentSessionService", lambda db: session_service)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.MessageService", lambda db: message_service)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.MessageRepository", lambda db: message_repo)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.AgentSessionRepository", lambda db: session_repo)
    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.asyncio.create_task",
        lambda coro: coro.close() or Mock(),
    )

    cleanup_tool.execute_task = AsyncMock(
        return_value=SimpleNamespace(
            was_stopped=False,
            assistant_message_ids=["a1"],
            raw_sdk_response={"type": "claude", "response": {"usage": {"input_tokens": 2, "output_tokens": 3}}},
        )
    )
    task_service.complete_task.return_value = SimpleNamespace(
        duration_ms=1234,
        raw_sdk_response={"type": "claude", "response": {"usage": {"input_tokens": 2, "output_tokens": 3}}},
    )
    await ExecutionService._execute_in_background(
        service,
        session_id="session-1",
        prompt="ok",
        task_id="task-1",
        stream=True,
        tool_type="claude-code",
        automation_execution_id="exec-1",
    )
    task_service.complete_task.assert_awaited_once_with(
        "task-1",
        raw_sdk_response={"type": "claude", "response": {"usage": {"input_tokens": 2, "output_tokens": 3}}},
        computed_context_window=5,
    )
    service.emitter.emit_task_completed.assert_awaited_once_with(
        session_id="session-1",
        task_id="task-1",
        duration_ms=1234,
        token_usage={
            "input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 5,
        },
    )
    assert "task-1" not in service._active_executions

    service._active_executions = {"task-2": Mock()}
    cleanup_tool.execute_task = AsyncMock(
        return_value=SimpleNamespace(was_stopped=True, assistant_message_ids=[], raw_sdk_response=None)
    )
    service._publish_automation_completed = AsyncMock()
    await ExecutionService._execute_in_background(
        service,
        session_id="session-2",
        prompt="stop",
        task_id="task-2",
        stream=False,
        tool_type="claude-code",
        automation_execution_id="exec-2",
    )
    task_service.stop_task.assert_awaited_once_with("task-2")
    service.emitter.emit_task_stopped.assert_awaited_once()

    service._active_executions = {"task-3": Mock()}
    cleanup_tool.execute_task = AsyncMock(side_effect=RuntimeError("boom"))
    await ExecutionService._execute_in_background(
        service,
        session_id="session-3",
        prompt="fail",
        task_id="task-3",
        stream=True,
        tool_type="claude-code",
        automation_execution_id="exec-3",
    )
    task_service.fail_task.assert_awaited_once_with("task-3", error_message="boom")
    service.emitter.emit_task_failed.assert_awaited_once()
    service.emitter.emit_streaming_error.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_queue_and_internal_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = object.__new__(ExecutionService)
    service.emitter = AsyncMock()

    called_sessions: list[str] = []

    async def fake_internal(session_id: str) -> None:
        called_sessions.append(session_id)

    service._process_queue_internal = fake_internal
    ExecutionService._queue_processing_locks = {}

    await ExecutionService._process_queue(service, "session-1")
    assert called_sessions == ["session-1"]

    lock = asyncio.Lock()
    await lock.acquire()
    ExecutionService._queue_processing_locks = {"session-2": lock}
    try:
        await ExecutionService._process_queue(service, "session-2")
        assert called_sessions == ["session-1"]
    finally:
        lock.release()

    queued_entity = SimpleNamespace(id="msg-1", queue_position=3, content=[{"type": "text", "text": "hello"}])
    first_db = AsyncMock()
    second_db = AsyncMock(commit=AsyncMock())

    class FakeMessageRepo:
        def __init__(self, db):
            self.db = db

        async def get_next_queued(self, session_id):
            return SimpleNamespace(id="raw")

        def to_entity(self, model):
            return queued_entity

    exec_instance = AsyncMock()
    exec_instance.execute_prompt = AsyncMock(return_value={"success": True})

    @asynccontextmanager
    async def fake_scope_success():
        yield fake_scope_success.dbs.pop(0)

    fake_scope_success.dbs = [first_db, second_db]
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.async_session_scope", fake_scope_success)
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.MessageRepository", FakeMessageRepo)
    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.AgentSessionService",
        lambda db: AsyncMock(get_session=AsyncMock(return_value=SimpleNamespace(id="session-1"))),
    )
    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.TaskService",
        lambda db: AsyncMock(get_active_tasks=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.modules.agent_session.services.execution_service.MessageService",
        lambda db: AsyncMock(delete_queued_message=AsyncMock()),
    )
    monkeypatch.setattr("app.modules.agent_session.services.execution_service.ExecutionService", lambda db: exec_instance)

    await ExecutionService._process_queue_internal(service, "session-1")
    service.emitter.emit.assert_awaited_once()
    assert service.emitter.emit.await_args.args[0].type == EventType.MESSAGE_DEQUEUED

    service.emitter.emit.reset_mock()
    exec_instance.execute_prompt = AsyncMock(side_effect=RuntimeError("queue fail"))
    fake_scope_success.dbs = [first_db, second_db]
    await ExecutionService._process_queue_internal(service, "session-1")
    assert service.emitter.emit.await_args.args[0].type == EventType.QUEUE_PROCESSING_FAILED
