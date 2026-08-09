"""CLI subagents API models."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.modules.claude_code.documents import DocumentScope


class SubagentSummary(BaseModel):
    """Subagent file summary."""

    path: str = Field(..., description="File path")
    name: str | None = Field(None, description="Subagent name")
    description: str | None = Field(None, description="Subagent description")
    scope: DocumentScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")
    plugin_name: str | None = Field(None, alias="pluginName", description="Plugin name")
    marketplace_name: str | None = Field(
        None, alias="marketplaceName", description="Marketplace name"
    )
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None

    model_config = {"populate_by_name": True}


class SubagentDocument(SubagentSummary):
    """Subagent detail content."""

    content: str = Field(..., description="Markdown content")


class AvailableSubagentScope(BaseModel):
    """Available subagent scope."""

    scope: DocumentScope = Field(..., description="Available scope")
    read_only: bool = Field(
        False, alias="readOnly", description="Whether scope is read-only"
    )

    model_config = {"populate_by_name": True}


class SubagentCollectionResponse(BaseModel):
    """Subagent files in all scopes."""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    items: List[SubagentSummary] = Field(default_factory=list, description="File list")
    available_scopes: List[AvailableSubagentScope] = Field(
        default_factory=list,
        alias="availableScopes",
        description="Available scopes",
    )

    model_config = {"populate_by_name": True}


class SubagentScopeResponse(BaseModel):
    """Subagent files in single scope."""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    revision: str = Field(..., description="Scope content revision token")
    documents: List[SubagentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class SubagentDocumentResponse(BaseModel):
    """Single subagent content."""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    revision: str = Field(..., description="Document content revision token")
    document: SubagentDocument = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class SubagentCreateRequest(BaseModel):
    """Create subagent request."""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected scope revision token")
    name: str | None = Field(None, description="Subagent name")
    description: str | None = Field(None, description="Subagent description")

    model_config = {"populate_by_name": True}


class SubagentUpdateRequest(BaseModel):
    """Update subagent request."""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected document revision token")
    name: str | None = Field(None, description="Subagent name")
    description: str | None = Field(None, description="Subagent description")

    model_config = {"populate_by_name": True}


class SubagentDeleteResponse(BaseModel):
    """Delete subagent response."""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    path: str = Field(..., description="File path")
    revision: str = Field(..., description="Scope content revision token")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
