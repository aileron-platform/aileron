"""Authorize Browser access and persist credential rotation requests."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.workspace.browser_credential_models import (
    BrowserAccessResponse,
    BrowserCredentialRotationResponse,
)
from app.modules.workspace.browser_credentials import (
    BROWSER_CREDENTIAL_ALGORITHM,
    BrowserCredentialService,
)
from app.modules.workspace.browser_turn_credentials import (
    BrowserTurnCredentialIssuer,
)
from app.modules.workspace.public_urls import WorkspacePublicUrls
from app.modules.workspace.runtime.job_repository import (
    WorkspaceRuntimeJobRepository,
)


class WorkspaceBrowserCredentialError(RuntimeError):
    def __init__(self, code: str, http_status: int) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


class WorkspaceBrowserCredentialService:
    """Return user-only credentials and rotate the desired Browser revision."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.operations = AuthorizationOperationPolicy(db)
        self.audit = AuditEventService(db)
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.turn_credential_issuer = BrowserTurnCredentialIssuer.from_settings(
            get_settings()
        )

    def access(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> BrowserAccessResponse:
        actor, workspace = self._authorize(
            actor=actor,
            workspace_id=workspace_id,
            operation=OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
            for_update=True,
        )
        if workspace.browser_status != "running":
            raise WorkspaceBrowserCredentialError("BROWSER_NOT_READY", 409)
        if workspace.browser_connectivity_admission != "allowed":
            if workspace.browser_connectivity_state == "unavailable":
                raise WorkspaceBrowserCredentialError(
                    "BROWSER_CONNECTIVITY_UNAVAILABLE",
                    503,
                )
            raise WorkspaceBrowserCredentialError(
                "BROWSER_CONNECTIVITY_NOT_READY",
                409,
            )
        if (
            workspace.browser_credential_revision
            != workspace.browser_credential_observed_revision
            or workspace.browser_credential_key_id
            != workspace.browser_credential_observed_key_id
            or workspace.browser_credential_algorithm
            != workspace.browser_credential_observed_algorithm
        ):
            raise WorkspaceBrowserCredentialError("BROWSER_CREDENTIAL_ROTATING", 409)
        pair = BrowserCredentialService.from_settings().derive(
            workspace_id=workspace.id,
            revision=workspace.browser_credential_revision,
            key_id=workspace.browser_credential_key_id,
            algorithm=workspace.browser_credential_algorithm,
        )
        self._audit(
            actor_id=actor.user_id,
            workspace=workspace,
            action="access_browser",
            event_type="workspace.browser_accessed",
            correlation_id=correlation_id,
        )
        self.db.commit()
        return BrowserAccessResponse(
            browserUrl=WorkspacePublicUrls.for_workspace(workspace.id).browser,
            password=pair.user_password,
            credentialRevision=pair.revision,
            iceServers=(
                self.turn_credential_issuer.issue(workspace_id=str(workspace.id))
                if self.turn_credential_issuer is not None
                else []
            ),
        )

    def rotate(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> BrowserCredentialRotationResponse:
        actor, workspace = self._authorize(
            actor=actor,
            workspace_id=workspace_id,
            operation=OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
            for_update=True,
        )
        keyring = BrowserCredentialService.from_settings()
        workspace.browser_credential_revision += 1
        workspace.browser_credential_key_id = keyring.active_key_id
        workspace.browser_credential_algorithm = BROWSER_CREDENTIAL_ALGORITHM
        workspace.browser_desired_revision += 1
        result = self.jobs.enqueue_browser_credential_rotation(
            workspace=workspace,
            correlation_id=correlation_id,
            scheduled_at=datetime.now(timezone.utc),
        )
        applied_on_next_start = workspace.browser_status != "running"
        self._audit(
            actor_id=actor.user_id,
            workspace=workspace,
            action="rotate_browser_credential",
            event_type="workspace.browser_credential_rotation_requested",
            correlation_id=correlation_id,
        )
        self.db.commit()
        return BrowserCredentialRotationResponse(
            jobId=result.job.id,
            status=result.job.status,
            credentialRevision=workspace.browser_credential_revision,
            appliedOnNextStart=applied_on_next_start,
        )

    def _authorize(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
        for_update: bool,
    ) -> tuple[AuthorizationActor, db_models.Workspace]:
        try:
            self.operations.require_workspace_operation(
                actor,
                workspace_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            raise WorkspaceBrowserCredentialError(
                exc.error_code,
                exc.http_status,
            ) from exc
        statement = select(db_models.Workspace).where(
            db_models.Workspace.id == workspace_id
        )
        if for_update:
            statement = statement.with_for_update()
        workspace = self.db.scalar(statement)
        if workspace is None:
            raise WorkspaceBrowserCredentialError(
                "WORKSPACE_ACCESS_DENIED",
                404,
            )
        return actor, workspace

    def _audit(
        self,
        *,
        actor_id: str,
        workspace: db_models.Workspace,
        action: str,
        event_type: str,
        correlation_id: str,
    ) -> None:
        self.audit.record(
            event_type=event_type,
            actor_type="user",
            actor_id=actor_id,
            actor_user_id=actor_id,
            target_type="workspace",
            target_id=workspace.id,
            action=action,
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "browser_credential_revision": (workspace.browser_credential_revision),
            },
        )


__all__ = [
    "WorkspaceBrowserCredentialError",
    "WorkspaceBrowserCredentialService",
]
