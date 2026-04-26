"""
Application configuration settings

Supports multi-environment configuration, loading settings from environment variables or .env files
"""

import json
import os
from functools import lru_cache
from typing import Annotated, List, Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings class"""

    # === Application basic settings ===
    APP_NAME: str = Field(default="Aileron - Workspace Manager", description="Application name")
    VERSION: str = Field(default="1.0.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENV: str = Field(default="production", description="Execution environment")

    # === ServerSettings ===
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=3001, description="Server port")

    # === DatabaseSettings ===
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/aileron",
        description="Database connection URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Whether to echo SQL queries")
    DATABASE_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Database connection pool max overflow")

    # === Redis Settings ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    REDIS_CACHE_TTL: int = Field(default=3600, description="Redis cache expiry time (seconds)")

    # === CORS Settings ===
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:8082,http://localhost:8083",
        description="Allowed CORS origins (comma-separated)"
    )

    # === Docker Settings ===
    DOCKER_HOST: Optional[str] = Field(default=None, description="Docker host")
    DOCKER_NETWORK: str = Field(default="aileron", description="Docker network name")
    WORKSPACE_IMAGE_PREFIX: str = Field(default="aidh-workspace", description="Workspace image prefix")

    # === Runtime provisioning settings ===
    RUNTIME_PROVISIONER: Literal["docker", "kubernetes"] = Field(
        default="docker", description="Runtime provisioning strategy"
    )
    PLATFORM: str = Field(
        default="linux", description="Runtime platform (linux/mac/windows)"
    )
    RUNTIME_SCRIPT_ROOT: str = Field(
        default="/data/init-scripts", description="Runtime generated scripts output root directory"
    )
    HOST_WORKSPACES_DIR: str = Field(
        default="/var/lib/aileron/workspaces",
        description="Host directory to mount workspace files",
    )
    HOST_WORKSPACE_SCRIPTS_DIR: str = Field(
        default="/var/lib/aileron/workspace-scripts",
        description="Workspace scripts host directory",
    )
    HOST_CLAUDE_DATA_DIR: str = Field(
        default="/var/lib/aileron/claude-data",
        description="Claude data host directory",
    )
    BROWSER_WEBRTC_RESERVED_UDP_RANGES: Annotated[List[str], NoDecode] = Field(
        default_factory=list,
        description="Reserved host UDP port ranges excluded from browser WebRTC allocation",
    )
    MANAGER_WORKSPACES_DIR: str = Field(
        default="/host/workspace-data",
        description="Workspace data directory mounted inside workspace-manager",
    )
    MANAGER_WORKSPACE_SCRIPTS_DIR: str = Field(
        default="/host/workspace-scripts",
        description="Workspace scripts directory mounted inside workspace-manager",
    )
    MANAGER_CLAUDE_DATA_DIR: str = Field(
        default="/host/claude-data",
        description="Claude data directory mounted inside workspace-manager",
    )
    HOST_KNOWLEDGE_BASES_DIR: str = Field(
        default="/var/lib/aileron/knowledge-bases",
        description="Host directory to mount knowledge base files",
    )
    MANAGER_KNOWLEDGE_BASES_DIR: str = Field(
        default="/host/knowledge-bases",
        description="Knowledge base data directory mounted inside workspace-manager",
    )
    RUNTIME_RESERVED_PORTS: Annotated[List[int], NoDecode] = Field(
        default_factory=lambda: [3002], description="Reserved container ports that cannot be used"
    )
    RUNTIME_AUTO_RETRY: bool = Field(default=True, description="Auto-retry on provisioning failure")
    RUNTIME_MAX_RETRIES: int = Field(default=3, description="Maximum retry count for background tasks")

    # === Kubernetes policy related settings ===
    RUNTIME_K8S_NAMESPACE: str = Field(default="default", description="Deploy namespace")
    RUNTIME_K8S_CR_NAMESPACE: Optional[str] = Field(
        default=None,
        description="Namespace for workspace custom resource creation; defaults to deploy namespace if not set",
    )
    RUNTIME_K8S_ALLOWED_NAMESPACES: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["default"],
        description="Allowed Kubernetes namespace list for users to choose from",
    )
    RUNTIME_K8S_SERVICE_TYPE: str = Field(
        default="ClusterIP", description="Service type"
    )
    RUNTIME_K8S_NODE_PORT: Optional[int] = Field(
        default=None, description="External port number if using NodePort"
    )
    RUNTIME_K8S_NODE_ADDRESS: str = Field(
        default="127.0.0.1", description="NodePort service external address"
    )
    RUNTIME_K8S_PVC_NAME: str = Field(
        default="workspace-runtime-pvc", description="Workspace PVC name"
    )
    RUNTIME_K8S_IMAGE: str = Field(
        default="ailerondocker/workspace-runtime:latest-lite-amd64",
        description="Container image used by runtime",
    )
    RUNTIME_K8S_BROWSER_IMAGE: str = Field(
        default="ailerondocker/workspace-chrome:latest-amd64",
        description="Container image used by browser",
    )
    RUNTIME_K8S_CANVAS_IMAGE: str = Field(
        default="ailerondocker/workspace-canvas:latest-amd64",
        description="Container image used by canvas",
    )
    RUNTIME_K8S_RUNTIME_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "2Gi"},
            "limits": {"cpu": "2000m", "memory": "4Gi"},
        },
        description="Kubernetes runtime default resource configuration",
    )
    RUNTIME_K8S_BROWSER_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        description="Kubernetes browser default resource configuration",
    )
    RUNTIME_K8S_CANVAS_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        description="Kubernetes canvas default resource configuration",
    )
    CILIUM_ENABLED: bool = Field(
        default=False,
        description="Is Cilium-based firewall feature enabled",
    )
    PUBLIC_SCHEME: str = Field(
        default="http",
        description="Scheme used for public URLs",
    )
    PUBLIC_BASE_DOMAIN: str = Field(
        default="aileron.localhost",
        description="Base domain for public URLs",
    )
    PUBLIC_FRONTEND_HOST: str = Field(
        default="aileron.{baseDomain}",
        description="Frontend public fixed host template",
    )
    PUBLIC_WORKSPACE_MANAGER_HOST: str = Field(
        default="workspace-manager.{baseDomain}",
        description="Workspace Manager public fixed host template",
    )
    PUBLIC_KEYCLOAK_HOST: str = Field(
        default="keycloak.{baseDomain}",
        description="Keycloak public fixed host template",
    )
    PUBLIC_RUNTIME_HOST_PATTERN: str = Field(
        default="workspace-runtime-{workspaceId}.{baseDomain}",
        description="Workspace runtime public host pattern",
    )
    PUBLIC_BROWSER_HOST_PATTERN: str = Field(
        default="workspace-browser-{workspaceId}.{baseDomain}",
        description="Workspace browser public host pattern",
    )
    PUBLIC_CANVAS_HOST_PATTERN: str = Field(
        default="workspace-canvas-{workspaceId}.{baseDomain}",
        description="Workspace canvas public host pattern",
    )
    FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS: Annotated[List[str], NoDecode] = Field(
        default_factory=list,
        description="Platform default workspace firewall allowed domain list",
    )
    FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS: Annotated[List[str], NoDecode] = Field(
        default_factory=list,
        description="Platform default browser firewall allowed domain list",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED: bool = Field(
        default=False,
        description="Whether to bootstrap default workspace in Kubernetes mode",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_ID: str = Field(
        default="default-workspace",
        description="Bootstrap default workspace ID",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL: str = Field(
        default="admin@aileron.com",
        description="Bootstrap default workspace owner email",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL: str = Field(
        default="",
        description="Bootstrap default workspace git URL",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH: str = Field(
        default="main",
        description="Bootstrap default workspace branch",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE: Optional[str] = Field(
        default=None,
        description="Bootstrap default workspace target namespace; defaults to RUNTIME_K8S_NAMESPACE if not set",
    )

    # === Celery Settings ===
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend"
    )

    # === FileSaveSettings ===
    UPLOAD_DIR: str = Field(default="./uploads", description="File upload directory")
    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, description="Maximum file size (bytes)")
    ALLOWED_FILE_TYPES: str = Field(
        default=".zip,.tar.gz,.tar,.py,.js,.ts,.json,.md",
        description="Allowed file types (comma-separated)"
    )

    # === Template center settings ===
    TEMPLATE_STORAGE_PATH: str = Field(
        default="/data/template-center",
        description="Template storage path"
    )

    # === File management settings ===
    FILE_TREE_MAX_DEPTH: int = Field(
        default=10,
        description="Maximum depth for file tree scan (default 10 levels)"
    )
    DEFAULT_USER_KB_QUOTA_BYTES: int = Field(
        default=5 * 1024 * 1024 * 1024,
        description="Total knowledge base default quota per user (bytes)",
    )
    DEFAULT_KB_QUOTA_BYTES: int = Field(
        default=512 * 1024 * 1024,
        description="Default quota per single knowledge base (bytes)",
    )
    KB_SINGLE_FILE_SIZE_LIMIT: int = Field(
        default=50 * 1024 * 1024,
        description="Knowledge base single file size limit (bytes)",
    )
    KB_ALLOWED_EXTENSIONS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            ".py",
            ".ts",
            ".js",
            ".go",
            ".rs",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".sh",
            ".sql",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".xml",
            ".md",
            ".txt",
            ".rst",
            ".csv",
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
        ],
        description="Knowledge base allowed file extension whitelist",
    )
    KB_TOMBSTONE_RETENTION_HOURS: int = Field(
        default=24,
        description="Knowledge base tombstone retention time (hours)",
    )

    # === Logging settings ===
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )

    # === Monitoring and health check settings ===
    HEALTH_CHECK_TIMEOUT: int = Field(default=30, description="Health check timeout (seconds)")

    # === Internal API Settings ===
    INTERNAL_API_TOKEN: str = Field(
        default="dev-internal-token",
        description="Internal API authentication token"
    )

    # === Keycloak Settings ===
    KEYCLOAK_SERVER_URL: str = Field(
        default="http://aileron-keycloak-dev:8080",
        description="Keycloak server URL (internal Docker network address)"
    )
    KEYCLOAK_REALM: str = Field(
        default="aileron",
        description="Keycloak realm name"
    )
    KEYCLOAK_CLIENT_ID: str = Field(
        default="aileron-frontend",
        description="Keycloak client ID"
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        """Get CORS origin list"""
        origins: list[str] = []

        if isinstance(self.ALLOWED_ORIGINS, str):
            # Remove possible quotes
            v = self.ALLOWED_ORIGINS.strip().strip('"').strip("'")
            # Check if is JSON format
            if v.startswith('[') and v.endswith(']'):
                import json
                try:
                    origins.extend(json.loads(v))
                except json.JSONDecodeError:
                    pass
            elif ',' in v:
                origins.extend(origin.strip() for origin in v.split(",") if origin.strip())
            elif v:
                origins.append(v)

        public_frontend_origin = self.build_public_url(self.PUBLIC_FRONTEND_HOST)
        origins.append(public_frontend_origin)

        if not origins:
            origins.extend([
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:8082",
            ])

        # Deduplicate while preserving order
        return list(dict.fromkeys(origins))

    @property
    def allowed_file_types_list(self) -> List[str]:
        """Get allowed file type list"""
        if isinstance(self.ALLOWED_FILE_TYPES, str):
            return [file_type.strip() for file_type in self.ALLOWED_FILE_TYPES.split(",") if file_type.strip()]
        return [".zip", ".tar.gz", ".tar", ".py", ".js", ".ts", ".json", ".md"]

    @field_validator("RUNTIME_RESERVED_PORTS", mode="before")
    @classmethod
    def parse_reserved_ports(cls, v):
        """Parse reserved port list"""
        if isinstance(v, str):
            return [int(port.strip()) for port in v.split(",") if port.strip()]
        return v

    @field_validator("BROWSER_WEBRTC_RESERVED_UDP_RANGES", mode="before")
    @classmethod
    def parse_browser_webrtc_reserved_udp_ranges(cls, v):
        """Parse Browser WebRTC UDP ranges to avoid"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("RUNTIME_K8S_ALLOWED_NAMESPACES", mode="before")
    @classmethod
    def parse_k8s_allowed_namespaces(cls, v):
        """Parse allowed Kubernetes namespace list"""
        if isinstance(v, str):
            namespaces = [namespace.strip() for namespace in v.split(",") if namespace.strip()]
            return namespaces or ["default"]
        return v

    @field_validator(
        "PUBLIC_SCHEME",
        "PUBLIC_BASE_DOMAIN",
        "PUBLIC_FRONTEND_HOST",
        "PUBLIC_WORKSPACE_MANAGER_HOST",
        "PUBLIC_KEYCLOAK_HOST",
        "PUBLIC_RUNTIME_HOST_PATTERN",
        "PUBLIC_BROWSER_HOST_PATTERN",
        "PUBLIC_CANVAS_HOST_PATTERN",
        mode="before",
    )
    @classmethod
    def normalize_public_routing_values(cls, v):
        """Normalize public routing settings strings."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("PUBLIC_SCHEME")
    @classmethod
    def validate_public_scheme(cls, v: str) -> str:
        """Validate public URL scheme."""
        normalized = v.lower()
        if normalized not in {"http", "https"}:
            raise ValueError("PUBLIC_SCHEME must be either 'http' or 'https'")
        return normalized

    @field_validator("PUBLIC_RUNTIME_HOST_PATTERN", "PUBLIC_BROWSER_HOST_PATTERN", "PUBLIC_CANVAS_HOST_PATTERN")
    @classmethod
    def validate_workspace_host_patterns(cls, v: str) -> str:
        """Verify workspace host pattern must include workspaceId."""
        if "{workspaceId}" not in v:
            raise ValueError("workspace host pattern must include '{workspaceId}'")
        return v

    @field_validator(
        "FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS",
        "FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS",
        mode="before",
    )
    @classmethod
    def parse_firewall_default_domains(cls, v):
        """Parse platform default firewall domain list."""
        if isinstance(v, str):
            return [domain.strip() for domain in v.split(",") if domain.strip()]
        return v

    @field_validator("KB_ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_kb_allowed_extensions(cls, v):
        """Parse KB allowed extension list."""
        if isinstance(v, str):
            return [extension.strip().lower() for extension in v.split(",") if extension.strip()]
        if isinstance(v, list):
            return [str(extension).strip().lower() for extension in v if str(extension).strip()]
        return v

    @field_validator(
        "RUNTIME_K8S_RUNTIME_RESOURCES",
        "RUNTIME_K8S_BROWSER_RESOURCES",
        "RUNTIME_K8S_CANVAS_RESOURCES",
        mode="before",
    )
    @classmethod
    def parse_k8s_component_resources(cls, v):
        """Parse Kubernetes component resources JSON."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode="after")
    def validate_public_routing_templates(self) -> "Settings":
        """Verify public routing required fields and templates."""
        if not self.PUBLIC_BASE_DOMAIN:
            raise ValueError("PUBLIC_BASE_DOMAIN must not be empty")

        self.resolve_public_host(self.PUBLIC_FRONTEND_HOST)
        self.resolve_public_host(self.PUBLIC_WORKSPACE_MANAGER_HOST)
        self.resolve_public_host(self.PUBLIC_KEYCLOAK_HOST)
        self.resolve_public_host(self.PUBLIC_RUNTIME_HOST_PATTERN, workspace_id="sample")
        self.resolve_public_host(self.PUBLIC_BROWSER_HOST_PATTERN, workspace_id="sample")
        self.resolve_public_host(self.PUBLIC_CANVAS_HOST_PATTERN, workspace_id="sample")
        return self

    def resolve_public_host(self, template: str, workspace_id: Optional[str] = None) -> str:
        """Resolve public host template to actual host."""
        host = template.replace("{baseDomain}", self.PUBLIC_BASE_DOMAIN)
        if "{workspaceId}" in host:
            if not workspace_id:
                raise ValueError("workspace_id is required to resolve workspace host pattern")
            host = host.replace("{workspaceId}", workspace_id)

        if "{" in host or "}" in host:
            raise ValueError(f"Unresolved public host template: {template}")
        if not host:
            raise ValueError("Resolved public host must not be empty")
        return host

    def build_public_url(self, template: str, workspace_id: Optional[str] = None) -> str:
        """Build complete public URL."""
        return f"{self.PUBLIC_SCHEME}://{self.resolve_public_host(template, workspace_id=workspace_id)}"

    @property
    def database_url_async(self) -> str:
        """Get async database connection URL."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    @property
    def is_development(self) -> bool:
        """Check if environment is development."""
        return self.ENV.lower() in ["development", "dev"]

    @property
    def is_production(self) -> bool:
        """Check if environment is production."""
        return self.ENV.lower() in ["production", "prod"]

    @property
    def is_testing(self) -> bool:
        """Check if environment is testing."""
        return self.ENV.lower() in ["testing", "test"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
        # Disable automatic JSON parsing, let validators handle it
        env_parse_none_str="null"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()


# Utility functions
def get_database_url() -> str:
    """Get database connection URL."""
    return get_settings().DATABASE_URL


def get_redis_url() -> str:
    """Get Redis Connection URL"""
    return get_settings().REDIS_URL


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return get_settings().DEBUG
