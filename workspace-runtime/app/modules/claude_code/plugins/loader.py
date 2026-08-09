"""Installed-root Claude plugin component adapter.

Slash commands, MCP, hooks, and subagent services use this module to project
components from the exact package roots reported by ``claude plugin list``.
Marketplace checkout/source roots are intentionally outside this boundary.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aileron_marketplace_core import (
    read_plugin_resource_owner,
    resolve_claude_plugin_resources,
)

from app.modules.claude_code.documents import DocumentScope, workspace_root
from app.modules.cli_settings.cache import ProcessTTLCache
from app.modules.marketplace_operations.gate import get_marketplace_provider_gate

from .provider_inventory import run_claude_plugin_cli

if TYPE_CHECKING:
    from ..settings.configuration import SettingsService

logger = logging.getLogger(__name__)

CLI_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class ComponentFileInfo:
    """Read-only Markdown component exposed by an installed plugin."""

    file_path: str
    file_name: str
    plugin_name: str
    marketplace_name: str
    description: str | None = None
    plugin_id: str | None = None
    relative_source_path: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class SkillDirectoryInfo:
    """Read-only skill directory exposed by an installed plugin."""

    directory_path: str
    skill_name: str
    plugin_name: str
    marketplace_name: str


@dataclass(frozen=True)
class _InstalledPlugin:
    plugin_id: str
    plugin_name: str
    marketplace_name: str
    install_root: Path


class PluginComponentsLoader:
    """Project enabled Claude components from provider-reported install roots."""

    def __init__(self, settings_service: SettingsService) -> None:
        self.settings_service = settings_service
        self._components_cache: ProcessTTLCache[
            tuple[str, int, str],
            dict[str, Any],
        ] = ProcessTTLCache()

    def load_plugin_commands(self, workspace_id: str) -> list[ComponentFileInfo]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return list(
            self._load_plugin_components(workspace_id, generation, "commands")[
                "commands"
            ]
        )

    def load_plugin_agents(self, workspace_id: str) -> list[ComponentFileInfo]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return list(
            self._load_plugin_components(workspace_id, generation, "agents")["agents"]
        )

    def load_plugin_mcp_servers(
        self,
        workspace_id: str,
    ) -> dict[str, dict[str, Any]]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return dict(
            self._load_plugin_components(workspace_id, generation, "mcp_servers")[
                "mcp_servers"
            ]
        )

    def load_plugin_hooks(
        self,
        workspace_id: str,
    ) -> dict[str, dict[str, Any]]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return dict(
            self._load_plugin_components(workspace_id, generation, "hooks")["hooks"]
        )

    def load_plugin_skills(self, workspace_id: str) -> list[SkillDirectoryInfo]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return list(
            self._load_plugin_components(workspace_id, generation, "skills")["skills"]
        )

    def load_plugin_output_styles(
        self,
        workspace_id: str,
    ) -> list[ComponentFileInfo]:
        generation = get_marketplace_provider_gate().generation("claude-code")
        return list(
            self._load_plugin_components(workspace_id, generation, "output_styles")[
                "output_styles"
            ]
        )

    def clear_cache(self, workspace_id: str | None = None) -> None:
        if workspace_id is None:
            self._components_cache.clear()
        else:
            self._components_cache.clear(lambda key: key[0] == workspace_id)

    def _load_plugin_components(
        self,
        workspace_id: str,
        provider_generation: int,
        capability: str,
    ) -> dict[str, Any]:
        key = (workspace_id, provider_generation, capability)

        def load() -> dict[str, Any]:
            enabled_plugins = self._get_enabled_plugins(workspace_id)
            installed_plugins = self._installed_plugins(enabled_plugins)
            result: dict[str, Any] = {
                "commands": [],
                "agents": [],
                "mcp_servers": {},
                "hooks": {},
                "skills": [],
                "output_styles": [],
            }
            for plugin in installed_plugins:
                self._merge_plugin_components(result, plugin, capability)
            return result

        return self._components_cache.get_or_load(key, load)

    def _merge_plugin_components(
        self,
        result: dict[str, Any],
        plugin: _InstalledPlugin,
        capability: str,
    ) -> None:
        resources = resolve_claude_plugin_resources(plugin.install_root)
        if resources.diagnostics:
            diagnostics = ", ".join(
                f"{item.code}:{item.source_locator}" for item in resources.diagnostics
            )
            raise ValueError(f"Invalid installed plugin resources: {diagnostics}")

        for resource in resources.file_resources:
            source_path = plugin.install_root / resource.source_locator
            if (resource.resource_type == "command" and capability == "commands") or (
                resource.resource_type == "agent" and capability == "agents"
            ):
                item = ComponentFileInfo(
                    file_path=str(source_path),
                    file_name=source_path.name,
                    plugin_name=plugin.plugin_name,
                    marketplace_name=plugin.marketplace_name,
                    description=self._extract_description(source_path),
                    plugin_id=plugin.plugin_id,
                    relative_source_path=resource.source_locator,
                )
                key = "commands" if resource.resource_type == "command" else "agents"
                result[key].append(item)
            elif resource.resource_type == "skill" and capability == "skills":
                skill_root = plugin.install_root / resource.resource_root_locator
                result["skills"].append(
                    SkillDirectoryInfo(
                        directory_path=str(skill_root),
                        skill_name=skill_root.name,
                        plugin_name=plugin.plugin_name,
                        marketplace_name=plugin.marketplace_name,
                    )
                )
            elif (
                resource.resource_type == "output-style"
                and capability == "output_styles"
            ):
                result["output_styles"].append(
                    ComponentFileInfo(
                        file_path=str(source_path),
                        file_name=source_path.name,
                        plugin_name=plugin.plugin_name,
                        marketplace_name=plugin.marketplace_name,
                        description=self._extract_description(source_path),
                        plugin_id=plugin.plugin_id,
                        relative_source_path=resource.source_locator,
                    )
                )

        if capability == "mcp_servers" and resources.mcp_servers:
            result["mcp_servers"][plugin.plugin_id] = {
                name: read_plugin_resource_owner(plugin.install_root, owner)
                for name, owner in sorted(resources.mcp_servers.items())
            }
        if capability == "hooks" and resources.hook_sources:
            merged: dict[str, list[Any]] = {}
            for owner in resources.hook_sources:
                value = read_plugin_resource_owner(plugin.install_root, owner)
                if not isinstance(value, dict):
                    raise ValueError("Installed plugin hooks must resolve to an object")
                for event, rules in value.items():
                    if isinstance(rules, list):
                        merged.setdefault(str(event), []).extend(rules)
            result["hooks"][plugin.plugin_id] = merged

    def _installed_plugins(
        self,
        enabled_plugins: dict[str, bool],
    ) -> tuple[_InstalledPlugin, ...]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in self._plugin_rows():
            plugin_id = row.get("id") or row.get("pluginId") or row.get("name")
            if isinstance(plugin_id, str) and plugin_id in enabled_plugins:
                groups.setdefault(plugin_id, []).append(row)

        plugins: list[_InstalledPlugin] = []
        for plugin_id in sorted(enabled_plugins):
            rows = groups.get(plugin_id)
            if not rows:
                continue
            selected = max(
                rows,
                key=lambda row: self._scope_rank(str(row.get("scope") or "user")),
            )
            if selected.get("enabled") is False:
                continue
            raw_path = selected.get("installPath") or selected.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            try:
                install_root = Path(raw_path).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if not install_root.is_dir():
                continue
            try:
                plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)
            except ValueError:
                continue
            plugins.append(
                _InstalledPlugin(
                    plugin_id=plugin_id,
                    plugin_name=plugin_name,
                    marketplace_name=marketplace_name,
                    install_root=install_root,
                )
            )
        return tuple(plugins)

    def _plugin_rows(self) -> list[dict[str, Any]]:
        try:
            completed = run_claude_plugin_cli(
                ["plugin", "list", "--json"],
                cwd=workspace_root(),
                timeout=CLI_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Claude plugin inventory is unavailable") from exc
        if completed.returncode != 0:
            raise RuntimeError("Claude plugin inventory failed")
        try:
            payload = json.loads(completed.stdout or "null")
        except json.JSONDecodeError as exc:
            raise ValueError("Claude plugin inventory returned invalid JSON") from exc
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("plugins") or payload.get("items") or payload.get("data")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        raise ValueError("Claude plugin inventory must contain a plugin list")

    def _get_enabled_plugins(self, workspace_id: str) -> dict[str, bool]:
        merged: dict[str, bool] = {}
        for scope in (
            DocumentScope.USER,
            DocumentScope.PROJECT,
            DocumentScope.LOCAL,
        ):
            try:
                state = self.settings_service._read_scope_state(workspace_id, scope)
                plugins = self.settings_service._extract_enabled_plugins(state)
                if plugins:
                    merged.update(plugins)
            except Exception as exc:
                logger.warning(
                    "Failed to read %s plugin settings: %s",
                    scope,
                    exc,
                )
        return {plugin_id: enabled for plugin_id, enabled in merged.items() if enabled}

    @staticmethod
    def _scope_rank(scope: str) -> int:
        return {"user": 0, "project": 1, "local": 2}.get(scope, 0)

    @staticmethod
    def _parse_plugin_id(plugin_id: str) -> tuple[str, str]:
        parts = plugin_id.split("@")
        if len(parts) != 2:
            raise ValueError(f"Invalid plugin ID format: {plugin_id}")
        plugin_name, marketplace_name = (part.strip() for part in parts)
        if not plugin_name or not marketplace_name:
            raise ValueError(f"Invalid plugin ID: {plugin_id}")
        return plugin_name, marketplace_name

    @staticmethod
    def _extract_description(file_path: Path) -> str | None:
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError:
            return None
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        for line in parts[1].splitlines():
            if line.strip().startswith("description:"):
                return line.split(":", 1)[1].strip().strip("\"'")
        return None


_loader_instance: PluginComponentsLoader | None = None
_loader_lock = threading.Lock()


def get_plugin_loader(settings_service: SettingsService) -> PluginComponentsLoader:
    """Return the process-wide installed plugin component adapter."""

    global _loader_instance
    if _loader_instance is None:
        with _loader_lock:
            if _loader_instance is None:
                _loader_instance = PluginComponentsLoader(settings_service)
    return _loader_instance
