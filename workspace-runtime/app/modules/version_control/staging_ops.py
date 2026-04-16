"""Git 變更與暫存操作

提供檔案變更查詢和暫存區管理功能。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from git import GitCommandError

from .cache import CacheKeys, CacheTTL
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
from .utils import DiffEntry, GitUtils, MAX_UNTRACKED_FILES, VersionControlError

if TYPE_CHECKING:
    from .cache import GitCache

logger = logging.getLogger(__name__)


class StagingOperations:
    """Git 變更與暫存操作

    提供變更查詢、暫存、取消暫存、放棄變更等功能。
    """

    def __init__(self, utils: GitUtils, cache: Optional["GitCache"] = None) -> None:
        """初始化

        Args:
            utils: Git 工具類實例
            cache: 快取層（可選）
        """
        self._utils = utils
        self.cache = cache

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
        # 檢查快取
        if self.cache:
            cached = self.cache.get(workspace_id, CacheKeys.CHANGES, page=page, page_size=page_size, context_id=context_id)
            if cached:
                return ChangesResponse(**cached)

        # 計算結果
        repo = self._utils.get_repo(workspace_id, context_id)
        staged = [self._to_file_change(entry) for entry in self._utils.diff_index(repo, staged=True)]
        unstaged = [self._to_file_change(entry) for entry in self._utils.diff_index(repo, staged=False)]

        # 效能優化: 使用 git ls-files 命令替代 repo.untracked_files
        worktree = Path(repo.working_tree_dir or ".")

        try:
            # 使用 Git 命令取得未追蹤檔案（自動套用 .gitignore）
            result_output = repo.git.execute(
                ["git", "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard"]
            )
            if result_output.strip():
                untracked_files = result_output.strip().split("\n")
            else:
                untracked_files = []
        except GitCommandError as exc:
            logger.warning(f"Failed to get untracked files for workspace {workspace_id}: {exc}")
            untracked_files = []

        # 安全保護: 限制最大檔案數量（防止極端情況）
        if len(untracked_files) > MAX_UNTRACKED_FILES:
            logger.warning(
                f"Workspace {workspace_id} has {len(untracked_files)} untracked files, "
                f"limiting to {MAX_UNTRACKED_FILES} for performance"
            )
            untracked_files = untracked_files[:MAX_UNTRACKED_FILES]

        total_untracked = len(untracked_files)

        # 計算分頁範圍
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # 取得當前頁的檔案
        page_files = untracked_files[start_idx:end_idx]
        has_more = end_idx < total_untracked

        untracked_changes = []
        for rel_path in page_files:
            file_path = worktree / rel_path
            if file_path.is_dir():
                continue

            # 效能優化: 不計算行數，直接設為 0
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

        result = ChangesResponse(
            staged=staged,
            unstaged=unstaged,
            untracked=untracked_changes,
            untrackedTotal=total_untracked,
            untrackedPage=page,
            untrackedPageSize=page_size,
            untrackedHasMore=has_more,
        )

        # 儲存快取（短時間快取，因為變更頻繁）
        if self.cache:
            self.cache.set(
                workspace_id,
                CacheKeys.CHANGES,
                result.model_dump(),
                ttl=CacheTTL.VERY_SHORT,  # 10 秒快取
                page=page,
                page_size=page_size,
                context_id=context_id,
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
