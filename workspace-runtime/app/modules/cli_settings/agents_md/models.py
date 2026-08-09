"""CLI Agents MD models"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AgentsMdScope(str, Enum):
    """Scopes supported by agents md"""

    PROJECT = "project"
    USER = "user"


class AgentsMdDocument(BaseModel):
    """Agents md document content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: AgentsMdScope = Field(..., description="File scope")
    content: str = Field(..., description="Agents md raw content")
    revision: str = Field(..., description="Content revision token")
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None

    model_config = {
        "populate_by_name": True,
    }


class AgentsMdUpdateRequest(BaseModel):
    """Request to update agents md"""

    scope: AgentsMdScope = Field(..., description="Update scope")
    content: str = Field(..., description="New agents md content")
    revision: str = Field(..., description="Expected content revision token")
    message: str | None = Field(None, description="Change description")

    model_config = {
        "populate_by_name": True,
    }


class AgentsMdUpdateResponse(BaseModel):
    """Result of updating agents md"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: AgentsMdScope = Field(..., description="Update scope")
    revision: str = Field(..., description="New content revision token")

    model_config = {
        "populate_by_name": True,
    }
