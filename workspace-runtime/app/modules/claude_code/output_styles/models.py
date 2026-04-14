"""Output Styles 模組資料模型"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class OutputStyleSummary(BaseModel):
    """輸出樣式檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    name: str | None = Field(None, description="樣式名稱")
    description: str | None = Field(None, description="樣式描述")
    scope: DocumentScope = Field(..., description="檔案範圍")
    size: str = Field(..., description="檔案大小")

    model_config = {"populate_by_name": True}


class OutputStyleDocument(OutputStyleSummary):
    """輸出樣式詳細內容"""

    content: str = Field(..., description="Markdown 內容")


class OutputStyleScopeGroup(BaseModel):
    """同一範圍的輸出樣式"""

    scope: DocumentScope = Field(..., description="檔案範圍")
    documents: List[OutputStyleSummary] = Field(
        default_factory=list, description="檔案列表"
    )


class OutputStyleCollectionResponse(BaseModel):
    """所有範圍的輸出樣式列表"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[OutputStyleScopeGroup] = Field(
        default_factory=list, description="依範圍分類的樣式"
    )

    model_config = {"populate_by_name": True}


class OutputStyleScopeResponse(BaseModel):
    """單一範圍輸出樣式列表"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    documents: List[OutputStyleSummary] = Field(
        default_factory=list, description="檔案列表"
    )

    model_config = {"populate_by_name": True}


class OutputStyleDocumentResponse(BaseModel):
    """單一輸出樣式內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    document: OutputStyleDocument = Field(..., description="檔案內容")

    model_config = {"populate_by_name": True}


class OutputStyleCreateRequest(BaseModel):
    """建立輸出樣式請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    content: str = Field(..., description="Markdown 內容")
    name: str | None = Field(None, description="樣式名稱預設值")
    description: str | None = Field(None, description="樣式描述預設值")

    model_config = {"populate_by_name": True}


class OutputStyleUpdateRequest(BaseModel):
    """更新輸出樣式請求"""

    content: str = Field(..., description="Markdown 內容")
    name: str | None = Field(None, description="樣式名稱預設值")
    description: str | None = Field(None, description="樣式描述預設值")


class OutputStyleDeleteResponse(BaseModel):
    """刪除輸出樣式回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="檔案範圍")
    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    deleted: bool = Field(True, description="刪除狀態")

    model_config = {"populate_by_name": True}
