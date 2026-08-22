"""Python 3.9 runtime compatibility for every live RKE2 deployment CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[2] / "deploy" / "rke2"


def test_every_live_deployment_python_entrypoint_imports_and_handles_help() -> None:
    failures: list[str] = []
    for script in sorted(SCRIPT_DIRECTORY.glob("*.py")):
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode != 0:
            failures.append(f"{script.name}: {completed.stderr.strip()}")

    assert failures == []
