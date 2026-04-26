"""Redis event subscription service

Used to subscribe to ExecutionComplete events published by Workspace Runtime
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    # If no redis.asyncio, use aioredis
    import aioredis  # type: ignore

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisEventSubscriber:
    """Redis event subscriber"""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None  # type: ignore
        self._settings = get_settings()

    async def get_redis(self) -> aioredis.Redis:  # type: ignore
        """Get Redis connection"""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self._settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                await self._redis.ping()
                logger.info(f"Redis connection established successfully: {self._settings.REDIS_URL}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    async def wait_for_execution_completed(
        self,
        execution_id: str,
        timeout: int = 3600,
    ) -> Optional[Dict[str, Any]]:
        """Wait for execution completion event

        Args:
            execution_id: Execution record ID
            timeout: Timeout in seconds (default 1 hour)

        Returns:
            Execution result data, or None if timeout
        """
        redis_client = await self.get_redis()
        channel = f"automation:execution:completed:{execution_id}"

        logger.info(f"Starting to subscribe to ExecutionComplete event: execution_id={execution_id}, channel={channel}, timeout={timeout}s")

        # First check if result already exists (polling fallback)
        result_key = f"automation:execution:result:{execution_id}"
        existing_result = await redis_client.get(result_key)
        if existing_result:
            logger.info(f"Got completed execution result from Redis key: execution_id={execution_id}")
            try:
                return json.loads(existing_result)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse execution result: {e}")

        # Create Pub/Sub subscription
        pubsub = redis_client.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.debug(f"Subscribed to channel: {channel}")

            # Wait for message with timeout
            start_time = asyncio.get_event_loop().time()

            while True:
                # Calculate remaining timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                remaining_timeout = timeout - elapsed

                if remaining_timeout <= 0:
                    logger.warning(f"Waiting for ExecutionComplete event timed out: execution_id={execution_id}, timeout={timeout}s")
                    return None

                try:
                    # Use shorter timeout for polling to check total timeout
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=min(remaining_timeout, 5.0)
                    )

                    if message and message["type"] == "message":
                        logger.info(f"Received ExecutionComplete event: execution_id={execution_id}")
                        try:
                            data = json.loads(message["data"])
                            logger.debug(f"Execution result data: {data}")
                            return data
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse ExecutionComplete event: {e}, data={message['data']}")
                            return None

                except asyncio.TimeoutError:
                    # Resume waiting
                    continue

        except Exception as e:
            logger.error(f"Failed to subscribe to ExecutionComplete event: {e}", exc_info=True)
            return None
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.debug(f"Unsubscribed and closed Pub/Sub: {channel}")
            except Exception as e:
                logger.warning(f"Failed to close Pub/Sub: {e}")

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


def wait_for_execution_completed_sync(
    execution_id: str,
    timeout: int = 3600,
) -> Optional[Dict[str, Any]]:
    """Synchronous version of waiting for ExecutionComplete event (for Celery tasks)

    Args:
        execution_id: Execution record ID
        timeout: Timeout in seconds (default 1 hour)

    Returns:
        Execution result data, or None if timeout
    """
    subscriber = RedisEventSubscriber()

    # Create new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            subscriber.wait_for_execution_completed(execution_id, timeout)
        )
        return result
    finally:
        loop.run_until_complete(subscriber.close())
        loop.close()

