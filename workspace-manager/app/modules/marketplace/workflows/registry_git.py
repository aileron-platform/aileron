"""Marketplace registry git workflow module."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

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
)
from aileron_git_core import GitCommandError as CoreGitCommandError
from aileron_git_core import (
    HistoryListQuery,
    LfsPatternsQuery,
    LfsPatternsUpdate,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
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
    git_allow_failure,
    to_change_dict,
)

from app.modules.marketplace.models import (
    MarketplaceGitCommitFilesResult,
    MarketplaceGitCommitRequest,
    MarketplaceGitCommitResult,
    MarketplaceGitDiffResponse,
    MarketplaceGitPathRequest,
    MarketplaceGitStageResult,
    MarketplaceGitUnstageResult,
    MarketplaceRegistryCloneRequest,
    MarketplaceRegistryGitOperationResult,
    MarketplaceRegistryRepositoryStatus,
)
from app.modules.version_control.application import (
    ManagerActorContextResolver,
    version_control_status_from_core,
)
from app.modules.version_control.models import (
    BlobResponse,
    BranchMutationResponse,
    CommitListResponse,
    CommitSummary,
    DiscardRequest,
    DiscardResponse,
    FileChange,
    LfsPatternsResponse,
    LfsSnapshotPreviewResponse,
    NumstatResponse,
    RemoteBranchesResponse,
    RemoteSettingsResponse,
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
from app.modules.version_control.target import MarketplaceRepositoryTargetResolver

from .kernel import _MarketplaceRegistrySupport
from .registry_operations import (
    MARKETPLACE_GIT_OPERATION_MANAGER,
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    _MarketplaceRegistryContext,
    _registry_git_operation,
)
from .settings_activity import MarketplaceSettingsActivityWorkflow


class MarketplaceRegistryGitWorkflow(_MarketplaceRegistrySupport):
    """Coordinate local and remote registry version-control workflows."""

    def __init__(
        self,
        *,
        context: _MarketplaceRegistryContext,
        settings_activity: MarketplaceSettingsActivityWorkflow,
    ) -> None:
        super().__init__(_context=context)
        self._settings_activity = settings_activity
        self.version_control = VersionControlApplication(
            MARKETPLACE_GIT_OPERATION_MANAGER,
            stale_threshold_seconds=self._stale_threshold,
        )

    def list_registry_file_history(
        self, *, path: str | None = None, limit: int = 50
    ) -> dict:
        normalized_path = (
            self._normalize_registry_file_path_with_core(path)
            if path is not None
            else None
        )
        return {
            "items": self.local_history.list_entries(
                domain="marketplace",
                resource_id="registry",
                path=normalized_path,
                limit=limit,
            )
        }

    @_registry_git_operation(OperationKind.WRITE, "restore_registry_file_history")
    def restore_registry_file_history(
        self,
        user_id: str,
        *,
        entry_id: str,
        revision: str | None = None,
    ) -> dict:
        try:
            entry = self.local_history.get_entry(
                domain="marketplace",
                resource_id="registry",
                entry_id=entry_id,
            )
        except KeyError as exc:
            raise FileNotFoundError("marketplace.registry.history.not_found") from exc

        if not entry.snapshot_path:
            raise FileNotFoundError("marketplace.registry.history.not_found")
        snapshot_path = Path(entry.snapshot_path)
        if not snapshot_path.exists() or not snapshot_path.is_file():
            raise FileNotFoundError("marketplace.registry.history.not_found")

        root = self.storage_root / "registry"
        relative_path = self._normalize_registry_file_path_with_core(entry.path)
        target_path = root / relative_path
        self._assert_relative_to(target_path, root)
        if target_path.exists() and revision is None:
            raise MarketplaceConflictError(
                "marketplace.registry.history.content_conflict"
            )

        content = snapshot_path.read_bytes()
        self._write_bytes_with_core(
            target_path,
            content,
            operation="restore",
            revision=revision,
        )
        self._validate_registry_file_after_restore(relative_path)
        self._invalidate_package_index(user_id)
        return {
            "path": relative_path,
            "restoredFrom": entry.id,
            "revision": sha256(content).hexdigest(),
        }

    def get_registry_repository_status(
        self, user_id: str
    ) -> MarketplaceRegistryRepositoryStatus:
        """Return current user's Marketplace registry Git repository status."""
        root = self._get_registry_root(user_id)
        is_git_repo = (root / ".git").exists()
        has_local_content = bool(self._registry_clone_blocking_entries(root))
        if not is_git_repo:
            return MarketplaceRegistryRepositoryStatus(
                is_git_repo=False,
                has_local_content=has_local_content,
                can_clone_safely=not has_local_content,
                can_init_safely=True,
                clone_blocked_reason=(
                    "VC_CLONE_TARGET_NOT_EMPTY" if has_local_content else None
                ),
            )
        status = self.version_control.read(self._target(), RepositoryStatusQuery())
        remote_url = self._git_output(root, ["remote", "get-url", "origin"]) or None
        return MarketplaceRegistryRepositoryStatus(
            is_git_repo=True,
            current_branch=status.current_branch,
            remote_url=remote_url,
            has_origin=bool(remote_url),
            has_local_content=has_local_content,
            can_clone_safely=False,
            can_init_safely=False,
            clone_blocked_reason="VC_REPOSITORY_ALREADY_INITIALIZED",
        )

    @_registry_git_operation(OperationKind.READ, "remote_branches")
    def remote_branches(
        self,
        user_id: str,
        remote_url: str,
    ) -> RemoteBranchesResponse:
        """List branches available from a remote Marketplace registry."""
        self.storage_root.mkdir(parents=True, exist_ok=True)
        try:
            result = discover_remote_branches(
                self.db,
                user_id=user_id,
                repo_root=self.storage_root,
                remote_url=remote_url,
            )
        except CoreGitCommandError as exc:
            raise MarketplaceImportSourceError(
                "marketplace.git.operation_failed"
            ) from exc
        return RemoteBranchesResponse(
            branches=result.branches,
            defaultBranch=result.default_branch,
        )

    def list_branches(self, user_id: str) -> VersionControlBranchListResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        result = self.version_control.read(self._target(), BranchListQuery())
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
        user_id: str,
        *,
        name: str,
        start_point: str,
        upstream: str | None,
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            user_id,
            BranchCreateAndSwitch(name, start_point, upstream),
        )

    def switch_branch(self, user_id: str, *, name: str) -> BranchMutationResponse:
        return self._execute_branch_command(user_id, BranchSwitch(name))

    def rename_branch(
        self, user_id: str, *, old_name: str, new_name: str
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            user_id,
            BranchRenameLocal(old_name, new_name),
        )

    def delete_branch(self, user_id: str, *, name: str) -> BranchMutationResponse:
        return self._execute_branch_command(user_id, BranchDeleteLocal(name))

    @_registry_git_operation(OperationKind.REMOTE, "publish_branch")
    def publish_branch(
        self,
        user_id: str,
        *,
        remote: str,
        remote_name: str | None,
    ) -> BranchMutationResponse:
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        remote_url = self._git_output(root, ["remote", "get-url", remote])
        with user_git_environment(
            self.db,
            user_id=user_id,
            remote_url=remote_url,
        ) as environment:
            target = MarketplaceRepositoryTargetResolver(self.storage_root).resolve(
                environment=environment
            )
            result = self.version_control.execute(
                target,
                BranchPublish(remote, remote_name),
            )
        return self._branch_mutation_response(result)

    def _execute_branch_command(self, user_id: str, command) -> BranchMutationResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        result = self.version_control.execute(self._target(), command)
        return self._branch_mutation_response(result)

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

    def _target(self, *, environment=None):
        return MarketplaceRepositoryTargetResolver(self.storage_root).resolve(
            environment=environment
        )

    def mark_conflicts_resolved(
        self, user_id: str, *, paths: list[str]
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            user_id,
            ConflictMarkResolved(tuple(paths)),
        )

    def abort_conflict(self, user_id: str) -> BranchMutationResponse:
        return self._execute_branch_command(user_id, ConflictAbort())

    def revert_commit(self, user_id: str, *, sha: str) -> BranchMutationResponse:
        return self._execute_branch_command(user_id, CommitRevert(sha))

    def update_lfs_patterns(
        self, user_id: str, *, patterns: list[str] | None = None
    ) -> BranchMutationResponse:
        return self._execute_branch_command(
            user_id,
            LfsPatternsUpdate(tuple(patterns or DEFAULT_LFS_PATTERNS)),
        )

    def get_lfs_patterns(self, user_id: str) -> LfsPatternsResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        result = self.version_control.read(self._target(), LfsPatternsQuery())
        return LfsPatternsResponse(patterns=list(result.patterns))

    def preview_lfs_snapshot(
        self, user_id: str, *, patterns: list[str] | None = None
    ) -> LfsSnapshotPreviewResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        target = self._target()
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
        self, user_id: str, *, paths: list[str]
    ) -> BranchMutationResponse:
        normalized_paths = [
            self._normalize_registry_file_path_with_core(path) for path in paths
        ]
        return self._execute_branch_command(
            user_id,
            LfsSnapshotConvert(tuple(normalized_paths)),
        )

    def cancel_operation(self, user_id: str) -> BranchMutationResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        result = self.version_control.execute(self._target(), OperationCancel())
        return self._branch_mutation_response(result)

    def initialize_git_repository(
        self,
        user_id: str,
        default_branch: str = "main",
    ) -> VersionControlStatus:
        """Initialize the current user's Marketplace registry as a Git repository."""
        with self._registry_lock:
            root = self._get_registry_root(user_id)
            if (root / ".git").exists():
                raise VersionControlError("repository_dirty")
            self._settings_activity.initialize_registry(user_id)
            self.version_control.execute(
                self._target(), RepositoryInitialize(default_branch)
            )
            return self.get_registry_status(user_id)

    def clone_registry(
        self,
        user_id: str,
        payload: MarketplaceRegistryCloneRequest,
    ) -> VersionControlStatus:
        """Clone a Marketplace registry into the current user's managed registry root."""
        with self._registry_lock:
            root = self._get_registry_root(user_id)
            if self._registry_clone_blocking_entries(root):
                raise VersionControlError("repository_dirty")
            root.parent.mkdir(parents=True, exist_ok=True)
            moved_checkout = False
            try:
                remote_url = validate_clone_remote_url(payload.remote_url)
                with user_git_environment(
                    self.db,
                    user_id=user_id,
                    remote_url=remote_url,
                ) as git_env:
                    with tempfile.TemporaryDirectory(
                        prefix="marketplace-registry-clone-",
                        dir=root.parent,
                    ) as checkout_parent:
                        checkout_root = Path(checkout_parent) / "registry"
                        staging_target = MarketplaceRepositoryTargetResolver(
                            self.storage_root
                        ).resolve_staging_clone(
                            checkout_root,
                            environment=git_env,
                        )
                        self.version_control.execute(
                            staging_target,
                            RepositoryClone(remote_url, payload.branch),
                        )
                        if (checkout_root / ".marketplace").exists():
                            raise MarketplaceImportSourceError(
                                "marketplace.registry.catalog_invalid"
                            )
                        catalog = self._read_catalog(checkout_root)
                        current_branch = self.version_control.read(
                            staging_target, RepositoryStatusQuery()
                        ).current_branch
                        if current_branch != catalog.publish_branch:
                            raise MarketplaceImportSourceError(
                                "marketplace.install.branch_mismatch"
                            )
                        root.mkdir(parents=True, exist_ok=True)
                        moved_checkout = True
                        for entry in checkout_root.iterdir():
                            shutil.move(str(entry), root / entry.name)
                self._ensure_target_client_roots(root)
                self._ensure_registry_gitignore(root, invalidation_key=user_id)
                self._generate_publish_manifests(
                    root,
                    self._read_catalog(root),
                    invalidation_key=user_id,
                )
                self._invalidate_package_index(user_id)
                return self.get_registry_status(user_id)
            except (CoreGitCommandError, OSError) as exc:
                if moved_checkout:
                    self._remove_cloned_registry_entries(root)
                git_error = self._registry_git_failure(
                    user_id,
                    getattr(exc, "stderr", "") or str(exc),
                )
                raise MarketplaceImportSourceError(git_error.code) from exc
            except MarketplaceImportSourceError:
                if moved_checkout:
                    self._remove_cloned_registry_entries(root)
                raise

    def set_registry_remote(
        self,
        user_id: str,
        remote_url: str,
    ) -> BranchMutationResponse:
        """Set current user's Marketplace registry origin remote."""
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        result = self.version_control.execute(
            self._target(),
            RemoteSettingsUpdate("origin", remote_url.strip()),
        )
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def get_remote_settings(self, user_id: str) -> RemoteSettingsResponse:
        self._require_registry_git_repo(self._get_registry_root(user_id))
        result = self.version_control.read(
            self._target(), RemoteSettingsQuery("origin")
        )
        return RemoteSettingsResponse(
            remoteName=result.remote_name,
            remoteUrl=result.remote_url,
            hasOrigin=result.has_origin,
        )

    def get_registry_changes(
        self,
        user_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
        group: Literal["all", "staged", "unstaged", "untracked", "conflicts"] = "all",
        include_stats: bool = True,
    ) -> VersionControlChangesResponse:
        """Unified changes response for the registry changes surface.

        Marketplace is single-page, so totals are derived from the lists and
        paging fields keep their defaults. ``include_stats=False`` defers numstat
        (null additions/deletions) to the ``/changes/numstat`` endpoint.
        """
        root = self._get_registry_root(user_id)
        if not (root / ".git").exists():
            return VersionControlChangesResponse()
        changes = self.version_control.read(
            self._target(), ChangesListQuery(group=group, cursor=cursor, limit=limit)
        )
        staged = [FileChange(**to_change_dict(item)) for item in changes.staged.items]
        unstaged = [
            FileChange(**to_change_dict(item)) for item in changes.unstaged.items
        ]
        untracked = [
            FileChange(**to_change_dict(item)) for item in changes.untracked.items
        ]
        conflicts = [
            FileChange(**to_change_dict(item)) for item in changes.conflicts.items
        ]
        if include_stats:
            stats = {
                item.path: (item.additions, item.deletions)
                for query in (
                    NumstatQuery(tuple(item.path for item in staged), staged=True),
                    NumstatQuery(tuple(item.path for item in unstaged), staged=False),
                )
                for item in self.version_control.read(self._target(), query).entries
            }
            for change in staged:
                stat = stats.get(change.path) or (
                    stats.get(change.oldPath) if change.oldPath else None
                )
                if stat is not None:
                    change.additions, change.deletions = stat
            for change in unstaged:
                stat = stats.get(change.path) or (
                    stats.get(change.oldPath) if change.oldPath else None
                )
                if stat is not None:
                    change.additions, change.deletions = stat
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

    def get_registry_changes_numstat(
        self,
        user_id: str,
        *,
        staged_paths: list[str],
        unstaged_paths: list[str],
    ) -> NumstatResponse:
        """Deferred numstat fill for the visible registry staged + unstaged paths."""
        root = self._get_registry_root(user_id)
        if not (root / ".git").exists():
            return NumstatResponse(stats={})
        stats = {
            item.path: (item.additions, item.deletions)
            for query in (
                NumstatQuery(tuple(staged_paths), staged=True),
                NumstatQuery(tuple(unstaged_paths), staged=False),
            )
            for item in self.version_control.read(self._target(), query).entries
        }
        return NumstatResponse(
            stats={
                path: {"additions": additions, "deletions": deletions}
                for path, (additions, deletions) in stats.items()
            }
        )

    def get_registry_status(self, user_id: str) -> VersionControlStatus:
        """Unified status response (branch + counts) for the registry status surface."""
        root = self._get_registry_root(user_id)
        if not (root / ".git").exists():
            return VersionControlStatus(
                isInitialized=False,
            )
        status = self.version_control.read(self._target(), RepositoryStatusQuery())
        return version_control_status_from_core(status)

    def get_registry_file_diff(
        self,
        user_id: str,
        path: str,
        *,
        head: Literal["WORKTREE", "INDEX"] = "WORKTREE",
    ) -> MarketplaceGitDiffResponse:
        """Return a selected registry file diff from the worktree or index."""
        root = self._get_registry_root(user_id)
        safe_path = self._resolve_registry_git_path(root, path)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError(
                "marketplace.git.repository_not_initialized"
            )
        untracked = self.version_control.read(
            self._target(), ChangesListQuery(group="untracked", limit=100_000)
        )
        if head != "INDEX" and safe_path in {
            item.path for item in untracked.untracked.items
        }:
            patch = self._untracked_registry_file_diff(root, safe_path)
            return MarketplaceGitDiffResponse(
                path=safe_path,
                patch=patch,
                diff=patch,
                binary="Binary files" in patch,
                head=head,
            )
        result = self.version_control.read(
            self._target(), DiffQuery(path=safe_path, staged=head == "INDEX")
        )
        patch = result.patch
        return MarketplaceGitDiffResponse(
            path=safe_path,
            patch=patch,
            diff=patch,
            binary="Binary files" in patch,
            head=head,
        )

    def get_registry_blob(
        self,
        user_id: str,
        *,
        path: str,
        revision: str | None = None,
    ) -> BlobResponse:
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        safe_path = self._resolve_registry_git_path(root, path)
        result = self.version_control.read(
            self._target(), BlobQuery(path=safe_path, ref=revision or "HEAD")
        )
        return BlobResponse(
            path=safe_path,
            revision=revision,
            content=result.content,
        )

    def get_registry_commit_file_diff(
        self,
        user_id: str,
        commit_id: str,
        path: str,
    ) -> MarketplaceGitDiffResponse:
        """Return a selected registry file diff for a commit."""
        root = self._get_registry_root(user_id)
        safe_path = self._resolve_registry_git_path(root, path)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError(
                "marketplace.git.repository_not_initialized"
            )
        result = self.version_control.read(
            self._target(), DiffQuery(path=safe_path, commit_sha=commit_id)
        )
        patch = result.patch
        return MarketplaceGitDiffResponse(
            path=safe_path,
            patch=patch,
            diff=patch,
            binary="Binary files" in patch,
            commit_id=commit_id,
        )

    def get_registry_commit_files(
        self, user_id: str, commit_id: str
    ) -> MarketplaceGitCommitFilesResult:
        """Return target_client-prefixed file changes for a selected commit."""
        root = self._get_registry_root(user_id)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError(
                "marketplace.git.repository_not_initialized"
            )
        result = self.version_control.read(self._target(), CommitFilesQuery(commit_id))
        files = []
        for item in result.files:
            change = self._git_file_change(
                item.path, item.status, old_path=item.original_path
            )
            change.additions = item.additions
            change.deletions = item.deletions
            change.diff = item.patch
            change.patch = item.patch
            files.append(change)
        return MarketplaceGitCommitFilesResult(commit_id=result.sha, files=files)

    def stage_registry_paths(
        self, user_id: str, payload: MarketplaceGitPathRequest
    ) -> MarketplaceGitStageResult:
        """Stage selected Marketplace registry paths."""
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        paths = (
            []
            if payload.all
            else [self._resolve_registry_git_path(root, path) for path in payload.paths]
        )
        command = StageAll() if payload.all else StagePaths(tuple(paths))
        self.version_control.execute(self._target(), command)
        return MarketplaceGitStageResult(staged=paths, unstaged=[])

    def unstage_registry_paths(
        self, user_id: str, payload: MarketplaceGitPathRequest
    ) -> MarketplaceGitUnstageResult:
        """Unstage selected Marketplace registry paths."""
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        paths = (
            []
            if payload.all
            else [self._resolve_registry_git_path(root, path) for path in payload.paths]
        )
        command = UnstageAll() if payload.all else UnstagePaths(tuple(paths))
        self.version_control.execute(self._target(), command)
        return MarketplaceGitUnstageResult(unstaged=paths, remaining_staged=0)

    def discard_registry_paths(
        self, user_id: str, payload: DiscardRequest
    ) -> DiscardResponse:
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        paths = [self._resolve_registry_git_path(root, path) for path in payload.paths]
        for path in paths:
            target = root / path
            if target.exists() and target.is_file():
                self.local_history.snapshot_file(
                    domain="marketplace",
                    resource_id="registry",
                    source_path=target,
                    relative_path=path,
                    operation="discard",
                )
        self.version_control.execute(
            self._target(),
            DiscardChanges(tuple(paths)),
        )
        self._invalidate_package_index(user_id)
        return DiscardResponse(discarded=paths, warnings=[])

    def commit_registry_changes(
        self,
        user_id: str,
        payload: MarketplaceGitCommitRequest,
    ) -> MarketplaceGitCommitResult:
        """Commit selected or already staged Marketplace registry changes."""
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        message = payload.message.strip()
        if not message:
            raise MarketplaceImportSourceError(
                "marketplace.git.commit_message_required"
            )
        status_before = self.version_control.read(
            self._target(), ChangesListQuery(group="staged", limit=1)
        )
        if not status_before.staged.items:
            return MarketplaceGitCommitResult(
                success=False,
                message_key="marketplace.git.no_changes_to_commit",
                error_code="marketplace.git.no_changes_to_commit",
            )
        actor_context = ManagerActorContextResolver(self.db).resolve(
            user_id=user_id,
            display_name="",
        )
        result = self.version_control.execute(
            self._target(),
            CommitCreate(message),
            actor_context,
        )
        history = self.version_control.read(
            self._target(),
            HistoryListQuery(scope="current", search=result.output, limit=1),
        )
        return MarketplaceGitCommitResult(
            success=True,
            message_key="marketplace.git.commit_success",
            commit=self._registry_commit_summary_from_core(history.items[0]),
        )

    def list_registry_commits(
        self,
        user_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
        query_scope: Literal["current", "all", "local", "remote"] = "current",
        branch: str | None = None,
        search: str | None = None,
    ) -> CommitListResponse:
        """List Marketplace registry commit history."""
        root = self._get_registry_root(user_id)
        if not (root / ".git").exists():
            return CommitListResponse(
                items=[],
                total=0,
                nextCursor=None,
                hasMore=False,
                queryScope=query_scope,
            )
        history = self.version_control.read(
            self._target(),
            HistoryListQuery(
                scope=query_scope,
                branch=branch,
                search=search,
                cursor=cursor,
                limit=limit,
            ),
        )
        current_branch = self.version_control.read(
            self._target(), RepositoryStatusQuery()
        ).current_branch
        return CommitListResponse(
            total=history.total,
            items=[
                CommitSummary(
                    id=summary.id,
                    message=summary.message,
                    author=summary.author,
                    email=summary.email,
                    timestamp=int(
                        datetime.fromisoformat(
                            summary.timestamp.replace("Z", "+00:00")
                        ).timestamp()
                        * 1000
                    ),
                    branch=current_branch,
                    additions=summary.additions,
                    deletions=summary.deletions,
                    files=summary.files_changed,
                )
                for commit in history.items
                for summary in [self._registry_commit_summary_from_core(commit)]
            ],
            nextCursor=history.next_cursor,
            hasMore=history.has_more,
            queryScope=history.query_scope,
        )

    def fetch_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Fetch current user's Marketplace registry remote."""
        return self._execute_remote_command(
            user_id, RemoteFetch("origin"), "marketplace.git.fetch_success"
        )

    def pull_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Pull current user's Marketplace registry remote branch."""
        status = self.version_control.read(self._target(), RepositoryStatusQuery())
        return self._execute_remote_command(
            user_id,
            RemotePullFastForward("origin", status.current_branch),
            "marketplace.git.pull_success",
        )

    @_registry_git_operation(OperationKind.REMOTE, "push_registry")
    def push_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Push current user's Marketplace registry branch to origin."""
        status = self.version_control.read(self._target(), RepositoryStatusQuery())
        return self._execute_remote_command(
            user_id,
            RemotePush("origin", status.current_branch),
            "marketplace.git.push_success",
        )

    def _execute_remote_command(
        self, user_id: str, command, message_key: str
    ) -> MarketplaceRegistryGitOperationResult:
        root = self._get_registry_root(user_id)
        self._require_registry_git_repo(root)
        remote_url = self._git_output(root, ["remote", "get-url", "origin"])
        if not remote_url:
            return MarketplaceRegistryGitOperationResult(
                success=False,
                message_key="marketplace.git.remote_required",
                error_code="marketplace.git.remote_required",
                repository=self.get_registry_repository_status(user_id),
            )
        with user_git_environment(
            self.db,
            user_id=user_id,
            remote_url=remote_url,
        ) as environment:
            self.version_control.execute(self._target(environment=environment), command)
        self._invalidate_package_index(user_id)
        return MarketplaceRegistryGitOperationResult(
            success=True,
            message_key=message_key,
            repository=self.get_registry_repository_status(user_id),
        )

    def force_unlock(self, user_id: str) -> BranchMutationResponse:
        """Clear stale Git locks through the shared application contract."""
        result = self.version_control.execute(self._target(), OperationForceUnlock())
        return BranchMutationResponse(
            commandId=result.command_id,
            headSha=result.head_sha,
            branch=result.branch,
            affectedTotal=result.affected_total,
            skippedTotal=result.skipped_total,
            output=result.output,
        )

    def get_registry_operation_status(
        self, user_id: str
    ) -> VersionControlOperationStatus:
        """Return the in-progress operation status without acquiring Git locks.

        Reads the operation manager's active mutating operation for this user's
        shared registry (READ operations never register, so this reflects only
        a write/working-tree/remote op in flight). This powers the client-side
        operation-status polling so the UI can uniformly disable writes and
        refresh on completion — aligned with workspace-runtime's
        ``get_operation_status`` and the knowledge-base equivalent.

        Not routed through ``_run_registry_operation`` (it must not acquire a
        lock); it only reads the manager state for the user's registry key.
        """
        target = self._target()
        metadata = MARKETPLACE_GIT_OPERATION_MANAGER.active_operation(
            target.lock_scope_keys.working_tree_target
        ) or MARKETPLACE_GIT_OPERATION_MANAGER.active_operation(
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
