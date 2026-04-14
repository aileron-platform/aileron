"""
JWKS 快取管理

提供 Keycloak JWKS (JSON Web Key Set) 的快取管理功能。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class JKWSCache:
    """JWKS 快取管理類"""

    def __init__(self):
        self.config = get_keycloak_config()
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._refresh_lock = asyncio.Lock()
        self._is_refreshing = False
        self._cache_hits = 0
        self._cache_misses = 0
        self._refresh_errors = 0

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled

    @property
    def cache_ttl(self) -> int:
        return self.config.jwks_cache_ttl

    @property
    def jwks_url(self) -> Optional[str]:
        return self.config.jwks_url

    def is_cache_valid(self) -> bool:
        if self._cache is None or self._cache_time is None:
            return False
        cache_age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return cache_age < self.cache_ttl

    async def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not self.is_enabled:
            raise JWKSFetchError("Authentication is not enabled")

        if not force_refresh and self.is_cache_valid():
            self._cache_hits += 1
            return self._cache

        return await self._refresh_jwks(force_refresh=force_refresh)

    async def _refresh_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        async with self._refresh_lock:
            if not force_refresh and not self._is_refreshing and self.is_cache_valid():
                return self._cache

            self._is_refreshing = True
            try:
                jwks_data = await self._fetch_jwks_from_server()
                self._cache = jwks_data
                self._cache_time = datetime.now(timezone.utc)
                self._cache_misses += 1
                logger.info(f"JWKS cache refreshed (keys: {len(jwks_data.get('keys', []))})")
                return jwks_data
            finally:
                self._is_refreshing = False

    async def _fetch_jwks_from_server(self) -> Dict[str, Any]:
        if not self.jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            if 'keys' not in jwks_data:
                raise JWKSFetchError("Invalid JWKS format: missing 'keys' field")

            self._refresh_errors = 0
            return jwks_data

        except httpx.HTTPError as e:
            self._refresh_errors += 1
            if self._cache is not None:
                logger.warning("Using stale JWKS cache due to fetch error")
                return self._cache
            raise JWKSFetchError(f"Failed to fetch JWKS from {self.jwks_url}: {e}")

        except Exception as e:
            self._refresh_errors += 1
            if self._cache is not None:
                return self._cache
            raise JWKSFetchError(f"Unexpected error: {e}")

    def clear(self):
        self._cache = None
        self._cache_time = None
        logger.info("JWKS cache cleared")

    def get_key_by_kid(self, kid: str) -> Optional[Dict[str, Any]]:
        if self._cache is None:
            return None
        for key in self._cache.get('keys', []):
            if key.get('kid') == kid:
                return key
        return None


class JWKSFetchError(Exception):
    """JWKS 獲取失敗異常"""
    pass


_jwks_cache_instance: Optional[JKWSCache] = None


def get_jwks_cache() -> JKWSCache:
    global _jwks_cache_instance
    if _jwks_cache_instance is None:
        _jwks_cache_instance = JKWSCache()
    return _jwks_cache_instance


def clear_jwks_cache():
    global _jwks_cache_instance
    if _jwks_cache_instance is not None:
        _jwks_cache_instance.clear()
