"""Workspace adapter for the shared Git version-control application."""

from __future__ import annotations

import base64
import filecmp
import logging
import os
import re
import shlex
import tempfile
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence, TypeVar

from app.config.settings import get_settings

from aileron_git_core import (
    ActorContext,
    BranchCreateAndSwitch,
    BranchDeleteLocal,
    BranchListQuery,
    BranchPublish,
    BranchRenameLocal,
    BranchSwitch,
    BlobQuery,
    ChangesListQuery,
    CommitCreate,
    CommitFilesQuery,
    CommitRevert,
    ConflictAbort,
    ConflictMarkResolved,
    DEFAULT_LFS_PATTERNS,
    DiffQuery,
    DiscardChanges,
    GitCommandError,
    GitOperationInProgressError,
    GitStaleLockError,
    HistoryListQuery,
    LockScopeKeys,
    LfsPatternsQuery,
    LfsPatternsUpdate,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
    OperationKind,
    OperationCancel,
    OperationForceUnlock,
    NumstatQuery,
    RemoteFetch,
    RemotePullFastForward,
    RemotePush,
    RemoteSettingsQuery,
    RemoteSettingsUpdate,
    RepositoryClone,
    RepositoryInitialize,
    RepositoryStatusQuery,
    RepositoryTarget,
    StageAll,
    StagePaths,
    UnstageAll,
    UnstagePaths,
    VersionControlApplication,
    VersionControlError as CoreVersionControlError,
    VersionControlOperation,
    git_allow_failure,
    list_remote_branches,
)

from .cache import GitCache, GitCacheInvalidator, WorkspaceGitCacheEffects
from .models import (
    BlobResponse,
    BranchCapabilities,
    BranchCapability,
    BranchInfo,
    BranchListResponse,
    BranchMutationResponse,
    ChangePage,
    ChangesResponse,
    CommitAuthor,
    CommitChange,
    CommitListItem,
    CommitDetailResponse,
    CommitFilesResponse,
    CommitListResponse,
    CommitRequest,
    CommitResponse,
    CommitStats,
    CommitSummary,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    FetchRequest,
    FetchResponse,
    FileChange,
    GitContextListResponse,
    LfsPatternsResponse,
    LfsSnapshotPreviewResponse,
    PullRequest,
    PullResponse,
    PushRequest,
    PushResponse,
    PushUpdate,
    RemoteBranchesResponse,
    RemoteSettingsRequest,
    RemoteSettingsResponse,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlOperationStatus,
    VersionControlRepositoryStatus,
    VersionControlStatus,
)
from .repository import GitUtils, VersionControlError
from .working_tree_operations import WorkingTreeOperations

if TYPE_CHECKING:
    from app.modules.file_system.local_history import WorkspaceLocalHistory

logger = logging.getLogger(__name__)

T = TypeVar("T")

_CLONE_PRESERVED_WORKSPACE_ENTRIES = frozenset(
    {
        ".agents",
        ".claude",
        ".codex",
        ".gitignore",
        ".mcp.json",
        ".opencode",
    }
)


_REDACTED = "[REDACTED]"
_URI_CREDENTIALS = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?P<credentials>[^/\s@]+)@"
)


def _redact_remote_credentials(value: str) -> str:
    """Strip inline credentials so remote diagnostics stay safe to log."""
    return _URI_CREDENTIALS.sub(
        lambda match: f"{match.group('scheme')}{_REDACTED}@", value
    )


def _is_ssh_remote_url(remote_url: str) -> bool:
    if remote_url.startswith("ssh://"):
        return True
    authority = remote_url.split(":", 1)[0]
    return "@" in authority and not remote_url.startswith(("http://", "https://"))


@dataclass(frozen=True)
class _ActiveVersionControlOperation:
    operation: str
    started_at: str


class GitService:
    """Git version control service (Facade)

    Provides unified interface for Git operations, delegates to specialized operation classes.

    Performance optimizations:
    - Redis cache layer reduces redundant computation
    - Batch operation optimization
    - Optimized diff computation
    - Fast total count calculation
    """

    def __init__(
        self,
        base_path: Optional[Path | str] = None,
        cache: Optional[GitCache] = None,
        worktree_subdir: str = ".worktrees",
        working_tree_operations: WorkingTreeOperations | None = None,
        local_history: WorkspaceLocalHistory | None = None,
        ssh_private_key_path: Path | None = None,
        version_control_application: VersionControlApplication | None = None,
        actor_context_resolver: Callable[[], ActorContext] | None = None,
    ) -> None:
        """Initialize Git service

        Args:
            base_path: Workspace root directory
            cache: Cache layer (optional)
        """
        root = (
            Path(base_path)
            if base_path
            else Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
        )
        self._root_path = root.resolve()
        self._root_path.mkdir(parents=True, exist_ok=True)
        self.cache = cache
        self._cache_invalidator = GitCacheInvalidator(cache)
        self._working_tree_operations = (
            working_tree_operations
            or WorkingTreeOperations.create(self._cache_invalidator)
        )
        self._stale_threshold = get_settings().GIT_STALE_LOCK_THRESHOLD_SECONDS
        self._version_control_application = (
            version_control_application
            or VersionControlApplication(
                self._working_tree_operations.operation_manager,
                stale_threshold_seconds=self._stale_threshold,
            )
        )
        self._actor_context_resolver = (
            actor_context_resolver or self._resolve_actor_context_from_settings
        )
        self._operation_status_lock = threading.Lock()
        self._active_operations: dict[str, list[_ActiveVersionControlOperation]] = {}
        self._ssh_private_key_path = (
            ssh_private_key_path or Path.home() / ".ssh" / "id_rsa"
        )
        self._local_history = local_history

        self._utils = GitUtils(self._root_path, cache, worktree_subdir=worktree_subdir)

    def _operation_key(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> str:
        return f"workspace:{workspace_id}:context:{context_id or 'primary'}"

    def _repository_target(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> RepositoryTarget:
        root = self._utils.resolve_context_path(workspace_id, context_id)
        checked_out_branches: tuple[str, ...] = ()
        if (root / ".git").exists():
            contexts = self._utils.list_contexts(workspace_id).contexts
            checked_out_branches = tuple(
                context.branch for context in contexts if context.branch is not None
            )
        return RepositoryTarget(
            root=root,
            lock_scope_keys=LockScopeKeys(
                common_repository=f"workspace:{workspace_id}:repository",
                working_tree_target=self._operation_key(workspace_id, context_id),
            ),
            checked_out_branches=checked_out_branches,
        )

    def _resolve_actor_context_from_settings(self) -> ActorContext:
        name_result = git_allow_failure(
            self._root_path, "config", "--global", "--get", "user.name"
        )
        email_result = git_allow_failure(
            self._root_path, "config", "--global", "--get", "user.email"
        )
        git_name = name_result.stdout.strip() if name_result.returncode == 0 else ""
        git_email = (
            email_result.stdout.strip() if email_result.returncode == 0 else ""
        )
        if not git_name or not git_email:
            raise VersionControlError(
                "Git identity is not configured",
                status_code=409,
                error_code="git_identity_missing",
            )
        return ActorContext(
            display_name=git_name,
            git_name=git_name,
            git_email=git_email,
        )

    def _read_shared(self, workspace_id: str, query, context_id: Optional[str] = None):
        try:
            return self._version_control_application.read(
                self._repository_target(workspace_id, context_id), query
            )
        except CoreVersionControlError as exc:
            self._raise_shared_error(exc)

    def _execute_shared(
        self,
        workspace_id: str,
        command,
        context_id: Optional[str] = None,
        *,
        actor_context: ActorContext | None = None,
        cache_operation: str,
        target: RepositoryTarget | None = None,
    ):
        try:
            result = self._version_control_application.execute(
                target or self._repository_target(workspace_id, context_id),
                command,
                actor_context,
            )
        except CoreVersionControlError as exc:
            self._raise_shared_error(exc)
        self._cache_invalidator.invalidate_effects(
            workspace_id,
            WorkspaceGitCacheEffects.for_operation(cache_operation),
        )
        return result

    @staticmethod
    def _branch_mutation_response(result) -> BranchMutationResponse:
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    @staticmethod
    def _raise_shared_error(exc: CoreVersionControlError) -> None:
        status_code = 409
        if exc.error_code in {"branch_not_found", "repository_not_initialized"}:
            status_code = 404
        elif exc.error_code in {"branch_name_invalid", "lfs_pattern_invalid"}:
            status_code = 422
        raise VersionControlError(
            str(exc),
            status_code=status_code,
            error_code=exc.error_code,
            message_key=exc.error_code,
            blocking_scope=exc.blocking_scope,
            operation_status=exc.operation_status,
            stale=exc.stale,
            can_force_unlock=exc.can_force_unlock,
        ) from exc

    def _push_active_operation(
        self,
        key: str,
        *,
        operation_name: str,
    ) -> None:
        operation = _ActiveVersionControlOperation(
            operation=operation_name,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._operation_status_lock:
            self._active_operations.setdefault(key, []).append(operation)

    def _pop_active_operation(self, key: str) -> None:
        with self._operation_status_lock:
            stack = self._active_operations.get(key)
            if not stack:
                return
            stack.pop()
            if not stack:
                self._active_operations.pop(key, None)

    def get_operation_status(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> VersionControlOperationStatus:
        """Return the current operation status without acquiring Git locks."""
        key = self._operation_key(workspace_id, context_id)
        with self._operation_status_lock:
            stack = self._active_operations.get(key)
            operation = stack[-1] if stack else None

        if operation is None:
            manager = self._version_control_application.operation_manager
            shared_operation = manager.active_operation(key) or manager.active_operation(
                f"workspace:{workspace_id}:repository"
            )
            if shared_operation is None:
                return VersionControlOperationStatus(isActive=False)
            return VersionControlOperationStatus(
                isActive=True,
                operation=shared_operation.operation_name,
                actorDisplayName=shared_operation.actor_display_name or None,
                startedAt=shared_operation.started_at.isoformat(),
                blockingScope=(
                    shared_operation.blocking_scope.value
                    if shared_operation.blocking_scope is not None
                    else None
                ),
                stale=shared_operation.stale,
                retryable=shared_operation.retryable,
                progressCurrent=shared_operation.progress_current,
                progressTotal=shared_operation.progress_total,
                phase=shared_operation.phase,
                cancellable=shared_operation.cancellable,
                cancelRequested=shared_operation.cancel_requested,
            )

        return VersionControlOperationStatus(
            isActive=True,
            operation=operation.operation,
            startedAt=operation.started_at,
            blockingScope="working_tree_target",
        )

    def _run_operation(
        self,
        *,
        workspace_id: str,
        context_id: Optional[str],
        kind: OperationKind,
        operation_name: str,
        cache_effects: list[str],
        callback: Callable[[], T],
        repo_root_override: Optional[Path] = None,
    ) -> T:
        key = self._operation_key(workspace_id, context_id)
        try:

            def run_with_status() -> T:
                self._push_active_operation(
                    key,
                    operation_name=operation_name,
                )
                try:
                    return callback()
                finally:
                    self._pop_active_operation(key)

            repo_root = Path(".")
            if kind != OperationKind.READ:
                repo_root = repo_root_override or Path(
                    self._utils.get_repo(workspace_id, context_id).working_tree_dir
                    or "."
                )
            return self._working_tree_operations.execute(
                workspace_id=workspace_id,
                operation_key=key,
                kind=kind,
                operation_name=operation_name,
                repo_root=repo_root,
                callback=run_with_status,
                cache_effects=cache_effects,
                stale_threshold_seconds=self._stale_threshold,
            )
        except GitStaleLockError as exc:
            # Stale on-disk git lock that could not be auto-cleared: the
            # client is allowed to force-unlock.
            raise VersionControlError(
                "Version control operation already in progress",
                status_code=409,
                error_code="VC_OPERATION_IN_PROGRESS",
                message_key="VC_OPERATION_IN_PROGRESS",
                blocking_scope="working_tree_target",
                stale=True,
                can_force_unlock=True,
            ) from exc
        except GitOperationInProgressError as exc:
            # In-memory operation collision (concurrent request): there is
            # no on-disk lock to force-unlock.
            raise VersionControlError(
                "Version control operation already in progress",
                status_code=409,
                error_code="VC_OPERATION_IN_PROGRESS",
                message_key="VC_OPERATION_IN_PROGRESS",
                blocking_scope="working_tree_target",
            ) from exc
        except GitCommandError as exc:
            # Safety net: any non-lock git failure that escapes the callback
            # (and the stale-lock recovery wrapper for mutating ops) becomes a
            # structured error instead of a bare 500. GitStaleLockError
            # subclasses GitOperationInProgressError (not GitCommandError), so
            # this clause never shadows the lock/collision handling above.
            raise VersionControlError(
                str(exc),
                status_code=500,
                error_code="VC_OPERATION_FAILED",
            ) from exc

    def force_unlock(
        self, *, workspace_id: str, context_id: Optional[str] = None
    ) -> BranchMutationResponse:
        """Clear stale Git locks through the shared application contract."""
        result = self._execute_shared(
            workspace_id,
            OperationForceUnlock(),
            context_id,
            cache_operation="force_unlock",
        )
        return self._branch_mutation_response(result)

    def update_lfs_patterns(
        self,
        workspace_id: str,
        *,
        patterns: Sequence[str] | None = None,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        """Update repository LFS patterns through the shared application."""
        resolved_patterns = tuple(patterns or DEFAULT_LFS_PATTERNS)
        result = self._execute_shared(
            workspace_id,
            LfsPatternsUpdate(patterns=resolved_patterns),
            context_id,
            cache_operation="stage",
        )
        return self._branch_mutation_response(result)

    def get_lfs_patterns(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> LfsPatternsResponse:
        """Get repository LFS patterns through the shared application."""
        result = self._read_shared(workspace_id, LfsPatternsQuery(), context_id)
        return LfsPatternsResponse(patterns=list(result.patterns))

    def preview_lfs_snapshot(
        self,
        workspace_id: str,
        *,
        patterns: Sequence[str] | None = None,
        context_id: Optional[str] = None,
    ) -> LfsSnapshotPreviewResponse:
        """Preview repository LFS conversion through the shared application."""
        selected_patterns = patterns
        if selected_patterns is None:
            selected_patterns = self._read_shared(
                workspace_id, LfsPatternsQuery(), context_id
            ).patterns
        result = self._execute_shared(
            workspace_id,
            LfsSnapshotPreview(patterns=tuple(selected_patterns)),
            context_id,
            cache_operation="stage",
        )
        return LfsSnapshotPreviewResponse(
            matchedTotal=result.matched_total,
            totalSize=result.total_size,
            pathSample=list(result.path_sample),
        )

    def convert_lfs_snapshot(
        self,
        workspace_id: str,
        *,
        paths: Sequence[str],
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        """Convert repository files to LFS through the shared application."""
        result = self._execute_shared(
            workspace_id,
            LfsSnapshotConvert(paths=tuple(paths)),
            context_id,
            cache_operation="stage",
        )
        return self._branch_mutation_response(result)

    def cancel_operation(
        self, workspace_id: str, *, context_id: Optional[str] = None
    ) -> BranchMutationResponse:
        """Request cancellation through the shared application."""
        result = self._execute_shared(
            workspace_id,
            OperationCancel(),
            context_id,
            cache_operation="operation_cancel",
        )
        return self._branch_mutation_response(result)

    # ------------------------------------------------------------------
    # Status and branch operations
    # ------------------------------------------------------------------
    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        """List available Git contexts for a workspace."""
        return self._run_operation(
            workspace_id=workspace_id,
            context_id=None,
            kind=OperationKind.READ,
            operation_name="list_contexts",
            cache_effects=[],
            callback=lambda: self._utils.list_contexts(workspace_id),
        )

    def initialize_repository(
        self, workspace_id: str, *, default_branch: str
    ) -> VersionControlStatus:
        """Initialize the primary workspace as a Git repository."""
        self._execute_shared(
            workspace_id,
            RepositoryInitialize(default_branch=default_branch),
            cache_operation="initialize_repository",
        )
        self.invalidate_context_path_cache(workspace_id)
        return self.get_status(workspace_id)

    def get_repository_status(
        self, workspace_id: str
    ) -> VersionControlRepositoryStatus:
        """Return repository state and whether root-level clone is safe."""
        workspace_path = self._utils.workspace_path(workspace_id).resolve()
        entries = list(workspace_path.iterdir())
        is_git_repo = (workspace_path / ".git").is_dir()

        if not is_git_repo:
            unsupported_entries = [
                entry
                for entry in entries
                if entry.name not in _CLONE_PRESERVED_WORKSPACE_ENTRIES
            ]
            can_clone_safely = not unsupported_entries
            return VersionControlRepositoryStatus(
                isGitRepo=False,
                hasOrigin=False,
                hasLocalContent=bool(entries),
                canCloneSafely=can_clone_safely,
                canInitSafely=True,
                cloneBlockedReason=(
                    None if can_clone_safely else "VC_CLONE_TARGET_NOT_EMPTY"
                ),
            )

        status = self.get_status(workspace_id)
        remote_result = git_allow_failure(
            workspace_path,
            "remote",
            "get-url",
            "origin",
        )
        has_origin = remote_result.returncode == 0
        return VersionControlRepositoryStatus(
            isGitRepo=True,
            currentBranch=status.currentBranch,
            remoteUrl=remote_result.stdout.strip() if has_origin else None,
            hasOrigin=has_origin,
            hasLocalContent=bool(entries),
            canCloneSafely=False,
            canInitSafely=False,
            cloneBlockedReason="VC_REPOSITORY_ALREADY_INITIALIZED",
        )

    def clone_repository(
        self,
        workspace_id: str,
        *,
        remote_url: str,
        branch: str | None = None,
    ) -> VersionControlStatus:
        """Clone a remote repository into the primary workspace root."""
        workspace_path = self._utils.workspace_path(workspace_id).resolve()
        if (workspace_path / ".git").exists():
            raise VersionControlError(
                "Repository is already initialized",
                status_code=409,
                error_code="VC_REPOSITORY_ALREADY_INITIALIZED",
            )
        unsupported_entries = sorted(
            entry.name
            for entry in workspace_path.iterdir()
            if entry.name not in _CLONE_PRESERVED_WORKSPACE_ENTRIES
        )
        if unsupported_entries:
            raise VersionControlError(
                "The workspace contains files that prevent cloning",
                status_code=409,
                error_code="VC_CLONE_TARGET_NOT_EMPTY",
            )
        git_environment = self._git_environment_for_remote(remote_url) or {}
        workspace_target = self._repository_target(workspace_id)

        def clone_and_publish() -> None:
            with tempfile.TemporaryDirectory(
                prefix=".aileron-clone-",
                dir=workspace_path,
            ) as temporary_directory:
                staging_path = Path(temporary_directory) / "repository"
                staging_target = RepositoryTarget(
                    root=staging_path,
                    lock_scope_keys=workspace_target.lock_scope_keys,
                    environment=git_environment,
                )
                self._execute_shared(
                    workspace_id,
                    RepositoryClone(remote_url=remote_url, branch=branch),
                    cache_operation="clone_repository",
                    target=staging_target,
                )
                if not (staging_path / ".git").is_dir():
                    raise VersionControlError(
                        "Clone did not produce a Git repository",
                        status_code=500,
                        error_code="VC_CLONE_FAILED",
                    )
                with self._version_control_application.operation_manager.acquire_scoped(
                    workspace_target.lock_scope_keys,
                    VersionControlOperation.REPOSITORY_CLONE,
                ):
                    self._publish_staged_repository(
                        staging_path=staging_path,
                        workspace_path=workspace_path,
                    )

        clone_and_publish()
        self._cache_invalidator.invalidate_effects(
            workspace_id, WorkspaceGitCacheEffects.CLONE_REPOSITORY
        )
        self.invalidate_context_path_cache(workspace_id)
        return self.get_status(workspace_id)

    def remote_branches(
        self,
        workspace_id: str,
        *,
        remote_url: str,
    ) -> RemoteBranchesResponse:
        """List branches available from a remote repository."""
        workspace_path = self._utils.workspace_path(workspace_id).resolve()
        try:
            result = list_remote_branches(
                workspace_path,
                remote_url,
                env=self._git_environment_for_remote(remote_url),
            )
        except GitCommandError as exc:
            logger.warning(
                "Failed to list remote branches for %s: %s",
                _redact_remote_credentials(remote_url),
                _redact_remote_credentials(exc.stderr.strip() or str(exc)),
            )
            raise VersionControlError(
                str(exc),
                status_code=400,
                error_code="VC_REMOTE_BRANCHES_FAILED",
            ) from exc
        return RemoteBranchesResponse(
            branches=result.branches,
            defaultBranch=result.default_branch,
        )

    def _git_environment_for_remote(
        self,
        remote_url: str,
    ) -> dict[str, str] | None:
        if not _is_ssh_remote_url(remote_url):
            return None
        if not (
            self._ssh_private_key_path.is_file()
            and self._ssh_private_key_path.stat().st_size > 0
        ):
            raise VersionControlError(
                "An SSH private key must be configured before accessing this repository",
                status_code=409,
                error_code="VC_SSH_KEY_REQUIRED",
            )
        return {
            **os.environ,
            "GIT_SSH_COMMAND": (
                f"ssh -i {shlex.quote(str(self._ssh_private_key_path))} "
                "-o IdentitiesOnly=yes "
                "-o StrictHostKeyChecking=accept-new"
            ),
        }

    @staticmethod
    def _publish_staged_repository(
        *,
        staging_path: Path,
        workspace_path: Path,
    ) -> None:
        added_paths: list[Path] = []
        created_directories: list[Path] = []
        modified_files: list[tuple[Path, bytes]] = []

        def paths_match(source: Path, target: Path) -> bool:
            if source.is_symlink() or target.is_symlink():
                return (
                    source.is_symlink()
                    and target.is_symlink()
                    and os.readlink(source) == os.readlink(target)
                )
            return (
                source.is_file()
                and target.is_file()
                and filecmp.cmp(source, target, shallow=False)
            )

        def publish_directory(source_directory: Path, target_directory: Path) -> None:
            for source in source_directory.iterdir():
                target = target_directory / source.name
                target_exists = os.path.lexists(target)
                if source.is_dir() and not source.is_symlink():
                    if not target_exists:
                        target.mkdir()
                        created_directories.append(target)
                    elif not target.is_dir() or target.is_symlink():
                        raise VersionControlError(
                            "Repository content conflicts with workspace content",
                            status_code=409,
                            error_code="VC_CLONE_PUBLISH_CONFLICT",
                        )
                    publish_directory(source, target)
                    continue
                if not target_exists:
                    os.replace(source, target)
                    added_paths.append(target)
                    continue
                if (
                    target == workspace_path / ".gitignore"
                    and source.is_file()
                    and not source.is_symlink()
                    and target.is_file()
                    and not target.is_symlink()
                ):
                    source_content = source.read_bytes().rstrip(b"\n")
                    target_content = target.read_bytes()
                    if source_content != target_content.rstrip(b"\n"):
                        local_content = target_content.rstrip(b"\n")
                        merged_parts = [
                            content
                            for content in (source_content, local_content)
                            if content
                        ]
                        modified_files.append((target, target_content))
                        target.write_bytes(b"\n".join(merged_parts) + b"\n")
                    continue
                if not paths_match(source, target):
                    raise VersionControlError(
                        "Repository content conflicts with workspace content",
                        status_code=409,
                        error_code="VC_CLONE_PUBLISH_CONFLICT",
                    )

        try:
            publish_directory(staging_path, workspace_path)
        except Exception:
            for path, original_content in reversed(modified_files):
                try:
                    path.write_bytes(original_content)
                except OSError:
                    logger.exception("Failed to restore cloned file: %s", path)
            for path in reversed(added_paths):
                try:
                    if os.path.lexists(path):
                        path.unlink()
                except OSError:
                    logger.exception("Failed to roll back cloned path: %s", path)
            for directory in reversed(created_directories):
                try:
                    directory.rmdir()
                except OSError:
                    logger.exception(
                        "Failed to roll back cloned directory: %s",
                        directory,
                    )
            raise

    def set_worktree_subdir(self, worktree_subdir: str) -> None:
        """Update the managed worktree subdirectory."""
        self._utils.set_worktree_subdir(worktree_subdir)

    def invalidate_context_path_cache(self, workspace_id: Optional[str] = None) -> None:
        """Invalidate cached Git context path resolutions."""
        self._utils.invalidate_context_path_cache(workspace_id)

    def managed_worktree_root(self, workspace_id: str) -> Path:
        """Return the configured managed-worktree root for a validated workspace."""
        repo = self._utils.get_repo(workspace_id)
        return repo.root / self._utils.worktree_subdir

    def run_serialized_worktree_operation(
        self,
        *,
        workspace_id: str,
        context_ids: Sequence[Optional[str]],
        operation_name: str,
        callback: Callable[[], T],
    ) -> T:
        """Run a worktree operation without automatic Git-state recovery.

        Automation uses this boundary because it must serialize with regular
        version-control operations while preserving user-owned Git locks and
        incomplete operations exactly as they are.
        """
        ordered_context_ids = sorted(
            set(context_ids), key=lambda value: (value is not None, value or "")
        )
        keys = [
            (context_id, self._operation_key(workspace_id, context_id))
            for context_id in ordered_context_ids
        ]
        try:
            with ExitStack() as stack:
                for _, key in keys:
                    stack.enter_context(
                        self._working_tree_operations.acquire(
                            key,
                            kind=OperationKind.WORKING_TREE,
                            operation_name=operation_name,
                        )
                    )
                for context_id, key in keys:
                    self._push_active_operation(
                        key,
                        operation_name=operation_name,
                    )
                try:
                    return callback()
                finally:
                    for _, key in reversed(keys):
                        self._pop_active_operation(key)
        except GitOperationInProgressError as exc:
            raise VersionControlError(
                "Version control operation already in progress",
                status_code=409,
                error_code="VC_OPERATION_IN_PROGRESS",
                message_key="VC_OPERATION_IN_PROGRESS",
                blocking_scope="working_tree_target",
            ) from exc

    def get_status(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> VersionControlStatus:
        """Get Git status

        Args:
            workspace_id: Workspace ID

        Returns:
            Version control status
        """
        result = self._read_shared(
            workspace_id, RepositoryStatusQuery(), context_id
        )
        operation_status = None
        if result.operation_status is not None:
            operation = result.operation_status
            operation_status = VersionControlOperationStatus(
                isActive=True,
                operation=operation.operation_name,
                actorDisplayName=operation.actor_display_name or None,
                startedAt=operation.started_at.isoformat(),
                blockingScope=(
                    operation.blocking_scope.value
                    if operation.blocking_scope is not None
                    else None
                ),
                stale=operation.stale,
                retryable=operation.retryable,
                progressCurrent=operation.progress_current,
                progressTotal=operation.progress_total,
                phase=operation.phase,
                cancellable=operation.cancellable,
                cancelRequested=operation.cancel_requested,
            )
        return VersionControlStatus(
            isInitialized=result.is_initialized,
            currentBranch=result.current_branch,
            detachedHead=result.detached_head,
            headSha=result.head_sha,
            hasOrigin=result.has_origin,
            upstream=result.upstream,
            ahead=result.ahead,
            behind=result.behind,
            hasConflicts=result.has_conflicts,
            stagedTotal=result.staged_total,
            unstagedTotal=result.unstaged_total,
            untrackedTotal=result.untracked_total,
            conflictTotal=result.conflict_total,
            operationStatus=operation_status,
        )

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = True,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
        include_metadata: bool = True,
    ) -> BranchListResponse:
        """List branches

        Args:
            workspace_id: Workspace ID
            include_remote: Whether to include remote branches
            search: Search keyword

        Returns:
            Branch list response
        """
        _ = include_metadata
        try:
            result = self._version_control_application.read(
                self._repository_target(workspace_id, context_id),
                BranchListQuery(),
            )
        except CoreVersionControlError as exc:
            self._raise_shared_error(exc)
        branches = [
            BranchInfo(
                name=branch.name,
                displayName=branch.display_name,
                kind=branch.kind,
                isCurrent=branch.is_current,
                upstream=branch.upstream,
                ahead=branch.ahead,
                behind=branch.behind,
                checkedOutTarget=branch.checked_out_target,
                capabilities=BranchCapabilities(
                    switch=BranchCapability(
                        allowed=branch.capabilities.switch.allowed,
                        disabledReasonKey=(
                            branch.capabilities.switch.disabled_reason_key
                        ),
                    ),
                    rename=BranchCapability(
                        allowed=branch.capabilities.rename.allowed,
                        disabledReasonKey=(
                            branch.capabilities.rename.disabled_reason_key
                        ),
                    ),
                    delete=BranchCapability(
                        allowed=branch.capabilities.delete.allowed,
                        disabledReasonKey=(
                            branch.capabilities.delete.disabled_reason_key
                        ),
                    ),
                ),
            )
            for branch in result.branches
            if (include_remote or branch.kind == "local")
            and (not search or search.lower() in branch.name.lower())
        ]
        return BranchListResponse(branches=branches)

    def _execute_branch_command(
        self,
        workspace_id: str,
        command,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        try:
            result = self._version_control_application.execute(
                self._repository_target(workspace_id, context_id), command
            )
        except CoreVersionControlError as exc:
            self._raise_shared_error(exc)
        self._cache_invalidator.invalidate_effects(
            workspace_id,
            WorkspaceGitCacheEffects.for_operation("checkout"),
        )
        return self._branch_mutation_response(result)

    def create_branch(
        self,
        workspace_id: str,
        *,
        name: str,
        start_point: str = "HEAD",
        upstream: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            workspace_id,
            BranchCreateAndSwitch(name=name, start_point=start_point, upstream=upstream),
            context_id,
        )

    def switch_branch(
        self,
        workspace_id: str,
        *,
        name: str,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            workspace_id, BranchSwitch(name=name), context_id
        )

    def rename_branch(
        self,
        workspace_id: str,
        *,
        old_name: str,
        new_name: str,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            workspace_id,
            BranchRenameLocal(old_name=old_name, new_name=new_name),
            context_id,
        )

    def delete_branch(
        self,
        workspace_id: str,
        *,
        name: str,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            workspace_id, BranchDeleteLocal(name=name), context_id
        )

    def publish_branch(
        self,
        workspace_id: str,
        *,
        remote: str = "origin",
        remote_name: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            workspace_id,
            BranchPublish(remote=remote, remote_name=remote_name),
            context_id,
        )

    def mark_conflicts_resolved(
        self,
        workspace_id: str,
        *,
        paths: list[str],
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        result = self._execute_shared(
            workspace_id,
            ConflictMarkResolved(tuple(paths)),
            context_id,
            cache_operation="stage",
        )
        return self._branch_mutation_response(result)

    def abort_conflict(
        self,
        workspace_id: str,
        *,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        result = self._execute_shared(
            workspace_id,
            ConflictAbort(),
            context_id,
            cache_operation="checkout",
        )
        return self._branch_mutation_response(result)

    def revert_commit(
        self,
        workspace_id: str,
        *,
        sha: str,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        result = self._execute_shared(
            workspace_id,
            CommitRevert(sha=sha),
            context_id,
            actor_context=self._actor_context_resolver(),
            cache_operation="commit",
        )
        return self._branch_mutation_response(result)

    # ------------------------------------------------------------------
    # Changes and staging operations
    # ------------------------------------------------------------------
    def get_changes(
        self,
        workspace_id: str,
        group: str = "all",
        cursor: str | None = None,
        limit: int = 100,
        context_id: Optional[str] = None,
        include_stats: bool = True,
    ) -> ChangesResponse:
        """Get file changes

        Args:
            workspace_id: Workspace ID
            group: Change group or all groups
            cursor: Opaque cursor returned by a previous response
            limit: Maximum items returned per group
            include_stats: When False, skip numstat (deferred to get_numstat)

        Returns:
            Changes response
        """
        _ = include_stats
        result = self._read_shared(
            workspace_id,
            ChangesListQuery(
                group=group,
                cursor=cursor,
                limit=limit,
            ),
            context_id,
        )

        def map_change(change) -> FileChange:
            return FileChange(
                name=Path(change.path).name,
                path=change.path,
                status=change.raw_status or change.status,
                type=change.type,
                oldPath=change.original_path,
            )

        def map_page(page) -> ChangePage:
            return ChangePage(
                items=[map_change(change) for change in page.items],
                total=page.total,
                nextCursor=page.next_cursor,
                hasMore=page.has_more,
            )

        return ChangesResponse(
            staged=map_page(result.staged),
            unstaged=map_page(result.unstaged),
            untracked=map_page(result.untracked),
            conflicts=map_page(result.conflicts),
        )

    def get_numstat(
        self,
        workspace_id: str,
        staged_paths: Optional[list[str]] = None,
        unstaged_paths: Optional[list[str]] = None,
        context_id: Optional[str] = None,
    ) -> dict[str, dict[str, int]]:
        """Get deferred numstat for specific paths.

        Args:
            workspace_id: Workspace ID
            staged_paths: Staged file paths
            unstaged_paths: Unstaged file paths
            context_id: Git context ID

        Returns:
            Map of {path: {additions, deletions}}
        """
        paths = tuple(dict.fromkeys((staged_paths or []) + (unstaged_paths or [])))
        result = self._read_shared(
            workspace_id,
            NumstatQuery(paths=paths),
            context_id,
        )
        return {
            entry.path: {
                "additions": entry.additions,
                "deletions": entry.deletions,
            }
            for entry in result.entries
        }

    def stage(
        self, workspace_id: str, payload: StageRequest, context_id: Optional[str] = None
    ) -> StageResponse:
        """Stage files

        Args:
            workspace_id: Workspace ID
            payload: Stage request

        Returns:
            Stage response
        """
        command = StageAll() if payload.all else StagePaths(tuple(payload.paths))
        self._execute_shared(
            workspace_id,
            command,
            context_id,
            cache_operation="stage",
        )
        return StageResponse(
            staged=[] if payload.all else list(payload.paths),
            unstaged=[],
        )

    def unstage(
        self,
        workspace_id: str,
        payload: UnstageRequest,
        context_id: Optional[str] = None,
    ) -> UnstageResponse:
        """Unstage files

        Args:
            workspace_id: Workspace ID
            payload: Unstage request

        Returns:
            Unstage response
        """
        command = UnstageAll() if payload.all else UnstagePaths(tuple(payload.paths))
        self._execute_shared(
            workspace_id,
            command,
            context_id,
            cache_operation="unstage",
        )
        return UnstageResponse(
            unstaged=[] if payload.all else list(payload.paths),
            remainingStaged=0,
        )

    def discard(
        self,
        workspace_id: str,
        payload: DiscardRequest,
        context_id: Optional[str] = None,
    ) -> DiscardResponse:
        """Discard changes

        Args:
            workspace_id: Workspace ID
            payload: Discard request

        Returns:
            Discard response
        """
        target = self._repository_target(workspace_id, context_id)
        if self._local_history is not None:
            for path in payload.paths:
                source_path = target.root / path
                if source_path.exists() and source_path.is_file():
                    self._local_history.snapshot_file(
                        source_path=source_path,
                        relative_path=path,
                        operation="discard",
                    )
        self._execute_shared(
            workspace_id,
            DiscardChanges(tuple(payload.paths)),
            context_id,
            cache_operation="discard",
        )
        return DiscardResponse(discarded=list(payload.paths), warnings=[])

    # ------------------------------------------------------------------
    # Commit and history operations
    # ------------------------------------------------------------------
    def commit(
        self,
        workspace_id: str,
        payload: CommitRequest,
        context_id: Optional[str] = None,
    ) -> CommitResponse:
        """Create commit

        Args:
            workspace_id: Workspace ID
            payload: Commit request

        Returns:
            Commit response
        """
        actor_context = self._actor_context_resolver()
        self._execute_shared(
            workspace_id,
            CommitCreate(message=payload.message),
            context_id,
            actor_context=actor_context,
            cache_operation="commit",
        )
        history = self._read_shared(
            workspace_id,
            HistoryListQuery(scope="current", limit=1),
            context_id,
        )
        committed = history.items[0]
        return CommitResponse(
            commit=CommitSummary(
                id=committed.sha,
                message=committed.message,
                author=CommitAuthor(
                    name=committed.author_name,
                    email=committed.author_email,
                ),
                timestamp=committed.authored_at.replace("+00:00", "Z"),
                additions=committed.additions,
                deletions=committed.deletions,
            )
        )

    def list_commits(
        self,
        workspace_id: str,
        cursor: str | None = None,
        limit: int = 50,
        query_scope: str = "current",
        branch: Optional[str] = None,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> CommitListResponse:
        """List commit history

        Args:
            workspace_id: Workspace ID
            cursor: Opaque cursor returned by a previous response
            limit: Maximum items returned
            query_scope: current, all, local, or remote
            branch: Branch name
            search: Search keyword

        Returns:
            Commit list response
        """
        result = self._read_shared(
            workspace_id,
            HistoryListQuery(
                scope=query_scope,
                branch=branch,
                search=search,
                cursor=cursor,
                limit=limit,
            ),
            context_id,
        )
        items = [
            CommitListItem(
                id=commit.sha,
                message=commit.message,
                author=commit.author_name,
                email=commit.author_email or None,
                timestamp=int(
                    datetime.fromisoformat(
                        commit.authored_at.replace("Z", "+00:00")
                    ).timestamp()
                    * 1000
                ),
                branch=branch or "",
                additions=commit.additions,
                deletions=commit.deletions,
                files=commit.files_changed,
            )
            for commit in result.items
        ]
        return CommitListResponse(
            total=result.total,
            items=items,
            nextCursor=result.next_cursor,
            hasMore=result.has_more,
            queryScope=result.query_scope,
        )

    def get_commit(
        self, workspace_id: str, commit_id: str, context_id: Optional[str] = None
    ) -> CommitDetailResponse:
        """Get commit details

        Args:
            workspace_id: Workspace ID
            commit_id: Commit ID

        Returns:
            Commit detail response
        """
        history = self._read_shared(
            workspace_id,
            HistoryListQuery(scope="local", branch=commit_id, limit=1),
            context_id,
        )
        if not history.items:
            raise VersionControlError(
                "Commit not found",
                status_code=404,
                error_code="file_conflict",
            )
        commit = history.items[0]
        files = self._read_shared(
            workspace_id,
            CommitFilesQuery(sha=commit_id),
            context_id,
        )
        changes = [
            CommitChange(
                name=Path(file.path).name,
                path=file.path,
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                patch=file.patch,
            )
            for file in files.files
        ]
        return CommitDetailResponse(
            id=commit.sha,
            message=commit.message,
            author=CommitAuthor(
                name=commit.author_name,
                email=commit.author_email,
            ),
            timestamp=commit.authored_at.replace("+00:00", "Z"),
            branch=self.get_status(workspace_id, context_id).currentBranch or "",
            stats=CommitStats(
                additions=commit.additions,
                deletions=commit.deletions,
                files=commit.files_changed,
            ),
            changes=changes,
        )

    def get_commit_files(
        self, workspace_id: str, commit_id: str, context_id: Optional[str] = None
    ) -> CommitFilesResponse:
        """Get commit file list

        Args:
            workspace_id: Workspace ID
            commit_id: Commit ID

        Returns:
            Commit file response
        """
        result = self._read_shared(
            workspace_id,
            CommitFilesQuery(sha=commit_id),
            context_id,
        )
        return CommitFilesResponse(
            commitId=result.sha,
            files=[
                CommitChange(
                    name=Path(file.path).name,
                    path=file.path,
                    status=file.status,
                    additions=file.additions,
                    deletions=file.deletions,
                    patch=file.patch,
                )
                for file in result.files
            ],
        )

    # ------------------------------------------------------------------
    # Remote operations
    # ------------------------------------------------------------------
    def push(
        self, workspace_id: str, payload: PushRequest, context_id: Optional[str] = None
    ) -> PushResponse:
        """Push to remote

        Args:
            workspace_id: Workspace ID
            payload: Push request

        Returns:
            Push response
        """
        status = self.get_status(workspace_id, context_id)
        target_branch = payload.branch or status.currentBranch or ""
        self._execute_shared(
            workspace_id,
            RemotePush(remote=payload.remote, branch=target_branch),
            context_id,
            cache_operation="push",
        )
        return PushResponse(
            remote=payload.remote,
            branch=target_branch,
            updates=[PushUpdate(ref=target_branch, status="ok")],
        )

    def pull(
        self, workspace_id: str, payload: PullRequest, context_id: Optional[str] = None
    ) -> PullResponse:
        """Pull from remote

        Args:
            workspace_id: Workspace ID
            payload: Pull request

        Returns:
            Pull response
        """
        status = self.get_status(workspace_id, context_id)
        target_branch = payload.branch or status.currentBranch or ""
        self._execute_shared(
            workspace_id,
            RemotePullFastForward(remote=payload.remote, branch=target_branch),
            context_id,
            cache_operation="pull",
        )
        return PullResponse(
            remote=payload.remote,
            branch=target_branch,
            fastForward=True,
            commits=[],
        )

    def fetch(
        self, workspace_id: str, payload: FetchRequest, context_id: Optional[str] = None
    ) -> FetchResponse:
        """Fetch updates from remote

        Args:
            workspace_id: Workspace ID
            payload: Fetch request

        Returns:
            Fetch response
        """
        result = self._execute_shared(
            workspace_id,
            RemoteFetch(remote=payload.remote),
            context_id,
            cache_operation="fetch",
        )
        return FetchResponse(
            remote=payload.remote,
            fetchedRefs=[line for line in result.output.splitlines() if line],
        )

    def get_remote_settings(
        self, workspace_id: str, context_id: Optional[str] = None
    ) -> RemoteSettingsResponse:
        """Get repository remote settings."""
        result = self._read_shared(
            workspace_id, RemoteSettingsQuery(name="origin"), context_id
        )
        return RemoteSettingsResponse(
            remoteName=result.remote_name,
            remoteUrl=result.remote_url,
            hasOrigin=result.has_origin,
        )

    def set_remote_settings(
        self,
        workspace_id: str,
        payload: RemoteSettingsRequest,
        context_id: Optional[str] = None,
    ) -> BranchMutationResponse:
        """Set repository remote settings."""
        result = self._execute_shared(
            workspace_id,
            RemoteSettingsUpdate(name="origin", url=payload.remote_url),
            context_id,
            cache_operation="remote_settings",
        )
        return self._branch_mutation_response(result)

    # ------------------------------------------------------------------
    # Diff and content operations
    # ------------------------------------------------------------------
    def diff(
        self,
        workspace_id: str,
        path: str,
        base: Optional[str] = None,
        head: Optional[str] = None,
        context: int = 3,
        include_metadata: bool = False,
        context_id: Optional[str] = None,
    ) -> DiffResponse:
        """Get file diff content

        Args:
            workspace_id: Workspace ID
            path: File path
            base: Comparison base
            head: Comparison target
            context: Context line count
            include_metadata: Whether to include file metadata

        Returns:
            Diff response
        """
        _ = include_metadata
        staged = head == "INDEX"
        commit_sha = None if head in {None, "INDEX", "WORKTREE"} else head
        result = self._read_shared(
            workspace_id,
            DiffQuery(path=path, staged=staged, commit_sha=commit_sha),
            context_id,
        )
        return DiffResponse(
            path=result.path,
            base=base or "HEAD",
            head=head or "WORKTREE",
            context=context,
            patch=result.patch,
        )

    def blob(
        self,
        workspace_id: str,
        path: str,
        revision: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> BlobResponse:
        """Get file content

        Args:
            workspace_id: Workspace ID
            path: File path
            revision: Version

        Returns:
            Blob response
        """
        result = self._read_shared(
            workspace_id,
            BlobQuery(path=path, ref=revision or "HEAD"),
            context_id,
        )
        return BlobResponse(
            path=result.path,
            revision=result.ref,
            content=base64.b64encode(result.content.encode("utf-8")).decode("ascii"),
            isBase64=True,
        )


__all__ = ["GitService", "VersionControlError"]
