"""Small Redis cache used by Marketplace read models."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

MARKETPLACE_CACHE_TTL_SECONDS = 300
_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _redis_client(redis_url: str) -> Redis:
    """Reuse one Redis client and connection pool for each configured URL."""
    return Redis.from_url(redis_url, decode_responses=True)


class MarketplaceCache:
    """Best-effort cache-aside wrapper.

    Redis is deliberately optional at runtime. Any Redis failure turns the
    operation into a cache miss so Marketplace filesystem reads remain usable.
    """

    def __init__(self, redis_url: str, client: Any | None = None) -> None:
        self._client = client if client is not None else _redis_client(redis_url)

    def registry_index_key(self) -> str:
        return "marketplace:registry:index"

    def package_overview_key(
        self,
        provider: str,
        package_id: str,
    ) -> str:
        return f"marketplace:package:{provider}:{package_id}:overview"

    def package_overview_pattern(self) -> str:
        return "marketplace:package:*:overview"

    def get_json(self, key: str) -> Any | None:
        try:
            payload = self._client.get(key)
        except RedisError:
            _LOGGER.debug("Marketplace Redis read failed", exc_info=True)
            return None
        if payload is None:
            return None
        try:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            return json.loads(payload)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.debug("Marketplace Redis payload is invalid", exc_info=True)
            return None

    def set_json(self, key: str, value: Any) -> None:
        try:
            self._client.set(
                key,
                json.dumps(value, separators=(",", ":"), ensure_ascii=False),
                ex=MARKETPLACE_CACHE_TTL_SECONDS,
            )
        except (RedisError, TypeError, ValueError):
            _LOGGER.debug("Marketplace Redis write failed", exc_info=True)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._client.delete(*keys)
        except RedisError:
            _LOGGER.debug("Marketplace Redis invalidation failed", exc_info=True)

    def delete_pattern(self, pattern: str) -> None:
        try:
            batch: list[str] = []
            for key in self._client.scan_iter(match=pattern, count=100):
                batch.append(key)
                if len(batch) >= 100:
                    self._client.delete(*batch)
                    batch.clear()
            if batch:
                self._client.delete(*batch)
        except RedisError:
            _LOGGER.debug("Marketplace Redis invalidation failed", exc_info=True)
