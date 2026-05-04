"""Claude Code Hooks Module Data Models"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field

from ..common import DocumentScope


class HookActionType(str, Enum):
    """Hook action type"""

    COMMAND = "command"
    WEBHOOK = "webhook"
    MCP_CALL = "mcp_call"


class HookAction(BaseModel):
    """Hook action definition"""

    type: HookActionType = Field(..., description="Action type")
    name: str | None = Field(None, description="Action name")
    command: str | None = Field(None, description="Command or instruction")
    timeout: int | None = Field(None, description="Timeout in seconds")
    description: str | None = Field(None, description="Action description")


class HookRule(BaseModel):
    """Hook rule"""

    matcher: str = Field(..., description="Event matcher")
    hooks: List[HookAction] = Field(default_factory=list, description="Action list")

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
    extension_name: str | None = Field(
        None,
        alias="extensionName",
        description="Extension name (has value only when scope='extension')",
    )
    extension_version: str | None = Field(
        None,
        alias="extensionVersion",
        description="Extension version (has value only when scope='extension')",
    )


class HookScopeDocument(BaseModel):
    """Hook configuration for single scope"""

    scope: DocumentScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="Event mapping")

    # Added: Plugin source mapping (has value only when scope='plugin')
    plugin_sources: Dict[str, str] | None = Field(
        None,
        alias="pluginSources",
        description="Plugin source mapping {event_name:index -> plugin_id}"
    )

    model_config = {"populate_by_name": True}


class HookScopesResponse(BaseModel):
    """List hooks for all scopes"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[HookScopeDocument] = Field(default_factory=list, description="Scope list")

    model_config = {"populate_by_name": True}


class HookScopeResponse(BaseModel):
    """Get single scope hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="Event mapping")

    model_config = {"populate_by_name": True}


class HookScopeUpsertRequest(BaseModel):
    """Update hook configuration request"""

    hooks: Dict[str, List[HookRule]] = Field(..., description="Complete hook configuration")

    model_config = {"populate_by_name": True}


class HookDeleteResponse(BaseModel):
    """Delete hook response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Hook scope")
    deleted: bool = Field(True, description="Deletion status")
    deleted_at: datetime = Field(..., alias="deletedAt", description="Deletion time")

    model_config = {"populate_by_name": True}


class HookExportResponse(BaseModel):
    """Export hook result"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    exported_at: datetime = Field(..., alias="exportedAt", description="Export time")
    scopes: List[HookScopeDocument] = Field(default_factory=list, description="Exported scopes")

    model_config = {"populate_by_name": True}


class HookImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


class HookImportRequest(BaseModel):
    """Import hook request"""

    mode: HookImportMode = Field(..., description="Import mode")
    scopes: List[HookScopeDocument] = Field(..., description="Import data")


class HookImportResponse(BaseModel):
    """Import result"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    mode: HookImportMode = Field(..., description="Import mode")
    imported: int = Field(..., description="Number created")
    updated: int = Field(..., description="Number updated")
    skipped: int = Field(..., description="Number skipped")

    model_config = {"populate_by_name": True}
