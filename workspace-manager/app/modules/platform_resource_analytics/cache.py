"""Best-effort Redis cache for platform resource read models."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=0.25,
        socket_timeout=0.5,
    )


class PlatformResourceCache:
    """Keep Redis optional while bounding duplicate rebuilds."""

    def __init__(self, redis_url: str, client: Any | None = None) -> None:
        self.client = client if client is not None else _redis_client(redis_url)

    @staticmethod
    def key(*, view: str, resource_type: str, range_value: str, time_zone: str) -> str:
        return f"platform-resources:v1:{view}:{resource_type}:{range_value}:{time_zone}"

    def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            payload = self.client.get(key)
            if payload is None:
                return None
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            if not isinstance(payload, (str, bytes, bytearray)):
                return None
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else None
        except (RedisError, UnicodeDecodeError, TypeError, json.JSONDecodeError):
            logger.debug("Platform resource Redis read failed", exc_info=True)
            return None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            self.client.set(
                key,
                json.dumps(value, separators=(",", ":"), ensure_ascii=False),
                ex=ttl_seconds,
            )
        except (RedisError, TypeError, ValueError):
            logger.debug("Platform resource Redis write failed", exc_info=True)

    def acquire_rebuild_lock(self, key: str, ttl_seconds: int = 10) -> str | None:
        token = str(uuid4())
        try:
            acquired = self.client.set(
                f"{key}:rebuild-lock",
                token,
                nx=True,
                ex=ttl_seconds,
            )
            return token if acquired else None
        except RedisError:
            logger.debug("Platform resource Redis lock failed", exc_info=True)
            return None

    def release_rebuild_lock(self, key: str, token: str | None) -> None:
        if token is None:
            return
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
          return redis.call('del', KEYS[1])
        end
        return 0
        """
        try:
            self.client.eval(script, 1, f"{key}:rebuild-lock", token)
        except RedisError:
            logger.debug("Platform resource Redis unlock failed", exc_info=True)

    def invalidate(self, resource_type: str) -> None:
        pattern = f"platform-resources:v1:*:{resource_type}:*"
        try:
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                self.client.delete(*keys)
        except RedisError:
            logger.debug("Platform resource Redis invalidation failed", exc_info=True)
