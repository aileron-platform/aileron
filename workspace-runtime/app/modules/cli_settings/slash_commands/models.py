"""CLI Slash Commands data models"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .config import SlashCommandScope, DocumentFormat


class CliSlashCommandDocumentSummary(BaseModel):
    """Slash Command file summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
    namespace: str | None = Field(None, description="Namespace")
    description: str | None = Field(None, description="Command description")
    scope: SlashCommandScope = Field(..., description="File scope")
    size: str = Field(..., description="File size")
    format: DocumentFormat = Field(..., description="Document format (markdown / toml)")
    extension_name: str | None = Field(None, alias="extensionName", description="Source extension name")
    extension_version: str | None = Field(None, alias="extensionVersion", description="Source extension version")

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentDetail(CliSlashCommandDocumentSummary):
    """Slash Command full content"""

    content: str = Field(..., description="File raw content")


class CliSlashCommandScopeGroup(BaseModel):
    """Command list for same scope"""

    scope: SlashCommandScope = Field(..., description="File scope")
    documents: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )


class CliSlashCommandScopesResponse(BaseModel):
    """List all commands by scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[CliSlashCommandScopeGroup] = Field(
        default_factory=list, description="Commands grouped by scope"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandScopeResponse(BaseModel):
    """Single scope command list"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="Command scope")
    documents: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="File list"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentResponse(BaseModel):
    """Single file content"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="File scope")
    document: CliSlashCommandDocumentDetail = Field(..., description="File content")

    model_config = {"populate_by_name": True}


class CliSlashCommandCreateRequest(BaseModel):
    """Create Slash Command request"""

    file_name: str = Field(..., alias="fileName", description="File name")
    content: str = Field(..., description="File content")
    namespace: str | None = Field(None, description="Namespace")

    model_config = {"populate_by_name": True}


class CliSlashCommandUpdateRequest(BaseModel):
    """Update Slash Command request"""

    content: str = Field(..., description="File content")
    namespace: str | None = Field(None, description="Namespace")


class CliSlashCommandDeleteResponse(BaseModel):
    """Delete command response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="Command scope")
    file_name: str = Field(..., alias="fileName", description="File name")
    deleted: bool = Field(True, description="Deletion status")

    model_config = {"populate_by_name": True}
