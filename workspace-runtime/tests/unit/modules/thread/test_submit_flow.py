from __future__ import annotations

import asyncio
import json
import logging
from tempfile import SpooledTemporaryFile
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.thread.domain.context_usage import context_tokens_from_usage
from app.modules.thread.domain.enums import AgenticTool, ThreadStatus
from app.modules.thread.domain.tool_names import (
    QUESTION_EXPIRED_ALREADY_ANSWERED,
    QUESTION_EXPIRED_CODE,
    QUESTION_EXPIRED_NOT_DELIVERED,
    QUESTION_EXPIRED_SUPERSEDED,
    QUESTION_TOOL_NAME,
)
from app.modules.thread.persistence_models import ThreadMessageModel, ThreadModel
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


def make_capabilities(
    models: list[str] | None = None, context_window: int = 200000
) -> dict:
    return {
        "tools": [
            {
                "id": "claude",
                "models": models or ["claude-opus-4-8"],
                "default_model": (models or ["claude-opus-4-8"])[0],
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": context_window,
            },
            {
                "id": "codex",
                "models": ["gpt-5.6-sol"],
                "default_model": "gpt-5.6-sol",
                "context_window": 200000,
            },
            {
                "id": "opencode",
                "models": ["qwen3-coder"],
                "default_model": "qwen3-coder",
                "context_window": 128000,
            },
        ],
        "default_tool": "claude",
    }


@pytest.fixture
async def submit_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
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
    callbacks: dict[str, Callable[[AgentEvent], Awaitable[None]]] = field(
        default_factory=dict
    )
    reserved: list[str] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    destroyed_threads: list[str] = field(default_factory=list)

    def reserve(self) -> str:
        execution_id = f"session-{len(self.reserved) + 1}"
        self.reserved.append(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self.reserved.append(execution_id)

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
        return None

    async def wait(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return True

    async def destroy_thread(self, thread_id: str) -> None:
        self.destroyed_threads.append(thread_id)

    async def dispatch(self, execution_id: str, event: AgentEvent) -> None:
        await self.callbacks[execution_id](event)


@dataclass
class QueueSnapshotRunner(FakeRunner):
    db: AsyncSession | None = None
    workspace_id: str = "workspace-a"
    thread_id: str = ""
    queued_snapshots_at_start: list[list[dict[str, Any]]] = field(default_factory=list)
    thread_snapshot_at_start: tuple[str | None, str | None] | None = None

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        if self.db is not None and self.thread_id:
            thread = await ThreadRepository(
                self.db, workspace_id=self.workspace_id
            ).locked_update(self.thread_id, lambda model: None)
            self.thread_snapshot_at_start = (
                (thread.status, thread.active_turn_execution_id)
                if thread is not None
                else None
            )
            self.queued_snapshots_at_start.append(
                list(thread.queued_messages) if thread is not None else []
            )
        await super().start(request, on_event, execution_id)


@dataclass
class FailingSecondStartRunner(FakeRunner):
    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        if len(self.requests) >= 1:
            assert execution_id in self.reserved
            self.requests.append(request)
            self.callbacks[execution_id] = on_event
            raise RuntimeError("runner_start_failed")
        await super().start(request, on_event, execution_id)


@dataclass
class FailingStartRunner(FakeRunner):
    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        assert execution_id in self.reserved
        self.requests.append(request)
        self.callbacks[execution_id] = on_event
        raise RuntimeError("runner_start_failed")


@dataclass
class AutoCompleteFollowUpRunner(FakeRunner):
    follow_up_event_task: asyncio.Task[None] | None = None

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        await super().start(request, on_event, execution_id)
        if len(self.requests) >= 2:
            self.follow_up_event_task = asyncio.create_task(
                on_event(AgentEvent(type="complete"))
            )
            await asyncio.sleep(0)


@dataclass
class ConcurrentRunner(FakeRunner):
    event_task: asyncio.Task[None] | None = None

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        assert execution_id in self.reserved
        self.requests.append(request)
        self.callbacks[execution_id] = on_event
        self.event_task = asyncio.create_task(
            on_event(
                AgentEvent(
                    type="agent_text",
                    content={"parts": [{"type": "text", "text": "Ready"}]},
                )
            )
        )
        await asyncio.sleep(0)


class FakeSink:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
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
        message_count = int(
            await self.db.scalar(
                select(func.count())
                .select_from(ThreadMessageModel)
                .where(ThreadMessageModel.thread_id == thread_id)
            )
            or 0
        )
        thread = await self.db.get(ThreadModel, thread_id)
        self.events.append(
            {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "thread_id": thread_id,
                "type": type_,
                "status": status,
                "message_count": message_count,
                "thread_status": thread.status if thread else None,
                **event_data,
            }
        )


class NoopSink:
    async def emit(
        self,
        user_id: str | None,
        workspace_id: str,
        thread_id: str,
        type_: str,
        status: str | None = None,
        **_event_data: Any,
    ) -> None:
        return None


async def put_capabilities(
    session: AsyncSession,
    workspace_id: str = "workspace-a",
    capabilities: dict | None = None,
) -> None:
    await CapabilitiesStore().put(
        session, workspace_id, capabilities or make_capabilities()
    )
    await session.commit()


def make_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    file = SpooledTemporaryFile()
    file.write(content)
    file.seek(0)
    return UploadFile(
        filename=filename,
        file=file,
        headers=Headers({"content-type": content_type}),
    )


async def create_draft(
    session: AsyncSession,
    runner: FakeRunner,
    sink: FakeSink,
    workspace_id: str = "workspace-a",
    attachment_service: ThreadAttachmentService | None = None,
) -> tuple[ThreadService, str]:
    service = ThreadService(
        session,
        workspace_id=workspace_id,
        runner=runner,
        invalidation_sink=sink,
        attachment_service=attachment_service,
    )
    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await session.commit()
    return service, draft.id


@pytest.mark.asyncio
async def test_submit_persists_reserved_execution_id_before_runner_start(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = QueueSnapshotRunner(db=submit_session)
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    runner.thread_id = thread_id

    updated = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "run", "attachments": []},
    )

    assert runner.thread_snapshot_at_start == (
        ThreadStatus.QUEUED.value,
        updated.active_turn_execution_id,
    )


@pytest.mark.asyncio
async def test_concurrent_terminal_submissions_allow_one_owner(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    _, thread_id = await create_draft(submit_session, runner, sink)
    submit_session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def submit_with_new_session(text: str):
        async with submit_session_factory() as session:
            service = ThreadService(
                session,
                "workspace-a",
                runner=runner,
                invalidation_sink=NoopSink(),
            )
            try:
                updated = await service.submit_thread(
                    thread_id=thread_id,
                    user_id="user-a",
                    message={"text": text, "attachments": []},
                )
                await session.commit()
                return updated
            except Exception:
                await session.rollback()
                raise

    results = await asyncio.gather(
        submit_with_new_session("first"),
        submit_with_new_session("second"),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, BaseException) for result in results) == 1
    errors = [result for result in results if isinstance(result, ValueError)]
    assert [str(error) for error in errors] == ["thread_busy"]
    assert len(runner.requests) == 1
    async with submit_session_factory() as session:
        messages = await list_thread_messages(session, thread_id)
    assert [message.type for message in messages] == ["user"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "late_event",
    [
        AgentEvent(type="complete"),
        AgentEvent(type="error", error_code="agent_error"),
    ],
)
async def test_late_terminal_event_cannot_overwrite_new_execution(
    submit_session: AsyncSession,
    late_event: AgentEvent,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)

    first = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None

    thread_repo = ThreadRepository(submit_session, workspace_id="workspace-a")
    turn_repo = ThreadTurnRepository(submit_session)
    before = await thread_repo.locked_update(thread_id, lambda model: None)
    assert before is not None
    turn = await turn_repo.latest_turn(thread_id)
    assert turn is not None
    await turn_repo.create_execution(
        thread=before,
        turn=turn,
        execution_id="session-2",
        agentic_tool=before.agentic_tool,
        status="running",
    )
    before.status = ThreadStatus.QUEUED.value
    await submit_session.flush()

    await runner.dispatch(first_execution_id, late_event)

    after = await ThreadRepository(
        submit_session, workspace_id="workspace-a"
    ).locked_update(thread_id, lambda model: None)
    assert after is not None
    assert after.status == ThreadStatus.QUEUED.value
    assert after.active_turn_execution_id == "session-2"
    assert after.error_code is None


@pytest.mark.asyncio
async def test_stale_complete_with_event_session_does_not_start_follow_up(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = FakeRunner()
    service = ThreadService(
        submit_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=NoopSink(),
        event_session_factory=session_factory,
    )
    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await submit_session.commit()

    first = await service.submit_thread(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None
    await submit_session.commit()

    queued = await service.post_message(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    assert len(queued.queued_messages) == 1
    await submit_session.commit()

    async with session_factory() as session:
        repo = ThreadRepository(session, workspace_id="workspace-a")
        turn_repo = ThreadTurnRepository(session)
        current = await repo.locked_update(draft.id, lambda model: None)
        assert current is not None
        turn = await turn_repo.latest_turn(draft.id)
        assert turn is not None
        await turn_repo.create_execution(
            thread=current,
            turn=turn,
            execution_id="session-2",
            agentic_tool=current.agentic_tool,
            status="running",
        )
        current.status = ThreadStatus.QUEUED.value
        await session.commit()

    async with session_factory() as snapshot_session:
        runner.db = snapshot_session
        await runner.dispatch(first_execution_id, AgentEvent(type="complete"))

    async with session_factory() as session:
        stored = await ThreadRepository(
            session, workspace_id="workspace-a"
        ).locked_update(draft.id, lambda model: None)
    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert stored.active_turn_execution_id == "session-2"
    assert [message["text"] for message in stored.queued_messages] == ["second"]
    assert stored.error_code is None
    assert len(runner.requests) == 1


@pytest.mark.asyncio
async def test_late_system_init_cannot_overwrite_new_execution_resume_id(
    submit_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)

    first = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None

    thread_repo = ThreadRepository(submit_session, workspace_id="workspace-a")
    turn_repo = ThreadTurnRepository(submit_session)
    before = await thread_repo.locked_update(thread_id, lambda model: None)
    assert before is not None
    turn = await turn_repo.latest_turn(thread_id)
    assert turn is not None
    second_execution = await turn_repo.create_execution(
        thread=before,
        turn=turn,
        execution_id="session-2",
        agentic_tool=before.agentic_tool,
        status="running",
    )
    second_execution.agent_resume_id = "resume-session-2"
    before.status = ThreadStatus.QUEUED.value
    await submit_session.flush()

    caplog.set_level(logging.WARNING)
    await runner.dispatch(
        first_execution_id,
        AgentEvent(
            type="system_init", content={"agentResumeId": "stale-resume-session"}
        ),
    )

    after = await ThreadRepository(
        submit_session, workspace_id="workspace-a"
    ).locked_update(thread_id, lambda model: None)
    assert after is not None
    assert after.status == ThreadStatus.QUEUED.value
    assert after.active_turn_execution_id == "session-2"
    stored_second_execution = await turn_repo.get_execution("session-2")
    assert stored_second_execution is not None
    assert stored_second_execution.agent_resume_id == "resume-session-2"
    assert any(
        "Ignoring stale agent event" in record.message
        and thread_id in record.message
        and first_execution_id in record.message
        and "session-2" in record.message
        and "system_init" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_complete_with_queue_atomically_hands_off_execution(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = FakeRunner()
    service = ThreadService(
        submit_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=NoopSink(),
        event_session_factory=session_factory,
    )
    thread = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await submit_session.commit()

    first = await service.submit_thread(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None
    await submit_session.commit()
    await service.post_message(
        thread_id=thread.id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    await submit_session.commit()

    await runner.dispatch(first_execution_id, AgentEvent(type="complete"))

    stored = await ThreadRepository(
        submit_session, workspace_id="workspace-a"
    ).locked_update(thread.id, lambda model: None)
    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert stored.queued_messages == []
    assert stored.active_turn_execution_id == runner.reserved[-1]
    assert [request.prompt_text for request in runner.requests] == ["first", "second"]


@pytest.mark.asyncio
async def test_complete_without_queue_clears_execution_and_errors(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    first = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None

    def seed_error(model: ThreadModel) -> None:
        model.error_code = "stale_error"
        model.error_message = "stale message"
        model.error_info = {"stale": True}

    await ThreadRepository(submit_session, workspace_id="workspace-a").locked_update(
        thread_id, seed_error
    )

    await runner.dispatch(first_execution_id, AgentEvent(type="complete"))

    stored = await ThreadRepository(
        submit_session, workspace_id="workspace-a"
    ).locked_update(thread_id, lambda model: None)
    assert stored is not None
    assert stored.status == ThreadStatus.COMPLETE.value
    assert stored.active_turn_execution_id is None
    assert stored.error_code is None
    assert stored.error_message is None
    assert stored.error_info is None


@pytest.mark.asyncio
async def test_queued_handoff_rolls_back_when_user_message_append_fails(
    submit_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await put_capabilities(submit_session)
    session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = FakeRunner()
    service = ThreadService(
        submit_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=NoopSink(),
        event_session_factory=session_factory,
    )
    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await submit_session.commit()
    first = await service.submit_thread(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    first_execution_id = first.active_turn_execution_id
    assert first_execution_id is not None
    await submit_session.commit()
    await service.post_message(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    await submit_session.commit()

    original_append = ThreadMessageRepository.append

    async def fail_second_user_message(
        self: ThreadMessageRepository,
        thread_id: str,
        turn_id: str,
        turn_execution_id: str,
        type_: str,
        content: dict[str, Any],
        **kwargs: Any,
    ) -> ThreadMessageModel:
        if (
            type_ == "user"
            and content.get("parts")
            and content["parts"][0].get("text") == "second"
        ):
            raise RuntimeError("append_failed")
        return await original_append(
            self,
            thread_id,
            turn_id,
            turn_execution_id,
            type_,
            content,
            **kwargs,
        )

    monkeypatch.setattr(ThreadMessageRepository, "append", fail_second_user_message)

    with pytest.raises(RuntimeError, match="append_failed"):
        await runner.dispatch(first_execution_id, AgentEvent(type="complete"))

    async with session_factory() as verification_session:
        stored = await ThreadRepository(
            verification_session, workspace_id="workspace-a"
        ).locked_update(draft.id, lambda model: None)
        messages = await list_thread_messages(verification_session, draft.id)

    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert stored.active_turn_execution_id == first_execution_id
    assert [message["text"] for message in stored.queued_messages] == ["second"]
    assert [
        message.content["parts"][0]["text"]
        for message in messages
        if message.type == "user"
    ] == ["first"]
    assert runner.stopped == [runner.reserved[-1]]


@pytest.mark.asyncio
async def test_submit_thread_returns_thread_detail_with_execution_id(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(
        submit_session, capabilities=make_capabilities(context_window=123456)
    )
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)

    submitted = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={
            "text": "Inspect startup flow\nwith details",
            "attachments": [],
        },
    )

    messages = await list_thread_messages(submit_session, thread_id)
    assert submitted.status == ThreadStatus.QUEUED.value
    assert submitted.active_turn_execution_id == runner.reserved[0]
    assert submitted.title == "Inspect startup flow"
    assert submitted.context_window == 123456
    assert submitted.draft_message is None
    assert messages[0].type == "user"
    assert messages[0].content == {
        "parts": [
            {"type": "text", "text": "Inspect startup flow\nwith details"},
        ]
    }
    assert runner.requests == [
        AgentExecutionRequest(
            thread_id=thread_id,
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            prompt_text="Inspect startup flow\nwith details",
            permission_mode=None,
            git_context_id=None,
            attachments=[],
        )
    ]


@pytest.mark.asyncio
async def test_agent_execution_request_carries_thread_id(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)

    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "hello", "attachments": []},
    )

    assert runner.requests[0].thread_id == thread_id
    assert runner.requests[0].git_context_id is None


@pytest.mark.asyncio
async def test_submit_preserves_typed_attachments_in_message_and_runner_request(
    submit_session: AsyncSession,
    tmp_path,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    attachment_service = ThreadAttachmentService(storage_root=tmp_path)
    service, thread_id = await create_draft(
        submit_session,
        runner,
        sink,
        attachment_service=attachment_service,
    )
    image = await attachment_service.save_upload(
        thread_id=thread_id,
        upload=make_upload_file(b"image-bytes", "diagram.png", "image/png"),
    )
    pdf = await attachment_service.save_upload(
        thread_id=thread_id,
        upload=make_upload_file(b"%PDF-1.7", "brief.pdf", "application/pdf"),
    )

    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={
            "text": "Review attachments",
            "attachments": [
                {"attachmentId": image.attachment_id},
                {"attachmentId": pdf.attachment_id},
            ],
        },
    )

    messages = await list_thread_messages(submit_session, thread_id)
    assert messages[0].content == {
        "parts": [
            {"type": "text", "text": "Review attachments"},
            {
                "type": "image",
                "attachmentId": image.attachment_id,
                "name": "diagram.png",
                "mimeType": "image/png",
                "size": len(b"image-bytes"),
            },
            {
                "type": "pdf",
                "attachmentId": pdf.attachment_id,
                "name": "brief.pdf",
                "mimeType": "application/pdf",
                "size": len(b"%PDF-1.7"),
            },
        ]
    }
    assert runner.requests[-1].attachments == [
        {
            "type": "image",
            "attachmentId": image.attachment_id,
            "name": "diagram.png",
            "mimeType": "image/png",
            "size": len(b"image-bytes"),
            "path": str(image.path),
        },
        {
            "type": "pdf",
            "attachmentId": pdf.attachment_id,
            "name": "brief.pdf",
            "mimeType": "application/pdf",
            "size": len(b"%PDF-1.7"),
            "path": str(pdf.path),
        },
    ]


@pytest.mark.asyncio
async def test_runner_event_uses_an_independent_session(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = ConcurrentRunner()
    service = ThreadService(
        submit_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=NoopSink(),
        event_session_factory=session_factory,
    )
    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await submit_session.commit()

    await service.submit_thread(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "Inspect", "attachments": []},
    )
    await submit_session.commit()
    assert runner.event_task is not None
    await runner.event_task

    async with session_factory() as verification_session:
        thread = await verification_session.get(ThreadModel, draft.id)
        messages = await list_thread_messages(verification_session, draft.id)

    assert thread is not None
    assert thread.status == ThreadStatus.WORKING.value
    assert [message.type for message in messages] == ["user", "agent_text"]


@pytest.mark.asyncio
async def test_submit_revalidates_latest_capabilities_snapshot(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await put_capabilities(
        submit_session,
        capabilities=make_capabilities(models=["claude-sonnet-5"]),
    )

    submitted = await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "hello", "attachments": []},
    )
    persisted = await submit_session.get(ThreadModel, thread_id)

    assert submitted.model == "claude-sonnet-5"
    assert runner.requests[-1].model == "claude-sonnet-5"
    assert persisted is not None
    assert persisted.model == "claude-sonnet-5"


@pytest.mark.asyncio
async def test_submit_failure_restores_original_model_after_fallback(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FailingStartRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await put_capabilities(
        submit_session,
        capabilities=make_capabilities(models=["claude-sonnet-5"]),
    )

    with pytest.raises(RuntimeError, match="runner_start_failed"):
        await service.submit_thread(
            thread_id=thread_id,
            user_id="user-a",
            message={"text": "hello", "attachments": []},
        )

    submit_session.expire_all()
    persisted = await submit_session.get(ThreadModel, thread_id)

    assert persisted is not None
    assert persisted.model == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_runner_events_update_status_messages_parent_links_and_emit_after_db_write(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "run checks", "attachments": []},
    )

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="agent_text", content={"parts": [{"type": "text", "text": "Working"}]}
        ),
    )
    working = await service.get_thread(thread_id, user_id="user-a")
    assert working.status == ThreadStatus.WORKING.value

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="tool_call",
            content={
                "name": "bash",
                "input": {"command": "pwd"},
            },
            tool_call_key="call-1",
        ),
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="tool_result",
            content={
                "isError": False,
                "result": {"stdout": "/workspace"},
            },
            tool_call_key="call-1",
            result_kind="provider_result",
        ),
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    detail = await service.get_thread(thread_id, user_id="user-a")
    messages = await list_thread_messages(service.db, thread_id)
    tool_call = next(message for message in messages if message.type == "tool_call")
    tool_result = next(message for message in messages if message.type == "tool_result")
    assert detail.status == ThreadStatus.COMPLETE.value
    assert detail.active_turn_execution_id is None
    assert tool_call.content == {"name": "bash", "parameters": {"command": "pwd"}}
    assert tool_result.parent_tool_use_id == tool_call.id
    assert tool_result.content["isError"] is False
    assert tool_result.content["preview"] == '{"stdout":"/workspace"}'
    assert tool_result.content["truncated"] is False
    assert tool_result.result_kind == "provider_result"
    assert sink.events[-2]["type"] == "timeline_updated"
    assert sink.events[-2]["thread_status"] == ThreadStatus.COMPLETE.value
    assert sink.events[-2]["thread_version"] == detail.version
    assert sink.events[-2]["turns"][0]["id"] == tool_call.turn_id
    assert sink.events[-2]["message_count"] >= 4
    assert sink.events[-1]["type"] == "status_updated"
    assert sink.events[-1]["status"] == ThreadStatus.COMPLETE.value


@pytest.mark.asyncio
async def test_upward_pagination_projects_result_with_tool_before_older_thinking(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    service, thread_id = await create_draft(
        submit_session, runner, FakeSink(submit_session)
    )
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "inspect", "attachments": []},
    )
    execution_id = runner.reserved[-1]
    await runner.dispatch(
        execution_id,
        AgentEvent(
            type="thinking",
            content={"parts": [{"type": "text", "text": "Checking"}]},
            source_event_key="thinking-1",
        ),
    )
    await runner.dispatch(
        execution_id,
        AgentEvent(
            type="tool_call",
            content={"name": "Bash", "input": {"command": "pwd"}},
            source_event_key="call-1",
            tool_call_key="call-1",
        ),
    )
    await runner.dispatch(
        execution_id,
        AgentEvent(
            type="tool_result",
            content={"result": "/workspace", "is_error": False},
            source_event_key="result-1",
            tool_call_key="call-1",
            result_kind="provider_result",
        ),
    )

    latest = await service.list_timeline(
        thread_id=thread_id, user_id="user-a", before_sequence=None, limit=1
    )
    assert latest.items[0].type == "tool"
    assert latest.items[0].provider_result is not None
    older = await service.list_timeline(
        thread_id=thread_id,
        user_id="user-a",
        before_sequence=latest.page_info.oldest_sequence,
        limit=1,
    )
    assert older.items[0].type == "thinking"


@pytest.mark.asyncio
async def test_error_and_unknown_events_preserve_structured_fallbacks(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "run checks", "attachments": []},
    )

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="unknown_progress",
            content={"step": 1},
            raw={"type": "unknown_progress", "payload": {"step": 1}},
        ),
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="error",
            error_code="agent_error",
            error_info={"exit_code": 1},
        ),
    )

    detail = await service.get_thread(thread_id, user_id="user-a")
    messages = await list_thread_messages(service.db, thread_id)
    system = next(message for message in messages if message.type == "system")
    assert detail.status == ThreadStatus.ERROR.value
    assert detail.active_turn_execution_id is None
    assert detail.error_code == "agent_error"
    assert detail.error_info == {"exit_code": 1}
    assert system.content == {
        "text": "Unsupported agent event: unknown_progress",
        "raw": {"type": "unknown_progress", "payload": {"step": 1}},
    }


@pytest.mark.asyncio
async def test_process_failure_preserves_prior_specific_error_fields(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "run codex", "attachments": []},
    )
    message = "The selected model requires a newer version of Codex."

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="error",
            error_code="agent_error",
            error_info={"message": message, "raw_type": "error"},
            content={"message": message},
        ),
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="error",
            error_code="agent_process_failed",
            error_info={"returncode": 1},
        ),
    )

    detail = await service.get_thread(thread_id, user_id="user-a")
    assert detail.status == ThreadStatus.ERROR.value
    assert detail.error_code == "agent_error"
    assert detail.error_info == {"message": message, "raw_type": "error"}
    assert detail.error_message == message


@pytest.mark.asyncio
async def test_system_init_event_is_persisted_for_the_init_widget(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "inspect workspace", "attachments": []},
    )
    content = {
        "agentResumeId": "session-1",
        "model": "claude-opus-4-8",
        "cwd": "/workspace",
        "tools": ["Read", "Bash"],
        "mcpServers": [{"name": "workspace", "status": "connected"}],
    }

    await runner.dispatch(
        runner.reserved[-1], AgentEvent(type="system_init", content=content)
    )

    messages = await list_thread_messages(service.db, thread_id)
    init_message = next(
        message for message in messages if message.type == "system_init"
    )
    assert init_message.content == content


@pytest.mark.asyncio
async def test_system_init_captures_agent_resume_id(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "inspect workspace", "attachments": []},
    )

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="system_init",
            content={
                "agentResumeId": "sess-abc",
                "model": "claude-opus-4-8",
                "cwd": "/workspace",
                "tools": [],
                "mcpServers": [],
            },
        ),
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "next", "attachments": []},
    )

    assert runner.requests[-1].agent_resume_id == "sess-abc"


@pytest.mark.asyncio
async def test_complete_event_hands_off_next_queued_message(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )

    queued = await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )

    assert len(queued.queued_messages) == 1
    assert queued.queued_messages[0]["id"]
    assert queued.queued_messages[0]["text"] == "second"

    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    detail = await service.get_thread(thread_id, user_id="user-a")
    messages = await list_thread_messages(service.db, thread_id)
    assert detail.queued_messages == []
    assert detail.status == ThreadStatus.QUEUED.value
    assert [request.prompt_text for request in runner.requests] == ["first", "second"]
    assert [message.type for message in messages if message.type == "user"] == [
        "user",
        "user",
    ]


@pytest.mark.asyncio
async def test_cancel_thread_clears_queue_without_starting_follow_up(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "third", "attachments": []},
    )
    before_cancel = await service.get_thread(thread_id, user_id="user-a")

    assert [message["text"] for message in before_cancel.queued_messages] == [
        "second",
        "third",
    ]

    canceled = await service.cancel_thread(thread_id=thread_id, user_id="user-a")

    detail = await service.get_thread(thread_id, user_id="user-a")
    messages = await list_thread_messages(service.db, thread_id)
    assert canceled.status == ThreadStatus.CANCELED.value
    assert detail.status == ThreadStatus.CANCELED.value
    assert detail.active_turn_execution_id is None
    assert detail.queued_messages == []
    assert [request.prompt_text for request in runner.requests] == ["first"]
    assert runner.stopped == [before_cancel.active_turn_execution_id]
    assert [message.type for message in messages if message.type == "user"] == ["user"]


@pytest.mark.asyncio
async def test_complete_event_dequeues_before_starting_follow_up_runner(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = QueueSnapshotRunner(db=submit_session)
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    runner.thread_id = thread_id
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    queued = await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    queued_message_id = queued.queued_messages[0]["id"]

    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    stored = await ThreadRepository(
        submit_session, workspace_id="workspace-a"
    ).locked_update(thread_id, lambda model: None)
    messages = await list_thread_messages(service.db, thread_id)
    assert stored is not None
    assert stored.status == ThreadStatus.QUEUED.value
    assert all(
        message.get("id") != queued_message_id for message in stored.queued_messages
    )
    assert [request.prompt_text for request in runner.requests] == ["first", "second"]
    assert [message.content for message in messages if message.type == "user"][-1] == {
        "parts": [{"type": "text", "text": "second"}]
    }
    assert runner.queued_snapshots_at_start == [
        [],
        [],
    ]
    assert all(
        queued_message_id not in {message.get("id") for message in snapshot}
        for snapshot in runner.queued_snapshots_at_start[1:]
    )


@pytest.mark.asyncio
async def test_complete_event_session_commits_before_follow_up_runner_events(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    session_factory = async_sessionmaker(
        submit_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = AutoCompleteFollowUpRunner()
    service = ThreadService(
        submit_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=NoopSink(),
        event_session_factory=session_factory,
    )
    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await submit_session.commit()

    await service.submit_thread(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    await submit_session.commit()
    queued = await service.post_message(
        thread_id=draft.id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    queued_message_id = queued.queued_messages[0]["id"]
    await submit_session.commit()

    await runner.callbacks[runner.reserved[0]](AgentEvent(type="complete"))
    assert runner.follow_up_event_task is not None
    await runner.follow_up_event_task

    async with session_factory() as verification_session:
        thread = await ThreadRepository(
            verification_session, workspace_id="workspace-a"
        ).locked_update(draft.id, lambda model: None)
        messages = await list_thread_messages(verification_session, draft.id)

    assert thread is not None
    assert thread.status == ThreadStatus.COMPLETE.value
    assert thread.queued_messages == []
    assert [request.prompt_text for request in runner.requests] == ["first", "second"]
    assert all(
        message.get("id") != queued_message_id for message in thread.queued_messages
    )
    assert [
        message.content["parts"][0]["text"]
        for message in messages
        if message.type == "user"
    ] == ["first", "second"]


@pytest.mark.asyncio
async def test_handoff_start_failure_marks_process_error_without_duplicate_user_message(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FailingSecondStartRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "first", "attachments": []},
    )
    queued = await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "second", "attachments": []},
    )
    assert queued.queued_messages[0]["text"] == "second"

    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    detail = await service.get_thread(thread_id, user_id="user-a")
    messages = await list_thread_messages(service.db, thread_id)
    user_texts = [
        message.content["parts"][0]["text"]
        for message in messages
        if message.type == "user"
    ]
    assert detail.status == ThreadStatus.ERROR.value
    assert detail.error_code == "agent_process_failed"
    assert detail.error_info == {"execution_id": runner.reserved[-1]}
    assert detail.queued_messages == []
    assert user_texts == ["first", "second"]


@pytest.mark.asyncio
async def test_error_event_clears_agent_resume_id(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "inspect workspace", "attachments": []},
    )

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="system_init",
            content={
                "agentResumeId": "sess-abc",
                "model": "claude-opus-4-8",
                "cwd": "/workspace",
                "tools": [],
                "mcpServers": [],
            },
        ),
    )
    await runner.dispatch(
        runner.reserved[-1], AgentEvent(type="error", error_code="agent_process_failed")
    )

    execution = await ThreadTurnRepository(submit_session).get_execution(
        runner.reserved[-1]
    )
    assert execution is not None
    assert execution.agent_resume_id is None


async def _seed_question(
    service: ThreadService,
    runner: FakeRunner,
    thread_id: str,
) -> int:
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="tool_call",
            content={
                "name": QUESTION_TOOL_NAME,
                "input": {
                    "id": "color",
                    "title": "Pick a color",
                    "questions": [
                        {
                            "id": "favorite",
                            "label": "Favorite color",
                            "type": "radio",
                            "options": ["red", "blue"],
                        }
                    ],
                },
            },
            tool_call_key="toolu_q1",
        ),
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="tool_result",
            content={
                "result": "Question form delivered to the user.",
                "isError": False,
            },
            tool_call_key="toolu_q1",
            result_kind="provider_result",
        ),
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))
    messages = await list_thread_messages(service.db, thread_id)
    question = next(
        message
        for message in messages
        if message.type == "tool_call" and message.content["name"] == QUESTION_TOOL_NAME
    )
    return question.id


@pytest.mark.asyncio
async def test_answer_question_appends_result_and_restarts(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    question_id = await _seed_question(service, runner, thread_id)

    await service.answer_question(
        thread_id=thread_id,
        user_id="user-a",
        message_id=question_id,
        answers={"Favorite color": "red"},
        text="[form answers — color]\nFavorite color: red",
    )

    messages = await list_thread_messages(service.db, thread_id)
    results = [
        message
        for message in messages
        if message.type == "tool_result" and message.parent_tool_use_id == question_id
    ]
    assert len(results) == 2
    assert json.loads(results[-1].content["preview"]) == {
        "answers": {"Favorite color": "red"}
    }
    assert runner.requests[-1].prompt_text.startswith("[form answers — color]")


@pytest.mark.asyncio
async def test_answer_question_rejects_unknown_message(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=999999,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == "question_not_found"


@pytest.mark.asyncio
async def test_answer_question_rejects_running_thread(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    question_id = await _seed_question(service, runner, thread_id)
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "go", "attachments": []},
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="agent_text",
            content={"parts": [{"type": "text", "text": "Working"}]},
        ),
    )

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=question_id,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == "thread_busy"


@pytest.mark.asyncio
async def test_answer_question_expired_after_user_message(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    question_id = await _seed_question(service, runner, thread_id)
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "never mind", "attachments": []},
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=question_id,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == QUESTION_EXPIRED_CODE
    assert exc_info.value.error_info["reason"] == QUESTION_EXPIRED_SUPERSEDED


@pytest.mark.asyncio
async def test_answer_question_rejects_second_answer(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    question_id = await _seed_question(service, runner, thread_id)
    await service.answer_question(
        thread_id=thread_id,
        user_id="user-a",
        message_id=question_id,
        answers={"Favorite color": "red"},
        text="[form answers — color]\nFavorite color: red",
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=question_id,
            answers={"Favorite color": "blue"},
            text="[form answers — color]\nFavorite color: blue",
        )
    assert exc_info.value.error_code == QUESTION_EXPIRED_CODE
    assert exc_info.value.error_info["reason"] == QUESTION_EXPIRED_ALREADY_ANSWERED


@pytest.mark.asyncio
async def test_answer_question_rejects_when_follow_up_is_running(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    question_id = await _seed_question(service, runner, thread_id)
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "go", "attachments": []},
    )
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "queued while running", "attachments": []},
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=question_id,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == "thread_busy"


@pytest.mark.asyncio
async def test_answer_question_unknown_message_rejects_when_follow_up_is_running(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    await _seed_question(service, runner, thread_id)
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "go", "attachments": []},
    )
    await service.post_message(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "queued while running", "attachments": []},
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=999999,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == "thread_busy"


@pytest.mark.asyncio
async def test_answer_question_expired_when_tool_result_missing(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "ask me", "attachments": []},
    )
    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="tool_call",
            content={
                "name": QUESTION_TOOL_NAME,
                "input": {"id": "f", "title": "T", "questions": []},
            },
            tool_call_key="toolu_q1",
        ),
    )
    await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))
    messages = await list_thread_messages(service.db, thread_id)
    question = next(message for message in messages if message.type == "tool_call")

    with pytest.raises(ThreadApiError) as exc_info:
        await service.answer_question(
            thread_id=thread_id,
            user_id="user-a",
            message_id=question.id,
            answers={},
            text="x",
        )
    assert exc_info.value.error_code == QUESTION_EXPIRED_CODE
    assert exc_info.value.error_info["reason"] == QUESTION_EXPIRED_NOT_DELIVERED


def test_context_tokens_from_usage() -> None:
    assert (
        context_tokens_from_usage(
            AgenticTool.CLAUDE,
            {
                "input_tokens": 10,
                "output_tokens": 999,
                "cache_creation_input_tokens": 20,
                "cache_read_input_tokens": 30,
            },
        )
        == 60
    )
    assert (
        context_tokens_from_usage(
            AgenticTool.CODEX,
            {
                "token_usage": {
                    "last": {"total_tokens": 321},
                    "total": {"total_tokens": 999},
                }
            },
        )
        == 321
    )
    assert (
        context_tokens_from_usage(
            AgenticTool.OPENCODE, {"prompt_tokens": 5, "completion_tokens": 7}
        )
        == 12
    )
    assert context_tokens_from_usage(AgenticTool.CLAUDE, {}) is None


@pytest.mark.asyncio
async def test_event_usage_updates_context_tokens_without_clearing_existing_value(
    submit_session: AsyncSession,
) -> None:
    await put_capabilities(submit_session)
    runner = FakeRunner()
    sink = FakeSink(submit_session)
    service, thread_id = await create_draft(submit_session, runner, sink)
    await service.submit_thread(
        thread_id=thread_id,
        user_id="user-a",
        message={"text": "run checks", "attachments": []},
    )

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="agent_text",
            content={"parts": [{"type": "text", "text": "Working"}]},
            usage={
                "input_tokens": 10,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 3,
            },
        ),
    )
    with_usage = await service.get_thread(thread_id, user_id="user-a")
    assert with_usage.context_tokens == 15

    await runner.dispatch(
        runner.reserved[-1],
        AgentEvent(
            type="agent_text",
            content={"parts": [{"type": "text", "text": "Still working"}]},
        ),
    )
    without_usage = await service.get_thread(thread_id, user_id="user-a")
    assert without_usage.context_tokens == 15
