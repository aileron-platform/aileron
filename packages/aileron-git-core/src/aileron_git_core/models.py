from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple

from .contracts import LockScope

if TYPE_CHECKING:
    from .mutations import CommitSummary


class OperationKind(str, Enum):
    READ = "read"
    WRITE = "write"
    WORKING_TREE = "working-tree"
    REMOTE = "remote"


@dataclass(frozen=True)
class OperationMetadata:
    operation_id: str
    key: str
    kind: OperationKind
    operation_name: str
    blocking: bool
    cache_effects: Tuple[str, ...] = field(default_factory=tuple)
    actor_display_name: str = ""
    blocking_scope: Optional[LockScope] = None
    stale: bool = False
    retryable: bool = True
    progress_current: int = 0
    progress_total: int = 0
    phase: str = ""
    cancellable: bool = False
    cancel_requested: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str
    type: str
    raw_status: Optional[str] = None
    original_path: Optional[str] = None


@dataclass(frozen=True)
class GitStatus:
    staged: List[FileChange] = field(default_factory=list)
    unstaged: List[FileChange] = field(default_factory=list)
    untracked: List[FileChange] = field(default_factory=list)
    conflicts: List[FileChange] = field(default_factory=list)


@dataclass(frozen=True)
class Capability:
    allowed: bool
    disabled_reason_key: Optional[str] = None


@dataclass(frozen=True)
class BranchCapabilities:
    switch: Capability
    rename: Capability
    delete: Capability


@dataclass(frozen=True)
class BranchSummary:
    name: str
    display_name: str
    kind: str
    is_current: bool
    upstream: Optional[str]
    ahead: int
    behind: int
    checked_out_target: Optional[str]
    capabilities: BranchCapabilities


@dataclass(frozen=True)
class BranchList:
    branches: List[BranchSummary]


@dataclass(frozen=True)
class RepositoryStatus:
    is_initialized: bool
    current_branch: Optional[str]
    detached_head: bool
    head_sha: Optional[str]
    has_origin: bool
    upstream: Optional[str]
    ahead: int
    behind: int
    has_conflicts: bool
    staged_total: int
    unstaged_total: int
    untracked_total: int
    conflict_total: int
    operation_status: Optional[OperationMetadata] = None


@dataclass(frozen=True)
class MutationResult:
    command_id: str
    head_sha: Optional[str] = None
    branch: Optional[str] = None
    affected_total: int = 0
    skipped_total: int = 0
    output: str = ""
    paths: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ChangePage:
    items: List[FileChange]
    total: int
    next_cursor: Optional[str]
    has_more: bool


@dataclass(frozen=True)
class PagedChanges:
    staged: ChangePage
    unstaged: ChangePage
    untracked: ChangePage
    conflicts: ChangePage


@dataclass(frozen=True)
class CommitHistoryPage:
    items: List["CommitSummary"]
    total: int
    next_cursor: Optional[str]
    has_more: bool
    query_scope: str


@dataclass(frozen=True)
class DiffResult:
    path: str
    patch: str


@dataclass(frozen=True)
class BlobResult:
    path: str
    ref: str
    content: str


@dataclass(frozen=True)
class LfsPatterns:
    patterns: Tuple[str, ...]


@dataclass(frozen=True)
class LfsSnapshotPreviewResult:
    matched_total: int
    total_size: int
    path_sample: Tuple[str, ...]


@dataclass(frozen=True)
class RemoteSettings:
    remote_name: str
    remote_url: Optional[str]
    has_origin: bool


@dataclass(frozen=True)
class NumstatEntry:
    path: str
    additions: int
    deletions: int
    binary: bool


@dataclass(frozen=True)
class NumstatResult:
    entries: List[NumstatEntry]


@dataclass(frozen=True)
class CommitFileDetail:
    path: str
    original_path: Optional[str]
    status: str
    additions: int
    deletions: int
    binary: bool
    patch: str


@dataclass(frozen=True)
class CommitFilesResult:
    sha: str
    files: List[CommitFileDetail]
