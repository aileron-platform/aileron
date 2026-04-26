"""Automation task queue manager

Use Redis Sorted Set to manage workspace task queue, ensuring tasks execute in order of addition time.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import redis

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)


class AutomationQueueManager:
    """Automation task queue manager

    Use Redis Sorted Set to manage task queue for each workspace:
    - Key: automation:queue:workspace:{workspace_id}
    - Score: timestamp (queue time)
    - Member: execution_id
    """

    def __init__(self, redis_client: redis.Redis):
        """Initialize queue manager

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client

    def _get_queue_key(self, workspace_id: str) -> str:
        """Get queue Redis key
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Redis Key
        """
        return f"automation:queue:workspace:{workspace_id}"

    def enqueue(self, workspace_id: str, execution_id: str) -> int:
        """Enqueue to queue

        Args:
            workspace_id: Workspace ID
            execution_id: Execution record ID

        Returns:
            Queue position (1-based)
        """
        key = self._get_queue_key(workspace_id)
        score = utcnow().timestamp()

        # Add to sorted set
        self.redis.zadd(key, {execution_id: score})

        # Set expiration time (24 hours)
        self.redis.expire(key, 86400)

        # Get queue position
        position = self.get_queue_position(workspace_id, execution_id)

        logger.info(
            "Task added to queue - workspace_id=%s, execution_id=%s, position=%d",
            workspace_id, execution_id, position
        )

        return position

    def dequeue(self, workspace_id: str) -> Optional[str]:
        """Dequeue next task

        Args:
            workspace_id: Workspace ID

        Returns:
            Execution record ID, or None if queue is empty
        """
        key = self._get_queue_key(workspace_id)

        # Remove element with smallest score (earliest added)
        result = self.redis.zpopmin(key, 1)

        if not result:
            return None

        execution_id = result[0][0]

        logger.info(
            "Task removed from queue - workspace_id=%s, execution_id=%s",
            workspace_id, execution_id
        )

        return execution_id

    def cancel(self, workspace_id: str, execution_id: str) -> bool:
        """Remove task from queue

        Args:
            workspace_id: Workspace ID
            execution_id: Execution record ID

        Returns:
            Whether successfully removed
        """
        key = self._get_queue_key(workspace_id)
        removed = self.redis.zrem(key, execution_id)

        if removed:
            logger.info(
                "Task removed from queue - workspace_id=%s, execution_id=%s",
                workspace_id, execution_id
            )

        return bool(removed)

    def get_queue_position(self, workspace_id: str, execution_id: str) -> int:
        """Query queue position

        Args:
            workspace_id: Workspace ID
            execution_id: Execution record ID

        Returns:
            Queue position (1-based), or 0 if not in queue
        """
        key = self._get_queue_key(workspace_id)
        rank = self.redis.zrank(key, execution_id)

        # zrank returns 0-based index, convert to 1-based position
        return rank + 1 if rank is not None else 0

    def get_queue_length(self, workspace_id: str) -> int:
        """Query queue length

        Args:
            workspace_id: Workspace ID

        Returns:
            Queue length
        """
        key = self._get_queue_key(workspace_id)
        return self.redis.zcard(key)

    def list_queued_executions(self, workspace_id: str, limit: int = 50) -> list[str]:
        """List queued tasks

        Args:
            workspace_id: Workspace ID
            limit: Maximum number to return

        Returns:
            List of execution record IDs (in queue order)
        """
        key = self._get_queue_key(workspace_id)
        return self.redis.zrange(key, 0, limit - 1)

    def cleanup_expired(self, workspace_id: str, timeout_seconds: int = 3600) -> int:
        """Clean up expired queued tasks

        Args:
            workspace_id: Workspace ID
            timeout_seconds: Timeout in seconds

        Returns:
            Number of tasks cleaned up
        """
        key = self._get_queue_key(workspace_id)
        cutoff = utcnow().timestamp() - timeout_seconds

        # Remove elements with score less than cutoff (timed out tasks)
        removed = self.redis.zremrangebyscore(key, 0, cutoff)

        if removed:
            logger.warning(
                "Cleaned up expired queued tasks - workspace_id=%s, removed=%d, timeout=%ds",
                workspace_id, removed, timeout_seconds
            )
        
        return removed

    def get_queue_info(self, workspace_id: str) -> dict:
        """Get queue information

        Args:
            workspace_id: Workspace ID

        Returns:
            Queue information dictionary
        """
        key = self._get_queue_key(workspace_id)
        length = self.redis.zcard(key)

        # Get oldest and newest task times
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
    """Get queue manager instance

    Returns:
        AutomationQueueManager instance
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

