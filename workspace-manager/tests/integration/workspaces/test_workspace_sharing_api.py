from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.db import models as db_models


def _authenticate_as(client, monkeypatch, user: db_models.User) -> None:
    async def mock_validate_token(self, token: str) -> dict[str, str]:
        return {
            "sub": f"keycloak-{user.id}",
            "preferred_username": user.username,
            "email": user.email,
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": "Bearer test-access-token"})


def _create_workspace(session_factory, *, owner_id: str, name: str = "Shared Workspace") -> str:
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=f"workspace-{uuid4().hex[:8]}",
            owner_id=owner_id,
            name=name,
            runtime="universal",
            provisioner="docker",
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


def _create_share(
    session_factory,
    *,
    workspace_id: str,
    shared_with_user_id: str,
    granted_by_user_id: str,
    role: str,
) -> str:
    with session_factory() as session:
        share = db_models.WorkspaceShare(
            id=f"share-{uuid4().hex[:8]}",
            workspace_id=workspace_id,
            shared_with_user_id=shared_with_user_id,
            granted_by_user_id=granted_by_user_id,
            role=role,
        )
        session.add(share)
        session.commit()
        return share.id


@pytest.mark.integration
def test_workspace_list_includes_owned_and_shared_workspaces(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    sharer = create_user(username="sharer")
    member = create_user(username="member")

    owned_workspace_id = _create_workspace(session_factory, owner_id=member.id, name="Owned")
    shared_workspace_id = _create_workspace(session_factory, owner_id=sharer.id, name="Shared")
    _create_share(
        session_factory,
        workspace_id=shared_workspace_id,
        shared_with_user_id=member.id,
        granted_by_user_id=sharer.id,
        role="viewer",
    )
    _authenticate_as(client, monkeypatch, member)

    response = client.get("/api/v1/workspaces?page=1&pageSize=20")

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[owned_workspace_id]["accessSource"] == "owned"
    assert items[owned_workspace_id]["accessRole"] == "owner"
    assert items[shared_workspace_id]["accessSource"] == "shared"
    assert items[shared_workspace_id]["accessRole"] == "viewer"


@pytest.mark.integration
def test_workspace_share_creation_rejects_duplicate_and_self_share(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    member = create_user(username="member")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"email": member.email, "role": "editor"},
    )
    duplicate_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"email": member.email, "role": "viewer"},
    )
    self_share_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"email": owner.email, "role": "manager"},
    )

    assert create_response.status_code == 201
    assert create_response.json()["role"] == "editor"
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"]
    assert self_share_response.status_code == 400
    assert "owner" in self_share_response.json()["detail"]


@pytest.mark.integration
def test_shared_user_can_get_workspace_detail_but_unauthorized_user_cannot(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    viewer = create_user(username="viewer")
    outsider = create_user(username="outsider")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        shared_with_user_id=viewer.id,
        granted_by_user_id=owner.id,
        role="viewer",
    )

    _authenticate_as(client, monkeypatch, viewer)
    shared_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    _authenticate_as(client, monkeypatch, outsider)
    denied_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert shared_response.status_code == 200
    assert shared_response.json()["accessSource"] == "shared"
    assert shared_response.json()["accessRole"] == "viewer"
    assert denied_response.status_code == 403


@pytest.mark.integration
def test_manager_can_update_and_manage_shares_but_editor_cannot(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    manager = create_user(username="manager")
    editor = create_user(username="editor")
    newcomer = create_user(username="newcomer")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        shared_with_user_id=manager.id,
        granted_by_user_id=owner.id,
        role="manager",
    )
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        shared_with_user_id=editor.id,
        granted_by_user_id=owner.id,
        role="editor",
    )

    _authenticate_as(client, monkeypatch, manager)
    update_response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "managed-update"},
    )
    list_response = client.get(f"/api/v1/workspaces/{workspace_id}/shares")
    create_share_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"email": newcomer.email, "role": "viewer"},
    )

    _authenticate_as(client, monkeypatch, editor)
    editor_update_response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "blocked-update"},
    )
    editor_share_response = client.get(f"/api/v1/workspaces/{workspace_id}/shares")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "managed-update"
    assert list_response.status_code == 200
    assert create_share_response.status_code == 201
    assert editor_update_response.status_code == 403
    assert editor_share_response.status_code == 403


@pytest.mark.integration
def test_only_owner_can_delete_workspace_and_manager_can_rebuild(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    manager = create_user(username="manager")
    viewer = create_user(username="viewer")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        shared_with_user_id=manager.id,
        granted_by_user_id=owner.id,
        role="manager",
    )
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        shared_with_user_id=viewer.id,
        granted_by_user_id=owner.id,
        role="viewer",
    )

    with patch("app.routers.workspaces.run_restart_workspace_task") as mock_rebuild:
        _authenticate_as(client, monkeypatch, manager)
        rebuild_response = client.post(f"/api/v1/workspaces/{workspace_id}/rebuild")
        _authenticate_as(client, monkeypatch, viewer)
        denied_rebuild_response = client.post(f"/api/v1/workspaces/{workspace_id}/rebuild")

    with patch("app.routers.workspaces.run_delete_workspace_task") as mock_delete:
        _authenticate_as(client, monkeypatch, manager)
        denied_delete_response = client.delete(f"/api/v1/workspaces/{workspace_id}")
        _authenticate_as(client, monkeypatch, owner)
        delete_response = client.delete(f"/api/v1/workspaces/{workspace_id}")

    assert rebuild_response.status_code == 202
    mock_rebuild.assert_called_once_with(workspace_id)
    assert denied_rebuild_response.status_code == 403
    assert denied_delete_response.status_code == 403
    assert delete_response.status_code == 202
    mock_delete.assert_called_once_with(workspace_id)
