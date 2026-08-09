"""Unit tests for assets/stage_state.py covering every scenario in
phase-orchestration/spec.md."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

import stage_state
from stage_state import (
    InvalidTransitionError,
    StagePreflightError,
    enter_phase,
    init,
    load,
    pass_gate,
    render_show,
    require,
    reset,
    resolve_workspace,
    save,
    set_flag,
    state_path,
)


# ---------------------------------------------------------------------------
# Workspace resolution
# ---------------------------------------------------------------------------


def test_resolve_workspace_prefers_explicit_argument(tmp_path: Path) -> None:
    target = tmp_path / "explicit"
    target.mkdir()
    resolved = resolve_workspace(target)
    assert resolved == target.resolve()


def test_resolve_workspace_falls_back_to_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    monkeypatch.setenv("WORKSPACE_DIR", str(fallback))
    resolved = resolve_workspace(None)
    assert resolved == fallback.resolve()


def test_resolve_workspace_without_source_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKSPACE_DIR", raising=False)
    with pytest.raises(InvalidTransitionError) as exc_info:
        resolve_workspace(None)
    assert "workspace path is required" in exc_info.value.render()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_creates_state_at_intake(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    assert state.current_phase == "intake"
    assert state.gates_passed == []
    assert state.version == stage_state.STATE_VERSION
    data = json.loads(state_path(workspace, session_id).read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["skill"] == "ppt-design-flow"
    assert data["current_phase"] == "intake"


def test_init_refuses_to_overwrite_existing_state(workspace: Path, session_id: str) -> None:
    init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        init(workspace, session_id)
    rendered = exc_info.value.render()
    assert f"state.json already exists for session '{session_id}'" in rendered


# ---------------------------------------------------------------------------
# Gate / phase transitions
# ---------------------------------------------------------------------------


def test_legal_pass_appends_gate(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    assert state.gates_passed == ["needs_confirmed"]
    # Persisted via save() during pass_gate
    persisted = json.loads(state_path(workspace, session_id).read_text(encoding="utf-8"))
    assert persisted["gates_passed"] == ["needs_confirmed"]
    history_events = [entry["event"] for entry in persisted["history"]]
    assert "gate_pass" in history_events


def test_pass_gate_out_of_order_is_rejected(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        pass_gate(state, "style_locked")
    rendered = exc_info.value.render()
    assert "expected_gate" in rendered
    assert "needs_confirmed" in rendered


def test_duplicate_gate_pass_is_rejected(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    with pytest.raises(InvalidTransitionError) as exc_info:
        pass_gate(state, "needs_confirmed")
    assert "has already been passed" in exc_info.value.render()


def test_legal_phase_entry(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    assert state.current_phase == "content-basis"


def test_phase_entry_blocked_by_missing_gate(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    state = pass_gate(state, "style_locked")
    with pytest.raises(InvalidTransitionError) as exc_info:
        enter_phase(state, "planning")
    rendered = exc_info.value.render()
    assert "missing" in rendered
    assert "style_breakdown_confirmed" in rendered


def test_unknown_phase_is_rejected(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        enter_phase(state, "no-such-phase")
    assert "unknown phase" in exc_info.value.render()


# ---------------------------------------------------------------------------
# Flag whitelist
# ---------------------------------------------------------------------------


def test_set_flag_accepts_valid_enum(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "preview_mode", "svg")
    assert state.flags["preview_mode"] == "svg"


def test_set_flag_rejects_unknown_key(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        set_flag(state, "foo", "bar")
    assert "unknown flag 'foo'" in exc_info.value.render()


def test_set_flag_rejects_invalid_value(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        set_flag(state, "preview_mode", "webp")
    rendered = exc_info.value.render()
    assert "preview_mode" in rendered
    assert "svg" in rendered and "imagegen" in rendered


def test_set_flag_boolean_parsing(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "pages_ready", "true")
    assert state.flags["pages_ready"] is True
    state = set_flag(state, "pages_ready", "false")
    assert state.flags["pages_ready"] is False


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def _advance_to_generation(workspace: Path, session_id: str) -> stage_state.State:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    state = pass_gate(state, "style_locked")
    state = pass_gate(state, "style_breakdown_confirmed")
    state = enter_phase(state, "planning")
    state = pass_gate(state, "pre_generation_confirmed")
    state = enter_phase(state, "generation")
    state = set_flag(state, "pages_ready", "true")
    return state


def test_reset_truncates_downstream_gates_and_flags(workspace: Path, session_id: str) -> None:
    state = _advance_to_generation(workspace, session_id)
    state = reset(state, "style")
    assert state.current_phase == "style"
    assert state.gates_passed == ["needs_confirmed"]
    assert state.flags["pages_ready"] is False


def test_reset_cannot_move_forward(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        reset(state, "planning")
    assert "reset cannot move forward" in exc_info.value.render()


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


def _advance_to_done_with_final_pages(workspace: Path, session_id: str) -> stage_state.State:
    state = _advance_to_generation(workspace, session_id)
    state = enter_phase(state, "review")
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["pptx", "html"]')
    state = enter_phase(state, "done")
    session_dir = state_path(workspace, session_id).parent
    final_dir = session_dir / "generation" / "final-pages"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "S01.png").write_bytes(b"p1")
    (final_dir / "S02.png").write_bytes(b"p2")
    (session_dir / "generation" / "final-pages.json").write_text(
        json.dumps(
            {
                "version": 1,
                "skill": "ppt-design-flow",
                "session_id": session_id,
                "pages": [
                    {"slide_id": "S01", "path": "generation/final-pages/S01.png"},
                    {"slide_id": "S02", "path": "generation/final-pages/S02.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return state


def test_revise_enters_revision_without_clearing_completed_state(
    workspace: Path, session_id: str
) -> None:
    state = _advance_to_done_with_final_pages(workspace, session_id)
    gates_before = list(state.gates_passed)

    state = stage_state.revise(state, pages=["S02"], reason="Update visual emphasis")

    assert state.current_phase == "revision"
    assert state.gates_passed == gates_before
    assert state.flags["output_formats"] == ["pptx", "html"]
    assert state.flags["revision_active"] is True
    assert state.flags["revision_id"] == "revision-001"
    assert state.flags["revision_pages"] == ["S02"]
    request_path = state_path(workspace, session_id).parent / "revisions" / "revision-001" / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["pages"] == ["S02"]
    assert request["reason"] == "Update visual emphasis"


def test_revise_rejects_sessions_before_review_approval(workspace: Path, session_id: str) -> None:
    state = _advance_to_generation(workspace, session_id)

    with pytest.raises(InvalidTransitionError) as exc_info:
        stage_state.revise(state, pages=["S01"])

    assert "review_approved" in exc_info.value.render()
    assert load(workspace, session_id).current_phase == "generation"


def test_revise_rejects_unknown_target_pages(workspace: Path, session_id: str) -> None:
    state = _advance_to_done_with_final_pages(workspace, session_id)

    with pytest.raises(InvalidTransitionError) as exc_info:
        stage_state.revise(state, pages=["S99"])

    rendered = exc_info.value.render()
    assert "unknown revision page" in rendered
    assert "S99" in rendered


def test_complete_revision_returns_to_done_and_preserves_outputs(
    workspace: Path, session_id: str
) -> None:
    state = _advance_to_done_with_final_pages(workspace, session_id)
    state = stage_state.revise(state, pages=["S01", "S02"])
    state = stage_state.complete_revision(state)

    assert state.current_phase == "done"
    assert "review_approved" in state.gates_passed
    assert state.flags["output_formats"] == ["pptx", "html"]
    assert state.flags["revision_active"] is False
    assert state.flags["revision_pages"] == []


def test_complete_revision_rejects_non_revision_session(
    workspace: Path, session_id: str
) -> None:
    state = _advance_to_done_with_final_pages(workspace, session_id)

    with pytest.raises(InvalidTransitionError) as exc_info:
        stage_state.complete_revision(state)

    assert "not in revision" in exc_info.value.render()


# ---------------------------------------------------------------------------
# Show
# ---------------------------------------------------------------------------


def test_render_show_includes_required_fields(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    rendered = render_show(state)
    assert "current_phase   : style" in rendered
    assert "gates_passed    : [needs_confirmed]" in rendered
    assert "next_gate       : style_locked" in rendered


# ---------------------------------------------------------------------------
# Require / pre-flight
# ---------------------------------------------------------------------------


def test_require_passes_when_constraints_met(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    require(
        workspace,
        session_id,
        phase_label="preview",
        phases=("style",),
        gates=("needs_confirmed",),
        flags={},
        next_action="python3 scripts/stage.py enter style --session-id <YYYY-MM-DD-title-slug>",
    )


def test_require_raises_when_phase_mismatch(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    with pytest.raises(StagePreflightError) as exc_info:
        require(
            workspace,
            session_id,
            phase_label="preview",
            phases=("style",),
            gates=("needs_confirmed",),
            flags={},
            next_action="python3 scripts/stage.py enter style --session-id <YYYY-MM-DD-title-slug>",
        )
    rendered = exc_info.value.render()
    assert "[stage] cannot build preview canvas: missing precondition" in rendered
    assert "current_phase   : intake" in rendered
    assert "missing" in rendered


def test_require_raises_when_flag_mismatch(workspace: Path, session_id: str) -> None:
    _advance_to_generation(workspace, session_id)
    state = load(workspace, session_id)
    # Force pages_ready off so the review flag check fails.
    state = set_flag(state, "pages_ready", "false")
    state.current_phase = "review"
    save(state)
    with pytest.raises(StagePreflightError) as exc_info:
        require(
            workspace,
            session_id,
            phase_label="review",
            phases=("review",),
            gates=(
                "needs_confirmed",
                "style_locked",
                "style_breakdown_confirmed",
                "pre_generation_confirmed",
            ),
            flags={"pages_ready": True},
            next_action="python3 scripts/stage.py set-flag pages_ready true --session-id <YYYY-MM-DD-title-slug>",
        )
    rendered = exc_info.value.render()
    assert "pages_ready=true" in rendered


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


def test_atomic_save_preserves_prior_content_on_replace_failure(
    workspace: Path, session_id: str
) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    prior = state_path(workspace, session_id).read_text(encoding="utf-8")

    state.current_phase = "content-basis"
    with mock.patch.object(os, "replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            save(state)

    after = state_path(workspace, session_id).read_text(encoding="utf-8")
    assert after == prior
