"""Shared Git working-tree snapshot helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from git import GitCommandError
from pydantic import BaseModel, Field

from .cache import CacheKeys, CacheTTL
from .models import FileChange
from .utils import DiffEntry, GitUtils, MAX_UNTRACKED_FILES

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class WorkingTreeSnapshot(BaseModel):
    """Internal read model shared by status and changes responses."""

    branch: str
    ahead: int = 0
    behind: int = 0
    detached: bool = False
    hasConflicts: bool = False
    staged: list[FileChange] = Field(default_factory=list)
    unstaged: list[FileChange] = Field(default_factory=list)
    untracked: list[FileChange] = Field(default_factory=list)
    untrackedTotal: int = 0
    untrackedPage: int = 1
    untrackedPageSize: int = 100
    untrackedHasMore: bool = False
    lastFetchedAt: Optional[str] = None


class WorkingTreeSnapshotProvider:
    """Build and cache shared working-tree snapshots."""

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        self._utils = utils
        self.cache = cache

    def get_snapshot(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 100,
        context_id: Optional[str] = None,
    ) -> WorkingTreeSnapshot:
        """Return a snapshot for status/changes reads."""

        if self.cache:
            cached = self.cache.get(
                workspace_id,
                CacheKeys.WORKING_TREE_SNAPSHOT,
                page=page,
                page_size=page_size,
                context_id=context_id,
            )
            if cached:
                return WorkingTreeSnapshot(**cached)

        repo = self._utils.get_repo(workspace_id, context_id)
        branch, detached = self._utils.current_branch(repo)
        ahead, behind = self._utils.tracking_delta(repo)
        staged_entries = self._utils.diff_index(repo, staged=True)
        unstaged_entries = self._utils.diff_index(repo, staged=False)
        untracked_files = self._list_untracked_files(repo, workspace_id)

        if len(untracked_files) > MAX_UNTRACKED_FILES:
            logger.warning(
                "Workspace %s has %s untracked files, limiting to %s for performance",
                workspace_id,
                len(untracked_files),
                MAX_UNTRACKED_FILES,
            )
            untracked_files = untracked_files[:MAX_UNTRACKED_FILES]

        total_untracked = len(untracked_files)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_files = untracked_files[start_idx:end_idx]
        worktree = Path(repo.working_tree_dir or ".")

        untracked_changes: list[FileChange] = []
        for rel_path in page_files:
            file_path = worktree / rel_path
            if file_path.is_dir():
                continue
            untracked_changes.append(
                FileChange(
                    name=file_path.name,
                    path=rel_path.replace("\\", "/"),
                    status="?",
                    type="untracked",
                    additions=0,
                    deletions=0,
                    diff=None,
                )
            )

        snapshot = WorkingTreeSnapshot(
            branch=branch,
            ahead=ahead,
            behind=behind,
            detached=detached,
            hasConflicts=bool(repo.index.unmerged_blobs()),
            staged=[self._to_file_change(entry) for entry in staged_entries],
            unstaged=[self._to_file_change(entry) for entry in unstaged_entries],
            untracked=untracked_changes,
            untrackedTotal=total_untracked,
            untrackedPage=page,
            untrackedPageSize=page_size,
            untrackedHasMore=end_idx < total_untracked,
            lastFetchedAt=self._utils.last_fetch_time(repo),
        )

        if self.cache:
            self.cache.set(
                workspace_id,
                CacheKeys.WORKING_TREE_SNAPSHOT,
                snapshot.model_dump(),
                ttl=CacheTTL.VERY_SHORT,
                page=page,
                page_size=page_size,
                context_id=context_id,
            )

        return snapshot

    @staticmethod
    def _list_untracked_files(repo, workspace_id: str) -> list[str]:
        try:
            result_output = repo.git.execute(
                ["git", "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard"]
            )
            return result_output.strip().split("\n") if result_output.strip() else []
        except GitCommandError as exc:
            logger.warning("Failed to get untracked files for workspace %s: %s", workspace_id, exc)
            return []

    def _to_file_change(self, entry: DiffEntry) -> FileChange:
        return FileChange(
            name=Path(entry.path).name,
            path=entry.path.replace("\\", "/"),
            status=entry.status,
            type=self._utils.map_change_type(entry.status),
            additions=entry.additions,
            deletions=entry.deletions,
            diff=entry.patch,
        )


__all__ = ["WorkingTreeSnapshot", "WorkingTreeSnapshotProvider"]
