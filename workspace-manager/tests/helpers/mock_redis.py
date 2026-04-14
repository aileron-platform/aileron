"""Mock Redis 服務 - 用於測試環境"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MockRedisManager:
    """Mock Redis 管理器 - 用於測試環境"""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._ttl: Dict[str, datetime] = {}
        self._connected = False

    async def get_redis(self):
        """Mock Redis 連接"""
        if not self._connected:
            self._connected = True
            logger.info("Mock Redis connection established successfully")
        return self

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """設定 key-value，支援過期時間"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            self._data[key] = value

            if expire:
                self._ttl[key] = datetime.now() + timedelta(seconds=expire)

            return True
        except Exception as e:
            logger.error(f"Mock Redis set error: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """取得 value"""
        try:
            # 檢查是否過期
            if key in self._ttl and datetime.now() > self._ttl[key]:
                await self.delete(key)
                return None

            value = self._data.get(key)
            if value is None:
                return None

            # 嘗試解析 JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Mock Redis get error: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """刪除 key"""
        try:
            deleted = key in self._data
            self._data.pop(key, None)
            self._ttl.pop(key, None)
            return deleted
        except Exception as e:
            logger.error(f"Mock Redis delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """檢查 key 是否存在"""
        try:
            # 檢查是否過期
            if key in self._ttl and datetime.now() > self._ttl[key]:
                await self.delete(key)
                return False
            return key in self._data
        except Exception as e:
            logger.error(f"Mock Redis exists error: {e}")
            return False

    async def keys(self, pattern: str) -> list[str]:
        """取得符合模式的所有 key"""
        try:
            import fnmatch
            matching_keys = []
            for key in list(self._data.keys()):
                if fnmatch.fnmatch(key, pattern):
                    # 檢查是否過期
                    if key in self._ttl and datetime.now() > self._ttl[key]:
                        continue
                    matching_keys.append(key)
            return matching_keys
        except Exception as e:
            logger.error(f"Mock Redis keys error: {e}")
            return []

    async def delete_pattern(self, pattern: str) -> int:
        """刪除符合模式的所有 key"""
        try:
            keys = await self.keys(pattern)
            count = 0
            for key in keys:
                if await self.delete(key):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Mock Redis delete_pattern error: {e}")
            return 0

    async def close(self):
        """關閉 Mock Redis 連接"""
        self._connected = False
        self._data.clear()
        self._ttl.clear()

    async def ping(self) -> str:
        """Mock ping"""
        return "PONG"


# 全域 Mock Redis 管理器實例
mock_redis_manager = MockRedisManager()


def get_mock_redis():
    """取得 Mock Redis 連接（便利函數）"""
    return mock_redis_manager


__all__ = ["MockRedisManager", "mock_redis_manager", "get_mock_redis"]