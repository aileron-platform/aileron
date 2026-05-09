"""Git remote operations

Provides Git remote repository push, pull, fetch and other operations.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from git import GitCommandError

from .models import (
    FetchRequest,
    FetchResponse,
    PullCommitInfo,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    PushUpdate,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
)
from .utils import GitUtils, VersionControlError
from .cache import CacheKeys

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class RemoteOperations:
    """Git remote operations

    Provides remote repository operations such as push, pull, fetch.
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """Initialize

        Args:
            utils: Git utility class instance
            cache: Cache layer (optional)
        """
        self._utils = utils
        self.cache = cache

    def push(self, workspace_id: str, payload: PushRequest, context_id: Optional[str] = None) -> PushResponse:
        """Push to remote

        Args:
            workspace_id: Workspace ID
            payload: Push request

        Returns:
            Push response

        Raises:
            VersionControlError: Push failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        branch, _ = self._utils.current_branch(repo)
        target_branch = payload.branch or branch
        self._utils.ensure_remote(repo, payload.remote)
        remote = repo.remote(payload.remote)

        try:
            results = remote.push(target_branch, force=payload.force)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_PUSH_FAILED") from exc

        updates: list[PushUpdate] = []
        for info in results:
            status = "ok"
            if info.flags & info.ERROR:
                status = "error"
            elif info.flags & info.REJECTED:
                status = "rejected"
            updates.append(
                PushUpdate(
                    ref=info.remote_ref_path or target_branch,
                    status=status,
                )
            )
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)
            self.cache.invalidate(workspace_id, CacheKeys.BRANCHES)
        return PushResponse(remote=payload.remote, branch=target_branch, updates=updates)

    def pull(self, workspace_id: str, payload: PullRequest, context_id: Optional[str] = None) -> PullResponse:
        """Pull from remote

        Args:
            workspace_id: Workspace ID
            payload: Pull request

        Returns:
            Pull response

        Raises:
            VersionControlError: Pull failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        branch, _ = self._utils.current_branch(repo)
        target_branch = payload.branch or branch
        self._utils.ensure_remote(repo, payload.remote)
        remote = repo.remote(payload.remote)
        old_head = repo.head.commit.hexsha if self._utils.has_head(repo) else None

        try:
            args = [target_branch]
            kwargs = {}
            if payload.rebase:
                kwargs["rebase"] = True
            if payload.autostash:
                kwargs["autostash"] = True
            remote.pull(*args, **kwargs)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_PULL_FAILED") from exc

        new_head = repo.head.commit.hexsha if self._utils.has_head(repo) else None
        commits: list[PullCommitInfo] = []
        fast_forward = False

        if old_head and new_head and old_head != new_head:
            for commit in repo.iter_commits(f"{old_head}..{new_head}"):
                commits.append(
                    PullCommitInfo(
                        id=commit.hexsha,
                        message=commit.message.strip(),
                        author=commit.author.name,
                    )
                )
            try:
                fast_forward = repo.commit(new_head).parents and repo.commit(new_head).parents[0].hexsha == old_head
            except (ValueError, GitCommandError):
                fast_forward = False

        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)
            self.cache.invalidate(workspace_id, CacheKeys.BRANCHES)
            self.cache.invalidate(workspace_id, CacheKeys.COMMITS)

        return PullResponse(
            remote=payload.remote,
            branch=target_branch,
            fastForward=fast_forward,
            commits=list(reversed(commits)),
        )

    def fetch(self, workspace_id: str, payload: FetchRequest, context_id: Optional[str] = None) -> FetchResponse:
        """Fetch updates from remote

        Args:
            workspace_id: Workspace ID
            payload: Fetch request

        Returns:
            Fetch response

        Raises:
            VersionControlError: Fetch failed
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        self._utils.ensure_remote(repo, payload.remote)
        remote = repo.remote(payload.remote)

        try:
            results = remote.fetch(prune=payload.prune)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_FETCH_FAILED") from exc

        refs = [info.name for info in results if info.name]
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)
            self.cache.invalidate(workspace_id, CacheKeys.BRANCHES)
        return FetchResponse(remote=payload.remote, fetchedRefs=refs)

    def get_settings(self, workspace_id: str, context_id: Optional[str] = None) -> RemoteSettingsResponse:
        """Read origin remote settings."""
        repo = self._utils.get_repo(workspace_id, context_id)
        branch, _ = self._utils.current_branch(repo)
        remote_url = self._origin_url(repo)

        return RemoteSettingsResponse(
            isInitialized=True,
            currentBranch=branch,
            remoteUrl=remote_url,
            hasOrigin=bool(remote_url),
        )

    def set_settings(
        self,
        workspace_id: str,
        payload: RemoteSettingsRequest,
        context_id: Optional[str] = None,
    ) -> RemoteSettingsResponse:
        """Create or update origin remote settings."""
        repo = self._utils.get_repo(workspace_id, context_id)
        remote_url = payload.remote_url.strip()
        if not remote_url:
            raise VersionControlError(
                "Remote URL is required",
                status_code=400,
                error_code="VC_REMOTE_URL_REQUIRED",
            )

        if "origin" in {remote.name for remote in repo.remotes}:
            repo.git.remote("set-url", "origin", remote_url)
        else:
            repo.create_remote("origin", remote_url)

        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)
            self.cache.invalidate(workspace_id, CacheKeys.BRANCHES)

        return self.get_settings(workspace_id, context_id)

    @staticmethod
    def _origin_url(repo) -> Optional[str]:
        if "origin" not in {remote.name for remote in repo.remotes}:
            return None

        urls = list(repo.remote("origin").urls)
        return urls[0] if urls else None


__all__ = ["RemoteOperations"]
