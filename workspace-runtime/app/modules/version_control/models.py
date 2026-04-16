"""版本控制模型定義"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CommitAuthor(BaseModel):
    """提交作者資訊"""

    name: str = Field(description="作者名稱")
    email: str = Field(description="作者電子郵件")


class GitContext(BaseModel):
    """Git context metadata for the primary checkout or a worktree."""

    id: str = Field(description="Stable context identifier")
    kind: Literal["primary", "worktree"] = Field(description="Context kind")
    displayName: str = Field(description="Display label")
    repoPath: str = Field(description="Repository path for this context")
    branch: Optional[str] = Field(default=None, description="Current branch name when available")
    headRef: Optional[str] = Field(default=None, description="Resolved HEAD ref when available")
    detached: bool = Field(default=False, description="Whether HEAD is detached")
    headSha: Optional[str] = Field(default=None, description="Current HEAD commit SHA")
    locked: bool = Field(default=False, description="Whether the worktree is locked")
    prunable: bool = Field(default=False, description="Whether the worktree is marked prunable")


class GitContextListResponse(BaseModel):
    """List of available Git contexts for a workspace."""

    activeContextId: str = Field(description="Default active Git context identifier")
    contexts: list[GitContext] = Field(description="Available Git contexts")


class VersionControlStatus(BaseModel):
    """Git 狀態摘要"""

    branch: str = Field(description="目前分支")
    ahead: int = Field(default=0, description="領先遠端提交數")
    behind: int = Field(default=0, description="落後遠端提交數")
    detached: bool = Field(default=False, description="是否為分離 HEAD 狀態")
    hasConflicts: bool = Field(default=False, description="是否存在衝突")
    stagedCount: int = Field(default=0, description="暫存檔案數量")
    unstagedCount: int = Field(default=0, description="未暫存檔案數量")
    untrackedCount: int = Field(default=0, description="未追蹤檔案數量")
    lastFetchedAt: Optional[str] = Field(
        default=None, description="最後一次遠端同步時間 (ISO8601)"
    )


class BranchCommitInfo(BaseModel):
    """分支最後一次提交資訊"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: str = Field(description="作者名稱")
    email: Optional[str] = Field(default=None, description="作者電子郵件")
    timestamp: str = Field(description="提交時間 (ISO8601)")


class BranchInfo(BaseModel):
    """分支資訊"""

    name: str = Field(description="分支完整名稱")
    displayName: str = Field(description="顯示名稱")
    isActive: bool = Field(description="是否為目前檢出分支")
    isRemote: bool = Field(description="是否為遠端分支")
    ahead: int = Field(default=0, description="領先提交數")
    behind: int = Field(default=0, description="落後提交數")
    lastCommit: Optional[BranchCommitInfo] = Field(
        default=None, description="最後提交資訊"
    )


class BranchListResponse(BaseModel):
    """分支列表回應"""

    branches: list[BranchInfo] = Field(description="分支清單")


class CheckoutRequest(BaseModel):
    """切換分支請求"""

    create: bool = Field(default=False, description="是否建立新分支")
    startPoint: Optional[str] = Field(
        default=None, description="新分支起始點，預設為目前 HEAD"
    )
    stashChanges: bool = Field(default=False, description="切換前是否建立 stash")


class CheckoutResponse(BaseModel):
    """切換分支回應"""

    branch: str = Field(description="最終分支名稱")
    created: bool = Field(description="是否建立了新分支")
    stashedChanges: Optional[str] = Field(
        default=None, description="建立的 stash 名稱 (若有)"
    )


class FileChange(BaseModel):
    """檔案變更資訊"""

    name: str = Field(description="檔案名稱")
    path: str = Field(description="檔案相對路徑")
    status: str = Field(description="Git 狀態代碼")
    type: Literal[
        "added",
        "modified",
        "deleted",
        "renamed",
        "copied",
        "typechange",
        "unmerged",
        "untracked",
    ] = Field(description="變更類型")
    additions: int = Field(default=0, description="新增行數")
    deletions: int = Field(default=0, description="刪除行數")
    diff: Optional[str] = Field(default=None, description="差異內容 (如適用)")


class ChangesResponse(BaseModel):
    """檔案變更回應"""

    staged: list[FileChange] = Field(default_factory=list, description="暫存變更")
    unstaged: list[FileChange] = Field(default_factory=list, description="未暫存變更")
    untracked: list[FileChange] = Field(default_factory=list, description="未追蹤檔案")
    # 分頁資訊
    untrackedTotal: int = Field(default=0, description="未追蹤檔案總數")
    untrackedPage: int = Field(default=1, description="當前頁碼")
    untrackedPageSize: int = Field(default=100, description="每頁數量")
    untrackedHasMore: bool = Field(default=False, description="是否還有更多檔案")


class StageRequest(BaseModel):
    """暫存檔案請求"""

    paths: list[str] = Field(description="要暫存的檔案或資料夾")
    includeUntracked: bool = Field(
        default=False, description="是否一併暫存未追蹤檔案"
    )


class StageResponse(BaseModel):
    """暫存檔案回應"""

    staged: list[str] = Field(description="成功暫存的路徑")
    unstaged: list[str] = Field(description="仍未暫存的路徑")


class UnstageRequest(BaseModel):
    """取消暫存請求"""

    paths: list[str] = Field(description="要取消暫存的檔案或資料夾")


class UnstageResponse(BaseModel):
    """取消暫存回應"""

    unstaged: list[str] = Field(description="取消暫存的路徑")
    remainingStaged: int = Field(description="仍暫存在索引中的檔案數量")


class DiscardRequest(BaseModel):
    """丟棄未暫存變更請求"""

    paths: list[str] = Field(description="要還原的檔案或資料夾")
    resetMode: Literal["soft", "mixed", "hard"] = Field(
        default="mixed", description="Git reset 模式"
    )


class DiscardResponse(BaseModel):
    """丟棄變更回應"""

    discarded: list[str] = Field(description="已還原的路徑")
    warnings: list[str] = Field(default_factory=list, description="額外警告訊息")


class CommitStats(BaseModel):
    """提交統計資訊"""

    additions: int = Field(description="新增行數")
    deletions: int = Field(description="刪除行數")
    files: int = Field(description="受影響檔案數")


class CommitChange(BaseModel):
    """提交中的單一檔案變更"""

    name: str = Field(description="檔案名稱")
    path: str = Field(description="檔案路徑")
    status: str = Field(description="變更狀態")
    additions: int = Field(description="新增行數")
    deletions: int = Field(description="刪除行數")
    patch: Optional[str] = Field(default=None, description="差異內容")


class CommitSummary(BaseModel):
    """提交摘要資訊"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: CommitAuthor = Field(description="作者資訊")
    timestamp: str = Field(description="提交時間 (ISO8601)")
    additions: int = Field(description="新增行數")
    deletions: int = Field(description="刪除行數")


class CommitRequest(BaseModel):
    """建立提交請求"""

    message: str = Field(description="提交訊息")
    author: Optional[CommitAuthor] = Field(
        default=None, description="提交作者，未提供則使用預設"
    )
    amend: bool = Field(default=False, description="是否為 amend 提交")
    paths: Optional[list[str]] = Field(
        default=None, description="限定提交的檔案，未提供則提交索引全部"
    )


class CommitResponse(BaseModel):
    """建立提交回應"""

    commit: CommitSummary = Field(description="新提交資訊")


class CommitListItem(BaseModel):
    """提交列表項目"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: str = Field(description="作者名稱")
    email: Optional[str] = Field(default=None, description="作者電子郵件")
    timestamp: int = Field(description="提交時間 (epoch ms)")
    branch: str = Field(description="所屬分支")
    additions: int = Field(description="新增行數")
    deletions: int = Field(description="刪除行數")
    files: int = Field(description="受影響檔案數")


class CommitListResponse(BaseModel):
    """提交列表回應"""

    page: int = Field(description="頁碼")
    pageSize: int = Field(description="每頁筆數")
    total: int = Field(description="提交總數")
    items: list[CommitListItem] = Field(description="提交清單")


class CommitDetailResponse(BaseModel):
    """單一提交詳細資訊"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: CommitAuthor = Field(description="作者資訊")
    timestamp: str = Field(description="提交時間 (ISO8601)")
    branch: str = Field(description="分支名稱")
    stats: CommitStats = Field(description="統計資訊")
    changes: list[CommitChange] = Field(description="檔案變更清單")


class CommitFilesResponse(BaseModel):
    """提交檔案差異回應"""

    commitId: str = Field(description="提交 ID")
    files: list[CommitChange] = Field(description="檔案差異清單")


class PushRequest(BaseModel):
    """推送請求"""

    remote: str = Field(default="origin", description="遠端名稱")
    branch: Optional[str] = Field(default=None, description="推送目標分支")
    force: bool = Field(default=False, description="是否強制推送")


class PushUpdate(BaseModel):
    """推送結果資訊"""

    ref: str = Field(description="更新的引用")
    status: str = Field(description="推送狀態")


class PushResponse(BaseModel):
    """推送回應"""

    remote: str = Field(description="遠端名稱")
    branch: str = Field(description="推送分支")
    updates: list[PushUpdate] = Field(description="推送結果清單")


class PullRequest(BaseModel):
    """拉取請求"""

    remote: str = Field(default="origin", description="遠端名稱")
    branch: Optional[str] = Field(default=None, description="拉取分支")
    rebase: bool = Field(default=False, description="是否使用 rebase")
    autostash: bool = Field(default=False, description="是否自動 stash 變更")


class PullCommitInfo(BaseModel):
    """拉取後的提交資訊"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: str = Field(description="作者名稱")


class PullResponse(BaseModel):
    """拉取回應"""

    remote: str = Field(description="遠端名稱")
    branch: str = Field(description="分支名稱")
    fastForward: bool = Field(description="是否為快轉合併")
    commits: list[PullCommitInfo] = Field(description="新增提交清單")


class FetchRequest(BaseModel):
    """同步遠端引用請求"""

    remote: str = Field(default="origin", description="遠端名稱")
    prune: bool = Field(default=False, description="是否移除遠端已刪除分支")


class FetchResponse(BaseModel):
    """同步遠端引用回應"""

    remote: str = Field(description="遠端名稱")
    fetchedRefs: list[str] = Field(description="同步的引用清單")


class DiffResponse(BaseModel):
    """差異結果回應"""

    path: str = Field(description="檔案路徑")
    base: str = Field(description="比較基準")
    head: str = Field(description="比較目標")
    context: int = Field(description="上下文行數")
    patch: str = Field(description="差異內容")
    metadata: Optional[dict] = Field(default=None, description="額外中繼資料")


class BlobResponse(BaseModel):
    """檔案內容回應"""

    path: str = Field(description="檔案路徑")
    revision: str = Field(description="提交或引用")
    encoding: str = Field(default="utf-8", description="內容編碼")
    content: str = Field(description="Base64 編碼內容")
    isBase64: bool = Field(default=True, description="是否為 Base64 編碼")


__all__ = [
    "BlobResponse",
    "BranchCommitInfo",
    "BranchInfo",
    "BranchListResponse",
    "ChangesResponse",
    "CheckoutRequest",
    "CheckoutResponse",
    "CommitAuthor",
    "CommitChange",
    "CommitDetailResponse",
    "CommitFilesResponse",
    "CommitListItem",
    "CommitListResponse",
    "CommitRequest",
    "CommitResponse",
    "CommitStats",
    "CommitSummary",
    "DiffResponse",
    "DiscardRequest",
    "DiscardResponse",
    "FetchRequest",
    "FetchResponse",
    "FileChange",
    "GitContext",
    "GitContextListResponse",
    "PullCommitInfo",
    "PullRequest",
    "PullResponse",
    "PushRequest",
    "PushResponse",
    "PushUpdate",
    "StageRequest",
    "StageResponse",
    "UnstageRequest",
    "UnstageResponse",
    "VersionControlStatus",
]
