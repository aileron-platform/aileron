"""Canvas module data models"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CanvasType = Literal["html", "nextjs", "default"]
CanvasManifestStatus = Literal["missing", "valid", "invalid"]


class CanvasRoute(BaseModel):
    """Canvas route information"""

    path: str = Field(..., description="Route path")
    file: str | None = Field(default=None, description="Corresponding file for HTML renderer")

    model_config = {"populate_by_name": True}


class CanvasDetectResponse(BaseModel):
    """Canvas detection result"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType
    manifest_status: CanvasManifestStatus = Field(..., alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    error: str | None = None
    detected_at: datetime = Field(..., alias="detectedAt")

    model_config = {"populate_by_name": True}


class CanvasRoutesResponse(BaseModel):
    """Canvas route list response"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType = "default"
    manifest_status: CanvasManifestStatus = Field("missing", alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    total: int = Field(..., description="Total route count")
    scanned_at: datetime = Field(..., alias="scannedAt", description="Scan time")

    model_config = {"populate_by_name": True}


class CanvasHealthResponse(BaseModel):
    """Canvas health status"""

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
    """Canvas action response"""

    workspace_id: str = Field(..., alias="workspaceId")
    status: str
    type: CanvasType | None = None
    manifest_status: CanvasManifestStatus | None = Field(default=None, alias="manifestStatus")
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CanvasLogsResponse(BaseModel):
    """Canvas log response"""

    workspace_id: str = Field(..., alias="workspaceId")
    logs: list[str] = Field(default_factory=list)
    renderer_logs: list[str] = Field(default_factory=list, alias="rendererLogs")
    total: int = 0

    model_config = {"populate_by_name": True}
