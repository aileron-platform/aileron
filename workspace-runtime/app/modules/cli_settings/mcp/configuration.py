"""CLI MCP server backend service

Provides CRUD operations for MCP configuration in Codex and OpenCode.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.core.revision import assert_revision, compute_revision
from app.config.settings import get_workspace_path
from app.modules.cli_settings.codex.plugin_controls import CodexPluginControlStore
from app.modules.cli_settings.codex.plugin_resources import CodexPluginResourceResolver
from app.modules.cli_settings.user_scope.paths import get_codex_path_resolver
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import get_user_scope_path_resolver
from app.modules.marketplace_operations.gate import get_marketplace_target_client_gate
from app.modules.marketplace_operations.plugin_resources import (
    plugin_resource_provenance,
    sanitize_plugin_definition,
)

from .config_strategies import (
    ConfigFileStrategy,
    JsonConfigStrategy,
    TomlConfigStrategy,
)
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
_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


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
    user_paths = get_user_scope_path_resolver()
    json_strategy = JsonConfigStrategy()
    toml_strategy = TomlConfigStrategy()

    return {
        McpTool.CODEX: CliMcpToolConfig(
            tool=McpTool.CODEX,
            project_file=".codex/config.toml",
            user_file_path=user_paths.resolve(
                UserScopeAgent.CODEX,
                UserScopeResource.MCP,
            ).runtime_path,
            servers_key="mcp_servers",
            strategy=toml_strategy,
            supports_toggle=True,
        ),
        McpTool.OPENCODE: CliMcpToolConfig(
            tool=McpTool.OPENCODE,
            project_file="opencode.json",
            user_file_path=user_paths.resolve(
                UserScopeAgent.OPENCODE,
                UserScopeResource.MCP,
            ).runtime_path,
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
        if config.tool is McpTool.CODEX:
            resolver = get_codex_path_resolver()
            self._codex_plugin_resolver = CodexPluginResourceResolver(resolver)
            self._codex_plugin_controls = CodexPluginControlStore(
                resolver,
                self._codex_plugin_resolver,
            )
        else:
            self._codex_plugin_resolver = None
            self._codex_plugin_controls = None

    # --- Public CRUD ------------------------------------------------------

    def list_servers(
        self, workspace_id: str, scope: CliMcpScope | None = None
    ) -> CliMcpServerCollectionResponse:
        generation = self._provider_generation()
        scopes = [scope] if scope else [CliMcpScope.PROJECT, CliMcpScope.USER]
        if not scope and self._config.tool == McpTool.CODEX:
            scopes.append(CliMcpScope.PLUGIN)
        groups: List[CliMcpScopeServers] = []
        for s in scopes:
            servers = self._load_servers(workspace_id, s)
            runtime_map = self._to_runtime_map(servers)
            groups.append(
                CliMcpScopeServers(
                    scope=s,
                    revision=self._servers_revision(servers),
                    mcpServers=runtime_map,
                )
            )
        return CliMcpServerCollectionResponse(
            workspaceId=workspace_id,
            scopes=groups,
            providerResourceGeneration=generation,
        )

    def get_scope(self, workspace_id: str, scope: CliMcpScope) -> CliMcpScopeResponse:
        generation = self._provider_generation()
        servers = self._load_servers(workspace_id, scope)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._servers_revision(servers),
            mcpServers=self._to_runtime_map(servers),
            providerResourceGeneration=generation,
        )

    def get_server(
        self, workspace_id: str, scope: CliMcpScope, server_name: str
    ) -> CliMcpScopeResponse:
        generation = self._provider_generation()
        servers = self._load_servers(workspace_id, scope)
        if server_name not in servers:
            raise CliMcpServerNotFoundError(server_name)
        entry = servers[server_name]
        runtime = self._to_runtime(entry)
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._servers_revision(servers),
            mcpServers={server_name: runtime},
            providerResourceGeneration=generation,
        )

    def create_servers(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        payload: CliMcpServerCreateRequest,
    ) -> CliMcpScopeResponse:
        self._ensure_mutable_scope(scope)
        file_path = self._scope_file(workspace_id, scope)
        with _write_lock(file_path):
            servers = self._load_servers(workspace_id, scope)
            assert_revision(self._servers_revision(servers), payload.revision)
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
            revision=self._servers_revision(all_servers),
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
        file_path = self._scope_file(workspace_id, scope)
        with _write_lock(file_path):
            servers = self._load_servers(workspace_id, scope)
            assert_revision(self._servers_revision(servers), payload.revision)
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
        runtime = self._to_runtime(updated[server_name])
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._servers_revision(updated),
            mcpServers={server_name: runtime},
        )

    def delete_server(
        self, workspace_id: str, scope: CliMcpScope, server_name: str, revision: str
    ) -> CliMcpServerDeleteResponse:
        self._ensure_mutable_scope(scope)
        file_path = self._scope_file(workspace_id, scope)
        with _write_lock(file_path):
            servers = self._load_servers(workspace_id, scope)
            assert_revision(self._servers_revision(servers), revision)
            if server_name not in servers:
                raise CliMcpServerNotFoundError(server_name)
            del servers[server_name]
            self._write_servers(workspace_id, scope, servers)
            updated = self._load_servers(workspace_id, scope)
        return CliMcpServerDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._servers_revision(updated),
        )

    def toggle_server_status(
        self,
        workspace_id: str,
        scope: CliMcpScope,
        server_name: str,
        enabled: bool,
        revision: str,
    ) -> CliMcpScopeResponse:
        self._ensure_mutable_scope(scope)
        if not self._config.supports_toggle:
            raise CliMcpToggleNotSupportedError(
                f"{self._config.tool.value} does not support MCP server toggle"
            )
        file_path = self._scope_file(workspace_id, scope)
        with _write_lock(file_path):
            servers = self._load_servers(workspace_id, scope)
            assert_revision(self._servers_revision(servers), revision)
            if server_name not in servers:
                raise CliMcpServerNotFoundError(server_name)
            entry = servers[server_name]
            entry["enabled"] = enabled
            self._write_servers(workspace_id, scope, servers)
            updated = self._load_servers(workspace_id, scope)
        runtime = self._to_runtime(updated[server_name])
        return CliMcpScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._servers_revision(updated),
            mcpServers={server_name: runtime},
        )

    # --- Import / Export --------------------------------------------------

    def import_servers(
        self, workspace_id: str, payload: CliMcpImportRequest
    ) -> CliMcpImportResponse:
        self._ensure_mutable_scope(payload.scope)
        file_path = self._scope_file(workspace_id, payload.scope)
        with _write_lock(file_path):
            servers = self._load_servers(workspace_id, payload.scope)
            assert_revision(self._servers_revision(servers), payload.revision)
            prepared = self._prepare_payload(payload.mcpServers)
            if not prepared:
                raise ValueError("Empty payload")
            created: List[str] = []
            updated_names: List[str] = []
            skipped: List[str] = []
            for name, config in prepared.items():
                native = self._normalize_to_native(config)
                if name in servers and not payload.overwrite:
                    skipped.append(name)
                    continue
                if name in servers:
                    updated_names.append(name)
                else:
                    created.append(name)
                servers[name] = native
            if created or updated_names:
                self._write_servers(workspace_id, payload.scope, servers)
                servers = self._load_servers(workspace_id, payload.scope)
        return CliMcpImportResponse(
            workspaceId=workspace_id,
            scope=payload.scope,
            revision=self._servers_revision(servers),
            created=sorted(created),
            updated=sorted(updated_names),
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
                revision=payload.revision,
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
            raise CliMcpReadOnlyScopeError(
                "Plugin MCP definitions are read-only; update their policy instead"
            )

    def _scope_file(self, workspace_id: str, scope: CliMcpScope) -> Path:
        if scope == CliMcpScope.PLUGIN:
            raise CliMcpScopeNotSupportedError(
                "Plugin MCP servers are read-only package sources"
            )
        if scope == CliMcpScope.PROJECT:
            return Path(get_workspace_path()) / self._config.project_file
        return self._config.user_file_path

    def _load_servers(
        self, workspace_id: str, scope: CliMcpScope
    ) -> Dict[str, Dict[str, Any]]:
        if scope == CliMcpScope.PLUGIN and self._config.tool == McpTool.CODEX:
            return self._load_codex_plugin_servers()
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
            raise CliMcpScopeNotSupportedError(
                "Plugin MCP servers are read-only package sources"
            )
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
            if not re.match(r"^[a-zA-Z0-9_-]+$", key):
                raise ValueError(
                    f"Invalid MCP server name '{key}': "
                    f"only alphanumeric characters, hyphens, and underscores are allowed"
                )

            prepared[key] = config
        return prepared

    @staticmethod
    def _servers_revision(servers: Dict[str, Dict[str, Any]]) -> str:
        content = json.dumps(servers, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    # --- Format Conversion: Native <-> Unified -----------------------------

    def _normalize_from_native(self, native: Dict[str, Any]) -> CliMcpServerConfig:
        """Convert native format to unified CliMcpServerConfig"""
        tool = self._config.tool

        if tool == McpTool.OPENCODE:
            return self._opencode_from_native(native)
        return self._codex_from_native(native)

    def _normalize_to_native(self, config: CliMcpServerConfig) -> Dict[str, Any]:
        """Convert unified CliMcpServerConfig to native format"""
        tool = self._config.tool

        if tool == McpTool.OPENCODE:
            return self._opencode_to_native(config)
        return self._codex_to_native(config)

    def _to_runtime(
        self,
        native: Dict[str, Any],
    ) -> CliMcpServerRuntime:
        config = self._normalize_from_native(native)
        data = config.model_dump(exclude_none=True)
        if self._config.supports_toggle:
            data["enabled"] = native.get("enabled", True)
        else:
            data["enabled"] = True
        return CliMcpServerRuntime.model_validate(data)

    def _to_runtime_map(
        self,
        servers: Dict[str, Dict[str, Any]],
    ) -> Dict[str, CliMcpServerRuntime]:
        return {
            name: self._to_runtime(entry) for name, entry in sorted(servers.items())
        }

    def _load_codex_plugin_servers(self) -> Dict[str, Dict[str, Any]]:
        if self._codex_plugin_resolver is None or self._codex_plugin_controls is None:
            raise CliMcpScopeNotSupportedError(
                "Plugin MCP servers are only available for Codex"
            )
        servers: Dict[str, Dict[str, Any]] = {}
        generation = self._provider_generation()
        policy_revision = self._codex_plugin_controls.user_revision()
        for server in self._codex_plugin_resolver.mcp_servers():
            marketplace_name = server.plugin.marketplace_name
            policy = self._codex_plugin_controls.mcp_policy(
                server.plugin.plugin_id,
                server.name,
            )
            key = f"{server.plugin.plugin_id}:{server.name}"
            servers[key] = {
                **sanitize_plugin_definition(
                    server.config,
                    installed_root=server.plugin.package_root,
                ),
                "enabled": policy.enabled,
                "scope": CliMcpScope.PLUGIN,
                "serverId": server.name,
                "pluginId": server.plugin.plugin_id,
                "pluginName": server.plugin.name,
                "marketplaceName": marketplace_name,
                "relativeSourcePath": server.relative_source_path,
                "readOnly": True,
                "editable": False,
                "generation": generation,
                "policy": policy.model_dump(mode="json", by_alias=True),
                "policyRevision": policy_revision,
                "effective": self._codex_plugin_controls.mcp_effective(
                    server,
                    policy,
                ),
                "provenance": plugin_resource_provenance(
                    target_client="codex",
                    plugin_id=server.plugin.plugin_id,
                    marketplace_id=marketplace_name,
                ).model_dump(mode="json", by_alias=True),
            }
        return servers

    def _provider_generation(self) -> int | None:
        if self._config.tool is not McpTool.CODEX:
            return None
        return get_marketplace_target_client_gate().generation("codex")

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
