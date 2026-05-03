from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.db import models as db_models
from app.services.workspace_service import WorkspaceError


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


def _create_workspace(
    session_factory,
    *,
    owner_id: str,
    name: str = "Shared Workspace",
    canvas_container_id: str | None = None,
) -> str:
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=f"workspace-{uuid4().hex[:8]}",
            owner_id=owner_id,
            name=name,
            runtime="universal",
            provisioner="docker",
            runtime_status="running",
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
            canvas_container_id=canvas_container_id,
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


def _create_runtime_log(
    session_factory,
    *,
    workspace_id: str,
    stage: str,
    message: str,
) -> str:
    with session_factory() as session:
        runtime_log = db_models.WorkspaceRuntimeLog(
            id=f"log-{uuid4().hex[:8]}",
            workspace_id=workspace_id,
            stage=stage,
            message=message,
            log_metadata={},
        )
        session.add(runtime_log)
        session.commit()
        return runtime_log.id


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
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "WORKSPACE_SHARE_CONFLICT"
    assert duplicate_response.json()["detail"]["message"] == "Workspace share already exists"
    assert duplicate_response.json()["detail"]["details"]["resource"] == "workspace_share"
    assert self_share_response.status_code == 400
    assert self_share_response.json()["detail"]["code"] == "WORKSPACE_INVALID_SHARE_TARGET"
    assert self_share_response.json()["detail"]["message"] == "Cannot share a workspace with its owner"
    assert self_share_response.json()["detail"]["details"]["resource"] == "workspace_share"


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
def test_workspace_share_update_and_delete_return_structured_not_found_error(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    update_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/shares/share-missing",
        json={"role": "viewer"},
    )
    delete_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/shares/share-missing"
    )

    assert update_response.status_code == 404
    assert update_response.json()["detail"]["code"] == "WORKSPACE_SHARE_NOT_FOUND"
    assert update_response.json()["detail"]["message"] == "Workspace share not found"
    assert update_response.json()["detail"]["details"]["resource"] == "workspace_share"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"]["code"] == "WORKSPACE_SHARE_NOT_FOUND"
    assert delete_response.json()["detail"]["message"] == "Workspace share not found"
    assert delete_response.json()["detail"]["details"]["resource"] == "workspace_share"


@pytest.mark.integration
def test_runtime_logs_do_not_expose_raw_detail_and_are_localized(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_runtime_log(
        session_factory,
        workspace_id=workspace_id,
        stage="browser_starting",
        message="Browser container startup failed: dial tcp 10.0.0.1:2375: connect: connection refused",
    )
    _create_runtime_log(
        session_factory,
        workspace_id=workspace_id,
        stage="unknown-stage",
        message="Unexpected internal stack trace marker",
    )
    _authenticate_as(client, monkeypatch, owner)

    en_response = client.get(f"/api/v1/workspaces/{workspace_id}/runtime-logs")
    client.headers["X-Language"] = "zh-TW"
    zh_response = client.get(f"/api/v1/workspaces/{workspace_id}/runtime-logs")

    assert en_response.status_code == 200
    en_messages = [item["message"] for item in en_response.json()]
    assert "Browser container startup failed" in en_messages
    assert "Runtime log updated" in en_messages
    assert all("connection refused" not in message for message in en_messages)
    assert all("Unexpected internal stack trace marker" not in message for message in en_messages)

    assert zh_response.status_code == 200
    zh_messages = [item["message"] for item in zh_response.json()]
    assert "Browser 容器啟動失敗" in zh_messages
    assert "Runtime 日誌已更新" in zh_messages
    assert all("connection refused" not in message for message in zh_messages)
    assert all("Unexpected internal stack trace marker" not in message for message in zh_messages)


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


@pytest.mark.integration
def test_restart_canvas_returns_localized_messages(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner")
    workspace_without_canvas = _create_workspace(session_factory, owner_id=owner.id)
    workspace_with_canvas = _create_workspace(
        session_factory,
        owner_id=owner.id,
        name="Canvas Workspace",
        canvas_container_id="canvas-container-1",
    )
    _authenticate_as(client, monkeypatch, owner)

    missing_response = client.post(f"/api/v1/workspaces/{workspace_without_canvas}/restart-canvas")

    with patch("app.routers.workspaces.run_restart_canvas_task") as mock_restart:
        with patch("app.routers.workspaces.WorkspaceService.mark_canvas_restarting", return_value=True):
            success_response = client.post(f"/api/v1/workspaces/{workspace_with_canvas}/restart-canvas")

    assert missing_response.status_code == 400
    assert missing_response.json()["detail"] == "No restartable Canvas container found for this workspace"
    assert success_response.status_code == 202
    assert success_response.json()["message"] == "Canvas container restart started"
    assert success_response.json()["workspaceId"] == workspace_with_canvas
    assert success_response.json()["status"] == "restarting"
    mock_restart.assert_called_once_with(workspace_with_canvas)


@pytest.mark.integration
def test_workspace_share_translation_uses_error_code_instead_of_exception_message(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner-coded")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.routers.workspaces.WorkspaceService.create_share",
        side_effect=WorkspaceError("totally different share conflict wording", code="WORKSPACE_SHARE_CONFLICT"),
    ):
        en_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/shares",
            json={"email": "someone@example.com", "role": "viewer"},
        )

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.routers.workspaces.WorkspaceService.create_share",
        side_effect=WorkspaceError("totally different share conflict wording", code="WORKSPACE_SHARE_CONFLICT"),
    ):
        zh_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/shares",
            json={"email": "someone@example.com", "role": "viewer"},
        )

    assert en_response.status_code == 409
    assert en_response.json()["detail"]["code"] == "WORKSPACE_SHARE_CONFLICT"
    assert en_response.json()["detail"]["message"] == "Workspace share already exists"
    assert zh_response.status_code == 409
    assert zh_response.json()["detail"]["code"] == "WORKSPACE_SHARE_CONFLICT"
    assert zh_response.json()["detail"]["message"] == "工作區分享已存在"
