from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.thread.claude_sdk_client_manager import (
    ClaudeSdkClientManager,
)
from app.modules.thread.execution import AgentExecutionRequest


@dataclass
class FakeClaudeClient:
    options: Any
    connected: bool = False
    disconnected: bool = False
    interrupted: bool = False
    prompts: list[str] = field(default_factory=list)

    async def connect(self) -> None:
        self.connected = True

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)

    def receive_response(self) -> Any:
        async def stream():
            if False:
                yield None

        return stream()

    async def interrupt(self) -> None:
        self.interrupted = True

    async def disconnect(self) -> None:
        self.disconnected = True


@dataclass
class ControllableClaudeClient(FakeClaudeClient):
    block_queries: bool = False
    query_error: BaseException | None = None
    disconnect_error: BaseException | None = None
    query_started: asyncio.Event = field(default_factory=asyncio.Event)
    release_query: asyncio.Event = field(default_factory=asyncio.Event)

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)
        if not self.block_queries:
            return
        self.query_started.set()
        await self.release_query.wait()
        if self.query_error is not None:
            raise self.query_error

    async def disconnect(self) -> None:
        self.disconnected = True
        if self.disconnect_error is not None:
            raise self.disconnect_error


@dataclass
class LateConnectingClaudeClient(FakeClaudeClient):
    connect_started: asyncio.Event = field(default_factory=asyncio.Event)
    release_connect: asyncio.Event = field(default_factory=asyncio.Event)
    disconnect_calls: int = 0
    transport_open: bool = False

    async def connect(self) -> None:
        self.connect_started.set()
        await self.release_connect.wait()
        self.connected = True
        self.disconnected = False
        self.transport_open = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.disconnected = True
        self.transport_open = False


@dataclass
class BlockingInterruptClaudeClient(FakeClaudeClient):
    interrupt_started: asyncio.Event = field(default_factory=asyncio.Event)
    release_interrupt: asyncio.Event = field(default_factory=asyncio.Event)
    disconnect_calls: int = 0

    async def interrupt(self) -> None:
        self.interrupted = True
        self.interrupt_started.set()
        await self.release_interrupt.wait()

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        await super().disconnect()


@dataclass
class BlockingDisconnectClaudeClient(FakeClaudeClient):
    disconnect_started: asyncio.Event = field(default_factory=asyncio.Event)
    release_disconnect: asyncio.Event = field(default_factory=asyncio.Event)
    disconnect_calls: int = 0

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.disconnect_started.set()
        await self.release_disconnect.wait()
        await super().disconnect()


def request(**overrides: object) -> AgentExecutionRequest:
    values = {
        "thread_id": "thread-1",
        "agentic_tool": "claude",
        "model": "claude-sonnet-4-5-20250929",
        "claude_mode": None,
        "prompt_text": "hello",
        "permission_mode": None,
        "git_context_id": "ctx-1",
        "agent_resume_id": None,
        "attachments": [],
    }
    values.update(overrides)
    return AgentExecutionRequest(**values)


@pytest.mark.asyncio
async def test_reused_query_claim_prevents_eviction_and_concurrent_start(
    tmp_path,
) -> None:
    clients: list[ControllableClaudeClient] = []
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: clients.append(ControllableClaudeClient(options))
        or clients[-1],
        idle_ttl_seconds=5,
    )
    first_execution_id = manager.reserve()
    first = await manager.start_turn(
        thread_id="thread-1",
        execution_id=first_execution_id,
        request=request(prompt_text="first"),
        cwd=tmp_path,
        now=10,
    )
    await manager.finish_execution(first_execution_id, now=20)

    clients[0].block_queries = True
    second_execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="thread-1",
            execution_id=second_execution_id,
            request=request(prompt_text="second"),
            cwd=tmp_path,
            now=30,
        )
    )
    await asyncio.wait_for(clients[0].query_started.wait(), timeout=1)

    assert manager.is_alive(second_execution_id) is True
    assert manager._execution_to_thread == {second_execution_id: "thread-1"}
    assert await manager.evict_idle(now=1_000) == 0
    assert clients[0].disconnected is False

    competing_execution_id = manager.reserve()
    with pytest.raises(ValueError, match="thread_execution_active"):
        await manager.start_turn(
            thread_id="thread-1",
            execution_id=competing_execution_id,
            request=request(prompt_text="competing"),
            cwd=tmp_path,
        )
    assert manager.is_alive(competing_execution_id) is False

    clients[0].release_query.set()
    second = await start_task
    assert first.client is second.client
    assert clients[0].prompts == ["first", "second"]

    await manager.finish_execution(second_execution_id, now=30)
    assert await manager.evict_idle(now=34) == 0
    assert await manager.evict_idle(now=35) == 1
    assert clients[0].disconnected is True


@pytest.mark.asyncio
async def test_query_failure_rolls_back_without_masking_disconnect_error(
    tmp_path,
) -> None:
    query_error = RuntimeError("query startup failed")
    client = ControllableClaudeClient(
        options=None,
        block_queries=True,
        query_error=query_error,
        disconnect_error=RuntimeError("disconnect failed"),
    )
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: client,
    )
    execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="thread-1",
            execution_id=execution_id,
            request=request(),
            cwd=tmp_path,
        )
    )
    await asyncio.wait_for(client.query_started.wait(), timeout=1)

    assert await manager.evict_idle(now=1_000) == 0
    client.release_query.set()
    with pytest.raises(RuntimeError, match="query startup failed") as raised:
        await start_task

    assert raised.value is query_error
    assert client.disconnected is True
    assert manager.is_alive(execution_id) is False
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager._reserved == set()


@pytest.mark.asyncio
async def test_cancelled_query_rolls_back_and_disconnects(tmp_path) -> None:
    client = ControllableClaudeClient(options=None, block_queries=True)
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: client,
    )
    execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="thread-1",
            execution_id=execution_id,
            request=request(),
            cwd=tmp_path,
        )
    )
    await asyncio.wait_for(client.query_started.wait(), timeout=1)

    start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start_task

    assert client.disconnected is True
    assert manager.is_alive(execution_id) is False
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager._reserved == set()


@pytest.mark.asyncio
async def test_replaced_state_rollback_removes_only_original_execution_mapping(
    tmp_path,
) -> None:
    original_client = ControllableClaudeClient(options=None, block_queries=True)
    replacement_client = ControllableClaudeClient(options=None)
    claude_clients = iter([original_client, replacement_client])
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: next(claude_clients),
    )
    original_execution_id = manager.reserve()
    original_start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="thread-1",
            execution_id=original_execution_id,
            request=request(prompt_text="original"),
            cwd=tmp_path,
        )
    )
    await asyncio.wait_for(original_client.query_started.wait(), timeout=1)

    original_state = manager._states.pop("thread-1")
    await original_client.disconnect()
    replacement_execution_id = manager.reserve()
    replacement_start = await manager.start_turn(
        thread_id="thread-1",
        execution_id=replacement_execution_id,
        request=request(prompt_text="replacement"),
        cwd=tmp_path,
    )
    replacement_state = manager._states["thread-1"]
    assert manager._execution_to_thread == {
        original_execution_id: "thread-1",
        replacement_execution_id: "thread-1",
    }

    original_client.release_query.set()
    with pytest.raises(
        RuntimeError, match="execution_stopped_during_startup"
    ) as raised:
        await original_start_task

    assert str(raised.value) == "execution_stopped_during_startup"
    assert manager._states == {"thread-1": replacement_state}
    assert manager._execution_to_thread == {replacement_execution_id: "thread-1"}
    assert original_state.active_execution_id is None
    assert replacement_state.active_execution_id == replacement_execution_id
    assert replacement_start.client is replacement_client
    assert replacement_client.disconnected is False
    assert manager.is_alive(original_execution_id) is False
    assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.asyncio
async def test_stop_during_connect_recleans_original_and_preserves_successor(
    tmp_path,
) -> None:
    original_client = LateConnectingClaudeClient(options=None)
    replacement_client = FakeClaudeClient(options=None)
    clients = iter([original_client, replacement_client])
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: next(clients),
    )
    original_execution_id = manager.reserve()
    original_start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="thread-1",
            execution_id=original_execution_id,
            request=request(prompt_text="original"),
            cwd=tmp_path,
        )
    )
    await asyncio.wait_for(original_client.connect_started.wait(), timeout=1)
    original_state = manager._states["thread-1"]

    await manager.stop_execution(original_execution_id)
    assert original_client.disconnect_calls == 1
    assert original_client.transport_open is False

    replacement_execution_id = manager.reserve()
    replacement_start = await manager.start_turn(
        thread_id="thread-1",
        execution_id=replacement_execution_id,
        request=request(prompt_text="replacement"),
        cwd=tmp_path,
    )
    replacement_state = manager._states["thread-1"]

    original_client.release_connect.set()
    with pytest.raises(RuntimeError, match="execution_stopped_during_startup"):
        await original_start_task

    assert original_client.disconnect_calls == 2
    assert original_client.transport_open is False
    assert original_client.disconnected is True
    assert original_state.active_execution_id is None
    assert manager._states == {"thread-1": replacement_state}
    assert manager._execution_to_thread == {replacement_execution_id: "thread-1"}
    assert replacement_state.active_execution_id == replacement_execution_id
    assert replacement_start.client is replacement_client
    assert replacement_client.disconnected is False
    assert manager.is_alive(original_execution_id) is False
    assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.asyncio
async def test_stale_stop_does_not_disconnect_successor_on_same_state(tmp_path) -> None:
    client = BlockingInterruptClaudeClient(options=None)
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: client,
    )
    original_execution_id = manager.reserve()
    original_start = await manager.start_turn(
        thread_id="thread-1",
        execution_id=original_execution_id,
        request=request(prompt_text="original"),
        cwd=tmp_path,
    )
    original_state = manager._states["thread-1"]

    stop_task = asyncio.create_task(manager.stop_execution(original_execution_id))
    await asyncio.wait_for(client.interrupt_started.wait(), timeout=1)
    await manager.finish_execution(original_execution_id)

    successor_execution_id = manager.reserve()
    successor_start = await manager.start_turn(
        thread_id="thread-1",
        execution_id=successor_execution_id,
        request=request(prompt_text="successor"),
        cwd=tmp_path,
    )
    assert manager._states["thread-1"] is original_state

    client.release_interrupt.set()
    await stop_task

    assert original_start.client is successor_start.client
    assert client.disconnect_calls == 0
    assert client.disconnected is False
    assert manager._states == {"thread-1": original_state}
    assert manager._execution_to_thread == {successor_execution_id: "thread-1"}
    assert original_state.active_execution_id == successor_execution_id
    assert manager.is_alive(original_execution_id) is False
    assert manager.is_alive(successor_execution_id) is True


@pytest.mark.asyncio
async def test_reuses_idle_client_for_same_thread_and_disconnects_on_destroy(
    tmp_path,
) -> None:
    clients: list[FakeClaudeClient] = []
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: clients.append(FakeClaudeClient(options))
        or clients[-1],
    )
    first_execution = manager.reserve()

    first = await manager.start_turn(
        thread_id="thread-1",
        execution_id=first_execution,
        request=request(prompt_text="first"),
        cwd=tmp_path,
        now=10,
    )
    await manager.finish_execution(first_execution, now=20)
    second_execution = manager.reserve()
    second = await manager.start_turn(
        thread_id="thread-1",
        execution_id=second_execution,
        request=request(prompt_text="second"),
        cwd=tmp_path,
        now=30,
    )

    assert first.client is second.client
    assert len(clients) == 1
    assert clients[0].prompts == ["first", "second"]

    await manager.destroy_thread("thread-1")

    assert clients[0].disconnected is True
    assert manager.is_alive(second_execution) is False


@pytest.mark.asyncio
async def test_start_rejects_second_active_turn_for_same_thread(tmp_path) -> None:
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=FakeClaudeClient,
    )
    first_execution = manager.reserve()
    await manager.start_turn(
        thread_id="thread-1",
        execution_id=first_execution,
        request=request(),
        cwd=tmp_path,
    )
    second_execution = manager.reserve()

    with pytest.raises(ValueError, match="thread_execution_active"):
        await manager.start_turn(
            thread_id="thread-1",
            execution_id=second_execution,
            request=request(prompt_text="follow-up"),
            cwd=tmp_path,
        )


@pytest.mark.asyncio
async def test_stop_interrupts_disconnects_and_clears_liveness(tmp_path) -> None:
    clients: list[FakeClaudeClient] = []
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: clients.append(FakeClaudeClient(options))
        or clients[-1],
    )
    execution_id = manager.reserve()
    await manager.start_turn(
        thread_id="thread-1",
        execution_id=execution_id,
        request=request(),
        cwd=tmp_path,
    )

    await manager.stop_execution(execution_id)

    assert clients[0].interrupted is True
    assert clients[0].disconnected is True
    assert manager.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_evict_idle_disconnects_inactive_clients(tmp_path) -> None:
    clients: list[FakeClaudeClient] = []
    manager = ClaudeSdkClientManager(
        workspace_id="workspace-1",
        client_factory=lambda options: clients.append(FakeClaudeClient(options))
        or clients[-1],
        idle_ttl_seconds=5,
    )
    execution_id = manager.reserve()
    await manager.start_turn(
        thread_id="thread-1",
        execution_id=execution_id,
        request=request(),
        cwd=tmp_path,
        now=10,
    )
    await manager.finish_execution(execution_id, now=10)

    assert await manager.evict_idle(now=14) == 0
    assert clients[0].disconnected is False
    assert await manager.evict_idle(now=15) == 1
    assert clients[0].disconnected is True


@pytest.mark.asyncio
async def test_evict_idle_repeatedly_skips_replaced_later_snapshot_state(
    tmp_path,
) -> None:
    for _ in range(25):
        first_client = BlockingDisconnectClaudeClient(options=None)
        stale_later_client = FakeClaudeClient(options=None)
        replacement_client = FakeClaudeClient(options=None)
        clients = iter([first_client, stale_later_client, replacement_client])
        manager = ClaudeSdkClientManager(
            workspace_id="workspace-1",
            client_factory=lambda options: next(clients),
            idle_ttl_seconds=5,
        )

        first_execution_id = manager.reserve()
        await manager.start_turn(
            thread_id="thread-first",
            execution_id=first_execution_id,
            request=request(thread_id="thread-first"),
            cwd=tmp_path,
            now=0,
        )
        await manager.finish_execution(first_execution_id, now=0)

        later_execution_id = manager.reserve()
        await manager.start_turn(
            thread_id="thread-later",
            execution_id=later_execution_id,
            request=request(thread_id="thread-later"),
            cwd=tmp_path,
            now=0,
        )
        await manager.finish_execution(later_execution_id, now=0)

        eviction_task = asyncio.create_task(manager.evict_idle(now=100))
        await asyncio.wait_for(first_client.disconnect_started.wait(), timeout=1)

        await manager.destroy_thread("thread-later")
        replacement_execution_id = manager.reserve()
        replacement_start = await manager.start_turn(
            thread_id="thread-later",
            execution_id=replacement_execution_id,
            request=request(thread_id="thread-later", prompt_text="replacement"),
            cwd=tmp_path,
            now=100,
        )
        replacement_state = manager._states["thread-later"]

        first_client.release_disconnect.set()
        assert await asyncio.wait_for(eviction_task, timeout=1) == 1

        assert first_client.disconnect_calls == 1
        assert first_client.disconnected is True
        assert stale_later_client.disconnected is True
        assert replacement_start.client is replacement_client
        assert replacement_client.disconnected is False
        assert manager._states == {"thread-later": replacement_state}
        assert manager._execution_to_thread == {
            replacement_execution_id: "thread-later"
        }
        assert manager.is_alive(replacement_execution_id) is True
