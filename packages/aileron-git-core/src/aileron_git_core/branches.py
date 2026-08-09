from pathlib import Path
from typing import Optional

from .command_runner import git_allow_failure, run_git
from .contracts import RepositoryTarget
from .errors import GitCommandError, VersionControlError
from .status import collect_status


def create_and_switch(
    target: RepositoryTarget,
    name: str,
    start_point: str,
    upstream: Optional[str] = None,
) -> str:
    _require_clean(target.root)
    _validate_branch_name(target.root, name)
    if _branch_exists(target.root, name):
        raise VersionControlError("branch_name_conflict")
    args = ["switch", "-c", name]
    if upstream:
        args.extend(["--track", upstream])
    else:
        args.append(start_point)
    try:
        run_git(target.root, *args)
    except GitCommandError as exc:
        raise _branch_error(exc) from exc
    return name


def switch(target: RepositoryTarget, name: str) -> str:
    _require_clean(target.root)
    if not _branch_exists(target.root, name):
        raise VersionControlError("branch_not_found")
    if name in target.checked_out_branches and name != _current_branch(target.root):
        raise VersionControlError("branch_checked_out")
    try:
        run_git(target.root, "switch", name)
    except GitCommandError as exc:
        raise _branch_error(exc) from exc
    return name


def rename_local(target: RepositoryTarget, old_name: str, new_name: str) -> str:
    _validate_branch_name(target.root, new_name)
    if not _branch_exists(target.root, old_name):
        raise VersionControlError("branch_not_found")
    if _branch_exists(target.root, new_name):
        raise VersionControlError("branch_name_conflict")
    if old_name in target.checked_out_branches and old_name != _current_branch(target.root):
        raise VersionControlError("branch_checked_out")
    try:
        run_git(target.root, "branch", "-m", old_name, new_name)
    except GitCommandError as exc:
        raise _branch_error(exc) from exc
    git_allow_failure(target.root, "branch", "--unset-upstream", new_name)
    return new_name


def delete_local(target: RepositoryTarget, name: str) -> str:
    if not _branch_exists(target.root, name):
        raise VersionControlError("branch_not_found")
    if name == _current_branch(target.root):
        raise VersionControlError("branch_checked_out")
    if name in target.checked_out_branches:
        raise VersionControlError("branch_checked_out")
    protected = set(target.protected_branches)
    remote_default = _remote_default_branch(target.root)
    if remote_default:
        protected.add(remote_default)
    if name in protected:
        raise VersionControlError("branch_default_protected")
    result = git_allow_failure(target.root, "branch", "-d", name)
    if result.returncode != 0:
        message = f"{result.stdout}\n{result.stderr}".lower()
        if "not fully merged" in message:
            raise VersionControlError("branch_unmerged")
        raise VersionControlError("branch_not_found")
    return name


def publish(target: RepositoryTarget, remote: str, remote_name: Optional[str]) -> str:
    current = _current_branch(target.root)
    if not current:
        raise VersionControlError("branch_not_found")
    destination = remote_name or current
    _validate_branch_name(target.root, destination)
    if git_allow_failure(target.root, "remote", "get-url", remote).returncode != 0:
        raise VersionControlError("upstream_missing")
    result = git_allow_failure(
        target.root,
        "push",
        "--porcelain",
        "--set-upstream",
        remote,
        f"HEAD:refs/heads/{destination}",
        env=target.environment,
    )
    if result.returncode != 0:
        raise VersionControlError(
            "remote_history_incompatible", diagnostic=result.stderr.strip()
        )
    return f"{remote}/{destination}"


def _require_clean(repo_root: Path) -> None:
    status = collect_status(repo_root)
    if status.staged or status.unstaged or status.untracked or status.conflicts:
        raise VersionControlError("repository_dirty")


def _validate_branch_name(repo_root: Path, name: str) -> None:
    result = git_allow_failure(repo_root, "check-ref-format", "--branch", name)
    if result.returncode != 0:
        raise VersionControlError("branch_name_invalid")


def _branch_exists(repo_root: Path, name: str) -> bool:
    return (
        git_allow_failure(repo_root, "show-ref", "--verify", f"refs/heads/{name}").returncode
        == 0
    )


def _current_branch(repo_root: Path) -> Optional[str]:
    result = git_allow_failure(repo_root, "branch", "--show-current")
    return result.stdout.strip() or None


def _remote_default_branch(repo_root: Path) -> Optional[str]:
    result = git_allow_failure(
        repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"
    )
    prefix = "refs/remotes/origin/"
    value = result.stdout.strip()
    return value[len(prefix) :] if value.startswith(prefix) else None


def _branch_error(exc: GitCommandError) -> VersionControlError:
    message = f"{exc.stdout}\n{exc.stderr}".lower()
    if "already exists" in message:
        return VersionControlError("branch_name_conflict")
    if "invalid branch name" in message or "not a valid branch name" in message:
        return VersionControlError("branch_name_invalid")
    if "already used by worktree" in message or "already checked out" in message:
        return VersionControlError("branch_checked_out")
    return VersionControlError("branch_not_found", diagnostic=exc.stderr.strip())
