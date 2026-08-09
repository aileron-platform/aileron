"""Knowledge base scoped Git version control service."""

from __future__ import annotations

import difflib
import functools
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Optional, TypeVar
from uuid import uuid4

from aileron_git_core import (
    DEFAULT_LFS_PATTERNS,
    BlobQuery,
    BranchCreateAndSwitch,
    BranchDeleteLocal,
    BranchListQuery,
    BranchPublish,
    BranchRenameLocal,
    BranchSwitch,
    ChangesListQuery,
    CommitCreate,
    CommitFilesQuery,
    CommitRevert,
    ConflictAbort,
    ConflictMarkResolved,
    DiffQuery,
    DiscardChanges,
    GitOperationInProgressError,
    GitStaleLockError,
    HistoryListQuery,
    LfsPatternsQuery,
    LfsPatternsUpdate,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
    LockScope,
    NumstatQuery,
    OperationCancel,
    OperationForceUnlock,
    OperationKind,
    RemoteFetch,
    RemotePullFastForward,
    RemotePush,
    RemoteSettingsQuery,
    RemoteSettingsUpdate,
    RepositoryClone,
    RepositoryInitialize,
    RepositoryStatusQuery,
    StageAll,
    StagePaths,
    UnstageAll,
    UnstagePaths,
    VersionControlApplication,
    VersionControlError,
    run_git,
    run_operation,
    to_change_dict,
)
from aileron_git_core import CommitSummary as CoreCommitSummary
from aileron_git_core import list_commits as core_list_commits
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.access import KnowledgeBaseService
from app.modules.knowledge_base.git_operations import (
    KB_GIT_OPERATION_IN_PROGRESS,
    KB_GIT_OPERATION_MANAGER,
    kb_git_operation_key,
)
from app.modules.knowledge_base.models import KnowledgeBaseGitCloneRequest
from app.modules.knowledge_base.storage import ensure_knowledge_base_storage_root
from app.modules.platform_resource_analytics.analytics import PlatformResourceActivityLedger
from app.modules.version_control.application import (
    ManagerActorContextResolver,
    version_control_status_from_core,
)
from app.modules.version_control.local_history import ManagerLocalHistoryService
from app.modules.version_control.models import (
    BlobResponse,
    BranchMutationResponse,
    CommitFilesResponse,
    CommitListResponse,
    CommitResponse,
    CommitSummary,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FileChange,
    GitRepositoryStatus,
    LfsPatternsResponse,
    LfsSnapshotPreviewResponse,
    NumstatResponse,
    RemoteBranchesResponse,
    RemoteRequest,
    RemoteResponse,
    RemoteSettingsResponse,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlBranch,
    VersionControlBranchListResponse,
    VersionControlChangePage,
    VersionControlChangesResponse,
    VersionControlOperationStatus,
    VersionControlStatus,
)
from app.modules.version_control.remote import (
    discover_remote_branches,
    user_git_environment,
    validate_clone_remote_url,
)
from app.modules.version_control.target import KnowledgeBaseRepositoryTargetResolver

logger = logging.getLogger(__name__)

KB_VERSION_CONTROL_DISABLED = "KB_VERSION_CONTROL_DISABLED"
VC_CLONE_TARGET_NOT_EMPTY = "VC_CLONE_TARGET_NOT_EMPTY"
T = TypeVar("T")


def _kb_git_operation_key(kb_id: str) -> str:
    return kb_git_operation_key(kb_id)


def _kb_git_operation(
    kind: OperationKind, operation_name: str
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(method: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(method)
        def wrapper(self: "KnowledgeBaseGitService", *args: Any, **kwargs: Any) -> T:
            return self._run_operation(
                kb_id=kwargs["kb_id"],
                kind=kind,
                operation_name=operation_name,
                callback=lambda: method(self, *args, **kwargs),
            )

        return wrapper

    return decorator


class KnowledgeBaseGitService:
    """Manage optional Git operations for a single knowledge base repository."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        history_root = getattr(self.settings, "MANAGER_LOCAL_HISTORY_DIR", None)
        if not isinstance(history_root, str) or not history_root:
            history_root = str(self.storage_root.parent / "local-history")
        self.local_history = ManagerLocalHistoryService(history_root=Path(history_root))
        self._stale_threshold = self.settings.GIT_STALE_LOCK_THRESHOLD_SECONDS
        self.version_control = VersionControlApplication(
            KB_GIT_OPERATION_MANAGER,
            stale_threshold_seconds=self._stale_threshold,
        )

    def _run_operation(
        self,
        *,
        kb_id: str,
        kind: OperationKind,
        operation_name: str,
        callback: Callable[[], T],
    ) -> T:
        key = _kb_git_operation_key(kb_id)
        try:
            return run_operation(
                KB_GIT_OPERATION_MANAGER,
                key=key,
                kind=kind,
                operation_name=operation_name,
                repo_root=self._kb_root(kb_id),
                callback=callback,
                stale_threshold_seconds=self._stale_threshold,
            )
        except GitStaleLockError:
            # Stale on-disk git lock that could not be auto-cleared: the
            # client is allowed to force-unlock.
            raise VersionControlError(
                KB_GIT_OPERATION_IN_PROGRESS,
                blocking_scope=LockScope.COMMON_REPOSITORY,
                stale=True,
                can_force_unlock=True,
            )
        except GitOperationInProgressError:
            # Active in-process lock collision: not stale, cannot force-unlock.
            raise VersionControlError(
                KB_GIT_OPERATION_IN_PROGRESS,
                blocking_scope=LockScope.COMMON_REPOSITORY,
            )

    def enable(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        default_branch: str = "main",
    ) -> VersionControlStatus:
        """Enable Git version control for a KB."""
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        if self.version_control.read(
            self._target(kb.id), RepositoryStatusQuery()
        ).is_initialized:
            raise ValueError("VC_REPOSITORY_ALREADY_INITIALIZED")
        self.version_control.execute(
            self._target(kb.id), RepositoryInitialize(default_branch)
        )
        kb.version_control_enabled = True
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        return self.get_version_control_status(actor=actor, kb_id=kb_id)

    def clone(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        payload: KnowledgeBaseGitCloneRequest,
    ) -> VersionControlStatus:
        """Clone a remote repository directly into the knowledge base root."""
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        root = self._kb_root(kb.id)
        if any(root.iterdir()):
            raise ValueError(VC_CLONE_TARGET_NOT_EMPTY)

        remote_url = validate_clone_remote_url(payload.remote_url)
        clone_published = False
        try:
            with user_git_environment(
                self.db,
                user_id=actor.user_id,
                remote_url=remote_url,
            ) as git_env:
                self.version_control.execute(
                    self._target(kb.id, environment=git_env),
                    RepositoryClone(remote_url, payload.branch),
                )
                clone_published = True

            kb.version_control_enabled = True
            kb.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(kb)
        except Exception:
            self.db.rollback()
            if clone_published:
                for entry in root.iterdir():
                    if entry.is_dir() and not entry.is_symlink():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
            raise
        return self.get_version_control_status(actor=actor, kb_id=kb_id)

    @_kb_git_operation(OperationKind.READ, "remote_branches")
    def remote_branches(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        remote_url: str,
    ) -> RemoteBranchesResponse:
        """List branches available from a remote knowledge base repository."""
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        result = discover_remote_branches(
            self.db,
            user_id=actor.user_id,
            repo_root=self._kb_root(kb.id),
            remote_url=remote_url,
        )
        return RemoteBranchesResponse(
            branches=result.branches,
            defaultBranch=result.default_branch,
        )

    def update_lfs_patterns(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        patterns: Optional[list[str]] = None,
    ) -> BranchMutationResponse:
        """Update Git LFS tracking patterns."""
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        self._require_repo(kb)
        target = self._target(kb.id)
        result = self.version_control.execute(
            target,
            LfsPatternsUpdate(tuple(patterns or DEFAULT_LFS_PATTERNS)),
        )
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def get_lfs_patterns(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> LfsPatternsResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        result = self.version_control.read(self._target(kb.id), LfsPatternsQuery())
        return LfsPatternsResponse(patterns=list(result.patterns))

    def preview_lfs_snapshot(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        patterns: Optional[list[str]] = None,
    ) -> LfsSnapshotPreviewResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        self._require_repo(kb)
        target = self._target(kb.id)
        selected_patterns = patterns
        if selected_patterns is None:
            selected_patterns = list(
                self.version_control.read(target, LfsPatternsQuery()).patterns
            )
        result = self.version_control.execute(
            target,
            LfsSnapshotPreview(tuple(selected_patterns)),
        )
        return LfsSnapshotPreviewResponse(
            matchedTotal=result.matched_total,
            totalSize=result.total_size,
            pathSample=list(result.path_sample),
        )

    def convert_lfs_snapshot(
        self, *, actor: AuthorizationActor, kb_id: str, paths: list[str]
    ) -> BranchMutationResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        self._require_repo(kb)
        result = self.version_control.execute(
            self._target(kb.id),
            LfsSnapshotConvert(tuple(self._safe_repo_paths(kb.id, paths))),
        )
        return self._branch_mutation_response(result)

    def cancel_operation(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> BranchMutationResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        if not (self._kb_root(kb.id) / ".git").is_dir():
            raise ValueError("GIT_REPO_NOT_FOUND")
        result = self.version_control.execute(self._target(kb.id), OperationCancel())
        return self._branch_mutation_response(result)

    @_kb_git_operation(OperationKind.READ, "repository_status")
    def repository_status(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> GitRepositoryStatus:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        root = self._kb_root(kb.id)
        status = self.version_control.read(self._target(kb.id), RepositoryStatusQuery())
        if not status.is_initialized:
            has_local_content = root.exists() and any(root.iterdir())
            return GitRepositoryStatus(
                is_git_repo=False,
                current_branch=None,
                remote_url=None,
                has_origin=False,
                has_local_content=has_local_content,
                can_clone_safely=not has_local_content,
                can_init_safely=True,
                clone_blocked_reason=(
                    VC_CLONE_TARGET_NOT_EMPTY if has_local_content else None
                ),
            )
        remote_url = self._origin_url(root)
        return GitRepositoryStatus(
            is_git_repo=True,
            current_branch=status.current_branch,
            remote_url=remote_url,
            has_origin=bool(remote_url),
            has_local_content=True,
            can_clone_safely=False,
            can_init_safely=False,
            clone_blocked_reason="VC_REPOSITORY_ALREADY_INITIALIZED",
        )

    def get_version_control_status(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> VersionControlStatus:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        status = self.version_control.read(
            self._target(kb.id),
            RepositoryStatusQuery(),
        )
        return version_control_status_from_core(status)

    def get_file_changes(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        cursor: Optional[str] = None,
        limit: int = 100,
        group: Literal["all", "staged", "unstaged", "untracked", "conflicts"] = "all",
        include_stats: bool = True,
    ) -> VersionControlChangesResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        changes = self.version_control.read(
            self._target(kb.id),
            ChangesListQuery(group=group, cursor=cursor, limit=limit),
        )
        staged = [FileChange(**to_change_dict(item)) for item in changes.staged.items]
        unstaged = [FileChange(**to_change_dict(item)) for item in changes.unstaged.items]
        untracked = [FileChange(**to_change_dict(item)) for item in changes.untracked.items]
        conflicts = [
            FileChange(**to_change_dict(item)) for item in changes.conflicts.items
        ]

        # Deferred numstat: skip the per-change git diff on the changes fast path
        # and fill it later via /changes/numstat for the visible paths only.
        if include_stats:
            stats = {
                item.path: (item.additions, item.deletions)
                for query in (
                    NumstatQuery(tuple(item.path for item in staged), staged=True),
                    NumstatQuery(tuple(item.path for item in unstaged), staged=False),
                )
                for item in self.version_control.read(
                    self._target(kb.id), query
                ).entries
            }
            for file_change in staged:
                stat = self._lookup_numstat(stats, file_change)
                if stat is not None:
                    file_change.additions, file_change.deletions = stat
            for file_change in unstaged:
                stat = self._lookup_numstat(stats, file_change)
                if stat is not None:
                    file_change.additions, file_change.deletions = stat

        return VersionControlChangesResponse(
            staged=VersionControlChangePage(
                items=staged,
                total=changes.staged.total,
                nextCursor=changes.staged.next_cursor,
                hasMore=changes.staged.has_more,
            ),
            unstaged=VersionControlChangePage(
                items=unstaged,
                total=changes.unstaged.total,
                nextCursor=changes.unstaged.next_cursor,
                hasMore=changes.unstaged.has_more,
            ),
            untracked=VersionControlChangePage(
                items=untracked,
                total=changes.untracked.total,
                nextCursor=changes.untracked.next_cursor,
                hasMore=changes.untracked.has_more,
            ),
            conflicts=VersionControlChangePage(
                items=conflicts,
                total=changes.conflicts.total,
                nextCursor=changes.conflicts.next_cursor,
                hasMore=changes.conflicts.has_more,
            ),
        )

    def get_file_changes_numstat(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        staged_paths: list[str],
        unstaged_paths: list[str],
    ) -> NumstatResponse:
        """Deferred numstat fill for the visible staged + unstaged paths."""
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        stats = {
            item.path: (item.additions, item.deletions)
            for query in (
                NumstatQuery(tuple(staged_paths), staged=True),
                NumstatQuery(tuple(unstaged_paths), staged=False),
            )
            for item in self.version_control.read(self._target(kb.id), query).entries
        }
        return NumstatResponse(
            stats={
                path: {"additions": additions, "deletions": deletions}
                for path, (additions, deletions) in stats.items()
            }
        )

    @staticmethod
    def _lookup_numstat(
        stats: dict, file_change: FileChange
    ) -> Optional[tuple[int, int]]:
        """Resolve numstat for a change, handling rename path variants."""
        stat = stats.get(file_change.path)
        if stat is None and file_change.oldPath:
            stat = stats.get(f"{file_change.oldPath} => {file_change.path}")
        return stat

    def stage(
        self, *, actor: AuthorizationActor, kb_id: str, payload: StageRequest
    ) -> StageResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        self._require_repo(kb)
        paths = [] if payload.all else self._safe_repo_paths(kb.id, payload.paths)
        command = StageAll() if payload.all else StagePaths(tuple(paths))
        self.version_control.execute(self._target(kb.id), command)
        return StageResponse(
            staged=paths,
            unstaged=[],
        )

    def unstage(
        self, *, actor: AuthorizationActor, kb_id: str, payload: UnstageRequest
    ) -> UnstageResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        self._require_repo(kb)
        paths = [] if payload.all else self._safe_repo_paths(kb.id, payload.paths)
        command = UnstageAll() if payload.all else UnstagePaths(tuple(paths))
        self.version_control.execute(self._target(kb.id), command)
        return UnstageResponse(
            unstaged=paths,
            remainingStaged=0,
        )

    def discard(
        self, *, actor: AuthorizationActor, kb_id: str, payload: DiscardRequest
    ) -> DiscardResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        self._require_repo(kb)
        paths = self._safe_repo_paths(kb.id, payload.paths)
        root = self._kb_root(kb.id)
        for path in paths:
            target = root / path
            if target.exists() and target.is_file():
                self.local_history.snapshot_file(
                    domain="knowledge-base",
                    resource_id=kb.id,
                    source_path=target,
                    relative_path=path,
                    operation="discard",
                )
        self.version_control.execute(
            self._target(kb.id),
            DiscardChanges(tuple(paths)),
        )
        return DiscardResponse(discarded=paths, warnings=[])

    def commit(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        message: str,
    ) -> CommitResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        repo = self._require_repo(kb)
        return self._commit_staged(kb, repo, message=message, actor=actor)

    def list_commits(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
        query_scope: Literal["current", "all", "local", "remote"] = "current",
        branch: Optional[str] = None,
        search: Optional[str] = None,
    ) -> CommitListResponse:
        self._require_repo(
            self._require_enabled_kb(
                actor=actor,
                kb_id=kb_id,
                operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            )
        )
        if not self.version_control.read(
            self._target(kb_id), RepositoryStatusQuery()
        ).head_sha:
            return CommitListResponse(
                items=[], total=0, nextCursor=None, hasMore=False, queryScope=query_scope
            )
        history = self.version_control.read(
            self._target(kb_id),
            HistoryListQuery(
                scope=query_scope,
                branch=branch,
                search=search,
                cursor=cursor,
                limit=limit,
            ),
        )
        return CommitListResponse(
            total=history.total,
            items=[self._commit_summary_from_core(kb_id, commit) for commit in history.items],
            nextCursor=history.next_cursor,
            hasMore=history.has_more,
            queryScope=history.query_scope,
        )

    @_kb_git_operation(OperationKind.READ, "get_commit_files")
    def get_commit_files(
        self, *, actor: AuthorizationActor, kb_id: str, commit_id: str
    ) -> CommitFilesResponse:
        self._require_repo(
            self._require_enabled_kb(
                actor=actor,
                kb_id=kb_id,
                operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            )
        )
        result = self.version_control.read(
            self._target(kb_id), CommitFilesQuery(commit_id)
        )
        change_types = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
            "U": "unmerged",
        }
        return CommitFilesResponse(
            commitId=result.sha,
            files=[
                FileChange(
                    name=Path(item.path).name,
                    path=item.path,
                    status=item.status,
                    type=change_types.get(item.status, "modified"),
                    oldPath=item.original_path,
                    additions=item.additions,
                    deletions=item.deletions,
                    diff=item.patch,
                    patch=item.patch,
                )
                for item in result.files
            ],
        )

    def diff(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str,
        head: str = "WORKTREE",
    ) -> DiffResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        safe_path = self._safe_repo_path(kb.id, path)
        untracked = self.version_control.read(
            self._target(kb.id), ChangesListQuery(group="untracked", limit=100_000)
        )
        if head != "INDEX" and safe_path in {
            item.path for item in untracked.untracked.items
        }:
            patch = self._untracked_file_diff(kb.id, safe_path)
            return DiffResponse(path=safe_path, patch=patch, diff=patch, binary=False)
        result = self.version_control.read(
            self._target(kb.id),
            DiffQuery(path=safe_path, staged=head == "INDEX"),
        )
        patch = result.patch
        return DiffResponse(
            path=safe_path, patch=patch, diff=patch, binary="Binary files" in patch
        )

    def blob(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str,
        revision: Optional[str] = None,
    ) -> BlobResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        safe_path = self._safe_repo_path(kb.id, path)
        result = self.version_control.read(
            self._target(kb.id),
            BlobQuery(path=safe_path, ref=revision or "HEAD"),
        )
        return BlobResponse(path=safe_path, revision=revision, content=result.content)

    def list_branches(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> VersionControlBranchListResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        result = self.version_control.read(self._target(kb.id), BranchListQuery())
        return VersionControlBranchListResponse(
            branches=[
                VersionControlBranch(
                    name=branch.name,
                    displayName=branch.display_name,
                    kind=branch.kind,
                    isCurrent=branch.is_current,
                    upstream=branch.upstream,
                    ahead=branch.ahead,
                    behind=branch.behind,
                    checkedOutTarget=branch.checked_out_target,
                    capabilities={
                        "switch": {
                            "allowed": branch.capabilities.switch.allowed,
                            "disabledReasonKey": branch.capabilities.switch.disabled_reason_key,
                        },
                        "rename": {
                            "allowed": branch.capabilities.rename.allowed,
                            "disabledReasonKey": branch.capabilities.rename.disabled_reason_key,
                        },
                        "delete": {
                            "allowed": branch.capabilities.delete.allowed,
                            "disabledReasonKey": branch.capabilities.delete.disabled_reason_key,
                        },
                    },
                )
                for branch in result.branches
            ]
        )

    def create_branch_and_switch(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        name: str,
        start_point: str,
        upstream: Optional[str],
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=BranchCreateAndSwitch(name, start_point, upstream),
        )

    def switch_branch(
        self, *, actor: AuthorizationActor, kb_id: str, name: str
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor, kb_id=kb_id, command=BranchSwitch(name)
        )

    def rename_branch(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        old_name: str,
        new_name: str,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=BranchRenameLocal(old_name, new_name),
        )

    def delete_branch(
        self, *, actor: AuthorizationActor, kb_id: str, name: str
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor, kb_id=kb_id, command=BranchDeleteLocal(name)
        )

    def publish_branch(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        remote: str,
        remote_name: Optional[str],
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=BranchPublish(remote, remote_name),
        )

    def _execute_branch_command(
        self, *, actor: AuthorizationActor, kb_id: str, command: Any
    ) -> BranchMutationResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        self._require_repo(kb)
        result = self.version_control.execute(self._target(kb.id), command)
        return self._branch_mutation_response(result)

    @staticmethod
    def _branch_mutation_response(result: Any) -> BranchMutationResponse:
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def _target(self, kb_id: str, *, environment=None):
        return KnowledgeBaseRepositoryTargetResolver(self.storage_root).resolve(
            kb_id,
            environment=environment,
        )

    def set_remote_url(
        self, *, actor: AuthorizationActor, kb_id: str, url: str
    ) -> BranchMutationResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        self._require_repo(kb)
        result = self.version_control.execute(
            self._target(kb.id),
            RemoteSettingsUpdate("origin", url.strip()),
        )
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def get_remote_settings(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> RemoteSettingsResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._require_repo(kb)
        result = self.version_control.read(
            self._target(kb.id), RemoteSettingsQuery("origin")
        )
        return RemoteSettingsResponse(
            remoteName=result.remote_name,
            remoteUrl=result.remote_url,
            hasOrigin=result.has_origin,
        )

    def fetch(
        self, *, actor: AuthorizationActor, kb_id: str, payload: RemoteRequest
    ) -> RemoteResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        repo = self._require_repo(kb)
        remote_url = run_git(repo, "remote", "get-url", payload.remote).stdout.strip()
        with user_git_environment(
            self.db,
            user_id=actor.user_id,
            remote_url=remote_url,
        ) as environment:
            self.version_control.execute(
                self._target(kb.id, environment=environment),
                RemoteFetch(payload.remote),
            )
        self._commit_activity(kb_id, "version_control_fetched")
        return RemoteResponse(
            remote=payload.remote, branch=payload.branch, message="GIT_FETCH_SUCCESS"
        )

    def pull(
        self, *, actor: AuthorizationActor, kb_id: str, payload: RemoteRequest
    ) -> RemoteResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        repo = self._require_repo(kb)
        branch = self.version_control.read(
            self._target(kb.id), RepositoryStatusQuery()
        ).current_branch
        target = payload.branch or branch
        remote_url = run_git(repo, "remote", "get-url", payload.remote).stdout.strip()
        with user_git_environment(
            self.db,
            user_id=actor.user_id,
            remote_url=remote_url,
        ) as environment:
            self.version_control.execute(
                self._target(kb.id, environment=environment),
                RemotePullFastForward(payload.remote, target),
            )
        self._commit_activity(kb_id, "version_control_pulled")
        return RemoteResponse(
            remote=payload.remote, branch=target, message="GIT_PULL_SUCCESS"
        )

    def push(
        self, *, actor: AuthorizationActor, kb_id: str, payload: RemoteRequest
    ) -> RemoteResponse:
        kb = self._require_enabled_kb(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        repo = self._require_repo(kb)
        branch = self.version_control.read(
            self._target(kb.id), RepositoryStatusQuery()
        ).current_branch
        target = payload.branch or branch
        remote_url = run_git(repo, "remote", "get-url", payload.remote).stdout.strip()
        with user_git_environment(
            self.db,
            user_id=actor.user_id,
            remote_url=remote_url,
        ) as environment:
            self.version_control.execute(
                self._target(kb.id, environment=environment),
                RemotePush(payload.remote, target),
            )
        self._commit_activity(kb_id, "version_control_pushed")
        return RemoteResponse(
            remote=payload.remote, branch=target, message="GIT_PUSH_SUCCESS"
        )

    def revert_commit(
        self, *, actor: AuthorizationActor, kb_id: str, commit_id: str
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=CommitRevert(commit_id),
        )

    def mark_conflicts_resolved(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        paths: list[str],
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=ConflictMarkResolved(tuple(paths)),
        )

    def abort_conflict(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            actor=actor,
            kb_id=kb_id,
            command=ConflictAbort(),
        )

    def force_unlock(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> BranchMutationResponse:
        """Clear stale Git locks through the shared application contract."""
        # Validate the caller has access to the KB before touching its repo.
        self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        result = self.version_control.execute(
            self._target(kb_id), OperationForceUnlock()
        )
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def get_operation_status(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> VersionControlOperationStatus:
        """Return the in-progress operation status without acquiring Git locks.

        Reads the operation manager's active mutating operation for this
        knowledge base (READ operations never register, so this reflects only
        a write/working-tree/remote op in flight). This powers the client-side
        operation-status polling so the UI can uniformly disable writes and
        refresh on completion — aligned with workspace-runtime's
        ``get_operation_status``.

        Not routed through ``_run_operation`` (it must not acquire a lock); it
        only validates reader access and reads the manager state.
        """
        self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        target = self._target(kb_id)
        metadata = KB_GIT_OPERATION_MANAGER.active_operation(
            target.lock_scope_keys.working_tree_target
        ) or KB_GIT_OPERATION_MANAGER.active_operation(
            target.lock_scope_keys.common_repository
        )
        if metadata is None:
            return VersionControlOperationStatus(isActive=False)
        return VersionControlOperationStatus(
            isActive=True,
            operation=metadata.operation_name,
            actorDisplayName=metadata.actor_display_name or None,
            startedAt=metadata.started_at.isoformat(),
            blockingScope=(
                metadata.blocking_scope.value if metadata.blocking_scope else None
            ),
            stale=metadata.stale,
            retryable=metadata.retryable,
            progressCurrent=metadata.progress_current,
            progressTotal=metadata.progress_total,
            phase=metadata.phase,
            cancellable=metadata.cancellable,
            cancelRequested=metadata.cancel_requested,
        )

    def _require_enabled_kb(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        operation: OperationId,
    ) -> db_models.KnowledgeBase:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=operation,
        )
        if not kb.version_control_enabled:
            raise ValueError(KB_VERSION_CONTROL_DISABLED)
        return kb

    def _require_repo(self, kb: db_models.KnowledgeBase) -> Path:
        root = self._kb_root(kb.id)
        status = self.version_control.read(self._target(kb.id), RepositoryStatusQuery())
        if not status.is_initialized:
            raise ValueError("GIT_REPO_NOT_FOUND")
        return root

    def _kb_root(self, kb_id: str) -> Path:
        return ensure_knowledge_base_storage_root(self.storage_root, kb_id)

    def _safe_repo_path(self, kb_id: str, path: str) -> str:
        normalized = path.strip().replace("\\", "/").lstrip("/")
        if not normalized or normalized == "." or ".." in Path(normalized).parts:
            raise ValueError("GIT_PATH_OUTSIDE_REPOSITORY")
        root = self._kb_root(kb_id).resolve()
        target = (root / normalized).resolve()
        if root != target and root not in target.parents:
            raise ValueError("GIT_PATH_OUTSIDE_REPOSITORY")
        return normalized

    def _safe_repo_paths(self, kb_id: str, paths: list[str]) -> list[str]:
        return [self._safe_repo_path(kb_id, path) for path in paths]

    @staticmethod
    def _origin_url(repo: Path) -> Optional[str]:
        try:
            url = run_git(repo, "remote", "get-url", "origin").stdout.strip()
            return url or None
        except Exception:
            return None

    def _commit_staged(
        self,
        kb: db_models.KnowledgeBase,
        repo: Path,
        *,
        message: str,
        actor: AuthorizationActor,
    ) -> CommitResponse:
        staged = self.version_control.read(
            self._target(kb.id), ChangesListQuery(group="staged", limit=1)
        )
        if not staged.staged.items:
            raise ValueError("GIT_NO_CHANGES")
        commit = self._commit_with_actor(
            kb.id,
            repo,
            message=message,
            actor=actor,
        )
        kb.updated_at = datetime.utcnow()
        self._add_activity(kb.id, "version_control_committed")
        self.db.commit()
        self.db.refresh(kb)
        return CommitResponse(commit=self._commit_summary_from_core(kb.id, commit))

    def _commit_with_actor(
        self,
        kb_id: str,
        repo: Path,
        *,
        message: str,
        actor: AuthorizationActor,
    ) -> CoreCommitSummary:
        actor_context = ManagerActorContextResolver(self.db).resolve(
            user_id=actor.user_id,
            display_name="",
        )
        result = self.version_control.execute(
            self._target(kb_id),
            CommitCreate(message),
            actor_context,
        )
        commits, _ = core_list_commits(repo, ref=result.output, limit=1)
        return commits[0]

    def _add_activity(self, kb_id: str, event_type: str) -> None:
        PlatformResourceActivityLedger(self.db).record_manager_activity(
            event_id=f"manager:{uuid4()}",
            resource_type="knowledge_base",
            resource_id=kb_id,
            event_type=event_type,
        )

    def _commit_activity(self, kb_id: str, event_type: str) -> None:
        self._add_activity(kb_id, event_type)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit_summary_from_core(
        self, kb_id: str, commit: CoreCommitSummary
    ) -> CommitSummary:
        branch = self.version_control.read(
            self._target(kb_id), RepositoryStatusQuery()
        ).current_branch
        timestamp = int(
            datetime.fromisoformat(
                commit.authored_at.replace("Z", "+00:00")
            ).timestamp()
            * 1000
        )
        return CommitSummary(
            id=commit.sha,
            message=commit.message.splitlines()[0] if commit.message else "",
            author=commit.author_name,
            email=commit.author_email,
            timestamp=timestamp,
            branch=branch,
            additions=commit.additions,
            deletions=commit.deletions,
            files=commit.files_changed,
        )

    def _untracked_file_diff(self, kb_id: str, path: str) -> str:
        file_path = self._kb_root(kb_id) / path
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Binary files /dev/null and b/{path} differ\n"
        return "".join(
            difflib.unified_diff(
                [],
                content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
