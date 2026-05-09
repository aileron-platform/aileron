"""Git version control service

Provides unified interface for Git version control operations (Facade pattern).

This service integrates the following operation modules:
- StatusOperations: Status and branch operations
- StagingOperations: Changes and staging operations
- CommitOperations: Commit and history operations
- RemoteOperations: Remote repository operations
- DiffOperations: Diff and content operations
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .cache import GitCache
from .commit_ops import CommitOperations
from .diff_ops import DiffOperations
from .models import (
    BlobResponse,
    BranchListResponse,
    ChangesResponse,
    CheckoutRequest,
    CheckoutResponse,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FetchRequest,
    FetchResponse,
    GitContextListResponse,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlStatus,
)
from .remote_ops import RemoteOperations
from .snapshot import WorkingTreeSnapshotProvider
from .staging_ops import StagingOperations
from .status_ops import StatusOperations
from .utils import GitUtils, VersionControlError

logger = logging.getLogger(__name__)


class GitService:
    """Git version control service (Facade)

    Provides unified interface for Git operations, delegates to specialized operation classes.

    Performance optimizations:
    - Redis cache layer reduces redundant computation
    - Batch operation optimization
    - Optimized diff computation
    - Fast total count calculation
    """

    def __init__(
        self,
        base_path: Optional[Path | str] = None,
        cache: Optional[GitCache] = None,
        worktree_subdir: str = ".worktrees",
    ) -> None:
        """Initialize Git service

        Args:
            base_path: Workspace root directory
            cache: Cache layer (optional)
        """
        root = Path(base_path) if base_path else Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
        self._root_path = root.resolve()
        self._root_path.mkdir(parents=True, exist_ok=True)
        self.cache = cache

        # Initialize utility class
        self._utils = GitUtils(self._root_path, cache, worktree_subdir=worktree_subdir)
        self._snapshot_provider = WorkingTreeSnapshotProvider(self._utils, cache)

        # Initialize operation classes
        self._status_ops = StatusOperations(self._utils, cache, self._snapshot_provider)
        self._staging_ops = StagingOperations(self._utils, cache, self._snapshot_provider)
        self._commit_ops = CommitOperations(self._utils, cache)
        self._remote_ops = RemoteOperations(self._utils, cache)
        self._diff_ops = DiffOperations(self._utils, cache)

    # ------------------------------------------------------------------
    # Compatibility wrapper
    # ------------------------------------------------------------------
    def _workspace_path(self, workspace_id: str) -> Path:
        """Backward compatibility: Get workspace path."""
        return self._utils.workspace_path(workspace_id)

    def _repo(self, workspace_id: str):
        """Backward compatibility: Get Git repo."""
        return self._utils.get_repo(workspace_id)

    def _has_head(self, repo) -> bool:
        """Backward compatibility: Check if repo has HEAD."""
        return self._utils.has_head(repo)

    def _current_branch(self, repo) -> tuple[str, bool]:
        """Backward compatibility: Get current branch."""
        return self._utils.current_branch(repo)

    def _tracking_delta(self, repo) -> tuple[int, int]:
        """Backward compatibility: Get tracking branch ahead/behind."""
        return self._utils.tracking_delta(repo)

    def _should_ignore_file(self, file_path: str) -> bool:
        """Backward compatibility: Determine if file should be ignored."""
        return self._utils.should_ignore_file(file_path)

    def _normalize_paths(self, repo, paths):
        """Backward compatibility: Normalize path list."""
        return self._utils.normalize_paths(repo, paths)

    def _map_change_type(self, change_type: str) -> str:
        """Backward compatibility: Map change type."""
        return self._utils.map_change_type(change_type)

    # ------------------------------------------------------------------
    # Status and branch operations
    # ------------------------------------------------------------------
    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        """List available Git contexts for a workspace."""
        return self._utils.list_contexts(workspace_id)

    def set_worktree_subdir(self, worktree_subdir: str) -> None:
        """Update the managed worktree subdirectory."""
        self._utils.set_worktree_subdir(worktree_subdir)

    def invalidate_context_path_cache(self, workspace_id: Optional[str] = None) -> None:
        """Invalidate cached Git context path resolutions."""
        self._utils.invalidate_context_path_cache(workspace_id)

    def get_status(self, workspace_id: str, context_id: Optional[str] = None) -> VersionControlStatus:
        """Get Git status

        Args:
            workspace_id: Workspace ID

        Returns:
            Version control status
        """
        return self._status_ops.get_status(workspace_id, context_id)

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = True,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
        include_metadata: bool = True,
    ) -> BranchListResponse:
        """List branches

        Args:
            workspace_id: Workspace ID
            include_remote: Whether to include remote branches
            search: Search keyword

        Returns:
            Branch list response
        """
        return self._status_ops.list_branches(workspace_id, include_remote, search, context_id, include_metadata)

    def checkout_branch(
        self,
        workspace_id: str,
        branch_name: str,
        payload: CheckoutRequest,
        context_id: Optional[str] = None,
    ) -> CheckoutResponse:
        """Checkout branch

        Args:
            workspace_id: Workspace ID
            branch_name: Target branch name
            payload: Checkout request

        Returns:
            Checkout response
        """
        return self._status_ops.checkout_branch(workspace_id, branch_name, payload, context_id)

    # ------------------------------------------------------------------
    # Changes and staging operations
    # ------------------------------------------------------------------
    def get_changes(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 100,
        context_id: Optional[str] = None,
    ) -> ChangesResponse:
        """Get file changes

        Args:
            workspace_id: Workspace ID
            page: Page number
            page_size: Items per page

        Returns:
            Changes response
        """
        return self._staging_ops.get_changes(workspace_id, page, page_size, context_id)

    def stage(self, workspace_id: str, payload: StageRequest, context_id: Optional[str] = None) -> StageResponse:
        """Stage files

        Args:
            workspace_id: Workspace ID
            payload: Stage request

        Returns:
            Stage response
        """
        return self._staging_ops.stage(workspace_id, payload, context_id)

    def unstage(self, workspace_id: str, payload: UnstageRequest, context_id: Optional[str] = None) -> UnstageResponse:
        """Unstage files

        Args:
            workspace_id: Workspace ID
            payload: Unstage request

        Returns:
            Unstage response
        """
        return self._staging_ops.unstage(workspace_id, payload, context_id)

    def discard(self, workspace_id: str, payload: DiscardRequest, context_id: Optional[str] = None) -> DiscardResponse:
        """Discard changes

        Args:
            workspace_id: Workspace ID
            payload: Discard request

        Returns:
            Discard response
        """
        return self._staging_ops.discard(workspace_id, payload, context_id)

    # ------------------------------------------------------------------
    # Commit and history operations
    # ------------------------------------------------------------------
    def commit(self, workspace_id: str, payload: CommitRequest, context_id: Optional[str] = None) -> CommitResponse:
        """Create commit

        Args:
            workspace_id: Workspace ID
            payload: Commit request

        Returns:
            Commit response
        """
        return self._commit_ops.commit(workspace_id, payload, context_id)

    def list_commits(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 20,
        branch: Optional[str] = None,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> CommitListResponse:
        """List commit history

        Args:
            workspace_id: Workspace ID
            page: Page number
            page_size: Items per page
            branch: Branch name
            search: Search keyword

        Returns:
            Commit list response
        """
        return self._commit_ops.list_commits(workspace_id, page, page_size, branch, search, context_id)

    def get_commit(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitDetailResponse:
        """Get commit details

        Args:
            workspace_id: Workspace ID
            commit_id: Commit ID

        Returns:
            Commit detail response
        """
        return self._commit_ops.get_commit(workspace_id, commit_id, context_id)

    def get_commit_files(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitFilesResponse:
        """Get commit file list

        Args:
            workspace_id: Workspace ID
            commit_id: Commit ID

        Returns:
            Commit file response
        """
        return self._commit_ops.get_commit_files(workspace_id, commit_id, context_id)

    # ------------------------------------------------------------------
    # Remote operations
    # ------------------------------------------------------------------
    def push(self, workspace_id: str, payload: PushRequest, context_id: Optional[str] = None) -> PushResponse:
        """Push to remote

        Args:
            workspace_id: Workspace ID
            payload: Push request

        Returns:
            Push response
        """
        return self._remote_ops.push(workspace_id, payload, context_id)

    def pull(self, workspace_id: str, payload: PullRequest, context_id: Optional[str] = None) -> PullResponse:
        """Pull from remote

        Args:
            workspace_id: Workspace ID
            payload: Pull request

        Returns:
            Pull response
        """
        return self._remote_ops.pull(workspace_id, payload, context_id)

    def fetch(self, workspace_id: str, payload: FetchRequest, context_id: Optional[str] = None) -> FetchResponse:
        """Fetch updates from remote

        Args:
            workspace_id: Workspace ID
            payload: Fetch request

        Returns:
            Fetch response
        """
        return self._remote_ops.fetch(workspace_id, payload, context_id)

    def get_remote_settings(self, workspace_id: str, context_id: Optional[str] = None) -> RemoteSettingsResponse:
        """Get repository remote settings."""
        return self._remote_ops.get_settings(workspace_id, context_id)

    def set_remote_settings(
        self,
        workspace_id: str,
        payload: RemoteSettingsRequest,
        context_id: Optional[str] = None,
    ) -> RemoteSettingsResponse:
        """Set repository remote settings."""
        return self._remote_ops.set_settings(workspace_id, payload, context_id)

    # ------------------------------------------------------------------
    # Diff and content operations
    # ------------------------------------------------------------------
    def diff(
        self,
        workspace_id: str,
        path: str,
        base: Optional[str] = None,
        head: Optional[str] = None,
        context: int = 3,
        include_metadata: bool = False,
        context_id: Optional[str] = None,
    ) -> DiffResponse:
        """Get file diff content

        Args:
            workspace_id: Workspace ID
            path: File path
            base: Comparison base
            head: Comparison target
            context: Context line count
            include_metadata: Whether to include file metadata

        Returns:
            Diff response
        """
        return self._diff_ops.diff(workspace_id, path, base, head, context, include_metadata, context_id)

    def blob(
        self,
        workspace_id: str,
        path: str,
        revision: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BlobResponse:
        """Get file content

        Args:
            workspace_id: Workspace ID
            path: File path
            revision: Version

        Returns:
            Blob response
        """
        return self._diff_ops.blob(workspace_id, path, revision, context_id)


__all__ = ["GitService", "VersionControlError"]
