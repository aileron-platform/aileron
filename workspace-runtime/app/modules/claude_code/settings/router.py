"""Settings API Routes"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses
from ..documents import DocumentScope
from .dependencies import get_settings_service
from .models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    RawSettingsResponse,
    RawSettingsUpdateRequest,
)
from .configuration import SettingsService

router = APIRouter(prefix="/settings", tags=["Claude Code - Settings"])
RawSettingsScope = Literal["local", "user", "project"]


def _raw_scope(value: RawSettingsScope) -> DocumentScope:
    return DocumentScope(value)


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


@router.get(
    "/raw",
    response_model=RawSettingsResponse,
    summary="Get raw Claude Code settings",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_raw_settings(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: RawSettingsScope = Query(..., description="Settings scope to read"),
    service: SettingsService = Depends(get_settings_service),
) -> RawSettingsResponse:
    scoped = _raw_scope(scope)
    return RawSettingsResponse(
        content=service.get_raw_settings(workspace_id, scoped),
        revision=service.get_settings_revision(workspace_id, scoped),
    )


@router.put(
    "/raw",
    response_model=RawSettingsResponse,
    summary="Update raw Claude Code settings",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_raw_settings(
    payload: RawSettingsUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: RawSettingsScope = Query(..., description="Settings scope to write"),
    service: SettingsService = Depends(get_settings_service),
) -> RawSettingsResponse:
    scoped = _raw_scope(scope)
    content = service.update_raw_settings(
        workspace_id, scoped, payload.content, payload.revision
    )
    return RawSettingsResponse(
        content=content,
        revision=service.get_settings_revision(workspace_id, scoped),
    )
