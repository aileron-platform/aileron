from __future__ import annotations

from pathlib import Path

AGENT_DEFAULTS_DIR = Path(__file__).resolve().parents[4] / "agent-defaults"


def test_claude_md_requires_canvas_skill_and_question_tool() -> None:
    content = (AGENT_DEFAULTS_DIR / "CLAUDE.md").read_text()

    assert "aileron-web-canvas" in content
    assert "MUST" in content
    assert "mcp__aileron__show_canvas_artifact" in content
    assert "mcp__aileron__ask_user_question" in content
    assert "end the turn immediately" in content
    assert "Never infer, invent, or fabricate user answers" in content
    assert "aileron-web-canvas skill owns the workflow" in content
    assert "Completion condition" in content
    assert "is not delivery" in content
    assert "no more than 5 questions" in content
    assert "set each question's default" in content


def test_agents_md_requires_canvas_skill_and_question_tool_with_both_tool_names() -> (
    None
):
    content = (AGENT_DEFAULTS_DIR / "AGENTS.md").read_text()

    assert "aileron-web-canvas" in content
    assert "MUST" in content
    assert "mcp__aileron__show_canvas_artifact" in content
    assert "mcp__aileron__ask_user_question" in content
    assert "aileron_show_canvas_artifact" in content
    assert "aileron_ask_user_question" in content
    assert "When an Aileron MCP tool is available" in content
    assert "do not route direct CLI execution through MCP" in content
    assert "Do not use AskUserQuestion" in content
    assert "end the turn immediately" in content
    assert "Never infer, invent, or fabricate user answers" in content
    assert "aileron-web-canvas skill owns the workflow" in content
    assert "Completion condition" in content
    assert "is not delivery" in content
    assert "no more than 5 questions" in content
    assert "set each question's default" in content


def test_aileron_web_canvas_skill_owns_manifest_file_contract() -> None:
    content = (
        AGENT_DEFAULTS_DIR / "skills" / "aileron-web-canvas" / "SKILL.md"
    ).read_text()

    assert "/workspace/.aileron/canvases/aileron-web-canvas/<slug>/" in content
    assert "`/workspace/canvases/...`" in content
    assert "`contentDir/index.html` exists" in content
    assert "`contentDir` resolves to the content directory" in content
    assert "window.aileron.theme" in content
    assert "aileron:themechange" in content
    assert "Do not mutate server-rendered `<html>` or `<body>` attributes before hydration" in content
    assert "never tell the user to run a" in content
    assert "dev server, share a raw file path, or paste HTML into the chat" in content
    assert "Ask no more than five questions" in content
    assert "each question's `default`" in content
