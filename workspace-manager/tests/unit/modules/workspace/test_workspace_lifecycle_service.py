"""Durable Workspace lifecycle orchestration tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select

import app.modules.workspace.tasks as tasks
from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.settings.models import UserSettings
from app.modules.workspace.capabilities import build_capabilities_from_settings
from app.modules.workspace.catalog import WorkspaceError, WorkspaceService
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionPlan,
    WorkspaceCustomResourceExecutionResult,
    WorkspaceCustomResourceNotReadyError,
)
from app.modules.workspace.lifecycle import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleRunResult,
    WorkspaceLifecycleService,
    _ClaimedLifecycleWork,
    _ClaimedRevisionChild,
    _ProvisionCycle,
)
from app.modules.workspace.models import WorkspaceUpdateRequest
from app.modules.workspace.orchestrator.base import (
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from app.modules.workspace.orchestrator.models import (
    ExecutionPlaneInfo,
    RuntimeContext,
    RuntimeInfo,
)
from app.modules.workspace.runtime.database import RuntimeDatabaseCredential
from app.modules.workspace.runtime.provisioning import (
    WorkspaceExecutionPlaneIdentity,
    WorkspaceExecutionPlanePlan,
)
from app.modules.workspace.runtime.sync import RuntimeCapabilitiesSyncError


def _seed_workspace(
    session_factory,
    *,
    runtime_status: str,
    operation: str | None = None,
    mount_revision: int = 0,
    observed_mount_revision: int = 0,
) -> tuple[str, str, str | None]:
    owner_id = f"owner-{uuid4()}"
    workspace_id = str(uuid4())
    runtime_instance_id = str(uuid4()) if runtime_status != "stopped" else None
    job_id = str(uuid4()) if operation is not None else None
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
                name="Durable lifecycle",
                runtime="universal",
                provisioner="docker",
                runtime_status=runtime_status,
                runtime_instance_id=runtime_instance_id,
                runtime_control_instance_id=runtime_instance_id,
                runtime_control_token_hash=("a" * 64 if runtime_instance_id else None),
                runtime_container_id=("runtime-old" if runtime_instance_id else None),
                browser_container_id=("browser-old" if runtime_instance_id else None),
                canvas_container_id=("canvas-old" if runtime_instance_id else None),
                runtime_internal_url=(
                    "http://runtime-old:3002" if runtime_instance_id else None
                ),
                terminal_internal_url=(
                    "http://runtime-old:3004" if runtime_instance_id else None
                ),
                knowledge_base_mount_desired_revision=mount_revision,
                knowledge_base_mount_observed_revision=observed_mount_revision,
                knowledge_base_mount_sync_status=(
                    "preflighting"
                    if mount_revision != observed_mount_revision
                    else "ready"
                ),
                knowledge_base_mount_active_snapshot=[],
                knowledge_base_mount_candidate_snapshot=(
                    [] if mount_revision != observed_mount_revision else None
                ),
                runtime_access_revision=0,
                runtime_access_observed_revision=0,
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        if job_id is not None:
            db.add(
                db_models.WorkspaceRuntimeJob(
                    id=job_id,
                    workspace_id=workspace_id,
                    operation=operation,
                    strategy="docker",
                    status="queued",
                    retries=0,
                    target_revision=None,
                    target_runtime_instance_id=runtime_instance_id,
                    correlation_id="lifecycle-attempt",
                    root_correlation_id="lifecycle-root",
                    job_metadata={"attempt": 0},
                    dispatch_attempts=0,
                    scheduled_at=datetime.utcnow(),
                )
            )
        if mount_revision != observed_mount_revision:
            db.add(
                db_models.WorkspaceRuntimeJob(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    operation="knowledge_base_mount_reconcile",
                    strategy="docker",
                    status="queued",
                    retries=0,
                    target_revision=mount_revision,
                    target_runtime_instance_id=runtime_instance_id,
                    correlation_id="mount-attempt",
                    root_correlation_id="mount-root",
                    job_metadata={
                        "attempt": 0,
                        "mount_action": "apply_candidate",
                        "mutation_action": "lifecycle_recovery",
                    },
                    dispatch_attempts=0,
                    scheduled_at=datetime.utcnow(),
                )
            )
        db.commit()
    return owner_id, workspace_id, job_id


def _seed_automation_executions(
    session_factory,
    *,
    workspace_id: str,
    owner_id: str,
) -> dict[str, str]:
    now = datetime.utcnow()
    execution_ids: dict[str, str] = {}
    with session_factory() as db:
        for execution_status in ("queued", "running"):
            job_id = f"automation-job-{uuid4()}"
            execution_id = f"automation-execution-{uuid4()}"
            job = db_models.AutomationJob(
                id=job_id,
                workspace_id=workspace_id,
                creator_user_id=owner_id,
                name=f"{execution_status} automation",
                description=None,
                prompt="run workspace automation",
                status="active",
                trigger="manual",
                schedule="manual",
                exact=False,
                agentic_tool="codex",
                model="test-model",
                agent_config={},
                worktree_key=f"automation/{job_id}",
                worktree_branch=f"automation/{job_id}",
                notification_config={},
                next_run_at=now,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
            db.add(job)
            db.add(
                db_models.AutomationExecution(
                    id=execution_id,
                    job_id=job_id,
                    workspace_id=workspace_id,
                    status=execution_status,
                    trigger="manual",
                    scheduled_for=now,
                    queued_at=now,
                    runner_instance_id=(
                        f"runner-{uuid4()}" if execution_status == "running" else None
                    ),
                    claim_request_id=(
                        f"claim-{uuid4()}" if execution_status == "running" else None
                    ),
                    started_at=now if execution_status == "running" else None,
                    finished_at=None,
                    cancel_requested_at=None,
                    principal_user_id_snapshot=owner_id,
                    prompt_snapshot="run workspace automation",
                    agentic_tool_snapshot="codex",
                    model_snapshot="test-model",
                    agent_config_snapshot={},
                    worktree_key_snapshot=f"automation/{job_id}",
                    error_code=None,
                    error_message=None,
                    notification_status=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            execution_ids[execution_status] = execution_id
        db.commit()
    return execution_ids


def _runtime_info(identifier: str, port: int) -> RuntimeInfo:
    return RuntimeInfo(
        identifier=identifier,
        internal_url=f"http://{identifier}:{port}",
        extra_info={"container_name": identifier},
    )


def _execution_plane(
    runtime_instance_id: str | None = None,
) -> ExecutionPlaneInfo:
    return ExecutionPlaneInfo(
        runtime_instance_id=runtime_instance_id or str(uuid4()),
        runtime=_runtime_info("runtime-new", 3002),
        browser=_runtime_info("browser-new", 6080),
        canvas=_runtime_info("canvas-new", 3003),
    )


def _plan(
    workspace: db_models.Workspace,
    runtime_instance_id: str | None = None,
) -> WorkspaceExecutionPlanePlan:
    prepared_instance_id = runtime_instance_id or str(uuid4())
    workspace.runtime_control_instance_id = prepared_instance_id
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
        runtime_instance_id=prepared_instance_id,
        mount_revision=workspace.knowledge_base_mount_desired_revision,
        observed_mount_revision=workspace.knowledge_base_mount_observed_revision,
        access_revision=workspace.runtime_access_revision,
        database_credential=RuntimeDatabaseCredential(
            workspace_id=workspace.id,
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            schema_name="ws_test",
            role_name="wsr_test_generation",
            role_prefix="wsr_test_",
            password="scoped-password",
            database_url="postgresql://runtime:scoped@postgres/app",
            secret_name="workspace-runtime-db-test",
        ),
        runtime_control_token="generation-token",
        runtime_context=RuntimeContext(),
        browser_context=RuntimeContext(),
        canvas_context=RuntimeContext(),
    )


def _runtime_replacement_plan(
    workspace: db_models.Workspace,
    runtime_instance_id: str,
) -> WorkspaceExecutionPlanePlan:
    plan = _plan(workspace, runtime_instance_id)
    return WorkspaceExecutionPlanePlan(
        workspace=plan.workspace,
        runtime_instance_id=runtime_instance_id,
        mount_revision=plan.mount_revision,
        observed_mount_revision=plan.observed_mount_revision,
        access_revision=plan.access_revision,
        database_credential=RuntimeDatabaseCredential(
            workspace_id=workspace.id,
            runtime_instance_id=runtime_instance_id,
            schema_name="ws_test",
            role_name="wsr_test_generation",
            role_prefix="wsr_test_",
            password="scoped-password",
            database_url="postgresql://runtime:scoped@postgres/app",
            secret_name="workspace-runtime-db-test",
        ),
        runtime_control_token=plan.runtime_control_token,
        runtime_context=plan.runtime_context,
        browser_context=plan.browser_context,
        canvas_context=plan.canvas_context,
    )


def _custom_resource_runtime_replacement_plan(
    workspace: db_models.Workspace,
    runtime_instance_id: str,
) -> WorkspaceCustomResourceExecutionPlan:
    workspace.runtime_control_instance_id = runtime_instance_id
    workspace.runtime_control_token_hash = "b" * 64
    return WorkspaceCustomResourceExecutionPlan(
        workspace_id=workspace.id,
        target_namespace="workspaces",
        runtime_instance_id=runtime_instance_id,
        mount_revision=workspace.knowledge_base_mount_desired_revision,
        observed_mount_revision=workspace.knowledge_base_mount_observed_revision,
        access_revision=workspace.runtime_access_revision,
        database_credential=RuntimeDatabaseCredential(
            workspace_id=workspace.id,
            runtime_instance_id=runtime_instance_id,
            schema_name="ws_test",
            role_name="wsr_test_generation",
            role_prefix="wsr_test_",
            password="scoped-password",
            database_url="postgresql://runtime:scoped@postgres/app",
            secret_name="workspace-runtime-db-test",
        ),
        runtime_control_token="generation-token",
        setup_script="#!/bin/sh\nexit 0\n",
        manifest={},
    )


def _service(
    db,
    *,
    runtime_provision: MagicMock | None = None,
    custom_resources: MagicMock | None = None,
    drain_service: MagicMock | None = None,
    runtime_database_service: MagicMock | None = None,
    runtime_sync: MagicMock | None = None,
) -> WorkspaceLifecycleService:
    settings = get_settings().model_copy(
        update={
            "RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS": 60,
            "RUNTIME_READY_TIMEOUT_SECONDS": 1,
        }
    )
    if runtime_sync is None:
        runtime_sync = MagicMock()
        runtime_sync.resolve_workspace_capabilities.return_value = (
            build_capabilities_from_settings(UserSettings())
        )
        runtime_sync.sync_capabilities_to_runtime_generation.return_value = {
            "success": True
        }
    return WorkspaceLifecycleService(
        db,
        settings=settings,
        runtime_provision=(
            runtime_provision if runtime_provision is not None else MagicMock()
        ),
        custom_resources=(
            custom_resources if custom_resources is not None else MagicMock()
        ),
        drain_service=drain_service if drain_service is not None else MagicMock(),
        runtime_database_service=(
            runtime_database_service
            if runtime_database_service is not None
            else MagicMock()
        ),
        runtime_sync=runtime_sync,
    )


def _actor(user_id: str) -> AuthorizationActor:
    return AuthorizationActor(user_id, "member")


def _assert_provision_failure(
    workspace: db_models.Workspace,
    *,
    error_code: str,
) -> None:
    assert workspace.runtime_status == "error"
    assert workspace.bootstrap_status == "error"
    assert workspace.bootstrap_error_code == error_code
    assert workspace.bootstrap_last_transition_at is not None
    for component in ("runtime", "browser", "canvas"):
        assert getattr(workspace, f"{component}_status") == "error"
        assert getattr(workspace, f"{component}_reason") == "ProvisionFailed"
        assert getattr(workspace, f"{component}_error_code") == error_code
        assert getattr(workspace, f"{component}_last_transition_at") is not None
    assert workspace.runtime_instance_id is None
    assert workspace.runtime_control_instance_id is None
    assert workspace.runtime_control_token_hash is None
    assert workspace.runtime_container_id is None
    assert workspace.browser_container_id is None
    assert workspace.canvas_container_id is None
    assert workspace.runtime_internal_url is None
    assert workspace.terminal_internal_url is None
    assert workspace.browser_webrtc_internal_url is None
    assert workspace.canvas_internal_url is None
    assert workspace.bootstrap_observed_revision == 0
    assert workspace.runtime_observed_revision == 0
    assert workspace.browser_observed_revision == 0
    assert workspace.canvas_observed_revision == 0


def test_start_command_is_atomic_and_idempotent(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )
    with session_factory() as db:
        service = _service(db)
        first = service.request_start(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            correlation_id="start-request",
        )
        second = service.request_start(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            correlation_id="duplicate-request",
        )

        assert first.created is True
        assert second.created is False
        assert second.job.id == first.job.id
        assert db.get(db_models.Workspace, workspace_id).runtime_status == "starting"
        assert (
            db.scalar(
                select(func.count(db_models.WorkspaceRuntimeJob.id)).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation == "workspace_start",
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(db_models.AuditEvent.id)).where(
                    db_models.AuditEvent.correlation_id == "start-request"
                )
            )
            == 1
        )


def test_component_restart_advances_only_target_revision_and_is_idempotent(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )

    with session_factory() as db:
        service = _service(db)
        first = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="browser",
            correlation_id="browser-restart",
        )
        second = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="browser",
            correlation_id="browser-restart-duplicate",
        )

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.runtime_desired_revision == 1
        assert workspace.browser_desired_revision == 2
        assert workspace.canvas_desired_revision == 1
        assert workspace.runtime_container_id == "runtime-old"
        assert workspace.canvas_container_id == "canvas-old"
        job = db.get(db_models.WorkspaceRuntimeJob, first.job.id)
        assert job is not None
        assert job.operation == "browser_restart"
        assert job.target_component == "browser"
        assert job.target_revision == 2

    assert first.created is True
    assert second.created is False
    assert first.job.id == second.job.id


def test_component_restart_failure_marks_only_target_component(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.browser_status = "running"
        workspace.canvas_status = "running"
        db.commit()

    runtime_provision = MagicMock()
    runtime_provision.restart_sibling_component.side_effect = RuntimeError(
        "browser restart failed"
    )
    with session_factory() as db:
        service = _service(db, runtime_provision=runtime_provision)
        command = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="browser",
            correlation_id="browser-restart-failure",
        )
        result = service.run_durable_job(command.job.id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_status == "running"
        assert workspace.runtime_error_code is None
        assert workspace.canvas_status == "running"
        assert workspace.canvas_error_code is None
        assert workspace.browser_status == "error"
        assert workspace.browser_error_code == "WORKSPACE_LIFECYCLE_FAILED"
        assert workspace.browser_last_transition_at is not None
        assert workspace.bootstrap_status == "pending"


def test_kubernetes_component_restart_renews_claim_and_uses_ready_timeout(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.provisioner = "kubernetes"
        old_instance_id = workspace.runtime_instance_id
        db.commit()

    custom_resources = MagicMock()
    prepared_plans: list[WorkspaceCustomResourceExecutionPlan] = []

    def prepare(workspace, *, runtime_instance_id):
        plan = _custom_resource_runtime_replacement_plan(
            workspace,
            runtime_instance_id,
        )
        prepared_plans.append(plan)
        return plan

    custom_resources.prepare_execution_plane.side_effect = prepare

    def apply_runtime(
        workspace,
        *,
        component,
        assert_claim,
        runtime_plan,
        max_attempts,
    ):
        assert component == "runtime"
        assert max_attempts == 1
        with session_factory() as state_db:
            state_workspace = state_db.get(db_models.Workspace, workspace_id)
            assert (
                state_workspace.runtime_instance_id == runtime_plan.runtime_instance_id
            )
            assert (
                state_workspace.runtime_control_instance_id
                == runtime_plan.runtime_instance_id
            )
            assert state_workspace.runtime_control_token_hash == "b" * 64
        assert_claim()

    custom_resources.apply_component_desired_revision.side_effect = apply_runtime
    drain_service = MagicMock()
    with session_factory() as db:
        service = _service(
            db,
            custom_resources=custom_resources,
            drain_service=drain_service,
        )
        command = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="runtime",
            correlation_id="runtime-restart",
        )
        result = service.run_durable_job(command.job.id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    assert len(prepared_plans) == 1
    assert prepared_plans[0].runtime_instance_id != old_instance_id
    call = custom_resources.apply_component_desired_revision.call_args
    assert call.kwargs["component"] == "runtime"
    assert call.kwargs["max_attempts"] == 1
    assert call.kwargs["runtime_plan"] is prepared_plans[0]
    drain_service.best_effort_drain.assert_called_once()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_instance_id == prepared_plans[0].runtime_instance_id
        assert workspace.runtime_control_instance_id == workspace.runtime_instance_id
        assert workspace.runtime_container_id == "runtime-old"
        assert workspace.browser_container_id == "browser-old"
        assert workspace.canvas_container_id == "canvas-old"


def test_docker_runtime_restart_rotates_only_runtime_generation(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id

    runtime_provision = MagicMock()
    prepared_plans: list[WorkspaceExecutionPlanePlan] = []

    def prepare(workspace, *, runtime_instance_id):
        plan = _runtime_replacement_plan(workspace, runtime_instance_id)
        prepared_plans.append(plan)
        return plan

    runtime_provision.prepare_execution_plane.side_effect = prepare
    runtime_result = _runtime_info(
        "runtime-new",
        3002,
    )

    def apply_runtime(plan, *, assert_claim):
        with session_factory() as state_db:
            state_workspace = state_db.get(db_models.Workspace, workspace_id)
            assert state_workspace.runtime_instance_id == plan.runtime_instance_id
            assert (
                state_workspace.runtime_control_instance_id == plan.runtime_instance_id
            )
            assert state_workspace.runtime_control_token_hash == "b" * 64
        assert_claim()
        return runtime_result

    runtime_provision.apply_prepared_runtime_component.side_effect = apply_runtime

    def stage(workspace, *, component, result):
        assert component == "runtime"
        workspace.runtime_container_id = result.identifier

    runtime_provision.apply_component_result.side_effect = stage
    drain_service = MagicMock()
    with session_factory() as db:
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=drain_service,
        )
        command = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="runtime",
            correlation_id="runtime-restart",
        )
        result = service.run_durable_job(command.job.id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    assert len(prepared_plans) == 1
    assert prepared_plans[0].runtime_instance_id != old_instance_id
    runtime_provision.apply_prepared_runtime_component.assert_called_once()
    runtime_provision.restart_sibling_component.assert_not_called()
    drain_service.best_effort_drain.assert_called_once()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_instance_id == prepared_plans[0].runtime_instance_id
        assert workspace.runtime_control_instance_id == workspace.runtime_instance_id
        assert workspace.runtime_container_id == "runtime-new"
        assert workspace.browser_container_id == "browser-old"
        assert workspace.canvas_container_id == "canvas-old"


def test_runtime_restart_failure_keeps_activated_generation_for_recovery(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id

    runtime_provision = MagicMock()
    prepared_plans: list[WorkspaceExecutionPlanePlan] = []

    def prepare(workspace, *, runtime_instance_id):
        plan = _runtime_replacement_plan(workspace, runtime_instance_id)
        prepared_plans.append(plan)
        return plan

    runtime_provision.prepare_execution_plane.side_effect = prepare

    def fail_after_start(plan, *, assert_claim):
        with session_factory() as state_db:
            state_workspace = state_db.get(db_models.Workspace, workspace_id)
            assert state_workspace.runtime_instance_id == plan.runtime_instance_id
            assert (
                state_workspace.runtime_control_instance_id == plan.runtime_instance_id
            )
            assert state_workspace.runtime_control_token_hash == "b" * 64
        assert_claim()
        raise RuntimeError("Runtime readiness timed out")

    runtime_provision.apply_prepared_runtime_component.side_effect = fail_after_start

    with session_factory() as db:
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        )
        command = service.request_component_restart(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            component="runtime",
            correlation_id="runtime-restart-failure",
        )
        result = service.run_durable_job(command.job.id)
        job_id = command.job.id

    assert result == WorkspaceLifecycleRunResult.FAILED
    assert len(prepared_plans) == 1
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace.runtime_status == "error"
        assert workspace.runtime_instance_id != old_instance_id
        assert workspace.runtime_instance_id == prepared_plans[0].runtime_instance_id
        assert workspace.runtime_control_instance_id == workspace.runtime_instance_id
        assert workspace.runtime_container_id == "runtime-old"
        assert job.status == "failed"


def test_start_rejects_running_workspace_without_creating_job(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    with session_factory() as db:
        with pytest.raises(WorkspaceLifecycleConflictError) as exc_info:
            _service(db).request_start(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                correlation_id="start-request",
            )

        assert exc_info.value.code == "WORKSPACE_START_NOT_ALLOWED"
        assert db.scalar(select(func.count(db_models.WorkspaceRuntimeJob.id))) == 0


def test_error_rebuild_runs_new_execution_plane_generation_to_ready(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="error",
    )
    with session_factory() as db:
        old_instance_id = db.get(
            db_models.Workspace,
            workspace_id,
        ).runtime_instance_id

    runtime_provision = MagicMock()
    prepared_instance_ids: list[str] = []

    def prepare(workspace, *, runtime_instance_id):
        prepared_instance_ids.append(runtime_instance_id)
        return _plan(workspace, runtime_instance_id)

    runtime_provision.prepare_execution_plane.side_effect = prepare

    def apply(plan, *, assert_claim, timeout_seconds):
        assert timeout_seconds == 1
        with session_factory() as state_db:
            state_workspace = state_db.get(db_models.Workspace, workspace_id)
            assert state_workspace.runtime_instance_id == plan.runtime_instance_id
            assert (
                state_workspace.runtime_control_instance_id == plan.runtime_instance_id
            )
            assert state_workspace.runtime_control_token_hash == "b" * 64
        assert_claim()
        return ExecutionPlaneInfo(
            runtime_instance_id=plan.runtime_instance_id,
            runtime=_runtime_info("runtime-rebuilt", 3002),
            browser=_runtime_info("browser-rebuilt", 6080),
            canvas=_runtime_info("canvas-rebuilt", 3003),
        )

    runtime_provision.apply_execution_plane.side_effect = apply

    def stage(workspace, result):
        workspace.runtime_instance_id = result.runtime_instance_id
        workspace.runtime_container_id = result.runtime.identifier
        workspace.browser_container_id = result.browser.identifier
        workspace.canvas_container_id = result.canvas.identifier

    runtime_provision.apply_execution_plane_result.side_effect = stage

    with session_factory() as db:
        service = _service(db, runtime_provision=runtime_provision)
        command = service.request_rebuild(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            correlation_id="error-rebuild",
        )
        job_id = command.job.id
        result = service.run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    assert len(prepared_instance_ids) == 1
    assert prepared_instance_ids[0] != old_instance_id
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        request_audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.correlation_id == "error-rebuild",
                db_models.AuditEvent.actor_type == "user",
            )
        )
        assert workspace.runtime_status == "running"
        assert workspace.runtime_instance_id == prepared_instance_ids[0]
        assert job.status == "succeeded"
        assert job.job_metadata["intent"] == "rebuild"
        assert request_audit.action == "rebuild_workspace"
        assert request_audit.event_metadata["intent"] == "rebuild"


def test_delete_command_requires_exact_workspace_name(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        with pytest.raises(WorkspaceLifecycleConflictError) as exc_info:
            _service(db).request_delete(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                confirmation_name="durable lifecycle",
                correlation_id="delete-request",
            )

    assert exc_info.value.code == "RESOURCE_DELETE_CONFIRMATION_MISMATCH"


@pytest.mark.parametrize("runtime_status", ("starting", "running"))
def test_delete_command_auto_stops_active_workspace(
    test_app,
    runtime_status: str,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, start_job_id = _seed_workspace(
        session_factory,
        runtime_status=runtime_status,
        operation="workspace_start" if runtime_status == "starting" else None,
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-request",
        )
        delete_job_id = command.job.id

    assert command.created is True
    assert command.runtime_status == "deleting"
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        delete_job = db.get(db_models.WorkspaceRuntimeJob, delete_job_id)
        assert workspace is not None
        assert workspace.runtime_status == "deleting"
        assert delete_job is not None
        assert delete_job.operation == "workspace_delete"
        if start_job_id is not None:
            start_job = db.get(db_models.WorkspaceRuntimeJob, start_job_id)
            assert start_job is not None
            assert start_job.status == "superseded"


def test_delete_command_accepts_stopped_workspace_directly(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-stopped",
        )
        delete_job_id = command.job.id

    assert command.runtime_status == "deleting"
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        delete_job = db.get(db_models.WorkspaceRuntimeJob, delete_job_id)
        assert workspace is not None
        assert workspace.runtime_status == "deleting"
        assert delete_job is not None
        assert delete_job.operation == "workspace_delete"
        assert delete_job.target_runtime_instance_id is None
        request_audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type
                == "workspace.lifecycle_delete_requested",
                db_models.AuditEvent.correlation_id == "delete-stopped",
            )
        )
        assert request_audit is not None
        assert request_audit.event_metadata["job_id"] == delete_job.id


def test_delete_command_reuses_one_in_progress_job(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        service = _service(db)
        first = service.request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-first",
        )
        second = service.request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-duplicate",
        )

    assert first.created is True
    assert second.created is False
    assert second.job.id == first.job.id
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count(db_models.WorkspaceRuntimeJob.id)).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation == "workspace_delete",
                    db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
                )
            )
            == 1
        )
        reuse_audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "workspace.lifecycle_delete_reused",
                db_models.AuditEvent.correlation_id == "delete-duplicate",
            )
        )
        assert reuse_audit is not None
        assert reuse_audit.event_metadata["job_id"] == first.job.id
        assert reuse_audit.event_metadata["reason"] == "idempotent_reuse"


def test_delete_command_converges_queued_and_running_automation_before_delete(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )
    execution_ids = _seed_automation_executions(
        session_factory,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-with-automation",
        )

    assert command.runtime_status == "deleting"
    with session_factory() as db:
        queued = db.get(
            db_models.AutomationExecution,
            execution_ids["queued"],
        )
        running = db.get(
            db_models.AutomationExecution,
            execution_ids["running"],
        )
        assert queued is not None
        assert queued.status == "cancelled"
        assert queued.finished_at is not None
        assert running is not None
        assert running.status == "running"
        assert running.cancel_requested_at is not None
        for execution in (queued, running):
            automation_job = db.get(db_models.AutomationJob, execution.job_id)
            assert automation_job is not None
            assert automation_job.status == "paused"
            assert automation_job.next_run_at is None


def test_deleting_workspace_rejects_other_lifecycle_and_metadata_mutations(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-locks-workspace",
        )

        with pytest.raises(WorkspaceLifecycleConflictError) as start_error:
            _service(db).request_start(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                correlation_id="start-during-delete",
            )
        assert start_error.value.code == "WORKSPACE_START_NOT_ALLOWED"

        with pytest.raises(WorkspaceLifecycleConflictError) as stop_error:
            _service(db).request_stop(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                correlation_id="stop-during-delete",
            )
        assert stop_error.value.code == "WORKSPACE_STOP_NOT_ALLOWED"

        with pytest.raises(WorkspaceLifecycleConflictError) as restart_error:
            _service(db).request_component_restart(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                component="runtime",
                correlation_id="restart-during-delete",
            )
        assert restart_error.value.code == "WORKSPACE_COMPONENT_RESTART_NOT_ALLOWED"

        with pytest.raises(WorkspaceError) as update_error:
            WorkspaceService(db).update(
                workspace_id,
                WorkspaceUpdateRequest(name="Renamed while deleting"),
                actor=_actor(owner_id),
                correlation_id="update-during-delete",
            )
        assert update_error.value.code == "WORKSPACE_LIFECYCLE_BUSY"


def test_superseded_revision_children_keep_operation_specific_targets() -> None:
    service = WorkspaceLifecycleService.__new__(WorkspaceLifecycleService)
    service.db = MagicMock()
    service.job_execution = MagicMock()
    service.audit_events = MagicMock()
    service._record_revision_audit = MagicMock()
    workspace = SimpleNamespace(
        id="workspace-1",
        runtime_instance_id="runtime-instance-2",
        knowledge_base_mount_desired_revision=7,
        runtime_access_revision=3,
    )
    service.db.scalar.return_value = workspace
    service.job_execution.supersede_revision.return_value = (
        MagicMock(),
        MagicMock(),
        True,
    )
    mount_child = _ClaimedRevisionChild(
        job_id="mount-job",
        operation="knowledge_base_mount_reconcile",
        claim_token="mount-claim",
        target_revision=6,
        correlation_id="mount-correlation",
        root_correlation_id="mount-root",
        attempt=1,
    )
    access_child = _ClaimedRevisionChild(
        job_id="access-job",
        operation="workspace_access_recycle",
        claim_token="access-claim",
        target_revision=2,
        correlation_id="access-correlation",
        root_correlation_id="access-root",
        attempt=1,
    )
    work = _ClaimedLifecycleWork(
        job_id="lifecycle-job",
        workspace_id=workspace.id,
        operation="workspace_start",
        claim_token="lifecycle-claim",
        correlation_id="lifecycle-correlation",
        root_correlation_id="lifecycle-root",
        attempt=1,
        workspace_identity=MagicMock(),
    )
    cycle = _ProvisionCycle(
        workspace_id=workspace.id,
        mount_revision=6,
        observed_mount_revision=5,
        access_revision=2,
        workspace_identity=MagicMock(),
        provider_plan=MagicMock(),
        children=(mount_child, access_child),
    )

    with patch("app.modules.workspace.lifecycle.acquire_workspace_transaction_lock"):
        service._supersede_cycle_children(work, cycle)

    calls = service.job_execution.supersede_revision.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["job_id"] == "mount-job"
    assert calls[0].kwargs["target_revision"] == 7
    assert calls[1].kwargs["job_id"] == "access-job"
    assert calls[1].kwargs["target_revision"] == 3
    service._record_revision_audit.assert_has_calls(
        [
            call(
                workspace=workspace,
                child=mount_child,
                suffix="superseded",
                result="success",
                error_code=None,
                reason="desired_revision_advanced",
            ),
            call(
                workspace=workspace,
                child=access_child,
                suffix="superseded",
                result="success",
                error_code=None,
                reason="desired_revision_advanced",
            ),
        ]
    )
    service.db.commit.assert_called_once()


def test_start_worker_absorbs_mount_child_and_opens_gate_after_ready(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
        mount_revision=1,
        observed_mount_revision=0,
    )
    knowledge_base_id = str(uuid4())
    attachment_id = str(uuid4())
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.KnowledgeBase(
                id=knowledge_base_id,
                slug=f"lifecycle-{knowledge_base_id}",
                name="Lifecycle absorption",
                owner_id=owner_id,
            )
        )
        workspace.knowledge_base_mount_candidate_snapshot = [
            {
                "attachmentId": attachment_id,
                "knowledgeBaseId": knowledge_base_id,
                "mountAlias": "lifecycle-absorption",
                "attachedById": owner_id,
            }
        ]
        workspace.runtime_access_revision = 1
        workspace.runtime_access_observed_revision = 0
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=str(uuid4()),
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy=workspace.provisioner,
                status="queued",
                retries=0,
                target_revision=1,
                target_runtime_instance_id=None,
                correlation_id="access-attempt",
                root_correlation_id="access-root",
                job_metadata={"attempt": 0, "reason": "membership_change"},
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        workspace.runtime_reason = "ProvisionFailed"
        workspace.runtime_error_code = "PREVIOUS_PROVISION_FAILURE"
        workspace.bootstrap_status = "error"
        workspace.bootstrap_error_code = "PREVIOUS_PROVISION_FAILURE"
        workspace.browser_status = "error"
        workspace.browser_reason = "ProvisionFailed"
        workspace.browser_error_code = "PREVIOUS_PROVISION_FAILURE"
        workspace.canvas_status = "error"
        workspace.canvas_reason = "ProvisionFailed"
        workspace.canvas_error_code = "PREVIOUS_PROVISION_FAILURE"
        db.commit()
        job_id = (
            _service(db)
            .request_start(
                actor=_actor(owner_id),
                workspace_id=workspace_id,
                correlation_id="lifecycle-root",
            )
            .job.id
        )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()
    runtime_provision.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _plan(
            workspace,
            execution_plane.runtime_instance_id,
        )
    )
    runtime_provision.apply_execution_plane.return_value = execution_plane

    def stage(workspace, result):
        workspace.runtime_instance_id = result.runtime_instance_id
        workspace.runtime_container_id = result.runtime.identifier
        workspace.browser_container_id = result.browser.identifier
        workspace.canvas_container_id = result.canvas.identifier

    runtime_provision.apply_execution_plane_result.side_effect = stage
    drain_service = MagicMock()
    capabilities = build_capabilities_from_settings(UserSettings())
    runtime_sync = MagicMock()
    runtime_sync.resolve_workspace_capabilities.return_value = capabilities
    runtime_sync.sync_capabilities_to_runtime_generation.return_value = {
        "success": True
    }
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=drain_service,
            runtime_sync=runtime_sync,
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id
                )
            ).all()
        )
        assert workspace.runtime_status == "running"
        assert workspace.runtime_reason is None
        assert workspace.runtime_error_code is None
        assert workspace.runtime_last_transition_at is not None
        assert workspace.bootstrap_status == "succeeded"
        assert workspace.bootstrap_error_code is None
        assert workspace.bootstrap_last_transition_at is not None
        assert workspace.browser_status == "running"
        assert workspace.browser_reason is None
        assert workspace.browser_error_code is None
        assert workspace.browser_last_transition_at is not None
        assert workspace.canvas_status == "running"
        assert workspace.canvas_reason is None
        assert workspace.canvas_error_code is None
        assert workspace.canvas_last_transition_at is not None
        assert workspace.knowledge_base_mount_active_revision == 1
        assert workspace.knowledge_base_mount_observed_revision == 1
        assert workspace.knowledge_base_mount_active_snapshot == [
            {
                "attachmentId": attachment_id,
                "knowledgeBaseId": knowledge_base_id,
                "mountAlias": "lifecycle-absorption",
                "attachedById": owner_id,
            }
        ]
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.knowledge_base_mount_sync_status == "ready"
        assert workspace.runtime_access_revision == 1
        assert workspace.runtime_access_observed_revision == 1
        assert workspace.runtime_instance_id == execution_plane.runtime_instance_id
        assert workspace.agentic_capabilities == capabilities.model_dump(by_alias=True)
        attachment = db.get(
            db_models.WorkspaceKnowledgeBaseAttachment,
            attachment_id,
        )
        assert attachment is not None
        assert attachment.workspace_id == workspace_id
        assert attachment.kb_id == knowledge_base_id
        assert attachment.mount_alias == "lifecycle-absorption"
        assert {job.operation: job.status for job in jobs} == {
            "workspace_start": "succeeded",
            "knowledge_base_mount_reconcile": "succeeded",
            "workspace_access_recycle": "succeeded",
        }
        lifecycle_events = {
            event.event_type
            for event in db.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.root_correlation_id == "lifecycle-root"
                )
            ).all()
        }
        mount_events = {
            event.event_type
            for event in db.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.root_correlation_id == "mount-root"
                )
            ).all()
        }
        assert lifecycle_events == {
            "workspace.lifecycle_start_requested",
            "workspace.lifecycle_started",
        }
        assert mount_events == {
            "runtime.mount_sync_started",
            "runtime.mount_sync_ready",
        }
    drain_service.best_effort_drain.assert_called_once()
    runtime_sync.sync_capabilities_to_runtime_generation.assert_called_once_with(
        workspace_id,
        execution_plane.runtime.internal_url,
        execution_plane.runtime_instance_id,
        capabilities,
    )
    assert (
        runtime_provision.apply_execution_plane.call_args.kwargs["timeout_seconds"] == 1
    )


@pytest.mark.parametrize("failure_stage", ["prepare", "apply"])
@pytest.mark.parametrize("offline_promotion", [False, True])
def test_start_failure_automatically_recovers_with_active_mount_snapshot(
    test_app,
    failure_stage: str,
    offline_promotion: bool,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, initial_parent_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
        mount_revision=1,
        observed_mount_revision=0,
    )
    active_attachment_id = str(uuid4())
    active_knowledge_base_id = str(uuid4())
    failed_attachment_id = str(uuid4())
    failed_knowledge_base_id = str(uuid4())
    active_snapshot = [
        {
            "attachmentId": active_attachment_id,
            "knowledgeBaseId": active_knowledge_base_id,
            "mountAlias": "active-docs",
            "attachedById": owner_id,
        }
    ]
    failed_snapshot = [
        {
            "attachmentId": failed_attachment_id,
            "knowledgeBaseId": failed_knowledge_base_id,
            "mountAlias": "failed-docs",
            "attachedById": owner_id,
        }
    ]
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        db.add(
            db_models.KnowledgeBase(
                id=active_knowledge_base_id,
                slug=f"active-{active_knowledge_base_id}",
                name="Active lifecycle recovery",
                owner_id=owner_id,
            )
        )
        workspace.knowledge_base_mount_active_snapshot = active_snapshot
        workspace.knowledge_base_mount_candidate_snapshot = failed_snapshot
        mount_job = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation
                == "knowledge_base_mount_reconcile",
            )
        )
        assert mount_job is not None
        mount_job.job_metadata = {
            **mount_job.job_metadata,
            "offline_promotion": offline_promotion,
        }
        db.commit()

    failed_runtime_provision = MagicMock()
    if failure_stage == "prepare":
        failed_runtime_provision.prepare_execution_plane.side_effect = RuntimeError(
            "candidate preflight failed"
        )
    else:
        failed_runtime_provision.prepare_execution_plane.side_effect = (
            lambda workspace, **_: _plan(workspace)
        )
        failed_runtime_provision.apply_execution_plane.side_effect = RuntimeError(
            "candidate apply failed"
        )
    with session_factory() as db:
        first_result = _service(
            db,
            runtime_provision=failed_runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(initial_parent_id)

    assert first_result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id
                )
            ).all()
        )
        recovery_parent = next(
            job
            for job in jobs
            if job.operation == "workspace_start" and job.id != initial_parent_id
        )
        failed_mount = next(
            job
            for job in jobs
            if job.operation == "knowledge_base_mount_reconcile"
            and job.target_revision == 1
        )
        compensation_mount = next(
            job
            for job in jobs
            if job.operation == "knowledge_base_mount_reconcile"
            and job.target_revision == 2
        )
        initial_parent = db.get(
            db_models.WorkspaceRuntimeJob,
            initial_parent_id,
        )
        assert initial_parent is not None
        assert workspace.runtime_status == "starting"
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert workspace.knowledge_base_mount_active_revision == 0
        assert workspace.knowledge_base_mount_observed_revision == 0
        assert workspace.knowledge_base_mount_active_snapshot == active_snapshot
        assert workspace.knowledge_base_mount_candidate_snapshot == active_snapshot
        assert workspace.knowledge_base_mount_failed_snapshot == failed_snapshot
        assert workspace.knowledge_base_mount_sync_status == "compensating"
        assert (
            db.get(
                db_models.WorkspaceRuntimeJob,
                initial_parent_id,
            ).status
            == "failed"
        )
        assert recovery_parent.status == "queued"
        assert recovery_parent.retry_of_job_id == initial_parent_id
        assert recovery_parent.root_correlation_id == initial_parent.root_correlation_id
        assert failed_mount.status == "failed"
        assert compensation_mount.status == "queued"
        assert compensation_mount.job_metadata["mount_action"] == "compensate"
        assert compensation_mount.retry_of_job_id == failed_mount.id
        assert (
            compensation_mount.root_correlation_id == failed_mount.root_correlation_id
        )
        recovery_parent_id = recovery_parent.id

    applied_snapshots: list[list[dict[str, str | None]]] = []
    recovered_runtime_provision = MagicMock()

    def prepare_active_snapshot(workspace, **_kwargs):
        assert workspace.knowledge_base_mount_sync_status == "compensating"
        assert workspace.knowledge_base_mount_candidate_snapshot == active_snapshot
        applied_snapshots.append(workspace.knowledge_base_mount_candidate_snapshot)
        return _plan(workspace, execution_plane.runtime_instance_id)

    recovered_runtime_provision.prepare_execution_plane.side_effect = (
        prepare_active_snapshot
    )
    execution_plane = _execution_plane()
    recovered_runtime_provision.apply_execution_plane.return_value = execution_plane

    def stage(workspace, result):
        workspace.runtime_instance_id = result.runtime_instance_id
        workspace.runtime_container_id = result.runtime.identifier
        workspace.browser_container_id = result.browser.identifier
        workspace.canvas_container_id = result.canvas.identifier

    recovered_runtime_provision.apply_execution_plane_result.side_effect = stage
    with session_factory() as db:
        recovery_result = _service(
            db,
            runtime_provision=recovered_runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(recovery_parent_id)

    assert recovery_result == WorkspaceLifecycleRunResult.SUCCEEDED
    assert applied_snapshots == [active_snapshot]
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id
                )
            ).all()
        )
        assert workspace.runtime_status == "running"
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert workspace.knowledge_base_mount_active_revision == 2
        assert workspace.knowledge_base_mount_observed_revision == 2
        assert workspace.knowledge_base_mount_active_snapshot == active_snapshot
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.knowledge_base_mount_failed_snapshot == failed_snapshot
        assert workspace.knowledge_base_mount_sync_status == "degraded"
        assert not any(job.status in {"queued", "running"} for job in jobs)


def test_start_rebuilds_failed_access_child_with_immutable_lineage(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    failed_access_id = str(uuid4())
    now = datetime.utcnow()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        workspace.runtime_access_revision = 1
        workspace.runtime_access_observed_revision = 0
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=failed_access_id,
                workspace_id=workspace_id,
                operation="workspace_access_recycle",
                strategy="docker",
                status="failed",
                retries=0,
                target_revision=1,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id="failed-access-attempt",
                root_correlation_id="failed-access-root",
                job_metadata={
                    "attempt": 0,
                    "reason": "membership_change",
                },
                dispatch_attempts=0,
                scheduled_at=now,
                started_at=now,
                finished_at=now,
                error_code="WORKSPACE_ACCESS_RECYCLE_FAILED",
            )
        )
        db.commit()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        _service(db)._ensure_pending_revision_jobs(
            workspace=workspace,
            correlation_id="recovery-parent-attempt",
            scheduled_at=datetime.utcnow(),
        )
        db.commit()

    with session_factory() as db:
        failed_access = db.get(
            db_models.WorkspaceRuntimeJob,
            failed_access_id,
        )
        retry = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_access_id,
            )
        )
        assert failed_access is not None
        assert failed_access.status == "failed"
        assert retry is not None
        assert retry.status == "queued"
        assert retry.target_revision == 1
        assert retry.correlation_id == "recovery-parent-attempt"
        assert retry.root_correlation_id == failed_access.root_correlation_id
        assert retry.retry_of_job_id == failed_access.id


def test_mount_compensation_failure_stops_without_recursive_recovery(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, initial_parent_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
        mount_revision=1,
        observed_mount_revision=0,
    )
    failed_runtime_provision = MagicMock()
    failed_runtime_provision.prepare_execution_plane.side_effect = RuntimeError(
        "execution plane unavailable"
    )

    with session_factory() as db:
        initial_result = _service(
            db,
            runtime_provision=failed_runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(initial_parent_id)

    assert initial_result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        recovery_parent = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == "workspace_start",
                db_models.WorkspaceRuntimeJob.id != initial_parent_id,
            )
        )
        assert recovery_parent is not None
        recovery_parent_id = recovery_parent.id

    with session_factory() as db:
        recovery_result = _service(
            db,
            runtime_provision=failed_runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(recovery_parent_id)

    assert recovery_result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.workspace_id == workspace_id)
                .order_by(db_models.WorkspaceRuntimeJob.scheduled_at)
            ).all()
        )
        lifecycle_jobs = [job for job in jobs if job.operation == "workspace_start"]
        mount_jobs = [
            job for job in jobs if job.operation == "knowledge_base_mount_reconcile"
        ]
        assert workspace is not None
        assert workspace.runtime_status == "error"
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert workspace.knowledge_base_mount_candidate_snapshot is None
        assert workspace.knowledge_base_mount_sync_status == "degraded"
        assert len(lifecycle_jobs) == 2
        assert len(mount_jobs) == 2
        assert all(job.status == "failed" for job in lifecycle_jobs)
        assert all(job.status == "failed" for job in mount_jobs)
        assert mount_jobs[1].retry_of_job_id == mount_jobs[0].id
        assert not any(job.status in {"queued", "running"} for job in jobs)


def test_mount_compensation_recovery_parent_is_republished_after_broker_outage(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    _, workspace_id, initial_parent_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
        mount_revision=1,
        observed_mount_revision=0,
    )
    failed_runtime_provision = MagicMock()
    failed_runtime_provision.prepare_execution_plane.side_effect = RuntimeError(
        "candidate preflight failed"
    )
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=failed_runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(initial_parent_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        recovery_parent = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == "workspace_start",
                db_models.WorkspaceRuntimeJob.id != initial_parent_id,
            )
        )
        assert recovery_parent is not None
        recovery_parent_id = recovery_parent.id

    monkeypatch.setattr(tasks, "SessionLocal", session_factory)

    def publish_failure(_name, _args):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(tasks.current_app, "send_task", publish_failure)
    sweep_started_at = datetime.utcnow()
    first_sweep = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert first_sweep["publish_failed"] == 1
    with session_factory() as db:
        recovery_parent = db.get(
            db_models.WorkspaceRuntimeJob,
            recovery_parent_id,
        )
        assert recovery_parent is not None
        assert recovery_parent.status == "queued"
        assert recovery_parent.dispatch_attempts == 1
        assert recovery_parent.scheduled_at > sweep_started_at
        recovery_parent.scheduled_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

    published: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        tasks.current_app,
        "send_task",
        lambda name, args: published.append((name, args)),
    )
    second_sweep = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert second_sweep["dispatched"] == 1
    assert published == [("workspace_runtime.reconcile_job", [recovery_parent_id])]
    with session_factory() as db:
        recovery_parent = db.get(
            db_models.WorkspaceRuntimeJob,
            recovery_parent_id,
        )
        assert recovery_parent is not None
        assert recovery_parent.status == "queued"
        assert recovery_parent.dispatch_attempts == 1


def test_start_failure_revokes_staged_runtime_control_generation(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    runtime_provision = MagicMock()

    def prepare(workspace, **_kwargs):
        plan = _plan(workspace)
        workspace.runtime_control_instance_id = plan.runtime_instance_id
        workspace.runtime_control_token_hash = "b" * 64
        return plan

    runtime_provision.prepare_execution_plane.side_effect = prepare
    runtime_provision.apply_execution_plane.side_effect = RuntimeError(
        "provision failed"
    )

    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        _assert_provision_failure(
            workspace,
            error_code="WORKSPACE_LIFECYCLE_FAILED",
        )


def test_kubernetes_start_timeout_persists_consistent_terminal_failure(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.provisioner = "kubernetes"
        workspace.target_namespace = "workspace-system"
        db.get(db_models.WorkspaceRuntimeJob, job_id).strategy = "kubernetes"
        db.commit()

    custom_resources = MagicMock()

    def prepare(workspace, *, runtime_instance_id):
        return _custom_resource_runtime_replacement_plan(
            workspace,
            runtime_instance_id,
        )

    custom_resources.prepare_execution_plane.side_effect = prepare
    custom_resources.apply_execution_plane.side_effect = (
        WorkspaceCustomResourceNotReadyError("workspace did not become ready")
    )

    with session_factory() as db:
        result = _service(
            db,
            custom_resources=custom_resources,
            drain_service=MagicMock(),
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        _assert_provision_failure(
            workspace,
            error_code="WORKSPACE_CUSTOM_RESOURCE_NOT_READY",
        )
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_CUSTOM_RESOURCE_NOT_READY"


def test_capabilities_sync_retry_succeeds_without_reprovision_or_termination(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()
    runtime_provision.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _plan(
            workspace,
            execution_plane.runtime_instance_id,
        )
    )
    runtime_provision.apply_execution_plane.return_value = execution_plane

    def stage(workspace, result):
        workspace.runtime_instance_id = result.runtime_instance_id
        workspace.runtime_container_id = result.runtime.identifier
        workspace.browser_container_id = result.browser.identifier
        workspace.canvas_container_id = result.canvas.identifier

    runtime_provision.apply_execution_plane_result.side_effect = stage
    runtime_sync = MagicMock()
    runtime_sync.resolve_workspace_capabilities.return_value = (
        build_capabilities_from_settings(UserSettings())
    )
    runtime_sync.sync_capabilities_to_runtime_generation.side_effect = [
        RuntimeCapabilitiesSyncError("runtime unavailable"),
        {"success": True},
    ]
    sleep = MagicMock()
    monkeypatch.setattr(
        "app.modules.workspace.lifecycle.time.sleep",
        sleep,
    )

    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
            runtime_sync=runtime_sync,
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    runtime_provision.apply_execution_plane.assert_called_once()
    runtime_provision.terminate_execution_plane.assert_not_called()
    assert runtime_sync.sync_capabilities_to_runtime_generation.call_count == 2
    sleep.assert_called_once_with(1)
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_status == "running"
        assert workspace.runtime_instance_id == execution_plane.runtime_instance_id


def test_completion_failure_terminates_exact_provider_result_once(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()
    runtime_provision.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _plan(
            workspace,
            execution_plane.runtime_instance_id,
        )
    )
    runtime_provision.apply_execution_plane.return_value = execution_plane

    with session_factory() as db:
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        )
        service._complete_provision_success = MagicMock(
            side_effect=RuntimeError("completion failed")
        )
        result = service.run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    runtime_provision.apply_execution_plane.assert_called_once()
    runtime_provision.terminate_execution_plane.assert_called_once()
    assert (
        runtime_provision.terminate_execution_plane.call_args.args[1] is execution_plane
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_status == "error"


def test_unverifiable_completion_keeps_provider_result_for_recovery(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()
    runtime_provision.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _plan(workspace)
    )
    runtime_provision.apply_execution_plane.return_value = execution_plane

    with session_factory() as db:
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        )
        service._complete_provision_success = MagicMock(
            side_effect=RuntimeError("completion failed")
        )
        service._provision_completion_state = MagicMock(return_value="unknown")
        result = service.run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.CLAIM_LOST
    runtime_provision.terminate_execution_plane.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        parent = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace.runtime_status == "starting"
        assert parent.status == "running"


def test_completion_commit_ack_failure_preserves_committed_result(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()
    runtime_provision.prepare_execution_plane.side_effect = (
        lambda workspace, **_: _plan(
            workspace,
            execution_plane.runtime_instance_id,
        )
    )
    runtime_provision.apply_execution_plane.return_value = execution_plane

    def stage(workspace, result):
        workspace.runtime_instance_id = result.runtime_instance_id

    runtime_provision.apply_execution_plane_result.side_effect = stage

    with session_factory() as db:
        original_commit = db.commit
        acknowledgement_failed = False
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        )
        original_terminal_audit = service._record_lifecycle_terminal_audit
        completion_pending = False

        def record_terminal_audit(**kwargs):
            nonlocal completion_pending
            if kwargs["result"] == "success":
                completion_pending = True
            return original_terminal_audit(**kwargs)

        service._record_lifecycle_terminal_audit = record_terminal_audit

        def commit_then_drop_acknowledgement():
            nonlocal acknowledgement_failed
            original_commit()
            if completion_pending and not acknowledgement_failed:
                acknowledgement_failed = True
                raise RuntimeError("completion acknowledgement lost")

        db.commit = commit_then_drop_acknowledgement
        result = service.run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    assert acknowledgement_failed is True
    runtime_provision.terminate_execution_plane.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        parent = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace.runtime_status == "running"
        assert workspace.runtime_instance_id == execution_plane.runtime_instance_id
        assert parent.status == "succeeded"


def test_capabilities_sync_failure_retries_and_never_opens_running_gate(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    execution_plane = _execution_plane()
    runtime_provision = MagicMock()

    def prepare(workspace, **_kwargs):
        plan = _plan(workspace)
        workspace.runtime_control_instance_id = plan.runtime_instance_id
        workspace.runtime_control_token_hash = "b" * 64
        return plan

    runtime_provision.prepare_execution_plane.side_effect = prepare
    runtime_provision.apply_execution_plane.return_value = execution_plane
    runtime_sync = MagicMock()
    runtime_sync.resolve_workspace_capabilities.return_value = (
        build_capabilities_from_settings(UserSettings())
    )
    runtime_sync.sync_capabilities_to_runtime_generation.side_effect = (
        RuntimeCapabilitiesSyncError("runtime unavailable")
    )
    sleep = MagicMock()
    monkeypatch.setattr(
        "app.modules.workspace.lifecycle.time.sleep",
        sleep,
    )

    with session_factory() as db:
        service = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
            runtime_sync=runtime_sync,
        )
        result = service.run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    assert runtime_sync.sync_capabilities_to_runtime_generation.call_count == 2
    sleep.assert_called_once_with(1)
    runtime_provision.terminate_execution_plane.assert_called_once()
    runtime_provision.apply_execution_plane_result.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        _assert_provision_failure(
            workspace,
            error_code="RUNTIME_CAPABILITIES_SYNC_FAILED",
        )
        assert workspace.agentic_capabilities is None
        assert job.status == "failed"
        assert job.error_code == "RUNTIME_CAPABILITIES_SYNC_FAILED"


def test_kubernetes_capabilities_failure_preserves_workspace_cr_and_pvcs(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.provisioner = "kubernetes"
        workspace.target_namespace = "workspace-system"
        db.get(db_models.WorkspaceRuntimeJob, job_id).strategy = "kubernetes"
        db.commit()

    custom_resources = MagicMock()
    prepared_plan: WorkspaceCustomResourceExecutionPlan | None = None

    def prepare(workspace, *, runtime_instance_id):
        nonlocal prepared_plan
        prepared_plan = _custom_resource_runtime_replacement_plan(
            workspace,
            runtime_instance_id,
        )
        return prepared_plan

    def apply(plan, **_kwargs):
        return WorkspaceCustomResourceExecutionResult(
            workspace_id=plan.workspace_id,
            target_namespace=plan.target_namespace,
            runtime_instance_id=plan.runtime_instance_id,
            mount_revision=plan.mount_revision,
            access_revision=plan.access_revision,
            runtime_pod_uid="runtime-pod-uid",
            browser_pod_uid="browser-pod-uid",
            canvas_pod_uid="canvas-pod-uid",
            status={"components": {"runtime": {"phase": "Running"}}},
        )

    custom_resources.prepare_execution_plane.side_effect = prepare
    custom_resources.apply_execution_plane.side_effect = apply
    runtime_sync = MagicMock()
    runtime_sync.resolve_workspace_capabilities.return_value = (
        build_capabilities_from_settings(UserSettings())
    )
    runtime_sync.sync_capabilities_to_runtime_generation.side_effect = (
        RuntimeCapabilitiesSyncError("runtime unavailable")
    )
    monkeypatch.setattr(
        "app.modules.workspace.lifecycle.time.sleep",
        lambda _seconds: None,
    )

    with session_factory() as db:
        result = _service(
            db,
            custom_resources=custom_resources,
            drain_service=MagicMock(),
            runtime_sync=runtime_sync,
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    assert prepared_plan is not None
    custom_resources.abandon_execution_plane_generation.assert_called_once()
    custom_resources.delete_persisted_workspace.assert_not_called()
    custom_resources.apply_execution_plane_result.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace.runtime_status == "error"
        assert job.error_code == "RUNTIME_CAPABILITIES_SYNC_FAILED"


def test_kubernetes_capabilities_sync_uses_ready_runtime_internal_url() -> None:
    result = WorkspaceCustomResourceExecutionResult(
        workspace_id="workspace-1",
        target_namespace="workspace-system",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        mount_revision=0,
        access_revision=0,
        runtime_pod_uid="runtime-pod-uid",
        browser_pod_uid="browser-pod-uid",
        canvas_pod_uid="canvas-pod-uid",
        status={"components": {"runtime": {"phase": "Running"}}},
    )

    assert WorkspaceLifecycleService._runtime_capabilities_sync_target(
        result,
        provisioner="kubernetes",
    ) == (
        "http://runtime-workspace-1.workspace-system.svc.cluster.local:3002",
        "11111111-1111-4111-8111-111111111111",
    )


def test_stop_worker_requires_exact_termination_before_clearing_identity(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="stopping",
        operation="workspace_stop",
    )
    runtime_provision = MagicMock()
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    runtime_provision.terminate_current_execution_plane.assert_called_once()
    runtime_provision.prove_execution_plane_absent.assert_called_once()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace.runtime_status == "stopped"
        assert workspace.runtime_instance_id is None
        assert workspace.runtime_control_instance_id is None
        assert workspace.runtime_control_token_hash is None
        assert workspace.runtime_container_id is None
        assert db.get(db_models.WorkspaceRuntimeJob, job_id).status == "succeeded"


def test_kubernetes_stop_preserves_custom_resource_and_workspace_record(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, stop_job_id = _seed_workspace(
        session_factory,
        runtime_status="stopping",
        operation="workspace_stop",
    )
    assert stop_job_id is not None
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, stop_job_id)
        assert workspace is not None
        assert job is not None
        workspace.provisioner = "kubernetes"
        workspace.target_namespace = "workspace-system"
        job.strategy = "kubernetes"
        db.commit()

    custom_resources = MagicMock()
    with session_factory() as db:
        result = _service(
            db,
            custom_resources=custom_resources,
            drain_service=MagicMock(),
        ).run_durable_job(stop_job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    custom_resources.stop_persisted_execution_plane.assert_called_once()
    custom_resources.delete_persisted_workspace.assert_not_called()
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.runtime_status == "stopped"


def test_delete_failure_keeps_workspace_and_references_fail_closed(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="deleting",
        operation="workspace_delete",
    )
    runtime_provision = MagicMock()
    runtime_provision.terminate_current_execution_plane.side_effect = RuntimeError(
        "sensitive backend failure"
    )
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace is not None
        assert workspace.runtime_status == "deleting"
        assert workspace.runtime_instance_id is not None
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_LIFECYCLE_FAILED"
        audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.root_correlation_id == "lifecycle-root",
                db_models.AuditEvent.event_type == "workspace.lifecycle_failed",
            )
        )
        assert audit is not None
        assert audit.error_code == "WORKSPACE_LIFECYCLE_FAILED"
        assert audit.event_metadata["job_id"] == job.id


def test_delete_failure_keeps_workspace_when_termination_is_unconfirmed(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="deleting",
        operation="workspace_delete",
    )
    runtime_provision = MagicMock()
    runtime_provision.prove_execution_plane_absent.side_effect = (
        WorkspaceRuntimeTerminationUnconfirmedError("runtime remains present")
    )
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert workspace is not None
        assert workspace.runtime_status == "deleting"
        assert workspace.runtime_instance_id is not None
        runtime_provision.terminate_current_execution_plane.assert_called_once()
        runtime_provision.prove_execution_plane_absent.assert_called_once()
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"
        audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.root_correlation_id == "lifecycle-root",
                db_models.AuditEvent.event_type == "workspace.lifecycle_failed",
            )
        )
        assert audit is not None
        assert audit.error_code == "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"
        assert audit.event_metadata["job_id"] == job.id


def test_delete_worker_completes_when_execution_plane_is_already_absent(
    test_app,
) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="deleting",
        operation="workspace_delete",
    )
    runtime_provision = MagicMock()
    runtime_database_service = MagicMock()

    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=MagicMock(),
            runtime_database_service=runtime_database_service,
        ).run_durable_job(job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    runtime_provision.terminate_current_execution_plane.assert_called_once()
    runtime_provision.prove_execution_plane_absent.assert_called_once()
    runtime_database_service.drop_workspace.assert_called_once_with(
        workspace_id=workspace_id
    )
    with session_factory() as db:
        assert db.get(db_models.Workspace, workspace_id) is None


def test_delete_worker_fails_closed_when_running_automation_is_not_cancelled(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="running",
    )
    execution_ids = _seed_automation_executions(
        session_factory,
        workspace_id=workspace_id,
        owner_id=owner_id,
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-cancel-automation",
        )
        delete_job_id = command.job.id

    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=MagicMock(),
            drain_service=MagicMock(),
            runtime_database_service=MagicMock(),
        ).run_durable_job(delete_job_id)

    assert result == WorkspaceLifecycleRunResult.FAILED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, delete_job_id)
        running = db.get(
            db_models.AutomationExecution,
            execution_ids["running"],
        )
        assert workspace is not None
        assert workspace.runtime_status == "deleting"
        assert job is not None
        assert job.status == "failed"
        assert job.error_code is not None
        assert running is not None
        assert running.status == "running"


def test_delete_worker_does_not_depend_on_owner_lifetime(test_app) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-owner-lifetime",
        )
        delete_job_id = command.job.id

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        replacement_owner_id = f"replacement-owner-{uuid4()}"
        db.add(
            db_models.User(
                id=replacement_owner_id,
                oidc_subject=f"kc-{replacement_owner_id}",
                username=replacement_owner_id,
                email=f"{replacement_owner_id}@example.com",
                platform_role="member",
                role_status="valid",
                sync_status="synced",
                identity_enabled=True,
                is_active=True,
            )
        )
        workspace.owner_id = replacement_owner_id
        db.commit()

    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=MagicMock(),
            drain_service=MagicMock(),
            runtime_database_service=MagicMock(),
        ).run_durable_job(delete_job_id)

    assert result == WorkspaceLifecycleRunResult.SUCCEEDED
    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        assert workspace is None
        deleted_audit = db.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "workspace.lifecycle_deleted",
                db_models.AuditEvent.correlation_id == "delete-owner-lifetime",
            )
        )
        assert deleted_audit is not None
        assert deleted_audit.event_metadata["job_id"] == delete_job_id
        phase_audits = db.scalars(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "workspace.lifecycle_phase_changed",
                db_models.AuditEvent.correlation_id == "delete-owner-lifetime",
            )
        ).all()
        assert phase_audits
        assert {audit.event_metadata["job_id"] for audit in phase_audits} == {
            delete_job_id
        }


def test_delete_request_exposes_accepted_async_phase_and_clean_error_state(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="stopped",
    )

    with session_factory() as db:
        command = _service(db).request_delete(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            confirmation_name="Durable lifecycle",
            correlation_id="delete-async-phase",
        )
        job = db.get(db_models.WorkspaceRuntimeJob, command.job.id)
        assert job is not None
        assert command.runtime_status == "deleting"
        assert job.status == "queued"
        assert job.started_at is None
        assert job.finished_at is None
        assert job.error_code is None


def test_lifecycle_fails_provisioner_mismatch_before_side_effect(test_app) -> None:
    _, session_factory = test_app
    _, workspace_id, job_id = _seed_workspace(
        session_factory,
        runtime_status="starting",
        operation="workspace_start",
    )
    with session_factory() as db:
        db.get(db_models.WorkspaceRuntimeJob, job_id).strategy = "kubernetes"
        db.commit()

    runtime_provision = MagicMock()
    drain_service = MagicMock()
    with session_factory() as db:
        result = _service(
            db,
            runtime_provision=runtime_provision,
            drain_service=drain_service,
        ).run_durable_job(job_id)

        assert result == WorkspaceLifecycleRunResult.FAILED
        assert runtime_provision.mock_calls == []
        assert drain_service.mock_calls == []

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert job.status == "failed"
        assert job.error_code == "WORKSPACE_PROVISIONER_MISMATCH"
        _assert_provision_failure(
            workspace,
            error_code="WORKSPACE_PROVISIONER_MISMATCH",
        )


def test_error_start_does_not_reopen_failed_mount_candidate(
    test_app,
) -> None:
    _, session_factory = test_app
    owner_id, workspace_id, _ = _seed_workspace(
        session_factory,
        runtime_status="error",
        mount_revision=1,
        observed_mount_revision=0,
    )
    with session_factory() as db:
        failed = db.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation
                == "knowledge_base_mount_reconcile",
            )
        )
        failed.status = "failed"
        failed.error_code = "RUNTIME_MOUNT_FAILED"
        failed.finished_at = datetime.utcnow()
        failed_id = failed.id
        workspace = db.get(db_models.Workspace, workspace_id)
        workspace.knowledge_base_mount_failed_snapshot = (
            workspace.knowledge_base_mount_candidate_snapshot
        )
        workspace.knowledge_base_mount_candidate_snapshot = None
        workspace.knowledge_base_mount_sync_status = "degraded"
        db.commit()

    with session_factory() as db:
        result = _service(db).request_start(
            actor=_actor(owner_id),
            workspace_id=workspace_id,
            correlation_id="error-recovery-start",
        )
        assert result.created is True

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        children = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "knowledge_base_mount_reconcile",
                )
            ).all()
        )
        assert workspace.runtime_status == "starting"
        assert len(children) == 1
        assert children[0].id == failed_id
        assert children[0].status == "failed"
