from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

INITIALIZER = (
    Path(__file__).resolve().parents[4] / "scripts" / "initialize_workspace_runtime.py"
)
INITIALIZER_SPEC = importlib.util.spec_from_file_location(
    "initialize_workspace_runtime",
    INITIALIZER,
)
assert INITIALIZER_SPEC is not None and INITIALIZER_SPEC.loader is not None
INITIALIZER_MODULE = importlib.util.module_from_spec(INITIALIZER_SPEC)
INITIALIZER_SPEC.loader.exec_module(INITIALIZER_MODULE)
sanitize_repository_url = INITIALIZER_MODULE.sanitize_repository_url
DEFAULTS_INITIALIZER = (
    Path(__file__).resolve().parents[4] / "scripts" / "initialize_agent_defaults.sh"
)


def _defaults_source(tmp_path: Path) -> Path:
    source = tmp_path / "defaults"
    skill = source / "skills" / "default-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Default\n", encoding="utf-8")
    (source / "mcp.json").write_text("{}\n", encoding="utf-8")
    (source / "CLAUDE.md").write_text("Claude policy\n", encoding="utf-8")
    (source / "AGENTS.md").write_text("Agent policy\n", encoding="utf-8")
    return source


def _environment(tmp_path: Path, **overrides: str) -> dict[str, str]:
    home = tmp_path / "home"
    setup_script = tmp_path / "custom-setup.sh"
    if not setup_script.exists():
        setup_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    environment = {
        **os.environ,
        "AILERON_WORKSPACE_ID": "workspace-test",
        "AILERON_WORKSPACE_PATH": str(tmp_path / "workspace"),
        "AILERON_AGENT_DEFAULTS_SOURCE": str(_defaults_source(tmp_path)),
        "AILERON_AGENT_DEFAULTS_INITIALIZER": str(DEFAULTS_INITIALIZER),
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "TERMINATION_LOG_PATH": str(tmp_path / "termination.log"),
        "CUSTOM_SETUP_SCRIPT": str(setup_script),
    }
    environment.update(overrides)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir(exist_ok=True)
    return environment


def _bootstrap_dir(environment: dict[str, str]) -> Path:
    return Path(environment["XDG_STATE_HOME"]) / "aileron" / "bootstrap"


def _run(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INITIALIZER)],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_initializer_derives_standard_paths_from_home(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    home = Path(environment["HOME"])
    for name in (
        "CODEX_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    ):
        environment.pop(name)

    result = _run(environment)

    assert result.returncode == 0, result.stderr
    assert (home / ".codex").is_dir()
    assert (home / ".config").is_dir()
    assert (home / ".local" / "share").is_dir()
    assert (
        home / ".local" / "state" / "aileron" / "bootstrap" / "state.json"
    ).is_file()


def _create_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    repository.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(repository)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Test User"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
        check=True,
    )
    (repository / "README.md").write_text("# Repository\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repository), "add", "README.md"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-m", "Initial"],
        check=True,
        capture_output=True,
    )
    return repository


@pytest.mark.unit
def test_repository_url_sanitizer_removes_credentials_and_query() -> None:
    assert (
        sanitize_repository_url(
            "https://token:secret@example.com/team/repo.git?access_token=secret#branch"
        )
        == "https://example.com/team/repo.git"
    )
    assert (
        sanitize_repository_url("ssh://git@example.com/team/repo.git")
        == "ssh://git@example.com/team/repo.git"
    )


@pytest.mark.unit
def test_initializer_clones_before_seeding_defaults(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path)
    environment = _environment(tmp_path, GIT_REPO_URL=str(repository))

    result = _run(environment)

    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    state = json.loads(
        (_bootstrap_dir(environment) / "state.json").read_text(encoding="utf-8")
    )
    assert result.returncode == 0, result.stderr
    assert (workspace / "README.md").read_text(encoding="utf-8") == "# Repository\n"
    home = Path(environment["HOME"])
    assert (home / ".claude" / "skills" / "default-skill").is_dir()
    assert (home / ".codex" / "skills" / "default-skill").is_dir()
    assert (home / ".config" / "opencode" / "skills" / "default-skill").is_dir()
    assert state["phase"] == "Succeeded"
    assert (
        state["gitRepoFingerprint"]
        == hashlib.sha256(str(repository).encode("utf-8")).hexdigest()
    )
    assert str(repository) not in json.dumps(state)
    assert not list(workspace.glob(".aileron-bootstrap-stage-*"))


@pytest.mark.unit
def test_initializer_rejects_nonempty_workspace_without_deleting_user_data(
    tmp_path: Path,
) -> None:
    repository = _create_repository(tmp_path)
    environment = _environment(tmp_path, GIT_REPO_URL=str(repository))
    user_file = Path(environment["AILERON_WORKSPACE_PATH"]) / "user.txt"
    user_file.write_text("keep\n", encoding="utf-8")

    result = _run(environment)

    assert result.returncode != 0
    assert result.stderr.strip() == "WORKSPACE_BOOTSTRAP_CONFLICT"
    assert user_file.read_text(encoding="utf-8") == "keep\n"
    assert not (Path(environment["AILERON_WORKSPACE_PATH"]) / ".git").exists()


@pytest.mark.unit
def test_initializer_resumes_publish_journal(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path)
    environment = _environment(tmp_path, GIT_REPO_URL=str(repository))
    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    bootstrap_dir = _bootstrap_dir(environment)
    bootstrap_dir.mkdir(parents=True)
    attempt_id = "resume-attempt"
    stage = workspace / f".aileron-bootstrap-stage-{attempt_id}"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(repository), str(stage)],
        check=True,
        capture_output=True,
    )
    (stage / ".git").rename(workspace / ".git")
    expected = sorted(entry.name for entry in [workspace / ".git", stage / "README.md"])
    state = {
        "schemaVersion": 1,
        "attemptId": attempt_id,
        "desiredRevision": 1,
        "observedRevision": 0,
        "gitRepoFingerprint": hashlib.sha256(
            str(repository).encode("utf-8")
        ).hexdigest(),
        "branch": "main",
        "commit": None,
        "phase": "Publishing",
        "publishJournal": {"expected": expected, "published": [".git"]},
        "errorCode": None,
    }
    (bootstrap_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    result = _run(environment)

    assert result.returncode == 0, result.stderr
    assert (workspace / "README.md").is_file()
    assert not stage.exists()


@pytest.mark.unit
def test_initializer_fails_when_succeeded_defaults_marker_is_missing(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    assert _run(environment).returncode == 0
    marker = _bootstrap_dir(environment) / "agent-defaults-v1.json"
    marker.unlink()

    result = _run(environment)

    assert result.returncode != 0
    assert result.stderr.strip() == "AGENT_DEFAULTS_STATE_MISSING"


@pytest.mark.unit
def test_initializer_surfaces_bounded_agent_defaults_diagnostic(
    tmp_path: Path,
) -> None:
    diagnostic_script = tmp_path / "failing-agent-defaults.sh"
    diagnostic_script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{'x' * 5000}agent-defaults-detail' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    diagnostic_script.chmod(0o755)
    environment = _environment(
        tmp_path,
        AILERON_AGENT_DEFAULTS_INITIALIZER=str(diagnostic_script),
    )

    result = _run(environment)

    assert result.returncode != 0
    diagnostic_lines = [
        line
        for line in result.stderr.splitlines()
        if line.startswith("Agent defaults initializer diagnostics: ")
    ]
    assert len(diagnostic_lines) == 1
    diagnostic = diagnostic_lines[0].split(": ", 1)[1]
    assert len(diagnostic) == 4096
    assert diagnostic.endswith("agent-defaults-detail")
    assert result.stderr.splitlines()[-1] == "AGENT_DEFAULTS_INIT_FAILED"


@pytest.mark.unit
def test_initializer_limits_custom_setup_output_and_returns_stable_code(
    tmp_path: Path,
) -> None:
    setup = tmp_path / "custom-setup.sh"
    setup.write_text(
        "while :; do printf '0123456789abcdef'; done\n",
        encoding="utf-8",
    )
    environment = _environment(
        tmp_path,
        CUSTOM_SETUP_SCRIPT=str(setup),
        CUSTOM_SETUP_OUTPUT_MAX_BYTES="1024",
        CUSTOM_SETUP_TIMEOUT_SECONDS="5",
    )

    result = _run(environment)

    assert result.returncode != 0
    assert result.stderr.strip() == "CUSTOM_SETUP_FAILED"
    assert (
        Path(environment["TERMINATION_LOG_PATH"]).read_text(encoding="ascii")
        == "CUSTOM_SETUP_FAILED\n"
    )
    assert not list(_bootstrap_dir(environment).glob(".custom-setup-*"))


@pytest.mark.unit
def test_initializer_rejects_missing_custom_setup_mount(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        CUSTOM_SETUP_SCRIPT=str(tmp_path / "missing-custom-setup.sh"),
    )

    result = _run(environment)

    assert result.returncode != 0
    assert result.stderr.strip() == "CUSTOM_SETUP_FAILED"
    assert (
        Path(environment["TERMINATION_LOG_PATH"]).read_text(encoding="ascii")
        == "CUSTOM_SETUP_FAILED\n"
    )


@pytest.mark.unit
def test_initializer_initializes_git_only_when_requested(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        WORKSPACE_INIT_GIT="1",
        GIT_INIT_BRANCH="main",
        GIT_USER_EMAIL="test@example.com",
    )

    result = _run(environment)

    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    assert result.returncode == 0, result.stderr
    assert (workspace / ".git").is_dir()
    email = subprocess.run(
        ["git", "-C", str(workspace), "config", "user.email"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert email.stdout.strip() == "test@example.com"


@pytest.mark.unit
def test_initializer_accepts_workspace_owned_by_injected_runtime_uid(
    tmp_path: Path,
) -> None:
    environment = _environment(
        tmp_path,
        WORKSPACE_INIT_GIT="1",
    )
    assert _run(environment).returncode == 0
    environment["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"

    result = _run(environment)

    assert result.returncode == 0, result.stderr
    global_safe_directories = subprocess.run(
        ["git", "config", "--global", "--get-all", "safe.directory"],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert global_safe_directories.returncode != 0
    assert global_safe_directories.stdout == ""


@pytest.mark.unit
def test_initializer_does_not_restore_deleted_defaults_on_restart(
    tmp_path: Path,
) -> None:
    environment = _environment(tmp_path)
    assert _run(environment).returncode == 0
    skill = (
        Path(environment["HOME"]) / ".codex" / "skills" / "default-skill"
    )
    shutil.rmtree(skill)

    result = _run(environment)

    assert result.returncode == 0, result.stderr
    assert not skill.exists()


@pytest.mark.unit
def test_initializer_rejects_missing_workspace_identity(tmp_path: Path) -> None:
    environment = _environment(tmp_path, AILERON_WORKSPACE_ID="")

    result = _run(environment)

    assert result.returncode != 0
    assert result.stderr.strip() == "RUNTIME_STATE_INIT_FAILED"
