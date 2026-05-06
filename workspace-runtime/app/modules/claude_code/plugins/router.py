"""Claude Code plugin workflow routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.core.openapi import build_responses

from .models import (
    ClaudePluginDetailResponse,
    ClaudePluginsResponse,
    ClaudePluginToggleRequest,
    ClaudePluginToggleResponse,
)
from .service import ClaudePluginsService, get_claude_plugins_service

router = APIRouter(prefix="/plugins", tags=["Claude Code - Plugins"])


@router.get("", response_model=ClaudePluginsResponse, responses=build_responses(400, 401, 422, 500, 502, 503, 504))
async def list_claude_plugins(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginsResponse:
    """Return installed Claude Code plugins across all scopes."""

    return service.list_plugins(workspace_id)


@router.get("/{plugin_id:path}", response_model=ClaudePluginDetailResponse, responses=build_responses(400, 401, 404, 422, 500, 502, 503, 504))
async def get_claude_plugin(
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginDetailResponse:
    """Return Claude Code plugin detail."""

    return service.get_plugin_detail(workspace_id, plugin_id)


@router.patch("/{plugin_id:path}", response_model=ClaudePluginToggleResponse, responses=build_responses(400, 401, 422, 500, 502, 503, 504))
async def set_claude_plugin_enabled(
    payload: ClaudePluginToggleRequest,
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginToggleResponse:
    """Enable or disable a Claude Code plugin in one scope."""

    return service.set_plugin_enabled(workspace_id, plugin_id, payload.scope, payload.enabled)
