from __future__ import annotations

from pathlib import Path

from deck_test_helpers import run_cli, write_final_pages
from stage_state import enter_phase, init, pass_gate, set_flag


def test_fast_flow_happy_path_builds_both_outputs(
    workspace: Path,
    session_id: str,
    build_pptx_cli: Path,
    build_html_cli: Path,
) -> None:
    state = init(workspace, session_id)
    state = set_flag(state, "fast_mode", "true")
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = set_flag(state, "content_basis_ready", "true")
    state = enter_phase(state, "style")
    state = pass_gate(state, "style_locked")
    state = pass_gate(state, "style_breakdown_confirmed")
    state = enter_phase(state, "planning")
    state = pass_gate(state, "pre_generation_confirmed")
    state = enter_phase(state, "generation")
    write_final_pages(workspace, session_id)
    state = set_flag(state, "pages_ready", "true")
    state = enter_phase(state, "review")
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["pptx","html"]')

    run_dir = workspace / "fast-run"
    pptx = run_dir / "fast.pptx"
    html = run_dir / "fast.html"
    pptx_result = run_cli(build_pptx_cli, ["--session-id", session_id, "--output", str(pptx)], workspace)
    html_result = run_cli(build_html_cli, ["--session-id", session_id, "--output", str(html)], workspace)
    assert pptx_result.returncode == 0, pptx_result.stderr
    assert html_result.returncode == 0, html_result.stderr
    assert pptx.exists()
    assert html.exists()
