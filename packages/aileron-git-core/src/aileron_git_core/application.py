import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional, Union

from .command_runner import git_allow_failure, run_git
from .branches import create_and_switch, delete_local, publish, rename_local, switch
from .contracts import (
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
    DiffQuery,
    DiscardChanges,
    HistoryListQuery,
    LfsPatternsQuery,
    LfsPatternsUpdate,
    LfsSnapshotConvert,
    LfsSnapshotPreview,
    MutationCommand,
    NumstatQuery,
    OperationCancel,
    OperationForceUnlock,
    ReadQuery,
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
    VersionControlOperation,
)
from .errors import (
    GitCommandError,
    GitOperationInProgressError,
    GitStaleLockError,
    VersionControlError,
)
from .conflicts import abort_conflict, mark_resolved, revert_commit
from .history import read_blob, read_commit_files, read_diff, read_history
from .lfs import convert_snapshot, preview_snapshot, read_patterns, update_patterns
from .numstat import read_numstat
from .models import (
    BranchCapabilities,
    BranchList,
    BranchSummary,
    BlobResult,
    Capability,
    ChangePage,
    CommitHistoryPage,
    CommitFilesResult,
    DiffResult,
    LfsPatterns,
    LfsSnapshotPreviewResult,
    MutationResult,
    NumstatResult,
    PagedChanges,
    RepositoryStatus,
    RemoteSettings,
)
from .operation_lock import OperationManager
from .mutations import (
    fetch_remote,
    pull_remote,
    push_remote,
    stage_all,
    stage_paths,
    unstage_all,
    unstage_paths,
)
from .status import collect_status
from .stale_lock import (
    DEFAULT_STALE_THRESHOLD_SECONDS,
    clear_locks,
    detect_stale_locks,
    has_live_git_process,
    with_stale_lock_recovery,
)


ReadResult = Union[
    RepositoryStatus,
    BranchList,
    PagedChanges,
    CommitHistoryPage,
    CommitFilesResult,
    DiffResult,
    BlobResult,
    LfsPatterns,
    RemoteSettings,
    NumstatResult,
]
ExecuteResult = Union[MutationResult, LfsSnapshotPreviewResult]


class VersionControlApplication:
    """Shared typed application boundary for product-specific adapters."""

    def __init__(
        self,
        operation_manager: Optional[OperationManager] = None,
        *,
        stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
    ) -> None:
        if stale_threshold_seconds < 0:
            raise ValueError("Stale threshold must not be negative")
        self.operation_manager = operation_manager or OperationManager()
        self.stale_threshold_seconds = stale_threshold_seconds

    def read(self, target: RepositoryTarget, query: ReadQuery) -> ReadResult:
        try:
            with self.operation_manager.acquire_read_scoped(target.lock_scope_keys):
                # Status and branch queries describe the repository itself, so they
                # answer for an uninitialized target instead of failing.
                if isinstance(query, RepositoryStatusQuery):
                    return self._read_status(target)
                if isinstance(query, BranchListQuery):
                    return self._read_branches(target)
                if not _is_initialized(target.root):
                    raise VersionControlError("repository_not_initialized")
                if isinstance(query, ChangesListQuery):
                    return self._read_changes(target, query)
                if isinstance(query, NumstatQuery):
                    return read_numstat(
                        target.root,
                        paths=_validated_paths(query.paths),
                        staged=query.staged,
                        commit_sha=query.commit_sha,
                    )
                if isinstance(query, CommitFilesQuery):
                    return read_commit_files(target.root, query.sha)
                if isinstance(query, HistoryListQuery):
                    return read_history(
                        target.root,
                        scope=query.scope,
                        branch=query.branch,
                        search=query.search,
                        cursor=query.cursor,
                        limit=query.limit,
                    )
                if isinstance(query, DiffQuery):
                    _validate_path(query.path)
                    return read_diff(
                        target.root,
                        path=query.path,
                        staged=query.staged,
                        commit_sha=query.commit_sha,
                    )
                if isinstance(query, BlobQuery):
                    _validate_path(query.path)
                    return read_blob(target.root, path=query.path, ref=query.ref)
                if isinstance(query, LfsPatternsQuery):
                    return read_patterns(target.root)
                if isinstance(query, RemoteSettingsQuery):
                    return _read_remote_settings(target.root, query.name)
        except GitOperationInProgressError as exc:
            raise self._operation_locked(exc) from exc
        except GitCommandError as exc:
            raise VersionControlError(
                "file_conflict", diagnostic=exc.stderr.strip()
            ) from exc
        raise TypeError(f"Unsupported version control query: {type(query).__name__}")

    def execute(
        self,
        target: RepositoryTarget,
        command: MutationCommand,
        actor_context: Optional[ActorContext] = None,
    ) -> ExecuteResult:
        try:
            operation = VersionControlOperation(command.command_id)
        except ValueError as exc:
            raise TypeError(
                f"Unsupported version control command: {type(command).__name__}"
            ) from exc
        actor_display_name = actor_context.display_name if actor_context else ""
        try:
            with self.operation_manager.acquire_scoped(
                target.lock_scope_keys,
                operation,
                actor_display_name=actor_display_name,
            ):
                if isinstance(command, OperationForceUnlock):
                    return self._execute_unlocked(target, command, actor_context)
                return with_stale_lock_recovery(
                    target.root,
                    lambda: self._execute_unlocked(target, command, actor_context),
                    threshold_seconds=self.stale_threshold_seconds,
                )
        except GitStaleLockError as exc:
            raise VersionControlError(
                "operation_locked",
                diagnostic="stale_git_lock",
                stale=True,
                can_force_unlock=True,
            ) from exc
        except GitOperationInProgressError as exc:
            raise self._operation_locked(exc) from exc
        except GitCommandError as exc:
            raise VersionControlError(
                "file_conflict", diagnostic=exc.stderr.strip()
            ) from exc

    def _operation_locked(
        self, exc: GitOperationInProgressError
    ) -> VersionControlError:
        active = self.operation_manager.active_operation(exc.key)
        stale = bool(
            active
            and (
                datetime.now(timezone.utc) - active.started_at
            ).total_seconds()
            >= self.stale_threshold_seconds
        )
        if active and active.stale != stale:
            active = replace(active, stale=stale, retryable=True)
        return VersionControlError(
            "operation_locked",
            blocking_scope=exc.blocking_scope,
            operation_status=active,
            stale=stale,
            can_force_unlock=stale,
        )

    def _execute_unlocked(
        self,
        target: RepositoryTarget,
        command: MutationCommand,
        actor_context: Optional[ActorContext],
    ) -> ExecuteResult:
        _ = actor_context
        if isinstance(command, OperationCancel):
            if not self.operation_manager.request_cancel(
                target.lock_scope_keys.working_tree_target
            ):
                raise VersionControlError("operation_not_cancellable")
            return MutationResult(command_id=command.command_id)
        if isinstance(command, OperationForceUnlock):
            stale = detect_stale_locks(
                target.root, self.stale_threshold_seconds
            )
            if not stale or has_live_git_process(target.root):
                raise VersionControlError("operation_lock_not_stale")
            cleared = clear_locks(target.root, force=True)
            return _mutation_result(
                target.root,
                command.command_id,
                affected_total=len(cleared),
            )
        if isinstance(command, RepositoryInitialize):
            target.root.mkdir(parents=True, exist_ok=True)
            if _is_initialized(target.root):
                raise VersionControlError("repository_dirty")
            run_git(target.root, "init", "-b", command.default_branch)
            return _mutation_result(target.root, command.command_id, branch=command.default_branch)
        if isinstance(command, RepositoryClone):
            if target.root.exists() and any(target.root.iterdir()):
                raise VersionControlError("repository_dirty")
            target.root.parent.mkdir(parents=True, exist_ok=True)
            args = ["clone"]
            if command.branch:
                args.extend(["--branch", command.branch])
            args.extend(["--", command.remote_url, target.root.name])
            run_git(target.root.parent, *args, env=target.environment)
            return _mutation_result(target.root, command.command_id)
        if isinstance(command, BranchCreateAndSwitch):
            branch = create_and_switch(
                target, command.name, command.start_point, command.upstream
            )
            return _mutation_result(target.root, command.command_id, branch=branch)
        if isinstance(command, BranchSwitch):
            branch = switch(target, command.name)
            return _mutation_result(target.root, command.command_id, branch=branch)
        if isinstance(command, BranchRenameLocal):
            branch = rename_local(target, command.old_name, command.new_name)
            return _mutation_result(target.root, command.command_id, branch=branch)
        if isinstance(command, BranchDeleteLocal):
            branch = delete_local(target, command.name)
            return _mutation_result(target.root, command.command_id, branch=branch)
        if isinstance(command, BranchPublish):
            upstream = publish(target, command.remote, command.remote_name)
            return _mutation_result(target.root, command.command_id, output=upstream)
        if isinstance(command, RemoteFetch):
            output = "\n".join(
                fetch_remote(target.root, command.remote, env=target.environment)
            )
            return _mutation_result(target.root, command.command_id, output=output)
        if isinstance(command, RemotePullFastForward):
            _require_clean_for_sync(target.root)
            try:
                output, _ = pull_remote(
                    target.root,
                    command.remote,
                    command.branch,
                    env=target.environment,
                )
            except Exception as exc:
                from .errors import GitCommandError

                if isinstance(exc, GitCommandError):
                    raise VersionControlError(
                        "fast_forward_required", diagnostic=exc.stderr.strip()
                    ) from exc
                raise
            return _mutation_result(target.root, command.command_id, output=output)
        if isinstance(command, RemotePush):
            pushed = push_remote(
                target.root,
                command.remote,
                command.branch,
                env=target.environment,
            )
            if any(item.status != "ok" for item in pushed):
                raise VersionControlError(
                    "remote_history_incompatible",
                    diagnostic="\n".join(item.summary for item in pushed),
                )
            return _mutation_result(
                target.root,
                command.command_id,
                output="\n".join(item.summary for item in pushed),
            )
        if isinstance(command, RemoteSettingsUpdate):
            if not command.name or not command.url:
                raise VersionControlError("upstream_missing")
            if git_allow_failure(target.root, "remote", "get-url", command.name).returncode == 0:
                run_git(target.root, "remote", "set-url", command.name, command.url)
            else:
                run_git(target.root, "remote", "add", command.name, command.url)
            return _mutation_result(target.root, command.command_id, output=command.name)
        if isinstance(command, StagePaths):
            paths = _validated_paths(command.paths)
            stage_paths(target.root, paths)
            return _mutation_result(
                target.root, command.command_id, affected_total=len(paths)
            )
        if isinstance(command, UnstagePaths):
            paths = _validated_paths(command.paths)
            unstage_paths(target.root, paths)
            return _mutation_result(
                target.root, command.command_id, affected_total=len(paths)
            )
        if isinstance(command, StageAll):
            before = collect_status(target.root)
            affected = len(before.unstaged) + len(before.untracked) + len(before.conflicts)
            stage_all(target.root)
            return _mutation_result(
                target.root, command.command_id, affected_total=affected
            )
        if isinstance(command, UnstageAll):
            affected = len(collect_status(target.root).staged)
            unstage_all(target.root)
            return _mutation_result(
                target.root, command.command_id, affected_total=affected
            )
        if isinstance(command, DiscardChanges):
            paths = _validated_paths(command.paths)
            affected = _discard(target.root, paths)
            return _mutation_result(
                target.root, command.command_id, affected_total=affected
            )
        if isinstance(command, CommitCreate):
            result = _commit(target, command, actor_context)
            return _mutation_result(
                target.root,
                command.command_id,
                branch=_current_branch(target.root),
                output=result,
            )
        if isinstance(command, ConflictMarkResolved):
            paths = _validated_paths(command.paths)
            mark_resolved(target.root, paths)
            return _mutation_result(
                target.root, command.command_id, affected_total=len(paths)
            )
        if isinstance(command, ConflictAbort):
            output = abort_conflict(target.root)
            return _mutation_result(target.root, command.command_id, output=output)
        if isinstance(command, CommitRevert):
            sha = revert_commit(
                target.root,
                command.sha,
                environment=_actor_environment(target, actor_context),
            )
            return _mutation_result(target.root, command.command_id, output=sha)
        if isinstance(command, LfsPatternsUpdate):
            patterns = update_patterns(target.root, command.patterns)
            stage_paths(target.root, (".gitattributes",))
            return _mutation_result(
                target.root,
                command.command_id,
                affected_total=len(patterns.patterns),
            )
        if isinstance(command, LfsSnapshotPreview):
            matched_total, total_size, path_sample = preview_snapshot(
                target.root, command.patterns
            )
            return LfsSnapshotPreviewResult(
                matched_total=matched_total,
                total_size=total_size,
                path_sample=path_sample,
            )
        if isinstance(command, LfsSnapshotConvert):
            paths = _validated_paths(command.paths)
            key = target.lock_scope_keys.working_tree_target
            converted = convert_snapshot(
                target.root,
                paths,
                progress=lambda current, total: self.operation_manager.update_progress(
                    key,
                    current=current,
                    total=total,
                    phase="renormalizing",
                ),
                is_cancel_requested=lambda: self.operation_manager.is_cancel_requested(
                    key
                ),
                environment=target.environment,
            )
            return _mutation_result(
                target.root,
                command.command_id,
                affected_total=len(converted),
                paths=converted,
            )
        raise TypeError(f"Unsupported version control command: {type(command).__name__}")

    def _read_status(self, target: RepositoryTarget) -> RepositoryStatus:
        if not _is_initialized(target.root):
            return RepositoryStatus(
                is_initialized=False,
                current_branch=None,
                detached_head=False,
                head_sha=None,
                has_origin=False,
                upstream=None,
                ahead=0,
                behind=0,
                has_conflicts=False,
                staged_total=0,
                unstaged_total=0,
                untracked_total=0,
                conflict_total=0,
            )
        current_branch = _current_branch(target.root)
        head_sha = _optional_git(target.root, "rev-parse", "--verify", "HEAD")
        upstream = _optional_git(
            target.root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
        ahead, behind = _ahead_behind(target.root, "HEAD", upstream)
        status = collect_status(target.root)
        active = self.operation_manager.active_operation(
            target.lock_scope_keys.working_tree_target
        ) or self.operation_manager.active_operation(target.lock_scope_keys.common_repository)
        return RepositoryStatus(
            is_initialized=True,
            current_branch=current_branch,
            detached_head=head_sha is not None and current_branch is None,
            head_sha=head_sha,
            has_origin=_has_remote(target.root, "origin"),
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            has_conflicts=bool(status.conflicts),
            staged_total=len(status.staged),
            unstaged_total=len(status.unstaged),
            untracked_total=len(status.untracked),
            conflict_total=len(status.conflicts),
            operation_status=active,
        )

    def _read_branches(self, target: RepositoryTarget) -> BranchList:
        if not _is_initialized(target.root):
            return BranchList(branches=[])
        current = _current_branch(target.root)
        result = run_git(
            target.root,
            "for-each-ref",
            "--format=%(refname)%00%(upstream:short)",
            "refs/heads",
            "refs/remotes",
        )
        branches = []
        for line in result.stdout.splitlines():
            refname, _, upstream = line.partition("\0")
            if refname.endswith("/HEAD"):
                continue
            if refname.startswith("refs/heads/"):
                name = refname[len("refs/heads/") :]
                ahead, behind = _ahead_behind(target.root, name, upstream or None)
                occupied = name in target.checked_out_branches and name != current
                branches.append(
                    BranchSummary(
                        name=name,
                        display_name=name,
                        kind="local",
                        is_current=name == current,
                        upstream=upstream or None,
                        ahead=ahead,
                        behind=behind,
                        checked_out_target=name if occupied else None,
                        capabilities=BranchCapabilities(
                            switch=Capability(
                                allowed=name != current and not occupied,
                                disabled_reason_key=(
                                    "versionControl.branch.current"
                                    if name == current
                                    else (
                                        "versionControl.branch.checkedOut"
                                        if occupied
                                        else None
                                    )
                                ),
                            ),
                            rename=Capability(
                                allowed=not occupied,
                                disabled_reason_key=(
                                    "versionControl.branch.checkedOut" if occupied else None
                                ),
                            ),
                            delete=Capability(
                                allowed=name != current and not occupied,
                                disabled_reason_key=(
                                    "versionControl.branch.current"
                                    if name == current
                                    else (
                                        "versionControl.branch.checkedOut"
                                        if occupied
                                        else None
                                    )
                                ),
                            ),
                        ),
                    )
                )
            elif refname.startswith("refs/remotes/"):
                name = refname[len("refs/remotes/") :]
                reason = "versionControl.branch.remoteTrackingRequired"
                branches.append(
                    BranchSummary(
                        name=name,
                        display_name=name,
                        kind="remote",
                        is_current=False,
                        upstream=None,
                        ahead=0,
                        behind=0,
                        checked_out_target=None,
                        capabilities=BranchCapabilities(
                            switch=Capability(False, reason),
                            rename=Capability(False, "versionControl.branch.localOnly"),
                            delete=Capability(False, "versionControl.branch.localOnly"),
                        ),
                    )
                )
        if current and not any(
            branch.kind == "local" and branch.name == current for branch in branches
        ):
            branches.append(
                BranchSummary(
                    name=current,
                    display_name=current,
                    kind="local",
                    is_current=True,
                    upstream=None,
                    ahead=0,
                    behind=0,
                    checked_out_target=None,
                    capabilities=BranchCapabilities(
                        switch=Capability(
                            allowed=False,
                            disabled_reason_key="versionControl.branch.current",
                        ),
                        rename=Capability(allowed=True),
                        delete=Capability(
                            allowed=False,
                            disabled_reason_key="versionControl.branch.current",
                        ),
                    ),
                )
            )
        branches.sort(key=lambda branch: (branch.kind != "local", branch.name))
        return BranchList(branches=branches)

    def _read_changes(
        self, target: RepositoryTarget, query: ChangesListQuery
    ) -> PagedChanges:
        if query.limit < 1:
            raise ValueError("Changes limit must be positive")
        offset = int(query.cursor or "0")
        status = collect_status(target.root)

        def page(items):
            selected = list(items[offset : offset + query.limit])
            next_offset = offset + len(selected)
            return ChangePage(
                items=selected,
                total=len(items),
                next_cursor=str(next_offset) if next_offset < len(items) else None,
                has_more=next_offset < len(items),
            )

        empty = ChangePage(items=[], total=0, next_cursor=None, has_more=False)
        groups = {
            "staged": page(status.staged),
            "unstaged": page(status.unstaged),
            "untracked": page(status.untracked),
            "conflicts": page(status.conflicts),
        }
        if query.group != "all":
            if query.group not in groups:
                raise ValueError("Unknown change group")
            groups = {
                name: value if name == query.group else empty
                for name, value in groups.items()
            }
        return PagedChanges(**groups)


def _is_initialized(repo_root: Path) -> bool:
    result = git_allow_failure(repo_root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _current_branch(repo_root: Path) -> Optional[str]:
    return _optional_git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD")


def _optional_git(repo_root: Path, *args: str) -> Optional[str]:
    result = git_allow_failure(repo_root, *args)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _has_remote(repo_root: Path, name: str) -> bool:
    return git_allow_failure(repo_root, "remote", "get-url", name).returncode == 0


def _read_remote_settings(repo_root: Path, name: str) -> RemoteSettings:
    remote_name = name.strip()
    if (
        not remote_name
        or remote_name.startswith("-")
        or any(character.isspace() for character in remote_name)
    ):
        raise VersionControlError("file_conflict")
    result = git_allow_failure(repo_root, "remote", "get-url", remote_name)
    remote_url = result.stdout.strip() if result.returncode == 0 else ""
    return RemoteSettings(
        remote_name=remote_name,
        remote_url=remote_url or None,
        has_origin=bool(remote_url),
    )


def _ahead_behind(
    repo_root: Path, local_ref: str, upstream_ref: Optional[str]
) -> tuple[int, int]:
    if not upstream_ref:
        return 0, 0
    result = git_allow_failure(
        repo_root, "rev-list", "--left-right", "--count", f"{local_ref}...{upstream_ref}"
    )
    if result.returncode != 0:
        return 0, 0
    left, _, right = result.stdout.strip().partition("\t")
    return int(left or "0"), int(right or "0")


def _mutation_result(
    repo_root: Path,
    command_id: str,
    *,
    branch: Optional[str] = None,
    affected_total: int = 0,
    skipped_total: int = 0,
    output: str = "",
    paths: tuple[str, ...] = (),
) -> MutationResult:
    return MutationResult(
        command_id=command_id,
        head_sha=_optional_git(repo_root, "rev-parse", "--verify", "HEAD"),
        branch=branch,
        affected_total=affected_total,
        skipped_total=skipped_total,
        output=output,
        paths=paths,
    )


def _require_clean_for_sync(repo_root: Path) -> None:
    status = collect_status(repo_root)
    if status.staged or status.unstaged or status.untracked or status.conflicts:
        raise VersionControlError("repository_dirty")


def _validate_path(path: str) -> str:
    candidate = PurePosixPath(path)
    if not path or candidate.is_absolute() or ".." in candidate.parts:
        raise VersionControlError("file_conflict")
    return path


def _validated_paths(paths) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_validate_path(path) for path in paths))


def _discard(repo_root: Path, paths: tuple[str, ...]) -> int:
    status = collect_status(repo_root)
    tracked = {item.path for item in status.staged + status.unstaged + status.conflicts}
    untracked = {item.path for item in status.untracked}
    affected = 0
    tracked_paths = [path for path in paths if path in tracked]
    if tracked_paths:
        if _optional_git(repo_root, "rev-parse", "--verify", "HEAD"):
            run_git(
                repo_root,
                "restore",
                "--source=HEAD",
                "--staged",
                "--worktree",
                "--",
                *tracked_paths,
            )
        else:
            unstage_paths(repo_root, tracked_paths)
        affected += len(tracked_paths)
    for path in paths:
        if path not in untracked:
            continue
        resolved = (repo_root / path).resolve()
        if repo_root.resolve() not in resolved.parents:
            raise VersionControlError("file_conflict")
        if resolved.is_dir():
            shutil.rmtree(resolved)
        elif resolved.exists() or resolved.is_symlink():
            resolved.unlink()
        affected += 1
    return affected


def _commit(
    target: RepositoryTarget,
    command: CommitCreate,
    actor_context: Optional[ActorContext],
) -> str:
    environment = _actor_environment(target, actor_context)
    if collect_status(target.root).conflicts:
        raise VersionControlError("unresolved_conflicts")
    if not command.message.strip():
        raise VersionControlError("file_conflict")
    try:
        run_git(
            target.root,
            "commit",
            "-m",
            command.message,
            env=environment,
        )
    except GitCommandError as exc:
        raise VersionControlError("file_conflict", diagnostic=exc.stderr.strip()) from exc
    return run_git(target.root, "rev-parse", "HEAD").stdout.strip()


def _actor_environment(
    target: RepositoryTarget,
    actor_context: Optional[ActorContext],
) -> dict[str, str]:
    if (
        not actor_context
        or not actor_context.git_name.strip()
        or not actor_context.git_email.strip()
    ):
        raise VersionControlError("git_identity_missing")
    return {
        **dict(target.environment),
        "GIT_AUTHOR_NAME": actor_context.git_name,
        "GIT_AUTHOR_EMAIL": actor_context.git_email,
        "GIT_COMMITTER_NAME": actor_context.git_name,
        "GIT_COMMITTER_EMAIL": actor_context.git_email,
    }
