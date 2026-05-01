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
    build_log = binary_dir / "build.log"
    fake_go.write_text(
        f"""#!/bin/sh
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
case "$GOARCH" in
  arm64) machine_octal='\\267\\000' ;;
  amd64) machine_octal='\\076\\000' ;;
  *) echo "unsupported GOARCH: $GOARCH" >&2; exit 1 ;;
esac
{{
  printf '\\177ELF'
  dd if=/dev/zero bs=1 count=14 2>/dev/null
  printf "$machine_octal"
}} > "$output"
printf '%s\\n' "$GOARCH" >> "{build_log}"
""",
        encoding="utf-8",
    )
    fake_go.chmod(fake_go.stat().st_mode | stat.S_IEXEC)


def _write_minimal_elf(path: Path, machine_code: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bytearray(20)
    payload[0:4] = b"\x7fELF"
    payload[18:20] = machine_code.to_bytes(2, byteorder="little")
    path.write_bytes(payload)


def _run_bootstrap(
    source_dir: Path,
    cache_dir: Path,
    fake_go_dir: Path,
    goarch: str,
    *,
    prebuilt_binary: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_TERMINAL_SOURCE_DIR"] = str(source_dir)
    env["WORKSPACE_TERMINAL_CACHE_DIR"] = str(cache_dir)
    env["WORKSPACE_TERMINAL_GOARCH"] = goarch
    env["WORKSPACE_TERMINAL_PREBUILT_BINARY"] = str(prebuilt_binary or (cache_dir / "prebuilt" / "terminal-service"))
    env["PATH"] = f"{fake_go_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.unit
def test_terminal_bootstrap_uses_prebuilt_binary_by_default(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    source_dir = tmp_path / "workspace-terminal"
    cache_dir = tmp_path / "terminal-cache"
    prebuilt_binary = tmp_path / "prebuilt" / "terminal-service"
    fake_go_dir = tmp_path / "fake-go"
    fake_go_dir.mkdir()
    _create_terminal_source_tree(source_dir)
    _create_fake_go(fake_go_dir)
    _write_minimal_elf(prebuilt_binary, 183)

    result = _run_bootstrap(source_dir, cache_dir, fake_go_dir, "arm64", prebuilt_binary=prebuilt_binary)

    assert result.returncode == 0, result.stderr
    assert f"Using terminal-service binary: {prebuilt_binary}" in result.stdout
    assert not any(cache_dir.rglob("terminal-service"))
    build_log = fake_go_dir / "build.log"
    assert not build_log.exists()


@pytest.mark.unit
def test_terminal_bootstrap_fails_on_missing_prebuilt_binary(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    source_dir = tmp_path / "workspace-terminal"
    cache_dir = tmp_path / "terminal-cache"
    fake_go_dir = tmp_path / "fake-go"
    fake_go_dir.mkdir()
    _create_terminal_source_tree(source_dir)
    _create_fake_go(fake_go_dir)

    # No prebuilt binary provided - should fail
    result = _run_bootstrap(source_dir, cache_dir, fake_go_dir, "arm64", prebuilt_binary=None)

    assert result.returncode != 0
    assert "ERROR: terminal-service prebuilt binary not found or incompatible" in result.stderr

@pytest.mark.unit
def test_terminal_bootstrap_fails_on_incompatible_prebuilt_binary(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    source_dir = tmp_path / "workspace-terminal"
    cache_dir = tmp_path / "terminal-cache"
    prebuilt_binary = tmp_path / "prebuilt" / "terminal-service"
    fake_go_dir = tmp_path / "fake-go"
    fake_go_dir.mkdir()
    _create_terminal_source_tree(source_dir)
    _create_fake_go(fake_go_dir)
    _write_minimal_elf(prebuilt_binary, 183)  # ARM64 binary

    # Request amd64 but provide ARM64 binary - should fail
    result = _run_bootstrap(source_dir, cache_dir, fake_go_dir, "amd64", prebuilt_binary=prebuilt_binary)

    assert result.returncode != 0
    assert "ERROR: terminal-service prebuilt binary not found or incompatible" in result.stderr
