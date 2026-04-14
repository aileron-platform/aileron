"""WebSocket replay store 單元測試."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.agent_session.websocket.replay_store import RedisWebSocketReplayStore

# 使用合法 UUID 作為 session_id（replay store 會驗證格式）
TEST_SESSION_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.mark.asyncio
async def test_append_event_assigns_seq_and_persists():
    """append_event 會分配 seq 並寫入 Redis."""
    store = RedisWebSocketReplayStore(max_events_per_session=100, ttl_seconds=300)

    mock_pipeline = AsyncMock()
    mock_pipeline.zadd = MagicMock()
    mock_pipeline.zremrangebyscore = MagicMock()
    mock_pipeline.expire = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=[1, True, True])

    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=42)
    mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

    with patch("app.modules.agent_session.websocket.replay_store.redis_manager") as mock_manager:
        mock_manager.get_redis = AsyncMock(return_value=mock_redis)

        seq = await store.append_event(
            session_id=TEST_SESSION_ID,
            payload={"type": "streaming:chunk", "data": {"content": "hello"}},
        )

    assert seq == 42
    mock_redis.incr.assert_called_once_with(f"agent_session:ws:replay:seq:{TEST_SESSION_ID}")
    mock_pipeline.zadd.assert_called_once()
    zadd_key, zadd_payload = mock_pipeline.zadd.call_args.args
    assert zadd_key == f"agent_session:ws:replay:events:{TEST_SESSION_ID}"
    stored_json = next(iter(zadd_payload.keys()))
    stored_event = json.loads(stored_json)
    assert stored_event["seq"] == 42
    assert stored_event["type"] == "streaming:chunk"


@pytest.mark.asyncio
async def test_list_events_since_filters_invalid_json():
    """list_events_since 會忽略非法 JSON."""
    store = RedisWebSocketReplayStore()

    mock_redis = AsyncMock()
    mock_redis.zrangebyscore = AsyncMock(
        return_value=[
            '{"seq": 2, "type": "thinking:chunk", "data": {"content": "A"}}',
            "not-json",
            '{"seq": 3, "type": "thinking:end", "data": {}}',
        ]
    )

    with patch("app.modules.agent_session.websocket.replay_store.redis_manager") as mock_manager:
        mock_manager.get_redis = AsyncMock(return_value=mock_redis)
        events = await store.list_events_since(TEST_SESSION_ID, last_seq=1, limit=100)

    assert [event["seq"] for event in events] == [2, 3]
    mock_redis.zrangebyscore.assert_called_once()


@pytest.mark.asyncio
async def test_append_event_rejects_invalid_session_id():
    """非 UUID 格式的 session_id 應直接回傳 None，不接觸 Redis."""
    store = RedisWebSocketReplayStore()

    result = await store.append_event(
        session_id="not-a-uuid",
        payload={"type": "streaming:chunk"},
    )
    assert result is None


@pytest.mark.asyncio
async def test_list_events_since_rejects_invalid_session_id():
    """非 UUID 格式的 session_id 應直接回傳空列表."""
    store = RedisWebSocketReplayStore()

    events = await store.list_events_since("../../../etc/passwd", last_seq=0)
    assert events == []
