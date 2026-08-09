from __future__ import annotations

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
