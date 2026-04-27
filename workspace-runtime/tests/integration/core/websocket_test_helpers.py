"""WebSocket test helper utilities."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock

import websockets
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WebSocketTestMessage(BaseModel):
    """WebSocket test message model."""
    type: str
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    approved: Optional[bool] = None
    reason: Optional[str] = None


class WebSocketTestClient:
    """WebSocket test client, simulates real WebSocket connection behavior."""

    def __init__(self, base_url: str = "http://localhost:3002") -> None:
        self.base_url = base_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.messages: List[WebSocketTestMessage] = []
        self.is_connected = False

    async def connect(self, endpoint: str) -> None:
        """Establish WebSocket connection."""
        ws_url = self.base_url.replace("http://", "ws://") + endpoint
        try:
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            logger.info(f"[WS-Test] Connection established: {ws_url}")
        except Exception as e:
            logger.error(f"[WS-Test] Connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("[WS-Test] Connection disconnected")
            self.websocket = None

    async def send_message(self, message: Union[Dict[str, Any], WebSocketTestMessage]) -> None:
        """Send message to WebSocket."""
        if not self.websocket or not self.is_connected:
            raise RuntimeError("WebSocket not connected")

        if isinstance(message, BaseModel):
            message = message.model_dump()

        await self.websocket.send(json.dumps(message))
        logger.debug(f"[WS-Test] Sent message: {message.get('type')}")

    async def receive_message(self, timeout: float = 10.0) -> Optional[WebSocketTestMessage]:
        """Receive WebSocket message."""
        if not self.websocket or not self.is_connected:
            raise RuntimeError("WebSocket not connected")

        try:
            data = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            message_dict = json.loads(data)
            message = WebSocketTestMessage(**message_dict)
            self.messages.append(message)
            logger.debug(f"[WS-Test] Received message: {message.type}")
            return message
        except asyncio.TimeoutError:
            logger.warning(f"[WS-Test] Receive message timeout ({timeout}s)")
            return None
        except Exception as e:
            logger.error(f"[WS-Test] Receive message error: {e}")
            return None

    async def receive_messages_until(
        self,
        condition: callable[[WebSocketTestMessage], bool],
        timeout: float = 30.0,
        max_messages: int = 100
    ) -> List[WebSocketTestMessage]:
        """Receive messages until condition is met or timeout."""
        messages = []
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout and len(messages) < max_messages:
            message = await self.receive_message(timeout=1.0)
            if message is None:
                continue

            messages.append(message)
            if condition(message):
                break

        return messages

    def get_messages_by_type(self, message_type: str) -> List[WebSocketTestMessage]:
        """Get messages of specified type."""
        return [msg for msg in self.messages if msg.type == message_type

    def clear_messages(self) -> None:
        """Clear received message records."""
        self.messages.clear()


class MockWebSocket:
    """Mock WebSocket object for unit testing."""

    def __init__(self, client_info: Optional[Dict[str, Any]] = None) -> None:
        self.client = client_info or {"host": "test-client", "port": 12345}
        self.messages_sent: List[Dict[str, Any]] = []
        self.messages_received: List[Dict[str, Any]] = []
        self.is_closed = False

    async def accept(self) -> None:
        """Accept connection."""
        logger.debug("[Mock-WS] Connection accepted")

    async def send_text(self, data: str) -> None:
        """Send text message."""
        if self.is_closed:
            raise RuntimeError("WebSocket closed")

        try:
            message = json.loads(data)
            self.messages_sent.append(message)
            logger.debug(f"[Mock-WS] Sent message: {message.get('type')}")
        except json.JSONDecodeError:
            self.messages_sent.append({"raw": data})
            logger.debug("[Mock-WS] Sent raw message")

    async def receive_json(self) -> Dict[str, Any]:
        """Receive JSON message."""
        if self.is_closed:
            raise RuntimeError("WebSocket closed")

        # Simulate receiving messages in tests
        if self.messages_received:
            return self.messages_received.pop(0)

        # If no preset messages, return a default ping message
        return {"type": "ping"}

    def add_received_message(self, message: Dict[str, Any]) -> None:
        """Add preset received message."""
        self.messages_received.append(message)

    async def close(self) -> None:
        """Close connection."""
        self.is_closed = True
        logger.debug("[Mock-WS] Connection closed")


class WebSocketTestHelper:
    """WebSocket test helper utilities collection."""

    @staticmethod
    def create_approval_response(request_id: str, approved: bool, reason: Optional[str] = None) -> Dict[str, Any]:
        """Create tool approval response message."""
        return {
            "type": "tool_approval_response",
            "request_id": request_id,
            "approved": approved,
            "reason": reason
        }

    @staticmethod
    def create_approval_request_event(request_id: str, session_id: str, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create tool approval request event."""
        return {
            "type": "tool_approval_request",
            "data": {
                "request_id": request_id,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "timeout": 60,
                "created_at": "2025-01-01T00:00:00Z"
            }
        }

    @staticmethod
    def create_session_message(session_id: str, role: str, content: str) -> Dict[str, Any]:
        """Create session message."""
        return {
            "type": "session_message",
            "data": {
                "session_id": session_id,
                "role": role,
                "normalized_content": content,
                "created_at": "2025-01-01T00:00:00Z"
            }
        }

    @staticmethod
    def create_session_started_event(session_id: str, instruction: str) -> Dict[str, Any]:
        """Create session started event."""
        return {
            "type": "session_started",
            "data": {
                "session_id": session_id,
                "instruction": instruction,
                "status": "running",
                "started_at": "2025-01-01T00:00:00Z"
            }
        }

    @staticmethod
    def create_session_completed_event(session_id: str, status: str, has_error: bool = False) -> Dict[str, Any]:
        """Create session completed event."""
        return {
            "type": "session_completed",
            "data": {
                "session_id": session_id,
                "status": status,
                "total_messages": 1,
                "has_error": has_error,
                "completed_at": "2025-01-01T00:01:00Z"
            }
        }

    @staticmethod
    async def wait_for_message_type(
        client: WebSocketTestClient,
        message_type: str,
        timeout: float = 10.0
    ) -> Optional[WebSocketTestMessage]:
        """Wait for specific type of message."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            message = await client.receive_message(timeout=1.0)
            if message and message.type == message_type:
                return message
            await asyncio.sleep(0.1)

        return None

    @staticmethod
    def assert_message_contains(
        message: Optional[WebSocketTestMessage],
        expected_fields: Dict[str, Any]
    ) -> None:
        """Verify message contains expected fields."""
        assert message is not None, "Message should not be empty"

        for field, expected_value in expected_fields.items():
            actual_value = getattr(message, field, None)
            if field == "data" and isinstance(expected_value, dict):
                assert actual_value is not None, "Message missing data field"
                for data_field, data_value in expected_value.items():
                    assert actual_value.get(data_field) == data_value, \
                        f"data.{data_field} should be {data_value}, actual is {actual_value.get(data_field)}"
            else:
                assert actual_value == expected_value, \
                    f"{field} should be {expected_value}, actual is {actual_value}"


__all__ = [
    "WebSocketTestMessage",
    "WebSocketTestClient",
    "MockWebSocket",
    "WebSocketTestHelper"
]