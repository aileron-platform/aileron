"""File Collections Data Models"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FileCollectionType(str, Enum):
    """File collection type"""

    SKILLS = "skills"
    PLUGINS = "plugins"
    SCRIPTS = "scripts"


class FileType(str, Enum):
    """Supported file types"""

    MARKDOWN = "markdown"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    YAML = "yaml"
    JSON = "json"
    PYTHON = "python"
    SHELL = "shell"
    OTHER = "other"


class FileSummary(BaseModel):
    """File summary"""

    file_name: str = Field(..., alias="fileName", description="File name")
    file_path: str = Field(..., alias="filePath", description="File relative path (without scope prefix)")
    file_type: FileType = Field(..., alias="fileType", description="File type")
    scope: str = Field(..., description="File scope: project, user, plugin")
    size_bytes: int = Field(..., alias="sizeBytes", description="File size (bytes)")
    size_label: str = Field(..., alias="sizeLabel", description="File size (human-readable)")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Update time")

    # Front Matter metadata (if Markdown)
    name: Optional[str] = Field(None, description="Display name (from Front Matter)")
    description: Optional[str] = Field(None, description="Description (from Front Matter)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Other metadata")

    model_config = {"populate_by_name": True}


class FileDetail(FileSummary):
    """File detail information"""

    content: str = Field(..., description="File content")


class FileTreeNode(BaseModel):
    """File tree node"""

    id: str = Field(..., description="Node unique identifier")
    name: str = Field(..., description="Node name")
    path: str = Field(..., description="Node path")
    type: str = Field(..., description="Node type: file or directory")
    file_type: Optional[FileType] = Field(None, alias="fileType", description="File type (files only)")
    scope: Optional[str] = Field(None, description="File scope: project, user, plugin (files only)")
    children: Optional[List[FileTreeNode]] = Field(None, description="Child nodes (directories only)")
    size_bytes: Optional[int] = Field(None, alias="sizeBytes", description="File size (files only)")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="Update time (files only)")

    model_config = {"populate_by_name": True}


class FileCollectionResponse(BaseModel):
    """File collection response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="Collection type")
    files: List[FileSummary] = Field(..., description="File list")
    tree: List[FileTreeNode] = Field(..., description="File tree")

    model_config = {"populate_by_name": True}


class FileResponse(BaseModel):
    """Single file response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="Collection type")
    file: FileDetail = Field(..., description="File detail information")

    model_config = {"populate_by_name": True}


class FileCreateRequest(BaseModel):
    """Create file request"""

    file_name: str = Field(..., alias="fileName", description="File name (can include subdirectory path, e.g., folder/file.md)")
    content: str = Field(..., description="File content")
    scope: Optional[str] = Field("project", description="File scope: project, user (default: project)")

    model_config = {"populate_by_name": True}


class FileUpdateRequest(BaseModel):
    """Update file request"""

    content: str = Field(..., description="File content")
    scope: Optional[str] = Field(None, description="File scope: project, user (optional, used to specify which scope's file to update)")


class FileMoveRequest(BaseModel):
    """Move/rename file request"""

    source_path: str = Field(..., alias="sourcePath", description="Source file relative path (without scope prefix)")
    dest_path: str = Field(..., alias="destPath", description="Destination file relative path (without scope prefix)")

    model_config = {"populate_by_name": True}


class FileCopyRequest(BaseModel):
    """Copy file request"""

    source_path: str = Field(..., alias="sourcePath", description="Source file relative path (without scope prefix)")
    dest_path: str = Field(..., alias="destPath", description="Destination file relative path (without scope prefix)")

    model_config = {"populate_by_name": True}


class FileDeleteResponse(BaseModel):
    """Delete file response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="Collection type")
    file_path: str = Field(..., alias="filePath", description="File path")
    deleted: bool = Field(..., description="Whether successfully deleted")

    model_config = {"populate_by_name": True}


class PluginSkillInfo(BaseModel):
    """Plugin Skill information"""

    plugin_id: str = Field(..., alias="pluginId", description="Plugin ID (format: name@marketplace)")
    plugin_name: str = Field(..., alias="pluginName", description="Plugin name")
    marketplace_name: str = Field(..., alias="marketplaceName", description="Marketplace name")
    skill_name: str = Field(..., alias="skillName", description="Skill name")
    skill_path: str = Field(..., alias="skillPath", description="Skill directory path")

    model_config = {"populate_by_name": True}


class PluginSkillsResponse(BaseModel):
    """Plugin Skills list response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    plugins: List[PluginSkillInfo] = Field(..., description="Plugin Skills list")

    model_config = {"populate_by_name": True}

