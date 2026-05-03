"""Codex settings API models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CodexEditableLayer = Literal["user", "project"]
CodexReadableLayer = Literal["user", "project", "plugin"]
CodexSubagentSource = Literal["built_in", "user", "project", "plugin"]


class CodexSettingsCapability(BaseModel):
    """Codex settings capability exposed by the API group."""

    id: str = Field(..., description="Capability identifier")
    path: str = Field(..., description="Relative API path")
    implemented: bool = Field(..., description="Whether the endpoint has full behavior")


class CodexSettingsCapabilitiesResponse(BaseModel):
    """Codex settings API group capabilities response."""

    workspaceId: str = Field(..., description="Workspace ID")
    editableLayers: list[str] = Field(default_factory=list, description="Editable layer identifiers")
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


class CodexAgentsMdCaveat(BaseModel):
    """AGENTS.md caveat shown to users."""

    type: Literal["override", "fallback", "size_limit"]
    path: str | None = None
    messageKey: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodexAgentsMdDocument(BaseModel):
    """Codex AGENTS.md document response."""

    workspaceId: str
    scope: CodexEditableLayer
    content: str
    path: str
    exists: bool
    activePath: str | None = None
    maxBytes: int
    sizeBytes: int
    caveats: list[CodexAgentsMdCaveat] = Field(default_factory=list)


class CodexAgentsMdUpdateRequest(BaseModel):
    """Codex AGENTS.md update request."""

    scope: CodexEditableLayer
    content: str


class CodexAgentsMdUpdateResponse(BaseModel):
    """Codex AGENTS.md update response."""

    workspaceId: str
    scope: CodexEditableLayer
    path: str


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
    layer: CodexEditableLayer
    path: str
    content: str
    exists: bool


class CodexConfigUpdateRequest(BaseModel):
    """Raw Codex config update request."""

    content: str


class CodexConfigUpdateResponse(BaseModel):
    """Raw Codex config update response."""

    workspaceId: str
    layer: CodexEditableLayer
    path: str


class CodexConfigSectionResponse(BaseModel):
    """Structured config section response."""

    workspaceId: str
    layer: CodexEditableLayer
    section: str
    path: str
    data: dict[str, Any] = Field(default_factory=dict)


class CodexConfigSectionUpdateRequest(BaseModel):
    """Structured config section update request."""

    data: dict[str, Any] = Field(default_factory=dict)


class CodexConfigSectionUpdateResponse(BaseModel):
    """Structured config section update response."""

    workspaceId: str
    layer: CodexEditableLayer
    section: str
    path: str
    data: dict[str, Any] = Field(default_factory=dict)


class CodexRulesFileSummary(BaseModel):
    """Rules file summary."""

    name: str
    path: str
    sizeBytes: int


class CodexRulesListResponse(BaseModel):
    """Rules file list response."""

    workspaceId: str
    layer: CodexEditableLayer
    directory: str
    files: list[CodexRulesFileSummary] = Field(default_factory=list)


class CodexTextFileResponse(BaseModel):
    """Text file response for Codex settings."""

    workspaceId: str
    layer: CodexReadableLayer
    path: str
    content: str
    exists: bool


class CodexTextFileUpdateRequest(BaseModel):
    """Text file update request."""

    path: str | None = None
    content: str


class CodexRulesValidationRequest(BaseModel):
    """Rules validation request."""

    layer: CodexEditableLayer
    path: str
    command: list[str]


class CodexRulesValidationResponse(BaseModel):
    """Rules validation response."""

    valid: bool
    exitCode: int
    stdout: str = ""
    stderr: str = ""


CodexHookSource = Literal["hooks_json", "inline_config", "plugin", "built_in", "project", "user"]
CodexHookEventScope = Literal["session_start", "turn"]
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
    raw: dict[str, Any] = Field(default_factory=dict)


class CodexHookEntry(BaseModel):
    """Normalized hook entry across editable and read-only sources."""

    id: str
    event: str
    index: int
    matcher: str | None = None
    actions: list[CodexHookCommandAction] = Field(default_factory=list)
    action: CodexHookCommandAction | dict[str, Any] = Field(default_factory=dict)
    source: CodexHookSource
    layer: CodexEditableLayer | None = None
    readOnly: bool
    sourcePath: str | None = None
    pluginId: str | None = None
    pluginName: str | None = None
    marketplaceName: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CodexHooksDocumentResponse(BaseModel):
    """Hooks document response."""

    workspaceId: str
    layer: CodexEditableLayer
    path: str
    content: str
    exists: bool
    featureEnabled: bool
    inlineHooks: list[dict[str, Any]] = Field(default_factory=list)
    entries: list[CodexHookEntry] = Field(default_factory=list)
    eventMetadata: list[CodexHookEventMetadata] = Field(default_factory=list)


class CodexHooksScopesResponse(BaseModel):
    """Hooks response for all editable scopes."""

    workspaceId: str
    scopes: list[CodexHooksDocumentResponse] = Field(default_factory=list)


class CodexFeatureEnableResponse(BaseModel):
    """Feature enable response."""

    workspaceId: str
    featureEnabled: bool


class CodexPluginSummary(BaseModel):
    """Local Codex plugin registry summary."""

    id: str
    name: str
    marketplace: str | None = None
    listed: bool = False
    installed: bool = False
    enabled: bool = False
    path: str | None = None
    sourcePath: str | None = None
    bundled: dict[str, Any] = Field(default_factory=dict)


class CodexPluginsResponse(BaseModel):
    """Codex plugins registry/config response."""

    workspaceId: str
    plugins: list[CodexPluginSummary] = Field(default_factory=list)
    installReserved: bool = True


class CodexPluginToggleRequest(BaseModel):
    """Plugin enabled state request."""

    layer: CodexEditableLayer = "user"
    enabled: bool


class CodexPluginToggleResponse(BaseModel):
    """Plugin enabled state response."""

    workspaceId: str
    layer: CodexEditableLayer
    pluginId: str
    enabled: bool
    newThreadRequired: bool = True


class CodexFileSummary(BaseModel):
    """Codex managed file summary."""

    name: str
    path: str
    sizeBytes: int
    source: Literal["user", "project", "plugin", "built_in"] = "project"
    readOnly: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodexFileListResponse(BaseModel):
    """Codex managed file list response."""

    workspaceId: str
    layer: CodexReadableLayer
    resource: str
    directory: str
    files: list[CodexFileSummary] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class CodexFileUpdateRequest(BaseModel):
    """Codex managed file update request."""

    path: str
    content: str


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
    layer: CodexEditableLayer | None = None
    path: str | None = None
    relativePath: str | None = None
    sourcePath: str | None = None
    content: str = ""
    definition: CodexSubagentDefinition | None = None
    effective: bool = False
    overridden: bool = False
    pluginId: str | None = None
    pluginName: str | None = None
    marketplaceName: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodexSubagentRegistrySettings(BaseModel):
    """Global Codex [agents] registry settings."""

    max_threads: int | None = None
    max_depth: int | None = None
    job_max_runtime_seconds: int | None = None


class CodexSubagentRegistrySource(BaseModel):
    """Source metadata for Codex [agents] registry settings."""

    layer: CodexEditableLayer
    path: str
    settings: CodexSubagentRegistrySettings


class CodexSubagentsResponse(BaseModel):
    """Codex subagents list response."""

    workspaceId: str
    items: list[CodexSubagentItem] = Field(default_factory=list)
    registry: list[CodexSubagentRegistrySource] = Field(default_factory=list)


class CodexSubagentSaveRequest(BaseModel):
    """Create or update a Codex subagent."""

    layer: CodexEditableLayer = "project"
    path: str | None = None
    content: str | None = None
    definition: CodexSubagentDefinition | None = None
    overwrite: bool = False


class CodexSubagentDeleteResponse(BaseModel):
    """Codex subagent delete response."""

    workspaceId: str
    layer: CodexEditableLayer
    path: str
    deleted: bool
