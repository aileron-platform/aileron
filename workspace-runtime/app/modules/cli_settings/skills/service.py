"""CLI Skills service

Inherits BaseFileService to provide skills file management for each CLI tool.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import yaml

from app.config.settings import get_workspace_path
from app.modules.cli_settings.gemini.extension_resources import GeminiExtensionResourceResolver, resolve_workspace_root
from app.modules.file_system import (
    BaseFileService,
    FileManagementException,
    InvalidScopeException,
    ReadonlyScopeException,
)

from .config import SkillScope, SkillToolConfig

logger = logging.getLogger(__name__)


class CliSkillService(BaseFileService):
    """CLI Skills file service

    Supported scopes:
    - project: Project level
    - user: User level
    """

    VALID_SCOPES = {SkillScope.PROJECT, SkillScope.USER}

    def __init__(self, config: SkillToolConfig, workspace_id: str):
        # No need for root_path, use scope to resolve paths
        super().__init__(root_path=Path("/tmp"))
        self._config = config
        self._workspace_id = workspace_id

    def _scope_root(self, scope: str) -> Path:
        """Get skills root directory for specified scope"""
        if scope == SkillScope.EXTENSION:
            raise ReadonlyScopeException(scope)
        if scope == SkillScope.USER:
            return self._config.user_root
        workspace_root = Path(get_workspace_path())
        return workspace_root / self._config.project_dot_dir / self._config.skill_dir_name

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        if not scope:
            scope = SkillScope.PROJECT

        if not self.validate_scope(scope):
            raise InvalidScopeException(f"Invalid scope: {scope}")

        if scope == SkillScope.EXTENSION:
            skill = self._find_extension_skill(relative_path)
            if skill is None:
                raise InvalidScopeException(f"Invalid extension skill path: {relative_path}")
            return Path(skill.path)

        scope_root = self._scope_root(scope)
        validated_path = self._validate_path(relative_path)
        return scope_root / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        if not scope:
            return True
        if scope == SkillScope.EXTENSION:
            return self._config.tool.value == "gemini"
        return scope in self.VALID_SCOPES

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        return scope == SkillScope.EXTENSION

    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> dict:
        if scope == SkillScope.EXTENSION:
            if not self.validate_scope(scope):
                raise InvalidScopeException(f"Invalid scope: {scope}")
            now = datetime.now(timezone.utc).isoformat()
            nodes = []
            for package, skill in GeminiExtensionResourceResolver().enabled_skills(resolve_workspace_root()):
                skill_dir_path = skill.name
                skill_file_path = f"{skill_dir_path}/SKILL.md"
                metadata = {
                    "extensionName": package.name,
                    "extensionVersion": package.version,
                }
                nodes.append(
                    {
                        "id": skill_dir_path,
                        "name": skill.name,
                        "path": skill_dir_path,
                        "type": "directory",
                        "scope": SkillScope.EXTENSION.value,
                        "size": 0,
                        "updatedAt": now,
                        "depth": 0,
                        "children": [
                            {
                                "id": skill_file_path,
                                "name": "SKILL.md",
                                "path": skill_file_path,
                                "type": "file",
                                "scope": SkillScope.EXTENSION.value,
                                "size": len(skill.content.encode("utf-8")),
                                "updatedAt": now,
                                "depth": 1,
                                "children": [],
                                "hasChildren": False,
                                "extension": ".md",
                                "fileType": "markdown",
                                "metadata": metadata,
                            }
                        ],
                        "hasChildren": True,
                        "metadata": metadata,
                    }
                )
            return {"path": path, "scope": scope, "nodes": nodes, "total": len(nodes) * 2}
        return super().get_tree(path, scope, include_hidden, max_depth)

    def read_file(self, path: str, scope: Optional[str] = None) -> dict:
        if scope == SkillScope.EXTENSION:
            if not self.validate_scope(scope):
                raise InvalidScopeException(f"Invalid scope: {scope}")
            match = self._find_extension_skill_with_package(path)
            if match is None:
                raise InvalidScopeException(f"Invalid extension skill path: {path}")
            package, skill = match
            content = skill.content
            now = datetime.now(timezone.utc).isoformat()
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            return {
                "path": path,
                "scope": scope,
                "content": content,
                "size": len(content.encode("utf-8")),
                "updatedAt": now,
                "versionId": f"extension:{package.name}:{skill.name}:{package.version}",
                "contentHash": f"sha256:{content_hash}",
                "metadata": {
                    "extensionName": package.name,
                    "extensionVersion": package.version,
                },
            }
        return super().read_file(path, scope)

    def _find_extension_skill(self, relative_path: str):
        match = self._find_extension_skill_with_package(relative_path)
        return match[1] if match else None

    def _find_extension_skill_with_package(self, relative_path: str):
        normalized = relative_path.strip("/")
        for package, skill in GeminiExtensionResourceResolver().enabled_skills(resolve_workspace_root()):
            if normalized in {f"{package.name}/{skill.name}/SKILL.md", f"{skill.name}/SKILL.md", "SKILL.md"}:
                return package, skill
        return None
