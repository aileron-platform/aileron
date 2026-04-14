"""Redis 連接管理器"""

import json
import logging
from typing import Any, Optional
import redis.asyncio as redis
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis 連接和操作管理器"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._settings = get_settings()

    async def get_redis(self) -> redis.Redis:
        """取得 Redis 連接"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self._settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # 測試連接
                await self._redis.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """設定 key-value，支援過期時間"""
        try:
            redis_client = await self.get_redis()
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if expire:
                return await redis_client.setex(key, expire, value)
            else:
                return await redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """取得 value"""
        try:
            redis_client = await self.get_redis()
            value = await redis_client.get(key)
            if value is None:
                return None

            # 嘗試解析 JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """刪除 key"""
        try:
            redis_client = await self.get_redis()
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """檢查 key 是否存在"""
        try:
            redis_client = await self.get_redis()
            return bool(await redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    async def keys(self, pattern: str) -> list[str]:
        """取得符合模式的所有 key"""
        try:
            redis_client = await self.get_redis()
            return await redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []

    async def delete_pattern(self, pattern: str) -> int:
        """刪除符合模式的所有 key"""
        try:
            redis_client = await self.get_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern error: {e}")
            return 0

    async def close(self):
        """關閉 Redis 連接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 全域 Redis 管理器實例
redis_manager = RedisManager()


async def get_redis() -> redis.Redis:
    """取得 Redis 連接（便利函數）"""
    return await redis_manager.get_redis()


__all__ = ["RedisManager", "redis_manager", "get_redis"]