"""Workspace-related Pydantic models"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.modules.workspace.firewall_contract import FirewallConfig
from app.core.pydantic import CamelModel
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
)
from app.modules.workspace.environment import (
    WorkspaceEnvironmentError,
    ensure_unique_workspace_env_key,
    validate_workspace_env_key,
)

BrowserStatusType = Literal["stopped", "starting", "running", "error", "restarting"]
CanvasStatusType = Literal["stopped", "starting", "running", "error", "restarting"]
CanvasType = Literal["html", "nextjs", "default"]
CanvasManifestStatus = Literal["missing", "valid", "invalid"]
ProvisionerType = Literal["docker", "kubernetes"]
WorkspaceShareRole = Literal["reader", "manager"]
WorkspaceAccessSource = ResourceAccessSource
DEFAULT_WORKTREE_SUBDIR = ".worktrees"
WORKTREE_SUBDIR_MAX_LENGTH = 64
SUPPORTED_AGENTIC_TOOLS = ("claude-code", "codex", "opencode")
SUPPORTED_AGENTIC_TOOL_SET = set(SUPPORTED_AGENTIC_TOOLS)
DEFAULT_AGENTIC_TOOLS = ["claude-code"]
SETUP_SCRIPT_MAX_BYTES = 256 * 1024


def validate_setup_script(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if "\x00" in value:
        raise ValueError("setupScript must not contain NUL bytes")
    if len(value.encode("utf-8")) > SETUP_SCRIPT_MAX_BYTES:
        raise ValueError(
            f"setupScript must not exceed {SETUP_SCRIPT_MAX_BYTES} UTF-8 bytes"
        )
    return value


def normalize_agentic_tools(value: list[str] | None) -> list[str]:
    """Validate and sort workspace enabled agentic tools."""
    if value is None:
        tools = list(DEFAULT_AGENTIC_TOOLS)
    else:
        tools = list(value)
    if not tools:
        raise ValueError("agenticTools must include at least one tool")
    if len(set(tools)) != len(tools):
        raise ValueError("agenticTools must not contain duplicates")
    unknown = [tool for tool in tools if tool not in SUPPORTED_AGENTIC_TOOL_SET]
    if unknown:
        raise ValueError(f"Unsupported agenticTools: {', '.join(unknown)}")
    return [tool for tool in SUPPORTED_AGENTIC_TOOLS if tool in tools]


def validate_worktree_subdir(value: Optional[str]) -> Optional[str]:
    """Normalize and validate a managed worktree relative path."""
    if value is None:
        return None

    normalized = value.strip()
    segments = normalized.split("/")
    if (
        not normalized
        or normalized == "."
        or normalized.startswith("/")
        or normalized.endswith("/")
        or "\\" in normalized
        or any(not segment for segment in segments)
        or any(segment in {".", ".."} for segment in segments)
        or len(normalized) > WORKTREE_SUBDIR_MAX_LENGTH
    ):
        raise PydanticCustomError(
            "WORKSPACE_WORKTREE_SUBDIR_INVALID",
            "workspace.worktree_subdir.invalid",
        )
    return normalized


class Pagination(CamelModel):
    page: int = 1
    page_size: int = Field(20, alias="pageSize")
    total: int = 0


class WorkspaceOwner(CamelModel):
    id: str
    display_name: str = Field(..., alias="displayName")
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")
    username: Optional[str] = None
    email: Optional[str] = None


class WorkspaceShareUser(CamelModel):
    id: str
    display_name: str = Field(..., alias="displayName")
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")
    username: Optional[str] = None
    email: Optional[str] = None


class WorkspaceEnvVar(CamelModel):
    key: str
    value: str

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        try:
            return validate_workspace_env_key(value)
        except WorkspaceEnvironmentError as exc:
            raise PydanticCustomError(
                exc.code,
                exc.message_key,
                {"key": exc.key},
            ) from exc


def validate_workspace_env_vars(
    value: list[WorkspaceEnvVar] | None,
) -> list[WorkspaceEnvVar] | None:
    """Reject ambiguous duplicate workspace environment keys."""

    seen: set[str] = set()
    for item in value or []:
        try:
            ensure_unique_workspace_env_key(item.key, seen)
        except WorkspaceEnvironmentError as exc:
            raise PydanticCustomError(
                exc.code,
                exc.message_key,
                {"key": exc.key},
            ) from exc
    return value


class RuntimeStatus(CamelModel):
    status: str = "stopped"
    container_id: Optional[str] = Field(None, alias="containerId")
    runtime_url: str = Field(..., alias="runtimeUrl")
    browser_url: str = Field(..., alias="browserUrl")
    canvas_url: str = Field(..., alias="canvasUrl")
    last_seen: Optional[datetime] = Field(None, alias="lastSeen")

    # Browser container fields
    browser_container_id: Optional[str] = Field(None, alias="browserContainerId")
    browser_status: BrowserStatusType = Field("stopped", alias="browserStatus")
    browser_created_at: Optional[datetime] = Field(None, alias="browserCreatedAt")
    browser_last_seen: Optional[datetime] = Field(None, alias="browserLastSeen")

    # Canvas container fields
    canvas_container_id: Optional[str] = Field(None, alias="canvasContainerId")
    canvas_status: CanvasStatusType = Field("stopped", alias="canvasStatus")
    canvas_created_at: Optional[datetime] = Field(None, alias="canvasCreatedAt")
    canvas_last_seen: Optional[datetime] = Field(None, alias="canvasLastSeen")

    canvas_type: CanvasType = Field("default", alias="canvasType")
    canvas_manifest_status: CanvasManifestStatus = Field(
        "missing", alias="canvasManifestStatus"
    )
    canvas_last_sync_at: Optional[datetime] = Field(None, alias="canvasLastSyncAt")
    canvas_last_reset_at: Optional[datetime] = Field(None, alias="canvasLastResetAt")


class WorkspaceComponentStatus(CamelModel):
    phase: str = "stopped"
    desired_revision: int = Field(1, alias="desiredRevision")
    observed_revision: int = Field(0, alias="observedRevision")
    ready: bool = False
    terminal_ready: Optional[bool] = Field(None, alias="terminalReady")
    workload_id: Optional[str] = Field(None, alias="workloadId")
    reason: Optional[str] = None
    error_code: Optional[str] = Field(None, alias="errorCode")
    last_transition_at: Optional[datetime] = Field(None, alias="lastTransitionAt")
    last_seen: Optional[datetime] = Field(None, alias="lastSeen")
    last_restart_requested_at: Optional[datetime] = Field(
        None, alias="lastRestartRequestedAt"
    )


class WorkspaceComponents(CamelModel):
    runtime: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)
    browser: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)
    canvas: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)


class WorkspaceBootstrapStatus(CamelModel):
    desired_revision: int = Field(1, alias="desiredRevision")
    observed_revision: int = Field(0, alias="observedRevision")
    phase: str = "Pending"
    error_code: Optional[str] = Field(None, alias="errorCode")
    last_transition_at: Optional[datetime] = Field(None, alias="lastTransitionAt")


class BrowserConnectivityStatus(CamelModel):
    contract_version: Literal["browser-connectivity/v1"] = Field(
        "browser-connectivity/v1", alias="contractVersion"
    )
    state: Literal["pending", "ready", "degraded", "not_ready", "unavailable"] = (
        "pending"
    )
    admission: Literal["allowed", "denied"] = "denied"
    profile_revision: Optional[str] = Field(None, alias="profileRevision")
    credential_revision: Optional[str] = Field(None, alias="credentialRevision")
    browser_generation: Optional[str] = Field(None, alias="observedBrowserGeneration")
    backend_state: Literal[
        "pending", "ready", "degraded", "not_ready", "unavailable"
    ] = Field("pending", alias="backendState")
    backend_accepted_at: Optional[datetime] = Field(None, alias="backendAcceptedAt")
    backend_expires_at: Optional[datetime] = Field(None, alias="backendExpiresAt")
    backend_reason: Optional[str] = Field(None, alias="backendReason")
    backend_error_code: Optional[str] = Field(None, alias="backendErrorCode")
    frontend_state: Literal[
        "pending", "ready", "degraded", "not_ready", "unavailable"
    ] = Field("pending", alias="frontendState")
    frontend_accepted_at: Optional[datetime] = Field(None, alias="frontendAcceptedAt")
    frontend_expires_at: Optional[datetime] = Field(None, alias="frontendExpiresAt")
    frontend_reason: Optional[str] = Field(None, alias="frontendReason")
    frontend_error_code: Optional[str] = Field(None, alias="frontendErrorCode")
    accepted_at: Optional[datetime] = Field(None, alias="acceptedAt")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")
    reason: str = "BrowserConnectivityPending"
    error_code: Optional[str] = Field(None, alias="errorCode")
    last_transition_at: Optional[datetime] = Field(None, alias="lastTransitionAt")


class WorkspaceSummary(CamelModel):
    id: str
    name: str
    description: Optional[str] = None
    owner: WorkspaceOwner
    git_url: Optional[str] = Field(None, alias="gitUrl")
    branch: str
    runtime: str
    provisioner: ProvisionerType = "docker"
    target_namespace: Optional[str] = Field(None, alias="targetNamespace")
    overall_phase: str = Field(..., alias="overallPhase")
    agentic_tools: list[str] = Field(
        default_factory=lambda: list(DEFAULT_AGENTIC_TOOLS),
        alias="agenticTools",
    )
    runtime_status: str = Field(..., alias="runtimeStatus")
    runtime_url: str = Field(..., alias="runtimeUrl")
    runtime_last_seen: Optional[datetime] = Field(None, alias="runtimeLastSeen")
    access_role: ResourceAccessRole = Field(..., alias="accessRole")
    access_source: WorkspaceAccessSource = Field(..., alias="accessSource")
    access_sources: list[WorkspaceAccessSource] = Field(..., alias="accessSources")
    allowed_operations: list[str] = Field(..., alias="allowedOperations")
    worktree_subdir: str = Field(DEFAULT_WORKTREE_SUBDIR, alias="worktreeSubdir")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class WorkspaceReadDetail(CamelModel):
    id: str
    owner: WorkspaceOwner
    name: str
    description: Optional[str] = None
    git_url: Optional[str] = Field(None, alias="gitUrl")
    branch: str
    runtime: str
    provisioner: ProvisionerType = "docker"
    target_namespace: Optional[str] = Field(None, alias="targetNamespace")
    overall_phase: str = Field(..., alias="overallPhase")
    agentic_tools: list[str] = Field(
        default_factory=lambda: list(DEFAULT_AGENTIC_TOOLS),
        alias="agenticTools",
    )
    runtime_status: RuntimeStatus = Field(..., alias="runtimeStatus")
    bootstrap: WorkspaceBootstrapStatus = Field(
        default_factory=WorkspaceBootstrapStatus
    )
    components: WorkspaceComponents = Field(default_factory=WorkspaceComponents)
    browser_connectivity: BrowserConnectivityStatus = Field(
        default_factory=BrowserConnectivityStatus,
        alias="browserConnectivity",
    )
    firewall_available: bool = Field(False, alias="firewallAvailable")
    firewall_unavailable_reason: Optional[str] = Field(
        None, alias="firewallUnavailableReason"
    )
    firewall: FirewallConfig = Field(default_factory=FirewallConfig)
    preferred_cli: str = Field("claude-code", alias="preferredCli")
    fallback_enabled: bool = Field(True, alias="fallbackEnabled")
    workspace_path: str = Field("/workspace", alias="workspacePath")
    worktree_subdir: str = Field(DEFAULT_WORKTREE_SUBDIR, alias="worktreeSubdir")
    access_role: ResourceAccessRole = Field(..., alias="accessRole")
    access_source: WorkspaceAccessSource = Field(..., alias="accessSource")
    access_sources: list[WorkspaceAccessSource] = Field(..., alias="accessSources")
    allowed_operations: list[str] = Field(..., alias="allowedOperations")
    attached_knowledge_bases: list["WorkspaceKnowledgeBaseAttachment"] = Field(
        default_factory=list,
        alias="attachedKnowledgeBases",
    )
    knowledge_base_mount_active_revision: int = Field(
        0,
        alias="knowledgeBaseMountActiveRevision",
    )
    knowledge_base_mount_desired_revision: int = Field(
        0,
        alias="knowledgeBaseMountDesiredRevision",
    )
    knowledge_base_mount_observed_revision: int = Field(
        0,
        alias="knowledgeBaseMountObservedRevision",
    )
    knowledge_base_mount_sync_status: Literal[
        "ready",
        "preflighting",
        "applying",
        "compensating",
        "degraded",
    ] = Field(
        "ready",
        alias="knowledgeBaseMountSyncStatus",
    )
    knowledge_base_mount_error_code: Optional[str] = Field(
        None,
        alias="knowledgeBaseMountErrorCode",
    )
    runtime_access_revision: int = Field(0, alias="runtimeAccessRevision")
    runtime_access_observed_revision: int = Field(
        0,
        alias="runtimeAccessObservedRevision",
    )
    runtime_instance_id: Optional[str] = Field(None, alias="runtimeInstanceId")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    runtime_job: Optional["WorkspaceRuntimeJobSummary"] = Field(
        None, alias="runtimeJob"
    )


class WorkspaceSensitiveEnvVar(CamelModel):
    key: str
    is_configured: bool = Field(..., alias="isConfigured")


class WorkspaceSensitiveSettings(CamelModel):
    setup_script: Optional[str] = Field(None, alias="setupScript")
    env_vars: list[WorkspaceSensitiveEnvVar] = Field(
        default_factory=list,
        alias="envVars",
    )
    acp_cli_args: list[str] = Field(default_factory=list, alias="acpCliArgs")


class WorkspaceSensitiveSettingsReplaceRequest(CamelModel):
    setup_script: Optional[str] = Field(None, alias="setupScript")
    env_vars: Optional[list[WorkspaceEnvVar]] = Field(None, alias="envVars")
    acp_cli_args: Optional[list[str]] = Field(None, alias="acpCliArgs")

    model_config = ConfigDict(extra="forbid")

    @field_validator("setup_script")
    @classmethod
    def validate_setup_script_field(cls, value: Optional[str]) -> Optional[str]:
        return validate_setup_script(value)

    @field_validator("env_vars")
    @classmethod
    def validate_env_vars(
        cls,
        value: Optional[list[WorkspaceEnvVar]],
    ) -> Optional[list[WorkspaceEnvVar]]:
        return validate_workspace_env_vars(value)


class WorkspaceRuntimeLogEntry(CamelModel):
    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    stage: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(..., alias="createdAt")


class WorkspaceRuntimeJobSummary(CamelModel):
    id: str
    operation: str
    strategy: str
    status: str
    retries: int
    target_component: Optional[str] = Field(None, alias="targetComponent")
    scheduled_at: datetime = Field(..., alias="scheduledAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    finished_at: Optional[datetime] = Field(None, alias="finishedAt")
    target_revision: Optional[int] = Field(None, alias="targetRevision")
    target_runtime_instance_id: Optional[str] = Field(
        None,
        alias="targetRuntimeInstanceId",
    )
    correlation_id: str = Field(..., alias="correlationId")
    root_correlation_id: str = Field(..., alias="rootCorrelationId")
    error_code: Optional[str] = Field(None, alias="errorCode")
    phase: Optional[str] = None


class WorkspaceShare(CamelModel):
    id: str
    target_type: Literal["user", "user_group"] = Field(..., alias="targetType")
    target_id: str = Field(..., alias="targetId")
    target_label: str = Field(..., alias="targetLabel")
    role: WorkspaceShareRole
    granted_by: WorkspaceShareUser = Field(..., alias="grantedBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class WorkspaceShareListResponse(CamelModel):
    items: list[WorkspaceShare]


class WorkspaceShareCandidate(CamelModel):
    id: str
    label: str


class WorkspaceShareCandidateListResponse(CamelModel):
    items: list[WorkspaceShareCandidate]


class WorkspaceShareCreateRequest(CamelModel):
    target_type: Literal["user", "user_group"] = Field(..., alias="targetType")
    target_id: str = Field(..., alias="targetId")
    role: WorkspaceShareRole


class WorkspaceShareUpdateRequest(CamelModel):
    role: WorkspaceShareRole


class WorkspaceDeleteRequest(CamelModel):
    confirmation_name: str = Field(..., alias="confirmationName", min_length=1)


class WorkspaceKnowledgeBaseAttachment(CamelModel):
    id: str
    kb_id: str = Field(..., alias="kbId")
    name: str
    slug: str
    mount_alias: str = Field(..., alias="mountAlias")
    status: Literal["active", "pending", "pending_removal"]
    attached_by_id: Optional[str] = Field(None, alias="attachedById")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class KnowledgeBaseMountSync(CamelModel):
    status: Literal["ready", "syncing", "degraded"]
    desired_revision: int = Field(..., alias="desiredRevision")
    observed_revision: int = Field(..., alias="observedRevision")
    last_known_good_revision: int = Field(..., alias="lastKnownGoodRevision")
    error_code: Optional[str] = Field(None, alias="errorCode")
    compensating: bool = False


class WorkspaceKnowledgeBaseAttachmentListResponse(CamelModel):
    items: list[WorkspaceKnowledgeBaseAttachment]
    knowledge_base_mount_sync: KnowledgeBaseMountSync = Field(
        ...,
        alias="knowledgeBaseMountSync",
    )


class WorkspaceKnowledgeBaseAttachmentMutationResponse(CamelModel):
    attachment: WorkspaceKnowledgeBaseAttachment
    knowledge_base_mount_sync: KnowledgeBaseMountSync = Field(
        ...,
        alias="knowledgeBaseMountSync",
    )


class KnowledgeBaseMountSyncResponse(CamelModel):
    knowledge_base_mount_sync: KnowledgeBaseMountSync = Field(
        ...,
        alias="knowledgeBaseMountSync",
    )


class BrowserExtensionPairingAssertionResponse(CamelModel):
    assertion: str
    runtime_instance_id: str = Field(..., alias="runtimeInstanceId")


class WorkspaceKnowledgeBaseErrorDetail(CamelModel):
    error_code: str = Field(..., alias="errorCode")
    correlation_id: str = Field(..., alias="correlationId")
    details: Optional[dict[str, Any]] = None


class WorkspaceKnowledgeBaseErrorResponse(CamelModel):
    detail: WorkspaceKnowledgeBaseErrorDetail


class WorkspaceKnowledgeBaseAttachmentCreateRequest(CamelModel):
    kb_id: str = Field(..., alias="kbId")
    mount_alias: str = Field(..., alias="mountAlias")

    model_config = ConfigDict(extra="forbid")


class WorkspaceKnowledgeBaseAttachmentUpdateRequest(CamelModel):
    mount_alias: str = Field(..., alias="mountAlias")

    model_config = ConfigDict(extra="forbid")


class WorkspaceListResponse(CamelModel):
    items: list[WorkspaceSummary]
    pagination: Pagination


class WorkspaceCreateRequest(CamelModel):
    name: str
    owner_id: Optional[str] = Field(None, alias="ownerId")
    description: Optional[str] = None
    runtime: str
    agentic_tools: list[str] = Field(
        default_factory=lambda: list(DEFAULT_AGENTIC_TOOLS),
        alias="agenticTools",
    )
    preferred_cli: Optional[str] = Field(None, alias="preferredCli")
    fallback_enabled: Optional[bool] = Field(None, alias="fallbackEnabled")
    workspace_path: Optional[str] = Field(None, alias="workspacePath")
    worktree_subdir: Optional[str] = Field(None, alias="worktreeSubdir")
    firewall: Optional[FirewallConfig] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("agentic_tools")
    @classmethod
    def validate_agentic_tools(cls, value: list[str]) -> list[str]:
        return normalize_agentic_tools(value)

    @field_validator("worktree_subdir")
    @classmethod
    def validate_worktree_subdir_field(cls, value: Optional[str]) -> Optional[str]:
        return validate_worktree_subdir(value)


class WorkspaceUpdateRequest(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    runtime: Optional[str] = None
    agentic_tools: Optional[list[str]] = Field(None, alias="agenticTools")
    preferred_cli: Optional[str] = Field(None, alias="preferredCli")
    fallback_enabled: Optional[bool] = Field(None, alias="fallbackEnabled")
    workspace_path: Optional[str] = Field(None, alias="workspacePath")
    worktree_subdir: Optional[str] = Field(None, alias="worktreeSubdir")

    model_config = ConfigDict(extra="forbid")

    @field_validator("agentic_tools")
    @classmethod
    def validate_agentic_tools(cls, value: Optional[list[str]]) -> list[str]:
        if value is None:
            raise ValueError("agenticTools must include at least one tool")
        return normalize_agentic_tools(value)

    @field_validator("worktree_subdir")
    @classmethod
    def validate_worktree_subdir_field(cls, value: Optional[str]) -> Optional[str]:
        return validate_worktree_subdir(value)


class WorkspaceSetupTaskStatus(CamelModel):
    task_key: str = Field(..., alias="taskKey")
    task_name: str = Field(..., alias="taskName")
    status: str
    message: Optional[str] = None


class WorkspaceSetupStatus(CamelModel):
    workspace_id: str = Field(..., alias="workspaceId")
    completed: bool
    tasks: list[WorkspaceSetupTaskStatus]
