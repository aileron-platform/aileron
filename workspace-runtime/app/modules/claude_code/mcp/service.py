"""MCP 伺服器後端服務"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from ..common import (
    DocumentScope,
    read_json_file,
    resolve_scope_root,
    workspace_root,
    write_json_file,
)

logger = logging.getLogger(__name__)
from .models import (
    McpImportRequest,
    McpImportResponse,
    McpImportUploadRequest,
    McpScopeResponse,
    McpScopeServers,
    McpServerCollectionResponse,
    McpServerConfig,
    McpServerCreateRequest,
    McpServerDeleteResponse,
    McpServerExportResponse,
    McpServerRuntime,
    McpServerUpdateRequest,
)


class McpScopeNotSupportedError(ValueError):
    """指定的 scope 不支援"""


class McpServerAlreadyExistsError(RuntimeError):
    """伺服器名稱重複"""


class McpServerNotFoundError(KeyError):
    """伺服器不存在"""




@dataclass
class McpServerEntry:
    """記錄單一 MCP 伺服器設定"""

    name: str
    config: McpServerConfig

    def to_runtime(self, enabled: bool = True) -> McpServerRuntime:
        """轉換為 Runtime 模型，包含 enabled 狀態"""
        data = self.config.model_dump(by_alias=True, exclude_none=True)
        data["enabled"] = enabled
        return McpServerRuntime.model_validate(data)

    def to_storage(self) -> Dict[str, Any]:
        return self.config.model_dump(by_alias=True, exclude_none=True)




class McpService:
    """管理 MCP 伺服器設定的檔案服務"""

    SUPPORTED_SCOPES: tuple[DocumentScope, ...] = (
        DocumentScope.PROJECT,
        DocumentScope.USER,
        DocumentScope.LOCAL,
    )
    # PLUGIN scope 支援讀取但不支援寫入
    READABLE_SCOPES: tuple[DocumentScope, ...] = (
        DocumentScope.PROJECT,
        DocumentScope.USER,
        DocumentScope.LOCAL,
        DocumentScope.PLUGIN,
    )
    _PROJECT_FILE = ".mcp.json"
    _USER_FILE = ".claude.json"
    _LOCAL_FILE = ".claude.json"

    # === 公開方法 ==================================================

    def list_servers(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> McpServerCollectionResponse:
        """
        列出所有 MCP servers

        修改：自動整合 plugin MCP servers
        """
        # 驗證 scope（如果指定）
        if scope is not None:
            scope = self._normalize_scope_for_read(scope)

            # 如果是 PLUGIN scope，直接返回 plugin servers
            if scope == DocumentScope.PLUGIN:
                plugin_servers = self._load_plugin_mcp_servers(workspace_id)
                return McpServerCollectionResponse(
                    workspaceId=workspace_id,
                    scopes=[McpScopeServers(scope=DocumentScope.PLUGIN, mcpServers=plugin_servers)]
                )

            scopes = [scope]
        else:
            scopes = self.SUPPORTED_SCOPES

        groups: List[McpScopeServers] = []

        # 1. 載入原有的 MCP servers（project/user/local）
        for scope_item in scopes:
            entries = self._load_scope_entries(workspace_id, scope_item)
            groups.append(
                McpScopeServers(
                    scope=scope_item,
                    mcpServers=self._runtime_map(entries, workspace_id),
                )
            )

        # 2. 載入 plugin MCP servers（新增）
        if scope is None or scope == DocumentScope.PLUGIN:
            try:
                plugin_servers = self._load_plugin_mcp_servers(workspace_id)
                if plugin_servers:
                    groups.append(
                        McpScopeServers(
                            scope=DocumentScope.PLUGIN,
                            mcpServers=plugin_servers
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to load plugin MCP servers: {e}")

        return McpServerCollectionResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> McpScopeResponse:
        normalized = self._normalize_scope_for_read(scope)

        # 如果是 PLUGIN scope，載入 plugin MCP servers
        if normalized == DocumentScope.PLUGIN:
            plugin_servers = self._load_plugin_mcp_servers(workspace_id)
            return McpScopeResponse(
                workspaceId=workspace_id,
                scope=normalized,
                mcpServers=plugin_servers,
            )

        entries = self._load_scope_entries(workspace_id, normalized)
        return McpScopeResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers=self._runtime_map(entries, workspace_id),
        )

    def get_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpScopeResponse:
        normalized = self._normalize_scope_for_read(scope)

        # 如果是 PLUGIN scope，從 plugin servers 中查找
        if normalized == DocumentScope.PLUGIN:
            plugin_servers = self._load_plugin_mcp_servers(workspace_id)
            if server_name not in plugin_servers:
                raise McpServerNotFoundError(server_name)
            return McpScopeResponse(
                workspaceId=workspace_id,
                scope=normalized,
                mcpServers={server_name: plugin_servers[server_name]},
            )

        entries = self._load_scope_entries(workspace_id, normalized)
        if server_name not in entries:
            raise McpServerNotFoundError(server_name)
        entry = entries[server_name]
        disabled_servers = self._load_disabled_servers(workspace_id)
        enabled = server_name not in disabled_servers
        response = McpScopeResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers={server_name: entry.to_runtime(enabled=enabled)},
        )
        return response

    def create_servers(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: McpServerCreateRequest,
    ) -> McpScopeResponse:
        normalized = self._normalize_scope(scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        duplicates = [name for name in prepared if name in entries]
        if duplicates:
            raise McpServerAlreadyExistsError(
                f"Duplicate server names: {', '.join(sorted(duplicates))}"
            )
        for name, config in prepared.items():
            entry = McpServerEntry(
                name=name,
                config=config,
            )
            entries[name] = entry
        self._write_scope_entries(workspace_id, normalized, entries)
        response = McpScopeResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers=self._runtime_map(entries, workspace_id),
        )
        return response

    def update_server(
        self,
        workspace_id: str,
        scope: DocumentScope,
        server_name: str,
        payload: McpServerUpdateRequest,
    ) -> McpScopeResponse:
        normalized = self._normalize_scope(scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        if server_name not in entries:
            raise McpServerNotFoundError(server_name)
        entry = entries[server_name]
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        if len(prepared) > 1:
            raise ValueError("Only one server can be updated per request")
        new_name, config = next(iter(prepared.items()))
        if new_name != server_name:
            raise McpServerAlreadyExistsError(
                f"Payload server name '{new_name}' does not match target '{server_name}'"
            )
        entry.config = config
        entries[server_name] = entry
        self._write_scope_entries(workspace_id, normalized, entries)
        response = McpScopeResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers={server_name: entry.to_runtime()},
        )
        return response

    def delete_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpServerDeleteResponse:
        normalized = self._normalize_scope(scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        if server_name not in entries:
            raise McpServerNotFoundError(server_name)
        entries.pop(server_name, None)
        self._write_scope_entries(workspace_id, normalized, entries)
        return McpServerDeleteResponse(
            workspaceId=workspace_id,
            scope=normalized,
        )

    def import_servers(
        self, workspace_id: str, payload: McpImportRequest
    ) -> McpImportResponse:
        normalized = self._normalize_scope(payload.scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        prepared = self._prepare_payload(payload.mcpServers)
        if not prepared:
            raise ValueError("Empty payload")
        created: List[str] = []
        updated: List[str] = []
        skipped: List[str] = []
        for name, config in prepared.items():
            if name in entries and not payload.overwrite:
                skipped.append(name)
                continue
            if name in entries:
                entry = entries[name]
                entry.config = config
                entries[name] = entry
                updated.append(name)
            else:
                entry = McpServerEntry(
                    name=name,
                    config=config,
                )
                entries[name] = entry
                created.append(name)
        if created or updated:
            self._write_scope_entries(workspace_id, normalized, entries)
        return McpImportResponse(
            workspaceId=workspace_id,
            scope=normalized,
            created=sorted(created),
            updated=sorted(updated),
            skipped=sorted(skipped),
        )

    def import_servers_from_file(
        self, workspace_id: str, payload: McpImportUploadRequest
    ) -> McpImportResponse:
        """從上傳的 JSON 檔案匯入 MCP 伺服器配置"""
        try:
            # 解析 JSON 檔案內容
            file_content = payload.file.decode('utf-8')
            json_data = json.loads(file_content)

            # 檢查是否包含 mcpServers 欄位
            if 'mcpServers' not in json_data:
                raise ValueError("Invalid format: missing 'mcpServers' field")

            mcp_servers_data = json_data['mcpServers']
            if not isinstance(mcp_servers_data, dict):
                raise ValueError("Invalid format: 'mcpServers' must be an object")

            # 轉換為 McpServerConfig 物件
            mcp_servers = {}
            for name, config in mcp_servers_data.items():
                if not isinstance(config, dict):
                    raise ValueError(f"Invalid server config for '{name}': must be an object")


                mcp_servers[name] = McpServerConfig(**config)

            # 建立匯入請求
            import_request = McpImportRequest(
                scope=payload.scope,
                mcpServers=mcp_servers,
                overwrite=payload.overwrite
            )

            # 執行匯入
            return self.import_servers(workspace_id, import_request)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except UnicodeDecodeError:
            raise ValueError("File encoding error: expected UTF-8")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to process import file: {str(e)}")

    def export_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpServerExportResponse:
        normalized = self._normalize_scope(scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        if server_name not in entries:
            raise McpServerNotFoundError(server_name)
        entry = entries[server_name]
        return McpServerExportResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers={server_name: entry.config},
        )

    def toggle_server_status(
        self, workspace_id: str, scope: DocumentScope, server_name: str, enabled: bool
    ) -> McpScopeResponse:
        """切換 MCP 伺服器的啟用/停用狀態

        Args:
            workspace_id: Workspace ID
            scope: 設定範圍
            server_name: 伺服器名稱
            enabled: True 為啟用，False 為停用

        Returns:
            更新後的 MCP 伺服器資訊

        Note:
            - 對於 plugin scope，會使用 plugin:{plugin_name}:{server_name} 格式
            - 對於其他 scope，使用 {server_name} 格式
        """
        # 處理 plugin scope
        if scope == DocumentScope.PLUGIN:
            return self._toggle_plugin_server_status(workspace_id, server_name, enabled)

        # 處理一般 scope (project/user/local)
        normalized = self._normalize_scope(scope)
        entries = self._load_scope_entries(workspace_id, normalized)
        if server_name not in entries:
            raise McpServerNotFoundError(server_name)

        # 載入當前的停用清單
        disabled_servers = self._load_disabled_servers(workspace_id)

        # 更新停用清單
        if enabled:
            # 啟用：從停用清單中移除
            if server_name in disabled_servers:
                disabled_servers.remove(server_name)
        else:
            # 停用：加入停用清單
            if server_name not in disabled_servers:
                disabled_servers.append(server_name)

        # 儲存更新後的停用清單
        self._save_disabled_servers(workspace_id, disabled_servers)

        # 回傳更新後的伺服器資訊
        entry = entries[server_name]
        return McpScopeResponse(
            workspaceId=workspace_id,
            scope=normalized,
            mcpServers={server_name: entry.to_runtime(enabled=enabled)},
        )

    # === 內部工具 ==================================================

    def _normalize_optional_scope(
        self, scope: DocumentScope | None
    ) -> DocumentScope | None:
        if scope is None:
            return None
        return self._normalize_scope(scope)

    def _normalize_scope(self, scope: DocumentScope) -> DocumentScope:
        """驗證 scope 是否支援寫入操作"""
        if scope not in self.SUPPORTED_SCOPES:
            raise McpScopeNotSupportedError(f"Unsupported scope: {scope}")
        return scope

    def _normalize_scope_for_read(self, scope: DocumentScope) -> DocumentScope:
        """驗證 scope 是否支援讀取操作（包含 PLUGIN）"""
        if scope not in self.READABLE_SCOPES:
            raise McpScopeNotSupportedError(f"Unsupported scope: {scope}")
        return scope

    def _project_file(self, workspace_id: str) -> Path:
        """Project scope: /workspace/.mcp.json (專案根目錄，與團隊共享)"""
        return workspace_root() / self._PROJECT_FILE

    def _local_file(self) -> Path:
        """Local scope: ~/.claude.json (巢狀結構: projects -> /workspace -> mcpServers)"""
        return Path.home() / self._LOCAL_FILE

    def _user_file(self) -> Path:
        """User scope: ~/.claude.json (直接結構: root -> mcpServers)"""
        return Path.home() / self._USER_FILE

    def _possible_user_project_keys(self, workspace_id: str) -> List[str]:
        """根據文檔範例，user scope的專案路徑識別"""
        workspace_base = workspace_root() / workspace_id
        normalized = workspace_base.resolve()

        # 按照文檔中claude.json的範例格式
        raw_candidates: List[str | None] = [
            "/workspace",  # 最常見的 key，優先嘗試
            normalized.as_posix(),  # 完整解析路徑
            workspace_base.as_posix(),  # 基本路徑
            str(normalized),  # 字串格式
            f"/{workspace_id}" if not workspace_id.startswith("/") else workspace_id,  # 相對workspace_id
            str(workspace_root()),  # workspace root 路徑
        ]
        seen: List[str] = []
        for candidate in raw_candidates:
            if not candidate:
                continue
            if candidate not in seen:
                seen.append(candidate)
        return seen

    def _primary_user_project_key(self, workspace_id: str) -> str:
        return self._possible_user_project_keys(workspace_id)[0]

    def _load_scope_entries(
        self, workspace_id: str, scope: DocumentScope
    ) -> Dict[str, McpServerEntry]:
        if scope == DocumentScope.PROJECT:
            return self._load_project_entries(workspace_id)
        if scope == DocumentScope.LOCAL:
            return self._load_local_entries(workspace_id)
        if scope == DocumentScope.USER:
            return self._load_user_entries(workspace_id)
        return {}

    def _write_scope_entries(
        self,
        workspace_id: str,
        scope: DocumentScope,
        entries: Dict[str, McpServerEntry],
    ) -> None:
        if scope == DocumentScope.PROJECT:
            self._write_project_entries(workspace_id, entries)
        elif scope == DocumentScope.LOCAL:
            self._write_local_entries(workspace_id, entries)
        elif scope == DocumentScope.USER:
            self._write_user_entries(workspace_id, entries)

    # --- Project ----------------------------------------------------

    def _load_project_entries(
        self, workspace_id: str
    ) -> Dict[str, McpServerEntry]:
        file_path = self._project_file(workspace_id)
        data = read_json_file(file_path)
        raw_servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        return self._decode_servers(raw_servers)

    def _write_project_entries(
        self, workspace_id: str, entries: Dict[str, McpServerEntry]
    ) -> None:
        file_path = self._project_file(workspace_id)
        data = read_json_file(file_path)
        data = dict(data) if isinstance(data, dict) else {}
        data["mcpServers"] = self._encode_servers(entries)
        write_json_file(file_path, data)

    # --- Local -------------------------------------------------------

    def _load_local_entries(
        self, workspace_id: str
    ) -> Dict[str, McpServerEntry]:
        """Local scope 使用 ~/.claude.json 巢狀結構: projects -> /workspace -> mcpServers"""
        path = self._local_file()
        data = read_json_file(path)
        if not isinstance(data, dict):
            return {}
        projects = data.get("projects")
        if not isinstance(projects, dict):
            return {}
        for key in self._possible_user_project_keys(workspace_id):
            project_block = projects.get(key)
            if isinstance(project_block, dict):
                raw = project_block.get("mcpServers")
                decoded = self._decode_servers(raw)
                if decoded:
                    return decoded
        return {}

    def _update_project_block_field(
        self, workspace_id: str, field_name: str, value: Any
    ) -> None:
        """更新 ~/.claude.json 中 project_block 的特定欄位，保留其他欄位

        Args:
            workspace_id: Workspace ID
            field_name: 要更新的欄位名稱（如 'mcpServers', 'disabledMcpServers'）
            value: 欄位值
        """
        path = self._local_file()
        data = read_json_file(path)
        if not isinstance(data, dict):
            data = {}

        # 確保 projects 存在
        if "projects" not in data:
            data["projects"] = {}
        projects = data["projects"]
        if not isinstance(projects, dict):
            projects = {}
            data["projects"] = projects

        # 取得 project key
        key = self._primary_user_project_key(workspace_id)

        # 取得現有的 project_block，如果不存在則創建新的
        if key not in projects:
            projects[key] = {}
        project_block = projects[key]
        if not isinstance(project_block, dict):
            project_block = {}
            projects[key] = project_block

        # 更新指定欄位，保留其他欄位
        project_block[field_name] = value

        write_json_file(path, data)

    def _write_local_entries(
        self, workspace_id: str, entries: Dict[str, McpServerEntry]
    ) -> None:
        """Local scope 使用 ~/.claude.json 巢狀結構: projects -> /workspace -> mcpServers

        注意：此方法會保留現有的 project_block 內容（如 disabledMcpServers），只更新 mcpServers
        """
        self._update_project_block_field(
            workspace_id, "mcpServers", self._encode_servers(entries)
        )

    # --- User -------------------------------------------------------

    def _load_user_entries(
        self, workspace_id: str  # pylint: disable=unused-argument
    ) -> Dict[str, McpServerEntry]:
        """User scope 使用 ~/.claude.json 直接結構: root -> mcpServers"""
        path = self._user_file()
        data = read_json_file(path)
        if not isinstance(data, dict):
            return {}
        raw = data.get("mcpServers")
        return self._decode_servers(raw)

    def _write_user_entries(
        self, workspace_id: str, entries: Dict[str, McpServerEntry]  # pylint: disable=unused-argument
    ) -> None:
        """User scope 使用 ~/.claude.json 直接結構: root -> mcpServers"""
        path = self._user_file()
        data = read_json_file(path)
        if not isinstance(data, dict):
            data = {}
        data["mcpServers"] = self._encode_servers(entries)
        write_json_file(path, data)

    # --- 共用編碼工具 -----------------------------------------------

    def _decode_servers(self, payload: Any) -> Dict[str, McpServerEntry]:
        result: Dict[str, McpServerEntry] = {}
        items = self._iter_payload_items(payload)
        for name, raw in items:
            if not name or not isinstance(raw, dict):
                continue
            try:
                config = McpServerConfig.model_validate(raw)
            except Exception:
                continue
            result[name] = McpServerEntry(
                name=name,
                config=config,
            )
        return result

    def _encode_servers(
        self, entries: Dict[str, McpServerEntry]
    ) -> Dict[str, Dict[str, Any]]:
        encoded: Dict[str, Dict[str, Any]] = {}
        for name in sorted(entries.keys()):
            encoded[name] = entries[name].to_storage()
        return encoded

    def _iter_payload_items(self, payload: Any) -> Iterable[Tuple[str, Dict[str, Any]]]:
        if isinstance(payload, dict):
            for name, raw in payload.items():
                if isinstance(raw, dict):
                    yield name, raw

    
    def _runtime_map(
        self, entries: Dict[str, McpServerEntry], workspace_id: str
    ) -> Dict[str, McpServerRuntime]:
        """將 McpServerEntry 轉換為 McpServerRuntime，包含 enabled 狀態"""
        disabled_servers = self._load_disabled_servers(workspace_id)
        return {
            name: entries[name].to_runtime(enabled=(name not in disabled_servers))
            for name in sorted(entries.keys())
        }

    def _prepare_payload(
        self, payload: Dict[str, McpServerConfig]
    ) -> Dict[str, McpServerConfig]:
        prepared: Dict[str, McpServerConfig] = {}
        for name, config in payload.items():
            key = (name or "").strip()
            if not key:
                continue
            prepared[key] = config
        return prepared

    # --- MCP 開關管理 -----------------------------------------------

    def _load_disabled_servers(self, workspace_id: str) -> List[str]:
        """從 ~/.claude.json 的 projects./workspace.disabledMcpServers 讀取停用清單"""
        path = self._local_file()
        data = read_json_file(path)
        if not isinstance(data, dict):
            logger.debug(f"[MCP Toggle] ~/.claude.json is not a dict")
            return []

        projects = data.get("projects")
        if not isinstance(projects, dict):
            logger.debug(f"[MCP Toggle] projects is not a dict")
            return []

        # 嘗試所有可能的 workspace key
        candidates = self._possible_user_project_keys(workspace_id)
        logger.debug(f"[MCP Toggle] Trying candidates: {candidates}")
        logger.debug(f"[MCP Toggle] Available project keys: {list(projects.keys())}")

        for key in candidates:
            project_block = projects.get(key)
            if isinstance(project_block, dict):
                disabled = project_block.get("disabledMcpServers")
                if isinstance(disabled, list):
                    logger.info(f"[MCP Toggle] Found disabled servers in key '{key}': {disabled}")
                    return disabled

        logger.debug(f"[MCP Toggle] No disabled servers found")
        return []

    def _save_disabled_servers(self, workspace_id: str, disabled_servers: List[str]) -> None:
        """將停用清單寫回 ~/.claude.json 的 projects./workspace.disabledMcpServers

        注意：此方法會保留現有的 project_block 內容（如 mcpServers），只更新 disabledMcpServers
        """
        self._update_project_block_field(workspace_id, "disabledMcpServers", disabled_servers)

    def _load_plugin_mcp_servers(
        self,
        workspace_id: str
    ) -> Dict[str, McpServerRuntime]:
        """
        載入 plugin MCP servers（新方法）

        支援透過 disabledMcpServers 停用 plugin MCP servers
        格式：plugin:{plugin_name}:{server_name}
        範例：plugin:chrome-devtools-mcp:chrome-devtools

        Returns:
            Dict[server_name, McpServerRuntime]: MCP servers 字典
        """
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        # 載入所有 plugin MCP servers（按 plugin 分組）
        plugin_mcp_dict = loader.load_plugin_mcp_servers(workspace_id)

        # 載入 disabled servers 清單
        disabled_servers = self._load_disabled_servers(workspace_id)

        # 合併為單一字典（server_name → McpServerRuntime）
        all_servers = {}

        for plugin_id, servers in plugin_mcp_dict.items():
            plugin_name, marketplace_name = plugin_id.split("@")

            # 防禦性檢查：確保 servers 是 dict
            if not isinstance(servers, dict):
                logger.warning(f"Plugin '{plugin_id}' MCP servers is not a dict: {type(servers)}")
                continue

            for server_name, server_config in servers.items():
                # 防禦性檢查：確保 server_config 是 dict
                if not isinstance(server_config, dict):
                    logger.warning(f"Plugin '{plugin_id}' server '{server_name}' config is not a dict: {type(server_config)}")
                    continue

                # 檢查是否被停用
                # 支援兩種格式：
                # 1. plugin:{plugin_name}:{server_name}
                # 2. {server_name} (向後相容)
                plugin_server_key = f"plugin:{plugin_name}:{server_name}"
                is_disabled = (
                    plugin_server_key in disabled_servers or
                    server_name in disabled_servers
                )

                # 轉換為 McpServerRuntime 格式
                try:
                    runtime_data = {
                        **server_config,
                        "enabled": not is_disabled,  # 根據 disabled 清單設定
                        "pluginName": plugin_name,
                        "marketplaceName": marketplace_name
                    }
                    runtime = McpServerRuntime.model_validate(runtime_data)
                    all_servers[server_name] = runtime
                except Exception as e:
                    logger.error(f"Failed to validate MCP server '{server_name}' from plugin '{plugin_id}': {e}")
                    continue

        return all_servers

    def _toggle_plugin_server_status(
        self,
        workspace_id: str,
        server_name: str,
        enabled: bool
    ) -> McpScopeResponse:
        """
        切換 plugin MCP 伺服器的啟用/停用狀態

        使用 plugin:{plugin_name}:{server_name} 格式儲存到 disabledMcpServers
        """
        # 載入所有 plugin MCP servers 以找到對應的 plugin_name
        plugin_servers = self._load_plugin_mcp_servers(workspace_id)

        if server_name not in plugin_servers:
            raise McpServerNotFoundError(server_name)

        server_runtime = plugin_servers[server_name]
        plugin_name = server_runtime.plugin_name

        if not plugin_name:
            raise ValueError(f"Server '{server_name}' is not a plugin server")

        # 載入當前的停用清單
        disabled_servers = self._load_disabled_servers(workspace_id)

        # 建構 plugin server key
        plugin_server_key = f"plugin:{plugin_name}:{server_name}"

        # 更新停用清單
        if enabled:
            # 啟用：從停用清單中移除（兩種格式都移除）
            if plugin_server_key in disabled_servers:
                disabled_servers.remove(plugin_server_key)
            if server_name in disabled_servers:
                disabled_servers.remove(server_name)
        else:
            # 停用：加入停用清單（使用 plugin 專用格式）
            if plugin_server_key not in disabled_servers:
                disabled_servers.append(plugin_server_key)
            # 移除舊的通用格式（如果存在）
            if server_name in disabled_servers:
                disabled_servers.remove(server_name)

        # 儲存更新後的停用清單
        self._save_disabled_servers(workspace_id, disabled_servers)

        # 更新 server runtime 的 enabled 狀態
        server_runtime.enabled = enabled

        # 回傳更新後的伺服器資訊
        return McpScopeResponse(
            workspaceId=workspace_id,
            scope=DocumentScope.PLUGIN,
            mcpServers={server_name: server_runtime},
        )

