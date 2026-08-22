"""Provisioner-neutral Workspace execution-plane operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session
from app.config.settings import Settings, get_settings
from app.db import models as db_models
from app.modules.workspace.orchestrator.models import ExecutionPlaneInfo, RuntimeInfo
from app.modules.workspace.runtime.assertions import (
    DrainAssertionContext,
    RuntimeAssertionService,
)
from app.modules.workspace.runtime.provisioning import (
    RuntimeProvisionService,
    WorkspaceExecutionPlaneIdentity,
    WorkspaceExecutionPlanePlan,
)
from app.modules.workspace.advisory_lock import WorkspaceAdvisoryLockLostError
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionIdentity,
    WorkspaceCustomResourceExecutionPlan,
    WorkspaceCustomResourceExecutionResult,
    WorkspaceCustomResourceService,
)
from app.modules.workspace.runtime.job_execution import RuntimeJobClaimLostError

logger = logging.getLogger(__name__)

_ExecutionPlaneAttempt = (
    WorkspaceExecutionPlanePlan | WorkspaceCustomResourceExecutionPlan
)


class GenerationState(str, Enum):
    """Provisioner-neutral execution-plane outcome."""

    READY = "ready"
    FAILED = "failed"
    ABSENT = "absent"


@dataclass(frozen=True)
class GenerationClaim:
    """One claimed generation transition with durable-job fencing."""

    workspace_id: str
    job_id: str
    assert_owned: Callable[[], None] = field(repr=False)
    desired_state: GenerationState = GenerationState.READY
    runtime_instance_id: str | None = None
    expected_mounted_revision: int = 0
    target_mounted_revision: int = 0
    identity: WorkspaceExecutionPlaneIdentity | None = None
    delete_workspace: bool = False


@dataclass(frozen=True)
class GenerationOutcome:
    """Observable generation state without provider plan leakage."""

    state: GenerationState
    workspace_id: str
    generation_id: str | None
    runtime_url: str | None = None
    error_code: str | None = None
    _attempt: object | None = field(default=None, repr=False, compare=False)
    _provider_result: object | None = field(default=None, repr=False, compare=False)
    _error: Exception | None = field(default=None, repr=False, compare=False)

    def raise_for_failure(self) -> None:
        """Re-raise the implementation failure for durable-job classification."""

        if self.state != GenerationState.FAILED:
            return
        if self._error is None:
            raise RuntimeError(self.error_code or "WORKSPACE_GENERATION_FAILED")
        raise self._error


class WorkspaceExecutionPlane:
    """Own the complete Workspace generation transaction."""

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        runtime_provision: RuntimeProvisionService | None = None,
        custom_resources: WorkspaceCustomResourceService | None = None,
        runtime_database_service: Any | None = None,
        assertion_service_factory: Callable[[], RuntimeAssertionService] | None = None,
        http_client_factory: Callable[..., httpx.Client] | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.runtime_database = runtime_database_service
        self.runtime_provision = (
            runtime_provision
            if runtime_provision is not None
            else RuntimeProvisionService(
                db,
                runtime_database_service=runtime_database_service,
            )
        )
        self.custom_resources = (
            custom_resources
            if custom_resources is not None
            else WorkspaceCustomResourceService(
                db,
                runtime_database_service=runtime_database_service,
            )
        )
        self._assertion_service_factory = (
            assertion_service_factory or RuntimeAssertionService.from_settings
        )
        self._http_client_factory = http_client_factory or httpx.Client

    def _prepare(self, workspace: db_models.Workspace, generation_id: str) -> object:
        """Prepare and persist one generation without exposing adapter plans."""

        if workspace.provisioner == "kubernetes":
            attempt = self.custom_resources._prepare_generation(
                workspace,
                runtime_instance_id=generation_id,
            )
        elif workspace.provisioner == "docker":
            attempt = self.runtime_provision._prepare_generation(
                workspace,
                runtime_instance_id=generation_id,
            )
        else:
            raise ValueError("Workspace provisioner is unsupported")
        if (
            workspace.runtime_control_instance_id != attempt.runtime_instance_id
            or not workspace.runtime_control_token_hash
        ):
            raise ValueError("Runtime control generation is not prepared")
        workspace.runtime_instance_id = attempt.runtime_instance_id
        return attempt

    def _prepare_execution_plane(self, workspace: db_models.Workspace) -> object:
        """Prepare an internal generation attempt for durable reconcilers."""

        return self._prepare(workspace, str(uuid4()))

    def reconcile(
        self, claim: GenerationClaim, *, attempt: object | None = None
    ) -> GenerationOutcome:
        """Converge one claimed Workspace generation transition."""

        claim.assert_owned()
        try:
            if claim.desired_state == GenerationState.ABSENT:
                if claim.identity is None:
                    return GenerationOutcome(
                        state=GenerationState.ABSENT,
                        workspace_id=claim.workspace_id,
                        generation_id=None,
                    )
                self.best_effort_drain(
                    workspace_id=claim.workspace_id,
                    workspace_identity=claim.identity,
                    expected_mounted_revision=claim.expected_mounted_revision,
                    target_mounted_revision=claim.target_mounted_revision,
                    job_id=claim.job_id,
                    assert_claim=claim.assert_owned,
                )
                self._revoke_generation(claim.identity)
                self._terminate_persisted(
                    claim.identity,
                    assert_claim=claim.assert_owned,
                    delete_workspace=claim.delete_workspace,
                )
                return GenerationOutcome(
                    state=GenerationState.ABSENT,
                    workspace_id=claim.workspace_id,
                    generation_id=claim.identity.runtime_instance_id,
                )

            if attempt is None or claim.runtime_instance_id is None:
                raise ValueError("Prepared Workspace generation is required")
            identity = claim.identity
            if identity is not None:
                self.best_effort_drain(
                    workspace_id=claim.workspace_id,
                    workspace_identity=identity,
                    expected_mounted_revision=claim.expected_mounted_revision,
                    target_mounted_revision=claim.target_mounted_revision,
                    job_id=claim.job_id,
                    assert_claim=claim.assert_owned,
                )
            result = self._apply(attempt, claim.assert_owned)
            return GenerationOutcome(
                state=GenerationState.READY,
                workspace_id=claim.workspace_id,
                generation_id=claim.runtime_instance_id,
                runtime_url=self._runtime_url(result),
                _attempt=attempt,
                _provider_result=result,
            )
        except (RuntimeJobClaimLostError, WorkspaceAdvisoryLockLostError):
            raise
        except Exception as exc:
            return GenerationOutcome(
                state=GenerationState.FAILED,
                workspace_id=claim.workspace_id,
                generation_id=claim.runtime_instance_id,
                error_code=getattr(exc, "code", type(exc).__name__.upper()),
                _attempt=attempt,
                _error=exc,
            )

    def _apply(self, attempt: object, assert_claim: Callable[[], None]) -> object:
        if isinstance(attempt, WorkspaceCustomResourceExecutionPlan):
            return self.custom_resources._apply_generation(
                attempt,
                assert_claim=assert_claim,
                max_attempts=max(1, self.settings.RUNTIME_READY_TIMEOUT_SECONDS),
                interval_seconds=1.0,
            )
        if not isinstance(attempt, WorkspaceExecutionPlanePlan):
            raise TypeError("Workspace generation attempt is invalid")
        return self.runtime_provision._apply_generation(
            attempt,
            assert_claim=assert_claim,
            timeout_seconds=self.settings.RUNTIME_READY_TIMEOUT_SECONDS,
        )

    def _stage_ready(
        self,
        workspace: db_models.Workspace,
        outcome: GenerationOutcome,
    ) -> None:
        """Internal durable completion bridge for a Ready outcome."""

        if outcome.state != GenerationState.READY or outcome._provider_result is None:
            raise ValueError("Ready Workspace generation outcome is required")
        result = outcome._provider_result
        if isinstance(result, WorkspaceCustomResourceExecutionResult):
            self.custom_resources._stage_generation(workspace, result)
        elif isinstance(result, ExecutionPlaneInfo):
            self.runtime_provision._stage_generation(workspace, result)
        else:
            raise TypeError("Workspace generation result is invalid")

    def _discard_ready(
        self,
        outcome: GenerationOutcome,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        """Discard a Ready generation that lost its durable target."""

        result = outcome._provider_result
        attempt = outcome._attempt
        if isinstance(result, WorkspaceCustomResourceExecutionResult):
            self.custom_resources._discard_generation(
                result,
                assert_claim=assert_claim,
            )
        elif isinstance(attempt, WorkspaceExecutionPlanePlan) and isinstance(
            result, ExecutionPlaneInfo
        ):
            self.runtime_provision._discard_generation(
                attempt,
                result,
                assert_claim=assert_claim,
            )
        else:
            raise TypeError("Workspace generation outcome is invalid")

    def _revoke_generation(self, identity: WorkspaceExecutionPlaneIdentity) -> None:
        if not identity.runtime_instance_id:
            return
        database = self.runtime_database
        if database is None:
            database = self.runtime_provision.runtime_database_service
        database.deactivate(
            database.prepare(
                workspace_id=identity.id,
                runtime_instance_id=identity.runtime_instance_id,
            )
        )

    def _terminate_persisted(
        self,
        identity: WorkspaceExecutionPlaneIdentity,
        *,
        assert_claim: Callable[[], None],
        delete_workspace: bool,
    ) -> None:
        if identity.provisioner == "kubernetes":
            custom_identity = WorkspaceCustomResourceExecutionIdentity(
                workspace_id=identity.id,
                target_namespace=self.settings.RUNTIME_K8S_NAMESPACE,
                runtime_instance_id=identity.runtime_instance_id,
                runtime_pod_uid=identity.runtime_container_id,
                browser_pod_uid=identity.browser_container_id,
                canvas_pod_uid=identity.canvas_container_id,
            )
            if delete_workspace:
                self.custom_resources._delete_persisted_workspace(
                    custom_identity,
                    assert_claim=assert_claim,
                )
            else:
                self.custom_resources._discard_generation(
                    custom_identity,
                    assert_claim=assert_claim,
                )
            return
        if identity.provisioner != "docker":
            raise ValueError("Workspace provisioner is unsupported")
        self.runtime_provision._terminate_persisted_generation(
            identity,
            assert_claim=assert_claim,
        )
        self.runtime_provision._prove_generation_absent(
            identity,
            assert_claim=assert_claim,
        )

    @staticmethod
    def _runtime_url(result: object) -> str:
        if isinstance(result, WorkspaceCustomResourceExecutionResult):
            return result.runtime_internal_url
        if isinstance(result, ExecutionPlaneInfo):
            return result.runtime.internal_url
        raise TypeError("Workspace generation result is invalid")

    @staticmethod
    def _execution_plane_identity(
        workspace: db_models.Workspace,
    ) -> WorkspaceExecutionPlaneIdentity:
        return WorkspaceExecutionPlaneIdentity(
            id=workspace.id,
            provisioner=workspace.provisioner,
            runtime_instance_id=workspace.runtime_instance_id,
            browser_instance_id=workspace.browser_instance_id,
            canvas_instance_id=workspace.canvas_instance_id,
            runtime_container_id=workspace.runtime_container_id,
            browser_container_id=workspace.browser_container_id,
            canvas_container_id=workspace.canvas_container_id,
            runtime_internal_url=workspace.runtime_internal_url,
            terminal_internal_url=workspace.terminal_internal_url,
            runtime_internal_port=workspace.runtime_internal_port,
            browser_webrtc_internal_port=workspace.browser_webrtc_internal_port,
            canvas_internal_port=workspace.canvas_internal_port,
        )

    def _custom_resource_execution_identity(
        self,
        workspace: db_models.Workspace,
    ) -> WorkspaceCustomResourceExecutionIdentity:
        if workspace.provisioner != "kubernetes":
            raise ValueError("Workspace provisioner must be kubernetes")
        return WorkspaceCustomResourceExecutionIdentity(
            workspace_id=workspace.id,
            target_namespace=self.settings.RUNTIME_K8S_NAMESPACE,
            runtime_instance_id=workspace.runtime_instance_id,
            runtime_pod_uid=workspace.runtime_container_id,
            browser_pod_uid=workspace.browser_container_id,
            canvas_pod_uid=workspace.canvas_container_id,
        )

    def _apply_runtime_component(
        self,
        *,
        workspace_id: str,
        target_revision: int,
        plan: _ExecutionPlaneAttempt,
        assert_claim: Callable[[], None],
    ) -> RuntimeInfo | None:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise RuntimeError("Workspace disappeared before Runtime reconcile")
        if workspace.runtime_desired_revision != target_revision:
            raise RuntimeJobClaimLostError("Runtime desired revision advanced")
        provisioner = workspace.provisioner
        self.db.expunge(workspace)
        self.db.rollback()
        if provisioner == "kubernetes":
            self.custom_resources.apply_component_desired_revision(
                workspace,
                component="runtime",
                assert_claim=assert_claim,
                runtime_plan=(
                    plan
                    if isinstance(plan, WorkspaceCustomResourceExecutionPlan)
                    else None
                ),
                max_attempts=max(1, self.settings.RUNTIME_READY_TIMEOUT_SECONDS),
            )
            return None
        if provisioner == "docker":
            if not isinstance(plan, WorkspaceExecutionPlanePlan):
                raise TypeError("Docker Runtime component plan is invalid")
            return self.runtime_provision.apply_prepared_runtime_component(
                plan,
                assert_claim=assert_claim,
            )
        raise ValueError("Workspace provisioner is unsupported")

    def _apply_runtime_component_result(
        self,
        workspace: db_models.Workspace,
        plan: _ExecutionPlaneAttempt,
        result: RuntimeInfo | None,
    ) -> None:
        if (
            workspace.runtime_instance_id != plan.runtime_instance_id
            or workspace.runtime_control_instance_id != plan.runtime_instance_id
            or not workspace.runtime_control_token_hash
        ):
            raise ValueError("Runtime control generation is not active")
        if workspace.provisioner == "docker":
            if not isinstance(plan, WorkspaceExecutionPlanePlan):
                raise TypeError("Docker Runtime component plan is invalid")
            if result is None:
                raise RuntimeError("Docker Runtime reconcile result is missing")
            self.runtime_provision.apply_component_result(
                workspace,
                component="runtime",
                result=result,
            )
        elif not isinstance(plan, WorkspaceCustomResourceExecutionPlan):
            raise TypeError("Kubernetes Runtime component plan is invalid")

    def _prove_execution_plane_absent(
        self,
        workspace_identity: WorkspaceExecutionPlaneIdentity,
        custom_resource_identity: WorkspaceCustomResourceExecutionIdentity | None,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        if workspace_identity.provisioner == "kubernetes":
            if custom_resource_identity is None:
                raise RuntimeError("Kubernetes execution-plane identity is missing")
            if all(
                pod_uid is None
                for pod_uid in (
                    custom_resource_identity.runtime_pod_uid,
                    custom_resource_identity.browser_pod_uid,
                    custom_resource_identity.canvas_pod_uid,
                )
            ):
                self.custom_resources.prove_workspace_pods_absent(
                    workspace_id=custom_resource_identity.workspace_id,
                    assert_claim=assert_claim,
                )
                return
            self.custom_resources._prove_generation_absent(
                custom_resource_identity,
                assert_claim=assert_claim,
            )
            return
        if workspace_identity.provisioner != "docker":
            raise ValueError("Workspace provisioner is unsupported")
        self.runtime_provision._prove_generation_absent(
            workspace_identity,
            assert_claim=assert_claim,
        )

    def best_effort_drain(
        self,
        *,
        workspace_id: str,
        workspace_identity: WorkspaceExecutionPlaneIdentity,
        expected_mounted_revision: int,
        target_mounted_revision: int,
        job_id: str,
        assert_claim: Callable[[], None],
    ) -> None:
        if workspace_identity.runtime_instance_id is None:
            return
        deadline = datetime.now(timezone.utc) + timedelta(
            seconds=self.settings.RUNTIME_DRAIN_DEADLINE_SECONDS
        )
        context = DrainAssertionContext(
            workspace_id=workspace_id,
            expected_runtime_instance_id=workspace_identity.runtime_instance_id,
            expected_mounted_revision=expected_mounted_revision,
            target_revision=target_mounted_revision,
            drain_attempt_id=str(uuid4()),
            deadline=deadline,
            job_id=job_id,
        )
        try:
            assertions = self._assertion_service_factory()
            endpoints = (
                (
                    "runtime",
                    workspace_identity.runtime_internal_url,
                    "/api/v1/internal/runtime/drain",
                    assertions.sign_runtime_drain,
                ),
                (
                    "terminal",
                    workspace_identity.terminal_internal_url,
                    "/internal/drain",
                    assertions.sign_terminal_drain,
                ),
            )
            for component, base_url, relative_path, signer in endpoints:
                assert_claim()
                if not base_url:
                    continue
                try:
                    assertion = signer(context)
                    with self._http_client_factory(
                        timeout=self.settings.RUNTIME_DRAIN_DEADLINE_SECONDS
                    ) as client:
                        response = client.post(
                            base_url.rstrip("/") + relative_path,
                            headers={
                                "Authorization": f"Bearer {assertion}",
                            },
                        )
                        response.raise_for_status()
                        if response.status_code == 204:
                            logger.info(
                                "Workspace component drain acknowledged",
                                extra={
                                    "job_id": job_id,
                                    "workspace_id": workspace_id,
                                    "component": component,
                                },
                            )
                        else:
                            logger.warning(
                                "Workspace component drain acknowledgement failed",
                                extra={
                                    "job_id": job_id,
                                    "workspace_id": workspace_id,
                                    "component": component,
                                },
                            )
                except (RuntimeJobClaimLostError, WorkspaceAdvisoryLockLostError):
                    raise
                except Exception:
                    logger.warning(
                        "Workspace component drain acknowledgement failed",
                        extra={
                            "job_id": job_id,
                            "workspace_id": workspace_id,
                            "component": component,
                        },
                    )
                assert_claim()
        except (RuntimeJobClaimLostError, WorkspaceAdvisoryLockLostError):
            raise
        except Exception:
            logger.warning(
                "Workspace drain preparation failed; forcing workload termination",
                extra={
                    "job_id": job_id,
                    "workspace_id": workspace_id,
                },
            )
            assert_claim()


__all__ = [
    "GenerationClaim",
    "GenerationOutcome",
    "GenerationState",
    "WorkspaceExecutionPlane",
]
