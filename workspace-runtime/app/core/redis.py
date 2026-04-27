"""Redis connection manager"""

import json
import logging
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    import aioredis  # type: ignore

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis connection and operation manager"""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None  # type: ignore
        self._settings = get_settings()

    async def get_redis(self) -> aioredis.Redis:  # type: ignore
        """Get Redis connection"""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self._settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                await self._redis.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        try:
            redis = await self.get_redis()
            value = await redis.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set Redis value"""
        try:
            redis = await self.get_redis()
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if expire:
                await redis.setex(key, expire, value)
            else:
                await redis.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete Redis key"""
        try:
            redis = await self.get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            redis = await self.get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check key existence {key}: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global Redis Manager instance
redis_manager = RedisManager()

__all__ = ["RedisManager", "redis_manager"]

