"""Git operation caching layer"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any, Optional

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class GitCache:
    """Git operation caching layer

    Provides Redis caching to reduce duplicate Git operations
    """

    def __init__(self, redis_client: Optional[Redis] = None, ttl: int = 300, enabled: bool = True):
        """Initialize cache

        Args:
            redis_client: Redis client instance
            ttl: Default cache TTL in seconds, default 5 minutes
            enabled: Whether to enable caching
        """
        self.redis = redis_client
        self.ttl = ttl
        self.enabled = enabled and redis_client is not None
        self.prefix = "git:cache:"
        
        if not self.enabled:
            logger.warning("GitCache is disabled (no Redis client provided)")

    def _make_key(self, workspace_id: str, operation: str, **params) -> str:
        """Generate cache key

        Args:
            workspace_id: Workspace ID
            operation: Operation name (e.g., 'changes', 'commits', 'status')
            **params: Additional parameters (will be serialized and hashed)

        Returns:
            Cache key string
        """
        # Sort and serialize parameters to ensure same parameters generate same key
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]  # Only take first 8 characters
        return f"{self.prefix}{workspace_id}:{operation}:{param_hash}"

    def get(self, workspace_id: str, operation: str, **params) -> Optional[Any]:
        """Get cached data

        Args:
            workspace_id: Workspace ID
            operation: Operation name
            **params: Additional parameters

        Returns:
            Cached data, returns None if not exists or expired
        """
        if not self.enabled:
            return None

        try:
            key = self._make_key(workspace_id, operation, **params)
            data = self.redis.get(key)
            
            if data:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(data)
            
            logger.debug(f"Cache MISS: {key}")
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(
        self,
        workspace_id: str,
        operation: str,
        data: Any,
        ttl: Optional[int] = None,
        **params
    ) -> bool:
        """Set cached data

        Args:
            workspace_id: Workspace ID
            operation: Operation name
            data: Data to cache (must be JSON serializable)
            ttl: Cache TTL in seconds, uses default if None
            **params: Additional parameters

        Returns:
            Whether cache was successfully set
        """
        if not self.enabled:
            return False

        try:
            key = self._make_key(workspace_id, operation, **params)
            serialized = json.dumps(data, default=str)
            
            self.redis.setex(
                key,
                timedelta(seconds=ttl or self.ttl),
                serialized
            )
            
            logger.debug(f"Cache SET: {key} (TTL: {ttl or self.ttl}s)")
            return True
            
        except (RedisError, TypeError, ValueError) as e:
            logger.error(f"Cache set error: {e}")
            return False

    def invalidate(self, workspace_id: str, pattern: str = "*") -> int:
        """Invalidate cache

        Args:
            workspace_id: Workspace ID
            pattern: Match pattern (supports * wildcard)

        Returns:
            Number of deleted keys
        """
        if not self.enabled:
            return 0

        try:
            # If pattern doesn't contain *, automatically add :* to match all related cache keys
            if "*" not in pattern:
                pattern = f"{pattern}:*"

            search_pattern = f"{self.prefix}{workspace_id}:{pattern}"
            keys = list(self.redis.scan_iter(match=search_pattern, count=100))

            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"Cache invalidated: {deleted} keys matching {search_pattern}")
                return deleted

            return 0

        except RedisError as e:
            logger.error(f"Cache invalidate error: {e}")
            return 0

    def invalidate_all(self, workspace_id: str) -> int:
        """Invalidate all cache

        Args:
            workspace_id: Workspace ID

        Returns:
            Number of deleted keys
        """
        return self.invalidate(workspace_id, "*")

    def get_stats(self, workspace_id: str) -> dict[str, Any]:
        """Get cache statistics

        Args:
            workspace_id: Workspace ID

        Returns:
            Dictionary containing cache statistics
        """
        if not self.enabled:
            return {
                "enabled": False,
                "total_keys": 0,
                "memory_usage": 0
            }

        try:
            search_pattern = f"{self.prefix}{workspace_id}:*"
            keys = list(self.redis.scan_iter(match=search_pattern, count=100))

            # Calculate memory usage (estimate)
            memory_usage = 0
            for key in keys[:100]:  # Only check first 100 keys
                try:
                    memory_usage += self.redis.memory_usage(key) or 0
                except RedisError:
                    pass
            
            return {
                "enabled": True,
                "total_keys": len(keys),
                "memory_usage": memory_usage,
                "prefix": self.prefix
            }
            
        except RedisError as e:
            logger.error(f"Cache stats error: {e}")
            return {
                "enabled": True,
                "error": str(e)
            }

    def clear_all(self) -> int:
        """Clear all Git cache (dangerous operation)

        Returns:
            Number of deleted keys
        """
        if not self.enabled:
            return 0

        try:
            search_pattern = f"{self.prefix}*"
            keys = list(self.redis.scan_iter(match=search_pattern, count=100))
            
            if keys:
                deleted = self.redis.delete(*keys)
                logger.warning(f"All Git cache cleared: {deleted} keys")
                return deleted
            
            return 0
            
        except RedisError as e:
            logger.error(f"Cache clear error: {e}")
            return 0


# Cache key constants
class CacheKeys:
    """Cache key name constants"""

    CHANGES = "changes"
    WORKING_TREE_SNAPSHOT = "working_tree_snapshot"
    STATUS = "status"
    BRANCHES = "branches"
    CONTEXT_PATH = "context_path"
    COMMITS = "commits"
    COMMIT_DETAIL = "commit_detail"
    COMMIT_FILES = "commit_files"
    DIFF = "diff"
    BLOB = "blob"


# Cache TTL constants (seconds)
class CacheTTL:
    """Cache TTL constants"""

    VERY_SHORT = 10      # 10 seconds - frequently changing data (e.g., changes, status)
    SHORT = 30           # 30 seconds - normal data
    MEDIUM = 300         # 5 minutes - relatively stable data (e.g., branches)
    LONG = 1800          # 30 minutes - rarely changing data (e.g., commit history)
    VERY_LONG = 3600     # 1 hour - almost static data (e.g., commit detail, blob)


def create_git_cache(redis_url: Optional[str] = None, enabled: bool = True) -> GitCache:
    """Factory function to create GitCache instance

    Args:
        redis_url: Redis connection URL (e.g., 'redis://localhost:6379/0')
        enabled: Whether to enable caching

    Returns:
        GitCache instance (returns disabled cache if Redis unavailable)
    """
    if not enabled:
        logger.warning("GitCache is disabled by configuration")
        return GitCache(redis_client=None, enabled=False)

    if not redis_url:
        logger.warning("Redis URL not configured, GitCache will be disabled")
        return GitCache(redis_client=None, enabled=False)

    try:
        redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )

        # Test connection
        redis_client.ping()
        logger.info(f"GitCache enabled with Redis: {redis_url}")

        return GitCache(redis_client=redis_client, enabled=True)

    except RedisError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.warning("GitCache will be disabled due to Redis connection failure")
        return GitCache(redis_client=None, enabled=False)
