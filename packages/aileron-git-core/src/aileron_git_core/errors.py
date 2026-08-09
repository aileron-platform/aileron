from typing import Optional, Sequence

from .contracts import LockScope


class GitCoreError(Exception):
    """Base error for shared git primitives."""


class VersionControlError(GitCoreError):
    """Stable application error consumed by product adapters."""

    def __init__(
        self,
        error_code: str,
        *,
        diagnostic: str = "",
        blocking_scope: Optional[LockScope] = None,
        operation_status: object = None,
        stale: bool = False,
        can_force_unlock: bool = False,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.diagnostic = diagnostic
        self.blocking_scope = blocking_scope
        self.operation_status = operation_status
        self.stale = stale
        self.can_force_unlock = can_force_unlock


class GitCommandError(GitCoreError):
    """Raised when a git command exits unsuccessfully."""

    def __init__(
        self,
        args: Sequence[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        command = " ".join(args)
        super().__init__(f"Git command failed ({returncode}): {command}")
        self.args_list = list(args)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class GitOperationInProgressError(GitCoreError):
    """Raised when a blocking git operation is already active for a key."""

    def __init__(self, key: str, blocking_scope: LockScope | None = None) -> None:
        super().__init__(f"Git operation already in progress for key: {key}")
        self.key = key
        self.blocking_scope = blocking_scope


class GitStaleLockError(GitOperationInProgressError):
    """Raised when an on-disk stale lock could not be cleared after recovery."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
