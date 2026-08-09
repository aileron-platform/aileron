from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Mapping, Optional, Tuple


class LockScope(str, Enum):
    WORKING_TREE_TARGET = "working_tree_target"
    COMMON_REPOSITORY = "common_repository"


@dataclass(frozen=True)
class LockScopeKeys:
    common_repository: str
    working_tree_target: str

    def __post_init__(self) -> None:
        if not self.common_repository or not self.working_tree_target:
            raise ValueError("Lock scope keys must not be empty")


@dataclass(frozen=True)
class RepositoryTarget:
    root: Path
    lock_scope_keys: LockScopeKeys
    environment: Mapping[str, str] = field(default_factory=dict)
    protected_branches: Tuple[str, ...] = field(default_factory=tuple)
    checked_out_branches: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ActorContext:
    display_name: str
    git_name: str
    git_email: str


class VersionControlOperation(str, Enum):
    REPOSITORY_INITIALIZE = "repository.initialize"
    REPOSITORY_CLONE = "repository.clone"
    BRANCH_CREATE_AND_SWITCH = "branch.createAndSwitch"
    BRANCH_SWITCH = "branch.switch"
    BRANCH_RENAME_LOCAL = "branch.renameLocal"
    BRANCH_DELETE_LOCAL = "branch.deleteLocal"
    BRANCH_PUBLISH = "branch.publish"
    CHANGES_STAGE_PATHS = "changes.stagePaths"
    CHANGES_UNSTAGE_PATHS = "changes.unstagePaths"
    CHANGES_STAGE_ALL = "changes.stageAll"
    CHANGES_UNSTAGE_ALL = "changes.unstageAll"
    CHANGES_DISCARD = "changes.discard"
    COMMIT_CREATE = "commit.create"
    REMOTE_FETCH = "remote.fetch"
    REMOTE_PULL_FAST_FORWARD = "remote.pullFastForward"
    REMOTE_PUSH = "remote.push"
    REMOTE_SETTINGS_UPDATE = "remote.settings.update"
    CONFLICT_MARK_RESOLVED = "conflict.markResolved"
    CONFLICT_ABORT = "conflict.abort"
    COMMIT_REVERT = "commit.revert"
    LFS_PATTERNS_UPDATE = "lfs.patterns.update"
    LFS_SNAPSHOT_PREVIEW = "lfs.snapshot.preview"
    LFS_SNAPSHOT_CONVERT = "lfs.snapshot.convert"
    OPERATION_FORCE_UNLOCK = "operation.forceUnlock"
    OPERATION_CANCEL = "operation.cancel"


_TARGET_ONLY = frozenset(
    {
        VersionControlOperation.CHANGES_STAGE_PATHS,
        VersionControlOperation.CHANGES_UNSTAGE_PATHS,
        VersionControlOperation.CHANGES_STAGE_ALL,
        VersionControlOperation.CHANGES_UNSTAGE_ALL,
        VersionControlOperation.CHANGES_DISCARD,
        VersionControlOperation.CONFLICT_MARK_RESOLVED,
        VersionControlOperation.LFS_PATTERNS_UPDATE,
        VersionControlOperation.LFS_SNAPSHOT_CONVERT,
    }
)
_COMMON_ONLY = frozenset(
    {
        VersionControlOperation.BRANCH_RENAME_LOCAL,
        VersionControlOperation.BRANCH_DELETE_LOCAL,
        VersionControlOperation.BRANCH_PUBLISH,
        VersionControlOperation.REMOTE_FETCH,
        VersionControlOperation.REMOTE_PUSH,
        VersionControlOperation.REMOTE_SETTINGS_UPDATE,
        VersionControlOperation.OPERATION_FORCE_UNLOCK,
    }
)
_BOTH = frozenset(
    {
        VersionControlOperation.REPOSITORY_INITIALIZE,
        VersionControlOperation.REPOSITORY_CLONE,
        VersionControlOperation.BRANCH_CREATE_AND_SWITCH,
        VersionControlOperation.BRANCH_SWITCH,
        VersionControlOperation.COMMIT_CREATE,
        VersionControlOperation.REMOTE_PULL_FAST_FORWARD,
        VersionControlOperation.CONFLICT_ABORT,
        VersionControlOperation.COMMIT_REVERT,
    }
)


def lock_scopes_for(operation: VersionControlOperation) -> Tuple[LockScope, ...]:
    if operation in _TARGET_ONLY:
        return (LockScope.WORKING_TREE_TARGET,)
    if operation in _COMMON_ONLY:
        return (LockScope.COMMON_REPOSITORY,)
    if operation in _BOTH:
        return (LockScope.COMMON_REPOSITORY, LockScope.WORKING_TREE_TARGET)
    if operation == VersionControlOperation.LFS_SNAPSHOT_PREVIEW:
        return ()
    if operation == VersionControlOperation.OPERATION_CANCEL:
        return ()
    raise ValueError(f"No lock classification for operation: {operation.value}")


class ReadQuery:
    query_id: ClassVar[str]


@dataclass(frozen=True)
class RepositoryStatusQuery(ReadQuery):
    query_id: ClassVar[str] = "repository.status"


@dataclass(frozen=True)
class BranchListQuery(ReadQuery):
    query_id: ClassVar[str] = "branch.list"


@dataclass(frozen=True)
class ChangesListQuery(ReadQuery):
    group: str = "all"
    cursor: Optional[str] = None
    limit: int = 100
    query_id: ClassVar[str] = "changes.list"


@dataclass(frozen=True)
class NumstatQuery(ReadQuery):
    paths: Tuple[str, ...]
    staged: bool = False
    commit_sha: Optional[str] = None
    query_id: ClassVar[str] = "changes.numstat"


@dataclass(frozen=True)
class CommitFilesQuery(ReadQuery):
    sha: str
    query_id: ClassVar[str] = "commit.files"


@dataclass(frozen=True)
class HistoryListQuery(ReadQuery):
    scope: str = "current"
    branch: Optional[str] = None
    search: Optional[str] = None
    cursor: Optional[str] = None
    limit: int = 50
    query_id: ClassVar[str] = "history.list"


@dataclass(frozen=True)
class DiffQuery(ReadQuery):
    path: str
    staged: bool = False
    commit_sha: Optional[str] = None
    query_id: ClassVar[str] = "diff.get"


@dataclass(frozen=True)
class BlobQuery(ReadQuery):
    path: str
    ref: str = "HEAD"
    query_id: ClassVar[str] = "blob.get"


@dataclass(frozen=True)
class LfsPatternsQuery(ReadQuery):
    query_id: ClassVar[str] = "lfs.patterns.get"


@dataclass(frozen=True)
class RemoteSettingsQuery(ReadQuery):
    name: str = "origin"
    query_id: ClassVar[str] = "remote.settings.get"


class MutationCommand:
    command_id: ClassVar[str]


@dataclass(frozen=True)
class RepositoryInitialize(MutationCommand):
    default_branch: str = "main"
    command_id: ClassVar[str] = VersionControlOperation.REPOSITORY_INITIALIZE.value


@dataclass(frozen=True)
class RepositoryClone(MutationCommand):
    remote_url: str
    branch: Optional[str] = None
    command_id: ClassVar[str] = VersionControlOperation.REPOSITORY_CLONE.value


@dataclass(frozen=True)
class BranchCreateAndSwitch(MutationCommand):
    name: str
    start_point: str = "HEAD"
    upstream: Optional[str] = None
    command_id: ClassVar[str] = VersionControlOperation.BRANCH_CREATE_AND_SWITCH.value


@dataclass(frozen=True)
class BranchSwitch(MutationCommand):
    name: str
    command_id: ClassVar[str] = VersionControlOperation.BRANCH_SWITCH.value


@dataclass(frozen=True)
class BranchRenameLocal(MutationCommand):
    old_name: str
    new_name: str
    command_id: ClassVar[str] = VersionControlOperation.BRANCH_RENAME_LOCAL.value


@dataclass(frozen=True)
class BranchDeleteLocal(MutationCommand):
    name: str
    command_id: ClassVar[str] = VersionControlOperation.BRANCH_DELETE_LOCAL.value


@dataclass(frozen=True)
class BranchPublish(MutationCommand):
    remote: str = "origin"
    remote_name: Optional[str] = None
    command_id: ClassVar[str] = VersionControlOperation.BRANCH_PUBLISH.value


@dataclass(frozen=True)
class PathsCommand(MutationCommand):
    paths: Tuple[str, ...]


@dataclass(frozen=True)
class StagePaths(PathsCommand):
    command_id: ClassVar[str] = VersionControlOperation.CHANGES_STAGE_PATHS.value


@dataclass(frozen=True)
class UnstagePaths(PathsCommand):
    command_id: ClassVar[str] = VersionControlOperation.CHANGES_UNSTAGE_PATHS.value


@dataclass(frozen=True)
class StageAll(MutationCommand):
    command_id: ClassVar[str] = VersionControlOperation.CHANGES_STAGE_ALL.value


@dataclass(frozen=True)
class UnstageAll(MutationCommand):
    command_id: ClassVar[str] = VersionControlOperation.CHANGES_UNSTAGE_ALL.value


@dataclass(frozen=True)
class DiscardChanges(PathsCommand):
    command_id: ClassVar[str] = VersionControlOperation.CHANGES_DISCARD.value


@dataclass(frozen=True)
class CommitCreate(MutationCommand):
    message: str
    command_id: ClassVar[str] = VersionControlOperation.COMMIT_CREATE.value


@dataclass(frozen=True)
class RemoteFetch(MutationCommand):
    remote: str = "origin"
    command_id: ClassVar[str] = VersionControlOperation.REMOTE_FETCH.value


@dataclass(frozen=True)
class RemotePullFastForward(MutationCommand):
    remote: str = "origin"
    branch: Optional[str] = None
    command_id: ClassVar[str] = VersionControlOperation.REMOTE_PULL_FAST_FORWARD.value


@dataclass(frozen=True)
class RemotePush(MutationCommand):
    remote: str = "origin"
    branch: Optional[str] = None
    command_id: ClassVar[str] = VersionControlOperation.REMOTE_PUSH.value


@dataclass(frozen=True)
class RemoteSettingsUpdate(MutationCommand):
    name: str
    url: str
    command_id: ClassVar[str] = VersionControlOperation.REMOTE_SETTINGS_UPDATE.value


@dataclass(frozen=True)
class ConflictMarkResolved(PathsCommand):
    command_id: ClassVar[str] = VersionControlOperation.CONFLICT_MARK_RESOLVED.value


@dataclass(frozen=True)
class ConflictAbort(MutationCommand):
    command_id: ClassVar[str] = VersionControlOperation.CONFLICT_ABORT.value


@dataclass(frozen=True)
class CommitRevert(MutationCommand):
    sha: str
    command_id: ClassVar[str] = VersionControlOperation.COMMIT_REVERT.value


@dataclass(frozen=True)
class LfsPatternsUpdate(MutationCommand):
    patterns: Tuple[str, ...]
    command_id: ClassVar[str] = VersionControlOperation.LFS_PATTERNS_UPDATE.value


@dataclass(frozen=True)
class LfsSnapshotPreview(MutationCommand):
    patterns: Tuple[str, ...]
    command_id: ClassVar[str] = VersionControlOperation.LFS_SNAPSHOT_PREVIEW.value


@dataclass(frozen=True)
class LfsSnapshotConvert(MutationCommand):
    paths: Tuple[str, ...]
    command_id: ClassVar[str] = VersionControlOperation.LFS_SNAPSHOT_CONVERT.value


@dataclass(frozen=True)
class OperationForceUnlock(MutationCommand):
    command_id: ClassVar[str] = VersionControlOperation.OPERATION_FORCE_UNLOCK.value


@dataclass(frozen=True)
class OperationCancel(MutationCommand):
    command_id: ClassVar[str] = VersionControlOperation.OPERATION_CANCEL.value
