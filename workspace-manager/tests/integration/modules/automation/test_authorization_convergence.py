"""Authorization-revocation convergence for Automation jobs and executions."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.execution import (
    AutomationExecutionService,
    AutomationWorkspaceDeletionError,
)
from app.modules.automation.repository import AutomationRepository
from app.modules.automation.runtime_client import RuntimeAutomationClient
from app.modules.automation.scheduler import AutomationScheduler
from app.modules.identity.admin import UserAdminService
from app.modules.identity.admin_models import AdminUserRoleRequest
from app.modules.identity.groups import UserGroupService
from app.modules.identity.snapshot_sync import UserSnapshotSyncService
from app.modules.workspace.catalog import WorkspaceService
from app.modules.workspace.models import WorkspaceShareUpdateRequest

WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture()
def authorization_database():
    schema = f"automation_authorization_{uuid4().hex}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def successful_runtime_cancel(monkeypatch) -> None:
    monkeypatch.setattr(
        RuntimeAutomationClient,
        "cancel_execution",
        lambda self, **kwargs: True,
    )


def _seed_principal_state(engine, *, platform_role: str = "member") -> None:
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        principal = db_models.User(
            id="principal",
            username="principal",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role=platform_role,
            role_status="valid",
        )
        workspace = db_models.Workspace(
            id=WORKSPACE_ID,
            owner_id=principal.id,
            name="Workspace",
            provisioner="kubernetes",
            runtime_internal_url="http://runtime.internal",
            runtime_instance_id=str(uuid4()),
        )
        session.add_all([principal, workspace])
        for status in ("active", "paused", "completed"):
            job_id = f"job-{status}"
            session.add(
                db_models.AutomationJob(
                    id=job_id,
                    workspace_id=workspace.id,
                    creator_user_id=principal.id,
                    name=job_id,
                    prompt="run",
                    status=status,
                    trigger="at" if status == "completed" else "every",
                    schedule=(
                        (now - timedelta(minutes=5)).isoformat()
                        if status == "completed"
                        else "1m"
                    ),
                    exact=True,
                    agentic_tool="claude",
                    model="claude-sonnet",
                    agent_config={"mode": "execute"},
                    worktree_key=f"automation/{job_id}",
                    worktree_branch=f"automation/{job_id}",
                    notification_config={},
                    next_run_at=(
                        now + timedelta(minutes=1) if status == "active" else None
                    ),
                )
            )
            for execution_status in ("queued", "running"):
                execution = db_models.AutomationExecution(
                    id=f"{job_id}-{execution_status}",
                    job_id=job_id,
                    workspace_id=workspace.id,
                    status=execution_status,
                    trigger="manual",
                    scheduled_for=now,
                    queued_at=now,
                    principal_user_id_snapshot=principal.id,
                    prompt_snapshot="run",
                    agentic_tool_snapshot="claude",
                    model_snapshot="claude-sonnet",
                    agent_config_snapshot={"mode": "execute"},
                    worktree_key_snapshot=f"automation/{job_id}",
                )
                if execution_status == "running":
                    execution.started_at = now
                    execution.runner_instance_id = str(uuid4())
                    execution.claim_request_id = str(uuid4())
                session.add(execution)
        session.commit()


def test_convergence_pauses_only_active_jobs_and_cancels_all_nonterminal_executions(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)

    with Session(authorization_database) as session:
        cancellations = AutomationExecutionService(
            AutomationRepository(session)
        ).converge_principal_authorization(principal_user_id="principal")

    assert {item.execution_id for item in cancellations} == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }
    with Session(authorization_database) as session:
        jobs = {
            job.id: job
            for job in session.scalars(select(db_models.AutomationJob)).all()
        }
        assert jobs["job-active"].status == "paused"
        assert jobs["job-active"].next_run_at is None
        assert jobs["job-paused"].status == "paused"
        assert jobs["job-completed"].status == "completed"
        executions = {
            execution.id: execution
            for execution in session.scalars(
                select(db_models.AutomationExecution)
            ).all()
        }
        for execution_id, execution in executions.items():
            if execution_id.endswith("-queued"):
                assert execution.status == "cancelled"
                assert execution.error_code == "authorization_revoked"
                assert execution.finished_at is not None
            else:
                assert execution.status == "running"
                assert execution.cancel_requested_at is not None


def test_workspace_deletion_convergence_cancels_and_confirms_all_executions(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database)
    cancel_calls: list[str] = []

    def cancel_and_complete(_self, **kwargs):
        execution_id = kwargs["execution_id"]
        cancel_calls.append(execution_id)
        with Session(authorization_database) as runtime_session:
            execution = runtime_session.get(db_models.AutomationExecution, execution_id)
            assert execution is not None
            assert execution.status == "running"
            execution.status = "cancelled"
            execution.finished_at = datetime.now(timezone.utc)
            execution.updated_at = execution.finished_at
            runtime_session.commit()
        return True

    monkeypatch.setattr(
        RuntimeAutomationClient, "cancel_execution", cancel_and_complete
    )

    with Session(authorization_database) as session:
        result = AutomationExecutionService(
            AutomationRepository(session),
        ).converge_workspace_deletion(
            workspace_id=WORKSPACE_ID,
            timeout_seconds=0,
            poll_interval_seconds=0,
        )

    assert result.workspace_id == WORKSPACE_ID
    assert result.phase == "cancelling_automations"
    assert set(cancel_calls) == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }
    with Session(authorization_database) as session:
        executions = {
            execution.id: execution
            for execution in session.scalars(
                select(db_models.AutomationExecution).where(
                    db_models.AutomationExecution.workspace_id == WORKSPACE_ID
                )
            ).all()
        }
        assert all(execution.status == "cancelled" for execution in executions.values())
        assert executions["job-active-queued"].error_code == "authorization_revoked"


def test_workspace_deletion_convergence_fails_closed_when_cancel_is_unconfirmed(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    cancel_calls: list[str] = []

    class UnconfirmedRuntimeClient:
        def cancel_execution(self, **kwargs):
            cancel_calls.append(kwargs["execution_id"])
            return False

    with Session(authorization_database) as session:
        service = AutomationExecutionService(
            AutomationRepository(session),
            runtime_client=UnconfirmedRuntimeClient(),
        )
        with pytest.raises(AutomationWorkspaceDeletionError) as error:
            service.converge_workspace_deletion(
                workspace_id=WORKSPACE_ID,
                timeout_seconds=0,
                poll_interval_seconds=0,
            )

    assert cancel_calls == ["job-active-running"]
    assert error.value.code == "WORKSPACE_AUTOMATION_CANCELLATION_UNCONFIRMED"
    assert error.value.phase == "cancelling_automations"
    assert error.value.execution_id == "job-active-running"
    with Session(authorization_database) as session:
        queued = session.get(db_models.AutomationExecution, "job-active-queued")
        running = session.get(db_models.AutomationExecution, "job-active-running")
        assert queued.status == "cancelled"
        assert running.status == "running"
        assert running.cancel_requested_at is not None


def test_workspace_deletion_convergence_fails_closed_without_terminal_confirmation(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    cancel_calls: list[str] = []

    class NonTerminalRuntimeClient:
        def cancel_execution(self, **kwargs):
            cancel_calls.append(kwargs["execution_id"])
            with Session(authorization_database) as verification:
                execution = verification.get(
                    db_models.AutomationExecution,
                    kwargs["execution_id"],
                )
                assert execution.cancel_requested_at is not None
                assert execution.status == "running"
            return True

    with Session(authorization_database) as session:
        service = AutomationExecutionService(
            AutomationRepository(session),
            runtime_client=NonTerminalRuntimeClient(),
        )
        with pytest.raises(AutomationWorkspaceDeletionError) as error:
            service.converge_workspace_deletion(
                workspace_id=WORKSPACE_ID,
                timeout_seconds=0,
                poll_interval_seconds=0,
            )

    assert cancel_calls == [
        "job-active-running",
        "job-completed-running",
        "job-paused-running",
    ]
    assert error.value.code == "WORKSPACE_AUTOMATION_CANCELLATION_UNCONFIRMED"
    assert error.value.phase == "cancelling_automations"
    assert error.value.execution_id == "job-active-running"
    with Session(authorization_database) as session:
        execution = session.get(
            db_models.AutomationExecution,
            "job-active-running",
        )
        assert execution.status == "running"
        assert execution.cancel_requested_at is not None


def test_workspace_deletion_convergence_in_transaction_does_not_commit_outer_changes(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)

    with Session(authorization_database) as session:
        plan = AutomationRepository(session).converge_workspace_deletion_in_transaction(
            workspace_id=WORKSPACE_ID
        )
        assert plan.workspace_id == WORKSPACE_ID
        assert set(plan.queued_execution_ids) == {
            "job-active-queued",
            "job-completed-queued",
            "job-paused-queued",
        }
        with Session(authorization_database) as verification:
            assert (
                verification.get(db_models.AutomationJob, "job-active").status
                == "active"
            )
            assert (
                verification.get(
                    db_models.AutomationExecution,
                    "job-active-queued",
                ).status
                == "queued"
            )
        session.rollback()

    with Session(authorization_database) as verification:
        assert (
            verification.get(db_models.AutomationJob, "job-active").status == "active"
        )
        assert (
            verification.get(
                db_models.AutomationExecution,
                "job-active-running",
            ).cancel_requested_at
            is None
        )


def test_workspace_deletion_convergence_is_idempotent_for_terminal_executions(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database)
    terminal_at = datetime.now(timezone.utc)
    with Session(authorization_database) as session:
        execution = session.get(
            db_models.AutomationExecution,
            "job-completed-queued",
        )
        execution.status = "success"
        execution.error_code = "already_terminal"
        execution.finished_at = terminal_at
        execution.updated_at = terminal_at
        session.commit()

    def cancel_and_complete(_self, **kwargs):
        with Session(authorization_database) as runtime_session:
            execution = runtime_session.get(
                db_models.AutomationExecution,
                kwargs["execution_id"],
            )
            execution.status = "cancelled"
            execution.finished_at = datetime.now(timezone.utc)
            execution.updated_at = execution.finished_at
            runtime_session.commit()
        return True

    monkeypatch.setattr(
        RuntimeAutomationClient, "cancel_execution", cancel_and_complete
    )
    with Session(authorization_database) as session:
        AutomationExecutionService(
            AutomationRepository(session),
        ).converge_workspace_deletion(
            workspace_id=WORKSPACE_ID,
            timeout_seconds=0,
            poll_interval_seconds=0,
        )

    def unexpected_cancel(_self, **kwargs):
        raise AssertionError(f"terminal execution was cancelled: {kwargs}")

    monkeypatch.setattr(RuntimeAutomationClient, "cancel_execution", unexpected_cancel)
    with Session(authorization_database) as session:
        result = AutomationExecutionService(
            AutomationRepository(session),
        ).converge_workspace_deletion(
            workspace_id=WORKSPACE_ID,
            timeout_seconds=0,
            poll_interval_seconds=0,
        )

    assert result.phase == "cancelling_automations"
    with Session(authorization_database) as session:
        execution = session.get(
            db_models.AutomationExecution,
            "job-completed-queued",
        )
        assert execution.status == "success"
        assert execution.error_code == "already_terminal"
        assert execution.finished_at == terminal_at


def test_transaction_owned_convergence_does_not_commit_outer_transaction(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)

    with Session(authorization_database) as session:
        cancellations = AutomationRepository(
            session
        ).converge_principal_authorization_in_transaction(
            principal_user_id="principal",
            workspace_id=WORKSPACE_ID,
        )
        assert {item.execution_id for item in cancellations} == {
            "job-active-running",
            "job-paused-running",
            "job-completed-running",
        }
        assert session.get(db_models.AutomationJob, "job-active").status == "paused"

        with Session(authorization_database) as verification:
            assert (
                verification.get(db_models.AutomationJob, "job-active").status
                == "active"
            )
            assert (
                verification.get(
                    db_models.AutomationExecution,
                    "job-active-running",
                ).cancel_requested_at
                is None
            )

        session.rollback()

    with Session(authorization_database) as verification:
        assert (
            verification.get(db_models.AutomationJob, "job-active").status == "active"
        )
        assert (
            verification.get(
                db_models.AutomationExecution,
                "job-active-running",
            ).cancel_requested_at
            is None
        )


def test_runtime_rpc_failure_preserves_committed_cancel_intent(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)

    class FailingRuntimeClient:
        def cancel_execution(self, **kwargs):
            raise RuntimeError("runtime unavailable")

    with Session(authorization_database) as session:
        service = AutomationExecutionService(
            AutomationRepository(session), runtime_client=FailingRuntimeClient()
        )
        cancellations = service.converge_principal_authorization(
            principal_user_id="principal"
        )
        service.cancel_running_after_commit(cancellations)

    with Session(authorization_database) as session:
        execution = session.get(db_models.AutomationExecution, "job-active-running")
        assert execution.status == "running"
        assert execution.cancel_requested_at is not None


def test_runtime_rpc_false_preserves_committed_cancel_intent(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    calls = []

    class FalseRuntimeClient:
        def cancel_execution(self, **kwargs):
            calls.append(kwargs["execution_id"])
            return False

    with Session(authorization_database) as session:
        service = AutomationExecutionService(
            AutomationRepository(session), runtime_client=FalseRuntimeClient()
        )
        cancellations = service.converge_principal_authorization(
            principal_user_id="principal"
        )
        service.cancel_running_after_commit(cancellations)

    assert set(calls) == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }
    with Session(authorization_database) as session:
        assert (
            session.get(
                db_models.AutomationExecution, "job-active-running"
            ).cancel_requested_at
            is not None
        )


def test_claim_integrity_error_rollback_discards_uncommitted_cancellations(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    calls = []

    class RuntimeClient:
        def cancel_execution(self, **kwargs):
            calls.append(kwargs)
            return True

    with Session(authorization_database) as session:
        session.get(db_models.User, "principal").is_active = False
        session.delete(session.get(db_models.AutomationExecution, "job-active-running"))
        session.commit()
        repository = AutomationRepository(session)
        service = AutomationExecutionService(repository, runtime_client=RuntimeClient())
        original_commit = session.commit

        def fail_commit() -> None:
            raise IntegrityError("forced claim recovery", {}, RuntimeError("forced"))

        session.commit = fail_commit
        with pytest.raises(IntegrityError):
            service.claim(
                workspace_id=WORKSPACE_ID,
                runner_instance_id=uuid4(),
                claim_request_id=uuid4(),
            )
        session.commit = original_commit
        service.cancel_running_after_commit(
            repository.take_committed_running_cancellations()
        )

    assert calls == []
    with Session(authorization_database) as session:
        executions = session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.principal_user_id_snapshot == "principal"
            )
        ).all()
        assert all(item.cancel_requested_at is None for item in executions)
        assert all(item.status in {"queued", "running"} for item in executions)


def test_scheduler_delivers_runtime_cancellation_only_after_commit(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database)
    due = datetime.now(timezone.utc) - timedelta(minutes=1)
    with Session(authorization_database) as session:
        session.get(db_models.User, "principal").is_active = False
        session.get(db_models.AutomationJob, "job-active").next_run_at = due
        session.commit()
    calls = []

    def record_cancel(_self, **kwargs):
        with Session(authorization_database) as verification:
            stored = verification.get(
                db_models.AutomationExecution, kwargs["execution_id"]
            )
            assert stored.cancel_requested_at is not None
        calls.append(kwargs["execution_id"])
        return True

    monkeypatch.setattr(RuntimeAutomationClient, "cancel_execution", record_cancel)
    factory = sessionmaker(bind=authorization_database, autoflush=False)

    assert AutomationScheduler(session_factory=factory).run_once() == 0
    assert set(calls) == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }


def test_claim_converges_invalid_then_claims_valid_and_delivers_after_commit(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    now = datetime.now(timezone.utc)
    with Session(authorization_database) as session:
        principal = session.get(db_models.User, "principal")
        principal.is_active = False
        session.delete(session.get(db_models.AutomationExecution, "job-active-running"))
        valid = db_models.User(
            id="valid-principal",
            username="valid-principal",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        session.add(valid)
        session.add(
            db_models.WorkspaceShare(
                id="valid-share",
                workspace_id=WORKSPACE_ID,
                target_type="user",
                target_id=valid.id,
                role="manager",
                granted_by_user_id="principal",
            )
        )
        session.add(
            db_models.AutomationJob(
                id="job-valid",
                workspace_id=WORKSPACE_ID,
                creator_user_id=valid.id,
                name="job-valid",
                prompt="valid run",
                status="active",
                trigger="every",
                schedule="1m",
                exact=True,
                agentic_tool="claude",
                model="claude-sonnet",
                agent_config={"mode": "execute"},
                worktree_key="automation/job-valid",
                worktree_branch="automation/job-valid",
                notification_config={},
            )
        )
        session.add(
            db_models.AutomationExecution(
                id="execution-valid",
                job_id="job-valid",
                workspace_id=WORKSPACE_ID,
                status="queued",
                trigger="manual",
                scheduled_for=now + timedelta(minutes=1),
                queued_at=now,
                principal_user_id_snapshot=valid.id,
                prompt_snapshot="valid run",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={"mode": "execute"},
                worktree_key_snapshot="automation/job-valid",
            )
        )
        session.commit()
    calls = []

    class RuntimeClient:
        def cancel_execution(self, **kwargs):
            with Session(authorization_database) as verification:
                stored = verification.get(
                    db_models.AutomationExecution, kwargs["execution_id"]
                )
                assert stored.cancel_requested_at is not None
            calls.append(kwargs["execution_id"])
            return True

    with Session(authorization_database) as session:
        claimed = AutomationExecutionService(
            AutomationRepository(session), runtime_client=RuntimeClient()
        ).claim(
            workspace_id=WORKSPACE_ID,
            runner_instance_id=uuid4(),
            claim_request_id=uuid4(),
        )

    assert claimed is not None
    assert claimed.execution_id == "execution-valid"
    assert set(calls) == {"job-paused-running", "job-completed-running"}


def test_reverse_scheduler_candidates_do_not_deadlock_principal_convergence(
    authorization_database,
) -> None:
    now = datetime.now(timezone.utc)
    with Session(authorization_database) as session:
        user = db_models.User(
            id="principal",
            username="principal",
            is_active=False,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        workspace = db_models.Workspace(
            id=WORKSPACE_ID,
            owner_id=user.id,
            name="Workspace",
            provisioner="kubernetes",
        )
        session.add_all([user, workspace])
        for job_id in ("job-a", "job-b"):
            session.add(
                db_models.AutomationJob(
                    id=job_id,
                    workspace_id=workspace.id,
                    creator_user_id=user.id,
                    name=job_id,
                    prompt="run",
                    status="active",
                    trigger="every",
                    schedule="1m",
                    exact=True,
                    agentic_tool="claude",
                    model="claude-sonnet",
                    agent_config={"mode": "execute"},
                    worktree_key=f"automation/{job_id}",
                    worktree_branch=f"automation/{job_id}",
                    notification_config={},
                    next_run_at=now,
                )
            )
        session.commit()

    barrier = Barrier(2)
    counter_lock = Lock()
    candidate_reads = 0

    def synchronize_candidate_reads(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        nonlocal candidate_reads
        if (
            "automation_jobs.id =" not in statement
            or "SELECT" not in statement
            or candidate_reads >= 2
        ):
            return
        with counter_lock:
            if candidate_reads >= 2:
                return
            candidate_reads += 1
        barrier.wait(timeout=5)

    event.listen(
        authorization_database, "after_cursor_execute", synchronize_candidate_reads
    )

    def enqueue(job_id: str):
        with Session(authorization_database) as session:
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            try:
                result = AutomationRepository(session).enqueue_scheduled_occurrence(
                    job_id=job_id,
                    expected_scheduled_for=now,
                )
                return ("ok", result)
            except Exception as exc:
                return ("error", exc.__class__.__name__)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(enqueue, ["job-a", "job-b"]))
    finally:
        event.remove(
            authorization_database,
            "after_cursor_execute",
            synchronize_candidate_reads,
        )

    assert results == [("ok", None), ("ok", None)]


def test_scheduler_does_not_enqueue_for_revoked_principal(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    due = datetime.now(timezone.utc) - timedelta(minutes=1)
    with Session(authorization_database) as session:
        principal = session.get(db_models.User, "principal")
        principal.is_active = False
        job = session.get(db_models.AutomationJob, "job-active")
        job.next_run_at = due
        session.commit()

    with Session(authorization_database) as session:
        result = AutomationRepository(session).enqueue_scheduled_occurrence(
            job_id="job-active", expected_scheduled_for=due
        )

    assert result is None
    with Session(authorization_database) as session:
        job = session.get(db_models.AutomationJob, "job-active")
        assert job.status == "paused"
        assert job.next_run_at is None
        assert (
            session.scalar(
                select(db_models.AutomationExecution).where(
                    db_models.AutomationExecution.job_id == "job-active",
                    db_models.AutomationExecution.scheduled_for == due,
                )
            )
            is None
        )


def test_claim_converges_revoked_principal_without_starting_execution(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    with Session(authorization_database) as session:
        session.get(db_models.User, "principal").is_active = False
        session.delete(session.get(db_models.AutomationExecution, "job-active-running"))
        session.commit()

    with Session(authorization_database) as session:
        result = AutomationRepository(session).claim_execution(
            workspace_id=WORKSPACE_ID,
            runner_instance_id=uuid4(),
            claim_request_id=uuid4(),
        )

    assert result is None
    with Session(authorization_database) as session:
        assert not session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.status == "queued"
            )
        ).all()


def test_concurrent_admin_demotions_cannot_remove_last_effective_admin(
    authorization_database,
) -> None:
    now = datetime.now(timezone.utc)
    with Session(authorization_database) as session:
        session.add_all(
            [
                db_models.User(
                    id=admin_id,
                    username=admin_id,
                    is_active=True,
                    identity_enabled=True,
                    sync_status="synced",
                    platform_role="admin",
                    role_status="valid",
                    created_at=now,
                    updated_at=now,
                )
                for admin_id in ("admin-1", "admin-2")
            ]
            + [
                db_models.User(
                    id="concurrency-test-actor",
                    username="concurrency-test-actor",
                    is_active=True,
                    identity_enabled=True,
                    sync_status="synced",
                    platform_role="member",
                    role_status="valid",
                    created_at=now,
                    updated_at=now,
                )
            ]
        )
        session.commit()

    def demote(admin_id: str) -> str:
        with Session(authorization_database) as session:
            try:
                UserAdminService(session).replace_role(
                    admin_id,
                    AdminUserRoleRequest(role="member"),
                    actor_user_id="concurrency-test-actor",
                )
            except HTTPException as exc:
                return str(exc.detail)
            return "success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(demote, ("admin-1", "admin-2")))

    assert sorted(results) == ["LAST_ADMIN_FORBIDDEN", "success"]
    with Session(authorization_database) as session:
        roles = (
            session.execute(
                select(db_models.User.platform_role)
                .where(db_models.User.id.in_(["admin-1", "admin-2"]))
                .order_by(db_models.User.id.asc())
            )
            .scalars()
            .all()
        )
    assert sorted(roles) == ["admin", "member"]


def test_stale_claim_role_does_not_override_local_authorization_snapshot(
    authorization_database,
) -> None:
    _seed_principal_state(authorization_database)
    with Session(authorization_database) as session:
        principal = session.get(db_models.User, "principal")
        principal.oidc_issuer = "https://issuer.example.test"
        principal.oidc_subject = "oidc-principal"
        session.commit()
        UserSnapshotSyncService(session).sync_from_claims(
            {
                "iss": "https://issuer.example.test",
                "sub": "oidc-principal",
                "preferred_username": "principal",
                "roles": ["reader"],
            }
        )
        assert session.get(db_models.User, "principal").platform_role == "member"
        assert session.get(db_models.AutomationJob, "job-active").status == "active"


@pytest.mark.parametrize("runtime_status", ["stopped", "error"])
@pytest.mark.parametrize("mutation", ["downgrade", "delete"])
def test_workspace_share_revocation_converges_authorization(
    authorization_database,
    mutation: str,
    runtime_status: str,
) -> None:
    _seed_principal_state(authorization_database)
    with Session(authorization_database) as session:
        owner = db_models.User(
            id="owner",
            username="owner",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        session.add(owner)
        workspace = session.get(db_models.Workspace, WORKSPACE_ID)
        workspace.owner_id = owner.id
        workspace.runtime_status = runtime_status
        share = db_models.WorkspaceShare(
            id="share",
            workspace_id=workspace.id,
            target_type="user",
            target_id="principal",
            role="manager",
            granted_by_user_id=owner.id,
        )
        session.add(share)
        session.commit()

        service = WorkspaceService(session)
        correlation_id = f"share-{mutation}-{runtime_status}"
        if mutation == "downgrade":
            service.update_share(
                WORKSPACE_ID,
                "share",
                WorkspaceShareUpdateRequest(role="reader"),
                actor=AuthorizationActor("owner", "member"),
                correlation_id=correlation_id,
                root_correlation_id=correlation_id,
            )
        else:
            assert service.delete_share(
                WORKSPACE_ID,
                "share",
                actor=AuthorizationActor("owner", "member"),
                correlation_id=correlation_id,
                root_correlation_id=correlation_id,
            )
        assert session.get(db_models.AutomationJob, "job-active").status == "paused"
        assert not session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.status == "running",
                db_models.AutomationExecution.cancel_requested_at.is_(None),
            )
        ).all()
        refreshed_workspace = session.get(db_models.Workspace, WORKSPACE_ID)
        assert refreshed_workspace.runtime_access_revision == 1
        assert refreshed_workspace.runtime_access_observed_revision == 0
        assert refreshed_workspace.knowledge_base_mount_desired_revision == 0
        runtime_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == WORKSPACE_ID,
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        )
        assert runtime_job.status == "queued"
        assert runtime_job.target_revision == 1
        assert runtime_job.correlation_id == correlation_id
        assert runtime_job.root_correlation_id == correlation_id
        assert runtime_job.job_metadata == {
            "reason": f"workspace_share_{'downgraded' if mutation == 'downgrade' else 'deleted'}"
        }
        audit = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "runtime.access_recycle_requested",
                db_models.AuditEvent.correlation_id == correlation_id,
            )
        )
        assert audit.root_correlation_id == correlation_id
        assert audit.event_metadata == {
            "workspace_id": WORKSPACE_ID,
            "runtime_access_revision": 1,
            "reason": runtime_job.job_metadata["reason"],
        }


def test_workspace_share_runtime_cancel_observes_committed_recycle(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database)
    correlation_id = str(uuid4())
    with Session(authorization_database) as session:
        owner = db_models.User(
            id="owner",
            username="owner",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        session.add(owner)
        workspace = session.get(db_models.Workspace, WORKSPACE_ID)
        workspace.owner_id = owner.id
        session.add(
            db_models.WorkspaceShare(
                id="share",
                workspace_id=workspace.id,
                target_type="user",
                target_id="principal",
                role="manager",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

    delivered: list[str] = []

    def record_cancel(_self, **kwargs):
        with Session(authorization_database) as verification:
            assert verification.get(db_models.WorkspaceShare, "share") is None
            workspace = verification.get(db_models.Workspace, WORKSPACE_ID)
            assert workspace.runtime_access_revision == 1
            assert verification.scalar(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == WORKSPACE_ID,
                    db_models.WorkspaceRuntimeJob.operation
                    == "workspace_access_recycle",
                    db_models.WorkspaceRuntimeJob.status == "queued",
                )
            )
            assert verification.scalar(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.event_type
                    == "runtime.access_recycle_requested",
                    db_models.AuditEvent.correlation_id == correlation_id,
                )
            )
            assert (
                verification.get(
                    db_models.AutomationExecution,
                    kwargs["execution_id"],
                ).cancel_requested_at
                is not None
            )
        delivered.append(kwargs["execution_id"])
        return True

    monkeypatch.setattr(RuntimeAutomationClient, "cancel_execution", record_cancel)

    with Session(authorization_database) as session:
        assert WorkspaceService(session).delete_share(
            WORKSPACE_ID,
            "share",
            actor=AuthorizationActor("owner", "member"),
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
        )

    assert set(delivered) == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }


def test_group_member_removal_runtime_cancel_observes_committed_recycle(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database, platform_role="member")
    correlation_id = str(uuid4())
    with Session(authorization_database) as session:
        owner = db_models.User(
            id="group-owner",
            username="group-owner",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        workspace = session.get(db_models.Workspace, WORKSPACE_ID)
        workspace.owner_id = owner.id
        session.add_all(
            [
                owner,
                db_models.UserGroup(id="automation-group", name="Automation Group"),
            ]
        )
        session.flush()
        session.add_all(
            [
                db_models.UserGroupMember(
                    id="automation-group-member",
                    group_id="automation-group",
                    user_id="principal",
                    created_by_id=owner.id,
                ),
                db_models.WorkspaceShare(
                    id="automation-group-share",
                    workspace_id=workspace.id,
                    target_type="user_group",
                    target_id="automation-group",
                    role="manager",
                    granted_by_user_id=owner.id,
                ),
            ]
        )
        session.commit()

    delivered: list[str] = []

    def record_cancel(_self, **kwargs):
        with Session(authorization_database) as verification:
            assert (
                verification.get(
                    db_models.UserGroupMember,
                    "automation-group-member",
                )
                is None
            )
            workspace = verification.get(db_models.Workspace, WORKSPACE_ID)
            assert workspace.runtime_access_revision == 1
            assert verification.scalar(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == WORKSPACE_ID,
                    db_models.WorkspaceRuntimeJob.operation
                    == "workspace_access_recycle",
                    db_models.WorkspaceRuntimeJob.status == "queued",
                )
            )
            assert (
                verification.get(
                    db_models.AutomationExecution,
                    kwargs["execution_id"],
                ).cancel_requested_at
                is not None
            )
        delivered.append(kwargs["execution_id"])
        return True

    monkeypatch.setattr(RuntimeAutomationClient, "cancel_execution", record_cancel)

    with Session(authorization_database) as session:
        UserGroupService(session).remove_member(
            group_id="automation-group",
            user_id="principal",
            actor_user_id="group-owner",
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
        )

    assert set(delivered) == {
        "job-active-running",
        "job-paused-running",
        "job-completed-running",
    }


def test_workspace_share_commit_failure_rolls_back_all_recycle_state(
    authorization_database,
    monkeypatch,
) -> None:
    _seed_principal_state(authorization_database)
    with Session(authorization_database) as session:
        owner = db_models.User(
            id="owner",
            username="owner",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        session.add(owner)
        workspace = session.get(db_models.Workspace, WORKSPACE_ID)
        workspace.owner_id = owner.id
        session.add(
            db_models.WorkspaceShare(
                id="share",
                workspace_id=workspace.id,
                target_type="user",
                target_id="principal",
                role="manager",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

    delivered: list[str] = []
    monkeypatch.setattr(
        RuntimeAutomationClient,
        "cancel_execution",
        lambda self, **kwargs: delivered.append(kwargs["execution_id"]),
    )

    with Session(authorization_database) as session:

        def fail_commit() -> None:
            raise IntegrityError("forced share rollback", {}, RuntimeError("forced"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError):
            WorkspaceService(session).delete_share(
                WORKSPACE_ID,
                "share",
                actor=AuthorizationActor("owner", "member"),
                correlation_id="rollback-correlation",
                root_correlation_id="rollback-correlation",
            )

    assert delivered == []
    with Session(authorization_database) as verification:
        assert verification.get(db_models.WorkspaceShare, "share").role == "manager"
        workspace = verification.get(db_models.Workspace, WORKSPACE_ID)
        assert workspace.runtime_access_revision == 0
        assert workspace.knowledge_base_mount_desired_revision == 0
        assert not verification.scalars(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == WORKSPACE_ID,
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        ).all()
        assert not verification.scalars(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "runtime.access_recycle_requested"
            )
        ).all()
        assert (
            verification.get(db_models.AutomationJob, "job-active").status == "active"
        )
        assert (
            verification.get(
                db_models.AutomationExecution,
                "job-active-running",
            ).cancel_requested_at
            is None
        )
