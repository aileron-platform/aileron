"""Deterministic job-owned Automation worktrees."""

from __future__ import annotations

import asyncio
import errno
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from aileron_git_core import GitCommandError, git_allow_failure, run_git

from app.config.settings import get_settings
from app.modules.version_control.git_operations import GitService
from app.modules.version_control.repository import VersionControlError

_JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_OPERATION_MARKERS = (
    "MERGE_HEAD",
    "rebase-merge",
    "rebase-apply",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
)
_LOCK_PATHS = (
    "index.lock",
    "HEAD.lock",
    "config.lock",
    "packed-refs.lock",
    "shallow.lock",
)
_STORAGE_ERROR_TEXT = ("no space left on device", "disk quota exceeded")


@dataclass(frozen=True)
class WorktreeContext:
    context_id: str
    path: Path
    branch: str


class AutomationWorktreeError(Exception):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class _WorktreeRegistration:
    path: Path
    branch: str | None


class AutomationWorktreeService:
    def __init__(
        self,
        *,
        git_service: GitService,
        workspace_id: str,
        disk_threshold: float | None = None,
    ) -> None:
        self._git_service = git_service
        self._workspace_id = workspace_id
        self._disk_threshold = (
            get_settings().DISK_THRESHOLD if disk_threshold is None else disk_threshold
        )

    async def validate_workspace(self) -> None:
        """Validate that the workspace can host job-owned Git worktrees."""
        try:
            await asyncio.to_thread(self._validate_workspace_locked)
        except VersionControlError as exc:
            if exc.error_code == "repository_not_initialized":
                raise self._error(
                    "workspace_git_repository_required",
                    "Workspace must be a Git repository with an initial commit",
                ) from exc
            raise

    async def ensure_for_job(
        self, *, job_id: str, worktree_key: str
    ) -> WorktreeContext:
        context = self._context_for(job_id=job_id, worktree_key=worktree_key)
        try:
            return await asyncio.to_thread(
                self._git_service.run_serialized_worktree_operation,
                workspace_id=self._workspace_id,
                context_ids=(None, context.context_id),
                operation_name="ensure_automation_worktree",
                callback=lambda: self._ensure_locked(context),
            )
        except VersionControlError as exc:
            if exc.error_code == "VC_OPERATION_IN_PROGRESS":
                raise self._error(
                    "worktree_locked",
                    "Automation worktree is locked by another operation",
                ) from exc
            raise

    async def preflight(self, context: WorktreeContext) -> None:
        self._validate_context(context)
        try:
            await asyncio.to_thread(
                self._git_service.run_serialized_worktree_operation,
                workspace_id=self._workspace_id,
                context_ids=(context.context_id,),
                operation_name="preflight_automation_worktree",
                callback=lambda: self._preflight_locked(context),
            )
        except VersionControlError as exc:
            if exc.error_code == "VC_OPERATION_IN_PROGRESS":
                raise self._error(
                    "worktree_locked",
                    "Automation worktree is locked by another operation",
                ) from exc
            raise

    def _context_for(self, *, job_id: str, worktree_key: str) -> WorktreeContext:
        expected_key = f"automation/{job_id}"
        if not _JOB_ID_PATTERN.fullmatch(job_id) or worktree_key != expected_key:
            raise self._error(
                "worktree_conflict",
                "Automation worktree identity does not match its job",
            )
        managed_root = self._git_service.managed_worktree_root(self._workspace_id)
        return WorktreeContext(
            context_id=f"worktree:automation--{job_id}",
            path=managed_root / "automation" / job_id,
            branch=expected_key,
        )

    def _validate_workspace_locked(self) -> None:
        primary = self._git_service._utils.get_repo(  # noqa: SLF001
            self._workspace_id
        ).root
        if git_allow_failure(primary, "rev-parse", "--verify", "HEAD").returncode != 0:
            raise self._error(
                "workspace_git_initial_commit_required",
                "Workspace Git repository must have an initial commit",
            )
        self._check_storage(primary)
        try:
            self._registrations(primary)
        except GitCommandError as exc:
            raise self._error(
                "worktree_conflict",
                "Workspace Git worktrees cannot be inspected",
            ) from exc

    def _validate_context(self, context: WorktreeContext) -> None:
        prefix = "automation/"
        if not context.branch.startswith(prefix):
            raise self._error("worktree_conflict", "Invalid Automation branch")
        job_id = context.branch.removeprefix(prefix)
        expected = self._context_for(job_id=job_id, worktree_key=context.branch)
        if context != expected:
            raise self._error(
                "worktree_conflict", "Automation worktree context does not match"
            )

    def _ensure_locked(self, context: WorktreeContext) -> WorktreeContext:
        primary = self._git_service._utils.get_repo(
            self._workspace_id
        ).root  # noqa: SLF001
        registrations = self._registrations(primary)
        target = context.path.resolve()
        target_registration = next(
            (
                registration
                for registration in registrations
                if registration.path == target
            ),
            None,
        )
        branch_registration = next(
            (
                registration
                for registration in registrations
                if registration.branch == context.branch
            ),
            None,
        )
        branch_exists = (
            git_allow_failure(
                primary,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{context.branch}",
            ).returncode
            == 0
        )

        if target_registration is not None:
            registration_matches = (
                branch_exists
                and target_registration.branch in {context.branch, None}
                and branch_registration in {target_registration, None}
                and context.path.is_dir()
                and self._is_registered_worktree(context)
            )
            if not registration_matches:
                raise self._error(
                    "worktree_conflict",
                    "Automation worktree registration does not match",
                )
            if self._operation_in_progress(context.path):
                return context
            if (
                target_registration.branch != context.branch
                or branch_registration != target_registration
                or not self._is_expected_worktree(context)
            ):
                raise self._error(
                    "worktree_conflict",
                    "Automation worktree registration does not match",
                )
            return context

        if branch_registration is not None or context.path.exists():
            raise self._error(
                "worktree_conflict", "Automation worktree path or branch is in use"
            )

        self._check_storage(primary)
        try:
            context.path.parent.mkdir(parents=True, exist_ok=True)
            if not branch_exists:
                run_git(primary, "branch", context.branch, "HEAD")
            run_git(primary, "worktree", "add", str(context.path), context.branch)
        except OSError as exc:
            if exc.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise self._error(
                    "worktree_storage_limit",
                    "Insufficient storage for Automation worktree",
                ) from exc
            raise
        except GitCommandError as exc:
            if self._is_storage_error(exc):
                raise self._error(
                    "worktree_storage_limit",
                    "Insufficient storage for Automation worktree",
                ) from exc
            raise self._error(
                "worktree_conflict", "Unable to create Automation worktree"
            ) from exc

        self._git_service.invalidate_context_path_cache(self._workspace_id)
        if not self._is_expected_worktree(context):
            raise self._error(
                "worktree_conflict", "Created Automation worktree does not match"
            )
        return context

    def _preflight_locked(self, context: WorktreeContext) -> None:
        if not context.path.is_dir():
            raise self._error(
                "worktree_conflict", "Automation worktree path does not exist"
            )
        try:
            operation_in_progress = self._operation_in_progress(context.path)
            worktree_locked = any(
                lock_path.exists() for lock_path in self._lock_paths(context)
            )
        except GitCommandError as exc:
            raise self._error(
                "worktree_conflict", "Automation worktree cannot be inspected"
            ) from exc

        if operation_in_progress:
            raise self._error(
                "worktree_operation_in_progress",
                "Automation worktree has an incomplete Git operation",
            )
        if worktree_locked:
            raise self._error("worktree_locked", "Automation worktree has a Git lock")

        primary = self._git_service._utils.get_repo(
            self._workspace_id
        ).root  # noqa: SLF001
        registration = next(
            (
                item
                for item in self._registrations(primary)
                if item.path == context.path.resolve()
            ),
            None,
        )
        if (
            registration is None
            or registration.branch != context.branch
            or not self._is_expected_worktree(context)
        ):
            raise self._error(
                "worktree_conflict", "Automation worktree registration does not match"
            )

    @staticmethod
    def _registrations(primary: Path) -> list[_WorktreeRegistration]:
        output = run_git(primary, "worktree", "list", "--porcelain").stdout
        registrations: list[_WorktreeRegistration] = []
        for block in output.split("\n\n"):
            metadata: dict[str, str] = {}
            for line in block.splitlines():
                key, _, value = line.partition(" ")
                if key:
                    metadata[key] = value.strip()
            raw_path = metadata.get("worktree")
            if not raw_path:
                continue
            branch_ref = metadata.get("branch")
            branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
            registrations.append(
                _WorktreeRegistration(path=Path(raw_path).resolve(), branch=branch)
            )
        return registrations

    @staticmethod
    def _git_path(repo: Path, name: str) -> Path:
        raw_path = run_git(repo, "rev-parse", "--git-path", name).stdout.strip()
        path = Path(raw_path)
        return path if path.is_absolute() else repo / path

    def _lock_paths(self, context: WorktreeContext) -> tuple[Path, ...]:
        lock_names = (*_LOCK_PATHS, f"refs/heads/{context.branch}.lock")
        return tuple(self._git_path(context.path, name) for name in lock_names)

    def _operation_in_progress(self, path: Path) -> bool:
        return any(
            self._git_path(path, marker).exists() for marker in _OPERATION_MARKERS
        )

    @staticmethod
    def _is_registered_worktree(context: WorktreeContext) -> bool:
        try:
            root = Path(
                run_git(context.path, "rev-parse", "--show-toplevel").stdout.strip()
            ).resolve()
        except GitCommandError:
            return False
        return root == context.path.resolve()

    @staticmethod
    def _is_expected_worktree(context: WorktreeContext) -> bool:
        if not AutomationWorktreeService._is_registered_worktree(context):
            return False
        try:
            branch = run_git(context.path, "branch", "--show-current").stdout.strip()
        except GitCommandError:
            return False
        return branch == context.branch

    def _check_storage(self, path: Path) -> None:
        try:
            usage = shutil.disk_usage(path)
        except OSError as exc:
            if exc.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise self._error(
                    "worktree_storage_limit",
                    "Unable to inspect Automation worktree storage",
                ) from exc
            raise
        used_percent = (usage.used / usage.total * 100) if usage.total else 100.0
        if used_percent >= self._disk_threshold:
            raise self._error(
                "worktree_storage_limit",
                "Automation worktree storage threshold exceeded",
            )

    @staticmethod
    def _is_storage_error(exc: GitCommandError) -> bool:
        message = "\n".join((str(exc), exc.stdout or "", exc.stderr or "")).lower()
        return any(fragment in message for fragment in _STORAGE_ERROR_TEXT)

    @staticmethod
    def _error(error_code: str, message: str) -> AutomationWorktreeError:
        return AutomationWorktreeError(message, error_code=error_code)


__all__ = [
    "AutomationWorktreeError",
    "AutomationWorktreeService",
    "WorktreeContext",
]
