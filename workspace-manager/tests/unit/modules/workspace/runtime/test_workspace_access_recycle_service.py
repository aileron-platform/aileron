"""Shared Workspace execution-plane access recycle tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.workspace.orchestrator.models import RuntimeContext
from app.modules.workspace.runtime.provisioning import (
    WorkspaceExecutionPlaneIdentity,
    WorkspaceExecutionPlanePlan,
)
from app.modules.workspace.access_recycle import (
    WorkspaceAccessRecycleService,
)
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionPlan,
)
from app.modules.workspace.execution_plane import GenerationOutcome, GenerationState
from app.modules.workspace.runtime.database import RuntimeDatabaseCredential
from app.modules.workspace.runtime.job_execution import WorkspaceRuntimeJobRunResult


def _database_credential(workspace_id: str, runtime_instance_id: str):
    return RuntimeDatabaseCredential(
        workspace_id=workspace_id,
        runtime_instance_id=runtime_instance_id,
        schema_name="ws_test",
        role_name="wsr_test_generation",
        role_prefix="wsr_test_",
        password="scoped-password",
        database_url="postgresql://runtime:scoped@postgres/app",
        secret_name="workspace-generation-0123456789abcdef",
    )


def _seed_access_job(
    session_factory,
    *,
    provisioner: str = "docker",
    runtime_status: str = "running",
    stale_target: bool = False,
) -> tuple[str, str]:
    owner_id = f"owner-{uuid4()}"
    workspace_id = str(uuid4())
    job_id = str(uuid4())
    runtime_instance_id = str(uuid4())
    with session_factory() as db:
        db.add(
            db_models.User(
                id=owner_id,
                oidc_subject=f"kc-{owner_id}",
                username=owner_id,
                email=f"{owner_id}@example.com",
                platform_role="member",
                role_status="valid",
                sync_status="synced",
                identity_enabled=True,
                is_active=True,
            )
        )
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Access recycle",
                runtime="universal",
                provisioner=provisioner,
                target_namespace=("team-a" if provisioner == "kubernetes" else None),
                runtime_status=runtime_status,
                runtime_desired_revision=1,
                runtime_observed_revision=1,
                runtime_instance_id=runtime_instance_id,
                runtime_control_instance_id=runtime_instance_id,
                runtime_control_token_hash="a" * 64,
                runtime_container_id="runtime-old",
                browser_container_id="browser-old",
                canvas_container_id="canvas-old",
                runtime_internal_url="http://runtime-old:3002",
                terminal_internal_url="http://runtime-old:3004",
                knowledge_base_mount_desired_revision=2,
                knowledge_base_mount_observed_revision=2,
                knowledge_base_mount_sync_status="ready",
                runtime_access_revision=1,
                runtime_access_observed_revision=0,
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy=provisioner,
                status="queued",
                retries=0,
                target_revision=1,
                target_runtime_instance_id=(
                    str(uuid4()) if stale_target else runtime_instance_id
                ),
                correlation_id="access-attempt",
                root_correlation_id="access-root",
                job_metadata={
                    "attempt": 0,
                    "reason": "workspace_share_deleted",
                },
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()
    return workspace_id, job_id


def _plan(workspace: db_models.Workspace) -> WorkspaceExecutionPlanePlan:
    runtime_instance_id = str(uuid4())
    workspace.runtime_control_instance_id = runtime_instance_id
    workspace.runtime_control_token_hash = "b" * 64
    return WorkspaceExecutionPlanePlan(
        workspace=WorkspaceExecutionPlaneIdentity(
            id=workspace.id,
            provisioner=workspace.provisioner,
            runtime_instance_id=workspace.runtime_instance_id,
            runtime_container_id=workspace.runtime_container_id,
            browser_container_id=workspace.browser_container_id,
            canvas_container_id=workspace.canvas_container_id,
            runtime_internal_url=workspace.runtime_internal_url,
            terminal_internal_url=workspace.terminal_internal_url,
        ),
        runtime_instance_id=runtime_instance_id,
        mount_revision=workspace.knowledge_base_mount_desired_revision,
        observed_mount_revision=workspace.knowledge_base_mount_observed_revision,
        access_revision=workspace.runtime_access_revision,
        database_credential=_database_credential(workspace.id, runtime_instance_id),
        runtime_control_token="generation-token",
        runtime_context=RuntimeContext(),
        browser_context=RuntimeContext(),
        canvas_context=RuntimeContext(),
    )


def _custom_resource_plan(
    workspace: db_models.Workspace,
) -> WorkspaceCustomResourceExecutionPlan:
    runtime_instance_id = str(uuid4())
    workspace.runtime_control_instance_id = runtime_instance_id
    workspace.runtime_control_token_hash = "b" * 64
    return WorkspaceCustomResourceExecutionPlan(
        workspace_id=workspace.id,
        target_namespace=workspace.target_namespace,
        runtime_instance_id=runtime_instance_id,
        mount_revision=workspace.knowledge_base_mount_desired_revision,
        observed_mount_revision=workspace.knowledge_base_mount_observed_revision,
        access_revision=workspace.runtime_access_revision,
        database_credential=_database_credential(workspace.id, runtime_instance_id),
        runtime_control_token="generation-token",
        setup_script="#!/bin/sh\nexit 0\n",
        manifest={},
    )


def _service(
    db,
    runtime_provision: MagicMock,
    custom_resources: MagicMock | None = None,
) -> WorkspaceAccessRecycleService:
    settings = get_settings().model_copy(
        update={
            "RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS": 60,
            "RUNTIME_READY_TIMEOUT_SECONDS": 1,
        }
    )
    service = WorkspaceAccessRecycleService(
        db,
        settings=settings,
        runtime_provision=runtime_provision,
        custom_resource_service=custom_resources,
        assertion_service_factory=MagicMock(),
    )
    service.best_effort_drain = MagicMock()

    def reconcile(claim, *, attempt):
        assert claim.runtime_instance_id == attempt.runtime_instance_id
        assert claim.identity.runtime_instance_id != claim.runtime_instance_id
        claim.assert_owned()
        return GenerationOutcome(
            state=GenerationState.READY,
            workspace_id=claim.workspace_id,
            generation_id=claim.runtime_instance_id,
            runtime_url=f"http://runtime-{claim.runtime_instance_id}:3002",
        )

    def stage_ready(workspace, outcome):
        generation_id = outcome.generation_id
        workspace.runtime_instance_id = generation_id
        workspace.runtime_control_instance_id = generation_id
        workspace.runtime_container_id = f"runtime-{generation_id}"
        workspace.browser_instance_id = generation_id
        workspace.browser_container_id = f"browser-{generation_id}"
        workspace.canvas_instance_id = generation_id
        workspace.canvas_container_id = f"canvas-{generation_id}"

    service.reconcile = MagicMock(side_effect=reconcile)
    service._stage_ready = MagicMock(side_effect=stage_ready)
    service._discard_ready = MagicMock()
    return service


def test_access_recycle_updates_observed_only_after_complete_generation(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id = _seed_access_job(session_factory)
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id
        runtime_provision = MagicMock()
        runtime_provision._prepare_generation.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        service = _service(db, runtime_provision)
        result = service.reconcile_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        event_types = {
            event.event_type
            for event in db.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.root_correlation_id == "access-root"
                )
            ).all()
        }
        assert job.status == "succeeded"
        assert workspace.runtime_access_observed_revision == 1
        assert workspace.runtime_instance_id != old_instance_id
        assert workspace.runtime_instance_id == workspace.runtime_control_instance_id
        assert workspace.runtime_instance_id == workspace.browser_instance_id
        assert workspace.runtime_instance_id == workspace.canvas_instance_id
        assert old_instance_id not in workspace.runtime_container_id
        assert old_instance_id not in workspace.browser_container_id
        assert old_instance_id not in workspace.canvas_container_id
        assert workspace.runtime_desired_revision == 2
        assert workspace.runtime_observed_revision == 2
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert event_types == {
            "runtime.access_recycle_started",
            "runtime.access_recycle_ready",
        }


def test_kubernetes_access_recycle_uses_provider_neutral_generation_boundary(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id = _seed_access_job(
        session_factory,
        provisioner="kubernetes",
    )
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id
        runtime_provision = MagicMock()
        custom_resources = MagicMock()
        custom_resources._prepare_generation.side_effect = (
            lambda workspace, **_: _custom_resource_plan(workspace)
        )
        service = _service(
            db,
            runtime_provision,
            custom_resources,
        )
        result = service.reconcile_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    service.reconcile.assert_called_once()
    service._stage_ready.assert_called_once()
    service._discard_ready.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_access_observed_revision == 1
        assert workspace.runtime_instance_id != old_instance_id
        assert workspace.runtime_instance_id == workspace.runtime_control_instance_id
        assert workspace.runtime_instance_id == workspace.browser_instance_id
        assert workspace.runtime_instance_id == workspace.canvas_instance_id
        assert workspace.runtime_desired_revision == 2
        assert workspace.runtime_observed_revision == 2


def test_access_recycle_failure_enters_fail_closed_lifecycle_error(test_app) -> None:
    _, session_factory = test_app
    workspace_id, job_id = _seed_access_job(session_factory)
    with session_factory() as db:
        runtime_provision = MagicMock()
        runtime_provision._prepare_generation.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        service = _service(db, runtime_provision)
        service.reconcile.side_effect = None
        service.reconcile.return_value = GenerationOutcome(
            state=GenerationState.FAILED,
            workspace_id=workspace_id,
            generation_id="failed-generation",
            error_code="WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED",
            _error=RuntimeError("sensitive failure"),
        )
        result = service.reconcile_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        event_types = {
            event.event_type
            for event in db.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.root_correlation_id == "access-root"
                )
            ).all()
        }
        assert workspace.runtime_status == "error"
        assert workspace.runtime_access_observed_revision == 0
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED"
        assert event_types == {
            "runtime.access_recycle_started",
            "runtime.access_recycle_failed",
        }


def test_failed_kubernetes_generation_never_advances_observed_revision(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id = _seed_access_job(
        session_factory,
        provisioner="kubernetes",
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        custom_resources = MagicMock()
        custom_resources._prepare_generation.side_effect = (
            lambda workspace, **_: _custom_resource_plan(workspace)
        )
        service = _service(db, runtime_provision, custom_resources)
        service.reconcile.side_effect = None
        service.reconcile.return_value = GenerationOutcome(
            state=GenerationState.FAILED,
            workspace_id=workspace_id,
            generation_id="stale-generation",
            error_code="WORKSPACE_CUSTOM_RESOURCE_NOT_READY",
            _error=RuntimeError("Kubernetes generation evidence is stale"),
        )
        result = service.reconcile_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace.runtime_status == "error"
        assert workspace.runtime_access_revision == 1
        assert workspace.runtime_access_observed_revision == 0
        assert job.status == "failed"


def test_access_recycle_fails_provisioner_mismatch_before_side_effect(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id = _seed_access_job(session_factory)
    with session_factory() as db:
        db.get(db_models.WorkspaceRuntimeJob, job_id).strategy = "kubernetes"
        db.commit()

    runtime_provision = MagicMock()
    custom_resources = MagicMock()
    with session_factory() as db:
        service = _service(db, runtime_provision, custom_resources)
        result = service.reconcile_job(job_id)

        assert result == WorkspaceRuntimeJobRunResult.FAILED
        service.best_effort_drain.assert_not_called()
        assert runtime_provision.mock_calls == []
        assert custom_resources.mock_calls == []

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_PROVISIONER_MISMATCH"
        assert workspace.runtime_status == "error"
        assert workspace.runtime_access_observed_revision == 0


def test_stale_access_target_is_replaced_without_side_effect(test_app) -> None:
    _, session_factory = test_app
    workspace_id, stale_job_id = _seed_access_job(
        session_factory,
        stale_target=True,
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        result = _service(db, runtime_provision).reconcile_job(stale_job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUPERSEDED
    runtime_provision._prepare_generation.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        stale_job = db.get(db_models.WorkspaceRuntimeJob, stale_job_id)
        replacement = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
            )
        )
        assert stale_job.status == "superseded"
        assert replacement.target_runtime_instance_id == workspace.runtime_instance_id
        assert replacement.root_correlation_id == "access-root"


def test_inactive_workspace_access_recycle_remains_queued(test_app) -> None:
    _, session_factory = test_app
    _, job_id = _seed_access_job(
        session_factory,
        runtime_status="stopped",
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        result = _service(db, runtime_provision).reconcile_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.NOT_CLAIMED
    with session_factory() as db:
        assert db.get(db_models.WorkspaceRuntimeJob, job_id).status == "queued"
    runtime_provision._prepare_generation.assert_not_called()
