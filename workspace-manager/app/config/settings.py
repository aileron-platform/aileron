"""
應用程式配置設定

支援多環境配置，從環境變數或 .env 檔案載入設定
"""

import json
import os
from functools import lru_cache
from typing import Annotated, List, Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """應用程式設定類別"""

    # === 應用程式基本設定 ===
    APP_NAME: str = Field(default="Aileron - Workspace Manager", description="應用程式名稱")
    VERSION: str = Field(default="1.0.0", description="應用程式版本")
    DEBUG: bool = Field(default=False, description="除錯模式")
    ENV: str = Field(default="production", description="執行環境")

    # === 伺服器設定 ===
    HOST: str = Field(default="0.0.0.0", description="伺服器主機")
    PORT: int = Field(default=3001, description="伺服器端口")

    # === 資料庫設定 ===
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/aileron",
        description="資料庫連線 URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="是否顯示 SQL 查詢")
    DATABASE_POOL_SIZE: int = Field(default=10, description="資料庫連線池大小")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="資料庫連線池最大溢位")

    # === Redis 設定 ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 連線 URL"
    )
    REDIS_CACHE_TTL: int = Field(default=3600, description="Redis 快取過期時間（秒）")

    # === CORS 設定 ===
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:8082,http://localhost:8083",
        description="允許的 CORS 來源（逗號分隔）"
    )

    # === Docker 設定 ===
    DOCKER_HOST: Optional[str] = Field(default=None, description="Docker 主機")
    DOCKER_NETWORK: str = Field(default="aileron", description="Docker 網路名稱")
    WORKSPACE_IMAGE_PREFIX: str = Field(default="aidh-workspace", description="工作區映像前綴")

    # === Runtime 佈建設定 ===
    RUNTIME_PROVISIONER: Literal["docker", "kubernetes"] = Field(
        default="docker", description="Runtime 佈建策略"
    )
    PLATFORM: str = Field(
        default="linux", description="運行平台 (linux/mac/windows)"
    )
    RUNTIME_SCRIPT_ROOT: str = Field(
        default="/data/init-scripts", description="Runtime 產生腳本輸出根目錄"
    )
    HOST_WORKSPACES_DIR: str = Field(
        default="/var/lib/aileron/workspaces",
        description="主機上掛載 workspace 檔案的目錄",
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
    RUNTIME_RESERVED_PORTS: Annotated[List[int], NoDecode] = Field(
        default_factory=lambda: [3002], description="預留不可使用的容器埠"
    )
    RUNTIME_AUTO_RETRY: bool = Field(default=True, description="佈建失敗時是否自動重試")
    RUNTIME_MAX_RETRIES: int = Field(default=3, description="背景任務最大重試次數")

    # === Kubernetes 策略相關設定 ===
    RUNTIME_K8S_NAMESPACE: str = Field(default="default", description="部署 Namespace")
    RUNTIME_K8S_CR_NAMESPACE: Optional[str] = Field(
        default=None,
        description="Workspace 自訂資源建立所在的 namespace；未設定時沿用部署 namespace",
    )
    RUNTIME_K8S_ALLOWED_NAMESPACES: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["default"],
        description="允許使用者選擇的 Kubernetes Namespace 清單",
    )
    RUNTIME_K8S_SERVICE_TYPE: str = Field(
        default="ClusterIP", description="Service 類型"
    )
    RUNTIME_K8S_NODE_PORT: Optional[int] = Field(
        default=None, description="若使用 NodePort，指定外部埠號"
    )
    RUNTIME_K8S_NODE_ADDRESS: str = Field(
        default="127.0.0.1", description="NodePort 服務對外位址"
    )
    RUNTIME_K8S_PVC_NAME: str = Field(
        default="workspace-runtime-pvc", description="Workspace PVC 名稱"
    )
    RUNTIME_K8S_IMAGE: str = Field(
        default="ailerondocker/workspace-runtime:latest-lite-amd64",
        description="Runtime 使用的容器映像",
    )
    RUNTIME_K8S_BROWSER_IMAGE: str = Field(
        default="ailerondocker/workspace-chrome:latest-amd64",
        description="Browser 使用的容器映像",
    )
    RUNTIME_K8S_NEXTJS_IMAGE: str = Field(
        default="ailerondocker/workspace-nextjs:latest-amd64",
        description="Next.js 使用的容器映像",
    )
    RUNTIME_K8S_RUNTIME_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "2Gi"},
            "limits": {"cpu": "2000m", "memory": "4Gi"},
        },
        description="Kubernetes runtime 預設資源配置",
    )
    RUNTIME_K8S_BROWSER_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        description="Kubernetes browser 預設資源配置",
    )
    RUNTIME_K8S_NEXTJS_RESOURCES: Annotated[dict, NoDecode] = Field(
        default_factory=lambda: {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        description="Kubernetes nextjs 預設資源配置",
    )
    CILIUM_ENABLED: bool = Field(
        default=False,
        description="是否啟用 Cilium 與 firewall 功能",
    )
    PUBLIC_SCHEME: str = Field(
        default="http",
        description="平台公開網址使用的 scheme",
    )
    PUBLIC_BASE_DOMAIN: str = Field(
        default="aileron.localhost",
        description="平台公開網址的 base domain",
    )
    PUBLIC_FRONTEND_HOST: str = Field(
        default="aileron.{baseDomain}",
        description="Frontend 對外固定 host 模板",
    )
    PUBLIC_WORKSPACE_MANAGER_HOST: str = Field(
        default="workspace-manager.{baseDomain}",
        description="Workspace Manager 對外固定 host 模板",
    )
    PUBLIC_KEYCLOAK_HOST: str = Field(
        default="keycloak.{baseDomain}",
        description="Keycloak 對外固定 host 模板",
    )
    PUBLIC_RUNTIME_HOST_PATTERN: str = Field(
        default="workspace-runtime-{workspaceId}.{baseDomain}",
        description="Workspace Runtime 對外 host pattern",
    )
    PUBLIC_BROWSER_HOST_PATTERN: str = Field(
        default="workspace-browser-{workspaceId}.{baseDomain}",
        description="Workspace Browser 對外 host pattern",
    )
    PUBLIC_NEXTJS_HOST_PATTERN: str = Field(
        default="workspace-nextjs-{workspaceId}.{baseDomain}",
        description="Workspace Next.js 對外 host pattern",
    )
    FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS: Annotated[List[str], NoDecode] = Field(
        default_factory=list,
        description="平台預設的 workspace firewall 允許網域清單",
    )
    FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS: Annotated[List[str], NoDecode] = Field(
        default_factory=list,
        description="平台預設的 browser firewall 允許網域清單",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED: bool = Field(
        default=False,
        description="是否在 Kubernetes 模式下 bootstrap 預設 workspace",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_ID: str = Field(
        default="default-workspace",
        description="bootstrap 預設 workspace ID",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_OWNER_EMAIL: str = Field(
        default="admin@aileron.com",
        description="bootstrap 預設 workspace owner email",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_GIT_URL: str = Field(
        default="",
        description="bootstrap 預設 workspace git URL",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_BRANCH: str = Field(
        default="main",
        description="bootstrap 預設 workspace branch",
    )
    BOOTSTRAP_DEFAULT_WORKSPACE_TARGET_NAMESPACE: Optional[str] = Field(
        default=None,
        description="bootstrap 預設 workspace target namespace；未設定時沿用 RUNTIME_K8S_NAMESPACE",
    )

    # === Celery 設定 ===
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery Broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery 結果後端"
    )

    # === 檔案儲存設定 ===
    UPLOAD_DIR: str = Field(default="./uploads", description="檔案上傳目錄")
    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024, description="最大檔案大小（位元組）")
    ALLOWED_FILE_TYPES: str = Field(
        default=".zip,.tar.gz,.tar,.py,.js,.ts,.json,.md",
        description="允許的檔案類型（逗號分隔）"
    )

    # === 模板中心設定 ===
    TEMPLATE_STORAGE_PATH: str = Field(
        default="/data/template-center",
        description="模板儲存路徑"
    )

    # === 檔案管理設定 ===
    FILE_TREE_MAX_DEPTH: int = Field(
        default=10,
        description="檔案樹掃描最大深度（預設 10 層）"
    )

    # === 日誌設定 ===
    LOG_LEVEL: str = Field(default="INFO", description="日誌等級")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日誌格式"
    )

    # === 監控與健康檢查設定 ===
    HEALTH_CHECK_TIMEOUT: int = Field(default=30, description="健康檢查超時時間（秒）")

    # === Internal API 設定 ===
    INTERNAL_API_TOKEN: str = Field(
        default="dev-internal-token",
        description="Internal API 認證 Token"
    )

    # === Keycloak 設定 ===
    KEYCLOAK_SERVER_URL: str = Field(
        default="http://aileron-keycloak-dev:8080",
        description="Keycloak 伺服器 URL（Docker 網路內部地址）"
    )
    KEYCLOAK_REALM: str = Field(
        default="aileron",
        description="Keycloak Realm 名稱"
    )
    KEYCLOAK_CLIENT_ID: str = Field(
        default="aileron-frontend",
        description="Keycloak Client ID"
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        """取得 CORS 來源清單"""
        origins: list[str] = []

        if isinstance(self.ALLOWED_ORIGINS, str):
            # 移除可能的引號
            v = self.ALLOWED_ORIGINS.strip().strip('"').strip("'")
            # 檢查是否為 JSON 格式
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

        # 保留順序去重
        return list(dict.fromkeys(origins))

    @property
    def allowed_file_types_list(self) -> List[str]:
        """取得允許的檔案類型清單"""
        if isinstance(self.ALLOWED_FILE_TYPES, str):
            return [file_type.strip() for file_type in self.ALLOWED_FILE_TYPES.split(",") if file_type.strip()]
        return [".zip", ".tar.gz", ".tar", ".py", ".js", ".ts", ".json", ".md"]

    @field_validator("RUNTIME_RESERVED_PORTS", mode="before")
    @classmethod
    def parse_reserved_ports(cls, v):
        """解析預留埠號清單"""
        if isinstance(v, str):
            return [int(port.strip()) for port in v.split(",") if port.strip()]
        return v

    @field_validator("BROWSER_WEBRTC_RESERVED_UDP_RANGES", mode="before")
    @classmethod
    def parse_browser_webrtc_reserved_udp_ranges(cls, v):
        """解析 Browser WebRTC 要避開的 UDP 區間"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("RUNTIME_K8S_ALLOWED_NAMESPACES", mode="before")
    @classmethod
    def parse_k8s_allowed_namespaces(cls, v):
        """解析允許的 Kubernetes namespace 清單"""
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
        "PUBLIC_NEXTJS_HOST_PATTERN",
        mode="before",
    )
    @classmethod
    def normalize_public_routing_values(cls, v):
        """正規化 public routing 設定字串。"""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("PUBLIC_SCHEME")
    @classmethod
    def validate_public_scheme(cls, v: str) -> str:
        """限制公開網址 scheme。"""
        normalized = v.lower()
        if normalized not in {"http", "https"}:
            raise ValueError("PUBLIC_SCHEME must be either 'http' or 'https'")
        return normalized

    @field_validator("PUBLIC_RUNTIME_HOST_PATTERN", "PUBLIC_BROWSER_HOST_PATTERN", "PUBLIC_NEXTJS_HOST_PATTERN")
    @classmethod
    def validate_workspace_host_patterns(cls, v: str) -> str:
        """驗證 workspace host pattern 必須包含 workspaceId。"""
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
        """解析平台預設 firewall 網域清單"""
        if isinstance(v, str):
            return [domain.strip() for domain in v.split(",") if domain.strip()]
        return v

    @field_validator(
        "RUNTIME_K8S_RUNTIME_RESOURCES",
        "RUNTIME_K8S_BROWSER_RESOURCES",
        "RUNTIME_K8S_NEXTJS_RESOURCES",
        mode="before",
    )
    @classmethod
    def parse_k8s_component_resources(cls, v):
        """解析 Kubernetes component resources JSON。"""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode="after")
    def validate_public_routing_templates(self) -> "Settings":
        """驗證 public routing 所需欄位與模板。"""
        if not self.PUBLIC_BASE_DOMAIN:
            raise ValueError("PUBLIC_BASE_DOMAIN must not be empty")

        self.resolve_public_host(self.PUBLIC_FRONTEND_HOST)
        self.resolve_public_host(self.PUBLIC_WORKSPACE_MANAGER_HOST)
        self.resolve_public_host(self.PUBLIC_KEYCLOAK_HOST)
        self.resolve_public_host(self.PUBLIC_RUNTIME_HOST_PATTERN, workspace_id="sample")
        self.resolve_public_host(self.PUBLIC_BROWSER_HOST_PATTERN, workspace_id="sample")
        self.resolve_public_host(self.PUBLIC_NEXTJS_HOST_PATTERN, workspace_id="sample")
        return self

    def resolve_public_host(self, template: str, workspace_id: Optional[str] = None) -> str:
        """將 public host 模板解析成實際 host。"""
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
        """組合完整 public URL。"""
        return f"{self.PUBLIC_SCHEME}://{self.resolve_public_host(template, workspace_id=workspace_id)}"

    @property
    def database_url_async(self) -> str:
        """取得非同步資料庫連線 URL"""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    @property
    def is_development(self) -> bool:
        """是否為開發環境"""
        return self.ENV.lower() in ["development", "dev"]

    @property
    def is_production(self) -> bool:
        """是否為生產環境"""
        return self.ENV.lower() in ["production", "prod"]

    @property
    def is_testing(self) -> bool:
        """是否為測試環境"""
        return self.ENV.lower() in ["testing", "test"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        env_ignore_empty=True,
        # 禁用 JSON 自動解析，讓 validator 處理
        env_parse_none_str="null"
    )


@lru_cache()
def get_settings() -> Settings:
    """取得應用程式設定（帶快取）"""
    return Settings()


# 便利函數
def get_database_url() -> str:
    """取得資料庫連線 URL"""
    return get_settings().DATABASE_URL


def get_redis_url() -> str:
    """取得 Redis 連線 URL"""
    return get_settings().REDIS_URL


def is_debug_mode() -> bool:
    """是否為除錯模式"""
    return get_settings().DEBUG
