"""Unversioned internal Automation cancellation route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from app.config.settings import get_settings
from app.modules.internal.dependencies import verify_manager_assertion

from .dependencies import get_automation_worktree_service
from .schemas import CancelExecutionRequest
from .worktree import AutomationWorktreeError, AutomationWorktreeService

router = APIRouter(
    prefix="/internal/automation",
    tags=["Internal Automation"],
    dependencies=[Depends(verify_manager_assertion)],
)


@router.post("/worktree/preflight", status_code=204)
async def preflight_worktree(
    workspace_id: str = Header(alias="X-Workspace-ID"),
    service: AutomationWorktreeService = Depends(get_automation_worktree_service),
) -> Response:
    """Validate workspace Git/worktree readiness before creating a job."""
    if workspace_id != get_settings().AILERON_WORKSPACE_ID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "workspace_mismatch"},
        )
    try:
        await service.validate_workspace()
    except AutomationWorktreeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.error_code},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/executions/{execution_id}/cancel", status_code=204)
async def cancel_execution(
    execution_id: str,
    payload: CancelExecutionRequest,
    request: Request,
) -> Response:
    runner = getattr(request.app.state, "automation_runner", None)
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "automation_runner_unavailable"},
        )
    try:
        await runner.cancel_execution(
            execution_id=execution_id,
            runner_instance_id=payload.runner_instance_id,
            claim_request_id=payload.claim_request_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "execution_not_owned"},
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
