"""Codex settings route group."""

from __future__ import annotations

import mimetypes
from pathlib import Path as FilePath
from typing import Callable, NoReturn, TypeVar
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.core.openapi import APIErrorDetail, build_responses
from app.core.resource_envelope import raise_resource_error

from .models import (
    CodexAppResponse,
    CodexAppsResponse,
    CodexCollectionScope,
    CodexConfigDocument,
    CodexConfigSectionResponse,
    CodexConfigSectionUpdateRequest,
    CodexConfigSectionUpdateResponse,
    CodexConfigUpdateRequest,
    CodexEditableLayer,
    CodexEditableScope,
    CodexFeatureEnableResponse,
    CodexFileListResponse,
    CodexFileUpdateRequest,
    CodexHookEntryDeleteRequest,
    CodexHookEntryUpsertRequest,
    CodexHooksDocumentResponse,
    CodexHooksDocumentUpdateRequest,
    CodexHooksScopesResponse,
    CodexManagedRequirementsResponse,
    CodexOverviewResponse,
    CodexPluginDetailResponse,
    CodexPluginHookTrustUpdateRequest,
    CodexPluginHookTrustUpdateResponse,
    CodexPluginMcpPolicyUpdateRequest,
    CodexPluginMcpPolicyUpdateResponse,
    CodexPluginsResponse,
    CodexPluginToggleRequest,
    CodexPluginToggleResponse,
    CodexReadableScope,
    CodexRulesListResponse,
    CodexRulesValidationRequest,
    CodexRulesValidationResponse,
    CodexScopedTextFileResponse,
    CodexSettingsCapabilitiesResponse,
    CodexSettingsCapability,
    CodexSubagentDeleteResponse,
    CodexSubagentItem,
    CodexSubagentSaveRequest,
    CodexSubagentsResponse,
    CodexTextFileResponse,
    CodexTextFileUpdateRequest,
    CodexTrustUpdateRequest,
    CodexTrustUpdateResponse,
)
from .settings import (
    CodexAgentSettings,
    CodexSettingsIntent,
    get_codex_agent_settings,
)

router = APIRouter(prefix="/codex", tags=["Codex Settings"])
T = TypeVar("T")
_RAW_BINARY_MEDIA_TYPES = (
    "application/octet-stream",
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/*",
    "text/*",
    "audio/*",
    "video/*",
    "*/*",
)

_CAPABILITY_PATHS = [
    ("overview", "overview", True),
    ("agents-md", "agents-md", True),
    ("config", "config", True),
    ("features", "features", True),
    ("profiles", "profiles", True),
    ("permissions-profiles", "permissions-profiles", True),
    ("model-providers", "model-providers", True),
    ("apps", "apps", True),
    ("memories", "memories", True),
    ("rules", "rules", True),
    ("hooks", "hooks", True),
    ("mcp-servers", "mcp-servers", True),
    ("plugins", "plugins", True),
    ("skills", "skills", True),
    ("subagents", "subagents", True),
    ("prompts", "prompts", True),
    ("managed-requirements", "managed-requirements", True),
]


def _raise_codex_http_error(error: HTTPException) -> NoReturn:
    detail: object = error.detail
    if isinstance(detail, dict):
        if "errorCode" in detail:
            raise error
        code = str(detail.get("error") or detail.get("code") or "CODEX_RESOURCE_ERROR")
        message = str(detail.get("message") or code)
        validation = detail.get("validationResults")
        raise_resource_error(
            code,
            message,
            error.status_code,
            validation if isinstance(validation, list) else None,
        )
    raise_resource_error("CODEX_RESOURCE_ERROR", str(detail), error.status_code)


def _raise_codex_internal_error(error: Exception) -> NoReturn:
    raise_resource_error(
        "INTERNAL_ERROR", str(error), status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _codex_resource_call(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException as e:
        raise _raise_codex_http_error(e) from e
    except Exception as e:
        raise _raise_codex_internal_error(e) from e


def _raw_file_response(path: str, content: bytes) -> Response:
    mime_type, _ = mimetypes.guess_type(path)
    filename = FilePath(path).name
    encoded_filename = quote(filename, safe="")
    disposition = (
        f"inline; filename*=utf-8''{encoded_filename}"
        if encoded_filename != filename
        else f'inline; filename="{filename}"'
    )
    return Response(
        content=content,
        media_type=mime_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


def _raw_binary_openapi_content() -> dict[str, dict[str, dict[str, str]]]:
    return {
        media_type: {"schema": {"type": "string", "format": "binary"}}
        for media_type in _RAW_BINARY_MEDIA_TYPES
    }


@router.get("", response_model=CodexSettingsCapabilitiesResponse)
async def get_codex_settings_capabilities(
    workspace_id: str,
) -> CodexSettingsCapabilitiesResponse:
    """Return the Codex settings API surface available for this workspace."""

    return CodexSettingsCapabilitiesResponse(
        workspaceId=workspace_id,
        editableLayers=["user", "project"],
        capabilities=[
            CodexSettingsCapability(
                id=capability_id, path=path, implemented=implemented
            )
            for capability_id, path, implemented in _CAPABILITY_PATHS
        ],
    )


@router.get(
    "/overview",
    response_model=CodexOverviewResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_overview(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexOverviewResponse:
    """Return Codex overview state."""

    return _codex_resource_call(
        lambda: service.execute(CodexSettingsIntent.GET_OVERVIEW, workspace_id)
    )


@router.patch(
    "/overview/trust",
    response_model=CodexTrustUpdateResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_trust(
    payload: CodexTrustUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexTrustUpdateResponse:
    """Update the active workspace trust state through the verified config write."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_TRUST, workspace_id, payload.trusted
        )
    )


@router.get(
    "/managed-requirements",
    response_model=CodexManagedRequirementsResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_managed_requirements(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexManagedRequirementsResponse:
    """Return read-only managed requirements sources."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_MANAGED_REQUIREMENTS, workspace_id
        )
    )


@router.get(
    "/config",
    response_model=CodexConfigDocument,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_config(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexConfigDocument:
    """Return raw Codex config.toml."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_CONFIG_DOCUMENT, workspace_id, scope
        )
    )


@router.put(
    "/config",
    response_model=CodexConfigDocument,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_config(
    payload: CodexConfigUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexConfigDocument:
    """Update raw Codex config.toml after TOML validation."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_CONFIG_DOCUMENT,
            workspace_id,
            scope,
            payload.content,
            payload.revision,
        )
    )


@router.get(
    "/config/{section}",
    response_model=CodexConfigSectionResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_codex_config_section(
    section: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexConfigSectionResponse:
    """Return a structured Codex config section."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_CONFIG_SECTION, workspace_id, scope, section
        )
    )


@router.put(
    "/config/{section}",
    response_model=CodexConfigSectionUpdateResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_codex_config_section(
    section: str,
    payload: CodexConfigSectionUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexConfigSectionUpdateResponse:
    """Update a structured Codex config section while preserving unknown keys."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_CONFIG_SECTION,
            workspace_id,
            scope,
            section,
            payload.data,
            payload.revision,
        )
    )


@router.get(
    "/rules",
    response_model=CodexRulesListResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def list_codex_rules(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexRulesListResponse:
    """List Codex .rules files."""

    return _codex_resource_call(
        lambda: service.execute(CodexSettingsIntent.LIST_RULES, workspace_id, scope)
    )


@router.get(
    "/rules/file",
    response_model=CodexScopedTextFileResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_rules_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexScopedTextFileResponse:
    """Return a Codex .rules file."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_RULES_FILE, workspace_id, scope, path
        )
    )


@router.put(
    "/rules/file",
    response_model=CodexScopedTextFileResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_rules_file(
    payload: CodexTextFileUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexScopedTextFileResponse:
    """Create or update a Codex .rules file."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_RULES_FILE,
            workspace_id,
            scope,
            payload.path or path,
            payload.content,
            payload.revision,
        )
    )


@router.delete(
    "/rules/file",
    response_model=dict[str, str],
    responses=build_responses(400, 401, 422, 500),
)
async def delete_codex_rules_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> dict[str, str]:
    """Delete a Codex .rules file."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.DELETE_RULES_FILE, workspace_id, scope, path
        )
    )


@router.post(
    "/rules/validate",
    response_model=CodexRulesValidationResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def validate_codex_rules_file(
    payload: CodexRulesValidationRequest,
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexRulesValidationResponse:
    """Run codex execpolicy check for a .rules file."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.VALIDATE_RULES_FILE,
            payload.scope,
            payload.path,
            payload.command,
        )
    )


@router.get(
    "/hooks/{scope}",
    response_model=CodexHooksDocumentResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_hooks(
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexHooksDocumentResponse:
    """Return Codex hooks.json and inline hook metadata."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_HOOKS_DOCUMENT, workspace_id, scope
        )
    )


@router.get(
    "/hooks-scopes",
    response_model=CodexHooksScopesResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def list_codex_hooks_scopes(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexHooksScopesResponse:
    """Return all editable Codex hooks documents with shared read-only sources."""

    return _codex_resource_call(
        lambda: service.execute(CodexSettingsIntent.LIST_HOOKS_DOCUMENTS, workspace_id)
    )


@router.put(
    "/hooks/{scope}",
    response_model=CodexHooksDocumentResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_hooks(
    payload: CodexHooksDocumentUpdateRequest,
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexHooksDocumentResponse:
    """Update Codex hooks.json after JSON validation."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_HOOKS_DOCUMENT,
            workspace_id,
            scope,
            payload.content,
            payload.revision,
        )
    )


@router.put(
    "/hooks/{scope}/entry",
    response_model=CodexHooksDocumentResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def upsert_codex_hook_entry(
    payload: CodexHookEntryUpsertRequest,
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexHooksDocumentResponse:
    """Create or update one editable Codex hooks.json entry."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPSERT_HOOK_ENTRY,
            workspace_id,
            scope,
            payload.entry,
            payload.revision,
            payload.previous,
        )
    )


@router.delete(
    "/hooks/{scope}/entry",
    response_model=CodexHooksDocumentResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def delete_codex_hook_entry(
    payload: CodexHookEntryDeleteRequest,
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexHooksDocumentResponse:
    """Delete one editable Codex hooks.json entry."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.DELETE_HOOK_ENTRY,
            workspace_id,
            scope,
            payload.entry,
            payload.revision,
        )
    )


@router.post(
    "/hooks/{scope}/enable",
    response_model=CodexFeatureEnableResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def enable_codex_hooks(
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexFeatureEnableResponse:
    """Enable canonical [features].hooks in the selected config scope."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.ENABLE_CODEX_HOOKS, workspace_id, scope
        )
    )


@router.post(
    "/hooks/{scope}/disable",
    response_model=CodexFeatureEnableResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def disable_codex_hooks(
    scope: CodexEditableLayer = Path(..., description="Settings scope"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexFeatureEnableResponse:
    """Disable canonical [features].hooks in the selected config scope."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.DISABLE_CODEX_HOOKS, workspace_id, scope
        )
    )


@router.get(
    "/apps",
    response_model=CodexAppsResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def list_codex_apps(
    workspace_id: str = Path(..., description="Workspace ID"),
    plugin_id: str | None = Query(
        default=None,
        alias="pluginId",
        description="Optionally filter by provider plugin ID",
    ),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexAppsResponse:
    """Return read-only apps and connectors from installed Codex plugins."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.LIST_APPS, workspace_id, plugin_id=plugin_id
        )
    )


@router.get(
    "/apps/{app_name:path}",
    response_model=CodexAppResponse,
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def get_codex_app(
    app_name: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    plugin_id: str | None = Query(
        default=None,
        alias="pluginId",
        description="Provider plugin ID used to disambiguate the app",
    ),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexAppResponse:
    """Return one installed Codex plugin app or connector definition."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_APP,
            workspace_id,
            app_name,
            plugin_id=plugin_id,
        )
    )


@router.get(
    "/plugins",
    response_model=CodexPluginsResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def list_codex_plugins(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexPluginsResponse:
    """Return local Codex plugin marketplace/cache/config state."""

    return _codex_resource_call(
        lambda: service.execute(CodexSettingsIntent.LIST_PLUGINS, workspace_id)
    )


@router.patch(
    "/plugins/{plugin_id:path}/mcp-servers/{server_id:path}/policy",
    response_model=CodexPluginMcpPolicyUpdateResponse,
    responses=build_responses(400, 401, 404, 409, 422, 423, 500),
)
async def update_codex_plugin_mcp_policy(
    payload: CodexPluginMcpPolicyUpdateRequest,
    plugin_id: str = Path(..., description="Provider plugin ID"),
    server_id: str = Path(..., description="Provider MCP server ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexPluginMcpPolicyUpdateResponse:
    """Replace a provider-native policy without editing the plugin definition."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_PLUGIN_MCP_POLICY,
            workspace_id,
            plugin_id,
            server_id,
            payload.policy,
            payload.revision,
        )
    )


@router.patch(
    "/plugins/{plugin_id:path}/hook-trust",
    response_model=CodexPluginHookTrustUpdateResponse,
    responses=build_responses(400, 401, 404, 409, 422, 423, 500),
)
async def update_codex_plugin_hook_trust(
    payload: CodexPluginHookTrustUpdateRequest,
    plugin_id: str = Path(..., description="Provider plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexPluginHookTrustUpdateResponse:
    """Approve or revoke provider-native command hook trust."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.UPDATE_PLUGIN_HOOK_TRUST,
            workspace_id,
            plugin_id,
            payload.trusted,
            payload.revision,
        )
    )


@router.get(
    "/plugins/{plugin_id:path}",
    response_model=CodexPluginDetailResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_codex_plugin(
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexPluginDetailResponse:
    """Return detailed Codex plugin metadata and bundled resources."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.GET_PLUGIN_DETAIL, workspace_id, plugin_id
        )
    )


@router.patch(
    "/plugins/{plugin_id:path}",
    response_model=CodexPluginToggleResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def set_codex_plugin_enabled(
    payload: CodexPluginToggleRequest,
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexPluginToggleResponse:
    """Enable or disable a Codex plugin config entry."""

    return _codex_resource_call(
        lambda: service.execute(
            CodexSettingsIntent.SET_PLUGIN_ENABLED,
            workspace_id,
            plugin_id,
            payload.scope,
            payload.enabled,
            payload.revision,
        )
    )


@router.get(
    "/subagents",
    response_model=CodexSubagentsResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def list_codex_subagents(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexSubagentsResponse:
    """Return Codex subagent sources and global registry settings."""

    return service.execute(CodexSettingsIntent.LIST_SUBAGENTS, workspace_id)


@router.get(
    "/subagents/detail",
    response_model=CodexSubagentItem,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_codex_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    source: str = Query(..., description="Subagent source"),
    path: str = Query(..., description="Relative .toml path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexSubagentItem:
    """Return a selected Codex subagent document."""

    return service.execute(CodexSettingsIntent.GET_SUBAGENT, workspace_id, source, path)


@router.put(
    "/subagents",
    response_model=CodexSubagentItem,
    responses=build_responses(400, 401, 409, 422, 500),
)
async def save_codex_subagent(
    payload: CodexSubagentSaveRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexSubagentItem:
    """Create or update a user/project Codex subagent TOML file."""

    return service.execute(CodexSettingsIntent.SAVE_SUBAGENT, workspace_id, payload)


@router.post(
    "/subagents",
    response_model=CodexSubagentItem,
    responses=build_responses(400, 401, 409, 422, 500),
)
async def create_codex_subagent(
    payload: CodexSubagentSaveRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexSubagentItem:
    """Create or update a user/project Codex subagent TOML file."""

    return service.execute(CodexSettingsIntent.SAVE_SUBAGENT, workspace_id, payload)


@router.delete(
    "/subagents",
    response_model=CodexSubagentDeleteResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def delete_codex_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableScope = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative .toml path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexSubagentDeleteResponse:
    """Delete an editable Codex subagent file."""

    return service.execute(
        CodexSettingsIntent.DELETE_SUBAGENT, workspace_id, scope, path
    )


@router.get(
    "/{resource}/files",
    response_model=CodexFileListResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_codex_files(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexCollectionScope = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexFileListResponse:
    """List Codex skills or prompts files."""

    if resource == "skills":
        return _codex_resource_call(
            lambda: service.execute(
                CodexSettingsIntent.LIST_FILES, workspace_id, scope, resource
            )
        )
    return service.execute(
        CodexSettingsIntent.LIST_FILES, workspace_id, scope, resource
    )


@router.get(
    "/{resource}/file",
    response_model=CodexTextFileResponse,
    response_model_exclude_none=True,
    responses={
        **build_responses(400, 401, 404, 422, 500),
        200: {
            "description": "JSON file content or raw binary preview content.",
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/CodexTextFileResponse",
                    }
                },
                **_raw_binary_openapi_content(),
            },
        },
        413: {
            "model": APIErrorDetail,
            "description": "Raw preview exceeds the configured size limit.",
        },
    },
)
async def get_codex_file(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexReadableScope = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative file path"),
    pluginId: str | None = Query(
        default=None, description="Plugin ID for plugin scope files"
    ),
    raw: bool = Query(
        default=False, description="Whether to return raw binary content"
    ),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexTextFileResponse | Response:
    """Return a Codex skills or prompts file."""

    if raw:

        def read_binary() -> bytes:
            return service.execute(
                CodexSettingsIntent.GET_FILE_BINARY,
                workspace_id,
                scope,
                resource,
                path,
                plugin_id=pluginId,
            )

        content = await run_in_threadpool(_codex_resource_call, read_binary)
        return _raw_file_response(path, content)

    if resource == "skills":
        return _codex_resource_call(
            lambda: service.execute(
                CodexSettingsIntent.GET_FILE,
                workspace_id,
                scope,
                resource,
                path,
                plugin_id=pluginId,
            )
        )
    return service.execute(
        CodexSettingsIntent.GET_FILE,
        workspace_id,
        scope,
        resource,
        path,
        plugin_id=pluginId,
    )


@router.put(
    "/{resource}/file",
    response_model=CodexTextFileResponse,
    response_model_exclude_none=True,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_codex_file(
    resource: str,
    payload: CodexFileUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableScope = Query(..., description="Settings scope"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> CodexTextFileResponse:
    """Create or update a Codex skills or prompts file."""

    if resource == "skills":
        if payload.revision is None:
            raise HTTPException(
                422,
                detail={
                    "errorCode": "REVISION_REQUIRED",
                    "message": "revision is required",
                },
            )
        return _codex_resource_call(
            lambda: service.execute(
                CodexSettingsIntent.UPDATE_FILE,
                workspace_id,
                scope,
                resource,
                payload.path,
                payload.content,
                payload.revision,
            )
        )
    return service.execute(
        CodexSettingsIntent.UPDATE_FILE,
        workspace_id,
        scope,
        resource,
        payload.path,
        payload.content,
    )


@router.delete(
    "/{resource}/file",
    response_model=dict[str, str],
    responses=build_responses(400, 401, 404, 422, 500),
)
async def delete_codex_file(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableScope = Query(..., description="Settings scope"),
    path: str = Query(..., description="Relative file path"),
    service: CodexAgentSettings = Depends(get_codex_agent_settings),
) -> dict[str, str]:
    """Delete a Codex skills or prompts file."""

    if resource == "skills":
        return _codex_resource_call(
            lambda: service.execute(
                CodexSettingsIntent.DELETE_FILE, workspace_id, scope, resource, path
            )
        )
    return service.execute(
        CodexSettingsIntent.DELETE_FILE, workspace_id, scope, resource, path
    )
