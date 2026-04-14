"""工作區 API"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from app.core.openapi import build_responses
from app.models import (
    WorkspaceCreateRequest,
    WorkspaceDetail,
    WorkspaceListResponse,
    WorkspaceUpdateRequest,
    WorkspaceRuntimeLogEntry,
)
from app.services import get_runtime_provision_service, get_workspace_service
from app.services.runtime_provision_service import (
    RuntimeProvisionService,
    run_runtime_provision_task,
)
from app.services.workspace_custom_resource_service import (
    run_apply_workspace_custom_resource_task,
)
from app.services.runtime_sync_service import RuntimeSyncService
from app.services.workspace_service import WorkspaceService
from app.services.workspace_lifecycle_service import (
    run_delete_workspace_task,
    run_restart_workspace_task,
    run_restart_browser_task,
    run_restart_nextjs_task,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_RUNTIME_LOG_STAGE_KEYS = {
    "queued": "workspace.runtime_log.queued",
    "provisioning": "workspace.runtime_log.provisioning",
    "preparing": "workspace.runtime_log.preparing",
    "provisioned": "workspace.runtime_log.provisioned",
    "browser_starting": "workspace.runtime_log.browser_starting",
    "browser_ready": "workspace.runtime_log.browser_ready",
    "nextjs_starting": "workspace.runtime_log.nextjs_starting",
    "nextjs_ready": "workspace.runtime_log.nextjs_ready",
    "completed": "workspace.runtime_log.completed",
    "browser_restarting": "workspace.runtime_log.browser_restarting",
    "browser_running": "workspace.runtime_log.browser_running",
    "nextjs_restarting": "workspace.runtime_log.nextjs_restarting",
    "nextjs_running": "workspace.runtime_log.nextjs_running",
}

_RUNTIME_LOG_EXACT_KEYS = {
    "沒有關聯的 Browser 容器": "workspace.runtime_log.browser_not_found",
    "No Browser container found for this workspace": "workspace.runtime_log.browser_not_found",
    "沒有關聯的 Next.js 容器": "workspace.runtime_log.nextjs_not_found",
    "No Next.js container found for this workspace": "workspace.runtime_log.nextjs_not_found",
}

_RUNTIME_LOG_PREFIX_KEYS = (
    ("Browser 容器啟動失敗: ", "workspace.runtime_log.browser_error"),
    ("Browser container startup failed: ", "workspace.runtime_log.browser_error"),
    ("Next.js 容器啟動失敗: ", "workspace.runtime_log.nextjs_error"),
    ("Next.js container startup failed: ", "workspace.runtime_log.nextjs_error"),
    ("重建失敗: ", "workspace.runtime_log.rebuild_error"),
    ("Rebuild failed: ", "workspace.runtime_log.rebuild_error"),
    ("已刪除目錄: ", "workspace.runtime_log.volume_removed"),
    ("Removed directory: ", "workspace.runtime_log.volume_removed"),
    ("刪除目錄失敗: ", "workspace.runtime_log.volume_error"),
    ("Failed to remove directory: ", "workspace.runtime_log.volume_error"),
)


def _translate_runtime_log_message(
    stage: str,
    message: str,
    translate,
) -> str:
    exact_key = _RUNTIME_LOG_EXACT_KEYS.get(message)
    if exact_key:
        return translate(exact_key)

    for prefix, key in _RUNTIME_LOG_PREFIX_KEYS:
        if message.startswith(prefix):
            detail = message[len(prefix):].strip()
            return translate(key, detail=detail)

    stage_key = _RUNTIME_LOG_STAGE_KEYS.get(stage)
    if stage_key:
        return translate(stage_key)

    return message


@router.get(
    "/",
    response_model=WorkspaceListResponse,
    summary="列出工作區",
    responses=build_responses(401, 422, 500),
)
def list_workspaces(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceListResponse:
    # 強制以 JWT 中的使用者 ID 過濾，防止越權存取其他使用者的工作區
    current_user_id = getattr(request.state, "user_id", None)
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return service.list(
        page=page,
        page_size=page_size,
        owner_id=current_user_id,
        status=status,
        search=search,
    )


@router.post(
    "/",
    response_model=WorkspaceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="建立工作區",
    responses=build_responses(400, 401, 422, 500),
)
def create_workspace(
    request: Request,
    payload: WorkspaceCreateRequest,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    try:
        # 強制以 JWT 中的使用者 ID 作為 owner，避免 client 透過 payload 冒用其他使用者。
        current_user_id = getattr(request.state, "user_id", None)
        if not current_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=request.state.translate("auth.unauthenticated")
            )
        payload.owner_id = current_user_id

        workspace = service.create(payload)
        if workspace.provisioner == "kubernetes":
            background_tasks.add_task(run_apply_workspace_custom_resource_task, workspace.id)
        else:
            background_tasks.add_task(run_runtime_provision_task, workspace.id)
        return workspace
    except ValueError as exc:  # owner 不存在
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="取得工作區詳情",
    responses=build_responses(404, 500),
)
def get_workspace(
    workspace_id: str,
    request: Request,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    workspace = service.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found")
        )
    return workspace


@router.get(
    "/{workspace_id}/runtime-logs",
    response_model=list[WorkspaceRuntimeLogEntry],
    summary="取得 Runtime 佈署日誌",
    responses=build_responses(422, 500),
)
def get_workspace_runtime_logs(
    request: Request,
    workspace_id: str,
    limit: int = Query(100, ge=1, le=500),
    stage: Optional[str] = Query(None),
    service: RuntimeProvisionService = Depends(get_runtime_provision_service),
) -> list[WorkspaceRuntimeLogEntry]:
    logs = service.get_runtime_logs(workspace_id, limit=limit, stage=stage)
    if not logs:
        return []

    # 手動轉換資料庫物件到 Pydantic model
    result = []
    for log in logs:
        log_entry = WorkspaceRuntimeLogEntry(
            id=log.id,
            workspace_id=log.workspace_id,
            stage=log.stage,
            message=_translate_runtime_log_message(log.stage, log.message, request.state.translate),
            metadata=log.log_metadata,  # 映射 log_metadata 到 metadata
            created_at=log.created_at,
        )
        result.append(log_entry)

    return result


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="更新工作區",
    responses=build_responses(404, 422, 500),
)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceDetail:
    try:
        # 只有 firewall 配置變更需要額外同步到 workspace-runtime，其餘欄位由 manager 自行持久化。
        firewall_changed = payload.firewall is not None

        workspace = service.update(workspace_id, payload)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("workspace.not_found")
            )

        # 如果防火牆配置有變更，背景同步到 runtime
        if firewall_changed and workspace.firewall:
            background_tasks.add_task(
                _sync_firewall_to_runtime,
                workspace_id,
                workspace.firewall.model_dump(by_alias=True)
            )

        if workspace.provisioner == "kubernetes":
            background_tasks.add_task(run_apply_workspace_custom_resource_task, workspace.id)

        return workspace
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _sync_firewall_to_runtime(workspace_id: str, firewall_config: dict):
    """背景任務：同步防火牆設定到 workspace-runtime"""
    logger.info(f"開始背景同步防火牆設定 - workspace_id: {workspace_id}")

    try:
        from app.config.settings import get_settings

        if not get_settings().CILIUM_ENABLED:
            logger.info(
                "略過防火牆設定同步，因平台未啟用 Cilium - workspace_id: %s",
                workspace_id,
            )
            return
        sync_service = RuntimeSyncService()
        result = await sync_service.sync_firewall_to_runtime(workspace_id, firewall_config)

        if result.get("success"):
            logger.info(f"防火牆設定同步成功 - workspace_id: {workspace_id}")
        else:
            logger.warning(f"防火牆設定同步跳過 - workspace_id: {workspace_id}, reason: {result.get('message')}")

    except Exception as e:
        logger.error(f"防火牆設定同步失敗 - workspace_id: {workspace_id}, error: {e}", exc_info=True)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="刪除工作區",
    responses=build_responses(404, 500),
)
def delete_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """刪除工作區

    此操作會在背景執行以下步驟：
    1. 停止並刪除 Docker container
    2. 刪除掛載的資料目錄
    3. 刪除資料庫中的 workspace 記錄

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在時
    """
    # 檢查 workspace 是否存在
    workspace = service.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
        )

    # 標記為刪除中
    if not service.mark_workspace_deleting(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("workspace.deletion_failed")
        )

    # 加入背景任務
    background_tasks.add_task(run_delete_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.deletion_started"),
        "workspaceId": workspace_id,
        "status": "deleting"
    }


@router.post(
    "/{workspace_id}/rebuild",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重建工作區 Runtime",
    responses=build_responses(404, 500),
)
def rebuild_workspace(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區 Container

    此操作會在背景執行以下步驟：
    1. 重啟 Docker container
    2. 更新 workspace 狀態

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在時
    """
    # 檢查 workspace 是否存在
    workspace = service.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
        )

    # 標記為重啟中
    if not service.mark_workspace_rebuilding(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("workspace.restart_failed")
        )

    # 加入背景任務
    background_tasks.add_task(run_restart_workspace_task, workspace_id)

    return {
        "message": request.state.translate("workspace.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-browser",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重啟 Browser 容器",
    responses=build_responses(400, 404, 500),
)
def restart_browser(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區的 Browser 容器

    此操作會在背景執行以下步驟：
    1. 重啟 Browser Docker container
    2. 更新 browser_status 狀態

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID

    Raises:
        HTTPException: 當 workspace 不存在或沒有 Browser 容器時
    """
    # 檢查 workspace 是否存在
    workspace = service.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
        )

    # Docker 模式才需要檢查 Browser 容器是否存在
    if (
        workspace.provisioner != "kubernetes"
        and not workspace.runtime_status.browser_container_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=request.state.translate("workspace.browser.not_found")
        )

    # 標記 Browser 為重啟中
    if not service.mark_browser_restarting(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("workspace.browser.restart_failed")
        )

    # 加入背景任務
    background_tasks.add_task(run_restart_browser_task, workspace_id)

    return {
        "message": request.state.translate("workspace.browser.restart_started"),
        "workspaceId": workspace_id,
        "status": "restarting"
    }


@router.post(
    "/{workspace_id}/restart-nextjs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="重啟 Next.js 容器",
    responses=build_responses(400, 404, 500),
)
def restart_nextjs(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict:
    """重啟工作區的 Next.js 容器

    Args:
        workspace_id: Workspace ID
        background_tasks: FastAPI 背景任務
        service: Workspace 服務

    Returns:
        dict: 包含訊息和 workspace ID
    """
    workspace = service.get(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found_with_id", workspace_id=workspace_id)
        )

    if (
        workspace.provisioner != "kubernetes"
        and not workspace.runtime_status.nextjs_container_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Next.js container not found for this workspace"
        )

    # 標記 Next.js 為重啟中
    if not service.mark_nextjs_restarting(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark Next.js container as restarting"
        )

    background_tasks.add_task(run_restart_nextjs_task, workspace_id)

    return {
        "message": "Next.js container restart initiated",
        "workspaceId": workspace_id,
        "status": "restarting"
    }


__all__ = ["router"]
