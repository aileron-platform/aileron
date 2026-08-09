from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from app.db import models as db_models
from app.modules.workspace.models import WorkspaceSetupStatus
from app.modules.workspace.setup import WorkspaceSetupError


def _create_workspace(session_factory, *, owner_id: str) -> str:
    workspace_id = str(uuid.uuid4())
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Setup authorization workspace",
                runtime="universal",
                provisioner="docker",
                runtime_status="running",
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        session.commit()
    return workspace_id


def _share_workspace(
    session_factory,
    *,
    workspace_id: str,
    actor_id: str,
    owner_id: str,
    role: str,
) -> None:
    with session_factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                target_type="user",
                target_id=actor_id,
                role=role,
                granted_by_user_id=owner_id,
            )
        )
        session.commit()


def _setup_status(workspace_id: str) -> WorkspaceSetupStatus:
    return WorkspaceSetupStatus(
        workspaceId=workspace_id,
        completed=True,
        tasks=[],
    )


class TestWorkspaceSetupAPI:
    @pytest.mark.integration
    def test_workspace_setup_sync_error_is_localized(
        self,
        authenticated_client,
        test_app,
    ):
        client, actor = authenticated_client
        _, session_factory = test_app
        workspace_id = _create_workspace(session_factory, owner_id=actor.id)

        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.run_initial_sync",
            side_effect=WorkspaceSetupError(
                "Workspace runtime is not ready. Unable to start sync",
                code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY",
            ),
        ):
            en_response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")
            assert en_response.status_code == status.HTTP_409_CONFLICT
            assert (
                en_response.json()["detail"]
                == "Workspace runtime is not ready. Unable to start sync."
            )

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.run_initial_sync",
            side_effect=WorkspaceSetupError(
                "Workspace runtime is not ready. Unable to start sync",
                code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY",
            ),
        ):
            zh_response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")
            assert zh_response.status_code == status.HTTP_409_CONFLICT
            assert (
                zh_response.json()["detail"]
                == "Workspace runtime 尚未就緒，無法啟動同步。"
            )

    @pytest.mark.integration
    def test_workspace_reader_cannot_start_workspace_setup_sync(
        self,
        authenticated_client,
        test_app,
        create_user,
    ) -> None:
        client, actor = authenticated_client
        _, session_factory = test_app
        owner = create_user(
            username="setup-owner",
            email="setup-owner@example.com",
        )
        workspace_id = _create_workspace(session_factory, owner_id=owner.id)
        _share_workspace(
            session_factory,
            workspace_id=workspace_id,
            actor_id=actor.id,
            owner_id=owner.id,
            role="reader",
        )

        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.run_initial_sync",
            new_callable=AsyncMock,
        ) as sync_mock:
            response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"]["errorCode"] == "WORKSPACE_OPERATION_DENIED"
        sync_mock.assert_not_awaited()

    @pytest.mark.integration
    @pytest.mark.parametrize("access_mode", ("owner", "manager"))
    def test_workspace_managers_can_start_workspace_setup_sync(
        self,
        authenticated_client,
        test_app,
        create_user,
        access_mode: str,
    ) -> None:
        client, actor = authenticated_client
        _, session_factory = test_app
        if access_mode == "owner":
            workspace_id = _create_workspace(session_factory, owner_id=actor.id)
        else:
            owner = create_user(
                username="setup-manager-owner",
                email="setup-manager-owner@example.com",
            )
            workspace_id = _create_workspace(session_factory, owner_id=owner.id)
            _share_workspace(
                session_factory,
                workspace_id=workspace_id,
                actor_id=actor.id,
                owner_id=owner.id,
                role="manager",
            )

        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.run_initial_sync",
            new_callable=AsyncMock,
            return_value=_setup_status(workspace_id),
        ) as sync_mock:
            response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["workspaceId"] == workspace_id
        sync_mock.assert_awaited_once_with(workspace_id)

    @pytest.mark.integration
    def test_unshared_workspace_status_is_denied_before_runtime_call(
        self,
        authenticated_client,
        test_app,
        create_user,
    ) -> None:
        client, _ = authenticated_client
        _, session_factory = test_app
        owner = create_user(
            username="status-owner",
            email="status-owner@example.com",
        )
        workspace_id = _create_workspace(session_factory, owner_id=owner.id)

        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.fetch_runtime_status",
            new_callable=AsyncMock,
        ) as status_mock:
            response = client.get(f"/api/v1/workspaces/{workspace_id}/setup/status")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"
        status_mock.assert_not_awaited()

    @pytest.mark.integration
    def test_workspace_reader_can_read_shared_workspace_setup_status(
        self,
        authenticated_client,
        test_app,
        create_user,
    ) -> None:
        client, actor = authenticated_client
        _, session_factory = test_app
        owner = create_user(
            username="status-owner-reader",
            email="status-owner-reader@example.com",
        )
        workspace_id = _create_workspace(session_factory, owner_id=owner.id)
        _share_workspace(
            session_factory,
            workspace_id=workspace_id,
            actor_id=actor.id,
            owner_id=owner.id,
            role="reader",
        )
        with patch(
            "app.modules.workspace.setup_router.WorkspaceSetupService.fetch_runtime_status",
            new_callable=AsyncMock,
            return_value=_setup_status(workspace_id),
        ) as status_mock:
            response = client.get(f"/api/v1/workspaces/{workspace_id}/setup/status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["workspaceId"] == workspace_id
        status_mock.assert_awaited_once_with(workspace_id)
