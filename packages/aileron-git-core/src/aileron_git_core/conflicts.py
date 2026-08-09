from pathlib import Path
from typing import Iterable, Mapping

from .command_runner import git_allow_failure, run_git
from .errors import GitCommandError, VersionControlError
from .mutations import stage_paths


def mark_resolved(repo_root: Path, paths: Iterable[str]) -> None:
    stage_paths(repo_root, paths)


def abort_conflict(repo_root: Path) -> str:
    operations = (
        ("MERGE_HEAD", ("merge", "--abort")),
        ("REVERT_HEAD", ("revert", "--abort")),
        ("CHERRY_PICK_HEAD", ("cherry-pick", "--abort")),
    )
    for marker, command in operations:
        if git_allow_failure(repo_root, "rev-parse", "--verify", marker).returncode == 0:
            run_git(repo_root, *command)
            return command[0]
    git_dir = run_git(repo_root, "rev-parse", "--git-dir").stdout.strip()
    resolved_git_dir = (
        (repo_root / git_dir).resolve()
        if not Path(git_dir).is_absolute()
        else Path(git_dir)
    )
    if (resolved_git_dir / "rebase-merge").exists() or (resolved_git_dir / "rebase-apply").exists():
        run_git(repo_root, "rebase", "--abort")
        return "rebase"
    raise VersionControlError("unresolved_conflicts")


def revert_commit(
    repo_root: Path,
    sha: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    parents = run_git(repo_root, "rev-list", "--parents", "-n", "1", sha).stdout.split()
    if len(parents) > 2:
        raise VersionControlError("revert_merge_commit_unsupported")
    try:
        run_git(repo_root, "revert", "--no-edit", sha, env=environment)
    except GitCommandError as exc:
        git_allow_failure(repo_root, "revert", "--abort")
        raise VersionControlError("file_conflict", diagnostic=exc.stderr.strip()) from exc
    return run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
