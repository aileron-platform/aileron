"""Authorized automation Job control-plane service."""

from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.authorization import AutomationAuthorizationService
from app.modules.automation.models import (
    AutomationAgentConfigSnapshot,
    AutomationJob,
    AutomationJobListResponse,
    AutomationNotificationConfig,
    JobCreateRequest,
    JobUpdateRequest,
)
from app.modules.automation.repository import AutomationRepository, JobProjection
from app.modules.automation.runtime_client import RuntimeAutomationClient
from app.modules.automation.schedules import (
    AutomationScheduleError,
    AutomationScheduleService,
)
from app.modules.workspace.catalog import WorkspaceService


class AutomationServiceError(RuntimeError):
    """Stable service-layer failure."""

    status_code = 400

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AutomationConflictError(AutomationServiceError):
    status_code = 409


class AutomationNotFoundError(AutomationServiceError):
    status_code = 404


class AutomationValidationError(AutomationServiceError):
    status_code = 422


class AutomationJobService:
    """Coordinate authorization, schedule policy, and repository transactions."""

    def __init__(
        self,
        repository: AutomationRepository,
        *,
        authorization: AutomationAuthorizationService | None = None,
        workspaces: WorkspaceService | None = None,
        schedule_service: AutomationScheduleService | None = None,
        id_provider: Callable[[], str] | None = None,
        worktree_preflight: Callable[[str], None] | None = None,
    ) -> None:
        self.repository = repository
        db = repository.db
        self.authorization = authorization or AutomationAuthorizationService(db)
        self.workspaces = workspaces or WorkspaceService(db)
        self.schedule_service = schedule_service or AutomationScheduleService()
        self._id_provider = id_provider or (lambda: str(uuid4()))
        self._worktree_preflight = worktree_preflight or self._require_worktree_ready

    def create(
        self, *, actor: AuthorizationActor, payload: JobCreateRequest
    ) -> AutomationJob:
        self.authorization.require_execute(
            actor=actor, workspace_id=payload.workspace_id
        )
        self._require_workspace_mutable(payload.workspace_id)
        try:
            self._worktree_preflight(payload.workspace_id)
            now = self.repository.transaction_now()
            agentic_tool, model, agent_config = self._resolve_agent_config(
                workspace_id=payload.workspace_id,
                actor_user_id=actor.user_id,
                tool=payload.agentic_tool,
                model=payload.model,
                mode=payload.agent_config.mode if payload.agent_config else None,
            )
            next_run_at = self.schedule_service.validate_and_next_run(
                trigger=payload.trigger.value,
                schedule=payload.schedule,
                exact=payload.exact,
                reference=now,
            )
            job_id = self._id_provider()
            identity = f"automation/{job_id}"
            notification = AutomationNotificationConfig(
                webhook_api_key=payload.webhook_api_key,
                delivery_webhook_url=payload.delivery_webhook_url,
                failure_destination=payload.failure_destination,
            )
            self.repository.create_job(
                {
                    "id": job_id,
                    "workspace_id": payload.workspace_id,
                    "creator_user_id": actor.user_id,
                    "name": payload.name,
                    "description": payload.description,
                    "prompt": payload.prompt,
                    "status": "active",
                    "trigger": payload.trigger.value,
                    "schedule": payload.schedule,
                    "exact": payload.exact,
                    "agentic_tool": agentic_tool,
                    "model": model,
                    "agent_config": agent_config.model_dump(
                        mode="json", by_alias=False
                    ),
                    "worktree_key": identity,
                    "worktree_branch": identity,
                    "notification_config": self._notification_dump(notification),
                    "next_run_at": next_run_at,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            self.repository.commit()
            projection = self.repository.get_job(job_id)
            if projection is None:
                raise AutomationNotFoundError("automation_job_not_found")
            return self._to_wire(projection)
        except AutomationScheduleError as exc:
            self.repository.rollback()
            self._raise_schedule(exc)
        except (AutomationServiceError, HTTPException):
            self.repository.rollback()
            raise

    def _require_worktree_ready(self, workspace_id: str) -> None:
        workspace = self.repository.db.get(db_models.Workspace, workspace_id)
        if (
            workspace is None
            or workspace.runtime_status != "running"
            or not workspace.runtime_internal_url
            or not workspace.runtime_instance_id
        ):
            raise AutomationConflictError("automation_runtime_unavailable")
        error_code = RuntimeAutomationClient().preflight_worktree(
            runtime_url=workspace.runtime_internal_url,
            workspace_id=workspace_id,
            runtime_instance_id=workspace.runtime_instance_id,
        )
        if error_code is not None:
            raise AutomationConflictError(error_code)

    def _require_workspace_mutable(self, workspace_id: str) -> None:
        workspace = self.repository.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise AutomationNotFoundError("workspace_not_found")
        if workspace.runtime_status == "deleting":
            raise AutomationConflictError("WORKSPACE_DELETING")

    def get(self, *, actor: AuthorizationActor, job_id: str) -> AutomationJob:
        projection = self._require_projection(job_id)
        self.authorization.require_read(
            actor=actor, workspace_id=projection.job.workspace_id
        )
        return self._to_wire(projection)

    def list(
        self, *, actor: AuthorizationActor, workspace_id: str | None = None
    ) -> AutomationJobListResponse:
        workspace_ids = self._scope(actor=actor, workspace_id=workspace_id)
        items = [
            self._to_wire(item) for item in self.repository.list_jobs(workspace_ids)
        ]
        return AutomationJobListResponse(items=items, total=len(items))

    def update(
        self,
        *,
        actor: AuthorizationActor,
        job_id: str,
        payload: JobUpdateRequest,
    ) -> AutomationJob:
        try:
            job = self._require_locked(job_id)
            self.authorization.require_execute(
                actor=actor, workspace_id=job.workspace_id
            )
            self.authorization.require_creator_execute(
                user_id=job.creator_user_id, workspace_id=job.workspace_id
            )
            self._require_workspace_mutable(job.workspace_id)
            now = self.repository.transaction_now()
            values = self._candidate_values(
                job,
                payload,
                actor_user_id=actor.user_id,
            )
            schedule_changed = bool(
                {"trigger", "schedule", "exact"} & payload.model_fields_set
            )
            status_changed = "status" in payload.model_fields_set
            candidate_status = values.get("status", job.status)
            candidate_trigger = values.get("trigger", job.trigger)
            candidate_schedule = values.get("schedule", job.schedule)
            candidate_exact = values.get("exact", job.exact)
            if candidate_status == "paused":
                if schedule_changed:
                    self.schedule_service.validate(
                        trigger=candidate_trigger,
                        schedule=candidate_schedule,
                    )
                values["next_run_at"] = None
            elif schedule_changed or (status_changed and job.status == "paused"):
                values["next_run_at"] = self.schedule_service.next_strictly_after(
                    trigger=candidate_trigger,
                    schedule=candidate_schedule,
                    exact=candidate_exact,
                    reference=now,
                )
            values["updated_at"] = now
            self.repository.update_job(job, values)
            self.repository.commit()
            projection = self.repository.get_job(job_id)
            if projection is None:
                raise AutomationNotFoundError("automation_job_not_found")
            return self._to_wire(projection)
        except AutomationScheduleError as exc:
            self.repository.rollback()
            self._raise_schedule(exc)
        except (AutomationServiceError, HTTPException):
            self.repository.rollback()
            raise

    def pause(self, *, actor: AuthorizationActor, job_id: str) -> AutomationJob:
        try:
            job = self._require_locked(job_id)
            self.authorization.require_execute(
                actor=actor, workspace_id=job.workspace_id
            )
            self._require_workspace_mutable(job.workspace_id)
            now = self.repository.transaction_now()
            self.repository.update_job(
                job,
                {"status": "paused", "next_run_at": None, "updated_at": now},
            )
            self.repository.commit()
            projection = self.repository.get_job(job_id)
            if projection is None:
                raise AutomationNotFoundError("automation_job_not_found")
            return self._to_wire(projection)
        except (AutomationServiceError, HTTPException):
            self.repository.rollback()
            raise

    def resume(self, *, actor: AuthorizationActor, job_id: str) -> AutomationJob:
        return self.update(
            actor=actor,
            job_id=job_id,
            payload=JobUpdateRequest(status="active"),
        )

    def delete(self, *, actor: AuthorizationActor, job_id: str) -> None:
        try:
            job = self._require_locked(job_id)
            self.authorization.require_execute(
                actor=actor, workspace_id=job.workspace_id
            )
            self._require_workspace_mutable(job.workspace_id)
            if self.repository.has_active_executions(job.id):
                raise AutomationConflictError("automation_job_has_active_executions")
            now = self.repository.transaction_now()
            self.repository.update_job(
                job,
                {
                    "status": "paused",
                    "next_run_at": None,
                    "deleted_at": now,
                    "updated_at": now,
                },
            )
            self.repository.commit()
        except (AutomationServiceError, HTTPException):
            self.repository.rollback()
            raise

    def metrics(
        self, *, actor: AuthorizationActor, workspace_id: str | None = None
    ) -> dict[str, Any]:
        return self.repository.metrics(
            self._scope(actor=actor, workspace_id=workspace_id)
        )

    def calendar(
        self, *, actor: AuthorizationActor, workspace_id: str | None = None
    ) -> dict[str, Any]:
        items = self.repository.calendar(
            self._scope(actor=actor, workspace_id=workspace_id)
        )
        return {"items": items, "total": len(items)}

    def _candidate_values(
        self, job: Any, payload: JobUpdateRequest, *, actor_user_id: str
    ) -> dict[str, Any]:
        fields = payload.model_fields_set
        values: dict[str, Any] = {}
        required_when_present = {
            "name",
            "prompt",
            "status",
            "trigger",
            "schedule",
            "exact",
        }
        if any(
            name in fields and getattr(payload, name) is None
            for name in required_when_present
        ):
            raise AutomationValidationError("automation_job_invalid")
        for name in [
            "name",
            "description",
            "prompt",
            "status",
            "schedule",
            "exact",
        ]:
            if name in fields:
                values[name] = getattr(payload, name)
        if "trigger" in fields:
            values["trigger"] = payload.trigger.value if payload.trigger else None
        if {"agentic_tool", "model", "agent_config"} & fields:
            tool, model, config = self._resolve_agent_config(
                workspace_id=job.workspace_id,
                actor_user_id=actor_user_id,
                tool=(
                    payload.agentic_tool
                    if "agentic_tool" in fields
                    else job.agentic_tool
                ),
                model=payload.model if "model" in fields else job.model,
                mode=(
                    payload.agent_config.mode
                    if "agent_config" in fields and payload.agent_config
                    else job.agent_config.get("mode")
                ),
            )
            values.update(
                agentic_tool=tool,
                model=model,
                agent_config=config.model_dump(mode="json", by_alias=False),
            )
        notification = dict(job.notification_config or {})
        notification_fields = {
            "webhook_api_key",
            "delivery_webhook_url",
            "failure_destination",
        }
        if fields & notification_fields:
            if "webhook_api_key" in fields:
                notification["webhook_api_key"] = (
                    payload.webhook_api_key.get_secret_value()
                    if payload.webhook_api_key is not None
                    else None
                )
            for name in ["delivery_webhook_url", "failure_destination"]:
                if name in fields:
                    value = getattr(payload, name)
                    notification[name] = str(value) if value is not None else None
            values["notification_config"] = notification
        return values

    def _resolve_agent_config(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        tool: str | None,
        model: str | None,
        mode: str | None,
    ) -> tuple[str, str, AutomationAgentConfigSnapshot]:
        try:
            context = self.workspaces.get_authorization_context(
                workspace_id, current_user_id=actor_user_id
            )
            if context is None:
                raise ValueError
            capabilities = context.capabilities
            resolved_tool = tool or capabilities.default_tool
            capability = next(
                item for item in capabilities.tools if item.id == resolved_tool
            )
            resolved_model = model or capability.default_model
            resolved_mode = mode if mode is not None else capability.default_mode
            if resolved_model not in capability.models:
                raise ValueError
            if capability.modes is None:
                if resolved_mode is not None:
                    raise ValueError
            elif resolved_mode not in capability.modes:
                raise ValueError
            snapshot = AutomationAgentConfigSnapshot(
                mode=resolved_mode, permissionMode="bypassPermissions"
            )
            return resolved_tool, resolved_model, snapshot
        except (StopIteration, ValueError, ValidationError) as exc:
            raise AutomationConflictError(
                "automation_agent_config_unavailable"
            ) from exc

    def _scope(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str | None,
    ) -> list[str]:
        if workspace_id is not None:
            self.authorization.require_read(actor=actor, workspace_id=workspace_id)
            return [workspace_id]
        return self.authorization.accessible_workspace_ids(actor=actor)

    def _require_locked(self, job_id: str):
        job = self.repository.lock_job(job_id)
        if job is None:
            raise AutomationNotFoundError("automation_job_not_found")
        return job

    def _require_projection(self, job_id: str) -> JobProjection:
        projection = self.repository.get_job(job_id)
        if projection is None:
            raise AutomationNotFoundError("automation_job_not_found")
        return projection

    @staticmethod
    def _notification_dump(config: AutomationNotificationConfig) -> dict[str, Any]:
        return {
            "webhook_api_key": (
                config.webhook_api_key.get_secret_value()
                if config.webhook_api_key is not None
                else None
            ),
            "delivery_webhook_url": (
                str(config.delivery_webhook_url)
                if config.delivery_webhook_url is not None
                else None
            ),
            "failure_destination": (
                str(config.failure_destination)
                if config.failure_destination is not None
                else None
            ),
        }

    @staticmethod
    def _to_wire(projection: JobProjection) -> AutomationJob:
        job = projection.job
        notification = job.notification_config or {}
        total = projection.total_executions
        return AutomationJob.model_validate(
            {
                "id": job.id,
                "workspaceId": job.workspace_id,
                "creatorUserId": job.creator_user_id,
                "creatorDisplayName": projection.creator_display_name,
                "name": job.name,
                "description": job.description,
                "prompt": job.prompt,
                "status": job.status,
                "trigger": job.trigger,
                "schedule": job.schedule,
                "exact": job.exact,
                "agenticTool": job.agentic_tool,
                "model": job.model,
                "agentConfig": AutomationAgentConfigSnapshot.model_validate(
                    job.agent_config
                ),
                "worktreeKey": job.worktree_key,
                "worktreeBranch": job.worktree_branch,
                "webhookConfigured": bool(notification.get("webhook_api_key")),
                "deliveryWebhookUrl": notification.get("delivery_webhook_url"),
                "failureDestination": notification.get("failure_destination"),
                "nextRunAt": job.next_run_at,
                "lastRunAt": projection.last_run_at,
                "totalExecutions": total,
                "successRate": (
                    projection.successful_executions / total if total else 0.0
                ),
                "averageDuration": projection.average_duration,
                "lastDuration": projection.last_duration,
                "createdAt": job.created_at,
                "updatedAt": job.updated_at,
                "deletedAt": job.deleted_at,
            }
        )

    @staticmethod
    def _raise_schedule(exc: AutomationScheduleError) -> None:
        if exc.code == "automation_schedule_expired":
            raise AutomationConflictError(exc.code) from exc
        raise AutomationValidationError(exc.code) from exc


__all__ = [
    "AutomationConflictError",
    "AutomationJobService",
    "AutomationNotFoundError",
    "AutomationServiceError",
    "AutomationValidationError",
]
