"""Workspace Manager adapters for the shared version-control application."""

from __future__ import annotations

from aileron_git_core import RepositoryStatus, VersionControlError
from aileron_git_core.contracts import ActorContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.version_control.models import (
    VersionControlOperationStatus,
    VersionControlStatus,
)


class GitIdentityMissingError(ValueError):
    """Raised when a platform-managed commit has no user Git identity."""

    def __init__(self) -> None:
        super().__init__("git_identity_missing")


class ManagerActorContextResolver:
    """Build shared Git actor context from authoritative System Settings."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def resolve(self, *, user_id: str, display_name: str) -> ActorContext:
        settings = self._db.scalar(
            select(db_models.UserSetting).where(
                db_models.UserSetting.user_id == user_id
            )
        )
        git_name = (settings.git_user_name or "").strip() if settings else ""
        git_email = (settings.git_user_email or "").strip() if settings else ""
        if not git_name or not git_email:
            raise GitIdentityMissingError()
        return ActorContext(
            display_name=display_name.strip() or git_name,
            git_name=git_name,
            git_email=git_email,
        )


def version_control_status_from_core(status: RepositoryStatus) -> VersionControlStatus:
    """Map the core read model to the exact shared HTTP wire contract."""
    operation = status.operation_status
    operation_status = None
    if operation is not None:
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
        isInitialized=status.is_initialized,
        currentBranch=status.current_branch,
        detachedHead=status.detached_head,
        headSha=status.head_sha,
        hasOrigin=status.has_origin,
        upstream=status.upstream,
        ahead=status.ahead,
        behind=status.behind,
        hasConflicts=status.has_conflicts,
        stagedTotal=status.staged_total,
        unstagedTotal=status.unstaged_total,
        untrackedTotal=status.untracked_total,
        conflictTotal=status.conflict_total,
        operationStatus=operation_status,
    )


def version_control_error_envelope(exc: VersionControlError) -> dict:
    """Serialize the shared version-control error contract without diagnostics."""
    operation = exc.operation_status
    operation_status = None
    if operation is not None:
        operation_status = {
            "isActive": True,
            "operation": operation.operation_name,
            "actorDisplayName": operation.actor_display_name or None,
            "startedAt": operation.started_at.isoformat(),
            "blockingScope": (
                operation.blocking_scope.value
                if operation.blocking_scope is not None
                else None
            ),
            "stale": operation.stale,
            "retryable": operation.retryable,
            "progressCurrent": operation.progress_current,
            "progressTotal": operation.progress_total,
            "phase": operation.phase,
            "cancellable": operation.cancellable,
            "cancelRequested": operation.cancel_requested,
        }
    return {
        "errorCode": exc.error_code,
        "messageKey": exc.error_code,
        "blockingScope": (
            exc.blocking_scope.value if exc.blocking_scope is not None else None
        ),
        "operationStatus": operation_status,
        "stale": exc.stale,
        "canForceUnlock": exc.can_force_unlock,
    }
