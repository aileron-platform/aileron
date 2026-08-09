"""PostgreSQL concurrency tests for Automation claim and terminal CAS."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, Lock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.execution import AutomationExecutionService
from app.modules.automation.models import CompletionRequest
from app.modules.automation.repository import (
    AutomationRepository,
    AutomationRepositoryError,
)

RUNTIME_INSTANCE_ID = "11111111-1111-4111-8111-111111111111"


def _actor(user_id: str) -> AuthorizationActor:
    return AuthorizationActor(user_id=user_id, platform_role="member")


@pytest.fixture()
def automation_database():
    schema = f"automation_claim_{uuid4().hex}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=10,
        max_overflow=5,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_workspace(engine, *, workspace_id: str = "workspace-1") -> str:
    user_id = f"user-{workspace_id}"
    with Session(engine) as session:
        session.add(
            db_models.User(
                id=user_id,
                username=user_id,
                display_name=user_id,
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=user_id,
                name=workspace_id,
                provisioner="kubernetes",
                runtime_internal_url="http://runtime.test",
                runtime_instance_id=RUNTIME_INSTANCE_ID,
            )
        )
        session.commit()
    return user_id


def _seed_job_and_execution(
    engine,
    *,
    job_id: str,
    execution_id: str,
    scheduled_for: datetime,
    workspace_id: str = "workspace-1",
    user_id: str = "user-workspace-1",
    trigger: str = "cron",
) -> None:
    with Session(engine) as session:
        if session.get(db_models.AutomationJob, job_id) is None:
            session.add(
                db_models.AutomationJob(
                    id=job_id,
                    workspace_id=workspace_id,
                    creator_user_id=user_id,
                    name=job_id,
                    prompt=f"prompt-{job_id}",
                    status="active",
                    trigger=trigger,
                    schedule="* * * * *" if trigger == "cron" else "",
                    exact=False,
                    agentic_tool="claude",
                    model="claude-sonnet",
                    agent_config={"permissionMode": "bypassPermissions"},
                    worktree_key=f"automation/{job_id}",
                    worktree_branch=f"automation/{job_id}",
                    notification_config={},
                    created_at=scheduled_for,
                    updated_at=scheduled_for,
                )
            )
            session.flush()
        session.add(
            db_models.AutomationExecution(
                id=execution_id,
                job_id=job_id,
                workspace_id=workspace_id,
                status="queued",
                trigger=trigger,
                scheduled_for=scheduled_for,
                queued_at=scheduled_for,
                principal_user_id_snapshot=user_id,
                prompt_snapshot=f"prompt-{job_id}",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={"permissionMode": "bypassPermissions"},
                worktree_key_snapshot=f"automation/{job_id}",
                created_at=scheduled_for,
                updated_at=scheduled_for,
            )
        )
        session.commit()


def _code(exc: Exception) -> str:
    return str(getattr(exc, "code", exc))


def test_claim_retry_returns_same_snapshot_and_current_cancel_intent(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=now,
    )
    runner_id = uuid4()
    request_id = uuid4()

    with Session(automation_database) as session:
        claimed = AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        assert claimed is not None
        immutable = (claimed.id, claimed.prompt_snapshot, claimed.started_at)

    with Session(automation_database) as session:
        execution = session.get(db_models.AutomationExecution, "execution-1")
        execution.cancel_requested_at = now + timedelta(seconds=1)
        session.commit()

    with Session(automation_database) as session:
        retry = AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        assert retry is not None
        assert (retry.id, retry.prompt_snapshot, retry.started_at) == immutable
        assert retry.cancel_requested_at is not None

        with pytest.raises(AutomationRepositoryError) as conflict:
            AutomationRepository(session).claim_execution(
                workspace_id="workspace-1",
                runner_instance_id=uuid4(),
                claim_request_id=request_id,
            )
        assert _code(conflict.value) == "claim_request_conflict"


@pytest.mark.parametrize("same_runner", [True, False])
def test_overlapping_same_claim_request_resolves_unique_winner(
    automation_database, same_runner: bool
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    for suffix in ["a", "b"]:
        _seed_job_and_execution(
            automation_database,
            job_id=f"job-{suffix}",
            execution_id=f"execution-{suffix}",
            scheduled_for=now,
        )
    claim_request_id = uuid4()
    shared_runner = uuid4()
    runners = [shared_runner, shared_runner if same_runner else uuid4()]
    receipt_barrier = Barrier(2)
    counter_lock = Lock()
    receipt_reads = 0

    def synchronize_initial_receipt_reads(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        nonlocal receipt_reads
        if (
            "SELECT" not in statement
            or "automation_executions.claim_request_id =" not in statement
        ):
            return
        with counter_lock:
            if receipt_reads >= 2:
                return
            receipt_reads += 1
        receipt_barrier.wait(timeout=5)

    event.listen(
        automation_database,
        "before_cursor_execute",
        synchronize_initial_receipt_reads,
    )

    def claim(runner_id):
        with Session(automation_database) as session:
            try:
                result = AutomationRepository(session).claim_execution(
                    workspace_id="workspace-1",
                    runner_instance_id=runner_id,
                    claim_request_id=claim_request_id,
                )
                return ("ok", result.id if result else None)
            except Exception as exc:
                return ("error", _code(exc))

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, runners))
    finally:
        event.remove(
            automation_database,
            "before_cursor_execute",
            synchronize_initial_receipt_reads,
        )

    if same_runner:
        assert results[0][0] == results[1][0] == "ok"
        assert results[0][1] == results[1][1]
    else:
        assert sorted(result[0] for result in results) == ["error", "ok"]
        assert ("error", "claim_request_conflict") in results
    with Session(automation_database) as session:
        winners = session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.workspace_id == "workspace-1",
                db_models.AutomationExecution.claim_request_id == str(claim_request_id),
            )
        ).all()
        assert len(winners) == 1


def test_no_work_does_not_persist_receipt_and_same_request_can_later_claim(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    runner_id = uuid4()
    request_id = uuid4()
    with Session(automation_database) as session:
        assert (
            AutomationRepository(session).claim_execution(
                workspace_id="workspace-1",
                runner_instance_id=runner_id,
                claim_request_id=request_id,
            )
            is None
        )
        assert (
            session.scalar(
                select(db_models.AutomationExecution).where(
                    db_models.AutomationExecution.claim_request_id == str(request_id)
                )
            )
            is None
        )

    _seed_job_and_execution(
        automation_database,
        job_id="job-later",
        execution_id="execution-later",
        scheduled_for=datetime.now(timezone.utc),
    )
    with Session(automation_database) as session:
        claimed = AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        assert claimed is not None
        assert claimed.id == "execution-later"


def test_claim_orders_job_heads_globally_and_never_skips_locked_job_head(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    # Reverse insertion plus same-time id tie-break proves deterministic global order.
    for job_id, execution_id, scheduled in [
        ("job-c", "execution-c", now + timedelta(seconds=2)),
        ("job-b", "execution-b", now),
        ("job-a", "execution-a", now),
    ]:
        _seed_job_and_execution(
            automation_database,
            job_id=job_id,
            execution_id=execution_id,
            scheduled_for=scheduled,
        )
    _seed_job_and_execution(
        automation_database,
        job_id="job-a",
        execution_id="execution-a-second",
        scheduled_for=now + timedelta(seconds=3),
    )

    locked = Event()
    release = Event()

    def hold_oldest_job() -> None:
        with Session(automation_database) as session:
            session.execute(
                select(db_models.AutomationJob)
                .where(db_models.AutomationJob.id == "job-a")
                .with_for_update()
            ).scalar_one()
            locked.set()
            release.wait(timeout=5)
            session.rollback()

    with ThreadPoolExecutor(max_workers=2) as executor:
        holder = executor.submit(hold_oldest_job)
        assert locked.wait(timeout=5)
        with Session(automation_database) as session:
            claimed = AutomationRepository(session).claim_execution(
                workspace_id="workspace-1",
                runner_instance_id=uuid4(),
                claim_request_id=uuid4(),
            )
            assert claimed is not None
            assert claimed.id == "execution-b"
        release.set()
        holder.result(timeout=5)

    with Session(automation_database) as session:
        claimed = AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=uuid4(),
            claim_request_id=uuid4(),
        )
        assert claimed is not None
        assert claimed.id == "execution-a"
        assert (
            session.get(db_models.AutomationExecution, "execution-a-second").status
            == "queued"
        )


def test_two_claims_do_not_create_two_running_for_one_job(automation_database) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    for execution_id, offset in [("execution-1", 0), ("execution-2", 1)]:
        _seed_job_and_execution(
            automation_database,
            job_id="job-1",
            execution_id=execution_id,
            scheduled_for=now + timedelta(seconds=offset),
        )
    barrier = Barrier(2)

    def claim() -> str | None:
        with Session(automation_database) as session:
            barrier.wait()
            result = AutomationRepository(session).claim_execution(
                workspace_id="workspace-1",
                runner_instance_id=uuid4(),
                claim_request_id=uuid4(),
            )
            return result.id if result else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: claim(), range(2)))
    assert sum(result is not None for result in results) == 1
    with Session(automation_database) as session:
        running = session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.status == "running"
            )
        ).all()
        assert len(running) == 1


@pytest.mark.parametrize("wrong_field", ["runner", "request", "terminal_owner"])
def test_completion_checks_ownership_before_terminal_idempotency(
    automation_database, wrong_field: str
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=now,
    )
    owner_runner = uuid4()
    owner_request = uuid4()
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=owner_runner,
            claim_request_id=owner_request,
        )
        if wrong_field == "terminal_owner":
            repository.complete_execution(
                execution_id="execution-1",
                runner_instance_id=owner_runner,
                claim_request_id=owner_request,
                status="success",
                error_code=None,
                error_message=None,
            )

    with Session(automation_database) as session:
        with pytest.raises(AutomationRepositoryError) as error:
            AutomationRepository(session).complete_execution(
                execution_id="execution-1",
                runner_instance_id=(
                    uuid4() if wrong_field != "request" else owner_runner
                ),
                claim_request_id=(
                    uuid4() if wrong_field == "request" else owner_request
                ),
                status="success",
                error_code=None,
                error_message=None,
            )
        assert _code(error.value) == "execution_not_owned"


def test_old_owner_cannot_idempotently_complete_reconcile_terminal(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=datetime.now(timezone.utc),
    )
    runner_id = uuid4()
    request_id = uuid4()
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        repository.reconcile_restart(
            workspace_id="workspace-1", new_runner_instance_id=uuid4()
        )

    with Session(automation_database) as session:
        with pytest.raises(AutomationRepositoryError) as error:
            AutomationRepository(session).complete_execution(
                execution_id="execution-1",
                runner_instance_id=runner_id,
                claim_request_id=request_id,
                status="failed",
                error_code="runner_restarted",
                error_message=None,
            )
        assert _code(error.value) == "execution_already_terminal"


def test_runtime_completion_cannot_create_runner_restarted_terminal(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=datetime.now(timezone.utc),
    )
    runner_id = uuid4()
    request_id = uuid4()
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        with pytest.raises(AutomationRepositoryError) as error:
            repository.complete_execution(
                execution_id="execution-1",
                runner_instance_id=runner_id,
                claim_request_id=request_id,
                status="failed",
                error_code="runner_restarted",
                error_message=None,
            )
        assert _code(error.value) == "execution_invalid_transition"


def test_invalid_principal_convergence_commits_and_claims_next_candidate(
    automation_database,
) -> None:
    owner_id = _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    invalid_user_id = "invalid-principal"
    with Session(automation_database) as session:
        session.add(
            db_models.User(
                id=invalid_user_id,
                username=invalid_user_id,
                display_name=invalid_user_id,
                is_active=False,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.WorkspaceShare(
                id="invalid-principal-share",
                workspace_id="workspace-1",
                target_type="user",
                target_id=invalid_user_id,
                granted_by_user_id=owner_id,
                role="manager",
            )
        )
        session.commit()
    _seed_job_and_execution(
        automation_database,
        job_id="job-invalid",
        execution_id="execution-invalid",
        scheduled_for=now,
        user_id=invalid_user_id,
    )
    _seed_job_and_execution(
        automation_database,
        job_id="job-valid",
        execution_id="execution-valid",
        scheduled_for=now + timedelta(seconds=1),
    )

    with Session(automation_database) as session:
        claimed = AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=uuid4(),
            claim_request_id=uuid4(),
        )
        assert claimed is not None
        assert claimed.id == "execution-valid"

    with Session(automation_database) as session:
        invalid_job = session.get(db_models.AutomationJob, "job-invalid")
        invalid_execution = session.get(
            db_models.AutomationExecution, "execution-invalid"
        )
        assert invalid_job.status == "paused"
        assert invalid_job.next_run_at is None
        assert invalid_execution.status == "cancelled"
        assert invalid_execution.error_code == "authorization_revoked"


@pytest.mark.parametrize("operation", ["complete", "reconcile"])
def test_notification_status_persistence_failure_returns_canonical_terminal(
    automation_database, monkeypatch, operation: str
) -> None:
    _seed_workspace(automation_database)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=datetime.now(timezone.utc),
    )
    runner_id = uuid4()
    request_id = uuid4()
    notifications = []

    class Notifications:
        def deliver_terminal(self, *, execution, notification_config):
            notifications.append((execution.status, notification_config))
            return "delivered"

    with Session(automation_database) as session:
        job = session.get(db_models.AutomationJob, "job-1")
        job.notification_config = {
            "delivery_webhook_url": "https://success.example/hook",
            "failure_destination": "https://failure.example/hook",
        }
        session.commit()

    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )

        def fail_status_update(*args, **kwargs):
            raise RuntimeError("notification status unavailable")

        monkeypatch.setattr(
            repository, "update_notification_status", fail_status_update
        )
        service = AutomationExecutionService(repository, notifications=Notifications())
        if operation == "complete":
            result = service.complete(
                execution_id="execution-1",
                payload=CompletionRequest(
                    runnerInstanceId=runner_id,
                    claimRequestId=request_id,
                    status="success",
                ),
            )
            assert result.status == "success"
        else:
            results = service.reconcile_restart(
                workspace_id="workspace-1",
                new_runner_instance_id=uuid4(),
            )
            assert [(item.status, item.error_code) for item in results] == [
                ("failed", "runner_restarted")
            ]

    with Session(automation_database) as session:
        stored = session.get(db_models.AutomationExecution, "execution-1")
        assert stored.status == ("success" if operation == "complete" else "failed")
        assert stored.notification_status is None
    assert notifications


def test_completion_sanitizes_sensitive_error_message_and_truncates(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=datetime.now(timezone.utc),
    )
    runner_id = uuid4()
    request_id = uuid4()
    raw_message = (
        "token=token-value credential=credential-value "
        "api_key=api-key-value password=password-value "
        "Bearer bearer-value\n"
        "prompt=private user prompt\n" + ("diagnostic " * 300)
    )
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        result = AutomationExecutionService(repository).complete(
            execution_id="execution-1",
            payload=CompletionRequest(
                runnerInstanceId=runner_id,
                claimRequestId=request_id,
                status="failed",
                errorCode="agent_failed",
                errorMessage=raw_message,
            ),
        )
        assert result.status == "failed"

    with Session(automation_database) as session:
        stored = session.get(db_models.AutomationExecution, "execution-1")
        assert stored.error_message is not None
        assert len(stored.error_message) <= 1024
        assert "[REDACTED]" in stored.error_message
        for secret in [
            "token-value",
            "credential-value",
            "api-key-value",
            "password-value",
            "bearer-value",
            "private user prompt",
        ]:
            assert secret not in stored.error_message


def test_cancel_completion_and_reconcile_follow_commit_order(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    for suffix in ["cancel", "complete", "reconcile"]:
        _seed_job_and_execution(
            automation_database,
            job_id=f"job-{suffix}",
            execution_id=f"execution-{suffix}",
            scheduled_for=now,
        )
    runner = uuid4()
    claims: dict[str, UUID] = {}
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        for suffix in ["cancel", "complete", "reconcile"]:
            request_id = uuid4()
            claims[suffix] = request_id
            repository.claim_execution(
                workspace_id="workspace-1",
                runner_instance_id=runner,
                claim_request_id=request_id,
            )

    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.cancel_execution(
            execution_id="execution-cancel", actor=_actor("user-workspace-1")
        )
        with pytest.raises(AutomationRepositoryError) as error:
            repository.complete_execution(
                execution_id="execution-cancel",
                runner_instance_id=runner,
                claim_request_id=claims["cancel"],
                status="success",
                error_code=None,
                error_message=None,
            )
        assert _code(error.value) == "execution_cancel_requested"
        cancelled = repository.complete_execution(
            execution_id="execution-cancel",
            runner_instance_id=runner,
            claim_request_id=claims["cancel"],
            status="cancelled",
            error_code=None,
            error_message=None,
        )
        assert cancelled.status == "cancelled"

    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        completed = repository.complete_execution(
            execution_id="execution-complete",
            runner_instance_id=runner,
            claim_request_id=claims["complete"],
            status="success",
            error_code=None,
            error_message=None,
        )
        assert (
            repository.cancel_execution(
                execution_id="execution-complete",
                actor=_actor("user-workspace-1"),
            ).status
            == completed.status
        )

    with Session(automation_database) as session:
        reconciled = AutomationRepository(session).reconcile_restart(
            workspace_id="workspace-1", new_runner_instance_id=uuid4()
        )
        assert [item.id for item in reconciled] == ["execution-reconcile"]
        assert reconciled[0].status == "failed"
        assert reconciled[0].error_code == "runner_restarted"


def test_queue_position_is_one_based_within_each_job(automation_database) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    for execution_id, offset in [("execution-2", 2), ("execution-1", 1)]:
        _seed_job_and_execution(
            automation_database,
            job_id="job-1",
            execution_id=execution_id,
            scheduled_for=now + timedelta(seconds=offset),
        )
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        assert repository.queue_position("execution-1") == 1
        assert repository.queue_position("execution-2") == 2


def test_running_public_cancel_commits_intent_before_runtime_rpc_failure(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=now,
    )
    runner_id = uuid4()
    request_id = uuid4()
    calls = []

    class RuntimeClient:
        def cancel_execution(self, **kwargs):
            with Session(automation_database) as verification:
                stored = verification.get(db_models.AutomationExecution, "execution-1")
                assert stored.cancel_requested_at is not None
            calls.append(kwargs)
            return False

    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        repository.claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
        result = AutomationExecutionService(
            repository, runtime_client=RuntimeClient()
        ).cancel(execution_id="execution-1", actor=_actor("user-workspace-1"))
        assert result.status == "running"
        assert result.cancel_requested_at is not None
    assert calls == [
        {
            "runtime_url": "http://runtime.test",
            "workspace_id": "workspace-1",
            "runtime_instance_id": RUNTIME_INSTANCE_ID,
            "execution_id": "execution-1",
            "runner_instance_id": str(runner_id),
            "claim_request_id": str(request_id),
        }
    ]


def test_cancel_and_completion_race_is_resolved_by_commit_order(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=now,
    )
    runner_id = uuid4()
    request_id = uuid4()
    with Session(automation_database) as session:
        AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
    barrier = Barrier(2)

    def cancel():
        with Session(automation_database) as session:
            barrier.wait()
            try:
                result = AutomationRepository(session).cancel_execution(
                    execution_id="execution-1",
                    actor=_actor("user-workspace-1"),
                )
                return ("ok", result.status)
            except Exception as exc:
                return ("error", _code(exc))

    def complete():
        with Session(automation_database) as session:
            barrier.wait()
            try:
                result = AutomationRepository(session).complete_execution(
                    execution_id="execution-1",
                    runner_instance_id=runner_id,
                    claim_request_id=request_id,
                    status="success",
                    error_code=None,
                    error_message=None,
                )
                return ("ok", result.status)
            except Exception as exc:
                return ("error", _code(exc))

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancel_future = executor.submit(cancel)
        complete_future = executor.submit(complete)
        cancel_result = cancel_future.result(timeout=10)
        complete_result = complete_future.result(timeout=10)

    assert (cancel_result, complete_result) in {
        (("ok", "running"), ("error", "execution_cancel_requested")),
        (("ok", "success"), ("ok", "success")),
    }


def test_reconcile_and_completion_race_never_overwrites_terminal(
    automation_database,
) -> None:
    _seed_workspace(automation_database)
    now = datetime.now(timezone.utc)
    _seed_job_and_execution(
        automation_database,
        job_id="job-1",
        execution_id="execution-1",
        scheduled_for=now,
    )
    runner_id = uuid4()
    request_id = uuid4()
    with Session(automation_database) as session:
        AutomationRepository(session).claim_execution(
            workspace_id="workspace-1",
            runner_instance_id=runner_id,
            claim_request_id=request_id,
        )
    barrier = Barrier(2)

    def reconcile():
        with Session(automation_database) as session:
            barrier.wait()
            rows = AutomationRepository(session).reconcile_restart(
                workspace_id="workspace-1",
                new_runner_instance_id=uuid4(),
            )
            return [(row.status, row.error_code) for row in rows]

    def complete():
        with Session(automation_database) as session:
            barrier.wait()
            try:
                result = AutomationRepository(session).complete_execution(
                    execution_id="execution-1",
                    runner_instance_id=runner_id,
                    claim_request_id=request_id,
                    status="success",
                    error_code=None,
                    error_message=None,
                )
                return ("ok", result.status)
            except Exception as exc:
                return ("error", _code(exc))

    with ThreadPoolExecutor(max_workers=2) as executor:
        reconcile_future = executor.submit(reconcile)
        complete_future = executor.submit(complete)
        reconcile_result = reconcile_future.result(timeout=10)
        complete_result = complete_future.result(timeout=10)

    if reconcile_result:
        assert reconcile_result == [("failed", "runner_restarted")]
        assert complete_result == ("error", "execution_already_terminal")
    else:
        assert complete_result == ("ok", "success")
    with Session(automation_database) as session:
        stored = session.get(db_models.AutomationExecution, "execution-1")
        assert (stored.status, stored.error_code) in {
            ("failed", "runner_restarted"),
            ("success", None),
        }
