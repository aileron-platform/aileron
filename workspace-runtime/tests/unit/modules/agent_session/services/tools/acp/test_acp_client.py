from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from acp import RequestError
from acp.schema import PermissionOption, ToolCallUpdate

from app.modules.agent_session.services.tools.acp import client as client_module


class FakeCallbacks:
    def __init__(self) -> None:
        self.stream_started: list[str] = []
        self.stream_chunks: list[tuple[str, str]] = []
        self.stream_ended: list[str] = []
        self.thinking_started: list[str] = []
        self.thinking_chunks: list[tuple[str, str]] = []
        self.thinking_ended: list[str] = []

    async def on_stream_start(self, message_id: str) -> None:
        self.stream_started.append(message_id)

    async def on_stream_chunk(self, message_id: str, text: str) -> None:
        self.stream_chunks.append((message_id, text))

    async def on_stream_end(self, message_id: str) -> None:
        self.stream_ended.append(message_id)

    async def on_thinking_start(self, message_id: str, metadata=None) -> None:
        self.thinking_started.append(message_id)

    async def on_thinking_chunk(self, message_id: str, text: str) -> None:
        self.thinking_chunks.append((message_id, text))

    async def on_thinking_end(self, message_id: str) -> None:
        self.thinking_ended.append(message_id)


class FakeAsyncScope:
    def __init__(self, db) -> None:
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def make_client(tmp_path: Path) -> client_module.AcpClient:
    return client_module.AcpClient(runtime_session_id="session-1", workspace_path=str(tmp_path))


@pytest.mark.asyncio
async def test_streaming_buffers_and_session_update_routes_events(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    callbacks = FakeCallbacks()
    emitted: list[tuple[str, dict]] = []
    client.set_task_context("task-1", callbacks, lambda name, payload: emitted.append((name, payload)))

    await client.session_update("sdk-1", SimpleNamespace(session_update="agent_message_chunk", content={"type": "text", "text": "hello"}))
    await client.session_update("sdk-1", SimpleNamespace(session_update="agent_thought_chunk", content={"type": "text", "text": "think"}))
    await client.session_update(
        "sdk-1",
        SimpleNamespace(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="Read",
            kind="read",
            raw_input={"path": "/a"},
            content=[{"type": "content", "text": "start"}],
            locations=[{"path": "/a"}],
        ),
    )
    await client.session_update(
        "sdk-1",
        SimpleNamespace(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="Read",
            kind="read",
            status="completed",
            raw_output={"ok": True},
            content=[{"type": "content", "text": "done"}],
            locations=[{"path": "/a"}],
        ),
    )
    await client.finalize_streaming()

    assert client.get_current_content() == ("hello", "think")
    assert len(callbacks.stream_started) == 1
    assert callbacks.stream_chunks[0][1] == "hello"
    assert len(callbacks.thinking_started) == 1
    assert callbacks.thinking_chunks[0][1] == "think"
    assert callbacks.stream_ended == callbacks.stream_started
    assert callbacks.thinking_ended == callbacks.thinking_started
    assert emitted[0][0] == "tool:start"
    assert emitted[1][0] == "tool:complete"
    assert client.get_tool_executions()[0]["tool_result"]["status"] == "completed"


@pytest.mark.asyncio
async def test_request_permission_handles_allow_reject_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(tmp_path)
    client.current_task_id = "task-1"
    emitted: list[tuple[str, dict]] = []
    client.emit_event = lambda name, payload: emitted.append((name, payload))
    db = object()
    async def create_permission_request(**kwargs):
        return None

    async def set_awaiting_permission(*args, **kwargs):
        return None

    message_service = SimpleNamespace(create_permission_request=create_permission_request)
    task_service = SimpleNamespace(set_awaiting_permission=set_awaiting_permission)
    monkeypatch.setattr(client_module, "async_session_scope", lambda: FakeAsyncScope(db))
    monkeypatch.setattr(client_module, "MessageService", lambda db_arg: message_service)
    monkeypatch.setattr(client_module, "TaskService", lambda db_arg: task_service)

    options = [
        PermissionOption(kind="allow_once", name="Allow", optionId="allow-1"),
        PermissionOption(kind="reject_once", name="Reject", optionId="reject-1"),
    ]
    tool_call = ToolCallUpdate(toolCallId="tool-1", title="Read", kind="read", rawInput={"path": "/a"})

    async def allow_decision(request_id, timeout=60):
        return {"outcome": "selected"}

    client._wait_for_decision = allow_decision
    allowed = await client.request_permission(options, "sdk-1", tool_call)

    async def reject_decision(request_id, timeout=60):
        return {"outcome": "selected", "option_id": "reject-1"}

    client._wait_for_decision = reject_decision
    denied = await client.request_permission(options, "sdk-1", tool_call)

    async def handle_timeout(request_id):
        emitted.append(("timeout-handled", {"request_id": request_id}))

    client._handle_decision_timeout = handle_timeout
    client._wait_for_decision = client_module.AcpClient._wait_for_decision.__get__(client, client_module.AcpClient)
    cancelled = await client._wait_for_decision("missing", timeout=0)

    assert allowed.outcome.outcome == "selected"
    assert allowed.outcome.option_id == "allow-1"
    assert denied.outcome.outcome == "cancelled"
    assert cancelled == {"outcome": "cancelled"}
    assert emitted[0][0] == "tool-decision:request"
    assert emitted[-1][0] == "timeout-handled"


@pytest.mark.asyncio
async def test_file_and_terminal_wrappers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(tmp_path)

    class FakeFileService:
        def __init__(self, root_path):
            self.root_path = root_path

        def read_file(self, relative_path):
            if relative_path == "missing.txt":
                raise client_module.FileNotFoundException("missing")
            return {"content": "a\nb\nc"}

        def write_file(self, relative_path, content):
            self.written = (relative_path, content)

    monkeypatch.setattr(client_module, "FileService", FakeFileService)
    async def create_terminal(**kwargs):
        return "term-1"

    async def get_output(terminal_id):
        return ("out", True, 5)

    async def wait_for_exit(terminal_id):
        return 5

    async def kill(terminal_id):
        return None

    async def release(terminal_id):
        return None

    monkeypatch.setattr(
        client,
        "_terminal_manager",
        SimpleNamespace(
            create_terminal=create_terminal,
            get_output=get_output,
            wait_for_exit=wait_for_exit,
            kill=kill,
            release=release,
        ),
    )

    read = await client.read_text_file(str(tmp_path / "demo.txt"), "sdk-1", limit=2, line=2)
    missing = await client.read_text_file(str(tmp_path / "missing.txt"), "sdk-1")
    write = await client.write_text_file("hello", str(tmp_path / "demo.txt"), "sdk-1")
    created = await client.create_terminal("bash", "sdk-1", args=["-lc", "pwd"], cwd=str(tmp_path))
    output = await client.terminal_output("sdk-1", "term-1")
    waited = await client.wait_for_terminal_exit("sdk-1", "term-1")
    killed = await client.kill_terminal("sdk-1", "term-1")
    released = await client.release_terminal("sdk-1", "term-1")

    assert read.content == "b\nc"
    assert missing.content == ""
    assert write is not None
    assert created.terminal_id == "term-1"
    assert output.output == "out" and output.truncated is True and output.exit_status.exit_code == 5
    assert waited.exit_code == 5
    assert killed is not None and released is not None

    with pytest.raises(RequestError):
        await client.read_text_file("relative.txt", "sdk-1")
    with pytest.raises(RequestError):
        await client.write_text_file("x", str(Path("/tmp/outside.txt")), "sdk-1")


@pytest.mark.asyncio
async def test_handle_decision_timeout_persists_and_emits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(tmp_path)
    client.current_task_id = "task-1"
    emitted: list[tuple[str, dict]] = []
    client.emit_event = lambda name, payload: emitted.append((name, payload))
    db = object()
    async def handle_timeout(**kwargs):
        return None

    service = SimpleNamespace(handle_timeout=handle_timeout)
    monkeypatch.setattr(client_module, "async_session_scope", lambda: FakeAsyncScope(db))
    monkeypatch.setattr(client_module, "ToolDecisionService", lambda db_arg: service)

    await client._handle_decision_timeout("req-1")

    assert emitted == [
        ("tool-decision:timeout", {"request_id": "req-1", "session_id": "session-1", "task_id": "task-1"})
    ]


def test_path_and_serialization_helpers(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    assert client._resolve_relative_path(str(tmp_path / "a.txt")) == "a.txt"
    with pytest.raises(ValueError):
        client._resolve_relative_path("/tmp/outside.txt")
    with pytest.raises(RequestError):
        client._ensure_absolute_path("relative.txt")

    assert client._extract_text({"type": "text", "text": "hello"}) == "hello"
    assert client._extract_text(SimpleNamespace(type="text", text="world")) == "world"
    assert client._extract_text({"type": "image"}) == ""
    assert client._extract_text(None) == ""
    assert client._extract_option_id({"optionId": "a"}) == "a"
    assert client._find_option_by_id([{"optionId": "a"}], "a") == {"optionId": "a"}
    assert client._is_reject_option({"kind": "reject_once"}) is True
    assert client._pick_default_allow_option([{"optionId": "a", "kind": "allow_once"}]) == "a"
    assert client._pick_default_allow_option([{"option_id": "b", "kind": "reject_once"}]) == "b"
    assert client._serialize_content_list([{"a": 1}, SimpleNamespace(model_dump=lambda **kwargs: {"b": 2})]) == [
        {"a": 1},
        {"b": 2},
    ]
    assert client._serialize_locations([{"p": 1}, SimpleNamespace(model_dump=lambda **kwargs: {"q": 2})]) == [
        {"p": 1},
        {"q": 2},
    ]

    tool_call = SimpleNamespace(
        tool_call_id="tool-1",
        title="Read",
        kind=SimpleNamespace(value="read"),
        status="completed",
        content=[{"type": "content"}],
        locations=[{"path": "/a"}],
        session_update="tool_call_update",
    )
    payload = client._serialize_tool_call(tool_call)
    assert payload["toolCallId"] == "tool-1"
    assert payload["kind"] == "read"
    assert client._build_tool_input_payload(tool_call_id="tool-1", raw_payload={}) == {"toolCallId": "tool-1"}
    assert client._build_tool_result_payload(tool_call_id="tool-1", status="completed", content=[{"x": 1}], raw_tool_update={}) == {
        "toolCallId": "tool-1",
        "status": "completed",
        "content": [{"x": 1}],
    }


@pytest.mark.asyncio
async def test_on_connect_resolve_decision_and_misc_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(tmp_path)
    registered: list[tuple[str, object]] = []
    monkeypatch.setattr(
        client_module,
        "global_tool_decision_manager",
        SimpleNamespace(register_hooks=lambda session_id, hooks: registered.append((session_id, hooks))),
    )
    event = asyncio.Event()
    client._pending_decisions["req-1"] = event

    client.on_connect(object())
    assert registered == [("session-1", client)]
    assert client.resolve_decision({"request_id": "req-1", "outcome": "selected"}) is True
    assert client.resolve_decision({"outcome": "selected"}) is False
    assert client.resolve_decision({"request_id": "missing"}) is False
    assert event.is_set() is True
    assert await client.ext_method("x", {}) == {}
    assert await client.ext_notification("x", {}) is None
