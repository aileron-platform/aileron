"""Template configuration models (MCP, Hooks, Commands and Agents)"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============ MCP Models ============


class McpTransportType(str, Enum):
    """MCP server transport protocol"""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class McpServerConfig(BaseModel):
    """MCP server configuration"""

    description: str = Field(description="MCP server description")
    type: McpTransportType = Field(default=McpTransportType.STDIO, description="Transport type")
    command: Optional[str] = Field(default=None, description="Execution command (stdio)")
    args: Optional[List[str]] = Field(default=None, description="Command parameters")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")
    url: Optional[str] = Field(default=None, description="Server URL (http/sse)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")

    model_config = {"use_enum_values": True}


class McpConfigResponse(BaseModel):
    """MCP configuration response"""

    template_id: str = Field(description="Template ID", alias="templateId")
    mcp_servers: Dict[str, McpServerConfig] = Field(
        default_factory=dict, description="MCP server configuration", alias="mcpServers"
    )

    model_config = {"populate_by_name": True}


class McpConfigUpdateRequest(BaseModel):
    """MCP configuration update request"""

    mcp_servers: Dict[str, McpServerConfig] = Field(
        description="MCP server configuration", alias="mcpServers"
    )

    model_config = {"populate_by_name": True}


# ============ Hooks Models ============


class HookExecution(BaseModel):
    """Hook execution configuration"""

    type: str = Field(default="command", description="Execution type")
    command: str = Field(description="Execution command")
    timeout: int = Field(default=30, description="Timeout in seconds")


class HookRule(BaseModel):
    """Hook rule"""

    matcher: str = Field(default="*", description="Event matcher")
    hooks: List[HookExecution] = Field(default_factory=list, description="Execution configuration list")


class HooksConfigResponse(BaseModel):
    """Hooks configuration response"""

    template_id: str = Field(description="Template ID", alias="templateId")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="Event mapping")

    model_config = {"populate_by_name": True}


class HooksConfigUpdateRequest(BaseModel):
    """Hooks configuration update request"""

    hooks: Dict[str, List[HookRule]] = Field(description="Event mapping")

    model_config = {"populate_by_name": True}


# ============ Commands Models ============


class TemplateCommandFile(BaseModel):
    """Template command file information"""

    file_name: str = Field(description="File name")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateCommandContent(BaseModel):
    """Template command file content"""

    file_name: str = Field(description="File name")
    content: str = Field(description="File content")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateCommandCreateRequest(BaseModel):
    """Create command file request"""

    file_name: str = Field(alias="fileName", description="File name (must end with .md)")
    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateCommandUpdateRequest(BaseModel):
    """Update command file request"""

    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateCommandResponse(BaseModel):
    """Command operation response"""

    success: bool = Field(description="Whether operation succeeded")
    data: Optional[TemplateCommandContent] = Field(default=None, description="Command file data")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")


class TemplateCommandListResponse(BaseModel):
    """Command file list response"""

    success: bool = Field(description="Whether operation succeeded")
    data: List[TemplateCommandFile] = Field(default_factory=list, description="File list")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")


# ============ Agents Models ============


class TemplateAgentFile(BaseModel):
    """Template agent file information"""

    file_name: str = Field(description="File name")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateAgentContent(BaseModel):
    """Template agent file content"""

    file_name: str = Field(description="File name")
    content: str = Field(description="File content")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateAgentCreateRequest(BaseModel):
    """Create agent file request"""

    file_name: str = Field(alias="fileName", description="File name (must end with .md)")
    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateAgentUpdateRequest(BaseModel):
    """Update agent file request"""

    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateAgentResponse(BaseModel):
    """Agent operation response"""

    success: bool = Field(description="Whether operation succeeded")
    data: Optional[TemplateAgentContent] = Field(default=None, description="Agent file data")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")


class TemplateAgentListResponse(BaseModel):
    """Agent file list response"""

    success: bool = Field(description="Whether operation succeeded")
    data: List[TemplateAgentFile] = Field(default_factory=list, description="File list")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")


# ============ Output Style Models ============


class TemplateOutputStyleFile(BaseModel):
    """Template output style file information"""

    file_name: str = Field(description="File name")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateOutputStyleContent(BaseModel):
    """Template output style file content"""

    file_name: str = Field(description="File name")
    content: str = Field(description="File content")
    size: int = Field(description="File size (bytes)")
    last_modified: datetime = Field(description="Last modification time")


class TemplateOutputStyleCreateRequest(BaseModel):
    """Create output style file request"""

    file_name: str = Field(alias="fileName", description="File name (must end with .md)")
    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleUpdateRequest(BaseModel):
    """Update output style file request"""

    content: str = Field(description="File content")

    model_config = {"populate_by_name": True}


class TemplateOutputStyleResponse(BaseModel):
    """Output style operation response"""

    success: bool = Field(description="Whether operation succeeded")
    data: Optional[TemplateOutputStyleContent] = Field(default=None, description="Output style file data")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")


class TemplateOutputStyleListResponse(BaseModel):
    """Output style file list response"""

    success: bool = Field(description="Whether operation succeeded")
    data: List[TemplateOutputStyleFile] = Field(default_factory=list, description="File list")
    message: Optional[str] = Field(default=None, description="Operation message")
    error: Optional[str] = Field(default=None, description="Error message")

