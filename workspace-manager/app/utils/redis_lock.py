"""Redis distributed lock implementation

Used to control automation task concurrent execution, ensuring only one task runs at a time for the same workspace.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Optional

import redis


class RedisLock:
    """Redis distributed lock

    Use Redis SETNX command to implement distributed lock, ensuring atomic operations in distributed environment.
    """

    def __init__(self, redis_client: redis.Redis, key: str, timeout: int = 3600):
        """Initialize Redis lock

        Args:
            redis_client: Redis client instance
            key: Lock key name
            timeout: Lock timeout (seconds), default 1 hour
        """
        self.redis = redis_client
        self.key = key
        self.timeout = timeout
        self.lock_value: Optional[str] = None

    def acquire(self, blocking: bool = False, block_timeout: Optional[int] = None) -> bool:
        """Acquire lock

        Args:
            blocking: Whether to block and wait for lock release
            block_timeout: Block wait timeout (seconds), None means use self.timeout

        Returns:
            bool: Whether lock was successfully acquired
        """
        self.lock_value = str(uuid.uuid4())

        if blocking:
            # Blocking lock acquisition
            end_time = time.time() + (block_timeout or self.timeout)
            while time.time() < end_time:
                if self.redis.set(self.key, self.lock_value, nx=True, ex=self.timeout):
                    return True
                time.sleep(0.1)
            return False
        else:
            # Non-blocking lock acquisition
            result = self.redis.set(self.key, self.lock_value, nx=True, ex=self.timeout)
            return bool(result)

    def release(self) -> bool:
        """Release lock

        Use Lua script to ensure atomicity: only the process holding the lock can release it.

        Returns:
            bool: Whether lock was successfully released
        """
        if not self.lock_value:
            return False

        # Lua script ensures atomicity: check if lock value matches, only delete if matches
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
        """Extend lock expiration time

        Args:
            additional_time: Time to extend (seconds)

        Returns:
            bool: Whether extension was successful
        """
        if not self.lock_value:
            return False

        # Lua script ensures atomicity: check if lock value matches, only extend expiry if it matches
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
    """Get Redis client instance

    Centralize Redis client creation logic to avoid code duplication.

    Returns:
        Redis client instance
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
    """Workspace lock context manager

    Used to ensure only one automation task runs at a time for the same workspace.

    Args:
        workspace_id: Workspace ID
        timeout: Lock timeout (seconds), default 1 hour
        blocking: Whether to block and wait for lock release

    Yields:
        bool: Whether lock was successfully acquired

    Example:
        ```python
        with workspace_lock(workspace_id) as acquired:
            if not acquired:
                logger.warning("Cannot acquire workspace lock")
                return
            # Execute task
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
    """Get workspace lock information

    Args:
        workspace_id: Workspace ID

    Returns:
        dict or None: Lock information (existence, remaining time, etc.), None if lock doesn't exist
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

