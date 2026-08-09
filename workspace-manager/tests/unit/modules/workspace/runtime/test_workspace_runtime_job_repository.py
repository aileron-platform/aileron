"""Unit tests for durable workspace runtime job persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.workspace.runtime.job_repository import (
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
    WORKSPACE_ACCESS_RECYCLE,
    WORKSPACE_START,
    ExpiredJobRecoveryAction,
    WorkspaceRuntimeJobRepository,
)


def _session_returning(*jobs: db_models.WorkspaceRuntimeJob) -> MagicMock:
    session = MagicMock(spec=Session)
    scalar_result = MagicMock()
    scalar_result.all.return_value = list(jobs)
    session.scalars.return_value = scalar_result
    return session


def _session_scalar_returning(*values: object) -> MagicMock:
    session = MagicMock(spec=Session)
    session.scalar.side_effect = list(values)
    return session


def _compiled(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _workspace() -> db_models.Workspace:
    return db_models.Workspace(
        id="workspace-1",
        provisioner="kubernetes",
        knowledge_base_mount_desired_revision=9,
        runtime_access_revision=4,
        runtime_instance_id="b43d266c-2db4-4f66-9f93-e2887956d06b",
    )


def test_enqueue_lifecycle_parent_has_immutable_strategy_and_no_revision() -> None:
    session = _session_scalar_returning(None)
    scheduled_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)

    result = WorkspaceRuntimeJobRepository(session).enqueue_lifecycle_job(
        workspace=_workspace(),
        operation=WORKSPACE_START,
        correlation_id="start-attempt",
        root_correlation_id="start-root",
        scheduled_at=scheduled_at,
        target_runtime_instance_id=None,
    )

    assert result.created is True
    assert result.job.operation == WORKSPACE_START
    assert result.job.strategy == "kubernetes"
    assert result.job.status == "queued"
    assert result.job.target_revision is None
    assert result.job.correlation_id == "start-attempt"
    assert result.job.root_correlation_id == "start-root"
    session.add.assert_called_once_with(result.job)
    session.commit.assert_not_called()


def test_enqueue_lifecycle_parent_returns_active_job_idempotently() -> None:
    active = _job(
        job_id="active-start",
        status="queued",
        correlation_id="existing-attempt",
        root_correlation_id="existing-root",
    )
    active.operation = WORKSPACE_START
    active.target_revision = None
    session = _session_scalar_returning(active)

    result = WorkspaceRuntimeJobRepository(session).enqueue_lifecycle_job(
        workspace=_workspace(),
        operation=WORKSPACE_START,
        correlation_id="duplicate-attempt",
        root_correlation_id="duplicate-root",
        scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
        target_runtime_instance_id=None,
    )

    assert result.created is False
    assert result.job is active
    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_access_recycle_supersedes_queued_intent_and_preserves_http_lineage() -> None:
    scheduled_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    old_job = _job(
        job_id="old-access-job",
        status="queued",
        correlation_id="old-correlation",
        root_correlation_id="old-root",
    )
    old_job.operation = WORKSPACE_ACCESS_RECYCLE
    session = _session_returning(old_job)

    new_job, superseded_jobs = WorkspaceRuntimeJobRepository(
        session
    ).supersede_queued_and_enqueue_access_recycle(
        workspace=_workspace(),
        correlation_id="http-correlation",
        root_correlation_id="http-root",
        scheduled_at=scheduled_at,
        job_metadata={"reason": "workspace_share_deleted"},
    )

    assert superseded_jobs == [old_job]
    assert old_job.status == "superseded"
    assert old_job.finished_at == scheduled_at
    assert old_job.correlation_id == "old-correlation"
    assert old_job.root_correlation_id == "old-root"
    assert new_job.operation == WORKSPACE_ACCESS_RECYCLE
    assert new_job.status == "queued"
    assert new_job.target_revision == 4
    assert new_job.target_runtime_instance_id == (
        "b43d266c-2db4-4f66-9f93-e2887956d06b"
    )
    assert new_job.correlation_id == "http-correlation"
    assert new_job.root_correlation_id == "http-root"
    assert new_job.job_metadata == {"reason": "workspace_share_deleted"}
    statement = session.scalars.call_args.args[0]
    compiled = _compiled(statement)
    assert "workspace_runtime_jobs.workspace_id = 'workspace-1'" in compiled
    assert "workspace_runtime_jobs.operation = 'workspace_access_recycle'" in compiled
    assert "workspace_runtime_jobs.status = 'queued'" in compiled
    assert "FOR UPDATE" in compiled
    assert session.flush.call_count == 2
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    "metadata",
    [
        {"principal_user_id": "secret-principal"},
        {"reason": ""},
        {"reason": "x" * 65},
        {"attempt": -1},
        {"attempt": "1"},
    ],
)
def test_access_recycle_rejects_metadata_outside_allowlist(metadata: dict) -> None:
    session = _session_returning()

    with pytest.raises(ValueError):
        WorkspaceRuntimeJobRepository(
            session
        ).supersede_queued_and_enqueue_access_recycle(
            workspace=_workspace(),
            correlation_id="http-correlation",
            root_correlation_id="http-correlation",
            scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
            job_metadata=metadata,
        )

    session.scalars.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("runtime_status", ["stopped", "error"])
def test_access_recycle_keeps_durable_queued_intent_for_inactive_runtime(
    runtime_status: str,
) -> None:
    workspace = _workspace()
    workspace.runtime_status = runtime_status
    session = _session_returning()

    new_job, superseded_jobs = WorkspaceRuntimeJobRepository(
        session
    ).supersede_queued_and_enqueue_access_recycle(
        workspace=workspace,
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
        scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
        job_metadata={"reason": "workspace_share_downgraded"},
    )

    assert superseded_jobs == []
    assert new_job.status == "queued"
    assert new_job.target_revision == 4
    session.commit.assert_not_called()


def _job(
    *,
    job_id: str,
    status: str,
    correlation_id: str,
    root_correlation_id: str,
    retries: int = 0,
    dispatch_attempts: int = 0,
    job_metadata: dict | None = None,
) -> db_models.WorkspaceRuntimeJob:
    return db_models.WorkspaceRuntimeJob(
        id=job_id,
        workspace_id="workspace-1",
        operation=KNOWLEDGE_BASE_MOUNT_RECONCILE,
        strategy="kubernetes",
        status=status,
        retries=retries,
        target_revision=8,
        target_runtime_instance_id="b43d266c-2db4-4f66-9f93-e2887956d06b",
        correlation_id=correlation_id,
        root_correlation_id=root_correlation_id,
        job_metadata=job_metadata or {"mutation_action": "attach"},
        dispatch_attempts=dispatch_attempts,
        scheduled_at=datetime(2026, 7, 19, 1, 0, tzinfo=timezone.utc),
    )


def test_supersede_then_insert_preserves_old_lineage_and_flushes_only() -> None:
    old_job = _job(
        job_id="old-job",
        status="queued",
        correlation_id="old-correlation",
        root_correlation_id="old-root",
    )
    session = _session_returning(old_job)
    repository = WorkspaceRuntimeJobRepository(session)
    scheduled_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)

    new_job, superseded_jobs = repository.supersede_queued_and_enqueue_mount_reconcile(
        workspace=_workspace(),
        correlation_id="new-correlation",
        scheduled_at=scheduled_at,
        job_metadata={
            "attachment_id": "attachment-1",
            "knowledge_base_id": "kb-1",
            "mutation_action": "update_alias",
        },
    )

    assert superseded_jobs == [old_job]
    assert old_job.status == "superseded"
    assert old_job.finished_at == scheduled_at
    assert old_job.correlation_id == "old-correlation"
    assert old_job.root_correlation_id == "old-root"
    assert old_job.target_revision == 8

    assert new_job.workspace_id == "workspace-1"
    assert new_job.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE
    assert new_job.strategy == "kubernetes"
    assert new_job.status == "queued"
    assert new_job.target_revision == 9
    assert new_job.target_runtime_instance_id == (
        "b43d266c-2db4-4f66-9f93-e2887956d06b"
    )
    assert new_job.correlation_id == "new-correlation"
    assert new_job.root_correlation_id == "new-correlation"
    assert new_job.scheduled_at == scheduled_at
    assert new_job.finished_at is None
    assert new_job.dispatch_attempts == 0
    assert new_job.job_metadata == {
        "attachment_id": "attachment-1",
        "knowledge_base_id": "kb-1",
        "mutation_action": "update_alias",
    }

    session.add.assert_called_once_with(new_job)
    assert session.flush.call_count == 2
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_supersede_query_locks_only_queued_jobs_for_same_operation() -> None:
    old_job = _job(
        job_id="old-job",
        status="queued",
        correlation_id="old-correlation",
        root_correlation_id="old-root",
    )
    running_job = _job(
        job_id="running-job",
        status="running",
        correlation_id="running-correlation",
        root_correlation_id="running-root",
    )
    session = _session_returning(old_job)
    repository = WorkspaceRuntimeJobRepository(session)

    repository.supersede_queued_and_enqueue_mount_reconcile(
        workspace=_workspace(),
        correlation_id="new-correlation",
        scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "workspace_runtime_jobs.workspace_id = 'workspace-1'" in compiled
    assert (
        "workspace_runtime_jobs.operation = "
        "'knowledge_base_mount_reconcile'" in compiled
    )
    assert "workspace_runtime_jobs.status = 'queued'" in compiled
    assert "FOR UPDATE" in compiled
    assert running_job.status == "running"
    assert running_job.finished_at is None
    assert running_job.correlation_id == "running-correlation"
    assert running_job.root_correlation_id == "running-root"


def test_enqueue_without_prior_queued_job_uses_one_flush() -> None:
    session = _session_returning()
    repository = WorkspaceRuntimeJobRepository(session)
    metadata = {
        "attempt": 0,
        "mount_action": "apply_candidate",
        "mutation_action": "attach",
    }

    new_job, superseded_jobs = repository.supersede_queued_and_enqueue_mount_reconcile(
        workspace=_workspace(),
        correlation_id="new-correlation",
        scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
        job_metadata=metadata,
    )

    assert superseded_jobs == []
    assert new_job.job_metadata == metadata
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "metadata",
    [
        {"token": "secret"},
        {"request_body": {"alias": "docs"}},
        {"attempt": -1},
        {"detach_only_cleanup": "true"},
    ],
)
def test_enqueue_rejects_metadata_outside_allowlist(metadata: dict) -> None:
    session = _session_returning()
    repository = WorkspaceRuntimeJobRepository(session)

    with pytest.raises(ValueError):
        repository.supersede_queued_and_enqueue_mount_reconcile(
            workspace=_workspace(),
            correlation_id="new-correlation",
            scheduled_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
            job_metadata=metadata,
        )

    session.scalars.assert_not_called()
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_claim_queued_job_uses_due_lifecycle_provisioner_and_running_cas() -> None:
    claimed_job = _job(
        job_id="job-1",
        status="running",
        correlation_id="request-correlation",
        root_correlation_id="root-correlation",
    )
    session = _session_scalar_returning(claimed_job)
    repository = WorkspaceRuntimeJobRepository(session)
    claimed_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    expires_at = claimed_at + timedelta(minutes=3)

    result = repository.claim_queued_job(
        job_id="job-1",
        claim_token="claim-1",
        claimed_at=claimed_at,
        claim_expires_at=expires_at,
        eligible_runtime_statuses={"running"},
    )

    assert result is claimed_job
    statement = session.scalar.call_args.args[0]
    compiled = _compiled(statement)
    assert "UPDATE workspace_runtime_jobs" in compiled
    assert "workspace_runtime_jobs.id = 'job-1'" in compiled
    assert "workspace_runtime_jobs.status = 'queued'" in compiled
    assert "workspace_runtime_jobs.scheduled_at <=" in compiled
    assert "workspace_runtime_jobs.claim_token IS NULL" in compiled
    assert "workspaces.runtime_status IN ('running')" in compiled
    assert "workspaces.provisioner = workspace_runtime_jobs.strategy" in compiled
    assert "workspace_runtime_jobs_1.status = 'running'" in compiled
    assert "NOT (EXISTS" in compiled
    assert "status='running'" in compiled
    assert "claim_token='claim-1'" in compiled
    assert "RETURNING" in compiled
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("statuses", "claim_token", "lease_seconds"),
    [
        (set(), "claim-1", 60),
        ({"creating"}, "claim-1", 60),
        ({"running"}, "", 60),
        ({"running"}, "claim-1", 0),
    ],
)
def test_claim_rejects_invalid_eligibility_or_lease(
    statuses: set[str],
    claim_token: str,
    lease_seconds: int,
) -> None:
    session = _session_scalar_returning()
    repository = WorkspaceRuntimeJobRepository(session)
    claimed_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        repository.claim_queued_job(
            job_id="job-1",
            claim_token=claim_token,
            claimed_at=claimed_at,
            claim_expires_at=claimed_at + timedelta(seconds=lease_seconds),
            eligible_runtime_statuses=statuses,
        )

    session.scalar.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_heartbeat_requires_live_matching_claim_token() -> None:
    session = _session_scalar_returning("job-1", None)
    repository = WorkspaceRuntimeJobRepository(session)
    heartbeat_at = datetime(2026, 7, 19, 2, 1, tzinfo=timezone.utc)
    expires_at = heartbeat_at + timedelta(minutes=3)

    assert repository.heartbeat_running_job(
        job_id="job-1",
        claim_token="current-token",
        heartbeat_at=heartbeat_at,
        claim_expires_at=expires_at,
    )
    assert not repository.heartbeat_running_job(
        job_id="job-1",
        claim_token="stale-token",
        heartbeat_at=heartbeat_at,
        claim_expires_at=expires_at,
    )

    statement = session.scalar.call_args_list[0].args[0]
    compiled = _compiled(statement)
    assert "workspace_runtime_jobs.status = 'running'" in compiled
    assert "workspace_runtime_jobs.claim_token = 'current-token'" in compiled
    assert "workspace_runtime_jobs.claim_expires_at >" in compiled
    assert "last_heartbeat_at=" in compiled
    assert "claim_expires_at=" in compiled
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("method_name", "expected_status", "error_code"),
    [
        ("complete_running_job", "succeeded", None),
        ("fail_running_job", "failed", "WORKSPACE_RUNTIME_APPLY_FAILED"),
        ("supersede_running_job", "superseded", None),
    ],
)
def test_claimed_terminal_transitions_are_token_and_lease_cas(
    method_name: str,
    expected_status: str,
    error_code: str | None,
) -> None:
    session = _session_scalar_returning("job-1")
    repository = WorkspaceRuntimeJobRepository(session)
    finished_at = datetime(2026, 7, 19, 2, 2, tzinfo=timezone.utc)
    kwargs = {
        "job_id": "job-1",
        "claim_token": "claim-1",
        "finished_at": finished_at,
    }
    if error_code is not None:
        kwargs["error_code"] = error_code

    assert getattr(repository, method_name)(**kwargs)

    statement = session.scalar.call_args.args[0]
    compiled = _compiled(statement)
    assert "workspace_runtime_jobs.status = 'running'" in compiled
    assert "workspace_runtime_jobs.claim_token = 'claim-1'" in compiled
    assert "workspace_runtime_jobs.claim_expires_at >" in compiled
    assert f"status='{expected_status}'" in compiled
    assert "claim_token=NULL" in compiled
    assert "claim_expires_at=NULL" in compiled
    if error_code is None:
        assert "error_code=NULL" in compiled
    else:
        assert f"error_code='{error_code}'" in compiled
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_stale_claim_token_cannot_complete_job() -> None:
    session = _session_scalar_returning(None)
    repository = WorkspaceRuntimeJobRepository(session)

    assert not repository.complete_running_job(
        job_id="job-1",
        claim_token="stale-token",
        finished_at=datetime(2026, 7, 19, 2, 2, tzinfo=timezone.utc),
    )
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_supersede_queued_job_only_accepts_unclaimed_queued_row() -> None:
    session = _session_scalar_returning("job-1")
    repository = WorkspaceRuntimeJobRepository(session)

    assert repository.supersede_queued_job(
        job_id="job-1",
        finished_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
    )

    compiled = _compiled(session.scalar.call_args.args[0])
    assert "workspace_runtime_jobs.status = 'queued'" in compiled
    assert "workspace_runtime_jobs.claim_token IS NULL" in compiled
    assert "workspace_runtime_jobs.claim_expires_at IS NULL" in compiled
    assert "status='superseded'" in compiled
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_retry_creates_new_queued_child_without_reopening_failed_row() -> None:
    failed_job = _job(
        job_id="failed-job",
        status="failed",
        correlation_id="failed-request",
        root_correlation_id="root-correlation",
        retries=2,
        job_metadata={"mutation_action": "attach", "attempt": 3},
    )
    failed_job.lifecycle_job_id = "lifecycle-job"
    failed_job.error_code = "WORKSPACE_RUNTIME_APPLY_FAILED"
    failed_job.finished_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    session = _session_scalar_returning(failed_job, None)
    scheduled_at = datetime(2026, 7, 19, 3, 0, tzinfo=timezone.utc)

    result = WorkspaceRuntimeJobRepository(session).enqueue_retry_for_failed_job(
        failed_job_id="failed-job",
        correlation_id="retry-request",
        scheduled_at=scheduled_at,
    )

    assert result is not None
    assert result.created
    retry_job = result.job
    assert retry_job.status == "queued"
    assert retry_job.retry_of_job_id == "failed-job"
    assert retry_job.root_correlation_id == "root-correlation"
    assert retry_job.correlation_id == "retry-request"
    assert retry_job.strategy == failed_job.strategy
    assert retry_job.operation == failed_job.operation
    assert retry_job.target_revision == failed_job.target_revision
    assert retry_job.target_runtime_instance_id == failed_job.target_runtime_instance_id
    assert retry_job.lifecycle_job_id == "lifecycle-job"
    assert retry_job.retries == 0
    assert retry_job.dispatch_attempts == 0
    assert retry_job.job_metadata == {
        "mutation_action": "attach",
        "attempt": 4,
    }
    assert retry_job.scheduled_at == scheduled_at
    assert retry_job.error_code is None
    assert failed_job.status == "failed"
    assert failed_job.error_code == "WORKSPACE_RUNTIME_APPLY_FAILED"
    session.add.assert_called_once_with(retry_job)
    session.flush.assert_called_once_with()
    for call in session.scalar.call_args_list:
        assert "FOR UPDATE" in _compiled(call.args[0])
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_duplicate_retry_returns_existing_child_idempotently() -> None:
    failed_job = _job(
        job_id="failed-job",
        status="failed",
        correlation_id="failed-request",
        root_correlation_id="root-correlation",
    )
    existing_retry = _job(
        job_id="retry-job",
        status="queued",
        correlation_id="first-retry-request",
        root_correlation_id="root-correlation",
    )
    existing_retry.retry_of_job_id = "failed-job"
    session = _session_scalar_returning(failed_job, existing_retry)

    result = WorkspaceRuntimeJobRepository(session).enqueue_retry_for_failed_job(
        failed_job_id="failed-job",
        correlation_id="duplicate-retry-request",
        scheduled_at=datetime(2026, 7, 19, 3, 0, tzinfo=timezone.utc),
    )

    assert result is not None
    assert not result.created
    assert result.job is existing_retry
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def _expired_running_job(*, retries: int = 0) -> db_models.WorkspaceRuntimeJob:
    job = _job(
        job_id="running-job",
        status="running",
        correlation_id="running-request",
        root_correlation_id="running-root",
        retries=retries,
    )
    job.claim_token = "expired-token"
    job.claim_expires_at = datetime(2026, 7, 19, 1, 59, tzinfo=timezone.utc)
    job.last_heartbeat_at = datetime(2026, 7, 19, 1, 56, tzinfo=timezone.utc)
    job.started_at = datetime(2026, 7, 19, 1, 50, tzinfo=timezone.utc)
    return job


def _recover(
    session: MagicMock,
    *,
    max_retries: int = 3,
):
    recovered_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    return WorkspaceRuntimeJobRepository(session).recover_expired_running_job(
        job_id="running-job",
        recovered_at=recovered_at,
        replacement_claim_token="replacement-token",
        replacement_claim_expires_at=recovered_at + timedelta(minutes=3),
        max_retries=max_retries,
        exhausted_error_code="WORKSPACE_RUNTIME_RETRY_EXHAUSTED",
    )


def test_recovery_supersedes_expired_running_job_when_successor_exists() -> None:
    running_job = _expired_running_job(retries=1)
    successor = _job(
        job_id="successor-job",
        status="queued",
        correlation_id="successor-request",
        root_correlation_id="successor-root",
    )
    session = _session_scalar_returning(running_job, successor)

    result = _recover(session)

    assert result.action is ExpiredJobRecoveryAction.SUPERSEDED
    assert result.job is running_job
    assert result.successor is successor
    assert running_job.status == "superseded"
    assert running_job.claim_token is None
    assert running_job.claim_expires_at is None
    assert running_job.finished_at == datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    assert successor.status == "queued"
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_recovery_reclaims_expired_running_row_in_place_without_successor() -> None:
    running_job = _expired_running_job(retries=1)
    original_started_at = running_job.started_at
    session = _session_scalar_returning(running_job, None)

    result = _recover(session, max_retries=3)

    assert result.action is ExpiredJobRecoveryAction.RECLAIMED
    assert result.job is running_job
    assert result.successor is None
    assert running_job.status == "running"
    assert running_job.retries == 2
    assert running_job.claim_token == "replacement-token"
    assert running_job.claim_expires_at == datetime(
        2026, 7, 19, 2, 3, tzinfo=timezone.utc
    )
    assert running_job.last_heartbeat_at == datetime(
        2026, 7, 19, 2, 0, tzinfo=timezone.utc
    )
    assert running_job.started_at == original_started_at
    assert running_job.finished_at is None
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_recovery_fails_expired_running_row_after_retry_budget() -> None:
    running_job = _expired_running_job(retries=3)
    session = _session_scalar_returning(running_job, None)

    result = _recover(session, max_retries=3)

    assert result.action is ExpiredJobRecoveryAction.FAILED
    assert result.job is running_job
    assert running_job.status == "failed"
    assert running_job.error_code == "WORKSPACE_RUNTIME_RETRY_EXHAUSTED"
    assert running_job.claim_token is None
    assert running_job.claim_expires_at is None
    assert running_job.finished_at == datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_recovery_does_not_take_over_unexpired_running_job() -> None:
    running_job = _expired_running_job()
    running_job.claim_expires_at = datetime(2026, 7, 19, 2, 1, tzinfo=timezone.utc)
    session = _session_scalar_returning(running_job)

    result = _recover(session)

    assert result.action is ExpiredJobRecoveryAction.NOOP
    assert result.job is running_job
    assert running_job.status == "running"
    assert running_job.claim_token == "expired-token"
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("attempts", "expected_delay_seconds"),
    [
        (0, 5),
        (3, 40),
        (20, 60),
    ],
)
def test_dispatch_failure_uses_attempt_cas_and_bounded_exponential_backoff(
    attempts: int,
    expected_delay_seconds: int,
) -> None:
    queued_job = _job(
        job_id="job-1",
        status="queued",
        correlation_id="request-correlation",
        root_correlation_id="root-correlation",
        dispatch_attempts=attempts + 1,
    )
    session = _session_scalar_returning(queued_job)
    failed_at = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)

    result = WorkspaceRuntimeJobRepository(session).record_dispatch_failure(
        job_id="job-1",
        expected_dispatch_attempts=attempts,
        failed_at=failed_at,
        base_delay_seconds=5,
        max_delay_seconds=60,
    )

    assert result is queued_job
    compiled = _compiled(session.scalar.call_args.args[0])
    assert "workspace_runtime_jobs.status = 'queued'" in compiled
    assert f"workspace_runtime_jobs.dispatch_attempts = {attempts}" in compiled
    assert "workspace_runtime_jobs.scheduled_at <=" in compiled
    assert f"dispatch_attempts={attempts + 1}" in compiled
    expected_next = failed_at + timedelta(seconds=expected_delay_seconds)
    assert str(expected_next) in compiled
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_stale_dispatch_attempt_does_not_change_backoff() -> None:
    session = _session_scalar_returning(None)

    result = WorkspaceRuntimeJobRepository(session).record_dispatch_failure(
        job_id="job-1",
        expected_dispatch_attempts=0,
        failed_at=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
        base_delay_seconds=5,
        max_delay_seconds=60,
    )

    assert result is None
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_recovery_queries_return_only_due_candidates_in_stable_order() -> None:
    queued = _job(
        job_id="queued-job",
        status="queued",
        correlation_id="queued-request",
        root_correlation_id="queued-root",
    )
    running = _expired_running_job()
    session = _session_returning(queued)
    repository = WorkspaceRuntimeJobRepository(session)
    now = datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc)

    assert repository.find_dispatchable_queued_jobs(now=now, limit=25) == [queued]
    queued_statement = session.scalars.call_args.args[0]
    queued_compiled = _compiled(queued_statement)
    assert "workspace_runtime_jobs.status = 'queued'" in queued_compiled
    assert "workspace_runtime_jobs.scheduled_at <=" in queued_compiled
    assert "LIMIT 25" in queued_compiled

    scalar_result = MagicMock()
    scalar_result.all.return_value = [running]
    session.scalars.return_value = scalar_result
    assert repository.find_expired_running_jobs(now=now, limit=30) == [running]
    running_statement = session.scalars.call_args.args[0]
    running_compiled = _compiled(running_statement)
    assert "workspace_runtime_jobs.status = 'running'" in running_compiled
    assert "workspace_runtime_jobs.claim_expires_at IS NOT NULL" in running_compiled
    assert "workspace_runtime_jobs.claim_expires_at <=" in running_compiled
    assert "LIMIT 30" in running_compiled
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("limit", [0, 1001, True])
def test_recovery_queries_reject_unsafe_limits(limit: int) -> None:
    session = _session_returning()
    repository = WorkspaceRuntimeJobRepository(session)

    with pytest.raises(ValueError):
        repository.find_dispatchable_queued_jobs(
            now=datetime(2026, 7, 19, 2, 0, tzinfo=timezone.utc),
            limit=limit,
        )

    session.scalars.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
