"""Claude Code Settings 模型定義"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_rule_list(values: Iterable[Any]) -> List[str]:
    """將權限規則轉換成不重複且去除空白的清單"""

    normalized: List[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        rule = str(value).strip()
        if not rule or rule in seen:
            continue
        seen.add(rule)
        normalized.append(rule)
    return normalized


def _normalize_env(env: Mapping[str, Any] | None) -> Dict[str, str]:
    """確保環境變數鍵值皆為字串且移除空鍵"""

    if not env:
        return {}

    normalized: Dict[str, str] = {}
    for key, raw_value in env.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        if raw_value is None:
            continue
        normalized[key_str] = str(raw_value)
    return normalized


def _normalize_model(value: Optional[str]) -> Optional[str]:
    """清理模型名稱字串"""

    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _normalize_enabled_plugins(plugins: Mapping[str, Any] | Dict[str, bool] | None) -> Dict[str, bool]:
    """確保 enabledPlugins 鍵為字串且值為布林值"""

    if plugins is None:
        return {}

    if not isinstance(plugins, dict):
        return {}

    normalized: Dict[str, bool] = {}
    for key, raw_value in plugins.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        # 將值轉換為布林值
        normalized[key_str] = bool(raw_value)
    return normalized


def _normalize_optional_string(value: Any) -> Optional[str]:
    """去除字串前後空白，空值回傳 None"""

    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value).strip() or None


def _normalize_int(value: Any) -> Optional[int]:
    """嘗試將輸入轉為非負整數"""

    if value is None:
        return None
    if isinstance(value, bool):
        # 避免 True/False 被轉為 1/0
        raise ValueError("Invalid integer value")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - 由驗證流程捕捉
        raise ValueError("Invalid integer value") from exc
    if integer < 0:
        raise ValueError("Value must be greater than or equal to 0")
    return integer


class McpServerPolicy(BaseModel):
    """MCP 伺服器允許/拒絕清單項目"""

    server_name: str = Field(..., alias="serverName", description="MCP 伺服器名稱")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("server_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        normalized = _normalize_optional_string(value)
        if not normalized:
            raise ValueError("serverName is required")
        return normalized


def _normalize_mcp_policy_list(values: Iterable[Any] | None) -> List[McpServerPolicy]:
    """正規化 MCP 伺服器策略列表"""

    if not values:
        return []

    normalized: List[McpServerPolicy] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, McpServerPolicy):
            entry = value
        elif isinstance(value, Mapping):
            entry = McpServerPolicy(**value)
        else:
            # 允許直接傳入字串形式
            entry = McpServerPolicy(serverName=str(value))

        if entry.server_name in seen:
            continue
        seen.add(entry.server_name)
        normalized.append(entry)

    return normalized


class PermissionMode(str, Enum):
    """Claude Code 權限模式枚舉"""

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"
    DONT_ASK = "dontAsk"
    AUTO = "auto"


class PermissionRules(BaseModel):
    """權限規則清單"""

    allow: List[str] = Field(default_factory=list, description="允許的操作規則")
    deny: List[str] = Field(default_factory=list, description="拒絕的操作規則")
    ask: List[str] = Field(default_factory=list, description="需要確認的操作規則")
    additional_directories: List[str] = Field(
        default_factory=list,
        alias="additionalDirectories",
        description="允許存取的額外目錄",
    )

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _normalize(self) -> "PermissionRules":
        self.allow = _normalize_rule_list(self.allow)
        self.deny = _normalize_rule_list(self.deny)
        self.ask = _normalize_rule_list(self.ask)
        self.additional_directories = _normalize_rule_list(self.additional_directories)
        return self

    def is_empty(self) -> bool:
        """檢查是否擁有任何規則"""
        return (
            not self.allow
            and not self.deny
            and not self.ask
            and not self.additional_directories
        )


class ClaudeCodeSettings(BaseModel):
    """Claude Code 設定內容"""

    mode: PermissionMode = Field(
        default=PermissionMode.DEFAULT, description="目前生效的權限模式"
    )
    default_mode: PermissionMode | None = Field(
        default=None, alias="defaultMode", description="設定檔儲存用的模式欄位"
    )
    output_style: str | None = Field(
        default=None, alias="outputStyle", description="預設的輸出樣式檔名"
    )
    permissions: PermissionRules = Field(
        default_factory=PermissionRules, description="允許與拒絕的權限集合"
    )
    env: Dict[str, str] = Field(
        default_factory=dict, description="附帶的環境變數設定"
    )
    model: Optional[str] = Field(
        default=None, alias="model", description="指定的模型覆寫"
    )
    enabled_plugins: Optional[Dict[str, bool]] = Field(
        default=None, alias="enabledPlugins", description="啟用的 Plugins 設定"
    )
    api_key_helper: Optional[str] = Field(
        default=None, alias="apiKeyHelper", description="產生 API Key 的 helper 腳本"
    )
    cleanup_period_days: Optional[int] = Field(
        default=None,
        alias="cleanupPeriodDays",
        description="聊天紀錄保留天數",
    )
    include_co_authored_by: bool = Field(
        default=True,
        alias="includeCoAuthoredBy",
        description="Git Commit 是否加入 co-authored-by Claude",
    )
    disable_all_hooks: bool = Field(
        default=False,
        alias="disableAllHooks",
        description="是否停用所有 hooks",
    )
    enable_all_project_mcp_servers: bool = Field(
        default=False,
        alias="enableAllProjectMcpServers",
        description="自動核准專案中所有 MCP 伺服器",
    )
    enabled_mcpjson_servers: List[str] = Field(
        default_factory=list,
        alias="enabledMcpjsonServers",
        description="從 .mcp.json 核准的伺服器",
    )
    disabled_mcpjson_servers: List[str] = Field(
        default_factory=list,
        alias="disabledMcpjsonServers",
        description="從 .mcp.json 拒絕的伺服器",
    )
    allowed_mcp_servers: List[McpServerPolicy] = Field(
        default_factory=list,
        alias="allowedMcpServers",
        description="允許的 MCP 伺服器清單",
    )
    denied_mcp_servers: List[McpServerPolicy] = Field(
        default_factory=list,
        alias="deniedMcpServers",
        description="拒絕的 MCP 伺服器清單",
    )

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @field_validator("enabled_plugins", mode="before")
    @classmethod
    def _validate_enabled_plugins(cls, value: Any) -> Dict[str, bool]:
        """驗證並正規化 enabled_plugins"""
        return _normalize_enabled_plugins(value)

    @field_validator("api_key_helper", mode="before")
    @classmethod
    def _validate_api_key_helper(cls, value: Any) -> Optional[str]:
        return _normalize_optional_string(value)

    @field_validator("cleanup_period_days", mode="before")
    @classmethod
    def _validate_cleanup_period(cls, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _normalize_int(value)

    @field_validator("enabled_mcpjson_servers", "disabled_mcpjson_servers", mode="before")
    @classmethod
    def _validate_mcpjson_lists(cls, value: Any) -> List[str]:
        return _normalize_rule_list(value or [])

    @field_validator("allowed_mcp_servers", "denied_mcp_servers", mode="before")
    @classmethod
    def _validate_mcp_policy_lists(cls, value: Any) -> List[McpServerPolicy]:
        return _normalize_mcp_policy_list(value)

    @model_validator(mode="after")
    def _sync_defaults(self) -> "ClaudeCodeSettings":
        self.env = _normalize_env(self.env)
        self.model = _normalize_model(self.model)
        # enabled_plugins 已經在 field_validator 中正規化
        if self.enabled_plugins is None:
            self.enabled_plugins = {}
        if self.default_mode is None:
            self.default_mode = self.mode
        return self

    @property
    def effective_mode(self) -> PermissionMode:
        """取得實際生效的模式值"""
        return self.default_mode or self.mode


class ClaudeCodeSettingsUpdateRequest(BaseModel):
    """更新 Claude Code 設定請求"""

    mode: PermissionMode | None = Field(
        default=None, description="新的權限模式值"
    )
    default_mode: PermissionMode | None = Field(
        default=None, alias="defaultMode", description="儲存使用的模式值"
    )
    output_style: str | None = Field(
        default=None, alias="outputStyle", description="要啟用的輸出樣式名稱"
    )
    model: Optional[str] = Field(
        default=None, alias="model", description="要覆寫的模型名稱"
    )
    permissions: PermissionRules | None = Field(
        default=None, description="新的權限規則"
    )
    env: Dict[str, str] | None = Field(
        default=None, description="要覆寫的環境變數"
    )
    enabled_plugins: Optional[Dict[str, bool]] = Field(
        default=None, alias="enabledPlugins", description="要覆寫的 Plugins 設定"
    )
    api_key_helper: Optional[str] = Field(
        default=None, alias="apiKeyHelper", description="更新 API Key helper 腳本"
    )
    cleanup_period_days: Optional[int] = Field(
        default=None,
        alias="cleanupPeriodDays",
        description="聊天紀錄保留天數",
    )
    include_co_authored_by: Optional[bool] = Field(
        default=None,
        alias="includeCoAuthoredBy",
        description="是否加入 co-authored-by Claude",
    )
    disable_all_hooks: Optional[bool] = Field(
        default=None,
        alias="disableAllHooks",
        description="停用所有 hooks",
    )
    enable_all_project_mcp_servers: Optional[bool] = Field(
        default=None,
        alias="enableAllProjectMcpServers",
        description="自動核准專案定義的 MCP 伺服器",
    )
    enabled_mcpjson_servers: Optional[List[str]] = Field(
        default=None,
        alias="enabledMcpjsonServers",
        description="從 .mcp.json 核准的伺服器",
    )
    disabled_mcpjson_servers: Optional[List[str]] = Field(
        default=None,
        alias="disabledMcpjsonServers",
        description="從 .mcp.json 拒絕的伺服器",
    )
    allowed_mcp_servers: Optional[List[McpServerPolicy]] = Field(
        default=None,
        alias="allowedMcpServers",
        description="允許設定的 MCP 伺服器",
    )
    denied_mcp_servers: Optional[List[McpServerPolicy]] = Field(
        default=None,
        alias="deniedMcpServers",
        description="拒絕設定的 MCP 伺服器",
    )

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @field_validator("enabled_plugins", mode="before")
    @classmethod
    def _validate_enabled_plugins(cls, value: Any) -> Optional[Dict[str, bool]]:
        """驗證並正規化 enabled_plugins"""
        if value is None:
            return None
        return _normalize_enabled_plugins(value)

    @field_validator("api_key_helper", mode="before")
    @classmethod
    def _validate_api_key_helper(cls, value: Any) -> Optional[str]:
        return _normalize_optional_string(value)

    @field_validator("cleanup_period_days", mode="before")
    @classmethod
    def _validate_cleanup_period(cls, value: Any) -> Optional[int]:
        if value is None:
            return None
        return _normalize_int(value)

    @field_validator("enabled_mcpjson_servers", "disabled_mcpjson_servers", mode="before")
    @classmethod
    def _validate_mcpjson_lists(cls, value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        return _normalize_rule_list(value)

    @field_validator("allowed_mcp_servers", "denied_mcp_servers", mode="before")
    @classmethod
    def _validate_mcp_policy_lists(
        cls, value: Any
    ) -> Optional[List[McpServerPolicy]]:
        if value is None:
            return None
        return _normalize_mcp_policy_list(value)

    def field_provided(self, field_name: str) -> bool:
        """判斷欄位是否有在請求中出現"""

        if field_name in self.model_fields_set:
            return True
        field = self.__class__.model_fields.get(field_name)
        return bool(field and field.alias and field.alias in self.model_fields_set)

    def resolved_mode(self) -> PermissionMode | None:
        """回傳請求中指定的模式值（defaultMode 優先）"""

        if self.field_provided("default_mode"):
            return self.default_mode
        if self.field_provided("mode"):
            return self.mode
        return None

    @model_validator(mode="after")
    def _normalize_optional_payload(self) -> "ClaudeCodeSettingsUpdateRequest":
        if self.env is not None:
            self.env = _normalize_env(self.env)
        if self.permissions is not None and self.permissions.is_empty():
            self.permissions = PermissionRules()
        if self.field_provided("model"):
            self.model = _normalize_model(self.model)
        # enabled_plugins 已經在 field_validator 中正規化
        if self.field_provided("output_style"):
            # 正規化 output_style:空字串轉為 None
            if self.output_style is not None:
                trimmed = self.output_style.strip()
                self.output_style = trimmed if trimmed else None
        if self.field_provided("api_key_helper") and self.api_key_helper is not None:
            trimmed = self.api_key_helper.strip()
            self.api_key_helper = trimmed if trimmed else None
        return self


# ============================================================================
# Marketplace & Plugin Models
# ============================================================================


class PluginMetadata(BaseModel):
    """Plugin 元數據"""

    name: str = Field(..., description="Plugin 名稱")
    description: str = Field(..., description="Plugin 描述")
    version: str = Field(default="1.0.0", description="Plugin 版本")
    author: Optional[Dict[str, str]] = Field(default=None, description="作者資訊")
    license: Optional[str] = Field(default=None, description="授權")
    keywords: Optional[List[str]] = Field(default=None, description="關鍵字")
    source: Optional[str | Dict[str, Any]] = Field(
        default=None, description="來源路徑或來源配置（支援相對路徑字串或 {'source': 'url', 'url': '...'} 格式）"
    )
    strict: Optional[bool] = Field(default=None, description="嚴格模式")
    commands: Optional[List[str]] = Field(default=None, description="命令列表")
    agents: Optional[List[str]] = Field(default=None, description="Agent 列表")
    mcpServers: Optional[Dict[str, Any]] = Field(
        default=None, alias="mcpServers", description="MCP 伺服器配置"
    )

    model_config = ConfigDict(populate_by_name=True)


class MarketplaceOwner(BaseModel):
    """Marketplace 擁有者資訊"""

    name: str = Field(..., description="擁有者名稱")
    email: Optional[str] = Field(default=None, description="Email")
    url: Optional[str] = Field(default=None, description="URL")


class MarketplaceMetadata(BaseModel):
    """Marketplace 元數據"""

    description: str = Field(..., description="Marketplace 描述")
    version: str = Field(..., description="Marketplace 版本")


class Marketplace(BaseModel):
    """Marketplace 資訊"""

    name: str = Field(..., description="Marketplace 名稱")
    owner: MarketplaceOwner = Field(..., description="擁有者資訊")
    metadata: MarketplaceMetadata = Field(..., description="元數據")
    plugins: List[PluginMetadata] = Field(default_factory=list, description="Plugin 列表")

    model_config = ConfigDict(populate_by_name=True)


class MarketplaceListResponse(BaseModel):
    """Marketplace 列表回應"""

    marketplaces: List[Marketplace] = Field(
        default_factory=list, description="Marketplace 列表"
    )
