from pathlib import Path
import subprocess

import aileron_git_core.mutations as mutations_module
from aileron_git_core import (
    GitCommandResult,
    checkout_paths,
    commit_staged,
    fetch_remote,
    git_allow_failure,
    has_head,
    list_commits,
    list_remote_branches,
    pull_remote,
    push_remote,
    stage_all,
    stage_paths,
    unstage_all,
    unstage_paths,
)


def run_git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=check,
        text=True,
    )


def init_repo(path: Path) -> Path:
    path.mkdir()
    run_git(path, "init", "-b", "main")
    run_git(path, "config", "user.name", "Tester")
    run_git(path, "config", "user.email", "tester@example.test")
    return path


def commit_file(repo: Path, relative_path: str, content: str, message: str) -> str:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    run_git(repo, "add", relative_path)
    run_git(repo, "commit", "-m", message)
    return run_git(repo, "rev-parse", "HEAD").stdout.strip()


def test_git_allow_failure_returns_non_zero_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    result = git_allow_failure(repo, "rev-parse", "--verify", "missing-ref")

    assert result.returncode != 0
    assert "missing-ref" in result.args


def test_git_allow_failure_passes_environment_overrides(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    git_allow_failure(tmp_path, "status", env={"GIT_SSH_COMMAND": "ssh -i key"})

    assert captured["GIT_SSH_COMMAND"] == "ssh -i key"


def test_remote_mutations_pass_explicit_environment(
    monkeypatch, tmp_path: Path
) -> None:
    environment = {"GIT_SSH_COMMAND": "ssh -i registry-key"}
    captured: list[tuple[tuple[str, ...], dict[str, str] | None]] = []

    def fake_run_git(_repo_root, *args, env=None, **_kwargs):
        captured.append((args, env))
        return GitCommandResult(
            args=["git", *args],
            returncode=0,
            stdout="",
            stderr="",
        )

    def fake_git_allow_failure(_repo_root, *args, env=None, **_kwargs):
        captured.append((args, env))
        return GitCommandResult(
            args=["git", *args],
            returncode=0,
            stdout="=\trefs/heads/main:refs/heads/main\t[up to date]\n",
            stderr="",
        )

    monkeypatch.setattr(mutations_module, "run_git", fake_run_git)
    monkeypatch.setattr(mutations_module, "git_allow_failure", fake_git_allow_failure)
    monkeypatch.setattr(mutations_module, "has_head", lambda _repo_root: False)

    fetch_remote(tmp_path, env=environment)
    pull_remote(tmp_path, branch="main", env=environment)
    push_remote(tmp_path, branch="main", env=environment)

    assert captured == [
        (("fetch", "origin"), environment),
        (("pull", "--ff-only", "origin", "main"), environment),
        (("push", "--porcelain", "origin", "main"), environment),
    ]


def test_list_remote_branches_returns_default_first_and_passes_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    environment = {"GIT_SSH_COMMAND": "ssh -i registry-key"}
    captured: dict[str, object] = {}

    def fake_run_git(_repo_root, *args, env=None, **_kwargs):
        captured["args"] = args
        captured["env"] = env
        return GitCommandResult(
            args=["git", *args],
            returncode=0,
            stdout=(
                "ref: refs/heads/main\tHEAD\n"
                "1111111111111111111111111111111111111111\tHEAD\n"
                "2222222222222222222222222222222222222222\trefs/heads/develop\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(mutations_module, "run_git", fake_run_git)

    result = list_remote_branches(
        tmp_path,
        "git@example.com:team/repository.git",
        env=environment,
    )

    assert result.default_branch == "main"
    assert result.branches == ["main", "develop"]
    assert captured == {
        "args": (
            "ls-remote",
            "--symref",
            "--",
            "git@example.com:team/repository.git",
            "HEAD",
            "refs/heads/*",
        ),
        "env": {
            **environment,
            "GIT_TERMINAL_PROMPT": "0",
        },
    }


def test_push_remote_preserves_all_ref_statuses_and_nonzero_exit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_git_allow_failure(_repo_root, *_args, **_kwargs):
        return GitCommandResult(
            args=["git", "push"],
            returncode=1,
            stdout=(
                " \trefs/heads/one:refs/heads/one\tabc..def\n"
                "!\trefs/heads/two:refs/heads/two\t[rejected] (fetch first)\n"
            ),
            stderr="remote rejected one or more refs",
        )

    monkeypatch.setattr(
        mutations_module,
        "git_allow_failure",
        fake_git_allow_failure,
    )

    result = push_remote(tmp_path)

    assert [(item.ref, item.status) for item in result] == [
        ("refs/heads/one", "ok"),
        ("refs/heads/two", "rejected"),
    ]
    assert all(item.diagnostic == "remote rejected one or more refs" for item in result)


def test_push_remote_adds_error_when_nonzero_exit_has_only_ok_ref_statuses(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_git_allow_failure(_repo_root, *_args, **_kwargs):
        return GitCommandResult(
            args=["git", "push"],
            returncode=1,
            stdout=" \trefs/heads/main:refs/heads/main\tabc..def\n",
            stderr="fatal: transport failed",
        )

    monkeypatch.setattr(
        mutations_module,
        "git_allow_failure",
        fake_git_allow_failure,
    )

    result = push_remote(tmp_path, branch="main")

    assert [(item.ref, item.status) for item in result] == [
        ("refs/heads/main", "ok"),
        ("main", "error"),
    ]
    assert result[-1].summary == "fatal: transport failed"


def test_has_head_detects_unborn_and_valid_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    assert has_head(repo) is False

    commit_file(repo, "tracked.txt", "base\n", "initial")

    assert has_head(repo) is True


def test_stage_and_unstage_update_index_state(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    commit_file(repo, "tracked.txt", "base\n", "initial")
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    stage_paths(repo, ["tracked.txt", "new.txt"])

    status = run_git(repo, "status", "--porcelain").stdout.splitlines()
    assert "M  tracked.txt" in status
    assert "A  new.txt" in status

    unstage_paths(repo, ["tracked.txt", "new.txt"])

    status = run_git(repo, "status", "--porcelain").stdout.splitlines()
    assert " M tracked.txt" in status
    assert "?? new.txt" in status


def test_stage_all_and_unstage_all_update_entire_index(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    commit_file(repo, "tracked.txt", "base\n", "initial")
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    stage_all(repo)

    status = run_git(repo, "status", "--porcelain").stdout.splitlines()
    assert "M  tracked.txt" in status
    assert "A  new.txt" in status

    unstage_all(repo)

    status = run_git(repo, "status", "--porcelain").stdout.splitlines()
    assert " M tracked.txt" in status
    assert "?? new.txt" in status


def test_checkout_paths_restores_modified_tracked_file(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    commit_file(repo, "tracked.txt", "base\n", "initial")
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")

    checkout_paths(repo, ["tracked.txt"])

    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "base\n"
    assert run_git(repo, "status", "--porcelain").stdout == ""


def test_commit_summary_includes_stats(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "alpha.txt").write_text("one\n", encoding="utf-8")
    stage_paths(repo, ["alpha.txt"])

    first = commit_staged(repo, "initial")

    assert first.message == "initial"
    assert first.author_name == "Tester"
    assert first.author_email == "tester@example.test"
    assert first.additions == 1
    assert first.deletions == 0
    assert first.files_changed == 1

def test_list_commits_returns_paginated_items_and_total_with_search(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    commit_file(repo, "one.txt", "one\n", "first feature")
    second_sha = commit_file(repo, "two.txt", "two\n", "second fix")
    third_sha = commit_file(repo, "three.txt", "three\n", "third feature")

    items, total = list_commits(repo, skip=1, limit=1)

    assert total == 3
    assert [item.sha for item in items] == [second_sha]

    searched, searched_total = list_commits(repo, search="feature")

    assert searched_total == 2
    assert [item.sha for item in searched] == [
        third_sha,
        run_git(repo, "rev-parse", "HEAD~2").stdout.strip(),
    ]


def test_push_remote_maps_successful_and_rejected_refs(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run_git(tmp_path, "init", "--bare", str(remote))
    clone_a = tmp_path / "clone-a"
    clone_b = tmp_path / "clone-b"
    run_git(tmp_path, "clone", str(remote), str(clone_a))
    run_git(tmp_path, "clone", str(remote), str(clone_b))
    for clone in (clone_a, clone_b):
        run_git(clone, "checkout", "-b", "main")
        run_git(clone, "config", "user.name", "Tester")
        run_git(clone, "config", "user.email", "tester@example.test")

    commit_file(clone_a, "a.txt", "a\n", "from a")

    success = push_remote(clone_a, branch="main")

    assert [(item.ref, item.status) for item in success] == [("refs/heads/main", "ok")]

    commit_file(clone_b, "b.txt", "b\n", "from b")

    rejected = push_remote(clone_b, branch="main")

    assert rejected
    assert rejected[0].status == "rejected"
    assert "main" in rejected[0].ref


def test_fetch_remote_returns_updated_refs(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run_git(tmp_path, "init", "--bare", str(remote))
    source = init_repo(tmp_path / "source")
    run_git(source, "remote", "add", "origin", str(remote))
    commit_file(source, "one.txt", "one\n", "one")
    push_remote(source, branch="main")
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", str(remote), str(clone))
    run_git(clone, "checkout", "-b", "main", "origin/main")
    commit_file(source, "two.txt", "two\n", "two")
    push_remote(source, branch="main")

    refs = fetch_remote(clone)

    assert any("origin/main" in ref for ref in refs)


def test_pull_remote_returns_incoming_commits_for_fast_forward(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    run_git(tmp_path, "init", "--bare", str(remote))
    source = init_repo(tmp_path / "source")
    run_git(source, "remote", "add", "origin", str(remote))
    commit_file(source, "one.txt", "one\n", "one")
    push_remote(source, branch="main")
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", str(remote), str(clone))
    run_git(clone, "checkout", "-b", "main", "origin/main")
    run_git(clone, "config", "user.name", "Tester")
    run_git(clone, "config", "user.email", "tester@example.test")
    incoming_sha = commit_file(source, "two.txt", "two\n", "two")
    push_remote(source, branch="main")

    output, incoming = pull_remote(clone, branch="main")

    assert "Fast-forward" in output
    assert [item.sha for item in incoming] == [incoming_sha]
    assert (clone / "two.txt").read_text(encoding="utf-8") == "two\n"
