"""OpenSpec runtime API models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OpenSpecActionAvailability(str, Enum):
    """OpenSpec action availability status."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    HIDDEN = "hidden"
    SETUP_REQUIRED = "setup_required"
    SYNC_REQUIRED = "sync_required"
    BLOCKED = "blocked"


class OpenSpecActionGroup(str, Enum):
    """OpenSpec action group."""

    START = "start"
    PLAN = "plan"
    IMPLEMENT = "implement"
    FINALIZE = "finalize"
    LEARN = "learn"


class OpenSpecActionProfile(str, Enum):
    """OpenSpec action workflow profile."""

    CORE = "core"
    EXPANDED = "expanded"


class OpenSpecWorkspaceProfile(str, Enum):
    """OpenSpec workspace currently enabled workflow profile."""

    CORE = "core"
    EXPANDED = "expanded"
    CUSTOM = "custom"


class OpenSpecActionInputKind(str, Enum):
    """OpenSpec action UI input type."""

    NONE = "none"
    CHANGE = "change"
    STRUCTURED = "structured"


class OpenSpecChangeStatus(str, Enum):
    """OpenSpec change navigation status."""

    IN_PROGRESS = "in-progress"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class OpenSpecActionContextSubview(str, Enum):
    """OpenSpec action frontend subview for resolution."""

    IN_PROGRESS = "in-progress"
    COMPLETE = "complete"
    ARCHIVED = "archived"
    CUSTOMIZATION = "customization"


class OpenSpecChangeSummary(BaseModel):
    """OpenSpec change summary."""

    name: str = Field(description="Change name")
    status: str | None = Field(default=None, description="Change status")
    completedTasks: int = Field(default=0, description="Number of completed tasks")
    totalTasks: int = Field(default=0, description="Total tasks")
    lastModified: str | None = Field(default=None, description="Last update time")


class OpenSpecSpecDocument(BaseModel):
    """OpenSpec spec document summary."""

    capabilityName: str = Field(description="Capability name")
    path: str = Field(description="Spec document path")


class OpenSpecNavigationChange(BaseModel):
    """OpenSpec second column navigation change data."""

    name: str = Field(description="Change name")
    status: OpenSpecChangeStatus = Field(description="Change navigation status")
    archived: bool = Field(description="Whether this is an archived change")
    proposalPath: str | None = Field(default=None, description="proposal.md path")
    designPath: str | None = Field(default=None, description="design.md path")
    tasksPath: str | None = Field(default=None, description="tasks.md path")
    specs: list[OpenSpecSpecDocument] = Field(default_factory=list, description="Spec document list")
    completedTasks: int = Field(default=0, description="Number of completed checklist tasks")
    totalTasks: int = Field(default=0, description="Total checklist tasks")
    lastModified: str | None = Field(default=None, description="Last update time")


class OpenSpecActionItem(BaseModel):
    """OpenSpec action definition."""

    id: str = Field(description="Action ID")
    title: str = Field(description="Display title")
    description: str = Field(description="Description")
    group: OpenSpecActionGroup = Field(description="Group")
    profile: OpenSpecActionProfile = Field(description="Belonging profile")
    availability: OpenSpecActionAvailability = Field(description="Availability")
    reason: str | None = Field(default=None, description="Status reason")
    recommended: bool = Field(default=False, description="Whether recommended")
    recommendedReason: str | None = Field(default=None, description="Recommended reason")
    requiresChange: bool = Field(default=False, description="Whether change context is required")
    supportsChangeArgument: bool = Field(default=False, description="Whether change name parameter is supported")
    inputKind: OpenSpecActionInputKind = Field(default=OpenSpecActionInputKind.NONE, description="UI input type")
    exampleCommand: str | None = Field(default=None, description="Example command")
    draftTemplate: str = Field(description="Default content to insert in chat draft")


class OpenSpecWorkspaceState(BaseModel):
    """Workspace OpenSpec state."""

    cliInstalled: bool = Field(description="Whether OpenSpec CLI is installed")
    cliVersion: str | None = Field(default=None, description="OpenSpec CLI version")
    initialized: bool = Field(description="Whether openspec/ is initialized")
    profile: OpenSpecWorkspaceProfile = Field(description="Current profile")
    projectSynced: bool | None = Field(default=None, description="Whether project is synced with workflow settings")
    activeChanges: list[OpenSpecChangeSummary] = Field(default_factory=list, description="Changes in progress")


class OpenSpecWorkspaceSummaryCounts(BaseModel):
    """Workspace OpenSpec grouped counts for generic surfaces."""

    inProgress: int = Field(default=0, description="Number of in-progress changes")
    complete: int = Field(default=0, description="Number of completed changes")
    archived: int = Field(default=0, description="Number of archived changes")


class OpenSpecWorkspaceSummaryResponse(BaseModel):
    """Workspace OpenSpec lightweight summary response."""

    workspaceId: str = Field(description="Workspace ID")
    initialized: bool = Field(description="Whether openspec/ is initialized")
    counts: OpenSpecWorkspaceSummaryCounts = Field(description="Change counts grouped by status")


class OpenSpecWorkspaceResponse(BaseModel):
    """OpenSpec workspace state and actions aggregate response."""

    workspaceId: str = Field(description="Workspace ID")
    state: OpenSpecWorkspaceState = Field(description="OpenSpec state")
    actions: list[OpenSpecActionItem] = Field(default_factory=list, description="Available actions")
    changes: list[OpenSpecNavigationChange] = Field(default_factory=list, description="OpenSpec navigation changes")


class OpenSpecCustomizationFileKind(str, Enum):
    """Customization file kind."""

    CONFIG = "config"
    SCHEMA = "schema"
    TEMPLATE = "template"


class OpenSpecCustomizationTemplateFile(BaseModel):
    """Schema template file summary."""

    name: str = Field(description="Template filename")
    path: str = Field(description="Template path")


class OpenSpecCustomizationSchema(BaseModel):
    """Project-local schema summary."""

    name: str = Field(description="Schema name")
    path: str = Field(description="Schema directory path")
    schemaPath: str = Field(description="schema.yaml path")
    isDefault: bool = Field(description="Whether this is the current default schema")
    isInvalid: bool = Field(description="Whether schema validation failed")
    templateFiles: list[OpenSpecCustomizationTemplateFile] = Field(default_factory=list, description="Template files")


class OpenSpecCustomizationStateResponse(BaseModel):
    """Customization explorer aggregate state."""

    workspaceId: str = Field(description="Workspace ID")
    configPath: str = Field(description="config.yaml path")
    configPresent: bool = Field(description="Whether config.yaml exists")
    defaultSchema: str | None = Field(default=None, description="Current project default schema")
    builtInSchemas: list[str] = Field(default_factory=list, description="Built-in schemas available for fork")
    schemas: list[OpenSpecCustomizationSchema] = Field(default_factory=list, description="Project-local schemas")


class OpenSpecCustomizationFileResponse(BaseModel):
    """Customization file content."""

    workspaceId: str = Field(description="Workspace ID")
    path: str = Field(description="File path")
    name: str = Field(description="Filename")
    kind: OpenSpecCustomizationFileKind = Field(description="File kind")
    content: str = Field(description="File content")
    editable: bool = Field(description="Whether editable")
    language: str = Field(description="Editor language")
    schemaName: str | None = Field(default=None, description="Belonging schema")
    metadata: dict[str, object] = Field(default_factory=dict, description="Additional metadata")


class OpenSpecCustomizationFileUpdateRequest(BaseModel):
    """Update customization file content."""

    content: str = Field(description="New file content")


class OpenSpecCustomizationSchemaForkRequest(BaseModel):
    """Fork schema request."""

    sourceSchema: str = Field(description="Source schema")
    destinationSchema: str = Field(description="Target schema name")


class OpenSpecCustomizationSchemaCreateRequest(BaseModel):
    """Create schema request."""

    name: str = Field(description="Schema name")
    description: str | None = Field(default=None, description="Schema description")
    artifacts: list[str] = Field(default_factory=list, description="Artifacts")


class OpenSpecCustomizationActionResponse(BaseModel):
    """Customization action generic response."""

    success: bool = Field(default=True, description="Whether successful")
    message: str = Field(description="Message")
    schemaName: str | None = Field(default=None, description="Schema name")
    path: str | None = Field(default=None, description="Related path")


class OpenSpecCustomizationValidationRequest(BaseModel):
    """Validation request."""

    path: str = Field(description="Current context path")


class OpenSpecCustomizationDiagnostic(BaseModel):
    """Validation diagnostics."""

    level: str = Field(description="Level")
    message: str = Field(description="Message")


class OpenSpecCustomizationValidationResponse(BaseModel):
    """Customization validation result."""

    workspaceId: str = Field(description="Workspace ID")
    targetPath: str = Field(description="Validation source path")
    schemaName: str | None = Field(default=None, description="Validated schema")
    valid: bool = Field(description="Whether passed")
    diagnostics: list[OpenSpecCustomizationDiagnostic] = Field(default_factory=list, description="Diagnostic results")


class OpenSpecCustomizationResolutionStep(BaseModel):
    """Schema resolution step."""

    order: int = Field(description="Order")
    label: str = Field(description="Step name")
    value: str | None = Field(default=None, description="Step value")
    selected: bool = Field(default=False, description="Whether this is the adopted source")


class OpenSpecCustomizationDebugResponse(BaseModel):
    """Customization debug / schema resolution result."""

    workspaceId: str = Field(description="Workspace ID")
    targetPath: str = Field(description="Source path")
    schemaName: str | None = Field(default=None, description="Derived schema name")
    resolvedName: str | None = Field(default=None, description="Final resolved schema")
    source: str | None = Field(default=None, description="Source")
    path: str | None = Field(default=None, description="resolved path")
    resolutionOrder: list[OpenSpecCustomizationResolutionStep] = Field(default_factory=list, description="Resolution steps")
