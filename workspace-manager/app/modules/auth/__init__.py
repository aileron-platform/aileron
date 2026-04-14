"""
Keycloak 認證模組

提供 OAuth2/OIDC 認證整合，包括：
- Keycloak 配置管理
- JWT token 驗證
- OAuth2 流程處理
- 用戶同步
- 角色和權限管理
- JWT 認證中間件
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
from app.modules.auth.router import router as auth_router
from app.modules.auth.user_sync import (
    UserSyncService,
    UserSyncError,
    UserNotFoundError,
    get_user_sync_service,
)
from app.modules.auth.auth_decorators import (
    PermissionDeniedError,
    get_user_permissions,
    has_permission,
    has_role,
    has_any_role,
    has_all_permissions,
    has_any_permission,
    require_role,
    require_any_role,
    require_permission,
    require_any_permission,
    require_all_permissions,
    get_current_user,
    get_optional_current_user,
    require_authenticated_user,
    get_current_user_id,
)
from app.modules.auth.middleware import (
    JWTAuthenticationMiddleware,
    StrictJWTAuthenticationMiddleware,
)
from app.modules.auth.keycloak_profile_sync import (
    KeycloakProfileSync,
    get_keycloak_profile_sync,
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
    "auth_router",
    "UserSyncService",
    "UserSyncError",
    "UserNotFoundError",
    "get_user_sync_service",
    "PermissionDeniedError",
    "get_user_permissions",
    "has_permission",
    "has_role",
    "has_any_role",
    "has_all_permissions",
    "has_any_permission",
    "require_role",
    "require_any_role",
    "require_permission",
    "require_any_permission",
    "require_all_permissions",
    "get_current_user",
    "get_optional_current_user",
    "require_authenticated_user",
    "get_current_user_id",
    "JWTAuthenticationMiddleware",
    "StrictJWTAuthenticationMiddleware",
    "KeycloakProfileSync",
    "get_keycloak_profile_sync",
]
