from __future__ import annotations

import json
from pathlib import Path

from app.modules.thread.domain.tool_names import CANVAS_TOOL_NAME, QUESTION_TOOL_NAME
from app.modules.thread.claude_sdk_options import (
    AILERON_MCP_SERVER_PATH,
    CLAUDE_AILERON_MCP_PROMPT,
    CLAUDE_PLAN_ALLOWED_TOOLS,
    build_claude_options,
    ensure_claude_mcp_config,
    prompt_with_attachments,
)
from app.modules.thread.execution import AgentExecutionRequest


def request(**overrides: object) -> AgentExecutionRequest:
    values = {
        "thread_id": "thread-1",
        "agentic_tool": "claude",
        "model": "claude-sonnet-4-5-20250929",
        "claude_mode": None,
        "prompt_text": "Please inspect this.",
        "permission_mode": None,
        "git_context_id": "ctx-1",
        "agent_resume_id": None,
        "attachments": [],
    }
    values.update(overrides)
    return AgentExecutionRequest(**values)


def test_build_options_preserves_cli_settings_sources_and_message_granularity(
    tmp_path,
) -> None:
    options = build_claude_options(
        workspace_id="workspace-1",
        request=request(agent_resume_id="session-1"),
        cwd=tmp_path,
    )

    assert options.cwd == tmp_path
    assert options.cli_path == "claude"
    assert options.model == "claude-sonnet-4-5-20250929"
    assert options.resume == "session-1"
    assert options.permission_mode == "bypassPermissions"
    assert options.setting_sources == ["user", "project"]
    assert options.include_partial_messages is False
    assert options.extra_args == {"thinking-display": "summarized"}
    assert options.system_prompt == {
        "type": "preset",
        "preset": "claude_code",
        "append": CLAUDE_AILERON_MCP_PROMPT,
    }


def test_plan_mode_uses_allowed_tools_and_plan_permission(tmp_path) -> None:
    options = build_claude_options(
        workspace_id="workspace-1",
        request=request(claude_mode="plan"),
        cwd=tmp_path,
    )

    assert options.permission_mode == "plan"
    assert options.allowed_tools == list(CLAUDE_PLAN_ALLOWED_TOOLS)
    assert QUESTION_TOOL_NAME in options.allowed_tools
    assert CANVAS_TOOL_NAME in options.allowed_tools


def test_prompt_with_attachments_preserves_existing_mime_aware_format() -> None:
    prompt = prompt_with_attachments(
        request(
            attachments=[
                {
                    "type": "text-file",
                    "name": "notes.md",
                    "mimeType": "text/markdown",
                    "path": "/workspace/notes.md",
                },
                {
                    "type": "pdf",
                    "name": "spec.pdf",
                    "mimeType": "application/pdf",
                    "path": "/workspace/spec.pdf",
                },
                {
                    "type": "image",
                    "name": "screen.png",
                    "mimeType": "image/png",
                    "path": "/workspace/screen.png",
                },
            ],
        )
    )

    assert prompt == (
        "Please inspect this.\n\n"
        "Attachments:\n"
        "Attached text file notes.md (text/markdown): /workspace/notes.md\n"
        "Attached PDF spec.pdf (application/pdf): /workspace/spec.pdf\n"
        "Attached image screen.png (image/png): /workspace/screen.png"
    )


def test_ensure_claude_mcp_config_writes_server_entry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.thread.claude_sdk_options.MCP_CONFIG_DIR",
        tmp_path,
    )

    config_path = ensure_claude_mcp_config("ws-1")

    payload = json.loads(Path(config_path).read_text())
    server = payload["mcpServers"]["aileron"]
    assert server["args"] == [str(AILERON_MCP_SERVER_PATH)]
    assert AILERON_MCP_SERVER_PATH.exists()


def test_ensure_claude_mcp_config_skips_existing_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.thread.claude_sdk_options.MCP_CONFIG_DIR",
        tmp_path,
    )

    config_path = Path(ensure_claude_mcp_config("ws-1"))
    original = config_path.read_text()

    config_path.write_text('{"sentinel": true}')

    assert Path(ensure_claude_mcp_config("ws-1")) == config_path
    assert config_path.read_text() == '{"sentinel": true}'
    assert original != config_path.read_text()


def test_ensure_claude_mcp_config_uses_workspace_scoped_paths(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.thread.claude_sdk_options.MCP_CONFIG_DIR",
        tmp_path,
    )

    first = ensure_claude_mcp_config("ws-1")
    second = ensure_claude_mcp_config("ws-2")

    assert first != second
    assert first.endswith("ws-1-mcp-config.json")
    assert second.endswith("ws-2-mcp-config.json")


def test_claude_aileron_prompt_requires_canvas_skill_and_question_tool() -> None:
    assert "aileron-web-canvas" in CLAUDE_AILERON_MCP_PROMPT
    assert "MUST" in CLAUDE_AILERON_MCP_PROMPT
    assert "mcp__aileron__show_canvas_artifact" in CLAUDE_AILERON_MCP_PROMPT
    assert "mcp__aileron__ask_user_question" in CLAUDE_AILERON_MCP_PROMPT
    assert "clarifying question" in CLAUDE_AILERON_MCP_PROMPT
    assert "expects the user to answer" in CLAUDE_AILERON_MCP_PROMPT
    assert "Do not use AskUserQuestion" in CLAUDE_AILERON_MCP_PROMPT
    assert "bare ask_user_question" in CLAUDE_AILERON_MCP_PROMPT
    assert "end the turn immediately" in CLAUDE_AILERON_MCP_PROMPT
    assert "Hard cap: 5 questions" in CLAUDE_AILERON_MCP_PROMPT
    assert "Set each question's default" in CLAUDE_AILERON_MCP_PROMPT
    assert "Never infer, invent, or fabricate user answers" in (
        CLAUDE_AILERON_MCP_PROMPT
    )
    assert "the aileron-web-canvas skill owns the workflow" in CLAUDE_AILERON_MCP_PROMPT
    assert "Completion condition" in CLAUDE_AILERON_MCP_PROMPT
    assert "is not delivery" in CLAUDE_AILERON_MCP_PROMPT
