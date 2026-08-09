from __future__ import annotations

from pathlib import Path

from deck_test_helpers import advance_to_review
from stage_state import pass_gate, reset, set_flag


def test_fast_flow_recovery_reset_to_style_allows_detailed_flow(workspace: Path, session_id: str) -> None:
    state = advance_to_review(workspace, session_id, fast_mode=True)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "fast_mode", "false")
    state = reset(state, "style")
    assert state.current_phase == "style"
    assert state.flags["fast_mode"] is False
    assert state.gates_passed == ["needs_confirmed"]
    state = pass_gate(state, "style_locked")
    assert "style_locked" in state.gates_passed
