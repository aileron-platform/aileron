"""Provider-boundary tests for Workspace execution-plane observation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceService,
    WorkspaceCustomResourceStatusSnapshot,
)
from app.modules.workspace.execution_plane_observation import (
    WorkspaceExecutionPlaneObservationService,
)
from app.modules.workspace.orchestrator.factory import OrchestratorFactory


def _workspace(*, provisioner: str = "docker") -> SimpleNamespace:
    instance_id = "11111111-1111-4111-8111-111111111111"
    return SimpleNamespace(
        id="workspace-1",
        provisioner=provisioner,
        runtime_instance_id=instance_id,
        browser_instance_id=instance_id,
        canvas_instance_id=instance_id,
        runtime_container_id="runtime-1",
        browser_container_id="browser-1",
        canvas_container_id="canvas-1",
        runtime_desired_revision=3,
        browser_desired_revision=4,
        canvas_desired_revision=5,
    )


def _kubernetes_snapshot(workspace) -> WorkspaceCustomResourceStatusSnapshot:
    components = {}
    for component, revision, pod_uid in (
        ("runtime", 3, "runtime-pod"),
        ("browser", 4, "browser-pod"),
        ("canvas", 5, "canvas-pod"),
    ):
        components[component] = {
            "observedInstanceId": getattr(workspace, f"{component}_instance_id"),
            "observedRevision": revision,
            "phase": "Running",
            "ready": True,
            "podUid": pod_uid,
        }
    return WorkspaceCustomResourceStatusSnapshot(
        workspace_id=workspace.id,
        resource_name=f"workspace-{workspace.id}",
        namespace="workspace-system",
        custom_resource={
            "metadata": {"generation": 7},
            "spec": {
                component: {
                    "instanceId": getattr(workspace, f"{component}_instance_id"),
                    "enabled": True,
                    "desiredState": "Running",
                }
                for component in ("runtime", "browser", "canvas")
            },
            "status": {
                "observedGeneration": 7,
                "phase": "Running",
                "components": components,
            },
        },
    )


@pytest.mark.parametrize(
    ("provider_result", "expected_state"),
    [(True, "ready"), (False, "drift")],
)
def test_docker_observation_projects_provider_identity_result(
    monkeypatch,
    provider_result: bool,
    expected_state: str,
) -> None:
    orchestrator = MagicMock()
    orchestrator.is_workspace_execution_plane_current.return_value = provider_result
    monkeypatch.setattr(
        OrchestratorFactory,
        "get_orchestrator",
        lambda _provisioner: orchestrator,
    )

    result = WorkspaceExecutionPlaneObservationService(MagicMock()).observe(
        _workspace()
    )

    assert result.state == expected_state


def test_provider_failure_is_unavailable_instead_of_drift(monkeypatch) -> None:
    monkeypatch.setattr(
        OrchestratorFactory,
        "get_orchestrator",
        lambda _provisioner: (_ for _ in ()).throw(RuntimeError("provider down")),
    )

    result = WorkspaceExecutionPlaneObservationService(MagicMock()).observe(
        _workspace()
    )

    assert result.state == "unavailable"


def test_kubernetes_observation_requires_cr_identity_and_all_pods() -> None:
    workspace = _workspace(provisioner="kubernetes")
    custom_resources = MagicMock()
    custom_resources.fetch_workspace_status_snapshot.return_value = (
        _kubernetes_snapshot(workspace)
    )
    custom_resources.fetch_workspace_pod_uids.return_value = frozenset(
        {"runtime-pod", "browser-pod", "canvas-pod"}
    )

    result = WorkspaceExecutionPlaneObservationService(
        MagicMock(),
        custom_resource_service=custom_resources,
    ).observe(workspace)

    assert result.state == "ready"


def test_kubernetes_observation_ignores_disabled_optional_components() -> None:
    workspace = _workspace(provisioner="kubernetes")
    snapshot = _kubernetes_snapshot(workspace)
    snapshot.custom_resource["spec"]["browser"]["enabled"] = False
    snapshot.custom_resource["spec"]["canvas"]["desiredState"] = "Stopped"
    del snapshot.custom_resource["status"]["components"]["browser"]
    del snapshot.custom_resource["status"]["components"]["canvas"]
    custom_resources = MagicMock()
    custom_resources.component_requires_running_workload.side_effect = (
        WorkspaceCustomResourceService.component_requires_running_workload
    )
    custom_resources.fetch_workspace_status_snapshot.return_value = snapshot
    custom_resources.fetch_workspace_pod_uids.return_value = frozenset({"runtime-pod"})

    result = WorkspaceExecutionPlaneObservationService(
        MagicMock(),
        custom_resource_service=custom_resources,
    ).observe(workspace)

    assert result.state == "ready"


@pytest.mark.parametrize("failure", ["missing_cr", "missing_pod", "wrong_generation"])
def test_kubernetes_partial_or_mismatched_execution_plane_is_drift(
    failure: str,
) -> None:
    workspace = _workspace(provisioner="kubernetes")
    snapshot = _kubernetes_snapshot(workspace)
    custom_resources = MagicMock()
    custom_resources.fetch_workspace_status_snapshot.return_value = snapshot
    custom_resources.fetch_workspace_pod_uids.return_value = frozenset(
        {"runtime-pod", "browser-pod", "canvas-pod"}
    )
    if failure == "missing_cr":
        custom_resources.fetch_workspace_status_snapshot.return_value = None
    elif failure == "missing_pod":
        custom_resources.fetch_workspace_pod_uids.return_value = frozenset(
            {"runtime-pod", "canvas-pod"}
        )
    else:
        snapshot.custom_resource["status"]["components"]["browser"][
            "observedInstanceId"
        ] = "22222222-2222-4222-8222-222222222222"

    result = WorkspaceExecutionPlaneObservationService(
        MagicMock(),
        custom_resource_service=custom_resources,
    ).observe(workspace)

    assert result.state == "drift"
