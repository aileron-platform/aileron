"""Version control module dependency injection"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config.settings import get_settings

from .cache import GitCache, GitCacheInvalidator, create_git_cache
from .git_operations import GitService
from .worktree_config import get_worktree_subdir
from .working_tree_operations import WorkingTreeOperations


MOCK_GIT_ROOT = Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
WORKSPACE_ROOT = Path("/workspace")


@lru_cache()
def get_git_cache() -> GitCache:
    """Get Git cache instance."""

    return create_git_cache()


@lru_cache()
def get_git_cache_invalidator() -> GitCacheInvalidator:
    """Get Git cache invalidator instance."""

    return GitCacheInvalidator(get_git_cache())


@lru_cache()
def get_working_tree_operations() -> WorkingTreeOperations:
    return WorkingTreeOperations.create(get_git_cache_invalidator())


@lru_cache()
def get_git_service() -> GitService:
    """Get the Git version control service instance."""

    if get_settings().is_development or WORKSPACE_ROOT.exists():
        base_path = WORKSPACE_ROOT
    else:
        base_path = MOCK_GIT_ROOT

    cache = get_git_cache()
    from app.modules.file_system.dependencies import get_workspace_local_history

    return GitService(
        base_path=base_path,
        cache=cache,
        worktree_subdir=get_worktree_subdir(),
        working_tree_operations=get_working_tree_operations(),
        local_history=get_workspace_local_history(),
    )


__all__ = [
    "get_git_service",
    "get_git_cache",
    "get_git_cache_invalidator",
    "get_working_tree_operations",
    "MOCK_GIT_ROOT",
]
