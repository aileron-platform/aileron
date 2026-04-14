"""CLI Hooks 模組資料模型

重用 Claude Code Hooks 的基礎模型（HookActionType, HookAction, HookRule），
並定義 CLI 專用的回應模型。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field

from ...claude_code.hooks.models import HookAction, HookActionType, HookRule

# Re-export base models
__all__ = [
    "HookActionType",
    "HookAction",
    "HookRule",
    "CliHookScope",
    "CliHookScopeDocument",
    "CliHookScopesResponse",
    "CliHookScopeResponse",
    "CliHookScopeUpsertRequest",
    "CliHookDeleteResponse",
    "CliHookExportResponse",
    "CliHookImportMode",
    "CliHookImportRequest",
    "CliHookImportResponse",
]


class CliHookScope(str, Enum):
    """CLI Hooks 支援的設定範圍"""

    PROJECT = "project"
    USER = "user"


class CliHookScopeDocument(BaseModel):
    """單一範圍的 Hook 設定"""

    scope: CliHookScope = Field(..., description="Hook 範圍")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="事件映射")

    model_config = {"populate_by_name": True}


class CliHookScopesResponse(BaseModel):
    """列出所有範圍的 Hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[CliHookScopeDocument] = Field(default_factory=list, description="範圍清單")

    model_config = {"populate_by_name": True}


class CliHookScopeResponse(BaseModel):
    """取得單一範圍 Hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: CliHookScope = Field(..., description="Hook 範圍")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="事件映射")

    model_config = {"populate_by_name": True}


class CliHookScopeUpsertRequest(BaseModel):
    """更新 Hook 設定請求"""

    hooks: Dict[str, List[HookRule]] = Field(..., description="完整 Hook 設定")

    model_config = {"populate_by_name": True}


class CliHookDeleteResponse(BaseModel):
    """刪除 Hook 回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: CliHookScope = Field(..., description="Hook 範圍")
    deleted: bool = Field(True, description="刪除狀態")
    deleted_at: datetime = Field(..., alias="deletedAt", description="刪除時間")

    model_config = {"populate_by_name": True}


class CliHookExportResponse(BaseModel):
    """匯出 Hook 結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    exported_at: datetime = Field(..., alias="exportedAt", description="匯出時間")
    scopes: List[CliHookScopeDocument] = Field(default_factory=list, description="匯出範圍")

    model_config = {"populate_by_name": True}


class CliHookImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


class CliHookImportRequest(BaseModel):
    """匯入 Hook 請求"""

    mode: CliHookImportMode = Field(..., description="匯入模式")
    scopes: List[CliHookScopeDocument] = Field(..., description="匯入資料")


class CliHookImportResponse(BaseModel):
    """匯入結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    mode: CliHookImportMode = Field(..., description="匯入模式")
    imported: int = Field(..., description="新建立數量")
    updated: int = Field(..., description="更新數量")
    skipped: int = Field(..., description="略過數量")

    model_config = {"populate_by_name": True}
