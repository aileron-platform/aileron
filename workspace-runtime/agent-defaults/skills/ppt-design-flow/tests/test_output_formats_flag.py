from __future__ import annotations

from pathlib import Path

import pytest

from deck_test_helpers import advance_to_review
from stage_state import InvalidTransitionError, init, pass_gate, reset, set_flag


def test_output_formats_defaults_empty(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    assert state.flags["output_formats"] == []


def test_output_formats_only_after_review_approved(workspace: Path, session_id: str) -> None:
    state = init(workspace, session_id)
    with pytest.raises(InvalidTransitionError) as exc_info:
        set_flag(state, "output_formats", '["pptx"]')
    assert "output_formats can only be set after review_approved" in exc_info.value.render()
    approved_session = f"{session_id}-approved"
    state = advance_to_review(workspace, approved_session)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["pptx", "html"]')
    assert state.flags["output_formats"] == ["pptx", "html"]


def test_output_formats_reject_invalid_element(workspace: Path, session_id: str) -> None:
    state = advance_to_review(workspace, session_id)
    state = pass_gate(state, "review_approved")
    with pytest.raises(InvalidTransitionError) as exc_info:
        set_flag(state, "output_formats", '["pdf"]')
    assert "output_formats elements must be one of {pptx, html}" in exc_info.value.render()


@pytest.mark.parametrize("from_phase", ["intake", "content-basis", "style", "planning", "generation", "review"])
def test_output_formats_reset_always_clears(workspace: Path, session_id: str, from_phase: str) -> None:
    state = advance_to_review(workspace, session_id)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["pptx", "html"]')
    state = reset(state, from_phase)
    assert state.flags["output_formats"] == []
