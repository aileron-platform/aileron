"""Redis 事件訂閱服務

用於訂閱 Workspace Runtime 發布的執行完成事件
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

try:
    import redis.asyncio as aioredis
except ImportError:
    # 如果沒有 redis.asyncio，使用 aioredis
    import aioredis  # type: ignore

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisEventSubscriber:
    """Redis 事件訂閱器"""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None  # type: ignore
        self._settings = get_settings()

    async def get_redis(self) -> aioredis.Redis:  # type: ignore
        """取得 Redis 連接"""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self._settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # 測試連接
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
        """等待執行完成事件

        Args:
            execution_id: 執行記錄 ID
            timeout: 超時時間（秒），預設 1 小時

        Returns:
            執行結果數據，如果超時則返回 None
        """
        redis_client = await self.get_redis()
        channel = f"automation:execution:completed:{execution_id}"
        
        logger.info(f"開始訂閱執行完成事件: execution_id={execution_id}, channel={channel}, timeout={timeout}s")
        
        # 先檢查是否已經有結果（輪詢備份）
        result_key = f"automation:execution:result:{execution_id}"
        existing_result = await redis_client.get(result_key)
        if existing_result:
            logger.info(f"從 Redis key 獲取到已完成的執行結果: execution_id={execution_id}")
            try:
                return json.loads(existing_result)
            except json.JSONDecodeError as e:
                logger.error(f"解析執行結果失敗: {e}")
        
        # 創建 Pub/Sub 訂閱
        pubsub = redis_client.pubsub()
        
        try:
            await pubsub.subscribe(channel)
            logger.debug(f"已訂閱頻道: {channel}")
            
            # 等待訊息，帶超時
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # 計算剩餘超時時間
                elapsed = asyncio.get_event_loop().time() - start_time
                remaining_timeout = timeout - elapsed
                
                if remaining_timeout <= 0:
                    logger.warning(f"等待執行完成事件超時: execution_id={execution_id}, timeout={timeout}s")
                    return None
                
                try:
                    # 使用較短的超時進行輪詢，以便檢查總超時
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=min(remaining_timeout, 5.0)
                    )
                    
                    if message and message["type"] == "message":
                        logger.info(f"收到執行完成事件: execution_id={execution_id}")
                        try:
                            data = json.loads(message["data"])
                            logger.debug(f"執行結果數據: {data}")
                            return data
                        except json.JSONDecodeError as e:
                            logger.error(f"解析執行完成事件失敗: {e}, data={message['data']}")
                            return None
                            
                except asyncio.TimeoutError:
                    # 繼續等待
                    continue
                    
        except Exception as e:
            logger.error(f"訂閱執行完成事件失敗: {e}", exc_info=True)
            return None
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.debug(f"已取消訂閱並關閉 Pub/Sub: {channel}")
            except Exception as e:
                logger.warning(f"關閉 Pub/Sub 失敗: {e}")

    async def close(self) -> None:
        """關閉 Redis 連接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


def wait_for_execution_completed_sync(
    execution_id: str,
    timeout: int = 3600,
) -> Optional[Dict[str, Any]]:
    """同步版本的等待執行完成事件（用於 Celery 任務）

    Args:
        execution_id: 執行記錄 ID
        timeout: 超時時間（秒），預設 1 小時

    Returns:
        執行結果數據，如果超時則返回 None
    """
    subscriber = RedisEventSubscriber()
    
    # 創建新的事件循環
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

