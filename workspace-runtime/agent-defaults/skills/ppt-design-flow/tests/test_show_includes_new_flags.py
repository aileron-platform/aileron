from __future__ import annotations

from pathlib import Path

from deck_test_helpers import advance_to_review
from stage_state import pass_gate, render_show, set_flag


def test_show_includes_fast_mode_and_output_formats(workspace: Path, session_id: str) -> None:
    state = advance_to_review(workspace, session_id, fast_mode=True)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["html"]')
    rendered = render_show(state)
    assert "fast_mode       : true" in rendered
    assert "output_formats  : [html]" in rendered
