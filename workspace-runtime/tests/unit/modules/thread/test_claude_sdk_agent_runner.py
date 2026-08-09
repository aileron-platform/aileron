from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
from claude_agent_sdk import ResultMessage, TextBlock, AssistantMessage

from app.modules.thread.claude_sdk_agent_runner import ClaudeSdkAgentRunner
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)


@dataclass
class FakeTurnStart:
    stream: Any


@dataclass
class FakeManager:
    reserved: set[str] = field(default_factory=set)
    stopped: list[str] = field(default_factory=list)
    finished: list[str] = field(default_factory=list)
    destroyed: list[str] = field(default_factory=list)
    evicted: int = 0

    def reserve(self) -> str:
        self.reserved.add("execution-1")
        return "execution-1"

    def adopt_reservation(self, execution_id: str) -> None:
        self.reserved.add(execution_id)

    async def start_turn(self, **kwargs: Any) -> FakeTurnStart:
        async def stream():
            yield AssistantMessage(
                content=[TextBlock(text="hello")],
                model="claude-sonnet-4-5-20250929",
            )
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="session-1",
            )

        return FakeTurnStart(stream=stream())

    async def stop_execution(self, execution_id: str) -> None:
        self.stopped.append(execution_id)

    def is_alive(self, execution_id: str) -> bool:
        return execution_id in self.reserved and execution_id not in self.finished

    async def finish_execution(self, execution_id: str) -> None:
        self.finished.append(execution_id)

    async def destroy_thread(self, thread_id: str) -> None:
        self.destroyed.append(thread_id)

    async def evict_idle(self) -> int:
        return self.evicted


def request() -> AgentExecutionRequest:
    return AgentExecutionRequest(
        thread_id="thread-1",
        agentic_tool="claude",
        model="claude-sonnet-4-5-20250929",
        claude_mode=None,
        prompt_text="hello",
        permission_mode=None,
        git_context_id="ctx-1",
    )


@pytest.mark.asyncio
async def test_runner_streams_mapped_events_and_finishes_execution() -> None:
    manager = FakeManager()
    runner = ClaudeSdkAgentRunner(
        workspace_id="workspace-1",
        manager=manager,
        cwd_resolver=lambda _: "/workspace",
    )
    events: list[AgentEvent] = []
    execution_id = runner.reserve()

    await runner.start(request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert [event.type for event in events] == ["agent_text", "complete"]
    assert manager.finished == [execution_id]
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_wait_blocks_until_finalizer_finishes_after_terminal_event() -> None:
    terminal_event_handled = asyncio.Event()
    finalizer_started = asyncio.Event()
    release_finalizer = asyncio.Event()

    class FinalizerBarrierManager(FakeManager):
        async def finish_execution(self, execution_id: str) -> None:
            finalizer_started.set()
            await release_finalizer.wait()
            await super().finish_execution(execution_id)

    manager = FinalizerBarrierManager()
    runner = ClaudeSdkAgentRunner(
        workspace_id="workspace-1",
        manager=manager,
        cwd_resolver=lambda _: "/workspace",
    )

    async def on_event(event: AgentEvent) -> None:
        if event.type == "complete":
            terminal_event_handled.set()

    execution_id = runner.reserve()
    await runner.start(request(), on_event, execution_id)
    await terminal_event_handled.wait()
    await finalizer_started.wait()

    wait_task = asyncio.create_task(runner.wait(execution_id))
    await asyncio.sleep(0)

    assert wait_task.done() is False
    assert runner.is_alive(execution_id) is True

    release_finalizer.set()
    await wait_task

    assert runner.is_alive(execution_id) is False
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_agent_task() -> None:
    stream_started = asyncio.Event()

    class BlockingManager(FakeManager):
        async def start_turn(self, **kwargs: Any) -> FakeTurnStart:
            async def stream():
                stream_started.set()
                await asyncio.Event().wait()
                yield None

            return FakeTurnStart(stream=stream())

    manager = BlockingManager()
    runner = ClaudeSdkAgentRunner(
        workspace_id="workspace-1",
        manager=manager,
        cwd_resolver=lambda _: "/workspace",
    )
    execution_id = runner.reserve()
    await runner.start(request(), lambda event: None, execution_id)
    await stream_started.wait()
    cancelled_waiter = asyncio.create_task(runner.wait(execution_id))
    surviving_waiter = asyncio.create_task(runner.wait(execution_id))
    await asyncio.sleep(0)

    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter
    await asyncio.sleep(0)
    alive_before_stop = runner.is_alive(execution_id)
    surviving_waiter_done_before_stop = surviving_waiter.done()

    await runner.stop(execution_id)
    await surviving_waiter

    assert alive_before_stop is True
    assert surviving_waiter_done_before_stop is False
    assert manager.stopped == [execution_id]
    assert manager.finished == [execution_id]
    assert runner.is_alive(execution_id) is False
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_stop_delegates_to_manager_and_cancels_running_task() -> None:
    stream_started = asyncio.Event()

    class BlockingManager(FakeManager):
        async def start_turn(self, **kwargs: Any) -> FakeTurnStart:
            async def stream():
                stream_started.set()
                await asyncio.Event().wait()
                yield None

            return FakeTurnStart(stream=stream())

    manager = BlockingManager()
    runner = ClaudeSdkAgentRunner(
        workspace_id="workspace-1",
        manager=manager,
        cwd_resolver=lambda _: "/workspace",
    )
    execution_id = runner.reserve()
    await runner.start(request(), lambda event: None, execution_id)
    await stream_started.wait()

    await runner.stop(execution_id)

    assert manager.stopped == [execution_id]
    assert manager.finished == [execution_id]
    assert runner.is_alive(execution_id) is False
    assert runner._tasks == {}
