from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    ServerToolResultBlock,
    ServerToolUseBlock,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from app.modules.thread.claude_sdk_event_mapper import ClaudeSdkEventMapper


def test_system_init_maps_to_existing_thread_contract() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        SystemMessage(
            subtype="init",
            data={
                "session_id": "session-1",
                "model": "claude-sonnet-4-5-20250929",
                "cwd": "/workspace",
                "tools": ["Read", "Bash"],
                "slash_commands": ["compact"],
                "output_style": "default",
                "agents": ["general-purpose"],
                "skills": ["code"],
                "plugins": ["example"],
                "mcp_servers": [{"name": "aileron", "status": "connected"}],
            },
        )
    )

    assert [event.type for event in events] == ["system_init"]
    assert events[0].content == {
        "agentResumeId": "session-1",
        "model": "claude-sonnet-4-5-20250929",
        "cwd": "/workspace",
        "tools": ["Read", "Bash"],
        "slashCommands": ["compact"],
        "outputStyle": "default",
        "agents": ["general-purpose"],
        "skills": ["code"],
        "plugins": ["example"],
        "mcpServers": [{"name": "aileron", "status": "connected"}],
    }
    assert events[0].raw is not None


def test_assistant_blocks_map_to_text_thinking_and_tool_call() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        AssistantMessage(
            content=[
                ThinkingBlock(thinking="considering", signature="sig"),
                TextBlock(text="hello"),
                ToolUseBlock(
                    id="tool-1",
                    name="mcp__aileron__ask_user_question",
                    input={"question": "Continue?"},
                ),
            ],
            model="claude-sonnet-4-5-20250929",
            usage={"input_tokens": 3, "output_tokens": 5},
        )
    )

    assert [event.type for event in events] == [
        "thinking",
        "agent_text",
        "tool_call",
    ]
    assert events[0].content == {"parts": [{"type": "text", "text": "considering"}]}
    assert events[1].content == {"parts": [{"type": "text", "text": "hello"}]}
    assert events[2].content == {
        "name": "mcp__aileron__ask_user_question",
        "input": {"question": "Continue?"},
    }
    assert events[2].tool_call_key == "tool-1"
    assert events[2].source_event_key == "claude:tool:tool-1:call"
    assert all(
        event.usage == {"input_tokens": 3, "output_tokens": 5} for event in events
    )


def test_server_tool_blocks_map_to_tool_events() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        AssistantMessage(
            content=[
                ServerToolUseBlock(
                    id="server-tool-1",
                    name="web_search",
                    input={"query": "Claude SDK"},
                ),
                ServerToolResultBlock(
                    tool_use_id="server-tool-1",
                    content={"type": "web_search_result", "items": []},
                ),
            ],
            model="claude-sonnet-4-5-20250929",
            usage={"input_tokens": 7, "output_tokens": 11},
        )
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content == {
        "name": "web_search",
        "input": {"query": "Claude SDK"},
    }
    assert events[1].content == {
        "result": {"type": "web_search_result", "items": []},
        "is_error": False,
    }
    assert events[1].tool_call_key == "server-tool-1"
    assert events[1].result_kind == "provider_result"


def test_assistant_parent_tool_identity_is_preserved_for_nested_call() -> None:
    mapper = ClaudeSdkEventMapper()

    [event] = mapper.map_message(
        AssistantMessage(
            content=[ToolUseBlock(id="child", name="Read", input={"path": "a"})],
            model="claude-sonnet-4-5-20250929",
            parent_tool_use_id="parent",
        )
    )

    assert event.tool_call_key == "child"
    assert event.parent_tool_call_key == "parent"


def test_user_tool_result_maps_to_tool_result_event() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        UserMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool-1",
                    content=[{"type": "text", "text": "approved"}],
                    is_error=False,
                )
            ]
        )
    )

    assert [event.type for event in events] == ["tool_result"]
    assert events[0].content == {
        "result": [{"type": "text", "text": "approved"}],
        "is_error": False,
    }


def test_user_text_replay_does_not_create_agent_message() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(UserMessage(content=[TextBlock(text="user prompt")]))

    assert events == []


def test_success_result_completes_turn() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            usage={"input_tokens": 3},
        )
    )

    assert events == []
    assert mapper.complete_event().type == "complete"


def test_error_result_is_terminal_and_suppresses_complete() -> None:
    mapper = ClaudeSdkEventMapper()

    events = mapper.map_message(
        ResultMessage(
            subtype="error",
            duration_ms=1,
            duration_api_ms=1,
            is_error=True,
            num_turns=1,
            session_id="session-1",
            result="permission denied",
            usage={"input_tokens": 3},
        )
    )

    assert [event.type for event in events] == ["error"]
    assert events[0].error_code == "claude_execution_failed"
    assert events[0].error_info == {"message": "permission denied"}
    assert events[0].content == {
        "parts": [{"type": "text", "text": "permission denied"}]
    }
    assert mapper.has_terminal_error is True
    assert mapper.complete_event() is None
