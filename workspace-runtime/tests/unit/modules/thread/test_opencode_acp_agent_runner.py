from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.modules.thread.opencode_acp_agent_runner import OpenCodeAcpClient
from app.modules.thread.opencode_acp_agent_runner import OpenCodeAcpAgentRunner
from app.modules.thread.mcp.config import AILERON_MCP_SERVER_PATH
from app.modules.thread.execution import AgentEvent
from app.modules.thread.execution import AgentExecutionRequest


@dataclass
class PermissionKind:
    value: str


@dataclass
class PermissionOption:
    option_id: str
    kind: PermissionKind
    name: str


@dataclass
class ToolCall:
    title: str = "Write file"


@dataclass
class EnvVar:
    name: str
    value: str


async def collect_event(events: list[AgentEvent], event: AgentEvent) -> None:
    events.append(event)


@pytest.mark.asyncio
async def test_permission_mode_none_allows_once(tmp_path: Path) -> None:
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    response = await client.request_permission(
        options=[
            PermissionOption("reject-1", PermissionKind("reject_once"), "Reject"),
            PermissionOption("allow-1", PermissionKind("allow_once"), "Allow"),
        ],
        session_id="session-1",
        tool_call=ToolCall(),
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "allow-1"


@pytest.mark.asyncio
async def test_non_allow_permission_mode_rejects_once(tmp_path: Path) -> None:
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode="default",
        on_event=lambda event: collect_event([], event),
    )

    response = await client.request_permission(
        options=[
            PermissionOption("allow-1", PermissionKind("allow_once"), "Allow"),
            PermissionOption("reject-1", PermissionKind("reject_once"), "Reject"),
        ],
        session_id="session-1",
        tool_call=ToolCall(),
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "reject-1"


@pytest.mark.asyncio
async def test_filesystem_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    with pytest.raises(PermissionError, match="path_outside_workspace"):
        await client.read_text_file("link.txt", session_id="session-1")


@pytest.mark.asyncio
async def test_filesystem_reads_and_writes_inside_workspace(tmp_path: Path) -> None:
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    await client.write_text_file("hello", "nested/file.txt", session_id="session-1")
    response = await client.read_text_file("nested/file.txt", session_id="session-1")

    assert response.content == "hello"


@pytest.mark.asyncio
async def test_read_text_file_limit_counts_lines(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    response = await client.read_text_file(
        "file.txt",
        session_id="session-1",
        line=2,
        limit=1,
    )

    assert response.content == "two"


@pytest.mark.asyncio
async def test_terminal_create_returns_before_process_exits(tmp_path: Path) -> None:
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    response = await client.create_terminal(
        command="python3",
        args=["-c", "import time; time.sleep(2); print('done')"],
        session_id="session-1",
    )

    assert response.terminal_id
    output = await client.terminal_output("session-1", response.terminal_id)
    assert output.exit_status is None or output.exit_status.exit_code is None
    await client.kill_terminal("session-1", response.terminal_id)


@pytest.mark.asyncio
async def test_terminal_output_streams_before_exit_and_applies_limit(
    tmp_path: Path,
) -> None:
    client = OpenCodeAcpClient(
        cwd=tmp_path,
        permission_mode=None,
        on_event=lambda event: collect_event([], event),
    )

    response = await client.create_terminal(
        command="python3",
        args=[
            "-c",
            "import os,time; print(os.environ['ACP_TEST'], flush=True); print('abcdef', flush=True); time.sleep(1)",
        ],
        session_id="session-1",
        env=[EnvVar("ACP_TEST", "from-env")],
        output_byte_limit=10,
    )
    early = await client.terminal_output("session-1", response.terminal_id)
    for _ in range(20):
        if "from-env" in early.output:
            break
        await asyncio.sleep(0.1)
        early = await client.terminal_output("session-1", response.terminal_id)
    exit_response = await client.wait_for_terminal_exit(
        "session-1",
        response.terminal_id,
    )
    output = await client.terminal_output("session-1", response.terminal_id)

    assert "from-env" in early.output
    assert exit_response.exit_code == 0
    assert output.truncated is True
    assert len(output.output.encode("utf-8")) <= 10


class FakePromptResponse:
    def __init__(self, stop_reason: str) -> None:
        self.stop_reason = stop_reason


@dataclass
class FakeContent:
    text: str


@dataclass
class FakeSessionUpdate:
    session_update: str
    content: object


class FakeNewSessionResponse:
    session_id = "session-1"


class FakeResumeSessionResponse:
    models = None
    modes = None


class FakeConnection:
    def __init__(
        self,
        *,
        stop_reason: str = "end_turn",
        fail_resume: bool = False,
        emit_update: bool = False,
    ) -> None:
        self.stop_reason = stop_reason
        self.fail_resume = fail_resume
        self.emit_update = emit_update
        self.client: object | None = None
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.cancelled: list[str] = []

    async def initialize(self, **kwargs: object) -> object:
        self.calls.append(("initialize", kwargs))
        return object()

    async def new_session(self, **kwargs: object) -> FakeNewSessionResponse:
        self.calls.append(("new_session", kwargs))
        return FakeNewSessionResponse()

    async def resume_session(self, **kwargs: object) -> FakeResumeSessionResponse:
        self.calls.append(("resume_session", kwargs))
        if self.fail_resume:
            raise RuntimeError("resume failed")
        return FakeResumeSessionResponse()

    async def load_session(self, **kwargs: object) -> FakeResumeSessionResponse:
        self.calls.append(("load_session", kwargs))
        return FakeResumeSessionResponse()

    async def set_session_model(self, **kwargs: object) -> object:
        self.calls.append(("set_session_model", kwargs))
        return object()

    async def prompt(self, **kwargs: object) -> FakePromptResponse:
        self.calls.append(("prompt", kwargs))
        if self.emit_update and self.client is not None:
            await self.client.session_update(
                str(kwargs["session_id"]),
                FakeSessionUpdate(
                    session_update="agent_message_chunk",
                    content=[FakeContent("hello from update")],
                ),
            )
        return FakePromptResponse(self.stop_reason)

    async def cancel(self, **kwargs: object) -> None:
        self.cancelled.append(str(kwargs["session_id"]))


class FakeProcess:
    pid = 123


class FakeSpawnContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.entered = False
        self.exited = False
        self.args: tuple[object, ...] | None = None
        self.kwargs: dict[str, object] | None = None

    async def __aenter__(self) -> tuple[FakeConnection, FakeProcess]:
        self.entered = True
        return self.connection, FakeProcess()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.exited = True


def execution_request(**overrides: object) -> AgentExecutionRequest:
    values = {
        "thread_id": "thread-1",
        "agentic_tool": "opencode",
        "model": "opencode-model",
        "claude_mode": None,
        "prompt_text": "hello",
        "permission_mode": None,
        "git_context_id": "ctx-1",
        "agent_resume_id": None,
        "attachments": [],
    }
    values.update(overrides)
    return AgentExecutionRequest(**values)


def test_prompt_prepends_aileron_canvas_policy() -> None:
    prompt = OpenCodeAcpAgentRunner._prompt(
        execution_request(prompt_text="Build an HTML page.")
    )

    assert prompt.startswith("Aileron platform MCP tools are available")
    assert "the aileron-web-canvas skill owns the workflow" in prompt
    assert "Completion condition" in prompt
    assert "is not delivery" in prompt
    assert "end the turn immediately" in prompt
    assert "Hard cap: 5 questions" in prompt
    assert "Set each question's default" in prompt
    assert "Never infer, invent, or fabricate user answers" in prompt
    assert "Build an HTML page." in prompt


@pytest.mark.asyncio
async def test_runner_spawns_opencode_acp_and_emits_complete(tmp_path: Path) -> None:
    connection = FakeConnection()
    context = FakeSpawnContext(connection)

    def spawn_agent(client: object, *args: str, **kwargs: object) -> FakeSpawnContext:
        connection.client = client
        context.args = args
        context.kwargs = kwargs
        return context

    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=spawn_agent,
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert context.args == ("opencode", "acp")
    assert context.kwargs is not None
    assert context.kwargs["cwd"] == str(tmp_path)
    assert [event.type for event in events] == ["system_init", "complete"]
    assert events[0].content["agentResumeId"] == "session-1"
    assert context.exited is True


@pytest.mark.asyncio
async def test_runner_opens_session_with_aileron_mcp_server(tmp_path: Path) -> None:
    connection = FakeConnection()
    context = FakeSpawnContext(connection)
    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )

    execution_id = runner.reserve()
    await runner.start(execution_request(), lambda event: None, execution_id)
    await runner.wait(execution_id)

    new_session_call = next(
        kwargs for name, kwargs in connection.calls if name == "new_session"
    )
    [server] = new_session_call["mcp_servers"]
    assert server.name == "aileron"
    assert server.args == [str(AILERON_MCP_SERVER_PATH)]
    assert AILERON_MCP_SERVER_PATH.exists()


@pytest.mark.asyncio
async def test_runner_maps_session_update_to_agent_event(tmp_path: Path) -> None:
    connection = FakeConnection(emit_update=True)
    context = FakeSpawnContext(connection)

    def spawn_agent(client: object, *args: str, **kwargs: object) -> FakeSpawnContext:
        connection.client = client
        return context

    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=spawn_agent,
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert [event.type for event in events] == [
        "system_init",
        "agent_text",
        "complete",
    ]
    assert events[1].content == {
        "parts": [{"type": "text", "text": "hello from update"}]
    }


@pytest.mark.asyncio
async def test_runner_uses_resume_then_load_fallback(tmp_path: Path) -> None:
    connection = FakeConnection(fail_resume=True)
    context = FakeSpawnContext(connection)

    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )

    execution_id = runner.reserve()
    await runner.start(
        execution_request(agent_resume_id="previous-session"),
        lambda event: None,
        execution_id,
    )
    await runner.wait(execution_id)

    assert [name for name, _ in connection.calls] == [
        "initialize",
        "resume_session",
        "load_session",
        "set_session_model",
        "prompt",
    ]
    set_model_call = next(
        kwargs for name, kwargs in connection.calls if name == "set_session_model"
    )
    prompt_call = next(kwargs for name, kwargs in connection.calls if name == "prompt")
    assert set_model_call["session_id"] == "previous-session"
    assert prompt_call["session_id"] == "previous-session"
    resume_call = next(
        kwargs for name, kwargs in connection.calls if name == "resume_session"
    )
    load_call = next(
        kwargs for name, kwargs in connection.calls if name == "load_session"
    )
    assert resume_call["mcp_servers"][0].name == "aileron"
    assert load_call["mcp_servers"][0].name == "aileron"


@pytest.mark.asyncio
async def test_cancelled_stop_reason_does_not_complete(tmp_path: Path) -> None:
    connection = FakeConnection(stop_reason="cancelled")
    context = FakeSpawnContext(connection)
    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert [event.type for event in events] == ["system_init"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_reason", ["max_tokens", "max_turn_requests", "refusal"])
async def test_non_end_turn_stop_reason_emits_error(
    tmp_path: Path,
    stop_reason: str,
) -> None:
    connection = FakeConnection(stop_reason=stop_reason)
    context = FakeSpawnContext(connection)
    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert events[-1].type == "error"
    assert events[-1].error_info is not None
    assert events[-1].error_info["stop_reason"] == stop_reason
    assert events[-1].content["text"]


@pytest.mark.asyncio
async def test_buffered_text_is_flushed_before_stop_reason_error(
    tmp_path: Path,
) -> None:
    connection = FakeConnection(emit_update=True, stop_reason="max_tokens")
    context = FakeSpawnContext(connection)

    def spawn_agent(client: object, *args: str, **kwargs: object) -> FakeSpawnContext:
        connection.client = client
        return context

    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=spawn_agent,
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert [event.type for event in events] == ["system_init", "agent_text", "error"]
    assert events[1].content == {
        "parts": [{"type": "text", "text": "hello from update"}]
    }


@pytest.mark.asyncio
async def test_stop_cancels_active_session(tmp_path: Path) -> None:
    prompt_started = asyncio.Event()
    release_prompt = asyncio.Event()

    class BlockingConnection(FakeConnection):
        async def prompt(self, **kwargs: object) -> FakePromptResponse:
            self.calls.append(("prompt", kwargs))
            prompt_started.set()
            await release_prompt.wait()
            return FakePromptResponse("cancelled")

    connection = BlockingConnection()
    context = FakeSpawnContext(connection)
    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )

    execution_id = runner.reserve()
    await runner.start(execution_request(), lambda event: None, execution_id)
    await prompt_started.wait()
    await runner.stop(execution_id)
    release_prompt.set()

    assert connection.cancelled == ["session-1"]
    assert runner.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_agent_task(
    tmp_path: Path,
) -> None:
    prompt_started = asyncio.Event()

    class BlockingConnection(FakeConnection):
        async def prompt(self, **kwargs: object) -> FakePromptResponse:
            self.calls.append(("prompt", kwargs))
            prompt_started.set()
            await asyncio.Event().wait()
            return FakePromptResponse("cancelled")

    connection = BlockingConnection()
    context = FakeSpawnContext(connection)
    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: context,
        cwd_resolver=lambda _: tmp_path,
    )
    execution_id = runner.reserve()
    await runner.start(execution_request(), lambda event: None, execution_id)
    await prompt_started.wait()
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
    assert connection.cancelled == ["session-1"]
    assert runner.is_alive(execution_id) is False
    assert runner._tasks == {}


@pytest.mark.asyncio
async def test_spawn_failure_releases_reservation_and_emits_error(
    tmp_path: Path,
) -> None:
    class FailingContext:
        async def __aenter__(self) -> tuple[FakeConnection, FakeProcess]:
            raise RuntimeError("spawn failed")

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    runner = OpenCodeAcpAgentRunner(
        workspace_id="ws-1",
        spawn_agent=lambda client, *args, **kwargs: FailingContext(),
        cwd_resolver=lambda _: tmp_path,
    )
    events: list[AgentEvent] = []

    execution_id = runner.reserve()
    await runner.start(execution_request(), events.append, execution_id)
    await runner.wait(execution_id)

    assert runner.is_alive(execution_id) is False
    assert events[-1].type == "error"
    assert events[-1].error_code == "opencode_execution_failed"
    assert events[-1].content["text"] == "spawn failed"
    assert runner._tasks == {}
