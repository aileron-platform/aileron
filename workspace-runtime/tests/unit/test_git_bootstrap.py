from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_git_repo.sh"


def _run_bootstrap(workspace_path: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_BOOTSTRAP_WORKSPACE_PATH"] = str(workspace_path)
    env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.unit
def test_git_bootstrap_leaves_plain_workspace_unchanged_by_default(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    result = _run_bootstrap(workspace_path)

    assert result.returncode == 0, result.stderr
    assert not (workspace_path / ".git").exists()


@pytest.mark.unit
def test_git_bootstrap_initializes_repo_when_enabled(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    result = _run_bootstrap(
        workspace_path,
        WORKSPACE_INIT_GIT="1",
        GIT_USER_NAME="Test User",
        GIT_USER_EMAIL="test@example.com",
        GIT_INIT_BRANCH="main",
    )

    assert result.returncode == 0, result.stderr
    assert (workspace_path / ".git").is_dir()

    branch = subprocess.run(
        ["git", "-C", str(workspace_path), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    )
    email = subprocess.run(
        ["git", "-C", str(workspace_path), "config", "user.email"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert branch.stdout.strip() == "main"
    assert email.stdout.strip() == "test@example.com"


@pytest.mark.unit
def test_git_bootstrap_skips_init_when_clone_source_is_configured(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("bash-based bootstrap test requires a POSIX shell")

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    result = _run_bootstrap(
        workspace_path,
        WORKSPACE_INIT_GIT="1",
        GIT_REPO_URL="git@github.com:example/repo.git",
    )

    assert result.returncode == 0, result.stderr
    assert not (workspace_path / ".git").exists()
