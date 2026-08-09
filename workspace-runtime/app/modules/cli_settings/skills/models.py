"""CLI Skills data models."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.modules.file_system.models import (
    FileContentResponse,
    FileNode,
    FileTreeResponse,
)


class SkillFileNode(FileNode):
    """Skill tree node."""

    children: List["SkillFileNode"] = Field(  # type: ignore[assignment]
        default_factory=list
    )
    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None


class SkillFileTreeResponse(FileTreeResponse):
    """Skill tree response with recursive nodes."""

    nodes: List[SkillFileNode] = Field(default_factory=list)  # type: ignore[assignment]


class SkillFileContentResponse(FileContentResponse):
    """Skill content response."""

    read_only: bool | None = Field(default=None, alias="readOnly")
    editable: bool | None = None


class PluginSkillInfo(BaseModel):
    """Plugin Skill information"""

    plugin_id: str = Field(
        ..., alias="pluginId", description="Plugin ID (format: name@marketplace)"
    )
    plugin_name: str = Field(..., alias="pluginName", description="Plugin name")
    marketplace_name: str = Field(
        ..., alias="marketplaceName", description="Marketplace name"
    )
    skill_name: str = Field(..., alias="skillName", description="Skill name")
    skill_path: str = Field(..., alias="skillPath", description="Skill directory path")

    model_config = {"populate_by_name": True}


class PluginSkillsResponse(BaseModel):
    """Plugin Skills list response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    plugins: List[PluginSkillInfo] = Field(..., description="Plugin Skills list")

    model_config = {"populate_by_name": True}
