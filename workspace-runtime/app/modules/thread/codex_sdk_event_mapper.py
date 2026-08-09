from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.modules.thread.execution import AgentEvent


class CodexSdkEventMapper:
    """Map Codex SDK notifications to thread AgentEvent values."""

    def __init__(self) -> None:
        self._terminal_error = False
        self._plan_revision = 0

    @property
    def has_terminal_error(self) -> bool:
        return self._terminal_error

    def map_notification(self, method: str, payload: object) -> list[AgentEvent]:
        if method in {"hook/started", "hook/completed", "configWarning"}:
            return []

        if method == "item/agentMessage/delta":
            return []

        if method == "thread/tokenUsage/updated":
            usage = self._usage_payload(
                getattr(payload, "token_usage", None) or getattr(payload, "usage", None)
            )
            return [AgentEvent(type="metadata", usage=usage)] if usage else []

        if method == "error":
            if bool(getattr(payload, "will_retry", False)):
                return []
            self._terminal_error = True
            message = self._error_message(payload)
            return [
                AgentEvent(
                    type="error",
                    content=self._text_content(message),
                    error_code="codex_execution_failed",
                    error_info={"message": message},
                )
            ]

        if method == "turn/plan/updated":
            todos = self._plan_todos(getattr(payload, "plan", None) or [])
            self._plan_revision += 1
            occurrence_id = uuid4().hex
            tool_call_key = f"turn-plan-write:{occurrence_id}"
            return [
                AgentEvent(
                    type="tool_call",
                    content={
                        "name": "TodoWrite",
                        "input": {"todos": todos},
                    },
                    source_event_key=f"codex:plan:{occurrence_id}:call",
                    tool_call_key=tool_call_key,
                ),
                AgentEvent(
                    type="tool_result",
                    content={
                        "result": self._todo_text("Updated todo list", todos),
                        "is_error": False,
                    },
                    source_event_key=(f"codex:plan:{occurrence_id}:provider-result"),
                    tool_call_key=tool_call_key,
                    result_kind="provider_result",
                ),
            ]

        item = self._root_item(getattr(payload, "item", None))
        if item is not None:
            item_type = str(getattr(item, "type", "") or "")
            item_id = str(getattr(item, "id", "") or "")
            tool_call_key = f"{item_type}:{item_id}"

            if item_type == "agentMessage" and method == "item/completed":
                text = self._string_attr(item, "text")
                if not text:
                    return []
                return [AgentEvent(type="agent_text", content=self._text_content(text))]

            if item_type == "commandExecution" and method == "item/started":
                return [
                    AgentEvent(
                        type="tool_call",
                        content={
                            "name": "Bash",
                            "input": {
                                "command": getattr(item, "command", None) or "",
                                "cwd": self._jsonable(getattr(item, "cwd", None)),
                            },
                        },
                        source_event_key=f"codex:{item_type}:{item_id}:call",
                        tool_call_key=tool_call_key,
                    )
                ]

            if item_type == "commandExecution" and method == "item/completed":
                status = str(getattr(item, "status", "") or "").lower()
                return [
                    AgentEvent(
                        type="tool_result",
                        content={
                            "result": (
                                getattr(item, "aggregated_output", None)
                                or getattr(item, "output", None)
                                or ""
                            ),
                            "is_error": status in {"failed", "error"},
                        },
                        source_event_key=(
                            f"codex:{item_type}:{item_id}:provider-result"
                        ),
                        tool_call_key=tool_call_key,
                        result_kind="provider_result",
                    )
                ]

            if item_type == "mcpToolCall" and method == "item/started":
                return [
                    AgentEvent(
                        type="tool_call",
                        content={
                            "name": self._mcp_tool_name(item),
                            "input": self._jsonable(
                                getattr(item, "arguments", None) or {}
                            ),
                        },
                        source_event_key=f"codex:{item_type}:{item_id}:call",
                        tool_call_key=tool_call_key,
                    )
                ]

            if item_type == "mcpToolCall" and method == "item/completed":
                status = str(getattr(item, "status", "") or "").lower()
                return [
                    AgentEvent(
                        type="tool_result",
                        content={
                            "result": self._jsonable(getattr(item, "result", None)),
                            "is_error": status in {"failed", "error"},
                        },
                        source_event_key=(
                            f"codex:{item_type}:{item_id}:provider-result"
                        ),
                        tool_call_key=tool_call_key,
                        result_kind="provider_result",
                    )
                ]

            if item_type == "webSearch" and method == "item/started":
                return [
                    AgentEvent(
                        type="tool_call",
                        content={
                            "name": "WebSearch",
                            "input": {"query": getattr(item, "query", None) or ""},
                        },
                        source_event_key=f"codex:{item_type}:{item_id}:call",
                        tool_call_key=tool_call_key,
                    )
                ]

            if item_type == "webSearch" and method == "item/completed":
                return [
                    AgentEvent(
                        type="tool_result",
                        content={
                            "result": json.dumps(
                                {
                                    "query": getattr(item, "query", None) or "",
                                    "action": self._jsonable(
                                        getattr(item, "action", None)
                                    ),
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            "is_error": False,
                        },
                        source_event_key=(
                            f"codex:{item_type}:{item_id}:provider-result"
                        ),
                        tool_call_key=tool_call_key,
                        result_kind="provider_result",
                    )
                ]

            if item_type == "fileChange":
                return []

        return []

    def complete_event(self) -> AgentEvent | None:
        if self._terminal_error:
            return None
        return AgentEvent(type="complete")

    @staticmethod
    def _text_content(value: str) -> dict[str, list[dict[str, str]]]:
        return {"parts": [{"type": "text", "text": value}]}

    @staticmethod
    def _error_message(payload: object) -> str:
        error = getattr(payload, "error", None)
        message = getattr(error, "message", None)
        if isinstance(message, str) and message.strip():
            return message.strip()
        return "codex_execution_failed"

    @staticmethod
    def _string_attr(payload: object, name: str) -> str | None:
        value = getattr(payload, name, None)
        return value if isinstance(value, str) else None

    @staticmethod
    def _usage_payload(token_usage: object) -> dict[str, Any] | None:
        if token_usage is None:
            return None

        def breakdown(value: object) -> dict[str, int]:
            return {
                "input_tokens": int(getattr(value, "input_tokens", 0) or 0),
                "cached_input_tokens": int(
                    getattr(value, "cached_input_tokens", 0) or 0
                ),
                "output_tokens": int(getattr(value, "output_tokens", 0) or 0),
                "reasoning_output_tokens": int(
                    getattr(value, "reasoning_output_tokens", 0) or 0
                ),
                "total_tokens": int(getattr(value, "total_tokens", 0) or 0),
            }

        return {
            "token_usage": {
                "last": breakdown(getattr(token_usage, "last", None)),
                "total": breakdown(getattr(token_usage, "total", None)),
                "model_context_window": getattr(
                    token_usage,
                    "model_context_window",
                    None,
                ),
            }
        }

    @staticmethod
    def _root_item(value: object) -> object | None:
        return getattr(value, "root", None)

    @staticmethod
    def _mcp_tool_name(item: object) -> str:
        server = str(getattr(item, "server", "") or "")
        tool = str(getattr(item, "tool", "") or "")
        if server and tool:
            return f"mcp__{server}__{tool}"
        return "mcp_tool"

    @staticmethod
    def _plan_todos(plan: list[object]) -> list[dict[str, str]]:
        todos: list[dict[str, str]] = []
        for index, step in enumerate(plan, start=1):
            status = str(getattr(step, "status", "") or "").lower()
            todos.append(
                {
                    "id": str(index),
                    "content": str(getattr(step, "step", "") or ""),
                    "status": "completed" if status == "completed" else "pending",
                }
            )
        return todos

    @staticmethod
    def _todo_text(prefix: str, todos: list[dict[str, str]]) -> str:
        lines = [prefix + ":"]
        for todo in todos:
            marker = "x" if todo["status"] == "completed" else " "
            lines.append(f"- [{marker}] {todo['content']}")
        return "\n".join(lines)

    @classmethod
    def _jsonable(cls, value: object) -> object:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=False)
        if isinstance(value, dict):
            return {key: cls._jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._jsonable(item) for item in value]
        if isinstance(value, str | int | float | bool):
            return value
        return str(value)
