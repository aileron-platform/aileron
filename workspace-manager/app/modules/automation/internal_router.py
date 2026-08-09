"""Internal Runtime-to-Manager Automation protocol routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import get_db
from app.modules.auth.internal_runtime import require_internal_runtime_identity
from app.modules.automation.execution import AutomationExecutionService
from app.modules.automation.models import (
    AutomationExecution,
    ClaimRequest,
    ClaimResponse,
    CompletionRequest,
    ReconcileRestartRequest,
)
from app.modules.automation.repository import (
    AutomationRepository,
    AutomationRepositoryError,
)

router = APIRouter(prefix="/internal/automation", tags=["Internal Automation"])


def get_internal_execution_service(
    db: Session = Depends(get_db),
) -> AutomationExecutionService:
    return AutomationExecutionService(AutomationRepository(db))


def _require_internal(
    request: Request,
    *,
    workspace_id: str,
    db: Session,
) -> None:
    require_internal_runtime_identity(request, workspace_id=workspace_id, db=db)


def _require_workspace_identity(header_workspace_id: str, workspace_id: str) -> None:
    if header_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "workspace_identity_mismatch"},
        )


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return exc
        code = str(exc.detail)
        return HTTPException(exc.status_code, detail={"code": code})
    return HTTPException(
        status_code=getattr(exc, "status_code", 500),
        detail={"code": str(getattr(exc, "code", "automation_request_failed"))},
    )


@router.post("/executions/claim", response_model=ClaimResponse)
def claim_execution(
    payload: ClaimRequest,
    request: Request,
    workspace_header: str = Header(alias="X-Workspace-ID"),
    service: AutomationExecutionService = Depends(get_internal_execution_service),
) -> ClaimResponse | Response:
    _require_internal(
        request,
        workspace_id=payload.workspace_id,
        db=service.repository.db,
    )
    _require_workspace_identity(workspace_header, payload.workspace_id)
    try:
        claimed = service.claim(
            workspace_id=payload.workspace_id,
            runner_instance_id=payload.runner_instance_id,
            claim_request_id=payload.claim_request_id,
        )
        if claimed is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return claimed
    except (AutomationRepositoryError, HTTPException) as exc:
        raise _translate(exc) from exc


@router.post("/executions/{execution_id}/complete", response_model=AutomationExecution)
def complete_execution(
    execution_id: str,
    payload: CompletionRequest,
    request: Request,
    workspace_header: str = Header(alias="X-Workspace-ID"),
    service: AutomationExecutionService = Depends(get_internal_execution_service),
) -> AutomationExecution:
    try:
        _require_internal(
            request,
            workspace_id=workspace_header,
            db=service.repository.db,
        )
        execution = service.repository.db.get(
            db_models.AutomationExecution, execution_id
        )
        if execution is None:
            raise AutomationRepositoryError("automation_execution_not_found", 404)
        _require_workspace_identity(workspace_header, execution.workspace_id)
        return service.complete(execution_id=execution_id, payload=payload)
    except (AutomationRepositoryError, HTTPException) as exc:
        raise _translate(exc) from exc


@router.post(
    "/workspaces/{workspace_id}/reconcile-restart",
    response_model=list[AutomationExecution],
)
def reconcile_restart(
    workspace_id: str,
    payload: ReconcileRestartRequest,
    request: Request,
    workspace_header: str = Header(alias="X-Workspace-ID"),
    service: AutomationExecutionService = Depends(get_internal_execution_service),
) -> list[AutomationExecution]:
    _require_internal(
        request,
        workspace_id=workspace_id,
        db=service.repository.db,
    )
    _require_workspace_identity(workspace_header, workspace_id)
    _require_workspace_identity(payload.workspace_id, workspace_id)
    try:
        return service.reconcile_restart(
            workspace_id=workspace_id,
            new_runner_instance_id=payload.new_runner_instance_id,
        )
    except (AutomationRepositoryError, HTTPException) as exc:
        raise _translate(exc) from exc


__all__ = ["router"]
