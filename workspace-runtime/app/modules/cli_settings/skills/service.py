"""CLI Skills service

Inherits BaseFileService to provide skills file management for each CLI tool.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from app.config.settings import get_workspace_path
from app.modules.file_system import (
    BaseFileService,
    FileManagementException,
    InvalidScopeException,
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
        if scope == SkillScope.USER:
            return self._config.user_root
        workspace_root = Path(get_workspace_path())
        return workspace_root / self._config.project_dot_dir / self._config.skill_dir_name

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        if not scope:
            scope = SkillScope.PROJECT

        if not self.validate_scope(scope):
            raise InvalidScopeException(f"Invalid scope: {scope}")

        scope_root = self._scope_root(scope)
        validated_path = self._validate_path(relative_path)
        return scope_root / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        if not scope:
            return True
        return scope in self.VALID_SCOPES

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        return False
