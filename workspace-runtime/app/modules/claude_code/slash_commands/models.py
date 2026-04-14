"""Slash Commands 模組資料模型"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class SlashCommandDocumentSummary(BaseModel):
    """Slash Command 檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    namespace: str | None = Field(None, description="命名空間")
    description: str | None = Field(None, description="指令描述")
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


class SlashCommandDocumentDetail(SlashCommandDocumentSummary):
    """Slash Command 完整內容"""

    content: str = Field(..., description="Markdown 內容")


class SlashCommandScopeGroup(BaseModel):
    """同一範圍的命令清單"""

    scope: DocumentScope = Field(..., description="檔案範圍")
    documents: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="檔案列表"
    )


class SlashCommandScopesResponse(BaseModel):
    """列出所有範圍的命令"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[SlashCommandScopeGroup] = Field(
        default_factory=list, description="依範圍分類的命令"
    )

    model_config = {"populate_by_name": True}


class SlashCommandScopeResponse(BaseModel):
    """單一範圍命令列表"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="命令範圍")
    documents: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="檔案列表"
    )

    model_config = {"populate_by_name": True}


class SlashCommandDocumentResponse(BaseModel):
    """單一檔案內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    document: SlashCommandDocumentDetail = Field(..., description="檔案內容")

    model_config = {"populate_by_name": True}


class SlashCommandCreateRequest(BaseModel):
    """建立 Slash Command 請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    content: str = Field(..., description="Markdown 內容")
    namespace: str | None = Field(None, description="命名空間預設值")
    description: str | None = Field(None, description="指令描述預設值")

    model_config = {"populate_by_name": True}


class SlashCommandUpdateRequest(BaseModel):
    """更新 Slash Command 請求"""

    content: str = Field(..., description="Markdown 內容")
    namespace: str | None = Field(None, description="命名空間預設值")
    description: str | None = Field(None, description="指令描述預設值")


class SlashCommandDeleteResponse(BaseModel):
    """刪除命令的回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="命令範圍")
    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    deleted: bool = Field(True, description="刪除狀態")

    model_config = {"populate_by_name": True}
