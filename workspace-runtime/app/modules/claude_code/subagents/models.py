"""Subagents Module Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class SubagentSummary(BaseModel):
    """Subagent file summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
    name: str | None = Field(None, description="Subagent name")
    description: str | None = Field(None, description="Subagent description")
    scope: DocumentScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")

    # Added: Plugin source information (has value when scope='plugin')
    plugin_name: str | None = Field(
        None,
        alias="pluginName",
        description="Plugin name (has value only when scope='plugin')"
    )
    marketplace_name: str | None = Field(
        None,
        alias="marketplaceName",
        description="Marketplace name (has value only when scope='plugin')"
    )

    model_config = {"populate_by_name": True}


class SubagentDocument(SubagentSummary):
    """Subagent detail content"""

    content: str = Field(..., description="Markdown content")


class SubagentScopeGroup(BaseModel):
    """Subagent files in same scope"""

    scope: DocumentScope = Field(..., description="File scope")
    documents: List[SubagentSummary] = Field(
        default_factory=list, description="File list"
    )


class SubagentCollectionResponse(BaseModel):
    """Subagent files in all scopes"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[SubagentScopeGroup] = Field(
        default_factory=list, description="Subagents grouped by scope"
    )

    model_config = {"populate_by_name": True}


class SubagentScopeResponse(BaseModel):
    """Subagent files in single scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    documents: List[SubagentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class SubagentDocumentResponse(BaseModel):
    """Single Subagent content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    document: SubagentDocument = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class SubagentCreateRequest(BaseModel):
    """Create Subagent request"""

    file_name: str = Field(..., alias="fileName", description="File name")
    content: str = Field(..., description="Markdown content")
    name: str | None = Field(None, description="Subagent name default value")
    description: str | None = Field(None, description="Subagent description default value")

    model_config = {"populate_by_name": True}


class SubagentUpdateRequest(BaseModel):
    """Update Subagent request"""

    content: str = Field(..., description="Markdown content")
    name: str | None = Field(None, description="Subagent name default value")
    description: str | None = Field(None, description="Subagent description default value")


class SubagentDeleteResponse(BaseModel):
    """Delete Subagent response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    file_name: str = Field(..., alias="fileName", description="File name")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
