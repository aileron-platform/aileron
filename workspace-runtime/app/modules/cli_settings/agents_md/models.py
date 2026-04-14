"""CLI Agents MD 模型"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AgentsMdScope(str, Enum):
    """Agents md 支援的範圍"""

    PROJECT = "project"
    USER = "user"


class AgentsMdDocument(BaseModel):
    """Agents md 文件內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: AgentsMdScope = Field(..., description="檔案範圍")
    content: str = Field(..., description="Agents md 原始內容")

    model_config = {
        "populate_by_name": True,
    }


class AgentsMdUpdateRequest(BaseModel):
    """更新 agents md 的請求"""

    scope: AgentsMdScope = Field(..., description="更新範圍")
    content: str = Field(..., description="新的 agents md 內容")
    message: str | None = Field(None, description="變更說明")

    model_config = {
        "populate_by_name": True,
    }


class AgentsMdUpdateResponse(BaseModel):
    """更新 agents md 的結果"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: AgentsMdScope = Field(..., description="更新範圍")

    model_config = {
        "populate_by_name": True,
    }
