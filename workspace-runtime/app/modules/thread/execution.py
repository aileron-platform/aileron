from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.domain.context_usage import context_tokens_from_usage
from app.modules.resource_telemetry.triggers import notify_agent_execution_started
from app.modules.thread.domain.enums import RUNNING_STATUSES, ThreadStatus
from app.modules.thread.persistence_models import (
    ThreadModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)
from app.modules.thread.message_repository import (
    ThreadMessageRepository,
)
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.thread.attachments import (
    ThreadAttachmentError,
    ThreadAttachmentService,
    ThreadStoredAttachment,
)
from app.modules.thread.state_changes import apply_thread_error

logger = logging.getLogger(__name__)
TOOL_RESULT_PREVIEW_MAX_BYTES = 4 * 1024
TOOL_RESULT_PREVIEW_MAX_LINES = 3
AsyncSessionFactory = Callable[[], AsyncSession]


@dataclass(frozen=True)
class AgentExecutionRequest:
    thread_id: str
    agentic_tool: str
    model: str
    claude_mode: str | None
    prompt_text: str
    permission_mode: str | None
    git_context_id: str | None
    agent_resume_id: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentEvent:
    type: str
    content: dict[str, Any] = field(default_factory=dict)
    source_event_key: str | None = None
    tool_call_key: str | None = None
    parent_tool_call_key: str | None = None
    result_kind: str | None = None
    usage: dict[str, Any] | None = None
    error_code: str | None = None
    error_info: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class RunnerStopTimeoutError(RuntimeError):
    """Raised when a stop-current-turn request cannot confirm the runner exited."""

    def __init__(self, execution_id: str) -> None:
        super().__init__(f"runner_stop_timeout:{execution_id}")
        self.execution_id = execution_id


@dataclass(frozen=True)
class TimelineInvalidation:
    thread: ThreadModel
    previous_status: str
    created_item_ids: tuple[str, ...] = ()
    changed_item_ids: tuple[str, ...] = ()
    turns: tuple[dict[str, Any], ...] = ()
    executions: tuple[dict[str, Any], ...] = ()


class AgentRunner(Protocol):
    def reserve(self) -> str: ...

    def adopt_reservation(self, execution_id: str) -> None: ...

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None: ...

    async def wait(self, execution_id: str) -> None: ...

    async def stop(self, execution_id: str) -> None: ...

    def is_alive(self, execution_id: str) -> bool: ...

    async def destroy_thread(self, thread_id: str) -> None: ...

    async def evict_idle(self) -> int: ...


class InvalidationSink(Protocol):
    async def emit(
        self,
        user_id: str | None,
        workspace_id: str,
        thread_id: str,
        type_: str,
        status: str | None = None,
        *,
        thread_version: int | None = None,
        created_item_ids: list[str] | None = None,
        changed_item_ids: list[str] | None = None,
        turns: list[dict[str, Any]] | None = None,
        executions: list[dict[str, Any]] | None = None,
        refresh_latest: bool = False,
    ) -> None: ...


class _ThreadExecution:
    """Own thread execution persistence and the provider runner seam."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        workspace_id: str,
        thread_repo: ThreadRepository,
        message_repo: ThreadMessageRepository,
        capabilities_store: CapabilitiesStore,
        runner: AgentRunner,
        invalidation_sink: InvalidationSink,
        event_session_factory: AsyncSessionFactory | None = None,
        attachment_service: ThreadAttachmentService | None = None,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.thread_repo = thread_repo
        self.message_repo = message_repo
        self.turn_repo = ThreadTurnRepository(db)
        self.capabilities_store = capabilities_store
        self._runner = runner
        self.invalidation_sink = invalidation_sink
        self.event_session_factory = event_session_factory
        self.attachment_service = attachment_service

    async def submit(
        self,
        thread_id: str,
        message: dict[str, Any],
        *,
        permission_mode: str | None = None,
    ) -> ThreadModel:
        execution_id = self._runner.reserve()
        ownership_acquired = False
        submission_committed = False
        try:
            updated, request, previous_status = await self._write_submission(
                thread_id,
                message,
                execution_id,
                permission_mode=permission_mode,
            )
            invalidation = await self._submission_invalidation(updated, previous_status)
            ownership_acquired = True
            await self.db.commit()
            submission_committed = True
            await self._emit_timeline(invalidation)
            await self._runner.start(
                request,
                lambda event: self._handle_runner_event(thread_id, execution_id, event),
                execution_id,
            )
            notify_agent_execution_started()
        except Exception:
            await self.db.rollback()
            if self._runner.is_alive(execution_id):
                await self._runner.stop(execution_id)
            if ownership_acquired and submission_committed:
                await self._handle_spawn_failure(thread_id, execution_id)
            raise

        return updated

    async def prepare_submission(
        self,
        thread_id: str,
        message: dict[str, Any],
        *,
        execution_id: str,
        permission_mode: str | None = None,
    ) -> ThreadModel:
        """Persist a reserved execution identity without spawning its process."""
        try:
            updated, _, previous_status = await self._write_submission(
                thread_id,
                message,
                execution_id,
                permission_mode=permission_mode,
            )
            invalidation = await self._submission_invalidation(updated, previous_status)
            await self.db.commit()
            await self._emit_timeline(invalidation)
            return updated
        except Exception:
            await self.db.rollback()
            raise

    async def start_prepared_submission(
        self,
        *,
        thread_id: str,
        execution_id: str,
        permission_mode: str | None = None,
    ) -> None:
        """Adopt and spawn an already-persisted execution identity."""
        try:
            _, request, _ = await self._write_submission(
                thread_id,
                {},
                execution_id,
                permission_mode=permission_mode,
            )
            self._runner.adopt_reservation(execution_id)
            await self._runner.start(
                request,
                lambda event: self._handle_runner_event(thread_id, execution_id, event),
                execution_id,
            )
            notify_agent_execution_started()
        except Exception:
            if self._runner.is_alive(execution_id):
                await self._runner.stop(execution_id)
            await self._handle_spawn_failure(thread_id, execution_id)
            raise

    def is_alive(self, execution_id: str) -> bool:
        return self._runner.is_alive(execution_id)

    async def wait(self, execution_id: str) -> None:
        await self._runner.wait(execution_id)

    async def stop(self, execution_id: str) -> None:
        await self._runner.stop(execution_id)

    async def stop_and_confirm(self, execution_id: str) -> None:
        if not self._runner.is_alive(execution_id):
            return
        await self._runner.stop(execution_id)
        await self._runner.wait(execution_id)
        if self._runner.is_alive(execution_id):
            raise RuntimeError("agent_process_still_alive")

    async def stop_and_confirm_for_turn_stop(self, execution_id: str) -> None:
        """Stop the runner for a user-initiated turn stop and confirm it exited.

        Any exception raised while signaling or waiting on the runner is
        swallowed and logged: the final `is_alive` check alone decides whether
        the stop is confirmed, so a runner that reports itself dead after a
        failed `stop()` call can still safely proceed to finalize the turn.
        """
        if not self._runner.is_alive(execution_id):
            return
        try:
            await self._runner.stop(execution_id)
            await self._runner.wait(execution_id)
        except Exception:
            logger.warning(
                "Runner stop/wait raised while stopping the current turn: "
                "execution_id=%s",
                execution_id,
                exc_info=True,
            )
        if self._runner.is_alive(execution_id):
            raise RunnerStopTimeoutError(execution_id)

    async def destroy_thread(self, thread_id: str) -> None:
        await self._runner.destroy_thread(thread_id)

    async def _write_submission(
        self,
        thread_id: str,
        message: dict[str, Any],
        execution_id: str,
        *,
        permission_mode: str | None = None,
    ) -> tuple[ThreadModel, AgentExecutionRequest, str]:
        thread = await self._get_thread_for_submission(thread_id)
        if thread is None:
            raise ValueError("thread_not_found")
        previous_status = thread.status

        existing_execution = await self.turn_repo.get_execution(execution_id)
        if existing_execution is not None:
            existing_turn = await self.turn_repo.get_turn(
                thread_id, existing_execution.turn_id
            )
            latest_user = await self.message_repo.latest_user_message(thread_id)
            if existing_turn is None or latest_user is None:
                raise ValueError("invalid_prepared_submission")
            return (
                thread,
                AgentExecutionRequest(
                    thread_id=thread.id,
                    agentic_tool=thread.agentic_tool,
                    model=thread.model,
                    claude_mode=thread.claude_mode,
                    prompt_text=self._text_from_user_content(latest_user.content),
                    attachments=[],
                    permission_mode=permission_mode,
                    git_context_id=thread.git_context_id,
                    agent_resume_id=existing_execution.agent_resume_id,
                ),
                previous_status,
            )

        capabilities = await self.capabilities_store.get(self.db, self.workspace_id)
        if capabilities is None:
            raise ValueError("capabilities_unavailable")
        if not capabilities.validate_selection(
            thread.agentic_tool, thread.model, thread.claude_mode
        ):
            raise ValueError("invalid_tool_selection")
        tool_capability = next(
            tool for tool in capabilities.tools if tool.id == thread.agentic_tool
        )

        text = str(message.get("text") or "")
        message_attachments, runner_attachments = self._message_attachments(
            thread_id, message
        )
        previous_turn = await self.turn_repo.latest_turn(thread_id)
        previous_executions = (
            await self.turn_repo.list_executions(previous_turn.id)
            if previous_turn is not None
            else []
        )
        previous_resume_id = (
            previous_executions[-1].agent_resume_id if previous_executions else None
        )
        self.db.expunge(thread)

        def mutate(model: ThreadModel) -> None:
            if (
                ThreadStatus(model.status) in RUNNING_STATUSES
                and model.active_turn_execution_id
            ):
                raise ValueError("thread_busy")
            if not model.title:
                model.title = self._title_from_text(text)
            model.context_window = tool_capability.context_window
            model.draft_message = None
            model.status = ThreadStatus.QUEUED.value
            model.error_code = None
            model.error_info = None
            model.error_message = None

        updated = await self.thread_repo.locked_update(thread_id, mutate)
        if updated is None:
            raise ValueError("thread_not_found")
        turn = await self.turn_repo.create_turn(
            thread=updated,
            turn_id=str(uuid4()),
            status="running",
        )
        execution = await self.turn_repo.create_execution(
            thread=updated,
            turn=turn,
            execution_id=execution_id,
            agentic_tool=updated.agentic_tool,
            status="running",
        )
        await self.message_repo.append(
            thread_id,
            turn.id,
            execution.id,
            "user",
            self._user_message_content(text, message_attachments),
            source_event_key=f"submission:{execution.id}",
        )

        request = AgentExecutionRequest(
            thread_id=updated.id,
            agentic_tool=updated.agentic_tool,
            model=updated.model,
            claude_mode=updated.claude_mode,
            prompt_text=text,
            attachments=runner_attachments,
            permission_mode=permission_mode,
            git_context_id=updated.git_context_id,
            agent_resume_id=previous_resume_id,
        )
        return updated, request, previous_status

    async def _submission_invalidation(
        self, thread: ThreadModel, previous_status: str
    ) -> TimelineInvalidation:
        latest_user = await self.message_repo.latest_user_message(thread.id)
        turn = (
            await self.turn_repo.get_turn(thread.id, thread.active_turn_id)
            if thread.active_turn_id
            else None
        )
        execution = (
            await self.turn_repo.get_execution(thread.active_turn_execution_id)
            if thread.active_turn_execution_id
            else None
        )
        return TimelineInvalidation(
            thread=thread,
            previous_status=previous_status,
            created_item_ids=(str(latest_user.id),) if latest_user else (),
            turns=(self._turn_metadata(turn),) if turn else (),
            executions=(self._execution_metadata(execution),) if execution else (),
        )

    async def restart(
        self,
        thread_id: str,
        *,
        prompt_text: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> ThreadModel:
        thread = await self._get_thread_for_submission(thread_id)
        if thread is None:
            raise ValueError("thread_not_found")
        previous_status = thread.status

        capabilities = await self.capabilities_store.get(self.db, self.workspace_id)
        if capabilities is None:
            raise ValueError("capabilities_unavailable")
        if not capabilities.validate_selection(
            thread.agentic_tool, thread.model, thread.claude_mode
        ):
            raise ValueError("invalid_tool_selection")
        tool_capability = next(
            tool for tool in capabilities.tools if tool.id == thread.agentic_tool
        )
        execution_id = self._runner.reserve()
        ownership_acquired = False
        turn = await self.turn_repo.latest_turn(thread_id)
        if turn is None:
            raise ValueError("turn_not_found")
        previous_execution = (
            await self.turn_repo.get_execution(thread.active_turn_execution_id)
            if thread.active_turn_execution_id
            else None
        )
        if previous_execution is None:
            executions = await self.turn_repo.list_executions(turn.id)
            previous_execution = executions[-1] if executions else None
        self.db.expunge(thread)

        def mutate(model: ThreadModel) -> None:
            if (
                ThreadStatus(model.status) in RUNNING_STATUSES
                and model.active_turn_execution_id
            ):
                raise ValueError("thread_busy")
            model.context_window = tool_capability.context_window
            model.status = ThreadStatus.QUEUED.value
            model.error_code = None
            model.error_info = None
            model.error_message = None

        try:
            updated = await self.thread_repo.locked_update(thread_id, mutate)
            if updated is None:
                raise ValueError("thread_not_found")
            restarted_execution = await self.turn_repo.create_execution(
                thread=updated,
                turn=turn,
                execution_id=execution_id,
                agentic_tool=updated.agentic_tool,
                status="running",
            )
            ownership_acquired = True
            _, runner_attachments = self._message_attachments(
                thread_id,
                {"attachments": attachments or []},
            )

            request = AgentExecutionRequest(
                thread_id=updated.id,
                agentic_tool=updated.agentic_tool,
                model=updated.model,
                claude_mode=updated.claude_mode,
                prompt_text=prompt_text,
                attachments=runner_attachments,
                permission_mode=None,
                git_context_id=updated.git_context_id,
                agent_resume_id=(
                    previous_execution.agent_resume_id
                    if previous_execution is not None
                    else None
                ),
            )
            await self.db.commit()
            await self._runner.start(
                request,
                lambda event: self._handle_runner_event(thread_id, execution_id, event),
                execution_id,
            )
        except Exception:
            await self.db.rollback()
            if self._runner.is_alive(execution_id):
                await self._runner.stop(execution_id)
            if ownership_acquired:
                await self._handle_spawn_failure(thread_id, execution_id)
            raise

        await self._emit_timeline(
            TimelineInvalidation(
                thread=updated,
                previous_status=previous_status,
                turns=(self._turn_metadata(turn),),
                executions=(self._execution_metadata(restarted_execution),),
            )
        )
        return updated

    async def _get_thread_for_submission(self, thread_id: str) -> ThreadModel | None:
        stmt = select(ThreadModel).where(
            and_(
                ThreadModel.id == thread_id,
                ThreadModel.workspace_id == self.workspace_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _handle_spawn_failure(self, thread_id: str, execution_id: str) -> None:
        await self._handle_runner_event(
            thread_id,
            execution_id,
            AgentEvent(
                type="error",
                error_code="agent_process_failed",
                error_info={"execution_id": execution_id},
            ),
        )

    async def _handle_runner_event(
        self, thread_id: str, execution_id: str, event: AgentEvent
    ) -> None:
        if self.event_session_factory is None:
            _, next_execution, invalidation = await self.handle_event(
                thread_id, execution_id, event
            )
            await self.db.commit()
            if invalidation is not None:
                await self._emit_timeline(invalidation)
            if next_execution is not None:
                await self._start_reserved_execution(thread_id, next_execution)
            return

        async with self.event_session_factory() as db:
            try:
                async with db.begin():
                    adapter = self._event_adapter(db)
                    _, next_execution, invalidation = await adapter.handle_event(
                        thread_id, execution_id, event
                    )
            finally:
                if db.in_transaction():
                    await db.rollback()
        if invalidation is not None:
            await self._emit_timeline(invalidation)
        if next_execution is not None:
            await self._start_reserved_execution(thread_id, next_execution)

    async def _finish_and_handoff(
        self,
        *,
        thread_id: str,
        updated: ThreadModel,
        execution: ThreadTurnExecutionModel,
        turn: ThreadTurnModel,
        finished_status: str,
        next_execution_id: str | None,
        queued_message: dict[str, Any] | None,
        timeline_turn_ids: list[str],
        affected_execution_ids: list[str],
        created_item_ids: list[str],
    ) -> tuple[str, AgentExecutionRequest] | None:
        """Finish the current turn/execution and, when a queued message was
        reserved, atomically build the handoff request for the next turn.

        Shared by the complete-event dequeue path and the stop-current-turn
        dequeue path so both advance the FIFO queue identically.
        """
        if queued_message is None or next_execution_id is None:
            await self.turn_repo.finish(
                thread=updated,
                execution=execution,
                turn=turn,
                status=finished_status,
            )
            return None

        await self.turn_repo.finish(
            thread=updated,
            execution=execution,
            turn=turn,
            status=finished_status,
        )
        message = {
            key: value for key, value in queued_message.items() if key != "id"
        }
        text = str(message.get("text") or "")
        message_attachments, runner_attachments = self._message_attachments(
            thread_id, message
        )
        next_turn = await self.turn_repo.create_turn(
            thread=updated,
            turn_id=str(uuid4()),
            status="running",
        )
        timeline_turn_ids.append(next_turn.id)
        next_turn_execution = await self.turn_repo.create_execution(
            thread=updated,
            turn=next_turn,
            execution_id=next_execution_id,
            agentic_tool=updated.agentic_tool,
            status="running",
        )
        affected_execution_ids.append(next_turn_execution.id)
        next_user = await self.message_repo.append(
            thread_id,
            next_turn.id,
            next_turn_execution.id,
            "user",
            self._user_message_content(text, message_attachments),
            source_event_key=f"submission:{next_execution_id}",
        )
        created_item_ids.append(str(next_user.id))
        return (
            next_execution_id,
            AgentExecutionRequest(
                thread_id=updated.id,
                agentic_tool=updated.agentic_tool,
                model=updated.model,
                claude_mode=updated.claude_mode,
                prompt_text=text,
                attachments=runner_attachments,
                permission_mode=None,
                git_context_id=updated.git_context_id,
                agent_resume_id=execution.agent_resume_id,
            ),
        )

    async def handle_event(
        self, thread_id: str, execution_id: str, event: AgentEvent
    ) -> tuple[
        bool,
        tuple[str, AgentExecutionRequest] | None,
        TimelineInvalidation | None,
    ]:
        execution = await self.turn_repo.get_execution(execution_id)
        if execution is None:
            logger.warning(
                "Ignoring event for unknown turn execution",
                extra={"thread_id": thread_id, "turn_execution_id": execution_id},
            )
            return False, None, None
        turn = await self.turn_repo.get_turn(thread_id, execution.turn_id)
        if turn is None:
            logger.error(
                "Turn execution references a missing turn",
                extra={"thread_id": thread_id, "turn_execution_id": execution_id},
            )
            return False, None, None

        stale_event = False
        next_execution_id: str | None = None
        queued_message: dict[str, Any] | None = None
        previous_status = ""
        timeline_turn_ids = [turn.id]
        affected_execution_ids = [execution.id]

        def mutate(model: ThreadModel) -> None:
            nonlocal next_execution_id, queued_message, stale_event, previous_status
            if model.active_turn_execution_id != execution_id:
                logger.warning(
                    "Ignoring stale agent event: thread_id=%s execution_id=%s current_execution_id=%s event_type=%s",
                    thread_id,
                    execution_id,
                    model.active_turn_execution_id,
                    event.type,
                )
                stale_event = True
                return
            previous_status = model.status
            if model.status in {ThreadStatus.QUEUED.value, ThreadStatus.BOOTING.value}:
                model.status = ThreadStatus.WORKING.value
            usage_tokens = context_tokens_from_usage(model.agentic_tool, event.usage)
            if usage_tokens is not None:
                model.context_tokens = usage_tokens
            if event.type == "complete":
                if model.queued_messages:
                    queued_message = model.queued_messages[0]
                    model.queued_messages = model.queued_messages[1:]
                    next_execution_id = self._runner.reserve()
                    model.status = ThreadStatus.QUEUED.value
                else:
                    model.status = ThreadStatus.COMPLETE.value
                model.error_code = None
                model.error_message = None
                model.error_info = None
            if event.type == "error":
                event_message = self._event_error_message(event)
                apply_thread_error(
                    model,
                    error_code=event.error_code or "agent_error",
                    error_message=event_message,
                    error_info=dict(event.error_info or {}),
                )

        try:
            updated = await self.thread_repo.locked_update(thread_id, mutate)
            if updated is None or stale_event:
                return False, None, None

            if event.type == "system_init":
                agent_resume_id = event.content.get("agentResumeId")
                if agent_resume_id:
                    execution.agent_resume_id = str(agent_resume_id)
                    execution.status = "running"
                    execution.version += 1
                    turn.version += 1
                    updated.version += 1

            next_execution: tuple[str, AgentExecutionRequest] | None = None
            created_item_ids, changed_item_ids = await self._append_event_message(
                thread_id,
                turn,
                execution,
                event,
            )
            if event.type == "complete":
                next_execution = await self._finish_and_handoff(
                    thread_id=thread_id,
                    updated=updated,
                    execution=execution,
                    turn=turn,
                    finished_status="complete",
                    next_execution_id=next_execution_id,
                    queued_message=queued_message,
                    timeline_turn_ids=timeline_turn_ids,
                    affected_execution_ids=affected_execution_ids,
                    created_item_ids=created_item_ids,
                )
            elif event.type == "error":
                execution.agent_resume_id = None
                await self.turn_repo.finish(
                    thread=updated,
                    execution=execution,
                    turn=turn,
                    status="error",
                    error_code=event.error_code or "agent_error",
                    error_info=dict(event.error_info or {}),
                )
        except Exception:
            if next_execution_id is not None and self._runner.is_alive(
                next_execution_id
            ):
                await self._runner.stop(next_execution_id)
            raise

        turns = await self.turn_repo.list_turns_by_ids(
            thread_id, set(timeline_turn_ids)
        )
        executions = await self.turn_repo.list_executions_by_ids(
            set(affected_execution_ids)
        )
        invalidation = TimelineInvalidation(
            thread=updated,
            previous_status=previous_status,
            created_item_ids=tuple(created_item_ids),
            changed_item_ids=tuple(changed_item_ids),
            turns=tuple(self._turn_metadata(item) for item in turns),
            executions=tuple(self._execution_metadata(item) for item in executions),
        )
        return True, next_execution, invalidation

    async def finalize_turn_stop(
        self, thread_id: str, execution_id: str
    ) -> tuple[
        bool,
        tuple[str, AgentExecutionRequest] | None,
        TimelineInvalidation | None,
    ]:
        """Atomically finish the current turn as canceled and, if a message
        is queued, hand off to the next turn.

        This is the stop-current-turn counterpart to the complete-event
        dequeue branch of `handle_event`, sharing `_finish_and_handoff` so
        both advance the FIFO queue identically. Returns `(False, None,
        None)` without mutating anything when `execution_id` is no longer
        the thread's active turn (already finalized by a concurrent stop, or
        superseded by a runner event) so repeated stop calls for the same
        execution are idempotent and never double-dequeue or start a
        duplicate turn.
        """
        execution = await self.turn_repo.get_execution(execution_id)
        if execution is None:
            return False, None, None
        turn = await self.turn_repo.get_turn(thread_id, execution.turn_id)
        if turn is None:
            return False, None, None

        stale = False
        next_execution_id: str | None = None
        queued_message: dict[str, Any] | None = None
        previous_status = ""
        timeline_turn_ids = [turn.id]
        affected_execution_ids = [execution.id]

        def mutate(model: ThreadModel) -> None:
            nonlocal next_execution_id, queued_message, stale, previous_status
            if (
                model.active_turn_execution_id != execution_id
                or ThreadStatus(model.status) not in RUNNING_STATUSES
            ):
                stale = True
                return
            previous_status = model.status
            if model.queued_messages:
                queued_message = model.queued_messages[0]
                model.queued_messages = model.queued_messages[1:]
                next_execution_id = self._runner.reserve()
                model.status = ThreadStatus.QUEUED.value
            else:
                model.status = ThreadStatus.CANCELED.value

        created_item_ids: list[str] = []
        try:
            updated = await self.thread_repo.locked_update(thread_id, mutate)
            if updated is None or stale:
                return False, None, None

            next_execution = await self._finish_and_handoff(
                thread_id=thread_id,
                updated=updated,
                execution=execution,
                turn=turn,
                finished_status="canceled",
                next_execution_id=next_execution_id,
                queued_message=queued_message,
                timeline_turn_ids=timeline_turn_ids,
                affected_execution_ids=affected_execution_ids,
                created_item_ids=created_item_ids,
            )
        except Exception:
            if next_execution_id is not None and self._runner.is_alive(
                next_execution_id
            ):
                await self._runner.stop(next_execution_id)
            raise

        turns = await self.turn_repo.list_turns_by_ids(
            thread_id, set(timeline_turn_ids)
        )
        executions = await self.turn_repo.list_executions_by_ids(
            set(affected_execution_ids)
        )
        invalidation = TimelineInvalidation(
            thread=updated,
            previous_status=previous_status,
            created_item_ids=tuple(created_item_ids),
            changed_item_ids=(),
            turns=tuple(self._turn_metadata(item) for item in turns),
            executions=tuple(self._execution_metadata(item) for item in executions),
        )
        return True, next_execution, invalidation

    async def stop_current_turn(self, thread_id: str, execution_id: str) -> bool:
        """Confirm the runner for `execution_id` stopped, then atomically
        finish the current turn as canceled and hand off to the next queued
        message if one is waiting.

        Mirrors `_handle_runner_event`'s session handling so the finalize
        step composes correctly whether or not a dedicated event session
        factory is configured. Returns False if this execution was already
        finalized by a concurrent stop or superseded runner event.
        """
        if self.event_session_factory is None:
            handled, next_execution, invalidation = await self.finalize_turn_stop(
                thread_id, execution_id
            )
            await self.db.commit()
            if invalidation is not None:
                await self._emit_timeline(invalidation)
            if next_execution is not None:
                await self._start_reserved_execution(thread_id, next_execution)
            return handled

        async with self.event_session_factory() as db:
            try:
                async with db.begin():
                    adapter = self._event_adapter(db)
                    handled, next_execution, invalidation = (
                        await adapter.finalize_turn_stop(thread_id, execution_id)
                    )
            finally:
                if db.in_transaction():
                    await db.rollback()
        if invalidation is not None:
            await self._emit_timeline(invalidation)
        if next_execution is not None:
            await self._start_reserved_execution(thread_id, next_execution)
        return handled

    async def _start_reserved_execution(
        self, thread_id: str, execution: tuple[str, AgentExecutionRequest]
    ) -> None:
        execution_id, request = execution
        try:
            await self._runner.start(
                request,
                lambda event: self._handle_runner_event(thread_id, execution_id, event),
                execution_id,
            )
            notify_agent_execution_started()
        except Exception:
            if self._runner.is_alive(execution_id):
                await self._runner.stop(execution_id)
            await self._handle_spawn_failure(thread_id, execution_id)

    def _event_adapter(self, db: AsyncSession) -> _ThreadExecution:
        return _ThreadExecution(
            db=db,
            workspace_id=self.workspace_id,
            thread_repo=ThreadRepository(db, workspace_id=self.workspace_id),
            message_repo=ThreadMessageRepository(db),
            capabilities_store=self.capabilities_store,
            runner=self._runner,
            invalidation_sink=self.invalidation_sink,
            attachment_service=self.attachment_service,
        )

    @staticmethod
    def _event_error_message(event: AgentEvent) -> str | None:
        for key in ("message", "text"):
            value = event.content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(event.error_info, dict):
            value = event.error_info.get("message")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    async def _append_event_message(
        self,
        thread_id: str,
        turn: ThreadTurnModel,
        execution: ThreadTurnExecutionModel,
        event: AgentEvent,
    ) -> tuple[list[str], list[str]]:
        source_event_key = self._source_event_key(event)
        if event.type in {"agent_text", "thinking", "system", "system_init"}:
            message = await self.message_repo.append(
                thread_id,
                turn.id,
                execution.id,
                event.type,
                event.content,
                source_event_key=source_event_key,
            )
            return [str(message.id)], []

        if event.type == "tool_call":
            call_id = event.tool_call_key
            if call_id is None:
                raise ValueError("tool_call_key_required")
            content = {
                "name": event.content.get("name", "unknown"),
                "parameters": event.content.get(
                    "parameters", event.content.get("input", {})
                ),
            }
            parent_key = event.parent_tool_call_key
            parent = (
                await self.message_repo.find_tool_call(execution.id, str(parent_key))
                if parent_key is not None
                else None
            )
            message = await self.message_repo.append(
                thread_id,
                turn.id,
                execution.id,
                "tool_call",
                content,
                source_event_key=source_event_key,
                parent_tool_use_id=parent.id if parent is not None else None,
                tool_call_key=call_id,
            )
            return [str(message.id)], []

        if event.type == "tool_result":
            call_id = event.tool_call_key
            if call_id is None:
                raise ValueError("tool_call_key_required")
            parent = await self.message_repo.find_tool_call(execution.id, call_id)
            if parent is None:
                logger.error(
                    "Tool result parent call was not found",
                    extra={
                        "error_code": "tool_call_parent_not_found",
                        "thread_id": thread_id,
                        "turn_execution_id": execution.id,
                        "tool_call_key": call_id,
                    },
                )
                raise ValueError("tool_call_parent_not_found")
            is_error = bool(
                event.content.get("isError", event.content.get("is_error", False))
            )
            result = event.content.get(
                "result", event.content.get("raw", event.content)
            )
            envelope, full_payload = self._tool_result_envelope(result, is_error)
            result_message = await self.message_repo.append(
                thread_id,
                turn.id,
                execution.id,
                "tool_result",
                envelope,
                source_event_key=source_event_key,
                parent_tool_use_id=parent.id,
                result_kind=event.result_kind or "provider_result",
            )
            if full_payload is not None:
                await self.message_repo.save_tool_result_content(
                    message_id=result_message.id,
                    media_type=envelope["mediaType"],
                    payload=full_payload,
                    line_count=envelope["lineCount"],
                )
            return [], [str(parent.id)]

        if event.type in {"complete", "error", "metadata"}:
            return [], []

        message = await self.message_repo.append(
            thread_id,
            turn.id,
            execution.id,
            "system",
            {
                "text": f"Unsupported agent event: {event.type}",
                "raw": event.raw or {"type": event.type, "content": event.content},
            },
            source_event_key=source_event_key,
        )
        return [str(message.id)], []

    async def _emit_timeline(self, event: TimelineInvalidation) -> None:
        thread = event.thread
        user_id = None if thread.origin == "automation" else thread.user_id
        await self.invalidation_sink.emit(
            user_id,
            thread.workspace_id,
            thread.id,
            "timeline_updated",
            thread_version=thread.version,
            created_item_ids=list(event.created_item_ids),
            changed_item_ids=list(event.changed_item_ids),
            turns=list(event.turns),
            executions=list(event.executions),
        )
        if thread.status != event.previous_status:
            await self.invalidation_sink.emit(
                user_id,
                thread.workspace_id,
                thread.id,
                "status_updated",
                thread.status,
                thread_version=thread.version,
            )

    @staticmethod
    def _turn_metadata(turn: ThreadTurnModel) -> dict[str, Any]:
        return {"id": turn.id, "version": turn.version, "status": turn.status}

    @staticmethod
    def _execution_metadata(execution: ThreadTurnExecutionModel) -> dict[str, Any]:
        return {
            "id": execution.id,
            "version": execution.version,
            "turnId": execution.turn_id,
            "status": execution.status,
        }

    def prepare_message(
        self, thread_id: str, message: dict[str, Any]
    ) -> dict[str, Any]:
        text = str(message.get("text") or "")
        message_attachments, _ = self._message_attachments(thread_id, message)
        return {"text": text, "attachments": message_attachments}

    def _message_attachments(
        self,
        thread_id: str,
        message: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        attachments = message.get("attachments", [])
        if not isinstance(attachments, list):
            return [], []
        message_parts: list[dict[str, Any]] = []
        runner_attachments: list[dict[str, Any]] = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            attachment_id = attachment.get("attachmentId")
            if not attachment_id:
                inline_path = attachment.get("path")
                if not inline_path:
                    continue
                message_part = {
                    "type": str(attachment.get("type") or "file"),
                    "name": str(attachment.get("name") or "attachment"),
                    "mimeType": str(
                        attachment.get("mimeType") or "application/octet-stream"
                    ),
                    "size": int(attachment.get("size") or 0),
                }
                message_parts.append(message_part)
                runner_attachments.append({**message_part, "path": str(inline_path)})
                continue
            stored = self._stored_attachment(thread_id, str(attachment_id))
            message_part = self._attachment_message_part(stored)
            message_parts.append(message_part)
            runner_attachments.append({**message_part, "path": str(stored.path)})
        return message_parts, runner_attachments

    def _stored_attachment(
        self,
        thread_id: str,
        attachment_id: str,
    ) -> ThreadStoredAttachment:
        if self.attachment_service is None:
            raise ValueError("attachment_not_found")
        try:
            return self.attachment_service.get_attachment(thread_id, attachment_id)
        except ThreadAttachmentError as exc:
            raise ValueError("attachment_not_found") from exc

    @staticmethod
    def _attachment_message_part(attachment: ThreadStoredAttachment) -> dict[str, Any]:
        return {
            "type": attachment.kind,
            "attachmentId": attachment.attachment_id,
            "name": attachment.name,
            "mimeType": attachment.mime_type,
            "size": attachment.size,
        }

    @staticmethod
    def _user_message_content(
        text: str, attachments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = []
        if text.strip():
            parts.append({"type": "text", "text": text})
        parts.extend(attachments)
        return {"parts": parts}

    @staticmethod
    def _title_from_text(text: str) -> str:
        title = text.strip().splitlines()[0].strip() if text.strip() else ""
        return (title or "aiChat.thread.untitled")[:80]

    @staticmethod
    def _source_event_key(event: AgentEvent) -> str:
        if event.source_event_key is not None:
            return event.source_event_key
        return f"generated:{uuid4()}"

    @staticmethod
    def _text_from_user_content(content: dict[str, Any]) -> str:
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        return "\n".join(
            str(part.get("text"))
            for part in parts
            if isinstance(part, dict)
            and part.get("type") == "text"
            and part.get("text") is not None
        )

    @staticmethod
    def _tool_result_envelope(
        result: Any, is_error: bool
    ) -> tuple[dict[str, Any], bytes | None]:
        if isinstance(result, str):
            serialized = result
            media_type = "text/plain; charset=utf-8"
            line_count: int | None = 0 if result == "" else result.count("\n") + 1
        else:
            serialized = json.dumps(
                result,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            media_type = "application/json"
            line_count = None

        payload = serialized.encode("utf-8")
        preview_chars: list[str] = []
        preview_bytes = 0
        preview_lines = 1
        for char in serialized:
            encoded = char.encode("utf-8")
            if preview_bytes + len(encoded) > TOOL_RESULT_PREVIEW_MAX_BYTES:
                break
            if char == "\n" and preview_lines >= TOOL_RESULT_PREVIEW_MAX_LINES:
                break
            preview_chars.append(char)
            preview_bytes += len(encoded)
            if char == "\n":
                preview_lines += 1
        preview = "".join(preview_chars)
        truncated = len(preview.encode("utf-8")) < len(payload)
        envelope = {
            "isError": is_error,
            "preview": preview,
            "byteLength": len(payload),
            "lineCount": line_count,
            "truncated": truncated,
            "mediaType": media_type,
        }
        return envelope, payload if truncated else None
