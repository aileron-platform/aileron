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


# ============ Commands 模型 ============


class TemplateCommandFile(BaseModel):
    """模板 Command 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateCommandContent(BaseModel):
    """模板 Command 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateCommandCreateRequest(BaseModel):
    """建立 Command 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateCommandUpdateRequest(BaseModel):
    """更新 Command 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateCommandResponse(BaseModel):
    """Command 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateCommandContent] = Field(default=None, description="Command 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateCommandListResponse(BaseModel):
    """Command 檔案列表回應"""

    success: bool = Field(description="操作是否成功")
    data: List[TemplateCommandFile] = Field(default_factory=list, description="檔案列表")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


# ============ Agents 模型 ============


class TemplateAgentFile(BaseModel):
    """模板 Agent 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateAgentContent(BaseModel):
    """模板 Agent 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateAgentCreateRequest(BaseModel):
    """建立 Agent 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateAgentUpdateRequest(BaseModel):
    """更新 Agent 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateAgentResponse(BaseModel):
    """Agent 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateAgentContent] = Field(default=None, description="Agent 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateAgentListResponse(BaseModel):
    """Agent 檔案列表回應"""

    success: bool = Field(description="操作是否成功")
    data: List[TemplateAgentFile] = Field(default_factory=list, description="檔案列表")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


# ============ Output Style 模型 ============


class TemplateOutputStyleFile(BaseModel):
    """模板 Output Style 檔案資訊"""

    file_name: str = Field(description="檔案名稱")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateOutputStyleContent(BaseModel):
    """模板 Output Style 檔案內容"""

    file_name: str = Field(description="檔案名稱")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小（位元組）")
    last_modified: datetime = Field(description="最後修改時間")


class TemplateOutputStyleCreateRequest(BaseModel):
    """建立 Output Style 檔案請求"""

    file_name: str = Field(alias="fileName", description="檔案名稱（必須以 .md 結尾）")
    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleUpdateRequest(BaseModel):
    """更新 Output Style 檔案請求"""

    content: str = Field(description="檔案內容")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleResponse(BaseModel):
    """Output Style 操作回應"""

    success: bool = Field(description="操作是否成功")
    data: Optional[TemplateOutputStyleContent] = Field(default=None, description="Output Style 檔案資料")
    message: Optional[str] = Field(default=None, description="操作訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")


class TemplateOutputStyleListResponse(BaseModel):
    """Output Style 檔案列表回應"""

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
