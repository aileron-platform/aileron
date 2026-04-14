"""
Keycloak 配置管理

從環境變數讀取 Keycloak 連接配置，提供認證相關的設定。
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


class KeycloakConfig(BaseSettings):
    """Keycloak 配置類

    從環境變數讀取 Keycloak 連接和認證配置。
    認證為強制啟用，不支援關閉。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Keycloak 服務配置 ===
    server_url: str
    realm: str
    client_id: str
    client_secret: Optional[str] = None

    # === 認證永遠啟用 ===
    enabled: bool = True

    # === JWT 配置 ===
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 30

    # === JWKS 配置 ===
    jwks_url: Optional[str] = None
    jwks_cache_ttl: int = 3600  # 秒

    @classmethod
    def from_env(cls) -> "KeycloakConfig":
        """從環境變數創建配置實例"""
        env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"

        possible_paths = [
            env_path,
            Path(__file__).parent.parent.parent.parent / ".env",
            Path.cwd() / ".env",
        ]

        for path in possible_paths:
            if path.exists():
                load_dotenv(path)
                break

        server_url = os.getenv("KEYCLOAK_SERVER_URL", "")
        realm = os.getenv("KEYCLOAK_REALM", "")
        client_id = os.getenv("KEYCLOAK_CLIENT_ID", "")
        client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")

        if server_url:
            if "/realms/" in server_url:
                if not server_url.endswith("/" + realm):
                    server_url = f"{server_url}/{realm}"
            else:
                server_url = f"{server_url}/realms/{realm}"

        return cls(
            enabled=True,
            server_url=server_url,
            realm=realm,
            client_id=client_id,
            client_secret=client_secret,
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "RS256"),
            jwt_access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            jwks_url=f"{server_url}/protocol/openid-connect/certs" if server_url else None,
        )

    @property
    def issuer_url(self) -> str:
        """獲取 issuer URL"""
        return self.server_url


@lru_cache()
def get_keycloak_config() -> KeycloakConfig:
    """獲取 Keycloak 配置單例（緩存）"""
    return KeycloakConfig.from_env()


def reload_keycloak_config() -> KeycloakConfig:
    """重新載入 Keycloak 配置（清除緩存）"""
    get_keycloak_config.cache_clear()
    return get_keycloak_config()
