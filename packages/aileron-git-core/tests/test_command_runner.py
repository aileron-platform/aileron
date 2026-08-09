import os
import subprocess

from aileron_git_core.command_runner import (
    _build_env,
    build_git_command,
    run_git,
)


def test_build_env_forces_c_locale():
    env = _build_env({"PATH": "/usr/bin"})
    assert env.get("LC_ALL") == "C"
    assert env.get("LANGUAGE") == "C"
    assert env["PATH"] == "/usr/bin"


def test_build_env_preserves_process_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/runtime-home")

    env = _build_env(None)

    assert env.get("LC_ALL") == "C"
    assert env.get("HOME") == "/tmp/runtime-home"


def test_build_env_uses_explicit_caller_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/runtime-home")

    env = _build_env({"PATH": "/usr/bin"})

    assert env.get("PATH") == "/usr/bin"
    assert "HOME" not in env


def test_build_git_command_uses_only_the_canonical_repository_path(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    command = build_git_command(repository / ".." / "repository", "status")

    assert command == [
        "git",
        "-c",
        f"safe.directory={repository.resolve()}",
        "-c",
        "core.quotepath=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-C",
        str(repository.resolve()),
        "status",
    ]


def test_run_git_accepts_repository_owned_by_a_different_uid(tmp_path):
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(repository)],
        check=True,
        capture_output=True,
    )
    different_owner_env = {
        **os.environ,
        "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
    }
    unsafe_result = subprocess.run(
        ["git", "-C", str(repository), "status", "--short"],
        env=different_owner_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert unsafe_result.returncode != 0
    assert "dubious ownership" in unsafe_result.stderr

    result = run_git(
        repository,
        "status",
        "--short",
        env=different_owner_env,
    )

    assert result.returncode == 0


def test_run_git_reads_global_config_from_process_home(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(repository)],
        check=True,
        capture_output=True,
    )
    runtime_home = tmp_path / "runtime-home"
    runtime_home.mkdir()
    monkeypatch.setenv("HOME", str(runtime_home))
    subprocess.run(
        ["git", "config", "--global", "user.name", "Configured User"],
        check=True,
        capture_output=True,
        env=dict(os.environ),
    )

    result = run_git(repository, "config", "--global", "--get", "user.name")

    assert result.returncode == 0
    assert result.stdout.strip() == "Configured User"


def test_run_git_reports_non_ascii_paths_raw_instead_of_octal_escaped(tmp_path):
    repository = tmp_path / "repository"
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(repository)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Tester"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "t@example.com"],
        check=True,
        capture_output=True,
    )
    target = repository / "測試檔案.md"
    target.write_text("content\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repository), "add", "測試檔案.md"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-m", "add file"],
        check=True,
        capture_output=True,
    )

    # Without core.quotepath=false, git would print this as
    # "\346\270\254\350\251\246\346\252\224\346\241\210.md" instead.
    result = run_git(repository, "diff", "--name-status", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", "HEAD")

    assert "測試檔案.md" in result.stdout
    assert "\\" not in result.stdout
