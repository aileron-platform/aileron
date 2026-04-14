"""Subagents 模組資料模型"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class SubagentSummary(BaseModel):
    """Subagent 檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    name: str | None = Field(None, description="Subagent 名稱")
    description: str | None = Field(None, description="Subagent 描述")
    scope: DocumentScope = Field(..., description="檔案範圍")
    size: str = Field(..., description="檔案大小")

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

    model_config = {"populate_by_name": True}


class SubagentDocument(SubagentSummary):
    """Subagent 詳細內容"""

    content: str = Field(..., description="Markdown 內容")


class SubagentScopeGroup(BaseModel):
    """同一範圍的 Subagent 檔案"""

    scope: DocumentScope = Field(..., description="檔案範圍")
    documents: List[SubagentSummary] = Field(
        default_factory=list, description="檔案列表"
    )


class SubagentCollectionResponse(BaseModel):
    """所有範圍的 Subagent 檔案"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[SubagentScopeGroup] = Field(
        default_factory=list, description="依範圍分類的 Subagent"
    )

    model_config = {"populate_by_name": True}


class SubagentScopeResponse(BaseModel):
    """單一範圍 Subagent 檔案"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    documents: List[SubagentSummary] = Field(
        default_factory=list, description="檔案列表"
    )

    model_config = {"populate_by_name": True}


class SubagentDocumentResponse(BaseModel):
    """單一 Subagent 內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    document: SubagentDocument = Field(..., description="檔案內容")

    model_config = {"populate_by_name": True}


class SubagentCreateRequest(BaseModel):
    """建立 Subagent 請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    content: str = Field(..., description="Markdown 內容")
    name: str | None = Field(None, description="Subagent 名稱預設值")
    description: str | None = Field(None, description="Subagent 描述預設值")

    model_config = {"populate_by_name": True}


class SubagentUpdateRequest(BaseModel):
    """更新 Subagent 請求"""

    content: str = Field(..., description="Markdown 內容")
    name: str | None = Field(None, description="Subagent 名稱預設值")
    description: str | None = Field(None, description="Subagent 描述預設值")


class SubagentDeleteResponse(BaseModel):
    """刪除 Subagent 回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    deleted: bool = Field(True, description="刪除狀態")

    model_config = {"populate_by_name": True}
