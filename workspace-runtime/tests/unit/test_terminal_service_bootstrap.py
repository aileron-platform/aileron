from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "terminal_service.sh"


def _create_terminal_source_tree(root: Path) -> None:
    (root / "cmd" / "server").mkdir(parents=True, exist_ok=True)
    (root / "go.mod").write_text("module example.com/terminal-service\n\ngo 1.22\n", encoding="utf-8")
    (root / "cmd" / "server" / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")


def _create_fake_go(binary_dir: Path) -> None:
    fake_go = binary_dir / "go"
    fake_go.write_text(
        """#!/bin/sh
set -eu
output=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    shift
    output="$1"
    break
  fi
  shift
done
mkdir -p "$(dirname "$output")"
printf '#!/bin/sh\\necho built-%s\\n' "$GOARCH" > "$output"
""",
        encoding="utf-8",
    )
    fake_go.chmod(fake_go.stat().st_mode | stat.S_IEXEC)


def _write_minimal_elf(path: Path, machine_code: int) -> None:
    payload = bytearray(20)
    payload[0:4] = b"\x7fELF"
    payload[18:20] = machine_code.to_bytes(2, byteorder="little")
    path.write_bytes(payload)


def _run_bootstrap(source_dir: Path, binary_dir: Path, fake_go_dir: Path, goarch: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_TERMINAL_SOURCE_DIR"] = str(source_dir)
    env["WORKSPACE_TERMINAL_BINARY_DIR"] = str(binary_dir)
    env["WORKSPACE_TERMINAL_GOARCH"] = goarch
    env["PATH"] = f"{fake_go_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.unit
def test_terminal_bootstrap_rebuilds_missing_binary(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    source_dir = tmp_path / "workspace-terminal"
    binary_dir = tmp_path / "terminal-cache" / "bin"
    fake_go_dir = tmp_path / "fake-go"
    fake_go_dir.mkdir()
    _create_terminal_source_tree(source_dir)
    _create_fake_go(fake_go_dir)

    result = _run_bootstrap(source_dir, binary_dir, fake_go_dir, "arm64")

    assert result.returncode == 0, result.stderr
    assert (binary_dir / "terminal-service").read_text(encoding="utf-8") == "#!/bin/sh\necho built-arm64\n"


@pytest.mark.unit
def test_terminal_bootstrap_rebuilds_wrong_arch_binary(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    source_dir = tmp_path / "workspace-terminal"
    binary_dir = tmp_path / "terminal-cache" / "bin"
    fake_go_dir = tmp_path / "fake-go"
    fake_go_dir.mkdir()
    _create_terminal_source_tree(source_dir)
    _create_fake_go(fake_go_dir)
    binary_dir.mkdir(parents=True, exist_ok=True)
    _write_minimal_elf(binary_dir / "terminal-service", 183)

    result = _run_bootstrap(source_dir, binary_dir, fake_go_dir, "amd64")

    assert result.returncode == 0, result.stderr
    assert (binary_dir / "terminal-service").read_text(encoding="utf-8") == "#!/bin/sh\necho built-amd64\n"
