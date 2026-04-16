"""Git 版本控制服務

提供 Git 版本控制操作的統一介面（Facade 模式）。

此服務整合了以下操作模組：
- StatusOperations: 狀態與分支操作
- StagingOperations: 變更與暫存操作
- CommitOperations: 提交與歷史操作
- RemoteOperations: 遠端倉庫操作
- DiffOperations: Diff 與內容操作
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
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlStatus,
)
from .remote_ops import RemoteOperations
from .staging_ops import StagingOperations
from .status_ops import StatusOperations
from .utils import GitUtils, VersionControlError

logger = logging.getLogger(__name__)


class GitService:
    """Git 版本控制服務（Facade）

    提供 Git 操作的統一介面，委派給專門的操作類別處理。

    效能優化：
    - Redis 快取層減少重複計算
    - 批次操作優化
    - 優化的 diff 計算
    - 快速的總數計算
    """

    def __init__(self, base_path: Optional[Path | str] = None, cache: Optional[GitCache] = None) -> None:
        """初始化 Git 服務

        Args:
            base_path: 工作區根目錄
            cache: 快取層（可選）
        """
        root = Path(base_path) if base_path else Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
        self._root_path = root.resolve()
        self._root_path.mkdir(parents=True, exist_ok=True)
        self.cache = cache

        # 初始化工具類
        self._utils = GitUtils(self._root_path, cache)

        # 初始化操作類
        self._status_ops = StatusOperations(self._utils, cache)
        self._staging_ops = StagingOperations(self._utils, cache)
        self._commit_ops = CommitOperations(self._utils, cache)
        self._remote_ops = RemoteOperations(self._utils, cache)
        self._diff_ops = DiffOperations(self._utils, cache)

    # ------------------------------------------------------------------
    # 相容 wrapper
    # ------------------------------------------------------------------
    def _workspace_path(self, workspace_id: str) -> Path:
        """向後相容：取得 workspace 路徑。"""
        return self._utils.workspace_path(workspace_id)

    def _repo(self, workspace_id: str):
        """向後相容：取得 Git repo。"""
        return self._utils.get_repo(workspace_id)

    def _has_head(self, repo) -> bool:
        """向後相容：檢查 repo 是否有 HEAD。"""
        return self._utils.has_head(repo)

    def _current_branch(self, repo) -> tuple[str, bool]:
        """向後相容：取得目前分支。"""
        return self._utils.current_branch(repo)

    def _tracking_delta(self, repo) -> tuple[int, int]:
        """向後相容：取得追蹤分支 ahead/behind。"""
        return self._utils.tracking_delta(repo)

    def _should_ignore_file(self, file_path: str) -> bool:
        """向後相容：判斷檔案是否應忽略。"""
        return self._utils.should_ignore_file(file_path)

    def _normalize_paths(self, repo, paths):
        """向後相容：正規化路徑清單。"""
        return self._utils.normalize_paths(repo, paths)

    def _map_change_type(self, change_type: str) -> str:
        """向後相容：映射變更類型。"""
        return self._utils.map_change_type(change_type)

    # ------------------------------------------------------------------
    # 狀態與分支操作
    # ------------------------------------------------------------------
    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        """List available Git contexts for a workspace."""
        return self._utils.list_contexts(workspace_id)

    def get_status(self, workspace_id: str, context_id: Optional[str] = None) -> VersionControlStatus:
        """取得 Git 狀態

        Args:
            workspace_id: 工作區 ID

        Returns:
            版本控制狀態
        """
        return self._status_ops.get_status(workspace_id, context_id)

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = True,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BranchListResponse:
        """列出分支

        Args:
            workspace_id: 工作區 ID
            include_remote: 是否包含遠端分支
            search: 搜尋關鍵字

        Returns:
            分支列表回應
        """
        return self._status_ops.list_branches(workspace_id, include_remote, search, context_id)

    def checkout_branch(
        self,
        workspace_id: str,
        branch_name: str,
        payload: CheckoutRequest,
        context_id: Optional[str] = None,
    ) -> CheckoutResponse:
        """切換分支

        Args:
            workspace_id: 工作區 ID
            branch_name: 目標分支名稱
            payload: 切換請求

        Returns:
            切換回應
        """
        return self._status_ops.checkout_branch(workspace_id, branch_name, payload, context_id)

    # ------------------------------------------------------------------
    # 變更與暫存操作
    # ------------------------------------------------------------------
    def get_changes(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 100,
        context_id: Optional[str] = None,
    ) -> ChangesResponse:
        """取得檔案變更

        Args:
            workspace_id: 工作區 ID
            page: 頁碼
            page_size: 每頁大小

        Returns:
            變更回應
        """
        return self._staging_ops.get_changes(workspace_id, page, page_size, context_id)

    def stage(self, workspace_id: str, payload: StageRequest, context_id: Optional[str] = None) -> StageResponse:
        """暫存檔案

        Args:
            workspace_id: 工作區 ID
            payload: 暫存請求

        Returns:
            暫存回應
        """
        return self._staging_ops.stage(workspace_id, payload, context_id)

    def unstage(self, workspace_id: str, payload: UnstageRequest, context_id: Optional[str] = None) -> UnstageResponse:
        """取消暫存檔案

        Args:
            workspace_id: 工作區 ID
            payload: 取消暫存請求

        Returns:
            取消暫存回應
        """
        return self._staging_ops.unstage(workspace_id, payload, context_id)

    def discard(self, workspace_id: str, payload: DiscardRequest, context_id: Optional[str] = None) -> DiscardResponse:
        """放棄變更

        Args:
            workspace_id: 工作區 ID
            payload: 放棄請求

        Returns:
            放棄回應
        """
        return self._staging_ops.discard(workspace_id, payload, context_id)

    # ------------------------------------------------------------------
    # 提交與歷史操作
    # ------------------------------------------------------------------
    def commit(self, workspace_id: str, payload: CommitRequest, context_id: Optional[str] = None) -> CommitResponse:
        """建立提交

        Args:
            workspace_id: 工作區 ID
            payload: 提交請求

        Returns:
            提交回應
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
        """列出提交歷史

        Args:
            workspace_id: 工作區 ID
            page: 頁碼
            page_size: 每頁大小
            branch: 分支名稱
            search: 搜尋關鍵字

        Returns:
            提交列表回應
        """
        return self._commit_ops.list_commits(workspace_id, page, page_size, branch, search, context_id)

    def get_commit(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitDetailResponse:
        """取得提交詳情

        Args:
            workspace_id: 工作區 ID
            commit_id: 提交 ID

        Returns:
            提交詳情回應
        """
        return self._commit_ops.get_commit(workspace_id, commit_id, context_id)

    def get_commit_files(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> CommitFilesResponse:
        """取得提交的檔案列表

        Args:
            workspace_id: 工作區 ID
            commit_id: 提交 ID

        Returns:
            提交檔案回應
        """
        return self._commit_ops.get_commit_files(workspace_id, commit_id, context_id)

    # ------------------------------------------------------------------
    # 遠端操作
    # ------------------------------------------------------------------
    def push(self, workspace_id: str, payload: PushRequest, context_id: Optional[str] = None) -> PushResponse:
        """推送到遠端

        Args:
            workspace_id: 工作區 ID
            payload: 推送請求

        Returns:
            推送回應
        """
        return self._remote_ops.push(workspace_id, payload, context_id)

    def pull(self, workspace_id: str, payload: PullRequest, context_id: Optional[str] = None) -> PullResponse:
        """從遠端拉取

        Args:
            workspace_id: 工作區 ID
            payload: 拉取請求

        Returns:
            拉取回應
        """
        return self._remote_ops.pull(workspace_id, payload, context_id)

    def fetch(self, workspace_id: str, payload: FetchRequest, context_id: Optional[str] = None) -> FetchResponse:
        """從遠端取得更新

        Args:
            workspace_id: 工作區 ID
            payload: Fetch 請求

        Returns:
            Fetch 回應
        """
        return self._remote_ops.fetch(workspace_id, payload, context_id)

    # ------------------------------------------------------------------
    # Diff 與內容操作
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
        """獲取檔案的差異內容

        Args:
            workspace_id: 工作區 ID
            path: 檔案路徑
            base: 比較基準
            head: 比較目標
            context: 上下文行數
            include_metadata: 是否包含檔案元資料

        Returns:
            Diff 回應
        """
        return self._diff_ops.diff(workspace_id, path, base, head, context, include_metadata, context_id)

    def blob(
        self,
        workspace_id: str,
        path: str,
        revision: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BlobResponse:
        """獲取檔案內容

        Args:
            workspace_id: 工作區 ID
            path: 檔案路徑
            revision: 版本

        Returns:
            Blob 回應
        """
        return self._diff_ops.blob(workspace_id, path, revision, context_id)


__all__ = ["GitService", "VersionControlError"]
