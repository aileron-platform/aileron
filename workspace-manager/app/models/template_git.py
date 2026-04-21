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


class TemplateChange(BaseModel):
    """單一模板的變更資訊"""

    template_id: str = Field(..., description="模板 ID")
    template_name: str = Field(..., description="模板名稱")
    status: Literal["modified", "added", "deleted", "untracked"] = Field(..., description="變更狀態")
    changed_files: List[str] = Field(default_factory=list, description="變更的檔案路徑列表（相對於模板根目錄）")
    changed_dirs: List[str] = Field(default_factory=list, description="有變更的子目錄路徑（相對於模板根目錄）")


class GitChangeLog(BaseModel):
    """Git 變更記錄"""

    templates: List[TemplateChange] = Field(default_factory=list, description="模板變更列表")
    total_changes: int = Field(..., description="總變更數")
    has_staged: bool = Field(default=False, description="是否有已 staged 的變更")
    has_unstaged: bool = Field(default=False, description="是否有未 staged 的變更")


class GitBranch(BaseModel):
    """Git 分支資訊"""

    name: str = Field(..., description="分支名稱")
    is_current: bool = Field(..., description="是否為當前分支")
    is_remote: bool = Field(default=False, description="是否為遠端分支")


class GitBranchList(BaseModel):
    """Git 分支列表"""

    branches: List[GitBranch] = Field(default_factory=list, description="分支列表")
    current_branch: str = Field(..., description="當前分支名稱")


class GitCommitRequest(BaseModel):
    """Git commit 請求"""

    message: str = Field(..., min_length=1, description="Commit 訊息")
    branch: Optional[str] = Field(None, description="目標分支（若為空則使用當前分支）")
    push: bool = Field(default=True, description="是否自動 push 到遠端")


class GitPullRequest(BaseModel):
    """Git pull 請求"""

    branch: Optional[str] = Field(None, description="要拉取的分支（若為空則使用當前分支）")


class GitOperationResponse(BaseModel):
    """Git 操作回應"""

    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="回應訊息")
    data: Optional[dict] = Field(None, description="額外資料")
    error: Optional[str] = Field(None, description="錯誤訊息")
    error_code: Optional[str] = Field(None, alias="errorCode", description="穩定錯誤代碼")

    model_config = ConfigDict(populate_by_name=True)


class GitStatusResponse(BaseModel):
    """Git 狀態回應"""

    success: bool = Field(..., description="操作是否成功")
    data: Optional[GitStatus] = Field(None, description="Git 狀態")
    error: Optional[str] = Field(None, description="錯誤訊息")


class GitChangeLogResponse(BaseModel):
    """Git 變更記錄回應"""

    success: bool = Field(..., description="操作是否成功")
    data: Optional[GitChangeLog] = Field(None, description="變更記錄")
    error: Optional[str] = Field(None, description="錯誤訊息")


class GitBranchListResponse(BaseModel):
    """Git 分支列表回應"""

    success: bool = Field(..., description="操作是否成功")
    data: Optional[GitBranchList] = Field(None, description="分支列表")
    error: Optional[str] = Field(None, description="錯誤訊息")


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

    model_config = ConfigDict(populate_by_name=True)
