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
    """JWT 驗證工具類"""

    def __init__(self):
        self.config = get_keycloak_config()
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cache_time: Optional[datetime] = None

    async def fetch_jwks(self) -> Dict[str, Any]:
        """從 Keycloak 獲取 JWKS"""
        if not self.config.enabled:
            raise JWKSFetchError("Authentication is not enabled")

        if self.jwks_cache is not None:
            cache_age = (datetime.now(timezone.utc) - self.jwks_cache_time).total_seconds()
            if cache_age < self.config.jwks_cache_ttl:
                return self.jwks_cache

        jwks_url = self.config.jwks_url
        if not jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

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
        """從 token header 的 kid 找到對應公鑰

        注意：此方法為同步方法，呼叫前必須確保 JWKS 快取已載入（呼叫 decode_token_async）。
        若快取為空會拋出錯誤，避免在執行中的事件迴圈內使用 run_until_complete 造成死鎖。
        """
        try:
            headers = jwt.get_unverified_headers(token)
            kid = headers.get('kid')

            if not kid:
                raise JWTValidationError("Token header missing 'kid' field")

            jwks_data = self.jwks_cache
            if not jwks_data:
                raise JWTValidationError(
                    "JWKS cache is empty. Use decode_token_async() to ensure the cache is loaded "
                    "before calling decode_token()."
                )

            for key in jwks_data.get('keys', []):
                if key.get('kid') == kid:
                    return key

            raise JWTValidationError(f"Public key not found for kid: {kid}")

        except JWTError as e:
            raise JWTValidationError(f"Invalid token header: {e}")

    def decode_token(self, token: str, verify_audience: bool = True) -> Dict[str, Any]:
        """解碼並驗證 JWT token"""
        if not self.config.enabled:
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            public_key = self.get_public_key(token)
            rsa_key = jwk.construct(public_key)
            public_key_pem = rsa_key.to_pem()

            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=[self.config.jwt_algorithm],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_nbf': True,
                    'verify_iat': True,
                    'verify_aud': False,
                },
                audience=self.config.client_id if verify_audience else None,
            )

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

    async def decode_token_async(self, token: str, verify_audience: bool = True) -> Dict[str, Any]:
        """異步解碼並驗證 JWT token"""
        if not self.config.enabled:
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            if self.jwks_cache is None:
                await self.fetch_jwks()
            return self.decode_token(token, verify_audience)
        except JWTValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise JWTValidationError(f"Token validation failed: {e}")

    def clear_jwks_cache(self):
        """清除 JWKS 快取"""
        self.jwks_cache = None
        self.jwks_cache_time = None
        logger.info("JWKS cache cleared")


_jwt_utils_instance: Optional[JWTUtils] = None


def get_jwt_utils() -> JWTUtils:
    """獲取 JWTUtils 單例實例"""
    global _jwt_utils_instance
    if _jwt_utils_instance is None:
        _jwt_utils_instance = JWTUtils()
    return _jwt_utils_instance


def clear_jwt_utils_cache():
    """清除 JWTUtils 快取"""
    global _jwt_utils_instance
    if _jwt_utils_instance is not None:
        _jwt_utils_instance.clear_jwks_cache()
