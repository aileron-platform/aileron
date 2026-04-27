"""Claude Code Settings Model Definitions"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_rule_list(values: Iterable[Any]) -> List[str]:
    """Convert permission rules to deduplicated list without empty entries"""

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
    """Ensure environment variable keys and values are strings and remove empty keys"""

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
    """Clean model name string"""

    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _normalize_enabled_plugins(plugins: Mapping[str, Any] | Dict[str, bool] | None) -> Dict[str, bool]:
    """Ensure enabledPlugins keys are strings and values are booleans"""

    if plugins is None:
        return {}

    if not isinstance(plugins, dict):
        return {}

    normalized: Dict[str, bool] = {}
    for key, raw_value in plugins.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        # Convert value to boolean
        normalized[key_str] = bool(raw_value)
    return normalized


def _normalize_optional_string(value: Any) -> Optional[str]:
    """Remove leading/trailing whitespace from string, return None for empty values"""

    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value).strip() or None


def _normalize_int(value: Any) -> Optional[int]:
    """Try to convert input to non-negative integer"""

    if value is None:
        return None
    if isinstance(value, bool):
        # Avoid True/False being converted to 1/0
        raise ValueError("Invalid integer value")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - caught by validation process
        raise ValueError("Invalid integer value") from exc
    if integer < 0:
        raise ValueError("Value must be greater than or equal to 0")
    return integer


class McpServerPolicy(BaseModel):
    """MCP server allow/deny list item"""

    server_name: str = Field(..., alias="serverName", description="MCP server name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("server_name", mode="before")
    @classmethod
    def _normalize_name(cls, value: Any) -> str:
        normalized = _normalize_optional_string(value)
        if not normalized:
            raise ValueError("serverName is required")
        return normalized


def _normalize_mcp_policy_list(values: Iterable[Any] | None) -> List[McpServerPolicy]:
    """Normalize MCP server policy list"""

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
            # Allow passing string form directly
            entry = McpServerPolicy(serverName=str(value))

        if entry.server_name in seen:
            continue
        seen.add(entry.server_name)
        normalized.append(entry)

    return normalized


class PermissionMode(str, Enum):
    """Claude Code permission mode enum"""

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"
    DONT_ASK = "dontAsk"
    AUTO = "auto"


class PermissionRules(BaseModel):
    """Permission rule list"""

    allow: List[str] = Field(default_factory=list, description="Allowed operation rules")
    deny: List[str] = Field(default_factory=list, description="Denied operation rules")
    ask: List[str] = Field(default_factory=list, description="Operation rules requiring confirmation")
    additional_directories: List[str] = Field(
        default_factory=list,
        alias="additionalDirectories",
        description="Additional allowed directories",
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
        """Check if has any rules"""
        return (
            not self.allow
            and not self.deny
            and not self.ask
            and not self.additional_directories
        )


class ClaudeCodeSettings(BaseModel):
    """Claude Code settings content"""

    mode: PermissionMode = Field(
        default=PermissionMode.DEFAULT, description="Currently effective permission mode"
    )
    default_mode: PermissionMode | None = Field(
        default=None, alias="defaultMode", description="Mode field for settings file storage"
    )
    output_style: str | None = Field(
        default=None, alias="outputStyle", description="Default output style filename"
    )
    permissions: PermissionRules = Field(
        default_factory=PermissionRules, description="Allowed and denied permission set"
    )
    env: Dict[str, str] = Field(
        default_factory=dict, description="Attached environment variable settings"
    )
    model: Optional[str] = Field(
        default=None, alias="model", description="Specified model override"
    )
    enabled_plugins: Optional[Dict[str, bool]] = Field(
        default=None, alias="enabledPlugins", description="Enabled plugins settings"
    )
    api_key_helper: Optional[str] = Field(
        default=None, alias="apiKeyHelper", description="Helper script for generating API Key"
    )
    cleanup_period_days: Optional[int] = Field(
        default=None,
        alias="cleanupPeriodDays",
        description="Chat history retention days",
    )
    include_co_authored_by: bool = Field(
        default=True,
        alias="includeCoAuthoredBy",
        description="Whether to add co-authored-by Claude in Git Commit",
    )
    disable_all_hooks: bool = Field(
        default=False,
        alias="disableAllHooks",
        description="Whether to disable all hooks",
    )
    enable_all_project_mcp_servers: bool = Field(
        default=False,
        alias="enableAllProjectMcpServers",
        description="Auto-approve all MCP servers in project",
    )
    enabled_mcpjson_servers: List[str] = Field(
        default_factory=list,
        alias="enabledMcpjsonServers",
        description="Servers approved from .mcp.json",
    )
    disabled_mcpjson_servers: List[str] = Field(
        default_factory=list,
        alias="disabledMcpjsonServers",
        description="Servers denied from .mcp.json",
    )
    allowed_mcp_servers: List[McpServerPolicy] = Field(
        default_factory=list,
        alias="allowedMcpServers",
        description="Allowed MCP server list",
    )
    denied_mcp_servers: List[McpServerPolicy] = Field(
        default_factory=list,
        alias="deniedMcpServers",
        description="Denied MCP server list",
    )

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @field_validator("enabled_plugins", mode="before")
    @classmethod
    def _validate_enabled_plugins(cls, value: Any) -> Dict[str, bool]:
        """Validate and normalize enabled_plugins"""
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
        # enabled_plugins already normalized in field_validator
        if self.enabled_plugins is None:
            self.enabled_plugins = {}
        if self.default_mode is None:
            self.default_mode = self.mode
        return self

    @property
    def effective_mode(self) -> PermissionMode:
        """Get actual effective mode value"""
        return self.default_mode or self.mode


class ClaudeCodeSettingsUpdateRequest(BaseModel):
    """Update Claude Code settings request"""

    mode: PermissionMode | None = Field(
        default=None, description="New permission mode value"
    )
    default_mode: PermissionMode | None = Field(
        default=None, alias="defaultMode", description="Mode value for storage"
    )
    output_style: str | None = Field(
        default=None, alias="outputStyle", description="Output style name to enable"
    )
    model: Optional[str] = Field(
        default=None, alias="model", description="Model name to override"
    )
    permissions: PermissionRules | None = Field(
        default=None, description="New permission rules"
    )
    env: Dict[str, str] | None = Field(
        default=None, description="Environment variables to override"
    )
    enabled_plugins: Optional[Dict[str, bool]] = Field(
        default=None, alias="enabledPlugins", description="Plugins settings to override"
    )
    api_key_helper: Optional[str] = Field(
        default=None, alias="apiKeyHelper", description="Update API Key helper script"
    )
    cleanup_period_days: Optional[int] = Field(
        default=None,
        alias="cleanupPeriodDays",
        description="Chat history retention days",
    )
    include_co_authored_by: Optional[bool] = Field(
        default=None,
        alias="includeCoAuthoredBy",
        description="Whether to add co-authored-by Claude",
    )
    disable_all_hooks: Optional[bool] = Field(
        default=None,
        alias="disableAllHooks",
        description="Disable all hooks",
    )
    enable_all_project_mcp_servers: Optional[bool] = Field(
        default=None,
        alias="enableAllProjectMcpServers",
        description="Auto-approve project-defined MCP servers",
    )
    enabled_mcpjson_servers: Optional[List[str]] = Field(
        default=None,
        alias="enabledMcpjsonServers",
        description="Servers approved from .mcp.json",
    )
    disabled_mcpjson_servers: Optional[List[str]] = Field(
        default=None,
        alias="disabledMcpjsonServers",
        description="Servers denied from .mcp.json",
    )
    allowed_mcp_servers: Optional[List[McpServerPolicy]] = Field(
        default=None,
        alias="allowedMcpServers",
        description="Allowed MCP servers to set",
    )
    denied_mcp_servers: Optional[List[McpServerPolicy]] = Field(
        default=None,
        alias="deniedMcpServers",
        description="Denied MCP servers to set",
    )

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    @field_validator("enabled_plugins", mode="before")
    @classmethod
    def _validate_enabled_plugins(cls, value: Any) -> Optional[Dict[str, bool]]:
        """Validate and normalize enabled_plugins"""
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
        """Check if field appears in request"""

        if field_name in self.model_fields_set:
            return True
        field = self.__class__.model_fields.get(field_name)
        return bool(field and field.alias and field.alias in self.model_fields_set)

    def resolved_mode(self) -> PermissionMode | None:
        """Return mode value specified in request (defaultMode prioritized)"""

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
        # enabled_plugins already normalized in field_validator
        if self.field_provided("output_style"):
            # Normalize output_style: empty string to None
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
    """Plugin metadata"""

    name: str = Field(..., description="Plugin name")
    description: str = Field(..., description="Plugin description")
    version: str = Field(default="1.0.0", description="Plugin version")
    author: Optional[Dict[str, str]] = Field(default=None, description="Author information")
    license: Optional[str] = Field(default=None, description="License")
    keywords: Optional[List[str]] = Field(default=None, description="Keywords")
    source: Optional[str | Dict[str, Any]] = Field(
        default=None, description="Source path or source config (supports relative path string or {'source': 'url', 'url': '...'} format)"
    )
    strict: Optional[bool] = Field(default=None, description="Strict mode")
    commands: Optional[List[str]] = Field(default=None, description="Command list")
    agents: Optional[List[str]] = Field(default=None, description="Agent list")
    mcpServers: Optional[Dict[str, Any]] = Field(
        default=None, alias="mcpServers", description="MCP server configuration"
    )

    model_config = ConfigDict(populate_by_name=True)


class MarketplaceOwner(BaseModel):
    """Marketplace owner information"""

    name: str = Field(..., description="Owner name")
    email: Optional[str] = Field(default=None, description="Email")
    url: Optional[str] = Field(default=None, description="URL")


class MarketplaceMetadata(BaseModel):
    """Marketplace metadata"""

    description: str = Field(..., description="Marketplace description")
    version: str = Field(..., description="Marketplace version")


class Marketplace(BaseModel):
    """Marketplace information"""

    name: str = Field(..., description="Marketplace name")
    owner: MarketplaceOwner = Field(..., description="Owner information")
    metadata: MarketplaceMetadata = Field(..., description="Metadata")
    plugins: List[PluginMetadata] = Field(default_factory=list, description="Plugin list")

    model_config = ConfigDict(populate_by_name=True)


class MarketplaceListResponse(BaseModel):
    """Marketplace list response"""

    marketplaces: List[Marketplace] = Field(
        default_factory=list, description="Marketplace list"
    )
