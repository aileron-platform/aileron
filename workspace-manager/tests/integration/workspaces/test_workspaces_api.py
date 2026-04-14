"""Workspace API 整合測試"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.db import models as db_models


def _create_workspace(session_factory, *, owner_id: str, provisioner: str) -> str:
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=f"workspace-{provisioner}",
            owner_id=owner_id,
            name=f"{provisioner} workspace",
            runtime="universal",
            provisioner=provisioner,
            target_namespace="aileron" if provisioner == "kubernetes" else None,
            runtime_status="running",
            env_vars=[],
            port_mappings=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        session.add(workspace)
        session.commit()
        return workspace.id


@pytest.mark.integration
def test_update_kubernetes_workspace_triggers_apply_custom_resource(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="kubernetes",
    )

    with patch("app.routers.workspaces.run_apply_workspace_custom_resource_task") as mock_apply:
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={
                "runtimeResources": {
                    "requests": {"cpu": "750m", "memory": "3Gi"},
                    "limits": {"cpu": "2500m", "memory": "5Gi"},
                }
            },
        )

    assert response.status_code == 200
    assert response.json()["runtimeResources"]["requests"]["cpu"] == "750m"
    mock_apply.assert_called_once_with(workspace_id)


@pytest.mark.integration
def test_update_docker_workspace_does_not_trigger_apply_custom_resource(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="docker",
    )

    with patch("app.routers.workspaces.run_apply_workspace_custom_resource_task") as mock_apply:
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={"name": "updated docker workspace"},
        )

    assert response.status_code == 200
    mock_apply.assert_not_called()
