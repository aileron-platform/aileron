"""Provider-neutral observation of the current Workspace execution plane."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.workspace.custom_resources import WorkspaceCustomResourceService
from app.modules.workspace.orchestrator.factory import OrchestratorFactory

logger = logging.getLogger(__name__)

ExecutionPlaneObservationState = Literal["ready", "drift", "unavailable"]


@dataclass(frozen=True)
class ExecutionPlaneObservation:
    """One provider observation without mutating control-plane state."""

    state: ExecutionPlaneObservationState

    @classmethod
    def ready(cls) -> ExecutionPlaneObservation:
        return cls(state="ready")

    @classmethod
    def drift(cls) -> ExecutionPlaneObservation:
        return cls(state="drift")

    @classmethod
    def unavailable(cls) -> ExecutionPlaneObservation:
        return cls(state="unavailable")


class WorkspaceExecutionPlaneObservationService:
    """Observe the persisted generation through its selected provider adapter."""

    def __init__(
        self,
        db: Session,
        *,
        custom_resource_service: WorkspaceCustomResourceService | None = None,
    ) -> None:
        self.custom_resources = (
            custom_resource_service
            if custom_resource_service is not None
            else WorkspaceCustomResourceService(db)
        )

    def observe(
        self,
        workspace: db_models.Workspace,
    ) -> ExecutionPlaneObservation:
        try:
            if workspace.provisioner == "kubernetes":
                return self._observe_kubernetes(workspace)
            orchestrator = OrchestratorFactory.get_orchestrator(workspace.provisioner)
            if orchestrator.is_workspace_execution_plane_current(workspace):
                return ExecutionPlaneObservation.ready()
            return ExecutionPlaneObservation.drift()
        except Exception:
            logger.warning(
                "Workspace execution-plane observation unavailable",
                extra={
                    "workspace_id": workspace.id,
                    "provisioner": workspace.provisioner,
                },
            )
            return ExecutionPlaneObservation.unavailable()

    def _observe_kubernetes(
        self,
        workspace: db_models.Workspace,
    ) -> ExecutionPlaneObservation:
        snapshot = self.custom_resources.fetch_workspace_status_snapshot(workspace.id)
        if snapshot is None:
            return ExecutionPlaneObservation.drift()
        custom_resource = snapshot.custom_resource
        metadata = custom_resource.get("metadata")
        spec = custom_resource.get("spec")
        status = custom_resource.get("status")
        if not all(isinstance(value, dict) for value in (metadata, spec, status)):
            return ExecutionPlaneObservation.drift()
        assert isinstance(metadata, dict)
        assert isinstance(spec, dict)
        assert isinstance(status, dict)
        generation = metadata.get("generation")
        components = status.get("components")
        if (
            not isinstance(generation, int)
            or status.get("observedGeneration") != generation
            or status.get("phase") != "Running"
            or not isinstance(components, dict)
        ):
            return ExecutionPlaneObservation.drift()

        expected_pod_uids: set[str] = set()
        for component in ("runtime", "browser", "canvas"):
            component_spec = spec.get(component)
            if not self.custom_resources.component_requires_running_workload(
                component,
                component_spec,
            ):
                continue
            component_status = components.get(component)
            expected_instance_id = (
                getattr(workspace, f"{component}_instance_id")
                or workspace.runtime_instance_id
            )
            expected_revision = getattr(workspace, f"{component}_desired_revision")
            if (
                not isinstance(component_spec, dict)
                or component_spec.get("instanceId") != expected_instance_id
                or not isinstance(component_status, dict)
                or component_status.get("observedInstanceId") != expected_instance_id
                or component_status.get("observedRevision") != expected_revision
                or component_status.get("phase") != "Running"
                or component_status.get("ready") is not True
            ):
                return ExecutionPlaneObservation.drift()
            pod_uid = component_status.get("podUid")
            if not isinstance(pod_uid, str) or not pod_uid:
                return ExecutionPlaneObservation.drift()
            expected_pod_uids.add(pod_uid)

        observed_pod_uids = self.custom_resources.fetch_workspace_pod_uids(workspace.id)
        if not expected_pod_uids.issubset(observed_pod_uids):
            return ExecutionPlaneObservation.drift()
        return ExecutionPlaneObservation.ready()


__all__ = [
    "ExecutionPlaneObservation",
    "ExecutionPlaneObservationState",
    "WorkspaceExecutionPlaneObservationService",
]
