"""Canvas 模組資料模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CanvasType = Literal["html", "nextjs", "default"]
CanvasManifestStatus = Literal["missing", "valid", "invalid"]


class CanvasRoute(BaseModel):
    """Canvas 路由資訊"""

    path: str = Field(..., description="路由路徑")
    file: str | None = Field(default=None, description="HTML renderer 對應檔案")

    model_config = {"populate_by_name": True}


class CanvasDetectResponse(BaseModel):
    """Canvas 偵測結果"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType
    manifest_status: CanvasManifestStatus = Field(..., alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    error: str | None = None
    detected_at: datetime = Field(..., alias="detectedAt")

    model_config = {"populate_by_name": True}


class CanvasRoutesResponse(BaseModel):
    """Canvas 路由列表回應"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType = "default"
    manifest_status: CanvasManifestStatus = Field("missing", alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    total: int = Field(..., description="總路由數量")
    scanned_at: datetime = Field(..., alias="scannedAt", description="掃描時間")

    model_config = {"populate_by_name": True}


class CanvasHealthResponse(BaseModel):
    """Canvas 健康狀態"""

    workspace_id: str = Field(..., alias="workspaceId")
    status: str
    type: CanvasType | None = None
    manifest_status: CanvasManifestStatus | None = Field(default=None, alias="manifestStatus")
    renderer_running: bool = Field(False, alias="rendererRunning")
    port_available: bool = Field(False, alias="portAvailable")
    message: str = ""
    source: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CanvasActionResponse(BaseModel):
    """Canvas 操作回應"""

    workspace_id: str = Field(..., alias="workspaceId")
    status: str
    type: CanvasType | None = None
    manifest_status: CanvasManifestStatus | None = Field(default=None, alias="manifestStatus")
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CanvasLogsResponse(BaseModel):
    """Canvas 日誌回應"""

    workspace_id: str = Field(..., alias="workspaceId")
    logs: list[str] = Field(default_factory=list)
    renderer_logs: list[str] = Field(default_factory=list, alias="rendererLogs")
    total: int = 0

    model_config = {"populate_by_name": True}
