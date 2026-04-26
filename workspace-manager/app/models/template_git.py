"""Template Git version control related data models"""

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class GitStatus(BaseModel):
    """Git repository status"""

    current_branch: str = Field(..., description="Current branch name")
    has_changes: bool = Field(..., description="Whether there are uncommitted changes")
    ahead_count: int = Field(default=0, description="Number of commits ahead of remote")
    behind_count: int = Field(default=0, description="Number of commits behind remote")
    remote_url: Optional[str] = Field(None, description="Remote repository URL")
    is_git_repo: bool = Field(..., description="Whether it is a Git repository")


class GitCommitRequest(BaseModel):
    """Git commit request"""

    message: str = Field(..., min_length=1, description="Commit message")
    paths: Optional[List[str]] = Field(default=None, description="Limited file paths to commit")


class GitOperationResponse(BaseModel):
    """Git operation response"""

    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Response message")
    data: Optional[dict] = Field(None, description="Additional data")
    error: Optional[str] = Field(None, description="Error message")
    error_code: Optional[str] = Field(None, alias="errorCode", description="Stable error code")

    model_config = ConfigDict(populate_by_name=True)


class GitUserConfig(BaseModel):
    """Git user information"""

    user_name: Optional[str] = Field(None, alias="userName", description="Git user name")
    user_email: Optional[str] = Field(None, alias="userEmail", description="Git user email")

    model_config = ConfigDict(populate_by_name=True)


class GitUserConfigResponse(BaseModel):
    """Git user information response"""

    success: bool = Field(..., description="Whether operation succeeded")
    data: Optional[GitUserConfig] = Field(None, description="Git user information")
    error: Optional[str] = Field(None, description="Error message")


class GitRemoteUrlRequest(BaseModel):
    """Set Git remote repository URL request"""

    url: str = Field(..., min_length=1, alias="remoteUrl", description="Remote repository URL")

    model_config = ConfigDict(populate_by_name=True)


class SSHKeysUpdateRequest(BaseModel):
    """Update SSH keys request"""

    private_key: str = Field(..., alias="privateKey", description="SSH private key")
    public_key: str = Field(..., alias="publicKey", description="SSH public key")

    model_config = ConfigDict(populate_by_name=True)


class GitCloneRequest(BaseModel):
    """Clone Git repository request"""

    url: str = Field(..., min_length=1, description="Remote repository URL")
    branch: Optional[str] = Field(None, description="Branch to clone (optional)")
    force: bool = Field(False, description="Whether to allow overwriting existing local content")

    model_config = ConfigDict(populate_by_name=True)


class GitRepositoryInitRequest(BaseModel):
    """Initialize template center Git repository request"""

    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="Origin URL to set after initialization")

    model_config = ConfigDict(populate_by_name=True)


class GitRepositoryStatus(BaseModel):
    """Template center Git repository lifecycle status"""

    is_git_repo: bool = Field(..., alias="isGitRepo", description="Whether initialized as Git repository")
    current_branch: Optional[str] = Field(None, alias="currentBranch", description="Current branch")
    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="origin URL")
    has_origin: bool = Field(False, alias="hasOrigin", description="Whether origin is set")
    has_local_content: bool = Field(False, alias="hasLocalContent", description="Whether there is local template center content")
    can_clone_safely: bool = Field(False, alias="canCloneSafely", description="Whether clone can be done safely")
    can_init_safely: bool = Field(False, alias="canInitSafely", description="Whether init can be done safely")
    clone_blocked_reason: Optional[str] = Field(None, alias="cloneBlockedReason", description="Reason why clone is blocked")

    model_config = ConfigDict(populate_by_name=True)


class TemplateVersionControlStatus(BaseModel):
    """Template Center file-level Git status."""

    branch: str = Field(description="Current branch")
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    detached: bool = Field(default=False, description="Whether detached HEAD")
    hasConflicts: bool = Field(default=False, description="Whether there are conflicts")
    stagedCount: int = Field(default=0, description="Number of staged files")
    unstagedCount: int = Field(default=0, description="Number of unstaged files")
    untrackedCount: int = Field(default=0, description="Number of untracked files")
    lastFetchedAt: Optional[str] = Field(default=None, description="Last fetch time")


class TemplateBranchCommitInfo(BaseModel):
    """Branch last commit summary."""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: str = Field(description="ISO8601 commit time")


class TemplateVersionControlBranch(BaseModel):
    """Template Center Git branch."""

    name: str = Field(description="Branch name")
    displayName: str = Field(description="Display name")
    isActive: bool = Field(description="Whether this is the current branch")
    isRemote: bool = Field(default=False, description="Whether this is a remote branch")
    ahead: int = Field(default=0, description="Number of commits ahead")
    behind: int = Field(default=0, description="Number of commits behind")
    lastCommit: Optional[TemplateBranchCommitInfo] = Field(default=None, description="Last commit information")


class TemplateVersionControlBranchListResponse(BaseModel):
    branches: List[TemplateVersionControlBranch] = Field(default_factory=list)


class TemplateFileChange(BaseModel):
    """File-level Git change for Template Center."""

    name: str = Field(description="File name")
    path: str = Field(description="Relative path")
    status: str = Field(description="Git status code")
    type: Literal[
        "added",
        "modified",
        "deleted",
        "renamed",
        "copied",
        "typechange",
        "unmerged",
        "untracked",
    ] = Field(description="Change type")
    oldPath: Optional[str] = Field(default=None, description="Path before rename")
    additions: int = Field(default=0, description="Number of lines added")
    deletions: int = Field(default=0, description="Number of lines deleted")
    diff: Optional[str] = Field(default=None, description="Difference content")
    patch: Optional[str] = Field(default=None, description="Difference content")


class TemplateChangesResponse(BaseModel):
    staged: List[TemplateFileChange] = Field(default_factory=list)
    unstaged: List[TemplateFileChange] = Field(default_factory=list)
    untracked: List[TemplateFileChange] = Field(default_factory=list)
    untrackedTotal: int = Field(default=0)
    untrackedPage: int = Field(default=1)
    untrackedPageSize: int = Field(default=100)
    untrackedHasMore: bool = Field(default=False)


class TemplateStageRequest(BaseModel):
    paths: List[str] = Field(description="Paths to stage")
    includeUntracked: bool = Field(default=True, description="Whether to include untracked files")


class TemplateStageResponse(BaseModel):
    staged: List[str] = Field(default_factory=list)
    unstaged: List[str] = Field(default_factory=list)


class TemplateUnstageRequest(BaseModel):
    paths: List[str] = Field(description="Paths to unstage")


class TemplateUnstageResponse(BaseModel):
    unstaged: List[str] = Field(default_factory=list)
    remainingStaged: int = Field(default=0)


class TemplateDiscardRequest(BaseModel):
    paths: List[str] = Field(description="Paths to restore")


class TemplateDiscardResponse(BaseModel):
    discarded: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class TemplateCommitAuthor(BaseModel):
    name: str = Field(description="Author name")
    email: str = Field(description="Author email")


class TemplateCommitSummary(BaseModel):
    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: int = Field(description="epoch ms")
    branch: Optional[str] = Field(default=None, description="Branch")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    files: int = Field(default=0)


class TemplateCommitResponse(BaseModel):
    commit: TemplateCommitSummary


class TemplateCommitListResponse(BaseModel):
    page: int = Field(description="Page number")
    pageSize: int = Field(description="Items per page")
    total: int = Field(description="Total items")
    items: List[TemplateCommitSummary] = Field(default_factory=list)


class TemplateCommitFilesResponse(BaseModel):
    commitId: str = Field(description="Commit ID")
    files: List[TemplateFileChange] = Field(default_factory=list)


class TemplateCheckoutRequest(BaseModel):
    create: bool = Field(default=False, description="Whether to create new branch")
    startPoint: Optional[str] = Field(default=None, description="New branch start point")
    stashChanges: bool = Field(default=False, description="Whether to stash before switching")


class TemplateCheckoutResponse(BaseModel):
    branch: str = Field(description="Branch after switching")
    created: bool = Field(description="Whether new branch was created")
    stashedChanges: Optional[str] = Field(default=None, description="Stash name")


class TemplateRemoteRequest(BaseModel):
    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Branch name")
    rebase: bool = Field(default=True, description="Whether to rebase during pull")
    autostash: bool = Field(default=True, description="Whether to autostash during pull")
    force: bool = Field(default=False, description="Whether to force during push")


class TemplateRemoteResponse(BaseModel):
    remote: str = Field(default="origin")
    branch: Optional[str] = None
    message: str = Field(default="")


class TemplateDiffResponse(BaseModel):
    path: str = Field(description="File path")
    patch: str = Field(default="", description="diff patch")
    diff: str = Field(default="", description="diff patch")
    binary: bool = Field(default=False, description="Whether binary")


class TemplateBlobResponse(BaseModel):
    path: str = Field(description="File path")
    revision: Optional[str] = Field(default=None, description="revision")
    content: str = Field(description="File content")
    encoding: str = Field(default="utf-8")
