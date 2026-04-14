"""WebSocket Connection Manager.

管理 WebSocket 連線，提供訊息廣播和分組功能。
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
    """WebSocket 連線資訊."""

    websocket: WebSocket
    user_id: Optional[str] = None
    session_ids: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionManager:
    """WebSocket Connection Manager.

    管理所有 WebSocket 連線，提供：
    - 連線/斷線管理
    - 按 session 分組
    - 廣播訊息
    - 使用者通知
    """

    def __init__(
        self,
        replay_store: Optional[RedisWebSocketReplayStore] = None,
    ):
        """初始化 Manager."""
        # 所有活躍連線
        self._connections: Dict[str, Connection] = {}
        # session_id -> connection_ids
        self._session_subscriptions: Dict[str, Set[str]] = {}
        # user_id -> connection_ids
        self._user_connections: Dict[str, Set[str]] = {}
        # 連線 ID 計數器
        self._connection_counter = 0
        # 鎖
        self._lock = asyncio.Lock()
        # WebSocket replay 儲存（可注入，便於測試）
        self._replay_store = replay_store

    @property
    def replay_store(self) -> RedisWebSocketReplayStore:
        """取得 replay store."""
        if self._replay_store is None:
            self._replay_store = get_websocket_replay_store()
        return self._replay_store

    async def _with_replay_seq(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """確保 session 訊息帶有 seq，缺失時即時寫入 replay store."""
        existing_seq = message.get("seq")
        if isinstance(existing_seq, int):
            return message

        seq = await self.replay_store.append_event(session_id, message)
        if isinstance(seq, int):
            enriched = dict(message)
            enriched["seq"] = seq
            return enriched

        # append_event 失敗時 replay_store 已自行記錄警告，這裡僅回退原訊息。
        return message

    def _generate_connection_id(self) -> str:
        """產生連線 ID."""
        self._connection_counter += 1
        return f"conn_{self._connection_counter}"

    def _enqueue_if_replay_mode(
        self,
        connection: Connection,
        message: Dict[str, Any],
    ) -> bool:
        """若連線處於 replay 模式，先把訊息放入暫存佇列."""
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
        """建立連線.

        Args:
            websocket: WebSocket 實例
            user_id: 使用者 ID
            session_id: 初始訂閱的 session ID

        Returns:
            連線 ID
        """
        await websocket.accept()

        async with self._lock:
            connection_id = self._generate_connection_id()

            connection = Connection(
                websocket=websocket,
                user_id=user_id,
            )

            self._connections[connection_id] = connection

            # 訂閱 session
            if session_id:
                connection.session_ids.add(session_id)
                if session_id not in self._session_subscriptions:
                    self._session_subscriptions[session_id] = set()
                self._session_subscriptions[session_id].add(connection_id)

            # 記錄使用者連線
            if user_id:
                if user_id not in self._user_connections:
                    self._user_connections[user_id] = set()
                self._user_connections[user_id].add(connection_id)

            return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """斷開連線.

        Args:
            connection_id: 連線 ID
        """
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return

            # 移除 session 訂閱
            for session_id in connection.session_ids:
                if session_id in self._session_subscriptions:
                    self._session_subscriptions[session_id].discard(connection_id)
                    if not self._session_subscriptions[session_id]:
                        del self._session_subscriptions[session_id]

            # 移除使用者連線
            if connection.user_id:
                if connection.user_id in self._user_connections:
                    self._user_connections[connection.user_id].discard(connection_id)
                    if not self._user_connections[connection.user_id]:
                        del self._user_connections[connection.user_id]

            # 移除連線
            del self._connections[connection_id]

    async def subscribe_session(
        self,
        connection_id: str,
        session_id: str,
    ) -> bool:
        """訂閱 session.

        Args:
            connection_id: 連線 ID
            session_id: Session ID

        Returns:
            是否成功訂閱
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
        """取消訂閱 session.

        Args:
            connection_id: 連線 ID
            session_id: Session ID

        Returns:
            是否成功取消訂閱
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
        """啟用 replay 模式（暫存即時訊息，待回放完成後再送出）."""
        async with self._lock:
            connection = self._connections.get(connection_id)
            if not connection:
                return False

            connection.metadata["replay_mode"] = True
            connection.metadata["replay_queue"] = []
            return True

    async def finish_replay_mode(self, connection_id: str) -> int:
        """結束 replay 模式並送出暫存佇列.

        為了維持順序，會在 replay_mode=True 的狀態下持續清空佇列，
        直到佇列為空才真正關閉 replay_mode。

        重要：此方法在鎖外對 connection.websocket 執行 send_text，
        因此必須確保呼叫端不會同時對同一個 connection 進行
        bypass_replay_queue=True 的發送。目前 router.py 中
        _replay_session_events 與 finish_replay_mode 為序列呼叫，
        滿足此前提。若未來調整執行順序，需加入 per-connection 發送鎖。
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
        """廣播訊息給所有連線.

        Args:
            message: 訊息內容

        Returns:
            成功發送的連線數
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
        """發送訊息給訂閱指定 session 的連線.

        Args:
            session_id: Session ID
            message: 訊息內容

        Returns:
            成功發送的連線數
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
        """發送訊息給指定使用者的所有連線.

        Args:
            user_id: 使用者 ID
            message: 訊息內容

        Returns:
            成功發送的連線數
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
        """發送訊息給指定連線.

        Args:
            connection_id: 連線 ID
            message: 訊息內容

        Returns:
            是否成功發送
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
        """取得連線數量.

        Returns:
            連線數量
        """
        return len(self._connections)

    def get_session_subscriber_count(self, session_id: str) -> int:
        """取得 session 訂閱者數量.

        Args:
            session_id: Session ID

        Returns:
            訂閱者數量
        """
        return len(self._session_subscriptions.get(session_id, set()))

    def get_user_connection_count(self, user_id: str) -> int:
        """取得使用者連線數量.

        Args:
            user_id: 使用者 ID

        Returns:
            連線數量
        """
        return len(self._user_connections.get(user_id, set()))


# 全域 Manager 實例
_global_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """取得全域 Connection Manager.

    Returns:
        Connection Manager 實例
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ConnectionManager()
    return _global_manager


def reset_connection_manager() -> None:
    """重置全域 Connection Manager.

    主要用於測試。
    """
    global _global_manager
    _global_manager = None


__all__ = [
    "Connection",
    "ConnectionManager",
    "get_connection_manager",
    "reset_connection_manager",
]
