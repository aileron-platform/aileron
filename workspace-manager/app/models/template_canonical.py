"""Canonical template filesystem models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CanonicalTarget(str, Enum):
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class CapabilityState(str, Enum):
    NATIVE = "native"
    MAPPED = "mapped"
    EMULATED = "emulated"
    UNSUPPORTED = "unsupported"


class ImportSourceType(str, Enum):
    CLAUDE = "claude-code"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class CanonicalFeaturePath(BaseModel):
    path: str = Field(description="Feature path relative to template root")


class CanonicalTemplateIndex(BaseModel):
    id: str = Field(description="Template ID")
    name: str = Field(description="Template name")
    version: str = Field(description="Template version")
    schema_version: str = Field(alias="schemaVersion", description="Canonical schema version")
    description: Optional[str] = Field(default=None, description="Template description")
    supported_targets: List[CanonicalTarget] = Field(
        default_factory=list, alias="supportedTargets", description="Supported compile targets"
    )
    features: Dict[str, CanonicalFeaturePath] = Field(
        default_factory=dict, description="Feature path index"
    )
    capabilities: Dict[str, Dict[CanonicalTarget, CapabilityState]] = Field(
        default_factory=dict, description="Per-feature per-target capability matrix"
    )
    compile_hints: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, alias="compileHints", description="Target-specific compile hints"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible metadata")

    model_config = {"populate_by_name": True, "use_enum_values": True}


class CanonicalFrontmatterDocument(BaseModel):
    name: str = Field(description="Logical name derived from frontmatter or filename")
    path: str = Field(description="Path relative to template root")
    content: str = Field(description="Markdown content without frontmatter")
    frontmatter: Dict[str, Any] = Field(default_factory=dict, description="YAML frontmatter")


class CanonicalSkill(BaseModel):
    id: str = Field(description="Skill identifier")
    path: str = Field(description="Skill directory path relative to template root")
    skill_md_path: str = Field(alias="skillMdPath", description="Path to SKILL.md")
    content: str = Field(description="SKILL.md content without frontmatter")
    frontmatter: Dict[str, Any] = Field(default_factory=dict, description="Skill frontmatter")

    model_config = {"populate_by_name": True}


class CanonicalHook(BaseModel):
    id: str = Field(description="Hook identifier")
    path: str = Field(description="Hook yaml path relative to template root")
    event: str = Field(description="Lifecycle event name")
    matcher: Dict[str, Any] = Field(default_factory=dict, description="Hook matcher")
    action: Dict[str, Any] = Field(default_factory=dict, description="Hook action")
    timeout: Optional[int] = Field(default=None, description="Hook timeout seconds")
    failure_policy: Optional[str] = Field(default=None, alias="failurePolicy", description="Failure policy")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Original YAML payload")

    model_config = {"populate_by_name": True}


class CanonicalMcpServer(BaseModel):
    id: str = Field(description="MCP server identifier")
    path: str = Field(description="MCP yaml path relative to template root")
    transport: str = Field(description="Transport type")
    command: Optional[str] = Field(default=None, description="Command for stdio transport")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    url: Optional[str] = Field(default=None, description="URL for http/sse transport")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Original YAML payload")


class CanonicalResourceNode(BaseModel):
    path: str = Field(description="Path relative to template root")
    type: Literal["file", "directory"] = Field(description="Node type")
    children: List["CanonicalResourceNode"] = Field(default_factory=list, description="Nested nodes")


class CanonicalOutputStyle(BaseModel):
    path: str = Field(description="Path relative to template root")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured output style data")
    fallback_instruction: Optional[str] = Field(
        default=None, alias="fallbackInstruction", description="Fallback instruction text"
    )

    model_config = {"populate_by_name": True}


class CanonicalTemplate(BaseModel):
    root_path: str = Field(alias="rootPath", description="Template root path")
    index: CanonicalTemplateIndex = Field(description="Root template index")
    agents_md_path: Optional[str] = Field(default=None, alias="agentsMdPath", description="agents.md path")
    agents_md_content: Optional[str] = Field(default=None, alias="agentsMdContent", description="agents.md content")
    output_style: Optional[CanonicalOutputStyle] = Field(default=None, alias="outputStyle")
    skills: List[CanonicalSkill] = Field(default_factory=list, description="Canonical skills")
    commands: List[CanonicalFrontmatterDocument] = Field(default_factory=list, description="Canonical commands")
    agents: List[CanonicalFrontmatterDocument] = Field(default_factory=list, description="Canonical agents")
    hooks: List[CanonicalHook] = Field(default_factory=list, description="Canonical hooks")
    mcp_servers: List[CanonicalMcpServer] = Field(default_factory=list, alias="mcpServers")
    resources: List[CanonicalResourceNode] = Field(default_factory=list, description="Canonical resources tree")

    model_config = {"populate_by_name": True}


class CompiledTemplateFile(BaseModel):
    path: str = Field(description="Target file path")
    source: str = Field(description="Canonical source reference")
    content: str = Field(description="Compiled file content")


class CompileIssue(BaseModel):
    feature: str = Field(description="Feature name")
    target: CanonicalTarget = Field(description="Target CLI")
    message: str = Field(description="Issue message")

    model_config = {"use_enum_values": True}


class InstallPlan(BaseModel):
    target: CanonicalTarget = Field(description="Target CLI")
    files: List[CompiledTemplateFile] = Field(default_factory=list, description="Files to install")
    warnings: List[CompileIssue] = Field(default_factory=list, description="Compile warnings")
    unsupported: List[CompileIssue] = Field(default_factory=list, description="Unsupported features")
    degradation_notes: List[CompileIssue] = Field(
        default_factory=list, alias="degradationNotes", description="Feature degradation notes"
    )
    install_hints: Dict[str, Any] = Field(
        default_factory=dict, alias="installHints", description="Target install hints"
    )
    source_hash: Optional[str] = Field(default=None, alias="sourceHash", description="Canonical source hash")
    cache_key: Optional[str] = Field(default=None, alias="cacheKey", description="Compile cache key")

    model_config = {"populate_by_name": True, "use_enum_values": True}


class ImportedTemplateMetadata(BaseModel):
    id: str = Field(description="Imported template ID")
    name: str = Field(description="Imported template name")
    version: str = Field(default="1.0.0", description="Imported template version")
    source_type: ImportSourceType = Field(alias="sourceType", description="Detected source type")
    description: Optional[str] = Field(default=None, description="Imported template description")
    author_name: str = Field(default="Unknown", alias="authorName", description="Author name")
    author_email: Optional[str] = Field(default=None, alias="authorEmail", description="Author email")
    author_url: Optional[str] = Field(default=None, alias="authorUrl", description="Author URL")
    status: Optional[str] = Field(default=None, description="Original source status")
    keywords: List[str] = Field(default_factory=list, description="Imported keywords")
    init_commands: Optional[str] = Field(default=None, alias="initCommands", description="Imported init commands")

    model_config = {"populate_by_name": True, "use_enum_values": True}


class ImportedTemplateAsset(BaseModel):
    path: str = Field(description="Asset path relative to source root")
    content: bytes = Field(description="Raw asset content")


class ImportedTemplate(BaseModel):
    root_path: str = Field(alias="rootPath", description="Imported source root path")
    metadata: ImportedTemplateMetadata = Field(description="Imported metadata")
    agents_md_content: Optional[str] = Field(default=None, alias="agentsMdContent", description="Canonical agents.md content")
    output_style: Optional[CanonicalOutputStyle] = Field(default=None, alias="outputStyle")
    skills: List[CanonicalSkill] = Field(default_factory=list, description="Imported skills")
    commands: List[CanonicalFrontmatterDocument] = Field(default_factory=list, description="Imported commands")
    agents: List[CanonicalFrontmatterDocument] = Field(default_factory=list, description="Imported agents")
    hooks: List[CanonicalHook] = Field(default_factory=list, description="Imported hooks")
    mcp_servers: List[CanonicalMcpServer] = Field(default_factory=list, alias="mcpServers")
    resources: List[ImportedTemplateAsset] = Field(default_factory=list, description="Imported extra resources")
    warnings: List[str] = Field(default_factory=list, description="Import warnings")
    unresolved_items: List[str] = Field(
        default_factory=list, alias="unresolvedItems", description="Unresolved import items"
    )

    model_config = {"populate_by_name": True, "use_enum_values": True}


CanonicalResourceNode.model_rebuild()
