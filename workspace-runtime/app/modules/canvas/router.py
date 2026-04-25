"""Canvas 模組路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from app.core.openapi import build_responses

from .dependencies import get_canvas_service
from .models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasRoutesResponse,
)
from .service import CanvasService

router = APIRouter(prefix="/workspaces/{workspace_id}/canvas", tags=["Canvas"])


@router.get(
    "/detect",
    response_model=CanvasDetectResponse,
    summary="偵測 Canvas 類型",
    responses=build_responses(401, 404, 500),
)
async def detect_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasDetectResponse:
    return service.detect(workspace_id)


@router.get(
    "/routes",
    response_model=CanvasRoutesResponse,
    summary="取得 Canvas 路由列表",
    responses=build_responses(401, 404, 500),
)
async def get_canvas_routes(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasRoutesResponse:
    return service.routes(workspace_id)


@router.get(
    "/health",
    response_model=CanvasHealthResponse,
    summary="檢查 Canvas 健康狀態",
    responses=build_responses(401, 404, 500),
)
async def check_canvas_health(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasHealthResponse:
    return service.health(workspace_id)


@router.get(
    "/logs",
    response_model=CanvasLogsResponse,
    summary="取得 Canvas 日誌",
    responses=build_responses(401, 404, 500),
)
async def get_canvas_logs(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasLogsResponse:
    return service.logs(workspace_id)


@router.post(
    "/sync",
    response_model=CanvasActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="同步 workspace 到 Canvas snapshot",
    responses=build_responses(401, 404, 422, 500),
)
async def sync_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasActionResponse:
    return service.sync(workspace_id)


@router.post(
    "/reset",
    response_model=CanvasActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="重置 Canvas snapshot",
    responses=build_responses(401, 404, 422, 500),
)
async def reset_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasActionResponse:
    return service.reset(workspace_id)
