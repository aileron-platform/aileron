"""
Keycloak configuration management

Read Keycloak connection configuration from environment variables and provide authentication-related settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from app.config.settings import get_settings


class KeycloakConfig(BaseSettings):
    """Keycloak configuration class

    Read Keycloak connection and authentication configuration from environment variables.
    Authentication is mandatory and does not support disabling.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Keycloak Service Configuration ===
    server_url: str
    external_server_url: str
    realm: str
    client_id: str
    client_secret: Optional[str] = None

    # === Authentication always enabled ===
    enabled: bool = True

    # === JWT Configuration ===
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 30

    # === JWKS Configuration ===
    jwks_url: Optional[str] = None
    jwks_cache_ttl: int = 3600  # seconds

    @classmethod
    def from_env(cls) -> "KeycloakConfig":
        """Create configuration instance from environment variables"""
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

        settings = get_settings()
        internal_server_url = os.getenv("KEYCLOAK_SERVER_URL", "")
        external_server_url = os.getenv("KEYCLOAK_EXTERNAL_SERVER_URL", "").strip()
        realm = os.getenv("KEYCLOAK_REALM", "")
        client_id = os.getenv("KEYCLOAK_CLIENT_ID", "")
        client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")

        if not external_server_url:
            external_server_url = settings.build_public_url(settings.PUBLIC_KEYCLOAK_HOST)

        return cls(
            enabled=True,
            server_url=cls._normalize_realm_url(internal_server_url, realm),
            external_server_url=cls._normalize_realm_url(external_server_url, realm),
            realm=realm,
            client_id=client_id,
            client_secret=client_secret,
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "RS256"),
            jwt_access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            jwks_url=(
                f"{cls._normalize_realm_url(internal_server_url, realm)}/protocol/openid-connect/certs"
                if internal_server_url
                else None
            ),
        )

    @staticmethod
    def _normalize_realm_url(server_url: str, realm: str) -> str:
        normalized = server_url.rstrip("/")
        if not normalized:
            return normalized
        if "/realms/" in normalized:
            if realm and not normalized.endswith(f"/{realm}"):
                return f"{normalized}/{realm}"
            return normalized
        if not realm:
            return normalized
        return f"{normalized}/realms/{realm}"

    def get_openid_configuration(self) -> dict:
        """Get OpenID Connect configuration endpoint URL"""
        return {
            "issuer": f"{self.external_server_url}",
            "authorization_endpoint": f"{self.external_server_url}/protocol/openid-connect/auth",
            "token_endpoint": f"{self.server_url}/protocol/openid-connect/token",
            "userinfo_endpoint": f"{self.server_url}/protocol/openid-connect/userinfo",
            "jwks_uri": f"{self.server_url}/protocol/openid-connect/certs",
            "end_session_endpoint": f"{self.external_server_url}/protocol/openid-connect/logout",
        }


@lru_cache()
def get_keycloak_config() -> KeycloakConfig:
    """Get Keycloak configuration singleton (cached)"""
    return KeycloakConfig.from_env()


def reload_keycloak_config() -> KeycloakConfig:
    """Reload Keycloak configuration (clear cache)"""
    get_keycloak_config.cache_clear()
    return get_keycloak_config()
