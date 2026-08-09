from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import MethodType
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.automation.runner import (
    AutomationRunner,
    _ExecutionContext,
    _ExecutionPhase,
    _StopConfirmationFailure,
)
from app.modules.automation.schemas import ClaimResponse, CompletionResponse
from app.modules.automation.control_plane_client import ControlPlaneConflict
from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.persistence_models import ThreadModel
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.thread.execution import AgentEvent
from app.modules.thread.lifecycle import ThreadService
from app.modules.automation.worktree import WorktreeContext
from app.modules.version_control.repository import VersionControlError


class NoopControlPlane:
    async def reconcile_restart(self, **kwargs):
        return None


class HangingStopRunner:
    async def stop(self, execution_id: str) -> None:
        await asyncio.Event().wait()

    async def wait(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return True


class RunnerThreadInterface:
    """Test adapter for the stable Thread execution interface."""

    def __init__(self, runner) -> None:
        self.runner = runner

    async def wait_for_execution(self, execution_id: str) -> None:
        await self.runner.wait(execution_id)

    async def stop_and_confirm_execution(self, execution_id: str) -> None:
        if not self.runner.is_alive(execution_id):
            return
        await self.runner.stop(execution_id)
        await self.runner.wait(execution_id)
        if self.runner.is_alive(execution_id):
            raise RuntimeError("agent_process_still_alive")

    def execution_is_alive(self, execution_id: str) -> bool:
        return self.runner.is_alive(execution_id)


@pytest.mark.asyncio
async def test_stop_call_itself_is_inside_grace_and_fatal_callback_runs_once() -> None:
    fatal_reasons: list[str] = []
    runner_id = uuid4()
    claim_id = uuid4()
    agent = HangingStopRunner()
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=NoopControlPlane(),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=agent,
        fatal_shutdown=fatal_reasons.append,
        stop_grace_seconds=0.01,
    )
    context = _ExecutionContext(
        runner_instance_id=runner_id,
        claim_request_id=claim_id,
        execution_id="execution-1",
        agent_execution_id="agent-1",
        thread_interface=RunnerThreadInterface(agent),
        phase=_ExecutionPhase.AGENT_RUNNING,
    )

    with pytest.raises(_StopConfirmationFailure):
        await runner._stop_or_fatal(context, reason="timeout")
    with pytest.raises(_StopConfirmationFailure):
        await runner._stop_or_fatal(context, reason="timeout")

    assert runner.is_healthy is False
    assert runner.fatal_reason == "automation_agent_stop_failed:timeout"
    assert fatal_reasons == ["automation_agent_stop_failed:timeout"]


class ShieldProbeRunner:
    def __init__(self) -> None:
        self.stopped = False
        self.wait_cancelled = False
        self.dead = asyncio.Event()

    async def wait(self, execution_id: str) -> None:
        try:
            await self.dead.wait()
        except asyncio.CancelledError:
            self.wait_cancelled = True
            raise

    async def stop(self, execution_id: str) -> None:
        self.stopped = True
        self.dead.set()

    def is_alive(self, execution_id: str) -> bool:
        return not self.dead.is_set()


@pytest.mark.asyncio
async def test_execution_timeout_does_not_cancel_underlying_agent_waiter(
    monkeypatch,
) -> None:
    agent = ShieldProbeRunner()
    runner_id = uuid4()
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=NoopControlPlane(),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=agent,
        execution_timeout_seconds=0.01,
        stop_grace_seconds=0.1,
    )
    context = _ExecutionContext(
        runner_id,
        uuid4(),
        execution_id="execution-1",
        agent_execution_id="agent-1",
        thread_interface=RunnerThreadInterface(agent),
        phase=_ExecutionPhase.AGENT_RUNNING,
    )

    async def wait_forever(self, current):
        await self._wait_for_agent_or_cancel(current)
        raise AssertionError("wait unexpectedly returned")

    monkeypatch.setattr(runner, "_execute", MethodType(wait_forever, runner))
    payload = await runner._run_with_deadline(context)
    assert payload.status == "failed"
    assert payload.error_code == "timeout"
    assert agent.stopped is True
    assert agent.wait_cancelled is False


@pytest.mark.asyncio
async def test_public_cancel_after_spawn_stops_waits_and_confirms_process_dead() -> (
    None
):
    agent = ShieldProbeRunner()
    runner_id = uuid4()
    claim_id = uuid4()
    context = _ExecutionContext(
        runner_id,
        claim_id,
        execution_id="execution-1",
        agent_execution_id="agent-1",
        thread_interface=RunnerThreadInterface(agent),
        phase=_ExecutionPhase.AGENT_RUNNING,
    )
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=NoopControlPlane(),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=agent,
        stop_grace_seconds=0.1,
    )
    runner._active["execution-1"] = context
    waiter = asyncio.create_task(runner._wait_for_agent_or_cancel(context))
    await asyncio.sleep(0)
    await runner.cancel_execution(
        execution_id="execution-1",
        runner_instance_id=runner_id,
        claim_request_id=claim_id,
    )
    await asyncio.wait_for(waiter, timeout=0.2)
    assert agent.stopped is True
    assert agent.is_alive("agent-1") is False


class CrashingClaimControlPlane(NoopControlPlane):
    async def claim(self, **kwargs):
        raise RuntimeError("claim loop exploded")


@pytest.mark.asyncio
async def test_unexpected_main_loop_failure_is_fatal() -> None:
    fatal_reasons: list[str] = []
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=CrashingClaimControlPlane(),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        fatal_shutdown=fatal_reasons.append,
    )
    await runner.start()
    for _ in range(20):
        if runner.fatal_reason:
            break
        await asyncio.sleep(0)
    assert runner.fatal_reason is not None
    assert len(fatal_reasons) == 1
    await runner.shutdown()


@pytest.mark.asyncio
async def test_fatal_execution_keeps_permit_and_prevents_new_claims(
    monkeypatch,
) -> None:
    control = QueueControlPlane(4)
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        max_concurrent_executions=1,
        stop_grace_seconds=0.01,
    )

    async def fatal_outcome(self, context):
        await self._mark_fatal("automation_agent_stop_failed:timeout")
        raise _StopConfirmationFailure("timeout")

    monkeypatch.setattr(runner, "_run_with_deadline", MethodType(fatal_outcome, runner))
    await runner.start()
    for _ in range(100):
        if runner.fatal_reason is not None:
            break
        await asyncio.sleep(0)
    assert control.claim_count == 1
    assert len(runner._active) == 1
    assert runner._semaphore._value == 0
    await runner.shutdown()


@pytest.mark.asyncio
async def test_shutdown_stops_and_confirms_all_active_executions(monkeypatch) -> None:
    class MultiAgent:
        def __init__(self):
            self.stops = []
            self.dead = {}

        async def stop(self, execution_id):
            self.stops.append(execution_id)
            self.dead.setdefault(execution_id, asyncio.Event()).set()

        async def wait(self, execution_id):
            await self.dead.setdefault(execution_id, asyncio.Event()).wait()

        def is_alive(self, execution_id):
            return not self.dead.setdefault(execution_id, asyncio.Event()).is_set()

    control = QueueControlPlane(3)
    agent = MultiAgent()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=agent,
        max_concurrent_executions=3,
        stop_grace_seconds=0.1,
    )

    async def active_until_shutdown(self, context):
        context.agent_execution_id = context.execution_id
        context.thread_interface = RunnerThreadInterface(agent)
        context.phase = _ExecutionPhase.AGENT_RUNNING
        await context.cancel_event.wait()
        await self._stop_or_fatal(context, reason="shutdown")
        return self._completion(context, "cancelled")

    monkeypatch.setattr(
        runner, "_run_with_deadline", MethodType(active_until_shutdown, runner)
    )
    await runner.start()
    for _ in range(100):
        if len(runner._active) == 3:
            break
        await asyncio.sleep(0)
    await runner.shutdown()
    assert sorted(agent.stops) == ["execution-1", "execution-2", "execution-3"]
    assert len(control.completions) == 3


def make_claim(index: int, runner_id, claim_id) -> ClaimResponse:
    return ClaimResponse.model_validate(
        {
            "executionId": f"execution-{index}",
            "jobId": f"job-{index}",
            "workspaceId": "workspace-1",
            "trigger": "manual",
            "scheduledFor": datetime.now(timezone.utc),
            "principalUserId": "user-1",
            "prompt": "run",
            "agenticTool": "claude",
            "model": "claude-opus-4-8",
            "agentConfig": {
                "mode": "execute",
                "permissionMode": "bypassPermissions",
            },
            "worktreeKey": f"automation/job-{index}",
            "runnerInstanceId": runner_id,
            "claimRequestId": claim_id,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cancel_stage", "expected_ensure", "expected_preflight"),
    [("initial", 0, 0), ("ensure", 1, 0), ("preflight", 1, 1)],
)
async def test_pre_thread_cancel_checkpoint_matrix(
    cancel_stage, expected_ensure, expected_preflight
) -> None:
    runner_id = uuid4()
    claim_id = uuid4()
    context = _ExecutionContext(runner_id, claim_id)
    context.execution_id = "execution-1"
    context.claim = make_claim(1, runner_id, claim_id)

    class StageWorktree:
        def __init__(self):
            self.ensure_calls = 0
            self.preflight_calls = 0

        async def ensure_for_job(self, **kwargs):
            self.ensure_calls += 1
            if cancel_stage == "ensure":
                context.cancel_event.set()
            return object()

        async def preflight(self, value):
            self.preflight_calls += 1
            if cancel_stage == "preflight":
                context.cancel_event.set()

    worktree = StageWorktree()
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=QueueControlPlane(0),
        worktree_service=worktree,
        session_factory=lambda: None,
        agent_runner=object(),
    )
    if cancel_stage == "initial":
        context.cancel_event.set()
    payload = await runner._execute(context)
    assert payload.status == "cancelled"
    assert worktree.ensure_calls == expected_ensure
    assert worktree.preflight_calls == expected_preflight


class QueueControlPlane(NoopControlPlane):
    def __init__(self, total: int) -> None:
        self.total = total
        self.claim_count = 0
        self.completions = []

    async def claim(self, *, runner_instance_id, claim_request_id):
        self.claim_count += 1
        if self.claim_count > self.total:
            return None
        return make_claim(self.claim_count, runner_instance_id, claim_request_id)

    async def complete(self, *, execution_id, payload):
        self.completions.append((execution_id, payload))
        return CompletionResponse(status=payload.status)


class BlockingWorktree:
    def __init__(self) -> None:
        self.entered = 0
        self.max_entered = 0
        self.release = asyncio.Event()

    async def ensure_for_job(self, **kwargs):
        self.entered += 1
        self.max_entered = max(self.max_entered, self.entered)
        await self.release.wait()
        self.entered -= 1
        return object()


@pytest.mark.asyncio
async def test_two_hundred_jobs_create_only_three_active_execution_tasks() -> None:
    control = QueueControlPlane(200)
    worktree = BlockingWorktree()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=worktree,
        session_factory=lambda: None,
        agent_runner=object(),
        poll_interval_seconds=0.001,
    )
    await runner.start()
    for _ in range(100):
        if control.claim_count == 3 and worktree.entered == 3:
            break
        await asyncio.sleep(0)

    assert control.claim_count == 3
    assert len(runner._active) == 3
    assert len(runner._execution_tasks) == 3
    assert worktree.max_entered == 3

    shutdown_task = asyncio.create_task(runner.shutdown())
    worktree.release.set()
    await asyncio.wait_for(shutdown_task, timeout=1)
    assert len(control.completions) == 3


class ParseBarrierControlPlane(QueueControlPlane):
    def __init__(self) -> None:
        super().__init__(1)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.identity = None
        self.returned = False

    async def claim(self, *, runner_instance_id, claim_request_id):
        if self.returned:
            return None
        self.identity = (runner_instance_id, claim_request_id)
        self.entered.set()
        await self.release.wait()
        self.returned = True
        return make_claim(1, runner_instance_id, claim_request_id)


class CountingWorktree:
    def __init__(self) -> None:
        self.calls = 0

    async def ensure_for_job(self, **kwargs):
        self.calls += 1
        raise AssertionError("cancelled pending claim reached worktree")


@pytest.mark.asyncio
async def test_cancel_committed_while_claim_response_is_pending_skips_worktree() -> (
    None
):
    control = ParseBarrierControlPlane()
    worktree = CountingWorktree()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=worktree,
        session_factory=lambda: None,
        agent_runner=object(),
    )
    await runner.start()
    await control.entered.wait()
    assert control.identity is not None
    await runner.cancel_execution(
        execution_id="execution-1",
        runner_instance_id=control.identity[0],
        claim_request_id=control.identity[1],
    )
    control.release.set()
    for _ in range(100):
        if control.completions:
            break
        await asyncio.sleep(0)
    assert control.completions[0][1].status == "cancelled"
    assert worktree.calls == 0
    await runner.shutdown()


@pytest.mark.asyncio
async def test_guarded_ordinary_failure_does_not_cancel_sibling(monkeypatch) -> None:
    control = QueueControlPlane(0)
    runner_id = uuid4()
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )
    contexts = [
        _ExecutionContext(runner_id, uuid4(), execution_id=f"execution-{index}")
        for index in (1, 2)
    ]
    for context in contexts:
        runner._active[context.execution_id] = context

    async def outcomes(self, context):
        if context.execution_id == "execution-1":
            raise RuntimeError("ordinary")
        await asyncio.sleep(0)
        return self._completion(context, "success")

    monkeypatch.setattr(runner, "_run_with_deadline", MethodType(outcomes, runner))
    await asyncio.gather(*(runner._run_execution_guarded(item) for item in contexts))
    assert {payload.status for _, payload in control.completions} == {
        "failed",
        "success",
    }


@pytest.mark.asyncio
async def test_manager_completion_delay_is_outside_execution_deadline(
    monkeypatch,
) -> None:
    control = QueueControlPlane(0)
    original_complete = control.complete

    async def delayed_complete(**kwargs):
        await asyncio.sleep(0.03)
        return await original_complete(**kwargs)

    monkeypatch.setattr(control, "complete", delayed_complete)
    runner_id = uuid4()
    context = _ExecutionContext(runner_id, uuid4(), execution_id="execution-1")
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        execution_timeout_seconds=0.001,
    )
    runner._active["execution-1"] = context

    async def immediate_outcome(self, current):
        return self._completion(current, "success")

    monkeypatch.setattr(
        runner, "_run_with_deadline", MethodType(immediate_outcome, runner)
    )
    await runner._run_execution_guarded(context)
    assert control.completions[0][1].status == "success"


@pytest.mark.asyncio
async def test_shutdown_interrupts_permanent_completion_transport_retry(
    monkeypatch,
) -> None:
    class HangingCompletionControl(QueueControlPlane):
        def __init__(self):
            super().__init__(1)
            self.completion_entered = asyncio.Event()
            self.interrupted = asyncio.Event()

        async def complete(self, **kwargs):
            self.completion_entered.set()
            await self.interrupted.wait()
            raise asyncio.CancelledError

        def interrupt(self):
            self.interrupted.set()

    control = HangingCompletionControl()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        stop_grace_seconds=0.01,
    )

    async def immediate_outcome(self, context):
        return self._completion(context, "success")

    monkeypatch.setattr(
        runner, "_run_with_deadline", MethodType(immediate_outcome, runner)
    )
    await runner.start()
    await asyncio.wait_for(control.completion_entered.wait(), timeout=1)
    await asyncio.wait_for(runner.shutdown(), timeout=0.2)
    assert control.interrupted.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("conflict_code", "expected_statuses"),
    [
        ("execution_cancel_requested", ["success", "cancelled"]),
        ("execution_already_terminal", ["success"]),
    ],
)
async def test_completion_conflicts_follow_manager_cas_decision(
    conflict_code, expected_statuses
) -> None:
    class ConflictControl(QueueControlPlane):
        async def complete(self, *, execution_id, payload):
            self.completions.append((execution_id, payload))
            if len(self.completions) == 1:
                raise ControlPlaneConflict(conflict_code, payload={})
            return CompletionResponse(status=payload.status)

    control = ConflictControl(0)
    runner_id = uuid4()
    context = _ExecutionContext(runner_id, uuid4(), execution_id="execution-1")
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )
    accepted = await runner._complete_with_conflict_resolution(
        context, runner._completion(context, "success")
    )
    assert accepted is True
    assert [payload.status for _, payload in control.completions] == expected_statuses


@pytest.mark.parametrize(
    ("thread_status", "expected"),
    [(ThreadStatus.COMPLETE, "success"), (ThreadStatus.ERROR, "failed")],
)
def test_late_cancel_preserves_existing_thread_terminal(
    thread_status, expected
) -> None:
    runner_id = uuid4()
    context = _ExecutionContext(runner_id, uuid4(), execution_id="execution-1")
    context.cancel_event.set()
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=QueueControlPlane(0),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )
    thread = ThreadModel(
        id="thread-1",
        workspace_id="workspace-1",
        user_id="user-1",
        origin="automation",
        title="",
        agentic_tool="claude",
        model="model",
        status=thread_status.value,
        queued_messages=[],
        archived=False,
        error_code=(
            "tool_specific_failure" if thread_status == ThreadStatus.ERROR else None
        ),
    )
    payload = runner._payload_from_thread(context, thread)
    assert payload.status == expected
    if expected == "failed":
        assert payload.error_code == "agent_execution_failed"


class CompletingAgentRunner:
    def __init__(self, *, fail_start: bool = False) -> None:
        self.fail_start = fail_start
        self.counter = 0
        self.alive: set[str] = set()
        self.requests = []
        self.stops: list[str] = []

    def reserve(self) -> str:
        self.counter += 1
        return f"agent-{self.counter}"

    def adopt_reservation(self, execution_id: str) -> None:
        return None

    async def start(self, request, on_event, execution_id: str) -> None:
        self.requests.append(request)
        if self.fail_start:
            raise RuntimeError("spawn failed")
        self.alive.add(execution_id)
        await on_event(AgentEvent(type="complete"))
        self.alive.discard(execution_id)

    async def wait(self, execution_id: str) -> None:
        while execution_id in self.alive:
            await asyncio.sleep(0)

    async def stop(self, execution_id: str) -> None:
        self.stops.append(execution_id)
        self.alive.discard(execution_id)

    def is_alive(self, execution_id: str) -> bool:
        return execution_id in self.alive

    async def destroy_thread(self, thread_id: str) -> None:
        return None


class ReadyWorktree:
    async def ensure_for_job(self, **kwargs):
        return WorktreeContext(
            context_id="worktree:automation--job-1",
            path=None,
            branch="automation/job-1",
        )

    async def preflight(self, context) -> None:
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fail_start", "execution_status", "thread_status", "thread_error"),
    [
        (False, "success", ThreadStatus.COMPLETE.value, None),
        (True, "failed", ThreadStatus.ERROR.value, "agent_process_failed"),
    ],
)
async def test_real_thread_persistence_uses_claim_snapshots_and_stable_errors(
    postgres_engine,
    fail_start,
    execution_status,
    thread_status,
    thread_error,
) -> None:
    workspace_id = str(uuid4())
    session_factory = async_sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with postgres_engine.begin() as connection:
        await connection.run_sync(ThreadModel.metadata.create_all)
    async with session_factory() as session:
        await CapabilitiesStore().put(
            session,
            workspace_id,
            {
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
            },
        )
        await session.commit()

    control = QueueControlPlane(1)
    original_claim = control.claim
    automation_execution_id = str(uuid4())

    async def workspace_claim(**kwargs):
        claim = await original_claim(**kwargs)
        if claim is not None:
            claim.workspace_id = workspace_id
            claim.principal_user_id = "principal-snapshot"
            claim.execution_id = automation_execution_id
        return claim

    control.claim = workspace_claim
    agent = CompletingAgentRunner(fail_start=fail_start)
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=session_factory,
        agent_runner=agent,
        poll_interval_seconds=0.01,
    )
    await runner.start()
    for _ in range(1000):
        if control.completions:
            break
        await asyncio.sleep(0.001)
    assert control.completions[0][1].status == execution_status

    async with session_factory() as session:
        thread = await ThreadRepository(
            session, workspace_id
        ).get_by_automation_execution(automation_execution_id)
        assert thread is not None
        assert thread.user_id == "principal-snapshot"
        assert thread.agentic_tool == "claude"
        assert thread.model == "claude-opus-4-8"
        assert thread.claude_mode == "execute"
        assert thread.status == thread_status
        assert thread.error_code == thread_error
    if not fail_start:
        assert agent.requests[0].permission_mode == "bypassPermissions"
    await runner.shutdown()


@pytest.mark.asyncio
async def test_each_claim_uses_a_distinct_async_session(postgres_engine) -> None:
    workspace_id = str(uuid4())
    base_factory = async_sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with postgres_engine.begin() as connection:
        await connection.run_sync(ThreadModel.metadata.create_all)
    async with base_factory() as session:
        await CapabilitiesStore().put(
            session,
            workspace_id,
            {
                "tools": [
                    {
                        "id": "claude",
                        "models": ["claude-opus-4-8"],
                        "default_model": "claude-opus-4-8",
                        "modes": ["execute"],
                        "default_mode": "execute",
                        "context_window": 200000,
                    }
                ],
                "default_tool": "claude",
            },
        )
        await session.commit()

    class TrackingFactory:
        def __init__(self):
            self.sessions = []

        def __call__(self):
            session = base_factory()
            self.sessions.append(session)
            return session

    tracking_factory = TrackingFactory()
    control = QueueControlPlane(2)
    original_claim = control.claim

    async def workspace_claim(**kwargs):
        claim = await original_claim(**kwargs)
        if claim is not None:
            claim.workspace_id = workspace_id
            claim.execution_id = str(uuid4())
        return claim

    control.claim = workspace_claim
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=tracking_factory,
        agent_runner=CompletingAgentRunner(),
        max_concurrent_executions=2,
        poll_interval_seconds=0.01,
    )
    await runner.start()
    for _ in range(1000):
        if len(control.completions) == 2:
            break
        await asyncio.sleep(0.001)
    assert len(control.completions) == 2
    assert len(tracking_factory.sessions) >= 2
    assert len({id(session) for session in tracking_factory.sessions}) == len(
        tracking_factory.sessions
    )
    await runner.shutdown()


@pytest.mark.asyncio
async def test_cancel_after_thread_submission_persisted_does_not_spawn_or_stop_agent(
    postgres_engine, monkeypatch
) -> None:
    workspace_id = str(uuid4())
    automation_execution_id = str(uuid4())
    session_factory = async_sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with postgres_engine.begin() as connection:
        await connection.run_sync(ThreadModel.metadata.create_all)
    async with session_factory() as session:
        await CapabilitiesStore().put(
            session,
            workspace_id,
            {
                "tools": [
                    {
                        "id": "claude",
                        "models": ["claude-opus-4-8"],
                        "default_model": "claude-opus-4-8",
                        "modes": ["execute"],
                        "default_mode": "execute",
                        "context_window": 200000,
                    }
                ],
                "default_tool": "claude",
            },
        )
        await session.commit()

    prepared = asyncio.Event()
    release = asyncio.Event()
    original_prepare = ThreadService.prepare_automation_execution

    async def prepare_barrier(self, *args, **kwargs):
        result = await original_prepare(self, *args, **kwargs)
        prepared.set()
        await release.wait()
        return result

    monkeypatch.setattr(
        ThreadService,
        "prepare_automation_execution",
        prepare_barrier,
    )
    control = QueueControlPlane(1)
    original_claim = control.claim

    async def workspace_claim(**kwargs):
        claim = await original_claim(**kwargs)
        if claim is not None:
            claim.workspace_id = workspace_id
            claim.execution_id = automation_execution_id
        return claim

    control.claim = workspace_claim
    agent = CompletingAgentRunner()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=session_factory,
        agent_runner=agent,
    )
    await runner.start()
    await asyncio.wait_for(prepared.wait(), timeout=1)
    context = runner._active[automation_execution_id]
    await runner.cancel_execution(
        execution_id=automation_execution_id,
        runner_instance_id=context.runner_instance_id,
        claim_request_id=context.claim_request_id,
    )
    release.set()
    for _ in range(1000):
        if control.completions:
            break
        await asyncio.sleep(0.001)
    assert control.completions[0][1].status == "cancelled"
    assert agent.requests == []
    assert agent.stops == []
    async with session_factory() as session:
        thread = await ThreadRepository(
            session, workspace_id
        ).get_by_automation_execution(automation_execution_id)
        assert thread is not None
        assert thread.status == ThreadStatus.CANCELED.value
    await runner.shutdown()


async def _prepare_automation_workspace(
    postgres_engine,
) -> tuple[str, async_sessionmaker]:
    workspace_id = str(uuid4())
    session_factory = async_sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with postgres_engine.begin() as connection:
        await connection.run_sync(ThreadModel.metadata.create_all)
    async with session_factory() as session:
        await CapabilitiesStore().put(
            session,
            workspace_id,
            {
                "tools": [
                    {
                        "id": "claude",
                        "models": ["claude-opus-4-8"],
                        "default_model": "claude-opus-4-8",
                        "modes": ["execute"],
                        "default_mode": "execute",
                        "context_window": 200000,
                    }
                ],
                "default_tool": "claude",
            },
        )
        await session.commit()
    return workspace_id, session_factory


def _bind_workspace_claim(control, workspace_id: str, execution_id: str) -> None:
    original_claim = control.claim

    async def workspace_claim(**kwargs):
        claim = await original_claim(**kwargs)
        if claim is not None:
            claim.workspace_id = workspace_id
            claim.execution_id = execution_id
        return claim

    control.claim = workspace_claim


class SpawnThenHangAgent(CompletingAgentRunner):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.start_cancelled = False

    async def start(self, request, on_event, execution_id: str) -> None:
        self.requests.append(request)
        self.alive.add(execution_id)
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.start_cancelled = True
            raise


@pytest.mark.asyncio
async def test_timeout_during_agent_start_stops_persisted_execution_identity(
    postgres_engine,
) -> None:
    workspace_id, session_factory = await _prepare_automation_workspace(postgres_engine)
    automation_execution_id = str(uuid4())
    control = QueueControlPlane(1)
    _bind_workspace_claim(control, workspace_id, automation_execution_id)
    agent = SpawnThenHangAgent()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=session_factory,
        agent_runner=agent,
        execution_timeout_seconds=1.0,
        stop_grace_seconds=0.1,
    )

    await runner.start()
    await asyncio.wait_for(agent.started.wait(), timeout=2)
    for _ in range(3000):
        if control.completions:
            break
        await asyncio.sleep(0.001)

    assert agent.start_cancelled is True
    assert len(agent.stops) == 1
    assert agent.is_alive(agent.stops[0]) is False
    assert control.completions[0][1].error_code == "timeout"
    await runner.shutdown()


class PublicCancelAgent(CompletingAgentRunner):
    def __init__(self, terminal_event: str | None) -> None:
        super().__init__()
        self.terminal_event = terminal_event
        self.started = asyncio.Event()
        self.on_event = None

    async def start(self, request, on_event, execution_id: str) -> None:
        self.requests.append(request)
        self.on_event = on_event
        self.alive.add(execution_id)
        self.started.set()

    async def stop(self, execution_id: str) -> None:
        self.stops.append(execution_id)
        if self.terminal_event is not None:
            await self.on_event(AgentEvent(type=self.terminal_event))
        self.alive.discard(execution_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("terminal_event", "expected_thread", "expected_completion"),
    [
        (None, ThreadStatus.CANCELED.value, "cancelled"),
        ("complete", ThreadStatus.COMPLETE.value, "success"),
    ],
)
async def test_public_cancel_converges_real_thread_after_stop_confirmation(
    postgres_engine,
    terminal_event,
    expected_thread,
    expected_completion,
) -> None:
    workspace_id, session_factory = await _prepare_automation_workspace(postgres_engine)
    automation_execution_id = str(uuid4())
    control = QueueControlPlane(1)
    _bind_workspace_claim(control, workspace_id, automation_execution_id)
    agent = PublicCancelAgent(terminal_event)
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=session_factory,
        agent_runner=agent,
        stop_grace_seconds=5.0,
    )

    await runner.start()
    await asyncio.wait_for(agent.started.wait(), timeout=1)
    context = runner._active[automation_execution_id]
    await runner.cancel_execution(
        execution_id=automation_execution_id,
        runner_instance_id=context.runner_instance_id,
        claim_request_id=context.claim_request_id,
    )
    for _ in range(5000):
        if control.completions:
            break
        await asyncio.sleep(0.001)

    assert control.completions
    async with session_factory() as session:
        thread = await ThreadRepository(
            session, workspace_id
        ).get_by_automation_execution(automation_execution_id)
        assert thread is not None
        assert thread.status == expected_thread
    assert control.completions[0][1].status == expected_completion
    await runner.shutdown()


@pytest.mark.asyncio
async def test_infrastructure_failure_after_spawn_attempt_is_not_agent_failure() -> (
    None
):
    runner_id = uuid4()
    context = _ExecutionContext(
        runner_id,
        uuid4(),
        execution_id="execution-1",
        agent_execution_id="agent-1",
        phase=_ExecutionPhase.AGENT_TERMINAL,
    )
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=QueueControlPlane(0),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )

    payload = await runner._ordinary_failure(
        context, RuntimeError("canonical thread reload failed")
    )

    assert payload.error_code == "automation_execution_failed"


@pytest.mark.asyncio
async def test_missing_git_repository_has_stable_execution_error_code() -> None:
    runner_id = uuid4()
    context = _ExecutionContext(
        runner_id,
        uuid4(),
        execution_id="execution-1",
        phase=_ExecutionPhase.INFRASTRUCTURE,
    )
    runner = AutomationRunner(
        runner_instance_id=runner_id,
        workspace_id="workspace-1",
        control_plane=QueueControlPlane(0),
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )

    payload = await runner._ordinary_failure(
        context,
        VersionControlError(
            "Workspace is not a git repository",
            status_code=404,
            error_code="repository_not_initialized",
        ),
    )

    assert payload.error_code == "workspace_git_repository_required"


class HangingInfrastructureWorktree:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.cancelled = False

    async def ensure_for_job(self, **kwargs):
        self.entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@pytest.mark.asyncio
async def test_shutdown_cancels_hanging_pre_spawn_infrastructure_within_bound() -> None:
    worktree = HangingInfrastructureWorktree()
    control = QueueControlPlane(1)
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=worktree,
        session_factory=lambda: None,
        agent_runner=object(),
        stop_grace_seconds=0.01,
    )
    await runner.start()
    await asyncio.wait_for(worktree.entered.wait(), timeout=1)

    await asyncio.wait_for(runner.shutdown(), timeout=0.2)

    assert worktree.cancelled is True
    assert control.completions == []
    assert len(runner._active) == 1
    assert runner._semaphore._value == 2


@pytest.mark.asyncio
async def test_shutdown_cancels_completion_hang_even_when_interrupt_does_nothing(
    monkeypatch,
) -> None:
    class UninterruptibleCompletionControl(QueueControlPlane):
        def __init__(self):
            super().__init__(1)
            self.entered = asyncio.Event()
            self.cancelled = False

        async def complete(self, **kwargs):
            self.entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise

        def interrupt(self):
            return None

    control = UninterruptibleCompletionControl()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        stop_grace_seconds=0.01,
    )

    async def immediate_outcome(self, context):
        return self._completion(context, "success")

    monkeypatch.setattr(
        runner, "_run_with_deadline", MethodType(immediate_outcome, runner)
    )
    await runner.start()
    await asyncio.wait_for(control.entered.wait(), timeout=1)

    await asyncio.wait_for(runner.shutdown(), timeout=0.2)

    assert control.cancelled is True
    assert len(runner._active) == 1
    assert runner._semaphore._value == 2


@pytest.mark.asyncio
async def test_shutdown_waits_for_stop_failure_to_mark_fatal_without_completion(
    monkeypatch,
) -> None:
    fatal_reasons = []
    control = QueueControlPlane(1)
    agent = HangingStopRunner()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=control,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=agent,
        fatal_shutdown=fatal_reasons.append,
        stop_grace_seconds=0.01,
    )

    async def stuck_started_agent(self, context):
        context.agent_execution_id = "agent-1"
        context.thread_interface = RunnerThreadInterface(agent)
        context.phase = _ExecutionPhase.AGENT_RUNNING
        await asyncio.Event().wait()

    monkeypatch.setattr(
        runner, "_run_with_deadline", MethodType(stuck_started_agent, runner)
    )
    await runner.start()
    for _ in range(100):
        if runner._active:
            break
        await asyncio.sleep(0)

    await asyncio.wait_for(runner.shutdown(), timeout=0.2)

    assert runner.fatal_reason == "automation_agent_stop_failed:shutdown"
    assert fatal_reasons == ["automation_agent_stop_failed:shutdown"]
    assert control.completions == []
    assert len(runner._active) == 1
    assert runner._semaphore._value == 2


class SilentExitAgent(CompletingAgentRunner):
    async def start(self, request, on_event, execution_id: str) -> None:
        self.requests.append(request)
        self.alive.add(execution_id)
        self.alive.discard(execution_id)


@pytest.mark.asyncio
async def test_silent_agent_exit_converges_real_thread_to_terminal_error(
    postgres_engine,
) -> None:
    workspace_id, session_factory = await _prepare_automation_workspace(postgres_engine)
    automation_execution_id = str(uuid4())
    control = QueueControlPlane(1)
    _bind_workspace_claim(control, workspace_id, automation_execution_id)
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id=workspace_id,
        control_plane=control,
        worktree_service=ReadyWorktree(),
        session_factory=session_factory,
        agent_runner=SilentExitAgent(),
    )

    await runner.start()
    for _ in range(5000):
        if control.completions:
            break
        await asyncio.sleep(0.001)

    assert control.completions
    assert control.completions[0][1].status == "failed"
    assert control.completions[0][1].error_code == "agent_execution_failed"
    async with session_factory() as session:
        thread = await ThreadRepository(
            session, workspace_id
        ).get_by_automation_execution(automation_execution_id)
        assert thread is not None
        assert thread.status == ThreadStatus.ERROR.value
        assert thread.error_code == "agent_process_failed"
    await runner.shutdown()
