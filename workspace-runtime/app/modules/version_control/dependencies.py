"""Version control module dependency injection"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .cache import create_git_cache
from .service import GitService
from .worktree_config import get_worktree_subdir


MOCK_GIT_ROOT = Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
WORKSPACE_ROOT = Path("/workspace")


@lru_cache()
def get_git_service() -> GitService:
    """Get Git version control service instance (optimized version - with Redis cache)"""

    # Use environment variable to determine whether to use actual workspace path
    if os.getenv("NODE_ENV") == "development" or os.path.exists("/workspace"):
        base_path = WORKSPACE_ROOT
    else:
        base_path = MOCK_GIT_ROOT

    # Create Redis cache (must be enabled)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_flag = os.getenv("GIT_CACHE_ENABLED")
    if cache_flag and cache_flag.lower() != "true":
        raise RuntimeError("Git version control requires Redis cache, please set GIT_CACHE_ENABLED to true")

    cache = create_git_cache(redis_url=redis_url, enabled=True)

    return GitService(base_path=base_path, cache=cache, worktree_subdir=get_worktree_subdir())


__all__ = ["get_git_service", "MOCK_GIT_ROOT"]
