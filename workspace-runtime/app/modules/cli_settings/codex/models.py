"""Codex settings API models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.marketplace_operations.plugin_resources import (
    PluginResourceProvenance,
)

CodexEditableLayer = Literal["user", "project"]
CodexReadableLayer = Literal["user", "project", "plugin", "session"]
CodexEditableScope = CodexEditableLayer
CodexReadableScope = CodexReadableLayer
CodexCollectionScope = Literal["user", "project", "plugin", "all"]
CodexSubagentSource = Literal["built_in", "user", "project"]
CodexMcpApprovalMode = Literal["auto", "prompt", "writes", "approve"]
CodexPluginHookTrustState = Literal["trusted", "untrusted", "modified", "mixed"]


class CodexSettingsCapability(BaseModel):
    """Codex settings capability exposed by the API group."""

    id: str = Field(..., description="Capability identifier")
    path: str = Field(..., description="Relative API path")
    implemented: bool = Field(..., description="Whether the endpoint has full behavior")


class CodexSettingsCapabilitiesResponse(BaseModel):
    """Codex settings API group capabilities response."""

    workspaceId: str = Field(..., description="Workspace ID")
    editableLayers: list[str] = Field(
        default_factory=list, description="Editable layer identifiers"
    )
    capabilities: list[CodexSettingsCapability] = Field(default_factory=list)


class CodexOverviewTrustState(BaseModel):
    """Project trust state summary."""

    workspacePath: str
    trustLevel: str | None = None
    trusted: bool = False
    sourcePath: str
    mutable: bool = True


class CodexOverviewManagedRequirementsState(BaseModel):
    """Managed requirements summary."""

    present: bool = False
    count: int = 0
    sources: list[str] = Field(default_factory=list)


class CodexOverviewPluginState(BaseModel):
    """Plugin state summary."""

    configured: int = 0
    enabled: int = 0
    disabled: int = 0


class CodexOverviewMemoryState(BaseModel):
    """Memory config summary."""

    use: bool | None = None
    generate: bool | None = None


class CodexOverviewResponse(BaseModel):
    """Codex Overview response."""

    workspaceId: str
    setupReady: bool
    codexHome: str
    activeModel: str | None = None
    activeProfile: str | None = None
    trust: CodexOverviewTrustState
    plugins: CodexOverviewPluginState
    managedRequirements: CodexOverviewManagedRequirementsState
    memories: CodexOverviewMemoryState


class CodexTrustUpdateRequest(BaseModel):
    """Trust update request."""

    trusted: bool


class CodexTrustUpdateResponse(BaseModel):
    """Trust update response."""

    workspaceId: str
    trust: CodexOverviewTrustState


class CodexManagedRequirementsSource(BaseModel):
    """Managed requirements source document."""

    layer: CodexEditableLayer
    path: str
    content: str
    sizeBytes: int


class CodexManagedRequirementsResponse(BaseModel):
    """Read-only managed requirements response."""

    workspaceId: str
    sources: list[CodexManagedRequirementsSource] = Field(default_factory=list)


class CodexConfigDocument(BaseModel):
    """Raw Codex config document."""

    workspaceId: str
    scope: CodexEditableLayer
    path: str
    content: str
    exists: bool
    revision: str


class CodexConfigUpdateRequest(BaseModel):
    """Raw Codex config update request."""

    content: str
    revision: str | None = None


class CodexConfigSectionResponse(BaseModel):
    """Structured config section response."""

    workspaceId: str
    scope: CodexEditableLayer
    section: str
    path: str
    data: dict[str, Any] = Field(default_factory=dict)
    revision: str


class CodexConfigSectionUpdateRequest(BaseModel):
    """Structured config section update request."""

    data: dict[str, Any] = Field(default_factory=dict)
    revision: str | None = None


class CodexConfigSectionUpdateResponse(BaseModel):
    """Structured config section update response."""

    workspaceId: str
    scope: CodexEditableLayer
    section: str
    path: str
    data: dict[str, Any] = Field(default_factory=dict)
    revision: str


class CodexRulesFileSummary(BaseModel):
    """Rules file summary."""

    name: str
    path: str
    sizeBytes: int
    scope: CodexReadableScope | None = None
    readOnly: bool | None = None
    editable: bool | None = None


class CodexRulesListResponse(BaseModel):
    """Rules file list response."""

    workspaceId: str
    scope: CodexEditableLayer
    directory: str
    files: list[CodexRulesFileSummary] = Field(default_factory=list)


class CodexTextFileResponse(BaseModel):
    """Text file response for Codex settings."""

    workspaceId: str
    scope: CodexReadableScope
    path: str
    content: str
    exists: bool
    revision: str | None = None
    readOnly: bool | None = None
    editable: bool | None = None


class CodexScopedTextFileResponse(BaseModel):
    """Text file response for scoped Codex settings."""

    workspaceId: str
    scope: CodexEditableLayer
    path: str
    content: str
    exists: bool
    revision: str | None = None
    readOnly: bool | None = None
    editable: bool | None = None


class CodexTextFileUpdateRequest(BaseModel):
    """Text file update request."""

    path: str | None = None
    content: str
    revision: str | None = None


class CodexRulesValidationRequest(BaseModel):
    """Rules validation request."""

    scope: CodexEditableLayer
    path: str
    command: list[str]


class CodexRulesValidationResponse(BaseModel):
    """Rules validation response."""

    valid: bool
    exitCode: int
    stdout: str = ""
    stderr: str = ""


CodexHookScope = Literal["user", "project", "plugin", "session"]
CodexHookSource = Literal["hooks_json", "inline_config", "plugin", "session"]
CodexHookEventScope = Literal["start", "turn", "end"]
CodexHookMatcherTarget = Literal["source", "tool_name", "none"]


class CodexHookEventMetadata(BaseModel):
    """Official Codex hook event behavior used by the UI."""

    event: str
    scope: CodexHookEventScope
    matcherSupported: bool
    matcherTarget: CodexHookMatcherTarget
    matcherExamples: list[str] = Field(default_factory=list)


class CodexHookCommandAction(BaseModel):
    """Command handler configured for a Codex hook."""

    type: Literal["command"] = "command"
    command: str = ""
    timeout: int | None = None
    statusMessage: str | None = None
    async_: bool | None = Field(default=None, alias="async")
    commandWindows: str | None = None
    additionalContextLimit: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


CodexHookAction = CodexHookCommandAction | dict[str, Any]


class CodexHookEntry(BaseModel):
    """Normalized hook entry across editable and read-only sources."""

    id: str
    event: str
    index: int
    matcher: str | None = None
    actions: list[CodexHookAction] = Field(default_factory=list)
    action: CodexHookAction = Field(default_factory=dict)
    source: CodexHookSource
    layer: CodexEditableLayer | None = None
    hookScope: CodexHookScope | None = None
    readOnly: bool
    editable: bool = False
    scope: CodexReadableScope | None = None
    sourcePath: str | None = None
    pluginId: str | None = None
    pluginName: str | None = None
    marketplaceName: str | None = None
    trustState: CodexPluginHookTrustState | None = None
    trusted: bool | None = None
    effective: bool | None = None
    trustRevision: str | None = None
    generation: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CodexHookEntryUpsertRequest(BaseModel):
    """Structured upsert for an editable hooks.json entry."""

    entry: CodexHookEntry
    previous: CodexHookEntry | None = None
    revision: str


class CodexHookEntryDeleteRequest(BaseModel):
    """Structured delete for an editable hooks.json entry."""

    entry: CodexHookEntry
    revision: str


class CodexHooksDocumentUpdateRequest(BaseModel):
    """Raw hooks.json update request."""

    content: str
    revision: str


class CodexHooksDocumentResponse(BaseModel):
    """Hooks document response."""

    workspaceId: str
    scope: CodexHookScope
    path: str
    content: str
    exists: bool
    revision: str
    featureEnabled: bool
    effectiveFeatureEnabled: bool = False
    readOnly: bool = False
    editable: bool = True
    source: CodexHookSource = "hooks_json"
    inlineHooks: list[dict[str, Any]] = Field(default_factory=list)
    entries: list[CodexHookEntry] = Field(default_factory=list)
    eventMetadata: list[CodexHookEventMetadata] = Field(default_factory=list)
    providerResourceGeneration: int | None = None


class CodexHooksScopesResponse(BaseModel):
    """Hooks response for all editable scopes."""

    workspaceId: str
    scopes: list[CodexHooksDocumentResponse] = Field(default_factory=list)
    providerResourceGeneration: int | None = None


class CodexFeatureEnableResponse(BaseModel):
    """Feature enable response."""

    workspaceId: str
    featureEnabled: bool


class CodexPluginScopeState(BaseModel):
    """Codex plugin enabled state for one config scope."""

    scope: CodexEditableScope
    configured: bool = False
    enabled: bool | None = None


class CodexPluginSummary(BaseModel):
    """Local Codex plugin registry summary."""

    id: str
    name: str
    displayName: str
    shortDescription: str | None = None
    version: str | None = None
    authorName: str | None = None
    category: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    brandColor: str | None = None
    homepage: str | None = None
    marketplace: str | None = None
    listed: bool = False
    installed: bool = False
    effectiveEnabled: bool = False
    scopes: list[CodexPluginScopeState] = Field(default_factory=list)
    resourceCounts: dict[str, int] = Field(default_factory=dict)


class CodexPluginSkillDetail(BaseModel):
    """Skill bundled in a Codex plugin."""

    name: str
    description: str | None = None
    path: str


class CodexPluginMcpToolPolicy(BaseModel):
    """One provider-native plugin MCP tool approval override."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    approval_mode: CodexMcpApprovalMode | None = Field(
        default=None,
        alias="approvalMode",
    )


class CodexPluginMcpPolicy(BaseModel):
    """Provider-native policy overlay for one plugin MCP server."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    enabled: bool = True
    default_tools_approval_mode: CodexMcpApprovalMode | None = Field(
        default=None,
        alias="defaultToolsApprovalMode",
    )
    enabled_tools: list[str] | None = Field(default=None, alias="enabledTools")
    disabled_tools: list[str] | None = Field(default=None, alias="disabledTools")
    tools: dict[str, CodexPluginMcpToolPolicy] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tool_sets(self) -> CodexPluginMcpPolicy:
        for values in (self.enabled_tools, self.disabled_tools):
            if values is None:
                continue
            if any(not item.strip() for item in values) or len(values) != len(
                set(values)
            ):
                raise ValueError("MCP tool names must be non-empty and unique")
        if self.enabled_tools is not None and self.disabled_tools is not None:
            overlap = set(self.enabled_tools) & set(self.disabled_tools)
            if overlap:
                raise ValueError("MCP tools cannot be both enabled and disabled")
        if any(not name.strip() for name in self.tools):
            raise ValueError("MCP tool policy names must be non-empty")
        return self


class CodexPluginMcpServerDetail(BaseModel):
    """MCP server bundled in a Codex plugin."""

    name: str
    serverId: str
    command: str | None = None
    url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    policy: CodexPluginMcpPolicy | None = None
    policyRevision: str | None = None
    effective: bool = False
    generation: int | None = None


class CodexPluginAppDetail(BaseModel):
    """App bundled in a Codex plugin."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class CodexAppResource(BaseModel):
    """Read-only app or connector definition from an installed Codex plugin."""

    name: str
    scope: Literal["plugin"] = "plugin"
    definition: dict[str, Any]
    plugin_id: str = Field(alias="pluginId")
    plugin_name: str = Field(alias="pluginName")
    marketplace_id: str = Field(alias="marketplaceId")
    enabled: bool
    read_only: Literal[True] = Field(default=True, alias="readOnly")
    editable: Literal[False] = False
    relative_source_path: str = Field(alias="relativeSourcePath")
    generation: int
    provenance: PluginResourceProvenance

    model_config = ConfigDict(populate_by_name=True)


class CodexAppsResponse(BaseModel):
    """Installed Codex plugin app and connector definitions."""

    workspace_id: str = Field(alias="workspaceId")
    provider_resource_generation: int = Field(alias="providerResourceGeneration")
    apps: list[CodexAppResource] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class CodexAppResponse(BaseModel):
    """One installed Codex plugin app or connector definition."""

    workspace_id: str = Field(alias="workspaceId")
    provider_resource_generation: int = Field(alias="providerResourceGeneration")
    app: CodexAppResource

    model_config = ConfigDict(populate_by_name=True)


class CodexPluginHookDetail(BaseModel):
    """Hook bundled in a Codex plugin."""

    name: str
    path: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    trustState: CodexPluginHookTrustState = "untrusted"
    trusted: bool = False
    effective: bool = False
    trustRevision: str | None = None
    generation: int | None = None


class CodexPluginDetail(BaseModel):
    """Codex plugin detail response."""

    id: str
    name: str
    displayName: str
    marketplace: str | None = None
    version: str | None = None
    authorName: str | None = None
    shortDescription: str | None = None
    longDescription: str | None = None
    category: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    brandColor: str | None = None
    homepage: str | None = None
    keywords: list[str] = Field(default_factory=list)
    license: str | None = None
    repository: str | None = None
    websiteURL: str | None = None
    privacyPolicyURL: str | None = None
    termsOfServiceURL: str | None = None
    defaultPrompts: list[str] = Field(default_factory=list)
    readme: str | None = None
    skills: list[CodexPluginSkillDetail] = Field(default_factory=list)
    mcpServers: list[CodexPluginMcpServerDetail] = Field(default_factory=list)
    apps: list[CodexPluginAppDetail] = Field(default_factory=list)
    hooks: list[CodexPluginHookDetail] = Field(default_factory=list)
    effectiveEnabled: bool = False
    scopes: list[CodexPluginScopeState] = Field(default_factory=list)


class CodexPluginDetailResponse(BaseModel):
    """Codex plugin detail response wrapper."""

    workspaceId: str
    providerResourceGeneration: int
    plugin: CodexPluginDetail


class CodexPluginsResponse(BaseModel):
    """Codex plugins registry/config response."""

    workspaceId: str
    providerResourceGeneration: int
    plugins: list[CodexPluginSummary] = Field(default_factory=list)
    installReserved: bool = True


class CodexPluginToggleRequest(BaseModel):
    """Plugin enabled state request."""

    model_config = ConfigDict(extra="forbid")

    scope: CodexEditableScope = "user"
    enabled: bool
    revision: str | None = None


class CodexPluginToggleResponse(BaseModel):
    """Plugin enabled state response."""

    workspaceId: str
    scope: CodexEditableScope
    pluginId: str
    enabled: bool
    revision: str
    providerResourceGeneration: int
    newThreadRequired: bool = True


class CodexPluginMcpPolicyUpdateRequest(BaseModel):
    """Replace one plugin MCP server policy with revision protection."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["user"] = "user"
    policy: CodexPluginMcpPolicy
    revision: str = Field(min_length=1)


class CodexPluginMcpPolicyUpdateResponse(BaseModel):
    """Verified plugin MCP policy mutation response."""

    workspaceId: str
    scope: Literal["user"] = "user"
    pluginId: str
    serverId: str
    policy: CodexPluginMcpPolicy
    effective: bool
    revision: str
    providerResourceGeneration: int
    newThreadRequired: bool = True


class CodexPluginHookTrustUpdateRequest(BaseModel):
    """Approve or revoke all command hooks contributed by one plugin."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["user"] = "user"
    trusted: bool
    revision: str = Field(min_length=1)


class CodexPluginHookTrustUpdateResponse(BaseModel):
    """Verified provider hook trust mutation response."""

    workspaceId: str
    scope: Literal["user"] = "user"
    pluginId: str
    trusted: bool
    trustState: CodexPluginHookTrustState
    revision: str
    providerResourceGeneration: int
    newThreadRequired: bool = True


class CodexFileSummary(BaseModel):
    """Codex managed file summary."""

    name: str
    path: str
    sizeBytes: int
    source: Literal["user", "project", "plugin", "built_in"] = "project"
    readOnly: bool = False
    editable: bool | None = None
    scope: CodexReadableScope | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodexFileListResponse(BaseModel):
    """Codex managed file list response."""

    workspaceId: str
    scope: CodexCollectionScope
    resource: str
    directory: str
    files: list[CodexFileSummary] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class CodexFileUpdateRequest(BaseModel):
    """Codex managed file update request."""

    path: str
    content: str
    revision: str | None = None


class CodexSubagentDefinition(BaseModel):
    """Structured Codex subagent definition."""

    name: str
    description: str
    developer_instructions: str
    nickname_candidates: list[str] | None = None
    model: str | None = None
    model_reasoning_effort: str | None = None
    sandbox_mode: str | None = None
    mcp_servers: dict[str, Any] | None = None
    skills: dict[str, Any] | None = None


class CodexSubagentItem(BaseModel):
    """Codex subagent source item."""

    id: str
    name: str
    source: CodexSubagentSource
    editable: bool = False
    readOnly: bool = True
    scope: CodexReadableScope | None = None
    path: str | None = None
    relativePath: str | None = None
    sourcePath: str | None = None
    content: str = ""
    definition: CodexSubagentDefinition | None = None
    effective: bool = False
    overridden: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodexSubagentRegistrySettings(BaseModel):
    """Global Codex [agents] registry settings."""

    max_threads: int | None = None
    max_depth: int | None = None
    job_max_runtime_seconds: int | None = None


class CodexSubagentRegistrySource(BaseModel):
    """Subagent registry settings source."""

    scope: CodexEditableScope
    path: str
    settings: dict[str, Any] = Field(default_factory=dict)


class CodexSubagentsResponse(BaseModel):
    """Codex subagents list response."""

    workspaceId: str
    items: list[CodexSubagentItem] = Field(default_factory=list)
    registry: list[CodexSubagentRegistrySource] = Field(default_factory=list)


class CodexSubagentSaveRequest(BaseModel):
    """Subagent save request."""

    scope: CodexEditableScope
    path: str | None = None
    previousPath: str | None = None
    content: str | None = None
    definition: CodexSubagentDefinition | None = None
    overwrite: bool = False


class CodexSubagentDeleteResponse(BaseModel):
    """Subagent delete response."""

    workspaceId: str
    scope: CodexEditableScope
    path: str
    deleted: bool
