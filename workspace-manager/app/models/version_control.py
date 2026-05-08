"""Shared Git version control data models."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class GitCommitRequest(BaseModel):
    """Git commit request."""

    message: str = Field(..., min_length=1, description="Commit message")
    paths: Optional[List[str]] = Field(default=None, description="Limited file paths to commit")


class GitOperationResponse(BaseModel):
    """Git operation response."""

    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Response message")
    data: Optional[dict] = Field(None, description="Additional data")
    error: Optional[str] = Field(None, description="Error message")
    error_code: Optional[str] = Field(None, alias="errorCode", description="Stable error code")

    model_config = ConfigDict(populate_by_name=True)


class GitRemoteUrlRequest(BaseModel):
    """Set Git remote repository URL request."""

    url: str = Field(..., min_length=1, alias="remoteUrl", description="Remote repository URL")

    model_config = ConfigDict(populate_by_name=True)


class GitRepositoryStatus(BaseModel):
    """Git repository lifecycle status."""

    is_git_repo: bool = Field(..., alias="isGitRepo", description="Whether initialized as Git repository")
    current_branch: Optional[str] = Field(None, alias="currentBranch", description="Current branch")
    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="origin URL")
    has_origin: bool = Field(False, alias="hasOrigin", description="Whether origin is set")
    has_local_content: bool = Field(False, alias="hasLocalContent", description="Whether there is local content")
    can_clone_safely: bool = Field(False, alias="canCloneSafely", description="Whether clone can be done safely")
    can_init_safely: bool = Field(False, alias="canInitSafely", description="Whether init can be done safely")
    clone_blocked_reason: Optional[str] = Field(None, alias="cloneBlockedReason", description="Reason why clone is blocked")

    model_config = ConfigDict(populate_by_name=True)


class VersionControlStatus(BaseModel):
    """File-level Git status."""

    branch: str = Field(description="Current branch")
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    detached: bool = Field(default=False, description="Whether detached HEAD")
    hasConflicts: bool = Field(default=False, description="Whether there are conflicts")
    stagedCount: int = Field(default=0, description="Number of staged files")
    unstagedCount: int = Field(default=0, description="Number of unstaged files")
    untrackedCount: int = Field(default=0, description="Number of untracked files")
    lastFetchedAt: Optional[str] = Field(default=None, description="Last fetch time")


class BranchCommitInfo(BaseModel):
    """Branch last commit summary."""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: str = Field(description="ISO8601 commit time")


class VersionControlBranch(BaseModel):
    """Git branch."""

    name: str = Field(description="Branch name")
    displayName: str = Field(description="Display name")
    isActive: bool = Field(description="Whether this is the current branch")
    isRemote: bool = Field(default=False, description="Whether this is a remote branch")
    ahead: int = Field(default=0, description="Number of commits ahead")
    behind: int = Field(default=0, description="Number of commits behind")
    lastCommit: Optional[BranchCommitInfo] = Field(default=None, description="Last commit information")


class VersionControlBranchListResponse(BaseModel):
    branches: List[VersionControlBranch] = Field(default_factory=list)


class FileChange(BaseModel):
    """File-level Git change."""

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


class ChangesResponse(BaseModel):
    staged: List[FileChange] = Field(default_factory=list)
    unstaged: List[FileChange] = Field(default_factory=list)
    untracked: List[FileChange] = Field(default_factory=list)
    untrackedTotal: int = Field(default=0)
    untrackedPage: int = Field(default=1)
    untrackedPageSize: int = Field(default=100)
    untrackedHasMore: bool = Field(default=False)


class StageRequest(BaseModel):
    paths: List[str] = Field(description="Paths to stage")
    includeUntracked: bool = Field(default=True, description="Whether to include untracked files")


class StageResponse(BaseModel):
    staged: List[str] = Field(default_factory=list)
    unstaged: List[str] = Field(default_factory=list)


class UnstageRequest(BaseModel):
    paths: List[str] = Field(description="Paths to unstage")


class UnstageResponse(BaseModel):
    unstaged: List[str] = Field(default_factory=list)
    remainingStaged: int = Field(default=0)


class DiscardRequest(BaseModel):
    paths: List[str] = Field(description="Paths to restore")


class DiscardResponse(BaseModel):
    discarded: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CommitSummary(BaseModel):
    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: int = Field(description="epoch ms")
    branch: Optional[str] = Field(default=None, description="Branch")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    files: int = Field(default=0)


class CommitResponse(BaseModel):
    commit: CommitSummary


class CommitListResponse(BaseModel):
    page: int = Field(description="Page number")
    pageSize: int = Field(description="Items per page")
    total: int = Field(description="Total items")
    items: List[CommitSummary] = Field(default_factory=list)


class CommitFilesResponse(BaseModel):
    commitId: str = Field(description="Commit ID")
    files: List[FileChange] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    create: bool = Field(default=False, description="Whether to create new branch")
    startPoint: Optional[str] = Field(default=None, description="New branch start point")
    stashChanges: bool = Field(default=False, description="Whether to stash before switching")


class CheckoutResponse(BaseModel):
    branch: str = Field(description="Branch after switching")
    created: bool = Field(description="Whether new branch was created")
    stashedChanges: Optional[str] = Field(default=None, description="Stash name")


class RemoteRequest(BaseModel):
    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Branch name")
    rebase: bool = Field(default=True, description="Whether to rebase during pull")
    autostash: bool = Field(default=True, description="Whether to autostash during pull")
    force: bool = Field(default=False, description="Whether to force during push")


class RemoteResponse(BaseModel):
    remote: str = Field(default="origin")
    branch: Optional[str] = None
    message: str = Field(default="")


class DiffResponse(BaseModel):
    path: str = Field(description="File path")
    patch: str = Field(default="", description="diff patch")
    diff: str = Field(default="", description="diff patch")
    binary: bool = Field(default=False, description="Whether binary")


class BlobResponse(BaseModel):
    path: str = Field(description="File path")
    revision: Optional[str] = Field(default=None, description="revision")
    content: str = Field(description="File content")
    encoding: str = Field(default="utf-8")
