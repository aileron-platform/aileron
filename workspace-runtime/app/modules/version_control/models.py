"""Version control model definitions"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CommitAuthor(BaseModel):
    """Commit author information"""

    name: str = Field(description="Author name")
    email: str = Field(description="Author email")


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
    """Git status summary"""

    branch: str = Field(description="Current branch")
    ahead: int = Field(default=0, description="Number of commits ahead of remote")
    behind: int = Field(default=0, description="Number of commits behind remote")
    detached: bool = Field(default=False, description="Whether HEAD is detached")
    hasConflicts: bool = Field(default=False, description="Whether conflicts exist")
    stagedCount: int = Field(default=0, description="Number of staged files")
    unstagedCount: int = Field(default=0, description="Number of unstaged files")
    untrackedCount: int = Field(default=0, description="Number of untracked files")
    lastFetchedAt: Optional[str] = Field(
        default=None, description="Last remote sync time (ISO8601)"
    )


class BranchCommitInfo(BaseModel):
    """Branch last commit information"""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author name")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: str = Field(description="Commit time (ISO8601)")


class BranchInfo(BaseModel):
    """Branch information"""

    name: str = Field(description="Branch full name")
    displayName: str = Field(description="Display name")
    isActive: bool = Field(description="Whether this is the active branch")
    isRemote: bool = Field(description="Whether this is a remote branch")
    ahead: int = Field(default=0, description="Number of commits ahead")
    behind: int = Field(default=0, description="Number of commits behind")
    lastCommit: Optional[BranchCommitInfo] = Field(
        default=None, description="Last commit information"
    )


class BranchListResponse(BaseModel):
    """Branch list response"""

    branches: list[BranchInfo] = Field(description="Branch list")


class CheckoutRequest(BaseModel):
    """Switch branch request"""

    create: bool = Field(default=False, description="Whether to create new branch")
    startPoint: Optional[str] = Field(
        default=None, description="New branch starting point, default is current HEAD"
    )
    stashChanges: bool = Field(default=False, description="Whether to create stash before switching")


class CheckoutResponse(BaseModel):
    """Switch branch response"""

    branch: str = Field(description="Final branch name")
    created: bool = Field(description="Whether new branch was created")
    stashedChanges: Optional[str] = Field(
        default=None, description="Name of created stash (if any)"
    )


class FileChange(BaseModel):
    """File change information"""

    name: str = Field(description="File name")
    path: str = Field(description="File relative path")
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
    additions: int = Field(default=0, description="Number of added lines")
    deletions: int = Field(default=0, description="Number of deleted lines")
    diff: Optional[str] = Field(default=None, description="Diff content (if applicable)")


class ChangesResponse(BaseModel):
    """File change response"""

    staged: list[FileChange] = Field(default_factory=list, description="Staged changes")
    unstaged: list[FileChange] = Field(default_factory=list, description="Unstaged changes")
    untracked: list[FileChange] = Field(default_factory=list, description="Untracked files")
    # Pagination info
    untrackedTotal: int = Field(default=0, description="Total number of untracked files")
    untrackedPage: int = Field(default=1, description="Current page number")
    untrackedPageSize: int = Field(default=100, description="Items per page")
    untrackedHasMore: bool = Field(default=False, description="Whether there are more files")


class StageRequest(BaseModel):
    """Stage files request"""

    paths: list[str] = Field(description="Files or directories to stage")
    includeUntracked: bool = Field(
        default=False, description="Whether to also stage untracked files"
    )


class StageResponse(BaseModel):
    """Stage files response"""

    staged: list[str] = Field(description="Successfully staged paths")
    unstaged: list[str] = Field(description="Paths that remain unstaged")


class UnstageRequest(BaseModel):
    """Unstage files request"""

    paths: list[str] = Field(description="Files or directories to unstage")


class UnstageResponse(BaseModel):
    """Unstage files response"""

    unstaged: list[str] = Field(description="Unstaged paths")
    remainingStaged: int = Field(description="Number of files still staged in index")


class DiscardRequest(BaseModel):
    """Discard unstaged changes request"""

    paths: list[str] = Field(description="Files or directories to restore")
    resetMode: Literal["soft", "mixed", "hard"] = Field(
        default="mixed", description="Git reset mode"
    )


class DiscardResponse(BaseModel):
    """Discard changes response"""

    discarded: list[str] = Field(description="Restored paths")
    warnings: list[str] = Field(default_factory=list, description="Additional warning messages")


class CommitStats(BaseModel):
    """Commit statistics"""

    additions: int = Field(description="Number of added lines")
    deletions: int = Field(description="Number of deleted lines")
    files: int = Field(description="Number of affected files")


class CommitChange(BaseModel):
    """Single file change in commit"""

    name: str = Field(description="File name")
    path: str = Field(description="File path")
    status: str = Field(description="Change status")
    additions: int = Field(description="Number of added lines")
    deletions: int = Field(description="Number of deleted lines")
    patch: Optional[str] = Field(default=None, description="Diff content")


class CommitSummary(BaseModel):
    """Commit summary information"""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: CommitAuthor = Field(description="Author information")
    timestamp: str = Field(description="Commit time (ISO8601)")
    additions: int = Field(description="Number of added lines")
    deletions: int = Field(description="Number of deleted lines")


class CommitRequest(BaseModel):
    """Create commit request"""

    message: str = Field(description="Commit message")
    author: Optional[CommitAuthor] = Field(
        default=None, description="Commit author, uses default if not provided"
    )
    amend: bool = Field(default=False, description="Whether this is an amend commit")
    paths: Optional[list[str]] = Field(
        default=None, description="Limit commit to specific files, commits entire index if not provided"
    )


class CommitResponse(BaseModel):
    """Create commit response"""

    commit: CommitSummary = Field(description="New commit information")


class CommitListItem(BaseModel):
    """Commit list item"""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author name")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: int = Field(description="Commit time (epoch ms)")
    branch: str = Field(description="Branch name")
    additions: int = Field(description="Number of added lines")
    deletions: int = Field(description="Number of deleted lines")
    files: int = Field(description="Number of affected files")


class CommitListResponse(BaseModel):
    """Commit list response"""

    page: int = Field(description="Page number")
    pageSize: int = Field(description="Items per page")
    total: int = Field(description="Total commits")
    items: list[CommitListItem] = Field(description="Commit list")


class CommitDetailResponse(BaseModel):
    """Single commit detail information"""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: CommitAuthor = Field(description="Author information")
    timestamp: str = Field(description="Commit time (ISO8601)")
    branch: str = Field(description="Branch name")
    stats: CommitStats = Field(description="Statistics information")
    changes: list[CommitChange] = Field(description="File change list")


class CommitFilesResponse(BaseModel):
    """Commit file diff response"""

    commitId: str = Field(description="Commit ID")
    files: list[CommitChange] = Field(description="File diff list")


class PushRequest(BaseModel):
    """Push request"""

    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Push target branch")
    force: bool = Field(default=False, description="Whether to force push")


class PushUpdate(BaseModel):
    """Push result information"""

    ref: str = Field(description="Updated reference")
    status: str = Field(description="Push status")


class PushResponse(BaseModel):
    """Push response"""

    remote: str = Field(description="Remote name")
    branch: str = Field(description="Pushed branch")
    updates: list[PushUpdate] = Field(description="Push result list")


class PullRequest(BaseModel):
    """Pull request"""

    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Pull branch")
    rebase: bool = Field(default=False, description="Whether to use rebase")
    autostash: bool = Field(default=False, description="Whether to auto stash changes")


class PullCommitInfo(BaseModel):
    """Commit information after pull"""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author name")


class PullResponse(BaseModel):
    """Pull response"""

    remote: str = Field(description="Remote name")
    branch: str = Field(description="Branch name")
    fastForward: bool = Field(description="Whether this is a fast-forward merge")
    commits: list[PullCommitInfo] = Field(description="New commit list")


class FetchRequest(BaseModel):
    """Sync remote references request"""

    remote: str = Field(default="origin", description="Remote name")
    prune: bool = Field(default=False, description="Whether to remove remote-deleted branches")


class FetchResponse(BaseModel):
    """Sync remote references response"""

    remote: str = Field(description="Remote name")
    fetchedRefs: list[str] = Field(description="Synced reference list")


class RemoteSettingsRequest(BaseModel):
    """Repository remote settings update request"""

    remote_url: str = Field(alias="remoteUrl", description="origin remote URL")


class RemoteSettingsResponse(BaseModel):
    """Repository remote settings response"""

    is_initialized: bool = Field(alias="isInitialized", description="Whether Git is initialized")
    current_branch: Optional[str] = Field(default=None, alias="currentBranch", description="Current branch name")
    remote_url: Optional[str] = Field(default=None, alias="remoteUrl", description="origin remote URL")
    has_origin: bool = Field(default=False, alias="hasOrigin", description="Whether origin remote exists")


class DiffResponse(BaseModel):
    """Diff result response"""

    path: str = Field(description="File path")
    base: str = Field(description="Comparison base")
    head: str = Field(description="Comparison target")
    context: int = Field(description="Context line count")
    patch: str = Field(description="Diff content")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class BlobResponse(BaseModel):
    """File content response"""

    path: str = Field(description="File path")
    revision: str = Field(description="Commit or reference")
    encoding: str = Field(default="utf-8", description="Content encoding")
    content: str = Field(description="Base64 encoded content")
    isBase64: bool = Field(default=True, description="Whether Base64 encoded")


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
    "RemoteSettingsRequest",
    "RemoteSettingsResponse",
    "StageRequest",
    "StageResponse",
    "UnstageRequest",
    "UnstageResponse",
    "VersionControlStatus",
]
