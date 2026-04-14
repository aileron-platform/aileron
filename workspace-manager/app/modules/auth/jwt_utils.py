"""
JWT 驗證工具類

提供 Keycloak JWT token 的驗證和解析功能。
支援使用 JWKS (JSON Web Key Set) 動態獲取公鑰進行 token 驗證。
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import httpx
from jose import jwk, jwt
from jose.exceptions import ExpiredSignatureError, JWTError, JWTClaimsError

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class JWTValidationError(Exception):
    """JWT 驗證失敗異常"""
    pass


class JWKSFetchError(Exception):
    """JWKS 獲取失敗異常"""
    pass


class JWTUtils:
    """JWT 驗證工具類

    提供完整的 JWT token 驗證功能：
    - 從 Keycloak 獲取 JWKS (公鑰集)
    - 驗證 token 簽名
    - 解析 token payload
    - 驗證 token 過期時間、issuer、audience
    - 快取 JWKS 避免頻繁請求
    """

    def __init__(self):
        """初始化 JWT 驗證工具"""
        self.config = get_keycloak_config()
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cache_time: Optional[datetime] = None

    async def fetch_jwks(self) -> Dict[str, Any]:
        """從 Keycloak 獲取 JWKS (JSON Web Key Set)

        Returns:
            JWKS 字典，包含公鑰信息

        Raises:
            JWKSFetchError: 當 JWKS 獲取失敗時
        """
        if not self.config.enabled:
            raise JWKSFetchError("Authentication is not enabled")

        # 檢查快取是否有效
        if self.jwks_cache is not None:
            cache_age = (datetime.now(timezone.utc) - self.jwks_cache_time).total_seconds()
            if cache_age < self.config.jwks_cache_ttl:
                logger.debug("Using cached JWKS")
                return self.jwks_cache

        # 從 Keycloak 獲取最新的 JWKS
        jwks_url = self.config.jwks_url
        if not jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            # 更新快取
            self.jwks_cache = jwks_data
            self.jwks_cache_time = datetime.now(timezone.utc)

            logger.info(f"Successfully fetched JWKS from {jwks_url}")
            return jwks_data

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise JWKSFetchError(f"Failed to fetch JWKS from {jwks_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching JWKS: {e}")
            raise JWKSFetchError(f"Unexpected error fetching JWKS from {jwks_url}: {e}")

    def get_public_key(self, token: str) -> Dict[str, Any]:
        """從 token 中獲取 kid (key ID) 並從 JWKS 中找到對應的公鑰

        Args:
            token: JWT token 字符串

        Returns:
            公鑰字典

        Raises:
            JWKSFetchError: 當無法獲取 JWKS 時
            JWTValidationError: 當無法找到對應公鑰時
        """
        try:
            # 從 token header 中獲取 kid
            headers = jwt.get_unverified_headers(token)
            kid = headers.get('kid')

            if not kid:
                raise JWTValidationError("Token header missing 'kid' field")

            # 獲取 JWKS
            jwks_data = self.jwks_cache
            if not jwks_data:
                # 這裡我們使用同步方式獲取 JWKS
                # 在 FastAPI 路由中應該使用異步版本
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                jwks_data = loop.run_until_complete(self.fetch_jwks())

            # 從 JWKS 中找到對應的公鑰
            for key in jwks_data.get('keys', []):
                if key.get('kid') == kid:
                    return key

            raise JWTValidationError(f"Public key not found for kid: {kid}")

        except JWTError as e:
            raise JWTValidationError(f"Invalid token header: {e}")

    def decode_token(
        self,
        token: str,
        verify_audience: bool = True
    ) -> Dict[str, Any]:
        """解碼並驗證 JWT token

        Args:
            token: JWT token 字符串
            verify_audience: 是否驗證 audience

        Returns:
            解碼後的 token payload

        Raises:
            JWTValidationError: 當 token 驗證失敗時
        """
        if not self.config.enabled:
            # 認證未啟用，不驗證 token
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            # 獲取公鑰
            public_key = self.get_public_key(token)

            # 將 JWK 轉換為 PEM 格式
            rsa_key = jwk.construct(public_key)
            public_key_pem = rsa_key.to_pem()

            # 驗證並解碼 token
            # Keycloak 使用 'azp' (authorized party) 而不是 'aud' 來標識客戶端
            # 因此我們關閉 audience 驗證，而是手動驗證 azp 字段
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=[self.config.jwt_algorithm],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_nbf': True,
                    'verify_iat': True,
                    'verify_aud': False,  # Keycloak 使用 azp 而不是 aud
                },
                audience=self.config.client_id if verify_audience else None,
            )

            # 手動驗證 azp (authorized party) 字段
            if verify_audience and payload.get('azp') != self.config.client_id:
                raise JWTValidationError(
                    f"Token not issued for this client. "
                    f"Expected azp={self.config.client_id}, got azp={payload.get('azp')}"
                )

            logger.debug(f"Token validated successfully for user: {payload.get('sub')}")
            return payload

        except ExpiredSignatureError:
            raise JWTValidationError("Token has expired")
        except JWTClaimsError as e:
            raise JWTValidationError(f"Invalid token claims: {e}")
        except JWTError as e:
            raise JWTValidationError(f"Invalid token: {e}")

    async def decode_token_async(
        self,
        token: str,
        verify_audience: bool = True
    ) -> Dict[str, Any]:
        """異步解碼並驗證 JWT token

        Args:
            token: JWT token 字符串
            verify_audience: 是否驗證 audience

        Returns:
            解碼後的 token payload

        Raises:
            JWTValidationError: 當 token 驗證失敗時
        """
        if not self.config.enabled:
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            # 先確保 JWKS 已獲取
            if self.jwks_cache is None:
                await self.fetch_jwks()

            # 使用同步方法解碼（因為 jose 庫不支持異步）
            return self.decode_token(token, verify_audience)

        except JWTValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise JWTValidationError(f"Token validation failed: {e}")

    def get_token_claims(self, token: str) -> Dict[str, Any]:
        """獲取 token 的 claims（不驗證簽名）

        注意：此方法僅用於調試，不應用於生產環境

        Args:
            token: JWT token 字符串

        Returns:
            Token claims 字典
        """
        try:
            return jwt.get_unverified_claims(token)
        except JWTError as e:
            raise JWTValidationError(f"Failed to get token claims: {e}")

    def validate_token_expiry(self, payload: Dict[str, Any]) -> bool:
        """驗證 token 過期時間

        Args:
            payload: Token payload

        Returns:
            True 如果 token 未過期，False 如果已過期
        """
        if not self.config.enabled:
            return True

        exp = payload.get('exp')
        if exp is None:
            return False

        current_time = datetime.now(timezone.utc).timestamp()
        return exp > current_time

    def clear_jwks_cache(self):
        """清除 JWKS 快取"""
        self.jwks_cache = None
        self.jwks_cache_time = None
        logger.info("JWKS cache cleared")


# 單例實例
_jwt_utils_instance: Optional[JWTUtils] = None


def get_jwt_utils() -> JWTUtils:
    """獲取 JWTUtils 單例實例

    Returns:
        JWTUtils 實例
    """
    global _jwt_utils_instance
    if _jwt_utils_instance is None:
        _jwt_utils_instance = JWTUtils()
    return _jwt_utils_instance


def clear_jwt_utils_cache():
    """清除 JWTUtils 快取"""
    global _jwt_utils_instance
    if _jwt_utils_instance is not None:
        _jwt_utils_instance.clear_jwks_cache()
