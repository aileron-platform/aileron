"""MCP Module Data Models"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..documents import DocumentScope


class McpTransportType(str, Enum):
    """Transport protocols supported by MCP server"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class McpServerConfig(BaseModel):
    """MCP server basic configuration"""

    type: McpTransportType = Field(
        default=McpTransportType.STDIO,
        description="Server transport type",
    )
    command: str | None = Field(None, description="Startup command")
    url: str | None = Field(None, description="Remote server URL")
    args: List[str] | None = Field(None, description="Command arguments")
    env: Dict[str, str] | None = Field(None, description="Environment variables")
    headers: Dict[str, str] | None = Field(None, description="HTTP headers")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> Self:
        """Validate required fields for different transport types"""
        if self.type in [McpTransportType.HTTP, McpTransportType.SSE]:
            if not self.url:
                raise ValueError(f"URL is required for transport type '{self.type}'")
        elif self.type == McpTransportType.STDIO:
            if not self.command:
                raise ValueError("Command is required for stdio transport type")
        return self


class McpServerRuntime(McpServerConfig):
    """MCP server information used in response, same as McpServerConfig"""

    enabled: bool = Field(default=True, description="Whether this server is enabled")

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


class McpScopeServers(BaseModel):
    """MCP server list for single scope"""

    scope: DocumentScope = Field(..., description="Configuration scope")
    revision: str = Field(..., description="Content revision token")
    mcpServers: Dict[str, McpServerRuntime] = Field(
        default_factory=dict, description="Server configuration"
    )


class McpServerCollectionResponse(BaseModel):
    """Response listing all MCP servers"""

    workspaceId: str = Field(..., description="Workspace ID")
    scopes: List[McpScopeServers] = Field(
        default_factory=list, description="Scope list"
    )


class McpScopeResponse(BaseModel):
    """Response for single scope or server"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="Configuration scope")
    revision: str = Field(..., description="Content revision token")
    mcpServers: Dict[str, McpServerRuntime] = Field(
        default_factory=dict, description="Server configuration"
    )


class McpServerCreateRequest(BaseModel):
    """Request to create MCP server"""

    revision: str = Field(..., description="Expected content revision token")
    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="Server collection to create"
    )


class McpServerUpdateRequest(BaseModel):
    """Request to update MCP server"""

    revision: str = Field(..., description="Expected content revision token")
    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="Updated server configuration"
    )


class McpServerDeleteResponse(BaseModel):
    """Result of deleting MCP server"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: DocumentScope = Field(..., description="Configuration scope")
    revision: str = Field(..., description="Content revision token")

    model_config = ConfigDict(populate_by_name=True)


class McpImportRequest(BaseModel):
    """Request to import MCP configuration"""

    scope: DocumentScope = Field(..., description="Import target scope")
    revision: str = Field(..., description="Expected content revision token")
    mcpServers: Dict[str, McpServerConfig] = Field(
        ..., min_length=1, description="Server configuration to import"
    )
    overwrite: bool = Field(
        False,
        description="Whether to overwrite existing configuration if same name exists",
    )


class McpImportUploadRequest(BaseModel):
    """Request to import MCP configuration via file upload"""

    scope: DocumentScope = Field(..., description="Import target scope")
    revision: str = Field(..., description="Expected content revision token")
    file: bytes = Field(..., description="Uploaded JSON file content")
    overwrite: bool = Field(
        False,
        description="Whether to overwrite existing configuration if same name exists",
    )


class McpImportResponse(BaseModel):
    """Result of importing MCP configuration"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="Configuration scope")
    revision: str = Field(..., description="Content revision token")
    created: List[str] = Field(default_factory=list, description="Created servers")
    updated: List[str] = Field(default_factory=list, description="Updated servers")
    skipped: List[str] = Field(
        default_factory=list, description="Servers skipped due to duplication"
    )


class McpServerExportResponse(BaseModel):
    """Response exporting MCP configuration"""

    workspaceId: str = Field(..., description="Workspace ID")
    scope: DocumentScope = Field(..., description="Configuration scope")
    mcpServers: Dict[str, McpServerConfig] = Field(
        default_factory=dict, description="Server configuration"
    )
