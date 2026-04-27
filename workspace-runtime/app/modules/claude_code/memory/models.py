"""Claude Code Memory Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MemoryDocumentSummary(BaseModel):
    """Memory file summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
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
    documents: List[MemoryDocumentSummary] = Field(
        default_factory=list, description="List of memory files"
    )

    model_config = {"populate_by_name": True}


class MemoryDocumentResponse(BaseModel):
    """Single memory file response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    document: MemoryDocumentDetail = Field(..., description="Memory file content")

    model_config = {"populate_by_name": True}


class MemoryCreateRequest(BaseModel):
    """Create memory file request"""

    file_name: str = Field(..., alias="fileName", description="File name")
    content: str = Field(..., description="Markdown content")

    model_config = {"populate_by_name": True}


class MemoryUpdateRequest(BaseModel):
    """Update memory file request"""

    content: str = Field(..., description="Markdown content")


class MemoryDeleteResponse(BaseModel):
    """Delete memory file response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    file_name: str = Field(..., alias="fileName", description="File name")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
