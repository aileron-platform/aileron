from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.modules.thread.opencode_acp_event_mapper import (
    OpenCodeAcpEventMapper,
)


@dataclass
class Content:
    text: str


@dataclass
class Update:
    session_update: str
    content: object | None = None
    tool_call_id: str | None = None
    title: str | None = None
    kind: str | None = None
    status: str | None = None
    raw_input: object | None = None
    raw_output: object | None = None
    state: object | None = None


def test_agent_message_chunks_buffer_until_flush() -> None:
    mapper = OpenCodeAcpEventMapper()

    first = mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("hel")])
    )
    second = mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("lo")])
    )
    events = mapper.flush_events()

    assert first == []
    assert second == []
    assert [event.type for event in events] == ["agent_text"]
    assert events[0].content == {"parts": [{"type": "text", "text": "hello"}]}


def test_agent_thought_chunks_buffer_until_flush() -> None:
    mapper = OpenCodeAcpEventMapper()

    pending = mapper.map_session_update(
        Update(session_update="agent_thought_chunk", content=Content("plan"))
    )
    events = mapper.flush_events()

    assert pending == []
    assert [event.type for event in events] == ["thinking"]
    assert events[0].content == {"parts": [{"type": "text", "text": "plan"}]}


def test_flush_preserves_thinking_and_text_segment_order() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(session_update="agent_thought_chunk", content=Content("think"))
    )
    mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("answer")])
    )
    events = mapper.flush_events()

    assert [event.type for event in events] == ["thinking", "agent_text"]
    assert events[0].content == {"parts": [{"type": "text", "text": "think"}]}
    assert events[1].content == {"parts": [{"type": "text", "text": "answer"}]}


def test_flush_events_clears_buffer() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("once")])
    )
    mapper.flush_events()

    assert mapper.flush_events() == []


def test_tool_call_flushes_buffered_text_first() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("before tool")])
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            raw_input={"command": "ls"},
        )
    )

    assert [event.type for event in events] == ["agent_text", "tool_call"]
    assert events[0].content == {"parts": [{"type": "text", "text": "before tool"}]}


def test_tool_call_update_flushes_buffered_text_first() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(session_update="agent_message_chunk", content=[Content("progress")])
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="bash",
            status="completed",
            raw_input={"command": "ls"},
            raw_output="done",
        )
    )

    assert [event.type for event in events] == [
        "agent_text",
        "tool_call",
        "tool_result",
    ]


def test_tool_call_uses_acp_tool_call_id_and_emits_once() -> None:
    mapper = OpenCodeAcpEventMapper()
    update = Update(
        session_update="tool_call",
        tool_call_id="tool-1",
        title="Read file",
        kind="read",
        status="pending",
        raw_input={"path": "README.md"},
    )

    first = mapper.map_session_update(update)
    second = mapper.map_session_update(update)

    assert [event.type for event in first] == ["tool_call"]
    assert first[0].content == {
        "name": "Read file",
        "input": {
            "kind": "read",
            "title": "Read file",
            "raw_input": {"path": "README.md"},
        },
    }
    assert first[0].tool_call_key == "tool-1"
    assert second == []


def test_aileron_mcp_tool_call_uses_canonical_name_and_raw_input() -> None:
    mapper = OpenCodeAcpEventMapper()
    form = {
        "id": "devops-form",
        "title": "DevOps",
        "questions": [
            {
                "id": "experience",
                "label": "Experience",
                "type": "text",
            }
        ],
    }

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="aileron_ask_user_question",
            kind="other",
            status="pending",
            raw_input=form,
        )
    )

    assert event.content == {
        "name": "mcp__aileron__ask_user_question",
        "input": form,
    }


def test_aileron_mcp_tool_call_falls_back_to_opencode_state_input() -> None:
    mapper = OpenCodeAcpEventMapper()
    form = {
        "id": "tool-test",
        "title": "Tool test",
        "questions": [
            {
                "id": "tool",
                "label": "Tool",
                "type": "radio",
                "options": ["ask_user_question", "show_canvas_artifact"],
            }
        ],
    }

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="aileron_ask_user_question",
            kind="other",
            status="completed",
            raw_input={},
            raw_output={
                "output": "Question form delivered to the user.",
                "metadata": {"truncated": False},
            },
            state={"input": form},
        )
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content == {
        "name": "mcp__aileron__ask_user_question",
        "input": form,
    }
    assert events[1].content == {
        "result": {
            "output": "Question form delivered to the user.",
            "metadata": {"truncated": False},
            "structuredContent": form,
        },
        "is_error": False,
    }
    assert events[1].tool_call_key == "tool-1"
    assert events[1].result_kind == "provider_result"


def test_aileron_mcp_tool_call_falls_back_to_opencode_db_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "opencode.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "create table part (session_id text, time_created integer, data text)"
    )
    form = {
        "id": "tool-test",
        "title": "Tool test",
        "questions": [
            {
                "id": "tool",
                "label": "Tool",
                "type": "radio",
                "options": ["ask_user_question", "show_canvas_artifact"],
            }
        ],
    }
    connection.execute(
        "insert into part (session_id, time_created, data) values (?, ?, ?)",
        (
            "session-1",
            1,
            json.dumps(
                {
                    "type": "tool",
                    "tool": "aileron_ask_user_question",
                    "callID": "tool-1",
                    "state": {
                        "status": "completed",
                        "input": form,
                        "output": "Question form delivered to the user.",
                    },
                }
            ),
        ),
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("OPENCODE_DB_PATH", str(db_path))
    mapper = OpenCodeAcpEventMapper()

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="aileron_ask_user_question",
            kind="other",
            status="completed",
            raw_input={},
            raw_output={
                "output": "Question form delivered to the user.",
                "metadata": {"truncated": False},
            },
        ),
        session_id="session-1",
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content["input"] == form
    assert events[1].content["result"]["structuredContent"] == form


def test_aileron_mcp_tool_call_ignores_mismatched_opencode_db_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "opencode.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "create table part (session_id text, time_created integer, data text)"
    )
    connection.execute(
        "insert into part (session_id, time_created, data) values (?, ?, ?)",
        (
            "session-1",
            1,
            json.dumps(
                {
                    "type": "tool",
                    "tool": "aileron_show_canvas_artifact",
                    "callID": "other-tool",
                    "state": {
                        "status": "completed",
                        "input": {"title": "Artifact"},
                    },
                }
            ),
        ),
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("OPENCODE_DB_PATH", str(db_path))
    mapper = OpenCodeAcpEventMapper()

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="aileron_ask_user_question",
            kind="other",
            status="completed",
            raw_input={},
            raw_output={
                "output": "Question form delivered to the user.",
                "metadata": {"truncated": False},
            },
        ),
        session_id="session-1",
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content["input"] == {}
    assert "structuredContent" not in events[1].content["result"]


def test_tool_call_update_result_shape_and_parent_id() -> None:
    mapper = OpenCodeAcpEventMapper()

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="Read file",
            kind="read",
            status="completed",
            raw_output="done",
        )
    )

    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].tool_call_key == "tool-1"
    assert events[1].content == {
        "result": "done",
        "is_error": False,
    }


def test_non_terminal_tool_call_update_does_not_duplicate_tool_call() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            raw_input={"command": "ls"},
        )
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="bash",
            status="running",
            raw_input={"command": "ls"},
        )
    )

    assert events == []


def test_failed_tool_call_update_marks_result_error() -> None:
    mapper = OpenCodeAcpEventMapper()

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="bash",
            status="failed",
            raw_output={"message": "boom"},
            raw_input={"command": "ls"},
        )
    )

    assert events[-1].type == "tool_result"
    assert events[-1].content["is_error"] is True
    assert events[-1].content["result"] == {"message": "boom"}


def test_unknown_update_is_ignored() -> None:
    mapper = OpenCodeAcpEventMapper()

    assert mapper.map_session_update(Update(session_update="current_mode_update")) == []


def test_raw_payload_is_json_safe() -> None:
    mapper = OpenCodeAcpEventMapper()

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="Tool",
            raw_input={"value": Content("nested")},
        )
    )

    assert event.raw is not None
    assert event.raw["raw_input"]["value"]["text"] == "nested"


def test_bash_tool_call_uses_canonical_name() -> None:
    mapper = OpenCodeAcpEventMapper()

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"command": "ls -la"},
        )
    )

    assert event.content["name"] == "Bash"


def test_opencode_builtin_tool_names_map_to_canonical_names() -> None:
    mapper = OpenCodeAcpEventMapper()
    expected = {
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
    }
    for index, (raw_name, canonical) in enumerate(expected.items()):
        [event] = mapper.map_session_update(
            Update(
                session_update="tool_call_update",
                tool_call_id=f"tool-{index}",
                title=raw_name,
                status="completed",
                raw_input={"any": "value"},
            )
        )[:1]
        assert event.content["name"] == canonical, raw_name


def test_unknown_tool_name_passes_through_unchanged() -> None:
    mapper = OpenCodeAcpEventMapper()

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="some_custom_tool",
            kind="other",
            status="pending",
        )
    )

    assert event.content["name"] == "some_custom_tool"


def test_bash_input_merges_raw_input_and_state_input() -> None:
    mapper = OpenCodeAcpEventMapper()

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"cwd": "/workspace"},
            state={"input": {"command": "echo hi"}},
        )
    )

    assert event.content == {
        "name": "Bash",
        "input": {"cwd": "/workspace", "command": "echo hi"},
    }


def test_bash_pending_without_command_defers_until_terminal_update() -> None:
    mapper = OpenCodeAcpEventMapper()

    pending = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"cwd": "/workspace"},
        )
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="completed",
            raw_input={"cwd": "/workspace"},
            raw_output={"output": "hi\n", "metadata": {"exit": 0}},
            state={"input": {"command": "echo hi"}},
        )
    )

    assert pending == []
    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content["input"] == {"cwd": "/workspace", "command": "echo hi"}


def test_bash_input_falls_back_to_opencode_db(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "opencode.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "create table part (session_id text, time_created integer, data text)"
    )
    connection.execute(
        "insert into part (session_id, time_created, data) values (?, ?, ?)",
        (
            "session-1",
            1,
            json.dumps(
                {
                    "type": "tool",
                    "tool": "bash",
                    "callID": "tool-1",
                    "state": {"status": "running", "input": {"command": "pwd"}},
                }
            ),
        ),
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("OPENCODE_DB_PATH", str(db_path))
    mapper = OpenCodeAcpEventMapper()

    [event] = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"cwd": "/workspace"},
        ),
        session_id="session-1",
    )

    assert event.content["input"] == {"cwd": "/workspace", "command": "pwd"}


def test_edit_input_keys_are_snake_cased() -> None:
    mapper = OpenCodeAcpEventMapper()

    [event, _result] = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="edit",
            status="completed",
            raw_input={
                "filePath": "/workspace/a.py",
                "oldString": "x = 1",
                "newString": "x = 2",
                "replaceAll": False,
            },
        )
    )

    assert event.content == {
        "name": "Edit",
        "input": {
            "file_path": "/workspace/a.py",
            "old_string": "x = 1",
            "new_string": "x = 2",
            "replace_all": False,
        },
    }


def test_bash_result_extracts_output_text() -> None:
    mapper = OpenCodeAcpEventMapper()

    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="bash",
            status="completed",
            raw_input={"command": "echo hi"},
            raw_output={"output": "hi\n", "metadata": {"exit": 0, "truncated": False}},
        )
    )

    assert events[-1].type == "tool_result"
    assert events[-1].content["result"] == "hi\n"
    assert events[-1].content["is_error"] is False


def test_terminal_title_mutation_keeps_canonical_name_for_deferred_call() -> None:
    mapper = OpenCodeAcpEventMapper()

    pending = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"cwd": "/workspace"},
        )
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="cat acp_probe.txt",
            kind=None,
            status="completed",
            raw_input={"cwd": "/workspace"},
            raw_output={"output": "hello\n", "metadata": {"exit": 0}},
            state={"input": {"command": "cat acp_probe.txt"}},
        )
    )

    assert pending == []
    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content["name"] == "Bash"
    assert events[0].content["input"] == {
        "cwd": "/workspace",
        "command": "cat acp_probe.txt",
    }
    assert events[1].content["result"] == "hello\n"


def test_terminal_title_mutation_unwraps_result_for_emitted_call() -> None:
    mapper = OpenCodeAcpEventMapper()

    mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"command": "echo hi"},
        )
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="echo hi",
            kind=None,
            status="completed",
            raw_output={"output": "hi\n", "metadata": {"exit": 0}},
        )
    )

    assert [event.type for event in events] == ["tool_result"]
    assert events[0].content["result"] == "hi\n"


def test_terminal_title_colliding_with_map_key_keeps_first_seen_name() -> None:
    mapper = OpenCodeAcpEventMapper()

    pending = mapper.map_session_update(
        Update(
            session_update="tool_call",
            tool_call_id="tool-1",
            title="bash",
            kind="execute",
            status="pending",
            raw_input={"cwd": "/workspace"},
        )
    )
    events = mapper.map_session_update(
        Update(
            session_update="tool_call_update",
            tool_call_id="tool-1",
            title="task",
            kind=None,
            status="completed",
            raw_input={"cwd": "/workspace"},
            raw_output={"output": "done\n", "metadata": {"exit": 0}},
            state={"input": {"command": "task"}},
        )
    )

    assert pending == []
    assert [event.type for event in events] == ["tool_call", "tool_result"]
    assert events[0].content["name"] == "Bash"
    assert events[1].content["result"] == "done\n"
