"""Manager-owned Workspace availability control plane."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NoReturn, cast

from celery import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.workspace.availability_contract import workspace_availability_reason
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.workspace.availability_models import (
    KnowledgeMountAvailability,
    WorkspaceAvailabilityActionResponse,
    WorkspaceAvailabilityResponse,
    WorkspaceDeletionPhase,
    WorkspaceDeletionProjection,
)
from app.modules.workspace.runtime.job_repository import (
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
    WORKSPACE_ACCESS_RECYCLE,
    WORKSPACE_DELETE,
    WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS,
    WORKSPACE_DELETE_PHASE_QUEUED,
    WORKSPACE_DELETE_PHASES,
    WORKSPACE_LIFECYCLE_OPERATIONS,
    WORKSPACE_START,
    WORKSPACE_STOP,
    WorkspaceRuntimeJobRepository,
)
from app.modules.workspace.advisory_lock import acquire_workspace_transaction_lock
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceService,
)
from app.modules.workspace.lifecycle import WorkspaceLifecycleService
from app.modules.workspace.execution_plane_observation import (
    WorkspaceExecutionPlaneObservationService,
)

logger = logging.getLogger(__name__)

_RUNTIME_JOB_TASK = "workspace_runtime.reconcile_job"
_TRANSITION_RETRY_AFTER_MS = 1500


@dataclass(frozen=True)
class WorkspaceAvailabilityError(Exception):
    """Stable control-plane failure consumed by the HTTP router."""

    code: str
    http_status: int


class WorkspaceAvailabilityService:
    """Resolve availability without depending on Runtime HTTP or WebSocket."""

    def __init__(
        self,
        db: Session,
        *,
        custom_resource_service: WorkspaceCustomResourceService | None = None,
        execution_plane_observer: (
            WorkspaceExecutionPlaneObservationService | None
        ) = None,
    ) -> None:
        self.db = db
        self.authorization = AuthorizationOperationPolicy(db)
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.custom_resources = (
            custom_resource_service
            if custom_resource_service is not None
            else WorkspaceCustomResourceService(db)
        )
        self.execution_plane_observer = (
            execution_plane_observer
            if execution_plane_observer is not None
            else WorkspaceExecutionPlaneObservationService(
                db,
                custom_resource_service=self.custom_resources,
            )
        )

    def get(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
    ) -> WorkspaceAvailabilityResponse:
        self._require_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_DETAIL_READ,
        )
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise self._error("WORKSPACE_NOT_FOUND")

        workspace = self._reconcile_orphan_transient(
            workspace=workspace,
        )
        allowed = self.authorization.allowed_workspace_operations(
            actor,
            workspace_id,
        )
        can_manage = OperationId.WORKSPACE_LIFECYCLE_EXECUTE.value in allowed
        availability, reason_code, retry_after_ms = self._global_state(workspace)
        if reason_code == "WORKSPACE_READY":
            observation = self.execution_plane_observer.observe(workspace)
            if observation.state == "drift":
                availability, reason_code, retry_after_ms = self._state(
                    "WORKSPACE_EXECUTION_PLANE_DRIFT",
                    None,
                )
            elif observation.state == "unavailable":
                availability, reason_code, retry_after_ms = self._state(
                    "WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE",
                    _TRANSITION_RETRY_AFTER_MS,
                )
        allowed_actions = self._allowed_actions(
            reason_code=reason_code,
            can_manage=can_manage,
        )
        reason_contract = workspace_availability_reason(reason_code)
        can_delete = OperationId.WORKSPACE_DELETE.value in allowed
        return WorkspaceAvailabilityResponse(
            workspace_id=workspace.id,
            availability=availability,
            reason_code=reason_code,
            runtime_status=workspace.runtime_status,
            runtime_instance_id=workspace.runtime_instance_id,
            runtime_access_desired_revision=workspace.runtime_access_revision,
            runtime_access_observed_revision=(
                workspace.runtime_access_observed_revision
            ),
            retryable=reason_contract.retryable and can_manage,
            allowed_actions=allowed_actions,
            retry_after_ms=retry_after_ms,
            knowledge_mount_status=self._knowledge_mount_status(workspace),
            deletion=self._deletion_projection(
                workspace=workspace,
                availability=availability,
                can_delete=can_delete,
            ),
        )

    def _deletion_projection(
        self,
        *,
        workspace: db_models.Workspace,
        availability: str,
        can_delete: bool,
    ) -> WorkspaceDeletionProjection:
        """Project the one destructive intent without exposing job internals."""

        if workspace.runtime_status != "deleting":
            return WorkspaceDeletionProjection(
                availability=availability,
                allowed_actions=["delete"] if can_delete else [],
            )

        active_job = self.jobs.find_active_lifecycle_job(
            workspace_id=workspace.id,
            operation=WORKSPACE_DELETE,
        )
        if active_job is not None:
            return WorkspaceDeletionProjection(
                availability="deleting",
                phase=self._deletion_job_phase(active_job),
                status=active_job.status,
            )

        failed_job = self.jobs.find_latest_failed_job(
            workspace_id=workspace.id,
            operation=WORKSPACE_DELETE,
        )
        if failed_job is not None:
            return WorkspaceDeletionProjection(
                availability="blocked",
                allowed_actions=["retry"] if can_delete else [],
                phase=self._deletion_job_phase(failed_job),
                status="failed",
                error_code=failed_job.error_code,
            )

        return WorkspaceDeletionProjection(
            availability="blocked",
            allowed_actions=["retry"] if can_delete else [],
            status="failed",
            error_code="WORKSPACE_DELETE_ATTEMPT_UNAVAILABLE",
        )

    @staticmethod
    def _deletion_job_phase(
        job: db_models.WorkspaceRuntimeJob,
    ) -> WorkspaceDeletionPhase:
        if job.status == "queued":
            return cast(WorkspaceDeletionPhase, WORKSPACE_DELETE_PHASE_QUEUED)
        phase = job.job_metadata.get("phase")
        if isinstance(phase, str) and phase in WORKSPACE_DELETE_PHASES:
            return cast(WorkspaceDeletionPhase, phase)
        return cast(
            WorkspaceDeletionPhase,
            WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS,
        )

    def _reconcile_orphan_transient(
        self,
        *,
        workspace: db_models.Workspace,
    ) -> db_models.Workspace:
        if workspace.provisioner != "kubernetes" or workspace.runtime_status not in {
            "starting",
            "running",
            "stopping",
            "restarting",
            "deleting",
        }:
            return workspace
        workspace_id = workspace.id
        self.db.rollback()
        try:
            snapshot = self.custom_resources.fetch_workspace_status_snapshot(
                workspace_id
            )
            if snapshot is not None:
                self.custom_resources.apply_workspace_status_snapshot(snapshot)
        except Exception:
            self.db.rollback()
            logger.warning(
                "Workspace availability orphan reconciliation failed",
                extra={"workspace_id": workspace_id},
            )
        refreshed = self.db.get(
            db_models.Workspace,
            workspace_id,
            populate_existing=True,
        )
        if refreshed is None:
            raise self._error("WORKSPACE_NOT_FOUND")
        return refreshed

    def request_action(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        action: Literal["start", "retry", "rebuild"],
        correlation_id: str,
    ) -> WorkspaceAvailabilityActionResponse:
        self._require_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
        )
        availability = self.get(
            actor=actor,
            workspace_id=workspace_id,
        )
        if action not in availability.allowed_actions:
            raise self._error("WORKSPACE_AVAILABILITY_ACTION_NOT_ALLOWED")
        self.db.rollback()

        lifecycle = WorkspaceLifecycleService(self.db)
        if action == "retry":
            if availability.reason_code == "WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED":
                job = self._retry_failed_access_recycle(
                    actor=actor,
                    workspace_id=workspace_id,
                    correlation_id=correlation_id,
                )
                runtime_status = availability.runtime_status or "error"
            else:
                result = lifecycle.request_start(
                    actor=actor,
                    workspace_id=workspace_id,
                    correlation_id=correlation_id,
                )
                job = result.job
                runtime_status = result.runtime_status
        elif action == "rebuild":
            result = lifecycle.request_rebuild(
                actor=actor,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
            )
            job = result.job
            runtime_status = result.runtime_status
        else:
            result = lifecycle.request_start(
                actor=actor,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
            )
            job = result.job
            runtime_status = result.runtime_status

        self._publish_after_commit(job.id)
        return WorkspaceAvailabilityActionResponse(
            workspace_id=workspace_id,
            action=action,
            job_id=job.id,
            status=runtime_status,
            reason_code="WORKSPACE_AVAILABILITY_ACTION_ACCEPTED",
        )

    def _retry_failed_access_recycle(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> db_models.WorkspaceRuntimeJob:
        try:
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise self._error("WORKSPACE_NOT_FOUND")
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_LIFECYCLE_EXECUTE,
            )
            failed_job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation == WORKSPACE_ACCESS_RECYCLE,
                    db_models.WorkspaceRuntimeJob.status == "failed",
                    db_models.WorkspaceRuntimeJob.target_revision
                    == workspace.runtime_access_revision,
                )
                .order_by(
                    db_models.WorkspaceRuntimeJob.finished_at.desc(),
                    db_models.WorkspaceRuntimeJob.id.desc(),
                )
                .limit(1)
                .with_for_update()
            )
            if failed_job is None:
                self._raise_action_not_allowed()
            retry = self.jobs.enqueue_retry_for_failed_job(
                failed_job_id=failed_job.id,
                correlation_id=correlation_id,
                scheduled_at=datetime.now(timezone.utc),
            )
            if retry is None:
                self._raise_action_not_allowed()
            self.db.commit()
            return retry.job
        except WorkspaceAvailabilityError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _publish_after_commit(job_id: str) -> None:
        try:
            current_app.send_task(_RUNTIME_JOB_TASK, args=[job_id])
        except Exception:
            logger.warning(
                "Workspace availability action publish failed; recovery will retry",
                extra={"job_id": job_id},
            )

    def _global_state(
        self,
        workspace: db_models.Workspace,
    ) -> tuple[str, str, int | None]:
        runtime_status = workspace.runtime_status
        if runtime_status == "deleting":
            return self._state(
                "WORKSPACE_DELETING",
                _TRANSITION_RETRY_AFTER_MS,
            )
        if runtime_status == "starting":
            return self._state(
                "WORKSPACE_RUNTIME_STARTING",
                _TRANSITION_RETRY_AFTER_MS,
            )
        if runtime_status == "restarting":
            return self._state(
                "WORKSPACE_RUNTIME_RESTARTING",
                _TRANSITION_RETRY_AFTER_MS,
            )
        if runtime_status == "stopping":
            return self._state(
                "WORKSPACE_RUNTIME_STOPPING",
                _TRANSITION_RETRY_AFTER_MS,
            )
        if runtime_status == "stopped":
            return self._state("WORKSPACE_RUNTIME_STOPPED", None)
        if runtime_status == "error":
            return self._state("WORKSPACE_RUNTIME_ERROR", None)
        if runtime_status != "running" or workspace.runtime_instance_id is None:
            return self._state("WORKSPACE_RUNTIME_INSTANCE_UNAVAILABLE", None)
        if workspace.runtime_control_instance_id != workspace.runtime_instance_id:
            return self._state(
                "WORKSPACE_RUNTIME_INSTANCE_MISMATCH",
                _TRANSITION_RETRY_AFTER_MS,
            )
        active_access_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation == WORKSPACE_ACCESS_RECYCLE,
                db_models.WorkspaceRuntimeJob.target_revision
                == workspace.runtime_access_revision,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
        )
        if (
            workspace.runtime_access_revision
            != workspace.runtime_access_observed_revision
            or active_access_job is not None
        ):
            latest_job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation == WORKSPACE_ACCESS_RECYCLE,
                    db_models.WorkspaceRuntimeJob.target_revision
                    == workspace.runtime_access_revision,
                )
                .order_by(
                    db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                    db_models.WorkspaceRuntimeJob.id.desc(),
                )
                .limit(1)
            )
            if latest_job is not None and latest_job.status == "failed":
                return self._state(
                    "WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED",
                    None,
                )
            return self._state(
                "WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS",
                _TRANSITION_RETRY_AFTER_MS,
            )
        if workspace.runtime_desired_revision != workspace.runtime_observed_revision:
            active_mount_job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation
                    == KNOWLEDGE_BASE_MOUNT_RECONCILE,
                    db_models.WorkspaceRuntimeJob.target_revision
                    == workspace.knowledge_base_mount_desired_revision,
                    db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
                )
                .limit(1)
            )
            if active_mount_job is None:
                return self._state(
                    "WORKSPACE_RUNTIME_RESTARTING",
                    _TRANSITION_RETRY_AFTER_MS,
                )
        lifecycle_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation.in_(
                    WORKSPACE_LIFECYCLE_OPERATIONS
                ),
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
        )
        if lifecycle_job is not None:
            lifecycle_state = {
                WORKSPACE_START: "WORKSPACE_RUNTIME_STARTING",
                WORKSPACE_STOP: "WORKSPACE_RUNTIME_STOPPING",
                WORKSPACE_DELETE: "WORKSPACE_DELETING",
            }[lifecycle_job.operation]
            return self._state(
                lifecycle_state,
                _TRANSITION_RETRY_AFTER_MS,
            )
        return self._state("WORKSPACE_READY", None)

    @staticmethod
    def _allowed_actions(
        *,
        reason_code: str,
        can_manage: bool,
    ) -> list[str]:
        actions = list(
            workspace_availability_reason(reason_code).default_allowed_actions
        )
        if can_manage:
            return actions
        return [action for action in actions if action == "return"]

    @staticmethod
    def _state(
        reason_code: str,
        retry_after_ms: int | None,
    ) -> tuple[str, str, int | None]:
        contract = workspace_availability_reason(reason_code)
        return contract.availability, reason_code, retry_after_ms

    @staticmethod
    def _knowledge_mount_status(
        workspace: db_models.Workspace,
    ) -> KnowledgeMountAvailability:
        if workspace.knowledge_base_mount_sync_status == "degraded":
            status = "degraded"
        elif (
            workspace.knowledge_base_mount_sync_status == "ready"
            and workspace.knowledge_base_mount_desired_revision
            == workspace.knowledge_base_mount_observed_revision
            and workspace.knowledge_base_mount_active_revision
            == workspace.knowledge_base_mount_observed_revision
        ):
            status = "ready"
        else:
            status = "syncing"
        return KnowledgeMountAvailability(
            status=status,
            desired_revision=workspace.knowledge_base_mount_desired_revision,
            observed_revision=workspace.knowledge_base_mount_observed_revision,
            last_known_good_revision=(workspace.knowledge_base_mount_active_revision),
            error_code=workspace.knowledge_base_mount_error_code,
            compensating=(workspace.knowledge_base_mount_sync_status == "compensating"),
        )

    def _require_operation(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
    ):
        try:
            return self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            code = (
                "WORKSPACE_AUTHENTICATION_REQUIRED"
                if exc.http_status == 401
                else "WORKSPACE_ACCESS_DENIED"
            )
            raise WorkspaceAvailabilityError(code, exc.http_status) from exc

    @staticmethod
    def _raise_action_not_allowed() -> NoReturn:
        raise WorkspaceAvailabilityService._error(
            "WORKSPACE_AVAILABILITY_ACTION_NOT_ALLOWED"
        )

    @staticmethod
    def _error(reason_code: str) -> WorkspaceAvailabilityError:
        contract = workspace_availability_reason(reason_code)
        return WorkspaceAvailabilityError(reason_code, contract.http_status)


__all__ = [
    "WorkspaceAvailabilityError",
    "WorkspaceAvailabilityService",
]
