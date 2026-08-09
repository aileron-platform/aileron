"""Knowledge base mount reconciliation service unit tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.knowledge_base.mount_reconcile import (
    KnowledgeBaseMountReconcileService,
)
from app.modules.workspace.orchestrator.models import (
    RuntimeContext,
    RuntimeInfo,
)
from app.modules.workspace.runtime.provisioning import (
    WorkspaceExecutionPlaneIdentity,
    WorkspaceExecutionPlanePlan,
)
from app.modules.workspace.availability import WorkspaceAvailabilityService
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionPlan,
    WorkspaceCustomResourceService,
    WorkspaceCustomResourceStatusSnapshot,
    WorkspaceKnowledgeBasePreflightError,
)
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
        secret_name="workspace-runtime-db-test",
    )


def _runtime_info(identifier: str, port: int) -> RuntimeInfo:
    return RuntimeInfo(
        identifier=identifier,
        internal_url=f"http://{identifier}:{port}",
        extra_info={"container_name": identifier},
    )


def _seed_mount_job(
    session_factory,
    *,
    provisioner: str = "docker",
    runtime_status: str = "running",
    offline_promotion: bool = False,
) -> tuple[str, str, str | None]:
    workspace_id = str(uuid4())
    owner_id = f"owner-{uuid4()}"
    job_id = str(uuid4())
    attachment_id = str(uuid4())
    kb_id = str(uuid4())
    old_instance_id = None if runtime_status == "stopped" else str(uuid4())
    active_revision = 1 if offline_promotion else 0
    desired_revision = active_revision + 1
    attachment_snapshot = {
        "attachmentId": attachment_id,
        "knowledgeBaseId": kb_id,
        "mountAlias": "docs",
        "attachedById": owner_id,
    }
    active_snapshot = [attachment_snapshot] if offline_promotion else []
    candidate_snapshot = [] if offline_promotion else [attachment_snapshot]
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
            db_models.KnowledgeBase(
                id=kb_id,
                owner_id=owner_id,
                slug=f"kb-{kb_id}",
                name="Mounted KB",
                description="",
            )
        )
        workspace = db_models.Workspace(
            id=workspace_id,
            owner_id=owner_id,
            name="Mount reconcile",
            runtime="universal",
            provisioner=provisioner,
            target_namespace=("team-a" if provisioner == "kubernetes" else None),
            runtime_status=runtime_status,
            runtime_desired_revision=1,
            runtime_observed_revision=1,
            runtime_instance_id=old_instance_id,
            runtime_control_instance_id=old_instance_id,
            runtime_control_token_hash=("a" * 64 if old_instance_id else None),
            runtime_container_id=(
                None if runtime_status == "stopped" else "runtime-old"
            ),
            browser_container_id=(
                None if runtime_status == "stopped" else "browser-old"
            ),
            canvas_container_id=(None if runtime_status == "stopped" else "canvas-old"),
            runtime_internal_url=(
                None if runtime_status == "stopped" else "http://runtime-old:3002"
            ),
            terminal_internal_url=(
                None if runtime_status == "stopped" else "http://runtime-old:3004"
            ),
            knowledge_base_mount_active_revision=active_revision,
            knowledge_base_mount_desired_revision=desired_revision,
            knowledge_base_mount_observed_revision=active_revision,
            knowledge_base_mount_sync_status="preflighting",
            knowledge_base_mount_active_snapshot=active_snapshot,
            knowledge_base_mount_candidate_snapshot=candidate_snapshot,
            knowledge_base_mount_failed_snapshot=None,
            runtime_access_revision=0,
            runtime_access_observed_revision=0,
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        db.add(workspace)
        if offline_promotion:
            db.add(
                db_models.WorkspaceKnowledgeBaseAttachment(
                    id=attachment_id,
                    workspace_id=workspace_id,
                    kb_id=kb_id,
                    mount_alias="docs",
                    attached_by_id=owner_id,
                )
            )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=workspace_id,
                operation="knowledge_base_mount_reconcile",
                strategy=provisioner,
                status="queued",
                retries=0,
                target_revision=desired_revision,
                target_runtime_instance_id=old_instance_id,
                correlation_id="mount-attempt",
                root_correlation_id="mount-root",
                job_metadata={
                    "attempt": 0,
                    "mount_action": "apply_candidate",
                    "mutation_action": "detach" if offline_promotion else "attach",
                    **({"offline_promotion": True} if offline_promotion else {}),
                },
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()
    return workspace_id, job_id, attachment_id


def _plan(workspace: db_models.Workspace) -> WorkspaceExecutionPlanePlan:
    new_instance_id = str(uuid4())
    workspace.runtime_control_instance_id = new_instance_id
    workspace.runtime_control_token_hash = "b" * 64
    identity = WorkspaceExecutionPlaneIdentity(
        id=workspace.id,
        provisioner=workspace.provisioner,
        runtime_instance_id=workspace.runtime_instance_id,
        runtime_container_id=workspace.runtime_container_id,
        browser_container_id=workspace.browser_container_id,
        canvas_container_id=workspace.canvas_container_id,
        runtime_internal_url=workspace.runtime_internal_url,
        terminal_internal_url=workspace.terminal_internal_url,
    )
    return WorkspaceExecutionPlanePlan(
        workspace=identity,
        runtime_instance_id=new_instance_id,
        mount_revision=workspace.knowledge_base_mount_desired_revision,
        observed_mount_revision=workspace.knowledge_base_mount_observed_revision,
        access_revision=workspace.runtime_access_revision,
        database_credential=_database_credential(workspace.id, new_instance_id),
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


def _ready_custom_resource(workspace: db_models.Workspace) -> dict[str, object]:
    return {
        "metadata": {"generation": 7},
        "spec": {
            "runtime": {
                "desiredState": "Running",
                "instanceId": workspace.runtime_instance_id,
                "revision": workspace.runtime_observed_revision,
                "mountRevision": workspace.knowledge_base_mount_active_revision,
                "accessRevision": workspace.runtime_access_observed_revision,
            }
        },
        "status": {
            "observedGeneration": 7,
            "phase": "Running",
            "components": {
                "runtime": {
                    "observedRevision": workspace.runtime_observed_revision,
                    "mountObservedRevision": (
                        workspace.knowledge_base_mount_active_revision
                    ),
                    "accessObservedRevision": (
                        workspace.runtime_access_observed_revision
                    ),
                    "phase": "Running",
                    "ready": True,
                    "terminalReady": True,
                    "podUid": "runtime-pod-old",
                }
            },
        },
    }


def _service(
    db,
    runtime_provision: MagicMock,
    custom_resources: MagicMock | None = None,
) -> KnowledgeBaseMountReconcileService:
    settings = get_settings().model_copy(
        update={
            "RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS": 60,
            "RUNTIME_READY_TIMEOUT_SECONDS": 1,
        }
    )
    service = KnowledgeBaseMountReconcileService(
        db,
        settings=settings,
        runtime_provision=runtime_provision,
        custom_resource_service=custom_resources,
        assertion_service_factory=MagicMock(),
    )
    service.best_effort_drain = MagicMock()
    return service


def test_running_mount_reconcile_commits_claim_before_external_io(test_app) -> None:
    _, session_factory = test_app
    workspace_id, job_id, _ = _seed_mount_job(session_factory)
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id
        runtime_provision = MagicMock()
        runtime_provision.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        runtime_result = _runtime_info("runtime-new", 3002)

        def apply_runtime(plan, *, assert_claim):
            assert not db.in_transaction()
            with session_factory() as state_db:
                state_workspace = state_db.get(
                    db_models.Workspace,
                    workspace_id,
                )
                assert state_workspace.knowledge_base_mount_sync_status == "applying"
                assert state_workspace.runtime_instance_id == plan.runtime_instance_id
                assert (
                    state_workspace.runtime_control_instance_id
                    == plan.runtime_instance_id
                )
                assert state_workspace.runtime_control_token_hash == "b" * 64
            assert_claim()
            return runtime_result

        runtime_provision.apply_prepared_runtime_component.side_effect = apply_runtime

        def stage_result(workspace, *, component, result):
            assert component == "runtime"
            workspace.runtime_container_id = result.identifier

        runtime_provision.apply_component_result.side_effect = stage_result
        service = _service(db, runtime_provision)

        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        event_types = {
            event.event_type
            for event in db.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.root_correlation_id == "mount-root"
                )
            ).all()
        }
        assert job.status == "succeeded"
        assert workspace.knowledge_base_mount_active_revision == 1
        assert workspace.knowledge_base_mount_observed_revision == 1
        assert workspace.knowledge_base_mount_sync_status == "ready"
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert len(workspace.knowledge_base_mount_active_snapshot) == 1
        assert (
            db.scalar(
                select(db_models.WorkspaceKnowledgeBaseAttachment).where(
                    db_models.WorkspaceKnowledgeBaseAttachment.workspace_id
                    == workspace_id
                )
            )
            is not None
        )
        assert workspace.runtime_container_id == "runtime-new"
        assert workspace.runtime_instance_id != old_instance_id
        assert workspace.runtime_instance_id == workspace.runtime_control_instance_id
        assert workspace.browser_container_id == "browser-old"
        assert workspace.canvas_container_id == "canvas-old"
        assert workspace.runtime_desired_revision == 2
        assert workspace.runtime_observed_revision == 2
        assert event_types == {
            "runtime.mount_sync_started",
            "runtime.mount_sync_ready",
        }


def test_kubernetes_mount_reconcile_uses_custom_resource_execution_api(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id, _ = _seed_mount_job(
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
        custom_resources.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _custom_resource_plan(workspace)
        )

        def apply(
            workspace,
            *,
            component,
            assert_claim,
            runtime_plan,
            max_attempts,
        ):
            assert not db.in_transaction()
            assert component == "runtime"
            assert isinstance(runtime_plan, WorkspaceCustomResourceExecutionPlan)
            assert max_attempts == 1
            with session_factory() as state_db:
                state_workspace = state_db.get(db_models.Workspace, workspace_id)
                assert (
                    state_workspace.runtime_instance_id
                    == runtime_plan.runtime_instance_id
                )
                assert (
                    state_workspace.runtime_control_instance_id
                    == runtime_plan.runtime_instance_id
                )
                assert state_workspace.runtime_control_token_hash == "b" * 64
            assert_claim()

        custom_resources.apply_component_desired_revision.side_effect = apply
        service = _service(db, runtime_provision, custom_resources)

        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    custom_resources.prepare_execution_plane.assert_called_once()
    custom_resources.apply_component_desired_revision.assert_called_once()
    custom_resources.apply_execution_plane.assert_not_called()
    custom_resources.apply_execution_plane_result.assert_not_called()
    custom_resources.abandon_execution_plane_generation.assert_not_called()
    runtime_provision.prepare_execution_plane.assert_not_called()
    runtime_provision.apply_prepared_runtime_component.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.knowledge_base_mount_active_revision == 1
        assert workspace.knowledge_base_mount_observed_revision == 1
        assert workspace.knowledge_base_mount_sync_status == "ready"
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.runtime_instance_id != old_instance_id
        assert workspace.runtime_instance_id == workspace.runtime_control_instance_id
        assert workspace.runtime_container_id == "runtime-old"
        assert workspace.browser_container_id == "browser-old"
        assert workspace.canvas_container_id == "canvas-old"
        assert workspace.runtime_desired_revision == 2
        assert workspace.runtime_observed_revision == 2


def test_kubernetes_stale_mount_revision_never_terminates_custom_resource(
    test_app,
) -> None:
    _, session_factory = test_app
    _, job_id, _ = _seed_mount_job(
        session_factory,
        provisioner="kubernetes",
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        custom_resources = MagicMock()
        custom_resources.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _custom_resource_plan(workspace)
        )
        custom_resources.apply_component_desired_revision.side_effect = (
            lambda workspace, **_: None
        )
        service = _service(db, runtime_provision, custom_resources)
        service._target_is_current = MagicMock(return_value=False)

        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUPERSEDED
    custom_resources.apply_component_desired_revision.assert_called_once()
    custom_resources.abandon_execution_plane_generation.assert_not_called()
    custom_resources.apply_execution_plane_result.assert_not_called()
    runtime_provision.terminate_execution_plane.assert_not_called()


def test_reconcile_failure_stages_last_known_good_compensation(test_app) -> None:
    _, session_factory = test_app
    workspace_id, job_id, _ = _seed_mount_job(session_factory)

    class ApplyError(RuntimeError):
        code = "KB_MOUNT_SOURCE_INVALID"

    with session_factory() as db:
        runtime_provision = MagicMock()
        runtime_provision.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        runtime_provision.apply_prepared_runtime_component.side_effect = ApplyError(
            "sensitive host path"
        )
        service = _service(db, runtime_provision)
        service._publish_after_commit = MagicMock()
        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        compensation = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.job_metadata["mount_action"].as_string()
                == "compensate",
            )
        )
        assert job.status == "failed"
        assert job.error_code == "KB_MOUNT_SOURCE_INVALID"
        assert workspace.knowledge_base_mount_sync_status == "compensating"
        assert workspace.knowledge_base_mount_error_code == ("KB_MOUNT_SOURCE_INVALID")
        assert len(workspace.knowledge_base_mount_failed_snapshot) == 1
        assert workspace.knowledge_base_mount_candidate_snapshot == []
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert compensation is not None
        assert compensation.status == "queued"
        assert compensation.target_revision == 2
        assert compensation.root_correlation_id == "mount-root"
        assert "sensitive" not in repr(job.job_metadata)


def test_compensation_success_restores_active_snapshot_and_keeps_degraded_state(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, failed_job_id, _ = _seed_mount_job(session_factory)

    with session_factory() as db:
        failed_runtime = MagicMock()
        failed_runtime.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        failed_runtime.apply_prepared_runtime_component.side_effect = RuntimeError(
            "mount apply failed"
        )
        failed_service = _service(db, failed_runtime)
        failed_service._publish_after_commit = MagicMock()

        assert (
            failed_service.reconcile_mount_job(failed_job_id)
            == WorkspaceRuntimeJobRunResult.FAILED
        )

    with session_factory() as db:
        compensation_job = db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.id != failed_job_id,
            )
            .order_by(db_models.WorkspaceRuntimeJob.scheduled_at.desc())
        )
        assert compensation_job is not None
        compensation_job_id = compensation_job.id

    with session_factory() as db:
        runtime_provision = MagicMock()
        runtime_provision.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        runtime_provision.apply_prepared_runtime_component.return_value = _runtime_info(
            "runtime-compensated",
            3002,
        )
        runtime_provision.apply_component_result.side_effect = (
            lambda workspace, *, component, result: setattr(
                workspace,
                "runtime_container_id",
                result.identifier,
            )
        )

        result = _service(db, runtime_provision).reconcile_mount_job(
            compensation_job_id
        )

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        compensation_job = db.get(
            db_models.WorkspaceRuntimeJob,
            compensation_job_id,
        )
        assert compensation_job.status == "succeeded"
        assert workspace.runtime_status == "running"
        assert workspace.knowledge_base_mount_active_revision == 2
        assert workspace.knowledge_base_mount_observed_revision == 2
        assert workspace.knowledge_base_mount_active_snapshot == []
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.knowledge_base_mount_sync_status == "degraded"
        assert len(workspace.knowledge_base_mount_failed_snapshot) == 1
        assert (
            workspace.knowledge_base_mount_error_code
            == "WORKSPACE_KB_MOUNT_RECONCILE_FAILED"
        )


def test_kubernetes_double_patch_failure_blocks_stale_custom_resource(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, candidate_job_id, _ = _seed_mount_job(
        session_factory,
        provisioner="kubernetes",
    )

    class PatchError(RuntimeError):
        code = "WORKSPACE_CUSTOM_RESOURCE_PATCH_FAILED"

    custom_resources = MagicMock()
    custom_resources.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _custom_resource_plan(workspace)
    )
    custom_resources.apply_component_desired_revision.side_effect = PatchError(
        "Workspace CR PATCH failed"
    )

    with session_factory() as db:
        candidate_service = _service(db, MagicMock(), custom_resources)
        candidate_service._publish_after_commit = MagicMock()
        candidate_result = candidate_service.reconcile_mount_job(candidate_job_id)

    assert candidate_result == WorkspaceRuntimeJobRunResult.FAILED
    with session_factory() as db:
        compensation_job = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.job_metadata["mount_action"].as_string()
                == "compensate",
            )
        )
        assert compensation_job is not None
        compensation_job_id = compensation_job.id

    with session_factory() as db:
        compensation_service = _service(db, MagicMock(), custom_resources)
        compensation_result = compensation_service.reconcile_mount_job(
            compensation_job_id
        )

    assert compensation_result == WorkspaceRuntimeJobRunResult.FAILED
    assert custom_resources.apply_component_desired_revision.call_count == 2

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        mount_jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "knowledge_base_mount_reconcile",
                )
                .order_by(db_models.WorkspaceRuntimeJob.scheduled_at)
            ).all()
        )
        assert workspace.runtime_desired_revision == 3
        assert workspace.runtime_observed_revision == 1
        assert workspace.runtime_status == "error"
        assert workspace.runtime_control_instance_id == workspace.runtime_instance_id
        assert workspace.knowledge_base_mount_sync_status == "degraded"
        assert len(mount_jobs) == 2
        assert all(job.status == "failed" for job in mount_jobs)
        assert {job.root_correlation_id for job in mount_jobs} == {"mount-root"}

        status_service = WorkspaceCustomResourceService(db)
        status_service.fetch_workspace_status_snapshot = MagicMock(
            return_value=WorkspaceCustomResourceStatusSnapshot(
                workspace_id=workspace.id,
                resource_name=f"workspace-{workspace.id}",
                namespace=status_service.settings.RUNTIME_K8S_NAMESPACE,
                custom_resource=_ready_custom_resource(workspace),
            )
        )
        availability = WorkspaceAvailabilityService(
            db,
            custom_resource_service=status_service,
        ).get(
            actor=AuthorizationActor(
                user_id=workspace.owner_id,
                platform_role="member",
            ),
            workspace_id=workspace.id,
        )

    assert availability.availability == "blocked"
    assert availability.reason_code == "WORKSPACE_RUNTIME_ERROR"
    assert availability.knowledge_mount_status.status == "degraded"
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        active_mount_jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "knowledge_base_mount_reconcile",
                    db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
                )
            ).all()
        )
        assert workspace.runtime_desired_revision == 3
        assert workspace.runtime_observed_revision == 1
        assert workspace.knowledge_base_mount_sync_status == "degraded"
        assert active_mount_jobs == []


def test_mount_reconcile_fails_provisioner_mismatch_before_side_effect(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id, _ = _seed_mount_job(session_factory)
    with session_factory() as db:
        db.get(db_models.WorkspaceRuntimeJob, job_id).strategy = "kubernetes"
        db.commit()

    runtime_provision = MagicMock()
    custom_resources = MagicMock()
    with session_factory() as db:
        service = _service(db, runtime_provision, custom_resources)
        service._publish_after_commit = MagicMock()
        result = service.reconcile_mount_job(job_id)

        assert result == WorkspaceRuntimeJobRunResult.FAILED
        service.best_effort_drain.assert_not_called()
        assert runtime_provision.mock_calls == []
        assert custom_resources.mock_calls == []

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_PROVISIONER_MISMATCH"
        assert workspace.knowledge_base_mount_sync_status == "compensating"
        assert (
            workspace.knowledge_base_mount_error_code
            == "WORKSPACE_PROVISIONER_MISMATCH"
        )


def test_stopped_candidate_promotion_requires_absence_proof_and_replaces_active_rows(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id, attachment_id = _seed_mount_job(
        session_factory,
        runtime_status="stopped",
        offline_promotion=True,
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        runtime_provision.prove_execution_plane_absent.side_effect = (
            lambda _identity, *, assert_claim: assert_claim()
        )
        service = _service(db, runtime_provision)
        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    runtime_provision.preflight_knowledge_base_mounts.assert_called_once()
    runtime_provision.apply_execution_plane.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert db.get(db_models.WorkspaceKnowledgeBaseAttachment, attachment_id) is None
        assert job.status == "succeeded"
        assert workspace.runtime_status == "stopped"
        assert workspace.knowledge_base_mount_active_revision == 2
        assert workspace.knowledge_base_mount_observed_revision == 2
        assert workspace.knowledge_base_mount_active_snapshot == []
        assert workspace.knowledge_base_mount_sync_status == "ready"


def test_kubernetes_stopped_candidate_promotion_preserves_cr_and_proves_pods_absent(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id, attachment_id = _seed_mount_job(
        session_factory,
        provisioner="kubernetes",
        runtime_status="stopped",
        offline_promotion=True,
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        custom_resources = MagicMock()
        custom_resources.prove_workspace_pods_absent.side_effect = (
            lambda **kwargs: kwargs["assert_claim"]()
        )
        result = _service(
            db,
            runtime_provision,
            custom_resources,
        ).reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.SUCCEEDED
    runtime_provision.preflight_knowledge_base_mounts.assert_called_once()
    custom_resources.prove_workspace_pods_absent.assert_called_once()
    proof_call = custom_resources.prove_workspace_pods_absent.call_args
    assert proof_call.kwargs["workspace_id"] == workspace_id
    custom_resources.prove_execution_plane_absent.assert_not_called()
    custom_resources.apply_execution_plane.assert_not_called()
    runtime_provision.prove_execution_plane_absent.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert db.get(db_models.WorkspaceKnowledgeBaseAttachment, attachment_id) is None
        assert workspace.knowledge_base_mount_active_revision == 2
        assert workspace.knowledge_base_mount_observed_revision == 2
        assert workspace.knowledge_base_mount_sync_status == "ready"


def test_kubernetes_stopped_pvc_preflight_failure_preserves_last_known_good_snapshot(
    test_app,
) -> None:
    _, session_factory = test_app
    workspace_id, job_id, attachment_id = _seed_mount_job(
        session_factory,
        provisioner="kubernetes",
        runtime_status="stopped",
        offline_promotion=True,
    )

    with session_factory() as db:
        runtime_provision = MagicMock()
        custom_resources = MagicMock()
        custom_resources.preflight_knowledge_base_mounts.side_effect = (
            WorkspaceKnowledgeBasePreflightError(
                "Shared knowledge base PVC is not bound"
            )
        )
        service = _service(db, runtime_provision, custom_resources)
        service._publish_after_commit = MagicMock()

        result = service.reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.FAILED
    runtime_provision.preflight_knowledge_base_mounts.assert_called_once()
    custom_resources.preflight_knowledge_base_mounts.assert_called_once()
    custom_resources.prove_workspace_pods_absent.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        attachment = db.get(
            db_models.WorkspaceKnowledgeBaseAttachment,
            attachment_id,
        )
        assert job.status == "failed"
        assert job.error_code == "KB_MOUNT_SOURCE_INVALID"
        assert attachment is not None
        assert workspace.knowledge_base_mount_active_revision == 1
        assert workspace.knowledge_base_mount_observed_revision == 1
        assert len(workspace.knowledge_base_mount_active_snapshot) == 1
        assert workspace.knowledge_base_mount_failed_snapshot == []
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.knowledge_base_mount_sync_status == "degraded"


def test_stopped_regular_mount_job_remains_queued(test_app) -> None:
    _, session_factory = test_app
    _, job_id, _ = _seed_mount_job(
        session_factory,
        runtime_status="stopped",
    )
    with session_factory() as db:
        runtime_provision = MagicMock()
        result = _service(db, runtime_provision).reconcile_mount_job(job_id)

    assert result == WorkspaceRuntimeJobRunResult.NOT_CLAIMED
    with session_factory() as db:
        assert db.get(db_models.WorkspaceRuntimeJob, job_id).status == "queued"
    runtime_provision.prepare_execution_plane.assert_not_called()
