"""Claude Code Memory 資料模型"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MemoryDocumentSummary(BaseModel):
    """Memory 檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    name: str | None = Field(None, description="顯示名稱")
    description: str | None = Field(None, description="描述")
    size: str = Field(..., description="檔案大小")

    model_config = {"populate_by_name": True}


class MemoryDocumentDetail(MemoryDocumentSummary):
    """Memory 檔案完整內容"""

    content: str = Field(..., description="Markdown 內容")


class MemoryCollectionResponse(BaseModel):
    """Memory 檔案列表回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    documents: List[MemoryDocumentSummary] = Field(
        default_factory=list, description="Memory 檔案列表"
    )

    model_config = {"populate_by_name": True}


class MemoryDocumentResponse(BaseModel):
    """單一 Memory 檔案回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    document: MemoryDocumentDetail = Field(..., description="Memory 檔案內容")

    model_config = {"populate_by_name": True}


class MemoryCreateRequest(BaseModel):
    """建立 Memory 檔案請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    content: str = Field(..., description="Markdown 內容")

    model_config = {"populate_by_name": True}


class MemoryUpdateRequest(BaseModel):
    """更新 Memory 檔案請求"""

    content: str = Field(..., description="Markdown 內容")


class MemoryDeleteResponse(BaseModel):
    """刪除 Memory 檔案回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    deleted: bool = Field(True, description="刪除狀態")

    model_config = {"populate_by_name": True}
