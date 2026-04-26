"""
JWT verification utility class

Provides JWT token verification and parsing features for Keycloak.
Supports using JWKS (JSON Web Key Set) to dynamically fetch public keys for token verification.
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
    """JWT verification failed exception"""
    pass


class JWKSFetchError(Exception):
    """JWKS fetch failed exception"""
    pass


class JWTUtils:
    """JWT verification utility class

    Provides complete JWT token verification features:
    - Fetch JWKS (public key set) from Keycloak
    - Verify token signature
    - Parse token payload
    - Verify token expiry time, issuer, and audience
    - Cache JWKS to avoid frequent requests
    """

    def __init__(self):
        """Initialize JWT verification utility"""
        self.config = get_keycloak_config()
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cache_time: Optional[datetime] = None

    async def fetch_jwks(self) -> Dict[str, Any]:
        """Get JWKS (JSON Web Key Set) from Keycloak

        Returns:
            JWKS dictionary containing public key information

        Raises:
            JWKSFetchError: When JWKS fetch fails
        """
        if not self.config.enabled:
            raise JWKSFetchError("Authentication is not enabled")

        # Check if cache is valid
        if self.jwks_cache is not None:
            cache_age = (datetime.now(timezone.utc) - self.jwks_cache_time).total_seconds()
            if cache_age < self.config.jwks_cache_ttl:
                logger.debug("Using cached JWKS")
                return self.jwks_cache

        # Get latest JWKS from Keycloak
        jwks_url = self.config.jwks_url
        if not jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            # Update cache
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
        """Get kid (key ID) from token and find corresponding public key from JWKS

        Args:
            token: JWT token string

        Returns:
            Public key dictionary

        Raises:
            JWKSFetchError: When unable to fetch JWKS
            JWTValidationError: When unable to find corresponding public key
        """
        try:
            # Get kid from token header
            headers = jwt.get_unverified_headers(token)
            kid = headers.get('kid')

            if not kid:
                raise JWTValidationError("Token header missing 'kid' field")

            # Get JWKS
            jwks_data = self.jwks_cache
            if not jwks_data:
                # We use synchronous method to get JWKS here
                # Should use async version in FastAPI routes
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                jwks_data = loop.run_until_complete(self.fetch_jwks())

            # Find corresponding public key from JWKS
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
        """Decode and verify JWT token

        Args:
            token: JWT token string
            verify_audience: Whether to verify audience

        Returns:
            Decoded token payload

        Raises:
            JWTValidationError: When token verification fails
        """
        if not self.config.enabled:
            # Authentication not enabled, do not verify token
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            # Get public key
            public_key = self.get_public_key(token)

            # Convert JWK to PEM format
            rsa_key = jwk.construct(public_key)
            public_key_pem = rsa_key.to_pem()

            # Validate and decode token
# Keycloak uses 'azp' (authorized party) instead of 'aud' to identify client
            # Therefore we disable audience verification and manually verify azp field
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=[self.config.jwt_algorithm],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_nbf': True,
                    'verify_iat': True,
                    'verify_aud': False,  # Keycloak uses azp instead of aud
                },
                audience=self.config.client_id if verify_audience else None,
            )

            # Manually verify azp (authorized party) field
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
        """Asynchronously decode and verify JWT token

        Args:
            token: JWT token string
            verify_audience: Whether to verify audience

        Returns:
            Decoded token payload

        Raises:
            JWTValidationError: When token verification fails
        """
        if not self.config.enabled:
            logger.warning("Authentication is disabled, skipping token validation")
            return {}

        try:
            # Ensure JWKS is fetched first
            if self.jwks_cache is None:
                await self.fetch_jwks()

            # Use synchronous method to decode (because jose library doesn't support async)
            return self.decode_token(token, verify_audience)

        except JWTValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise JWTValidationError(f"Token validation failed: {e}")

    def get_token_claims(self, token: str) -> Dict[str, Any]:
        """Get token claims (without signature verification)

        Note: This method is only for debugging, do not use in production environment

        Args:
            token: JWT token string

        Returns:
            Token claims dictionary
        """
        try:
            return jwt.get_unverified_claims(token)
        except JWTError as e:
            raise JWTValidationError(f"Failed to get token claims: {e}")

    def validate_token_expiry(self, payload: Dict[str, Any]) -> bool:
        """Verify token expiry time

        Args:
            payload: Token payload

        Returns:
            True if token is not expired, False if expired
        """
        if not self.config.enabled:
            return True

        exp = payload.get('exp')
        if exp is None:
            return False

        current_time = datetime.now(timezone.utc).timestamp()
        return exp > current_time

    def clear_jwks_cache(self):
        """Clear JWKS cache"""
        self.jwks_cache = None
        self.jwks_cache_time = None
        logger.info("JWKS cache cleared")


# Singleton instance
_jwt_utils_instance: Optional[JWTUtils] = None


def get_jwt_utils() -> JWTUtils:
    """Get JWTUtils singleton instance

    Returns:
        JWTUtils instance
    """
    global _jwt_utils_instance
    if _jwt_utils_instance is None:
        _jwt_utils_instance = JWTUtils()
    return _jwt_utils_instance


def clear_jwt_utils_cache():
    """Clear JWTUtils cache"""
    global _jwt_utils_instance
    if _jwt_utils_instance is not None:
        _jwt_utils_instance.clear_jwks_cache()
