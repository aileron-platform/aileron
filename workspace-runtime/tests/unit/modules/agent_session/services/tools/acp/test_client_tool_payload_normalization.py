"""ACP Client raw tool payload persistence tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.agent_session.services.tools.acp.client import AcpClient


def _make_client() -> AcpClient:
    return AcpClient(runtime_session_id="session-1", workspace_path="/workspace")


@pytest.mark.asyncio
async def test_emit_tool_start_preserves_acp_raw_shape() -> None:
    client = _make_client()
    events: list[tuple[str, dict]] = []
    client.emit_event = lambda event_type, data: events.append((event_type, data))

    start_call = SimpleNamespace(
        tool_call_id="write_file-1",
        title="Writing to demo.txt",
        raw_input={"hint": "raw"},
        kind=SimpleNamespace(value="edit"),
        content=[],
        locations=[{"path": "/workspace/demo.txt"}],
    )
    await client._emit_tool_start(start_call)  # noqa: SLF001 - test private helper intentionally

    execution = client.get_tool_executions()[0]
    tool_input = execution["tool_input"]

    assert tool_input["toolCallId"] == "write_file-1"
    assert tool_input["title"] == "Writing to demo.txt"
    assert tool_input["kind"] == "edit"
    assert tool_input["locations"] == [{"path": "/workspace/demo.txt"}]
    assert "rawInput" not in tool_input

    assert events[0][0] == "tool:start"
    assert events[0][1]["tool_input"]["toolCallId"] == "write_file-1"


@pytest.mark.asyncio
async def test_emit_tool_update_uses_raw_result_payload() -> None:
    client = _make_client()
    events: list[tuple[str, dict]] = []
    client.emit_event = lambda event_type, data: events.append((event_type, data))

    start_call = SimpleNamespace(
        tool_call_id="run_shell_command-1",
        title="echo hi [current working directory /workspace]",
        raw_input=None,
        kind=SimpleNamespace(value="execute"),
        content=None,
        locations=None,
    )
    await client._emit_tool_start(start_call)  # noqa: SLF001 - test private helper intentionally

    update_call = SimpleNamespace(
        tool_call_id="run_shell_command-1",
        title="echo hi [current working directory /workspace]",
        raw_input=None,
        kind=SimpleNamespace(value="execute"),
        status="completed",
        raw_output=None,
        content=[{"type": "content", "content": {"type": "text", "text": "HI"}}],
        locations=None,
    )
    await client._emit_tool_update(update_call)  # noqa: SLF001 - test private helper intentionally

    execution = client.get_tool_executions()[0]
    result_payload = execution["tool_result"]

    assert result_payload["toolCallId"] == "run_shell_command-1"
    assert result_payload["status"] == "completed"
    assert isinstance(result_payload["content"], list)
    assert result_payload["content"][0]["type"] == "content"

    assert events[-1][0] == "tool:complete"
    assert isinstance(events[-1][1]["result"], dict)
    assert events[-1][1]["result"]["status"] == "completed"


@pytest.mark.asyncio
async def test_emit_tool_update_backfills_execution_when_start_missing() -> None:
    client = _make_client()

    update_call = SimpleNamespace(
        tool_call_id="write_file-2",
        title="Writing to fallback.txt",
        raw_input=None,
        kind=None,
        status="completed",
        raw_output=None,
        content=[{"type": "diff", "path": "fallback.txt", "oldText": "", "newText": "ok"}],
        locations=[{"path": "/workspace/fallback.txt"}],
    )
    await client._emit_tool_update(update_call)  # noqa: SLF001 - test private helper intentionally

    execution = client.get_tool_executions()[0]
    assert execution["tool_call_id"] == "write_file-2"
    assert execution["tool_input"]["toolCallId"] == "write_file-2"
    assert execution["tool_input"]["title"] == "Writing to fallback.txt"
    assert execution["tool_result"]["status"] == "completed"
    assert execution["tool_result"]["content"][0]["type"] == "diff"


@pytest.mark.asyncio
async def test_emit_tool_update_failed_uses_acp_shape_and_error_event() -> None:
    client = _make_client()
    events: list[tuple[str, dict]] = []
    client.emit_event = lambda event_type, data: events.append((event_type, data))

    update_call = SimpleNamespace(
        tool_call_id="run_shell_command-err",
        title="bad command",
        raw_input=None,
        kind=SimpleNamespace(value="execute"),
        status="failed",
        raw_output={"error_message": "boom", "code": 127},
        content=None,
        locations=None,
    )
    await client._emit_tool_update(update_call)  # noqa: SLF001 - test private helper intentionally

    execution = client.get_tool_executions()[0]
    assert execution["is_error"] is True
    assert execution["tool_result"]["status"] == "failed"
    assert "rawOutput" not in execution["tool_result"]

    assert events[-1][0] == "tool:error"
    assert events[-1][1]["error_message"] == "boom"
    assert events[-1][1]["error_code"] == "127"


@pytest.mark.asyncio
async def test_emit_tool_update_does_not_fallback_to_raw_output_when_content_empty() -> None:
    client = _make_client()

    update_call = SimpleNamespace(
        tool_call_id="read_file-raw-only",
        title="Reading demo.txt",
        raw_input=None,
        kind=SimpleNamespace(value="read"),
        status="completed",
        raw_output={"content": "RAW_ONLY_CONTENT"},
        content=[],
        locations=[{"path": "/workspace/demo.txt"}],
    )
    await client._emit_tool_update(update_call)  # noqa: SLF001 - test private helper intentionally

    execution = client.get_tool_executions()[0]
    result_payload = execution["tool_result"]

    assert result_payload["toolCallId"] == "read_file-raw-only"
    assert result_payload["status"] == "completed"
    assert "content" not in result_payload
