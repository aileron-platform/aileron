"""Git 操作快取層"""

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
    """Git 操作快取層
    
    提供 Redis 快取功能，減少重複的 Git 操作
    """

    def __init__(self, redis_client: Optional[Redis] = None, ttl: int = 300, enabled: bool = True):
        """初始化快取
        
        Args:
            redis_client: Redis 客戶端實例
            ttl: 預設快取過期時間（秒），預設 5 分鐘
            enabled: 是否啟用快取
        """
        self.redis = redis_client
        self.ttl = ttl
        self.enabled = enabled and redis_client is not None
        self.prefix = "git:cache:"
        
        if not self.enabled:
            logger.warning("GitCache is disabled (no Redis client provided)")

    def _make_key(self, workspace_id: str, operation: str, **params) -> str:
        """生成快取鍵
        
        Args:
            workspace_id: Workspace ID
            operation: 操作名稱（如 'changes', 'commits', 'status'）
            **params: 額外參數（會被序列化並雜湊）
        
        Returns:
            快取鍵字串
        """
        # 將參數排序並序列化，確保相同參數產生相同的鍵
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]  # 只取前 8 位
        return f"{self.prefix}{workspace_id}:{operation}:{param_hash}"

    def get(self, workspace_id: str, operation: str, **params) -> Optional[Any]:
        """取得快取資料
        
        Args:
            workspace_id: Workspace ID
            operation: 操作名稱
            **params: 額外參數
        
        Returns:
            快取的資料，如果不存在或已過期則返回 None
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
        """設定快取資料
        
        Args:
            workspace_id: Workspace ID
            operation: 操作名稱
            data: 要快取的資料（必須可 JSON 序列化）
            ttl: 快取過期時間（秒），None 則使用預設值
            **params: 額外參數
        
        Returns:
            是否成功設定快取
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
        """使快取失效

        Args:
            workspace_id: Workspace ID
            pattern: 匹配模式（支援 * 通配符）

        Returns:
            刪除的鍵數量
        """
        if not self.enabled:
            return 0

        try:
            # 如果 pattern 不包含 *，則自動添加 :* 以匹配所有相關的快取鍵
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
        """使所有快取失效
        
        Args:
            workspace_id: Workspace ID
        
        Returns:
            刪除的鍵數量
        """
        return self.invalidate(workspace_id, "*")

    def get_stats(self, workspace_id: str) -> dict[str, Any]:
        """取得快取統計資訊
        
        Args:
            workspace_id: Workspace ID
        
        Returns:
            包含快取統計的字典
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
            
            # 計算記憶體使用（估算）
            memory_usage = 0
            for key in keys[:100]:  # 只檢查前 100 個鍵
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
        """清除所有 Git 快取（危險操作）
        
        Returns:
            刪除的鍵數量
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


# 快取鍵常數
class CacheKeys:
    """快取鍵名稱常數"""

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


# 快取 TTL 常數（秒）
class CacheTTL:
    """快取過期時間常數"""
    
    VERY_SHORT = 10      # 10 秒 - 頻繁變更的資料（如 changes, status）
    SHORT = 30           # 30 秒 - 一般資料
    MEDIUM = 300         # 5 分鐘 - 較穩定的資料（如 branches）
    LONG = 1800          # 30 分鐘 - 很少變更的資料（如 commit history）
    VERY_LONG = 3600     # 1 小時 - 幾乎不變的資料（如 commit detail, blob）


def create_git_cache(redis_url: Optional[str] = None, enabled: bool = True) -> GitCache:
    """建立 GitCache 實例的工廠函數

    Args:
        redis_url: Redis 連接 URL（如 'redis://localhost:6379/0'）
        enabled: 是否啟用快取

    Returns:
        GitCache 實例（如果 Redis 不可用則返回禁用的快取）
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

        # 測試連接
        redis_client.ping()
        logger.info(f"GitCache enabled with Redis: {redis_url}")

        return GitCache(redis_client=redis_client, enabled=True)

    except RedisError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.warning("GitCache will be disabled due to Redis connection failure")
        return GitCache(redis_client=None, enabled=False)
