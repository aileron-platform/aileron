"""WebSocket Connection Manager.

Manages WebSocket connections, provides message broadcast and grouping functionality.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from .replay_store import RedisWebSocketReplayStore, get_websocket_replay_store

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    """WebSocket connection information."""

    websocket: WebSocket
    user_id: Optional[str] = None
    session_ids: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """WebSocket Connection Manager.

    Manages all WebSocket connections, provides:
    - Connection/disconnection management
    - Group by session
    - Broadcast messages
    - User notifications
    """

    def __init__(
        self,
        replay_store: Optional[RedisWebSocketReplayStore] = None,
    ):
        """Initialize Manager."""
        # All active connections
        self._connections: Dict[str, Connection] = {}
        # session_id -> connection_ids
        self._session_subscriptions: Dict[str, Set[str]] = {}
        # user_id -> connection_ids
        self._user_connections: Dict[str, Set[str]] = {}
        # Connection ID counter
        self._connection_counter = 0
        # Lock
        self._lock = asyncio.Lock()
        # WebSocket replay storage (injectable for testing)
        self._replay_store = replay_store

    @property
    def replay_store(self) -> RedisWebSocketReplayStore:
        """Get replay store."""
        if self._replay_store is None:
            self._replay_store = get_websocket_replay_store()
        return self._replay_store

    async def _with_replay_seq(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Ensure session messages have seq, write to replay store immediately when missing."""
        existing_seq = message.get("seq")
        if isinstance(existing_seq, int):
            return message

        seq = await self.replay_store.append_event(session_id, message)
        if isinstance(seq, int):
            enriched = dict(message)
            enriched["seq"] = seq
            return enriched

        # When append_event fails replay_store already logged warning, here just fallback to original message.
        return message

    def _generate_connection_id(self) -> str:
        """Generate connection ID."""
        self._connection_counter += 1
        return f"conn_{self._connection_counter}"

    def _enqueue_if_replay_mode(
        self,
        connection: Connection,
        message: Dict[str, Any],
    ) -> bool:
        """If connection is in replay mode, put message in temporary queue first."""
        if not connection.metadata.get("replay_mode"):
            return False

        queue = connection.metadata.get("replay_queue")
        if not isinstance(queue, list):
            queue = []
            connection.metadata["replay_queue"] = queue

        queue.append(dict(message))
        return True

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Establish connection.

        Args:
            websocket: WebSocket instance
            user_id: User ID
            session_id: Initial subscribed session ID

        Returns:
            Connection ID
        """
        await websocket.accept()

        async with self._lock:
            connection_id = self._generate_connection_id()

            connection = Connection(
                websocket=websocket,
                user_id=user_id,
            )

            self._connections[connection_id] = connection

            # Subscribe to session
            if session_id:
                connection.session_ids.add(session_id)
                if session_id not in self._session_subscriptions:
                    self._session_subscriptions[session_id] = set()
                self._session_subscriptions[session_id].add(connection_id)

            # Record user connection
            if user_id:
                if user_id not in self._user_connections:
                    self._user_connections[user_id] = set()
                self._user_connections[user_id].add(connection_id)

            return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect connection.

        Args:
            connection_id: Connection ID
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return

            # Remove session subscription
            for session_id in connection.session_ids:
                if session_id in self._session_subscriptions:
                    self._session_subscriptions[session_id].discard(connection_id)
                    if not self._session_subscriptions[session_id]:
                        del self._session_subscriptions[session_id]

            # Remove user connection
            if connection.user_id:
                if connection.user_id in self._user_connections:
                    self._user_connections[connection.user_id].discard(connection_id)
                    if not self._user_connections[connection.user_id]:
                        del self._user_connections[connection.user_id]

            # Remove connection
            del self._connections[connection_id]

    async def subscribe_session(
        self,
        connection_id: str,
        session_id: str,
    ) -> bool:
        """Subscribe to session.

        Args:
            connection_id: Connection ID
            session_id: Session ID

        Returns:
            Whether subscription succeeded
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.session_ids.add(session_id)

            if session_id not in self._session_subscriptions:
                self._session_subscriptions[session_id] = set()
            self._session_subscriptions[session_id].add(connection_id)

            return True

    async def unsubscribe_session(
        self,
        connection_id: str,
        session_id: str,
    ) -> bool:
        """Unsubscribe from session.

        Args:
            connection_id: Connection ID
            session_id: Session ID

        Returns:
            Whether unsubscription succeeded
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.session_ids.discard(session_id)

            if session_id in self._session_subscriptions:
                self._session_subscriptions[session_id].discard(connection_id)
                if not self._session_subscriptions[session_id]:
                    del self._session_subscriptions[session_id]

            return True

    async def start_replay_mode(self, connection_id: str) -> bool:
        """Enable replay mode (buffer real-time messages, send after replay completes)."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.metadata["replay_mode"] = True
            connection.metadata["replay_queue"] = []
            return True

    async def finish_replay_mode(self, connection_id: str) -> int:
        """Finish replay mode and send buffered queue.

        To maintain order, will continuously drain queue while replay_mode=True,
        only close replay_mode when queue is empty.

        Important: this method calls send_text on connection.websocket outside the lock,
        therefore must ensure caller does not simultaneously perform
        bypass_replay_queue=True sends to the same connection. Currently in router.py
        _replay_session_events and finish_replay_mode are called serially,
        satisfying this premise. If execution order changes in future, need to add per-connection send lock.
        """
        sent_count = 0

        while True:
            async with self._lock:
                connection = self._connections.get(connection_id)
                if not connection:
                    return sent_count

                queue = connection.metadata.get("replay_queue")
                if not isinstance(queue, list):
                    queue = []
                    connection.metadata["replay_queue"] = queue

                if not queue:
                    connection.metadata["replay_mode"] = False
                    connection.metadata["replay_queue"] = []
                    return sent_count

                batch = list(queue)
                connection.metadata["replay_queue"] = []

            for message in batch:
                try:
                    json_message = json.dumps(message)
                    await connection.websocket.send_text(json_message)
                    sent_count += 1
                except Exception:
                    return sent_count

    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all connections.

        Args:
            message: Message content

        Returns:
            Number of successfully sent connections
        """
        json_message = json.dumps(message)
        sent_count = 0

        for connection in list(self._connections.values()):
            try:
                if self._enqueue_if_replay_mode(connection, message):
                    sent_count += 1
                    continue
                await connection.websocket.send_text(json_message)
                sent_count += 1
            except WebSocketDisconnect:
                # Expected: connection already closed
                pass
            except Exception as exc:
                # Unexpected error: log for debugging
                logger.warning(
                    "Unexpected error broadcasting to connection: %s", exc,
                    exc_info=True,
                )

        return sent_count

    async def send_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> int:
        """Send message to connections subscribed to specified session.

        Args:
            session_id: Session ID
            message: Message content

        Returns:
            Number of successfully sent connections
        """
        connection_ids = self._session_subscriptions.get(session_id, set())
        if not connection_ids:
            return 0

        try:
            payload = await self._with_replay_seq(session_id, message)
            json_message = json.dumps(payload)
        except Exception as exc:
            logger.warning(
                "Failed to serialize websocket message for session %s: %s",
                session_id,
                exc,
            )
            return 0

        sent_count = 0

        for connection_id in list(connection_ids):
            connection = self._connections.get(connection_id)
            if connection:
                try:
                    if self._enqueue_if_replay_mode(connection, payload):
                        sent_count += 1
                        continue
                    await connection.websocket.send_text(json_message)
                    sent_count += 1
                except WebSocketDisconnect:
                    # Expected: connection already closed
                    pass
                except Exception as exc:
                    # Unexpected error: log for debugging
                    logger.warning(
                        "Unexpected error sending to session %s connection %s: %s",
                        session_id, connection_id, exc, exc_info=True,
                    )

        return sent_count

    async def send_to_user(
        self,
        user_id: str,
        message: Dict[str, Any],
    ) -> int:
        """Send message to all connections of specified user.

        Args:
            user_id: User ID
            message: Message content

        Returns:
            Number of successfully sent connections
        """
        connection_ids = self._user_connections.get(user_id, set())
        if not connection_ids:
            return 0

        json_message = json.dumps(message)
        sent_count = 0

        for connection_id in list(connection_ids):
            connection = self._connections.get(connection_id)
            if connection:
                try:
                    if self._enqueue_if_replay_mode(connection, message):
                        sent_count += 1
                        continue
                    await connection.websocket.send_text(json_message)
                    sent_count += 1
                except WebSocketDisconnect:
                    # Expected: connection already closed
                    pass
                except Exception as exc:
                    # Unexpected error: log for debugging
                    logger.warning(
                        "Unexpected error sending to user %s connection %s: %s",
                        user_id, connection_id, exc, exc_info=True,
                    )

        return sent_count

    async def send_to_connection(
        self,
        connection_id: str,
        message: Dict[str, Any],
        *,
        bypass_replay_queue: bool = False,
    ) -> bool:
        """Send message to specified connection.

        Args:
            connection_id: Connection ID
            message: Message content

        Returns:
            Whether send succeeded
        """
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        try:
            if (not bypass_replay_queue) and self._enqueue_if_replay_mode(connection, message):
                return True
            json_message = json.dumps(message)
            await connection.websocket.send_text(json_message)
            return True
        except WebSocketDisconnect:
            # Expected: connection already closed
            return False
        except Exception as exc:
            # Unexpected error: log for debugging
            logger.warning(
                "Unexpected error sending to connection %s: %s",
                connection_id, exc, exc_info=True,
            )
            return False

    def get_connection_count(self) -> int:
        """Get connection count.

        Returns:
            Connection count
        """
        return len(self._connections)

    def get_session_subscriber_count(self, session_id: str) -> int:
        """Get session subscriber count.

        Args:
            session_id: Session ID

        Returns:
            Subscriber count
        """
        return len(self._session_subscriptions.get(session_id, set()))

    def get_user_connection_count(self, user_id: str) -> int:
        """Get user connection count.

        Args:
            user_id: User ID

        Returns:
            Connection count
        """
        return len(self._user_connections.get(user_id, set()))


# Global Manager instance
_global_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get global Connection Manager.

    Returns:
        Connection Manager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ConnectionManager()
    return _global_manager


def reset_connection_manager() -> None:
    """Reset global Connection Manager.

    Mainly used for testing.
    """
    global _global_manager
    _global_manager = None


__all__ = [
    "Connection",
    "ConnectionManager",
    "get_connection_manager",
    "reset_connection_manager",
]
