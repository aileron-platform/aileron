"""
Keycloak 認證模組 (Workspace Runtime)

提供 JWT token 驗證功能，用於驗證前端傳來的 Keycloak access token。
"""

from app.modules.auth.config import KeycloakConfig, get_keycloak_config
from app.modules.auth.jwt_utils import (
    JWTUtils,
    JWTValidationError,
    JWKSFetchError,
    get_jwt_utils,
    clear_jwt_utils_cache,
)
from app.modules.auth.jwks_cache import (
    JKWSCache,
    JWKSFetchError as JWKSProviderError,
    get_jwks_cache,
    clear_jwks_cache,
)

__all__ = [
    "KeycloakConfig",
    "get_keycloak_config",
    "JWTUtils",
    "JWTValidationError",
    "JWKSFetchError",
    "get_jwt_utils",
    "clear_jwt_utils_cache",
    "JKWSCache",
    "JWKSProviderError",
    "get_jwks_cache",
    "clear_jwks_cache",
]
