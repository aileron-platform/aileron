"""Codex settings route group."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses

from .models import (
    CodexAgentsMdDocument,
    CodexAgentsMdUpdateRequest,
    CodexAgentsMdUpdateResponse,
    CodexConfigDocument,
    CodexConfigSectionResponse,
    CodexConfigSectionUpdateRequest,
    CodexConfigSectionUpdateResponse,
    CodexConfigUpdateRequest,
    CodexConfigUpdateResponse,
    CodexEditableLayer,
    CodexFeatureEnableResponse,
    CodexFileListResponse,
    CodexFileUpdateRequest,
    CodexHooksDocumentResponse,
    CodexHooksScopesResponse,
    CodexManagedRequirementsResponse,
    CodexOverviewResponse,
    CodexPluginToggleRequest,
    CodexPluginToggleResponse,
    CodexPluginsResponse,
    CodexReadableLayer,
    CodexSettingsCapabilitiesResponse,
    CodexSettingsCapability,
    CodexRulesListResponse,
    CodexRulesValidationRequest,
    CodexRulesValidationResponse,
    CodexSubagentDeleteResponse,
    CodexSubagentItem,
    CodexSubagentSaveRequest,
    CodexSubagentsResponse,
    CodexTextFileResponse,
    CodexTextFileUpdateRequest,
    CodexTrustUpdateRequest,
    CodexTrustUpdateResponse,
)
from .service import CodexSettingsService, get_codex_settings_service

router = APIRouter(prefix="/codex", tags=["Codex Settings"])

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


@router.get("", response_model=CodexSettingsCapabilitiesResponse)
async def get_codex_settings_capabilities(workspace_id: str) -> CodexSettingsCapabilitiesResponse:
    """Return the Codex settings API surface available for this workspace."""

    return CodexSettingsCapabilitiesResponse(
        workspaceId=workspace_id,
        editableLayers=["user", "project"],
        capabilities=[
            CodexSettingsCapability(id=capability_id, path=path, implemented=implemented)
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
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexOverviewResponse:
    """Return Codex overview state."""

    return service.get_overview(workspace_id)


@router.patch(
    "/overview/trust",
    response_model=CodexTrustUpdateResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_trust(
    payload: CodexTrustUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexTrustUpdateResponse:
    """Update the active workspace trust state through the verified config write."""

    return service.update_trust(workspace_id, payload.trusted)


@router.get(
    "/agents-md",
    response_model=CodexAgentsMdDocument,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_agents_md(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexAgentsMdDocument:
    """Return user or project Codex AGENTS.md with source caveats."""

    return service.get_agents_md(workspace_id, scope)


@router.put(
    "/agents-md",
    response_model=CodexAgentsMdUpdateResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_agents_md(
    payload: CodexAgentsMdUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexAgentsMdUpdateResponse:
    """Update user or project Codex AGENTS.md."""

    return service.update_agents_md(workspace_id, payload)


@router.get(
    "/managed-requirements",
    response_model=CodexManagedRequirementsResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_managed_requirements(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexManagedRequirementsResponse:
    """Return read-only managed requirements sources."""

    return service.get_managed_requirements(workspace_id)


@router.get(
    "/config",
    response_model=CodexConfigDocument,
    responses=build_responses(400, 401, 422, 500),
)
async def get_codex_config(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexConfigDocument:
    """Return raw Codex config.toml."""

    return service.get_config_document(workspace_id, layer)


@router.put(
    "/config",
    response_model=CodexConfigUpdateResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def update_codex_config(
    payload: CodexConfigUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexConfigUpdateResponse:
    """Update raw Codex config.toml after TOML validation."""

    return service.update_config_document(workspace_id, layer, payload.content)


@router.get(
    "/config/{section}",
    response_model=CodexConfigSectionResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_codex_config_section(
    section: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexConfigSectionResponse:
    """Return a structured Codex config section."""

    return service.get_config_section(workspace_id, layer, section)


@router.put(
    "/config/{section}",
    response_model=CodexConfigSectionUpdateResponse,
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_codex_config_section(
    section: str,
    payload: CodexConfigSectionUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexConfigSectionUpdateResponse:
    """Update a structured Codex config section while preserving unknown keys."""

    return service.update_config_section(workspace_id, layer, section, payload.data)


@router.get("/rules", response_model=CodexRulesListResponse, responses=build_responses(400, 401, 422, 500))
async def list_codex_rules(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexRulesListResponse:
    """List Codex .rules files."""

    return service.list_rules(workspace_id, layer)


@router.get("/rules/file", response_model=CodexTextFileResponse, responses=build_responses(400, 401, 422, 500))
async def get_codex_rules_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexTextFileResponse:
    """Return a Codex .rules file."""

    return service.get_rules_file(workspace_id, layer, path)


@router.put("/rules/file", response_model=CodexTextFileResponse, responses=build_responses(400, 401, 422, 500))
async def update_codex_rules_file(
    payload: CodexTextFileUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexTextFileResponse:
    """Create or update a Codex .rules file."""

    return service.update_rules_file(workspace_id, layer, payload.path or path, payload.content)


@router.delete("/rules/file", response_model=dict[str, str], responses=build_responses(400, 401, 422, 500))
async def delete_codex_rules_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative .rules path"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> dict[str, str]:
    """Delete a Codex .rules file."""

    return service.delete_rules_file(workspace_id, layer, path)


@router.post("/rules/validate", response_model=CodexRulesValidationResponse, responses=build_responses(400, 401, 422, 500))
async def validate_codex_rules_file(
    payload: CodexRulesValidationRequest,
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexRulesValidationResponse:
    """Run codex execpolicy check for a .rules file."""

    return service.validate_rules_file(payload.layer, payload.path, payload.command)


@router.get("/hooks", response_model=CodexHooksDocumentResponse, responses=build_responses(400, 401, 422, 500))
async def get_codex_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexHooksDocumentResponse:
    """Return Codex hooks.json and inline hook metadata."""

    return service.get_hooks_document(workspace_id, layer)


@router.get("/hooks-scopes", response_model=CodexHooksScopesResponse, responses=build_responses(400, 401, 422, 500))
async def list_codex_hooks_scopes(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexHooksScopesResponse:
    """Return all editable Codex hooks documents with shared read-only sources."""

    return service.list_hooks_documents(workspace_id)


@router.put("/hooks", response_model=CodexHooksDocumentResponse, responses=build_responses(400, 401, 422, 500))
async def update_codex_hooks(
    payload: CodexTextFileUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexHooksDocumentResponse:
    """Update Codex hooks.json after JSON validation."""

    return service.update_hooks_document(workspace_id, layer, payload.content)


@router.post("/hooks/enable", response_model=CodexFeatureEnableResponse, responses=build_responses(400, 401, 422, 500))
async def enable_codex_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexFeatureEnableResponse:
    """Enable features.codex_hooks in the selected config layer."""

    return service.enable_codex_hooks(workspace_id, layer)


@router.get("/plugins", response_model=CodexPluginsResponse, responses=build_responses(400, 401, 422, 500))
async def list_codex_plugins(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexPluginsResponse:
    """Return local Codex plugin marketplace/cache/config state."""

    return service.list_plugins(workspace_id)


@router.patch("/plugins/{plugin_id:path}", response_model=CodexPluginToggleResponse, responses=build_responses(400, 401, 422, 500))
async def set_codex_plugin_enabled(
    payload: CodexPluginToggleRequest,
    plugin_id: str = Path(..., description="Plugin ID"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexPluginToggleResponse:
    """Enable or disable a Codex plugin config entry."""

    return service.set_plugin_enabled(workspace_id, payload.layer, plugin_id, payload.enabled)


@router.get("/subagents", response_model=CodexSubagentsResponse, responses=build_responses(400, 401, 422, 500))
async def list_codex_subagents(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexSubagentsResponse:
    """Return Codex subagent sources and global registry settings."""

    return service.list_subagents(workspace_id)


@router.get("/subagents/detail", response_model=CodexSubagentItem, responses=build_responses(400, 401, 404, 422, 500))
async def get_codex_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    source: str = Query(..., description="Subagent source"),
    path: str = Query(..., description="Relative .toml path"),
    pluginId: str | None = Query(default=None, description="Plugin ID for plugin subagents"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexSubagentItem:
    """Return a selected Codex subagent document."""

    return service.get_subagent(workspace_id, source, path, plugin_id=pluginId)


@router.put("/subagents", response_model=CodexSubagentItem, responses=build_responses(400, 401, 409, 422, 500))
async def save_codex_subagent(
    payload: CodexSubagentSaveRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexSubagentItem:
    """Create or update a user/project Codex subagent TOML file."""

    return service.save_subagent(workspace_id, payload)


@router.post("/subagents", response_model=CodexSubagentItem, responses=build_responses(400, 401, 409, 422, 500))
async def create_codex_subagent(
    payload: CodexSubagentSaveRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexSubagentItem:
    """Create or update a user/project Codex subagent TOML file."""

    return service.save_subagent(workspace_id, payload)


@router.delete(
    "/subagents",
    response_model=CodexSubagentDeleteResponse,
    responses=build_responses(400, 401, 422, 500),
)
async def delete_codex_subagent(
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative .toml path"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexSubagentDeleteResponse:
    """Delete an editable Codex subagent file."""

    return service.delete_subagent(workspace_id, layer, path)


@router.get("/{resource}/files", response_model=CodexFileListResponse, responses=build_responses(400, 401, 404, 422, 500))
async def list_codex_files(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexReadableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexFileListResponse:
    """List Codex skills, subagents, or prompts files."""

    return service.list_files(workspace_id, layer, resource)


@router.get("/{resource}/file", response_model=CodexTextFileResponse, responses=build_responses(400, 401, 404, 422, 500))
async def get_codex_file(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexReadableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative file path"),
    pluginId: str | None = Query(default=None, description="Plugin ID for plugin layer files"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexTextFileResponse:
    """Return a Codex skills, subagents, or prompts file."""

    return service.get_file(workspace_id, layer, resource, path, plugin_id=pluginId)


@router.put("/{resource}/file", response_model=CodexTextFileResponse, responses=build_responses(400, 401, 404, 422, 500))
async def update_codex_file(
    resource: str,
    payload: CodexFileUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> CodexTextFileResponse:
    """Create or update a Codex skills, subagents, or prompts file."""

    return service.update_file(workspace_id, layer, resource, payload.path, payload.content)


@router.delete("/{resource}/file", response_model=dict[str, str], responses=build_responses(400, 401, 404, 422, 500))
async def delete_codex_file(
    resource: str,
    workspace_id: str = Path(..., description="Workspace ID"),
    layer: CodexEditableLayer = Query(..., description="Settings layer"),
    path: str = Query(..., description="Relative file path"),
    service: CodexSettingsService = Depends(get_codex_settings_service),
) -> dict[str, str]:
    """Delete a Codex skills, subagents, or prompts file."""

    return service.delete_file(workspace_id, layer, resource, path)
