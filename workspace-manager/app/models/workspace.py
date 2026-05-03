"""Workspace-related Pydantic models"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from app.utils.pydantic import CamelModel
from app.models.knowledge_base import KnowledgeBaseAttachmentMode, KnowledgeBaseRole

BrowserStatusType = Literal['stopped', 'starting', 'running', 'error', 'restarting']
CanvasStatusType = Literal['stopped', 'starting', 'running', 'error', 'restarting']
CanvasType = Literal['html', 'nextjs', 'default']
CanvasManifestStatus = Literal['missing', 'valid', 'invalid']
ProvisionerType = Literal['docker', 'kubernetes']
FirewallDomainAccessMode = Literal['all', 'specific']
WorkspaceShareRole = Literal['viewer', 'editor', 'manager']
WorkspaceAccessRole = Literal['owner', 'manager', 'editor', 'viewer']
WorkspaceAccessSource = Literal['owned', 'shared']


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


class WorkspaceResourceValues(CamelModel):
    cpu: str
    memory: str


class WorkspaceResourceRequirements(CamelModel):
    requests: WorkspaceResourceValues
    limits: WorkspaceResourceValues


class RuntimeStatus(CamelModel):
    status: str = "stopped"
    container_id: Optional[str] = Field(None, alias="containerId")
    internal_url: Optional[str] = Field(None, alias="internalUrl")
    external_url: Optional[str] = Field(None, alias="externalUrl")
    internal_port: int = Field(3002, alias="internalPort")
    external_port: Optional[int] = Field(None, alias="externalPort")
    last_seen: Optional[datetime] = Field(None, alias="lastSeen")
    terminal_external_port: Optional[int] = Field(None, alias="terminalExternalPort")
    terminal_external_url: Optional[str] = Field(None, alias="terminalExternalUrl")

    # Browser container fields
    browser_container_id: Optional[str] = Field(None, alias="browserContainerId")
    browser_status: BrowserStatusType = Field("stopped", alias="browserStatus")
    browser_created_at: Optional[datetime] = Field(None, alias="browserCreatedAt")
    browser_last_seen: Optional[datetime] = Field(None, alias="browserLastSeen")

    # Browser WebRTC (neko) fields
    browser_webrtc_internal_url: Optional[str] = Field(None, alias="browserWebrtcInternalUrl")
    browser_webrtc_external_url: Optional[str] = Field(None, alias="browserWebrtcExternalUrl")
    browser_webrtc_internal_port: int = Field(6080, alias="browserWebrtcInternalPort")
    browser_webrtc_external_port: Optional[int] = Field(None, alias="browserWebrtcExternalPort")

    # Browser CDP fields
    browser_cdp_internal_port: int = Field(9223, alias="browserCdpInternalPort")
    browser_cdp_external_port: Optional[int] = Field(None, alias="browserCdpExternalPort")

    # Canvas container fields
    canvas_container_id: Optional[str] = Field(None, alias="canvasContainerId")
    canvas_status: CanvasStatusType = Field("stopped", alias="canvasStatus")
    canvas_created_at: Optional[datetime] = Field(None, alias="canvasCreatedAt")
    canvas_last_seen: Optional[datetime] = Field(None, alias="canvasLastSeen")

    # Canvas URL/port fields
    canvas_internal_url: Optional[str] = Field(None, alias="canvasInternalUrl")
    canvas_external_url: Optional[str] = Field(None, alias="canvasExternalUrl")
    canvas_internal_port: int = Field(3003, alias="canvasInternalPort")
    canvas_external_port: Optional[int] = Field(None, alias="canvasExternalPort")

    # Canvas management API port and detection state
    canvas_api_internal_port: int = Field(3013, alias="canvasApiInternalPort")
    canvas_api_external_port: Optional[int] = Field(None, alias="canvasApiExternalPort")
    canvas_type: CanvasType = Field("default", alias="canvasType")
    canvas_manifest_status: CanvasManifestStatus = Field("missing", alias="canvasManifestStatus")
    canvas_last_sync_at: Optional[datetime] = Field(None, alias="canvasLastSyncAt")
    canvas_last_reset_at: Optional[datetime] = Field(None, alias="canvasLastResetAt")


class WorkspaceComponentStatus(CamelModel):
    phase: str = "stopped"
    internal_url: Optional[str] = Field(None, alias="internalUrl")
    external_url: Optional[str] = Field(None, alias="externalUrl")
    last_seen: Optional[datetime] = Field(None, alias="lastSeen")
    last_restart_requested_at: Optional[datetime] = Field(
        None, alias="lastRestartRequestedAt"
    )


class WorkspaceComponents(CamelModel):
    runtime: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)
    browser: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)
    canvas: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)


class FirewallRuleConfig(CamelModel):
    network_access_enabled: bool = Field(True, alias="networkAccessEnabled")
    domain_access_mode: FirewallDomainAccessMode = Field("all", alias="domainAccessMode")
    allowed_domains: list[str] = Field(default_factory=list, alias="allowedDomains")
    effective_allowed_domains: list[str] = Field(
        default_factory=list, alias="effectiveAllowedDomains"
    )


class FirewallConfig(CamelModel):
    workspace: FirewallRuleConfig = Field(default_factory=FirewallRuleConfig)
    browser: FirewallRuleConfig = Field(default_factory=FirewallRuleConfig)


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
    cli_type: str = Field("claude-code", alias="cliType")
    runtime_status: str = Field(..., alias="runtimeStatus")
    runtime_external_url: Optional[str] = Field(None, alias="runtimeExternalUrl")
    runtime_last_seen: Optional[datetime] = Field(None, alias="runtimeLastSeen")
    access_role: WorkspaceAccessRole = Field("owner", alias="accessRole")
    access_source: WorkspaceAccessSource = Field("owned", alias="accessSource")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class WorkspaceDetail(CamelModel):
    id: str
    owner: WorkspaceOwner
    name: str
    description: Optional[str] = None
    template_id: Optional[str] = Field(None, alias="templateId")
    git_url: Optional[str] = Field(None, alias="gitUrl")
    branch: str
    runtime: str
    provisioner: ProvisionerType = "docker"
    target_namespace: Optional[str] = Field(None, alias="targetNamespace")
    overall_phase: str = Field(..., alias="overallPhase")
    cli_type: str = Field("claude-code", alias="cliType")
    setup_script: Optional[str] = Field(None, alias="setupScript")
    env_vars: list[WorkspaceEnvVar] = Field(default_factory=list, alias="envVars")
    runtime_resources: Optional[WorkspaceResourceRequirements] = Field(
        None,
        alias="runtimeResources",
    )
    runtime_status: RuntimeStatus = Field(default_factory=RuntimeStatus, alias="runtimeStatus")
    components: WorkspaceComponents = Field(default_factory=WorkspaceComponents)
    firewall_available: bool = Field(False, alias="firewallAvailable")
    firewall_unavailable_reason: Optional[str] = Field(
        None, alias="firewallUnavailableReason"
    )
    firewall: FirewallConfig = Field(default_factory=FirewallConfig)
    preferred_cli: str = Field("claude-code", alias="preferredCli")
    fallback_enabled: bool = Field(True, alias="fallbackEnabled")
    workspace_path: str = Field("/workspace", alias="workspacePath")
    acp_cli_args: list[str] = Field(default_factory=list, alias="acpCliArgs")
    access_role: WorkspaceAccessRole = Field("owner", alias="accessRole")
    access_source: WorkspaceAccessSource = Field("owned", alias="accessSource")
    attached_knowledge_bases: list["WorkspaceKnowledgeBaseAttachment"] = Field(
        default_factory=list,
        alias="attachedKnowledgeBases",
    )
    mounted_kb_signature: Optional[str] = Field(None, alias="mountedKbSignature")
    has_pending_kb_changes: bool = Field(False, alias="hasPendingKbChanges")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    runtime_job: Optional["WorkspaceRuntimeJobSummary"] = Field(
        None, alias="runtimeJob"
    )


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
    scheduled_at: datetime = Field(..., alias="scheduledAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    finished_at: Optional[datetime] = Field(None, alias="finishedAt")
    error_message: Optional[str] = Field(None, alias="errorMessage")


class WorkspaceShare(CamelModel):
    id: str
    user: WorkspaceShareUser
    role: WorkspaceShareRole
    granted_by: WorkspaceShareUser = Field(..., alias="grantedBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class WorkspaceShareListResponse(CamelModel):
    items: list[WorkspaceShare]


class WorkspaceShareCreateRequest(CamelModel):
    email: str
    role: WorkspaceShareRole


class WorkspaceShareUpdateRequest(CamelModel):
    role: WorkspaceShareRole


class WorkspaceKnowledgeBaseAttachment(CamelModel):
    id: str
    kb_id: str = Field(..., alias="kbId")
    name: str
    slug: str
    role: Optional[KnowledgeBaseRole] = None
    mount_alias: str = Field(..., alias="mountAlias")
    mode: KnowledgeBaseAttachmentMode
    attached_by_id: str = Field(..., alias="attachedById")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class WorkspaceKnowledgeBaseAttachmentListResponse(CamelModel):
    items: list[WorkspaceKnowledgeBaseAttachment]


class WorkspaceKnowledgeBaseAttachmentCreateRequest(CamelModel):
    kb_id: str = Field(..., alias="kbId")
    mount_alias: Optional[str] = Field(None, alias="mountAlias")
    mode: str = "rw"


class WorkspaceKnowledgeBaseAttachmentUpdateRequest(CamelModel):
    mount_alias: Optional[str] = Field(None, alias="mountAlias")
    mode: Optional[str] = None


class WorkspaceListResponse(CamelModel):
    items: list[WorkspaceSummary]
    pagination: Pagination


class WorkspaceCreateRequest(CamelModel):
    name: str
    owner_id: Optional[str] = Field(None, alias="ownerId")
    description: Optional[str] = None
    git_url: Optional[str] = Field(None, alias="gitUrl")
    branch: Optional[str] = None
    runtime: str
    provisioner: ProvisionerType = "docker"
    target_namespace: Optional[str] = Field(None, alias="targetNamespace")
    cli_type: Optional[str] = Field(None, alias="cliType")
    setup_script: Optional[str] = Field(None, alias="setupScript")
    env_vars: list[WorkspaceEnvVar] = Field(default_factory=list, alias="envVars")
    runtime_resources: Optional[WorkspaceResourceRequirements] = Field(
        None,
        alias="runtimeResources",
    )
    template_id: Optional[str] = Field(None, alias="templateId")
    preferred_cli: Optional[str] = Field(None, alias="preferredCli")
    fallback_enabled: Optional[bool] = Field(None, alias="fallbackEnabled")
    workspace_path: Optional[str] = Field(None, alias="workspacePath")
    acp_cli_args: Optional[list[str]] = Field(None, alias="acpCliArgs")
    firewall: Optional[FirewallConfig] = None


class WorkspaceUpdateRequest(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    git_url: Optional[str] = Field(None, alias="gitUrl")
    branch: Optional[str] = None
    runtime: Optional[str] = None
    provisioner: Optional[ProvisionerType] = None
    target_namespace: Optional[str] = Field(None, alias="targetNamespace")
    setup_script: Optional[str] = Field(None, alias="setupScript")
    env_vars: Optional[list[WorkspaceEnvVar]] = Field(None, alias="envVars")
    runtime_resources: Optional[WorkspaceResourceRequirements] = Field(
        None,
        alias="runtimeResources",
    )
    runtime_status: Optional[RuntimeStatus] = Field(None, alias="runtimeStatus")
    firewall: Optional[FirewallConfig] = None
    preferred_cli: Optional[str] = Field(None, alias="preferredCli")
    fallback_enabled: Optional[bool] = Field(None, alias="fallbackEnabled")
    workspace_path: Optional[str] = Field(None, alias="workspacePath")
    acp_cli_args: Optional[list[str]] = Field(None, alias="acpCliArgs")


class WorkspaceSetupTaskStatus(CamelModel):
    task_key: str = Field(..., alias="taskKey")
    task_name: str = Field(..., alias="taskName")
    status: str
    message: Optional[str] = None


class WorkspaceSetupStatus(CamelModel):
    workspace_id: str = Field(..., alias="workspaceId")
    completed: bool
    tasks: list[WorkspaceSetupTaskStatus]
