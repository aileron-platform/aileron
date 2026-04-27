"""WebSocket integration tests."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, WebSocket

from app.modules.agent_session.websocket.manager import (
    ConnectionManager,
    get_connection_manager,
    reset_connection_manager,
)
from app.modules.agent_session.websocket.events import (
    EventEmitter,
    EventType,
    WebSocketEvent,
    get_event_emitter,
    reset_event_emitter,
)


class TestConnectionManager:
    """ConnectionManager tests."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset manager before each test."""
        reset_connection_manager()
        yield
        reset_connection_manager()

    @pytest.fixture
    def manager(self):
        """Create ConnectionManager."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create Mock WebSocket."""
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """Test connection."""
        connection_id = await manager.connect(
            mock_websocket,
            user_id="user-123",
            session_id="session-456",
        )

        assert connection_id is not None
        assert manager.get_connection_count() == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """Test disconnection."""
        connection_id = await manager.connect(mock_websocket)
        assert manager.get_connection_count() == 1

        await manager.disconnect(connection_id)
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_subscribe_session(self, manager, mock_websocket):
        """Test subscribe Session."""
        connection_id = await manager.connect(mock_websocket)

        result = await manager.subscribe_session(connection_id, "session-abc")

        assert result is True
        assert manager.get_session_subscriber_count("session-abc") == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_session(self, manager, mock_websocket):
        """Test unsubscribe Session."""
        connection_id = await manager.connect(
            mock_websocket,
            session_id="session-xyz",
        )
        assert manager.get_session_subscriber_count("session-xyz") == 1

        result = await manager.unsubscribe_session(connection_id, "session-xyz")

        assert result is True
        assert manager.get_session_subscriber_count("session-xyz") == 0

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """Test broadcast."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        count = await manager.broadcast({"type": "test", "data": "hello"})

        assert count == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_session(self, manager):
        """Test send to Session."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1, session_id="session-a")
        await manager.connect(ws2, session_id="session-b")

        count = await manager.send_to_session(
            "session-a",
            {"type": "test", "data": "for session-a"},
        )

        assert count == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_user(self, manager):
        """Test send to user."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1, user_id="user-a")
        await manager.connect(ws2, user_id="user-b")

        count = await manager.send_to_user(
            "user-a",
            {"type": "test", "data": "for user-a"},
        )

        assert count == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_sessions_per_connection(self, manager, mock_websocket):
        """Test single connection subscribing to multiple Sessions."""
        connection_id = await manager.connect(mock_websocket)

        await manager.subscribe_session(connection_id, "session-1")
        await manager.subscribe_session(connection_id, "session-2")
        await manager.subscribe_session(connection_id, "session-3")

        assert manager.get_session_subscriber_count("session-1") == 1
        assert manager.get_session_subscriber_count("session-2") == 1
        assert manager.get_session_subscriber_count("session-3") == 1


class TestEventEmitter:
    """EventEmitter tests."""

    @pytest.fixture(autouse=True)
    def reset_emitter(self):
        """Reset emitter before each test."""
        reset_event_emitter()
        reset_connection_manager()
        yield
        reset_event_emitter()
        reset_connection_manager()

    @pytest.fixture
    def emitter(self):
        """Create EventEmitter."""
        return EventEmitter()

    @pytest.mark.asyncio
    async def test_emit_session_created(self, emitter):
        """Test emit session created event."""
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await emitter.manager.connect(mock_ws, session_id="new-session")

        count = await emitter.emit_session_created(
            "new-session",
            {"id": "new-session", "status": "idle"},
        )

        assert count == 1
        mock_ws.send_text.assert_called_once()
        call_args = mock_ws.send_text.call_args[0][0]
        data = json.loads(call_args)
        assert data["type"] == "sessions created"

    @pytest.mark.asyncio
    async def test_emit_streaming_chunk(self, emitter):
        """Test emit streaming chunk event."""
        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await emitter.manager.connect(mock_ws, session_id="stream-session")

        count = await emitter.emit_streaming_chunk(
            "stream-session",
            "task-123",
            "Hello, ",
            is_partial=True,
        )

        assert count == 1
        call_args = mock_ws.send_text.call_args[0][0]
        data = json.loads(call_args)
        assert data["type"] == "streaming:chunk"
        assert data["data"]["content"] == "Hello, "
        assert data["data"]["is_partial"] is True

    @pytest.mark.asyncio
    async def test_event_listener(self, emitter):
        """Test event listener."""
        received_events = []

        def listener(event):
            received_events.append(event)

        emitter.on(EventType.SESSIONS_CREATED, listener)

        # Even without WebSocket connection, listener should be called
        await emitter.emit(
            WebSocketEvent.session_created(
                "listener-session",
                {"id": "listener-session"},
            )
        )

        assert len(received_events) == 1
        assert received_events[0].type == EventType.SESSIONS_CREATED

    @pytest.mark.asyncio
    async def test_remove_event_listener(self, emitter):
        """Test remove event listener."""
        received_events = []

        def listener(event):
            received_events.append(event)

        emitter.on(EventType.TASKS_CREATED, listener)
        emitter.off(EventType.TASKS_CREATED, listener)

        await emitter.emit(
            WebSocketEvent.task_created(
                "session-1",
                "task-1",
                {"id": "task-1"},
            )
        )

        assert len(received_events) == 0


class TestWebSocketEvent:
    """WebSocketEvent tests."""

    def test_session_created_event(self):
        """Test session created event."""
        event = WebSocketEvent.session_created(
            "session-123",
            {"session_id": "session-123", "status": "idle"},
        )

        assert event.type == EventType.SESSIONS_CREATED
        assert event.session_id == "session-123"
        assert event.data["session_id"] == "session-123"

    def test_streaming_chunk_event(self):
        """Test streaming chunk event."""
        event = WebSocketEvent.streaming_chunk(
            "session-123",
            "task-456",
            "Hello world",
            is_partial=False,
        )

        assert event.type == EventType.STREAMING_CHUNK
        assert event.session_id == "session-123"
        assert event.task_id == "task-456"
        assert event.data["content"] == "Hello world"
        assert event.data["is_partial"] is False

    def test_thinking_event(self):
        """Test thinking event."""
        event = WebSocketEvent.thinking_chunk(
            "session-123",
            "task-456",
            "Analyzing the problem...",
            is_partial=True,
        )

        assert event.type == EventType.THINKING_CHUNK
        assert event.data["content"] == "Analyzing the problem..."

    def test_tool_complete_event(self):
        """Test tool complete event."""
        event = WebSocketEvent.tool_complete(
            "session-123",
            "task-456",
            "toolu_abc",
            "read_file",
            "file content here",
            is_error=False,
        )

        assert event.type == EventType.TOOL_COMPLETE
        assert event.data["tool_use_id"] == "toolu_abc"
        assert event.data["tool_name"] == "read_file"
        assert event.data["result"] == "file content here"
        assert event.data["is_error"] is False

    def test_event_to_dict(self):
        """Test event convert to dict."""
        event = WebSocketEvent.session_patched(
            "session-123",
            {"status": "running"},
        )

        d = event.to_dict()

        assert d["type"] == "sessions patched"
        assert d["session_id"] == "session-123"
        assert d["data"]["status"] == "running"
        assert "timestamp" in d
