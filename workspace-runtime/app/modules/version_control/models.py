"""Version control model definitions"""

from __future__ import annotations

import re
from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    branch: Optional[str] = Field(
        default=None, description="Current branch name when available"
    )
    headRef: Optional[str] = Field(
        default=None, description="Resolved HEAD ref when available"
    )
    detached: bool = Field(default=False, description="Whether HEAD is detached")
    headSha: Optional[str] = Field(default=None, description="Current HEAD commit SHA")
    locked: bool = Field(default=False, description="Whether the worktree is locked")
    prunable: bool = Field(
        default=False, description="Whether the worktree is marked prunable"
    )


class GitContextListResponse(BaseModel):
    """List of available Git contexts for a workspace."""

    activeContextId: str = Field(description="Default active Git context identifier")
    contexts: list[GitContext] = Field(description="Available Git contexts")


class VersionControlStatus(BaseModel):
    """Shared repository status wire contract."""

    model_config = ConfigDict(extra="forbid")

    isInitialized: bool
    currentBranch: Optional[str] = None
    detachedHead: bool = False
    headSha: Optional[str] = None
    hasOrigin: bool = False
    upstream: Optional[str] = None
    ahead: int = Field(default=0, description="Number of commits ahead of remote")
    behind: int = Field(default=0, description="Number of commits behind remote")
    hasConflicts: bool = Field(default=False, description="Whether conflicts exist")
    stagedTotal: int = Field(default=0, description="Number of staged files")
    unstagedTotal: int = Field(default=0, description="Number of unstaged files")
    untrackedTotal: int = Field(default=0, description="Number of untracked files")
    conflictTotal: int = Field(default=0, description="Number of conflicted files")
    operationStatus: Optional["VersionControlOperationStatus"] = None


class VersionControlRepositoryStatus(BaseModel):
    """Repository initialization and clone-safety status."""

    isGitRepo: bool = Field(description="Whether the workspace root is a Git repository")
    currentBranch: Optional[str] = Field(
        default=None, description="Current branch when the repository is initialized"
    )
    remoteUrl: Optional[str] = Field(
        default=None, description="Origin remote URL when configured"
    )
    hasOrigin: bool = Field(description="Whether the origin remote is configured")
    hasLocalContent: bool = Field(
        description="Whether the workspace root contains local content"
    )
    canCloneSafely: bool = Field(
        description="Whether a repository can be cloned into the workspace root"
    )
    canInitSafely: bool = Field(
        description="Whether Git can be initialized in the workspace root"
    )
    cloneBlockedReason: Optional[str] = Field(
        default=None, description="Stable error code explaining why clone is blocked"
    )


class RemoteRepositoryRequest(BaseModel):
    """Remote repository request."""

    remoteUrl: str = Field(
        min_length=1,
        max_length=2048,
        description="Remote repository URL",
    )

    @field_validator("remoteUrl")
    @classmethod
    def validate_remote_url(cls, value: str) -> str:
        normalized = value.strip()
        scp_style_ssh = re.fullmatch(
            r"[^@\s/:]+@[A-Za-z0-9._-]+:[^\s]+",
            normalized,
        )
        if scp_style_ssh:
            return normalized

        try:
            parsed = urlsplit(normalized)
        except ValueError as exc:
            raise ValueError("Invalid repository URL") from exc

        if (
            parsed.scheme not in {"http", "https", "ssh"}
            or not parsed.hostname
            or parsed.path in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Only HTTP(S) and SSH repository URLs are supported")
        if parsed.scheme in {"http", "https"} and (
            parsed.username or parsed.password
        ):
            raise ValueError("Repository URL must not contain credentials")
        if parsed.password:
            raise ValueError("Repository URL must not contain credentials")
        return normalized


class CloneRepositoryRequest(RemoteRepositoryRequest):
    """Clone repository request."""

    branch: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Remote branch to clone",
    )

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or any(character in normalized for character in "\0\r\n"):
            raise ValueError("Invalid branch name")
        return normalized


class RepositoryInitializeRequest(BaseModel):
    """Initialize a repository with the requested default branch."""

    model_config = ConfigDict(extra="forbid")

    defaultBranch: str = Field(min_length=1, max_length=255)

    @field_validator("defaultBranch")
    @classmethod
    def validate_default_branch(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(character in normalized for character in "\0\r\n"):
            raise ValueError("Invalid branch name")
        return normalized


class RemoteBranchesResponse(BaseModel):
    """Branches available from a remote repository."""

    branches: list[str] = Field(default_factory=list)
    defaultBranch: Optional[str] = Field(
        default=None,
        description="Remote default branch",
    )


class VersionControlOperationStatus(BaseModel):
    """Shared currently running version-control operation contract."""

    model_config = ConfigDict(extra="forbid")

    isActive: bool = Field(description="Whether a version control operation is active")
    operation: Optional[str] = Field(
        default=None, description="Current operation name when active"
    )
    actorDisplayName: Optional[str] = None
    startedAt: Optional[str] = Field(
        default=None, description="Operation start time (ISO8601)"
    )
    blockingScope: Optional[
        Literal["working_tree_target", "common_repository"]
    ] = None
    stale: bool = False
    retryable: bool = True
    progressCurrent: int = 0
    progressTotal: int = 0
    phase: str = ""
    cancellable: bool = False
    cancelRequested: bool = False


class BranchCapability(BaseModel):
    """Availability of one branch action."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    allowed: bool
    disabledReasonKey: Optional[str] = None


class BranchCapabilities(BaseModel):
    """Branch actions decided by the shared Git application."""

    model_config = ConfigDict(extra="forbid")

    switch: BranchCapability
    rename: BranchCapability
    delete: BranchCapability


class BranchInfo(BaseModel):
    """Branch information"""

    model_config = ConfigDict(extra="forbid")

    name: str
    displayName: str
    kind: Literal["local", "remote"]
    isCurrent: bool
    upstream: Optional[str] = None
    ahead: int = Field(default=0, description="Number of commits ahead")
    behind: int = Field(default=0, description="Number of commits behind")
    checkedOutTarget: Optional[str] = None
    capabilities: BranchCapabilities


class BranchListResponse(BaseModel):
    """Branch list response"""

    branches: list[BranchInfo] = Field(description="Branch list")


class BranchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    startPoint: str = Field(default="HEAD")
    upstream: Optional[str] = None


class BranchSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class BranchRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oldName: str = Field(min_length=1)
    newName: str = Field(min_length=1)


class BranchDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class BranchPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remote: str = Field(default="origin", min_length=1)
    remoteName: Optional[str] = None


class BranchMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commandId: str
    headSha: Optional[str] = None
    branch: Optional[str] = None
    affectedTotal: int = 0
    skippedTotal: int = 0
    output: str = ""


class LfsPatternsUpdateRequest(BaseModel):
    """Repository-wide LFS pattern update request."""

    model_config = ConfigDict(extra="forbid")

    patterns: Optional[list[str]] = None


class LfsPatternsResponse(BaseModel):
    """Repository-wide LFS patterns response."""

    model_config = ConfigDict(extra="forbid")

    patterns: list[str] = Field(default_factory=list)


class LfsSnapshotPreviewRequest(BaseModel):
    """Repository LFS snapshot preview request."""

    model_config = ConfigDict(extra="forbid")

    patterns: Optional[list[str]] = None


class LfsSnapshotPreviewResponse(BaseModel):
    """Repository LFS snapshot preview response."""

    model_config = ConfigDict(extra="forbid")

    matchedTotal: int = 0
    totalSize: int = 0
    pathSample: list[str] = Field(default_factory=list)


class LfsSnapshotConvertRequest(BaseModel):
    """Repository LFS snapshot conversion request."""

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(min_length=1)


class ConflictPathsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(min_length=1)


class RevertCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str = Field(min_length=1)


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
    additions: Optional[int] = Field(default=None, description="Number of added lines")
    deletions: Optional[int] = Field(
        default=None, description="Number of deleted lines"
    )
    diff: Optional[str] = Field(
        default=None, description="Diff content (if applicable)"
    )
    oldPath: Optional[str] = Field(default=None, description="Path before rename")


class ChangePage(BaseModel):
    """One independently cursor-paged change group."""

    model_config = ConfigDict(extra="forbid")

    items: list[FileChange] = Field(default_factory=list)
    total: int = 0
    nextCursor: Optional[str] = None
    hasMore: bool = False


class ChangesResponse(BaseModel):
    """Shared paged changes wire contract."""

    model_config = ConfigDict(extra="forbid")

    staged: ChangePage = Field(default_factory=ChangePage)
    unstaged: ChangePage = Field(default_factory=ChangePage)
    untracked: ChangePage = Field(default_factory=ChangePage)
    conflicts: ChangePage = Field(default_factory=ChangePage)


class NumstatRequest(BaseModel):
    """Request body for the deferred numstat endpoint.

    Clients send the visible/paged staged + unstaged paths so the server can
    compute additions/deletions only for what the user actually sees, avoiding
    the expensive staged numstat on the initial changes fast path.
    """

    stagedPaths: list[str] = Field(
        default_factory=list, description="Staged file paths"
    )
    unstagedPaths: list[str] = Field(
        default_factory=list, description="Unstaged file paths"
    )


class NumstatResponse(BaseModel):
    """Deferred numstat response: a map of path to {additions, deletions}."""

    stats: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Map of file path to {additions, deletions}",
    )


class StageRequest(BaseModel):
    """Stage files request"""

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(
        default_factory=list, description="Files or directories to stage"
    )
    all: bool = Field(default=False, description="Whether to stage all changes")


class StageResponse(BaseModel):
    """Stage files response"""

    staged: list[str] = Field(description="Successfully staged paths")
    unstaged: list[str] = Field(description="Paths that remain unstaged")


class UnstageRequest(BaseModel):
    """Unstage files request"""

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(
        default_factory=list, description="Files or directories to unstage"
    )
    all: bool = Field(default=False, description="Whether to unstage all changes")


class UnstageResponse(BaseModel):
    """Unstage files response"""

    unstaged: list[str] = Field(description="Unstaged paths")
    remainingStaged: int = Field(description="Number of files still staged in index")


class DiscardRequest(BaseModel):
    """Discard unstaged changes request"""

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(description="Files or directories to restore")


class DiscardResponse(BaseModel):
    """Discard changes response"""

    discarded: list[str] = Field(description="Restored paths")
    warnings: list[str] = Field(
        default_factory=list, description="Additional warning messages"
    )


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

    model_config = ConfigDict(extra="forbid")

    message: str = Field(description="Commit message")


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
    """Shared cursor-paged commit history response."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(description="Total commits")
    items: list[CommitListItem] = Field(description="Commit list")
    nextCursor: Optional[str] = None
    hasMore: bool = False
    queryScope: Literal["current", "all", "local", "remote"]


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

    model_config = ConfigDict(extra="forbid")

    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Push target branch")


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

    model_config = ConfigDict(extra="forbid")

    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Pull branch")


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
    prune: bool = Field(
        default=False, description="Whether to remove remote-deleted branches"
    )


class FetchResponse(BaseModel):
    """Sync remote references response"""

    remote: str = Field(description="Remote name")
    fetchedRefs: list[str] = Field(description="Synced reference list")


class RemoteSettingsRequest(BaseModel):
    """Repository remote settings update request"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    remote_url: str = Field(alias="remoteUrl", description="origin remote URL")


class RemoteSettingsResponse(BaseModel):
    """Repository remote settings response"""

    model_config = ConfigDict(extra="forbid")

    remoteName: str
    remoteUrl: Optional[str] = None
    hasOrigin: bool = False


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
    "BranchCapabilities",
    "BranchCapability",
    "BranchCreateRequest",
    "BranchDeleteRequest",
    "BranchInfo",
    "BranchListResponse",
    "BranchMutationResponse",
    "BranchPublishRequest",
    "BranchRenameRequest",
    "BranchSwitchRequest",
    "ChangePage",
    "ChangesResponse",
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
    "ConflictPathsRequest",
    "DiffResponse",
    "DiscardRequest",
    "DiscardResponse",
    "FetchRequest",
    "FetchResponse",
    "FileChange",
    "GitContext",
    "GitContextListResponse",
    "LfsPatternsResponse",
    "LfsPatternsUpdateRequest",
    "LfsSnapshotConvertRequest",
    "LfsSnapshotPreviewRequest",
    "LfsSnapshotPreviewResponse",
    "NumstatRequest",
    "NumstatResponse",
    "PullCommitInfo",
    "PullRequest",
    "PullResponse",
    "PushRequest",
    "PushResponse",
    "PushUpdate",
    "RemoteSettingsRequest",
    "RemoteSettingsResponse",
    "RepositoryInitializeRequest",
    "RevertCommitRequest",
    "StageRequest",
    "StageResponse",
    "UnstageRequest",
    "UnstageResponse",
    "VersionControlOperationStatus",
    "VersionControlStatus",
]
