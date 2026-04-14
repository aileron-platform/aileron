"""Redis 事件發布服務

用於發布執行完成事件給 Workspace Manager
"""

import json
import logging
from typing import Optional

from .redis import redis_manager

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    """Redis 事件發布器

    使用 RedisManager 來管理 Redis 連接，避免重複的連接邏輯。
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
        """發布執行完成事件

        Args:
            execution_id: 執行記錄 ID
            session_id: Session ID
            workspace_id: Workspace ID
            status: 執行狀態 (completed, failed, aborted)
            total_messages: 訊息總數
            has_error: 是否有錯誤
            error_message: 錯誤訊息
        """
        try:
            redis_client = await redis_manager.get_redis()

            # 構建事件數據
            event_data = {
                "execution_id": execution_id,
                "session_id": session_id,
                "workspace_id": workspace_id,
                "status": status,
                "total_messages": total_messages,
                "has_error": has_error,
                "error_message": error_message,
            }

            # 發布到特定執行 ID 的頻道
            channel = f"automation:execution:completed:{execution_id}"
            message = json.dumps(event_data)

            await redis_client.publish(channel, message)
            logger.info(
                f"Published execution completed event: execution_id={execution_id}, "
                f"status={status}, channel={channel}"
            )

            # 同時設置一個 key 用於輪詢備份（TTL 1小時）
            result_key = f"automation:execution:result:{execution_id}"
            await redis_client.setex(result_key, 3600, message)
            logger.debug(f"Set execution result key: {result_key}")

        except Exception as e:
            logger.error(f"Failed to publish execution completed event: {e}", exc_info=True)
            # 不拋出異常，避免影響主流程

    async def close(self) -> None:
        """關閉 Redis 連接

        注意：這會關閉共享的 redis_manager 連接，
        只有在確定不再需要 Redis 連接時才應該呼叫。
        """
        await redis_manager.close()


# 全局單例
_publisher: Optional[RedisEventPublisher] = None


def get_redis_publisher() -> RedisEventPublisher:
    """取得 Redis 事件發布器單例"""
    global _publisher
    if _publisher is None:
        _publisher = RedisEventPublisher()
    return _publisher
