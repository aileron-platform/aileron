"""Slash Commands Module Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..documents import DocumentScope


class SlashCommandDocumentSummary(BaseModel):
    """Slash Command file summary"""

    path: str = Field(..., description="File path")
    description: str | None = Field(None, description="Command description")
    scope: DocumentScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")

    # Added: Plugin source information (has value when scope='plugin')
    plugin_name: str | None = Field(
        None,
        alias="pluginName",
        description="Plugin name (has value only when scope='plugin')",
    )
    marketplace_name: str | None = Field(
        None,
        alias="marketplaceName",
        description="Marketplace name (has value only when scope='plugin')",
    )
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None

    model_config = {"populate_by_name": True}


class SlashCommandDocumentDetail(SlashCommandDocumentSummary):
    """Slash Command full content"""

    content: str = Field(..., description="Markdown content")


class SlashCommandAvailableScope(BaseModel):
    """Available command scope"""

    scope: DocumentScope = Field(..., description="Available scope")
    read_only: bool = Field(
        False, alias="readOnly", description="Whether scope is read-only"
    )

    model_config = {"populate_by_name": True}


class SlashCommandScopesResponse(BaseModel):
    """List commands as flat items with scope metadata"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    items: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )
    available_scopes: List[SlashCommandAvailableScope] = Field(
        default_factory=list,
        alias="availableScopes",
        description="Available scopes",
    )

    model_config = {"populate_by_name": True}


class SlashCommandScopeResponse(BaseModel):
    """Command list in single scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Command scope")
    revision: str = Field(..., description="Scope content revision token")
    documents: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class SlashCommandDocumentResponse(BaseModel):
    """Single file content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    revision: str = Field(..., description="Document content revision token")
    document: SlashCommandDocumentDetail = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class SlashCommandCreateRequest(BaseModel):
    """Create Slash Command request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected scope revision token")
    description: str | None = Field(
        None, description="Command description default value"
    )

    model_config = {"populate_by_name": True}


class SlashCommandUpdateRequest(BaseModel):
    """Update Slash Command request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="Markdown content")
    revision: str = Field(..., description="Expected document revision token")
    description: str | None = Field(
        None, description="Command description default value"
    )


class SlashCommandDeleteResponse(BaseModel):
    """Delete command response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Command scope")
    path: str = Field(..., description="File path")
    revision: str = Field(..., description="Scope content revision token")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
