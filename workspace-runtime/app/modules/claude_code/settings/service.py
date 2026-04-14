"""Claude Code Settings 服務"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from ..common import DocumentScope, read_json_file, resolve_scope_root, write_json_file
from .models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    Marketplace,
    MarketplaceListResponse,
    MarketplaceMetadata,
    MarketplaceOwner,
    McpServerPolicy,
    PermissionMode,
    PermissionRules,
    PluginMetadata,
)


class SettingsService:
    """提供 Claude Code settings 讀寫操作"""

    _SETTINGS_FILES = {
        DocumentScope.USER: "settings.json",
        DocumentScope.PROJECT: "settings.json",
        DocumentScope.LOCAL: "settings.local.json",
    }

    def get_settings(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> ClaudeCodeSettings:
        """讀取目前生效的設定，必要時限定權限來源"""

        if scope is not None:
            state = self._read_scope_state(workspace_id, scope)
            mode_value = self._extract_mode(state) or PermissionMode.DEFAULT
            permissions = self._extract_permissions(state) or PermissionRules()
            env_values = state.get("env") if isinstance(state.get("env"), dict) else {}
            model_value = self._extract_model(state)
            output_style = state.get("outputStyle")
            if not isinstance(output_style, str):
                output_style = None
            enabled_plugins = self._extract_enabled_plugins(state)
            api_key_helper = self._extract_api_key_helper(state)
            cleanup_period = self._extract_cleanup_period(state)
            include_co_authored_by = self._extract_bool(state, "includeCoAuthoredBy")
            disable_all_hooks = self._extract_bool(state, "disableAllHooks")
            enable_all_project_mcp = self._extract_bool(
                state, "enableAllProjectMcpServers"
            )
            _, enabled_mcpjson = self._extract_string_list(
                state, "enabledMcpjsonServers"
            )
            _, disabled_mcpjson = self._extract_string_list(
                state, "disabledMcpjsonServers"
            )
            _, allowed_mcp = self._extract_mcp_policies(state, "allowedMcpServers")
            _, denied_mcp = self._extract_mcp_policies(state, "deniedMcpServers")

            resolved_include = (
                include_co_authored_by if include_co_authored_by is not None else True
            )
            resolved_disable = (
                disable_all_hooks if disable_all_hooks is not None else False
            )
            resolved_enable_project = (
                enable_all_project_mcp if enable_all_project_mcp is not None else False
            )

            return ClaudeCodeSettings(
                mode=mode_value,
                defaultMode=mode_value,
                outputStyle=output_style,
                permissions=permissions,
                env={
                    str(key): str(value)
                    for key, value in env_values.items()
                    if key is not None and value is not None
                },
                model=model_value,
                enabledPlugins=enabled_plugins,
                apiKeyHelper=api_key_helper,
                cleanupPeriodDays=cleanup_period,
                includeCoAuthoredBy=resolved_include,
                disableAllHooks=resolved_disable,
                enableAllProjectMcpServers=resolved_enable_project,
                enabledMcpjsonServers=enabled_mcpjson,
                disabledMcpjsonServers=disabled_mcpjson,
                allowedMcpServers=allowed_mcp,
                deniedMcpServers=denied_mcp,
            )

        aggregated = self._aggregate_settings(workspace_id)
        return aggregated

    def update_settings(
        self,
        workspace_id: str,
        payload: ClaudeCodeSettingsUpdateRequest,
        scope: DocumentScope,
    ) -> ClaudeCodeSettings:
        """更新指定範圍的設定檔，回傳合併後結果"""

        file_path = self._settings_file(workspace_id, scope)
        state = read_json_file(file_path)

        # 定義欄位映射：payload 屬性 -> state 鍵名 -> 值轉換器
        field_mappings: List[Tuple[str, str, Optional[Callable[[Any], Any]]]] = [
            ("output_style", "outputStyle", None),
            ("model", "model", None),
            ("api_key_helper", "apiKeyHelper", None),
            ("cleanup_period_days", "cleanupPeriodDays", None),
            ("include_co_authored_by", "includeCoAuthoredBy", None),
            ("disable_all_hooks", "disableAllHooks", None),
            ("enable_all_project_mcp_servers", "enableAllProjectMcpServers", None),
        ]

        # 處理簡單欄位
        for payload_attr, state_key, transformer in field_mappings:
            if payload.field_provided(payload_attr):
                value = getattr(payload, payload_attr)
                if value is None:
                    state.pop(state_key, None)
                else:
                    state[state_key] = transformer(value) if transformer else value

        # 處理 mode 欄位（特殊邏輯）
        resolved_mode = payload.resolved_mode()
        if resolved_mode is not None or payload.field_provided("mode") or payload.field_provided("default_mode"):
            if resolved_mode is not None:
                state["defaultMode"] = resolved_mode if isinstance(resolved_mode, str) else resolved_mode.value
            else:
                state.pop("defaultMode", None)

        # 處理複雜欄位
        if payload.field_provided("permissions"):
            state["permissions"] = payload.permissions.model_dump() if payload.permissions else None

        if payload.field_provided("env"):
            state["env"] = payload.env if payload.env is not None else None

        if payload.field_provided("enabled_plugins"):
            state["enabledPlugins"] = payload.enabled_plugins if payload.enabled_plugins is not None else None

        # 處理列表欄位
        for payload_attr, state_key in [
            ("enabled_mcpjson_servers", "enabledMcpjsonServers"),
            ("disabled_mcpjson_servers", "disabledMcpjsonServers"),
        ]:
            if payload.field_provided(payload_attr):
                value = getattr(payload, payload_attr)
                state[state_key] = value if value else None

        # 處理 MCP 伺服器策略列表
        for payload_attr, state_key in [
            ("allowed_mcp_servers", "allowedMcpServers"),
            ("denied_mcp_servers", "deniedMcpServers"),
        ]:
            if payload.field_provided(payload_attr):
                value = getattr(payload, payload_attr)
                if value:
                    state[state_key] = [entry.model_dump(by_alias=True, exclude_none=True) for entry in value]
                else:
                    state.pop(state_key, None)

        # 寫入檔案，加入錯誤處理
        if state:
            try:
                write_json_file(file_path, state)
                # 驗證寫入成功
                if not file_path.exists() or file_path.stat().st_size == 0:
                    raise IOError(f"Failed to write settings file: {file_path}")
            except (IOError, OSError, PermissionError) as e:
                logger.error(
                    "Failed to save settings file",
                    extra={
                        "file_path": str(file_path),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "workspace_id": workspace_id,
                        "scope": scope.value
                    }
                )
                raise
        elif file_path.exists():
            try:
                file_path.unlink()
            except (IOError, OSError, PermissionError) as e:
                logger.error(
                    "Failed to delete settings file",
                    extra={
                        "file_path": str(file_path),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "workspace_id": workspace_id,
                        "scope": scope.value
                    }
                )
                raise

        return self.get_settings(workspace_id, scope)

    # 內部工具 -------------------------------------------------------
    def _aggregate_settings(self, workspace_id: str) -> ClaudeCodeSettings:
        """聚合所有範圍的設定，使用統一的欄位提取邏輯"""

        # 定義所有可聚合的欄位及其提取器
        aggregatable_fields: Dict[str, Tuple[Any, Callable[[Dict[str, Any]], Any]]] = {
            "mode": (None, self._extract_mode),
            "output_style": (None, lambda s: s.get("outputStyle")),
            "permissions": (PermissionRules(), self._extract_permissions),
            "model_value": (None, self._extract_model),
            "include_co_authored_by": (None, lambda s: self._extract_bool(s, "includeCoAuthoredBy")),
            "disable_all_hooks": (None, lambda s: self._extract_bool(s, "disableAllHooks")),
            "enable_all_project_mcp": (None, lambda s: self._extract_bool(s, "enableAllProjectMcpServers")),
            "api_key_helper": (None, self._extract_api_key_helper),
            "cleanup_period": (None, self._extract_cleanup_period),
        }

        # 需要合併的欄位（dict 或 list）
        mergeable_fields: Dict[str, Any] = {
            "env": {},
            "enabled_plugins": {},
            "enabled_mcpjson": None,
            "disabled_mcpjson": None,
            "allowed_mcp": None,
            "denied_mcp": None,
        }

        for scope in self._merge_order():
            state = self._read_scope_state(workspace_id, scope)
            if not state:
                continue

            # 處理單值欄位（後面的覆蓋前面的）
            for field_name, (default, extractor) in aggregatable_fields.items():
                value = extractor(state)
                if value is not None:
                    aggregatable_fields[field_name] = (value, extractor)

            # 處理合併欄位
            if isinstance(state.get("env"), dict):
                mergeable_fields["env"].update(
                    {str(k): str(v) for k, v in state["env"].items() if k is not None and v is not None}
                )

            plugins = self._extract_enabled_plugins(state)
            if plugins:
                mergeable_fields["enabled_plugins"].update(plugins)

            for list_key, extractor_name, target_key in [
                ("enabledMcpjsonServers", "_extract_string_list", "enabled_mcpjson"),
                ("disabledMcpjsonServers", "_extract_string_list", "disabled_mcpjson"),
                ("allowedMcpServers", "_extract_mcp_policies", "allowed_mcp"),
                ("deniedMcpServers", "_extract_mcp_policies", "denied_mcp"),
            ]:
                provided, value = getattr(self, extractor_name)(state, list_key)
                if provided:
                    mergeable_fields[target_key] = value

        # 解包聚合結果
        mode = aggregatable_fields["mode"][0] or PermissionMode.DEFAULT
        output_style = aggregatable_fields["output_style"][0]
        permissions = aggregatable_fields["permissions"][0]
        model_value = aggregatable_fields["model_value"][0]
        include_co_authored_by = aggregatable_fields["include_co_authored_by"][0]
        disable_all_hooks = aggregatable_fields["disable_all_hooks"][0]
        enable_all_project_mcp = aggregatable_fields["enable_all_project_mcp"][0]
        api_key_helper = aggregatable_fields["api_key_helper"][0]
        cleanup_period = aggregatable_fields["cleanup_period"][0]

        return ClaudeCodeSettings(
            mode=mode,
            defaultMode=mode,
            outputStyle=output_style,
            permissions=permissions,
            env=mergeable_fields["env"],
            model=model_value,
            enabledPlugins=mergeable_fields["enabled_plugins"],
            apiKeyHelper=api_key_helper,
            cleanupPeriodDays=cleanup_period,
            includeCoAuthoredBy=include_co_authored_by if include_co_authored_by is not None else True,
            disableAllHooks=disable_all_hooks if disable_all_hooks is not None else False,
            enableAllProjectMcpServers=enable_all_project_mcp if enable_all_project_mcp is not None else False,
            enabledMcpjsonServers=mergeable_fields["enabled_mcpjson"] or [],
            disabledMcpjsonServers=mergeable_fields["disabled_mcpjson"] or [],
            allowedMcpServers=mergeable_fields["allowed_mcp"] or [],
            deniedMcpServers=mergeable_fields["denied_mcp"] or [],
        )

    def _read_scope_state(self, workspace_id: str, scope: DocumentScope) -> Dict[str, Any]:
        file_path = self._settings_file(workspace_id, scope)
        return read_json_file(file_path)

    def _settings_file(self, workspace_id: str, scope: DocumentScope) -> Path:
        file_name = self._SETTINGS_FILES.get(scope)
        if file_name is None:
            raise ValueError(f"Unsupported scope: {scope}")
        if scope == DocumentScope.USER:
            root = resolve_scope_root(workspace_id, DocumentScope.USER)
        else:
            root = resolve_scope_root(workspace_id, DocumentScope.PROJECT)
        return root / file_name

    def _merge_order(self) -> Tuple[DocumentScope, ...]:
        return (
            DocumentScope.USER,
            DocumentScope.PROJECT,
            DocumentScope.LOCAL,
        )

    def _extract_mode(self, state: Dict[str, Any]) -> PermissionMode | None:
        mode_value = state.get("defaultMode") or state.get("mode")
        if isinstance(mode_value, str) and mode_value.strip():
            try:
                return PermissionMode(mode_value)
            except ValueError:
                return None
        return None

    def _extract_permissions(
        self, state: Dict[str, Any]
    ) -> PermissionRules | None:
        permissions = state.get("permissions")
        if not isinstance(permissions, dict):
            return None
        return PermissionRules(
            allow=self._normalize_string_list(permissions.get("allow")),
            deny=self._normalize_string_list(permissions.get("deny")),
            ask=self._normalize_string_list(permissions.get("ask")),
            additionalDirectories=self._normalize_string_list(
                permissions.get("additionalDirectories")
            ),
        )

    def _extract_model(self, state: Dict[str, Any]) -> Optional[str]:
        value = state.get("model")
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
        return None

    def _extract_enabled_plugins(self, state: Dict[str, Any]) -> Dict[str, bool]:
        """從狀態中提取 enabledPlugins 設定"""
        plugins = state.get("enabledPlugins")
        if not isinstance(plugins, dict):
            return {}

        result: Dict[str, bool] = {}
        for key, value in plugins.items():
            if isinstance(key, str) and key.strip():
                result[key.strip()] = bool(value)
        return result

    def _extract_api_key_helper(self, state: Dict[str, Any]) -> Optional[str]:
        value = state.get("apiKeyHelper")
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return None

    def _extract_cleanup_period(self, state: Dict[str, Any]) -> Optional[int]:
        if "cleanupPeriodDays" not in state:
            return None
        value = state.get("cleanupPeriodDays")
        if isinstance(value, int) and value >= 0:
            return value
        return None

    def _extract_bool(self, state: Dict[str, Any], key: str) -> Optional[bool]:
        if key not in state:
            return None
        value = state.get(key)
        if isinstance(value, bool):
            return value
        return None

    def _extract_string_list(
        self, state: Dict[str, Any], key: str
    ) -> Tuple[bool, List[str]]:
        if key not in state:
            return False, []
        return True, self._normalize_string_list(state.get(key))

    def _extract_mcp_policies(
        self, state: Dict[str, Any], key: str
    ) -> Tuple[bool, List[McpServerPolicy]]:
        if key not in state:
            return False, []
        raw = state.get(key)
        if not isinstance(raw, list):
            return True, []
        normalized: List[McpServerPolicy] = []
        seen: set[str] = set()
        for item in raw:
            try:
                if isinstance(item, McpServerPolicy):
                    entry = item
                elif isinstance(item, dict):
                    entry = McpServerPolicy(**item)
                else:
                    entry = McpServerPolicy(serverName=str(item))
            except Exception:  # pragma: no cover - 忽略無效項目
                continue
            if entry.server_name in seen:
                continue
            seen.add(entry.server_name)
            normalized.append(entry)
        return True, normalized

    def _normalize_string_list(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        normalized: List[str] = []
        seen: set[str] = set()
        for item in values:
            if item is None:
                continue
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def get_marketplaces(self, workspace_id: str) -> MarketplaceListResponse:
        """讀取所有可用的 marketplaces"""
        # 取得 workspace 的 home 目錄 (已經包含 .claude)
        user_root = resolve_scope_root(workspace_id, DocumentScope.USER)
        marketplaces_dir = user_root / "plugins" / "marketplaces"

        marketplaces: List[Marketplace] = []

        if not marketplaces_dir.exists():
            return MarketplaceListResponse(marketplaces=[])

        # 遍歷所有 marketplace 目錄
        for marketplace_path in marketplaces_dir.iterdir():
            if not marketplace_path.is_dir():
                continue

            # 讀取 marketplace.json
            marketplace_json = (
                marketplace_path / ".claude-plugin" / "marketplace.json"
            )
            if not marketplace_json.exists():
                continue

            try:
                with open(marketplace_json, "r", encoding="utf-8") as f:
                    data = f.read()
                    import json

                    marketplace_data = json.loads(data)

                # 解析 marketplace
                # description 和 version 可能在頂層或 metadata 對象中
                metadata_obj = marketplace_data.get("metadata", {})

                # 解析 plugins，單獨處理每個 plugin 的驗證錯誤
                plugins_data: List[PluginMetadata] = []
                for plugin in marketplace_data.get("plugins", []):
                    try:
                        plugins_data.append(PluginMetadata(**plugin))
                    except Exception as e:
                        # 只跳過無效的 plugin，不影響整個 marketplace
                        plugin_name = plugin.get("name", "unknown")
                        logger.warning(
                            "Failed to parse plugin '%s' in marketplace %s: %s",
                            plugin_name,
                            marketplace_path.name,
                            e,
                        )
                        continue

                marketplace = Marketplace(
                    name=marketplace_data.get("name", ""),
                    owner=MarketplaceOwner(**marketplace_data.get("owner", {})),
                    metadata=MarketplaceMetadata(
                        description=marketplace_data.get("description") or metadata_obj.get("description", ""),
                        version=marketplace_data.get("version") or metadata_obj.get("version", "1.0.0"),
                    ),
                    plugins=plugins_data,
                )
                marketplaces.append(marketplace)
            except FileNotFoundError:
                logger.debug("Marketplace file not found: %s", marketplace_json)
                continue
            except PermissionError as e:
                logger.error(
                    "Permission denied reading marketplace file",
                    extra={"file_path": str(marketplace_json), "error": str(e)}
                )
                continue
            except json.JSONDecodeError as e:
                logger.error(
                    "Invalid JSON in marketplace file",
                    extra={
                        "file_path": str(marketplace_json),
                        "line": e.lineno,
                        "column": e.colno,
                        "error": e.msg
                    }
                )
                continue
            except Exception as e:
                logger.error(
                    "Failed to parse marketplace %s: %s",
                    marketplace_path.name,
                    e,
                    extra={
                        "marketplace_path": str(marketplace_path),
                        "error_type": type(e).__name__,
                        "error": str(e)
                    }
                )
                continue

        return MarketplaceListResponse(marketplaces=marketplaces)
