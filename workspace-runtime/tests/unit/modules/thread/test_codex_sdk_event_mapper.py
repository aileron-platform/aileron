from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.thread.codex_sdk_event_mapper import CodexSdkEventMapper


@dataclass
class DeltaPayload:
    delta: str


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


@dataclass
class UsagePayload:
    token_usage: ThreadUsage


@dataclass
class TurnError:
    message: str


@dataclass
class ErrorPayload:
    error: TurnError
    will_retry: bool


@dataclass
class SdkItem:
    id: str
    type: str
    command: str | None = None
    cwd: object | None = None
    status: str | None = None
    aggregated_output: str | None = None
    output: str | None = None
    text: str | None = None
    phase: str | None = None
    server: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: object | None = None
    query: str | None = None
    action: object | None = None
    changes: list[dict[str, Any]] | None = None


@dataclass
class SdkRootItem:
    root: SdkItem


@dataclass
class ItemPayload:
    item: SdkRootItem


@dataclass
class LegacyItemPayload:
    item: SdkItem


@dataclass
class PlanStep:
    step: str
    status: str


@dataclass
class PlanPayload:
    plan: list[PlanStep]


@dataclass
class ModelDumpResult:
    content: list[dict[str, str]]

    def model_dump(self, *, mode: str = "python", by_alias: bool = False) -> dict:
        return {"content": self.content}


def item_payload(item: SdkItem) -> ItemPayload:
    return ItemPayload(item=SdkRootItem(root=item))


def test_agent_message_delta_is_not_persisted_as_fragmented_text() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/agentMessage/delta",
        DeltaPayload(delta="hello"),
    )

    assert events == []


def test_agent_message_completed_maps_to_single_text_message() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/completed",
        item_payload(
            SdkItem(
                id="msg-1",
                type="agentMessage",
                text="我先讀這份文件。",
            )
        ),
    )

    assert [event.type for event in events] == ["agent_text"]
    assert events[0].content == {
        "parts": [{"type": "text", "text": "我先讀這份文件。"}]
    }


def test_token_usage_maps_to_metadata_event() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "thread/tokenUsage/updated",
        UsagePayload(
            token_usage=ThreadUsage(
                last=TokenBreakdown(
                    input_tokens=3,
                    cached_input_tokens=4,
                    output_tokens=5,
                    reasoning_output_tokens=0,
                    total_tokens=12,
                ),
                total=TokenBreakdown(
                    input_tokens=30,
                    cached_input_tokens=40,
                    output_tokens=50,
                    reasoning_output_tokens=0,
                    total_tokens=120,
                ),
                model_context_window=200000,
            )
        ),
    )

    assert [event.type for event in events] == ["metadata"]
    assert events[0].usage == {
        "token_usage": {
            "last": {
                "input_tokens": 3,
                "cached_input_tokens": 4,
                "output_tokens": 5,
                "reasoning_output_tokens": 0,
                "total_tokens": 12,
            },
            "total": {
                "input_tokens": 30,
                "cached_input_tokens": 40,
                "output_tokens": 50,
                "reasoning_output_tokens": 0,
                "total_tokens": 120,
            },
            "model_context_window": 200000,
        }
    }


def test_hook_and_config_lifecycle_events_are_not_user_visible_messages() -> None:
    mapper = CodexSdkEventMapper()

    assert mapper.map_notification("hook/started", object()) == []
    assert mapper.map_notification("hook/completed", object()) == []
    assert mapper.map_notification("configWarning", object()) == []


def test_retryable_error_is_not_terminal_and_does_not_emit_user_visible_fallback_copy() -> (
    None
):
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "error",
        ErrorPayload(error=TurnError(message="temporary overload"), will_retry=True),
    )

    assert events == []
    assert mapper.has_terminal_error is False
    assert mapper.complete_event().type == "complete"


def test_non_retryable_error_is_terminal_and_suppresses_complete() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "error",
        ErrorPayload(error=TurnError(message="fatal failure"), will_retry=False),
    )

    assert [event.type for event in events] == ["error"]
    assert events[0].error_code == "codex_execution_failed"
    assert events[0].content == {"parts": [{"type": "text", "text": "fatal failure"}]}
    assert events[0].error_info == {"message": "fatal failure"}
    assert mapper.has_terminal_error is True
    assert mapper.complete_event() is None


def test_command_execution_started_maps_to_tool_call_from_sdk_item_object() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/started",
        item_payload(
            SdkItem(
                id="cmd-1",
                type="commandExecution",
                command="pytest",
                cwd="/workspace",
            )
        ),
    )

    assert [event.type for event in events] == ["tool_call"]
    assert events[0].content == {
        "name": "Bash",
        "input": {"command": "pytest", "cwd": "/workspace"},
    }
    assert events[0].tool_call_key == "commandExecution:cmd-1"


def test_command_execution_started_serializes_sdk_path_objects() -> None:
    class SdkPath:
        def __str__(self) -> str:
            return "/workspace"

    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/started",
        item_payload(
            SdkItem(
                id="cmd-1",
                type="commandExecution",
                command="pytest",
                cwd=SdkPath(),
            )
        ),
    )

    assert events[0].content["input"] == {
        "command": "pytest",
        "cwd": "/workspace",
    }


def test_command_execution_completed_maps_to_tool_result_from_sdk_item_object() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/completed",
        item_payload(
            SdkItem(
                id="cmd-1",
                type="commandExecution",
                status="completed",
                aggregated_output="ok",
            )
        ),
    )

    assert [event.type for event in events] == ["tool_result"]
    assert events[0].content == {
        "result": "ok",
        "is_error": False,
    }
    assert events[0].tool_call_key == "commandExecution:cmd-1"
    assert events[0].result_kind == "provider_result"


def test_mcp_tool_call_started_uses_server_and_tool_name() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/started",
        item_payload(
            SdkItem(
                id="mcp-1",
                type="mcpToolCall",
                server="aileron",
                tool="ask_user_question",
                arguments={"question": "Continue?"},
            )
        ),
    )

    assert [event.type for event in events] == ["tool_call"]
    assert events[0].content == {
        "name": "mcp__aileron__ask_user_question",
        "input": {"question": "Continue?"},
    }


def test_mcp_tool_call_completed_serializes_pydantic_result() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/completed",
        item_payload(
            SdkItem(
                id="mcp-1",
                type="mcpToolCall",
                server="aileron",
                tool="show_canvas_artifact",
                status="completed",
                result=ModelDumpResult(content=[{"type": "text", "text": "ok"}]),
            )
        ),
    )

    assert [event.type for event in events] == ["tool_result"]
    assert events[0].content == {
        "result": {"content": [{"type": "text", "text": "ok"}]},
        "is_error": False,
    }


def test_web_search_maps_to_tool_events_without_fake_results() -> None:
    mapper = CodexSdkEventMapper()

    started = mapper.map_notification(
        "item/started",
        item_payload(SdkItem(id="search-1", type="webSearch", query="Aileron")),
    )
    completed = mapper.map_notification(
        "item/completed",
        item_payload(SdkItem(id="search-1", type="webSearch", query="Aileron")),
    )

    assert started[0].content == {
        "name": "WebSearch",
        "input": {"query": "Aileron"},
    }
    assert completed[0].content == {
        "result": '{\n  "query": "Aileron",\n  "action": null\n}',
        "is_error": False,
    }


def test_plan_updated_maps_to_todo_tool_events_from_sdk_notification() -> None:
    mapper = CodexSdkEventMapper()
    payload = PlanPayload(
        plan=[
            PlanStep(step="Fix queue", status="pending"),
            PlanStep(step="Ship change", status="completed"),
        ]
    )

    events = mapper.map_notification("turn/plan/updated", payload)

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content == {
        "name": "TodoWrite",
        "input": {
            "todos": [
                {"id": "1", "content": "Fix queue", "status": "pending"},
                {"id": "2", "content": "Ship change", "status": "completed"},
            ]
        },
    }
    assert (
        events[1].content["result"]
        == "Updated todo list:\n- [ ] Fix queue\n- [x] Ship change"
    )


def test_repeated_plan_content_remains_distinct_occurrences() -> None:
    mapper = CodexSdkEventMapper()
    payloads = [
        PlanPayload(plan=[PlanStep(step=value, status="pending")])
        for value in ("A", "B", "A")
    ]

    occurrences = [
        mapper.map_notification("turn/plan/updated", payload) for payload in payloads
    ]

    keys = [events[0].tool_call_key for events in occurrences]
    assert len(set(keys)) == 3
    assert all(
        events[0].tool_call_key == events[1].tool_call_key for events in occurrences
    )
    assert all(events[1].result_kind == "provider_result" for events in occurrences)


def test_file_change_is_ignored_until_append_only_representation_exists() -> None:
    mapper = CodexSdkEventMapper()

    events = mapper.map_notification(
        "item/completed",
        item_payload(
            SdkItem(id="file-1", type="fileChange", changes=[{"path": "app.py"}])
        ),
    )

    assert events == []


def test_legacy_dict_or_unwrapped_item_shape_is_not_accepted() -> None:
    mapper = CodexSdkEventMapper()

    assert (
        mapper.map_notification(
            "item/started",
            LegacyItemPayload(
                item=SdkItem(id="cmd-1", type="commandExecution", command="pytest")
            ),
        )
        == []
    )
