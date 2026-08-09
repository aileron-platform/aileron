from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.thread.invalidation_emitter import (
    InvalidationEmitter,
    ThreadConnectionManager,
)
from app.modules.thread.lifecycle import ThreadService
from tests.unit.modules.thread.db_fixture import drop_thread_tables, reset_thread_tables


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.accepted = False
        self.accepted_subprotocol: str | None = None
        self.messages: list[dict[str, Any]] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted = True
        self.accepted_subprotocol = subprotocol

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.fail:
            raise WebSocketDisconnect()
        self.messages.append(message)

    async def close(self, *, code: int, reason: str) -> None:
        self.closed = (code, reason)


class CloseFailingWebSocket(FakeWebSocket):
    async def close(self, *, code: int, reason: str) -> None:
        raise RuntimeError("close failed")


@pytest.mark.asyncio
async def test_connection_selects_only_the_application_subprotocol() -> None:
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(
        websocket,
        workspace_id="workspace-a",
        user_id="user-a",
        subprotocol="aileron-thread-v1",
    )

    assert websocket.accepted is True
    assert websocket.accepted_subprotocol == "aileron-thread-v1"


@pytest.mark.asyncio
async def test_full_drain_closes_every_actor_connection() -> None:
    manager = ThreadConnectionManager()
    user_a = FakeWebSocket()
    user_b = FakeWebSocket()
    await manager.connect(user_a, workspace_id="workspace-a", user_id="user-a")
    await manager.connect(user_b, workspace_id="workspace-a", user_id="user-b")

    await manager.close_all()

    assert manager.connection_count == 0
    assert user_a.closed == (1012, "WORKSPACE_RUNTIME_DRAINING")
    assert user_b.closed == (1012, "WORKSPACE_RUNTIME_DRAINING")


@pytest.mark.asyncio
async def test_full_drain_reports_failed_connection_close_after_clearing_registry() -> (
    None
):
    manager = ThreadConnectionManager()
    broken = CloseFailingWebSocket()
    healthy = FakeWebSocket()
    await manager.connect(broken, workspace_id="workspace-a", user_id="user-a")
    await manager.connect(healthy, workspace_id="workspace-a", user_id="user-b")

    with pytest.raises(RuntimeError, match="thread_connection_drain_incomplete"):
        await manager.close_all()

    assert manager.connection_count == 0
    assert healthy.closed == (1012, "WORKSPACE_RUNTIME_DRAINING")


@dataclass
class DestroyTrackingRunner:
    destroyed_threads: list[str] = field(default_factory=list)

    def reserve(self) -> str:
        return "session-1"

    def adopt_reservation(self, execution_id: str) -> None:
        return None

    async def start(self, request: Any, on_event: Any, execution_id: str) -> None:
        return None

    async def stop(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return False

    async def destroy_thread(self, thread_id: str) -> None:
        self.destroyed_threads.append(thread_id)


def make_capabilities() -> dict:
    return {
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8"],
                "default_model": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            }
        ],
        "default_tool": "claude",
    }


@pytest.fixture
async def invalidation_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as conn:
        await reset_thread_tables(conn)

    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as conn:
        await drop_thread_tables(conn)


@pytest.mark.asyncio
async def test_emitter_coalesces_messages_per_thread() -> None:
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, workspace_id="workspace-a", user_id="user-a")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)

    for _ in range(5):
        await emitter.emit("user-a", "workspace-a", "thread-a", "messages_updated")

    await asyncio.sleep(0.05)

    assert websocket.messages == [{"threadId": "thread-a", "type": "messages_updated"}]


@pytest.mark.asyncio
async def test_emitter_preserves_distinct_types_and_latest_status() -> None:
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, workspace_id="workspace-a", user_id="user-a")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)

    await emitter.emit("user-a", "workspace-a", "thread-a", "messages_updated")
    await emitter.emit("user-a", "workspace-a", "thread-a", "status_updated", "queued")
    await emitter.emit("user-a", "workspace-a", "thread-a", "status_updated", "working")

    await asyncio.sleep(0.05)

    assert {"threadId": "thread-a", "type": "messages_updated"} in websocket.messages
    assert {
        "threadId": "thread-a",
        "type": "status_updated",
        "status": "working",
    } in websocket.messages
    assert len(websocket.messages) == 2


@pytest.mark.asyncio
async def test_timeline_invalidation_is_bounded_and_keeps_latest_metadata() -> None:
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, workspace_id="workspace-a", user_id="user-a")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)

    await emitter.emit(
        "user-a",
        "workspace-a",
        "thread-a",
        "timeline_updated",
        created_item_ids=[str(index) for index in range(201)],
        turns=[{"id": "turn-a", "version": 1, "status": "running"}],
    )
    await emitter.emit(
        "user-a",
        "workspace-a",
        "thread-a",
        "timeline_updated",
        turns=[{"id": "turn-a", "version": 2, "status": "complete"}],
    )
    await asyncio.sleep(0.05)

    assert websocket.messages == [
        {
            "threadId": "thread-a",
            "type": "timeline_updated",
            "threadVersion": 0,
            "createdItemIds": [],
            "changedItemIds": [],
            "turns": [{"id": "turn-a", "version": 2, "status": "complete"}],
            "executions": [],
            "refreshLatest": True,
        }
    ]


@pytest.mark.asyncio
async def test_manager_removes_disconnected_clients_without_blocking_other_connections() -> (
    None
):
    manager = ThreadConnectionManager()
    broken = FakeWebSocket(fail=True)
    healthy = FakeWebSocket()
    await manager.connect(broken, workspace_id="workspace-a", user_id="user-a")
    await manager.connect(healthy, workspace_id="workspace-a", user_id="user-a")

    sent = await manager.send_to_user(
        workspace_id="workspace-a",
        user_id="user-a",
        message={"threadId": "thread-a", "type": "messages_updated"},
    )

    assert sent == 1
    assert healthy.messages == [{"threadId": "thread-a", "type": "messages_updated"}]
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_user_targeted_emit_and_workspace_broadcast_are_scoped_correctly() -> (
    None
):
    manager = ThreadConnectionManager()
    user_a = FakeWebSocket()
    user_b = FakeWebSocket()
    await manager.connect(user_a, workspace_id="workspace-a", user_id="user-a")
    await manager.connect(user_b, workspace_id="workspace-a", user_id="user-b")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)

    await emitter.emit("user-a", "workspace-a", "thread-a", "messages_updated")
    await asyncio.sleep(0.05)
    assert user_a.messages == [{"threadId": "thread-a", "type": "messages_updated"}]
    assert user_b.messages == []

    await emitter.emit(None, "workspace-a", "thread-auto", "status_updated", "working")
    await asyncio.sleep(0.05)
    assert user_a.messages[-1] == {
        "threadId": "thread-auto",
        "type": "status_updated",
        "status": "working",
    }
    assert user_b.messages[-1] == {
        "threadId": "thread-auto",
        "type": "status_updated",
        "status": "working",
    }


@pytest.mark.asyncio
async def test_thread_service_emits_create_patch_and_archive_events(
    invalidation_session: AsyncSession,
) -> None:
    await CapabilitiesStore().put(
        invalidation_session, "workspace-a", make_capabilities()
    )
    await invalidation_session.commit()
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, workspace_id="workspace-a", user_id="user-a")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)
    runner = DestroyTrackingRunner()
    service = ThreadService(
        invalidation_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=emitter,
    )

    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await service.update_draft(
        thread_id=draft.id,
        user_id="user-a",
        patch={"draft_message": {"text": "hello", "attachments": []}},
    )
    await service.archive_thread(thread_id=draft.id, user_id="user-a")
    await asyncio.sleep(0.05)

    assert {"threadId": draft.id, "type": "thread_created"} in websocket.messages
    assert {"threadId": draft.id, "type": "messages_updated"} in websocket.messages
    assert {"threadId": draft.id, "type": "archived"} in websocket.messages
    assert runner.destroyed_threads == [draft.id]


@pytest.mark.asyncio
async def test_thread_service_delete_emits_deleted_event(
    invalidation_session: AsyncSession,
) -> None:
    await CapabilitiesStore().put(
        invalidation_session, "workspace-a", make_capabilities()
    )
    await invalidation_session.commit()
    manager = ThreadConnectionManager()
    websocket = FakeWebSocket()
    await manager.connect(websocket, workspace_id="workspace-a", user_id="user-a")
    emitter = InvalidationEmitter(manager, coalesce_ms=20)
    runner = DestroyTrackingRunner()
    service = ThreadService(
        invalidation_session,
        workspace_id="workspace-a",
        runner=runner,
        invalidation_sink=emitter,
    )

    draft = await service.create_draft(
        user_id="user-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        claude_mode="execute",
    )
    await service.delete_thread(thread_id=draft.id, user_id="user-a")
    await asyncio.sleep(0.05)

    assert {"threadId": draft.id, "type": "deleted"} in websocket.messages
    assert runner.destroyed_threads == [draft.id]
