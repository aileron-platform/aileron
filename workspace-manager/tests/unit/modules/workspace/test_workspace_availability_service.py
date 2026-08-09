"""Manager-owned Workspace availability contract tests."""

from __future__ import annotations

from datetime import datetime
from typing import get_args
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.authorization.actor import actor_from_valid_user
from app.modules.workspace.availability_contract import (
    load_workspace_availability_contract,
)
from app.db import models as db_models
from app.modules.workspace.availability_models import (
    KnowledgeMountAvailabilityState,
    WorkspaceAvailabilityAction,
    WorkspaceAvailabilityState,
    WorkspaceDeletionAction,
    WorkspaceDeletionPhase,
)
from app.modules.workspace.availability import (
    WorkspaceAvailabilityError,
    WorkspaceAvailabilityService,
)
from app.modules.workspace.execution_plane_observation import (
    ExecutionPlaneObservation,
    WorkspaceExecutionPlaneObservationService,
)


def _valid_user(create_user, *, user_id: str = "availability-owner"):
    return create_user(
        id=user_id,
        platform_role="member",
        role_status="valid",
        identity_enabled=True,
        sync_status="synced",
        is_active=True,
    )


@pytest.fixture(autouse=True)
def _default_execution_plane_is_observed(monkeypatch) -> None:
    monkeypatch.setattr(
        WorkspaceExecutionPlaneObservationService,
        "observe",
        lambda _self, _workspace: ExecutionPlaneObservation.ready(),
    )


def _seed_workspace(
    session_factory,
    *,
    owner_id: str,
    runtime_status: str = "running",
    runtime_instance_id: str | None = None,
    mount_status: str = "ready",
    mount_active_revision: int = 1,
    mount_desired_revision: int = 1,
    mount_observed_revision: int = 1,
    access_desired_revision: int = 1,
    access_observed_revision: int = 1,
    provisioner: str = "docker",
    runtime_desired_revision: int = 1,
    runtime_observed_revision: int = 1,
) -> str:
    workspace_id = str(uuid4())
    instance_id = (
        runtime_instance_id if runtime_instance_id is not None else str(uuid4())
    )
    with session_factory() as db:
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Availability",
                runtime="universal",
                provisioner=provisioner,
                runtime_status=runtime_status,
                runtime_instance_id=instance_id,
                runtime_control_instance_id=instance_id,
                runtime_control_token_hash="a" * 64,
                runtime_desired_revision=runtime_desired_revision,
                runtime_observed_revision=runtime_observed_revision,
                knowledge_base_mount_active_revision=mount_active_revision,
                knowledge_base_mount_desired_revision=mount_desired_revision,
                knowledge_base_mount_observed_revision=mount_observed_revision,
                knowledge_base_mount_sync_status=mount_status,
                knowledge_base_mount_active_snapshot=[],
                knowledge_base_mount_candidate_snapshot=(
                    [] if mount_status in {"applying", "compensating"} else None
                ),
                knowledge_base_mount_failed_snapshot=(
                    [] if mount_status == "degraded" else None
                ),
                knowledge_base_mount_error_code=(
                    "KB_MOUNT_SOURCE_INVALID" if mount_status == "degraded" else None
                ),
                runtime_access_revision=access_desired_revision,
                runtime_access_observed_revision=access_observed_revision,
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        db.commit()
    return workspace_id


def _seed_failed_access_job(
    session_factory,
    *,
    workspace_id: str,
    target_revision: int,
) -> str:
    job_id = str(uuid4())
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy=workspace.provisioner,
                status="failed",
                retries=0,
                target_revision=target_revision,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id=f"failed-{job_id}",
                root_correlation_id=f"root-{job_id}",
                job_metadata={"attempt": 0},
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                error_code="WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED",
            )
        )
        db.commit()
    return job_id


def _seed_queued_access_job(
    session_factory,
    *,
    workspace_id: str,
    target_revision: int,
) -> str:
    job_id = str(uuid4())
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy=workspace.provisioner,
                status="queued",
                retries=0,
                target_revision=target_revision,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id=f"queued-{job_id}",
                root_correlation_id=f"root-{job_id}",
                job_metadata={"attempt": 0, "reason": "membership_change"},
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()
    return job_id


def test_mount_degradation_does_not_block_global_workspace_availability(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        mount_status="degraded",
        mount_active_revision=1,
        mount_desired_revision=2,
        mount_observed_revision=1,
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "ready"
    assert result.reason_code == "WORKSPACE_READY"
    assert result.allowed_actions == []
    assert result.deletion.availability == "ready"
    assert result.deletion.allowed_actions == ["delete"]
    assert result.deletion.phase is None
    assert result.knowledge_mount_status.status == "degraded"
    assert result.knowledge_mount_status.desired_revision == 2
    assert result.knowledge_mount_status.observed_revision == 1
    assert result.knowledge_mount_status.last_known_good_revision == 1
    assert result.knowledge_mount_status.error_code == "KB_MOUNT_SOURCE_INVALID"


def test_running_workspace_with_execution_plane_drift_allows_only_deletion(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="drift-owner")
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
    )
    observer = MagicMock()
    observer.observe.return_value = ExecutionPlaneObservation.drift()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(
            db,
            execution_plane_observer=observer,
        ).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "blocked"
    assert result.reason_code == "WORKSPACE_EXECUTION_PLANE_DRIFT"
    assert result.retryable is False
    assert result.allowed_actions == []
    assert result.retry_after_ms is None
    assert result.deletion.allowed_actions == ["delete"]
    with session_factory() as db:
        assert db.get(db_models.Workspace, workspace_id).runtime_status == "running"


def test_provider_observation_unavailable_is_retryable_without_recovery_action(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="observation-owner")
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
    )
    observer = MagicMock()
    observer.observe.return_value = ExecutionPlaneObservation.unavailable()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(
            db,
            execution_plane_observer=observer,
        ).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "transitioning"
    assert result.reason_code == "WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE"
    assert result.retryable is False
    assert result.allowed_actions == []
    assert result.retry_after_ms == 1500
    assert result.deletion.allowed_actions == ["delete"]


def test_active_mount_apply_runtime_revision_does_not_block_workspace(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        mount_status="applying",
        mount_active_revision=1,
        mount_desired_revision=2,
        mount_observed_revision=1,
        runtime_desired_revision=2,
        runtime_observed_revision=1,
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="knowledge_base_mount_reconcile",
                strategy=workspace.provisioner,
                status="queued",
                retries=0,
                target_revision=2,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id="mount-apply",
                root_correlation_id="mount-apply",
                job_metadata={
                    "attempt": 0,
                    "mount_action": "apply_candidate",
                    "mutation_action": "attach",
                },
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "ready"
    assert result.reason_code == "WORKSPACE_READY"
    assert result.knowledge_mount_status.status == "syncing"


def test_restarting_reason_precedes_inactive_access_failure(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status="restarting",
        access_desired_revision=2,
        access_observed_revision=1,
    )
    _seed_failed_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "transitioning"
    assert result.reason_code == "WORKSPACE_RUNTIME_RESTARTING"
    assert result.retryable is False
    assert result.allowed_actions == ["return"]


@pytest.mark.parametrize(
    ("runtime_status", "expected_availability", "expected_reason", "expected_actions"),
    (
        (
            "stopped",
            "stopped",
            "WORKSPACE_RUNTIME_STOPPED",
            ["start", "return"],
        ),
        (
            "error",
            "blocked",
            "WORKSPACE_RUNTIME_ERROR",
            ["retry", "rebuild", "return"],
        ),
    ),
)
def test_inactive_runtime_access_job_does_not_hide_lifecycle_actions(
    test_app,
    create_user,
    runtime_status,
    expected_availability,
    expected_reason,
    expected_actions,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status=runtime_status,
        access_desired_revision=2,
        access_observed_revision=1,
    )
    _seed_queued_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.runtime_instance_id = None
        workspace.runtime_control_instance_id = None
        workspace.runtime_control_token_hash = None
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == expected_availability
    assert result.reason_code == expected_reason
    assert result.allowed_actions == expected_actions


def test_old_failed_access_revision_does_not_mask_current_recycle(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        access_desired_revision=3,
        access_observed_revision=1,
    )
    _seed_failed_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy=workspace.provisioner,
                status="queued",
                retries=0,
                target_revision=3,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id="current-access",
                root_correlation_id="current-access",
                job_metadata={"attempt": 0, "reason": "membership_change"},
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "transitioning"
    assert result.reason_code == "WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS"


def test_running_kubernetes_revision_divergence_reconciles_before_ready(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        provisioner="kubernetes",
        runtime_desired_revision=2,
        runtime_observed_revision=1,
    )
    custom_resources = MagicMock()
    custom_resources.fetch_workspace_status_snapshot.return_value = object()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(
            db,
            custom_resource_service=custom_resources,
        ).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    custom_resources.fetch_workspace_status_snapshot.assert_called_once_with(
        workspace_id
    )
    custom_resources.apply_workspace_status_snapshot.assert_called_once()
    assert result.availability == "transitioning"
    assert result.reason_code == "WORKSPACE_RUNTIME_RESTARTING"


def test_deleting_reason_precedes_access_failure(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status="deleting",
        access_desired_revision=2,
        access_observed_revision=1,
    )
    _seed_failed_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.availability == "deleting"
    assert result.reason_code == "WORKSPACE_DELETING"
    assert result.allowed_actions == ["return"]
    assert result.deletion.availability == "blocked"
    assert result.deletion.allowed_actions == ["retry"]
    assert result.deletion.status == "failed"
    assert result.deletion.error_code == "WORKSPACE_DELETE_ATTEMPT_UNAVAILABLE"


def test_availability_projects_queued_workspace_deletion(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status="deleting",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="workspace_delete",
                strategy=workspace.provisioner,
                status="queued",
                retries=0,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id="delete-queued",
                root_correlation_id="delete-queued",
                job_metadata={
                    "attempt": 0,
                    "intent": "delete",
                    "phase": "queued",
                    "requires_stop": True,
                    "stop_confirmed": False,
                },
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.deletion.availability == "deleting"
    assert result.deletion.allowed_actions == []
    assert result.deletion.phase == "queued"
    assert result.deletion.status == "queued"


def test_availability_projects_failed_workspace_deletion_as_owner_retry(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status="deleting",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="workspace_delete",
                strategy=workspace.provisioner,
                status="failed",
                retries=0,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id="delete-failed",
                root_correlation_id="delete-failed",
                job_metadata={
                    "attempt": 0,
                    "intent": "delete",
                    "phase": "stopping_runtime",
                    "requires_stop": True,
                    "stop_confirmed": False,
                },
                dispatch_attempts=1,
                scheduled_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                error_code="WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED",
            )
        )
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.deletion.availability == "blocked"
    assert result.deletion.allowed_actions == ["retry"]
    assert result.deletion.phase == "stopping_runtime"
    assert result.deletion.status == "failed"
    assert result.deletion.error_code == "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"


def test_rebuild_action_marks_unavailable_instance_as_retryable(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.runtime_instance_id = None
        workspace.runtime_control_instance_id = None
        workspace.runtime_control_token_hash = None
        db.commit()

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).get(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )

    assert result.reason_code == "WORKSPACE_RUNTIME_INSTANCE_UNAVAILABLE"
    assert result.allowed_actions == ["rebuild", "return"]
    assert result.retryable is True


def test_availability_distinguishes_authentication_authorization_and_not_found(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)

    with session_factory() as db:
        service = WorkspaceAvailabilityService(db)
        with pytest.raises(WorkspaceAvailabilityError) as unauthenticated:
            service.get(
                actor=None,
                workspace_id=str(uuid4()),
            )
        with pytest.raises(WorkspaceAvailabilityError) as invalid_principal:
            service.get(
                actor="invalid-principal",
                workspace_id=str(uuid4()),
            )
        with pytest.raises(WorkspaceAvailabilityError) as missing:
            service.get(
                actor=actor_from_valid_user(actor),
                workspace_id=str(uuid4()),
            )

    assert (unauthenticated.value.code, unauthenticated.value.http_status) == (
        "WORKSPACE_AUTHENTICATION_REQUIRED",
        401,
    )
    assert (invalid_principal.value.code, invalid_principal.value.http_status) == (
        "WORKSPACE_AUTHENTICATION_REQUIRED",
        401,
    )
    assert (missing.value.code, missing.value.http_status) == (
        "WORKSPACE_ACCESS_DENIED",
        404,
    )


def test_access_retry_creates_immutable_child_job(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        access_desired_revision=2,
        access_observed_revision=1,
    )
    failed_job_id = _seed_failed_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )
    published: list[str] = []
    monkeypatch.setattr(
        WorkspaceAvailabilityService,
        "_publish_after_commit",
        staticmethod(published.append),
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).request_action(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
            action="retry",
            correlation_id="availability-retry",
        )

    assert result.action == "retry"
    assert result.job_id != failed_job_id
    assert published == [result.job_id]
    with session_factory() as db:
        failed_job = db.get(db_models.WorkspaceRuntimeJob, failed_job_id)
        retry_job = db.get(db_models.WorkspaceRuntimeJob, result.job_id)
        assert failed_job.status == "failed"
        assert retry_job.status == "queued"
        assert retry_job.retry_of_job_id == failed_job_id
        assert retry_job.root_correlation_id == failed_job.root_correlation_id
        assert retry_job.job_metadata["attempt"] == 1


def test_access_failure_rebuild_routes_to_full_generation_job(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user)
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        access_desired_revision=2,
        access_observed_revision=1,
    )
    failed_job_id = _seed_failed_access_job(
        session_factory,
        workspace_id=workspace_id,
        target_revision=2,
    )
    published: list[str] = []
    monkeypatch.setattr(
        WorkspaceAvailabilityService,
        "_publish_after_commit",
        staticmethod(published.append),
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).request_action(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
            action="rebuild",
            correlation_id="availability-rebuild",
        )

    assert result.action == "rebuild"
    assert published == [result.job_id]
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        rebuild_job = db.get(db_models.WorkspaceRuntimeJob, result.job_id)
        access_retry = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_job_id
            )
        )
        assert workspace.runtime_status == "starting"
        assert rebuild_job.operation == "workspace_start"
        assert rebuild_job.job_metadata["intent"] == "rebuild"
        assert access_retry is not None
        assert access_retry.status == "queued"


@pytest.mark.parametrize(
    ("initial_status", "action", "expected_intent"),
    [
        ("stopped", "start", None),
        ("error", "retry", None),
        ("error", "rebuild", "rebuild"),
    ],
)
def test_lifecycle_availability_actions_route_by_action(
    test_app,
    create_user,
    monkeypatch,
    initial_status: str,
    action: str,
    expected_intent: str | None,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id=f"owner-{action}")
    workspace_id = _seed_workspace(
        session_factory,
        owner_id=actor.id,
        runtime_status=initial_status,
    )
    if initial_status == "stopped":
        with session_factory() as db:
            workspace = db.get(db_models.Workspace, workspace_id)
            workspace.runtime_instance_id = None
            workspace.runtime_control_instance_id = None
            workspace.runtime_control_token_hash = None
            db.commit()
    monkeypatch.setattr(
        WorkspaceAvailabilityService,
        "_publish_after_commit",
        staticmethod(lambda _job_id: None),
    )

    with session_factory() as db:
        result = WorkspaceAvailabilityService(db).request_action(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
            action=action,
            correlation_id=f"availability-{action}",
        )

    assert result.action == action
    with session_factory() as db:
        job = db.get(db_models.WorkspaceRuntimeJob, result.job_id)
        assert job.operation == "workspace_start"
        assert job.job_metadata.get("intent") == expected_intent


def test_machine_readable_manifest_covers_manager_availability_contract() -> None:
    manifest = load_workspace_availability_contract()

    assert manifest["availabilityStates"] == list(get_args(WorkspaceAvailabilityState))
    assert manifest["allowedActions"] == list(get_args(WorkspaceAvailabilityAction))
    assert manifest["knowledgeMountStates"] == list(
        get_args(KnowledgeMountAvailabilityState)
    )
    assert manifest["deletionProjection"]["phases"] == list(
        get_args(WorkspaceDeletionPhase)
    )
    assert manifest["deletionProjection"]["actions"] == list(
        get_args(WorkspaceDeletionAction)
    )
