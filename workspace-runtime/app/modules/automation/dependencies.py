"""Dependency providers for Runtime Automation services."""

from functools import lru_cache

from app.config.settings import get_settings
from app.modules.version_control.dependencies import get_git_service

from .worktree import AutomationWorktreeService


@lru_cache()
def get_automation_worktree_service() -> AutomationWorktreeService:
    """Return the process-wide job-owned worktree service."""
    settings = get_settings()
    return AutomationWorktreeService(
        git_service=get_git_service(),
        workspace_id=settings.AILERON_WORKSPACE_ID,
        disk_threshold=settings.DISK_THRESHOLD,
    )


__all__ = ["get_automation_worktree_service"]
