"""
Client Browser Relay 資料模型

定義 CDP Relay Server 所需的資料結構
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Target 相關模型
# ============================================================================


class TargetInfo(BaseModel):
    """CDP Target 資訊"""

    target_id: str = Field(..., alias="targetId")
    type: str = "page"
    title: str = ""
    url: str = ""
    attached: bool = False
    browser_context_id: str = Field("default", alias="browserContextId")

    class Config:
        populate_by_name = True


@dataclass
class ConnectedTarget:
    """已連接的 Target"""

    session_id: str
    target_id: str
    target_info: TargetInfo


@dataclass
class PlaywrightClient:
    """Playwright 客戶端連接"""

    id: str
    known_targets: set[str] = field(default_factory=set)


# ============================================================================
# API 回應模型
# ============================================================================


class RelayStatusResponse(BaseModel):
    """Relay Server 狀態回應"""

    ws_endpoint: str = Field(..., alias="wsEndpoint")
    extension_connected: bool = Field(..., alias="extensionConnected")
    mode: str = "extension"
    connected_targets_count: int = Field(0, alias="connectedTargetsCount")
    playwright_clients_count: int = Field(0, alias="playwrightClientsCount")

    class Config:
        populate_by_name = True


class NamedPagesResponse(BaseModel):
    """命名頁面列表回應"""

    pages: list[str] = Field(default_factory=list)


class CreatePageRequest(BaseModel):
    """建立頁面請求"""

    name: str


class CreatePageResponse(BaseModel):
    """建立頁面回應"""

    ws_endpoint: str = Field(..., alias="wsEndpoint")
    name: str
    target_id: str = Field(..., alias="targetId")
    url: str

    class Config:
        populate_by_name = True


class DeletePageResponse(BaseModel):
    """刪除頁面回應"""

    success: bool
