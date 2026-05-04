"""CLI MCP module data models

Aligns with Claude Code MCP API response format, ensuring no frontend changes needed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class CliMcpScope(str, Enum):
    """MCP configuration scopes supported by CLI tools"""

    PROJECT = "project"
    USER = "user"
    PLUGIN = "plugin"
    EXTENSION = "extension"


class CliMcpTransportType(str, Enum):
    """Transport protocols supported by MCP servers"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class CliMcpServerConfig(BaseModel):
    """Basic MCP server configuration (extra=allow preserves native fields from each tool)"""

    type: CliMcpTransportType = Field(
        default=CliMcpTransportType.STDIO,
        description="Server transport type",
    )
    command: str | None = Field(None, description="Startup command")
    url: str | None = Field(None, description="Remote server URL")
    args: List[str] | None = Field(None, description="Command arguments")
    env: Dict[str, str] | None = Field(None, description="Environment variables")
    headers: Dict[str, str] | None = Field(None, description="HTTP headers")

    model_config = ConfigDict(extra="allow")


class CliMcpServerRuntime(CliMcpServerConfig):
    """MCP server information for responses, including enabled status"""

    enabled: bool = Field(default=True, description="Whether this server is enabled")


class CliMcpScopeServers(BaseModel):
    """MCP server list for a single scope"""

    scope: CliMcpScope = Field(..., description="Configuration scope")
    mcpServers: Dict[str, CliMcpServerRuntime] = Field(
        default_factory=dict, description="Server configuration"
    )


class CliMcpServerCollectionResponse(BaseModel):
    """Response listing all MCP servers"""

    workspaceId: str = Field(..., description="Workspace ID")
    scopes: List[CliMcpScopeServers] = Field(
        default_factory=list, description="Scope list"
    )


class CliMcpScopeResponse(BaseModel):
    """Response for single scope or server"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="Configuration scope")
    mcpServers: Dict[str, CliMcpServerRuntime] = Field(
        default_factory=dict, description="Server configuration"
    )


class CliMcpServerCreateRequest(BaseModel):
    """Request to create MCP servers"""

    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="Server collection to create"
    )


class CliMcpServerUpdateRequest(BaseModel):
    """Request to update MCP servers"""

    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="Updated server configuration"
    )


class CliMcpServerDeleteResponse(BaseModel):
    """Result of deleting MCP servers"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="Configuration scope")


class CliMcpImportRequest(BaseModel):
    """Request to import MCP configuration"""

    scope: CliMcpScope = Field(..., description="Import target scope")
    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        ..., min_length=1, description="Server configuration to import"
    )
    overwrite: bool = Field(
        False, description="Whether to overwrite existing configuration if same name exists"
    )


class CliMcpImportUploadRequest(BaseModel):
    """Request to import MCP configuration via file upload"""

    scope: CliMcpScope = Field(..., description="Import target scope")
    file: bytes = Field(..., description="Uploaded JSON file content")
    overwrite: bool = Field(
        False, description="Whether to overwrite existing configuration if same name exists"
    )


class CliMcpImportResponse(BaseModel):
    """Result of importing MCP configuration"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="Configuration scope")
    created: List[str] = Field(default_factory=list, description="Created servers")
    updated: List[str] = Field(default_factory=list, description="Updated servers")
    skipped: List[str] = Field(
        default_factory=list, description="Servers skipped due to duplicates"
    )


class CliMcpServerExportResponse(BaseModel):
    """Response for exporting MCP configuration"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: CliMcpScope = Field(..., description="Configuration scope")
    mcpServers: Dict[str, CliMcpServerConfig] = Field(
        default_factory=dict, description="Server configuration"
    )
