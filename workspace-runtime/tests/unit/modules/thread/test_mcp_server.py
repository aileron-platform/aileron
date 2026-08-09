from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SERVER_PATH = (
    Path(__file__).resolve().parents[4]
    / "app"
    / "modules"
    / "thread"
    / "mcp"
    / "server.py"
)


def run_server(requests: list[dict]) -> list[dict]:
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    completed = subprocess.run(
        [sys.executable, str(SERVER_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
}


def test_initialize_returns_server_info() -> None:
    responses = run_server([INITIALIZE])
    assert responses[0]["id"] == 1
    assert responses[0]["result"]["serverInfo"]["name"] == "aileron"


def test_tools_list_exposes_both_tools() -> None:
    responses = run_server(
        [INITIALIZE, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    )
    tools = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert tools == {"ask_user_question", "show_canvas_artifact"}


def test_ask_user_question_schema_matches_question_form() -> None:
    responses = run_server(
        [INITIALIZE, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    )
    tool = next(
        tool
        for tool in responses[1]["result"]["tools"]
        if tool["name"] == "ask_user_question"
    )
    assert "mcp__aileron__ask_user_question" in tool["description"]
    assert "send no additional assistant text" in tool["description"]
    assert tool["annotations"] == {"readOnlyHint": True}
    schema = tool["inputSchema"]
    assert schema["required"] == ["id", "title", "questions"]
    assert schema["properties"]["questions"]["maxItems"] == 5
    question_schema = schema["properties"]["questions"]["items"]
    assert set(question_schema["required"]) == {"id", "label", "type"}
    assert question_schema["properties"]["default"] == {
        "type": ["string", "array"],
        "items": {"type": "string"},
    }
    assert "show_if" in question_schema["properties"]
    assert "options_by" in question_schema["properties"]
    assert "Hard cap: 5 questions" in tool["description"]


def test_ask_user_question_call_tells_agent_to_end_turn() -> None:
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "ask_user_question",
            "arguments": {
                "id": "color",
                "title": "Pick a color",
                "questions": [
                    {
                        "id": "favorite",
                        "label": "Favorite color",
                        "type": "radio",
                        "options": ["red", "blue"],
                    }
                ],
            },
        },
    }
    responses = run_server([INITIALIZE, call])
    text = responses[1]["result"]["content"][0]["text"]
    assert "End your turn" in text
    assert "Do not send any additional assistant text" in text
    assert responses[1]["result"]["structuredContent"] == call["params"]["arguments"]
    assert responses[1]["result"].get("isError") is not True


def test_show_canvas_artifact_call_returns_success() -> None:
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "show_canvas_artifact",
            "arguments": {"title": "Landing page", "route": "/landing"},
        },
    }
    responses = run_server([INITIALIZE, call])
    text = responses[1]["result"]["content"][0]["text"]
    assert "shown to the user" in text


def test_unknown_tool_call_returns_error_result() -> None:
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    }
    responses = run_server([INITIALIZE, call])
    assert responses[1]["result"]["isError"] is True


def test_notifications_produce_no_response() -> None:
    responses = run_server(
        [INITIALIZE, {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    )
    assert len(responses) == 1
