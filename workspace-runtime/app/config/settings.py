"""
Workspace Runtime configuration settings

Configuration dedicated to runtime environment, supporting container environment variable configuration
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Workspace Runtime settings class"""

    # === Application basic settings ===
    APP_NAME: str = Field(default="Aileron - Workspace Runtime", description="Application name")
    VERSION: str = Field(default="1.0.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENV: str = Field(default="production", description="Execution environment")

    # === Server settings ===
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=3002, description="Server port")

    # === Database settings ===
    # Use the same database as Workspace Manager to read scheduled tasks
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/aileron",
        description="Database connection string (shared with Workspace Manager)"
    )

    # === Redis settings ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (for token authentication)"
    )

    # === Workspace settings ===
    WORKSPACE_ID: str = Field(default="default", description="Workspace ID")
    WORKSPACE_PATH: str = Field(default="/workspace", description="Workspace path")
    WORKSPACE_USER: str = Field(default="developer", description="Workspace user")

    # === Workspace Manager connection settings ===
    MANAGER_URL: str = Field(
        default="http://workspace-manager:8000",
        description="Workspace Manager API URL"
    )
    MANAGER_API_TOKEN: Optional[str] = Field(default=None, description="Manager API Token")

    # === Public Routing settings ===
    FRONTEND_PUBLIC_URL: Optional[str] = Field(
        default=None,
        description="Frontend public URL, used for CORS in public domain mode"
    )

    # === Claude Code settings ===
    CLAUDE_EXECUTION_TIMEOUT_SECONDS: int = Field(
        default=1800,
        description="Maximum allowed seconds for single Claude CLI execution (default 30 minutes)"
    )
    DEFAULT_CLAUDE_MODEL: Optional[str] = Field(
        default=None,
        description="Default Claude model. If None or empty string, let Claude SDK use its default value"
    )

    # === CORS settings ===
    ALLOWED_ORIGINS: List[str] = Field(
        default=[],
        description="Allowed CORS origins"
    )

    # === File management settings ===
    FILE_TREE_MAX_DEPTH: int = Field(
        default=10,
        description="File tree scan maximum depth (default 10 levels)"
    )
    ARCHIVE_MAX_TOTAL_SIZE_BYTES: int = Field(
        default=100 * 1024 * 1024,
        description="Archive extraction total size limit"
    )
    ARCHIVE_MAX_ENTRY_SIZE_BYTES: int = Field(
        default=20 * 1024 * 1024,
        description="Archive single file size limit"
    )
    ARCHIVE_MAX_ENTRY_COUNT: int = Field(
        default=1000,
        description="Archive entry count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS: int = Field(
        default=100,
        description="Archive download selected root path count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT: int = Field(
        default=5000,
        description="Archive download file entry count limit"
    )
    ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES: int = Field(
        default=250 * 1024 * 1024,
        description="Archive download total uncompressed size limit"
    )
    ARCHIVE_DOWNLOAD_TTL_SECONDS: int = Field(
        default=1800,
        description="Archive download temporary file TTL seconds"
    )

    # === File monitoring settings ===
    WATCH_PATTERNS: List[str] = Field(
        default=["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", "*.json", "*.md"],
        description="Monitored file patterns"
    )
    IGNORE_PATTERNS: List[str] = Field(
        default=[
            "node_modules/*", ".git/*", "__pycache__/*", "*.pyc",
            ".venv/*", "venv/*", ".env", "*.log", ".DS_Store"
        ],
        description="Ignored file patterns"
    )

    # === System monitoring settings ===
    MONITOR_INTERVAL: int = Field(default=5, description="System monitoring interval (seconds)")
    CPU_THRESHOLD: float = Field(default=80.0, description="CPU usage warning threshold")
    MEMORY_THRESHOLD: float = Field(default=85.0, description="Memory usage warning threshold")
    DISK_THRESHOLD: float = Field(default=90.0, description="Disk usage warning threshold")

    # === WebSocket settings ===
    WS_HEARTBEAT_INTERVAL: int = Field(default=30, description="WebSocket heartbeat interval (seconds)")
    WS_MESSAGE_MAX_SIZE: int = Field(default=1024 * 1024, description="WebSocket message maximum size")

    # === Logging settings ===
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )

    # === Security settings ===
    INTERNAL_API_TOKEN: str = Field(
        default="dev-internal-token",
        description="Internal API authentication token"
    )

    # === Development tools settings ===
    AUTO_INSTALL_PACKAGES: bool = Field(default=True, description="Auto-install packages")
    PACKAGE_MANAGERS: List[str] = Field(
        default=["npm", "pip", "yarn", "pnpm"],
        description="Supported package managers"
    )

    # === Execution environment settings ===
    NODE_VERSION: Optional[str] = Field(default=None, description="Node.js version")
    PYTHON_VERSION: Optional[str] = Field(default=None, description="Python version")

    # === Draw.io integration settings ===
    DRAWIO_ENABLED: bool = Field(
        default=True,
        description="Whether Draw.io container integration is enabled (default enabled for existing deployment compatibility)"
    )
    DRAWIO_EXTERNAL_URL: str = Field(
        default="http://localhost:8083/draw",
        description="Draw.io external access URL (browser accessible)"
    )
    DRAWIO_INTERNAL_URL: str = Field(
        default="http://drawio:8080",
        description="Draw.io internal access URL (container internal access)"
    )
    DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS: float = Field(
        default=1.5,
        description="Draw.io internal health check timeout seconds"
    )
    DRAWIO_HEALTHCHECK_TTL_SECONDS: int = Field(
        default=30,
        description="Draw.io health check result cache seconds"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("WATCH_PATTERNS", mode="before")
    @classmethod
    def parse_watch_patterns(cls, v):
        """Parse watch patterns list"""
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split(",")]
        return v

    @field_validator("IGNORE_PATTERNS", mode="before")
    @classmethod
    def parse_ignore_patterns(cls, v):
        """Parse ignore patterns list"""
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split(",")]
        return v

    @field_validator("PACKAGE_MANAGERS", mode="before")
    @classmethod
    def parse_package_managers(cls, v):
        """Parse package managers list"""
        if isinstance(v, str):
            return [manager.strip() for manager in v.split(",")]
        return v

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
    def workspace_url(self) -> str:
        """Workspace external URL"""
        return f"http://localhost:{self.PORT}"

    @property
    def effective_allowed_origins(self) -> List[str]:
        """Get effective CORS origins."""
        origins: List[str] = []

        for origin in self.ALLOWED_ORIGINS:
            normalized = self._normalize_origin(origin)
            if normalized and normalized not in origins:
                origins.append(normalized)

        frontend_origin = self._normalize_origin(self.FRONTEND_PUBLIC_URL)
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)

        if origins:
            return origins

        if self.is_development or self.is_testing:
            return [
                "http://localhost:8082",
                "http://127.0.0.1:8082",
            ]

        return []

    @property
    def manager_headers(self) -> dict:
        """Manager API request headers"""
        headers = {"Content-Type": "application/json"}
        # Prioritize internal token to allow runtime to directly call manager (inter-container service communication)
        if self.INTERNAL_API_TOKEN:
            headers["X-Internal-Token"] = self.INTERNAL_API_TOKEN
        if self.MANAGER_API_TOKEN:
            headers["Authorization"] = f"Bearer {self.MANAGER_API_TOKEN}"
        return headers

    @staticmethod
    def _normalize_origin(value: Optional[str]) -> Optional[str]:
        """Normalize URL/Origin to CORS origin."""
        if value is None:
            return None

        normalized = value.strip().rstrip("/")
        return normalized or None

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True
    )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (with cache)"""
    import logging
    _settings = Settings()
    if _settings.is_production and _settings.INTERNAL_API_TOKEN == "dev-internal-token":
        logging.getLogger(__name__).warning(
            "INTERNAL_API_TOKEN is using insecure default value in production! "
            "Set the INTERNAL_API_TOKEN environment variable."
        )
    return _settings


# Convenience functions
def get_workspace_path() -> str:
    """Get workspace path"""
    return get_settings().WORKSPACE_PATH


def get_manager_url() -> str:
    """Get Manager URL"""
    return get_settings().MANAGER_URL


def is_debug_mode() -> bool:
    """Whether debug mode is enabled"""
    return get_settings().DEBUG
