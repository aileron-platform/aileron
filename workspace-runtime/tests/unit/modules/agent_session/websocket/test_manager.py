"""WebSocket ConnectionManager replay mode tests."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock
from fastapi import WebSocketDisconnect

from app.modules.agent_session.websocket.manager import (
    ConnectionManager,
    get_connection_manager,
    reset_connection_manager,
)


@pytest.mark.asyncio
async def test_replay_mode_queues_then_flushes_messages():
    """Queue messages in replay mode and send them sequentially after replay ends."""
    manager = ConnectionManager()
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    connection_id = await manager.connect(
        websocket=websocket,
        user_id="user-1",
        session_id="session-1",
    )

    started = await manager.start_replay_mode(connection_id)
    assert started is True

    queued_count = await manager.send_to_session(
        "session-1",
        {"type": "streaming:chunk", "seq": 10, "data": {"content": "A"}},
    )
    assert queued_count == 1
    websocket.send_text.assert_not_called()

    flushed_count = await manager.finish_replay_mode(connection_id)
    assert flushed_count == 1
    assert websocket.send_text.call_count == 1

    live_count = await manager.send_to_session(
        "session-1",
        {"type": "streaming:chunk", "seq": 11, "data": {"content": "B"}},
    )
    assert live_count == 1
    assert websocket.send_text.call_count == 2


@pytest.mark.asyncio
async def test_send_to_session_appends_seq_when_missing():
    """Session events missing seq should have seq appended before sending."""
    replay_store = AsyncMock()
    replay_store.append_event = AsyncMock(return_value=42)

    manager = ConnectionManager(replay_store=replay_store)
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    await manager.connect(
        websocket=websocket,
        user_id="user-1",
        session_id="session-1",
    )

    original_message = {
        "type": "thinking:chunk",
        "session_id": "session-1",
        "task_id": "task-1",
        "data": {"content": "hello", "is_partial": True, "message_id": "msg-1"},
    }

    sent_count = await manager.send_to_session("session-1", original_message)

    assert sent_count == 1
    replay_store.append_event.assert_awaited_once_with("session-1", original_message)

    sent_payload = json.loads(websocket.send_text.await_args.args[0])
    assert sent_payload["seq"] == 42
    assert sent_payload["type"] == "thinking:chunk"


@pytest.mark.asyncio
async def test_send_to_session_preserves_existing_seq():
    """Events that already have seq should not write to replay store again."""
    replay_store = AsyncMock()
    replay_store.append_event = AsyncMock()

    manager = ConnectionManager(replay_store=replay_store)
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()

    await manager.connect(
        websocket=websocket,
        user_id="user-1",
        session_id="session-1",
    )

    message_with_seq = {
        "type": "streaming:chunk",
        "session_id": "session-1",
        "task_id": "task-1",
        "seq": 99,
        "data": {"content": "A", "is_partial": True, "message_id": "msg-1"},
    }

    sent_count = await manager.send_to_session("session-1", message_with_seq)

    assert sent_count == 1
    replay_store.append_event.assert_not_awaited()

    sent_payload = json.loads(websocket.send_text.await_args.args[0])
    assert sent_payload["seq"] == 99


@pytest.mark.asyncio
async def test_connect_disconnect_subscribe_and_unsubscribe_counts():
    manager = ConnectionManager()
    websocket = AsyncMock()
    websocket.accept = AsyncMock()

    connection_id = await manager.connect(websocket=websocket, user_id="user-1", session_id="session-1")

    assert manager.get_connection_count() == 1
    assert manager.get_session_subscriber_count("session-1") == 1
    assert manager.get_user_connection_count("user-1") == 1

    assert await manager.subscribe_session(connection_id, "session-2") is True
    assert manager.get_session_subscriber_count("session-2") == 1
    assert await manager.unsubscribe_session(connection_id, "session-2") is True
    assert manager.get_session_subscriber_count("session-2") == 0

    await manager.disconnect(connection_id)
    assert manager.get_connection_count() == 0
    assert manager.get_session_subscriber_count("session-1") == 0
    assert manager.get_user_connection_count("user-1") == 0


@pytest.mark.asyncio
async def test_subscribe_unsubscribe_and_replay_mode_return_false_for_missing_connection():
    manager = ConnectionManager()

    assert await manager.subscribe_session("missing", "session-1") is False
    assert await manager.unsubscribe_session("missing", "session-1") is False
    assert await manager.start_replay_mode("missing") is False
    assert await manager.finish_replay_mode("missing") == 0
    await manager.disconnect("missing")


@pytest.mark.asyncio
async def test_finish_replay_mode_stops_on_send_error():
    manager = ConnectionManager()
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock(side_effect=RuntimeError("boom"))

    connection_id = await manager.connect(websocket=websocket, session_id="session-1")
    await manager.start_replay_mode(connection_id)
    await manager.send_to_connection(connection_id, {"type": "queued"})

    flushed = await manager.finish_replay_mode(connection_id)

    assert flushed == 0


@pytest.mark.asyncio
async def test_broadcast_and_send_helpers_handle_disconnects_and_replay_queue():
    manager = ConnectionManager()
    live_socket = AsyncMock()
    live_socket.accept = AsyncMock()
    live_socket.send_text = AsyncMock()
    replay_socket = AsyncMock()
    replay_socket.accept = AsyncMock()
    replay_socket.send_text = AsyncMock(side_effect=WebSocketDisconnect())

    live_conn = await manager.connect(websocket=live_socket, user_id="user-1", session_id="session-1")
    replay_conn = await manager.connect(websocket=replay_socket, user_id="user-1", session_id="session-1")
    await manager.start_replay_mode(replay_conn)

    assert await manager.broadcast({"type": "notice"}) == 2
    assert live_socket.send_text.await_count == 1
    assert replay_socket.send_text.await_count == 0

    assert await manager.send_to_user("user-1", {"type": "user"}) == 2
    assert await manager.send_to_connection(replay_conn, {"type": "queued"}) is True
    assert await manager.send_to_connection(replay_conn, {"type": "forced"}, bypass_replay_queue=True) is False
    assert await manager.send_to_connection("missing", {"type": "none"}) is False

    queued = manager._connections[replay_conn].metadata["replay_queue"]
    assert len(queued) == 3
    assert queued[0]["type"] == "notice"


@pytest.mark.asyncio
async def test_send_to_session_returns_zero_on_missing_subscription_and_serialization_error():
    replay_store = AsyncMock()
    replay_store.append_event = AsyncMock(return_value=1)
    manager = ConnectionManager(replay_store=replay_store)

    assert await manager.send_to_session("missing", {"type": "x"}) == 0

    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    await manager.connect(websocket=websocket, session_id="session-1")

    assert await manager.send_to_session("session-1", {"type": "bad", "payload": {1, 2, 3}}) == 0


def test_global_connection_manager_reset():
    reset_connection_manager()
    first = get_connection_manager()
    second = get_connection_manager()

    assert first is second

    reset_connection_manager()
    third = get_connection_manager()
    assert third is not first
