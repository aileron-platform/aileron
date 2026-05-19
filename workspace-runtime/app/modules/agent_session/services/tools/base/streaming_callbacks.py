"""
Streaming callback interface.

Streaming callback interface for SDK event handling.
"""

from typing import Any, Dict, Optional, Protocol


class StreamingCallbacks(Protocol):
    """
    Streaming callback interface.

    Used for real-time UI updates (typewriter effect).
    """
    
    async def on_stream_start(self, message_id: str) -> None:
        """
        Start streaming text.
        
        Args:
            message_id: Message ID
        """
        ...
    
    async def on_stream_chunk(self, message_id: str, chunk: str) -> None:
        """
        Receive text chunk.
        
        Args:
            message_id: Message ID
            chunk: Text chunk (3-10 characters)
        """
        ...
    
    async def on_stream_end(self, message_id: str) -> None:
        """
        End streaming text.
        
        Args:
            message_id: Message ID
        """
        ...
    
    async def on_thinking_start(
        self,
        message_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Start thinking.
        
        Args:
            message_id: Message ID
            metadata: Metadata (e.g., budget)
        """
        ...
    
    async def on_thinking_chunk(self, message_id: str, chunk: str) -> None:
        """
        Receive thinking chunk.
        
        Args:
            message_id: Message ID
            chunk: Thinking chunk
        """
        ...
    
    async def on_thinking_end(self, message_id: str) -> None:
        """
        End thinking.
        
        Args:
            message_id: Message ID
        """
        ...

    async def on_message_created(self, message: Dict[str, Any]) -> None:
        """
        Message created notification.

        Args:
            message: Message data
        """
        ...

    async def on_status_notice(self, notice: Dict[str, Any]) -> None:
        """
        Non-terminal task status notification.

        Args:
            notice: Status notice payload.
        """
        ...

    def emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        Emit WebSocket event.

        Args:
            event_name: Event name (e.g., 'permission:request')
            data: Event data
        """
        ...
