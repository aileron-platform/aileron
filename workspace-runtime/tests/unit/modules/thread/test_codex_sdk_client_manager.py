from __future__ import annotations

from dataclasses import dataclass, field
import json
import sys
from typing import Any

import pytest
from openai_codex import ApprovalMode, Sandbox

from app.modules.thread.mcp.config import AILERON_MCP_SERVER_PATH
import app.modules.thread.codex_sdk_client_manager as codex_sdk_client_manager
from app.modules.thread.codex_sdk_client_manager import CodexSdkClientManager


@dataclass
class FakeTurn:
    id: str = "turn-1"
    interrupted: bool = False

    async def interrupt(self) -> None:
        self.interrupted = True


@dataclass
class FakeThread:
    id: str
    turns: list[FakeTurn] = field(default_factory=list)
    turn_inputs: list[object] = field(default_factory=list)
    turn_kwargs: list[dict[str, Any]] = field(default_factory=list)

    async def turn(self, input, **kwargs):
        turn = FakeTurn(id=f"turn-{len(self.turns) + 1}")
        self.turns.append(turn)
        self.turn_inputs.append(input)
        self.turn_kwargs.append(kwargs)
        return turn


@dataclass
class FakeCodex:
    started_threads: list[FakeThread] = field(default_factory=list)
    resumed_threads: list[str] = field(default_factory=list)
    start_kwargs: list[dict[str, Any]] = field(default_factory=list)
    resume_kwargs: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    async def thread_start(self, **kwargs):
        thread = FakeThread(id="019f507e-2fe8-7c12-a9fc-48f3d316b569")
        self.start_kwargs.append(kwargs)
        self.started_threads.append(thread)
        return thread

    async def thread_resume(self, thread_id: str, **kwargs):
        self.resumed_threads.append(thread_id)
        self.resume_kwargs.append(kwargs)
        return FakeThread(id=thread_id)

    async def close(self) -> None:
        self.closed = True


def fake_codex_factory() -> FakeCodex:
    return FakeCodex()


@pytest.mark.asyncio
async def test_default_codex_config_enables_aileron_mcp_server(
    tmp_path,
    monkeypatch,
) -> None:
    captured_configs: list[Any] = []

    class CapturingCodex(FakeCodex):
        def __init__(self, *, config: Any) -> None:
            super().__init__()
            captured_configs.append(config)

    monkeypatch.setattr(codex_sdk_client_manager, "AsyncCodex", CapturingCodex)
    manager = CodexSdkClientManager(
        codex_bin="/usr/local/bin/codex",
        codex_home=str(tmp_path / "codex-home"),
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert captured_configs
    config_overrides = captured_configs[0].config_overrides
    assert (
        f"mcp_servers.aileron.command={json.dumps(sys.executable)}" in config_overrides
    )
    assert (
        "mcp_servers.aileron.args="
        f"[{json.dumps(str(AILERON_MCP_SERVER_PATH))}]" in config_overrides
    )
    assert AILERON_MCP_SERVER_PATH.exists()


@pytest.mark.asyncio
async def test_adopt_reservation_allows_external_execution_id() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    manager.adopt_reservation("external-exec")

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id="external-exec",
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert started.codex_thread_id == "019f507e-2fe8-7c12-a9fc-48f3d316b569"


@pytest.mark.asyncio
async def test_start_turn_starts_new_thread_and_tracks_execution() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model="gpt-5.6-sol",
    )

    assert started.codex_thread_id == "019f507e-2fe8-7c12-a9fc-48f3d316b569"
    assert len(started.codex_thread_id) <= 64
    assert started.codex.start_kwargs[0]["sandbox"] is Sandbox.full_access
    assert started.codex.start_kwargs[0]["approval_mode"] is ApprovalMode.deny_all
    assert started.thread.turn_kwargs[0]["sandbox"] is Sandbox.full_access
    assert started.thread.turn_kwargs[0]["approval_mode"] is ApprovalMode.deny_all
    assert manager.is_alive(execution_id) is True


@pytest.mark.asyncio
async def test_start_turn_resumes_existing_thread_id() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id="codex-thread-existing",
        model=None,
    )

    assert started.codex_thread_id == "codex-thread-existing"


@pytest.mark.asyncio
async def test_stop_interrupts_active_turn_without_closing_codex() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    await manager.stop_execution(execution_id)

    assert started.turn.interrupted is True
    assert started.codex.closed is False


@pytest.mark.asyncio
async def test_destroy_thread_closes_codex_and_clears_execution() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    await manager.destroy_thread("aileron-thread-1")

    assert started.codex.closed is True
    assert manager.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_evict_idle_closes_inactive_state() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=10,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
        now=100,
    )
    await manager.finish_execution(execution_id, now=100)

    evicted = await manager.evict_idle(now=111)

    assert evicted == 1
    assert started.codex.closed is True


@pytest.mark.asyncio
async def test_start_turn_preserves_prompt_and_supported_attachments_in_run_input() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="inspect these",
        attachments=[
            {
                "name": "screen.png",
                "mimeType": "image/png",
                "path": "/workspace/.aileron/uploads/screen.png",
            },
            {
                "name": "notes.txt",
                "mimeType": "text/plain",
                "path": "/workspace/.aileron/uploads/notes.txt",
            },
        ],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    run_input = started.thread.turn_inputs[0]
    assert [type(item).__name__ for item in run_input] == [
        "TextInput",
        "LocalImageInput",
        "TextInput",
    ]
    assert run_input[0].text == "inspect these"
    assert run_input[1].path == "/workspace/.aileron/uploads/screen.png"
    assert run_input[2].text == (
        "Attached file: notes.txt (/workspace/.aileron/uploads/notes.txt)"
    )


@pytest.mark.asyncio
async def test_start_turn_passes_aileron_canvas_developer_instructions_on_new_thread() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert (
        started.codex.start_kwargs[0]["developer_instructions"]
        == codex_sdk_client_manager.CODEX_AILERON_MCP_PROMPT
    )
    assert (
        "clarifying question" in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "expects the user to answer"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Do not use AskUserQuestion"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "end the turn immediately"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Never infer, invent, or fabricate user answers"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "the aileron-web-canvas skill owns the workflow"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Completion condition"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert "is not delivery" in started.codex.start_kwargs[0]["developer_instructions"]
    assert (
        "Hard cap: 5 questions"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Set each question's default"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert started.codex.start_kwargs[0]["config"] == {
        "mcp_servers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }


@pytest.mark.asyncio
async def test_start_turn_passes_aileron_canvas_developer_instructions_on_resume() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id="codex-thread-existing",
        model=None,
    )

    assert (
        started.codex.resume_kwargs[0]["developer_instructions"]
        == codex_sdk_client_manager.CODEX_AILERON_MCP_PROMPT
    )
    assert (
        "clarifying question"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "expects the user to answer"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Do not use AskUserQuestion"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "end the turn immediately"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Never infer, invent, or fabricate user answers"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "the aileron-web-canvas skill owns the workflow"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Completion condition"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert "is not delivery" in started.codex.resume_kwargs[0]["developer_instructions"]
    assert (
        "Hard cap: 5 questions"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Set each question's default"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert started.codex.resume_kwargs[0]["config"] == {
        "mcp_servers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }
