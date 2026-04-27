"""WebSocket event Replay Store.

Uses Redis to store recent events for each session, supports replay after reconnection.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.redis import redis_manager

logger = logging.getLogger(__name__)


_SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_session_id(session_id: str) -> bool:
    """Validate session_id as valid UUID format to prevent Redis key injection."""
    return bool(session_id) and _SESSION_ID_PATTERN.match(session_id) is not None


class RedisWebSocketReplayStore:
    """Redis-backed WebSocket replay store."""

    def __init__(
        self,
        max_events_per_session: int = 2000,
        ttl_seconds: int = 3600,
    ):
        self.max_events_per_session = max_events_per_session
        self.ttl_seconds = ttl_seconds

    def _seq_key(self, session_id: str) -> str:
        return f"agent_session:ws:replay:seq:{session_id}"

    def _events_key(self, session_id: str) -> str:
        return f"agent_session:ws:replay:events:{session_id}"

    async def append_event(
        self,
        session_id: str,
        payload: Dict[str, Any],
    ) -> Optional[int]:
        """Append event and assign seq.

        Returns:
            Event seq; returns None if Redis is unavailable.
        """
        if not _validate_session_id(session_id):
            return None

        try:
            redis_client = await redis_manager.get_redis()
            seq = await redis_client.incr(self._seq_key(session_id))

            event_with_seq = dict(payload)
            event_with_seq["seq"] = seq
            serialized = json.dumps(event_with_seq, ensure_ascii=False)

            trim_before = max(seq - self.max_events_per_session, 0)
            pipeline = redis_client.pipeline(transaction=True)
            pipeline.zadd(self._events_key(session_id), {serialized: seq})
            if trim_before > 0:
                pipeline.zremrangebyscore(
                    self._events_key(session_id),
                    "-inf",
                    trim_before,
                )
            pipeline.expire(self._seq_key(session_id), self.ttl_seconds)
            pipeline.expire(self._events_key(session_id), self.ttl_seconds)
            await pipeline.execute()
            return int(seq)
        except Exception as exc:
            logger.warning(
                "Failed to append websocket replay event for session %s: %s",
                session_id,
                exc,
            )
            return None

    async def list_events_since(
        self,
        session_id: str,
        last_seq: int,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Query events after specified seq (in order)."""
        if not _validate_session_id(session_id):
            return []

        normalized_last_seq = max(int(last_seq), 0)
        normalized_limit = max(int(limit), 1)

        try:
            redis_client = await redis_manager.get_redis()
            raw_items = await redis_client.zrangebyscore(
                self._events_key(session_id),
                f"({normalized_last_seq}",
                "+inf",
                start=0,
                num=normalized_limit,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load websocket replay events for session %s: %s",
                session_id,
                exc,
            )
            return []

        events: List[Dict[str, Any]] = []
        for raw_item in raw_items:
            try:
                parsed = json.loads(raw_item)
                if isinstance(parsed, dict):
                    events.append(parsed)
            except json.JSONDecodeError:
                continue
        return events


_global_replay_store: Optional[RedisWebSocketReplayStore] = None


def get_websocket_replay_store() -> RedisWebSocketReplayStore:
    """Get global replay store."""
    global _global_replay_store
    if _global_replay_store is None:
        _global_replay_store = RedisWebSocketReplayStore()
    return _global_replay_store


def reset_websocket_replay_store() -> None:
    """Reset global replay store (mainly for testing)."""
    global _global_replay_store
    _global_replay_store = None


__all__ = [
    "RedisWebSocketReplayStore",
    "get_websocket_replay_store",
    "reset_websocket_replay_store",
]
