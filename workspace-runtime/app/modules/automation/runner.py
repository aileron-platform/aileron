"""Single-loop Runtime Automation execution coordinator."""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.domain.enums import RUNNING_STATUSES, ThreadStatus
from app.modules.thread.persistence_models import ThreadModel
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.execution import (
    AgentRunner,
    AsyncSessionFactory,
)
from app.modules.thread.lifecycle import ThreadService
from app.modules.version_control.repository import VersionControlError
from app.modules.runtime_control.state import (
    RuntimeDrainingError,
    get_runtime_admission_state,
)

from .control_plane_client import ControlPlaneConflict
from .schemas import ClaimResponse, CompletionRequest, CompletionStatus
from .worktree import AutomationWorktreeError

logger = logging.getLogger(__name__)

AUTOMATION_MAX_CONCURRENT_EXECUTIONS = 3
AUTOMATION_EXECUTION_TIMEOUT_SECONDS = 1800
AUTOMATION_AGENT_STOP_GRACE_SECONDS = 30


class ControlPlane(Protocol):
    async def reconcile_restart(self, *, new_runner_instance_id: UUID) -> None: ...
    async def claim(
        self, *, runner_instance_id: UUID, claim_request_id: UUID
    ) -> ClaimResponse | None: ...
    async def complete(
        self, *, execution_id: str, payload: CompletionRequest
    ) -> Any: ...


class _ExecutionPhase(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    AGENT_STARTING = "agent_starting"
    AGENT_RUNNING = "agent_running"
    AGENT_TERMINAL = "agent_terminal"
    AGENT_STOPPED = "agent_stopped"


@dataclass
class _ExecutionContext:
    runner_instance_id: UUID
    claim_request_id: UUID
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    execution_id: str | None = None
    claim: ClaimResponse | None = None
    thread_id: str | None = None
    agent_execution_id: str | None = None
    thread_interface: ThreadService | None = None
    phase: _ExecutionPhase = _ExecutionPhase.INFRASTRUCTURE


class _StopConfirmationFailure(RuntimeError):
    pass


class _AgentExecutionFailure(RuntimeError):
    pass


class AutomationRunner:
    def __init__(
        self,
        *,
        runner_instance_id: UUID,
        workspace_id: str,
        control_plane: ControlPlane,
        worktree_service: Any,
        session_factory: AsyncSessionFactory,
        agent_runner: AgentRunner,
        fatal_shutdown: Callable[[str], Any] | None = None,
        max_concurrent_executions: int = AUTOMATION_MAX_CONCURRENT_EXECUTIONS,
        execution_timeout_seconds: float = AUTOMATION_EXECUTION_TIMEOUT_SECONDS,
        stop_grace_seconds: float = AUTOMATION_AGENT_STOP_GRACE_SECONDS,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.runner_instance_id = runner_instance_id
        self._workspace_id = workspace_id
        self._control_plane = control_plane
        self._worktree_service = worktree_service
        self._session_factory = session_factory
        self._agent_runner = agent_runner
        self._fatal_shutdown = fatal_shutdown or (lambda reason: None)
        self._semaphore = asyncio.Semaphore(max_concurrent_executions)
        self._execution_timeout = execution_timeout_seconds
        self._stop_grace = stop_grace_seconds
        self._poll_interval = poll_interval_seconds
        self._completion_event = asyncio.Event()
        self._pending: dict[tuple[UUID, UUID], _ExecutionContext] = {}
        self._active: dict[str, _ExecutionContext] = {}
        self._execution_tasks: set[asyncio.Task[None]] = set()
        self._coordinator_task: asyncio.Task[None] | None = None
        self._claim_task: asyncio.Task[None] | None = None
        self._task_group: asyncio.TaskGroup | None = None
        self._stopping = False
        self._fatal_reason: str | None = None
        self._fatal_callback_called = False

    @property
    def is_healthy(self) -> bool:
        return self._fatal_reason is None and (
            self._coordinator_task is None or not self._coordinator_task.done()
        )

    @property
    def fatal_reason(self) -> str | None:
        return self._fatal_reason

    def _claiming_disabled(self) -> bool:
        return self._stopping or self._fatal_reason is not None

    async def start(self) -> None:
        get_runtime_admission_state().require_accepting()
        if self._coordinator_task is not None:
            return
        await self._control_plane.reconcile_restart(
            new_runner_instance_id=self.runner_instance_id
        )
        self._coordinator_task = asyncio.create_task(
            self._run_coordinator(), name="automation-runner"
        )
        await asyncio.sleep(0)

    async def shutdown(self) -> None:
        self._stopping = True
        self._completion_event.set()
        if self._claim_task is not None:
            self._claim_task.cancel()
        for context in [*self._pending.values(), *self._active.values()]:
            context.cancel_event.set()
        coordinator = self._coordinator_task
        if coordinator is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(coordinator), timeout=self._stop_grace
                )
            except TimeoutError:
                interrupt = getattr(self._control_plane, "interrupt", None)
                if callable(interrupt):
                    interrupt()
                coordinator.cancel()
                try:
                    await asyncio.wait_for(
                        asyncio.shield(coordinator), timeout=self._stop_grace * 2
                    )
                except (TimeoutError, asyncio.CancelledError):
                    pass
            except asyncio.CancelledError:
                pass
            self._coordinator_task = None

    async def drain(self) -> None:
        """Stop claims and cancel every scheduled automation in this Runtime."""

        await self.shutdown()

    async def cancel_execution(
        self,
        *,
        execution_id: str,
        runner_instance_id: UUID,
        claim_request_id: UUID,
    ) -> None:
        context = self._active.get(execution_id)
        if context is not None and (
            context.runner_instance_id != runner_instance_id
            or context.claim_request_id != claim_request_id
        ):
            raise LookupError("execution_not_owned")
        if context is None:
            context = self._pending.get((runner_instance_id, claim_request_id))
        if context is None:
            raise LookupError("execution_not_owned")
        context.cancel_event.set()

    async def _run_coordinator(self) -> None:
        try:
            async with asyncio.TaskGroup() as task_group:
                self._task_group = task_group
                self._claim_task = task_group.create_task(
                    self._claim_loop(), name="automation-claim-loop"
                )
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            if not self._stopping:
                await self._mark_fatal(
                    f"automation_main_loop_failed:{type(exc).__name__}"
                )
        finally:
            self._task_group = None
            self._claim_task = None

    async def _claim_loop(self) -> None:
        while not self._claiming_disabled():
            try:
                get_runtime_admission_state().require_accepting()
            except RuntimeDrainingError:
                return
            await self._semaphore.acquire()
            if self._claiming_disabled():
                self._semaphore.release()
                return
            claim_request_id = uuid4()
            context = _ExecutionContext(self.runner_instance_id, claim_request_id)
            key = (self.runner_instance_id, claim_request_id)
            self._pending[key] = context
            try:
                claim = await self._control_plane.claim(
                    runner_instance_id=self.runner_instance_id,
                    claim_request_id=claim_request_id,
                )
            except asyncio.CancelledError:
                self._pending.pop(key, None)
                self._semaphore.release()
                raise
            if claim is None:
                self._pending.pop(key, None)
                self._semaphore.release()
                self._completion_event.clear()
                try:
                    await asyncio.wait_for(
                        self._completion_event.wait(), timeout=self._poll_interval
                    )
                except TimeoutError:
                    pass
                continue

            try:
                get_runtime_admission_state().require_accepting()
            except RuntimeDrainingError:
                context.cancel_event.set()
                self._pending.pop(key, None)
                self._semaphore.release()
                return

            if (
                claim.runner_instance_id != self.runner_instance_id
                or claim.claim_request_id != claim_request_id
                or claim.workspace_id != self._workspace_id
            ):
                raise RuntimeError("claim_identity_mismatch")

            # Bind synchronously before any await so cancellation cannot miss ownership.
            context.execution_id = claim.execution_id
            context.claim = claim
            self._pending.pop(key, None)
            self._active[claim.execution_id] = context
            if claim.cancel_requested_at is not None:
                context.cancel_event.set()
            if self._fatal_reason is not None:
                # The claim committed while another execution made this Runtime
                # fatal. Keep ownership running for restart reconciliation; do
                # not start, complete, or release its permit in this process.
                context.cancel_event.set()
                return
            if self._task_group is None:
                raise RuntimeError("automation_task_group_unavailable")
            task = self._task_group.create_task(
                self._run_execution_guarded(context),
                name=f"automation-execution-{claim.execution_id}",
            )
            self._execution_tasks.add(task)
            task.add_done_callback(self._execution_tasks.discard)

    async def _run_execution_guarded(self, context: _ExecutionContext) -> None:
        accepted = False
        try:
            payload = await self._run_with_deadline(context)
            accepted = await self._complete_with_conflict_resolution(context, payload)
        except _StopConfirmationFailure:
            return
        except asyncio.CancelledError:
            if self._stopping:
                await asyncio.shield(self._stop_or_fatal(context, reason="shutdown"))
                raise
            logger.exception("Unexpected Automation execution cancellation")
        except Exception as exc:
            logger.exception("Automation execution failed unexpectedly")
            payload = await self._ordinary_failure(context, exc)
            accepted = await self._complete_with_conflict_resolution(context, payload)
        finally:
            if accepted and context.execution_id is not None:
                self._active.pop(context.execution_id, None)
                self._semaphore.release()
                self._completion_event.set()

    async def _run_with_deadline(self, context: _ExecutionContext) -> CompletionRequest:
        try:
            async with asyncio.timeout(self._execution_timeout):
                return await self._execute(context)
        except TimeoutError:
            await self._stop_or_fatal(context, reason="timeout")
            await self._transition_thread(context, ThreadStatus.ERROR, "timeout")
            return self._completion(context, "failed", "timeout")

    async def _execute(self, context: _ExecutionContext) -> CompletionRequest:
        claim = context.claim
        if claim is None:
            raise RuntimeError("claim_missing")
        if context.cancel_event.is_set():
            return self._completion(context, "cancelled")

        worktree = await self._worktree_service.ensure_for_job(
            job_id=claim.job_id, worktree_key=claim.worktree_key
        )
        if context.cancel_event.is_set():
            return self._completion(context, "cancelled")
        await self._worktree_service.preflight(worktree)
        if context.cancel_event.is_set():
            return self._completion(context, "cancelled")

        async with self._session_factory() as session:
            service = ThreadService(
                session,
                self._workspace_id,
                runner=self._agent_runner,
                event_session_factory=self._session_factory,
            )
            context.thread_interface = service
            detail = await service.create_or_get_automation_thread(
                automation_job_id=claim.job_id,
                automation_execution_id=claim.execution_id,
                user_id=claim.principal_user_id,
                git_context_id=worktree.context_id,
                agentic_tool=claim.agentic_tool,
                model=claim.model,
                agent_mode=claim.agent_config.mode,
            )
            context.thread_id = detail.id
            await session.commit()
            if context.cancel_event.is_set():
                await self._transition_thread_in_session(
                    session, context, ThreadStatus.CANCELED, None
                )
                return self._completion(context, "cancelled")

            execution_id = str(uuid4())
            await service.prepare_automation_execution(
                thread_id=detail.id,
                message={"text": claim.prompt, "attachments": []},
                execution_id=execution_id,
                permission_mode=claim.agent_config.permission_mode,
            )
            context.agent_execution_id = execution_id
            if context.cancel_event.is_set():
                await self._transition_thread_in_session(
                    session, context, ThreadStatus.CANCELED, None
                )
                return self._completion(context, "cancelled")

            context.phase = _ExecutionPhase.AGENT_STARTING
            try:
                await service.start_automation_execution(
                    thread_id=detail.id,
                    execution_id=execution_id,
                    permission_mode=claim.agent_config.permission_mode,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise _AgentExecutionFailure("agent_start_failed") from exc
            context.phase = _ExecutionPhase.AGENT_RUNNING
            if context.cancel_event.is_set():
                await self._stop_or_fatal(context, reason="cancelled")
                await self._transition_thread_in_session(
                    session, context, ThreadStatus.CANCELED, None
                )
                return self._completion(context, "cancelled")

            try:
                await self._wait_for_agent_or_cancel(context)
            except (asyncio.CancelledError, _StopConfirmationFailure):
                raise
            except Exception as exc:
                raise _AgentExecutionFailure("agent_run_failed") from exc
            if context.cancel_event.is_set():
                await self._transition_thread(context, ThreadStatus.CANCELED, None)
            elif context.phase == _ExecutionPhase.AGENT_RUNNING:
                context.phase = _ExecutionPhase.AGENT_TERMINAL
            session.expire_all()
            thread = await ThreadRepository(
                session, self._workspace_id
            ).get_by_automation_execution(claim.execution_id)
            if thread is None:
                raise RuntimeError("automation_thread_missing")
            if not context.cancel_event.is_set() and ThreadStatus(
                thread.status
            ) in RUNNING_STATUSES | {ThreadStatus.DRAFT}:
                await self._transition_thread(
                    context, ThreadStatus.ERROR, "agent_process_failed"
                )
                session.expire_all()
                thread = await ThreadRepository(
                    session, self._workspace_id
                ).get_by_automation_execution(claim.execution_id)
                if thread is None:
                    raise RuntimeError("automation_thread_missing")
            return self._payload_from_thread(context, thread)

    async def _wait_for_agent_or_cancel(self, context: _ExecutionContext) -> None:
        execution_id = context.agent_execution_id
        if execution_id is None:
            raise RuntimeError("agent_execution_identity_missing")
        thread_interface = context.thread_interface
        if thread_interface is None:
            raise RuntimeError("thread_interface_missing")
        wait_task = asyncio.create_task(
            thread_interface.wait_for_execution(execution_id)
        )
        cancel_task = asyncio.create_task(context.cancel_event.wait())
        try:
            done, _ = await asyncio.wait(
                {wait_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if cancel_task in done and context.cancel_event.is_set():
                await self._stop_or_fatal(context, reason="cancelled")
            else:
                await asyncio.shield(wait_task)
        finally:
            cancel_task.cancel()
            # Never cancel the underlying Agent waiter. Timeout/cancel paths must
            # first stop the process and then confirm the same execution is dead.

    async def _stop_or_fatal(self, context: _ExecutionContext, *, reason: str) -> None:
        execution_id = context.agent_execution_id
        if execution_id is None or context.phase not in {
            _ExecutionPhase.AGENT_STARTING,
            _ExecutionPhase.AGENT_RUNNING,
        }:
            return
        thread_interface = context.thread_interface
        if thread_interface is None:
            raise RuntimeError("thread_interface_missing")

        async def stop_and_confirm() -> None:
            if not thread_interface.execution_is_alive(execution_id):
                context.phase = _ExecutionPhase.AGENT_STOPPED
                return
            await asyncio.shield(
                thread_interface.stop_and_confirm_execution(execution_id)
            )
            context.phase = _ExecutionPhase.AGENT_STOPPED

        try:
            async with asyncio.timeout(self._stop_grace):
                await stop_and_confirm()
        except (TimeoutError, Exception) as exc:
            await self._mark_fatal(f"automation_agent_stop_failed:{reason}")
            raise _StopConfirmationFailure(reason) from exc

    async def _ordinary_failure(
        self, context: _ExecutionContext, exc: Exception
    ) -> CompletionRequest:
        if context.phase in {
            _ExecutionPhase.AGENT_STARTING,
            _ExecutionPhase.AGENT_RUNNING,
        }:
            await self._stop_or_fatal(context, reason="exception")
        agent_failure = isinstance(exc, _AgentExecutionFailure)
        execution_code = (
            "agent_execution_failed" if agent_failure else "automation_execution_failed"
        )
        if isinstance(exc, AutomationWorktreeError):
            execution_code = exc.error_code
        elif (
            isinstance(exc, VersionControlError)
            and exc.error_code == "repository_not_initialized"
        ):
            execution_code = "workspace_git_repository_required"
        if context.thread_id is not None:
            await self._transition_thread(
                context,
                ThreadStatus.ERROR,
                (
                    "agent_process_failed"
                    if agent_failure
                    else "automation_execution_failed"
                ),
            )
        return self._completion(context, "failed", execution_code)

    async def _transition_thread(
        self,
        context: _ExecutionContext,
        status: ThreadStatus,
        error_code: str | None,
    ) -> None:
        if context.thread_id is None:
            return
        async with self._session_factory() as session:
            await self._transition_thread_in_session(
                session, context, status, error_code
            )

    async def _transition_thread_in_session(
        self,
        session: AsyncSession,
        context: _ExecutionContext,
        status: ThreadStatus,
        error_code: str | None,
    ) -> None:
        if context.thread_id is None:
            return

        transitioned = False

        def mutate(thread: ThreadModel) -> None:
            nonlocal transitioned
            current = ThreadStatus(thread.status)
            if current not in RUNNING_STATUSES and current != ThreadStatus.DRAFT:
                return
            transitioned = True
            thread.status = status.value
            thread.queued_messages = []
            if status == ThreadStatus.ERROR and not thread.error_code:
                thread.error_code = error_code
                thread.error_info = {"code": error_code} if error_code else None

        updated = await ThreadRepository(session, self._workspace_id).locked_update(
            context.thread_id, mutate
        )
        if transitioned and updated is not None:
            execution_id = context.agent_execution_id
            turn_repo = ThreadTurnRepository(session)
            execution = (
                await turn_repo.get_execution(execution_id)
                if execution_id is not None
                else None
            )
            turn = (
                await turn_repo.get_turn(updated.id, execution.turn_id)
                if execution is not None
                else None
            )
            if execution is not None and turn is not None:
                await turn_repo.finish(
                    thread=updated,
                    execution=execution,
                    turn=turn,
                    status=status.value,
                    error_code=error_code,
                    error_info={"code": error_code} if error_code else None,
                )
            else:
                updated.active_turn_id = None
                updated.active_turn_execution_id = None
        await session.commit()

    def _payload_from_thread(
        self, context: _ExecutionContext, thread: ThreadModel
    ) -> CompletionRequest:
        status = ThreadStatus(thread.status)
        if context.cancel_event.is_set():
            if status in RUNNING_STATUSES:
                return self._completion(context, "cancelled")
            if status == ThreadStatus.CANCELED:
                return self._completion(context, "cancelled")
        if status == ThreadStatus.COMPLETE:
            return self._completion(context, "success")
        if status == ThreadStatus.CANCELED:
            return self._completion(context, "cancelled")
        return self._completion(
            context,
            "failed",
            "agent_execution_failed",
            thread.error_message,
        )

    def _completion(
        self,
        context: _ExecutionContext,
        status: CompletionStatus,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> CompletionRequest:
        return CompletionRequest(
            runnerInstanceId=context.runner_instance_id,
            claimRequestId=context.claim_request_id,
            status=status,
            errorCode=error_code,
            errorMessage=error_message,
        )

    async def _complete_with_conflict_resolution(
        self, context: _ExecutionContext, payload: CompletionRequest
    ) -> bool:
        if context.execution_id is None:
            raise RuntimeError("execution_identity_missing")
        try:
            await self._control_plane.complete(
                execution_id=context.execution_id, payload=payload
            )
            return True
        except ControlPlaneConflict as exc:
            if exc.code == "execution_already_terminal":
                return True
            if exc.code != "execution_cancel_requested":
                raise
            context.cancel_event.set()
            await self._stop_or_fatal(context, reason="cancelled")
            await self._transition_thread(context, ThreadStatus.CANCELED, None)
            await self._control_plane.complete(
                execution_id=context.execution_id,
                payload=self._completion(context, "cancelled"),
            )
            return True

    async def _mark_fatal(self, reason: str) -> None:
        if self._fatal_reason is None:
            self._fatal_reason = reason
            self._stopping = True
            self._completion_event.set()
        if self._fatal_callback_called:
            return
        self._fatal_callback_called = True
        result = self._fatal_shutdown(reason)
        if inspect.isawaitable(result):
            await result


__all__ = [
    "AUTOMATION_AGENT_STOP_GRACE_SECONDS",
    "AUTOMATION_EXECUTION_TIMEOUT_SECONDS",
    "AUTOMATION_MAX_CONCURRENT_EXECUTIONS",
    "AutomationRunner",
]
