"""Claude Code Hooks 模組資料模型"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class HookActionType(str, Enum):
    """Hook 動作型別"""

    COMMAND = "command"
    WEBHOOK = "webhook"
    MCP_CALL = "mcp_call"


class HookAction(BaseModel):
    """Hook 動作定義"""

    type: HookActionType = Field(..., description="動作型別")
    command: str | None = Field(None, description="命令或指令")
    timeout: int | None = Field(None, description="逾時秒數")


class HookRule(BaseModel):
    """Hook 規則"""

    matcher: str = Field(..., description="事件匹配器")
    hooks: List[HookAction] = Field(default_factory=list, description="動作清單")

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


class HookScopeDocument(BaseModel):
    """單一範圍的 Hook 設定"""

    scope: DocumentScope = Field(..., description="Hook 範圍")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="事件映射")

    # 新增：Plugin 來源映射表（僅 scope='plugin' 時有值）
    plugin_sources: Dict[str, str] | None = Field(
        None,
        alias="pluginSources",
        description="Plugin 來源映射表 {event_name:index -> plugin_id}"
    )

    model_config = {"populate_by_name": True}


class HookScopesResponse(BaseModel):
    """列出所有範圍的 Hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[HookScopeDocument] = Field(default_factory=list, description="範圍清單")

    model_config = {"populate_by_name": True}


class HookScopeResponse(BaseModel):
    """取得單一範圍 Hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Hook 範圍")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="事件映射")

    model_config = {"populate_by_name": True}


class HookScopeUpsertRequest(BaseModel):
    """更新 Hook 設定請求"""

    hooks: Dict[str, List[HookRule]] = Field(..., description="完整 Hook 設定")

    model_config = {"populate_by_name": True}


class HookDeleteResponse(BaseModel):
    """刪除 Hook 回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Hook 範圍")
    deleted: bool = Field(True, description="刪除狀態")
    deleted_at: datetime = Field(..., alias="deletedAt", description="刪除時間")

    model_config = {"populate_by_name": True}


class HookExportResponse(BaseModel):
    """匯出 Hook 結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    exported_at: datetime = Field(..., alias="exportedAt", description="匯出時間")
    scopes: List[HookScopeDocument] = Field(default_factory=list, description="匯出範圍")

    model_config = {"populate_by_name": True}


class HookImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


class HookImportRequest(BaseModel):
    """匯入 Hook 請求"""

    mode: HookImportMode = Field(..., description="匯入模式")
    scopes: List[HookScopeDocument] = Field(..., description="匯入資料")


class HookImportResponse(BaseModel):
    """匯入結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    mode: HookImportMode = Field(..., description="匯入模式")
    imported: int = Field(..., description="新建立數量")
    updated: int = Field(..., description="更新數量")
    skipped: int = Field(..., description="略過數量")

    model_config = {"populate_by_name": True}
