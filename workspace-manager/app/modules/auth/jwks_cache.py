"""
JWKS cache management

Provides cache management functionality for Keycloak JWKS (JSON Web Key Set).
Automatically updates public keys periodically to avoid requesting Keycloak on every token verification.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class JKWSCache:
    """JWKS cache management class

    Provides the following features:
    - Automatic JWKS data caching
    - Periodic auto-refresh (configurable TTL)
    - Asynchronous refresh to avoid blocking requests
    - Failure retry mechanism
    - Cache hit rate statistics
    """

    def __init__(self):
        """Initialize JWKS cache"""
        self.config = get_keycloak_config()
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._refresh_lock = asyncio.Lock()
        self._is_refreshing = False

        # Statistics information
        self._cache_hits = 0
        self._cache_misses = 0
        self._refresh_errors = 0

    @property
    def is_enabled(self) -> bool:
        """Check if cache is active"""
        return self.config.enabled

    @property
    def cache_ttl(self) -> int:
        """Get cache TTL (seconds)"""
        return self.config.jwks_cache_ttl

    @property
    def jwks_url(self) -> Optional[str]:
        """Get JWKS URL"""
        return self.config.jwks_url

    def is_cache_valid(self) -> bool:
        """Check if cache is valid

        Returns:
            True if cache exists and is not expired
        """
        if self._cache is None or self._cache_time is None:
            return False

        cache_age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return cache_age < self.cache_ttl

    def get_cache_age_seconds(self) -> Optional[float]:
        """Get cache age (seconds)

        Returns:
            Cache age, or None if cache does not exist
        """
        if self._cache_time is None:
            return None
        return (datetime.now(timezone.utc) - self._cache_time).total_seconds()

    async def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get JWKS data (using cache)

        Args:
            force_refresh: Whether to force refresh cache

        Returns:
            JWKS data dictionary

        Raises:
            JWKSFetchError: When unable to get JWKS
        """
        if not self.is_enabled:
            raise JWKSFetchError("Authentication is not enabled")

        if not force_refresh and self.is_cache_valid():
            self._cache_hits += 1
            logger.debug(f"Using cached JWKS (age: {self.get_cache_age_seconds():.1f}s)")
            return self._cache

        # Need to refresh cache
        return await self._refresh_jwks(force_refresh=force_refresh)

    async def _refresh_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Internal method: Refresh JWKS cache

        Returns:
            Latest JWKS data

        Raises:
            JWKSFetchError: When refresh fails
        """
        # Use lock to avoid concurrent refresh
        async with self._refresh_lock:
            # Check cache again, maybe other task already refreshed
            if not force_refresh and not self._is_refreshing and self.is_cache_valid():
                return self._cache

            self._is_refreshing = True
            try:
                jwks_data = await self._fetch_jwks_from_server()

                # Update cache
                self._cache = jwks_data
                self._cache_time = datetime.now(timezone.utc)
                self._cache_misses += 1

                logger.info(
                    f"JWKS cache refreshed successfully "
                    f"(age: {self.get_cache_age_seconds():.1f}s, "
                    f"keys: {len(jwks_data.get('keys', []))})"
                )

                return jwks_data

            finally:
                self._is_refreshing = False

    async def _fetch_jwks_from_server(self) -> Dict[str, Any]:
        """Get JWKS from Keycloak server

        Returns:
            JWKS data dictionary

        Raises:
            JWKSFetchError: When request fails
        """
        if not self.jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            # Validate JWKS format
            if 'keys' not in jwks_data:
                raise JWKSFetchError("Invalid JWKS format: missing 'keys' field")

            self._refresh_errors = 0  # Reset error counter
            return jwks_data

        except httpx.HTTPError as e:
            self._refresh_errors += 1
            logger.error(f"Failed to fetch JWKS (error #{self._refresh_errors}): {e}")

            # Return stale cache if available on error
            if self._cache is not None:
                logger.warning("Using stale JWKS cache due to fetch error")
                return self._cache

            raise JWKSFetchError(f"Failed to fetch JWKS from {self.jwks_url}: {e}")

        except Exception as e:
            self._refresh_errors += 1
            logger.error(f"Unexpected error fetching JWKS: {e}")
            if self._cache is not None:
                logger.warning("Using stale JWKS cache due to unexpected fetch error")
                return self._cache

            raise JWKSFetchError(f"Unexpected error: {e}")

    async def start_background_refresh(self, interval_seconds: Optional[int] = None):
        """Start background auto-refresh task

        Args:
            interval_seconds: Refresh interval (seconds), default is 80% of cache_ttl
        """
        if interval_seconds is None:
            interval_seconds = int(self.cache_ttl * 0.8)

        logger.info(f"Starting background JWKS refresh (interval: {interval_seconds}s)")

        async def refresh_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    await self.get_jwks(force_refresh=True)
                except Exception as e:
                    logger.error(f"Background JWKS refresh failed: {e}")

        # Create background task
        asyncio.create_task(refresh_loop())

    def clear(self):
        """Clear cache"""
        self._cache = None
        self._cache_time = None
        logger.info("JWKS cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Statistics information dictionary
        """
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'refresh_errors': self._refresh_errors,
            'is_cached': self._cache is not None,
            'cache_age_seconds': self.get_cache_age_seconds(),
            'is_valid': self.is_cache_valid(),
        }

    def get_key_by_kid(self, kid: str) -> Optional[Dict[str, Any]]:
        """Get public key by kid (Key ID)

        Args:
            kid: Key ID

        Returns:
            Public key dictionary, or None if not found
        """
        if self._cache is None:
            return None

        for key in self._cache.get('keys', []):
            if key.get('kid') == kid:
                return key

        return None


class JWKSFetchError(Exception):
    """JWKS fetch failed exception"""
    pass


# Singleton instance
_jwks_cache_instance: Optional[JKWSCache] = None


def get_jwks_cache() -> JKWSCache:
    """Get JWKS cache singleton instance

    Returns:
        JWKS cache instance
    """
    global _jwks_cache_instance
    if _jwks_cache_instance is None:
        _jwks_cache_instance = JKWSCache()
    return _jw_cache_instance


def clear_jwks_cache():
    """Clear JWKS cache"""
    global _jwks_cache_instance
    if _jwks_cache_instance is not None:
        _jwks_cache_instance.clear()
