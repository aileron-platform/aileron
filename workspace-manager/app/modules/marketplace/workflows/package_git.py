"""Private Marketplace git support mixin."""

from __future__ import annotations

import difflib
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from aileron_git_core import CommitSummary as CoreCommitSummary
from aileron_git_core import GitCommandError as CoreGitCommandError
from aileron_git_core import (
    GitOperationInProgressError,
    GitStaleLockError,
    LockScope,
    OperationKind,
    VersionControlError,
    git_allow_failure,
    run_git,
    run_operation,
)
from aileron_git_core.stale_lock import _is_lock_signature

from app.modules.marketplace.models import (
    MarketplaceGitCommitSummary,
    MarketplaceImportSource,
)
from app.modules.version_control.models import FileChange

from .registry_operations import (
    _LOGGER,
    MARKETPLACE_GIT_OPERATION_IN_PROGRESS,
    MARKETPLACE_GIT_OPERATION_MANAGER,
    MarketplaceImportSourceError,
    MarketplacePathError,
    T,
)


class _MarketplaceGitSupport:
    """Provide git support behavior to the composed private kernel."""

    def _registry_operation_key(self, user_id: str) -> str:
        """Return the operation key for the shared Marketplace registry."""
        _ = user_id
        return "marketplace:registry"

    def _run_registry_operation(
        self,
        user_id: str,
        *,
        kind: OperationKind,
        operation_name: str,
        callback: Callable[[], T],
    ) -> T:
        """Acquire the registry operation lock and run ``callback``.

        Non-READ callbacks are wrapped with ``with_stale_lock_recovery`` so a
        stale on-disk git lock can be auto-cleared; the repo root is resolved
        internally via ``get_registry_root`` so callers stay unchanged. Both
        conflict sources (stale on-disk lock vs. active in-process collision)
        surface as ``VersionControlError`` so the request boundary can return
        the shared version-control error envelope.
        """
        key = self._registry_operation_key(user_id)
        try:
            return run_operation(
                MARKETPLACE_GIT_OPERATION_MANAGER,
                key=key,
                kind=kind,
                operation_name=operation_name,
                repo_root=self._get_registry_root(user_id),
                callback=callback,
                stale_threshold_seconds=self._stale_threshold,
            )
        # GitStaleLockError subclasses GitOperationInProgressError, so this
        # branch must be matched first.
        except GitStaleLockError:
            raise VersionControlError(
                MARKETPLACE_GIT_OPERATION_IN_PROGRESS,
                blocking_scope=LockScope.COMMON_REPOSITORY,
                stale=True,
                can_force_unlock=True,
            )
        except GitOperationInProgressError:
            raise VersionControlError(
                MARKETPLACE_GIT_OPERATION_IN_PROGRESS,
                blocking_scope=LockScope.COMMON_REPOSITORY,
            )

    def _registry_clone_blocking_entries(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return [entry for entry in root.iterdir() if entry.name != ".marketplace"]

    def _remove_cloned_registry_entries(self, root: Path) -> None:
        for entry in self._registry_clone_blocking_entries(root):
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink(missing_ok=True)

    def _git_output(self, root: Path, args: list[str]) -> str:
        result = git_allow_failure(root, *args)
        return result.stdout.rstrip("\n") if result.returncode == 0 else ""

    def _run_process(self, command: list[str], *, cwd: Path) -> None:
        if command and command[0] == "git":
            try:
                run_git(cwd, *command[1:])
            except CoreGitCommandError as exc:
                # Let lock-signature GitCommandError propagate so
                # with_stale_lock_recovery (wrapping init/clone/remote) can
                # auto-clear and retry; non-lock errors stay soft-fail.
                if _is_lock_signature(exc):
                    raise
                raise MarketplaceImportSourceError(
                    "marketplace.git.operation_failed"
                ) from exc
            return
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.git.operation_failed"
            ) from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")

    def _process_output(self, command: list[str], *, cwd: Path) -> str:
        if command and command[0] == "git":
            try:
                return run_git(cwd, *command[1:]).stdout.strip()
            except CoreGitCommandError as exc:
                # Lock-signature errors must reach the recovery wrapper raw;
                # non-lock errors soft-fail as an import-source error.
                if _is_lock_signature(exc):
                    raise
                raise MarketplaceImportSourceError(
                    "marketplace.git.operation_failed"
                ) from exc
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.git.operation_failed"
            ) from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")
        return result.stdout.strip()

    def _git_file_change(
        self,
        path: str,
        status_code: str,
        *,
        old_path: str | None = None,
    ) -> FileChange:
        change_type_by_status = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
            "U": "unmerged",
            "?": "untracked",
        }
        return FileChange(
            name=path.rsplit("/", 1)[-1] if path else path,
            path=path,
            status=status_code,
            type=change_type_by_status.get(status_code[:1], "modified"),  # type: ignore[arg-type]
            oldPath=old_path,
        )

    def _validate_registry_remote(self, remote_url: str) -> None:
        """Reject embedded credentials at every Registry remote boundary."""

        if self._git_scp_like_pattern.match(remote_url):
            return
        try:
            parsed = urlparse(remote_url)
            username = parsed.username
            password = parsed.password
        except ValueError as exc:
            raise MarketplaceImportSourceError(
                "marketplace.install.remote_url_invalid"
            ) from exc
        if password is not None or (
            parsed.scheme.lower() in {"http", "https"} and username is not None
        ):
            raise MarketplaceImportSourceError(
                "marketplace.install.remote_url_credentials_forbidden"
            )

    def _sanitize_registry_git_diagnostic(self, user_id: str, message: str) -> str:
        cleaned = re.sub(
            r"(?i)\b(https?://)[^/@\s]+@",
            r"\1[REDACTED]@",
            message,
        )
        cleaned = re.sub(
            r"-----BEGIN [^-]+ PRIVATE KEY-----.*?" r"-----END [^-]+ PRIVATE KEY-----",
            "[REDACTED]",
            cleaned,
            flags=re.DOTALL,
        )
        return cleaned.strip()[:4096]

    def _registry_git_failure(
        self,
        user_id: str,
        message: str,
        *,
        code: str = "marketplace.git.operation_failed",
    ) -> MarketplaceImportSourceError:
        diagnostic = self._sanitize_registry_git_diagnostic(user_id, message)
        if diagnostic:
            _LOGGER.warning("Marketplace registry Git operation failed: %s", diagnostic)
        return MarketplaceImportSourceError(
            code,
            {"diagnostic": diagnostic} if diagnostic else {},
        )

    def _reject_raw_secret_material(self, source: MarketplaceImportSource) -> None:
        values = [source.source]
        if any(self._raw_private_key_pattern.search(value) for value in values):
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.raw_private_key_unsupported"
            )

    def _ensure_registry_gitignore(
        self,
        root: Path,
        *,
        invalidation_key: str,
    ) -> None:
        """Keep Manager-private Registry state outside every published commit."""

        path = root / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if any(line.strip() == ".marketplace/" for line in existing.splitlines()):
            return
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        self._write_text_with_core(
            path,
            f"{prefix}.marketplace/\n",
            invalidation_key=invalidation_key,
        )

    def _resolve_registry_git_path(self, root: Path, path: str) -> str:
        cleaned = path.strip().replace("\\", "/")
        if not cleaned or cleaned.startswith("/") or "\x00" in cleaned:
            raise MarketplacePathError("marketplace.package.path_escape")
        candidate = root / cleaned
        self._assert_relative_to(candidate, root)
        return str(Path(cleaned))

    def _require_registry_git_repo(self, root: Path) -> None:
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError(
                "marketplace.git.repository_not_initialized"
            )

    def _registry_commit_summary_from_core(
        self, commit: CoreCommitSummary
    ) -> MarketplaceGitCommitSummary:
        return MarketplaceGitCommitSummary(
            id=commit.sha,
            author=commit.author_name,
            email=commit.author_email,
            timestamp=commit.authored_at,
            message=commit.message,
            additions=commit.additions,
            deletions=commit.deletions,
            files_changed=commit.files_changed,
        )

    def _untracked_registry_file_diff(self, root: Path, path: str) -> str:
        file_path = root / path
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
