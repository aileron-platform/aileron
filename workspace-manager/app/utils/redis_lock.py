"""Redis 分散式鎖實作

用於控制自動化任務的並發執行，確保同一個工作區同時只有一個任務在執行。
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Optional

import redis


class RedisLock:
    """Redis 分散式鎖
    
    使用 Redis 的 SETNX 命令實現分散式鎖，確保在分散式環境下的原子性操作。
    """

    def __init__(self, redis_client: redis.Redis, key: str, timeout: int = 3600):
        """初始化 Redis 鎖
        
        Args:
            redis_client: Redis 客戶端實例
            key: 鎖的鍵名
            timeout: 鎖的超時時間（秒），預設 1 小時
        """
        self.redis = redis_client
        self.key = key
        self.timeout = timeout
        self.lock_value: Optional[str] = None

    def acquire(self, blocking: bool = False, block_timeout: Optional[int] = None) -> bool:
        """獲取鎖
        
        Args:
            blocking: 是否阻塞等待鎖釋放
            block_timeout: 阻塞等待的超時時間（秒），None 表示使用 self.timeout
            
        Returns:
            bool: 是否成功獲取鎖
        """
        self.lock_value = str(uuid.uuid4())

        if blocking:
            # 阻塞式獲取鎖
            end_time = time.time() + (block_timeout or self.timeout)
            while time.time() < end_time:
                if self.redis.set(self.key, self.lock_value, nx=True, ex=self.timeout):
                    return True
                time.sleep(0.1)
            return False
        else:
            # 非阻塞式獲取鎖
            result = self.redis.set(self.key, self.lock_value, nx=True, ex=self.timeout)
            return bool(result)

    def release(self) -> bool:
        """釋放鎖
        
        使用 Lua 腳本確保原子性：只有持有鎖的進程才能釋放鎖。
        
        Returns:
            bool: 是否成功釋放鎖
        """
        if not self.lock_value:
            return False

        # Lua 腳本確保原子性：檢查鎖的值是否匹配，匹配才刪除
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = self.redis.eval(lua_script, 1, self.key, self.lock_value)
        return bool(result)

    def extend(self, additional_time: int) -> bool:
        """延長鎖的過期時間
        
        Args:
            additional_time: 要延長的時間（秒）
            
        Returns:
            bool: 是否成功延長
        """
        if not self.lock_value:
            return False

        # Lua 腳本確保原子性：檢查鎖的值是否匹配，匹配才延長過期時間
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = self.redis.eval(
            lua_script, 1, self.key, self.lock_value, additional_time
        )
        return bool(result)


def _get_redis_client() -> redis.Redis:
    """獲取 Redis 客戶端實例

    集中管理 Redis 客戶端創建邏輯，避免重複代碼。

    Returns:
        Redis 客戶端實例
    """
    from app.config.settings import get_settings

    settings = get_settings()
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


@contextmanager
def workspace_lock(workspace_id: str, timeout: int = 3600, blocking: bool = False):
    """工作區鎖上下文管理器

    用於確保同一個工作區同時只有一個自動化任務在執行。

    Args:
        workspace_id: 工作區 ID
        timeout: 鎖的超時時間（秒），預設 1 小時
        blocking: 是否阻塞等待鎖釋放

    Yields:
        bool: 是否成功獲取鎖

    Example:
        ```python
        with workspace_lock(workspace_id) as acquired:
            if not acquired:
                logger.warning("無法獲取工作區鎖")
                return
            # 執行任務
            ...
        ```
    """
    redis_client = _get_redis_client()
    lock_key = f"automation:lock:workspace:{workspace_id}"
    lock = RedisLock(redis_client, lock_key, timeout)

    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
        redis_client.close()


def get_workspace_lock_info(workspace_id: str) -> Optional[dict]:
    """獲取工作區鎖的資訊

    Args:
        workspace_id: 工作區 ID

    Returns:
        dict 或 None: 鎖的資訊（是否存在、剩餘時間等），如果鎖不存在則返回 None
    """
    redis_client = _get_redis_client()
    lock_key = f"automation:lock:workspace:{workspace_id}"

    try:
        lock_value = redis_client.get(lock_key)
        if not lock_value:
            return None

        ttl = redis_client.ttl(lock_key)

        return {
            "locked": True,
            "lock_value": lock_value,
            "ttl": ttl,
            "workspace_id": workspace_id,
        }
    finally:
        redis_client.close()

