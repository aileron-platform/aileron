"""
串流回調介面.

比照 agor-main 的 StreamingCallbacks
"""

from typing import Any, Dict, Optional, Protocol


class StreamingCallbacks(Protocol):
    """
    串流回調介面.
    
    用於實時 UI 更新（打字機效果）。
    """
    
    async def on_stream_start(self, message_id: str) -> None:
        """
        開始串流文字.
        
        Args:
            message_id: 訊息 ID
        """
        ...
    
    async def on_stream_chunk(self, message_id: str, chunk: str) -> None:
        """
        接收文字片段.
        
        Args:
            message_id: 訊息 ID
            chunk: 文字片段（3-10 個字）
        """
        ...
    
    async def on_stream_end(self, message_id: str) -> None:
        """
        結束串流文字.
        
        Args:
            message_id: 訊息 ID
        """
        ...
    
    async def on_thinking_start(
        self,
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        開始思考.
        
        Args:
            message_id: 訊息 ID
            metadata: 元數據（例如 budget）
        """
        ...
    
    async def on_thinking_chunk(self, message_id: str, chunk: str) -> None:
        """
        接收思考片段.
        
        Args:
            message_id: 訊息 ID
            chunk: 思考片段
        """
        ...
    
    async def on_thinking_end(self, message_id: str) -> None:
        """
        結束思考.
        
        Args:
            message_id: 訊息 ID
        """
        ...

    async def on_message_created(self, message: Dict[str, Any]) -> None:
        """
        訊息建立通知.

        Args:
            message: 訊息資料
        """
        ...

    def emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        發送 WebSocket 事件.

        Args:
            event_name: 事件名稱 (e.g., 'permission:request')
            data: 事件資料
        """
        ...

