"""Redis 連接管理器"""

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
    """Redis 連接和操作管理器"""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None  # type: ignore
        self._settings = get_settings()

    async def get_redis(self) -> aioredis.Redis:  # type: ignore
        """取得 Redis 連接"""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self._settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # 測試連接
                await self._redis.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """從 Redis 取得值"""
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
        """設定 Redis 值"""
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
        """刪除 Redis 鍵"""
        try:
            redis = await self.get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """檢查鍵是否存在"""
        try:
            redis = await self.get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check key existence {key}: {e}")
            return False

    async def close(self) -> None:
        """關閉 Redis 連接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 全域 Redis Manager 實例
redis_manager = RedisManager()

__all__ = ["RedisManager", "redis_manager"]

