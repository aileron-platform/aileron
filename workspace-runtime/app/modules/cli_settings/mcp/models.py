"""CLI MCP 模組資料模型

對齊 Claude Code MCP API 回應格式，確保前端不需修改。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class CliMcpScope(str, Enum):
    """CLI 工具支援的 MCP 設定範圍"""

    PROJECT = "project"
    USER = "user"


class CliMcpTransportType(str, Enum):
    """MCP 伺服器支援的傳輸協定"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class CliMcpServerConfig(BaseModel):
    """MCP 伺服器的基本設定（extra=allow 保留各工具原生欄位）"""

    type: CliMcpTransportType = Field(
        default=CliMcpTransportType.STDIO,
        description="伺服器傳輸型態",
    )
    command: str | None = Field(None, description="啟動命令")
    url: str | None = Field(None, description="遠端伺服器 URL")
    args: List[str] | None = Field(None, description="命令參數")
    env: Dict[str, str] | None = Field(None, description="環境變數")
    headers: Dict[str, str] | None = Field(None, description="HTTP 標頭")

    model_config = ConfigDict(extra="allow")


class CliMcpServerRuntime(CliMcpServerConfig):
    """回應使用的 MCP 伺服器資訊，包含 enabled 狀態"""

    enabled: bool = Field(default=True, description="是否啟用此伺服器")


class CliMcpScopeServers(BaseModel):
    """單一 scope 的 MCP 伺服器列表"""

    scope: CliMcpScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, CliMcpServerRuntime] = Field(
        default_factory=dict, description="伺服器設定"
    )


class CliMcpServerCollectionResponse(BaseModel):
    """列出全部 MCP 伺服器的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scopes: List[CliMcpScopeServers] = Field(
        default_factory=list, description="範圍清單"
    )


class CliMcpScopeResponse(BaseModel):
    """單一範圍或伺服器的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, CliMcpServerRuntime] = Field(
        default_factory=dict, description="伺服器設定"
    )


class CliMcpServerCreateRequest(BaseModel):
    """建立 MCP 伺服器的請求"""

    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="要建立的伺服器集合"
    )


class CliMcpServerUpdateRequest(BaseModel):
    """更新 MCP 伺服器的請求"""

    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="更新後的伺服器設定"
    )


class CliMcpServerDeleteResponse(BaseModel):
    """刪除 MCP 伺服器的結果"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="設定範圍")


class CliMcpImportRequest(BaseModel):
    """匯入 MCP 設定的請求"""

    scope: CliMcpScope = Field(..., description="匯入目標範圍")
    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="要匯入的伺服器設定"
    )
    overwrite: bool = Field(
        False, description="若存在相同名稱時是否覆寫既有設定"
    )


class CliMcpImportUploadRequest(BaseModel):
    """上傳檔案匯入 MCP 設定的請求"""

    scope: CliMcpScope = Field(..., description="匯入目標範圍")
    file: bytes = Field(..., description="上傳的 JSON 檔案內容")
    overwrite: bool = Field(
        False, description="若存在相同名稱時是否覆寫既有設定"
    )


class CliMcpImportResponse(BaseModel):
    """匯入 MCP 設定的結果"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="設定範圍")
    created: List[str] = Field(default_factory=list, description="新增的伺服器")
    updated: List[str] = Field(default_factory=list, description="更新的伺服器")
    skipped: List[str] = Field(
        default_factory=list, description="因重複而跳過的伺服器"
    )


class CliMcpServerExportResponse(BaseModel):
    """匯出 MCP 設定的回應"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="設定範圍")
    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        default_factory=dict, description="伺服器設定"
    )
