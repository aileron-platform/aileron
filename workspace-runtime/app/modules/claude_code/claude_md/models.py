"""Claude.md 模組資料模型"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..common import DocumentScope


class ClaudeMdScope(str, Enum):
    """Claude.md 支援的範圍"""

    PROJECT = DocumentScope.PROJECT.value
    USER = DocumentScope.USER.value


class ClaudeMdDocument(BaseModel):
    """Claude.md 文件內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: ClaudeMdScope = Field(..., description="檔案範圍")
    content: str = Field(..., description="Claude.md 原始內容")

    model_config = {
        "populate_by_name": True,
    }


class ClaudeMdUpdateRequest(BaseModel):
    """更新 Claude.md 的請求"""

    scope: ClaudeMdScope = Field(..., description="更新範圍")
    content: str = Field(..., description="新的 Claude.md 內容")
    message: str | None = Field(None, description="變更說明")

    model_config = {
        "populate_by_name": True,
    }


class ClaudeMdUpdateResponse(BaseModel):
    """更新 Claude.md 的結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: ClaudeMdScope = Field(..., description="更新範圍")

    model_config = {
        "populate_by_name": True,
    }
