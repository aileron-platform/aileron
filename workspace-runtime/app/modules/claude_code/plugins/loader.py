"""Plugin Components Loader - 核心共用服務
供 Slash Commands、MCP、Hooks、Subagents 模組使用
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
import threading

logger = logging.getLogger(__name__)


class ComponentFileInfo:
    """組件檔案資訊（輕量級）"""
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
    """Skill 目錄資訊"""
    def __init__(
        self,
        directory_path: str,
        skill_name: str,
        plugin_name: str,
        marketplace_name: str,
    ):
        self.directory_path = directory_path  # 完整的目錄絕對路徑
        self.skill_name = skill_name          # skill 名稱 (例如: xlsx, pdf)
        self.plugin_name = plugin_name
        self.marketplace_name = marketplace_name


class PluginComponentsLoader:
    """
    Plugin 組件載入器

    職責：
    1. 從 enabledPlugins 設定中找出已啟用的 plugins
    2. 載入各 plugin 的組件（commands/agents/hooks/mcpServers）
    3. 提供結構化資料給各功能模組使用
    """

    def __init__(self, settings_service):
        """
        初始化 Loader

        Args:
            settings_service: SettingsService 實例
        """
        self.settings_service = settings_service

    # =========================================================================
    # 公開方法 - 供各功能模組呼叫
    # =========================================================================

    def load_plugin_commands(
        self,
        workspace_id: str
    ) -> list[ComponentFileInfo]:
        """載入所有已啟用 plugins 的 commands

        供 Slash Commands 模組使用

        Returns:
            List[ComponentFileInfo]: Commands 清單
        """
        result = []

        try:
            enabled_plugins = self._get_enabled_plugins(workspace_id)

            for plugin_id in enabled_plugins.keys():
                try:
                    commands = self._load_plugin_commands_for_plugin(
                        workspace_id, plugin_id
                    )
                    result.extend(commands)
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load commands from plugin '{plugin_id}': {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin commands: {e}")

        return result

    def load_plugin_agents(
        self,
        workspace_id: str
    ) -> list[ComponentFileInfo]:
        """載入所有已啟用 plugins 的 agents/subagents

        供 Subagents 模組使用

        Returns:
            List[ComponentFileInfo]: Agents 清單
        """
        result = []

        try:
            enabled_plugins = self._get_enabled_plugins(workspace_id)

            for plugin_id in enabled_plugins.keys():
                try:
                    agents = self._load_plugin_agents_for_plugin(
                        workspace_id, plugin_id
                    )
                    result.extend(agents)
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load agents from plugin '{plugin_id}': {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin agents: {e}")

        return result

    def load_plugin_mcp_servers(
        self,
        workspace_id: str
    ) -> dict[str, dict[str, Any]]:
        """載入所有已啟用 plugins 的 MCP servers

        供 MCP 模組使用

        Returns:
            Dict[plugin_id, Dict[server_name, server_config]]:
            MCP servers 字典，按 plugin 分組
        """
        result = {}

        try:
            enabled_plugins = self._get_enabled_plugins(workspace_id)

            for plugin_id in enabled_plugins.keys():
                try:
                    mcp_servers = self._load_plugin_mcp_for_plugin(
                        workspace_id, plugin_id
                    )
                    if mcp_servers:
                        result[plugin_id] = mcp_servers
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load MCP servers from plugin '{plugin_id}': {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin MCP servers: {e}")

        return result

    def load_plugin_hooks(
        self,
        workspace_id: str
    ) -> dict[str, dict[str, Any]]:
        """載入所有已啟用 plugins 的 hooks

        供 Hooks 模組使用

        Returns:
            Dict[plugin_id, hooks_config]: Hooks 配置，按 plugin 分組
        """
        result = {}

        try:
            enabled_plugins = self._get_enabled_plugins(workspace_id)

            for plugin_id in enabled_plugins.keys():
                try:
                    hooks = self._load_plugin_hooks_for_plugin(
                        workspace_id, plugin_id
                    )
                    if hooks:
                        result[plugin_id] = hooks
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load hooks from plugin '{plugin_id}': {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin hooks: {e}")

        return result

    def load_plugin_skills(
        self,
        workspace_id: str
    ) -> list[SkillDirectoryInfo]:
        """載入所有已啟用 plugins 的 skills

        供 Skills 模組使用

        Returns:
            List[SkillDirectoryInfo]: Skills 目錄清單
        """
        result = []

        try:
            enabled_plugins = self._get_enabled_plugins(workspace_id)

            for plugin_id in enabled_plugins.keys():
                try:
                    skills = self._load_plugin_skills_for_plugin(
                        workspace_id, plugin_id
                    )
                    result.extend(skills)
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load skills from plugin '{plugin_id}': {e}")

        except Exception as e:
            logger.error(f"Failed to load plugin skills: {e}")

        return result

    # =========================================================================
    # 私有方法 - 內部實作
    # =========================================================================

    def _get_enabled_plugins(self, workspace_id: str) -> dict[str, bool]:
        """取得已啟用的 plugins

        合併三個 scope（local > project > user）的 enabledPlugins
        過濾出 enabled=true 的項目
        """
        merged: dict[str, bool] = {}

        from ..common import DocumentScope

        # 依序讀取 user → project → local（後面的覆蓋前面的）
        for scope in [DocumentScope.USER, DocumentScope.PROJECT, DocumentScope.LOCAL]:
            try:
                state = self.settings_service._read_scope_state(workspace_id, scope)
                plugins = self.settings_service._extract_enabled_plugins(state)
                if plugins:
                    merged.update(plugins)
            except Exception as e:
                logger.warning(f"Failed to read {scope} settings: {e}")

        # 過濾出 enabled=true
        return {k: v for k, v in merged.items() if v}

    def _load_plugin_commands_for_plugin(
        self,
        workspace_id: str,
        plugin_id: str
    ) -> list[ComponentFileInfo]:
        """載入單一 plugin 的 commands"""
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
                file_name=Path(file_path).name,  # 保留完整附檔名（包含 .md）
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
        """載入單一 plugin 的 agents"""
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
                file_name=Path(file_path).name,  # 保留完整附檔名（包含 .md）
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
        """載入單一 plugin 的 MCP servers 配置"""
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
        """載入單一 plugin 的 hooks 配置"""
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
        """載入單一 plugin 的 skills"""
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)

        marketplace_path = self._get_marketplace_path(workspace_id, marketplace_name)
        marketplace_data = self._read_json_file(marketplace_path)
        plugin_config = self._find_plugin_in_marketplace(marketplace_data, plugin_name)

        skills_raw = plugin_config.get("skills", [])

        if not skills_raw:
            return []

        base_path = self._get_marketplace_base_path(marketplace_path)
        source = plugin_config.get("source", "./")
        plugin_base_path = self._resolve_path(base_path, source)

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
    # 工具方法
    # =========================================================================

    def _get_marketplace_base_path(self, marketplace_path: Path) -> Path:
        """取得 marketplace 根目錄

        Args:
            marketplace_path: marketplace.json 的完整路徑

        Returns:
            marketplace 根目錄（marketplace.json 的父目錄的父目錄）
        """
        return marketplace_path.parent.parent

    def _scan_commands_strict_mode(
        self,
        base_path: Path,
        plugin_config: dict[str, Any]
    ) -> list[Path]:
        """strict=true: 掃描 commands/ 目錄下的所有 .md 檔案"""
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
        """strict=false: 從配置讀取 commands 清單"""
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
        """strict=true: 掃描 agents/ 目錄下的所有 .md 檔案"""
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
        """strict=false: 從配置讀取 agents 清單"""
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
        """解析 plugin_id

        Args:
            plugin_id: 格式 "plugin_name@marketplace_name"

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
        """取得 marketplace.json 的路徑"""
        from ..common import DocumentScope, resolve_scope_root

        user_root = resolve_scope_root(workspace_id, DocumentScope.USER)
        marketplace_json = (
            user_root / "plugins" / "marketplaces" / marketplace_name /
            ".claude-plugin" / "marketplace.json"
        )

        if not marketplace_json.exists():
            raise FileNotFoundError(f"Marketplace config not found: {marketplace_json}")

        return marketplace_json

    def _find_plugin_in_marketplace(
        self,
        marketplace_data: dict[str, Any],
        plugin_name: str
    ) -> dict[str, Any]:
        """在 marketplace.json 的 plugins 陣列中找出對應的 plugin"""
        plugins = marketplace_data.get("plugins", [])

        for plugin in plugins:
            if plugin.get("name") == plugin_name:
                return plugin

        raise ValueError(f"Plugin '{plugin_name}' not found in marketplace")

    def _resolve_path(self, base_path: Path, relative_path: str) -> Path:
        """解析相對路徑為絕對路徑"""
        path_str = relative_path.replace("${CLAUDE_PLUGIN_ROOT}", "")

        if path_str.startswith("/"):
            return Path(path_str)
        else:
            return (base_path / path_str).resolve()

    def _replace_env_vars(self, base_path: Path, config: Any) -> Any:
        """遞迴替換配置中的環境變數"""
        if isinstance(config, str):
            return config.replace("${CLAUDE_PLUGIN_ROOT}", str(base_path))
        elif isinstance(config, dict):
            return {k: self._replace_env_vars(base_path, v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(base_path, item) for item in config]
        else:
            return config

    def _read_json_file(self, file_path: Path) -> dict[str, Any]:
        """讀取並解析 JSON 檔案"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file: {file_path}. Error: {e}") from e

    def _extract_description(self, file_path: Path) -> str | None:
        """從 Markdown frontmatter 提取 description"""
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
# 全域實例（線程安全的單例模式）
# =========================================================================

_loader_instance: PluginComponentsLoader | None = None
_loader_lock = threading.Lock()


def get_plugin_loader(settings_service) -> PluginComponentsLoader:
    """取得 PluginComponentsLoader 單例（線程安全）"""
    global _loader_instance

    if _loader_instance is None:
        with _loader_lock:
            if _loader_instance is None:
                _loader_instance = PluginComponentsLoader(settings_service)

    return _loader_instance

