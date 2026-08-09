from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.modules.thread.composite_agent_runner import CompositeAgentRunner
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.runtime_control.state import (
    RuntimeDrainingError,
    get_runtime_admission_state,
)


@dataclass
class FakeSubRunner:
    name: str
    reserved: list[str] = field(default_factory=list)
    started: list[tuple[str, str]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    destroyed: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    waited: list[str] = field(default_factory=list)
    idle_evicted: int = 0
    completions: dict[str, asyncio.Event] = field(default_factory=dict)

    def reserve(self) -> str:
        execution_id = f"{self.name}-reserved"
        self.reserved.append(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self.adopted.append(execution_id)

    async def start(self, request: Any, on_event: Any, execution_id: str) -> None:
        assert execution_id in self.adopted
        self.started.append((request.agentic_tool, execution_id))
        self.completions[execution_id] = asyncio.Event()
        self.on_event = on_event

    async def wait(self, execution_id: str) -> None:
        self.waited.append(execution_id)
        completion = self.completions.get(execution_id)
        if completion is not None:
            await asyncio.shield(completion.wait())

    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)
        self.finish(execution_id)

    def is_alive(self, execution_id: str) -> bool:
        return (
            execution_id in {item[1] for item in self.started}
            and not self.completions[execution_id].is_set()
        )

    def finish(self, execution_id: str) -> None:
        self.completions[execution_id].set()

    async def destroy_thread(self, thread_id: str) -> None:
        self.destroyed.append(thread_id)

    async def evict_idle(self) -> int:
        return self.idle_evicted


@dataclass
class StartFailingSubRunner(FakeSubRunner):
    async def start(self, request: Any, on_event: Any, execution_id: str) -> None:
        await super().start(request, on_event, execution_id)
        raise RuntimeError("start failed")


@dataclass
class StopFailingSubRunner(FakeSubRunner):
    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)
        self.finish(execution_id)
        raise RuntimeError("stop failed")


def request(tool: str) -> AgentExecutionRequest:
    return AgentExecutionRequest(
        thread_id="thread-1",
        agentic_tool=tool,
        model="model",
        claude_mode=None,
        prompt_text="hello",
        permission_mode=None,
        git_context_id="ctx-1",
    )


@pytest.mark.asyncio
async def test_full_drain_stops_all_agent_owners() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )
    first = runner.reserve()
    second = runner.reserve()
    await runner.start(request("codex"), lambda event: None, first)
    await runner.start(request("claude"), lambda event: None, second)

    await runner.drain_all()

    assert codex.stopped == [first]
    assert claude.stopped == [second]
    assert runner.is_alive(first) is False
    assert runner.is_alive(second) is False


@pytest.mark.asyncio
async def test_full_drain_reports_agent_stop_failure() -> None:
    opencode = FakeSubRunner("opencode")
    codex = StopFailingSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )
    execution_id = runner.reserve()
    await runner.start(request("codex"), lambda event: None, execution_id)

    with pytest.raises(RuntimeError, match="agent_drain_incomplete"):
        await runner.drain_all()

    await runner.wait(execution_id)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_drain_blocks_adopting_a_late_agent_reservation() -> None:
    admission = get_runtime_admission_state()
    runner = CompositeAgentRunner(
        opencode_runner=FakeSubRunner("opencode"),
        codex_runner=FakeSubRunner("codex"),
        claude_runner=FakeSubRunner("claude"),
    )
    await admission.begin_drain("attempt-a")

    with pytest.raises(RuntimeDrainingError):
        runner.adopt_reservation("execution-a")


@pytest.mark.asyncio
async def test_reserve_is_composite_owned_and_start_routes_by_tool() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("codex"), lambda event: None, execution_id)

    assert execution_id not in opencode.reserved
    assert execution_id not in codex.reserved
    assert execution_id not in claude.reserved
    assert codex.adopted == [execution_id]
    assert codex.started == [("codex", execution_id)]
    assert opencode.started == []
    assert claude.started == []
    codex.finish(execution_id)
    await runner.wait(execution_id)


@pytest.mark.asyncio
async def test_opencode_routes_to_opencode_runner() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("opencode"), lambda event: None, execution_id)

    assert opencode.adopted == [execution_id]
    assert opencode.started == [("opencode", execution_id)]
    assert codex.started == []
    assert claude.started == []
    opencode.finish(execution_id)
    await runner.wait(execution_id)


@pytest.mark.asyncio
async def test_stop_and_is_alive_use_start_routing_owner() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("claude"), lambda event: None, execution_id)

    assert runner.is_alive(execution_id) is True
    await runner.stop(execution_id)
    assert opencode.stopped == []
    assert codex.stopped == []
    assert claude.stopped == [execution_id]
    assert runner.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_destroy_thread_delegates_to_stateful_sdk_runners() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    await runner.destroy_thread("thread-1")

    assert opencode.destroyed == ["thread-1"]
    assert codex.destroyed == ["thread-1"]
    assert claude.destroyed == ["thread-1"]


@pytest.mark.asyncio
async def test_destroy_thread_stops_active_executions_for_that_thread_and_cleans_owner() -> (
    None
):
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("codex"), lambda event: None, execution_id)
    await runner.destroy_thread("thread-1")

    assert codex.stopped == [execution_id]
    assert opencode.destroyed == ["thread-1"]
    assert codex.destroyed == ["thread-1"]
    assert claude.destroyed == ["thread-1"]
    assert runner.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_terminal_event_does_not_release_owner_before_runner_finalizer() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )
    events: list[str] = []

    async def on_event(event: AgentEvent) -> None:
        events.append(event.type)
        assert runner.is_alive(execution_id) is True

    execution_id = runner.reserve()
    await runner.start(request("codex"), on_event, execution_id)
    await codex.on_event(AgentEvent(type="complete"))

    assert events == ["complete"]
    wait_task = asyncio.create_task(runner.wait(execution_id))
    await asyncio.sleep(0)
    assert wait_task.done() is False
    assert runner.is_alive(execution_id) is True
    assert execution_id in runner._owners
    assert opencode.stopped == []
    assert codex.stopped == []
    assert claude.stopped == []

    codex.finish(execution_id)
    await wait_task
    await asyncio.sleep(0)

    assert runner.is_alive(execution_id) is False
    assert runner._owners == {}
    assert runner._execution_threads == {}
    assert runner._reserved == set()
    assert runner._cleanup_watchers == {}


@pytest.mark.asyncio
async def test_start_failure_rolls_back_owner_and_thread_mapping() -> None:
    opencode = FakeSubRunner("opencode")
    codex = StartFailingSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    with pytest.raises(RuntimeError, match="start failed"):
        await runner.start(request("codex"), lambda event: None, execution_id)

    assert runner.is_alive(execution_id) is False
    await runner.destroy_thread("thread-1")
    assert opencode.destroyed == ["thread-1"]
    assert codex.destroyed == ["thread-1"]
    assert claude.destroyed == ["thread-1"]
    assert codex.stopped == [execution_id]


@pytest.mark.asyncio
async def test_unknown_tool_raises_and_releases_owner() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    with pytest.raises(ValueError, match="unsupported_agentic_tool:unknown"):
        await runner.start(request("unknown"), lambda event: None, execution_id)

    assert runner.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_wait_routes_to_active_owner_and_missing_owner_is_safe_noop() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("claude"), lambda event: None, execution_id)
    wait_task = asyncio.create_task(runner.wait(execution_id))
    await asyncio.sleep(0)

    assert execution_id in claude.waited
    assert opencode.waited == []
    assert codex.waited == []
    assert wait_task.done() is False

    claude.finish(execution_id)
    await wait_task
    await asyncio.sleep(0)
    await runner.wait(execution_id)

    assert runner.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_cancelled_waiter_keeps_owner_and_cleanup_watcher_until_stop() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    execution_id = runner.reserve()
    await runner.start(request("codex"), lambda event: None, execution_id)
    cancelled_waiter = asyncio.create_task(runner.wait(execution_id))
    surviving_waiter = asyncio.create_task(runner.wait(execution_id))
    await asyncio.sleep(0)

    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter
    await asyncio.sleep(0)

    assert runner.is_alive(execution_id) is True
    assert execution_id in runner._owners
    assert execution_id in runner._cleanup_watchers
    assert surviving_waiter.done() is False

    await runner.stop(execution_id)
    await surviving_waiter
    await asyncio.sleep(0)

    assert codex.stopped == [execution_id]
    assert runner.is_alive(execution_id) is False
    assert runner._owners == {}
    assert runner._execution_threads == {}
    assert runner._reserved == set()
    assert runner._cleanup_watchers == {}


@pytest.mark.asyncio
async def test_many_completed_executions_leave_no_lifecycle_memory() -> None:
    opencode = FakeSubRunner("opencode")
    codex = FakeSubRunner("codex")
    claude = FakeSubRunner("claude")
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    for index in range(100):
        execution_id = runner.reserve()
        await runner.start(request("codex"), lambda event: None, execution_id)
        await codex.on_event(AgentEvent(type="complete", content={"index": index}))
        codex.finish(execution_id)
        await runner.wait(execution_id)

    await asyncio.sleep(0)

    assert runner._owners == {}
    assert runner._execution_threads == {}
    assert runner._reserved == set()
    assert runner._cleanup_watchers == {}
    assert not hasattr(runner, "_released")


@pytest.mark.asyncio
async def test_evict_idle_delegates_to_sdk_runners() -> None:
    opencode = FakeSubRunner("opencode", idle_evicted=3)
    codex = FakeSubRunner("codex", idle_evicted=2)
    claude = FakeSubRunner("claude", idle_evicted=4)
    runner = CompositeAgentRunner(
        opencode_runner=opencode,
        codex_runner=codex,
        claude_runner=claude,
    )

    evicted = await runner.evict_idle()

    assert evicted == 9
