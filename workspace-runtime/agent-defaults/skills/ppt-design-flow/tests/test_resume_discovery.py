"""Tests for resumable ppt-design-flow session discovery."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import stage_state
from deck_test_helpers import advance_to_review
from stage_state import (
    InvalidTransitionError,
    enter_phase,
    init,
    pass_gate,
    state_path,
)


def _set_updated_at(workspace: Path, session_id: str, value: str) -> None:
    path = state_path(workspace, session_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["updated_at"] = value
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _stage_cli(stage_cli: Path, workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(stage_cli), *args, "--workspace", str(workspace)],
        capture_output=True,
        check=False,
        text=True,
    )


def test_discover_sessions_lists_unfinished_by_updated_at(workspace: Path) -> None:
    older = init(workspace, "2026-05-19-older")
    older = pass_gate(older, "needs_confirmed")
    enter_phase(older, "content-basis")
    newer = init(workspace, "2026-05-19-newer")
    newer = pass_gate(newer, "needs_confirmed")
    enter_phase(newer, "content-basis")
    _set_updated_at(workspace, "2026-05-19-older", "2026-05-19T01:00:00Z")
    _set_updated_at(workspace, "2026-05-19-newer", "2026-05-19T02:00:00Z")

    result = stage_state.discover_sessions(workspace)

    assert [session.session_id for session in result.sessions] == [
        "2026-05-19-newer",
        "2026-05-19-older",
    ]
    assert result.invalid == []


def test_discover_sessions_excludes_done_by_default_and_all_includes_it(workspace: Path) -> None:
    done = advance_to_review(workspace, "2026-05-19-done")
    pass_gate(done, "review_approved")
    active = init(workspace, "2026-05-19-active")

    default_result = stage_state.discover_sessions(workspace)
    all_result = stage_state.discover_sessions(workspace, include_completed=True)

    assert [session.session_id for session in default_result.sessions] == [active.session_id]
    assert {session.session_id for session in all_result.sessions} == {
        active.session_id,
        done.session_id,
    }


def test_discover_sessions_includes_active_revision_as_unfinished(workspace: Path) -> None:
    done = advance_to_review(workspace, "2026-05-19-revision")
    done = pass_gate(done, "review_approved")
    enter_phase(done, "done")
    session_dir = state_path(workspace, done.session_id).parent
    final_dir = session_dir / "generation" / "final-pages"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "S01.png").write_bytes(b"p1")
    (session_dir / "generation" / "final-pages.json").write_text(
        json.dumps({"version": 1, "pages": [{"slide_id": "S01", "path": "generation/final-pages/S01.png"}]}),
        encoding="utf-8",
    )
    stage_state.revise(done, pages=["S01"])

    result = stage_state.discover_sessions(workspace)
    summary = stage_state.resolve_resume_session(workspace)

    assert [session.session_id for session in result.sessions] == ["2026-05-19-revision"]
    assert summary.current_phase == "revision"
    assert summary.next_action == "build revision review"


def test_discover_sessions_reports_invalid_state_without_blocking_valid_sessions(workspace: Path) -> None:
    init(workspace, "2026-05-19-valid")
    bad_path = (
        workspace
        / ".aileron"
        / "canvases"
        / stage_state.SKILL_NAME
        / "2026-05-19-bad"
        / "state.json"
    )
    bad_path.parent.mkdir(parents=True)
    bad_path.write_text("{not-json", encoding="utf-8")

    result = stage_state.discover_sessions(workspace, include_completed=True)

    assert [session.session_id for session in result.sessions] == ["2026-05-19-valid"]
    assert len(result.invalid) == 1
    assert result.invalid[0].session_id == "2026-05-19-bad"


def test_resolve_resume_session_selects_recent_unfinished_without_query(workspace: Path) -> None:
    init(workspace, "2026-05-19-older")
    init(workspace, "2026-05-19-newer")
    _set_updated_at(workspace, "2026-05-19-older", "2026-05-19T01:00:00Z")
    _set_updated_at(workspace, "2026-05-19-newer", "2026-05-19T02:00:00Z")

    summary = stage_state.resolve_resume_session(workspace)

    assert summary.session_id == "2026-05-19-newer"
    assert summary.phase_file == "phases/10-intake.md"
    assert summary.next_action == "needs_confirmed"


def test_resolve_resume_session_rejects_ambiguous_query(workspace: Path) -> None:
    init(workspace, "2026-05-19-client-a")
    init(workspace, "2026-05-19-client-b")

    with pytest.raises(InvalidTransitionError) as exc_info:
        stage_state.resolve_resume_session(workspace, query="client")

    rendered = exc_info.value.render()
    assert "matches multiple sessions" in rendered
    assert "2026-05-19-client-a" in rendered
    assert "2026-05-19-client-b" in rendered


def test_stage_cli_resume_outputs_concise_continuation(stage_cli: Path, workspace: Path) -> None:
    state = init(workspace, "2026-05-19-demo")
    state = pass_gate(state, "needs_confirmed")
    enter_phase(state, "content-basis")
    before = state_path(workspace, "2026-05-19-demo").read_text(encoding="utf-8")

    result = _stage_cli(stage_cli, workspace, "resume")

    after = state_path(workspace, "2026-05-19-demo").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "session_id      : 2026-05-19-demo" in result.stdout
    assert "current_phase   : content-basis" in result.stdout
    assert "phase_file      : phases/20-content-basis.md" in result.stdout
    assert before == after


def test_stage_cli_revise_and_complete_revision(stage_cli: Path, workspace: Path) -> None:
    state = advance_to_review(workspace, "2026-05-19-cli-revision")
    state = pass_gate(state, "review_approved")
    enter_phase(state, "done")
    session_dir = state_path(workspace, state.session_id).parent
    final_dir = session_dir / "generation" / "final-pages"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "S01.png").write_bytes(b"p1")
    (session_dir / "generation" / "final-pages.json").write_text(
        json.dumps({"version": 1, "pages": [{"slide_id": "S01", "path": "generation/final-pages/S01.png"}]}),
        encoding="utf-8",
    )

    revise_result = _stage_cli(
        stage_cli,
        workspace,
        "revise",
        "--session-id",
        state.session_id,
        "--pages",
        '["S01"]',
        "--reason",
        "CLI revision",
    )
    complete_result = _stage_cli(
        stage_cli,
        workspace,
        "complete-revision",
        "--session-id",
        state.session_id,
    )

    assert revise_result.returncode == 0, revise_result.stderr
    assert "current_phase   : revision" in revise_result.stdout
    assert '"revision_pages": ["S01"]' in revise_result.stdout
    assert complete_result.returncode == 0, complete_result.stderr
    assert "current_phase   : done" in complete_result.stdout


def test_stage_cli_revise_rejects_invalid_page(stage_cli: Path, workspace: Path) -> None:
    state = advance_to_review(workspace, "2026-05-19-cli-invalid")
    state = pass_gate(state, "review_approved")
    enter_phase(state, "done")
    session_dir = state_path(workspace, state.session_id).parent
    (session_dir / "generation").mkdir(parents=True, exist_ok=True)
    (session_dir / "generation" / "final-pages.json").write_text(
        json.dumps({"version": 1, "pages": [{"slide_id": "S01", "path": "generation/final-pages/S01.png"}]}),
        encoding="utf-8",
    )

    result = _stage_cli(
        stage_cli,
        workspace,
        "revise",
        "--session-id",
        state.session_id,
        "--pages",
        '["S99"]',
    )

    assert result.returncode == 3
    assert "unknown revision page" in result.stderr


def test_stage_cli_list_reports_valid_and_invalid_sessions(stage_cli: Path, workspace: Path) -> None:
    init(workspace, "2026-05-19-valid")
    bad_path = (
        workspace
        / ".aileron"
        / "canvases"
        / stage_state.SKILL_NAME
        / "2026-05-19-bad"
        / "state.json"
    )
    bad_path.parent.mkdir(parents=True)
    bad_path.write_text("{not-json", encoding="utf-8")

    result = _stage_cli(stage_cli, workspace, "list", "--all")

    assert result.returncode == 0
    assert "2026-05-19-valid" in result.stdout
    assert "[invalid] 2026-05-19-bad" in result.stdout


def test_stage_cli_resume_query_errors_are_agent_readable(stage_cli: Path, workspace: Path) -> None:
    init(workspace, "2026-05-19-alpha")
    init(workspace, "2026-05-19-beta")

    ambiguous = _stage_cli(stage_cli, workspace, "resume", "2026")
    missing = _stage_cli(stage_cli, workspace, "resume", "missing")

    assert ambiguous.returncode == 3
    assert "matches multiple sessions" in ambiguous.stderr
    assert "2026-05-19-alpha" in ambiguous.stderr
    assert missing.returncode == 3
    assert "no session matches query 'missing'" in missing.stderr
