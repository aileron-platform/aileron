from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[4]
INSTALLER_PATH = RUNTIME_ROOT / "install-claude-cli.sh"
DOCKERFILE_PATH = RUNTIME_ROOT / "Dockerfile"
EXPECTED_FINGERPRINT = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_installer(
    tmp_path: Path,
    *,
    target: str,
    architecture: str,
    package_version: str,
    cli_output: str,
    primary_fingerprints: tuple[str, ...] = (EXPECTED_FINGERPRINT,),
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "calls.log"
    keyring_dir = tmp_path / "keyrings"
    source_dir = tmp_path / "sources"

    _write_executable(
        fake_bin / "curl",
        f"""#!/bin/sh
set -eu
printf 'curl %s\\n' "$*" >> "{call_log}"
output=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output" ]; then
        shift
        output="$1"
    fi
    shift
done
printf 'test signing key\\n' > "$output"
""",
    )
    _write_executable(
        fake_bin / "gpg",
        """#!/bin/sh
set -eu
"""
        + f'printf \'gpg %s\\n\' "$*" >> "{call_log}"\n'
        + "".join(
            f"printf 'pub:::::::::\\n'\nprintf 'fpr:::::::::{fingerprint}:\\n'\n"
            for fingerprint in primary_fingerprints
        ),
    )
    _write_executable(
        fake_bin / "dpkg",
        f"""#!/bin/sh
set -eu
printf 'dpkg %s\\n' "$*" >> "{call_log}"
test "$1" = "--print-architecture"
printf '{architecture}\\n'
""",
    )
    _write_executable(
        fake_bin / "apt-get",
        f"""#!/bin/sh
set -eu
printf 'apt-get %s\\n' "$*" >> "{call_log}"
""",
    )
    _write_executable(
        fake_bin / "dpkg-query",
        f"""#!/bin/sh
set -eu
printf 'dpkg-query %s\\n' "$*" >> "{call_log}"
printf '{package_version}'
""",
    )
    _write_executable(
        fake_bin / "claude",
        f"""#!/bin/sh
set -eu
printf 'claude %s\\n' "$*" >> "{call_log}"
printf '%s\\n' '{cli_output}'
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["CLAUDE_APT_KEYRING_DIR"] = str(keyring_dir)
    env["CLAUDE_APT_SOURCE_DIR"] = str(source_dir)
    result = subprocess.run(
        ["sh", str(INSTALLER_PATH), target],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return result, call_log, source_dir / "claude-code.list"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "architecture", "package_version", "channel", "package_spec"),
    [
        ("stable", "amd64", "3.2.1-1", "stable", "claude-code"),
        ("latest", "arm64", "3.2.1-1", "latest", "claude-code"),
        ("3.2.1", "arm64", "3.2.1-1", "latest", "claude-code=3.2.1-1"),
    ],
)
def test_installer_maps_supported_architectures_and_version_targets(
    tmp_path: Path,
    target: str,
    architecture: str,
    package_version: str,
    channel: str,
    package_spec: str,
) -> None:
    result, call_log, source_path = _run_installer(
        tmp_path,
        target=target,
        architecture=architecture,
        package_version=package_version,
        cli_output=f"{package_version.removesuffix('-1')} (Claude Code)",
    )

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text(encoding="utf-8")
    assert calls.count("apt-get -o Acquire::Retries=5") == 2
    assert "Acquire::http::Timeout=300" in calls
    assert "Acquire::https::Timeout=300" in calls
    assert calls.count(" install -y --no-install-recommends ") == 1
    assert package_spec in calls
    assert "--retry 5" in calls
    assert "--retry-all-errors" in calls
    assert source_path.read_text(encoding="utf-8") == (
        f"deb [arch={architecture} signed-by={tmp_path / 'keyrings' / 'claude-code.asc'}] "
        f"https://downloads.claude.ai/claude-code/apt/{channel} {channel} main\n"
    )


@pytest.mark.unit
def test_installer_rejects_untrusted_signing_key_before_apt(tmp_path: Path) -> None:
    result, call_log, source_path = _run_installer(
        tmp_path,
        target="stable",
        architecture="amd64",
        package_version="3.2.1-1",
        cli_output="3.2.1 (Claude Code)",
        primary_fingerprints=("0000000000000000000000000000000000000000",),
    )

    assert result.returncode != 0
    assert "signing key fingerprint verification failed" in result.stderr
    assert "apt-get" not in call_log.read_text(encoding="utf-8")
    assert not source_path.exists()


@pytest.mark.unit
def test_installer_rejects_extra_primary_signing_key(tmp_path: Path) -> None:
    result, call_log, source_path = _run_installer(
        tmp_path,
        target="stable",
        architecture="arm64",
        package_version="3.2.1-1",
        cli_output="3.2.1 (Claude Code)",
        primary_fingerprints=(
            EXPECTED_FINGERPRINT,
            "0000000000000000000000000000000000000000",
        ),
    )

    assert result.returncode != 0
    assert "signing key fingerprint verification failed" in result.stderr
    assert "apt-get" not in call_log.read_text(encoding="utf-8")
    assert not source_path.exists()


@pytest.mark.unit
def test_installer_rejects_cli_and_package_version_mismatch(tmp_path: Path) -> None:
    result, _, _ = _run_installer(
        tmp_path,
        target="stable",
        architecture="arm64",
        package_version="3.2.1-1",
        cli_output="3.2.0 (Claude Code)",
    )

    assert result.returncode != 0
    assert "executable version mismatch" in result.stderr


@pytest.mark.unit
def test_runtime_dockerfile_uses_single_official_package_install_path() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "https://claude.ai/install.sh" not in dockerfile
    assert (
        "COPY workspace-runtime/install-claude-cli.sh "
        "/usr/local/bin/install-claude-cli.sh" in dockerfile
    )
    assert '/usr/local/bin/install-claude-cli.sh "${CLAUDE_CLI_VERSION}"' in dockerfile
    package_block = dockerfile.split(
        "RUN apt-get update && apt-get install -y --fix-missing \\\n", 1
    )[1].split("    && rm -rf /var/lib/apt/lists/*", 1)[0]
    packages = tuple(
        line.strip().removesuffix("\\").strip()
        for line in package_block.splitlines()
        if line.strip()
    )
    assert packages == (
        "bubblewrap",
        "ca-certificates",
        "curl",
        "gnupg",
        "supervisor",
        "tzdata",
        "locales",
        "wget",
    )
    assert "/home/developer/.local/bin/claude" not in dockerfile
    assert "/opt/aileron/bin/claude" not in dockerfile
    assert "/usr/bin:/bin" in dockerfile
