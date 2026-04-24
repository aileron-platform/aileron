"""Template Install Internal API 資料模型"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============ Request Models ============


class SlashCommandInstallItem(BaseModel):
    """Slash Command 安裝項目"""

    fileName: str = Field(..., alias="fileName", description="檔案名稱（含 .md）")
    content: str = Field(..., description="Markdown 內容")

    model_config = {"populate_by_name": True}


class SlashCommandInstallRequest(BaseModel):
    """Slash Commands 安裝請求"""

    commands: List[SlashCommandInstallItem] = Field(..., description="命令列表")


class SubagentInstallItem(BaseModel):
    """Subagent 安裝項目"""

    fileName: str = Field(..., alias="fileName", description="檔案名稱（含 .md）")
    content: str = Field(..., description="Markdown 內容")

    model_config = {"populate_by_name": True}


class SubagentInstallRequest(BaseModel):
    """Subagents 安裝請求"""

    subagents: List[SubagentInstallItem] = Field(..., description="Subagent 列表")


class OutputStyleInstallItem(BaseModel):
    """Output Style 安裝項目"""

    fileName: str = Field(..., alias="fileName", description="檔案名稱（含 .md）")
    content: str = Field(..., description="Markdown 內容")

    model_config = {"populate_by_name": True}


class OutputStyleInstallRequest(BaseModel):
    """Output Styles 安裝請求"""

    outputStyles: List[OutputStyleInstallItem] = Field(..., alias="outputStyles", description="Output Style 列表")

    model_config = {"populate_by_name": True}


class ClaudeMdInstallRequest(BaseModel):
    """Claude.md 安裝請求"""

    content: str = Field(..., description="Claude.md 內容")


class McpServerConfigInstall(BaseModel):
    """MCP Server 配置（用於安裝）"""

    type: str = Field(default="stdio", description="傳輸類型")
    command: Optional[str] = Field(None, description="啟動命令（stdio）")
    args: Optional[List[str]] = Field(None, description="命令參數")
    env: Optional[Dict[str, str]] = Field(None, description="環境變數")
    url: Optional[str] = Field(None, description="服務 URL（http/sse）")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP 標頭")


class McpInstallRequest(BaseModel):
    """MCP Servers 安裝請求"""

    mcpServers: Dict[str, McpServerConfigInstall] = Field(
        ..., alias="mcpServers", description="MCP 伺服器配置"
    )

    model_config = {"populate_by_name": True}


class HookActionInstall(BaseModel):
    """Hook 動作（用於安裝）"""

    type: str = Field(..., description="動作類型")
    command: Optional[str] = Field(None, description="命令")
    timeout: Optional[int] = Field(None, description="逾時秒數")


class HookRuleInstall(BaseModel):
    """Hook 規則（用於安裝）"""

    matcher: str = Field(..., description="匹配器")
    hooks: List[HookActionInstall] = Field(..., description="動作列表")


class HooksInstallRequest(BaseModel):
    """Hooks 安裝請求"""

    hooks: Dict[str, List[HookRuleInstall]] = Field(
        ..., description="Hooks 配置（事件 -> 規則列表）"
    )


class ScriptFileItem(BaseModel):
    """Script 檔案項目"""

    path: str = Field(..., description="相對路徑")
    content: str = Field(..., description="檔案內容")
    executable: bool = Field(default=False, description="是否可執行")


class ScriptsInstallRequest(BaseModel):
    """Scripts 安裝請求"""

    templateName: str = Field(..., alias="templateName", description="模板名稱")
    scripts: List[ScriptFileItem] = Field(..., description="腳本檔案列表")

    model_config = {"populate_by_name": True}


class SkillFileItem(BaseModel):
    """Skill 檔案項目"""

    path: str = Field(..., description="相對路徑")
    content: str = Field(..., description="檔案內容")


class SkillsInstallRequest(BaseModel):
    """Skills 安裝請求"""

    cliType: str = Field(..., alias="cliType", description="CLI 類型")
    skills: List[SkillFileItem] = Field(..., description="技能檔案列表")

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
    """模板批次安裝請求"""

    templateId: str = Field(..., alias="templateId", description="模板 ID")
    templateName: str = Field(..., alias="templateName", description="模板名稱")
    cliType: Optional[str] = Field(None, alias="cliType", description="CLI 類型")
    initCommands: Optional[str] = Field(
        None, alias="initCommands", description="初始化指令"
    )
    installPlan: Optional[InstallPlanRequest] = Field(
        None, alias="installPlan", description="Compiled install plan"
    )
    claudeMd: Optional[ClaudeMdInstallRequest] = Field(
        None, alias="claudeMd", description="Claude.md 配置"
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
    """安裝結果統計"""

    created: List[str] = Field(default_factory=list, description="新建檔案")
    updated: List[str] = Field(default_factory=list, description="更新檔案")
    failed: List[str] = Field(default_factory=list, description="失敗檔案")


class SlashCommandInstallResponse(BaseModel):
    """Slash Commands 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="安裝結果")

    model_config = {"populate_by_name": True}


class SubagentInstallResponse(BaseModel):
    """Subagents 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="安裝結果")

    model_config = {"populate_by_name": True}


class OutputStyleInstallResponse(BaseModel):
    """Output Styles 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="安裝結果")

    model_config = {"populate_by_name": True}


class ClaudeMdInstallResponse(BaseModel):
    """Claude.md 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class McpInstallResponse(BaseModel):
    """MCP Servers 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: InstallResults = Field(..., description="安裝結果")

    model_config = {"populate_by_name": True}


class HooksInstallResponse(BaseModel):
    """Hooks 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class ScriptsInstallResponse(BaseModel):
    """Scripts 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    templateName: str = Field(..., alias="templateName", description="模板名稱")
    targetPath: str = Field(..., alias="targetPath", description="目標路徑")
    results: InstallResults = Field(..., description="安裝結果")
    totalFiles: int = Field(..., alias="totalFiles", description="總檔案數")
    totalSize: int = Field(..., alias="totalSize", description="總大小（bytes）")

    model_config = {"populate_by_name": True}


class SkillsInstallResponse(BaseModel):
    """Skills 安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    cliType: str = Field(..., alias="cliType", description="CLI 類型")
    targetPath: str = Field(..., alias="targetPath", description="目標路徑")
    results: InstallResults = Field(..., description="安裝結果")
    totalFiles: int = Field(..., alias="totalFiles", description="總檔案數")
    totalSize: int = Field(..., alias="totalSize", description="總大小（bytes）")

    model_config = {"populate_by_name": True}


class TemplateInstallItemResult(BaseModel):
    """單項安裝結果"""

    success: bool = Field(..., description="是否成功")
    created: int = Field(default=0, description="新建數量")
    updated: int = Field(default=0, description="更新數量")
    failed: int = Field(default=0, description="失敗數量")
    error: Optional[str] = Field(None, description="錯誤訊息")


class TemplateInstallResults(BaseModel):
    """模板安裝結果"""

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
    """模板批次安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    templateId: str = Field(..., alias="templateId", description="模板 ID")
    templateName: str = Field(..., alias="templateName", description="模板名稱")
    results: TemplateInstallResults = Field(..., description="各項安裝結果")

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
