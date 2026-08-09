from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import app.modules.thread.codex_sdk_agent_runner as runner_module
from app.modules.thread.codex_sdk_agent_runner import CodexSdkAgentRunner
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)


@dataclass
class Notification:
    method: str
    payload: object


@dataclass
class Payload:
    delta: str | None = None
    token_usage: object | None = None
    item: object | None = None


@dataclass
class RootItem:
    root: object


@dataclass
class AgentMessageItem:
    id: str = "msg-1"
    type: str = "agentMessage"
    text: str = "hello"


@dataclass
class TokenBreakdown:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int


@dataclass
class ThreadUsage:
    last: TokenBreakdown
    total: TokenBreakdown
    model_context_window: int | None = None


class FakeTurn:
    id = "turn-1"

    async def stream(self):
        yield Notification("item/agentMessage/delta", Payload(delta="hello"))
        yield Notification(
            "item/completed",
            Payload(item=RootItem(root=AgentMessageItem())),
        )
        yield Notification(
            "thread/tokenUsage/updated",
            Payload(
                token_usage=ThreadUsage(
                    last=TokenBreakdown(3, 4, 5, 0, 12),
                    total=TokenBreakdown(30, 40, 50, 0, 120),
                    model_context_window=200000,
                )
            ),
        )
        yield Notification("turn/completed", Payload())


class FailingTurn:
    id = "turn-1"

    async def stream(self):
        raise RuntimeError("sdk stream failed")
        yield


class BlockingTurn:
    id = "turn-1"

    def __init__(self, started: asyncio.Event) -> None:
        self.started = started

    async def stream(self):
        self.started.set()
        await asyncio.Event().wait()
        yield


@dataclass
class FakeTurnStart:
    turn: object
    codex_thread_id: str = "019f507e-2fe8-7c12-a9fc-48f3d316b569"


class FakeManager:
    def __init__(self) -> None:
        self.reserved: set[str] = set()
        self.destroyed: list[str] = []
        self.finished: list[str] = []
        self.start_kwargs: list[dict[str, Any]] = []
        self.turn: object = FakeTurn()

    def reserve(self) -> str:
        self.reserved.add("exec-1")
        return "exec-1"

    def adopt_reservation(self, execution_id: str) -> None:
        self.reserved.add(execution_id)

    async def start_turn(self, **kwargs: Any) -> FakeTurnStart:
        assert kwargs["thread_id"] == "thread-1"
        assert kwargs["execution_id"] == "exec-1"
        assert kwargs["prompt"] == "hello"
        assert kwargs["attachments"] == [
            {"path": "/workspace/image.png", "mimeType": "image/png"}
        ]
        assert kwargs["cwd"] == "/workspace/worktrees/ctx-1"
        assert kwargs["model"] == "gpt-5.6-sol"
        self.start_kwargs.append(kwargs)
        return FakeTurnStart(turn=self.turn)

    async def stop_execution(self, execution_id: str) -> None:
        self.finished.append(f"stop:{execution_id}")

    def is_alive(self, execution_id: str) -> bool:
        return execution_id in self.reserved

    async def finish_execution(self, execution_id: str) -> None:
        self.finished.append(execution_id)
        self.reserved.discard(execution_id)

    async def destroy_thread(self, thread_id: str) -> None:
        self.destroyed.append(thread_id)

    async def evict_idle(self) -> int:
        return 0


def request() -> AgentExecutionRequest:
    return AgentExecutionRequest(
        thread_id="thread-1",
        agentic_tool="codex",
        model="gpt-5.6-sol",
        claude_mode=None,
        prompt_text="hello",
        attachments=[{"path": "/workspace/image.png", "mimeType": "image/png"}],
        permission_mode=None,
        git_context_id="ctx-1",
        agent_resume_id=None,
    )


def test_default_cwd_resolver_uses_workspace_as_git_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeGitUtils:
        def __init__(self, root_path: Path, *, worktree_subdir: str) -> None:
            captured["root_path"] = root_path
            captured["worktree_subdir"] = worktree_subdir

        def resolve_context_path(
            self, workspace_id: str, context_id: str | None = None
        ) -> Path:
            captured["workspace_id"] = workspace_id
            captured["context_id"] = context_id
            return Path("/workspace")

    monkeypatch.setattr(runner_module, "GitUtils", FakeGitUtils)

    runner = CodexSdkAgentRunner(
        workspace_id="workspace-example", manager=FakeManager()
    )

    assert runner._resolve_cwd(None) == Path("/workspace")
    assert captured["root_path"] == Path("/workspace")
    assert captured["workspace_id"] == "workspace-example"
    assert captured["context_id"] is None


@pytest.mark.asyncio
async def test_codex_runner_emits_system_text_metadata_and_complete() -> None:
    manager = FakeManager()
    runner = CodexSdkAgentRunner(
        workspace_id="ws-1",
        manager=manager,
        cwd_resolver=lambda context_id: f"/workspace/worktrees/{context_id}",
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(request(), lambda event: events.append(event), execution_id)
    await runner.wait(execution_id)

    assert [event.type for event in events] == [
        "system_init",
        "agent_text",
        "metadata",
        "complete",
    ]
    assert events[0].content["agentResumeId"] == "019f507e-2fe8-7c12-a9fc-48f3d316b569"
    assert events[1].content == {"parts": [{"type": "text", "text": "hello"}]}
    assert events[2].usage is not None
    assert events[2].usage["token_usage"]["total"]["total_tokens"] == 120
    assert manager.finished == ["exec-1"]
    assert manager.start_kwargs[0]["attachments"] == [
        {"path": "/workspace/image.png", "mimeType": "image/png"}
    ]
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_codex_runner_destroys_sdk_state_after_terminal_error_callback_returns() -> (
    None
):
    manager = FakeManager()
    manager.turn = FailingTurn()
    runner = CodexSdkAgentRunner(
        workspace_id="ws-1",
        manager=manager,
        cwd_resolver=lambda context_id: f"/workspace/worktrees/{context_id}",
    )
    events: list[AgentEvent] = []
    callback_running = False

    async def on_event(event: AgentEvent) -> None:
        nonlocal callback_running
        callback_running = True
        events.append(event)
        assert manager.destroyed == []
        callback_running = False

    execution_id = runner.reserve()
    await runner.start(request(), on_event, execution_id)
    await runner.wait(execution_id)

    assert callback_running is False
    assert [event.type for event in events] == ["system_init", "error"]
    assert manager.destroyed == ["thread-1"]
    assert manager.finished == ["exec-1"]
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_agent_task() -> None:
    stream_started = asyncio.Event()
    manager = FakeManager()
    manager.turn = BlockingTurn(stream_started)
    runner = CodexSdkAgentRunner(
        workspace_id="ws-1",
        manager=manager,
        cwd_resolver=lambda context_id: f"/workspace/worktrees/{context_id}",
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
    assert manager.finished == [f"stop:{execution_id}", execution_id]
    assert runner.is_alive(execution_id) is False
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_destroy_thread_delegates_to_manager() -> None:
    manager = FakeManager()
    runner = CodexSdkAgentRunner(
        workspace_id="ws-1",
        manager=manager,
        cwd_resolver=lambda _: "/workspace",
    )

    await runner.destroy_thread("thread-1")

    assert manager.destroyed == ["thread-1"]
