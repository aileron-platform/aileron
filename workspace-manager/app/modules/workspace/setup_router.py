"""Workspace initialization sync related APIs"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.core.api_error import authorization_error_detail
from app.modules.workspace.dependencies import get_workspace_setup_service
from app.modules.workspace.models import WorkspaceSetupStatus
from app.modules.workspace.setup import (
    WorkspaceSetupError,
    WorkspaceSetupService,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/setup", tags=["workspace-setup"])


def _translate_workspace_setup_value_error(
    translate, exc: Exception, *, operation: str
) -> str:
    code = getattr(exc, "code", "")
    if code == "WORKSPACE_NOT_FOUND":
        return translate("workspace.not_found")
    if code == "WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY":
        return translate("workspace_setup.sync.runtime_not_ready")
    if code == "WORKSPACE_SETUP_STATUS_RUNTIME_NOT_READY":
        return translate("workspace_setup.status.runtime_not_ready")
    return translate(f"workspace_setup.{operation}.failed")


def _require_workspace_operation(
    request: Request,
    db: Session,
    *,
    actor: AuthorizationActor,
    workspace_id: str,
    operation: OperationId,
) -> None:
    try:
        AuthorizationOperationPolicy(db).require_workspace_operation(
            actor,
            workspace_id,
            operation,
        )
    except AuthorizationOperationError as exc:
        message = (
            request.state.translate("workspace.not_found")
            if exc.http_status == status.HTTP_404_NOT_FOUND
            else request.state.translate("workspace.access_denied")
        )
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                message,
            ),
        ) from exc


@router.post(
    "/sync",
    response_model=WorkspaceSetupStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start workspace initialization sync",
    responses=build_responses(401, 403, 404, 409, 422, 500),
)
async def trigger_workspace_initial_sync(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """Start initial sync process for newly created workspace."""
    _require_workspace_operation(
        request,
        db,
        actor=actor,
        workspace_id=workspace_id,
        operation=OperationId.WORKSPACE_CONTENT_WRITE,
    )
    try:
        return await service.run_initial_sync(workspace_id)
    except WorkspaceSetupError as exc:
        if getattr(exc, "code", "") == "WORKSPACE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_workspace_setup_value_error(
                request.state.translate, exc, operation="sync"
            ),
        ) from exc


@router.get(
    "/status",
    response_model=WorkspaceSetupStatus,
    summary="Query initialization sync status",
    responses=build_responses(401, 403, 404, 409, 500),
)
async def get_workspace_setup_status(
    workspace_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    db: Session = Depends(get_db),
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """Query latest status of workspace initialization sync.

    This exposes manager's own `WorkspaceSetupStatus` contract to frontend,
    does not directly forward workspace-runtime's raw response format.
    """
    _require_workspace_operation(
        request,
        db,
        actor=actor,
        workspace_id=workspace_id,
        operation=OperationId.WORKSPACE_DETAIL_READ,
    )
    try:
        return await service.fetch_runtime_status(workspace_id)
    except WorkspaceSetupError as exc:
        if getattr(exc, "code", "") == "WORKSPACE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found"),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_workspace_setup_value_error(
                request.state.translate, exc, operation="status"
            ),
        ) from exc


__all__ = ["router"]
