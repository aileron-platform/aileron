"""Settings API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses
from ..common import DocumentScope
from .dependencies import get_settings_service
from .models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    MarketplaceListResponse,
)
from .service import SettingsService

router = APIRouter(prefix="/settings", tags=["Claude Code - 設定"])


@router.get(
    "",
    response_model=ClaudeCodeSettings,
    summary="取得 Claude Code 設定",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_settings(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        default=None,
        description="指定後僅回傳該範圍的權限集合",
    ),
    service: SettingsService = Depends(get_settings_service),
) -> ClaudeCodeSettings:
    return service.get_settings(workspace_id, scope)


@router.get(
    "/marketplaces",
    response_model=MarketplaceListResponse,
    summary="取得所有 Marketplaces",
    responses=build_responses(401, 404, 500),
)
async def get_marketplaces(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: SettingsService = Depends(get_settings_service),
) -> MarketplaceListResponse:
    return service.get_marketplaces(workspace_id)


@router.put(
    "",
    response_model=ClaudeCodeSettings,
    summary="更新 Claude Code 設定",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_settings(
    payload: ClaudeCodeSettingsUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Query(
        default=DocumentScope.PROJECT,
        description="要寫入的設定範圍，預設為 project",
    ),
    service: SettingsService = Depends(get_settings_service),
) -> ClaudeCodeSettings:
    return service.update_settings(workspace_id, payload, scope)
