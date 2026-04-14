"""WebSocket 測試輔助工具."""

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
    """WebSocket 測試訊息模型."""
    type: str
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    approved: Optional[bool] = None
    reason: Optional[str] = None


class WebSocketTestClient:
    """WebSocket 測試客戶端，模擬真實的 WebSocket 連線行為."""

    def __init__(self, base_url: str = "http://localhost:3002") -> None:
        self.base_url = base_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.messages: List[WebSocketTestMessage] = []
        self.is_connected = False

    async def connect(self, endpoint: str) -> None:
        """建立 WebSocket 連線."""
        ws_url = self.base_url.replace("http://", "ws://") + endpoint
        try:
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            logger.info(f"[WS-Test] 連線建立: {ws_url}")
        except Exception as e:
            logger.error(f"[WS-Test] 連線失敗: {e}")
            raise

    async def disconnect(self) -> None:
        """斷開 WebSocket 連線."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("[WS-Test] 連線已斷開")
            self.websocket = None

    async def send_message(self, message: Union[Dict[str, Any], WebSocketTestMessage]) -> None:
        """發送訊息到 WebSocket."""
        if not self.websocket or not self.is_connected:
            raise RuntimeError("WebSocket 未連線")

        if isinstance(message, BaseModel):
            message = message.model_dump()

        await self.websocket.send(json.dumps(message))
        logger.debug(f"[WS-Test] 發送訊息: {message.get('type')}")

    async def receive_message(self, timeout: float = 10.0) -> Optional[WebSocketTestMessage]:
        """接收 WebSocket 訊息."""
        if not self.websocket or not self.is_connected:
            raise RuntimeError("WebSocket 未連線")

        try:
            data = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            message_dict = json.loads(data)
            message = WebSocketTestMessage(**message_dict)
            self.messages.append(message)
            logger.debug(f"[WS-Test] 接收訊息: {message.type}")
            return message
        except asyncio.TimeoutError:
            logger.warning(f"[WS-Test] 接收訊息超時 ({timeout}s)")
            return None
        except Exception as e:
            logger.error(f"[WS-Test] 接收訊息錯誤: {e}")
            return None

    async def receive_messages_until(
        self,
        condition: callable[[WebSocketTestMessage], bool],
        timeout: float = 30.0,
        max_messages: int = 100
    ) -> List[WebSocketTestMessage]:
        """接收訊息直到滿足條件或超時。"""
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
        """取得指定類型的訊息。"""
        return [msg for msg in self.messages if msg.type == message_type]

    def clear_messages(self) -> None:
        """清除已接收的訊息記錄。"""
        self.messages.clear()


class MockWebSocket:
    """模擬 WebSocket 物件，用於單元測試。"""

    def __init__(self, client_info: Optional[Dict[str, Any]] = None) -> None:
        self.client = client_info or {"host": "test-client", "port": 12345}
        self.messages_sent: List[Dict[str, Any]] = []
        self.messages_received: List[Dict[str, Any]] = []
        self.is_closed = False

    async def accept(self) -> None:
        """接受連線。"""
        logger.debug("[Mock-WS] 接受連線")

    async def send_text(self, data: str) -> None:
        """發送文字訊息。"""
        if self.is_closed:
            raise RuntimeError("WebSocket 已關閉")

        try:
            message = json.loads(data)
            self.messages_sent.append(message)
            logger.debug(f"[Mock-WS] 發送訊息: {message.get('type')}")
        except json.JSONDecodeError:
            self.messages_sent.append({"raw": data})
            logger.debug("[Mock-WS] 發送原始訊息")

    async def receive_json(self) -> Dict[str, Any]:
        """接收 JSON 訊息。"""
        if self.is_closed:
            raise RuntimeError("WebSocket 已關閉")

        # 在測試中模擬接收訊息
        if self.messages_received:
            return self.messages_received.pop(0)

        # 如果沒有預設訊息，返回一個預設的 ping 訊息
        return {"type": "ping"}

    def add_received_message(self, message: Dict[str, Any]) -> None:
        """添加預設的接收訊息。"""
        self.messages_received.append(message)

    async def close(self) -> None:
        """關閉連線。"""
        self.is_closed = True
        logger.debug("[Mock-WS] 連線已關閉")


class WebSocketTestHelper:
    """WebSocket 測試輔助工具集合。"""

    @staticmethod
    def create_approval_response(request_id: str, approved: bool, reason: Optional[str] = None) -> Dict[str, Any]:
        """建立工具審批回應訊息。"""
        return {
            "type": "tool_approval_response",
            "request_id": request_id,
            "approved": approved,
            "reason": reason
        }

    @staticmethod
    def create_approval_request_event(request_id: str, session_id: str, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """建立工具審批請求事件。"""
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
        """建立 session 訊息。"""
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
        """建立 session 開始事件。"""
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
        """建立 session 完成事件。"""
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
        """等待特定類型的訊息。"""
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
        """驗證訊息包含預期欄位。"""
        assert message is not None, "訊息不應為空"

        for field, expected_value in expected_fields.items():
            actual_value = getattr(message, field, None)
            if field == "data" and isinstance(expected_value, dict):
                assert actual_value is not None, f"訊息缺少 data 欄位"
                for data_field, data_value in expected_value.items():
                    assert actual_value.get(data_field) == data_value, \
                        f"data.{data_field} 應為 {data_value}，實際為 {actual_value.get(data_field)}"
            else:
                assert actual_value == expected_value, \
                    f"{field} 應為 {expected_value}，實際為 {actual_value}"


__all__ = [
    "WebSocketTestMessage",
    "WebSocketTestClient",
    "MockWebSocket",
    "WebSocketTestHelper"
]