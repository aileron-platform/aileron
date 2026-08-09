from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.modules.cli_settings.user_scope.paths import runtime_user_home
from app.modules.thread.execution import AgentEvent


OPENCODE_TOOL_NAMES: dict[str, str] = {
    "bash": "Bash",
    "edit": "Edit",
    "write": "Write",
    "read": "Read",
    "grep": "Grep",
    "glob": "Glob",
    "list": "LS",
    "todowrite": "TodoWrite",
    "todoread": "TodoRead",
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
    "task": "Task",
    "aileron_ask_user_question": "mcp__aileron__ask_user_question",
    "aileron_show_canvas_artifact": "mcp__aileron__show_canvas_artifact",
}

REQUIRED_INPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "Bash": ("command",),
    "Edit": ("file_path", "old_string", "new_string"),
    "Write": ("file_path", "content"),
    "Read": ("file_path",),
    "Grep": ("pattern",),
    "Glob": ("pattern",),
    "WebFetch": ("url",),
}

TERMINAL_TOOL_STATUSES = {"completed", "failed", "error"}

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class OpenCodeAcpEventMapper:
    """Map OpenCode ACP session updates to thread AgentEvent values.

    Text and thought chunks are buffered into whole segments instead of being
    emitted per chunk; segments are flushed at tool-call boundaries and at the
    end of the turn.
    """

    def __init__(self) -> None:
        self._seen_tool_call_ids: set[str] = set()
        self._segments: list[tuple[str, list[str]]] = []
        self._aileron_tool_inputs: dict[str, dict[str, Any]] = {}
        # OpenCode mutates the ACP `title` field across a tool call's
        # lifecycle (e.g. "bash" at pending -> the command string at
        # completed). Cache the first-seen normalized raw name per
        # tool_call_id so later updates keep resolving to the same tool.
        self._raw_names: dict[str, str] = {}

    def map_session_update(
        self,
        update: object,
        *,
        session_id: str | None = None,
    ) -> list[AgentEvent]:
        kind = str(getattr(update, "session_update", "") or "")
        raw = self._jsonable(update)

        if kind == "agent_message_chunk":
            self._buffer_text("agent_text", getattr(update, "content", None))
            return []

        if kind == "agent_thought_chunk":
            self._buffer_text("thinking", getattr(update, "content", None))
            return []

        if kind == "tool_call":
            event = self._tool_call_event(update, raw, session_id=session_id)
            return self.flush_events() + ([event] if event is not None else [])

        if kind == "tool_call_update":
            return self.flush_events() + self._tool_update_events(
                update,
                raw,
                session_id=session_id,
            )

        return []

    def flush_events(self) -> list[AgentEvent]:
        events = [
            AgentEvent(type=event_type, content=self._text_content("".join(pieces)))
            for event_type, pieces in self._segments
        ]
        self._segments = []
        return events

    def complete_event(self) -> AgentEvent:
        return AgentEvent(type="complete")

    def _buffer_text(self, event_type: str, content: object) -> None:
        text = self._extract_text(content)
        if not text:
            return
        if self._segments and self._segments[-1][0] == event_type:
            self._segments[-1][1].append(text)
            return
        self._segments.append((event_type, [text]))

    def _tool_call_event(
        self,
        update: object,
        raw: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> AgentEvent | None:
        tool_call_id = self._tool_call_id(update)
        if tool_call_id is None or tool_call_id in self._seen_tool_call_ids:
            return None
        raw_name = self._resolve_raw_name(update, tool_call_id)
        tool_input = self._tool_input(
            update,
            raw_name,
            session_id=session_id,
            tool_call_id=tool_call_id,
        )
        status = str(getattr(update, "status", "") or "").lower()
        if (
            self._is_normalized_tool(raw_name)
            and not self._input_ready(raw_name, tool_input)
            and status not in TERMINAL_TOOL_STATUSES
        ):
            return None
        if self._is_aileron_tool(raw_name) and tool_input:
            self._aileron_tool_inputs[tool_call_id] = tool_input
        self._seen_tool_call_ids.add(tool_call_id)
        return AgentEvent(
            type="tool_call",
            content={
                "name": self._tool_name(raw_name),
                "input": tool_input,
            },
            source_event_key=f"opencode:tool:{tool_call_id}:call",
            tool_call_key=tool_call_id,
            raw=raw,
        )

    def _tool_update_events(
        self,
        update: object,
        raw: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> list[AgentEvent]:
        tool_call_id = self._tool_call_id(update)
        if tool_call_id is None:
            return []

        events: list[AgentEvent] = []
        call_event = self._tool_call_event(update, raw, session_id=session_id)
        if call_event is not None:
            events.append(call_event)

        status = str(getattr(update, "status", "") or "").lower()
        if status not in TERMINAL_TOOL_STATUSES:
            return events

        raw_name = self._resolve_raw_name(update, tool_call_id)
        result = self._tool_result(
            update,
            raw_name,
            session_id=session_id,
            tool_call_id=tool_call_id,
        )
        events.append(
            AgentEvent(
                type="tool_result",
                content={
                    "result": result,
                    "is_error": status in {"failed", "error"},
                },
                source_event_key=(f"opencode:tool:{tool_call_id}:provider-result"),
                tool_call_key=tool_call_id,
                result_kind="provider_result",
                raw=raw,
            )
        )
        return events

    @staticmethod
    def _tool_call_id(update: object) -> str | None:
        value = getattr(update, "tool_call_id", None) or getattr(update, "id", None)
        return str(value) if value is not None else None

    @staticmethod
    def _raw_tool_name(update: object) -> str:
        return (
            str(getattr(update, "title", "") or "")
            or str(getattr(update, "kind", "") or "")
            or "opencode_tool"
        )

    def _resolve_raw_name(self, update: object, tool_call_id: str | None) -> str:
        """Resolve the effective raw tool name for an update.

        OpenCode mutates the ACP `title` field across a tool call's
        lifecycle (e.g. "bash" at pending -> the resolved command string
        at completed). Once a title resolves to a known OpenCode tool
        name, pin it for the tool_call_id so later updates that carry a
        mutated title (which no longer matches a known tool name) still
        resolve to the original tool. First-seen wins: the pin is set only
        if tool_call_id has not been seen before.
        """
        raw_name = self._raw_tool_name(update)
        if tool_call_id is None:
            return raw_name
        if raw_name in OPENCODE_TOOL_NAMES:
            self._raw_names.setdefault(tool_call_id, raw_name)
            return self._raw_names[tool_call_id]
        return self._raw_names.get(tool_call_id, raw_name)

    @staticmethod
    def _tool_name(raw_name: str) -> str:
        return OPENCODE_TOOL_NAMES.get(raw_name, raw_name)

    @staticmethod
    def _is_normalized_tool(raw_name: str) -> bool:
        return raw_name in OPENCODE_TOOL_NAMES

    def _tool_input(
        self,
        update: object,
        raw_name: str,
        *,
        session_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> dict[str, Any]:
        if not self._is_normalized_tool(raw_name):
            return {
                "kind": self._jsonable(getattr(update, "kind", None)),
                "title": self._jsonable(getattr(update, "title", None)),
                "raw_input": self._jsonable(getattr(update, "raw_input", None)),
            }
        raw_input = self._jsonable(getattr(update, "raw_input", None))
        merged: dict[str, Any] = dict(raw_input) if isinstance(raw_input, dict) else {}
        state_input = self._state_input(update)
        if state_input is None and session_id and tool_call_id:
            state_input = self._opencode_state_input(session_id, tool_call_id)
        if state_input:
            merged.update(state_input)
        return self._snake_case_top_level_keys(merged)

    @classmethod
    def _is_aileron_tool(cls, raw_name: str) -> bool:
        return cls._tool_name(raw_name).startswith("mcp__aileron__")

    @classmethod
    def _input_ready(cls, raw_name: str, tool_input: dict[str, Any]) -> bool:
        if not tool_input:
            return False
        required = REQUIRED_INPUT_FIELDS.get(cls._tool_name(raw_name), ())
        return all(field in tool_input for field in required)

    @staticmethod
    def _snake_case_top_level_keys(value: dict[str, Any]) -> dict[str, Any]:
        return {
            _CAMEL_BOUNDARY.sub("_", str(key)).lower(): item
            for key, item in value.items()
        }

    def _tool_result(
        self,
        update: object,
        raw_name: str,
        *,
        session_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> Any:
        raw_output = self._jsonable(getattr(update, "raw_output", None))
        result = (
            raw_output
            if raw_output is not None
            else self._jsonable(getattr(update, "content", None))
        )
        if self._is_aileron_tool(raw_name):
            state_input = (
                self._aileron_tool_inputs.get(tool_call_id)
                if tool_call_id is not None
                else None
            )
            if state_input is None:
                state_input = self._state_input(update)
            if state_input is None and session_id and tool_call_id:
                state_input = self._opencode_state_input(session_id, tool_call_id)
            if state_input is None:
                return result
            if isinstance(result, dict):
                return {**result, "structuredContent": state_input}
            return {"output": result, "structuredContent": state_input}
        if (
            self._is_normalized_tool(raw_name)
            and isinstance(result, dict)
            and isinstance(result.get("output"), str)
        ):
            return result["output"]
        return result

    def _state_input(self, update: object) -> dict[str, Any] | None:
        state = self._jsonable(getattr(update, "state", None))
        if not isinstance(state, dict):
            return None
        state_input = state.get("input")
        return state_input if isinstance(state_input, dict) and state_input else None

    def _opencode_state_input(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> dict[str, Any] | None:
        # Last-resort fallback for OpenCode ACP versions that emit pending
        # tool_call rawInput as {} even though part.state.input contains the
        # arguments. Upstream fixed this on dev in PR #31321, which closes
        # #31313 and #23947:
        # https://github.com/anomalyco/opencode/pull/31321
        # https://github.com/anomalyco/opencode/issues/31313
        # https://github.com/anomalyco/opencode/issues/23947
        db_path = Path(
            os.environ.get(
                "OPENCODE_DB_PATH",
                str(
                    runtime_user_home()
                    / ".local"
                    / "share"
                    / "opencode"
                    / "opencode.db"
                ),
            )
        )
        if not db_path.exists():
            return None
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
                rows = connection.execute(
                    "select data from part where session_id = ? order by time_created",
                    (session_id,),
                ).fetchall()
        except sqlite3.Error:
            return None

        for (raw_data,) in rows:
            data = self._parse_json_object(raw_data)
            if data.get("type") != "tool" or data.get("callID") != tool_call_id:
                continue
            state = data.get("state")
            if not isinstance(state, dict):
                return None
            state_input = state.get("input")
            return (
                state_input if isinstance(state_input, dict) and state_input else None
            )
        return None

    @staticmethod
    def _parse_json_object(value: object) -> dict[str, Any]:
        if not isinstance(value, str):
            return {}
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _text_content(value: str) -> dict[str, list[dict[str, str]]]:
        return {"parts": [{"type": "text", "text": value}]}

    @classmethod
    def _extract_text(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list | tuple):
            return "".join(cls._extract_text(item) for item in value)
        text = getattr(value, "text", None)
        if isinstance(text, str):
            return text
        return str(value) if isinstance(value, int | float | bool) else ""

    @classmethod
    def _jsonable(cls, value: object) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, list | tuple | set):
            return [cls._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._jsonable(item) for key, item in value.items()}
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return cls._jsonable(model_dump(mode="json", by_alias=True))
        if is_dataclass(value) and not isinstance(value, type):
            return cls._jsonable(asdict(value))
        attrs = (
            {key: item for key, item in vars(value).items() if not key.startswith("_")}
            if hasattr(value, "__dict__")
            else None
        )
        if attrs is not None:
            return cls._jsonable(attrs)
        return str(value)
