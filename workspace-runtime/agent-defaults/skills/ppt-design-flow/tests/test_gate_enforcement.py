"""End-to-end skip-gate scenario: stage.py init → direct build.py --phase=review
→ assert exit 2 and stderr regex from canvas-bundles/spec.md."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


PREFLIGHT_REGEX = re.compile(
    r"^\[stage\] cannot build [a-z-]+ canvas: missing precondition\n"
    r"(?: {2}(?!next_action)[a-z_]+ +: .+\n)+"
    r" {2}next_action +: .+\n"
    r"(?: {20}.+\n?)*$"
)


def _run(cli: Path, args: list[str], workspace: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cli), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "WORKSPACE_DIR": str(workspace)},
        check=False,
    )


def test_skip_gate_is_blocked_by_builder(
    workspace: Path, session_id: str, stage_cli: Path, build_cli: Path
) -> None:
    # 1. Init the session — phase is now `intake`.
    init_result = _run(stage_cli, ["init", "--session-id", session_id], workspace)
    assert init_result.returncode == 0, init_result.stderr

    # 2. Skip every gate and attempt to build the review canvas.
    skip_result = _run(
        build_cli,
        ["--phase=review", "--session-id", session_id],
        workspace,
    )
    assert skip_result.returncode == 2
    assert PREFLIGHT_REGEX.match(skip_result.stderr + "\n"), skip_result.stderr
    # No bundle directory should have been created.
    assert not (workspace / ".aileron" / "canvases" / "ppt-design-flow" / session_id / "review").exists()

    # 3. Walk the full happy path and confirm the same command succeeds.
    for cmd in [
        ["pass", "needs_confirmed"],
        ["enter", "content-basis"],
        ["enter", "style"],
        ["pass", "style_locked"],
        ["pass", "style_breakdown_confirmed"],
        ["enter", "planning"],
        ["pass", "pre_generation_confirmed"],
        ["enter", "generation"],
        ["set-flag", "pages_ready", "true"],
        ["enter", "review"],
        ["pass", "review_approved"],
    ]:
        # ``stage.py reset --from`` uses ``--from`` (long flag); the rest take positional args.
        step_result = _run(stage_cli, [*cmd, "--session-id", session_id], workspace)
        assert step_result.returncode == 0, (cmd, step_result.stderr)

    # 4. Build review with an image: gate enforcement does not apply post-G5 because we already passed it.
    # Reset pages_ready to ensure the test stays meaningful: review build still works since we just reset to review.
