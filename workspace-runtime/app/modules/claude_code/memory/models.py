"""Claude Code Memory Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.core.resource_envelope import ResourceResult
from ..documents import DocumentScope


class MemoryDocumentSummary(BaseModel):
    """Memory file summary"""

    path: str = Field(..., description="File path")
    scope: DocumentScope = Field(..., description="File scope")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description")
    size: str = Field(..., description="File size")

    model_config = {"populate_by_name": True}


class MemoryDocumentDetail(MemoryDocumentSummary):
    """Memory file complete content"""

    content: str = Field(..., description="Markdown content")


class MemoryCollectionResponse(BaseModel):
    """Memory file list response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    revision: str = Field(..., description="Memory collection revision token")
    items: List[MemoryDocumentSummary] = Field(
        default_factory=list, description="File list"
    )
    available_scopes: List["MemoryAvailableScope"] = Field(
        default_factory=list,
        alias="availableScopes",
        description="Available scopes",
    )

    model_config = {"populate_by_name": True}


class MemoryAvailableScope(BaseModel):
    """Available memory scope"""

    scope: DocumentScope = Field(..., description="Available scope")
    read_only: bool = Field(
        False, alias="readOnly", description="Whether scope is read-only"
    )

    model_config = {"populate_by_name": True}


class MemoryDocumentResponse(ResourceResult):
    """Single memory file response"""


class MemoryCreateRequest(BaseModel):
    """Create memory file request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected memory collection revision token")

    model_config = {"populate_by_name": True}


class MemoryUpdateRequest(BaseModel):
    """Update memory file request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected memory document revision token")


class MemoryDeleteResponse(ResourceResult):
    """Delete memory file response"""
