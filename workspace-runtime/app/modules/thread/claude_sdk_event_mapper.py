from __future__ import annotations

from typing import Any

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

from app.modules.thread.execution import AgentEvent


class ClaudeSdkEventMapper:
    """Map Claude Agent SDK messages to thread AgentEvent values."""

    def __init__(self) -> None:
        self._terminal_error = False

    @property
    def has_terminal_error(self) -> bool:
        return self._terminal_error

    def map_message(self, message: object) -> list[AgentEvent]:
        if isinstance(message, SystemMessage):
            return self._map_system(message)
        if isinstance(message, AssistantMessage):
            return self._map_assistant(message)
        if isinstance(message, UserMessage):
            return self._map_user(message)
        if isinstance(message, ResultMessage):
            return self._map_result(message)
        return []

    def complete_event(self) -> AgentEvent | None:
        if self._terminal_error:
            return None
        return AgentEvent(type="complete")

    def _map_system(self, message: SystemMessage) -> list[AgentEvent]:
        if message.subtype != "init":
            return []
        data = message.data
        return [
            AgentEvent(
                type="system_init",
                content={
                    "agentResumeId": self._optional_string(data.get("session_id")),
                    "model": self._optional_string(data.get("model")),
                    "cwd": self._optional_string(data.get("cwd")),
                    "tools": self._string_list(data.get("tools")),
                    "slashCommands": self._string_list(data.get("slash_commands")),
                    "outputStyle": self._optional_string(data.get("output_style")),
                    "agents": self._string_list(data.get("agents")),
                    "skills": self._string_list(data.get("skills")),
                    "plugins": self._string_list(data.get("plugins")),
                    "mcpServers": self._mcp_servers(data.get("mcp_servers")),
                },
                raw=dict(data),
            )
        ]

    def _map_assistant(self, message: AssistantMessage) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        parent_tool_call_key = self._optional_string(
            getattr(message, "parent_tool_use_id", None)
        )
        for block in message.content:
            if isinstance(block, TextBlock):
                events.append(
                    AgentEvent(
                        type="agent_text",
                        content=self._text_content(block.text),
                        usage=message.usage,
                    )
                )
            elif isinstance(block, ThinkingBlock):
                events.append(
                    AgentEvent(
                        type="thinking",
                        content=self._text_content(block.thinking),
                        usage=message.usage,
                    )
                )
            elif isinstance(block, ToolUseBlock):
                events.append(
                    AgentEvent(
                        type="tool_call",
                        content={
                            "name": block.name,
                            "input": block.input,
                        },
                        source_event_key=f"claude:tool:{block.id}:call",
                        tool_call_key=block.id,
                        parent_tool_call_key=parent_tool_call_key,
                        usage=message.usage,
                    )
                )
            elif isinstance(block, ServerToolUseBlock):
                events.append(
                    AgentEvent(
                        type="tool_call",
                        content={
                            "name": block.name,
                            "input": block.input,
                        },
                        source_event_key=f"claude:tool:{block.id}:call",
                        tool_call_key=block.id,
                        parent_tool_call_key=parent_tool_call_key,
                        usage=message.usage,
                    )
                )
            elif isinstance(block, ServerToolResultBlock):
                events.append(
                    AgentEvent(
                        type="tool_result",
                        content={
                            "result": block.content,
                            "is_error": False,
                        },
                        source_event_key=(
                            f"claude:tool:{block.tool_use_id}:provider-result"
                        ),
                        tool_call_key=block.tool_use_id,
                        result_kind="provider_result",
                        usage=message.usage,
                    )
                )
        return events

    def _map_user(self, message: UserMessage) -> list[AgentEvent]:
        if not isinstance(message.content, list):
            return []
        events: list[AgentEvent] = []
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                events.append(
                    AgentEvent(
                        type="tool_result",
                        content={
                            "result": block.content,
                            "is_error": bool(block.is_error),
                        },
                        source_event_key=(
                            f"claude:tool:{block.tool_use_id}:provider-result"
                        ),
                        tool_call_key=block.tool_use_id,
                        result_kind="provider_result",
                    )
                )
        return events

    def _map_result(self, message: ResultMessage) -> list[AgentEvent]:
        if not message.is_error:
            return []
        self._terminal_error = True
        text = message.result or message.stop_reason or "claude_execution_failed"
        return [
            AgentEvent(
                type="error",
                content=self._text_content(text),
                usage=message.usage,
                error_code="claude_execution_failed",
                error_info={"message": text},
            )
        ]

    @staticmethod
    def _text_content(value: str) -> dict[str, list[dict[str, str]]]:
        return {"parts": [{"type": "text", "text": value}]}

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        return [str(item) for item in value] if isinstance(value, list) else []

    @staticmethod
    def _mcp_servers(value: Any) -> list[dict[str, str | None]]:
        if not isinstance(value, list):
            return []
        return [
            {
                "name": str(item.get("name") or ""),
                "status": (
                    str(item["status"]) if item.get("status") is not None else None
                ),
            }
            for item in value
            if isinstance(item, dict)
        ]
