"""CLI Skills 服務

繼承 BaseFileService，為各 CLI 工具提供 skills 檔案管理。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

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
    """CLI Skills 檔案服務

    支援的 scope:
    - project: 專案級別
    - user: 使用者級別
    - plugin: 插件級別（僅 Claude，唯讀）
    """

    VALID_SCOPES = {SkillScope.PROJECT, SkillScope.USER, SkillScope.PLUGIN}

    def __init__(self, config: SkillToolConfig, workspace_id: str):
        # 不需要 root_path，使用 scope 來解析路徑
        super().__init__(root_path=Path("/tmp"))
        self._config = config
        self._workspace_id = workspace_id

    def _scope_root(self, scope: str) -> Path:
        """取得指定 scope 的 skills 根目錄"""
        if scope == SkillScope.USER:
            return self._config.user_root
        # PROJECT (and PLUGIN for claude handled separately)
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
        if scope == SkillScope.PLUGIN:
            return self._config.supports_plugin
        return scope in self.VALID_SCOPES

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        return scope == SkillScope.PLUGIN

    # --- Plugin Skills (Claude only) ---

    def get_plugin_skills(self) -> List[Dict]:
        """取得所有插件的 Skills（僅 Claude 支援）"""
        if not self._config.supports_plugin:
            return []

        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.settings.service import SettingsService

        plugin_skills = []
        try:
            settings_service = SettingsService()
            loader = get_plugin_loader(settings_service)
            skills = loader.load_plugin_skills(self._workspace_id)

            for skill in skills:
                plugin_skills.append({
                    "pluginId": f"{skill.plugin_name}@{skill.marketplace_name}",
                    "pluginName": skill.plugin_name,
                    "marketplaceName": skill.marketplace_name,
                    "skillName": skill.skill_name,
                    "skillPath": skill.directory_path,
                })
        except Exception:
            logger.warning("Failed to load plugin skills", exc_info=True)

        return plugin_skills
