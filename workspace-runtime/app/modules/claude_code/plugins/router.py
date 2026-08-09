"""Claude Code plugin workflow routes."""

from __future__ import annotations

from typing import Callable, NoReturn, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error

from .models import (
    ClaudePluginDetailResponse,
    ClaudePluginsResponse,
    ClaudePluginToggleRequest,
    ClaudePluginToggleResponse,
)
from .catalog import ClaudePluginsService, get_claude_plugins_service

router = APIRouter(prefix="/plugins", tags=["Claude Code - Plugins"])
T = TypeVar("T")


def _raise_plugin_error(error: HTTPException) -> NoReturn:
    detail = vars(error).get("detail")
    if isinstance(detail, dict):
        if "errorCode" in detail:
            raise error
        code = str(detail.get("error") or detail.get("code") or "CLAUDE_PLUGIN_ERROR")
        message = str(detail.get("message") or code)
        validation = detail.get("validationResults")
        raise_resource_error(
            code,
            message,
            error.status_code,
            validation if isinstance(validation, list) else None,
        )
    raise_resource_error("CLAUDE_PLUGIN_ERROR", str(detail), error.status_code)


def _plugin_resource_call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException as exc:
        _raise_plugin_error(exc)
    except Exception as exc:
        raise_resource_error(
            "INTERNAL_ERROR", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get(
    "",
    response_model=ClaudePluginsResponse,
    responses=build_responses(400, 401, 422, 500, 502, 503, 504),
)
async def list_claude_plugins(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginsResponse:
    """Return installed Claude Code plugins across all scopes."""

    return _plugin_resource_call(lambda: service.list_plugins(workspace_id))


@router.get(
    "/{plugin_id:path}",
    response_model=ClaudePluginDetailResponse,
    responses=build_responses(400, 401, 404, 422, 500, 502, 503, 504),
)
async def get_claude_plugin(
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginDetailResponse:
    """Return Claude Code plugin detail."""

    return _plugin_resource_call(
        lambda: service.get_plugin_detail(workspace_id, plugin_id)
    )


@router.patch(
    "/{plugin_id:path}",
    response_model=ClaudePluginToggleResponse,
    responses=build_responses(400, 401, 422, 500, 502, 503, 504),
)
async def set_claude_plugin_enabled(
    payload: ClaudePluginToggleRequest,
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudePluginsService = Depends(get_claude_plugins_service),
) -> ClaudePluginToggleResponse:
    """Enable or disable a Claude Code plugin in one scope."""

    return _plugin_resource_call(
        lambda: service.set_plugin_enabled(
            workspace_id,
            plugin_id,
            payload.scope,
            payload.enabled,
            payload.revision,
        )
    )
