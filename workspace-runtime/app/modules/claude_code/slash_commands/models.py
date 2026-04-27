"""Slash Commands Module Data Models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class SlashCommandDocumentSummary(BaseModel):
    """Slash Command file summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
    namespace: str | None = Field(None, description="Namespace")
    description: str | None = Field(None, description="Command description")
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


class SlashCommandDocumentDetail(SlashCommandDocumentSummary):
    """Slash Command full content"""

    content: str = Field(..., description="Markdown content")


class SlashCommandScopeGroup(BaseModel):
    """Command list in same scope"""

    scope: DocumentScope = Field(..., description="File scope")
    documents: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )


class SlashCommandScopesResponse(BaseModel):
    """List commands in all scopes"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[SlashCommandScopeGroup] = Field(
        default_factory=list, description="Commands grouped by scope"
    )

    model_config = {"populate_by_name": True}


class SlashCommandScopeResponse(BaseModel):
    """Command list in single scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Command scope")
    documents: List[SlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class SlashCommandDocumentResponse(BaseModel):
    """Single file content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="File scope")
    document: SlashCommandDocumentDetail = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class SlashCommandCreateRequest(BaseModel):
    """Create Slash Command request"""

    file_name: str = Field(..., alias="fileName", description="File name")
    content: str = Field(..., description="Markdown content")
    namespace: str | None = Field(None, description="Namespace default value")
    description: str | None = Field(None, description="Command description default value")

    model_config = {"populate_by_name": True}


class SlashCommandUpdateRequest(BaseModel):
    """Update Slash Command request"""

    content: str = Field(..., description="Markdown content")
    namespace: str | None = Field(None, description="Namespace default value")
    description: str | None = Field(None, description="Command description default value")


class SlashCommandDeleteResponse(BaseModel):
    """Delete command response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Command scope")
    file_name: str = Field(..., alias="fileName", description="File name")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
