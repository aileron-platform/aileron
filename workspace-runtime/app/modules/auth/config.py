"""
Keycloak configuration management

Reads Keycloak connection configuration from environment variables and provides authentication settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


class KeycloakConfig(BaseSettings):
    """Keycloak configuration class

    Reads Keycloak connection and authentication configuration from environment variables.
    Authentication is mandatory and cannot be disabled.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Keycloak service configuration ===
    server_url: str
    realm: str
    client_id: str
    client_secret: Optional[str] = None

    # === Authentication always enabled ===
    enabled: bool = True

    # === JWT configuration ===
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 30

    # === JWKS configuration ===
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
        """Get issuer URL"""
        return self.server_url


@lru_cache()
def get_keycloak_config() -> KeycloakConfig:
    """Get Keycloak configuration singleton (cached)"""
    return KeycloakConfig.from_env()


def reload_keycloak_config() -> KeycloakConfig:
    """Reload Keycloak configuration (clear cache)"""
    get_keycloak_config.cache_clear()
    return get_keycloak_config()
