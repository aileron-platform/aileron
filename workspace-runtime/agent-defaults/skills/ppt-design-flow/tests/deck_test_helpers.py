"""Test helpers for final deck builder tests."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

import stage_state
from stage_state import enter_phase, init, pass_gate, set_flag


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l0z9WQAAAABJRU5ErkJggg=="
)


def run_cli(cli: Path, args: list[str], workspace: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "WORKSPACE_DIR": str(workspace)}
    return subprocess.run(
        [sys.executable, str(cli), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def write_final_pages(workspace: Path, session_id: str, count: int = 2) -> list[Path]:
    generation_dir = stage_state.state_path(workspace, session_id).parent / "generation" / "final-pages"
    generation_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(1, count + 1):
        path = generation_dir / f"S{index:02d}.png"
        path.write_bytes(PNG_BYTES)
        paths.append(path)
    return paths


def advance_to_review(workspace: Path, session_id: str, *, fast_mode: bool = False) -> stage_state.State:
    state = init(workspace, session_id)
    if fast_mode:
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
    state = set_flag(state, "pages_ready", "true")
    state = enter_phase(state, "review")
    return state


def approve_for_formats(
    workspace: Path,
    session_id: str,
    formats: list[str],
    *,
    fast_mode: bool = False,
) -> stage_state.State:
    state = advance_to_review(workspace, session_id, fast_mode=fast_mode)
    state = pass_gate(state, "review_approved")
    state = set_flag(state, "output_formats", formats)
    write_final_pages(workspace, session_id)
    return state
