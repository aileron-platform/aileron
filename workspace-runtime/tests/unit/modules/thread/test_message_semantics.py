from __future__ import annotations

from tempfile import SpooledTemporaryFile
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import Headers

from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.persistence_models import ThreadModel
from app.modules.thread.message_repository import (
    ThreadMessageRepository,
)
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.thread.attachments import (
    ThreadAttachmentService,
)
from app.modules.thread.lifecycle import ThreadApiError, ThreadService
from tests.unit.modules.thread.db_fixture import (
    drop_thread_tables,
    list_thread_messages,
    reset_thread_tables,
)


def make_capabilities() -> dict:
    return {
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8"],
                "default_model": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            }
        ],
        "default_tool": "claude",
    }


@pytest.fixture
async def message_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as conn:
        await reset_thread_tables(conn)

    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as conn:
        await drop_thread_tables(conn)


@dataclass
class FakeRunner:
    requests: list[AgentExecutionRequest] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    callbacks: dict[str, Callable[[AgentEvent], Awaitable[None]]] = field(
        default_factory=dict
    )
    reserved: list[str] = field(default_factory=list)

    def reserve(self) -> str:
        execution_id = f"session-{len(self.reserved) + 1}"
        self.reserved.append(execution_id)
        return execution_id

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        assert execution_id in self.reserved
        self.requests.append(request)
        self.callbacks[execution_id] = on_event

    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)

    async def wait(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return execution_id not in self.stopped


@dataclass
class DeadRunner(FakeRunner):
    def is_alive(self, execution_id: str) -> bool:
        return False


@dataclass
class FailingStopRunner(FakeRunner):
    alive: bool = True

    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)
        self.alive = False
        raise RuntimeError("stop failed after client disconnect")

    def is_alive(self, execution_id: str) -> bool:
        return self.alive


@dataclass
class StuckRunner(FakeRunner):
    """A runner that never confirms termination after `stop()`."""

    def is_alive(self, execution_id: str) -> bool:
        return True


class TransitionBeforeLockRepository:
    def __init__(
        self,
        inner: ThreadRepository,
        *,
        transition_to: ThreadStatus,
        active_turn_execution_id: str | None = None,
    ) -> None:
        self.inner = inner
        self.transition_to = transition_to
        self.active_turn_execution_id = active_turn_execution_id
        self.transitioned = False

    async def get(self, thread_id: str, user_id: str) -> ThreadModel | None:
        return await self.inner.get(thread_id, user_id=user_id)

    async def locked_update(
        self,
        thread_id: str,
        mutate: Callable[[ThreadModel], None],
    ) -> ThreadModel | None:
        if not self.transitioned:
            self.transitioned = True

            def transition(model: ThreadModel) -> None:
                model.status = self.transition_to.value
                model.active_turn_execution_id = self.active_turn_execution_id

            await self.inner.locked_update(thread_id, transition)
        return await self.inner.locked_update(thread_id, mutate)


class FakeSink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(
        self,
        user_id: str | None,
        workspace_id: str,
        thread_id: str,
        type_: str,
        status: str | None = None,
        **event_data: Any,
    ) -> None:
        self.events.append(
            {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "thread_id": thread_id,
                "type": type_,
                "status": status,
                **event_data,
            }
        )


def make_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    file = SpooledTemporaryFile()
    file.write(content)
    file.seek(0)
    return UploadFile(
        filename=filename,
        file=file,
        headers=Headers({"content-type": content_type}),
    )


async def make_service(
    session: AsyncSession,
    *,
    runner: FakeRunner | None = None,
    sink: FakeSink | None = None,
    attachment_service: ThreadAttachmentService | None = None,
    event_session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> tuple[ThreadService, FakeRunner, FakeSink]:
    await CapabilitiesStore().put(session, "workspace-a", make_capabilities())
    await session.commit()
    fake_runner = runner or FakeRunner()
    fake_sink = sink or FakeSink()
    return (
        ThreadService(
            session,
            workspace_id="workspace-a",
            runner=fake_runner,
            invalidation_sink=fake_sink,
            attachment_service=attachment_service,
            event_session_factory=event_session_factory,
        ),
        fake_runner,
        fake_sink,
    )


async def create_thread(
    session: AsyncSession,
    *,
    status: ThreadStatus,
    user_id: str = "user-a",
    origin: str = "user",
    active_turn_execution_id: str | None = None,
    error_code: str | None = None,
    error_info: dict[str, Any] | None = None,
    error_message: str | None = None,
    queued_messages: list[dict[str, Any]] | None = None,
) -> ThreadModel:
    thread = await ThreadRepository(session, workspace_id="workspace-a").create(
        ThreadModel(
            id=f"{status.value}-thread",
            workspace_id="workspace-a",
            user_id=user_id,
            origin=origin,
            title="Existing thread",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=status.value,
            queued_messages=queued_messages or [],
            draft_message=None,
            error_code=error_code,
            error_info=error_info,
            error_message=error_message,
            archived=False,
        )
    )
    if status != ThreadStatus.DRAFT:
        turn_repo = ThreadTurnRepository(session)
        turn = await turn_repo.create_turn(
            thread=thread,
            turn_id=f"{thread.id}-turn",
            status=status.value,
        )
        execution_id = active_turn_execution_id or "execution-1"
        execution = await turn_repo.create_execution(
            thread=thread,
            turn=turn,
            execution_id=execution_id,
            agentic_tool=thread.agentic_tool,
            status=status.value,
        )
        turn.status = status.value
        execution.status = status.value
        should_be_active = status in {
            ThreadStatus.QUEUED,
            ThreadStatus.BOOTING,
            ThreadStatus.WORKING,
            ThreadStatus.STOPPING,
        }
        if should_be_active:
            thread.active_turn_id = turn.id
            thread.active_turn_execution_id = execution.id
        else:
            thread.active_turn_id = None
            thread.active_turn_execution_id = None
        await ThreadMessageRepository(session).append(
            thread.id,
            turn.id,
            execution.id,
            "user",
            {"parts": [{"type": "text", "text": "original prompt"}]},
            source_event_key=f"seed:{thread.id}",
        )
    await session.commit()
    return thread


@pytest.mark.asyncio
async def test_post_message_queues_payload_while_thread_is_running(
    message_session: AsyncSession,
    tmp_path,
) -> None:
    attachment_service = ThreadAttachmentService(storage_root=tmp_path)
    service, runner, sink = await make_service(
        message_session,
        attachment_service=attachment_service,
    )
    thread = await create_thread(message_session, status=ThreadStatus.WORKING)
    image = await attachment_service.save_upload(
        thread_id=thread.id,
        upload=make_upload_file(b"image-a", "image-a.png", "image/png"),
    )

    updated = await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={
            "text": "follow later",
            "attachments": [{"attachmentId": image.attachment_id}],
        },
    )

    assert updated.status == ThreadStatus.WORKING.value
    assert len(updated.queued_messages) == 1
    assert isinstance(updated.queued_messages[0]["id"], str)
    assert updated.queued_messages[0]["id"]
    assert updated.queued_messages[0]["text"] == "follow later"
    assert updated.queued_messages[0]["attachments"] == [
        {
            "type": "image",
            "attachmentId": image.attachment_id,
            "name": "image-a.png",
            "mimeType": "image/png",
            "size": len(b"image-a"),
        }
    ]
    assert len(runner.requests) == 0
    assert sink.events[-1]["type"] == "messages_updated"


@pytest.mark.asyncio
async def test_post_message_queues_payload_while_thread_is_stopping(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.STOPPING)

    updated = await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "arrived mid-stop", "attachments": []},
    )

    assert updated.status == ThreadStatus.STOPPING.value
    assert [message["text"] for message in updated.queued_messages] == [
        "arrived mid-stop"
    ]
    assert len(runner.requests) == 0


@pytest.mark.asyncio
async def test_post_message_after_terminal_status_starts_follow_up_run_with_locked_settings(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.COMPLETE)

    updated = await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "next prompt", "attachments": []},
    )

    messages = await list_thread_messages(message_session, thread.id)
    assert updated.status == ThreadStatus.QUEUED.value
    assert updated.agentic_tool == "claude"
    assert updated.model == "claude-opus-4-8"
    assert updated.claude_mode == "execute"
    assert [message.type for message in messages] == ["user", "user"]
    assert messages[-1].content == {"parts": [{"type": "text", "text": "next prompt"}]}
    assert runner.requests[-1].prompt_text == "next prompt"


@pytest.mark.asyncio
async def test_post_message_rechecks_running_status_before_queue_append(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.WORKING)
    service.thread_repo = TransitionBeforeLockRepository(
        service.thread_repo,
        transition_to=ThreadStatus.COMPLETE,
        active_turn_execution_id=None,
    )

    updated = await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "follow up", "attachments": []},
    )

    messages = await list_thread_messages(message_session, thread.id)
    assert updated.status == ThreadStatus.QUEUED.value
    assert updated.queued_messages == []
    assert [message.type for message in messages] == ["user", "user"]
    assert messages[-1].content == {"parts": [{"type": "text", "text": "follow up"}]}
    assert len(runner.requests) == 1
    assert runner.requests[-1].prompt_text == "follow up"


@pytest.mark.asyncio
async def test_post_message_rejects_draft_threads(
    message_session: AsyncSession,
) -> None:
    service, _runner, _sink = await make_service(message_session)
    draft = await create_thread(
        message_session, status=ThreadStatus.DRAFT, active_turn_execution_id=None
    )

    with pytest.raises(ThreadApiError) as draft_error:
        await service.post_message(
            thread_id=draft.id,
            user_id="user-a",
            message={"text": "wrong path", "attachments": []},
        )

    assert draft_error.value.status_code == 422
    assert draft_error.value.error_code == "use_submit_for_draft"


@pytest.mark.asyncio
async def test_post_message_after_error_starts_follow_up_run_with_new_message(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.ERROR,
        error_code="agent_error",
        error_info={"exit_code": 1},
    )

    updated = await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "try a different approach", "attachments": []},
    )

    messages = await list_thread_messages(message_session, thread.id)
    assert updated.status == ThreadStatus.QUEUED.value
    assert updated.error_code is None
    assert updated.error_info is None
    assert [message.type for message in messages] == ["user", "user"]
    assert messages[-1].content == {
        "parts": [{"type": "text", "text": "try a different approach"}]
    }
    assert runner.requests[-1].prompt_text == "try a different approach"


@pytest.mark.asyncio
async def test_retry_only_error_threads_clears_error_and_restarts_without_new_messages(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.ERROR,
        error_code="agent_error",
        error_info={"exit_code": 1},
        error_message="failed",
    )
    before = await list_thread_messages(message_session, thread.id)

    updated = await service.retry_thread(thread_id=thread.id, user_id="user-a")

    after = await list_thread_messages(message_session, thread.id)
    assert updated.status == ThreadStatus.QUEUED.value
    assert updated.error_code is None
    assert updated.error_info is None
    assert updated.error_message is None
    assert [message.id for message in after] == [message.id for message in before]
    assert runner.requests[-1].prompt_text == "original prompt"


@pytest.mark.asyncio
async def test_retry_rejects_non_error_thread(
    message_session: AsyncSession,
) -> None:
    service, _runner, _sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.COMPLETE)

    with pytest.raises(ThreadApiError) as exc_info:
        await service.retry_thread(thread_id=thread.id, user_id="user-a")

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "invalid_state"


@pytest.mark.asyncio
async def test_get_thread_reconciles_stale_queued_runner(
    message_session: AsyncSession,
) -> None:
    service, _runner, sink = await make_service(
        message_session,
        runner=DeadRunner(),
    )
    thread = await create_thread(
        message_session,
        status=ThreadStatus.QUEUED,
        active_turn_execution_id="missing-execution",
    )

    detail = await service.get_thread(thread.id, user_id="user-a")
    stored = await ThreadRepository(
        message_session, workspace_id="workspace-a"
    ).locked_update(thread.id, lambda model: None)

    assert detail.status == ThreadStatus.ERROR.value
    assert detail.active_turn_execution_id is None
    assert detail.error_code == "runtime_restarted"
    assert detail.error_info == {"active_execution_id": "missing-execution"}
    assert stored is not None
    assert stored.status == ThreadStatus.ERROR.value
    assert stored.active_turn_execution_id is None
    assert sink.events[-1]["user_id"] == "user-a"
    assert sink.events[-1]["workspace_id"] == "workspace-a"
    assert sink.events[-1]["thread_id"] == thread.id
    assert sink.events[-1]["type"] == "status_updated"
    assert sink.events[-1]["status"] == ThreadStatus.ERROR.value


@pytest.mark.asyncio
async def test_list_threads_reconciles_stale_queued_runner(
    message_session: AsyncSession,
) -> None:
    service, _runner, _sink = await make_service(
        message_session,
        runner=DeadRunner(),
    )
    thread = await create_thread(
        message_session,
        status=ThreadStatus.QUEUED,
        active_turn_execution_id="missing-execution",
    )

    summaries = await service.list_threads(user_id="user-a", archived=False)

    assert [(summary.id, summary.status) for summary in summaries] == [
        (thread.id, ThreadStatus.ERROR.value)
    ]
    assert summaries[0].active_turn_execution_id is None
    assert summaries[0].error_code == "runtime_restarted"


@pytest.mark.asyncio
async def test_get_thread_keeps_reserved_queued_runner_alive(
    message_session: AsyncSession,
) -> None:
    service, _runner, sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.QUEUED,
        active_turn_execution_id="execution-1",
    )

    detail = await service.get_thread(thread.id, user_id="user-a")

    assert detail.status == ThreadStatus.QUEUED.value
    assert detail.active_turn_execution_id == "execution-1"
    assert detail.error_code is None
    assert sink.events == []


@pytest.mark.asyncio
async def test_list_threads_keeps_active_working_runner_alive(
    message_session: AsyncSession,
) -> None:
    service, _runner, sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.WORKING,
        active_turn_execution_id="execution-1",
    )

    summaries = await service.list_threads(user_id="user-a", archived=False)

    assert [(summary.id, summary.status) for summary in summaries] == [
        (thread.id, ThreadStatus.WORKING.value)
    ]
    assert summaries[0].active_turn_execution_id == "execution-1"
    assert summaries[0].error_code is None
    assert sink.events == []


@pytest.mark.asyncio
async def test_get_thread_does_not_reconcile_stopping_thread_as_runtime_restart(
    message_session: AsyncSession,
) -> None:
    service, _runner, sink = await make_service(
        message_session,
        runner=DeadRunner(),
    )
    thread = await create_thread(
        message_session,
        status=ThreadStatus.STOPPING,
        active_turn_execution_id="missing-execution",
    )

    detail = await service.get_thread(thread.id, user_id="user-a")

    assert detail.status == ThreadStatus.STOPPING.value
    assert detail.active_turn_execution_id == "missing-execution"
    assert detail.error_code is None
    assert sink.events == []


@pytest.mark.asyncio
async def test_list_threads_does_not_reconcile_stopping_thread_as_runtime_restart(
    message_session: AsyncSession,
) -> None:
    service, _runner, sink = await make_service(
        message_session,
        runner=DeadRunner(),
    )
    thread = await create_thread(
        message_session,
        status=ThreadStatus.STOPPING,
        active_turn_execution_id="missing-execution",
    )

    summaries = await service.list_threads(user_id="user-a", archived=False)

    assert [(summary.id, summary.status) for summary in summaries] == [
        (thread.id, ThreadStatus.STOPPING.value)
    ]
    assert summaries[0].active_turn_execution_id == "missing-execution"
    assert summaries[0].error_code is None
    assert sink.events == []


@pytest.mark.asyncio
async def test_stop_rejects_non_running_thread(
    message_session: AsyncSession,
) -> None:
    service, _runner, _sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.COMPLETE)

    with pytest.raises(ThreadApiError) as exc_info:
        await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "invalid_state"


@pytest.mark.asyncio
async def test_stop_queued_thread_transitions_through_stopping_to_canceled_and_stops_runner(
    message_session: AsyncSession,
) -> None:
    service, runner, sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.QUEUED)

    updated = await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert updated.status == ThreadStatus.CANCELED.value
    assert runner.stopped == ["execution-1"]
    status_events = [event for event in sink.events if event["type"] == "status_updated"]
    assert [event["status"] for event in status_events[-2:]] == ["stopping", "canceled"]
    timeline_events = [event for event in sink.events if event["type"] == "timeline_updated"]
    assert timeline_events[-1]["user_id"] == "user-a"
    assert timeline_events[-1]["workspace_id"] == "workspace-a"
    assert timeline_events[-1]["thread_id"] == thread.id
    assert timeline_events[-1]["turns"][0]["id"] == f"{thread.id}-turn"


@pytest.mark.asyncio
async def test_stop_working_thread_transitions_through_stopping_to_canceled_and_stops_runner(
    message_session: AsyncSession,
) -> None:
    service, runner, sink = await make_service(message_session)
    thread = await create_thread(message_session, status=ThreadStatus.WORKING)

    updated = await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert updated.status == ThreadStatus.CANCELED.value
    assert runner.stopped == ["execution-1"]
    status_events = [event for event in sink.events if event["type"] == "status_updated"]
    assert [event["status"] for event in status_events[-2:]] == ["stopping", "canceled"]


@pytest.mark.asyncio
async def test_stop_working_thread_finalizes_canceled_after_runner_stop_failure(
    message_session: AsyncSession,
    postgres_engine,
) -> None:
    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    service, runner, sink = await make_service(
        message_session,
        runner=FailingStopRunner(),
        event_session_factory=session_factory,
    )
    thread = await create_thread(message_session, status=ThreadStatus.WORKING)
    thread_id = thread.id

    updated = await service.stop_thread(thread_id=thread_id, user_id="user-a")
    detail = await service.get_thread(thread_id, user_id="user-a")
    stored = await ThreadRepository(
        message_session,
        workspace_id="workspace-a",
    ).get(thread_id, user_id="user-a")

    assert updated.status == ThreadStatus.CANCELED.value
    assert detail.status == ThreadStatus.CANCELED.value
    assert detail.error_code is None
    assert stored is not None
    assert stored.status == ThreadStatus.CANCELED.value
    assert stored.active_turn_execution_id is None
    assert runner.stopped == ["execution-1"]
    status_events = [event for event in sink.events if event["type"] == "status_updated"]
    assert [event["status"] for event in status_events[-2:]] == ["stopping", "canceled"]


@pytest.mark.asyncio
async def test_stop_dequeues_next_message_and_keeps_remainder_in_fifo_order(
    message_session: AsyncSession,
) -> None:
    service, runner, sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.WORKING,
        queued_messages=[
            {"id": "second", "text": "second message"},
            {"id": "third", "text": "third message"},
        ],
    )

    updated = await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert updated.status == ThreadStatus.QUEUED.value
    assert [message["id"] for message in updated.queued_messages] == ["third"]
    assert runner.stopped == ["execution-1"]
    assert len(runner.reserved) == 1
    next_execution_id = runner.reserved[0]
    assert runner.requests[-1].prompt_text == "second message"
    assert next_execution_id in runner.callbacks

    stored = await ThreadRepository(
        message_session, workspace_id="workspace-a"
    ).get(thread.id, user_id="user-a")
    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert stored.active_turn_execution_id == next_execution_id
    assert [message["id"] for message in stored.queued_messages] == ["third"]

    old_execution = await ThreadTurnRepository(message_session).get_execution(
        "execution-1"
    )
    assert old_execution is not None
    assert old_execution.status == "canceled"


@pytest.mark.asyncio
async def test_stop_confirms_runner_stopped_before_dequeuing_next_message(
    message_session: AsyncSession,
) -> None:
    @dataclass
    class OrderTrackingRunner(FakeRunner):
        call_order: list[str] = field(default_factory=list)

        def reserve(self) -> str:
            self.call_order.append("reserve")
            return super().reserve()

        async def stop(self, execution_id: str) -> None:
            self.call_order.append("stop")
            await super().stop(execution_id)

        async def wait(self, execution_id: str) -> None:
            self.call_order.append("wait")
            await super().wait(execution_id)

    tracking_runner = OrderTrackingRunner()
    service, runner, _sink = await make_service(message_session, runner=tracking_runner)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.WORKING,
        queued_messages=[{"id": "second", "text": "second message"}],
    )

    await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert runner.call_order.index("stop") < runner.call_order.index("reserve")
    assert runner.call_order.index("wait") < runner.call_order.index("reserve")


@pytest.mark.asyncio
async def test_stop_confirmation_timeout_keeps_thread_stopping_with_queue_intact(
    message_session: AsyncSession,
) -> None:
    service, runner, sink = await make_service(message_session, runner=StuckRunner())
    thread = await create_thread(
        message_session,
        status=ThreadStatus.WORKING,
        queued_messages=[{"id": "second", "text": "second message"}],
    )

    with pytest.raises(ThreadApiError) as exc_info:
        await service.stop_thread(thread_id=thread.id, user_id="user-a")

    assert exc_info.value.status_code == 503
    assert exc_info.value.error_code == "stop_confirmation_failed"

    stored = await ThreadRepository(
        message_session, workspace_id="workspace-a"
    ).get(thread.id, user_id="user-a")
    assert stored is not None
    assert stored.status == ThreadStatus.STOPPING.value
    assert stored.active_turn_execution_id == "execution-1"
    assert [message["id"] for message in stored.queued_messages] == ["second"]
    assert runner.reserved == []
    status_events = [event for event in sink.events if event["type"] == "status_updated"]
    assert status_events[-1]["status"] == "stopping"


@pytest.mark.asyncio
async def test_repeated_stop_finalize_for_same_execution_is_idempotent(
    message_session: AsyncSession,
) -> None:
    service, runner, _sink = await make_service(message_session)
    thread = await create_thread(
        message_session,
        status=ThreadStatus.WORKING,
        queued_messages=[{"id": "second", "text": "second message"}],
    )

    first = await service._execution.stop_current_turn(thread.id, "execution-1")
    second = await service._execution.stop_current_turn(thread.id, "execution-1")

    assert first is True
    assert second is False
    assert len(runner.reserved) == 1
    assert len(runner.requests) == 1

    stored = await ThreadRepository(
        message_session, workspace_id="workspace-a"
    ).get(thread.id, user_id="user-a")
    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert stored.queued_messages == []
