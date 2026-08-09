"""Instance-bound, action-aware Workspace Runtime authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.workspace.execution_plane_observation import (
    WorkspaceExecutionPlaneObservationService,
)

_RUNTIME_ACCESS_ACTIONS = frozenset(
    {
        "runtime_read",
        "runtime_write",
        "workspace_settings",
        "terminal",
        "agent",
        "automation",
        "browser_automation",
    }
)


@dataclass(frozen=True)
class WorkspaceRuntimeAccessError(Exception):
    """Stable Runtime gate denial consumed by the HTTP router."""

    code: str
    http_status: int


@dataclass(frozen=True)
class WorkspaceRuntimeAccessContext:
    """Fresh actor and current Workspace generation authorized by one request."""

    actor: AuthorizationActor
    workspace: db_models.Workspace


class WorkspaceRuntimeAccessService:
    """Authorize one actor and one action against the current generation."""

    def __init__(
        self,
        db: Session,
        *,
        execution_plane_observer: (
            WorkspaceExecutionPlaneObservationService | None
        ) = None,
    ) -> None:
        self.db = db
        self.authorization = AuthorizationOperationPolicy(db)
        self.execution_plane_observer = (
            execution_plane_observer
            if execution_plane_observer is not None
            else WorkspaceExecutionPlaneObservationService(db)
        )

    def authorize(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        action: str | None,
        runtime_instance_id: str | None,
    ) -> WorkspaceRuntimeAccessContext:
        canonical_instance_id = self._validate_request(action, runtime_instance_id)
        canonical_action = cast(str, action)
        operation = self._operation_for_action(canonical_action)
        self._require_operation(
            actor=actor,
            workspace_id=workspace_id,
            operation=operation,
            action=canonical_action,
        )
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise WorkspaceRuntimeAccessError("WORKSPACE_NOT_FOUND", 404)

        return self._authorize_workspace(
            actor=actor,
            workspace=workspace,
            action=canonical_action,
            runtime_instance_id=canonical_instance_id,
        )

    def authorize_current_browser_automation(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
    ) -> WorkspaceRuntimeAccessContext:
        """Authorize pairing against the current ready browser workload."""

        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
            )
        except AuthorizationOperationError as exc:
            raise WorkspaceRuntimeAccessError(
                exc.error_code,
                exc.http_status,
            ) from exc
        workspace = self.db.scalar(
            select(db_models.Workspace)
            .where(db_models.Workspace.id == workspace_id)
            .with_for_update()
        )
        if workspace is None:
            raise WorkspaceRuntimeAccessError("WORKSPACE_NOT_FOUND", 404)

        context = self._authorize_workspace(
            actor=actor,
            workspace=workspace,
            action="browser_automation",
            runtime_instance_id=workspace.runtime_instance_id,
        )
        if (
            workspace.browser_status != "running"
            or not isinstance(workspace.browser_container_id, str)
            or not workspace.browser_container_id
            or workspace.browser_container_id != workspace.browser_container_id.strip()
            or len(workspace.browser_container_id) > 256
        ):
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_BROWSER_WORKLOAD_NOT_READY",
                423,
            )
        return context

    def _authorize_workspace(
        self,
        *,
        actor: AuthorizationActor,
        workspace: db_models.Workspace,
        action: str,
        runtime_instance_id: str | None,
    ) -> WorkspaceRuntimeAccessContext:
        self._require_converged_runtime_access(workspace)
        canonical_instance_id = self._canonical_current_instance_id(runtime_instance_id)
        if (
            workspace.runtime_status != "running"
            or workspace.runtime_instance_id != canonical_instance_id
        ):
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_INSTANCE_MISMATCH",
                423,
            )
        observation = self.execution_plane_observer.observe(workspace)
        if observation.state == "drift":
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_EXECUTION_PLANE_DRIFT",
                409,
            )
        if observation.state == "unavailable":
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE",
                503,
            )
        return WorkspaceRuntimeAccessContext(actor=actor, workspace=workspace)

    def _require_operation(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
        action: str,
    ) -> None:
        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            raise WorkspaceRuntimeAccessError(
                (
                    "WORKSPACE_ACCESS_DENIED"
                    if exc.http_status == 404
                    else "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
                ),
                exc.http_status,
            ) from exc

    @staticmethod
    def _operation_for_action(action: str) -> OperationId:
        operation = {
            "runtime_read": OperationId.WORKSPACE_DETAIL_READ,
            "runtime_write": OperationId.WORKSPACE_CONTENT_WRITE,
            "workspace_settings": OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
            "terminal": OperationId.WORKSPACE_TERMINAL_USE,
            "agent": OperationId.WORKSPACE_AGENT_CHAT_USE,
            "automation": OperationId.WORKSPACE_AUTOMATION_EXECUTE,
            "browser_automation": OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
        }.get(action)
        if operation is None:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_ACTION_INVALID",
                422,
            )
        return operation

    @staticmethod
    def _validate_request(
        action: str | None,
        runtime_instance_id: str | None,
    ) -> str:
        if action not in _RUNTIME_ACCESS_ACTIONS or not runtime_instance_id:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_ACTION_INVALID",
                422,
            )
        try:
            parsed = UUID(runtime_instance_id)
        except ValueError as exc:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_ACTION_INVALID",
                422,
            ) from exc
        if str(parsed) != runtime_instance_id:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_ACTION_INVALID",
                422,
            )
        return runtime_instance_id

    @staticmethod
    def _canonical_current_instance_id(runtime_instance_id: str | None) -> str:
        if not runtime_instance_id:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_INSTANCE_MISMATCH",
                423,
            )
        try:
            parsed = UUID(runtime_instance_id)
        except ValueError as exc:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_INSTANCE_MISMATCH",
                423,
            ) from exc
        if str(parsed) != runtime_instance_id:
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_INSTANCE_MISMATCH",
                423,
            )
        return runtime_instance_id

    def _require_converged_runtime_access(
        self,
        workspace: db_models.Workspace,
    ) -> None:
        if (
            workspace.runtime_access_revision
            == workspace.runtime_access_observed_revision
        ):
            return
        latest_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
        )
        if latest_job is not None and latest_job.status == "failed":
            raise WorkspaceRuntimeAccessError(
                "WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED",
                423,
            )
        raise WorkspaceRuntimeAccessError(
            "WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS",
            423,
        )


__all__ = [
    "WorkspaceRuntimeAccessContext",
    "WorkspaceRuntimeAccessError",
    "WorkspaceRuntimeAccessService",
]
