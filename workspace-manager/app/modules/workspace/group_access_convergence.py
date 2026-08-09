"""Converge Workspace authorization after user-group access reductions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    role_satisfies,
)
from app.modules.automation.execution import AutomationExecutionService
from app.modules.automation.repository import AutomationRepository, RunningCancellation
from app.modules.identity.platform_role import PlatformRole, normalize_platform_role
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy
from app.modules.workspace.advisory_lock import acquire_workspace_transaction_lock
from app.modules.workspace.access_repository import WorkspaceAccessResolver
from app.modules.workspace.runtime.job_repository import WorkspaceRuntimeJobRepository


@dataclass(frozen=True)
class _WorkspacePrincipalAccessBeforeImage:
    """Effective access captured while the affected Workspace rows are locked."""

    workspace_id: str
    principal_user_id: str
    access_role: ResourceAccessRole


@dataclass(frozen=True)
class _GroupWorkspaceAccessChange:
    """Locked Workspace scope and before-images for one group mutation."""

    group_id: str
    workspaces: tuple[db_models.Workspace, ...]
    group_shares: tuple[db_models.WorkspaceShare, ...]
    before_images: tuple[_WorkspacePrincipalAccessBeforeImage, ...]


@dataclass(frozen=True)
class _PostCommitAuthorizationDelivery:
    """Committed cancellation intents awaiting Runtime delivery."""

    automation: AutomationExecutionService
    cancellations: tuple[RunningCancellation, ...]

    def deliver(self) -> None:
        self.automation.cancel_running_after_commit(list(self.cancellations))


class GroupWorkspaceAuthorizationConvergence:
    """Own transactional convergence caused by group membership or deletion."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_events = AuditEventService(db)
        self.runtime_jobs = WorkspaceRuntimeJobRepository(db)
        self.automation = AutomationExecutionService(AutomationRepository(db))
        self.authorization_policy = UserAuthorizationPolicy()
        self.access_resolver = WorkspaceAccessResolver(db)

    def apply_reduction_in_transaction(
        self,
        *,
        group_id: str,
        principal_user_ids: list[str],
        mutation: Callable[[_GroupWorkspaceAccessChange], None],
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
        reason: str,
    ) -> _PostCommitAuthorizationDelivery:
        """Apply one access-reducing group mutation in the caller transaction."""

        change = self._capture_before_change(
            group_id=group_id,
            principal_user_ids=principal_user_ids,
        )
        mutation(change)
        self.db.flush()
        cancellations = self._converge_reductions(
            change,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            reason=reason,
        )
        return _PostCommitAuthorizationDelivery(
            automation=self.automation,
            cancellations=tuple(cancellations),
        )

    def _capture_before_change(
        self,
        *,
        group_id: str,
        principal_user_ids: list[str],
    ) -> _GroupWorkspaceAccessChange:
        """Lock affected Workspaces and capture effective access before mutation."""

        principal_ids = tuple(sorted(set(principal_user_ids)))
        principals = (
            tuple(
                self.db.scalars(
                    select(db_models.User)
                    .where(db_models.User.id.in_(principal_ids))
                    .order_by(db_models.User.id)
                    .with_for_update()
                ).all()
            )
            if principal_ids
            else ()
        )
        platform_admin_ids = {
            principal.id
            for principal in principals
            if normalize_platform_role(principal.platform_role) is PlatformRole.ADMIN
            and self.authorization_policy.is_authorized(principal)
        }
        workspace_ids = tuple(
            self.db.scalars(
                select(db_models.WorkspaceShare.workspace_id)
                .where(
                    db_models.WorkspaceShare.target_type == "user_group",
                    db_models.WorkspaceShare.target_id == group_id,
                )
                .distinct()
                .order_by(db_models.WorkspaceShare.workspace_id)
            ).all()
        )
        for workspace_id in workspace_ids:
            acquire_workspace_transaction_lock(self.db, workspace_id)

        workspaces = (
            tuple(
                self.db.scalars(
                    select(db_models.Workspace)
                    .where(db_models.Workspace.id.in_(workspace_ids))
                    .order_by(db_models.Workspace.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).all()
            )
            if workspace_ids
            else ()
        )
        group_shares = (
            tuple(
                self.db.scalars(
                    select(db_models.WorkspaceShare)
                    .where(
                        db_models.WorkspaceShare.workspace_id.in_(workspace_ids),
                        db_models.WorkspaceShare.target_type == "user_group",
                        db_models.WorkspaceShare.target_id == group_id,
                    )
                    .order_by(
                        db_models.WorkspaceShare.workspace_id,
                        db_models.WorkspaceShare.id,
                    )
                    .with_for_update()
                ).all()
            )
            if workspace_ids
            else ()
        )
        before_images = tuple(
            _WorkspacePrincipalAccessBeforeImage(
                workspace_id=workspace.id,
                principal_user_id=principal_user_id,
                access_role=access_role,
            )
            for workspace in workspaces
            for principal_user_id in principal_ids
            if principal_user_id not in platform_admin_ids
            if (
                access_role := self._resolve_effective_role(
                    workspace=workspace,
                    principal_user_id=principal_user_id,
                )
            )
            is not None
        )
        return _GroupWorkspaceAccessChange(
            group_id=group_id,
            workspaces=workspaces,
            group_shares=group_shares,
            before_images=before_images,
        )

    def _converge_reductions(
        self,
        change: _GroupWorkspaceAccessChange,
        *,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
        reason: str,
    ) -> list[RunningCancellation]:
        """Persist runtime and automation convergence for actual role reductions."""

        workspace_by_id = {workspace.id: workspace for workspace in change.workspaces}
        reduced_principals: dict[str, list[str]] = defaultdict(list)
        cancellations: list[RunningCancellation] = []
        for before in change.before_images:
            workspace = workspace_by_id[before.workspace_id]
            after_role = self._resolve_effective_role(
                workspace=workspace,
                principal_user_id=before.principal_user_id,
            )
            if after_role is not None and role_satisfies(
                after_role, before.access_role
            ):
                continue
            reduced_principals[workspace.id].append(before.principal_user_id)
            cancellations.extend(
                self.automation.converge_principal_authorization_in_transaction(
                    principal_user_id=before.principal_user_id,
                    workspace_id=workspace.id,
                )
            )

        scheduled_at = datetime.now(timezone.utc)
        for workspace_id in sorted(reduced_principals):
            workspace = workspace_by_id[workspace_id]
            workspace.runtime_access_revision += 1
            self.runtime_jobs.supersede_queued_and_enqueue_access_recycle(
                workspace=workspace,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                scheduled_at=scheduled_at,
                job_metadata={"reason": reason},
            )
            self.audit_events.record(
                event_type="runtime.access_recycle_requested",
                actor_type="user",
                actor_id=actor_user_id,
                actor_user_id=actor_user_id,
                target_type="workspace",
                target_id=workspace.id,
                action="request_access_recycle",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "runtime_access_revision": workspace.runtime_access_revision,
                    "reason": reason,
                },
            )
        return cancellations

    def _resolve_effective_role(
        self,
        *,
        workspace: db_models.Workspace,
        principal_user_id: str,
    ) -> ResourceAccessRole | None:
        access = self.access_resolver.resolve(
            workspace=workspace,
            user_id=principal_user_id,
        )
        return access.access_role if access is not None else None


__all__ = ["GroupWorkspaceAuthorizationConvergence"]
