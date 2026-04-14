"""認證服務"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SimpleUser:
    """簡單的用戶對象（用於認證）"""

    def __init__(self, user_id: str, email: Optional[str] = None, username: Optional[str] = None, roles: Optional[list] = None):
        self.id = user_id
        self.user_id = user_id  # 兼容性
        self.email = email
        self.username = username or user_id
        self.roles = roles or []


class AuthService:
    """提供基本的使用者認證流程（只讀驗證）

    使用 JWT Token (Keycloak) 進行認證。
    """

    def __init__(self) -> None:
        self._jwt_utils = None
        self._keycloak_enabled = False

        # 嘗試導入 JWT 工具
        try:
            from app.modules.auth import get_keycloak_config, get_jwt_utils
            config = get_keycloak_config()
            if config.enabled:
                self._jwt_utils = get_jwt_utils()
                self._keycloak_enabled = True
                logger.info("JWT authentication enabled (Keycloak)")
            else:
                logger.warning("JWT authentication disabled by config — all tokens will be rejected")
        except ImportError as e:
            logger.warning(f"JWT auth module unavailable, all tokens will be rejected: {e}")
        except Exception as e:
            logger.warning(f"Failed to initialize JWT auth, all tokens will be rejected: {e}", exc_info=True)

    async def validate_access_token(self, token: str) -> Optional[SimpleUser]:
        """驗證 access token 並返回用戶對象

        Args:
            token: JWT Access token

        Returns:
            SimpleUser 對象或 None
        """
        if not self._keycloak_enabled or self._jwt_utils is None:
            logger.warning("JWT authentication not enabled, rejecting token")
            return None

        try:
            # JWT tokens 有點號分隔
            if '.' not in token or len(token.split('.')) != 3:
                logger.debug("Token is not a valid JWT format")
                return None

            token_preview = f"{token[:20]}..." if len(token) > 20 else token
            logger.info(f"JWT authentication attempt: {token_preview}")

            jwt_validation_start = time.perf_counter()
            payload = await self._jwt_utils.decode_token_async(token, verify_audience=False)
            jwt_validation_duration = time.perf_counter() - jwt_validation_start

            user_id = payload.get("sub")
            if user_id:
                realm_access = payload.get("realm_access", {})
                roles = realm_access.get("roles", [])

                user = SimpleUser(
                    user_id=user_id,
                    email=payload.get("email"),
                    username=payload.get("preferred_username"),
                    roles=roles
                )

                logger.info(f"JWT authentication successful: user_id={user_id}, username={user.username}, roles={len(roles)}, duration={jwt_validation_duration*1000:.2f}ms")
                return user
            else:
                logger.warning("JWT authentication failed: missing 'sub' claim in token")
                return None

        except Exception as e:
            logger.warning(f"JWT authentication failed: {str(e)}")
            return None


# 全域 AuthService 實例
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """獲取 AuthService 單例"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


__all__ = ["AuthService", "SimpleUser", "get_auth_service"]
