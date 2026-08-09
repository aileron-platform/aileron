from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.modules.runtime_control.state import (
    RuntimeDrainingError,
    get_runtime_admission_state,
)


@dataclass
class ThreadConnection:
    websocket: WebSocket
    workspace_id: str
    user_id: str


@dataclass
class PendingInvalidation:
    user_id: str | None
    workspace_id: str
    thread_id: str
    type_: str
    status: str | None = None
    thread_version: int | None = None
    created_item_ids: set[str] | None = None
    changed_item_ids: set[str] | None = None
    turns: dict[str, dict[str, Any]] | None = None
    executions: dict[str, dict[str, Any]] | None = None
    refresh_latest: bool = False


class ThreadConnectionManager:
    """Tracks thread invalidation websocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, ThreadConnection] = {}
        self._workspace_connections: dict[str, set[str]] = {}
        self._user_workspace_connections: dict[tuple[str, str], set[str]] = {}
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(
        self,
        websocket: WebSocket,
        *,
        workspace_id: str,
        user_id: str,
        subprotocol: str | None = None,
    ) -> str:
        try:
            get_runtime_admission_state().require_accepting()
        except RuntimeDrainingError as exc:
            await websocket.close(code=4423, reason=exc.error_code)
            raise
        if subprotocol is None:
            await websocket.accept()
        else:
            await websocket.accept(subprotocol=subprotocol)
        connection_id = uuid4().hex
        async with self._lock:
            if get_runtime_admission_state().is_draining:
                await websocket.close(
                    code=1012,
                    reason="WORKSPACE_RUNTIME_DRAINING",
                )
                raise RuntimeDrainingError()
            self._connections[connection_id] = ThreadConnection(
                websocket=websocket,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._workspace_connections.setdefault(workspace_id, set()).add(
                connection_id
            )
            self._user_workspace_connections.setdefault(
                (workspace_id, user_id), set()
            ).add(connection_id)
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        async with self._lock:
            self._remove_connection(connection_id)

    async def close_all(self) -> None:
        """Close every actor WebSocket in this shared Runtime generation."""

        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
            self._workspace_connections.clear()
            self._user_workspace_connections.clear()
        results = await asyncio.gather(
            *(
                connection.websocket.close(
                    code=1012,
                    reason="WORKSPACE_RUNTIME_DRAINING",
                )
                for connection in connections
            ),
            return_exceptions=True,
        )
        if any(isinstance(result, BaseException) for result in results):
            raise RuntimeError("thread_connection_drain_incomplete")

    async def send_to_user(
        self, *, workspace_id: str, user_id: str, message: dict[str, Any]
    ) -> int:
        connection_ids = self._user_workspace_connections.get(
            (workspace_id, user_id), set()
        )
        return await self._send_to_connections(connection_ids, message)

    async def broadcast_workspace(
        self, *, workspace_id: str, message: dict[str, Any]
    ) -> int:
        connection_ids = self._workspace_connections.get(workspace_id, set())
        return await self._send_to_connections(connection_ids, message)

    async def _send_to_connections(
        self, connection_ids: set[str], message: dict[str, Any]
    ) -> int:
        sent = 0
        stale_connection_ids: list[str] = []
        for connection_id in list(connection_ids):
            connection = self._connections.get(connection_id)
            if connection is None:
                continue
            try:
                await connection.websocket.send_json(message)
                sent += 1
            except WebSocketDisconnect:
                stale_connection_ids.append(connection_id)
            except Exception:
                stale_connection_ids.append(connection_id)

        if stale_connection_ids:
            async with self._lock:
                for connection_id in stale_connection_ids:
                    self._remove_connection(connection_id)

        return sent

    def _remove_connection(self, connection_id: str) -> None:
        connection = self._connections.pop(connection_id, None)
        if connection is None:
            return

        workspace_connections = self._workspace_connections.get(connection.workspace_id)
        if workspace_connections is not None:
            workspace_connections.discard(connection_id)
            if not workspace_connections:
                self._workspace_connections.pop(connection.workspace_id, None)

        user_key = (connection.workspace_id, connection.user_id)
        user_connections = self._user_workspace_connections.get(user_key)
        if user_connections is not None:
            user_connections.discard(connection_id)
            if not user_connections:
                self._user_workspace_connections.pop(user_key, None)


class InvalidationEmitter:
    """Coalesces per-thread invalidation signals before broadcasting."""

    def __init__(
        self,
        manager: ThreadConnectionManager,
        *,
        coalesce_ms: int = 150,
    ) -> None:
        self.manager = manager
        self.coalesce_seconds = coalesce_ms / 1000
        self._pending: dict[tuple[str | None, str, str, str], PendingInvalidation] = {}
        self._flush_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._timeline_item_limit = 200

    async def emit(
        self,
        user_id: str | None,
        workspace_id: str,
        thread_id: str,
        type_: str,
        status: str | None = None,
        *,
        thread_version: int | None = None,
        created_item_ids: list[str] | None = None,
        changed_item_ids: list[str] | None = None,
        turns: list[dict[str, Any]] | None = None,
        executions: list[dict[str, Any]] | None = None,
        refresh_latest: bool = False,
    ) -> None:
        key = (user_id, workspace_id, thread_id, type_)
        async with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                pending = PendingInvalidation(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    thread_id=thread_id,
                    type_=type_,
                    status=status,
                    thread_version=thread_version,
                    created_item_ids=set(created_item_ids or []),
                    changed_item_ids=set(changed_item_ids or []),
                    turns=self._metadata_by_id(turns),
                    executions=self._metadata_by_id(executions),
                    refresh_latest=refresh_latest,
                )
                self._pending[key] = pending
            else:
                pending.status = status or pending.status
                pending.thread_version = max(
                    pending.thread_version or 0,
                    thread_version or 0,
                )
                pending.created_item_ids = (pending.created_item_ids or set()).union(
                    created_item_ids or []
                )
                pending.changed_item_ids = (pending.changed_item_ids or set()).union(
                    changed_item_ids or []
                )
                pending.turns = self._merge_metadata(pending.turns, turns)
                pending.executions = self._merge_metadata(
                    pending.executions, executions
                )
                pending.refresh_latest = pending.refresh_latest or refresh_latest
            item_count = len(pending.created_item_ids or set()) + len(
                pending.changed_item_ids or set()
            )
            if item_count > self._timeline_item_limit:
                pending.created_item_ids = set()
                pending.changed_item_ids = set()
                pending.refresh_latest = True
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._delayed_flush())

    async def flush(self) -> None:
        async with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()

        for event in pending:
            await self._broadcast(event)

    async def _delayed_flush(self) -> None:
        await asyncio.sleep(self.coalesce_seconds)
        await self.flush()

    async def _broadcast(self, event: PendingInvalidation) -> None:
        payload: dict[str, Any] = {
            "threadId": event.thread_id,
            "type": event.type_,
        }
        if event.type_ == "timeline_updated":
            payload.update(
                {
                    "threadVersion": event.thread_version or 0,
                    "createdItemIds": sorted(event.created_item_ids or set()),
                    "changedItemIds": sorted(event.changed_item_ids or set()),
                    "turns": list((event.turns or {}).values()),
                    "executions": list((event.executions or {}).values()),
                    "refreshLatest": event.refresh_latest,
                }
            )
        if event.type_ == "status_updated":
            payload["status"] = event.status

        if event.user_id is None:
            await self.manager.broadcast_workspace(
                workspace_id=event.workspace_id,
                message=payload,
            )
            return

        await self.manager.send_to_user(
            workspace_id=event.workspace_id,
            user_id=event.user_id,
            message=payload,
        )

    @staticmethod
    def _metadata_by_id(
        values: list[dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        return {
            str(value["id"]): value
            for value in values or []
            if value.get("id") is not None
        }

    @classmethod
    def _merge_metadata(
        cls,
        current: dict[str, dict[str, Any]] | None,
        incoming: list[dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]]:
        merged = dict(current or {})
        for item_id, value in cls._metadata_by_id(incoming).items():
            existing = merged.get(item_id)
            if existing is None or int(value.get("version", 0)) >= int(
                existing.get("version", 0)
            ):
                merged[item_id] = value
        return merged


_connection_manager = ThreadConnectionManager()
_invalidation_emitter = InvalidationEmitter(_connection_manager)


def get_thread_connection_manager() -> ThreadConnectionManager:
    return _connection_manager


def get_thread_invalidation_emitter() -> InvalidationEmitter:
    return _invalidation_emitter
