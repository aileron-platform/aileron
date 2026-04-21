"""Workspace 初始化同步相關 API"""

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
    """Git 分支列表回應"""
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
    summary="啟動 Workspace 初始化同步",
    responses=build_responses(404, 409, 422, 500),
)
async def trigger_workspace_initial_sync(
    workspace_id: str,
    request: Request,
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """啟動新建 Workspace 的初始同步流程"""
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
    summary="查詢初始化同步狀態",
    responses=build_responses(404, 409, 500),
)
async def get_workspace_setup_status(
    workspace_id: str,
    request: Request,
    service: WorkspaceSetupService = Depends(get_workspace_setup_service),
) -> WorkspaceSetupStatus:
    """查詢 Workspace 初始化同步的最新狀態

    這裡對 frontend 暴露的是 manager 自己的 `WorkspaceSetupStatus` 契約，
    不直接透傳 workspace-runtime 的原始回應格式。
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
    summary="取得遠端 Git 分支列表",
    responses=build_responses(400, 500),
)
async def get_git_branches(
    workspace_id: str,
    request: Request,
    git_url: str = Query(..., description="Git repository URL"),
) -> GitBranchesResponse:
    """
    獲取 Git repository 的分支列表

    此 API 會使用 workspace-manager 的 SSH key 來認證私有倉庫。
    如果是公開倉庫，則不需要認證。

    Args:
        workspace_id: Workspace ID（用於日誌記錄）
        git_url: Git repository URL

    Returns:
        分支列表

    Raises:
        400: Git URL 無效
        500: 無法獲取分支列表
    """
    # 檢查 SSH key 是否存在
    ssh_key_path = Path.home() / ".ssh" / "id_rsa"

    # 創建 GitService 實例
    git_service = get_git_service(
        ssh_key_path=ssh_key_path if ssh_key_path.exists() else None
    )

    try:
        branches = git_service.get_remote_branches(git_url)
        return GitBranchesResponse(branches=branches, total=len(branches))
    except GitBranchLookupError as exc:
        # Git URL 無效或認證失敗
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
