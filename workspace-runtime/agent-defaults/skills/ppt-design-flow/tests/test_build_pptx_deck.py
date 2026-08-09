from __future__ import annotations

import re
import zipfile
from pathlib import Path

from deck_test_helpers import advance_to_review, approve_for_formats, run_cli, write_final_pages
from stage_state import pass_gate, set_flag


PREFLIGHT_REGEX = re.compile(
    r"^\[stage\] cannot build pptx deck: missing precondition\n"
    r"(?: {2}(?!next_action)[a-z_]+ +: .+\n)+"
    r" {2}next_action +: .+\n"
    r"(?: {20}.+\n?)*$"
)


def test_pptx_refuses_without_review_approved(workspace: Path, session_id: str, build_pptx_cli: Path) -> None:
    advance_to_review(workspace, session_id)
    write_final_pages(workspace, session_id)
    output = workspace / "deck.pptx"
    result = run_cli(build_pptx_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 2
    assert not output.exists()
    assert "missing         : [review_approved" in result.stderr
    assert PREFLIGHT_REGEX.match(result.stderr + "\n"), result.stderr


def test_pptx_refuses_without_format_flag(workspace: Path, session_id: str, build_pptx_cli: Path) -> None:
    state = advance_to_review(workspace, session_id)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", '["html"]')
    write_final_pages(workspace, session_id)
    output = workspace / "deck.pptx"
    result = run_cli(build_pptx_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 2
    assert "missing         : [output_formats contains pptx]" in result.stderr


def test_pptx_success_builds_valid_file(workspace: Path, session_id: str, build_pptx_cli: Path) -> None:
    approve_for_formats(workspace, session_id, ["pptx"])
    output = workspace / "custom-run" / "deck.pptx"
    result = run_cli(build_pptx_cli, ["--session-id", session_id, "--output", str(output)], workspace)
    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert zipfile.is_zipfile(output)
    with zipfile.ZipFile(output) as archive:
        slides = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
    assert len(slides) == 2
