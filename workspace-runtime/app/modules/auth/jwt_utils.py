"""
JWT validation utility class

Provides Keycloak JWT token validation and parsing functionality.
Supports using JWKS (JSON Web Key Set) to dynamically fetch public keys for token validation.
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
    """JWT validation failure exception"""
    pass


class JWKSFetchError(Exception):
    """JWKS fetch failure exception"""
    pass


class JWTUtils:
    """JWT validation utility class"""

    def __init__(self):
        self.config = get_keycloak_config()
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cache_time: Optional[datetime] = None

    async def fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Keycloak"""
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
        """Find corresponding public key from token header's kid

        Note: This is a synchronous method. Before calling, ensure JWKS cache is loaded (call decode_token_async).
        If cache is empty, an error will be thrown to avoid deadlock when using run_until_complete in running event loop.
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
        """Decode and validate JWT token"""
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
        """Asynchronously decode and validate JWT token"""
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
        """Clear JWKS cache"""
        self.jwks_cache = None
        self.jwks_cache_time = None
        logger.info("JWKS cache cleared")


_jwt_utils_instance: Optional[JWTUtils] = None


def get_jwt_utils() -> JWTUtils:
    """Get JWTUtils singleton instance"""
    global _jwt_utils_instance
    if _jwt_utils_instance is None:
        _jwt_utils_instance = JWTUtils()
    return _jwt_utils_instance


def clear_jwt_utils_cache():
    """Clear JWTUtils cache"""
    global _jwt_utils_instance
    if _jwt_utils_instance is not None:
        _jwt_utils_instance.clear_jwks_cache()
