"""CLI Skills service

Inherits BaseFileService to provide skills file management for each CLI tool.
Plugin scope and SKILL.md front-matter enrichment are only active when the
tool config sets supports_plugin=True (currently Claude Code only).
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.config.settings import get_workspace_path
from app.modules.cli_settings.cache import ProcessTTLCache
from app.modules.file_system.base_operations import BaseFileService
from app.modules.file_system.exceptions import (
    FileManagementException,
    InvalidScopeException,
)

from .config import SkillScope, SkillToolConfig
from .models import PluginSkillInfo

logger = logging.getLogger(__name__)
_tree_cache: ProcessTTLCache[
    tuple[str, str, str, str, bool, int | None],
    dict,
] = ProcessTTLCache()


def clear_skill_tree_cache(
    *,
    tool: str | None = None,
    workspace_id: str | None = None,
    scope: str | None = None,
) -> None:
    """Clear completed skill tree summaries for one identity."""

    _tree_cache.clear(
        lambda key: (tool is None or key[0] == tool)
        and (workspace_id is None or key[1] == workspace_id)
        and (scope is None or scope == "all" or key[3] in {scope, "all"})
    )


class CliSkillService(BaseFileService):
    """CLI Skills file service

    Supported scopes:
    - project: Project level
    - user: User level
    - plugin: Plugin level, read-only (only when config.supports_plugin)
    """

    def __init__(
        self,
        config: SkillToolConfig,
        workspace_id: str,
    ):
        # No need for root_path, use scope to resolve paths
        super().__init__(root_path=Path("/tmp"))
        self._config = config
        self._workspace_id = workspace_id
        self._valid_scopes = {SkillScope.PROJECT, SkillScope.USER}
        if config.supports_plugin:
            self._valid_scopes.add(SkillScope.PLUGIN)

    def _plugin_loader(self) -> Any:
        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.settings.dependencies import get_settings_service

        return get_plugin_loader(get_settings_service())

    def clear_tree_cache(self, scope: str | None = None) -> None:
        """Invalidate cached trees after a successful mutation."""

        clear_skill_tree_cache(
            tool=self._config.tool.value,
            workspace_id=self._workspace_id,
            scope=scope,
        )
        if self._config.tool.value == "codex":
            from app.modules.cli_settings.codex.settings import (
                CodexSettingsIntent,
                get_codex_agent_settings,
            )

            get_codex_agent_settings().execute(
                CodexSettingsIntent.REFRESH_CACHE,
                workspace_id=self._workspace_id,
                capability="skills",
                scope=scope,
            )

    def _scope_root(self, scope: str) -> Path:
        """Get skills root directory for specified scope"""
        if scope == SkillScope.USER:
            return self._config.user_root
        workspace_root = Path(get_workspace_path())
        return (
            workspace_root / self._config.project_dot_dir / self._config.skill_dir_name
        )

    @staticmethod
    def _validate_relative_path(relative_path: str) -> Path:
        path = Path(relative_path.lstrip("/") or ".")
        if any(part in {"..", ""} for part in path.parts):
            raise FileManagementException(
                "INVALID_PATH",
                "Path traversal not allowed",
                {"path": relative_path},
                400,
            )
        return path

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        if not scope:
            scope = SkillScope.PROJECT

        if not self.validate_scope(scope):
            raise InvalidScopeException(f"Invalid scope: {scope}")

        if scope == SkillScope.PLUGIN and self._config.supports_plugin:
            return self._resolve_plugin_skill_path(relative_path)

        scope_root = self._scope_root(scope)
        validated_path = self._validate_relative_path(relative_path)
        return scope_root / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        if not scope:
            return True
        return scope in self._valid_scopes

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        return scope == SkillScope.PLUGIN and self._config.supports_plugin

    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> dict:
        normalized_scope = (
            scope.value
            if isinstance(scope, SkillScope)
            else scope or SkillScope.PROJECT.value
        )
        key = (
            self._config.tool.value,
            self._workspace_id,
            path,
            normalized_scope,
            include_hidden,
            max_depth,
        )
        result = _tree_cache.get_or_load(
            key,
            lambda: self._get_tree_uncached(
                path,
                normalized_scope,
                include_hidden,
                max_depth,
            ),
        )
        return deepcopy(result)

    def _get_tree_uncached(
        self,
        path: str,
        scope: str,
        include_hidden: bool,
        max_depth: Optional[int],
    ) -> dict:
        if scope == "all":
            scopes = [SkillScope.PROJECT, SkillScope.USER]
            if self._config.supports_plugin:
                scopes.append(SkillScope.PLUGIN)
            trees = [
                self.get_tree(path, item, include_hidden, max_depth) for item in scopes
            ]
            nodes: list[dict] = []
            for tree in trees:
                tree_scope = (
                    tree["scope"].value
                    if isinstance(tree["scope"], SkillScope)
                    else str(tree["scope"])
                )
                for node in tree["nodes"]:
                    self._apply_scope_metadata(node, tree_scope)
                    nodes.append(node)
            return {
                "path": path,
                "scope": "all",
                "nodes": nodes,
                "total": sum(int(tree["total"]) for tree in trees),
            }
        if scope == SkillScope.PLUGIN and self._config.supports_plugin:
            return self._get_plugin_skill_tree(path)
        result = super().get_tree(path, scope, include_hidden, max_depth)
        if self._config.supports_plugin:
            self._enrich_skill_nodes(result["nodes"], scope)
        return result

    @classmethod
    def _apply_scope_metadata(cls, node: dict, scope: str) -> None:
        node["scope"] = scope
        for child in node.get("children") or []:
            cls._apply_scope_metadata(child, scope)

    def read_file(self, path: str, scope: Optional[str] = None) -> dict:
        if scope == SkillScope.PLUGIN and self._config.supports_plugin:
            fs_path = self._resolve_plugin_skill_path(path)
            if not fs_path.is_file():
                raise FileManagementException(
                    "FILE_NOT_FOUND",
                    f"File not found: {path}",
                    {"path": path},
                    404,
                )
            stat = fs_path.stat()
            content = fs_path.read_text(encoding="utf-8")
            return {
                "path": path,
                "scope": SkillScope.PLUGIN.value,
                "content": content,
                "size": stat.st_size,
                "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "revision": None,
            }
        return super().read_file(path, scope)

    def _get_plugin_skill_tree(self, path: str = "/") -> Dict:
        """Build a read-only tree from enabled plugin skill directories."""
        if path not in {"/", ""}:
            # Plugin skill children are returned eagerly from the root tree.
            return {
                "path": path,
                "scope": SkillScope.PLUGIN.value,
                "nodes": [],
                "total": 0,
            }

        plugin_dirs: Dict[str, Dict] = {}
        for skill in self._plugin_loader().load_plugin_skills(self._workspace_id):
            plugin_id = f"{skill.plugin_name}@{skill.marketplace_name}"
            skill_root = Path(skill.directory_path)
            skill_file = skill_root / "SKILL.md"
            if not skill_file.is_file():
                continue
            stat = skill_file.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            plugin_dir = plugin_dirs.setdefault(
                plugin_id,
                {
                    "id": f"/{plugin_id}",
                    "name": plugin_id,
                    "path": f"/{plugin_id}",
                    "type": "directory",
                    "scope": SkillScope.PLUGIN.value,
                    "size": 0,
                    "updatedAt": updated_at,
                    "depth": 0,
                    "children": [],
                    "hasChildren": True,
                },
            )
            if updated_at > plugin_dir["updatedAt"]:
                plugin_dir["updatedAt"] = updated_at
            skill_path = f"/{plugin_id}/{skill.skill_name}"
            plugin_dir["children"].append(
                {
                    "id": skill_path,
                    "name": skill.skill_name,
                    "path": skill_path,
                    "type": "directory",
                    "scope": SkillScope.PLUGIN.value,
                    "size": 0,
                    "updatedAt": updated_at,
                    "depth": 1,
                    "children": [
                        {
                            "id": f"{skill_path}/SKILL.md",
                            "name": "SKILL.md",
                            "path": f"{skill_path}/SKILL.md",
                            "type": "file",
                            "scope": SkillScope.PLUGIN.value,
                            "size": stat.st_size,
                            "updatedAt": updated_at,
                            "depth": 2,
                        }
                    ],
                    "hasChildren": True,
                }
            )

        nodes = sorted(plugin_dirs.values(), key=lambda item: item["name"].lower())
        for node in nodes:
            node["children"] = sorted(
                node["children"], key=lambda item: item["name"].lower()
            )
        self._enrich_skill_nodes(nodes, SkillScope.PLUGIN)
        return {
            "path": path,
            "scope": SkillScope.PLUGIN.value,
            "nodes": nodes,
            "total": len(nodes),
        }

    def _resolve_plugin_skill_path(self, relative_path: str) -> Path:
        validated_path = self._validate_relative_path(relative_path)
        parts = Path(validated_path).parts
        if len(parts) < 3:
            return Path("/__missing_plugin_skill__") / validated_path

        plugin_id, skill_name = parts[0], parts[1]
        tail = Path(*parts[2:])
        for skill in self._plugin_loader().load_plugin_skills(self._workspace_id):
            if (
                f"{skill.plugin_name}@{skill.marketplace_name}" == plugin_id
                and skill.skill_name == skill_name
            ):
                return Path(skill.directory_path) / tail
        return Path("/__missing_plugin_skill__") / validated_path

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

    def _parse_front_matter(self, content: str) -> tuple[Optional[Dict], str]:
        """Parse YAML front matter, returning (front_matter_dict, remaining_content)"""
        if not content.startswith("---\n"):
            return None, content

        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            return None, content

        front_matter_str = content[4:end_marker]
        remaining_content = content[end_marker + 5 :]

        try:
            front_matter = yaml.safe_load(front_matter_str)
            return front_matter, remaining_content
        except yaml.YAMLError:
            return None, content

    def get_plugin_skills(self) -> List[PluginSkillInfo]:
        """Get all plugin Skills"""
        if not self._config.supports_plugin:
            return []

        plugin_skills: List[PluginSkillInfo] = []
        try:
            for skill in self._plugin_loader().load_plugin_skills(self._workspace_id):
                skill_file = Path(skill.directory_path) / "SKILL.md"
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    front_matter, _ = self._parse_front_matter(content)
                    plugin_skills.append(
                        PluginSkillInfo(
                            pluginId=f"{skill.plugin_name}@{skill.marketplace_name}",
                            pluginName=skill.plugin_name,
                            marketplaceName=skill.marketplace_name,
                            skillName=skill.skill_name,
                            skillPath=f"{skill.plugin_name}@{skill.marketplace_name}/{skill.skill_name}/SKILL.md",
                        )
                    )
                except Exception:
                    continue
        except Exception:
            logger.error("Failed to load plugin skills", exc_info=True)

        return plugin_skills


__all__ = ["CliSkillService", "clear_skill_tree_cache"]
