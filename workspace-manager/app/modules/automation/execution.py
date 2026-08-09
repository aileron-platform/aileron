"""Automation execution admission service."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import SecretStr

from app.core.error_sanitization import sanitize_error_message
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.models import (
    AutomationExecution,
    AutomationExecutionListResponse,
    AutomationExecutionPageResponse,
    ClaimResponse,
    CompletionRequest,
)
from app.modules.automation.notifications import AutomationNotificationService
from app.modules.automation.repository import (
    AutomationRepository,
    AutomationWorkspaceDeletionError,
    RunningCancellation,
    WorkspaceDeletionConvergencePlan,
)
from app.modules.automation.runtime_client import RuntimeAutomationClient
from app.modules.workspace.runtime.job_repository import (
    WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS,
)

logger = logging.getLogger(__name__)

WORKSPACE_DELETION_PHASE_CANCELLING_AUTOMATIONS = (
    WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS
)
WORKSPACE_DELETION_TERMINAL_STATUSES = frozenset({"success", "failed", "cancelled"})
WORKSPACE_DELETION_CONFIRMATION_TIMEOUT_SECONDS = 10.0
WORKSPACE_DELETION_CONFIRMATION_POLL_INTERVAL_SECONDS = 0.1


@dataclass(frozen=True)
class WorkspaceDeletionConvergenceResult:
    """Observed Automation convergence required before Workspace deletion."""

    workspace_id: str
    phase: str
    queued_execution_ids: tuple[str, ...]
    running_execution_ids: tuple[str, ...]
    confirmed_execution_ids: tuple[str, ...]


class AutomationExecutionService:
    """Expose immutable execution admission and authorized history reads."""

    def __init__(
        self,
        repository: AutomationRepository,
        *,
        notifications: AutomationNotificationService | None = None,
        runtime_client: RuntimeAutomationClient | None = None,
    ) -> None:
        self.repository = repository
        self.notifications = notifications or AutomationNotificationService()
        self.runtime_client = runtime_client or RuntimeAutomationClient()

    def enqueue_manual(
        self,
        *,
        job_id: str,
        actor: AuthorizationActor,
    ) -> AutomationExecution:
        return self._to_wire(self.repository.enqueue_manual(job_id=job_id, actor=actor))

    def enqueue_webhook(
        self, *, job_id: str, presented_key: SecretStr
    ) -> AutomationExecution:
        return self._to_wire(
            self.repository.enqueue_webhook(job_id=job_id, presented_key=presented_key)
        )

    def get(
        self,
        *,
        execution_id: str,
        actor: AuthorizationActor,
    ) -> AutomationExecution:
        return self._to_wire(
            self.repository.get_execution_for_actor(
                execution_id=execution_id, actor=actor
            )
        )

    def list_for_job(
        self,
        *,
        job_id: str,
        actor: AuthorizationActor,
        page: int,
        page_size: int,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> AutomationExecutionPageResponse:
        records, total = self.repository.list_job_executions(
            job_id=job_id,
            actor=actor,
            page=page,
            page_size=page_size,
            range_start=range_start,
            range_end=range_end,
        )
        items = [self._to_wire(item) for item in records]
        return AutomationExecutionPageResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )

    def list(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str | None,
        limit: int,
    ) -> AutomationExecutionListResponse:
        items = [
            self._to_wire(item)
            for item in self.repository.list_executions_for_actor(
                actor=actor,
                workspace_id=workspace_id,
                limit=limit,
            )
        ]
        return AutomationExecutionListResponse(items=items, total=len(items))

    def claim(
        self,
        *,
        workspace_id: str,
        runner_instance_id: UUID,
        claim_request_id: UUID,
    ) -> ClaimResponse | None:
        execution = self.repository.claim_execution(
            workspace_id=workspace_id,
            runner_instance_id=runner_instance_id,
            claim_request_id=claim_request_id,
        )
        self.cancel_running_after_commit(
            self.repository.take_committed_running_cancellations()
        )
        if execution is None:
            return None
        return ClaimResponse(
            executionId=execution.id,
            jobId=execution.job_id,
            workspaceId=execution.workspace_id,
            trigger=execution.trigger,
            scheduledFor=execution.scheduled_for,
            principalUserId=execution.principal_user_id_snapshot,
            prompt=execution.prompt_snapshot,
            agenticTool=execution.agentic_tool_snapshot,
            model=execution.model_snapshot,
            agentConfig=execution.agent_config_snapshot,
            worktreeKey=execution.worktree_key_snapshot,
            runnerInstanceId=execution.runner_instance_id,
            claimRequestId=execution.claim_request_id,
            cancelRequestedAt=execution.cancel_requested_at,
        )

    def complete(
        self, *, execution_id: str, payload: CompletionRequest
    ) -> AutomationExecution:
        execution = self.repository.complete_execution(
            execution_id=execution_id,
            runner_instance_id=payload.runner_instance_id,
            claim_request_id=payload.claim_request_id,
            status=payload.status,
            error_code=payload.error_code,
            error_message=sanitize_error_message(payload.error_message),
        )
        if getattr(execution, "_terminal_transition_won", False):
            self._notify_after_commit(execution)
        return self._to_wire(execution)

    def cancel(
        self,
        *,
        execution_id: str,
        actor: AuthorizationActor,
    ) -> AutomationExecution:
        execution = self.repository.cancel_execution(
            execution_id=execution_id, actor=actor
        )
        if execution.status == "running" and execution.cancel_requested_at is not None:
            workspace = self.repository.db.get(
                db_models.Workspace, execution.workspace_id
            )
            runtime_url = (
                workspace.runtime_internal_url if workspace is not None else None
            )
            if (
                runtime_url
                and workspace is not None
                and workspace.runtime_instance_id
                and execution.runner_instance_id
                and execution.claim_request_id
            ):
                self.runtime_client.cancel_execution(
                    runtime_url=runtime_url,
                    workspace_id=execution.workspace_id,
                    runtime_instance_id=workspace.runtime_instance_id,
                    execution_id=execution.id,
                    runner_instance_id=execution.runner_instance_id,
                    claim_request_id=execution.claim_request_id,
                )
        return self._to_wire(execution)

    def reconcile_restart(
        self, *, workspace_id: str, new_runner_instance_id: UUID
    ) -> list[AutomationExecution]:
        executions = self.repository.reconcile_restart(
            workspace_id=workspace_id,
            new_runner_instance_id=new_runner_instance_id,
        )
        for execution in executions:
            self._notify_after_commit(execution)
        return [self._to_wire(execution) for execution in executions]

    def converge_principal_authorization(
        self, *, principal_user_id: str, workspace_id: str | None = None
    ) -> list[RunningCancellation]:
        """Commit principal convergence without waiting for Runtime networking."""
        return self.repository.converge_principal_authorization(
            principal_user_id=principal_user_id,
            workspace_id=workspace_id,
        )

    def converge_principal_authorization_in_transaction(
        self,
        *,
        principal_user_id: str,
        workspace_id: str | None = None,
    ) -> list[RunningCancellation]:
        """Converge DB state without committing the caller-owned transaction."""

        return self.repository.converge_principal_authorization_in_transaction(
            principal_user_id=principal_user_id,
            workspace_id=workspace_id,
        )

    def converge_workspace_deletion(
        self,
        *,
        workspace_id: str,
        timeout_seconds: float = WORKSPACE_DELETION_CONFIRMATION_TIMEOUT_SECONDS,
        poll_interval_seconds: float = (
            WORKSPACE_DELETION_CONFIRMATION_POLL_INTERVAL_SECONDS
        ),
    ) -> WorkspaceDeletionConvergenceResult:
        """Cancel Workspace executions and confirm Runtime terminal convergence."""
        if timeout_seconds < 0 or poll_interval_seconds < 0:
            raise ValueError(
                "Workspace deletion confirmation timing must be non-negative"
            )

        plan = self.repository.converge_workspace_deletion(workspace_id=workspace_id)
        confirmed_execution_ids: list[str] = list(plan.queued_execution_ids)
        requested_running_ids: list[str] = []

        for cancellation in plan.running_cancellations:
            status = self.repository.execution_statuses(
                execution_ids=(cancellation.execution_id,)
            ).get(cancellation.execution_id)
            if status in WORKSPACE_DELETION_TERMINAL_STATUSES:
                confirmed_execution_ids.append(cancellation.execution_id)
                continue
            try:
                delivered = self._deliver_runtime_cancellation(cancellation)
            except Exception as exc:
                raise AutomationWorkspaceDeletionError(
                    phase=WORKSPACE_DELETION_PHASE_CANCELLING_AUTOMATIONS,
                    execution_id=cancellation.execution_id,
                ) from exc
            if not delivered:
                status = self.repository.execution_statuses(
                    execution_ids=(cancellation.execution_id,)
                ).get(cancellation.execution_id)
                if status in WORKSPACE_DELETION_TERMINAL_STATUSES:
                    confirmed_execution_ids.append(cancellation.execution_id)
                    continue
                raise AutomationWorkspaceDeletionError(
                    phase=WORKSPACE_DELETION_PHASE_CANCELLING_AUTOMATIONS,
                    execution_id=cancellation.execution_id,
                )
            requested_running_ids.append(cancellation.execution_id)

        if requested_running_ids:
            confirmed_execution_ids.extend(
                self._wait_for_terminal_workspace_executions(
                    execution_ids=tuple(requested_running_ids),
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                )
            )

        return WorkspaceDeletionConvergenceResult(
            workspace_id=workspace_id,
            phase=WORKSPACE_DELETION_PHASE_CANCELLING_AUTOMATIONS,
            queued_execution_ids=plan.queued_execution_ids,
            running_execution_ids=plan.running_execution_ids,
            confirmed_execution_ids=tuple(confirmed_execution_ids),
        )

    def converge_workspace_deletion_in_transaction(
        self,
        *,
        workspace_id: str,
    ) -> WorkspaceDeletionConvergencePlan:
        """Stage deletion cancellation intents in a caller-owned transaction."""
        return self.repository.converge_workspace_deletion_in_transaction(
            workspace_id=workspace_id
        )

    def _deliver_runtime_cancellation(self, cancellation: RunningCancellation) -> bool:
        workspace = self.repository.db.get(
            db_models.Workspace, cancellation.workspace_id
        )
        runtime_instance_id = (
            workspace.runtime_instance_id if workspace is not None else None
        )
        if (
            not cancellation.runtime_url
            or not isinstance(runtime_instance_id, str)
            or not runtime_instance_id
            or not cancellation.runner_instance_id
            or not cancellation.claim_request_id
        ):
            return False
        return self.runtime_client.cancel_execution(
            runtime_url=cancellation.runtime_url,
            workspace_id=cancellation.workspace_id,
            runtime_instance_id=runtime_instance_id,
            execution_id=cancellation.execution_id,
            runner_instance_id=cancellation.runner_instance_id,
            claim_request_id=cancellation.claim_request_id,
        )

    def _wait_for_terminal_workspace_executions(
        self,
        *,
        execution_ids: tuple[str, ...],
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> tuple[str, ...]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            statuses = self.repository.execution_statuses(execution_ids=execution_ids)
            pending = tuple(
                execution_id
                for execution_id in execution_ids
                if statuses.get(execution_id)
                not in WORKSPACE_DELETION_TERMINAL_STATUSES
            )
            if not pending:
                return execution_ids
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AutomationWorkspaceDeletionError(
                    phase=WORKSPACE_DELETION_PHASE_CANCELLING_AUTOMATIONS,
                    execution_id=pending[0],
                )
            time.sleep(min(poll_interval_seconds, remaining))

    def cancel_running_after_commit(
        self, cancellations: list[RunningCancellation]
    ) -> None:
        """Best-effort Runtime delivery for already committed cancel intents."""
        for cancellation in cancellations:
            try:
                delivered = self._deliver_runtime_cancellation(cancellation)
            except Exception as exc:
                logger.warning(
                    "Runtime automation authorization cancellation failed for execution %s: %s",
                    cancellation.execution_id,
                    type(exc).__name__,
                )
                continue
            if not delivered:
                logger.warning(
                    "Runtime automation authorization cancellation failed for execution %s",
                    cancellation.execution_id,
                )

    def _notify_after_commit(self, execution: db_models.AutomationExecution) -> None:
        try:
            config = execution.job.notification_config if execution.job else {}
            result = self.notifications.deliver_terminal(
                execution=execution, notification_config=config or {}
            )
            if result is not None:
                self.repository.update_notification_status(
                    execution_id=execution.id, notification_status=result
                )
                execution.notification_status = result
        except Exception as exc:
            try:
                self.repository.db.rollback()
            except Exception:
                pass
            logger.warning(
                "Automation notification handling failed for execution %s: %s",
                execution.id,
                type(exc).__name__,
            )

    def _to_wire(self, execution: db_models.AutomationExecution) -> AutomationExecution:
        values = {
            column.name: getattr(execution, column.name)
            for column in db_models.AutomationExecution.__table__.columns
        }
        values["queue_position"] = self.repository.queue_position(execution.id)
        return AutomationExecution.model_validate(values)


__all__ = [
    "AutomationExecutionService",
    "RunningCancellation",
    "WorkspaceDeletionConvergenceResult",
]
