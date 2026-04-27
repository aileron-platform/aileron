"""Redis event publishing service

Used to publish execution completion events to Workspace Manager
"""

import json
import logging
from typing import Optional

from .redis import redis_manager

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    """Redis event publisher

    Use RedisManager to manage Redis connections, avoiding duplicate connection logic.
    """

    async def publish_execution_completed(
        self,
        execution_id: str,
        session_id: str,
        workspace_id: str,
        status: str,
        total_messages: int,
        has_error: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Publish execution completion event

        Args:
            execution_id: Execution record ID
            session_id: Session ID
            workspace_id: Workspace ID
            status: Execution status (completed, failed, aborted)
            total_messages: Total message count
            has_error: Whether there is an error
            error_message: Error message
        """
        try:
            redis_client = await redis_manager.get_redis()

            # Build event data
            event_data = {
                "execution_id": execution_id,
                "session_id": session_id,
                "workspace_id": workspace_id,
                "status": status,
                "total_messages": total_messages,
                "has_error": has_error,
                "error_message": error_message,
            }

            # Publish to channel for specific execution ID
            channel = f"automation:execution:completed:{execution_id}"
            message = json.dumps(event_data)

            await redis_client.publish(channel, message)
            logger.info(
                f"Published execution completed event: execution_id={execution_id}, "
                f"status={status}, channel={channel}"
            )

            # Also set a key for polling backup (TTL 1 hour)
            result_key = f"automation:execution:result:{execution_id}"
            await redis_client.setex(result_key, 3600, message)
            logger.debug(f"Set execution result key: {result_key}")

        except Exception as e:
            logger.error(f"Failed to publish execution completed event: {e}", exc_info=True)
            # Do not raise exception to avoid affecting main flow

    async def close(self) -> None:
        """Close Redis connection

        Note: This will close the shared redis_manager connection,
        should only be called when Redis connection is no longer needed.
        """
        await redis_manager.close()


# Global singleton
_publisher: Optional[RedisEventPublisher] = None


def get_redis_publisher() -> RedisEventPublisher:
    """Get Redis event publisher singleton"""
    global _publisher
    if _publisher is None:
        _publisher = RedisEventPublisher()
    return _publisher
