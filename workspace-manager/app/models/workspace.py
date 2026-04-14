"""工作區相關的 Pydantic 模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from app.utils.pydantic import CamelModel

# Browser 容器狀態類型
BrowserStatusType = Literal['stopped', 'starting', 'running', 'error', 'restarting']
# Next.js 容器狀態類型
NextjsStatusType = Literal['stopped', 'starting', 'running', 'error', 'restarting']
ProvisionerType = Literal['docker', 'kubernetes']
FirewallDomainAccessMode = Literal['all', 'specific']


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


class WorkspaceEnvVar(CamelModel):
    key: str
    value: str


class WorkspacePortMapping(CamelModel):
    container_port: int = Field(..., alias="containerPort")
    host_port: Optional[int] = Field(None, alias="hostPort")
    protocol: str
    description: Optional[str] = None


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
    web_preview_internal_port: int = Field(3003, alias="webPreviewInternalPort")
    web_preview_external_port: Optional[int] = Field(None, alias="webPreviewExternalPort")
    web_preview_internal_url: Optional[str] = Field(None, alias="webPreviewInternalUrl")
    web_preview_external_url: Optional[str] = Field(None, alias="webPreviewExternalUrl")
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

    # Next.js container fields
    nextjs_container_id: Optional[str] = Field(None, alias="nextjsContainerId")
    nextjs_status: NextjsStatusType = Field("stopped", alias="nextjsStatus")
    nextjs_created_at: Optional[datetime] = Field(None, alias="nextjsCreatedAt")
    nextjs_last_seen: Optional[datetime] = Field(None, alias="nextjsLastSeen")

    # Next.js URL/port fields
    nextjs_internal_url: Optional[str] = Field(None, alias="nextjsInternalUrl")
    nextjs_external_url: Optional[str] = Field(None, alias="nextjsExternalUrl")
    nextjs_internal_port: int = Field(3003, alias="nextjsInternalPort")
    nextjs_external_port: Optional[int] = Field(None, alias="nextjsExternalPort")

    # Next.js management API port
    nextjs_api_internal_port: int = Field(3013, alias="nextjsApiInternalPort")
    nextjs_api_external_port: Optional[int] = Field(None, alias="nextjsApiExternalPort")


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
    nextjs: WorkspaceComponentStatus = Field(default_factory=WorkspaceComponentStatus)


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
    port_mappings: list[WorkspacePortMapping] = Field(
        default_factory=list, alias="portMappings"
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
    port_mappings: list[WorkspacePortMapping] = Field(
        default_factory=list, alias="portMappings"
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
    port_mappings: Optional[list[WorkspacePortMapping]] = Field(
        None, alias="portMappings"
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
