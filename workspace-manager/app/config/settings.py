"""
Application configuration settings

Supports multi-environment configuration, loading settings from environment variables or .env files
"""

import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.modules.workspace.firewall_contract import (
    FirewallConfig,
    validate_firewall_seed_payload,
)

_SUPPORTED_OIDC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
)


def _is_loopback_host(hostname: str | None) -> bool:
    if hostname == "localhost":
        return True
    if hostname is None:
        return False
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _is_local_service_host(hostname: str | None) -> bool:
    """Return whether a host is a single-label local service name."""

    return bool(hostname) and "." not in hostname and ":" not in hostname


def _validate_public_url(
    value: str,
    *,
    field_name: str,
    environment: str,
    exact_origin: bool,
    allow_local_service_host: bool = False,
) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} contains an invalid port") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"{field_name} contains an invalid port")
    if exact_origin and parsed.path:
        raise ValueError(f"{field_name} must be one exact origin without a path")
    if not exact_origin and normalized.endswith("/"):
        raise ValueError(f"{field_name} must not have a trailing slash")
    if parsed.scheme == "http" and environment.lower() not in {
        "testing",
        "development",
        "test",
    }:
        raise ValueError(
            f"{field_name} must use HTTPS except for local URLs in local environments"
        )
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        if not allow_local_service_host or not _is_local_service_host(parsed.hostname):
            raise ValueError(
                f"{field_name} must use HTTPS except for local URLs in local environments"
            )
    return normalized


class Settings(BaseSettings):
    """Application settings class"""

    _firewall_seed: FirewallConfig = PrivateAttr(default_factory=FirewallConfig)

    # === Application basic settings ===
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENV: str = Field(default="production", description="Execution environment")
    TZ: str = Field(default="Asia/Taipei", description="System timezone")

    # === ServerSettings ===
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=3001, description="Server port")

    # === DatabaseSettings ===
    DATABASE_URL_FILE: str = Field(
        default="",
        description="Mounted file containing the complete database connection URL",
    )
    RUNTIME_DATABASE_CA_SECRET_NAME: str = Field(
        default="",
        description="Installation-owned database CA Secret mounted into Kubernetes Runtime pods",
    )
    RUNTIME_DATABASE_CA_SECRET_KEY: str = Field(
        default="",
        description="Key in the installation-owned database CA Secret",
    )
    RUNTIME_DATABASE_CA_REVISION: str = Field(
        default="",
        description="Revision that rolls Kubernetes Runtime pods after CA rotation",
    )
    HOST_PLATFORM_DATABASE_CA_CERT_FILE: str = Field(
        default="",
        description="Host path mounted as the platform database CA in Docker Runtime containers",
    )
    AUTOMATION_SCHEDULER_POLL_SECONDS: float = Field(
        default=5,
        gt=0,
        description="Automation scheduler polling interval in seconds",
    )

    # === Redis Settings ===
    REDIS_URL_FILE: str = Field(
        default="",
        description="Mounted file containing the general Redis connection URL",
    )
    REDIS_CA_CERT_FILE: str = Field(
        default="",
        description="Mounted CA certificate for the general Redis connection",
    )
    PLATFORM_RESOURCE_SUMMARY_CACHE_TTL_SECONDS: int = Field(default=30, gt=0)
    PLATFORM_RESOURCE_TREND_CACHE_TTL_SECONDS: int = Field(default=300, gt=0)
    PLATFORM_RESOURCE_ACTIVITY_RETENTION_DAYS: int = Field(default=90, ge=1)

    # === Platform public endpoint ===
    PLATFORM_PUBLIC_ORIGIN: str = Field(
        ...,
        description="Canonical browser-facing platform origin",
    )

    # === Docker Settings ===
    DOCKER_NETWORK: str = Field(default="aileron", description="Docker network name")
    AILERON_INSTALLATION_ID: str = Field(
        default="",
        description="Stable Browser connectivity evidence installation identity",
    )
    BROWSER_CONNECTIVITY_PROBE_IMAGE: str = Field(
        default="",
        description="Workspace Operator image used for Docker Browser connectivity probes",
    )
    WORKSPACE_RUNTIME_IMAGE: str = Field(
        default="",
        description="Default Runtime image selected for Docker Workspace provisioning",
    )
    WORKSPACE_BROWSER_IMAGE: str = Field(
        default="",
        description="Browser image selected for Docker Workspace provisioning",
    )
    WORKSPACE_CANVAS_IMAGE: str = Field(
        default="",
        description="Canvas image selected for Docker Workspace provisioning",
    )
    WORKSPACE_AVAILABILITY_CONTRACT_PATH: str = Field(
        default="",
        description="Optional explicit path to the Workspace availability contract",
    )
    GIT_STALE_LOCK_THRESHOLD_SECONDS: int = Field(
        default=35,
        ge=1,
        description="Age threshold used to recover stale managed Git lock files",
    )
    TURN_REACHABILITY_PROFILE_FILE: str = Field(
        default="",
        description="Canonical TURN reachability profile mounted into Manager",
    )
    HOST_TURN_REACHABILITY_PROFILE_FILE: str = Field(
        default="",
        description="Host path for the canonical TURN reachability profile",
    )
    TURN_REST_SHARED_SECRET_FILE: str = Field(
        default="",
        description="Manager-readable TURN REST shared secret file",
    )
    TURN_BROWSER_CREDENTIAL_ISSUER_KIND: Literal["", "turnRest"] = Field(
        default="",
        description="TURN Browser credential issuer mode when no profile file is mounted",
    )
    TURN_BROWSER_CREDENTIAL_TTL_SECONDS: int = Field(
        default=300,
        ge=60,
        description="TURN Browser credential lifetime when no profile file is mounted",
    )
    TURN_FRONTEND_ICE_SERVERS_JSON_FILE: str = Field(
        default="",
        description="Mounted file containing Browser TURN ICE server metadata",
    )
    TURN_BACKEND_ICE_SERVERS_JSON_FILE: str = Field(
        default="",
        description="Mounted file containing backend TURN ICE server metadata",
    )
    HOST_TURN_REST_SHARED_SECRET_FILE: str = Field(
        default="",
        description="Host path for the TURN REST shared secret",
    )
    HOST_TURN_BACKEND_ICE_SERVERS_JSON_FILE: str = Field(
        default="",
        description="Host path for backend TURN ICE server metadata",
    )
    TURN_CREDENTIAL_REVISION: str = Field(
        default="",
        description="Installation TURN credential revision",
    )
    TURN_CONNECTIVITY_GATEWAY_URL: str = Field(
        default="http://connectivity-evidence-gateway:8083",
        description="Internal Connectivity Evidence Gateway URL",
    )
    TURN_CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE: str = Field(
        default="",
        description="Manager-readable Gateway internal token file",
    )
    TURN_BROWSER_CONNECTIVITY_HTTP_TIMEOUT_SECONDS: float = Field(
        default=3,
        gt=0,
        le=60,
        description="Timeout for one Docker Browser connectivity evidence request",
    )
    TURN_BROWSER_CONNECTIVITY_RECONCILIATION_INTERVAL_SECONDS: int = Field(
        default=5,
        gt=0,
        le=300,
        description="Docker Browser connectivity reconciliation interval",
    )
    TURN_BROWSER_CONNECTIVITY_RECONCILIATION_BATCH_SIZE: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Maximum Docker Browser connectivity workspaces per scan",
    )

    # === Runtime provisioning settings ===
    RUNTIME_PROVISIONER: Literal["docker", "kubernetes"] = Field(
        default="docker", description="Runtime provisioning strategy"
    )
    RUNTIME_SCRIPT_ROOT: str = Field(
        default="/data/init-scripts",
        description="Runtime generated scripts output root directory",
    )
    HOST_PROJECT_ROOT: str = Field(
        default="",
        description="Absolute host project root used to resolve relative Docker mounts",
    )
    HOST_WORKSPACE_RUNTIME_DIR: str = Field(
        default="",
        description="Host Runtime source directory mounted for development execution",
    )
    HOST_WORKSPACES_DIR: str = Field(
        default="/var/lib/aileron/workspaces",
        description="Host directory to mount workspace files",
    )
    HOST_WORKSPACE_SCRIPTS_DIR: str = Field(
        default="/var/lib/aileron/workspace-scripts",
        description="Workspace scripts host directory",
    )
    HOST_RUNTIME_HOME_DIR: str = Field(
        default="/var/lib/aileron/runtime-home",
        description="Host directory to mount each Runtime user home",
    )
    HOST_BROWSER_CREDENTIALS_DIR: str = Field(
        default="/var/lib/aileron/browser-credentials",
        description="Host directory containing generated Docker Browser credential files",
    )
    MANAGER_WORKSPACES_DIR: str = Field(
        default="/host/workspace-data",
        description="Workspace data directory mounted inside workspace-manager",
    )
    MANAGER_WORKSPACE_SCRIPTS_DIR: str = Field(
        default="/host/workspace-scripts",
        description="Workspace scripts directory mounted inside workspace-manager",
    )
    MANAGER_RUNTIME_HOME_DIR: str = Field(
        default="/host/runtime-home",
        description="Runtime home directory mounted inside workspace-manager",
    )
    MANAGER_BROWSER_CREDENTIALS_DIR: str = Field(
        default="/host/browser-credentials",
        description="Manager path for generated Docker Browser credential files",
    )
    HOST_KNOWLEDGE_BASES_DIR: str = Field(
        default="/var/lib/aileron/knowledge-bases",
        description="Host directory to mount knowledge base files",
    )
    HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE: str = Field(
        default="/var/lib/aileron/runtime-assertions/jwks.json",
        description="Host JWKS file mounted read-only into Docker Runtime containers",
    )
    MANAGER_KNOWLEDGE_BASES_DIR: str = Field(
        default="/host/knowledge-bases",
        description="Knowledge base data directory mounted inside workspace-manager",
    )
    MANAGER_LOCAL_HISTORY_DIR: str = Field(
        default="/host/local-history",
        description="Local history metadata and snapshot directory",
    )
    RUNTIME_MAX_RETRIES: int = Field(
        default=3, description="Maximum retry count for background tasks"
    )
    RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS: int = Field(
        default=180,
        gt=30,
        le=1800,
        description="Lease duration for one claimed Workspace runtime job",
    )
    RUNTIME_JOB_RECOVERY_INTERVAL_SECONDS: int = Field(
        default=15,
        gt=0,
        le=300,
        description="Interval for durable Workspace job dispatch and recovery",
    )
    KUBERNETES_STATUS_RECONCILIATION_INTERVAL_SECONDS: int = Field(
        default=5,
        gt=0,
        le=300,
        description="Interval for Kubernetes Workspace status reconciliation",
    )
    KUBERNETES_STATUS_RECONCILIATION_BATCH_SIZE: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Maximum Kubernetes Workspace statuses reconciled per scan",
    )
    KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS: float = Field(
        default=5,
        gt=0,
        le=60,
        description="Timeout for one Kubernetes Workspace status request",
    )
    RUNTIME_JOB_DISPATCH_BASE_DELAY_SECONDS: int = Field(
        default=2,
        gt=0,
        le=300,
        description="Initial broker retry delay for durable Workspace jobs",
    )
    RUNTIME_JOB_DISPATCH_MAX_DELAY_SECONDS: int = Field(
        default=60,
        gt=0,
        le=3600,
        description="Maximum broker retry delay for durable Workspace jobs",
    )
    FIREWALL_SYNC_INTERVAL_SECONDS: int = Field(
        default=5,
        gt=0,
        le=300,
        description="Interval for durable firewall desired-state delivery",
    )
    FIREWALL_SYNC_LEASE_SECONDS: int = Field(
        default=60,
        gt=0,
        le=600,
        description="Lease duration for one firewall delivery command",
    )
    FIREWALL_SYNC_MAX_ATTEMPTS: int = Field(
        default=8,
        gt=0,
        le=100,
        description="Maximum firewall delivery attempts",
    )
    FIREWALL_SYNC_BASE_DELAY_SECONDS: int = Field(
        default=2,
        gt=0,
        le=300,
        description="Initial firewall delivery retry delay",
    )
    FIREWALL_SYNC_MAX_DELAY_SECONDS: int = Field(
        default=60,
        gt=0,
        le=3600,
        description="Maximum firewall delivery retry delay",
    )
    FIREWALL_SYNC_BATCH_SIZE: int = Field(
        default=25,
        gt=0,
        le=500,
        description="Maximum firewall delivery commands processed per scan",
    )
    RUNTIME_READY_TIMEOUT_SECONDS: int = Field(
        default=120,
        gt=0,
        le=600,
        description="Maximum time to verify all execution-plane components",
    )
    RUNTIME_DRAIN_DEADLINE_SECONDS: int = Field(
        default=30,
        gt=0,
        le=300,
        description="Graceful runtime drain deadline in seconds",
    )
    RUNTIME_ASSERTION_TTL_SECONDS: int = Field(
        default=60,
        gt=0,
        le=60,
        description="Maximum lifetime of Manager-signed runtime assertions",
    )
    RUNTIME_ASSERTION_ISSUER: str = Field(
        default="workspace-manager",
        min_length=1,
        max_length=128,
        description="Issuer used by Manager-signed runtime assertions",
    )
    RUNTIME_ASSERTION_KID: str = Field(
        default="workspace-manager-ed25519-v1",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="Active Ed25519 key ID for Manager-signed assertions",
    )
    RUNTIME_ASSERTION_PRIVATE_KEY_FILE: str = Field(
        default="/run/secrets/aileron/private-key.pem",
        min_length=1,
        description="Manager-only Ed25519 private key file path",
    )
    BROWSER_CREDENTIAL_KEYRING_FILE: str = Field(
        default="/run/secrets/aileron/browser-credential-keyring.json",
        min_length=1,
        description="Browser credential HKDF keyring file",
    )
    RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE: str = Field(
        default="/run/secrets/aileron/jwks.json",
        min_length=1,
        description="Ed25519 JWKS file containing active and rotation public keys",
    )
    RUNTIME_DATABASE_CREDENTIAL_KEY_FILE: str = Field(
        default="/run/secrets/aileron/runtime-database-credential.key",
        min_length=1,
        description="Manager-only HMAC key used to derive generation database credentials",
    )

    # === Kubernetes policy related settings ===
    RUNTIME_K8S_NAMESPACE: str = Field(
        default="default", description="Deploy namespace"
    )
    WORKSPACE_STORAGE_SIZE: str = Field(
        default="20Gi",
        min_length=1,
        description="Default Kubernetes Workspace data volume capacity",
    )
    RUNTIME_HOME_STORAGE_SIZE: str = Field(
        default="2Gi",
        min_length=1,
        description="Default Kubernetes Runtime home volume capacity",
    )
    KNOWLEDGE_BASES_PVC_NAME: str = Field(
        default="knowledge-bases-pvc",
        min_length=1,
        max_length=253,
        pattern=r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$",
        description="Shared Kubernetes PVC containing knowledge base subpaths",
    )
    RUNTIME_ASSERTION_PUBLIC_KEY_SET_SECRET_NAME: str = Field(
        default="runtime-assertion-public-jwks",
        min_length=1,
        max_length=253,
        pattern=r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?(?:\.[a-z0-9](?:[-a-z0-9]*[a-z0-9])?)*$",
        description="Kubernetes Secret containing the Runtime public JWKS",
    )
    RUNTIME_K8S_IMAGE: str = Field(
        default="",
        description="Container image used by runtime",
    )
    RUNTIME_K8S_BROWSER_IMAGE: str = Field(
        default="",
        description="Container image used by browser",
    )
    RUNTIME_K8S_CANVAS_IMAGE: str = Field(
        default="",
        description="Container image used by canvas",
    )
    RUNTIME_K8S_RUNTIME_RESOURCES: Annotated[Optional[dict], NoDecode] = Field(
        default=None,
        description="Helm-injected Kubernetes runtime resource configuration",
    )
    RUNTIME_K8S_BROWSER_RESOURCES: Annotated[Optional[dict], NoDecode] = Field(
        default=None,
        description="Helm-injected Kubernetes browser resource configuration",
    )
    RUNTIME_K8S_CANVAS_RESOURCES: Annotated[Optional[dict], NoDecode] = Field(
        default=None,
        description="Helm-injected Kubernetes canvas resource configuration",
    )
    CILIUM_ENABLED: bool = Field(
        default=False,
        description="Is Cilium-based firewall feature enabled",
    )
    FIREWALL_SEED_FILE: str = Field(
        default="",
        description="Manager-only initial workspace firewall configuration file",
    )
    # === Codex login settings ===
    CODEX_BIN: str = Field(
        default="/usr/local/bin/codex",
        description="Codex CLI binary used by workspace-manager for manager-owned login",
    )
    CODEX_MANAGER_STATE_DIR: str = Field(
        default="/data/codex-login",
        description="Directory for manager-owned per-user Codex login state",
    )

    # === Celery Settings ===
    CELERY_BROKER_URL_FILE: str = Field(
        default="",
        description="Mounted file containing the Celery broker Redis URL",
    )
    CELERY_BROKER_CA_CERT_FILE: str = Field(
        default="",
        description="Mounted CA certificate for the Celery broker Redis connection",
    )
    CELERY_RESULT_BACKEND_FILE: str = Field(
        default="",
        description="Mounted file containing the Celery result Redis URL",
    )
    CELERY_RESULT_BACKEND_CA_CERT_FILE: str = Field(
        default="",
        description="Mounted CA certificate for the Celery result Redis connection",
    )

    # === FileSaveSettings ===
    MARKETPLACE_STORAGE_PATH: str = Field(
        default="/data/marketplace", description="Marketplace registry storage path"
    )

    # === File management settings ===
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
    # === Logging settings ===
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # === Provider-neutral OIDC settings ===
    OIDC_ISSUER_URL: str = Field(
        ...,
        description="Canonical OIDC issuer URL",
    )
    OIDC_CA_CERT_FILE: str = Field(
        default="",
        description="Optional OIDC custom CA certificate file path",
    )
    OIDC_CLIENT_ID: str = Field(
        ...,
        description="OIDC confidential Manager client ID",
    )
    OIDC_CLIENT_SECRET_FILE: str = Field(
        default="/run/secrets/aileron/oidc-client-secret",
        min_length=1,
        description="Manager-readable OIDC client secret file",
    )
    OIDC_ALLOWED_ALGORITHMS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["RS256"],
        description="Allowed JWT signature algorithms",
    )
    OIDC_MAX_TOKEN_LIFETIME_SECONDS: int = Field(
        default=1800,
        gt=0,
        description="Maximum accepted JWT lifetime in seconds",
    )
    OIDC_REQUIRED_ACR: Optional[str] = Field(
        default=None,
        description="Required OIDC authentication assurance value",
    )
    OIDC_SCOPES: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        description="OIDC scopes requested by the browser client",
    )
    OIDC_JWKS_CACHE_TTL: int = Field(
        default=3600,
        gt=0,
        description="OIDC JWKS cache TTL in seconds",
    )
    OIDC_DISCOVERY_TIMEOUT_SECONDS: float = Field(
        default=5,
        gt=0,
        le=60,
        description="OIDC Discovery request timeout in seconds",
    )

    @property
    def oidc_discovery_url(self) -> str:
        """Return the canonical issuer Discovery URL."""

        return f"{self.OIDC_ISSUER_URL}/.well-known/openid-configuration"

    @property
    def oidc_callback_url(self) -> str:
        """Return the browser callback derived from the platform origin."""

        return f"{self.PLATFORM_PUBLIC_ORIGIN}/api/v1/oauth2/callback"

    @property
    def oidc_post_logout_redirect_url(self) -> str:
        """Return the post-logout redirect derived from the platform origin."""

        return f"{self.PLATFORM_PUBLIC_ORIGIN}/login"

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return the single credentialed browser origin."""

        return [self.PLATFORM_PUBLIC_ORIGIN]

    @property
    def oidc_client_secret(self) -> str:
        """Load the OIDC client secret from the configured mounted file."""

        try:
            value = Path(self.OIDC_CLIENT_SECRET_FILE).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("OIDC_CLIENT_SECRET_FILE must be readable") from exc
        secret = value.strip()
        if not secret:
            raise ValueError("OIDC_CLIENT_SECRET_FILE must not be empty")
        return secret

    @model_validator(mode="after")
    def load_firewall_seed(self) -> "Settings":
        """Load and validate the new-workspace firewall seed."""
        if not self.FIREWALL_SEED_FILE:
            self._firewall_seed = FirewallConfig()
            return self

        seed_path = Path(self.FIREWALL_SEED_FILE)
        try:
            seed_data = json.loads(seed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Invalid FIREWALL_SEED_FILE: {self.FIREWALL_SEED_FILE}"
            ) from exc
        self._firewall_seed = validate_firewall_seed_payload(seed_data)
        return self

    @property
    def firewall_seed(self) -> FirewallConfig:
        """Return a copy of the validated new-workspace firewall seed."""
        return self._firewall_seed.model_copy(deep=True)

    @field_validator("KB_ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_kb_allowed_extensions(cls, v):
        """Parse KB allowed extension list."""
        if isinstance(v, str):
            return [
                extension.strip().lower()
                for extension in v.split(",")
                if extension.strip()
            ]
        if isinstance(v, list):
            return [
                str(extension).strip().lower()
                for extension in v
                if str(extension).strip()
            ]
        return v

    @field_validator("OIDC_ALLOWED_ALGORITHMS", "OIDC_SCOPES", mode="before")
    @classmethod
    def parse_oidc_list_settings(cls, v):
        """Parse comma-separated OIDC list settings."""
        if isinstance(v, str):
            return [
                item.strip() for item in v.replace(",", " ").split() if item.strip()
            ]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("OIDC_REQUIRED_ACR", mode="before")
    @classmethod
    def normalize_oidc_required_acr(cls, v):
        """Normalize the optional required authentication assurance value."""

        if v is None:
            return None
        normalized = str(v).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_platform_oidc_configuration(self) -> "Settings":
        """Validate the canonical platform origin and OIDC issuer."""

        self.PLATFORM_PUBLIC_ORIGIN = _validate_public_url(
            self.PLATFORM_PUBLIC_ORIGIN,
            field_name="PLATFORM_PUBLIC_ORIGIN",
            environment=self.ENV,
            exact_origin=True,
        )
        self.OIDC_ISSUER_URL = _validate_public_url(
            self.OIDC_ISSUER_URL,
            field_name="OIDC_ISSUER_URL",
            environment=self.ENV,
            exact_origin=False,
            allow_local_service_host=True,
        )
        self.OIDC_CLIENT_ID = self.OIDC_CLIENT_ID.strip()
        self.OIDC_CLIENT_SECRET_FILE = self.OIDC_CLIENT_SECRET_FILE.strip()
        self.OIDC_CA_CERT_FILE = self.OIDC_CA_CERT_FILE.strip()
        if not self.OIDC_CLIENT_ID:
            raise ValueError("OIDC_CLIENT_ID must not be empty")
        if not self.OIDC_CLIENT_SECRET_FILE:
            raise ValueError("OIDC_CLIENT_SECRET_FILE must not be empty")
        unsupported = sorted(
            set(self.OIDC_ALLOWED_ALGORITHMS) - _SUPPORTED_OIDC_ALGORITHMS
        )
        if unsupported:
            raise ValueError(
                "Unsupported OIDC JWT algorithms: " + ", ".join(unsupported)
            )
        if not self.OIDC_ALLOWED_ALGORITHMS:
            raise ValueError("OIDC_ALLOWED_ALGORITHMS must not be empty")
        if "openid" not in self.OIDC_SCOPES:
            raise ValueError("OIDC_SCOPES must include the openid scope")
        return self

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
    def validate_runtime_database_trust(self) -> "Settings":
        """Require an atomic Kubernetes Runtime database trust reference."""

        values = {
            "RUNTIME_DATABASE_CA_SECRET_NAME": self.RUNTIME_DATABASE_CA_SECRET_NAME,
            "RUNTIME_DATABASE_CA_SECRET_KEY": self.RUNTIME_DATABASE_CA_SECRET_KEY,
            "RUNTIME_DATABASE_CA_REVISION": self.RUNTIME_DATABASE_CA_REVISION,
        }
        configured = [name for name, value in values.items() if value.strip()]
        if configured and len(configured) != len(values):
            raise ValueError(
                "Runtime database CA Secret name, key, and revision must be configured together"
            )
        for name, value in values.items():
            setattr(self, name, value.strip())
        self.HOST_PLATFORM_DATABASE_CA_CERT_FILE = (
            self.HOST_PLATFORM_DATABASE_CA_CERT_FILE.strip()
        )
        return self

    @model_validator(mode="after")
    def validate_k8s_component_resources(self) -> "Settings":
        """Require deployment-injected resources for Kubernetes provisioning."""
        if self.RUNTIME_PROVISIONER != "kubernetes":
            return self

        resources = {
            "RUNTIME_K8S_RUNTIME_RESOURCES": self.RUNTIME_K8S_RUNTIME_RESOURCES,
            "RUNTIME_K8S_BROWSER_RESOURCES": self.RUNTIME_K8S_BROWSER_RESOURCES,
            "RUNTIME_K8S_CANVAS_RESOURCES": self.RUNTIME_K8S_CANVAS_RESOURCES,
        }
        missing = [name for name, value in resources.items() if value is None]
        if missing:
            raise ValueError(
                "Kubernetes component resources must be injected by deployment: "
                + ", ".join(missing)
            )
        return self

    @property
    def is_production(self) -> bool:
        """Check if environment is production."""
        return self.ENV.lower() in ["production", "prod"]

    @property
    def database_url(self) -> str:
        """Resolve the database URL from the mounted Secret when configured."""

        secret_file = self.DATABASE_URL_FILE.strip()
        if not secret_file:
            raise ValueError("DATABASE_URL_FILE must reference a readable file")
        try:
            value = Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(
                "DATABASE_URL_FILE must reference a readable file"
            ) from exc
        if not value:
            raise ValueError("DATABASE_URL_FILE must not be empty")
        return value

    @staticmethod
    def _redis_url_from_file(
        *,
        url_file: str,
        ca_cert_file: str,
        setting_name: str,
    ) -> str:
        """Resolve one standalone Redis URL and its optional mounted trust bundle."""

        path_value = url_file.strip()
        if not path_value:
            raise ValueError(f"{setting_name}_FILE must reference a readable file")
        try:
            value = Path(path_value).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(
                f"{setting_name}_FILE must reference a readable file"
            ) from exc
        if not value:
            raise ValueError(f"{setting_name}_FILE must not be empty")

        parsed = urlsplit(value)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError(
                f"{setting_name}_FILE must contain a standalone redis:// or rediss:// URL"
            )
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError(
                f"{setting_name}_FILE must contain one standalone Redis endpoint"
            ) from exc
        logical_database = parsed.path.removeprefix("/")
        if not logical_database.isdigit() or "/" in logical_database:
            raise ValueError(
                f"{setting_name}_FILE must select one numeric logical database"
            )

        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "ssl_ca_certs" in query or "ssl_cert_reqs" in query:
            raise ValueError(
                f"{setting_name}_FILE must not configure TLS trust in the URL"
            )

        ca_path = ca_cert_file.strip()
        if parsed.scheme == "redis" and ca_path:
            raise ValueError(f"{setting_name} cannot configure a CA for redis://")
        if parsed.scheme == "rediss":
            query["ssl_cert_reqs"] = "required"
            if ca_path:
                try:
                    Path(ca_path).read_bytes()
                except OSError as exc:
                    raise ValueError(
                        f"{setting_name}_CA_CERT_FILE must reference a readable file"
                    ) from exc
                query["ssl_ca_certs"] = ca_path

        return urlunsplit(parsed._replace(query=urlencode(query)))

    @property
    def redis_url(self) -> str:
        """Resolve the general Redis URL from its mounted Secret."""

        return self._redis_url_from_file(
            url_file=self.REDIS_URL_FILE,
            ca_cert_file=self.REDIS_CA_CERT_FILE,
            setting_name="REDIS_URL",
        )

    @property
    def celery_broker_url(self) -> str:
        """Resolve the Celery broker URL from its mounted Secret."""

        return self._redis_url_from_file(
            url_file=self.CELERY_BROKER_URL_FILE,
            ca_cert_file=self.CELERY_BROKER_CA_CERT_FILE,
            setting_name="CELERY_BROKER_URL",
        )

    @property
    def celery_result_backend(self) -> str:
        """Resolve the Celery result backend URL from its mounted Secret."""

        return self._redis_url_from_file(
            url_file=self.CELERY_RESULT_BACKEND_FILE,
            ca_cert_file=self.CELERY_RESULT_BACKEND_CA_CERT_FILE,
            setting_name="CELERY_RESULT_BACKEND",
        )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
        # Disable automatic JSON parsing, let validators handle it
        env_parse_none_str="null",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    settings = Settings()
    return settings
