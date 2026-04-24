"""模板 Git 版本控制相關的資料模型"""

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class GitStatus(BaseModel):
    """Git 倉庫狀態"""

    current_branch: str = Field(..., description="當前分支名稱")
    has_changes: bool = Field(..., description="是否有未提交的變更")
    ahead_count: int = Field(default=0, description="領先遠端的 commit 數")
    behind_count: int = Field(default=0, description="落後遠端的 commit 數")
    remote_url: Optional[str] = Field(None, description="遠端倉庫 URL")
    is_git_repo: bool = Field(..., description="是否為 Git 倉庫")


class GitCommitRequest(BaseModel):
    """Git commit 請求"""

    message: str = Field(..., min_length=1, description="Commit 訊息")
    paths: Optional[List[str]] = Field(default=None, description="限定提交的檔案路徑")


class GitOperationResponse(BaseModel):
    """Git 操作回應"""

    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="回應訊息")
    data: Optional[dict] = Field(None, description="額外資料")
    error: Optional[str] = Field(None, description="錯誤訊息")
    error_code: Optional[str] = Field(None, alias="errorCode", description="穩定錯誤代碼")

    model_config = ConfigDict(populate_by_name=True)


class GitUserConfig(BaseModel):
    """Git 使用者資訊"""

    user_name: Optional[str] = Field(None, alias="userName", description="Git 使用者名稱")
    user_email: Optional[str] = Field(None, alias="userEmail", description="Git 使用者 Email")

    model_config = ConfigDict(populate_by_name=True)


class GitUserConfigResponse(BaseModel):
    """Git 使用者資訊回應"""

    success: bool = Field(..., description="操作是否成功")
    data: Optional[GitUserConfig] = Field(None, description="Git 使用者資訊")
    error: Optional[str] = Field(None, description="錯誤訊息")


class GitRemoteUrlRequest(BaseModel):
    """設定 Git 遠端倉庫 URL 請求"""

    url: str = Field(..., min_length=1, alias="remoteUrl", description="遠端倉庫 URL")

    model_config = ConfigDict(populate_by_name=True)


class SSHKeysUpdateRequest(BaseModel):
    """更新 SSH Keys 請求"""

    private_key: str = Field(..., alias="privateKey", description="SSH 私鑰")
    public_key: str = Field(..., alias="publicKey", description="SSH 公鑰")

    model_config = ConfigDict(populate_by_name=True)


class GitCloneRequest(BaseModel):
    """Clone Git 倉庫請求"""

    url: str = Field(..., min_length=1, description="遠端倉庫 URL")
    branch: Optional[str] = Field(None, description="要 clone 的分支（可選）")
    force: bool = Field(False, description="是否允許覆蓋既有本地內容")

    model_config = ConfigDict(populate_by_name=True)


class GitRepositoryInitRequest(BaseModel):
    """初始化模板中心 Git 倉庫請求"""

    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="初始化後要設定的 origin URL")

    model_config = ConfigDict(populate_by_name=True)


class GitRepositoryStatus(BaseModel):
    """模板中心 Git 倉庫生命週期狀態"""

    is_git_repo: bool = Field(..., alias="isGitRepo", description="是否已初始化為 Git 倉庫")
    current_branch: Optional[str] = Field(None, alias="currentBranch", description="目前分支")
    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="origin URL")
    has_origin: bool = Field(False, alias="hasOrigin", description="是否已設定 origin")
    has_local_content: bool = Field(False, alias="hasLocalContent", description="是否已有本地模板中心內容")
    can_clone_safely: bool = Field(False, alias="canCloneSafely", description="是否可安全 clone")
    can_init_safely: bool = Field(False, alias="canInitSafely", description="是否可安全 init")
    clone_blocked_reason: Optional[str] = Field(None, alias="cloneBlockedReason", description="clone 被阻擋原因")

    model_config = ConfigDict(populate_by_name=True)


class TemplateVersionControlStatus(BaseModel):
    """Template Center file-level Git status."""

    branch: str = Field(description="目前分支")
    ahead: int = Field(default=0, description="領先遠端提交數")
    behind: int = Field(default=0, description="落後遠端提交數")
    detached: bool = Field(default=False, description="是否為 detached HEAD")
    hasConflicts: bool = Field(default=False, description="是否存在衝突")
    stagedCount: int = Field(default=0, description="暫存檔案數")
    unstagedCount: int = Field(default=0, description="未暫存檔案數")
    untrackedCount: int = Field(default=0, description="未追蹤檔案數")
    lastFetchedAt: Optional[str] = Field(default=None, description="最後 fetch 時間")


class TemplateBranchCommitInfo(BaseModel):
    """分支最後提交摘要。"""

    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: str = Field(description="作者")
    email: Optional[str] = Field(default=None, description="作者 Email")
    timestamp: str = Field(description="ISO8601 提交時間")


class TemplateVersionControlBranch(BaseModel):
    """Template Center Git branch."""

    name: str = Field(description="分支名稱")
    displayName: str = Field(description="顯示名稱")
    isActive: bool = Field(description="是否為目前分支")
    isRemote: bool = Field(default=False, description="是否為遠端分支")
    ahead: int = Field(default=0, description="領先提交數")
    behind: int = Field(default=0, description="落後提交數")
    lastCommit: Optional[TemplateBranchCommitInfo] = Field(default=None, description="最後提交資訊")


class TemplateVersionControlBranchListResponse(BaseModel):
    branches: List[TemplateVersionControlBranch] = Field(default_factory=list)


class TemplateFileChange(BaseModel):
    """File-level Git change for Template Center."""

    name: str = Field(description="檔名")
    path: str = Field(description="相對路徑")
    status: str = Field(description="Git 狀態碼")
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
    oldPath: Optional[str] = Field(default=None, description="rename 前路徑")
    additions: int = Field(default=0, description="新增行數")
    deletions: int = Field(default=0, description="刪除行數")
    diff: Optional[str] = Field(default=None, description="差異內容")
    patch: Optional[str] = Field(default=None, description="差異內容")


class TemplateChangesResponse(BaseModel):
    staged: List[TemplateFileChange] = Field(default_factory=list)
    unstaged: List[TemplateFileChange] = Field(default_factory=list)
    untracked: List[TemplateFileChange] = Field(default_factory=list)
    untrackedTotal: int = Field(default=0)
    untrackedPage: int = Field(default=1)
    untrackedPageSize: int = Field(default=100)
    untrackedHasMore: bool = Field(default=False)


class TemplateStageRequest(BaseModel):
    paths: List[str] = Field(description="要暫存的路徑")
    includeUntracked: bool = Field(default=True, description="是否包含未追蹤檔案")


class TemplateStageResponse(BaseModel):
    staged: List[str] = Field(default_factory=list)
    unstaged: List[str] = Field(default_factory=list)


class TemplateUnstageRequest(BaseModel):
    paths: List[str] = Field(description="要取消暫存的路徑")


class TemplateUnstageResponse(BaseModel):
    unstaged: List[str] = Field(default_factory=list)
    remainingStaged: int = Field(default=0)


class TemplateDiscardRequest(BaseModel):
    paths: List[str] = Field(description="要還原的路徑")


class TemplateDiscardResponse(BaseModel):
    discarded: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TemplateCommitAuthor(BaseModel):
    name: str = Field(description="作者名稱")
    email: str = Field(description="作者 Email")


class TemplateCommitSummary(BaseModel):
    id: str = Field(description="提交 ID")
    message: str = Field(description="提交訊息")
    author: str = Field(description="作者")
    email: Optional[str] = Field(default=None, description="作者 Email")
    timestamp: int = Field(description="epoch ms")
    branch: Optional[str] = Field(default=None, description="分支")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    files: int = Field(default=0)


class TemplateCommitResponse(BaseModel):
    commit: TemplateCommitSummary


class TemplateCommitListResponse(BaseModel):
    page: int = Field(description="頁碼")
    pageSize: int = Field(description="每頁筆數")
    total: int = Field(description="總筆數")
    items: List[TemplateCommitSummary] = Field(default_factory=list)


class TemplateCommitFilesResponse(BaseModel):
    commitId: str = Field(description="提交 ID")
    files: List[TemplateFileChange] = Field(default_factory=list)


class TemplateCheckoutRequest(BaseModel):
    create: bool = Field(default=False, description="是否建立新分支")
    startPoint: Optional[str] = Field(default=None, description="新分支起始點")
    stashChanges: bool = Field(default=False, description="切換前是否 stash")


class TemplateCheckoutResponse(BaseModel):
    branch: str = Field(description="切換後分支")
    created: bool = Field(description="是否建立新分支")
    stashedChanges: Optional[str] = Field(default=None, description="stash 名稱")


class TemplateRemoteRequest(BaseModel):
    remote: str = Field(default="origin", description="遠端名稱")
    branch: Optional[str] = Field(default=None, description="分支名稱")
    rebase: bool = Field(default=True, description="pull 時是否 rebase")
    autostash: bool = Field(default=True, description="pull 時是否 autostash")
    force: bool = Field(default=False, description="push 時是否 force")


class TemplateRemoteResponse(BaseModel):
    remote: str = Field(default="origin")
    branch: Optional[str] = None
    message: str = Field(default="")


class TemplateDiffResponse(BaseModel):
    path: str = Field(description="檔案路徑")
    patch: str = Field(default="", description="diff patch")
    diff: str = Field(default="", description="diff patch")
    binary: bool = Field(default=False, description="是否為二進位")


class TemplateBlobResponse(BaseModel):
    path: str = Field(description="檔案路徑")
    revision: Optional[str] = Field(default=None, description="revision")
    content: str = Field(description="檔案內容")
    encoding: str = Field(default="utf-8")
