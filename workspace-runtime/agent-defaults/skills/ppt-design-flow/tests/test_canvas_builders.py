"""Tests for assets/canvas/build.py covering each --phase value and the
pre-flight failure paths described in canvas-bundles/spec.md."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import stage_state
from deck_test_helpers import PNG_BYTES
from stage_state import (
    enter_phase,
    init,
    pass_gate,
    save,
    set_flag,
)


def _run_build(build_cli: Path, args: list[str], env_workspace: Path) -> subprocess.CompletedProcess:
    env = {"WORKSPACE_DIR": str(env_workspace), "PATH": ""}  # PATH unused; subprocess inherits via Popen default
    # Use sys.executable to ensure pytest's Python interpreter is used.
    return subprocess.run(
        [sys.executable, str(build_cli), *args],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, **env},
        check=False,
    )


def _advance_state(workspace: Path, session_id: str, *, up_to_review: bool = False) -> None:
    state = init(workspace, session_id)
    state = pass_gate(state, "needs_confirmed")
    state = enter_phase(state, "content-basis")
    state = enter_phase(state, "style")
    if not up_to_review:
        return
    state = pass_gate(state, "style_locked")
    state = pass_gate(state, "style_breakdown_confirmed")
    state = enter_phase(state, "planning")
    state = pass_gate(state, "pre_generation_confirmed")
    state = enter_phase(state, "generation")
    state = set_flag(state, "pages_ready", "true")
    state = enter_phase(state, "review")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_preview_phase_builds_preview_shell(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id)
    result = _run_build(
        build_cli,
        ["--phase=preview", "--session-id", session_id, "--print-artifact"],
        workspace,
    )
    assert result.returncode == 0, result.stderr
    bundle_index = (
        workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "style-preview" / "index.html"
    )
    assert bundle_index.exists()
    manifest = json.loads((workspace / ".aileron" / "canvas.json").read_text(encoding="utf-8"))
    assert manifest["contentDir"].endswith("/style-preview")
    assert manifest["contentDir"].startswith("./canvases/ppt-design-flow/")
    assert manifest["owner"] == {"skillName": "ppt-design-flow"}
    artifact_args = json.loads(result.stdout.rstrip().splitlines()[-1])
    assert artifact_args == {"title": "PPT style preview", "route": "/"}


def test_preview_phase_binds_passed_images(
    workspace: Path, session_id: str, build_cli: Path, tmp_path: Path
) -> None:
    _advance_state(workspace, session_id)
    img_a = tmp_path / "proposal-a-cover.png"
    img_b = tmp_path / "proposal-a-toc.png"
    img_c = tmp_path / "proposal-a-content.png"
    img_a.write_bytes(PNG_BYTES)
    img_b.write_bytes(PNG_BYTES)
    img_c.write_bytes(PNG_BYTES)

    result = _run_build(
        build_cli,
        [
            "--phase=preview",
            "--session-id",
            session_id,
            "--image",
            str(img_a),
            "--image",
            str(img_b),
            "--image",
            str(img_c),
            "--print-artifact",
        ],
        workspace,
    )

    assert result.returncode == 0, result.stderr
    bundle = (
        workspace
        / ".aileron"
        / "canvases"
        / "ppt-design-flow"
        / session_id
        / "style-preview"
    )
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert (bundle / "images" / "proposal-a-cover.png").exists()
    assert 'src="images/proposal-a-cover.png"' in index_html
    assert 'src="images/proposal-a-toc.png"' in index_html
    assert 'src="images/proposal-a-content.png"' in index_html


def test_preview_phase_reference_mode_binds_adopted_images_without_copy(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id)
    adopted = (
        workspace
        / ".aileron"
        / "canvases"
        / "ppt-design-flow"
        / session_id
        / "style"
        / "candidates"
        / "proposal-a-cover.png"
    )
    adopted.parent.mkdir(parents=True, exist_ok=True)
    adopted.write_bytes(PNG_BYTES)

    result = _run_build(
        build_cli,
        [
            "--phase=preview",
            "--session-id",
            session_id,
            "--asset-mode",
            "reference",
            "--image",
            str(adopted),
            "--print-artifact",
        ],
        workspace,
    )

    assert result.returncode == 0, result.stderr
    session_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id
    bundle = session_dir / "style-preview"
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert not (bundle / "images" / "proposal-a-cover.png").exists()
    assert 'src="style/candidates/proposal-a-cover.png"' in index_html
    assert (session_dir / "index.html").exists()


def test_candidate_picker_phase_builds_shell(
    workspace: Path, session_id: str, build_cli: Path, tmp_path: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    # Roll back to generation and set candidate_mode multi for the candidate-picker happy path.
    state = stage_state.load(workspace, session_id)
    state = stage_state.reset(state, "generation")
    state = set_flag(state, "candidate_mode", "multi")
    save(state)
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    img_a.write_bytes(b"a")
    img_b.write_bytes(b"b")
    result = _run_build(
        build_cli,
        [
            "--phase=candidate-picker",
            "--session-id",
            session_id,
            "--image",
            str(img_a),
            "--image",
            str(img_b),
            "--print-artifact",
        ],
        workspace,
    )
    assert result.returncode == 0, result.stderr
    bundle = (
        workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "candidate-picker"
    )
    assert (bundle / "index.html").exists()
    assert (bundle / "images" / "a.png").exists()
    assert (bundle / "images" / "b.png").exists()


def test_review_phase_builds_shell(
    workspace: Path, session_id: str, build_cli: Path, tmp_path: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    img_a = tmp_path / "S01.png"
    img_b = tmp_path / "S02.png"
    img_a.write_bytes(b"p1")
    img_b.write_bytes(b"p2")
    result = _run_build(
        build_cli,
        [
            "--phase=review",
            "--session-id",
            session_id,
            "--image",
            str(img_a),
            "--image",
            str(img_b),
            "--print-artifact",
        ],
        workspace,
    )
    assert result.returncode == 0, result.stderr
    bundle = (
        workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "review"
    )
    assert (bundle / "index.html").exists()
    assert (bundle / "images" / "S01.png").exists()
    assert (bundle / "images" / "S02.png").exists()
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert '"image": "images/S01.png"' in index_html
    assert '"image": "images/S02.png"' in index_html
    assert "data:image/svg+xml" not in index_html


def test_review_phase_reference_mode_uses_adopted_images_without_copy(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    adopted = (
        workspace
        / ".aileron"
        / "canvases"
        / "ppt-design-flow"
        / session_id
        / "generation"
        / "final-pages"
        / "S01.png"
    )
    adopted.parent.mkdir(parents=True, exist_ok=True)
    adopted.write_bytes(PNG_BYTES)

    result = _run_build(
        build_cli,
        [
            "--phase=review",
            "--session-id",
            session_id,
            "--asset-mode",
            "reference",
            "--image",
            str(adopted),
            "--print-artifact",
        ],
        workspace,
    )

    assert result.returncode == 0, result.stderr
    bundle = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "review"
    assert (bundle / "index.html").exists()
    assert not (bundle / "images" / "S01.png").exists()
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert '"image": "generation/final-pages/S01.png"' in index_html
    assert "../generation" not in index_html
    manifest = json.loads((workspace / ".aileron" / "canvas.json").read_text(encoding="utf-8"))
    assert manifest["contentDir"].endswith(f"/ppt-design-flow/{session_id}")
    assert manifest["routes"] == [{"path": "/", "label": "PPT review"}]
    assert (workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "index.html").exists()


def test_review_phase_uses_image_list_without_copy(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    session_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id
    final_dir = session_dir / "generation" / "final-pages"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "S01-v2.png").write_bytes(PNG_BYTES)
    (final_dir / "S02.png").write_bytes(PNG_BYTES)
    image_list = session_dir / "generation" / "final-pages.json"
    image_list.write_text(
        json.dumps(
            {
                "version": 1,
                "pages": [
                    {"slide_id": "S01", "path": "generation/final-pages/S01-v2.png"},
                    {"slide_id": "S02", "path": "generation/final-pages/S02.png"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _run_build(
        build_cli,
        [
            "--phase=review",
            "--session-id",
            session_id,
            "--asset-mode",
            "reference",
            "--image-list",
            str(image_list),
            "--print-artifact",
        ],
        workspace,
    )

    assert result.returncode == 0, result.stderr
    bundle = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "review"
    assert not (bundle / "images" / "S01-v2.png").exists()
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert '"image": "generation/final-pages/S01-v2.png"' in index_html
    assert '"image": "generation/final-pages/S02.png"' in index_html


def test_revision_phase_builds_focused_review_shell(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    state = stage_state.load(workspace, session_id)
    state = pass_gate(state, "review_approved")
    state = enter_phase(state, "done")
    session_dir = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id
    final_dir = session_dir / "generation" / "final-pages"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "S01.png").write_bytes(PNG_BYTES)
    (final_dir / "S02.png").write_bytes(PNG_BYTES)
    image_list = session_dir / "generation" / "final-pages.json"
    image_list.write_text(
        json.dumps(
            {
                "version": 1,
                "pages": [
                    {"slide_id": "S01", "path": "generation/final-pages/S01.png"},
                    {"slide_id": "S02", "path": "generation/final-pages/S02.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    stage_state.revise(state, pages=["S02"])

    result = _run_build(
        build_cli,
        [
            "--phase=revision",
            "--session-id",
            session_id,
            "--revision-id",
            "revision-001",
            "--asset-mode",
            "reference",
            "--image-list",
            str(image_list),
            "--print-artifact",
        ],
        workspace,
    )

    assert result.returncode == 0, result.stderr
    bundle = workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "revision"
    index_html = (bundle / "index.html").read_text(encoding="utf-8")
    assert '"image": "generation/final-pages/S02.png"' in index_html
    assert '"image": "generation/final-pages/S01.png"' not in index_html
    assert "review-shell-v2" in index_html


def test_revision_phase_requires_revision_state(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    result = _run_build(
        build_cli,
        ["--phase=revision", "--session-id", session_id],
        workspace,
    )

    assert result.returncode == 2
    assert "current_phase∈{revision}" in result.stderr


def test_reference_mode_rejects_images_outside_workspace(
    workspace: Path, session_id: str, build_cli: Path, tmp_path: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    outside = tmp_path / "S01.png"
    outside.write_bytes(PNG_BYTES)

    result = _run_build(
        build_cli,
        [
            "--phase=review",
            "--session-id",
            session_id,
            "--asset-mode",
            "reference",
            "--image",
            str(outside),
        ],
        workspace,
    )

    assert result.returncode != 0
    assert "reference-mode images must live under the workspace root" in result.stderr


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_review_build_blocked_when_pages_not_ready(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    # Clear the pages_ready flag so review pre-flight fails.
    state = stage_state.load(workspace, session_id)
    state = set_flag(state, "pages_ready", "false")
    save(state)
    result = _run_build(
        build_cli,
        ["--phase=review", "--session-id", session_id],
        workspace,
    )
    assert result.returncode == 2
    assert "missing         : [pages_ready=true]" in result.stderr


def test_review_build_fails_when_image_is_missing(
    workspace: Path, session_id: str, build_cli: Path, tmp_path: Path
) -> None:
    _advance_state(workspace, session_id, up_to_review=True)
    result = _run_build(
        build_cli,
        [
            "--phase=review",
            "--session-id",
            session_id,
            "--image",
            str(tmp_path / "missing.png"),
        ],
        workspace,
    )
    assert result.returncode != 0
    assert "Image source not found" in result.stderr


def test_preview_build_blocked_outside_style_phase(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    init(workspace, session_id)  # phase: intake
    result = _run_build(
        build_cli,
        ["--phase=preview", "--session-id", session_id],
        workspace,
    )
    assert result.returncode == 2
    assert "current_phase   : intake" in result.stderr


def test_unknown_phase_rejected_by_argparse(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    result = _run_build(
        build_cli,
        ["--phase=foo", "--session-id", session_id],
        workspace,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower()
    bundle_root = workspace / ".aileron" / "canvases"
    assert not bundle_root.exists()


# ---------------------------------------------------------------------------
# Stderr contract
# ---------------------------------------------------------------------------


PREFLIGHT_REGEX = re.compile(
    r"^\[stage\] cannot build [a-z-]+ canvas: missing precondition\n"
    r"(?: {2}(?!next_action)[a-z_]+ +: .+\n)+"
    r" {2}next_action +: .+\n"
    r"(?: {20}.+\n?)*$"
)


def test_preflight_stderr_matches_documented_regex(
    workspace: Path, session_id: str, build_cli: Path
) -> None:
    init(workspace, session_id)  # intake
    result = _run_build(
        build_cli,
        ["--phase=review", "--session-id", session_id],
        workspace,
    )
    assert result.returncode == 2
    assert PREFLIGHT_REGEX.match(result.stderr + "\n"), result.stderr
