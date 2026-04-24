"""Git 變更與暫存操作

提供檔案變更查詢和暫存區管理功能。
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
    """Git 變更與暫存操作

    提供變更查詢、暫存、取消暫存、放棄變更等功能。
    """

    def __init__(
        self,
        utils: GitUtils,
        cache: Optional["GitCache"] = None,
        snapshot_provider: Optional[WorkingTreeSnapshotProvider] = None,
    ) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
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
        """取得檔案變更（優化版 - 支援快取 + 使用 Git 命令避免記憶體爆炸）

        Args:
            workspace_id: 工作區 ID
            page: 頁碼
            page_size: 每頁大小

        Returns:
            變更回應
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
        """暫存檔案（優化版 - 使快取失效）

        Args:
            workspace_id: 工作區 ID
            payload: 暫存請求

        Returns:
            暫存回應

        Raises:
            VersionControlError: 暫存失敗
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        normalized = self._utils.normalize_paths(repo, payload.paths)
        try:
            repo.index.add(normalized, write=True)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_STAGE_FAILED") from exc

        # 使快取失效
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)

        staged = [entry.path for entry in self._utils.diff_index(repo, staged=True)]
        unstaged = [entry.path for entry in self._utils.diff_index(repo, staged=False)]
        return StageResponse(staged=staged, unstaged=unstaged)

    def unstage(self, workspace_id: str, payload: UnstageRequest, context_id: Optional[str] = None) -> UnstageResponse:
        """取消暫存檔案（優化版 - 批次處理 + 使快取失效）

        Args:
            workspace_id: 工作區 ID
            payload: 取消暫存請求

        Returns:
            取消暫存回應

        Raises:
            VersionControlError: 取消暫存失敗
        """
        repo = self._utils.get_repo(workspace_id, context_id)
        normalized = self._utils.normalize_paths(repo, payload.paths)

        # 優化：批次處理，一次 Git 命令
        try:
            if self._utils.has_head(repo):
                # 一次處理所有檔案
                repo.git.reset("HEAD", "--", *normalized)
            else:
                # 批次移除
                repo.index.remove(normalized, working_tree=False)
        except GitCommandError as exc:
            raise VersionControlError(str(exc), error_code="VC_UNSTAGE_FAILED") from exc

        # 使快取失效
        if self.cache:
            self.cache.invalidate(workspace_id, CacheKeys.CHANGES)
            self.cache.invalidate(workspace_id, CacheKeys.STATUS)
            self.cache.invalidate(workspace_id, CacheKeys.WORKING_TREE_SNAPSHOT)

        remaining = len(self._utils.diff_index(repo, staged=True))
        return UnstageResponse(unstaged=normalized, remainingStaged=remaining)

    def discard(self, workspace_id: str, payload: DiscardRequest, context_id: Optional[str] = None) -> DiscardResponse:
        """放棄變更

        Args:
            workspace_id: 工作區 ID
            payload: 放棄請求

        Returns:
            放棄回應
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
        """將 DiffEntry 轉換為 FileChange

        Args:
            entry: DiffEntry 物件

        Returns:
            FileChange 物件
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
