from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.modules.workspace.firewall_contract import (
    FirewallReplacementRequest,
    FirewallResource,
    FirewallRuleConfig,
)
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.advisory_lock import acquire_workspace_transaction_lock
from app.modules.workspace.catalog import (
    WorkspaceNotFoundError,
)


class WorkspaceFirewallRevisionConflictError(RuntimeError):
    code = "FIREWALL_REVISION_CONFLICT"


class WorkspaceFirewallRetryNotAllowedError(RuntimeError):
    code = "FIREWALL_RETRY_NOT_ALLOWED"


class WorkspaceFirewallUnavailableError(RuntimeError):
    code = "CILIUM_NOT_ENABLED"


@dataclass(frozen=True)
class WorkspaceFirewallMutationResult:
    resource: FirewallResource
    changed: bool


class WorkspaceFirewallService:
    """Manage the database-owned Workspace firewall desired state."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.commands = WorkspaceFirewallSyncCommandRepository(db)
        self.authorization = AuthorizationOperationPolicy(db)

    def get(
        self,
        *,
        workspace_id: str,
        actor: AuthorizationActor,
    ) -> FirewallResource:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace not found")
        self.authorization.require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_FIREWALL_READ,
        )
        return self._to_resource(workspace)

    def replace(
        self,
        *,
        workspace_id: str,
        actor: AuthorizationActor,
        payload: FirewallReplacementRequest,
    ) -> WorkspaceFirewallMutationResult:
        try:
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise WorkspaceNotFoundError("Workspace not found")
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_FIREWALL_MANAGE,
            )
            if (
                workspace.provisioner == "kubernetes"
                and not self.settings.CILIUM_ENABLED
            ):
                raise WorkspaceFirewallUnavailableError()
            if payload.revision != workspace.firewall_revision:
                raise WorkspaceFirewallRevisionConflictError()

            changed = self._is_changed(workspace, payload)
            if not changed:
                resource = self._to_resource(workspace)
                self.db.rollback()
                return WorkspaceFirewallMutationResult(
                    resource=resource,
                    changed=False,
                )

            workspace.workspace_firewall_egress_mode = payload.workspace.egress_mode
            workspace.workspace_firewall_allowed_domains = list(
                payload.workspace.allowed_domains
            )
            workspace.browser_firewall_egress_mode = payload.browser.egress_mode
            workspace.browser_firewall_allowed_domains = list(
                payload.browser.allowed_domains
            )
            workspace.firewall_revision += 1
            workspace.firewall_sync_status = "applying"
            workspace.firewall_error_code = None
            self.commands.enqueue(
                workspace=workspace,
                scheduled_at=datetime.now(timezone.utc),
            )
            self.db.commit()
            self.db.refresh(workspace)
            return WorkspaceFirewallMutationResult(
                resource=self._to_resource(workspace),
                changed=True,
            )
        except Exception:
            self.db.rollback()
            raise

    def retry(
        self,
        *,
        workspace_id: str,
        actor: AuthorizationActor,
    ) -> FirewallResource:
        try:
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                raise WorkspaceNotFoundError("Workspace not found")
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_FIREWALL_MANAGE,
            )
            if (
                workspace.provisioner == "kubernetes"
                and not self.settings.CILIUM_ENABLED
            ):
                raise WorkspaceFirewallUnavailableError()
            if workspace.firewall_sync_status != "error":
                raise WorkspaceFirewallRetryNotAllowedError()
            retry_command = self.commands.enqueue_retry(
                workspace=workspace,
                scheduled_at=datetime.now(timezone.utc),
            )
            if retry_command is None:
                raise WorkspaceFirewallRetryNotAllowedError()

            workspace.firewall_sync_status = "applying"
            workspace.firewall_error_code = None
            self.db.commit()
            self.db.refresh(workspace)
            return self._to_resource(workspace)
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _is_changed(
        workspace: db_models.Workspace,
        payload: FirewallReplacementRequest,
    ) -> bool:
        return any(
            (
                workspace.workspace_firewall_egress_mode
                != payload.workspace.egress_mode,
                (workspace.workspace_firewall_allowed_domains or [])
                != payload.workspace.allowed_domains,
                workspace.browser_firewall_egress_mode != payload.browser.egress_mode,
                (workspace.browser_firewall_allowed_domains or [])
                != payload.browser.allowed_domains,
            )
        )

    def _to_resource(self, workspace: db_models.Workspace) -> FirewallResource:
        unavailable = (
            workspace.provisioner == "kubernetes" and not self.settings.CILIUM_ENABLED
        )
        return FirewallResource(
            revision=workspace.firewall_revision,
            observedRevision=workspace.firewall_observed_revision,
            syncStatus=(
                "unavailable" if unavailable else workspace.firewall_sync_status
            ),
            errorCode=(
                WorkspaceFirewallUnavailableError.code
                if unavailable
                else workspace.firewall_error_code
            ),
            workspace=FirewallRuleConfig(
                egressMode=workspace.workspace_firewall_egress_mode,
                allowedDomains=workspace.workspace_firewall_allowed_domains or [],
            ),
            browser=FirewallRuleConfig(
                egressMode=workspace.browser_firewall_egress_mode,
                allowedDomains=workspace.browser_firewall_allowed_domains or [],
            ),
        )


__all__ = [
    "WorkspaceAccessDeniedError",
    "WorkspaceFirewallMutationResult",
    "WorkspaceFirewallRetryNotAllowedError",
    "WorkspaceFirewallRevisionConflictError",
    "WorkspaceFirewallService",
    "WorkspaceFirewallUnavailableError",
]
