"""Authorization policy for the automation control plane."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.authorization.actor import AuthorizationActor, actor_from_valid_user
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.identity.authorization import PlatformAuthorizationService
from app.modules.workspace.catalog import WorkspaceService


class AutomationAuthorizationService:
    """Combine platform capability and public workspace-access services."""

    def __init__(
        self,
        db: Session,
        *,
        platform: PlatformAuthorizationService | None = None,
        workspaces: WorkspaceService | None = None,
    ) -> None:
        self.db = db
        self.platform = platform or PlatformAuthorizationService(db)
        self.workspaces = workspaces or WorkspaceService(db)
        self.operations = AuthorizationOperationPolicy(db)

    def require_read(self, *, actor: AuthorizationActor, workspace_id: str) -> None:
        self._require(actor, workspace_id, OperationId.WORKSPACE_DETAIL_READ)

    def require_execute(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
    ) -> None:
        self._require(actor, workspace_id, OperationId.WORKSPACE_AUTOMATION_EXECUTE)

    def require_creator_execute(self, *, user_id: str, workspace_id: str) -> None:
        user = self.platform.get_valid_user(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"errorCode": "automation_principal_inactive"},
            )
        try:
            self.require_execute(
                actor=actor_from_valid_user(user),
                workspace_id=workspace_id,
            )
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"errorCode": "automation_principal_inactive"},
            ) from exc

    def accessible_workspace_ids(self, *, actor: AuthorizationActor) -> list[str]:
        return self.workspaces.list_accessible_workspace_ids(
            current_user_id=actor.user_id
        )

    def _require(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
    ) -> None:
        try:
            self.operations.require_workspace_operation(
                actor,
                workspace_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail={"errorCode": exc.error_code},
            ) from exc


__all__ = ["AutomationAuthorizationService"]
