"""Durable Workspace lifecycle command and worker orchestration."""

from __future__ import annotations

import logging
import re
import shutil
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.knowledge_base.mount_reconcile import (
    KnowledgeBaseMountReconcileService,
)
from app.modules.knowledge_base.mount_snapshot import canonical_mount_snapshot
from app.modules.workspace.advisory_lock import (
    WorkspaceAdvisoryLockLostError,
    WorkspaceAdvisoryLockUnavailableError,
    acquire_workspace_transaction_lock,
    workspace_session_advisory_lock,
)
from app.modules.workspace.browser_connectivity_reconcile import (
    enqueue_docker_browser_connectivity_reconcile,
)
from app.modules.workspace.capabilities import WorkspaceCapabilities
from app.modules.workspace.catalog import (
    WORKSPACE_ACCESS_DENIED_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
    WorkspaceAccessDeniedError,
    WorkspaceNotFoundError,
    WorkspaceService,
)
from app.modules.workspace.custom_resources import WorkspaceCustomResourceService
from app.modules.workspace.execution_plane import (
    GenerationClaim,
    GenerationOutcome,
    GenerationState,
    WorkspaceExecutionPlane,
)
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.orchestrator.models import RuntimeInfo
from app.modules.workspace.runtime.database import (
    WorkspaceRuntimeDatabaseService,
)
from app.modules.workspace.runtime.job_execution import (
    ComponentJobClaim,
    JobExecutionOutcome,
    JobTerminalState,
    RuntimeJobClaimLostError,
    WorkspaceRuntimeJobExecution,
)
from app.modules.workspace.runtime.job_repository import (
    BROWSER_RESTART,
    CANVAS_RESTART,
    COMPONENT_OPERATIONS,
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
    RUNTIME_RESTART,
    WORKSPACE_ACCESS_RECYCLE,
    WORKSPACE_DELETE,
    WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS,
    WORKSPACE_DELETE_PHASE_DELETING_RESOURCES,
    WORKSPACE_DELETE_PHASE_FINALIZING,
    WORKSPACE_DELETE_PHASE_QUEUED,
    WORKSPACE_DELETE_PHASE_STOPPING_RUNTIME,
    WORKSPACE_LIFECYCLE_OPERATIONS,
    WORKSPACE_PROVISIONER_MISMATCH,
    WORKSPACE_START,
    WORKSPACE_STOP,
    WorkspaceRuntimeJobRepository,
)
from app.modules.workspace.runtime.provisioning import (
    RuntimeProvisionService,
    WorkspaceExecutionPlaneIdentity,
)
from app.modules.workspace.runtime.sync import (
    RuntimeCapabilitiesSyncError,
    RuntimeSyncService,
)

logger = logging.getLogger(__name__)

_SERVICE_ACTOR_ID = "workspace-lifecycle-reconciler"
_STABLE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_LIFECYCLE_TARGET_STATUS = {
    WORKSPACE_START: "starting",
    WORKSPACE_STOP: "stopping",
    WORKSPACE_DELETE: "deleting",
}
_REQUEST_EVENT = {
    WORKSPACE_START: "workspace.lifecycle_start_requested",
    WORKSPACE_STOP: "workspace.lifecycle_stop_requested",
    WORKSPACE_DELETE: "workspace.lifecycle_delete_requested",
}
_SUCCESS_EVENT = {
    WORKSPACE_START: "workspace.lifecycle_started",
    WORKSPACE_STOP: "workspace.lifecycle_stopped",
    WORKSPACE_DELETE: "workspace.lifecycle_deleted",
}
_COMMAND_ACTION = {
    WORKSPACE_START: "start_workspace",
    WORKSPACE_STOP: "stop_workspace",
    WORKSPACE_DELETE: "delete_workspace",
}
_NOT_ALLOWED_CODE = {
    WORKSPACE_START: "WORKSPACE_START_NOT_ALLOWED",
    WORKSPACE_STOP: "WORKSPACE_STOP_NOT_ALLOWED",
    WORKSPACE_DELETE: "WORKSPACE_DELETE_NOT_ALLOWED",
}
_COMPONENT_RESTART_OPERATION = {
    "runtime": RUNTIME_RESTART,
    "browser": BROWSER_RESTART,
    "canvas": CANVAS_RESTART,
}
_PROVISION_FAILURE_REASON = "ProvisionFailed"

DELETE_PHASE_CANCELLING_AUTOMATIONS = WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS
DELETE_PHASE_QUEUED = WORKSPACE_DELETE_PHASE_QUEUED
DELETE_PHASE_STOPPING_RUNTIME = WORKSPACE_DELETE_PHASE_STOPPING_RUNTIME
DELETE_PHASE_DELETING_RESOURCES = WORKSPACE_DELETE_PHASE_DELETING_RESOURCES
DELETE_PHASE_FINALIZING = WORKSPACE_DELETE_PHASE_FINALIZING


class WorkspaceLifecycleRunResult(str, Enum):
    """Stable Celery worker result."""

    NOT_CLAIMED = "not_claimed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CLAIM_LOST = "claim_lost"
    SUPERSEDED = "superseded"


class _ProvisionCompletionState(str, Enum):
    """Persisted outcome after a provisioning completion acknowledgement fails."""

    COMMITTED = "committed"
    NOT_COMMITTED = "not_committed"
    UNKNOWN = "unknown"


class WorkspaceLifecycleConflictError(RuntimeError):
    """A lifecycle command conflicts with the persisted lifecycle state."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class WorkspaceLifecycleCommandResult:
    """Accepted durable lifecycle command."""

    workspace_id: str
    runtime_status: str
    job: db_models.WorkspaceRuntimeJob
    created: bool
    component: str | None = None
    target_revision: int | None = None


@dataclass
class _ClaimedLifecycleWork:
    job_id: str
    workspace_id: str
    operation: str
    claim_token: str
    correlation_id: str
    root_correlation_id: str
    attempt: int
    workspace_identity: WorkspaceExecutionPlaneIdentity
    phase: str | None = None


@dataclass(frozen=True)
class _ClaimedRevisionChild:
    job_id: str
    operation: str
    claim_token: str
    target_revision: int
    correlation_id: str
    root_correlation_id: str
    attempt: int


@dataclass(frozen=True)
class _ProvisionCycle:
    workspace_id: str
    mount_revision: int
    observed_mount_revision: int
    access_revision: int
    workspace_identity: WorkspaceExecutionPlaneIdentity
    generation_attempt: object
    children: tuple[_ClaimedRevisionChild, ...]


class WorkspaceLifecycleService:
    """Persist lifecycle commands and execute them with lease fencing."""

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        runtime_provision: RuntimeProvisionService | None = None,
        custom_resources: WorkspaceCustomResourceService | None = None,
        execution_plane: WorkspaceExecutionPlane | None = None,
        runtime_database_service: WorkspaceRuntimeDatabaseService | None = None,
        runtime_sync: RuntimeSyncService | None = None,
        automation_execution_service: Any | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.job_execution = WorkspaceRuntimeJobExecution(
            db,
            claim_timeout_seconds=self.settings.RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS,
        )
        self.audit_events = AuditEventService(db)
        self.authorization = AuthorizationOperationPolicy(db)
        self.workspaces = WorkspaceService(db)
        self.runtime_provision = (
            runtime_provision
            if runtime_provision is not None
            else RuntimeProvisionService(db)
        )
        self.custom_resources = (
            custom_resources
            if custom_resources is not None
            else WorkspaceCustomResourceService(db)
        )
        self.execution_plane = (
            execution_plane
            if execution_plane is not None
            else WorkspaceExecutionPlane(
                db,
                settings=self.settings,
                runtime_provision=self.runtime_provision,
                custom_resources=self.custom_resources,
                runtime_database_service=runtime_database_service,
            )
        )
        self._runtime_database_service = runtime_database_service
        self.runtime_sync = runtime_sync or RuntimeSyncService(db)
        if automation_execution_service is None:
            from app.modules.automation.execution import AutomationExecutionService
            from app.modules.automation.repository import AutomationRepository

            automation_execution_service = AutomationExecutionService(
                AutomationRepository(db)
            )
        self.automation_execution_service = automation_execution_service

    def _database_service(self) -> WorkspaceRuntimeDatabaseService:
        if self._runtime_database_service is None:
            self._runtime_database_service = WorkspaceRuntimeDatabaseService()
        return self._runtime_database_service

    def request_start(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> WorkspaceLifecycleCommandResult:
        return self._request_command(
            actor=actor,
            workspace_id=workspace_id,
            operation=WORKSPACE_START,
            correlation_id=correlation_id,
            authorization_operation=OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        )

    def request_rebuild(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> WorkspaceLifecycleCommandResult:
        """Request a new full execution-plane generation."""

        return self._request_command(
            actor=actor,
            workspace_id=workspace_id,
            operation=WORKSPACE_START,
            correlation_id=correlation_id,
            authorization_operation=OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
            allowed_runtime_statuses={"running", "restarting", "error"},
            intent="rebuild",
        )

    def request_stop(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> WorkspaceLifecycleCommandResult:
        return self._request_command(
            actor=actor,
            workspace_id=workspace_id,
            operation=WORKSPACE_STOP,
            correlation_id=correlation_id,
            authorization_operation=OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        )

    def request_component_restart(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        component: str,
        correlation_id: str,
    ) -> WorkspaceLifecycleCommandResult:
        operation = _COMPONENT_RESTART_OPERATION.get(component)
        if operation is None:
            raise ValueError("Workspace component is invalid")
        requested_at = datetime.now(timezone.utc)
        try:
            self._require_authorization_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
            )
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise WorkspaceNotFoundError("Workspace does not exist")
            if workspace.runtime_status != "running":
                raise WorkspaceLifecycleConflictError(
                    "WORKSPACE_COMPONENT_RESTART_NOT_ALLOWED"
                )

            active_job = self.jobs.find_active_component_job(
                workspace_id=workspace.id,
                component=component,
                for_update=True,
            )
            if active_job is not None:
                self.db.commit()
                return WorkspaceLifecycleCommandResult(
                    workspace_id=workspace.id,
                    runtime_status=workspace.runtime_status,
                    job=active_job,
                    created=False,
                    component=component,
                    target_revision=active_job.target_revision,
                )

            revision_attr = f"{component}_desired_revision"
            status_attr = f"{component}_status"
            reason_attr = f"{component}_reason"
            transition_attr = f"{component}_last_transition_at"
            setattr(workspace, revision_attr, getattr(workspace, revision_attr) + 1)
            setattr(workspace, status_attr, "restarting")
            setattr(workspace, reason_attr, "restart_requested")
            setattr(workspace, transition_attr, requested_at)
            enqueue_result = self.jobs.enqueue_component_job(
                workspace=workspace,
                operation=operation,
                correlation_id=correlation_id,
                scheduled_at=requested_at,
            )
            self.db.commit()
            return WorkspaceLifecycleCommandResult(
                workspace_id=workspace.id,
                runtime_status=workspace.runtime_status,
                job=enqueue_result.job,
                created=enqueue_result.created,
                component=component,
                target_revision=enqueue_result.job.target_revision,
            )
        except Exception:
            self.db.rollback()
            raise

    def request_delete(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        confirmation_name: str,
        correlation_id: str,
    ) -> WorkspaceLifecycleCommandResult:
        return self._request_command(
            actor=actor,
            workspace_id=workspace_id,
            operation=WORKSPACE_DELETE,
            correlation_id=correlation_id,
            authorization_operation=OperationId.WORKSPACE_DELETE,
            delete_confirmation_name=confirmation_name,
        )

    def _request_command(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: str,
        correlation_id: str,
        authorization_operation: OperationId,
        allowed_runtime_statuses: set[str] | None = None,
        intent: str | None = None,
        delete_confirmation_name: str | None = None,
    ) -> WorkspaceLifecycleCommandResult:
        if operation not in WORKSPACE_LIFECYCLE_OPERATIONS:
            raise ValueError("Workspace lifecycle operation is invalid")
        requested_at = datetime.now(timezone.utc)
        try:
            self._require_authorization_operation(
                actor,
                workspace_id,
                authorization_operation,
            )
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise WorkspaceNotFoundError("Workspace does not exist")
            target_status = _LIFECYCLE_TARGET_STATUS[operation]
            if operation == WORKSPACE_DELETE:
                if delete_confirmation_name != workspace.name:
                    raise WorkspaceLifecycleConflictError(
                        "RESOURCE_DELETE_CONFIRMATION_MISMATCH"
                    )
                active_delete_job = self.jobs.find_active_lifecycle_job(
                    workspace_id=workspace.id,
                    operation=WORKSPACE_DELETE,
                    for_update=True,
                )
                if workspace.runtime_status == target_status and active_delete_job:
                    self._record_delete_reuse_audit(
                        actor=actor,
                        workspace=workspace,
                        job=active_delete_job,
                        correlation_id=correlation_id,
                    )
                    self.db.commit()
                    self.db.refresh(active_delete_job)
                    return WorkspaceLifecycleCommandResult(
                        workspace_id=workspace.id,
                        runtime_status=workspace.runtime_status,
                        job=active_delete_job,
                        created=False,
                    )
                self.automation_execution_service.converge_workspace_deletion_in_transaction(
                    workspace_id=workspace.id
                )
            active_job = self.jobs.find_active_lifecycle_job(
                workspace_id=workspace.id,
                operation=operation,
                for_update=True,
            )
            if workspace.runtime_status == target_status and active_job is not None:
                if operation == WORKSPACE_DELETE:
                    self._record_delete_reuse_audit(
                        actor=actor,
                        workspace=workspace,
                        job=active_job,
                        correlation_id=correlation_id,
                    )
                self.db.commit()
                self.db.refresh(active_job)
                return WorkspaceLifecycleCommandResult(
                    workspace_id=workspace.id,
                    runtime_status=workspace.runtime_status,
                    job=active_job,
                    created=False,
                )

            if allowed_runtime_statuses is None:
                self._require_command_transition(
                    operation=operation,
                    runtime_status=workspace.runtime_status,
                )
            elif workspace.runtime_status not in allowed_runtime_statuses:
                raise WorkspaceLifecycleConflictError("WORKSPACE_REBUILD_NOT_ALLOWED")
            previous_status = workspace.runtime_status
            if operation == WORKSPACE_DELETE:
                self._supersede_queued_lifecycle_conflicts(
                    workspace=workspace,
                    actor_user_id=actor.user_id,
                    finished_at=requested_at,
                )
            retry_parent = None
            if previous_status == target_status:
                retry_parent = self.jobs.find_latest_failed_job(
                    workspace_id=workspace.id,
                    operation=operation,
                    for_update=True,
                )
            workspace.runtime_status = target_status
            desired_state = "running" if operation == WORKSPACE_START else "stopped"
            if operation in {WORKSPACE_START, WORKSPACE_STOP}:
                workspace.runtime_desired_state = desired_state
                workspace.browser_desired_state = desired_state
                workspace.canvas_desired_state = desired_state
            workspace.updated_at = requested_at
            target_runtime_instance_id = (
                None
                if operation == WORKSPACE_START and previous_status == "stopped"
                else workspace.runtime_instance_id
            )
            delete_metadata: dict[str, Any] | None = None
            if operation == WORKSPACE_DELETE:
                retry_metadata = retry_parent.job_metadata if retry_parent else {}
                delete_metadata = {
                    "intent": "delete",
                    "phase": DELETE_PHASE_QUEUED,
                    "requires_stop": (
                        retry_metadata.get(
                            "requires_stop",
                            previous_status != "stopped"
                            or workspace.runtime_instance_id is not None,
                        )
                    ),
                    "stop_confirmed": bool(retry_metadata.get("stop_confirmed", False)),
                }
            enqueue_result = self.jobs.enqueue_lifecycle_job(
                workspace=workspace,
                operation=operation,
                correlation_id=correlation_id,
                root_correlation_id=(
                    retry_parent.root_correlation_id
                    if retry_parent is not None
                    else correlation_id
                ),
                scheduled_at=requested_at,
                target_runtime_instance_id=target_runtime_instance_id,
                retry_of_job_id=(retry_parent.id if retry_parent is not None else None),
                job_metadata=(
                    delete_metadata
                    if delete_metadata is not None
                    else ({"intent": intent} if intent is not None else None)
                ),
            )
            if operation == WORKSPACE_START and (
                previous_status == "error" or intent == "rebuild"
            ):
                self._ensure_revision_recovery_children(
                    workspace=workspace,
                    correlation_id=correlation_id,
                    requested_at=requested_at,
                )
            self.audit_events.record(
                event_type=_REQUEST_EVENT[operation],
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type="workspace",
                target_id=workspace.id,
                action=(
                    "rebuild_workspace"
                    if intent == "rebuild"
                    else _COMMAND_ACTION[operation]
                ),
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=enqueue_result.job.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "job_id": enqueue_result.job.id,
                    **({"intent": intent} if intent is not None else {}),
                    **(
                        {"phase": delete_metadata["phase"]}
                        if delete_metadata is not None
                        else {}
                    ),
                    **(
                        {"runtime_instance_id": workspace.runtime_instance_id}
                        if workspace.runtime_instance_id
                        else {}
                    ),
                },
            )
            self.db.commit()
            return WorkspaceLifecycleCommandResult(
                workspace_id=workspace.id,
                runtime_status=workspace.runtime_status,
                job=enqueue_result.job,
                created=enqueue_result.created,
            )
        except Exception:
            self.db.rollback()
            raise

    def _record_delete_reuse_audit(
        self,
        *,
        actor: AuthorizationActor,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        correlation_id: str,
    ) -> None:
        """Record an idempotent DELETE reuse without duplicating side effects."""

        attempt = job.job_metadata.get("attempt", 0)
        self.audit_events.record(
            event_type="workspace.lifecycle_delete_reused",
            actor_type="user",
            actor_id=actor.user_id,
            actor_user_id=actor.user_id,
            target_type="workspace",
            target_id=workspace.id,
            action=_COMMAND_ACTION[WORKSPACE_DELETE],
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=job.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "job_id": job.id,
                "attempt": attempt,
                "reason": "idempotent_reuse",
            },
        )

    def _require_authorization_operation(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
    ) -> None:
        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            if exc.http_status == 404:
                raise WorkspaceNotFoundError(WORKSPACE_NOT_FOUND_MESSAGE) from exc
            raise WorkspaceAccessDeniedError(
                WORKSPACE_ACCESS_DENIED_MESSAGE,
                code="WORKSPACE_RUNTIME_ACTION_FORBIDDEN",
            ) from exc

    def _supersede_queued_lifecycle_conflicts(
        self,
        *,
        workspace: db_models.Workspace,
        actor_user_id: str,
        finished_at: datetime,
    ) -> None:
        queued_jobs = list(
            self.db.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation.in_(
                        (
                            WORKSPACE_LIFECYCLE_OPERATIONS
                            | {
                                KNOWLEDGE_BASE_MOUNT_RECONCILE,
                                WORKSPACE_ACCESS_RECYCLE,
                            }
                        )
                        - {WORKSPACE_DELETE}
                    ),
                    db_models.WorkspaceRuntimeJob.status == "queued",
                )
                .order_by(db_models.WorkspaceRuntimeJob.scheduled_at)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )
        for job in queued_jobs:
            if not self.job_execution.finish_queued(
                job_id=job.id,
                state=JobTerminalState.SUPERSEDED,
                finished_at=finished_at,
            ):
                raise RuntimeJobClaimLostError(
                    "Conflicting lifecycle job could not be superseded"
                )
            self.audit_events.record(
                event_type="workspace.lifecycle_superseded",
                actor_type="user",
                actor_id=actor_user_id,
                actor_user_id=actor_user_id,
                target_type="workspace",
                target_id=workspace.id,
                action=_COMMAND_ACTION.get(
                    job.operation,
                    f"supersede_{job.operation}",
                ),
                result="success",
                error_code=None,
                correlation_id=job.correlation_id,
                root_correlation_id=job.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "job_id": job.id,
                    "reason": "workspace_delete_requested",
                },
            )

    @staticmethod
    def _require_command_transition(
        *,
        operation: str,
        runtime_status: str,
    ) -> None:
        allowed = {
            WORKSPACE_START: {"stopped", "error", "starting"},
            WORKSPACE_STOP: {"running", "error", "stopping"},
            WORKSPACE_DELETE: {
                "starting",
                "running",
                "stopping",
                "stopped",
                "restarting",
                "error",
                "deleting",
            },
        }
        if runtime_status not in allowed[operation]:
            raise WorkspaceLifecycleConflictError(_NOT_ALLOWED_CODE[operation])

    def _ensure_revision_recovery_children(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        requested_at: datetime,
    ) -> None:
        self._ensure_revision_jobs(
            workspace=workspace,
            correlation_id=correlation_id,
            scheduled_at=requested_at,
            reason="lifecycle_recovery",
            lock_active_job=True,
        )

    def _ensure_revision_jobs(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        scheduled_at: datetime,
        reason: str,
        lock_active_job: bool,
    ) -> None:
        revisions = (
            (
                KNOWLEDGE_BASE_MOUNT_RECONCILE,
                workspace.knowledge_base_mount_desired_revision,
                workspace.knowledge_base_mount_active_revision,
            ),
            (
                WORKSPACE_ACCESS_RECYCLE,
                workspace.runtime_access_revision,
                workspace.runtime_access_observed_revision,
            ),
        )
        for operation, desired, observed in revisions:
            if desired == observed:
                continue
            active_job_query = (
                select(
                    db_models.WorkspaceRuntimeJob
                    if lock_active_job
                    else db_models.WorkspaceRuntimeJob.id
                )
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation == operation,
                    db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
                )
                .limit(1)
            )
            if lock_active_job:
                active_job_query = active_job_query.with_for_update()
            active = self.db.scalar(active_job_query)
            if active is not None:
                continue
            if operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
                if (
                    workspace.knowledge_base_mount_candidate_snapshot is None
                    or workspace.knowledge_base_mount_sync_status
                    not in {"preflighting", "applying", "compensating"}
                ):
                    continue
                if self._enqueue_current_revision_retry(
                    workspace=workspace,
                    operation=operation,
                    desired_revision=desired,
                    correlation_id=correlation_id,
                    scheduled_at=scheduled_at,
                ):
                    continue
                self.jobs.supersede_queued_and_enqueue_mount_reconcile(
                    workspace=workspace,
                    correlation_id=correlation_id,
                    scheduled_at=scheduled_at,
                    job_metadata={
                        "attempt": 0,
                        "mount_action": (
                            "compensate"
                            if workspace.knowledge_base_mount_sync_status
                            == "compensating"
                            else "apply_candidate"
                        ),
                        "mutation_action": reason,
                    },
                )
            else:
                if self._enqueue_current_revision_retry(
                    workspace=workspace,
                    operation=operation,
                    desired_revision=desired,
                    correlation_id=correlation_id,
                    scheduled_at=scheduled_at,
                ):
                    continue
                self.jobs.supersede_queued_and_enqueue_access_recycle(
                    workspace=workspace,
                    correlation_id=correlation_id,
                    root_correlation_id=correlation_id,
                    scheduled_at=scheduled_at,
                    job_metadata={
                        "attempt": 0,
                        "reason": reason,
                    },
                )

    def _enqueue_current_revision_retry(
        self,
        *,
        workspace: db_models.Workspace,
        operation: str,
        desired_revision: int,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> bool:
        failed = self.jobs.find_latest_failed_job(
            workspace_id=workspace.id,
            operation=operation,
            for_update=True,
        )
        if failed is None or failed.target_revision != desired_revision:
            return False
        return (
            self.jobs.enqueue_retry_for_failed_job(
                failed_job_id=failed.id,
                correlation_id=correlation_id,
                scheduled_at=scheduled_at,
            )
            is not None
        )

    def run_durable_job(self, job_id: str) -> WorkspaceLifecycleRunResult:
        """Claim and execute one lifecycle parent using its database identifier."""

        job = self.db.get(db_models.WorkspaceRuntimeJob, job_id)
        if job is None:
            self.db.rollback()
            return WorkspaceLifecycleRunResult.NOT_CLAIMED
        if job.operation in COMPONENT_OPERATIONS:
            self.db.rollback()
            return self._run_component_job(job_id)
        if job.operation not in WORKSPACE_LIFECYCLE_OPERATIONS:
            self.db.rollback()
            return WorkspaceLifecycleRunResult.NOT_CLAIMED
        workspace_id = job.workspace_id
        self.db.rollback()
        claimed: _ClaimedLifecycleWork | None = None
        try:
            with workspace_session_advisory_lock(
                self.db.get_bind(),
                workspace_id,
            ) as session_lock:
                claimed, terminal_result = self._claim_parent(job_id)
                if terminal_result is not None:
                    return terminal_result
                if claimed is None:
                    return WorkspaceLifecycleRunResult.NOT_CLAIMED
                with self.job_execution.lease(
                    job_id=claimed.job_id,
                    claim_token=claimed.claim_token,
                    session_lock=session_lock,
                ) as assert_parent:
                    if claimed.operation == WORKSPACE_START:
                        return self._run_provisioning_parent(
                            claimed,
                            session_lock=session_lock,
                            assert_parent=assert_parent,
                        )
                    return self._run_termination_parent(
                        claimed,
                        assert_claim=assert_parent,
                    )
        except WorkspaceAdvisoryLockUnavailableError:
            self.db.rollback()
            return WorkspaceLifecycleRunResult.NOT_CLAIMED
        except (RuntimeJobClaimLostError, WorkspaceAdvisoryLockLostError):
            self.db.rollback()
            return WorkspaceLifecycleRunResult.CLAIM_LOST
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "Workspace lifecycle reconcile failed",
                extra={
                    "job_id": job_id,
                    "workspace_id": workspace_id,
                    "error_code": self._stable_error_code(exc),
                    "error_type": type(exc).__name__,
                },
            )
            if claimed is None:
                return WorkspaceLifecycleRunResult.NOT_CLAIMED
            if self._complete_superseded_if_state_advanced(claimed):
                return WorkspaceLifecycleRunResult.SUPERSEDED
            return self._complete_failure(claimed, exc)

    def _run_component_job(self, job_id: str) -> WorkspaceLifecycleRunResult:
        """Apply one component revision without replacing sibling workloads."""

        now = datetime.now(timezone.utc)
        claim_result = self.job_execution.claim_component(job_id, claimed_at=now)
        if claim_result.outcome == JobExecutionOutcome.NOT_CLAIMED:
            return WorkspaceLifecycleRunResult.NOT_CLAIMED
        if claim_result.outcome == JobExecutionOutcome.SUPERSEDED:
            return WorkspaceLifecycleRunResult.SUPERSEDED
        claim = claim_result.claim
        if claim is None:
            raise RuntimeError("Claimed component job is missing its claim")

        try:
            with self.job_execution.lease(
                job_id=claim.job_id,
                claim_token=claim.claim_token,
            ) as assert_claim:
                workspace = self.db.get(db_models.Workspace, claim.workspace_id)
                if workspace is None:
                    self.db.rollback()
                    return WorkspaceLifecycleRunResult.NOT_CLAIMED

                component_result: RuntimeInfo | None = None
                component_instance_id: str | None = None
                runtime_capabilities_snapshot: WorkspaceCapabilities | None = None
                generation_outcome: GenerationOutcome | None = None
                if claim.component == "runtime":
                    workspace_identity = self._execution_identity(workspace)
                    generation_attempt = self.execution_plane._prepare(
                        workspace, str(uuid4())
                    )
                    self.db.commit()
                    generation_outcome = self.execution_plane.reconcile(
                        GenerationClaim(
                            workspace_id=claim.workspace_id,
                            job_id=claim.job_id,
                            assert_owned=assert_claim,
                            runtime_instance_id=self._attempt_generation_id(
                                generation_attempt
                            ),
                            expected_mounted_revision=getattr(
                                generation_attempt, "observed_mount_revision"
                            ),
                            target_mounted_revision=getattr(
                                generation_attempt, "mount_revision"
                            ),
                            identity=workspace_identity,
                        ),
                        attempt=generation_attempt,
                    )
                    generation_outcome.raise_for_failure()
                    runtime_capabilities_snapshot = self._sync_generation_capabilities(
                        workspace_id=claim.workspace_id,
                        outcome=generation_outcome,
                        assert_claim=assert_claim,
                    )
                elif workspace.provisioner == "kubernetes":
                    component_instance_id = str(uuid4())
                    self.custom_resources.apply_component_desired_revision(
                        workspace,
                        component=claim.component,
                        component_instance_id=component_instance_id,
                        assert_claim=assert_claim,
                        max_attempts=max(
                            1,
                            self.settings.RUNTIME_READY_TIMEOUT_SECONDS,
                        ),
                    )
                else:
                    component_result = self.runtime_provision.restart_sibling_component(
                        workspace,
                        component=claim.component,
                        assert_claim=assert_claim,
                    )

                def apply_result(locked_workspace: db_models.Workspace) -> None:
                    self._apply_component_execution_result(
                        locked_workspace,
                        claim=claim,
                        generation_outcome=generation_outcome,
                        component_result=component_result,
                        component_instance_id=component_instance_id,
                    )
                    if runtime_capabilities_snapshot is not None:
                        locked_workspace.agentic_capabilities = (
                            runtime_capabilities_snapshot.model_dump(by_alias=True)
                        )

                outcome = self.job_execution.complete_component(
                    claim,
                    finished_at=datetime.now(timezone.utc),
                    apply_result=apply_result,
                )
                if (
                    outcome == JobExecutionOutcome.SUCCEEDED
                    and claim.component == "browser"
                    and workspace.provisioner == "docker"
                ):
                    enqueue_docker_browser_connectivity_reconcile(claim.workspace_id)
                return WorkspaceLifecycleRunResult(outcome.value)
        except Exception as exc:
            error_code = self._stable_error_code(exc)
            logger.error(
                "Workspace component reconcile failed",
                extra={
                    "job_id": claim.job_id,
                    "workspace_id": claim.workspace_id,
                    "component": claim.component,
                    "error_code": error_code,
                    "error_type": type(exc).__name__,
                },
            )
            self.job_execution.fail_component(
                claim,
                failed_at=datetime.now(timezone.utc),
                error_code=error_code,
            )
            return WorkspaceLifecycleRunResult.FAILED

    def _apply_component_execution_result(
        self,
        workspace: db_models.Workspace,
        *,
        claim: ComponentJobClaim,
        generation_outcome: GenerationOutcome | None,
        component_result: RuntimeInfo | None,
        component_instance_id: str | None,
    ) -> None:
        if generation_outcome is not None:
            self.execution_plane._stage_ready(workspace, generation_outcome)
        elif component_result is not None:
            self.runtime_provision.apply_component_result(
                workspace,
                component=claim.component,
                result=component_result,
            )
        elif component_instance_id is not None:
            setattr(
                workspace,
                f"{claim.component}_instance_id",
                component_instance_id,
            )

    def _claim_parent(
        self,
        job_id: str,
    ) -> tuple[_ClaimedLifecycleWork | None, WorkspaceLifecycleRunResult | None]:
        now = datetime.now(timezone.utc)
        try:
            job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                job is None
                or job.operation not in WORKSPACE_LIFECYCLE_OPERATIONS
                or job.status not in {"queued", "running"}
            ):
                self.db.rollback()
                return None, WorkspaceLifecycleRunResult.NOT_CLAIMED
            acquire_workspace_transaction_lock(self.db, job.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == job.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return None, WorkspaceLifecycleRunResult.NOT_CLAIMED
            if workspace.provisioner != job.strategy:
                return self._fail_lifecycle_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code=WORKSPACE_PROVISIONER_MISMATCH,
                )
            if (
                workspace.runtime_status != _LIFECYCLE_TARGET_STATUS[job.operation]
                or job.target_runtime_instance_id != workspace.runtime_instance_id
            ):
                self.db.rollback()
                return None, WorkspaceLifecycleRunResult.NOT_CLAIMED
            if job.status == "queued":
                claimed_job, claim_token = self.job_execution.claim_revision(
                    job_id=job.id,
                    claimed_at=now,
                    eligible_runtime_statuses={workspace.runtime_status},
                )
                if claimed_job is None:
                    self.db.rollback()
                    return None, WorkspaceLifecycleRunResult.NOT_CLAIMED
            else:
                claim_token = job.claim_token or ""
                if (
                    not claim_token
                    or job.claim_expires_at is None
                    or self._as_utc(job.claim_expires_at) <= now
                ):
                    self.db.rollback()
                    return None, WorkspaceLifecycleRunResult.NOT_CLAIMED
                claimed_job = job
            attempt = int(claimed_job.job_metadata.get("attempt", 0)) + int(
                claimed_job.retries
            )
            self.audit_events.record(
                event_type="workspace.lifecycle_started",
                actor_type="service",
                actor_id=_SERVICE_ACTOR_ID,
                actor_user_id=None,
                target_type="workspace",
                target_id=workspace.id,
                action=_COMMAND_ACTION[claimed_job.operation],
                result="success",
                error_code=None,
                correlation_id=claimed_job.correlation_id,
                root_correlation_id=claimed_job.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "attempt": attempt,
                    **(
                        {"phase": claimed_job.job_metadata["phase"]}
                        if isinstance(claimed_job.job_metadata.get("phase"), str)
                        else {}
                    ),
                    **(
                        {"runtime_instance_id": workspace.runtime_instance_id}
                        if workspace.runtime_instance_id
                        else {}
                    ),
                },
            )
            work = _ClaimedLifecycleWork(
                job_id=claimed_job.id,
                workspace_id=workspace.id,
                operation=claimed_job.operation,
                claim_token=claim_token,
                correlation_id=claimed_job.correlation_id,
                root_correlation_id=claimed_job.root_correlation_id,
                attempt=attempt,
                workspace_identity=self._execution_identity(workspace),
                phase=(
                    claimed_job.job_metadata.get("phase")
                    if isinstance(claimed_job.job_metadata.get("phase"), str)
                    else None
                ),
            )
            self.db.commit()
            return work, None
        except Exception:
            self.db.rollback()
            raise

    def _fail_lifecycle_before_side_effect(
        self,
        *,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        now: datetime,
        error_code: str,
    ) -> tuple[None, WorkspaceLifecycleRunResult]:
        if job.status == "queued":
            transitioned = self.job_execution.finish_queued(
                job_id=job.id,
                state=JobTerminalState.FAILED,
                finished_at=now,
                error_code=error_code,
            )
            lost_result = WorkspaceLifecycleRunResult.NOT_CLAIMED
        else:
            transitioned = bool(job.claim_token) and self.job_execution.finish_claim(
                job_id=job.id,
                claim_token=job.claim_token or "",
                state=JobTerminalState.FAILED,
                finished_at=now,
                error_code=error_code,
            )
            lost_result = WorkspaceLifecycleRunResult.CLAIM_LOST
        if not transitioned:
            self.db.rollback()
            return None, lost_result
        attempt = int(job.job_metadata.get("attempt", 0)) + int(job.retries)
        if job.operation == WORKSPACE_START:
            self._mark_provision_failure(
                workspace,
                error_code=error_code,
                transitioned_at=now,
            )
        elif job.operation != WORKSPACE_DELETE:
            workspace.runtime_status = "error"
        self.audit_events.record(
            event_type="workspace.lifecycle_failed",
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=_COMMAND_ACTION[job.operation],
            result="failure",
            error_code=error_code,
            correlation_id=job.correlation_id,
            root_correlation_id=job.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "attempt": attempt,
                **(
                    {"phase": job.job_metadata["phase"]}
                    if isinstance(job.job_metadata.get("phase"), str)
                    else {}
                ),
            },
        )
        self.db.commit()
        return None, WorkspaceLifecycleRunResult.FAILED

    def _run_provisioning_parent(
        self,
        work: _ClaimedLifecycleWork,
        *,
        session_lock,
        assert_parent: Callable[[], None],
    ) -> WorkspaceLifecycleRunResult:
        while True:
            cycle = self._prepare_provision_cycle(work)
            with ExitStack() as child_leases:
                assertions: list[Callable[[], None]] = []
                for child in cycle.children:
                    assertions.append(
                        child_leases.enter_context(
                            self.job_execution.lease(
                                job_id=child.job_id,
                                claim_token=child.claim_token,
                                session_lock=session_lock,
                            ),
                        )
                    )

                child_assertions = tuple(assertions)

                def assert_claim(
                    assertions_to_check: tuple[Callable[[], None], ...] = (
                        child_assertions
                    ),
                ) -> None:
                    assert_parent()
                    for assert_child in assertions_to_check:
                        assert_child()

                assert_claim()
                outcome = self.execution_plane.reconcile(
                    GenerationClaim(
                        workspace_id=work.workspace_id,
                        job_id=work.job_id,
                        assert_owned=assert_claim,
                        runtime_instance_id=self._attempt_generation_id(
                            cycle.generation_attempt
                        ),
                        expected_mounted_revision=cycle.observed_mount_revision,
                        target_mounted_revision=cycle.mount_revision,
                        identity=cycle.workspace_identity,
                    ),
                    attempt=cycle.generation_attempt,
                )
                outcome.raise_for_failure()
                termination_attempted = False
                completion_attempted = False
                try:
                    assert_claim()
                    capabilities = self._sync_generation_capabilities(
                        workspace_id=work.workspace_id,
                        outcome=outcome,
                        assert_claim=assert_claim,
                    )
                    if not self._provision_target_is_current(work, cycle):
                        termination_attempted = True
                        self.execution_plane._discard_ready(
                            outcome,
                            assert_claim=assert_claim,
                        )
                        if self._complete_superseded_if_state_advanced(work):
                            return WorkspaceLifecycleRunResult.SUPERSEDED
                        self._supersede_cycle_children(work, cycle)
                        continue
                    completion_attempted = True
                    return self._complete_provision_success(
                        work,
                        cycle,
                        outcome,
                        capabilities,
                    )
                except Exception as exc:
                    if completion_attempted:
                        completion_state = self._provision_completion_state(
                            work=work,
                            cycle=cycle,
                            outcome=outcome,
                        )
                        if completion_state == _ProvisionCompletionState.COMMITTED:
                            logger.warning(
                                "Recovered committed Workspace provisioning after "
                                "completion acknowledgement failure",
                                extra={
                                    "workspace_id": work.workspace_id,
                                    "job_id": work.job_id,
                                    "runtime_instance_id": outcome.generation_id,
                                },
                            )
                            return WorkspaceLifecycleRunResult.SUCCEEDED
                        if completion_state == _ProvisionCompletionState.UNKNOWN:
                            raise RuntimeJobClaimLostError(
                                "Provision completion state could not be verified"
                            ) from exc
                    if not termination_attempted:
                        termination_attempted = True
                        self.execution_plane._discard_ready(
                            outcome,
                            assert_claim=assert_claim,
                        )
                    raise

    def _prepare_provision_cycle(
        self,
        work: _ClaimedLifecycleWork,
    ) -> _ProvisionCycle:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            parent = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.id == work.job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                parent is None
                or workspace is None
                or parent.status != "running"
                or parent.claim_token != work.claim_token
                or workspace.runtime_status != _LIFECYCLE_TARGET_STATUS[work.operation]
            ):
                self.db.rollback()
                raise RuntimeJobClaimLostError("Lifecycle parent claim was lost")
            self._ensure_pending_revision_jobs(
                workspace=workspace,
                correlation_id=parent.correlation_id,
                scheduled_at=now,
            )
            children = self._claim_revision_children(
                workspace=workspace,
                parent=parent,
                claimed_at=now,
            )
            workspace_identity = self._execution_identity(workspace)
            generation_attempt = self.execution_plane._prepare(workspace, str(uuid4()))
            cycle = _ProvisionCycle(
                workspace_id=workspace.id,
                mount_revision=workspace.knowledge_base_mount_desired_revision,
                observed_mount_revision=(
                    workspace.knowledge_base_mount_observed_revision
                ),
                access_revision=workspace.runtime_access_revision,
                workspace_identity=workspace_identity,
                generation_attempt=generation_attempt,
                children=tuple(children),
            )
            self.db.commit()
            return cycle
        except Exception:
            self.db.rollback()
            raise

    def _ensure_pending_revision_jobs(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> None:
        self._ensure_revision_jobs(
            workspace=workspace,
            correlation_id=correlation_id,
            scheduled_at=scheduled_at,
            reason="lifecycle_absorption",
            lock_active_job=False,
        )

    def _claim_revision_children(
        self,
        *,
        workspace: db_models.Workspace,
        parent: db_models.WorkspaceRuntimeJob,
        claimed_at: datetime,
    ) -> list[_ClaimedRevisionChild]:
        rows = list(
            self.db.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation.in_(
                        {
                            KNOWLEDGE_BASE_MOUNT_RECONCILE,
                            WORKSPACE_ACCESS_RECYCLE,
                        }
                    ),
                    db_models.WorkspaceRuntimeJob.status == "queued",
                )
                .order_by(db_models.WorkspaceRuntimeJob.operation)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )
        children: list[_ClaimedRevisionChild] = []
        for row in rows:
            row.lifecycle_job_id = parent.id
            self.db.flush()
            claimed, claim_token = self.job_execution.claim_revision(
                job_id=row.id,
                claimed_at=claimed_at,
                eligible_runtime_statuses={workspace.runtime_status},
            )
            if claimed is None:
                raise RuntimeJobClaimLostError("Revision child could not be claimed")
            attempt = int(claimed.job_metadata.get("attempt", 0)) + int(claimed.retries)
            children.append(
                _ClaimedRevisionChild(
                    job_id=claimed.id,
                    operation=claimed.operation,
                    claim_token=claim_token,
                    target_revision=claimed.target_revision or 0,
                    correlation_id=claimed.correlation_id,
                    root_correlation_id=claimed.root_correlation_id,
                    attempt=attempt,
                )
            )
            self._record_revision_audit(
                workspace=workspace,
                child=children[-1],
                suffix="started",
                result="success",
                error_code=None,
            )
        return children

    def _provision_target_is_current(
        self,
        work: _ClaimedLifecycleWork,
        cycle: _ProvisionCycle,
    ) -> bool:
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            parent = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            current = bool(
                parent is not None
                and workspace is not None
                and parent.status == "running"
                and parent.claim_token == work.claim_token
                and workspace.runtime_status == _LIFECYCLE_TARGET_STATUS[work.operation]
                and workspace.knowledge_base_mount_desired_revision
                == cycle.mount_revision
                and workspace.runtime_access_revision == cycle.access_revision
            )
            self.db.rollback()
            return current
        except Exception:
            self.db.rollback()
            raise

    def _supersede_cycle_children(
        self,
        work: _ClaimedLifecycleWork,
        cycle: _ProvisionCycle,
    ) -> None:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise RuntimeJobClaimLostError("Workspace disappeared")
            for child in cycle.children:
                target_revision = (
                    workspace.knowledge_base_mount_desired_revision
                    if child.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE
                    else workspace.runtime_access_revision
                )
                transitioned = self.job_execution.supersede_revision(
                    job_id=child.job_id,
                    claim_token=child.claim_token,
                    target_revision=target_revision,
                    target_runtime_instance_id=workspace.runtime_instance_id,
                    correlation_id=str(uuid4()),
                    scheduled_at=now,
                )
                if transitioned is None:
                    raise RuntimeJobClaimLostError("Revision child claim was lost")
                self._record_revision_audit(
                    workspace=workspace,
                    child=child,
                    suffix="superseded",
                    result="success",
                    error_code=None,
                    reason="desired_revision_advanced",
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _complete_provision_success(
        self,
        work: _ClaimedLifecycleWork,
        cycle: _ProvisionCycle,
        outcome: GenerationOutcome,
        capabilities: WorkspaceCapabilities,
    ) -> WorkspaceLifecycleRunResult:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            parent = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
            if (
                workspace is None
                or parent is None
                or parent.status != "running"
                or parent.claim_token != work.claim_token
                or workspace.runtime_status != _LIFECYCLE_TARGET_STATUS[work.operation]
                or workspace.knowledge_base_mount_desired_revision
                != cycle.mount_revision
                or workspace.runtime_access_revision != cycle.access_revision
            ):
                raise RuntimeJobClaimLostError("Lifecycle target advanced")
            self.execution_plane._stage_ready(workspace, outcome)
            self._mark_provision_success(workspace, transitioned_at=now)
            workspace.runtime_access_observed_revision = cycle.access_revision
            workspace.agentic_capabilities = capabilities.model_dump(by_alias=True)
            self._complete_revision_children(
                workspace=workspace,
                children=cycle.children,
                finished_at=now,
            )
            if not self.job_execution.finish_claim(
                job_id=work.job_id,
                claim_token=work.claim_token,
                state=JobTerminalState.SUCCEEDED,
                finished_at=now,
            ):
                raise RuntimeJobClaimLostError("Lifecycle parent claim was lost")
            self._record_lifecycle_terminal_audit(
                workspace=workspace,
                work=work,
                event_type=_SUCCESS_EVENT[work.operation],
                result="success",
                error_code=None,
                runtime_instance_id=workspace.runtime_instance_id,
            )
            self.db.commit()
            if workspace.provisioner == "docker":
                enqueue_docker_browser_connectivity_reconcile(workspace.id)
            return WorkspaceLifecycleRunResult.SUCCEEDED
        except Exception:
            self.db.rollback()
            self.db.expunge_all()
            raise

    def _provision_completion_state(
        self,
        *,
        work: _ClaimedLifecycleWork,
        cycle: _ProvisionCycle,
        outcome: GenerationOutcome,
    ) -> _ProvisionCompletionState:
        """Read completion through a fresh session after commit acknowledgement loss."""

        try:
            with Session(bind=self.db.get_bind()) as verification_db:
                workspace = verification_db.get(db_models.Workspace, work.workspace_id)
                parent = verification_db.get(
                    db_models.WorkspaceRuntimeJob,
                    work.job_id,
                )
                if (
                    workspace is not None
                    and parent is not None
                    and parent.status == "succeeded"
                    and workspace.runtime_status == "running"
                    and workspace.runtime_instance_id == outcome.generation_id
                    and workspace.knowledge_base_mount_desired_revision
                    == cycle.mount_revision
                    and workspace.knowledge_base_mount_observed_revision
                    == cycle.mount_revision
                    and workspace.runtime_access_revision == cycle.access_revision
                    and workspace.runtime_access_observed_revision
                    == cycle.access_revision
                ):
                    return _ProvisionCompletionState.COMMITTED
                return _ProvisionCompletionState.NOT_COMMITTED
        except Exception:
            logger.exception(
                "Workspace provisioning completion state verification failed",
                extra={
                    "workspace_id": work.workspace_id,
                    "job_id": work.job_id,
                    "runtime_instance_id": outcome.generation_id,
                },
            )
            return _ProvisionCompletionState.UNKNOWN

    def _run_termination_parent(
        self,
        work: _ClaimedLifecycleWork,
        *,
        assert_claim: Callable[[], None],
    ) -> WorkspaceLifecycleRunResult:
        if work.operation == WORKSPACE_DELETE:
            self._advance_delete_phase(
                work,
                phase=DELETE_PHASE_CANCELLING_AUTOMATIONS,
                assert_claim=assert_claim,
            )
            convergence = self.automation_execution_service.converge_workspace_deletion(
                workspace_id=work.workspace_id,
            )
            running_execution_ids = set(
                getattr(convergence, "running_execution_ids", ())
            )
            confirmed_execution_ids = set(
                getattr(convergence, "confirmed_execution_ids", ())
            )
            if not running_execution_ids.issubset(confirmed_execution_ids):
                raise RuntimeError("Workspace automation cancellation is unconfirmed")
            assert_claim()

        def reconcile_absent(*, delete_workspace: bool) -> None:
            outcome = self.execution_plane.reconcile(
                GenerationClaim(
                    workspace_id=work.workspace_id,
                    job_id=work.job_id,
                    assert_owned=assert_claim,
                    desired_state=GenerationState.ABSENT,
                    expected_mounted_revision=self._load_observed_mount_revision(
                        work.workspace_id
                    ),
                    target_mounted_revision=self._load_desired_mount_revision(
                        work.workspace_id
                    ),
                    identity=work.workspace_identity,
                    delete_workspace=delete_workspace,
                )
            )
            outcome.raise_for_failure()

        assert_claim()
        if work.operation == WORKSPACE_DELETE:
            self._advance_delete_phase(
                work,
                phase=DELETE_PHASE_STOPPING_RUNTIME,
                assert_claim=assert_claim,
            )
            if self._delete_requires_runtime_stop(work):
                reconcile_absent(delete_workspace=False)
                self._mark_delete_stop_confirmed(work, assert_claim=assert_claim)
            assert_claim()
            self._advance_delete_phase(
                work,
                phase=DELETE_PHASE_DELETING_RESOURCES,
                assert_claim=assert_claim,
            )
            if work.workspace_identity.provisioner == "kubernetes":
                reconcile_absent(delete_workspace=True)
            elif (
                work.workspace_identity.runtime_instance_id is not None
                and not self._delete_stop_confirmed(work)
            ):
                reconcile_absent(delete_workspace=False)
            self._cleanup_workspace_volumes(work.workspace_id)
            self._advance_delete_phase(
                work,
                phase=DELETE_PHASE_FINALIZING,
                assert_claim=assert_claim,
            )
        else:
            reconcile_absent(delete_workspace=False)
        assert_claim()
        return self._complete_termination_success(work)

    def _advance_delete_phase(
        self,
        work: _ClaimedLifecycleWork,
        *,
        phase: str,
        assert_claim: Callable[[], None],
    ) -> None:
        if work.operation != WORKSPACE_DELETE:
            return
        if work.phase == phase:
            assert_claim()
            return
        self._update_delete_metadata(
            work,
            updates={"phase": phase},
            assert_claim=assert_claim,
        )

    def _mark_delete_stop_confirmed(
        self,
        work: _ClaimedLifecycleWork,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        self._update_delete_metadata(
            work,
            updates={"stop_confirmed": True},
            assert_claim=assert_claim,
        )

    def _update_delete_metadata(
        self,
        work: _ClaimedLifecycleWork,
        *,
        updates: dict[str, Any],
        assert_claim: Callable[[], None],
    ) -> None:
        assert_claim()
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.id == work.job_id,
                    db_models.WorkspaceRuntimeJob.workspace_id == work.workspace_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                workspace is None
                or workspace.runtime_status != "deleting"
                or job is None
                or job.status != "running"
                or job.claim_token != work.claim_token
            ):
                raise RuntimeJobClaimLostError(
                    "Workspace deletion claim is no longer current"
                )
            metadata = dict(job.job_metadata or {})
            metadata.update(updates)
            job.job_metadata = metadata
            self.db.flush()
            phase = metadata.get("phase")
            if isinstance(phase, str) and phase != work.phase:
                self.audit_events.record(
                    event_type="workspace.lifecycle_phase_changed",
                    actor_type="service",
                    actor_id=_SERVICE_ACTOR_ID,
                    actor_user_id=None,
                    target_type="workspace",
                    target_id=workspace.id,
                    action=_COMMAND_ACTION[WORKSPACE_DELETE],
                    result="success",
                    error_code=None,
                    correlation_id=work.correlation_id,
                    root_correlation_id=work.root_correlation_id,
                    metadata={
                        "workspace_id": workspace.id,
                        "job_id": work.job_id,
                        "attempt": work.attempt,
                        "phase": phase,
                    },
                )
                work.phase = phase
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        assert_claim()

    def _delete_stop_confirmed(self, work: _ClaimedLifecycleWork) -> bool:
        job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == work.job_id,
                db_models.WorkspaceRuntimeJob.workspace_id == work.workspace_id,
            )
            .execution_options(populate_existing=True)
        )
        if (
            job is None
            or job.status != "running"
            or job.claim_token != work.claim_token
        ):
            raise RuntimeJobClaimLostError(
                "Workspace deletion claim is no longer current"
            )
        return bool(job.job_metadata.get("stop_confirmed", False))

    def _delete_requires_runtime_stop(self, work: _ClaimedLifecycleWork) -> bool:
        if self._delete_stop_confirmed(work):
            return False
        job = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
        if job is None:
            raise RuntimeJobClaimLostError(
                "Workspace deletion job is no longer available"
            )
        requires_stop = job.job_metadata.get("requires_stop")
        if type(requires_stop) is bool:
            return requires_stop
        return work.workspace_identity.runtime_instance_id is not None

    def _complete_termination_success(
        self,
        work: _ClaimedLifecycleWork,
    ) -> WorkspaceLifecycleRunResult:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return WorkspaceLifecycleRunResult.SUCCEEDED
            if workspace.runtime_status != _LIFECYCLE_TARGET_STATUS[work.operation]:
                self._supersede_claimed_lifecycle_locked(
                    work=work,
                    workspace=workspace,
                    finished_at=now,
                )
                self.db.commit()
                return WorkspaceLifecycleRunResult.SUPERSEDED
            if not self.job_execution.finish_claim(
                job_id=work.job_id,
                claim_token=work.claim_token,
                state=JobTerminalState.SUCCEEDED,
                finished_at=now,
            ):
                raise RuntimeJobClaimLostError("Lifecycle parent claim was lost")
            if work.operation == WORKSPACE_STOP:
                self._clear_execution_plane(workspace)
                workspace.runtime_status = "stopped"
                self._record_lifecycle_terminal_audit(
                    workspace=workspace,
                    work=work,
                    event_type=_SUCCESS_EVENT[work.operation],
                    result="success",
                    error_code=None,
                )
            else:
                self._record_lifecycle_terminal_audit(
                    workspace=workspace,
                    work=work,
                    event_type=_SUCCESS_EVENT[work.operation],
                    result="success",
                    error_code=None,
                )
                self._database_service().drop_workspace(workspace_id=workspace.id)
                WorkspaceFirewallSyncCommandRepository(self.db).supersede_workspace(
                    workspace_id=workspace.id, at=now
                )
                self.db.delete(workspace)
            self.db.commit()
            return WorkspaceLifecycleRunResult.SUCCEEDED
        except Exception:
            self.db.rollback()
            raise

    def _complete_superseded_if_state_advanced(
        self,
        work: _ClaimedLifecycleWork,
    ) -> bool:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return True
            if workspace.runtime_status == _LIFECYCLE_TARGET_STATUS[work.operation]:
                self.db.rollback()
                return False
            self._supersede_claimed_lifecycle_locked(
                work=work,
                workspace=workspace,
                finished_at=now,
            )
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def _supersede_claimed_lifecycle_locked(
        self,
        *,
        work: _ClaimedLifecycleWork,
        workspace: db_models.Workspace,
        finished_at: datetime,
    ) -> None:
        running_children = list(
            self.db.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.lifecycle_job_id == work.job_id,
                    db_models.WorkspaceRuntimeJob.status == "running",
                )
                .order_by(db_models.WorkspaceRuntimeJob.operation)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )
        for child_job in running_children:
            claim_token = child_job.claim_token or ""
            if not claim_token or not self.job_execution.finish_claim(
                job_id=child_job.id,
                claim_token=claim_token,
                state=JobTerminalState.SUPERSEDED,
                finished_at=finished_at,
            ):
                raise RuntimeJobClaimLostError(
                    "Revision child claim was lost during supersede"
                )
            self._record_revision_audit(
                workspace=workspace,
                child=_ClaimedRevisionChild(
                    job_id=child_job.id,
                    operation=child_job.operation,
                    claim_token=claim_token,
                    target_revision=child_job.target_revision or 0,
                    correlation_id=child_job.correlation_id,
                    root_correlation_id=child_job.root_correlation_id,
                    attempt=int(child_job.job_metadata.get("attempt", 0))
                    + int(child_job.retries),
                ),
                suffix="superseded",
                result="success",
                error_code=None,
                reason="lifecycle_state_advanced",
            )
        if not self.job_execution.finish_claim(
            job_id=work.job_id,
            claim_token=work.claim_token,
            state=JobTerminalState.SUPERSEDED,
            finished_at=finished_at,
        ):
            raise RuntimeJobClaimLostError("Lifecycle parent claim was lost")
        self.audit_events.record(
            event_type="workspace.lifecycle_superseded",
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=_COMMAND_ACTION[work.operation],
            result="success",
            error_code=None,
            correlation_id=work.correlation_id,
            root_correlation_id=work.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "reason": "lifecycle_state_advanced",
            },
        )

    def _complete_failure(
        self,
        work: _ClaimedLifecycleWork,
        exc: Exception,
    ) -> WorkspaceLifecycleRunResult:
        now = datetime.now(timezone.utc)
        error_code = self._stable_error_code(exc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return WorkspaceLifecycleRunResult.CLAIM_LOST
            if workspace.runtime_status != _LIFECYCLE_TARGET_STATUS[work.operation]:
                self._supersede_claimed_lifecycle_locked(
                    work=work,
                    workspace=workspace,
                    finished_at=now,
                )
                self.db.commit()
                return WorkspaceLifecycleRunResult.SUPERSEDED
            if not self.job_execution.finish_claim(
                job_id=work.job_id,
                claim_token=work.claim_token,
                state=JobTerminalState.FAILED,
                finished_at=now,
                error_code=error_code,
            ):
                self.db.rollback()
                return WorkspaceLifecycleRunResult.CLAIM_LOST
            running_children = list(
                self.db.scalars(
                    select(db_models.WorkspaceRuntimeJob)
                    .where(
                        db_models.WorkspaceRuntimeJob.lifecycle_job_id == work.job_id,
                        db_models.WorkspaceRuntimeJob.status == "running",
                    )
                    .order_by(db_models.WorkspaceRuntimeJob.operation)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).all()
            )
            mount_compensation_job: db_models.WorkspaceRuntimeJob | None = None
            for child_job in running_children:
                child = _ClaimedRevisionChild(
                    job_id=child_job.id,
                    operation=child_job.operation,
                    claim_token=child_job.claim_token or "",
                    target_revision=child_job.target_revision or 0,
                    correlation_id=child_job.correlation_id,
                    root_correlation_id=child_job.root_correlation_id,
                    attempt=int(child_job.job_metadata.get("attempt", 0))
                    + int(child_job.retries),
                )
                if not self.job_execution.finish_claim(
                    job_id=child.job_id,
                    claim_token=child.claim_token,
                    state=JobTerminalState.FAILED,
                    finished_at=now,
                    error_code=error_code,
                ):
                    raise RuntimeJobClaimLostError(
                        "Revision child claim was lost during failure"
                    )
                if child.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
                    mount_compensation_job = KnowledgeBaseMountReconcileService(
                        self.db,
                        settings=self.settings,
                    ).stage_terminal_recovery(
                        workspace=workspace,
                        failed_job=child_job,
                        error_code=error_code,
                        now=now,
                        offline_promotion=False,
                    )
                self._record_revision_audit(
                    workspace=workspace,
                    child=child,
                    suffix="failed",
                    result="failure",
                    error_code=error_code,
                )
            if work.operation == WORKSPACE_START and mount_compensation_job is None:
                mount_compensation_job = self._fail_queued_mount_child_for_lifecycle(
                    workspace=workspace,
                    error_code=error_code,
                    finished_at=now,
                )
            if work.operation == WORKSPACE_START:
                self._mark_provision_failure(
                    workspace,
                    error_code=error_code,
                    transitioned_at=now,
                )
            elif work.operation != WORKSPACE_DELETE:
                workspace.runtime_status = "error"
            self._record_lifecycle_terminal_audit(
                workspace=workspace,
                work=work,
                event_type="workspace.lifecycle_failed",
                result="failure",
                error_code=error_code,
            )
            if work.operation == WORKSPACE_START and mount_compensation_job is not None:
                self._enqueue_mount_compensation_recovery(
                    workspace=workspace,
                    failed_parent_job_id=work.job_id,
                    failed_parent_root_correlation_id=work.root_correlation_id,
                    requested_at=now,
                )
            self.db.commit()
            return WorkspaceLifecycleRunResult.FAILED
        except Exception:
            self.db.rollback()
            raise

    def _fail_queued_mount_child_for_lifecycle(
        self,
        *,
        workspace: db_models.Workspace,
        error_code: str,
        finished_at: datetime,
    ) -> db_models.WorkspaceRuntimeJob | None:
        if (
            workspace.knowledge_base_mount_candidate_snapshot is None
            or workspace.knowledge_base_mount_sync_status
            not in {"preflighting", "applying", "compensating"}
        ):
            return None
        queued_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation
                == KNOWLEDGE_BASE_MOUNT_RECONCILE,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.target_revision
                == workspace.knowledge_base_mount_desired_revision,
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at,
                db_models.WorkspaceRuntimeJob.id,
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if queued_job is None:
            return None
        if not self.job_execution.finish_queued(
            job_id=queued_job.id,
            state=JobTerminalState.FAILED,
            finished_at=finished_at,
            error_code=error_code,
        ):
            raise RuntimeJobClaimLostError(
                "Queued mount child advanced during lifecycle failure"
            )
        child = _ClaimedRevisionChild(
            job_id=queued_job.id,
            operation=queued_job.operation,
            claim_token="",
            target_revision=queued_job.target_revision or 0,
            correlation_id=queued_job.correlation_id,
            root_correlation_id=queued_job.root_correlation_id,
            attempt=int(queued_job.job_metadata.get("attempt", 0))
            + int(queued_job.retries),
        )
        compensation_job = KnowledgeBaseMountReconcileService(
            self.db,
            settings=self.settings,
        ).stage_terminal_recovery(
            workspace=workspace,
            failed_job=queued_job,
            error_code=error_code,
            now=finished_at,
            offline_promotion=False,
        )
        self._record_revision_audit(
            workspace=workspace,
            child=child,
            suffix="failed",
            result="failure",
            error_code=error_code,
        )
        return compensation_job

    def _enqueue_mount_compensation_recovery(
        self,
        *,
        workspace: db_models.Workspace,
        failed_parent_job_id: str,
        failed_parent_root_correlation_id: str,
        requested_at: datetime,
    ) -> db_models.WorkspaceRuntimeJob:
        correlation_id = str(uuid4())
        workspace.runtime_status = _LIFECYCLE_TARGET_STATUS[WORKSPACE_START]
        workspace.runtime_desired_state = "running"
        workspace.browser_desired_state = "running"
        workspace.canvas_desired_state = "running"
        workspace.updated_at = requested_at
        enqueue_result = self.jobs.enqueue_lifecycle_job(
            workspace=workspace,
            operation=WORKSPACE_START,
            correlation_id=correlation_id,
            root_correlation_id=failed_parent_root_correlation_id,
            scheduled_at=requested_at,
            target_runtime_instance_id=workspace.runtime_instance_id,
            retry_of_job_id=failed_parent_job_id,
        )
        self.audit_events.record(
            event_type=_REQUEST_EVENT[WORKSPACE_START],
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=_COMMAND_ACTION[WORKSPACE_START],
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=enqueue_result.job.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "reason": "mount_compensation",
            },
        )
        return enqueue_result.job

    def recover_missing_revision_jobs(self, *, limit: int = 100) -> int:
        """Recreate durable revision owners without reopening terminal failures."""

        workspace_ids = list(
            self.db.scalars(
                select(db_models.Workspace.id)
                .where(
                    or_(
                        and_(
                            db_models.Workspace.knowledge_base_mount_desired_revision
                            != db_models.Workspace.knowledge_base_mount_active_revision,
                            db_models.Workspace.knowledge_base_mount_sync_status.in_(
                                {"applying", "compensating"}
                            ),
                        ),
                        db_models.Workspace.runtime_access_revision
                        != db_models.Workspace.runtime_access_observed_revision,
                    )
                )
                .order_by(db_models.Workspace.id)
                .limit(limit)
            ).all()
        )
        self.db.rollback()
        recovered = 0
        for workspace_id in workspace_ids:
            now = datetime.now(timezone.utc)
            try:
                acquire_workspace_transaction_lock(self.db, workspace_id)
                workspace = self.db.scalar(
                    select(db_models.Workspace)
                    .where(db_models.Workspace.id == workspace_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if workspace is None:
                    self.db.rollback()
                    continue
                created = 0
                if (
                    workspace.knowledge_base_mount_desired_revision
                    != workspace.knowledge_base_mount_active_revision
                    and workspace.knowledge_base_mount_sync_status
                    in {"preflighting", "applying", "compensating"}
                    and workspace.knowledge_base_mount_candidate_snapshot is not None
                    and self._active_revision_job(
                        workspace_id=workspace.id,
                        operation=KNOWLEDGE_BASE_MOUNT_RECONCILE,
                    )
                    is None
                ):
                    correlation_id = str(uuid4())
                    self.jobs.supersede_queued_and_enqueue_mount_reconcile(
                        workspace=workspace,
                        correlation_id=correlation_id,
                        scheduled_at=now,
                        job_metadata={
                            "attempt": 0,
                            "mount_action": (
                                "compensate"
                                if workspace.knowledge_base_mount_sync_status
                                == "compensating"
                                else "apply_candidate"
                            ),
                            "mutation_action": "orphan_recovery",
                            **(
                                {"offline_promotion": True}
                                if workspace.runtime_status == "stopped"
                                and workspace.runtime_instance_id is None
                                else {}
                            ),
                        },
                    )
                    created += 1
                if (
                    workspace.runtime_status == "running"
                    and workspace.runtime_access_revision
                    != workspace.runtime_access_observed_revision
                    and self._active_revision_job(
                        workspace_id=workspace.id,
                        operation=WORKSPACE_ACCESS_RECYCLE,
                    )
                    is None
                    and self.jobs.find_latest_failed_job(
                        workspace_id=workspace.id,
                        operation=WORKSPACE_ACCESS_RECYCLE,
                        for_update=True,
                    )
                    is None
                ):
                    correlation_id = str(uuid4())
                    self.jobs.supersede_queued_and_enqueue_access_recycle(
                        workspace=workspace,
                        correlation_id=correlation_id,
                        root_correlation_id=correlation_id,
                        scheduled_at=now,
                        job_metadata={
                            "attempt": 0,
                            "reason": "orphan_recovery",
                        },
                    )
                    created += 1
                if created == 0:
                    self.db.rollback()
                    continue
                self.db.commit()
                recovered += created
            except Exception:
                self.db.rollback()
                logger.error(
                    "Workspace revision owner recovery failed",
                    extra={"workspace_id": workspace_id},
                )
        return recovered

    def _active_revision_job(
        self,
        *,
        workspace_id: str,
        operation: str,
    ) -> db_models.WorkspaceRuntimeJob | None:
        return self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == operation,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
            .with_for_update()
        )

    def _sync_generation_capabilities(
        self,
        *,
        workspace_id: str,
        outcome: GenerationOutcome,
        assert_claim: Callable[[], None],
    ) -> WorkspaceCapabilities:
        runtime_url = outcome.runtime_url
        runtime_instance_id = outcome.generation_id
        if not runtime_url or not runtime_instance_id:
            raise RuntimeCapabilitiesSyncError(
                "Ready Runtime generation has no capabilities sync target"
            )
        return self._sync_runtime_capabilities(
            workspace_id=workspace_id,
            runtime_url=runtime_url,
            runtime_instance_id=runtime_instance_id,
            assert_claim=assert_claim,
        )

    @staticmethod
    def _attempt_generation_id(attempt: object) -> str:
        generation_id = getattr(attempt, "runtime_instance_id", None)
        if not isinstance(generation_id, str) or not generation_id:
            raise ValueError("Prepared Workspace generation identity is missing")
        return generation_id

    def _sync_runtime_capabilities(
        self,
        *,
        workspace_id: str,
        runtime_url: str,
        runtime_instance_id: str,
        assert_claim: Callable[[], None],
    ) -> WorkspaceCapabilities:
        capability_resolution = (
            self.runtime_sync.resolve_workspace_capability_resolution(workspace_id)
        )
        effective_capabilities = capability_resolution.effective
        convergence_budget_seconds = max(
            0,
            self.settings.RUNTIME_READY_TIMEOUT_SECONDS,
        )
        elapsed_retry_seconds = 0
        retry_delay_seconds = 1
        attempt = 0
        while True:
            attempt += 1
            assert_claim()
            try:
                sync_result = self.runtime_sync.sync_capabilities_to_runtime_generation(
                    workspace_id,
                    runtime_url,
                    runtime_instance_id,
                    effective_capabilities,
                )
                if sync_result.get("success") is not True:
                    raise RuntimeCapabilitiesSyncError(
                        "Runtime rejected its capabilities snapshot"
                    )
                assert_claim()
                return capability_resolution.snapshot
            except RuntimeCapabilitiesSyncError:
                remaining_seconds = convergence_budget_seconds - elapsed_retry_seconds
                if remaining_seconds <= 0:
                    raise
                sleep_seconds = min(retry_delay_seconds, remaining_seconds)
                logger.warning(
                    "Runtime capabilities sync retry scheduled",
                    extra={
                        "workspace_id": workspace_id,
                        "attempt": attempt,
                        "remaining_seconds": remaining_seconds,
                    },
                )
                time.sleep(sleep_seconds)
                elapsed_retry_seconds += sleep_seconds
                retry_delay_seconds = min(retry_delay_seconds * 2, 5)

    def _execution_identity(
        self,
        workspace: db_models.Workspace,
    ) -> WorkspaceExecutionPlaneIdentity:
        return WorkspaceExecutionPlaneIdentity(
            id=workspace.id,
            provisioner=workspace.provisioner,
            runtime_instance_id=workspace.runtime_instance_id,
            browser_instance_id=workspace.browser_instance_id,
            canvas_instance_id=workspace.canvas_instance_id,
            runtime_container_id=workspace.runtime_container_id,
            browser_container_id=workspace.browser_container_id,
            canvas_container_id=workspace.canvas_container_id,
            runtime_internal_url=workspace.runtime_internal_url,
            terminal_internal_url=workspace.terminal_internal_url,
            runtime_internal_port=workspace.runtime_internal_port,
            browser_webrtc_internal_port=workspace.browser_webrtc_internal_port,
            canvas_internal_port=workspace.canvas_internal_port,
            target_namespace=(
                self.settings.RUNTIME_K8S_NAMESPACE
                if workspace.provisioner == "kubernetes"
                else None
            ),
        )

    def _load_observed_mount_revision(self, workspace_id: str) -> int:
        value = self.db.scalar(
            select(db_models.Workspace.knowledge_base_mount_observed_revision).where(
                db_models.Workspace.id == workspace_id
            )
        )
        self.db.rollback()
        return int(value or 0)

    def _load_desired_mount_revision(self, workspace_id: str) -> int:
        value = self.db.scalar(
            select(db_models.Workspace.knowledge_base_mount_desired_revision).where(
                db_models.Workspace.id == workspace_id
            )
        )
        self.db.rollback()
        return int(value or 0)

    def _complete_revision_children(
        self,
        *,
        workspace: db_models.Workspace,
        children: tuple[_ClaimedRevisionChild, ...],
        finished_at: datetime,
    ) -> None:
        for child in children:
            if child.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
                self._promote_mount_revision_child(
                    workspace=workspace,
                    child=child,
                )
            if not self.job_execution.finish_claim(
                job_id=child.job_id,
                claim_token=child.claim_token,
                state=JobTerminalState.SUCCEEDED,
                finished_at=finished_at,
            ):
                raise RuntimeJobClaimLostError("Revision child claim was lost")
            self._record_revision_audit(
                workspace=workspace,
                child=child,
                suffix="ready",
                result="success",
                error_code=None,
            )

    def _promote_mount_revision_child(
        self,
        *,
        workspace: db_models.Workspace,
        child: _ClaimedRevisionChild,
    ) -> None:
        if (
            child.target_revision != workspace.knowledge_base_mount_desired_revision
            or workspace.knowledge_base_mount_candidate_snapshot is None
        ):
            raise RuntimeJobClaimLostError("Mount revision child target advanced")
        candidate = canonical_mount_snapshot(
            workspace.knowledge_base_mount_candidate_snapshot
        )
        current = list(
            self.db.scalars(
                select(db_models.WorkspaceKnowledgeBaseAttachment)
                .where(
                    db_models.WorkspaceKnowledgeBaseAttachment.workspace_id
                    == workspace.id
                )
                .order_by(db_models.WorkspaceKnowledgeBaseAttachment.id)
                .with_for_update()
            ).all()
        )
        current_by_id = {attachment.id: attachment for attachment in current}
        candidate_ids = {str(entry["attachmentId"]) for entry in candidate}
        for attachment in current:
            attachment.mount_alias = f"pending-{attachment.id}"
        if current:
            self.db.flush()
        for attachment in current:
            if attachment.id not in candidate_ids:
                self.db.delete(attachment)
        for entry in candidate:
            attachment_id = str(entry["attachmentId"])
            attachment = current_by_id.get(attachment_id)
            if attachment is None:
                attachment = db_models.WorkspaceKnowledgeBaseAttachment(
                    id=attachment_id,
                    workspace_id=workspace.id,
                    kb_id=str(entry["knowledgeBaseId"]),
                    mount_alias=str(entry["mountAlias"]),
                )
                self.db.add(attachment)
            attachment.kb_id = str(entry["knowledgeBaseId"])
            attachment.mount_alias = str(entry["mountAlias"])
            attachment.attached_by_id = (
                str(entry["attachedById"])
                if entry.get("attachedById") is not None
                else None
            )

        job = self.db.get(db_models.WorkspaceRuntimeJob, child.job_id)
        mount_action = job.job_metadata.get("mount_action") if job is not None else None
        workspace.knowledge_base_mount_active_snapshot = candidate
        workspace.knowledge_base_mount_active_revision = child.target_revision
        workspace.knowledge_base_mount_observed_revision = child.target_revision
        workspace.knowledge_base_mount_candidate_snapshot = None
        if mount_action == "compensate":
            workspace.knowledge_base_mount_sync_status = "degraded"
        else:
            workspace.knowledge_base_mount_sync_status = "ready"
            workspace.knowledge_base_mount_error_code = None
            workspace.knowledge_base_mount_failed_snapshot = None

    def _record_revision_audit(
        self,
        *,
        workspace: db_models.Workspace,
        child: _ClaimedRevisionChild,
        suffix: str,
        result: str,
        error_code: str | None,
        reason: str | None = None,
    ) -> None:
        event_prefix = (
            "runtime.mount_sync"
            if child.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE
            else "runtime.access_recycle"
        )
        self.audit_events.record(
            event_type=f"{event_prefix}_{suffix}",
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=f"lifecycle_{suffix}_{child.operation}",
            result=result,
            error_code=error_code,
            correlation_id=child.correlation_id,
            root_correlation_id=child.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "target_revision": child.target_revision,
                "attempt": child.attempt,
                **({"reason": reason} if reason else {}),
            },
        )

    def _record_lifecycle_terminal_audit(
        self,
        *,
        workspace: db_models.Workspace,
        work: _ClaimedLifecycleWork,
        event_type: str,
        result: str,
        error_code: str | None,
        runtime_instance_id: str | None = None,
    ) -> None:
        self.audit_events.record(
            event_type=event_type,
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=_COMMAND_ACTION[work.operation],
            result=result,
            error_code=error_code,
            correlation_id=work.correlation_id,
            root_correlation_id=work.root_correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "job_id": work.job_id,
                "attempt": work.attempt,
                **({"phase": work.phase} if work.phase else {}),
                **(
                    {"runtime_instance_id": runtime_instance_id}
                    if runtime_instance_id
                    else {}
                ),
            },
        )

    @staticmethod
    def _clear_execution_plane(workspace: db_models.Workspace) -> None:
        workspace.runtime_instance_id = None
        workspace.browser_instance_id = None
        workspace.canvas_instance_id = None
        workspace.runtime_control_instance_id = None
        workspace.runtime_control_token_hash = None
        workspace.runtime_container_id = None
        workspace.browser_container_id = None
        workspace.canvas_container_id = None
        workspace.runtime_internal_url = None
        workspace.terminal_internal_url = None
        workspace.browser_webrtc_internal_url = None
        workspace.browser_connectivity_browser_generation = None
        workspace.browser_connectivity_state = "pending"
        workspace.browser_connectivity_contract_version = "browser-connectivity/v1"
        workspace.browser_connectivity_admission = "denied"
        workspace.browser_connectivity_profile_revision = None
        workspace.browser_connectivity_credential_revision = None
        workspace.browser_connectivity_accepted_at = None
        workspace.browser_connectivity_expires_at = None
        workspace.browser_connectivity_reason = "BrowserConnectivityPending"
        workspace.browser_connectivity_error_code = None
        workspace.browser_connectivity_last_transition_at = None
        workspace.browser_connectivity_backend_state = "pending"
        workspace.browser_connectivity_backend_accepted_at = None
        workspace.browser_connectivity_backend_expires_at = None
        workspace.browser_connectivity_backend_reason = None
        workspace.browser_connectivity_backend_error_code = None
        workspace.browser_connectivity_frontend_state = "pending"
        workspace.browser_connectivity_frontend_accepted_at = None
        workspace.browser_connectivity_frontend_expires_at = None
        workspace.browser_connectivity_frontend_reason = None
        workspace.browser_connectivity_frontend_error_code = None
        workspace.canvas_internal_url = None
        workspace.browser_status = "stopped"
        workspace.canvas_status = "stopped"

    @classmethod
    def _mark_provision_failure(
        cls,
        workspace: db_models.Workspace,
        *,
        error_code: str,
        transitioned_at: datetime,
    ) -> None:
        cls._clear_execution_plane(workspace)
        workspace.bootstrap_status = "error"
        workspace.bootstrap_error_code = error_code
        workspace.bootstrap_last_transition_at = transitioned_at
        for component in ("runtime", "browser", "canvas"):
            setattr(workspace, f"{component}_status", "error")
            setattr(workspace, f"{component}_reason", _PROVISION_FAILURE_REASON)
            setattr(workspace, f"{component}_error_code", error_code)
            setattr(
                workspace,
                f"{component}_last_transition_at",
                transitioned_at,
            )

    @staticmethod
    def _mark_provision_success(
        workspace: db_models.Workspace,
        *,
        transitioned_at: datetime,
    ) -> None:
        workspace.bootstrap_status = "succeeded"
        workspace.bootstrap_error_code = None
        workspace.bootstrap_last_transition_at = transitioned_at
        for component in ("runtime", "browser", "canvas"):
            setattr(workspace, f"{component}_status", "running")
            setattr(workspace, f"{component}_reason", None)
            setattr(workspace, f"{component}_error_code", None)
            setattr(
                workspace,
                f"{component}_last_transition_at",
                transitioned_at,
            )

    def _cleanup_workspace_volumes(self, workspace_id: str) -> None:
        safe_workspace_id = workspace_id.replace("-", "_")
        directories = (
            Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_RUNTIME_HOME_DIR) / safe_workspace_id,
        )
        for directory in directories:
            if directory.exists():
                shutil.rmtree(directory)

    @classmethod
    def _stable_error_code(cls, exc: Exception) -> str:
        candidate = getattr(exc, "code", None)
        if isinstance(candidate, str) and _STABLE_ERROR_CODE.fullmatch(candidate):
            return candidate
        return "WORKSPACE_LIFECYCLE_FAILED"

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


__all__ = [
    "WorkspaceLifecycleCommandResult",
    "WorkspaceLifecycleConflictError",
    "WorkspaceLifecycleRunResult",
    "WorkspaceLifecycleService",
]
