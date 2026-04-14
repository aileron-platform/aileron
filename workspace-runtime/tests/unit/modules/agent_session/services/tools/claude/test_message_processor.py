from __future__ import annotations

import time

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk.types import StreamEvent

from app.modules.agent_session.domain.enums import MessageRole
from app.modules.agent_session.services.tools.base.types import (
    CompleteEvent,
    EndEvent,
    PartialEvent,
    ResultEvent,
    ThinkingCompleteEvent,
    ThinkingPartialEvent,
    ToolCompleteEvent,
    ToolStartEvent,
)
from app.modules.agent_session.services.tools.claude.message_processor import (
    ProcessorOptions,
    SDKMessageProcessor,
)


@pytest.mark.asyncio
async def test_process_assistant_message_tracks_tools_thinking_and_results() -> None:
    processor = SDKMessageProcessor(ProcessorOptions(session_id="session-1"))
    message = AssistantMessage(
        content=[
            TextBlock(text="hello"),
            ThinkingBlock(thinking="reasoning", signature="sig"),
            ToolUseBlock(id="tool-1", name="AskUserQuestion", input={"question": "Name?"}),
            ToolResultBlock(tool_use_id="tool-1", content="Alice", is_error=True),
        ],
        model="claude-3",
    )

    events = await processor.process(message)

    assert processor.get_state().message_count == 1
    assert [type(event) for event in events] == [
        ThinkingCompleteEvent,
        ToolStartEvent,
        ToolCompleteEvent,
        CompleteEvent,
    ]
    complete_event = events[-1]
    assert isinstance(complete_event, CompleteEvent)
    assert complete_event.role == MessageRole.ASSISTANT
    assert complete_event.tool_uses == [
        {
            "id": "tool-1",
            "name": "AskUserQuestion",
            "input": {"question": "Name?"},
        }
    ]
    assert complete_event.content == [
        {"type": "text", "text": "hello"},
        {"type": "thinking", "thinking": "reasoning"},
        {
            "type": "tool_use",
            "id": "tool-1",
            "name": "AskUserQuestion",
            "input": {"question": "Name?"},
        },
        {
            "type": "tool_result",
            "tool_use_id": "tool-1",
            "content": "Alice",
            "is_error": False,
        },
    ]
    assert processor.get_state().tool_use_registry == {"tool-1": "AskUserQuestion"}


@pytest.mark.asyncio
async def test_process_result_message_captures_usage_and_structured_output() -> None:
    processor = SDKMessageProcessor(ProcessorOptions(session_id="session-1"))
    message = ResultMessage(
        subtype="success",
        duration_ms=1200,
        duration_api_ms=900,
        is_error=False,
        num_turns=3,
        session_id="sdk-session-1",
        stop_reason="end_turn",
        total_cost_usd=0.42,
        usage={
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_read_input_tokens": 5,
            "cache_creation_input_tokens": 7,
        },
        result="done",
        structured_output={"answer": 42},
    )

    events = await processor.process(message)

    assert [type(event) for event in events] == [ResultEvent, EndEvent]
    result_event = events[0]
    assert isinstance(result_event, ResultEvent)
    assert processor.get_state().captured_agent_session_id == "sdk-session-1"
    assert result_event.token_usage.input == 10
    assert result_event.token_usage.output == 20
    assert result_event.token_usage.cache_read == 5
    assert result_event.token_usage.cache_creation == 7
    assert result_event.structured_output == {"answer": 42}
    assert result_event.raw_sdk_message["structured_output"] == {"answer": 42}
    assert result_event.raw_sdk_message["duration_ms"] == 1200
    assert events[1].reason == "result"


@pytest.mark.asyncio
async def test_process_user_and_system_messages_update_content_and_model() -> None:
    processor = SDKMessageProcessor(ProcessorOptions(session_id="session-1"))
    processor.get_state().tool_use_registry["tool-1"] = "AskUserQuestion"

    user_events = await processor.process(
        UserMessage(
            content=[
                TextBlock(text="user text"),
                ToolResultBlock(tool_use_id="tool-1", content="answer", is_error=True),
            ]
        )
    )
    system_events = await processor.process(
        SystemMessage(subtype="meta", data={"model": "claude-4", "source": "sdk"})
    )

    assert len(user_events) == 2
    assert isinstance(user_events[0], ToolCompleteEvent)
    assert isinstance(user_events[1], CompleteEvent)
    assert user_events[1].role == MessageRole.USER
    assert user_events[1].content == [
        {"type": "text", "text": "user text"},
        {
            "type": "tool_result",
            "tool_use_id": "tool-1",
            "content": "answer",
            "is_error": False,
        },
    ]
    assert len(system_events) == 1
    assert isinstance(system_events[0], CompleteEvent)
    assert system_events[0].role == MessageRole.SYSTEM
    assert system_events[0].content == [
        {"type": "system", "subtype": "meta", "data": {"model": "claude-4", "source": "sdk"}}
    ]
    assert processor.get_state().resolved_model == "claude-4"


@pytest.mark.asyncio
async def test_process_stream_events_cover_message_start_delta_and_stop() -> None:
    processor = SDKMessageProcessor(ProcessorOptions(session_id="session-1"))

    assert await processor.process(
        StreamEvent(
            uuid="1",
            session_id="sdk-session",
            event={"type": "message_start", "message": {"model": "claude-stream"}},
        )
    ) == []
    tool_start_events = await processor.process(
        StreamEvent(
            uuid="2",
            session_id="sdk-session",
            event={
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "tool-1", "name": "Read"},
            },
        )
    )
    await processor.process(
        StreamEvent(
            uuid="3",
            session_id="sdk-session",
            event={"type": "content_block_start", "index": 1, "content_block": {"type": "thinking"}},
        )
    )
    await processor.process(
        StreamEvent(
            uuid="4",
            session_id="sdk-session",
            event={"type": "content_block_start", "index": 2, "content_block": {"type": "text"}},
        )
    )
    text_delta_events = await processor.process(
        StreamEvent(
            uuid="5",
            session_id="sdk-session",
            event={"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}},
        )
    )
    thinking_delta_events = await processor.process(
        StreamEvent(
            uuid="6",
            session_id="sdk-session",
            event={
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": "pondering"},
            },
        )
    )
    assert await processor.process(
        StreamEvent(
            uuid="7",
            session_id="sdk-session",
            event={"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{"}},
        )
    ) == []
    tool_stop_events = await processor.process(
        StreamEvent(
            uuid="8",
            session_id="sdk-session",
            event={"type": "content_block_stop", "index": 0},
        )
    )
    thinking_stop_events = await processor.process(
        StreamEvent(
            uuid="9",
            session_id="sdk-session",
            event={"type": "content_block_stop", "index": 1},
        )
    )

    assert len(tool_start_events) == 1
    assert isinstance(tool_start_events[0], ToolStartEvent)
    assert tool_start_events[0].tool_name == "Read"
    assert len(text_delta_events) == 1
    assert isinstance(text_delta_events[0], PartialEvent)
    assert text_delta_events[0].text == "hello"
    assert text_delta_events[0].resolved_model == "claude-stream"
    assert len(thinking_delta_events) == 1
    assert isinstance(thinking_delta_events[0], ThinkingPartialEvent)
    assert thinking_delta_events[0].thinking_chunk == "pondering"
    assert len(tool_stop_events) == 1
    assert isinstance(tool_stop_events[0], ToolCompleteEvent)
    assert tool_stop_events[0].tool_use_id == "tool-1"
    assert len(thinking_stop_events) == 1
    assert isinstance(thinking_stop_events[0], ThinkingCompleteEvent)
    assert processor.get_state().tool_input_chunk_count == 1
    assert processor.get_state().tool_use_registry["tool-1"] == "Read"


@pytest.mark.asyncio
async def test_process_handles_disabled_streaming_unknown_message_and_timeout() -> None:
    processor = SDKMessageProcessor(
        ProcessorOptions(session_id="session-1", enable_token_streaming=False, idle_timeout_ms=1)
    )

    stream_events = await processor.process(
        StreamEvent(uuid="1", session_id="sdk-session", event={"type": "message_start", "message": {"model": "x"}})
    )
    unknown_events = await processor.process(object())
    processor.get_state().last_activity_time = time.time() - 1

    assert stream_events == []
    assert unknown_events == []
    assert processor.has_timed_out() is True
    assert processor.get_state().message_count == 2
