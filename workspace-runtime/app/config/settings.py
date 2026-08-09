"""
Workspace Runtime configuration settings

Configuration dedicated to runtime environment, supporting container environment variable configuration
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BeforeValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_marketplace_operation_journal_dir() -> str:
    """Return the Marketplace journal path under the standard user state root."""

    configured_state_home = os.environ.get("XDG_STATE_HOME")
    state_home = (
        Path(configured_state_home)
        if configured_state_home
        else Path.home() / ".local" / "state"
    )
    return str(state_home / "aileron" / "marketplace-operations")


def read_required_secret_file(value: object) -> SecretStr:
    """Read a required secret from its canonical file reference."""

    if not isinstance(value, (str, Path)):
        raise ValueError("Secret file reference must be a path")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Secret file reference must be absolute")
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Secret file is unavailable: {path}") from exc
    if not secret:
        raise ValueError(f"Secret file is empty: {path}")
    return SecretStr(secret)


RequiredSecretFile = Annotated[SecretStr, BeforeValidator(read_required_secret_file)]


class Settings(BaseSettings):
    """Workspace Runtime settings class"""

    # === Application basic settings ===
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENV: str = Field(default="production", description="Execution environment")
    LOG_LEVEL: str = Field(default="INFO", description="Application log level")

    # === Server settings ===
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=3002, description="Server port")
    TERMINAL_PORT: int = Field(default=3004, ge=1, le=65535)
    RUNTIME_ROUTE_INVENTORY_PATH: str = Field(
        default="",
        description="Optional absolute path to the generated Runtime route inventory",
    )
    GIT_STALE_LOCK_THRESHOLD_SECONDS: int = Field(default=35, ge=1)

    # === Platform-owned Runtime environment ===
    AILERON_WORKSPACE_ID: str = Field(..., min_length=1, description="Workspace ID")
    AILERON_WORKSPACE_PATH: str = Field(..., min_length=1, description="Workspace path")
    AILERON_RUNTIME_STATE_DATABASE_URL_FILE: RequiredSecretFile = Field(
        ...,
        description="File containing the Workspace-scoped Runtime state database URL",
    )
    AILERON_RUNTIME_CONTROL_TOKEN_FILE: RequiredSecretFile = Field(
        ...,
        description="File containing the generation-scoped Manager control token",
    )
    AILERON_MANAGER_INTERNAL_URL: str = Field(
        ..., min_length=1, description="Workspace Manager internal API URL"
    )
    AILERON_PLATFORM_PUBLIC_ORIGIN: str = Field(
        ..., min_length=1, description="Exact public platform origin"
    )
    AILERON_WORKTREE_SUBDIR: str = Field(
        ..., min_length=1, description="Managed Git worktree directory"
    )
    MARKETPLACE_OPERATION_JOURNAL_DIR: str = Field(
        default_factory=default_marketplace_operation_journal_dir,
        description="Runtime-owned durable Marketplace operation journal",
    )

    # === Workspace Manager connection settings ===
    MANAGER_ACCESS_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        gt=0,
        le=30,
        description="Workspace Manager runtime-access request timeout",
    )
    AILERON_RUNTIME_INSTANCE_ID: str = Field(
        ...,
        description="Immutable execution-plane generation identifier",
    )
    AILERON_KB_MOUNT_REVISION: int = Field(
        ...,
        ge=0,
        description="Knowledge Base mount revision applied to this Runtime",
    )
    AILERON_RUNTIME_ACCESS_REVISION: int = Field(
        ...,
        ge=0,
        description="Manager authorization revision fenced into execution grants",
    )
    RESOURCE_TELEMETRY_INTERVAL_SECONDS: int = Field(
        default=900,
        ge=60,
        description="Capacity measurement interval in seconds",
    )
    RESOURCE_TELEMETRY_PROBE_TIMEOUT_SECONDS: float = Field(
        default=30,
        gt=0,
        le=120,
        description="Capacity probe timeout in seconds",
    )
    RESOURCE_TELEMETRY_RETRY_INTERVAL_SECONDS: float = Field(
        default=30,
        gt=0,
        le=300,
        description="Durable telemetry outbox retry interval in seconds",
    )
    RESOURCE_TELEMETRY_DELAYED_PROBE_SECONDS: float = Field(
        default=5,
        ge=0,
        le=60,
        description="Debounce delay after managed filesystem mutations",
    )
    RESOURCE_TELEMETRY_SHUTDOWN_TIMEOUT_SECONDS: float = Field(
        default=5,
        gt=0,
        le=30,
        description="Final telemetry outbox drain timeout in seconds",
    )
    AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE: str = Field(
        ...,
        min_length=1,
        description="Manager Ed25519 public JWKS file",
    )
    AILERON_RUNTIME_ASSERTION_ISSUER: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Expected issuer for Manager-signed Runtime assertions",
    )
    AILERON_BROWSER_SERVICE_NAME: str = Field(..., min_length=1)
    AILERON_BROWSER_WEBRTC_INTERNAL_URL: str = Field(..., min_length=1)
    AILERON_BROWSER_CDP_URL: str = Field(..., min_length=1)
    AILERON_CANVAS_SERVICE_NAME: str = Field(..., min_length=1)
    AILERON_CANVAS_INTERNAL_URL: str = Field(..., min_length=1)
    AILERON_CANVAS_API_URL: str = Field(..., min_length=1)
    AUTOMATION_MAX_CONCURRENT_EXECUTIONS: int = Field(
        default=3,
        ge=1,
        le=3,
        description="Maximum concurrent Automation executions (hard limit: 3)",
    )
    AUTOMATION_EXECUTION_TIMEOUT_SECONDS: int = Field(
        default=1800, description="Automation execution deadline in seconds"
    )
    AUTOMATION_AGENT_STOP_GRACE_SECONDS: int = Field(
        default=30, description="Automation Agent stop confirmation deadline"
    )

    # === File management settings ===
    FILE_TREE_MAX_DEPTH: int = Field(
        default=10, description="File tree scan maximum depth (default 10 levels)"
    )
    LOCAL_HISTORY_DIR: str = Field(
        default="/workspace/.aileron/local-history",
        description="Workspace local history metadata and snapshot directory",
    )
    ARCHIVE_MAX_TOTAL_SIZE_BYTES: int = Field(
        default=100 * 1024 * 1024, description="Archive extraction total size limit"
    )
    ARCHIVE_MAX_ENTRY_SIZE_BYTES: int = Field(
        default=20 * 1024 * 1024, description="Archive single file size limit"
    )
    ARCHIVE_MAX_ENTRY_COUNT: int = Field(
        default=1000, description="Archive entry count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS: int = Field(
        default=100, description="Archive download selected root path count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT: int = Field(
        default=5000, description="Archive download file entry count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES: int = Field(
        default=250 * 1024 * 1024,
        description="Archive download total uncompressed size limit",
    )
    ARCHIVE_DOWNLOAD_TTL_SECONDS: int = Field(
        default=1800, description="Archive download temporary file TTL seconds"
    )

    # === System monitoring settings ===
    DISK_THRESHOLD: float = Field(
        default=90.0, description="Disk usage warning threshold"
    )

    # === Draw.io integration settings ===
    DRAWIO_ENABLED: bool = Field(
        default=True,
        description="Whether the same-origin Draw.io integration is enabled",
    )
    DRAWIO_EXTERNAL_URL: str = Field(
        default="/draw",
        description="Same-origin Draw.io public path",
    )
    DRAWIO_INTERNAL_URL: str = Field(
        default="http://drawio:8080",
        description="Draw.io internal access URL (container internal access)",
    )
    DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS: float = Field(
        default=1.5, description="Draw.io internal health check timeout seconds"
    )
    DRAWIO_HEALTHCHECK_TTL_SECONDS: int = Field(
        default=30, description="Draw.io health check result cache seconds"
    )

    @field_validator("AILERON_PLATFORM_PUBLIC_ORIGIN")
    @classmethod
    def validate_platform_public_origin(cls, value: str) -> str:
        """Require an exact HTTP(S) origin without URL suffixes."""

        if value != value.strip() or value.endswith("/"):
            raise ValueError("Platform public origin must be exact")
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Platform public origin must be exact") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or (port is not None and not 1 <= port <= 65535)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Platform public origin must be exact")
        return value

    @field_validator("AILERON_RUNTIME_INSTANCE_ID")
    @classmethod
    def validate_runtime_instance_id(cls, value: str) -> str:
        """Require the canonical lowercase, hyphenated UUID representation."""
        if value != value.strip():
            raise ValueError("Runtime instance ID must be a canonical UUID")
        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Runtime instance ID must be a canonical UUID") from exc
        if str(parsed) != value:
            raise ValueError("Runtime instance ID must be a canonical UUID")
        return value

    @field_validator(
        "AILERON_WORKSPACE_PATH",
        "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE",
    )
    @classmethod
    def validate_absolute_platform_path(cls, value: str) -> str:
        """Require canonical platform file and directory references."""

        if value != value.strip() or not Path(value).is_absolute():
            raise ValueError("Platform path must be absolute")
        return value

    @field_validator("RUNTIME_ROUTE_INVENTORY_PATH")
    @classmethod
    def validate_optional_absolute_runtime_path(cls, value: str) -> str:
        """Accept an empty route inventory override or an exact absolute path."""

        if not value:
            return value
        if value != value.strip() or not Path(value).is_absolute():
            raise ValueError("Runtime route inventory path must be absolute")
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize the supported application log levels."""

        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Unsupported application log level")
        return normalized

    @property
    def is_development(self) -> bool:
        """Whether it is development environment"""
        return self.ENV.lower() in ["development", "dev"]

    @property
    def is_production(self) -> bool:
        """Whether it is production environment"""
        return self.ENV.lower() in ["production", "prod"]

    @property
    def is_testing(self) -> bool:
        """Whether it is testing environment"""
        return self.ENV.lower() in ["testing", "test"]

    @property
    def effective_allowed_origins(self) -> list[str]:
        """Return the single exact platform Origin allowed by Runtime."""

        return [self.AILERON_PLATFORM_PUBLIC_ORIGIN]

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_ignore_empty=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (with cache)"""
    return Settings()


# Convenience functions
def get_workspace_path() -> str:
    """Get workspace path"""
    return get_settings().AILERON_WORKSPACE_PATH
