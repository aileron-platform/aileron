"""Worktree directory configuration shared by runtime request handlers."""

from __future__ import annotations

DEFAULT_WORKTREE_SUBDIR = ".worktrees"
WORKTREE_SUBDIR_MAX_LENGTH = 64

_worktree_subdir = DEFAULT_WORKTREE_SUBDIR


def validate_worktree_subdir(subdir: str) -> str:
    """Validate and normalize the configured worktree relative path."""
    normalized = (subdir or "").strip()
    segments = normalized.split("/")
    if (
        not normalized
        or normalized == "."
        or normalized.startswith("/")
        or normalized.endswith("/")
        or "\\" in normalized
        or any(not segment for segment in segments)
        or any(segment in {".", ".."} for segment in segments)
        or len(normalized) > WORKTREE_SUBDIR_MAX_LENGTH
    ):
        raise ValueError("WORKTREE_SUBDIR_INVALID")
    return normalized


def get_worktree_subdir() -> str:
    """Return the current cached worktree subdirectory."""
    return _worktree_subdir


def set_worktree_subdir(subdir: str) -> str:
    """Update the cached worktree subdirectory."""
    global _worktree_subdir
    _worktree_subdir = validate_worktree_subdir(subdir)
    return _worktree_subdir


__all__ = [
    "DEFAULT_WORKTREE_SUBDIR",
    "get_worktree_subdir",
    "set_worktree_subdir",
    "validate_worktree_subdir",
]
