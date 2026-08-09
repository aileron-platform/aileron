from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.workspace.catalog import WorkspaceError
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


def _create_workspace(
    session_factory,
    *,
    owner_id: str,
    name: str = "Shared Workspace",
    browser_container_id: str | None = None,
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
            browser_container_id=browser_container_id,
            canvas_container_id=canvas_container_id,
        )
        session.add(workspace)
        session.commit()
        return workspace.id


def _create_share(
    session_factory,
    *,
    workspace_id: str,
    target_id: str,
    granted_by_user_id: str,
    role: str,
) -> str:
    with session_factory() as session:
        share = db_models.WorkspaceShare(
            id=f"share-{uuid4().hex[:8]}",
            workspace_id=workspace_id,
            target_type="user",
            target_id=target_id,
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
    sharer = create_user(username="sharer", platform_role="member", role_status="valid")
    member = create_user(username="member", platform_role="member", role_status="valid")

    owned_workspace_id = _create_workspace(
        session_factory, owner_id=member.id, name="Owned"
    )
    shared_workspace_id = _create_workspace(
        session_factory, owner_id=sharer.id, name="Shared"
    )
    _create_share(
        session_factory,
        workspace_id=shared_workspace_id,
        target_id=member.id,
        granted_by_user_id=sharer.id,
        role="reader",
    )
    _authenticate_as(client, monkeypatch, member)

    response = client.get("/api/v1/workspaces?page=1&pageSize=20")

    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}
    assert items[owned_workspace_id]["accessSource"] == "owned"
    assert items[owned_workspace_id]["accessRole"] == "owner"
    assert items[shared_workspace_id]["accessSource"] == "direct_share"
    assert items[shared_workspace_id]["accessRole"] == "reader"


@pytest.mark.integration
def test_workspace_share_creation_rejects_duplicate_and_self_share(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    member = create_user(username="member", platform_role="member", role_status="valid")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"targetType": "user", "targetId": member.id, "role": "manager"},
    )
    duplicate_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"targetType": "user", "targetId": member.id, "role": "reader"},
    )
    self_share_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"targetType": "user", "targetId": owner.id, "role": "manager"},
    )

    assert create_response.status_code == 201
    assert create_response.json()["role"] == "manager"
    assert duplicate_response.status_code == 409
    assert (
        duplicate_response.json()["detail"]["errorCode"] == "WORKSPACE_SHARE_CONFLICT"
    )
    assert (
        duplicate_response.json()["detail"]["message"]
        == "Workspace share already exists"
    )
    assert (
        duplicate_response.json()["detail"]["details"]["resource"] == "workspace_share"
    )
    assert self_share_response.status_code == 400
    assert (
        self_share_response.json()["detail"]["errorCode"]
        == "WORKSPACE_INVALID_SHARE_TARGET"
    )
    assert (
        self_share_response.json()["detail"]["message"]
        == "Cannot share a workspace with its owner"
    )
    assert (
        self_share_response.json()["detail"]["details"]["resource"] == "workspace_share"
    )
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        access_jobs = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "workspace_access_recycle",
                )
            )
        )
    assert workspace.runtime_access_revision == 0
    assert access_jobs == []


@pytest.mark.integration
def test_shared_user_can_get_workspace_detail_but_unauthorized_user_cannot(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    reader = create_user(username="reader", platform_role="member", role_status="valid")
    outsider = create_user(
        username="outsider", platform_role="member", role_status="valid"
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=reader.id,
        granted_by_user_id=owner.id,
        role="reader",
    )

    _authenticate_as(client, monkeypatch, reader)
    shared_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    _authenticate_as(client, monkeypatch, outsider)
    denied_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert shared_response.status_code == 200
    assert shared_response.json()["accessSource"] == "direct_share"
    assert shared_response.json()["accessRole"] == "reader"
    assert denied_response.status_code == 404
    assert denied_response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.integration
def test_manager_can_update_and_manage_shares_but_reader_cannot(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    manager = create_user(
        username="manager", platform_role="member", role_status="valid"
    )
    reader = create_user(username="reader", platform_role="member", role_status="valid")
    newcomer = create_user(
        username="newcomer", platform_role="member", role_status="valid"
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=manager.id,
        granted_by_user_id=owner.id,
        role="manager",
    )
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=reader.id,
        granted_by_user_id=owner.id,
        role="reader",
    )

    _authenticate_as(client, monkeypatch, manager)
    update_response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "managed-update"},
    )
    list_response = client.get(f"/api/v1/workspaces/{workspace_id}/shares")
    create_share_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/shares",
        json={"targetType": "user", "targetId": newcomer.id, "role": "reader"},
    )

    _authenticate_as(client, monkeypatch, reader)
    reader_update_response = client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "blocked-update"},
    )
    reader_share_response = client.get(f"/api/v1/workspaces/{workspace_id}/shares")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "managed-update"
    assert list_response.status_code == 200
    assert create_share_response.status_code == 201
    assert reader_update_response.status_code == 403
    assert reader_share_response.status_code == 403


@pytest.mark.integration
def test_workspace_share_update_and_delete_return_structured_not_found_error(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    update_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/shares/share-missing",
        json={"role": "reader"},
    )
    delete_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/shares/share-missing"
    )

    assert update_response.status_code == 404
    assert update_response.json()["detail"]["errorCode"] == "WORKSPACE_SHARE_NOT_FOUND"
    assert update_response.json()["detail"]["message"] == "Workspace share not found"
    assert update_response.json()["detail"]["details"]["resource"] == "workspace_share"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"]["errorCode"] == "WORKSPACE_SHARE_NOT_FOUND"
    assert delete_response.json()["detail"]["message"] == "Workspace share not found"
    assert delete_response.json()["detail"]["details"]["resource"] == "workspace_share"


@pytest.mark.integration
def test_workspace_share_access_reduction_uses_http_lineage_and_durable_recycle(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(
        username="recycle-owner", platform_role="member", role_status="valid"
    )
    member = create_user(
        username="recycle-member", platform_role="member", role_status="valid"
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    share_id = _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=member.id,
        granted_by_user_id=owner.id,
        role="manager",
    )
    _authenticate_as(client, monkeypatch, owner)
    downgrade_correlation_id = str(uuid4())
    upgrade_correlation_id = str(uuid4())
    delete_correlation_id = str(uuid4())

    downgrade_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/shares/{share_id}",
        json={"role": "reader"},
        headers={"X-Correlation-ID": downgrade_correlation_id},
    )
    upgrade_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/shares/{share_id}",
        json={"role": "manager"},
        headers={"X-Correlation-ID": upgrade_correlation_id},
    )
    delete_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/shares/{share_id}",
        headers={"X-Correlation-ID": delete_correlation_id},
    )

    assert downgrade_response.status_code == 200
    assert downgrade_response.headers["X-Correlation-ID"] == downgrade_correlation_id
    assert upgrade_response.status_code == 200
    assert delete_response.status_code == 204
    assert delete_response.headers["X-Correlation-ID"] == delete_correlation_id

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        jobs = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "workspace_access_recycle",
                )
                .order_by(db_models.WorkspaceRuntimeJob.target_revision)
            )
        )
        audits = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(
                    db_models.AuditEvent.event_type
                    == "runtime.access_recycle_requested",
                    db_models.AuditEvent.target_id == workspace_id,
                )
                .order_by(db_models.AuditEvent.created_at, db_models.AuditEvent.id)
            )
        )

        assert session.get(db_models.WorkspaceShare, share_id) is None

    assert workspace.runtime_access_revision == 2
    assert workspace.runtime_access_observed_revision == 0
    assert workspace.knowledge_base_mount_desired_revision == 0
    assert [job.target_revision for job in jobs] == [1, 2]
    assert [job.status for job in jobs] == ["superseded", "queued"]
    assert [job.correlation_id for job in jobs] == [
        downgrade_correlation_id,
        delete_correlation_id,
    ]
    assert [job.root_correlation_id for job in jobs] == [
        downgrade_correlation_id,
        delete_correlation_id,
    ]
    assert [job.job_metadata["reason"] for job in jobs] == [
        "workspace_share_downgraded",
        "workspace_share_deleted",
    ]
    assert all(job.target_runtime_instance_id is None for job in jobs)
    audits_by_correlation = {audit.correlation_id: audit for audit in audits}
    assert set(audits_by_correlation) == {
        downgrade_correlation_id,
        delete_correlation_id,
    }
    assert all(audit.root_correlation_id == audit.correlation_id for audit in audits)
    assert upgrade_correlation_id not in {job.correlation_id for job in jobs} | {
        audit.correlation_id for audit in audits
    }


@pytest.mark.integration
def test_runtime_logs_do_not_expose_raw_detail_and_are_localized(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
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
    assert all(
        "Unexpected internal stack trace marker" not in message
        for message in en_messages
    )

    assert zh_response.status_code == 200
    zh_messages = [item["message"] for item in zh_response.json()]
    assert "Browser 容器啟動失敗" in zh_messages
    assert "Runtime 日誌已更新" in zh_messages
    assert all("connection refused" not in message for message in zh_messages)
    assert all(
        "Unexpected internal stack trace marker" not in message
        for message in zh_messages
    )


@pytest.mark.integration
def test_only_owner_can_delete_workspace_and_manager_can_restart_component(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    manager = create_user(
        username="manager", platform_role="member", role_status="valid"
    )
    reader = create_user(username="reader", platform_role="member", role_status="valid")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=manager.id,
        granted_by_user_id=owner.id,
        role="manager",
    )
    _create_share(
        session_factory,
        workspace_id=workspace_id,
        target_id=reader.id,
        granted_by_user_id=owner.id,
        role="reader",
    )

    _authenticate_as(client, monkeypatch, manager)
    restart_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/components/runtime/restart"
    )
    _authenticate_as(client, monkeypatch, reader)
    denied_restart_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/components/runtime/restart"
    )

    _authenticate_as(client, monkeypatch, manager)
    denied_delete_response = client.request(
        "DELETE",
        f"/api/v1/workspaces/{workspace_id}",
        json={"confirmationName": "Shared Workspace"},
    )
    _authenticate_as(client, monkeypatch, owner)
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        workspace.runtime_status = "stopped"
        for job in list(workspace.runtime_jobs):
            session.delete(job)
        session.commit()
    delete_response = client.request(
        "DELETE",
        f"/api/v1/workspaces/{workspace_id}",
        json={"confirmationName": "Shared Workspace"},
    )

    assert restart_response.status_code == 202
    assert restart_response.json()["component"] == "runtime"
    assert restart_response.json()["targetRevision"] == 2
    assert denied_restart_response.status_code == 403
    assert denied_delete_response.status_code == 403
    assert delete_response.status_code == 202
    assert delete_response.json()["jobId"]


@pytest.mark.integration
def test_restart_browser_advances_only_browser_revision(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(
        username="browser-owner", platform_role="member", role_status="valid"
    )
    workspace_id = _create_workspace(
        session_factory,
        owner_id=owner.id,
        name="Browser Workspace",
        browser_container_id="browser-container-1",
    )
    _authenticate_as(client, monkeypatch, owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/components/browser/restart"
    )

    assert response.status_code == 202
    assert response.json()["workspaceId"] == workspace_id
    assert response.json()["status"] == "running"
    assert response.json()["component"] == "browser"
    assert response.json()["targetRevision"] == 2
    assert response.json()["jobId"]


@pytest.mark.integration
def test_restart_canvas_advances_only_canvas_revision(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(username="owner", platform_role="member", role_status="valid")
    workspace_without_canvas = _create_workspace(session_factory, owner_id=owner.id)
    workspace_with_canvas = _create_workspace(
        session_factory,
        owner_id=owner.id,
        name="Canvas Workspace",
        canvas_container_id="canvas-container-1",
    )
    _authenticate_as(client, monkeypatch, owner)

    missing_response = client.post(
        f"/api/v1/workspaces/{workspace_without_canvas}/components/canvas/restart"
    )

    success_response = client.post(
        f"/api/v1/workspaces/{workspace_with_canvas}/components/canvas/restart"
    )

    assert missing_response.status_code == 202
    assert missing_response.json()["status"] == "running"
    assert missing_response.json()["component"] == "canvas"
    assert missing_response.json()["jobId"]
    assert success_response.status_code == 202
    assert success_response.json()["workspaceId"] == workspace_with_canvas
    assert success_response.json()["status"] == "running"
    assert success_response.json()["component"] == "canvas"
    assert success_response.json()["jobId"]


@pytest.mark.integration
def test_workspace_share_translation_uses_error_code_instead_of_exception_message(
    test_app,
    create_user,
    monkeypatch,
):
    client, session_factory = test_app
    owner = create_user(
        username="owner-coded", platform_role="member", role_status="valid"
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.modules.workspace.router.WorkspaceService.create_share",
        side_effect=WorkspaceError(
            "totally different share conflict wording", code="WORKSPACE_SHARE_CONFLICT"
        ),
    ):
        en_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/shares",
            json={"targetType": "user", "targetId": "missing", "role": "reader"},
        )

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.modules.workspace.router.WorkspaceService.create_share",
        side_effect=WorkspaceError(
            "totally different share conflict wording", code="WORKSPACE_SHARE_CONFLICT"
        ),
    ):
        zh_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/shares",
            json={"targetType": "user", "targetId": "missing", "role": "reader"},
        )

    assert en_response.status_code == 409
    assert en_response.json()["detail"]["errorCode"] == "WORKSPACE_SHARE_CONFLICT"
    assert en_response.json()["detail"]["message"] == "Workspace share already exists"
    assert zh_response.status_code == 409
    assert zh_response.json()["detail"]["errorCode"] == "WORKSPACE_SHARE_CONFLICT"
    assert zh_response.json()["detail"]["message"] == "工作區分享已存在"
