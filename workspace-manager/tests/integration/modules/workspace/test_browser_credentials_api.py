from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.db import models as db_models


def _set_platform_role(session_factory, *, user_id: str, role: str) -> None:
    with session_factory() as session:
        user = session.get(db_models.User, user_id)
        assert user is not None
        user.platform_role = role
        session.commit()


def _create_browser_workspace(session_factory, *, owner_id: str) -> str:
    workspace_id = str(uuid4())
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Browser credential workspace",
                runtime="universal",
                provisioner="docker",
                runtime_status="running",
                runtime_instance_id=str(uuid4()),
                browser_status="running",
                browser_connectivity_state="ready",
                browser_connectivity_contract_version="browser-connectivity/v1",
                browser_connectivity_admission="allowed",
                browser_connectivity_accepted_at=datetime.now(timezone.utc),
                browser_connectivity_expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=1),
                browser_desired_state="running",
                browser_desired_revision=1,
                browser_observed_revision=1,
                browser_credential_revision=1,
                browser_credential_observed_revision=1,
                browser_credential_key_id="test-browser-key",
                browser_credential_observed_key_id="test-browser-key",
                browser_credential_algorithm="hkdf-sha256-v1",
                browser_credential_observed_algorithm="hkdf-sha256-v1",
                browser_webrtc_internal_url="http://workspace-browser:6080",
                agentic_tools=["claude-code"],
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        session.commit()
    return workspace_id


@pytest.mark.integration
def test_browser_access_and_rotation_contract(
    authenticated_client,
    test_app,
) -> None:
    client, user = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_browser_workspace(session_factory, owner_id=user.id)

    access = client.post(f"/api/v1/workspaces/{workspace_id}/browser/access")

    assert access.status_code == 200
    assert access.headers["cache-control"] == "no-store"
    assert set(access.json()) == {
        "browserUrl",
        "password",
        "credentialRevision",
        "iceServers",
    }
    assert access.json()["credentialRevision"] == 1
    assert access.json()["iceServers"] == []
    assert access.json()["browserUrl"] == f"/workspaces/{workspace_id}/browser"

    rotation = client.post(
        f"/api/v1/workspaces/{workspace_id}/browser/credentials/rotate"
    )

    assert rotation.status_code == 202
    assert rotation.headers["cache-control"] == "no-store"
    assert rotation.json()["credentialRevision"] == 2
    assert rotation.json()["appliedOnNextStart"] is False
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.browser_credential_revision == 2
        assert workspace.browser_desired_revision == 2
        job = (
            session.query(db_models.WorkspaceRuntimeJob)
            .filter_by(
                workspace_id=workspace_id,
                operation="browser_credential_rotate",
            )
            .one()
        )
        assert job.job_metadata == {"browser_credential_revision": 2}


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    (
        "browser/access",
        "browser/credentials/rotate",
    ),
)
def test_workspace_owner_member_can_use_browser_operations(
    authenticated_client,
    test_app,
    path: str,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_browser_workspace(session_factory, owner_id=actor.id)
    _set_platform_role(session_factory, user_id=actor.id, role="member")

    response = client.post(f"/api/v1/workspaces/{workspace_id}/{path}")

    assert response.status_code == (200 if path == "browser/access" else 202)


@pytest.mark.integration
def test_workspace_reader_cannot_issue_browser_stream_credentials(
    authenticated_client,
    test_app,
    create_user,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    owner = create_user(
        username="browser-owner",
        email="browser-owner@example.com",
    )
    workspace_id = _create_browser_workspace(session_factory, owner_id=owner.id)
    with session_factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id=str(uuid4()),
                workspace_id=workspace_id,
                target_type="user",
                target_id=actor.id,
                role="reader",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings"
    ) as credential_factory:
        response = client.post(f"/api/v1/workspaces/{workspace_id}/browser/access")

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == "WORKSPACE_OPERATION_DENIED"
    assert set(response.json()["detail"]) == {
        "errorCode",
        "message",
        "details",
    }
    credential_factory.assert_not_called()


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    (
        "browser/access",
        "browser/credentials/rotate",
    ),
)
def test_workspace_member_manager_can_use_browser_operations(
    authenticated_client,
    test_app,
    create_user,
    path: str,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    owner = create_user(
        username="assistant-browser-owner",
        email="assistant-browser-owner@example.com",
    )
    workspace_id = _create_browser_workspace(session_factory, owner_id=owner.id)
    _set_platform_role(
        session_factory,
        user_id=actor.id,
        role="member",
    )
    with session_factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id=str(uuid4()),
                workspace_id=workspace_id,
                target_type="user",
                target_id=actor.id,
                role="manager",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

    response = client.post(f"/api/v1/workspaces/{workspace_id}/{path}")

    assert response.status_code == (200 if path == "browser/access" else 202)


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    (
        "browser/access",
        "browser/credentials/rotate",
    ),
)
def test_member_without_workspace_relation_gets_hidden_not_found(
    authenticated_client,
    test_app,
    create_user,
    path: str,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    owner = create_user(
        username="member-browser-owner",
        email="member-browser-owner@example.com",
    )
    workspace_id = _create_browser_workspace(session_factory, owner_id=owner.id)
    _set_platform_role(session_factory, user_id=actor.id, role="member")

    response = client.post(f"/api/v1/workspaces/{workspace_id}/{path}")

    assert response.status_code == 404
    assert response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"
    assert set(response.json()["detail"]) == {
        "errorCode",
        "message",
        "details",
    }
