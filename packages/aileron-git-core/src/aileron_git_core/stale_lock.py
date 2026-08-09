"""Stale git lock detection and recovery primitives."""

import subprocess
import time
from pathlib import Path
from typing import Callable, List, TypeVar

from .command_runner import GitCommandError
from .errors import GitStaleLockError

T = TypeVar("T")

DEFAULT_STALE_THRESHOLD_SECONDS = 35

# index.lock is cleared in the auto path; the rest only on force=True.
AUTO_CLEARABLE = ("index.lock",)
GIT_LOCK_FILES = ("index.lock", "HEAD.lock", "config.lock")


def detect_stale_locks(repo_root: Path, threshold_seconds: int) -> List[Path]:
    """Return git lock files whose mtime is older than ``threshold_seconds``."""
    git_dir = _git_dir(repo_root)
    if not git_dir.exists():
        return []
    now = time.time()
    stale: List[Path] = []
    for name in GIT_LOCK_FILES:
        lock = git_dir / name
        if lock.exists() and (now - lock.stat().st_mtime) >= threshold_seconds:
            stale.append(lock)
    return stale


def has_live_git_process(repo_root: Path) -> bool:
    """Best-effort: True if a live ``git`` process is operating on ``repo_root``.

    Scoped to processes whose command line contains the resolved
    ``repo_root`` (so unrelated git processes elsewhere do not block
    auto-clear). Resolved against the host process table; only meaningful
    when the user-runnable git shares the service's container
    (workspace-runtime). **Auto-clear does NOT cover git runs from a
    browser-desktop terminal or any process outside the service's
    container** — those are invisible to ``pgrep`` here; the manual
    force-unlock is the fallback for that case. Fail-safe: on any
    inspection error, return True (never auto-clear).
    """
    try:
        target = str(repo_root.resolve())
        completed = subprocess.run(
            ["pgrep", "-f", target],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if completed.returncode != 0:
            return False
        # Confirm the matched process is actually git (pgrep -f <root> could
        # match a non-git process whose args happen to contain the path).
        out = completed.stdout.strip()
        if not out:
            return False
        for pid in out.splitlines():
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
            if "git" in cmdline and target in cmdline:
                return True
        return False
    except Exception:
        return True


def clear_locks(
    repo_root: Path,
    *,
    force: bool = False,
    threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> List[Path]:
    """Remove git lock files.

    force=False: clear only ``index.lock`` and only when it is stale
    (age >= threshold) and no live git process is running. Fail-safe: if
    process state cannot be verified, treat as live and do not clear.
    force=True: clear index.lock, HEAD.lock, config.lock unconditionally.
    Returns the paths actually removed.
    """
    git_dir = _git_dir(repo_root)
    cleared: List[Path] = []
    if force:
        for name in GIT_LOCK_FILES:
            lock = git_dir / name
            if lock.exists():
                lock.unlink()
                cleared.append(lock)
        return cleared

    if has_live_git_process(repo_root):
        return cleared
    stale = detect_stale_locks(repo_root, threshold_seconds)
    for lock in stale:
        if lock.name in AUTO_CLEARABLE:
            lock.unlink()
            cleared.append(lock)
    return cleared


def _git_dir(repo_root: Path) -> Path:
    # repo_root may itself be a worktree whose .git is a file pointing elsewhere;
    # for lock recovery the on-disk index.lock lives under the worktree's resolved
    # git dir. Resolve the common case (.git is a directory) and fall back.
    dot_git = repo_root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        # gitdir pointer file: "gitdir: /path/.git/worktrees/<name>"
        try:
            text = dot_git.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                resolved = Path(text.split(":", 1)[1].strip())
                return resolved
        except Exception:
            pass
    return dot_git


_LOCK_SIGNATURES = ("index.lock", "another git process")


def _is_lock_signature(exc: GitCommandError) -> bool:
    blob = "\n".join((str(exc), exc.stdout or "", exc.stderr or "")).lower()
    return any(sig in blob for sig in _LOCK_SIGNATURES)


def with_stale_lock_recovery(
    repo_root: Path,
    callback: Callable[[], T],
    *,
    threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> T:
    """Run a mutating callback; recover once from a stale on-disk git lock.

    On a lock-signature GitCommandError, attempt clear_locks(force=False)
    and retry the callback once. If it still fails (or the lock could not
    be cleared safely), raise GitStaleLockError. Non-lock errors propagate.
    """
    try:
        return callback()
    except GitCommandError as exc:
        if not _is_lock_signature(exc):
            raise
        clear_locks(repo_root, force=False, threshold_seconds=threshold_seconds)
        try:
            return callback()
        except GitCommandError as retry_exc:
            if _is_lock_signature(retry_exc):
                raise GitStaleLockError(str(repo_root)) from retry_exc
            raise
