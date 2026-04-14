"""
JWKS 快取管理

提供 Keycloak JWKS (JSON Web Key Set) 的快取管理功能。
自動定期更新公鑰，避免每次驗證 token 都請求 Keycloak。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.modules.auth.config import get_keycloak_config

logger = logging.getLogger(__name__)


class JKWSCache:
    """JWKS 快取管理類

    提供以下功能：
    - 自動快取 JWKS 數據
    - 定期自動刷新（可配置 TTL）
    - 異步刷新避免阻塞請求
    - 失敗重試機制
    - 快取命中率統計
    """

    def __init__(self):
        """初始化 JWKS 快取"""
        self.config = get_keycloak_config()
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._refresh_lock = asyncio.Lock()
        self._is_refreshing = False

        # 統計信息
        self._cache_hits = 0
        self._cache_misses = 0
        self._refresh_errors = 0

    @property
    def is_enabled(self) -> bool:
        """檢查快取是否啟用"""
        return self.config.enabled

    @property
    def cache_ttl(self) -> int:
        """獲取快取 TTL（秒）"""
        return self.config.jwks_cache_ttl

    @property
    def jwks_url(self) -> Optional[str]:
        """獲取 JWKS URL"""
        return self.config.jwks_url

    def is_cache_valid(self) -> bool:
        """檢查快取是否有效

        Returns:
            True 如果快取存在且未過期
        """
        if self._cache is None or self._cache_time is None:
            return False

        cache_age = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return cache_age < self.cache_ttl

    def get_cache_age_seconds(self) -> Optional[float]:
        """獲取快取年齡（秒）

        Returns:
            快存的年齡，如果快取不存在則返回 None
        """
        if self._cache_time is None:
            return None
        return (datetime.now(timezone.utc) - self._cache_time).total_seconds()

    async def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """獲取 JWKS 數據（使用快取）

        Args:
            force_refresh: 是否強制刷新快取

        Returns:
            JWKS 數據字典

        Raises:
            JWKSFetchError: 當無法獲取 JWKS 時
        """
        if not self.is_enabled:
            raise JWKSFetchError("Authentication is not enabled")

        if not force_refresh and self.is_cache_valid():
            self._cache_hits += 1
            logger.debug(f"Using cached JWKS (age: {self.get_cache_age_seconds():.1f}s)")
            return self._cache

        # 需要刷新快取
        return await self._refresh_jwks(force_refresh=force_refresh)

    async def _refresh_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """內部方法：刷新 JWKS 快取

        Returns:
            最新的 JWKS 數據

        Raises:
            JWKSFetchError: 當刷新失敗時
        """
        # 使用鎖避免並發刷新
        async with self._refresh_lock:
            # 再次檢查快取，可能其他任務已經刷新了
            if not force_refresh and not self._is_refreshing and self.is_cache_valid():
                return self._cache

            self._is_refreshing = True
            try:
                jwks_data = await self._fetch_jwks_from_server()

                # 更新快取
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
        """從 Keycloak 服務器獲取 JWKS

        Returns:
            JWKS 數據字典

        Raises:
            JWKSFetchError: 當請求失敗時
        """
        if not self.jwks_url:
            raise JWKSFetchError("JWKS URL not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                jwks_data = response.json()

            # 驗證 JWKS 格式
            if 'keys' not in jwks_data:
                raise JWKSFetchError("Invalid JWKS format: missing 'keys' field")

            self._refresh_errors = 0  # 重置錯誤計數
            return jwks_data

        except httpx.HTTPError as e:
            self._refresh_errors += 1
            logger.error(f"Failed to fetch JWKS (error #{self._refresh_errors}): {e}")

            # 如果有舊的快取，在錯誤情況下返回舊快取
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
        """啟動後台自動刷新任務

        Args:
            interval_seconds: 刷新間隔（秒），預設為 cache_ttl 的 80%
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

        # 創建後台任務
        asyncio.create_task(refresh_loop())

    def clear(self):
        """清除快取"""
        self._cache = None
        self._cache_time = None
        logger.info("JWKS cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計信息

        Returns:
            統計信息字典
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
        """根據 kid (Key ID) 獲取公鑰

        Args:
            kid: Key ID

        Returns:
            公鑰字典，如果找不到則返回 None
        """
        if self._cache is None:
            return None

        for key in self._cache.get('keys', []):
            if key.get('kid') == kid:
                return key

        return None


class JWKSFetchError(Exception):
    """JWKS 獲取失敗異常"""
    pass


# 單例實例
_jwks_cache_instance: Optional[JKWSCache] = None


def get_jwks_cache() -> JKWSCache:
    """獲取 JKWSCache 單例實例

    Returns:
        JKWSCache 實例
    """
    global _jwks_cache_instance
    if _jwks_cache_instance is None:
        _jwks_cache_instance = JKWSCache()
    return _jwks_cache_instance


def clear_jwks_cache():
    """清除 JWKS 快取"""
    global _jwks_cache_instance
    if _jwks_cache_instance is not None:
        _jwks_cache_instance.clear()
