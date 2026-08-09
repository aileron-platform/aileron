"""Claude Code Hooks Module Data Models"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from ..documents import DocumentScope


class HookActionType(str, Enum):
    """Hook action type"""

    COMMAND = "command"
    HTTP = "http"
    MCP_TOOL = "mcp_tool"
    PROMPT = "prompt"
    AGENT = "agent"


class HookAction(BaseModel):
    """Hook action definition"""

    type: HookActionType = Field(..., description="Action type")
    args: List[str] | None = Field(None, description="Command arguments")
    name: str | None = Field(None, description="Action name")
    command: str | None = Field(None, description="Command or instruction")
    url: str | None = Field(None, description="HTTP endpoint URL")
    headers: Dict[str, str] | None = Field(None, description="HTTP headers")
    allowed_env_vars: List[str] | None = Field(
        None, alias="allowedEnvVars", description="Allowed environment variables"
    )
    server: str | None = Field(None, description="MCP server name")
    tool: str | None = Field(None, description="MCP tool name")
    input: Dict[str, Any] | None = Field(None, description="MCP tool input")
    prompt: str | None = Field(None, description="Prompt content")
    model: str | None = Field(None, description="Model override")
    timeout: int | None = Field(None, description="Timeout in seconds")
    description: str | None = Field(None, description="Action description")
    status_message: str | None = Field(
        None, alias="statusMessage", description="Status message"
    )
    if_condition: str | None = Field(
        None, alias="if", description="Conditional expression"
    )
    once: bool | None = Field(None, description="Run once")
    async_: bool | None = Field(None, alias="async", description="Run asynchronously")
    async_rewake: bool | None = Field(
        None, alias="asyncRewake", description="Rewake after async completion"
    )
    shell: str | None = Field(None, description="Shell")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class HookRule(BaseModel):
    """Hook rule"""

    matcher: str = Field(..., description="Event matcher")
    hooks: List[HookAction] = Field(default_factory=list, description="Action list")

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
    scope: DocumentScope | None = None
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class HookScopeDocument(BaseModel):
    """Hook configuration for single scope"""

    scope: DocumentScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(
        default_factory=dict, description="Event mapping"
    )
    revision: str | None = Field(None, description="Content revision token")

    # Added: Plugin source mapping (has value only when scope='plugin')
    plugin_sources: Dict[str, str] | None = Field(
        None,
        alias="pluginSources",
        description="Plugin source mapping {event_name:index -> plugin_id}",
    )
    source_id: str | None = Field(None, alias="sourceId")
    source_path: str | None = Field(None, alias="sourcePath")
    read_only: bool = Field(default=False, alias="readOnly")
    editable: bool = True

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )


class HookScopesResponse(BaseModel):
    """List hooks for all scopes"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[HookScopeDocument] = Field(
        default_factory=list, description="Scope list"
    )

    model_config = {"populate_by_name": True}


class HookScopeResponse(BaseModel):
    """Get single scope hook"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(
        default_factory=dict, description="Event mapping"
    )
    revision: str = Field(..., description="Content revision token")

    model_config = {"populate_by_name": True}


class HookScopeUpsertRequest(BaseModel):
    """Update hook configuration request"""

    hooks: Dict[str, List[HookRule]] = Field(
        ..., description="Complete hook configuration"
    )
    revision: str = Field(..., description="Expected content revision token")

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
    scopes: List[HookScopeDocument] = Field(
        default_factory=list, description="Exported scopes"
    )

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
