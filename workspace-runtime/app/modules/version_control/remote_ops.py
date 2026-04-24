"""Git 遠端操作

提供 Git 遠端倉庫的 push、pull、fetch 等操作。
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
)
from .utils import GitUtils, VersionControlError
from .cache import CacheKeys

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class RemoteOperations:
    """Git 遠端操作

    提供 push、pull、fetch 等遠端倉庫操作。
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
        """
        self._utils = utils
        self.cache = cache

    def push(self, workspace_id: str, payload: PushRequest, context_id: Optional[str] = None) -> PushResponse:
        """推送到遠端

        Args:
            workspace_id: 工作區 ID
            payload: 推送請求

        Returns:
            推送回應

        Raises:
            VersionControlError: 推送失敗
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
        """從遠端拉取

        Args:
            workspace_id: 工作區 ID
            payload: 拉取請求

        Returns:
            拉取回應

        Raises:
            VersionControlError: 拉取失敗
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
        """從遠端取得更新

        Args:
            workspace_id: 工作區 ID
            payload: Fetch 請求

        Returns:
            Fetch 回應

        Raises:
            VersionControlError: Fetch 失敗
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


__all__ = ["RemoteOperations"]
