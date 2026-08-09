from __future__ import annotations

from pathlib import Path

from app.modules.thread.mcp.agent_policy import (
    CANVAS_POLICY_BODY,
    CANVAS_POLICY_BODY_BYTE_BUDGET,
)

SKILL_PATH = (
    Path(__file__).resolve().parents[4]
    / "agent-defaults"
    / "skills"
    / "aileron-web-canvas"
    / "SKILL.md"
)


def test_canvas_policy_stays_within_byte_budget() -> None:
    assert len(CANVAS_POLICY_BODY.encode()) <= CANVAS_POLICY_BODY_BYTE_BUDGET


def test_canvas_policy_keeps_frozen_completion_markers() -> None:
    assert "canvas.json" in CANVAS_POLICY_BODY
    assert "{canvas_tool}" in CANVAS_POLICY_BODY


def test_canvas_workflow_details_have_one_owner() -> None:
    skill = SKILL_PATH.read_text()

    assert "Work under `/workspace`." in skill
    assert "never tell the user to run a" in skill
    assert "dev server, share a raw file path, or paste HTML into the chat" in skill

    assert "work under /workspace" not in CANVAS_POLICY_BODY
    assert "dev server" not in CANVAS_POLICY_BODY
