from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "terminal_service.sh"


def _write_minimal_elf(path: Path, machine_code: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bytearray(20)
    payload[0:4] = b"\x7fELF"
    payload[18:20] = machine_code.to_bytes(2, byteorder="little")
    path.write_bytes(payload)


def _run_bootstrap(
    prebuilt_binary: Path,
    goarch: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_TERMINAL_GOARCH"] = goarch
    env["WORKSPACE_TERMINAL_PREBUILT_BINARY"] = str(prebuilt_binary)
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _require_posix_shell() -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")


@pytest.mark.unit
def test_terminal_bootstrap_uses_compatible_prebuilt_binary(tmp_path: Path) -> None:
    _require_posix_shell()
    prebuilt_binary = tmp_path / "prebuilt" / "terminal-service"
    _write_minimal_elf(prebuilt_binary, 183)

    result = _run_bootstrap(prebuilt_binary, "arm64")

    assert result.returncode == 0, result.stderr
    assert f"Using terminal-service binary: {prebuilt_binary}" in result.stdout


@pytest.mark.unit
def test_terminal_bootstrap_fails_on_missing_prebuilt_binary(tmp_path: Path) -> None:
    _require_posix_shell()

    result = _run_bootstrap(tmp_path / "missing" / "terminal-service", "arm64")

    assert result.returncode != 0
    assert (
        "ERROR: terminal-service prebuilt binary not found or incompatible"
        in result.stderr
    )


@pytest.mark.unit
def test_terminal_bootstrap_fails_on_incompatible_prebuilt_binary(
    tmp_path: Path,
) -> None:
    _require_posix_shell()
    prebuilt_binary = tmp_path / "prebuilt" / "terminal-service"
    _write_minimal_elf(prebuilt_binary, 183)

    result = _run_bootstrap(prebuilt_binary, "amd64")

    assert result.returncode != 0
    assert (
        "ERROR: terminal-service prebuilt binary not found or incompatible"
        in result.stderr
    )
