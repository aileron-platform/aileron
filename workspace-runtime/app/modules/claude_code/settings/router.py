"""Settings API Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses
from ..common import DocumentScope
from .dependencies import get_settings_service
from .models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
)
from .service import SettingsService

router = APIRouter(prefix="/settings", tags=["Claude Code - Settings"])


@router.get(
    "",
    response_model=ClaudeCodeSettings,
    summary="Get Claude Code settings",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_settings(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        default=None,
        description="If specified, return only that scope's permission set",
    ),
    service: SettingsService = Depends(get_settings_service),
) -> ClaudeCodeSettings:
    return service.get_settings(workspace_id, scope)


@router.put(
    "",
    response_model=ClaudeCodeSettings,
    summary="Update Claude Code settings",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_settings(
    payload: ClaudeCodeSettingsUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Query(
        default=DocumentScope.PROJECT,
        description="Settings scope to write to, defaults to project",
    ),
    service: SettingsService = Depends(get_settings_service),
) -> ClaudeCodeSettings:
    return service.update_settings(workspace_id, payload, scope)
