"""模板配置模型（MCP、Hooks、Commands 和 Agents）"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ MCP 模型 ============


class McpTransportType(str, Enum):
    """MCP 伺服器傳輸協定"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class McpServerConfig(BaseModel):
    """MCP 伺服器配置"""

    description: str = Field(description="MCP 伺服器描述")
    type: McpTransportType = Field(default=McpTransportType.STDIO, description="傳輸型態")
    command: Optional[str] = Field(default=None, description="執行命令（stdio）")
    args: Optional[List[str]] = Field(default=None, description="命令參數")
    env: Optional[Dict[str, str]] = Field(default=None, description="環境變數")
    url: Optional[str] = Field(default=None, description="伺服器 URL（http/sse）")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP 標頭")

    model_config = {"use_enum_values": True}


class McpConfigResponse(BaseModel):
    """MCP 配置回應"""

    template_id: str = Field(description="模板 ID", alias="templateId")
    mcp_servers: Dict[str, McpServerConfig] = Field(
        default_factory=dict, description="MCP 伺服器配置", alias="mcpServers"
    )

    model_config = {"populate_by_name": True}


class McpConfigUpdateRequest(BaseModel):
    """MCP 配置更新請求"""

    mcp_servers: Dict[str, McpServerConfig] = Field(
        description="MCP 伺服器配置", alias="mcpServers"
    )

    model_config = {"populate_by_name": True}


# ============ Hooks 模型 ============


class HookExecution(BaseModel):
    """Hook 執行配置"""

    type: str = Field(default="command", description="執行類型")
    command: str = Field(description="執行命令")
    timeout: int = Field(default=30, description="逾時秒數")


class HookRule(BaseModel):
    """Hook 規則"""

    matcher: str = Field(default="*", description="事件匹配器")
    hooks: List[HookExecution] = Field(default_factory=list, description="執行配置列表")


class HooksConfigResponse(BaseModel):
    """Hooks 配置回應"""

    template_id: str = Field(description="模板 ID", alias="templateId")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="事件映射")

    model_config = {"populate_by_name": True}


class HooksConfigUpdateRequest(BaseModel):
    """Hooks 配置更新請求"""

    hooks: Dict[str, List[HookRule]] = Field(description="事件映射")

    model_config = {"populate_by_name": True}


# ============ SlashCommands 模型 ============


class TemplateSlashCommandFile(BaseModel):
    """模板 SlashCommand 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateSlashCommandContent(BaseModel):
    """模板 SlashCommand 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateSlashCommandCreateRequest(BaseModel):
    """建立 SlashCommand 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateSlashCommandUpdateRequest(BaseModel):
    """更新 SlashCommand 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateSlashCommandResponse(BaseModel):
    """SlashCommand 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateSlashCommandContent] = Field(default=None, description="SlashCommand 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateSlashCommandListResponse(BaseModel):
    """SlashCommand 檔案列表回應"""

    success: bool = Field(description="操作是否成功")
    data: List[TemplateSlashCommandFile] = Field(default_factory=list, description="檔案列表")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


# ============ SubAgents 模型 ============


class TemplateSubAgentFile(BaseModel):
    """模板 SubAgent 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateSubAgentContent(BaseModel):
    """模板 SubAgent 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateSubAgentCreateRequest(BaseModel):
    """建立 SubAgent 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateSubAgentUpdateRequest(BaseModel):
    """更新 SubAgent 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateSubAgentResponse(BaseModel):
    """SubAgent 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateSubAgentContent] = Field(default=None, description="SubAgent 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateSubAgentListResponse(BaseModel):
    """SubAgent 檔案列表回應"""

    success: bool = Field(description="操作是否成功")
    data: List[TemplateSubAgentFile] = Field(default_factory=list, description="檔案列表")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


# ============ OutputStyles 模型 ============


class TemplateOutputStyleFile(BaseModel):
    """模板 OutputStyle 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateOutputStyleContent(BaseModel):
    """模板 OutputStyle 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateOutputStyleCreateRequest(BaseModel):
    """建立 OutputStyle 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleUpdateRequest(BaseModel):
    """更新 OutputStyle 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleResponse(BaseModel):
    """OutputStyle 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateOutputStyleContent] = Field(default=None, description="OutputStyle 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateOutputStyleListResponse(BaseModel):
    """OutputStyle 檔案列表回應"""

    success: bool = Field(description="操作是否成功")
    data: List[TemplateOutputStyleFile] = Field(default_factory=list, description="檔案列表")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


# ============ Marketplace 配置模型 ============


class MarketplaceOwner(BaseModel):
    """Marketplace 擁有者資訊"""

    name: str = Field(default="", description="擁有者名稱")
    email: str = Field(default="", description="擁有者 Email")


class MarketplaceMetadata(BaseModel):
    """Marketplace 元資料"""

    description: str = Field(default="", description="描述")
    version: str = Field(default="1.0.0", description="版本")
    homepage: str = Field(default="", description="首頁 URL")


class MarketplaceConfig(BaseModel):
    """Marketplace 配置"""

    name: str = Field(default="claude-code-marketplace", description="Marketplace 名稱")
    owner: MarketplaceOwner = Field(default_factory=MarketplaceOwner, description="擁有者資訊")
    metadata: MarketplaceMetadata = Field(default_factory=MarketplaceMetadata, description="元資料")


class MarketplaceConfigResponse(BaseModel):
    """Marketplace 配置回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[MarketplaceConfig] = Field(default=None, description="Marketplace 配置")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class MarketplaceConfigUpdateRequest(BaseModel):
    """Marketplace 配置更新請求"""

    name: str = Field(description="Marketplace 名稱")
    owner: MarketplaceOwner = Field(description="擁有者資訊")
    metadata: MarketplaceMetadata = Field(description="元資料")

