"""MCP 模組資料模型"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..common import DocumentScope


class McpTransportType(str, Enum):
    """MCP 伺服器支援的傳輸協定"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"




class McpServerConfig(BaseModel):
    """MCP 伺服器的基本設定"""

    type: McpTransportType = Field(
        default=McpTransportType.STDIO,
        description="伺服器傳輸型態",
    )
    command: str | None = Field(None, description="啟動命令")
    url: str | None = Field(None, description="遠端伺服器 URL")
    args: List[str] | None = Field(None, description="命令參數")
    env: Dict[str, str] | None = Field(None, description="環境變數")
    headers: Dict[str, str] | None = Field(None, description="HTTP 標頭")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode='after')
    def validate_transport_requirements(self):
        """驗證不同 transport 類型的必要欄位"""
        if self.type in [McpTransportType.HTTP, McpTransportType.SSE]:
            if not self.url:
                raise ValueError(f"URL is required for transport type '{self.type}'")
        elif self.type == McpTransportType.STDIO:
            if not self.command:
                raise ValueError("Command is required for stdio transport type")
        return self


class McpServerRuntime(McpServerConfig):
    """回應使用的 MCP 伺服器資訊，與 McpServerConfig 相同"""
    enabled: bool = Field(default=True, description="是否啟用此伺服器")

    # 新增：Plugin 來源資訊（當 scope='plugin' 時有值）
    plugin_name: str | None = Field(
        None,
        alias="pluginName",
        description="Plugin 名稱（僅 scope='plugin' 時有值）"
    )
    marketplace_name: str | None = Field(
        None,
        alias="marketplaceName",
        description="Marketplace 名稱（僅 scope='plugin' 時有值）"
    )


class McpScopeServers(BaseModel):
    """單一 scope 的 MCP 伺服器列表"""

    scope: DocumentScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, McpServerRuntime] = Field(
        default_factory=dict, description="伺服器設定"
    )


class McpServerCollectionResponse(BaseModel):
    """列出全部 MCP 伺服器的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scopes: List[McpScopeServers] = Field(default_factory=list, description="範圍清單")


class McpScopeResponse(BaseModel):
    """單一範圍或伺服器的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, McpServerRuntime] = Field(
        default_factory=dict, description="伺服器設定"
    )


class McpServerCreateRequest(BaseModel):
    """建立 MCP 伺服器的請求"""

    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="要建立的伺服器集合"
    )


class McpServerUpdateRequest(BaseModel):
    """更新 MCP 伺服器的請求"""

    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="更新後的伺服器設定"
    )


class McpServerDeleteResponse(BaseModel):
    """刪除 MCP 伺服器的結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="設定範圍")

    model_config = ConfigDict(populate_by_name=True)


class McpImportRequest(BaseModel):
    """匯入 MCP 設定的請求"""

    scope: DocumentScope = Field(..., description="匯入目標範圍")
    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="要匯入的伺服器設定"
    )
    overwrite: bool = Field(
        False, description="若存在相同名稱時是否覆寫既有設定"
    )


class McpImportUploadRequest(BaseModel):
    """上傳檔案匯入 MCP 設定的請求"""

    scope: DocumentScope = Field(..., description="匯入目標範圍")
    file: bytes = Field(..., description="上傳的 JSON 檔案內容")
    overwrite: bool = Field(
        False, description="若存在相同名稱時是否覆寫既有設定"
    )


class McpImportResponse(BaseModel):
    """匯入 MCP 設定的結果"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="設定範圍")
    created: List[str] = Field(default_factory=list, description="新增的伺服器")
    updated: List[str] = Field(default_factory=list, description="更新的伺服器")
    skipped: List[str] = Field(default_factory=list, description="因重複而跳過的伺服器")


class McpServerExportResponse(BaseModel):
    """匯出 MCP 設定的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, McpServerConfig] = Field(
        default_factory=dict, description="伺服器設定"
    )


