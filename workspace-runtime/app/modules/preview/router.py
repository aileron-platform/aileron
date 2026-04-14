"""預覽模組路由"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status

from app.core.openapi import build_responses
from .dependencies import get_preview_service
from .models import (
    NextJsRoutesResponse,
    PreviewSyncRequest,
    PreviewSyncResponse,
    PreviewSyncStatusResponse,
)
from .service import PreviewService

router = APIRouter(prefix="/workspaces/{workspace_id}/preview", tags=["預覽服務"])


@router.get(
    "/nextjs/routes",
    response_model=NextJsRoutesResponse,
    summary="取得 Next.js 路由列表",
    description="掃描 /web-preview 目錄下的 Next.js App Router 路由結構",
    responses=build_responses(401, 404, 500),
)
async def get_nextjs_routes(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: PreviewService = Depends(get_preview_service),
) -> NextJsRoutesResponse:
    """
    掃描並返回 Next.js App Router 的所有路由

    - 支援 page.tsx (頁面路由)
    - 支援 route.ts (API 路由)
    - 支援動態路由 [param]
    - 支援 catch-all 路由 [...param]
    - 支援 optional catch-all 路由 [[...param]]
    """
    return service.scan_nextjs_routes(workspace_id)


@router.post(
    "/sync",
    response_model=PreviewSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="同步 /workspace 到 /web-preview",
    description="將 /workspace 目錄的內容複製到 /web-preview 並重啟 Next.js 服務",
    responses=build_responses(401, 404, 422, 500),
)
async def sync_preview(
    background_tasks: BackgroundTasks,
    payload: PreviewSyncRequest = PreviewSyncRequest(),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: PreviewService = Depends(get_preview_service),
) -> PreviewSyncResponse:
    """
    同步預覽目錄

    執行步驟：
    1. 停止 Next.js 服務
    2. 複製 /workspace 到 /web-preview
    3. 設定權限
    4. 重啟 Next.js 服務

    返回操作 ID，可透過
    `GET /api/v1/workspaces/{workspace_id}/preview/sync/{operation_id}` 查詢進度
    """
    response = service.start_sync(workspace_id, payload)
    # 在背景執行同步操作
    background_tasks.add_task(service.execute_sync, response.operation_id)
    return response


@router.get(
    "/sync/{operation_id}",
    response_model=PreviewSyncStatusResponse,
    summary="取得同步操作狀態",
    responses=build_responses(401, 404, 500),
)
async def get_sync_status(
    operation_id: str = Path(..., description="操作 ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: PreviewService = Depends(get_preview_service),
) -> PreviewSyncStatusResponse:
    """查詢同步操作的進度和狀態"""
    return service.get_sync_status(operation_id)


@router.get(
    "/health",
    summary="檢查預覽服務健康狀態",
    description="檢查 Next.js 服務是否正常運行",
    responses=build_responses(401, 404, 500),
)
async def check_preview_health(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: PreviewService = Depends(get_preview_service),
) -> dict:
    """
    檢查預覽服務健康狀態

    返回:
    - status: "healthy" | "unhealthy" | "starting"
    - nextjs_running: Next.js 服務是否運行
    - port_available: 端口是否可用
    - message: 狀態訊息
    """
    return service.check_health(workspace_id)
