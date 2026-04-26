"""Template models"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .common import TimestampMixin


class TemplateAuthor(BaseModel):
    """Template author information"""

    name: str = Field(description="Author name")
    email: Optional[str] = Field(default=None, description="Author email")
    url: Optional[str] = Field(default=None, description="Author personal page")


class TemplateCreate(BaseModel):
    """Create template request"""

    template_id: str = Field(description="Template identifier (kebab-case, English only)", alias="templateId")
    name: str = Field(description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    version: Optional[str] = Field(default="1.0.0", description="Version number")
    author: TemplateAuthor = Field(description="Author information")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Keyword array")
    cli_type: Literal["claude-code", "codex", "gemini", "opencode"] = Field(
        default="claude-code", description="CLI Type"
    )
    status: Literal["draft", "released"] = Field(default="draft", description="Template status")
    init_commands: Optional[str] = Field(default=None, description="Initialize command", alias="initCommands")

    model_config = {"populate_by_name": True}


class TemplateUpdate(BaseModel):
    """Update template request"""

    name: Optional[str] = Field(default=None, description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    version: Optional[str] = Field(default=None, description="Version number")
    author: Optional[TemplateAuthor] = Field(default=None, description="Author information")
    keywords: Optional[List[str]] = Field(default=None, description="Keyword array")
    categoryId: Optional[str] = Field(default=None, description="Category ID", alias="categoryId")
    cli_type: Optional[Literal["claude-code", "codex", "gemini", "opencode"]] = Field(
        default=None, description="CLI Type"
    )
    status: Optional[Literal["draft", "released"]] = Field(default=None, description="Template status")
    init_commands: Optional[str] = Field(default=None, description="Initialize command", alias="initCommands")

    model_config = {"populate_by_name": True}


class TemplateMcpServer(BaseModel):
    """MCP server configuration"""

    id: str = Field(description="Server ID")
    name: str = Field(description="Server name")
    type: Literal["stdio", "http", "sse"] = Field(default="stdio", description="Transport type")
    command: Optional[str] = Field(default=None, description="Execution command")
    args: Optional[List[str]] = Field(default=None, description="Command parameters")
    url: Optional[str] = Field(default=None, description="Server URL")
    description: Optional[str] = Field(default=None, description="Server description")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")


class TemplateCommand(BaseModel):
    """Command configuration"""

    id: str = Field(description="Command ID")
    fileName: str = Field(description="File name")
    description: Optional[str] = Field(default=None, description="Command description")
    content: str = Field(description="Command content")


class TemplateHook(BaseModel):
    """Hook configuration"""

    id: str = Field(description="Hook ID")
    name: str = Field(description="Hook name")
    event: str = Field(description="Event name")
    matcher: Optional[str] = Field(default=None, description="Matcher")
    action: Literal["command", "script"] = Field(default="command", description="Action type")
    command: Optional[str] = Field(default=None, description="Execution command")
    script: Optional[str] = Field(default=None, description="Script content")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")


class TemplateAgent(BaseModel):
    """Agent configuration"""

    id: str = Field(description="Agent ID")
    fileName: str = Field(description="File name")
    description: Optional[str] = Field(default=None, description="Description")
    content: str = Field(description="File content")


class TemplateOutputStyle(BaseModel):
    """Output style configuration"""

    id: str = Field(description="Style ID")
    fileName: str = Field(description="File name")
    description: Optional[str] = Field(default=None, description="Description")
    content: str = Field(description="File content")


class TemplateFileNode(BaseModel):
    """File node"""

    id: str = Field(description="Node ID")
    name: str = Field(description="Node name")
    path: str = Field(description="File path")
    type: Literal["file", "directory"] = Field(description="Node type")
    size: Optional[int] = Field(default=None, description="File size")
    content: Optional[str] = Field(default=None, description="File content")
    children: Optional[List["TemplateFileNode"]] = Field(default=None, description="Child nodes")


class Template(TimestampMixin):
    """Template response model"""

    id: str = Field(description="Template ID")
    name: str = Field(description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    version: str = Field(default="1.0.0", description="Version number")
    author: TemplateAuthor = Field(description="Author information")
    keywords: List[str] = Field(default_factory=list, description="Keyword array")
    categoryId: Optional[str] = Field(default=None, description="Category ID", alias="categoryId")
    cliType: str = Field(default="claude-code", description="CLI Type", alias="cliType")
    status: str = Field(default="draft", description="Template status")
    documentation: Optional[str] = Field(default=None, description="Documentation")
    agentsMd: Optional[str] = Field(default=None, description="AGENTS.md content", alias="agentsMd")
    isActive: bool = Field(default=True, description="Is active", alias="isActive")
    storage_path: Optional[str] = Field(default=None, description="Storage path", alias="storagePath")
    initCommands: Optional[str] = Field(default=None, description="Initialize command", alias="initCommands")

    # Configuration data
    mcpServers: List[TemplateMcpServer] = Field(default_factory=list, description="MCP servers", alias="mcpServers")
    commands: List[TemplateCommand] = Field(default_factory=list, description="Commands", alias="commands")
    hooks: List[TemplateHook] = Field(default_factory=list, description="Hooks", alias="hooks")
    agents: List[TemplateAgent] = Field(default_factory=list, description="Agents", alias="agents")
    outputStyle: List[TemplateOutputStyle] = Field(default_factory=list, description="Output style", alias="outputStyle")
    scripts: List[TemplateFileNode] = Field(default_factory=list, description="Scripts", alias="scripts")
    skills: List[TemplateFileNode] = Field(default_factory=list, description="Skills", alias="skills")

    model_config = {"from_attributes": True, "populate_by_name": True}


class TemplateCanonicalUpdate(BaseModel):
    """Canonical template editor update request"""

    name: str = Field(description="Template name")
    description: Optional[str] = Field(default=None, description="Template description")
    version: str = Field(description="Version number")
    author: TemplateAuthor = Field(description="Author information")
    keywords: List[str] = Field(default_factory=list, description="Keyword array")
    categoryId: Optional[str] = Field(default=None, description="Category ID", alias="categoryId")
    documentation: Optional[str] = Field(default=None, description="Documentation")
    agentsMd: Optional[str] = Field(default=None, description="AGENTS.md canonical content", alias="agentsMd")
    initCommands: Optional[str] = Field(default=None, description="Initialize command", alias="initCommands")
    mcpServers: List[TemplateMcpServer] = Field(default_factory=list, description="MCP servers", alias="mcpServers")
    commands: List[TemplateCommand] = Field(default_factory=list, description="Commands", alias="commands")
    hooks: List[TemplateHook] = Field(default_factory=list, description="Hooks", alias="hooks")
    agents: List[TemplateAgent] = Field(default_factory=list, description="Agents", alias="agents")
    outputStyle: List[TemplateOutputStyle] = Field(default_factory=list, description="Output style", alias="outputStyle")
    skills: List[TemplateFileNode] = Field(default_factory=list, description="Skills", alias="skills")
    scripts: List[TemplateFileNode] = Field(default_factory=list, description="Scripts", alias="scripts")
    isActive: bool = Field(default=True, description="Is active", alias="isActive")
    cliType: Optional[Literal["claude-code", "codex", "gemini", "opencode"]] = Field(
        default=None,
        description="Default CLI Type",
        alias="cliType",
    )

    model_config = {"populate_by_name": True}


class TemplateListResponse(BaseModel):
    """Template list response"""

    items: List[Template]
    total: int
    page: Optional[int] = Field(default=None, description="Current page number")
    limit: Optional[int] = Field(default=None, description="Items per page")
    total_pages: Optional[int] = Field(default=None, description="Total pages", alias="totalPages")

    model_config = {"populate_by_name": True}


class TemplateFeatureListResponse(BaseModel):
    """Return available feature key list by CLI type"""

    items: list[str]


class TemplateCategory(BaseModel):
    """Template category"""

    id: str = Field(description="Category ID")
    name: str = Field(description="Category name")
    description: Optional[str] = Field(default=None, description="Category description")
    icon: Optional[str] = Field(default=None, description="Icon name")
    sortOrder: int = Field(default=0, description="Sort order", alias="sortOrder")
    isActive: bool = Field(default=True, description="Is active", alias="isActive")

    model_config = {"from_attributes": True, "populate_by_name": True}


class TemplateCategoryListResponse(BaseModel):
    """Template category list response"""

    items: List[TemplateCategory]


# ============ Feature Index Related Models ============

class TemplateFeatureInfo(BaseModel):
    """Template feature information"""

    templateId: str = Field(description="Template ID", alias="templateId")
    features: List[str] = Field(description="Feature list")
    indexedAt: Optional[str] = Field(default=None, description="Index time", alias="indexedAt")

    model_config = {"populate_by_name": True}


class FeatureStatItem(BaseModel):
    """Single feature statistics information"""

    name: str = Field(description="Feature name")
    count: int = Field(description="Number of templates with this feature")
    description: Optional[str] = Field(default=None, description="Feature description")


class FeatureStatsResponse(BaseModel):
    """Feature statistics response"""

    stats: Dict[str, FeatureStatItem] = Field(description="Feature statistics information")
