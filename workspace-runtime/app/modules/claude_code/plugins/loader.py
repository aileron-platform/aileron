"""Plugin Components Loader - Core Shared Service
Used by Slash Commands, MCP, Hooks, Subagents modules
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
import threading

logger = logging.getLogger(__name__)


class ComponentFileInfo:
    """Component file information (lightweight)"""
    def __init__(
        self,
        file_path: str,
        file_name: str,
        plugin_name: str,
        marketplace_name: str,
        description: Optional[str] = None,
    ):
        self.file_path = file_path
        self.file_name = file_name
        self.plugin_name = plugin_name
        self.marketplace_name = marketplace_name
        self.description = description


class SkillDirectoryInfo:
    """Skill directory information"""
    def __init__(
        self,
        directory_path: str,
        skill_name: str,
        plugin_name: str,
        marketplace_name: str,
    ):
        self.directory_path = directory_path  # Complete absolute directory path
        self.skill_name = skill_name          # skill name (e.g., xlsx, pdf)
        self.plugin_name = plugin_name
        self.marketplace_name = marketplace_name


class PluginComponentsLoader:
    """
    Plugin component loader

    Responsibilities:
    1. Find enabled plugins from enabledPlugins settings
    2. Load each plugin's components (commands/agents/hooks/mcpServers)
    3. Provide structured data to functional modules
    """

    def __init__(self, settings_service):
        """
        Initialize loader

        Args:
            settings_service: SettingsService instance
        """
        self.settings_service = settings_service
        self._components_cache: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    # =========================================================================
    # Public Methods - Called by functional modules
    # =========================================================================

    def load_plugin_commands(
        self,
        workspace_id: str
    ) -> list[ComponentFileInfo]:
        """Load commands from all enabled plugins

        Used by Slash Commands module

        Returns:
            List[ComponentFileInfo]: Commands list
        """
        try:
            return list(self._load_plugin_components(workspace_id)["commands"])

        except Exception as e:
            logger.error(f"Failed to load plugin commands: {e}")

        return []

    def load_plugin_agents(
        self,
        workspace_id: str
    ) -> list[ComponentFileInfo]:
        """Load agents/subagents from all enabled plugins

        Used by Subagents module

        Returns:
            List[ComponentFileInfo]: Agents list
        """
        try:
            return list(self._load_plugin_components(workspace_id)["agents"])

        except Exception as e:
            logger.error(f"Failed to load plugin agents: {e}")

        return []

    def load_plugin_mcp_servers(
        self,
        workspace_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load MCP servers from all enabled plugins

        Used by MCP module

        Returns:
            Dict[plugin_id, Dict[server_name, server_config]]:
            MCP servers dictionary grouped by plugin
        """
        try:
            return dict(self._load_plugin_components(workspace_id)["mcp_servers"])

        except Exception as e:
            logger.error(f"Failed to load plugin MCP servers: {e}")

        return {}

    def load_plugin_hooks(
        self,
        workspace_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load hooks from all enabled plugins

        Used by Hooks module

        Returns:
            Dict[plugin_id, hooks_config]: Hooks configuration grouped by plugin
        """
        try:
            return dict(self._load_plugin_components(workspace_id)["hooks"])

        except Exception as e:
            logger.error(f"Failed to load plugin hooks: {e}")

        return {}

    def load_plugin_skills(
        self,
        workspace_id: str
    ) -> list[SkillDirectoryInfo]:
        """Load skills from all enabled plugins

        Used by Skills module

        Returns:
            List[SkillDirectoryInfo]: Skills directory list
        """
        try:
            return list(self._load_plugin_components(workspace_id)["skills"])

        except Exception as e:
            logger.error(f"Failed to load plugin skills: {e}")

        return []

    def clear_cache(self, workspace_id: str | None = None) -> None:
        """Clear cached plugin component discovery."""

        with self._cache_lock:
            if workspace_id is None:
                self._components_cache.clear()
            else:
                self._components_cache.pop(workspace_id, None)

    # =========================================================================
    # Private Methods - Internal implementation
    # =========================================================================

    def _load_plugin_components(self, workspace_id: str) -> dict[str, Any]:
        enabled_plugins = self._get_enabled_plugins(workspace_id)
        cache_key = self._components_cache_key(workspace_id, enabled_plugins)
        with self._cache_lock:
            cached = self._components_cache.get(workspace_id)
            if cached is not None and cached[0] == cache_key:
                return cached[1]

        result: dict[str, Any] = {
            "commands": [],
            "agents": [],
            "mcp_servers": {},
            "hooks": {},
            "skills": [],
        }
        for plugin_id in enabled_plugins.keys():
            try:
                result["commands"].extend(self._load_plugin_commands_for_plugin(workspace_id, plugin_id))
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load commands from plugin '{plugin_id}': {e}")
            try:
                result["agents"].extend(self._load_plugin_agents_for_plugin(workspace_id, plugin_id))
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load agents from plugin '{plugin_id}': {e}")
            try:
                mcp_servers = self._load_plugin_mcp_for_plugin(workspace_id, plugin_id)
                if mcp_servers:
                    result["mcp_servers"][plugin_id] = mcp_servers
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load MCP servers from plugin '{plugin_id}': {e}")
            try:
                hooks = self._load_plugin_hooks_for_plugin(workspace_id, plugin_id)
                if hooks:
                    result["hooks"][plugin_id] = hooks
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load hooks from plugin '{plugin_id}': {e}")
            try:
                result["skills"].extend(self._load_plugin_skills_for_plugin(workspace_id, plugin_id))
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load skills from plugin '{plugin_id}': {e}")

        with self._cache_lock:
            self._components_cache[workspace_id] = (cache_key, result)
        return result

    def _components_cache_key(self, workspace_id: str, enabled_plugins: dict[str, bool]) -> tuple[Any, ...]:
        plugin_signatures: list[tuple[str, tuple[Any, ...] | None]] = []
        for plugin_id in sorted(enabled_plugins):
            try:
                plugin_signatures.append((plugin_id, self._plugin_component_signature(workspace_id, plugin_id)))
            except (FileNotFoundError, ValueError):
                plugin_signatures.append((plugin_id, None))
        return (tuple(sorted(enabled_plugins.items())), tuple(plugin_signatures))

    def _plugin_component_signature(self, workspace_id: str, plugin_id: str) -> tuple[Any, ...]:
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)
        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)
        base_path = self._get_marketplace_base_path(marketplace_path)
        source_path = self._resolve_path(base_path, plugin_config.get("source", "./"))
        strict_mode = plugin_config.get("strict", True)

        if strict_mode:
            command_signature = self._directory_component_signature(source_path / "commands", "*.md")
            agent_signature = self._directory_component_signature(source_path / "agents", "*.md")
        else:
            command_signature = self._configured_component_paths_signature(
                base_path,
                plugin_config.get("commands", []),
                "*.md",
            )
            agent_signature = self._configured_component_paths_signature(
                base_path,
                plugin_config.get("agents", []),
                "*.md",
            )

        return (
            self._file_signature(marketplace_path),
            ("commands", command_signature),
            ("agents", agent_signature),
            ("mcp", self._mcp_component_signature(base_path, source_path, plugin_config)),
            ("hooks", self._hooks_component_signature(base_path, source_path, plugin_config)),
            ("skills", self._skills_component_signature(source_path, plugin_config.get("skills", []))),
        )

    def _mcp_component_signature(
        self,
        base_path: Path,
        source_path: Path,
        plugin_config: dict[str, Any],
    ) -> tuple[Any, ...]:
        mcp_servers = plugin_config.get("mcpServers")
        if isinstance(mcp_servers, str):
            return self._file_signature(self._resolve_path(base_path, mcp_servers))
        if not mcp_servers:
            return self._file_signature(source_path / ".mcp.json")
        return ("inline",)

    def _hooks_component_signature(
        self,
        base_path: Path,
        source_path: Path,
        plugin_config: dict[str, Any],
    ) -> tuple[Any, ...]:
        hooks = plugin_config.get("hooks")
        if isinstance(hooks, str):
            return self._file_signature(self._resolve_path(base_path, hooks))
        if not hooks:
            return self._file_signature(source_path / "hooks" / "hooks.json")
        return ("inline",)

    def _skills_component_signature(
        self,
        source_path: Path,
        skills_raw: Any,
    ) -> tuple[Any, ...]:
        if not skills_raw:
            return self._path_tree_signature(source_path / "skills")
        if isinstance(skills_raw, str):
            skills_raw = [skills_raw]
        if not isinstance(skills_raw, list):
            return ()
        signatures = []
        for skill_relative_path in skills_raw:
            if not isinstance(skill_relative_path, str):
                continue
            skill_path = self._resolve_path(source_path, skill_relative_path)
            signatures.append((str(skill_path), self._path_tree_signature(skill_path)))
        return tuple(signatures)

    def _configured_component_paths_signature(
        self,
        base_path: Path,
        paths_raw: Any,
        pattern: str,
    ) -> tuple[Any, ...]:
        if isinstance(paths_raw, str):
            paths_raw = [paths_raw]
        if not isinstance(paths_raw, list):
            return ()
        signatures = []
        for item in paths_raw:
            if not isinstance(item, str):
                continue
            item_path = self._resolve_path(base_path, item)
            if item_path.is_dir():
                signatures.append((str(item_path), self._directory_component_signature(item_path, pattern)))
            else:
                signatures.append(self._file_signature(item_path))
        return tuple(signatures)

    def _directory_component_signature(self, directory: Path, pattern: str) -> tuple[Any, ...]:
        if not directory.exists():
            return (str(directory), None)
        if not directory.is_dir():
            return self._file_signature(directory)
        return (
            str(directory),
            self._path_mtime_ns(directory),
            tuple(self._file_signature(path) for path in sorted(directory.rglob(pattern))),
        )

    def _path_tree_signature(self, path: Path) -> tuple[Any, ...]:
        if not path.exists():
            return (str(path), None)
        if path.is_file():
            return self._file_signature(path)
        return (
            str(path),
            self._path_mtime_ns(path),
            tuple(
                self._file_signature(child)
                for child in sorted(path.rglob("*"))
                if child.is_file()
            ),
        )

    def _file_signature(self, path: Path) -> tuple[str, int | None, int | None]:
        try:
            stat = path.stat()
            return (str(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (str(path), None, None)

    @staticmethod
    def _path_mtime_ns(path: Path) -> int | None:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return None

    def _get_enabled_plugins(self, workspace_id: str) -> dict[str, bool]:
        """Get enabled plugins

        Merge enabledPlugins from three scopes (local > project > user)
        Filter out enabled=true items
        """
        merged: dict[str, bool] = {}

        from ..common import DocumentScope

        # Read user → project → local sequentially (later overrides earlier)
        for scope in [DocumentScope.USER, DocumentScope.PROJECT, DocumentScope.LOCAL]:
            try:
                state = self.settings_service._read_scope_state(workspace_id, scope)
                plugins = self.settings_service._extract_enabled_plugins(state)
                if plugins:
                    merged.update(plugins)
            except Exception as e:
                logger.warning(f"Failed to read {scope} settings: {e}")

        # Filter out enabled=true
        return {k: v for k, v in merged.items() if v}

    def _load_plugin_commands_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> list[ComponentFileInfo]:
        """Load commands from single plugin"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        base_path = self._get_marketplace_base_path(marketplace_path)
        strict_mode = plugin_config.get("strict", True)

        if strict_mode:
            command_files = self._scan_commands_strict_mode(base_path, plugin_config)
        else:
            command_files = self._scan_commands_list_mode(base_path, plugin_config)

        return [
            ComponentFileInfo(
                file_path=str(file_path),
                file_name=Path(file_path).name,  # Keep complete extension (including .md)
                plugin_name=plugin_name,
                marketplace_name=marketplace_name,
                description=self._extract_description(file_path)
            )
            for file_path in command_files
        ]

    def _load_plugin_agents_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> list[ComponentFileInfo]:
        """Load agents from single plugin"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        base_path = self._get_marketplace_base_path(marketplace_path)
        strict_mode = plugin_config.get("strict", True)

        if strict_mode:
            agent_files = self._scan_agents_strict_mode(base_path, plugin_config)
        else:
            agent_files = self._scan_agents_list_mode(base_path, plugin_config)

        return [
            ComponentFileInfo(
                file_path=str(file_path),
                file_name=Path(file_path).name,  # Keep complete extension (including .md)
                plugin_name=plugin_name,
                marketplace_name=marketplace_name,
                description=self._extract_description(file_path)
            )
            for file_path in agent_files
        ]

    def _load_plugin_mcp_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> dict[str, Any] | None:
        """Load MCP servers configuration from single plugin"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        base_path = self._get_marketplace_base_path(marketplace_path)

        mcp_servers = plugin_config.get("mcpServers")

        if not mcp_servers:
            source = plugin_config.get("source", "./")
            source_path = self._resolve_path(base_path, source)
            mcp_file = source_path / ".mcp.json"

            if mcp_file.exists():
                mcp_data = self._read_json_file(mcp_file)
                mcp_servers = mcp_data.get("mcpServers")

        if isinstance(mcp_servers, str):
            config_path = self._resolve_path(base_path, mcp_servers)
            mcp_data = self._read_json_file(config_path)
            mcp_servers = mcp_data.get("mcpServers")

        if mcp_servers:
            mcp_servers = self._replace_env_vars(base_path, mcp_servers)

        return mcp_servers

    def _load_plugin_hooks_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> dict[str, Any] | None:
        """Load hooks configuration from single plugin"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        base_path = self._get_marketplace_base_path(marketplace_path)

        hooks = plugin_config.get("hooks")

        if not hooks:
            source = plugin_config.get("source", "./")
            source_path = self._resolve_path(base_path, source)
            hooks_file = source_path / "hooks" / "hooks.json"

            if hooks_file.exists():
                hooks_data = self._read_json_file(hooks_file)
                hooks = hooks_data.get("hooks")

        if isinstance(hooks, str):
            config_path = self._resolve_path(base_path, hooks)
            hooks_data = self._read_json_file(config_path)
            hooks = hooks_data.get("hooks")

        if hooks:
            hooks = self._replace_env_vars(base_path, hooks)

        return hooks

    def _load_plugin_skills_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> list[SkillDirectoryInfo]:
        """Load skills from single plugin"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        skills_raw = plugin_config.get("skills", [])

        base_path = self._get_marketplace_base_path(marketplace_path)
        source = plugin_config.get("source", "./")
        plugin_base_path = self._resolve_path(base_path, source)

        if not skills_raw:
            skills_dir = plugin_base_path / "skills"
            if not skills_dir.is_dir():
                return []
            return [
                SkillDirectoryInfo(
                    directory_path=str(skill_file.parent),
                    skill_name=skill_file.parent.name,
                    plugin_name=plugin_name,
                    marketplace_name=marketplace_name,
                )
                for skill_file in sorted(skills_dir.glob("*/SKILL.md"))
                if skill_file.is_file()
            ]

        result = []
        for skill_relative_path in skills_raw:
            skill_full_path = self._resolve_path(plugin_base_path, skill_relative_path)
            skill_name = Path(skill_relative_path).name

            result.append(
                SkillDirectoryInfo(
                    directory_path=str(skill_full_path),
                    skill_name=skill_name,
                    plugin_name=plugin_name,
                    marketplace_name=marketplace_name
                )
            )

        return result

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _get_marketplace_base_path(self, marketplace_path: Path) -> Path:
        """Get marketplace root directory

        Args:
            marketplace_path: Complete path to marketplace.json

        Returns:
            Marketplace root directory (parent of parent of marketplace.json)
        """
        return marketplace_path.parent.parent

    def _scan_commands_strict_mode(
        self,
        base_path: Path,
        plugin_config: dict[str, Any]
    ) -> list[Path]:
        """strict=true: Scan all .md files under commands/ directory"""
        source = plugin_config.get("source", "./")
        source_path = self._resolve_path(base_path, source)
        commands_dir = source_path / "commands"

        if not commands_dir.exists():
            return []

        return list(commands_dir.rglob("*.md"))

    def _scan_commands_list_mode(
        self,
        base_path: Path,
        plugin_config: dict[str, Any]
    ) -> list[Path]:
        """strict=false: Read commands list from configuration"""
        commands_raw = plugin_config.get("commands", [])

        if isinstance(commands_raw, str):
            commands_raw = [commands_raw]

        result = []
        for item in commands_raw:
            item_path = self._resolve_path(base_path, item)

            if not item_path.exists():
                logger.warning(f"Command path not found: {item_path}")
                continue

            if item_path.is_dir():
                result.extend(item_path.rglob("*.md"))
            else:
                result.append(item_path)

        return result

    def _scan_agents_strict_mode(
        self,
        base_path: Path,
        plugin_config: dict[str, Any]
    ) -> list[Path]:
        """strict=true: Scan all .md files under agents/ directory"""
        source = plugin_config.get("source", "./")
        source_path = self._resolve_path(base_path, source)
        agents_dir = source_path / "agents"

        if not agents_dir.exists():
            return []

        return list(agents_dir.rglob("*.md"))

    def _scan_agents_list_mode(
        self,
        base_path: Path,
        plugin_config: dict[str, Any]
    ) -> list[Path]:
        """strict=false: Read agents list from configuration"""
        agents_raw = plugin_config.get("agents", [])

        if isinstance(agents_raw, str):
            agents_raw = [agents_raw]

        result = []
        for item in agents_raw:
            item_path = self._resolve_path(base_path, item)

            if not item_path.exists():
                logger.warning(f"Agent path not found: {item_path}")
                continue

            if item_path.is_dir():
                result.extend(item_path.rglob("*.md"))
            else:
                result.append(item_path)

        return result

    def _parse_plugin_id(self, plugin_id: str) -> tuple[str, str]:
        """Parse plugin_id

        Args:
            plugin_id: Format "plugin_name@marketplace_name"

        Returns:
            (plugin_name, marketplace_name)
        """
        parts = plugin_id.split("@")
        if len(parts) != 2:
            raise ValueError(f"Invalid plugin_id format: '{plugin_id}'")

        plugin_name = parts[0].strip()
        marketplace_name = parts[1].strip()

        if not plugin_name or not marketplace_name:
            raise ValueError(f"Invalid plugin_id: '{plugin_id}'")

        return plugin_name, marketplace_name

    def _get_marketplace_path(
        self,
        workspace_id: str,
        marketplace_name: str
    ) -> Path:
        """Get path to marketplace.json"""
        from ..common import DocumentScope, resolve_scope_root

        user_root = resolve_scope_root(workspace_id, DocumentScope.USER)
        candidates = [(
            user_root / "plugins" / "marketplaces" / marketplace_name /
            ".claude-plugin" / "marketplace.json"
        )]

        for registry_file in [
            user_root / "plugins" / "known_marketplaces.json",
            user_root / "settings.json",
        ]:
            candidates.extend(self._marketplace_paths_from_registry_file(registry_file, marketplace_name))

        for marketplace_json in candidates:
            if marketplace_json.exists():
                return marketplace_json

        raise FileNotFoundError(f"Marketplace config not found: {candidates[0]}")

    def _marketplace_paths_from_registry_file(
        self,
        registry_file: Path,
        marketplace_name: str,
    ) -> list[Path]:
        try:
            data = self._read_json_file(registry_file)
        except (FileNotFoundError, ValueError):
            return []

        if registry_file.name == "settings.json":
            entries = data.get("extraKnownMarketplaces")
        else:
            entries = data
        if not isinstance(entries, dict):
            return []

        entry = entries.get(marketplace_name)
        if not isinstance(entry, dict):
            return []

        paths: list[Path] = []
        install_location = entry.get("installLocation")
        if isinstance(install_location, str) and install_location.strip():
            paths.append(Path(install_location.strip()) / ".claude-plugin" / "marketplace.json")

        source = entry.get("source")
        if isinstance(source, dict):
            source_path = source.get("path")
            if isinstance(source_path, str) and source_path.strip():
                paths.append(Path(source_path.strip()) / ".claude-plugin" / "marketplace.json")
        return paths

    def _find_plugin_in_marketplace(
        self,
        marketplace_data: dict[str, Any],
        plugin_name: str
    ) -> dict[str, Any]:
        """Find corresponding plugin in plugins array of marketplace.json"""
        plugins = marketplace_data.get("plugins", [])

        for plugin in plugins:
            if plugin.get("name") == plugin_name:
                return plugin

        raise ValueError(f"Plugin '{plugin_name}' not found in marketplace")

    def _resolve_path(self, base_path: Path, relative_path: str) -> Path:
        """Resolve relative path to absolute path"""
        path_str = relative_path.replace("${CLAUDE_PLUGIN_ROOT}", "")

        if path_str.startswith("/"):
            return Path(path_str)
        else:
            return (base_path / path_str).resolve()

    def _replace_env_vars(self, base_path: Path, config: Any) -> Any:
        """Recursively replace environment variables in configuration"""
        if isinstance(config, str):
            return config.replace("${CLAUDE_PLUGIN_ROOT}", str(base_path))
        elif isinstance(config, dict):
            return {k: self._replace_env_vars(base_path, v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(base_path, item) for item in config]
        else:
            return config

    def _read_json_file(self, file_path: Path) -> dict[str, Any]:
        """Read and parse JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file: {file_path}. Error: {e}") from e

    def _extract_description(self, file_path: Path) -> str | None:
        """Extract description from Markdown frontmatter"""
        try:
            if not file_path.exists():
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    for line in frontmatter.split('\n'):
                        if line.strip().startswith('description:'):
                            return line.split(':', 1)[1].strip().strip('"\'')

            return None
        except (OSError, IOError) as e:
            logger.warning(f"Failed to extract description from {file_path}: {e}")
            return None


# =========================================================================
# Global Instance (Thread-safe singleton)
# =========================================================================

_loader_instance: PluginComponentsLoader | None = None
_loader_lock = threading.Lock()


def get_plugin_loader(settings_service) -> PluginComponentsLoader:
    """Get PluginComponentsLoader singleton (thread-safe)"""
    global _loader_instance

    if _loader_instance is None:
        with _loader_lock:
            if _loader_instance is None:
                _loader_instance = PluginComponentsLoader(settings_service)

    return _loader_instance
