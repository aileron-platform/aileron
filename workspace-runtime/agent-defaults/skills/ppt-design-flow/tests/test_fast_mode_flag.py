from __future__ import annotations

from pathlib import Path

import pytest

from stage_state import InvalidTransitionError, enter_phase, init, pass_gate, reset, set_flag


def test_fast_mode_defaults_false(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    assert state.flags["fast_mode"] is False


def test_fast_mode_true_only_during_intake(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "fast_mode", "true")
    assert state.flags["fast_mode"] is True
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    with pytest.raises(InvalidTransitionError) as exc_info:
        set_flag(state, "fast_mode", "true")
    assert "fast_mode can only be enabled during intake" in exc_info.value.render()


def test_fast_mode_false_allowed_in_any_phase(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "fast_mode", "true")
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    state = set_flag(state, "fast_mode", "false")
    assert state.flags["fast_mode"] is False


@pytest.mark.parametrize(
    ("from_phase", "preserved"),
    [
        ("intake", True),
        ("content-basis", True),
        ("style", False),
        ("planning", False),
        ("generation", False),
        ("review", False),
    ],
)
def test_fast_mode_reset_rules(workspace: Path, session_id: str, from_phase: str, preserved: bool) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "fast_mode", "true")
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    state = pass_gate(state, "style_locked")
    state = pass_gate(state, "style_breakdown_confirmed")
    state = enter_phase(state, "planning")
    state = pass_gate(state, "pre_generation_confirmed")
    state = enter_phase(state, "generation")
    state = set_flag(state, "pages_ready", "true")
    state = enter_phase(state, "review")
    state = reset(state, from_phase)
    assert state.flags["fast_mode"] is preserved
