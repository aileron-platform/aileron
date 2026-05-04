"""CLI MCP server backend service

Provides CRUD operations for MCP configuration in Gemini, Codex, and OpenCode.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config.settings import get_workspace_path
from app.modules.cli_settings.codex_paths import CodexLayer, CodexResource, get_codex_path_resolver
from app.modules.cli_settings.codex.plugin_resources import CodexPluginResourceResolver
from app.modules.cli_settings.gemini.extension_resources import GeminiExtensionResourceResolver, resolve_workspace_root
from app.modules.cli_settings.toml_utils import parse_toml

from .config_strategies import ConfigFileStrategy, JsonConfigStrategy, TomlConfigStrategy
from .models import (
    CliMcpImportRequest,
    CliMcpImportResponse,
    CliMcpImportUploadRequest,
    CliMcpScope,
    CliMcpScopeResponse,
    CliMcpScopeServers,
    CliMcpServerCollectionResponse,
    CliMcpServerConfig,
    CliMcpServerCreateRequest,
    CliMcpServerDeleteResponse,
    CliMcpServerExportResponse,
    CliMcpServerRuntime,
    CliMcpServerUpdateRequest,
    CliMcpTransportType,
)

logger = logging.getLogger(__name__)


# === Exceptions ==========================================================


class CliMcpScopeNotSupportedError(ValueError):
    """Specified scope is not supported"""


class CliMcpServerAlreadyExistsError(RuntimeError):
    """Server name already exists"""


class CliMcpServerNotFoundError(KeyError):
    """Server does not exist"""


class CliMcpToggleNotSupportedError(ValueError):
    """This tool does not support toggle"""


class CliMcpReadOnlyScopeError(ValueError):
    """Specified scope is read-only and cannot be mutated"""


# === Tool Enum ==========================================================


class McpTool(str, Enum):
    """CLI tools that support MCP"""

    GEMINI = "gemini"
    OPENCODE = "opencode"
    CODEX = "codex"


# === Tool Configuration ==================================================


@dataclass(frozen=True)
class CliMcpToolConfig:
    """MCP configuration file information for each CLI tool"""

    tool: McpTool
    project_file: str  # Path relative to workspace root
    user_file_path: Path  # Absolute path
    servers_key: str  # Key for storing servers in JSON/TOML
    strategy: ConfigFileStrategy
    supports_toggle: bool = True


def _tool_configs() -> Dict[McpTool, CliMcpToolConfig]:
    home = Path.home()
    codex_paths = get_codex_path_resolver()
    json_strategy = JsonConfigStrategy()
    toml_strategy = TomlConfigStrategy()

    return {
        McpTool.GEMINI: CliMcpToolConfig(
            tool=McpTool.GEMINI,
            project_file=".gemini/settings.json",
            user_file_path=home / ".gemini" / "settings.json",
            servers_key="mcpServers",
            strategy=json_strategy,
            supports_toggle=False,
        ),
        McpTool.CODEX: CliMcpToolConfig(
            tool=McpTool.CODEX,
            project_file=".codex/config.toml",
            user_file_path=codex_paths.resolve(CodexLayer.USER, CodexResource.CONFIG),
            servers_key="mcp_servers",
            strategy=toml_strategy,
            supports_toggle=True,
        ),
        McpTool.OPENCODE: CliMcpToolConfig(
            tool=McpTool.OPENCODE,
            project_file="opencode.json",
            user_file_path=home / ".config" / "opencode" / "opencode.json",
            servers_key="mcp",
            strategy=json_strategy,
            supports_toggle=True,
        ),
    }


def get_mcp_tool_config(tool: McpTool) -> CliMcpToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported MCP tool: {tool}")
    return configs[tool]


# === Service =============================================================


class CliMcpService:
    """File service for managing CLI tool MCP server configuration"""

    def __init__(self, config: CliMcpToolConfig) -> None:
        self._config = config

    # --- Public CRUD ------------------------------------------------------

    def list_servers(
        self, workspace_id: str, scope: CliMcpScope | None = None
    ) -> CliMcpServerCollectionResponse:
        scopes = [scope] if scope else [CliMcpScope.PROJECT, CliMcpScope.USER]
        if not scope and self._config.tool == McpTool.CODEX:
            scopes.append(CliMcpScope.PLUGIN)
        if not scope and self._config.tool == McpTool.GEMINI:
            extension_servers = self._load_gemini_extension_servers(workspace_id)
            if extension_servers:
                scopes.append(CliMcpScope.EXTENSION)
        groups: List[CliMcpScopeServers] = []
        for s in scopes:
            servers = self._load_servers(workspace_id, s)
            runtime_map = self._to_runtime_map(servers)
            groups.append(CliMcpScopeServers(scope=s, mcpServers=runtime_map))
        return CliMcpServerCollectionResponse(
            workspaceId=workspace_id, scopes=groups
        )

    def get_scope(
        self, workspace_id: str, scope: CliMcpScope
    ) -> CliMcpScopeResponse:
        servers = self._load_servers(workspace_id, scope)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers=self._to_runtime_map(servers),
        )

    def get_server(
        self, workspace_id: str, scope: CliMcpScope, server_name: str
    ) -> CliMcpScopeResponse:
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        entry = servers[server_name]
        runtime = self._to_runtime(server_name, entry)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers={server_name: runtime},
        )

    def create_servers(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        payload: CliMcpServerCreateRequest,
    ) -> CliMcpScopeResponse:
        self._ensure_mutable_scope(scope)
        servers = self._load_servers(workspace_id, scope)
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        duplicates = [n for n in prepared if n in servers]
        if duplicates:
            raise CliMcpServerAlreadyExistsError(
                f"Duplicate server names: {', '.join(sorted(duplicates))}"
            )
        for name, config in prepared.items():
            servers[name] = self._normalize_to_native(config)
        self._write_servers(workspace_id, scope, servers)
        all_servers = self._load_servers(workspace_id, scope)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers=self._to_runtime_map(all_servers),
        )

    def update_server(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        server_name: str,
        payload: CliMcpServerUpdateRequest,
    ) -> CliMcpScopeResponse:
        self._ensure_mutable_scope(scope)
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        if len(prepared) > 1:
            raise ValueError("Only one server can be updated per request")
        new_name, config = next(iter(prepared.items()))
        if new_name != server_name:
            raise CliMcpServerAlreadyExistsError(
                f"Payload server name '{new_name}' does not match target '{server_name}'"
            )
        servers[server_name] = self._normalize_to_native(config)
        self._write_servers(workspace_id, scope, servers)
        updated = self._load_servers(workspace_id, scope)
        runtime = self._to_runtime(server_name, updated[server_name])
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers={server_name: runtime},
        )

    def delete_server(
        self, workspace_id: str, scope: CliMcpScope, server_name: str
    ) -> CliMcpServerDeleteResponse:
        self._ensure_mutable_scope(scope)
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        del servers[server_name]
        self._write_servers(workspace_id, scope, servers)
        return CliMcpServerDeleteResponse(
            workspaceId=workspace_id, scope=scope
        )

    def toggle_server_status(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        server_name: str,
        enabled: bool,
    ) -> CliMcpScopeResponse:
        self._ensure_mutable_scope(scope)
        if not self._config.supports_toggle:
            raise CliMcpToggleNotSupportedError(
                f"{self._config.tool.value} does not support MCP server toggle"
            )
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        entry = servers[server_name]
        entry["enabled"] = enabled
        self._write_servers(workspace_id, scope, servers)
        runtime = self._to_runtime(server_name, entry)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers={server_name: runtime},
        )

    # --- Import / Export --------------------------------------------------

    def import_servers(
        self, workspace_id: str, payload: CliMcpImportRequest
    ) -> CliMcpImportResponse:
        self._ensure_mutable_scope(payload.scope)
        servers = self._load_servers(workspace_id, payload.scope)
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        created: List[str] = []
        updated: List[str] = []
        skipped: List[str] = []
        for name, config in prepared.items():
            native = self._normalize_to_native(config)
            if name in servers and not payload.overwrite:
                skipped.append(name)
                continue
            if name in servers:
                updated.append(name)
            else:
                created.append(name)
            servers[name] = native
        if created or updated:
            self._write_servers(workspace_id, payload.scope, servers)
        return CliMcpImportResponse(
            workspaceId=workspace_id,
            scope=payload.scope,
            created=sorted(created),
            updated=sorted(updated),
            skipped=sorted(skipped),
        )

    def import_servers_from_file(
        self, workspace_id: str, payload: CliMcpImportUploadRequest
    ) -> CliMcpImportResponse:
        try:
            file_content = payload.file.decode("utf-8")
            json_data = json.loads(file_content)
            if "mcpServers" not in json_data:
                raise ValueError("Invalid format: missing 'mcpServers' field")
            mcp_servers_data = json_data["mcpServers"]
            if not isinstance(mcp_servers_data, dict):
                raise ValueError("Invalid format: 'mcpServers' must be an object")
            mcp_servers: Dict[str, CliMcpServerConfig] = {}
            for name, config in mcp_servers_data.items():
                if not isinstance(config, dict):
                    raise ValueError(
                        f"Invalid server config for '{name}': must be an object"
                    )
                mcp_servers[name] = CliMcpServerConfig(**config)
            import_request = CliMcpImportRequest(
                scope=payload.scope,
                mcpServers=mcp_servers,
                overwrite=payload.overwrite,
            )
            return self.import_servers(workspace_id, import_request)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except UnicodeDecodeError:
            raise ValueError("File encoding error: expected UTF-8")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to process import file: {str(e)}")

    def export_server(
        self, workspace_id: str, scope: CliMcpScope, server_name: str
    ) -> CliMcpServerExportResponse:
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        entry = servers[server_name]
        config = self._normalize_from_native(entry)
        return CliMcpServerExportResponse(
            workspaceId=workspace_id,
            scope=scope,
            mcpServers={server_name: config},
        )

    # === Internal Utilities ================================================

    @staticmethod
    def _ensure_mutable_scope(scope: CliMcpScope) -> None:
        if scope == CliMcpScope.PLUGIN:
            raise CliMcpReadOnlyScopeError("Plugin MCP servers are controlled by plugin enablement")
        if scope == CliMcpScope.EXTENSION:
            raise CliMcpReadOnlyScopeError("Extension MCP servers are controlled by Gemini extension enablement")

    def _scope_file(self, workspace_id: str, scope: CliMcpScope) -> Path:
        if scope == CliMcpScope.PLUGIN:
            raise CliMcpScopeNotSupportedError("Plugin MCP servers are read-only package sources")
        if scope == CliMcpScope.EXTENSION:
            raise CliMcpScopeNotSupportedError("Extension MCP servers are read-only package sources")
        if scope == CliMcpScope.PROJECT:
            return Path(get_workspace_path()) / self._config.project_file
        return self._config.user_file_path

    def _load_servers(
        self, workspace_id: str, scope: CliMcpScope
    ) -> Dict[str, Dict[str, Any]]:
        if scope == CliMcpScope.PLUGIN and self._config.tool == McpTool.CODEX:
            return self._load_codex_plugin_servers()
        if scope == CliMcpScope.EXTENSION and self._config.tool == McpTool.GEMINI:
            return self._load_gemini_extension_servers(workspace_id)
        path = self._scope_file(workspace_id, scope)
        data = self._config.strategy.read(path)
        raw = data.get(self._config.servers_key)
        if not isinstance(raw, dict):
            return {}
        return dict(raw)

    def _write_servers(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        servers: Dict[str, Dict[str, Any]],
    ) -> None:
        if scope == CliMcpScope.PLUGIN:
            raise CliMcpScopeNotSupportedError("Plugin MCP servers are read-only package sources")
        if scope == CliMcpScope.EXTENSION:
            raise CliMcpScopeNotSupportedError("Extension MCP servers are read-only package sources")
        path = self._scope_file(workspace_id, scope)
        data = self._config.strategy.read(path)
        data[self._config.servers_key] = servers
        self._config.strategy.write(path, data)

    def _prepare_payload(
        self, payload: Dict[str, CliMcpServerConfig]
    ) -> Dict[str, CliMcpServerConfig]:
        import re

        prepared: Dict[str, CliMcpServerConfig] = {}
        for name, config in payload.items():
            key = (name or "").strip()
            if not key:
                continue

            # Validate server_name format: only alphanumeric, hyphens, underscores allowed
            # This is to prevent special characters from corrupting the configuration file
            if not re.match(r'^[a-zA-Z0-9_-]+$', key):
                raise ValueError(
                    f"Invalid MCP server name '{key}': "
                    f"only alphanumeric characters, hyphens, and underscores are allowed"
                )

            prepared[key] = config
        return prepared

    # --- Format Conversion: Native <-> Unified -----------------------------

    def _normalize_from_native(
        self, native: Dict[str, Any]
    ) -> CliMcpServerConfig:
        """Convert native format to unified CliMcpServerConfig"""
        tool = self._config.tool

        if tool == McpTool.OPENCODE:
            return self._opencode_from_native(native)
        if tool == McpTool.CODEX:
            return self._codex_from_native(native)
        # Gemini: almost identical to Claude
        return CliMcpServerConfig.model_validate(native)

    def _normalize_to_native(
        self, config: CliMcpServerConfig
    ) -> Dict[str, Any]:
        """Convert unified CliMcpServerConfig to native format"""
        tool = self._config.tool

        if tool == McpTool.OPENCODE:
            return self._opencode_to_native(config)
        if tool == McpTool.CODEX:
            return self._codex_to_native(config)
        # Gemini: direct output
        return config.model_dump(exclude_none=True)

    def _to_runtime(
        self, name: str, native: Dict[str, Any]
    ) -> CliMcpServerRuntime:
        config = self._normalize_from_native(native)
        data = config.model_dump(exclude_none=True)
        if self._config.supports_toggle:
            data["enabled"] = native.get("enabled", True)
        else:
            data["enabled"] = True
        return CliMcpServerRuntime.model_validate(data)

    def _to_runtime_map(
        self, servers: Dict[str, Dict[str, Any]]
    ) -> Dict[str, CliMcpServerRuntime]:
        return {
            name: self._to_runtime(name, entry)
            for name, entry in sorted(servers.items())
        }

    def _load_codex_plugin_servers(self) -> Dict[str, Dict[str, Any]]:
        servers: Dict[str, Dict[str, Any]] = {}
        resolver = CodexPluginResourceResolver(get_codex_path_resolver())
        for server in resolver.mcp_servers(self._enabled_codex_plugin_ids()):
            servers[f"{server.plugin.name}:{server.name}"] = {
                **server.config,
                "enabled": True,
                "pluginId": server.plugin.plugin_id,
                "pluginName": server.plugin.name,
                "marketplaceName": server.plugin.marketplace_name or "",
            }
        return servers

    def _load_gemini_extension_servers(self, workspace_id: str) -> Dict[str, Dict[str, Any]]:
        return GeminiExtensionResourceResolver().enabled_mcp_servers(resolve_workspace_root())

    @staticmethod
    def _enabled_codex_plugin_ids() -> set[str]:
        resolver = get_codex_path_resolver()
        merged: dict[str, Any] = {}
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            path = resolver.resolve(layer, CodexResource.CONFIG)
            if not path.is_file():
                continue
            try:
                config = parse_toml(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            plugins = config.get("plugins")
            if not isinstance(plugins, dict):
                continue
            merged.update(plugins)
        return {
            plugin_id
            for plugin_id, plugin_config in merged.items()
            if isinstance(plugin_id, str)
            and isinstance(plugin_config, dict)
            and plugin_config.get("enabled") is True
        }

    # --- OpenCode Format Conversion -----------------------------------------

    @staticmethod
    def _opencode_from_native(native: Dict[str, Any]) -> CliMcpServerConfig:
        """
        OpenCode native format:
          - type: "local" -> stdio, "remote" -> http
          - command: ["npx", "-y", "..."] (list) -> command + args
          - url: remote URL
          - environment: {...} -> env
        """
        data: Dict[str, Any] = {}
        oc_type = native.get("type", "local")
        if oc_type == "remote":
            data["type"] = CliMcpTransportType.HTTP
            data["url"] = native.get("url")
        else:
            data["type"] = CliMcpTransportType.STDIO
            cmd_list = native.get("command")
            if isinstance(cmd_list, list) and cmd_list:
                data["command"] = cmd_list[0]
                if len(cmd_list) > 1:
                    data["args"] = cmd_list[1:]
            elif isinstance(cmd_list, str):
                data["command"] = cmd_list

        environment = native.get("environment")
        if isinstance(environment, dict):
            data["env"] = environment

        if native.get("headers"):
            data["headers"] = native["headers"]

        if "enabled" in native:
            data["enabled"] = native["enabled"]

        return CliMcpServerConfig.model_validate(data)

    @staticmethod
    def _opencode_to_native(config: CliMcpServerConfig) -> Dict[str, Any]:
        """Unified format -> OpenCode native format"""
        native: Dict[str, Any] = {}

        if config.type in (CliMcpTransportType.HTTP, CliMcpTransportType.SSE):
            native["type"] = "remote"
            if config.url:
                native["url"] = config.url
        else:
            native["type"] = "local"
            cmd_list: List[str] = []
            if config.command:
                cmd_list.append(config.command)
            if config.args:
                cmd_list.extend(config.args)
            if cmd_list:
                native["command"] = cmd_list

        if config.env:
            native["environment"] = config.env

        if config.headers:
            native["headers"] = config.headers

        return native

    # --- Codex Format Conversion -------------------------------------------

    @staticmethod
    def _codex_from_native(native: Dict[str, Any]) -> CliMcpServerConfig:
        """
        Codex native format:
          - No type field, determined by presence of url
          - command, args, env same as Claude
          - enabled natively supported
        """
        data: Dict[str, Any] = {
            key: value
            for key, value in native.items()
            if key
            not in {
                "command",
                "args",
                "env",
                "headers",
                "url",
            }
        }

        if native.get("url"):
            data["type"] = CliMcpTransportType.HTTP
            data["url"] = native["url"]
        else:
            data["type"] = CliMcpTransportType.STDIO

        if native.get("command"):
            data["command"] = native["command"]
        if native.get("args"):
            data["args"] = native["args"]
        if native.get("env"):
            data["env"] = native["env"]
        if native.get("headers"):
            data["headers"] = native["headers"]
        if "enabled" in native:
            data["enabled"] = native["enabled"]

        return CliMcpServerConfig.model_validate(data)

    @staticmethod
    def _codex_to_native(config: CliMcpServerConfig) -> Dict[str, Any]:
        """Unified format -> Codex native format (does not save type field)"""
        native: Dict[str, Any] = dict(config.model_extra or {})

        if config.type in (CliMcpTransportType.HTTP, CliMcpTransportType.SSE):
            if config.url:
                native["url"] = config.url
        else:
            if config.command:
                native["command"] = config.command
            if config.args:
                native["args"] = list(config.args)

        if config.env:
            native["env"] = dict(config.env)
        if config.headers:
            native["headers"] = dict(config.headers)
        if "enabled" in config.model_fields_set:
            native["enabled"] = getattr(config, "enabled", True)

        return native
