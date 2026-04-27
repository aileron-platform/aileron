"""Template Install Internal API data models"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============ Request Models ============


class SlashCommandInstallItem(BaseModel):
    """Slash Command install item"""

    fileName: str = Field(..., alias="fileName", description="File name (including .md)")
    content: str = Field(..., description="Markdown content")

    model_config = {"populate_by_name": True}


class SlashCommandInstallRequest(BaseModel):
    """Slash Commands install request"""

    commands: List[SlashCommandInstallItem] = Field(..., description="Command list")


class SubagentInstallItem(BaseModel):
    """Subagent install item"""

    fileName: str = Field(..., alias="fileName", description="File name (including .md)")
    content: str = Field(..., description="Markdown content")

    model_config = {"populate_by_name": True}


class SubagentInstallRequest(BaseModel):
    """Subagents install request"""

    subagents: List[SubagentInstallItem] = Field(..., description="Subagent list")


class OutputStyleInstallItem(BaseModel):
    """Output Style install item"""

    fileName: str = Field(..., alias="fileName", description="File name (including .md)")
    content: str = Field(..., description="Markdown content")

    model_config = {"populate_by_name": True}


class OutputStyleInstallRequest(BaseModel):
    """Output Styles install request"""

    outputStyles: List[OutputStyleInstallItem] = Field(..., alias="outputStyles", description="Output Style list")

    model_config = {"populate_by_name": True}


class ClaudeMdInstallRequest(BaseModel):
    """Claude.md install request"""

    content: str = Field(..., description="Claude.md content")


class McpServerConfigInstall(BaseModel):
    """MCP Server configuration (for installation)"""

    type: str = Field(default="stdio", description="Transport type")
    command: Optional[str] = Field(None, description="Startup command (stdio)")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    url: Optional[str] = Field(None, description="Service URL (http/sse)")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")


class McpInstallRequest(BaseModel):
    """MCP Servers install request"""

    mcpServers: Dict[str, McpServerConfigInstall] = Field(
        ..., alias="mcpServers", description="MCP server configuration"
    )

    model_config = {"populate_by_name": True}


class HookActionInstall(BaseModel):
    """Hook action (for installation)"""

    type: str = Field(..., description="Action type")
    command: Optional[str] = Field(None, description="Command")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")


class HookRuleInstall(BaseModel):
    """Hook rule (for installation)"""

    matcher: str = Field(..., description="Matcher")
    hooks: List[HookActionInstall] = Field(..., description="Action list")


class HooksInstallRequest(BaseModel):
    """Hooks install request"""

    hooks: Dict[str, List[HookRuleInstall]] = Field(
        ..., description="Hooks configuration (event -> rule list)"
    )


class ScriptFileItem(BaseModel):
    """Script file item"""

    path: str = Field(..., description="Relative path")
    content: str = Field(..., description="File content")
    executable: bool = Field(default=False, description="Executable")


class ScriptsInstallRequest(BaseModel):
    """Scripts install request"""

    templateName: str = Field(..., alias="templateName", description="Template name")
    scripts: List[ScriptFileItem] = Field(..., description="Script file list")

    model_config = {"populate_by_name": True}


class SkillFileItem(BaseModel):
    """Skill file item"""

    path: str = Field(..., description="Relative path")
    content: str = Field(..., description="File content")


class SkillsInstallRequest(BaseModel):
    """Skills install request"""

    cliType: str = Field(..., alias="cliType", description="CLI type")
    skills: List[SkillFileItem] = Field(..., description="Skill file list")

    model_config = {"populate_by_name": True}


class CompiledTemplateFileInstallItem(BaseModel):
    """Compiled template file item."""

    path: str = Field(..., description="Target relative path")
    source: str = Field(..., description="Canonical source path")
    content: str = Field(..., description="Compiled content")


class CompileIssueInstallItem(BaseModel):
    """Compile issue item."""

    feature: str = Field(..., description="Feature name")
    target: str = Field(..., description="Target CLI")
    message: str = Field(..., description="Issue message")


class InstallPlanRequest(BaseModel):
    """Compiled install plan request payload."""

    target: str = Field(..., description="Target CLI")
    files: List[CompiledTemplateFileInstallItem] = Field(default_factory=list, description="Files to install")
    warnings: List[CompileIssueInstallItem] = Field(default_factory=list, description="Compile warnings")
    unsupported: List[CompileIssueInstallItem] = Field(default_factory=list, description="Unsupported features")
    degradation_notes: List[CompileIssueInstallItem] = Field(
        default_factory=list,
        alias="degradationNotes",
        description="Feature degradation notes",
    )
    install_hints: Dict[str, Any] = Field(
        default_factory=dict,
        alias="installHints",
        description="Runtime install hints",
    )
    source_hash: Optional[str] = Field(default=None, alias="sourceHash", description="Canonical source hash")
    cache_key: Optional[str] = Field(default=None, alias="cacheKey", description="Compile cache key")

    model_config = {"populate_by_name": True}


class TemplateInstallRequest(BaseModel):
    """Template batch install request"""

    templateId: str = Field(..., alias="templateId", description="Template ID")
    templateName: str = Field(..., alias="templateName", description="Template name")
    cliType: Optional[str] = Field(None, alias="cliType", description="CLI type")
    initCommands: Optional[str] = Field(
        None, alias="initCommands", description="Initialization commands"
    )
    installPlan: Optional[InstallPlanRequest] = Field(
        None, alias="installPlan", description="Compiled install plan"
    )
    claudeMd: Optional[ClaudeMdInstallRequest] = Field(
        None, alias="claudeMd", description="Claude.md configuration"
    )
    slashCommands: Optional[List[SlashCommandInstallItem]] = Field(
        None, alias="slashCommands", description="Slash Commands"
    )
    subagents: Optional[List[SubagentInstallItem]] = Field(
        None, description="Subagents"
    )
    outputStyles: Optional[List[OutputStyleInstallItem]] = Field(
        None, alias="outputStyles", description="Output Styles"
    )
    mcpServers: Optional[Dict[str, McpServerConfigInstall]] = Field(
        None, alias="mcpServers", description="MCP Servers"
    )
    hooks: Optional[Dict[str, List[HookRuleInstall]]] = Field(
        None, description="Hooks"
    )
    scripts: Optional[List[ScriptFileItem]] = Field(None, description="Scripts")
    skills: Optional[List[SkillFileItem]] = Field(None, description="Skills")

    model_config = {"populate_by_name": True}


# ============ Response Models ============


class InstallResults(BaseModel):
    """Installation result statistics"""

    created: List[str] = Field(default_factory=list, description="Created files")
    updated: List[str] = Field(default_factory=list, description="Updated files")
    failed: List[str] = Field(default_factory=list, description="Failed files")


class SlashCommandInstallResponse(BaseModel):
    """Slash Commands install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="Installation results")

    model_config = {"populate_by_name": True}


class SubagentInstallResponse(BaseModel):
    """Subagents install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="Installation results")

    model_config = {"populate_by_name": True}


class OutputStyleInstallResponse(BaseModel):
    """Output Styles install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="Installation results")

    model_config = {"populate_by_name": True}


class ClaudeMdInstallResponse(BaseModel):
    """Claude.md install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class McpInstallResponse(BaseModel):
    """MCP Servers install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="Installation results")

    model_config = {"populate_by_name": True}


class HooksInstallResponse(BaseModel):
    """Hooks install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class ScriptsInstallResponse(BaseModel):
    """Scripts install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    templateName: str = Field(..., alias="templateName", description="Template name")
    targetPath: str = Field(..., alias="targetPath", description="Target path")
    results: InstallResults = Field(..., description="Installation results")
    totalFiles: int = Field(..., alias="totalFiles", description="Total file count")
    totalSize: int = Field(..., alias="totalSize", description="Total size (bytes)")

    model_config = {"populate_by_name": True}


class SkillsInstallResponse(BaseModel):
    """Skills install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    cliType: str = Field(..., alias="cliType", description="CLI type")
    targetPath: str = Field(..., alias="targetPath", description="Target path")
    results: InstallResults = Field(..., description="Installation results")
    totalFiles: int = Field(..., alias="totalFiles", description="Total file count")
    totalSize: int = Field(..., alias="totalSize", description="Total size (bytes)")

    model_config = {"populate_by_name": True}


class TemplateInstallItemResult(BaseModel):
    """Single item installation result"""

    success: bool = Field(..., description="Success")
    created: int = Field(default=0, description="Created count")
    updated: int = Field(default=0, description="Updated count")
    failed: int = Field(default=0, description="Failed count")
    error: Optional[str] = Field(None, description="Error message")


class TemplateInstallResults(BaseModel):
    """Template installation results"""

    claudeMd: Optional[TemplateInstallItemResult] = Field(None, alias="claudeMd")
    slashCommands: Optional[TemplateInstallItemResult] = Field(
        None, alias="slashCommands"
    )
    subagents: Optional[TemplateInstallItemResult] = Field(None)
    outputStyles: Optional[TemplateInstallItemResult] = Field(None, alias="outputStyles")
    mcp: Optional[TemplateInstallItemResult] = Field(None)
    hooks: Optional[TemplateInstallItemResult] = Field(None)
    scripts: Optional[TemplateInstallItemResult] = Field(None)
    skills: Optional[TemplateInstallItemResult] = Field(None)

    model_config = {"populate_by_name": True}


class TemplateInstallResponse(BaseModel):
    """Template batch install response"""

    success: bool = Field(..., description="Success")
    message: str = Field(..., description="Message")
    templateId: str = Field(..., alias="templateId", description="Template ID")
    templateName: str = Field(..., alias="templateName", description="Template name")
    results: TemplateInstallResults = Field(..., description="Installation results")

    model_config = {"populate_by_name": True}


__all__ = [
    # Request Models
    "SlashCommandInstallItem",
    "SlashCommandInstallRequest",
    "SubagentInstallItem",
    "SubagentInstallRequest",
    "OutputStyleInstallItem",
    "OutputStyleInstallRequest",
    "ClaudeMdInstallRequest",
    "McpServerConfigInstall",
    "McpInstallRequest",
    "HookActionInstall",
    "HookRuleInstall",
    "HooksInstallRequest",
    "ScriptFileItem",
    "ScriptsInstallRequest",
    "SkillFileItem",
    "SkillsInstallRequest",
    "CompiledTemplateFileInstallItem",
    "CompileIssueInstallItem",
    "InstallPlanRequest",
    "TemplateInstallRequest",
    # Response Models
    "InstallResults",
    "SlashCommandInstallResponse",
    "SubagentInstallResponse",
    "OutputStyleInstallResponse",
    "ClaudeMdInstallResponse",
    "McpInstallResponse",
    "HooksInstallResponse",
    "ScriptsInstallResponse",
    "SkillsInstallResponse",
    "TemplateInstallItemResult",
    "TemplateInstallResults",
    "TemplateInstallResponse",
]
