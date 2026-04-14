"""預覽模組資料模型"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NextJsRoute(BaseModel):
    """Next.js 路由資訊"""
    path: str = Field(..., description="路由路徑，例如: /, /about, /contact")

    model_config = {
        "populate_by_name": True,
    }


class NextJsRoutesResponse(BaseModel):
    """Next.js 路由列表回應"""
    workspace_id: str = Field(..., alias="workspaceId")
    routes: list[NextJsRoute] = Field(default_factory=list)
    total: int = Field(..., description="總路由數量")
    scanned_at: datetime = Field(..., alias="scannedAt", description="掃描時間")

    model_config = {
        "populate_by_name": True,
    }


class PreviewSyncRequest(BaseModel):
    """預覽同步請求"""
    force: bool = Field(default=False, description="是否強制覆蓋")

    model_config = {
        "populate_by_name": True,
    }


class PreviewSyncResponse(BaseModel):
    """預覽同步回應"""
    workspace_id: str = Field(..., alias="workspaceId")
    operation_id: str = Field(..., alias="operationId", description="操作 ID")
    status: str = Field(..., description="狀態: pending, running, completed, failed")
    message: str = Field(..., description="狀態訊息")
    started_at: datetime = Field(..., alias="startedAt", description="開始時間")

    model_config = {
        "populate_by_name": True,
    }


class PreviewSyncStatusResponse(BaseModel):
    """預覽同步狀態回應"""
    workspace_id: str = Field(..., alias="workspaceId")
    operation_id: str = Field(..., alias="operationId")
    status: str = Field(..., description="狀態: pending, running, completed, failed")
    progress: float = Field(default=0.0, description="進度 0.0-1.0", ge=0.0, le=1.0)
    message: str = Field(..., description="狀態訊息")
    started_at: datetime = Field(..., alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    error: str | None = Field(default=None, description="錯誤訊息")

    model_config = {
        "populate_by_name": True,
    }
