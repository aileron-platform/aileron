"""Git 狀態與分支操作

提供 Git 狀態查詢和分支管理功能。
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Optional, TYPE_CHECKING

from git import GitCommandError

from .models import (
    BranchCommitInfo,
    BranchInfo,
    BranchListResponse,
    CheckoutRequest,
    CheckoutResponse,
    VersionControlStatus,
)
from .utils import GitUtils, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class StatusOperations:
    """Git 狀態與分支操作

    提供狀態查詢、分支列表、分支切換等功能。
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
        """
        self._utils = utils
        self.cache = cache

    def get_status(self, workspace_id: str) -> VersionControlStatus:
        """取得 Git 狀態

        Args:
            workspace_id: 工作區 ID

        Returns:
            版本控制狀態
        """
        repo = self._utils.get_repo(workspace_id)
        branch, detached = self._utils.current_branch(repo)
        ahead, behind = self._utils.tracking_delta(repo)
        staged_entries = self._utils.diff_index(repo, staged=True)
        unstaged_entries = self._utils.diff_index(repo, staged=False)

        # 使用 git ls-files 命令替代 repo.untracked_files（效能優化 + 中文檔名支援）
        try:
            result_output = repo.git.execute(
                ["git", "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard"]
            )
            untracked_files = result_output.strip().split("\n") if result_output.strip() else []
        except GitCommandError as exc:
            logger.warning(f"Failed to get untracked files for workspace {workspace_id}: {exc}")
            untracked_files = []

        has_conflicts = bool(repo.index.unmerged_blobs())
        return VersionControlStatus(
            branch=branch,
            ahead=ahead,
            behind=behind,
            detached=detached,
            hasConflicts=has_conflicts,
            stagedCount=len(staged_entries),
            unstagedCount=len(unstaged_entries),
            untrackedCount=len(untracked_files),
            lastFetchedAt=self._utils.last_fetch_time(repo),
        )

    def list_branches(
        self, workspace_id: str, include_remote: bool = True, search: Optional[str] = None
    ) -> BranchListResponse:
        """列出分支

        Args:
            workspace_id: 工作區 ID
            include_remote: 是否包含遠端分支
            search: 搜尋關鍵字

        Returns:
            分支列表回應
        """
        repo = self._utils.get_repo(workspace_id)
        current_branch, detached = self._utils.current_branch(repo)
        query = search.lower() if search else None
        branches: list[BranchInfo] = []

        for branch in repo.branches:
            if query and query not in branch.name.lower():
                continue
            ahead, behind = 0, 0
            tracking = branch.tracking_branch()
            if tracking:
                try:
                    ahead = sum(1 for _ in repo.iter_commits(f"{tracking}..{branch}"))
                    behind = sum(1 for _ in repo.iter_commits(f"{branch}..{tracking}"))
                except GitCommandError:
                    ahead = behind = 0
            last_commit = None
            try:
                commit = branch.commit
                last_commit = BranchCommitInfo(
                    id=commit.hexsha,
                    message=commit.message.strip(),
                    author=commit.author.name,
                    email=getattr(commit.author, "email", None),
                    timestamp=commit.committed_datetime.replace(tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                )
            except ValueError:
                last_commit = None
            branches.append(
                BranchInfo(
                    name=branch.name,
                    displayName=branch.name,
                    isActive=(branch.name == current_branch and not detached),
                    isRemote=False,
                    ahead=ahead,
                    behind=behind,
                    lastCommit=last_commit,
                )
            )

        if include_remote:
            # 收集本地分支名稱，避免重複顯示
            local_branch_names = {b.name for b in branches}

            for remote in repo.remotes:
                for ref in remote.refs:
                    fullname = ref.name

                    # 跳過 HEAD 引用（如 origin/HEAD）
                    if ref.remote_head == "HEAD":
                        continue

                    # 如果遠端分支對應的本地分支已存在，跳過
                    if ref.remote_head in local_branch_names:
                        continue

                    if query and query not in fullname.lower():
                        continue

                    # 使用完整名稱作為 displayName，避免與本地分支混淆
                    branches.append(
                        BranchInfo(
                            name=fullname,
                            displayName=fullname,
                            isActive=False,
                            isRemote=True,
                            ahead=0,
                            behind=0,
                            lastCommit=None,
                        )
                    )

        return BranchListResponse(branches=branches)

    def checkout_branch(
        self, workspace_id: str, branch_name: str, payload: CheckoutRequest
    ) -> CheckoutResponse:
        """切換分支

        Args:
            workspace_id: 工作區 ID
            branch_name: 目標分支名稱
            payload: 切換請求

        Returns:
            切換回應

        Raises:
            VersionControlError: 切換失敗
        """
        repo = self._utils.get_repo(workspace_id)
        stashed = None

        if payload.stashChanges:
            try:
                stashed = repo.git.stash("push", "-u")
            except GitCommandError as exc:
                raise VersionControlError(str(exc), error_code="VC_STASH_FAILED") from exc

        try:
            if payload.create:
                args = ["-b", branch_name]
                if payload.startPoint:
                    args.append(payload.startPoint)
                repo.git.checkout(*args)
                created = True
            else:
                repo.git.checkout(branch_name)
                created = False
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_BRANCH_CHECKOUT_FAILED") from exc

        return CheckoutResponse(
            branch=branch_name,
            created=created,
            stashedChanges=stashed if stashed else None,
        )


__all__ = ["StatusOperations"]
