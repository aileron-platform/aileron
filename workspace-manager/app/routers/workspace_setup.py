"""Workspace initialization sync related APIs"""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.core.openapi import build_responses
from app.models import WorkspaceSetupStatus
from app.services import get_workspace_setup_service
from app.services.git_service import GitBranchLookupError, get_git_service
from app.services.workspace_setup_service import WorkspaceSetupError, WorkspaceSetupService

router = APIRouter(prefix="/workspaces/{workspace_id}/setup", tags=["workspace-setup"])


class GitBranchesResponse(BaseModel):
    """Git branch list response."""
    branches: List[str]
    total: int


def _translate_workspace_setup_value_error(translate, exc: Exception, *, operation: str) -> str:
    code = getattr(exc, "code", "")
    if code == "WORKSPACE_NOT_FOUND":
        return translate("workspace.not_found")
    if code == "WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY":
        return translate("workspace_setup.sync.runtime_not_ready")
    if code == "WORKSPACE_SETUP_STATUS_RUNTIME_NOT_READY":
        return translate("workspace_setup.status.runtime_not_ready")
    return translate(f"workspace_setup.{operation}.failed")


def _translate_git_branch_error(translate, exc: Exception) -> str:
    code = getattr(exc, "code", "")
    if code == "WORKSPACE_SETUP_GIT_EMPTY_URL":
        return translate("workspace_setup.git.empty_url")
    if code == "WORKSPACE_SETUP_GIT_INVALID_URL":
        return translate("workspace_setup.git.invalid_url")
    if code == "WORKSPACE_SETUP_GIT_AUTH_FAILED":
        return translate("workspace_setup.git.auth_failed")
    if code == "WORKSPACE_SETUP_GIT_RESOLVE_FAILED":
        return translate("workspace_setup.git.resolve_failed")
    if code == "WORKSPACE_SETUP_GIT_REPOSITORY_NOT_FOUND":
        return translate("workspace_setup.git.repository_not_found")
    if code == "WORKSPACE_SETUP_GIT_TIMEOUT":
        return translate("workspace_setup.git.timeout")
    if code == "WORKSPACE_SETUP_GIT_FETCH_FAILED":
        return translate("workspace_setup.git.fetch_failed")
    return translate("workspace_setup.git.fetch_failed")


@router.post(
    "/sync",
    response_model=WorkspaceSetupStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start workspace initialization sync",
    responses=build_responses(404, 409, 422, 500),
)
async def trigger_workspace_initial_sync(
    workspace_id: str,
    request: Request,
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """Start initial sync process for newly created workspace."""
    try:
        return await service.run_initial_sync(workspace_id)
    except WorkspaceSetupError as exc:
        if getattr(exc, "code", "") == "WORKSPACE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
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
    responses=build_responses(404, 409, 500),
)
async def get_workspace_setup_status(
    workspace_id: str,
    request: Request,
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """Query latest status of workspace initialization sync.

    This exposes manager's own `WorkspaceSetupStatus` contract to frontend,
    does not directly forward workspace-runtime's raw response format.
    """
    try:
        return await service.fetch_runtime_status(workspace_id)
    except WorkspaceSetupError as exc:
        if getattr(exc, "code", "") == "WORKSPACE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_workspace_setup_value_error(
                request.state.translate, exc, operation="status"
            ),
        ) from exc


@router.get(
    "/git-branches",
    response_model=GitBranchesResponse,
    summary="Get remote Git branch list",
    responses=build_responses(400, 500),
)
async def get_git_branches(
    workspace_id: str,
    request: Request,
    git_url: str = Query(..., description="Git repository URL"),
) -> GitBranchesResponse:
    """
    Get branch list of Git repository.

    This API uses workspace-manager's SSH key to authenticate private repositories.
    No authentication required for public repositories.

    Args:
        workspace_id: Workspace ID (for logging)
        git_url: Git repository URL

    Returns:
        List of branches

    Raises:
        400: Invalid Git URL
        500: Failed to get branch list
    """
    # Check if SSH key exists
    ssh_key_path = Path.home() / ".ssh" / "id_rsa"

    # Create GitService instance
    git_service = get_git_service(
        ssh_key_path=ssh_key_path if ssh_key_path.exists() else None
    )

    try:
        branches = git_service.get_remote_branches(git_url)
        return GitBranchesResponse(branches=branches, total=len(branches))
    except GitBranchLookupError as exc:
        # Git URL invalid or authentication failed
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_git_branch_error(request.state.translate, exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_git_branch_error(request.state.translate, exc)
        ) from exc


__all__ = ["router"]
