"""Claude.md Module Data Models"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..common import DocumentScope


class ClaudeMdScope(str, Enum):
    """Claude.md supported scopes"""

    PROJECT = DocumentScope.PROJECT.value
    USER = DocumentScope.USER.value


class ClaudeMdDocument(BaseModel):
    """Claude.md document content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: ClaudeMdScope = Field(..., description="File scope")
    content: str = Field(..., description="Claude.md raw content")

    model_config = {
        "populate_by_name": True,
    }


class ClaudeMdUpdateRequest(BaseModel):
    """Request to update Claude.md"""

    scope: ClaudeMdScope = Field(..., description="Update scope")
    content: str = Field(..., description="New Claude.md content")
    message: str | None = Field(None, description="Change description")

    model_config = {
        "populate_by_name": True,
    }


class ClaudeMdUpdateResponse(BaseModel):
    """Result of updating Claude.md"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: ClaudeMdScope = Field(..., description="Update scope")

    model_config = {
        "populate_by_name": True,
    }
