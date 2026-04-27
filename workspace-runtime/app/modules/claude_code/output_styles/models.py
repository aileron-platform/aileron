"""Output Styles Module Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class OutputStyleSummary(BaseModel):
    """Output style file summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
    name: str | None = Field(None, description="Style name")
    description: str | None = Field(None, description="Style description")
    scope: DocumentScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")

    model_config = {"populate_by_name": True}


class OutputStyleDocument(OutputStyleSummary):
    """Output style detail content"""

    content: str = Field(..., description="Markdown content")


class OutputStyleScopeGroup(BaseModel):
    """Output styles in same scope"""

    scope: DocumentScope = Field(..., description="File scope")
    documents: List[OutputStyleSummary] = Field(
        default_factory=list, description="File list"
    )


class OutputStyleCollectionResponse(BaseModel):
    """Output style list in all scopes"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[OutputStyleScopeGroup] = Field(
        default_factory=list, description="Styles grouped by scope"
    )

    model_config = {"populate_by_name": True}


class OutputStyleScopeResponse(BaseModel):
    """Output style list in single scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    documents: List[OutputStyleSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class OutputStyleDocumentResponse(BaseModel):
    """Single output style content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    document: OutputStyleDocument = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class OutputStyleCreateRequest(BaseModel):
    """Create output style request"""

    file_name: str = Field(..., alias="fileName", description="File name")
    content: str = Field(..., description="Markdown content")
    name: str | None = Field(None, description="Style name default value")
    description: str | None = Field(None, description="Style description default value")

    model_config = {"populate_by_name": True}


class OutputStyleUpdateRequest(BaseModel):
    """Update output style request"""

    content: str = Field(..., description="Markdown content")
    name: str | None = Field(None, description="Style name default value")
    description: str | None = Field(None, description="Style description default value")


class OutputStyleDeleteResponse(BaseModel):
    """Delete output style response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    file_name: str = Field(..., alias="fileName", description="File name")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
