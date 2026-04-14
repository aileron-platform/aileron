"""自動化任務佇列管理器

使用 Redis Sorted Set 管理工作區任務佇列，確保任務按照加入時間順序執行。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import redis

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)


class AutomationQueueManager:
    """自動化任務佇列管理器
    
    使用 Redis Sorted Set 管理每個工作區的任務佇列：
    - Key: automation:queue:workspace:{workspace_id}
    - Score: timestamp (排隊時間)
    - Member: execution_id
    """

    def __init__(self, redis_client: redis.Redis):
        """初始化佇列管理器
        
        Args:
            redis_client: Redis 客戶端實例
        """
        self.redis = redis_client

    def _get_queue_key(self, workspace_id: str) -> str:
        """獲取佇列 Redis Key
        
        Args:
            workspace_id: 工作區 ID
            
        Returns:
            Redis Key
        """
        return f"automation:queue:workspace:{workspace_id}"

    def enqueue(self, workspace_id: str, execution_id: str) -> int:
        """加入佇列
        
        Args:
            workspace_id: 工作區 ID
            execution_id: 執行記錄 ID
            
        Returns:
            排隊位置（1-based）
        """
        key = self._get_queue_key(workspace_id)
        score = utcnow().timestamp()
        
        # 加入 Sorted Set
        self.redis.zadd(key, {execution_id: score})
        
        # 設定過期時間（24 小時）
        self.redis.expire(key, 86400)
        
        # 獲取排隊位置
        position = self.get_queue_position(workspace_id, execution_id)
        
        logger.info(
            "任務加入佇列 - workspace_id=%s, execution_id=%s, position=%d",
            workspace_id, execution_id, position
        )
        
        return position

    def dequeue(self, workspace_id: str) -> Optional[str]:
        """取出下一個任務
        
        Args:
            workspace_id: 工作區 ID
            
        Returns:
            執行記錄 ID，如果佇列為空則返回 None
        """
        key = self._get_queue_key(workspace_id)
        
        # 取出分數最小的元素（最早加入的）
        result = self.redis.zpopmin(key, 1)
        
        if not result:
            return None
        
        execution_id = result[0][0]
        
        logger.info(
            "從佇列取出任務 - workspace_id=%s, execution_id=%s",
            workspace_id, execution_id
        )
        
        return execution_id

    def cancel(self, workspace_id: str, execution_id: str) -> bool:
        """從佇列移除任務
        
        Args:
            workspace_id: 工作區 ID
            execution_id: 執行記錄 ID
            
        Returns:
            是否成功移除
        """
        key = self._get_queue_key(workspace_id)
        removed = self.redis.zrem(key, execution_id)
        
        if removed:
            logger.info(
                "從佇列移除任務 - workspace_id=%s, execution_id=%s",
                workspace_id, execution_id
            )
        
        return bool(removed)

    def get_queue_position(self, workspace_id: str, execution_id: str) -> int:
        """查詢排隊位置
        
        Args:
            workspace_id: 工作區 ID
            execution_id: 執行記錄 ID
            
        Returns:
            排隊位置（1-based），如果不在佇列中則返回 0
        """
        key = self._get_queue_key(workspace_id)
        rank = self.redis.zrank(key, execution_id)
        
        # zrank 返回 0-based 索引，轉換為 1-based 位置
        return rank + 1 if rank is not None else 0

    def get_queue_length(self, workspace_id: str) -> int:
        """查詢佇列長度
        
        Args:
            workspace_id: 工作區 ID
            
        Returns:
            佇列長度
        """
        key = self._get_queue_key(workspace_id)
        return self.redis.zcard(key)

    def list_queued_executions(self, workspace_id: str, limit: int = 50) -> list[str]:
        """列出排隊中的任務
        
        Args:
            workspace_id: 工作區 ID
            limit: 最大返回數量
            
        Returns:
            執行記錄 ID 列表（按排隊順序）
        """
        key = self._get_queue_key(workspace_id)
        return self.redis.zrange(key, 0, limit - 1)

    def cleanup_expired(self, workspace_id: str, timeout_seconds: int = 3600) -> int:
        """清理超時的排隊任務
        
        Args:
            workspace_id: 工作區 ID
            timeout_seconds: 超時時間（秒）
            
        Returns:
            清理的任務數量
        """
        key = self._get_queue_key(workspace_id)
        cutoff = utcnow().timestamp() - timeout_seconds
        
        # 移除分數小於 cutoff 的元素（超時的任務）
        removed = self.redis.zremrangebyscore(key, 0, cutoff)
        
        if removed:
            logger.warning(
                "清理超時排隊任務 - workspace_id=%s, removed=%d, timeout=%ds",
                workspace_id, removed, timeout_seconds
            )
        
        return removed

    def get_queue_info(self, workspace_id: str) -> dict:
        """獲取佇列資訊
        
        Args:
            workspace_id: 工作區 ID
            
        Returns:
            佇列資訊字典
        """
        key = self._get_queue_key(workspace_id)
        length = self.redis.zcard(key)
        
        # 獲取最早和最晚的任務時間
        oldest = None
        newest = None
        
        if length > 0:
            oldest_result = self.redis.zrange(key, 0, 0, withscores=True)
            newest_result = self.redis.zrange(key, -1, -1, withscores=True)
            
            if oldest_result:
                oldest = datetime.fromtimestamp(oldest_result[0][1])
            if newest_result:
                newest = datetime.fromtimestamp(newest_result[0][1])
        
        return {
            "workspace_id": workspace_id,
            "queue_length": length,
            "oldest_queued_at": oldest,
            "newest_queued_at": newest,
        }


def get_queue_manager() -> AutomationQueueManager:
    """獲取佇列管理器實例
    
    Returns:
        AutomationQueueManager 實例
    """
    from app.config.settings import get_settings
    
    settings = get_settings()
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    
    return AutomationQueueManager(redis_client)


__all__ = [
    "AutomationQueueManager",
    "get_queue_manager",
]

