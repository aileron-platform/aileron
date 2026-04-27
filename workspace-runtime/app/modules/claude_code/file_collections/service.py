"""File Collections Service Layer - Refactored Version

Inherits from BaseFileService, supports Skills and Scripts file management
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.modules.file_system import (
    BaseFileService,
    FileNode,
    FileManagementException,
    InvalidScopeException,
    ReadonlyScopeException,
)
from ..common import DocumentScope, resolve_scope_root
from ..plugins.loader import get_plugin_loader
from ..settings.service import SettingsService
from .models import (
    FileCollectionType,
    FileType,
    PluginSkillInfo,
)


class FileCollectionService(BaseFileService):
    """File Collection Service - Unified handling of Skills and Scripts
    
    Supported scopes:
    - project: Project level
    - user: User level
    - plugin: Plugin level (read-only)
    """

    # File type mapping
    FILE_TYPE_MAP = {
        ".md": FileType.MARKDOWN,
        ".ts": FileType.TYPESCRIPT,
        ".js": FileType.JAVASCRIPT,
        ".yaml": FileType.YAML,
        ".yml": FileType.YAML,
        ".json": FileType.JSON,
        ".py": FileType.PYTHON,
        ".sh": FileType.SHELL,
    }

    # Valid scope values
    VALID_SCOPES = {DocumentScope.PROJECT, DocumentScope.USER, DocumentScope.PLUGIN}

    def __init__(self, collection_type: FileCollectionType, workspace_id: str):
        """Initialize service

        Args:
            collection_type: Collection type (SKILLS or SCRIPTS)
            workspace_id: Workspace ID
        """
        # No need for root_path, as we use scope to resolve paths
        super().__init__(root_path=Path("/tmp"))  # Temporary path, will not be used
        
        self.collection_type = collection_type
        self.workspace_id = workspace_id
        self.settings_service = SettingsService()
        self.plugin_loader = get_plugin_loader(self.settings_service)

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """Resolve scope and relative path to actual file system path
        
        Args:
            scope: Scope identifier (project/user/plugin)
            relative_path: Relative path
            
        Returns:
            Actual file system path
            
        Raises:
            InvalidScopeException: Invalid scope
        """
        # Use project scope by default
        if not scope:
            scope = DocumentScope.PROJECT
        
        # Validate scope
        if not self.validate_scope(scope):
            raise InvalidScopeException(f"Invalid scope: {scope}")
        
        # Resolve scope root directory
        scope_root = resolve_scope_root(self.workspace_id, scope)
        
        # Add subdirectory based on collection type
        if self.collection_type == FileCollectionType.SKILLS:
            collection_dir = scope_root / "skills"
        else:  # SCRIPTS
            collection_dir = scope_root / "scripts"
        
        # Validate and resolve relative path
        validated_path = self._validate_path(relative_path)
        
        return collection_dir / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        """Validate if scope is valid
        
        Args:
            scope: Scope identifier
            
        Returns:
            Whether valid
        """
        if not scope:
            return True  # None will be converted to default project
        
        return scope in self.VALID_SCOPES

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """Check if scope is read-only
        
        Args:
            scope: Scope identifier
            
        Returns:
            Whether read-only
        """
        return scope == DocumentScope.PLUGIN

    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> Dict:
        """Get file tree and embed front matter metadata for SKILL.md nodes"""
        result = super().get_tree(path, scope, include_hidden, max_depth)
        if self.collection_type == FileCollectionType.SKILLS:
            self._enrich_skill_nodes(result["nodes"], scope)
        return result

    def _enrich_skill_nodes(self, nodes: List[Dict], scope: Optional[str]) -> None:
        """Recursively traverse nodes and embed skillName/skillDescription for SKILL.md file nodes"""
        for node in nodes:
            if node.get("type") == "file" and node.get("name") == "SKILL.md":
                try:
                    fs_path = self.resolve_scope_path(scope, node["path"])
                    content = fs_path.read_text(encoding="utf-8")
                    front_matter, _ = self._parse_front_matter(content)
                    if front_matter:
                        skill_name = front_matter.get("name")
                        skill_description = front_matter.get("description")
                        if skill_name:
                            node["skillName"] = str(skill_name)
                        if skill_description:
                            node["skillDescription"] = str(skill_description)
                except Exception:
                    pass
            elif node.get("type") == "directory" and node.get("children"):
                self._enrich_skill_nodes(node["children"], scope)

    def _get_file_type(self, file_path: Path) -> FileType:
        """Get file type"""
        suffix = file_path.suffix.lower()
        return self.FILE_TYPE_MAP.get(suffix, FileType.OTHER)

    def _parse_front_matter(self, content: str) -> tuple[Optional[Dict], str]:
        """Parse Front Matter
        
        Args:
            content: File content
            
        Returns:
            (front_matter_dict, content_without_front_matter)
        """
        # Check if YAML Front Matter exists
        if not content.startswith("---\n"):
            return None, content
        
        # Find second ---
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            return None, content
        
        # Extract Front Matter
        front_matter_str = content[4:end_marker]
        remaining_content = content[end_marker + 5:]
        
        try:
            front_matter = yaml.safe_load(front_matter_str)
            return front_matter, remaining_content
        except yaml.YAMLError:
            return None, content

    def get_tree_with_metadata(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: int = 1
    ) -> List[FileNode]:
        """Get file tree with Front Matter metadata
        
        Args:
            path: Target path
            scope: Scope identifier
            include_hidden: Whether to include hidden files
            max_depth: Maximum depth
            
        Returns:
            File node list (with metadata)
        """
        # Use parent class get_tree method
        tree_response = self.get_tree(path, scope, include_hidden, max_depth)
        nodes = tree_response["nodes"]
        
        # Add Front Matter metadata to each file node
        for node in nodes:
            if node["type"] == "file":
                try:
                    # Read file content
                    content_response = self.read_file(node["path"], scope)
                    content = content_response["content"]
                    
                    # Parse Front Matter
                    front_matter, _ = self._parse_front_matter(content)
                    
                    if front_matter:
                        # Add Front Matter to metadata
                        if node.get("metadata") is None:
                            node["metadata"] = {}
                        node["metadata"]["frontMatter"] = front_matter
                        
                        # Add file type
                        file_type = self._get_file_type(Path(node["path"]))
                        node["fileType"] = file_type.value
                        
                except Exception:
                    # If read fails, skip metadata
                    pass
        
        return nodes

    def get_plugin_skills(self) -> List[PluginSkillInfo]:
        """Get all plugin Skills
        
        Returns:
            Plugin Skills list
        """
        plugin_skills = []
        
        try:
            # Get all installed plugins
            plugins = self.plugin_loader.get_installed_plugins()
            
            for plugin in plugins:
                # Get plugin skills directory
                plugin_root = resolve_scope_root(self.workspace_id, DocumentScope.PLUGIN)
                skills_dir = plugin_root / plugin.name / "skills"
                
                if not skills_dir.exists():
                    continue
                
                # Scan skills directory
                for skill_file in skills_dir.glob("*.md"):
                    try:
                        content = skill_file.read_text(encoding="utf-8")
                        front_matter, _ = self._parse_front_matter(content)
                        
                        plugin_skills.append(PluginSkillInfo(
                            pluginName=plugin.name,
                            pluginVersion=plugin.version,
                            skillName=skill_file.stem,
                            skillPath=str(skill_file.relative_to(plugin_root)),
                            description=front_matter.get("description", "") if front_matter else "",
                            metadata=front_matter
                        ))
                    except Exception:
                        # Skip unreadable files
                        continue
        
        except Exception:
            # If getting plugins fails, return empty list
            pass
        
        return plugin_skills


__all__ = ["FileCollectionService"]

