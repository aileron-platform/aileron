"""Gemini extension API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.core.openapi import build_responses

from .extension_resources import (
    GeminiExtensionResourceResolver,
    disable,
    enable,
    resolve_toggle_cwd,
    resolve_workspace_root,
)
from .models import (
    GeminiExtensionCommandError,
    GeminiExtensionDetailResponse,
    GeminiExtensionListResponse,
    GeminiExtensionSummary,
    GeminiExtensionToggleResponse,
    GeminiExtensionToggleScope,
)

router = APIRouter(prefix="/gemini/extensions", tags=["gemini - Extensions"])


def _resolver() -> GeminiExtensionResourceResolver:
    return GeminiExtensionResourceResolver()


def _summary(extension) -> GeminiExtensionSummary:
    install_info = extension.installInfo
    return GeminiExtensionSummary(
        name=extension.name,
        version=extension.version,
        description=extension.description,
        contextFileName=extension.contextFile.path.rsplit("/", 1)[-1] if extension.contextFile else None,
        installSource=install_info.source if install_info else None,
        installType=install_info.type if install_info else None,
        releaseTag=install_info.releaseTag if install_info else None,
        enabledHere=extension.enabledHere,
        overrides=extension.overrides,
        resourceCounts={
            "mcp": len(extension.mcpServers),
            "commands": len(extension.slashCommands),
            "skills": len(extension.skills),
            "hooks": len(extension.hooks),
            "policies": len(extension.policies),
        },
        excludeToolsCount=len(extension.excludeTools),
    )


def _command_error(error: GeminiExtensionCommandError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "GEMINI_EXTENSION_COMMAND_FAILED",
            "messageKey": "workspace.agentSettings.geminiExtensions.errors.commandFailed",
            "stderr": error.stderr,
            "command": error.command,
            "returnCode": error.returncode,
        },
    )


@router.get("", response_model=GeminiExtensionListResponse, responses=build_responses(400, 401, 422, 500))
async def list_extensions(
    workspace_id: str = Path(..., description="Workspace ID"),
) -> GeminiExtensionListResponse:
    workspace_root = resolve_workspace_root()
    extensions = [_summary(item) for item in _resolver().list_extensions(workspace_root)]
    return GeminiExtensionListResponse(workspaceId=workspace_id, extensions=extensions)


@router.get("/{name}", response_model=GeminiExtensionDetailResponse, responses=build_responses(400, 401, 404, 422, 500))
async def get_extension(
    name: str = Path(..., description="Extension name"),
    workspace_id: str = Path(..., description="Workspace ID"),
) -> GeminiExtensionDetailResponse:
    extension = _resolver().get_extension(name, resolve_workspace_root())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "GEMINI_EXTENSION_NOT_FOUND", "message": "Gemini extension not found"},
        )
    return GeminiExtensionDetailResponse(workspaceId=workspace_id, extension=extension)


@router.post("/{name}/enable", response_model=GeminiExtensionToggleResponse, responses=build_responses(400, 401, 404, 422, 500))
async def enable_extension(
    name: str = Path(..., description="Extension name"),
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: GeminiExtensionToggleScope = Query(..., description="Toggle scope"),
) -> GeminiExtensionToggleResponse:
    workspace_root = resolve_workspace_root()
    try:
        enable(name, scope, resolve_toggle_cwd(scope, workspace_root))
    except GeminiExtensionCommandError as error:
        raise _command_error(error) from error
    extension = _resolver().get_extension(name, workspace_root)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "GEMINI_EXTENSION_NOT_FOUND"})
    return GeminiExtensionToggleResponse(
        workspaceId=workspace_id,
        name=name,
        scope=scope,
        enabledHere=extension.enabledHere,
        overrides=extension.overrides,
    )


@router.post("/{name}/disable", response_model=GeminiExtensionToggleResponse, responses=build_responses(400, 401, 404, 422, 500))
async def disable_extension(
    name: str = Path(..., description="Extension name"),
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: GeminiExtensionToggleScope = Query(..., description="Toggle scope"),
) -> GeminiExtensionToggleResponse:
    workspace_root = resolve_workspace_root()
    try:
        disable(name, scope, resolve_toggle_cwd(scope, workspace_root))
    except GeminiExtensionCommandError as error:
        raise _command_error(error) from error
    extension = _resolver().get_extension(name, workspace_root)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "GEMINI_EXTENSION_NOT_FOUND"})
    return GeminiExtensionToggleResponse(
        workspaceId=workspace_id,
        name=name,
        scope=scope,
        enabledHere=extension.enabledHere,
        overrides=extension.overrides,
    )
