"""
Workspace Runtime 配置設定

運行時環境專用配置，支援容器內環境變數配置
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Workspace Runtime 設定類別"""

    # === 應用程式基本設定 ===
    APP_NAME: str = Field(default="Aileron - Workspace Runtime", description="應用程式名稱")
    VERSION: str = Field(default="1.0.0", description="應用程式版本")
    DEBUG: bool = Field(default=False, description="除錯模式")
    ENV: str = Field(default="production", description="執行環境")

    # === 伺服器設定 ===
    HOST: str = Field(default="0.0.0.0", description="伺服器主機")
    PORT: int = Field(default=3002, description="伺服器端口")

    # === 資料庫設定 ===
    # 使用與 Workspace Manager 相同的資料庫以讀取排程任務
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/aileron",
        description="資料庫連線字串（與 Workspace Manager 共用）"
    )

    # === Redis 設定 ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 連線 URL（用於 token 驗證）"
    )

    # === 工作區設定 ===
    WORKSPACE_ID: str = Field(default="default", description="工作區 ID")
    WORKSPACE_PATH: str = Field(default="/workspace", description="工作區路徑")
    WORKSPACE_USER: str = Field(default="developer", description="工作區用戶")

    # === Workspace Manager 連接設定 ===
    MANAGER_URL: str = Field(
        default="http://workspace-manager:8000",
        description="Workspace Manager API URL"
    )
    MANAGER_API_TOKEN: Optional[str] = Field(default=None, description="Manager API Token")

    # === Public Routing 設定 ===
    FRONTEND_PUBLIC_URL: Optional[str] = Field(
        default=None,
        description="Frontend 對外公開 URL，用於 public domain 模式下的 CORS"
    )

    # === Claude Code 設定 ===
    CLAUDE_EXECUTION_TIMEOUT_SECONDS: int = Field(
        default=1800,
        description="Claude CLI 單次執行允許的最長秒數 (預設 30 分鐘)"
    )
    DEFAULT_CLAUDE_MODEL: Optional[str] = Field(
        default=None,
        description="預設的 Claude 模型。如果為 None 或空字串,則讓 Claude SDK 使用其預設值"
    )

    # === CORS 設定 ===
    ALLOWED_ORIGINS: List[str] = Field(
        default=[],
        description="允許的 CORS 來源"
    )

    # === 檔案管理設定 ===
    FILE_TREE_MAX_DEPTH: int = Field(
        default=10,
        description="檔案樹掃描最大深度（預設 10 層）"
    )
    ARCHIVE_MAX_TOTAL_SIZE_BYTES: int = Field(
        default=100 * 1024 * 1024,
        description="壓縮檔解壓總大小上限"
    )
    ARCHIVE_MAX_ENTRY_SIZE_BYTES: int = Field(
        default=20 * 1024 * 1024,
        description="壓縮檔單一檔案大小上限"
    )
    ARCHIVE_MAX_ENTRY_COUNT: int = Field(
        default=1000,
        description="壓縮檔 entry 數量上限"
    )

    # === 檔案監控設定 ===
    WATCH_PATTERNS: List[str] = Field(
        default=["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", "*.json", "*.md"],
        description="監控的檔案模式"
    )
    IGNORE_PATTERNS: List[str] = Field(
        default=[
            "node_modules/*", ".git/*", "__pycache__/*", "*.pyc",
            ".venv/*", "venv/*", ".env", "*.log", ".DS_Store"
        ],
        description="忽略的檔案模式"
    )

    # === 系統監控設定 ===
    MONITOR_INTERVAL: int = Field(default=5, description="系統監控間隔（秒）")
    CPU_THRESHOLD: float = Field(default=80.0, description="CPU 使用率警告閾值")
    MEMORY_THRESHOLD: float = Field(default=85.0, description="記憶體使用率警告閾值")
    DISK_THRESHOLD: float = Field(default=90.0, description="磁碟使用率警告閾值")

    # === WebSocket 設定 ===
    WS_HEARTBEAT_INTERVAL: int = Field(default=30, description="WebSocket 心跳間隔（秒）")
    WS_MESSAGE_MAX_SIZE: int = Field(default=1024 * 1024, description="WebSocket 訊息最大大小")

    # === 日誌設定 ===
    LOG_LEVEL: str = Field(default="INFO", description="日誌等級")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日誌格式"
    )

    # === 安全設定 ===
    INTERNAL_API_TOKEN: str = Field(
        default="dev-internal-token",
        description="內部 API 認證 Token"
    )

    # === 開發工具設定 ===
    AUTO_INSTALL_PACKAGES: bool = Field(default=True, description="自動安裝套件")
    PACKAGE_MANAGERS: List[str] = Field(
        default=["npm", "pip", "yarn", "pnpm"],
        description="支援的套件管理器"
    )

    # === 執行環境設定 ===
    NODE_VERSION: Optional[str] = Field(default=None, description="Node.js 版本")
    PYTHON_VERSION: Optional[str] = Field(default=None, description="Python 版本")

    # === Draw.io 整合設定 ===
    DRAWIO_ENABLED: bool = Field(
        default=True,
        description="Draw.io 容器整合是否啟用（預設啟用以維持既有部署相容）"
    )
    DRAWIO_EXTERNAL_URL: str = Field(
        default="http://localhost:8083/draw",
        description="Draw.io 外部訪問 URL（瀏覽器可訪問）"
    )
    DRAWIO_INTERNAL_URL: str = Field(
        default="http://drawio:8080",
        description="Draw.io 內部訪問 URL（容器內部訪問）"
    )
    DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS: float = Field(
        default=1.5,
        description="Draw.io 內部健康檢查逾時秒數"
    )
    DRAWIO_HEALTHCHECK_TTL_SECONDS: int = Field(
        default=30,
        description="Draw.io 健康檢查結果快取秒數"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS 來源清單"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("WATCH_PATTERNS", mode="before")
    @classmethod
    def parse_watch_patterns(cls, v):
        """解析監控模式清單"""
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split(",")]
        return v

    @field_validator("IGNORE_PATTERNS", mode="before")
    @classmethod
    def parse_ignore_patterns(cls, v):
        """解析忽略模式清單"""
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split(",")]
        return v

    @field_validator("PACKAGE_MANAGERS", mode="before")
    @classmethod
    def parse_package_managers(cls, v):
        """解析套件管理器清單"""
        if isinstance(v, str):
            return [manager.strip() for manager in v.split(",")]
        return v

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

    @property
    def workspace_url(self) -> str:
        """工作區外部 URL"""
        return f"http://localhost:{self.PORT}"

    @property
    def effective_allowed_origins(self) -> List[str]:
        """取得實際生效的 CORS origins。"""
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
        """Manager API 請求標頭"""
        headers = {"Content-Type": "application/json"}
        # 優先使用內部 token 讓 runtime 可直接呼叫 manager（容器內服務通訊）
        if self.INTERNAL_API_TOKEN:
            headers["X-Internal-Token"] = self.INTERNAL_API_TOKEN
        if self.MANAGER_API_TOKEN:
            headers["Authorization"] = f"Bearer {self.MANAGER_API_TOKEN}"
        return headers

    @staticmethod
    def _normalize_origin(value: Optional[str]) -> Optional[str]:
        """將 URL/Origin 正規化為 CORS origin。"""
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
    """取得應用程式設定（帶快取）"""
    import logging
    _settings = Settings()
    if _settings.is_production and _settings.INTERNAL_API_TOKEN == "dev-internal-token":
        logging.getLogger(__name__).warning(
            "INTERNAL_API_TOKEN is using insecure default value in production! "
            "Set the INTERNAL_API_TOKEN environment variable."
        )
    return _settings


# 便利函數
def get_workspace_path() -> str:
    """取得工作區路徑"""
    return get_settings().WORKSPACE_PATH


def get_manager_url() -> str:
    """取得 Manager URL"""
    return get_settings().MANAGER_URL


def is_debug_mode() -> bool:
    """是否為除錯模式"""
    return get_settings().DEBUG
