"""WebSocket fixtures for testing

Provides fixtures for testing WebSocket functionality.
"""

import pytest
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
async def async_client() -> AsyncGenerator:
    """Create async test client for integration tests

    Usage:
        @pytest.mark.asyncio
        async def test_endpoint(async_client):
            response = await async_client.get("/api/v1/health")
            assert response.status_code == 200
    """
    from app.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def websocket_test_client():
    """Create WebSocket test client

    Usage:
        def test_websocket(websocket_test_client):
            with websocket_test_client.websocket_connect("/ws") as websocket:
                websocket.send_json({"type": "ping"})
                data = websocket.receive_json()
                assert data["type"] == "pong"
    """
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
async def websocket_manager():
    """Create WebSocketManager for testing

    Usage:
        @pytest.mark.asyncio
        async def test_manager(websocket_manager):
            mock_websocket = MagicMock()
            await websocket_manager.connect("ws_123", mock_websocket)
            assert websocket_manager.get_connection_count("ws_123") == 1
    """
    from app.modules.sessions.websocket.manager import WebSocketManager

    manager = WebSocketManager()
    yield manager

    # Cleanup all connections
    try:
        await manager.disconnect_all()
    except AttributeError:
        # If disconnect_all doesn't exist, manually clean up
        manager._connections = {}


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket connection

    Usage:
        @pytest.mark.asyncio
        async def test_send(mock_websocket, websocket_manager):
            await websocket_manager.connect("ws_123", mock_websocket)
            await websocket_manager.broadcast_event("ws_123", {"type": "test"})
            mock_websocket.send_json.assert_called_once()
    """
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_json = AsyncMock(return_value={"type": "ping"})
    websocket.receive_text = AsyncMock(return_value="ping")
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    return websocket


@pytest.fixture
def mock_websocket_with_messages():
    """Create mock WebSocket with predefined messages

    Usage:
        @pytest.mark.asyncio
        async def test_receive(mock_websocket_with_messages):
            msg1 = await mock_websocket_with_messages.receive_json()
            assert msg1["type"] == "session_started"
    """
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    websocket.send_text = AsyncMock()

    messages = [
        {"type": "session_started", "session_id": "sess_123"},
        {"type": "message", "content": "Test message"},
        {"type": "session_completed", "status": "success"},
    ]

    async def receive_json():
        if messages:
            return messages.pop(0)
        raise Exception("No more messages")

    websocket.receive_json = AsyncMock(side_effect=receive_json)
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    return websocket


# Real WebSocket testing (requires running server)

@pytest.fixture
async def websocket_connection():
    """Create real WebSocket connection for integration tests

    Requires workspace-runtime server running on localhost:3002

    Usage:
        @pytest.mark.asyncio
        @pytest.mark.integration
        async def test_real_websocket(websocket_connection):
            ws = await websocket_connection("ws_test")
            await ws.send(json.dumps({"type": "ping"}))
            response = await ws.recv()
            assert json.loads(response)["type"] == "pong"
    """
    import websockets
    import json

    async def connect(workspace_id: str):
        uri = f"ws://localhost:3002/api/v1/agent-sessions/ws/{workspace_id}"
        try:
            websocket = await websockets.connect(uri, timeout=5.0)
            return websocket
        except (OSError, websockets.exceptions.WebSocketException) as e:
            pytest.skip(f"WebSocket server not available: {e}")

    return connect


# WebSocket event helpers

@pytest.fixture
def websocket_event_factory():
    """Factory for creating WebSocket events

    Usage:
        def test_events(websocket_event_factory):
            event = websocket_event_factory.session_started("sess_123")
            assert event["type"] == "session_started"
    """
    class WebSocketEventFactory:
        @staticmethod
        def session_started(session_id: str, workspace_id: str = "ws_test"):
            return {
                "type": "session_started",
                "session_id": session_id,
                "workspace_id": workspace_id,
                "timestamp": "2025-01-01T00:00:00Z"
            }

        @staticmethod
        def session_completed(
            session_id: str,
            status: str = "completed",
            total_messages: int = 0,
            has_error: bool = False
        ):
            return {
                "type": "session_completed",
                "session_id": session_id,
                "status": status,
                "total_messages": total_messages,
                "has_error": has_error
            }

        @staticmethod
        def message_chunk(session_id: str, content: str):
            return {
                "type": "message_chunk",
                "session_id": session_id,
                "content": content
            }

        @staticmethod
        def tool_approval_request(
            request_id: str,
            session_id: str,
            tool_name: str,
            tool_input: dict
        ):
            return {
                "type": "tool_approval_request",
                "request_id": request_id,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "timeout": 60
            }

    return WebSocketEventFactory()
