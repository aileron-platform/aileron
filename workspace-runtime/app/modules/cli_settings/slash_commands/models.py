"""CLI Slash Commands data models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .config import SlashCommandScope, DocumentFormat


class CliSlashCommandDocumentSummary(BaseModel):
    """Slash Command file summary"""

    path: str = Field(..., description="File path")
    description: str | None = Field(None, description="Command description")
    scope: SlashCommandScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")
    format: DocumentFormat = Field(..., description="Document format (markdown / toml)")
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentDetail(CliSlashCommandDocumentSummary):
    """Slash Command full content"""

    content: str = Field(..., description="File raw content")


class CliSlashCommandAvailableScope(BaseModel):
    """Available command scope."""

    scope: SlashCommandScope = Field(..., description="Available scope")
    read_only: bool = Field(
        False, alias="readOnly", description="Whether scope is read-only"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandScopesResponse(BaseModel):
    """List all commands as flat items with scope metadata"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    items: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )
    available_scopes: List[CliSlashCommandAvailableScope] = Field(
        default_factory=list,
        alias="availableScopes",
        description="Available scopes",
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandScopeResponse(BaseModel):
    """Single scope command list"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="Command scope")
    revision: str = Field(..., description="Scope content revision token")
    documents: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentResponse(BaseModel):
    """Single file content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="File scope")
    revision: str = Field(..., description="Document content revision token")
    document: CliSlashCommandDocumentDetail = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class CliSlashCommandCreateRequest(BaseModel):
    """Create Slash Command request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="File content")
    revision: str = Field(..., description="Expected scope revision token")

    model_config = {"populate_by_name": True}


class CliSlashCommandUpdateRequest(BaseModel):
    """Update Slash Command request"""

    path: str = Field(..., description="File path")
    content: str = Field(..., description="File content")
    revision: str = Field(..., description="Expected document revision token")


class CliSlashCommandDeleteResponse(BaseModel):
    """Delete command response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="Command scope")
    path: str = Field(..., description="File path")
    revision: str = Field(..., description="Scope content revision token")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
