from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from claude_agent_sdk import ResultMessage

from app.modules.agent_session.services.tools.base.types import EndEvent, PartialEvent, StoppedEvent
from app.modules.agent_session.services.tools.claude import prompt_service as prompt_module


def _patch_session_repo(monkeypatch: pytest.MonkeyPatch, session_repo) -> None:
    """Patch async_session_scope and AgentSessionRepository so service uses the mock."""

    @asynccontextmanager
    async def fake_scope():
        yield Mock()

    monkeypatch.setattr(prompt_module, "async_session_scope", fake_scope)
    monkeypatch.setattr(prompt_module, "AgentSessionRepository", lambda db: session_repo)


class FakeClient:
    def __init__(
        self,
        options=None,
        messages=None,
        connect_error=None,
        interrupt_error=None,
        set_mode_error=None,
        events: list[str] | None = None,
        block_on_receive: asyncio.Event | None = None,
        receive_started: asyncio.Event | None = None,
    ):
        self.options = options
        self.messages = list(messages or [])
        self.connect_error = connect_error
        self.interrupt_error = interrupt_error
        self.set_mode_error = set_mode_error
        self.events = events if events is not None else []
        self.block_on_receive = block_on_receive
        self.receive_started = receive_started
        self.connected_payload = None
        self.queries: list[object] = []
        self.receive_calls = 0
        self.receive_cancelled = 0
        self.yielded_messages = 0
        self.interrupt_calls = 0
        self.disconnect_calls = 0
        self.mode_calls: list[str] = []
        self.events.append("create")

    async def connect(self, payload=None):
        self.events.append("connect")
        if self.connect_error:
            raise self.connect_error
        if payload is None:
            self.connected_payload = None
            return
        self.connected_payload = []
        async for item in payload:
            self.connected_payload.append(item)

    async def query(self, prompt):
        self.events.append("query")
        if isinstance(prompt, str):
            self.queries.append(prompt)
            return

        streamed = []
        async for item in prompt:
            streamed.append(item)
        self.queries.append(streamed)

    def receive_messages(self):
        self.events.append("receive_messages")
        self.receive_calls += 1

        async def _gen():
            if self.receive_started:
                self.receive_started.set()
            if self.block_on_receive:
                try:
                    await self.block_on_receive.wait()
                except asyncio.CancelledError:
                    self.receive_cancelled += 1
                    raise
            for item in self.messages:
                if isinstance(item, Exception):
                    raise item
                self.yielded_messages += 1
                yield item

        return _gen()

    async def interrupt(self):
        self.events.append("interrupt")
        self.interrupt_calls += 1
        if self.interrupt_error:
            raise self.interrupt_error

    async def disconnect(self):
        self.events.append("disconnect")
        self.disconnect_calls += 1

    async def set_permission_mode(self, mode: str):
        self.events.append("set_permission_mode")
        self.mode_calls.append(mode)
        if self.set_mode_error:
            raise self.set_mode_error


@pytest.mark.asyncio
async def test_prompt_session_streaming_requires_existing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = SimpleNamespace(find_by_id=AsyncMock(return_value=None))
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()

    with pytest.raises(ValueError, match="Session not found: session-1"):
        async for _ in service.prompt_session_streaming("session-1", "hello"):
            pass


@pytest.mark.asyncio
async def test_prompt_session_streaming_yields_processor_events(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    options = SimpleNamespace(name="opts")
    service.query_builder.setup_query = AsyncMock(return_value=options)

    lifecycle_events: list[str] = []
    client = FakeClient(options=options, messages=[object()], events=lifecycle_events)

    class FakeProcessor:
        def __init__(self, options):
            self.options = options
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=7)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return [PartialEvent(text="chunk"), EndEvent(reason="result")]

    created_options: list[object] = []

    def fake_client_factory(options):
        created_options.append(options)
        assert options is client.options
        return client

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", fake_client_factory)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    events = [event async for event in service.prompt_session_streaming("session-1", "hello", task_id="task-1")]

    assert [type(event) for event in events] == [PartialEvent, EndEvent]
    assert created_options == [options]
    assert client.connected_payload is None
    assert client.queries == ["hello"]
    assert client.receive_calls == 1
    assert service.active_clients["session-1"] is client
    assert lifecycle_events == ["create", "connect", "query", "receive_messages"]


@pytest.mark.asyncio
async def test_prompt_session_streaming_uses_async_iterable_query_when_can_use_tool_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))

    lifecycle_events: list[str] = []
    client = FakeClient(messages=[object()], events=lifecycle_events)

    class FakeProcessor:
        def __init__(self, options):
            self.options = options
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=7)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return [EndEvent(reason="result")]

    async def fake_can_use_tool(*args, **kwargs):
        return None

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    events = [
        event
        async for event in service.prompt_session_streaming(
            "session-1",
            "hello",
            can_use_tool=fake_can_use_tool,
        )
    ]

    assert [type(event) for event in events] == [EndEvent]
    assert client.connected_payload is None
    assert client.queries == [[
        {
            "type": "user",
            "message": {"role": "user", "content": "hello"},
            "parent_tool_use_id": None,
            "session_id": "default",
        }
    ]]
    assert lifecycle_events == ["create", "connect", "query", "receive_messages"]


@pytest.mark.asyncio
async def test_prompt_session_streaming_tracks_client_when_connect_fails_until_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))

    lifecycle_events: list[str] = []
    client = FakeClient(connect_error=RuntimeError("connect failed"), events=lifecycle_events)

    class FakeProcessor:
        def __init__(self, options):
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=0)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return []

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    with pytest.raises(RuntimeError, match="connect failed"):
        async for _ in service.prompt_session_streaming("session-1", "hello"):
            pass

    assert service.active_clients["session-1"] is client
    assert lifecycle_events == ["create", "connect"]

    await service.cleanup_client("session-1")

    assert "session-1" not in service.active_clients
    assert lifecycle_events == ["create", "connect", "disconnect"]


@pytest.mark.asyncio
async def test_prompt_session_streaming_stops_when_abort_event_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))
    client = FakeClient(messages=[object()])

    class FakeProcessor:
        def __init__(self, options):
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=0)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return []

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    abort_event = asyncio.Event()
    abort_event.set()
    events = [event async for event in service.prompt_session_streaming("session-1", "hello", abort_event=abort_event)]

    assert len(events) == 1
    assert isinstance(events[0], StoppedEvent)
    assert client.interrupt_calls == 1
    assert client.receive_calls == 1
    assert client.yielded_messages == 0


@pytest.mark.asyncio
async def test_prompt_session_streaming_interrupts_when_abort_event_triggers_during_message_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))

    block_on_receive = asyncio.Event()
    receive_started = asyncio.Event()
    lifecycle_events: list[str] = []
    client = FakeClient(
        messages=[object()],
        events=lifecycle_events,
        block_on_receive=block_on_receive,
        receive_started=receive_started,
    )

    class FakeProcessor:
        def __init__(self, options):
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=0)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return []

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    abort_event = asyncio.Event()

    async def collect_events():
        return [
            event
            async for event in service.prompt_session_streaming(
                "session-1",
                "hello",
                abort_event=abort_event,
            )
        ]

    collect_task = asyncio.create_task(collect_events())
    await asyncio.wait_for(receive_started.wait(), timeout=1)
    abort_event.set()
    events = await asyncio.wait_for(collect_task, timeout=1)

    assert len(events) == 1
    assert isinstance(events[0], StoppedEvent)
    assert client.interrupt_calls == 1
    assert client.receive_calls == 1
    assert client.receive_cancelled == 1
    assert client.yielded_messages == 0
    assert lifecycle_events == ["create", "connect", "query", "receive_messages", "interrupt"]


@pytest.mark.asyncio
async def test_prompt_session_streaming_converts_abort_like_errors_to_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))
    client = FakeClient(messages=[RuntimeError("interrupt requested")])

    class FakeProcessor:
        def __init__(self, options):
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=0)

        def has_timed_out(self):
            return False

        def get_state(self):
            return self.state

        async def process(self, msg):
            return []

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    events = [event async for event in service.prompt_session_streaming("session-1", "hello")]

    assert len(events) == 1
    assert isinstance(events[0], StoppedEvent)


@pytest.mark.asyncio
async def test_prompt_session_streaming_raises_timeout_when_processor_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    session_repo = SimpleNamespace(
        find_by_id=AsyncMock(return_value=SimpleNamespace()),
        to_entity=lambda _: SimpleNamespace(sdk_session_id="sdk-1"),
    )
    _patch_session_repo(monkeypatch, session_repo)
    service = prompt_module.ClaudePromptService()
    service.query_builder.setup_query = AsyncMock(return_value=SimpleNamespace(name="opts"))
    client = FakeClient(
        messages=[
            ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="sdk-1",
            )
        ]
    )

    class FakeProcessor:
        def __init__(self, options):
            self.state = SimpleNamespace(last_activity_time=0.0, idle_timeout_ms=1000, message_count=9)

        def has_timed_out(self):
            return True

        def get_state(self):
            return self.state

        async def process(self, msg):
            return []

    monkeypatch.setattr(prompt_module, "ClaudeSDKClient", lambda options: client)
    monkeypatch.setattr(prompt_module, "SDKMessageProcessor", FakeProcessor)

    with pytest.raises(TimeoutError, match="Claude SDK idle timeout"):
        async for _ in service.prompt_session_streaming("session-1", "hello"):
            pass


@pytest.mark.asyncio
async def test_cleanup_client_cover_success_and_failures() -> None:
    service = prompt_module.ClaudePromptService()

    ok_client = FakeClient()
    cleanup_fail_client = FakeClient()
    cleanup_fail_client.disconnect = AsyncMock(side_effect=RuntimeError("disconnect failed"))
    service.active_clients["ok"] = ok_client
    service.active_clients["cleanup-fail"] = cleanup_fail_client

    await service.cleanup_client("ok")
    await service.cleanup_client("cleanup-fail")
    await service.cleanup_client("missing")

    assert ok_client.disconnect_calls == 1
    cleanup_fail_client.disconnect.assert_awaited_once()
    assert "ok" not in service.active_clients
    assert "cleanup-fail" not in service.active_clients
