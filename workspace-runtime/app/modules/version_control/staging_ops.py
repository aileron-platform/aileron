"""Git changes and staging operations

Provides file change query and staging area management functionality.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from git import GitCommandError

from .cache import CacheKeys
from .models import (
    ChangesResponse,
    DiscardRequest,
    DiscardResponse,
    FileChange,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
)
from .snapshot import WorkingTreeSnapshotProvider
from .utils import DiffEntry, GitUtils, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

class StagingOperations:
    """Git changes and staging operations

    Provides functionality such as change query, stage, unstage, discard changes.
    """

    def __init__(
        self,
        utils: GitUtils,
        cache: Optional["GitCache"] = None,
        snapshot_provider: Optional[WorkingTreeSnapshotProvider] = None,
    ) -> None:
        """Initialize

        Args:
            utils: Git utility class instance
            cache: Cache layer (optional)
        """
        self._utils = utils
        self.cache = cache
        self._snapshot_provider = snapshot_provider or WorkingTreeSnapshotProvider(utils, cache)

    def get_changes(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 100,
        context_id: Optional[str] = None,
    ) -> ChangesResponse:
        """Get file changes (optimized version - with cache + use Git commands to avoid memory explosion)

        Args:
            workspace_id: Workspace ID
            page: Page number
            page_size: Items per page

        Returns:
            Changes response
        """
        snapshot = self._snapshot_provider.get_snapshot(workspace_id, page=page, page_size=page_size, context_id=context_id)

        result = ChangesResponse(
            staged=snapshot.staged,
            unstaged=snapshot.unstaged,
            untracked=snapshot.untracked,
            untrackedTotal=snapshot.untrackedTotal,
            untrackedPage=snapshot.untrackedPage,
            untrackedPageSize=snapshot.untrackedPageSize,
            untrackedHasMore=snapshot.untrackedHasMore,
        )
        return result

    def stage(self, workspace_id: str, payload: StageRequest, context_id: Optional[str] = None) -> StageResponse:
        """Stage files (optimized version - invalidate cache)

        Args:
            workspace_id: Workspace ID
            payload: Stage request

        Returns:
            Stage response

        Raises:
            VersionControlError: Stage failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        normalized = self._utils.normalize_paths(repo, payload.paths)
        try:
            repo.index.add(normalized, write=True)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_STAGE_FAILED") from exc

        # Invalidate cache
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)

        staged = [entry.path for entry in self._utils.diff_index(repo, staged=True)]
        unstaged = [entry.path for entry in self._utils.diff_index(repo, staged=False)]
        return StageResponse(staged=staged, unstaged=unstaged)

    def unstage(self, workspace_id: str, payload: UnstageRequest, context_id: Optional[str] = None) -> UnstageResponse:
        """Unstage files (optimized version - batch processing + invalidate cache)

        Args:
            workspace_id: Workspace ID
            payload: Unstage request

        Returns:
            Unstage response

        Raises:
            VersionControlError: Unstage failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        normalized = self._utils.normalize_paths(repo, payload.paths)

        # Optimization: batch processing, single Git command
        try:
            if self._utils.has_head(repo):
                # Process all files at once
                repo.git.reset("HEAD", "--", *normalized)
            else:
                # Batch remove
                repo.index.remove(normalized, working_tree=False)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_UNSTAGE_FAILED") from exc

        # Invalidate cache
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)

        remaining = len(self._utils.diff_index(repo, staged=True))
        return UnstageResponse(unstaged=normalized, remainingStaged=remaining)

    def discard(self, workspace_id: str, payload: DiscardRequest, context_id: Optional[str] = None) -> DiscardResponse:
        """Discard changes

        Args:
            workspace_id: Workspace ID
            payload: Discard request

        Returns:
            Discard response
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        worktree = Path(repo.working_tree_dir or ".")
        normalized = self._utils.normalize_paths(repo, payload.paths)
        discarded: list[str] = []

        for path in normalized:
            target = worktree / path
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                discarded.append(path)
            else:
                try:
                    repo.git.checkout("--", path)
                    discarded.append(path)
                except GitCommandError:
                    continue

        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)

        return DiscardResponse(discarded=discarded, warnings=[])

    def _to_file_change(self, entry: DiffEntry) -> FileChange:
        """Convert DiffEntry to FileChange

        Args:
            entry: DiffEntry object

        Returns:
            FileChange object
        """
        return FileChange(
            name=Path(entry.path).name,
            path=entry.path.replace("\\", "/"),
            status=entry.status,
            type=self._utils.map_change_type(entry.status),
            additions=entry.additions,
            deletions=entry.deletions,
            diff=entry.patch,
        )


__all__ = ["StagingOperations"]
