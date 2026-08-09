"""Shared Git version control data models."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class GitCommitRequest(BaseModel):
    """Git commit request."""

    message: str = Field(..., min_length=1, description="Commit message")

    model_config = ConfigDict(extra="forbid")


class LfsPatternsUpdateRequest(BaseModel):
    """Shared repository-wide LFS pattern update request."""

    patterns: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")


class LfsPatternsResponse(BaseModel):
    patterns: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LfsSnapshotPreviewRequest(BaseModel):
    patterns: Optional[List[str]] = None

    model_config = ConfigDict(extra="forbid")


class LfsSnapshotPreviewResponse(BaseModel):
    matchedTotal: int = 0
    totalSize: int = 0
    pathSample: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LfsSnapshotConvertRequest(BaseModel):
    paths: List[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class RemoteSettingsResponse(BaseModel):
    remoteName: str
    remoteUrl: Optional[str] = None
    hasOrigin: bool = False

    model_config = ConfigDict(extra="forbid")


class RepositoryInitializeRequest(BaseModel):
    """Shared repository initialize request."""

    default_branch: str = Field("main", alias="defaultBranch")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class GitRemoteUrlRequest(BaseModel):
    """Set Git remote repository URL request."""

    url: str = Field(
        ..., min_length=1, alias="remoteUrl", description="Remote repository URL"
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class GitRepositoryStatus(BaseModel):
    """Git repository lifecycle status."""

    is_git_repo: bool = Field(
        ..., alias="isGitRepo", description="Whether initialized as Git repository"
    )
    current_branch: Optional[str] = Field(
        None, alias="currentBranch", description="Current branch"
    )
    remote_url: Optional[str] = Field(None, alias="remoteUrl", description="origin URL")
    has_origin: bool = Field(
        False, alias="hasOrigin", description="Whether origin is set"
    )
    has_local_content: bool = Field(
        False, alias="hasLocalContent", description="Whether there is local content"
    )
    can_clone_safely: bool = Field(
        False, alias="canCloneSafely", description="Whether clone can be done safely"
    )
    can_init_safely: bool = Field(
        False, alias="canInitSafely", description="Whether init can be done safely"
    )
    clone_blocked_reason: Optional[str] = Field(
        None, alias="cloneBlockedReason", description="Reason why clone is blocked"
    )

    model_config = ConfigDict(populate_by_name=True)


class RemoteBranchesRequest(BaseModel):
    remote_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        alias="remoteUrl",
        description="Remote repository URL",
    )

    model_config = ConfigDict(populate_by_name=True)


class RemoteBranchesResponse(BaseModel):
    branches: List[str] = Field(default_factory=list)
    default_branch: Optional[str] = Field(
        default=None,
        alias="defaultBranch",
        description="Remote default branch",
    )

    model_config = ConfigDict(populate_by_name=True)


class VersionControlStatus(BaseModel):
    """Shared repository status wire contract."""

    isInitialized: bool
    currentBranch: Optional[str] = None
    detachedHead: bool = False
    headSha: Optional[str] = None
    hasOrigin: bool = False
    upstream: Optional[str] = None
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    hasConflicts: bool = Field(default=False, description="Whether there are conflicts")
    stagedTotal: int = Field(default=0, description="Number of staged files")
    unstagedTotal: int = Field(default=0, description="Number of unstaged files")
    untrackedTotal: int = Field(default=0, description="Number of untracked files")
    conflictTotal: int = Field(default=0, description="Number of conflicted files")
    operationStatus: Optional["VersionControlOperationStatus"] = None

    model_config = ConfigDict(extra="forbid")


class VersionControlOperationStatus(BaseModel):
    """Shared currently running version-control operation contract."""

    isActive: bool = Field(description="Whether a version control operation is active")
    operation: Optional[str] = Field(
        default=None, description="Current operation name when active"
    )
    actorDisplayName: Optional[str] = None
    startedAt: Optional[str] = Field(
        default=None, description="Operation start time (ISO8601)"
    )
    blockingScope: Optional[Literal[
        "working_tree_target", "common_repository"
    ]] = None
    stale: bool = False
    retryable: bool = True
    progressCurrent: int = 0
    progressTotal: int = 0
    phase: str = ""
    cancellable: bool = False
    cancelRequested: bool = False

    model_config = ConfigDict(extra="forbid")


class BranchCommitInfo(BaseModel):
    """Branch last commit summary."""

    id: str = Field(description="Commit ID")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author")
    email: Optional[str] = Field(default=None, description="Author email")
    timestamp: str = Field(description="ISO8601 commit time")


class BranchCapability(BaseModel):
    allowed: bool
    disabled_reason_key: Optional[str] = Field(None, alias="disabledReasonKey")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BranchCapabilities(BaseModel):
    switch: BranchCapability
    rename: BranchCapability
    delete: BranchCapability

    model_config = ConfigDict(extra="forbid")


class VersionControlBranch(BaseModel):
    """Shared local or remote branch summary."""

    name: str
    display_name: str = Field(alias="displayName")
    kind: Literal["local", "remote"]
    is_current: bool = Field(alias="isCurrent")
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    checked_out_target: Optional[str] = Field(None, alias="checkedOutTarget")
    capabilities: BranchCapabilities

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


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
    # Optional so a changes fast path can defer numstat (null additions/deletions)
    # and fill it later via the /changes/numstat endpoint.
    additions: Optional[int] = Field(default=None, description="Number of lines added")
    deletions: Optional[int] = Field(
        default=None, description="Number of lines deleted"
    )
    diff: Optional[str] = Field(default=None, description="Difference content")
    patch: Optional[str] = Field(default=None, description="Difference content")


class VersionControlChangePage(BaseModel):
    items: List[FileChange] = Field(default_factory=list)
    total: int = 0
    nextCursor: Optional[str] = None
    hasMore: bool = False

    model_config = ConfigDict(extra="forbid")


class VersionControlChangesResponse(BaseModel):
    """Shared cursor-paged changes wire contract."""

    staged: VersionControlChangePage = Field(default_factory=VersionControlChangePage)
    unstaged: VersionControlChangePage = Field(default_factory=VersionControlChangePage)
    untracked: VersionControlChangePage = Field(default_factory=VersionControlChangePage)
    conflicts: VersionControlChangePage = Field(default_factory=VersionControlChangePage)

    model_config = ConfigDict(extra="forbid")


class NumstatEntry(BaseModel):
    """Per-file additions/deletions for the deferred numstat endpoint."""

    additions: int = Field(default=0)
    deletions: int = Field(default=0)


class NumstatRequest(BaseModel):
    """Request body for the deferred numstat endpoint.

    Clients send the visible staged + unstaged paths so the server computes
    additions/deletions only for what the user sees, avoiding the expensive
    numstat on the initial changes fast path.
    """

    stagedPaths: List[str] = Field(default_factory=list)
    unstagedPaths: List[str] = Field(default_factory=list)


class NumstatResponse(BaseModel):
    """Deferred numstat response: a map of path to {additions, deletions}."""

    stats: dict = Field(
        default_factory=dict, description="path -> {additions, deletions}"
    )


class StageRequest(BaseModel):
    paths: List[str] = Field(default_factory=list, description="Paths to stage")
    all: bool = Field(default=False, description="Whether to stage all changes")

    model_config = ConfigDict(extra="forbid")


class StageResponse(BaseModel):
    staged: List[str] = Field(default_factory=list)
    unstaged: List[str] = Field(default_factory=list)


class UnstageRequest(BaseModel):
    paths: List[str] = Field(default_factory=list, description="Paths to unstage")
    all: bool = Field(default=False, description="Whether to unstage all changes")

    model_config = ConfigDict(extra="forbid")


class UnstageResponse(BaseModel):
    unstaged: List[str] = Field(default_factory=list)
    remainingStaged: int = Field(default=0)


class DiscardRequest(BaseModel):
    paths: List[str] = Field(description="Paths to restore")

    model_config = ConfigDict(extra="forbid")


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
    items: List[CommitSummary] = Field(default_factory=list)
    total: int = Field(description="Total items")
    nextCursor: Optional[str] = None
    hasMore: bool = False
    queryScope: Literal["current", "all", "local", "remote"] = "current"

    model_config = ConfigDict(extra="forbid")


class CommitFilesResponse(BaseModel):
    commitId: str = Field(description="Commit ID")
    files: List[FileChange] = Field(default_factory=list)


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    start_point: str = Field("HEAD", alias="startPoint")
    upstream: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BranchSwitchRequest(BaseModel):
    name: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class BranchRenameRequest(BaseModel):
    old_name: str = Field(min_length=1, alias="oldName")
    new_name: str = Field(min_length=1, alias="newName")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BranchDeleteRequest(BaseModel):
    name: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class BranchPublishRequest(BaseModel):
    remote: str = Field("origin", min_length=1)
    remote_name: Optional[str] = Field(None, alias="remoteName")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BranchMutationResponse(BaseModel):
    command_id: str = Field(alias="commandId")
    head_sha: Optional[str] = Field(None, alias="headSha")
    branch: Optional[str] = None
    affected_total: int = Field(0, alias="affectedTotal")
    skipped_total: int = Field(0, alias="skippedTotal")
    output: str = ""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ConflictPathsRequest(BaseModel):
    paths: List[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class CommitRevertRequest(BaseModel):
    sha: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class RemoteRequest(BaseModel):
    remote: str = Field(default="origin", description="Remote name")
    branch: Optional[str] = Field(default=None, description="Branch name")

    model_config = ConfigDict(extra="forbid")


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
