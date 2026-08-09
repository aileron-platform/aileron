"""Workspace API Integration Test"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.settings.models import default_tool_model
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


@pytest.mark.integration
def test_create_workspace_accepts_agentic_tools(
    authenticated_client,
    test_app,
):
    client, _user = authenticated_client
    _, session_factory = test_app

    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "OpenCode Workspace",
            "description": "OpenCode workspace",
            "runtime": "universal",
            "agenticTools": ["opencode", "claude-code"],
        },
    )

    assert response.status_code == 201
    assert response.json()["agenticTools"] == ["claude-code", "opencode"]
    runtime_status = response.json()["runtimeStatus"]
    workspace_id = response.json()["id"]
    assert runtime_status["runtimeUrl"] == f"/workspaces/{workspace_id}/runtime"
    assert runtime_status["browserUrl"] == f"/workspaces/{workspace_id}/browser"
    assert runtime_status["canvasUrl"] == f"/workspaces/{workspace_id}/canvas"
    with session_factory() as db:
        job = (
            db.query(db_models.WorkspaceRuntimeJob)
            .filter_by(
                workspace_id=response.json()["id"],
                operation="workspace_start",
            )
            .one()
        )
        assert job.status == "queued"
        assert job.correlation_id == response.headers["X-Correlation-ID"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "deployment_field,deployment_value",
    (
        ("provisioner", "kubernetes"),
        ("targetNamespace", "workspace-system"),
    ),
)
def test_create_workspace_rejects_public_deployment_fields_with_code_only_400(
    authenticated_client,
    deployment_field: str,
    deployment_value: str,
) -> None:
    client, _user = authenticated_client

    response = client.post(
        "/api/v1/workspaces",
        json={
            "name": "Workspace",
            "runtime": "universal",
            deployment_field: deployment_value,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"errorCode": "WORKSPACE_INVALID_REQUEST"}}


@pytest.mark.integration
def test_update_workspace_accepts_agentic_tools(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"agenticTools": ["opencode", "claude-code"]},
    )

    assert response.status_code == 200
    assert response.json()["agenticTools"] == ["claude-code", "opencode"]


@pytest.mark.integration
def test_workspace_detail_includes_complete_authorization_snapshot(
    authenticated_client,
    test_app,
) -> None:
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="docker",
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert response.status_code == 200
    assert response.json()["accessRole"] == "owner"
    assert response.json()["accessSource"] == "owned"
    assert response.json()["accessSources"] == ["owned"]
    assert "workspace.detail.read" in response.json()["allowedOperations"]


@pytest.mark.integration
def test_workspace_get_and_list_project_only_same_origin_runtime_urls(
    authenticated_client,
    test_app,
) -> None:
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="docker",
    )

    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}")
    list_response = client.get("/api/v1/workspaces?page=1&pageSize=50")

    assert detail_response.status_code == 200
    runtime_status = detail_response.json()["runtimeStatus"]
    assert runtime_status["runtimeUrl"] == f"/workspaces/{workspace_id}/runtime"
    assert runtime_status["browserUrl"] == f"/workspaces/{workspace_id}/browser"
    assert runtime_status["canvasUrl"] == f"/workspaces/{workspace_id}/canvas"
    forbidden_runtime_fields = {
        "internalUrl",
        "externalUrl",
        "externalPort",
        "terminalExternalUrl",
        "browserWebrtcInternalUrl",
        "browserWebrtcExternalUrl",
        "browserWebrtcExternalPort",
        "canvasInternalUrl",
        "canvasExternalUrl",
        "canvasExternalPort",
    }
    assert forbidden_runtime_fields.isdisjoint(runtime_status)
    assert list_response.status_code == 200
    item = next(item for item in list_response.json()["items"] if item["id"] == workspace_id)
    assert item["runtimeUrl"] == f"/workspaces/{workspace_id}/runtime"
    assert "runtimeExternalUrl" not in item


@pytest.mark.integration
def test_workspace_gateway_authorization_allows_workspace_reader(
    authenticated_client,
    test_app,
) -> None:
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="docker",
    )

    response = client.get(
        "/api/v1/workspaces/gateway/authorize",
        headers={"X-Aileron-Workspace-Id": workspace_id},
    )

    assert response.status_code == 204
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.integration
def test_workspace_gateway_authorization_hides_unknown_workspace(
    authenticated_client,
) -> None:
    client, _user = authenticated_client

    response = client.get(
        "/api/v1/workspaces/gateway/authorize",
        headers={"X-Aileron-Workspace-Id": "unknown-workspace"},
    )

    assert response.status_code == 403


@pytest.mark.integration
def test_workspace_gateway_authorization_requires_manager_session(test_app) -> None:
    client, _session_factory = test_app

    response = client.get(
        "/api/v1/workspaces/gateway/authorize",
        headers={"X-Aileron-Workspace-Id": "unknown-workspace"},
    )

    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize(
    "deployment_field,deployment_value",
    (
        ("provisioner", "kubernetes"),
        ("targetNamespace", "workspace-system"),
        ("runtimeStatus", {"status": "running"}),
    ),
)
def test_update_workspace_rejects_manager_owned_fields_with_code_only_400(
    authenticated_client,
    test_app,
    deployment_field: str,
    deployment_value: object,
) -> None:
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="docker",
    )

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={deployment_field: deployment_value},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": {"errorCode": "WORKSPACE_INVALID_REQUEST"}}


@pytest.mark.integration
def test_update_workspace_rejects_empty_agentic_tools(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"agenticTools": []},
    )

    assert response.status_code == 422


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
            runtime_internal_url="http://workspace-runtime:3002",
            runtime_instance_id=str(uuid4()),
            agentic_tools=["claude-code"],
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        session.add(workspace)
        session.commit()
        return workspace.id


@pytest.mark.integration
def test_get_workspace_capabilities_returns_default_when_unset(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}/capabilities")

    assert response.status_code == 200
    assert response.json()["defaultTool"] == "claude"
    assert response.json()["tools"][0]["defaultModel"] == default_tool_model("claude")


@pytest.mark.integration
def test_put_workspace_capabilities_round_trips(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )

    payload = {
        "defaultTool": "codex",
        "tools": [
            {
                "id": "codex",
                "models": [default_tool_model("codex")],
                "defaultModel": default_tool_model("codex"),
                "modes": None,
                "defaultMode": None,
                "contextWindow": 200000,
            }
        ],
    }

    put_response = client.put(
        f"/api/v1/workspaces/{workspace_id}/capabilities",
        json=payload,
    )
    get_response = client.get(f"/api/v1/workspaces/{workspace_id}/capabilities")

    assert put_response.status_code == 200
    assert put_response.json() == payload
    assert get_response.status_code == 200
    assert get_response.json() == payload


@pytest.mark.integration
def test_put_workspace_capabilities_pushes_running_runtime(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )
    payload = {
        "defaultTool": "codex",
        "tools": [
            {
                "id": "codex",
                "models": [default_tool_model("codex")],
                "defaultModel": default_tool_model("codex"),
                "modes": None,
                "defaultMode": None,
                "contextWindow": 200000,
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post.return_value = mock_response

    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch(
            "app.modules.workspace.runtime.sync.runtime_command_headers",
            return_value={
                "Authorization": "Bearer signed-assertion",
                "Content-Type": "application/json",
            },
        ),
        patch("app.modules.workspace.router.SessionLocal", session_factory),
    ):
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}/capabilities",
            json=payload,
        )

    assert response.status_code == 200
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.call_args
    assert (
        call_args.args[0]
        == "http://workspace-runtime:3002/api/v1/internal/settings/capabilities"
    )
    assert call_args.kwargs["json"]["workspace_id"] == workspace_id
    assert call_args.kwargs["json"]["capabilities"]["default_tool"] == "codex"


@pytest.mark.integration
def test_put_workspace_capabilities_rejects_empty_tools(
    authenticated_client,
    test_app,
):
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(
        session_factory, owner_id=user.id, provisioner="docker"
    )

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}/capabilities",
        json={"defaultTool": "claude", "tools": []},
    )

    assert response.status_code == 422


@pytest.mark.integration
def test_workspace_capabilities_require_workspace_access(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(
        username="cap-owner",
        platform_role="member",
        role_status="valid",
    )
    outsider = create_user(
        username="cap-outsider",
        platform_role="member",
        role_status="valid",
    )
    workspace_id = _create_workspace(
        session_factory, owner_id=owner.id, provisioner="docker"
    )
    _authenticate_as(client, monkeypatch, outsider)

    get_response = client.get(f"/api/v1/workspaces/{workspace_id}/capabilities")
    put_response = client.put(
        f"/api/v1/workspaces/{workspace_id}/capabilities",
        json={
            "defaultTool": "codex",
            "tools": [
                {
                    "id": "codex",
                    "models": [default_tool_model("codex")],
                    "defaultModel": default_tool_model("codex"),
                    "modes": None,
                    "defaultMode": None,
                    "contextWindow": 200000,
                }
            ],
        },
    )

    assert get_response.status_code == 404
    assert put_response.status_code == 404
    assert get_response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"
    assert put_response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.integration
def test_update_kubernetes_workspace_enqueues_runtime_component_restart(
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

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"agenticTools": ["codex"]},
    )

    assert response.status_code == 200
    assert response.json()["agenticTools"] == ["codex"]
    assert response.json()["runtimeStatus"]["status"] == "restarting"
    with session_factory() as session:
        job = (
            session.query(db_models.WorkspaceRuntimeJob)
            .filter_by(
                workspace_id=workspace_id,
                operation="runtime_restart",
            )
            .one()
        )
        assert job.status == "queued"
        assert job.target_component == "runtime"
        assert job.target_revision == 2
        assert job.correlation_id == response.headers["X-Correlation-ID"]


@pytest.mark.integration
def test_update_docker_workspace_does_not_enqueue_restart(
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

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "updated docker workspace"},
    )

    assert response.status_code == 200
    with session_factory() as session:
        assert (
            session.query(db_models.WorkspaceRuntimeJob)
            .filter_by(workspace_id=workspace_id)
            .count()
            == 0
        )


@pytest.mark.integration
def test_workspace_worktree_subdir_round_trip(
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

    update_response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"worktreeSubdir": " branches/team-a "},
    )

    assert update_response.status_code == 200
    assert update_response.json()["worktreeSubdir"] == "branches/team-a"

    get_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert get_response.status_code == 200
    assert get_response.json()["worktreeSubdir"] == "branches/team-a"


@pytest.mark.integration
def test_update_docker_workspace_firewall_enqueues_delivery_command(
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

    response = client.put(
        f"/api/v1/workspaces/{workspace_id}/firewall",
        json={
            "revision": 1,
            "workspace": {
                "egressMode": "allowlist",
                "allowedDomains": ["example.com"],
            },
            "browser": {
                "egressMode": "unrestricted",
                "allowedDomains": [],
            },
        },
    )

    assert response.status_code == 202
    assert response.json()["workspace"]["allowedDomains"] == ["example.com"]
    with session_factory() as session:
        assert (
            session.query(db_models.WorkspaceFirewallSyncCommand)
            .filter_by(workspace_id=workspace_id, status="pending")
            .count()
            == 1
        )


@pytest.mark.integration
def test_update_kubernetes_workspace_firewall_does_not_restart_components(
    authenticated_client,
    test_app,
    monkeypatch,
):
    client, user = authenticated_client
    _, session_factory = test_app
    monkeypatch.setenv("CILIUM_ENABLED", "true")
    get_settings.cache_clear()
    workspace_id = _create_workspace(
        session_factory,
        owner_id=user.id,
        provisioner="kubernetes",
    )

    try:
        response = client.put(
            f"/api/v1/workspaces/{workspace_id}/firewall",
            json={
                "revision": 1,
                "workspace": {
                    "egressMode": "allowlist",
                    "allowedDomains": ["example.com"],
                },
                "browser": {
                    "egressMode": "unrestricted",
                    "allowedDomains": [],
                },
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 202
    with session_factory() as session:
        assert (
            session.query(db_models.WorkspaceRuntimeJob)
            .filter_by(workspace_id=workspace_id)
            .count()
            == 0
        )
