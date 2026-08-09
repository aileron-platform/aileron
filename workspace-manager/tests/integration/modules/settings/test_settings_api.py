"""User Settings API Integration Test."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.routing import APIRoute

from app.db import models as db_models
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.settings.models import default_tool_model
from app.modules.settings.router import router as settings_router


def _create_workspace(session_factory, *, owner_id: str) -> str:
    workspace_id = f"settings-sync-{uuid4().hex[:8]}"
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Settings sync workspace",
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
                id=str(uuid4()),
                workspace_id=workspace_id,
                target_type="user",
                target_id=actor_id,
                role=role,
                granted_by_user_id=owner_id,
            )
        )
        session.commit()


class TestSettingsAPI:
    """Only keep Settings CRUD tests currently used by the product."""

    def test_every_settings_route_uses_request_scoped_actor(self) -> None:
        routes = {
            route.name: route
            for route in settings_router.routes
            if isinstance(route, APIRoute)
        }

        assert routes
        for route in routes.values():
            dependency_calls = {
                dependency.call
                for dependency in route.dependant.dependencies
                for dependency in (dependency, *dependency.dependencies)
            }
            assert get_authorization_actor in dependency_calls

    @pytest.mark.integration
    def test_settings_001_get_user_settings(self, authenticated_client):
        """ST-001 Can get existing user settings"""
        client, user = authenticated_client

        # Get user settings
        response = client.get(f"/api/v1/users/{user.id}/settings")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        settings_data = data["data"]
        for field in ["general", "claudeCode", "codex"]:
            assert field in settings_data
        assert "gemini" not in settings_data
        assert settings_data["codex"]["loginStatus"] == "notConnected"
        assert settings_data["codex"]["model"] == default_tool_model("codex")
        assert settings_data["codex"]["modelSelection"]["availableModels"][
            0
        ] == default_tool_model("codex")
        assert settings_data["codex"]["modelSelection"]["allowedModels"][
            0
        ] == default_tool_model("codex")
        assert settings_data["codex"]["modelSelection"][
            "defaultModel"
        ] == default_tool_model("codex")
        assert settings_data["opencode"]["modelSelection"][
            "defaultModel"
        ] == default_tool_model("opencode")

    @pytest.mark.integration
    def test_settings_002_update_user_settings(self, authenticated_client):
        """ST-002 Can update existing user settings"""
        client, user = authenticated_client

        # Update user settings
        payload = {
            "general": {
                "theme": "dark",
                "language": "zh-TW",
                "timezone": "Asia/Taipei",
            },
            "claudeCode": {
                "model": "claude-cli-fixture",
            },
            "codex": {
                "loginStatus": "connected",
                "account": {
                    "accountId": "codex-account-1",
                    "email": "codex@example.com",
                    "planType": "pro",
                },
                "model": default_tool_model("codex"),
                "environmentVariables": [
                    {"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"}
                ],
                "modelSelection": {
                    "customModels": ["gpt-custom"],
                    "allowedModels": ["gpt-custom"],
                    "defaultModel": "gpt-custom",
                },
            },
            "opencode": {
                "model": "opencode-custom",
                "environmentVariables": [],
                "modelSelection": {
                    "customModels": ["opencode-custom"],
                    "allowedModels": ["opencode-custom"],
                    "defaultModel": "opencode-custom",
                },
            },
            "git": {
                "userName": "Test User",
                "userEmail": user.email,
            },
        }

        response = client.put(f"/api/v1/users/{user.id}/settings", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        settings_data = data["data"]
        assert settings_data["general"]["theme"] == "dark"
        assert settings_data["claudeCode"]["model"] == "claude-cli-fixture"
        assert settings_data["codex"]["loginStatus"] == "connected"
        assert settings_data["codex"]["account"]["email"] == "codex@example.com"
        assert (
            settings_data["codex"]["environmentVariables"][0]["key"]
            == "OPENAI_BASE_URL"
        )
        assert (
            settings_data["codex"]["modelSelection"]["availableModels"][-1]
            == "gpt-custom"
        )
        assert settings_data["opencode"]["modelSelection"]["allowedModels"] == [
            "opencode-custom"
        ]
        assert (
            settings_data["opencode"]["modelSelection"]["defaultModel"]
            == "opencode-custom"
        )
        assert settings_data["git"]["userName"] == "Test User"
        assert "gemini" not in settings_data

        reload_response = client.get(f"/api/v1/users/{user.id}/settings")
        assert reload_response.status_code == status.HTTP_200_OK
        reloaded_settings = reload_response.json()["data"]
        assert reloaded_settings["opencode"]["modelSelection"]["allowedModels"] == [
            "opencode-custom"
        ]
        assert (
            reloaded_settings["opencode"]["modelSelection"]["defaultModel"]
            == "opencode-custom"
        )

    @pytest.mark.integration
    def test_settings_update_ignores_removed_gemini_payload(self, authenticated_client):
        """Removed Gemini settings are not stored or returned."""
        client, user = authenticated_client

        response = client.put(
            f"/api/v1/users/{user.id}/settings",
            json={
                "gemini": {
                    "authMethod": "subscription",
                    "accessToken": "removed-token",
                    "environmentVariables": [{"key": "GEMINI_API_KEY", "value": "x"}],
                }
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert "gemini" not in response.json()["data"]

        reload_response = client.get(f"/api/v1/users/{user.id}/settings")
        assert reload_response.status_code == status.HTTP_200_OK
        assert "gemini" not in reload_response.json()["data"]

    @pytest.mark.integration
    def test_settings_update_rejects_invalid_model_selection(
        self, authenticated_client
    ):
        client, user = authenticated_client

        response = client.put(
            f"/api/v1/users/{user.id}/settings",
            json={
                "opencode": {
                    "modelSelection": {
                        "customModels": ["opencode-custom"],
                        "allowedModels": ["opencode-custom"],
                        "defaultModel": default_tool_model("opencode"),
                    }
                }
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["detail"] == "Model selection settings are invalid."

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.put(
            f"/api/v1/users/{user.id}/settings",
            json={
                "opencode": {
                    "modelSelection": {
                        "customModels": ["opencode-custom"],
                        "allowedModels": ["opencode-custom"],
                        "defaultModel": default_tool_model("opencode"),
                    }
                }
            },
        )

        assert zh_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert zh_response.json()["detail"] == "模型選擇設定無效。"

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("method", "path", "service_method"),
        (
            ("GET", "/api/v1/users/another-user/settings", "get_settings"),
            ("PUT", "/api/v1/users/another-user/settings", "get_settings"),
            (
                "POST",
                "/api/v1/users/another-user/ssh-keys/generate",
                "generate_and_save_ssh_keys",
            ),
        ),
    )
    def test_personal_settings_endpoints_reject_cross_user_access_before_service_call(
        self,
        authenticated_client,
        method: str,
        path: str,
        service_method: str,
    ) -> None:
        client, _ = authenticated_client

        with patch(
            f"app.modules.settings.router.SettingsService.{service_method}"
        ) as service_mock:
            response = client.request(
                method,
                path,
                json={} if method == "PUT" else None,
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        service_mock.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("owns_running_workspace", "should_sync"),
        (
            (True, True),
            (False, False),
        ),
    )
    def test_personal_settings_save_syncs_only_to_owned_running_workspaces(
        self,
        authenticated_client,
        test_app,
        owns_running_workspace: bool,
        should_sync: bool,
    ) -> None:
        client, user = authenticated_client
        _, session_factory = test_app
        if owns_running_workspace:
            _create_workspace(session_factory, owner_id=user.id)

        with patch(
            "app.modules.settings.router._sync_settings_to_runtimes",
            new_callable=AsyncMock,
        ) as sync_mock:
            response = client.put(
                f"/api/v1/users/{user.id}/settings",
                json={
                    "git": {
                        "userName": "Runtime Sync User",
                        "userEmail": "runtime-sync@example.com",
                    }
                },
            )

        assert response.status_code == status.HTTP_200_OK
        if should_sync:
            sync_mock.assert_awaited_once()
        else:
            sync_mock.assert_not_awaited()

    @pytest.mark.integration
    async def test_background_settings_sync_rechecks_capability_before_runtime_call(
        self,
        authenticated_client,
        test_app,
        monkeypatch,
    ) -> None:
        _, user = authenticated_client
        _, session_factory = test_app
        monkeypatch.setattr(
            "app.modules.settings.router.SessionLocal",
            session_factory,
        )

        with patch(
            "app.modules.settings.router.RuntimeSyncService.sync_settings_to_runtimes",
            new_callable=AsyncMock,
        ) as sync_mock:
            from app.modules.settings.router import _sync_settings_to_runtimes

            await _sync_settings_to_runtimes(
                user.id,
                {"git": {"userName": "ReadOnlyUser"}},
            )

        sync_mock.assert_not_awaited()

    @pytest.mark.integration
    def test_settings_003_sync_errors_are_localized(self, authenticated_client):
        client, user = authenticated_client

        with patch(
            "app.modules.workspace.runtime.settings_snapshot_sync.RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces",
            side_effect=RuntimeError("sync exploded"),
        ):
            en_response = client.post(f"/api/v1/users/{user.id}/settings/sync")
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Sync failed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.modules.workspace.runtime.settings_snapshot_sync.RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces",
            side_effect=RuntimeError("sync exploded"),
        ):
            zh_response = client.post(f"/api/v1/users/{user.id}/settings/sync")
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "同步失敗"

    @pytest.mark.integration
    @pytest.mark.parametrize("access_role", ("reader", "manager"))
    def test_non_owners_cannot_sync_settings_to_workspace(
        self,
        authenticated_client,
        test_app,
        create_user,
        access_role: str,
    ) -> None:
        client, user = authenticated_client
        _, session_factory = test_app
        owner = create_user(
            username=f"sync-{access_role}-owner",
            email=f"sync-{access_role}-owner@example.com",
        )
        workspace_id = _create_workspace(session_factory, owner_id=owner.id)
        _share_workspace(
            session_factory,
            workspace_id=workspace_id,
            actor_id=user.id,
            owner_id=owner.id,
            role=access_role,
        )
        target = (
            "app.modules.workspace.runtime.settings_snapshot_sync."
            "RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime"
        )

        with patch(target, new_callable=AsyncMock) as sync_mock:
            response = client.post(
                f"/api/v1/users/{user.id}/settings/sync/{workspace_id}"
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"]["errorCode"] == "WORKSPACE_OPERATION_DENIED"
        assert response.json()["detail"]["details"] == {}
        sync_mock.assert_not_awaited()

    @pytest.mark.integration
    @pytest.mark.parametrize("scope", ("all", "single"))
    def test_workspace_owner_can_sync_settings_to_runtime(
        self,
        authenticated_client,
        test_app,
        scope: str,
    ) -> None:
        client, user = authenticated_client
        _, session_factory = test_app
        workspace_id = _create_workspace(session_factory, owner_id=user.id)
        if scope == "all":
            target = "app.modules.workspace.runtime.settings_snapshot_sync.RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces"
            result = {
                "success": True,
                "message": "Settings synchronized",
                "workspaces": [],
            }
            url = f"/api/v1/users/{user.id}/settings/sync"
        else:
            target = "app.modules.workspace.runtime.settings_snapshot_sync.RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime"
            result = {"git": {"success": True}}
            url = f"/api/v1/users/{user.id}/settings/sync/{workspace_id}"

        with patch(target, new_callable=AsyncMock, return_value=result) as sync_mock:
            response = client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        sync_mock.assert_awaited_once()

    @pytest.mark.integration
    def test_settings_004_generate_ssh_key_error_is_localized(
        self, authenticated_client
    ):
        client, user = authenticated_client

        with patch(
            "app.modules.settings.router.SettingsService.generate_and_save_ssh_keys",
            side_effect=RuntimeError("ssh exploded"),
        ):
            en_response = client.post(f"/api/v1/users/{user.id}/ssh-keys/generate")
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Failed to generate SSH Key"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.modules.settings.router.SettingsService.generate_and_save_ssh_keys",
            side_effect=RuntimeError("ssh exploded"),
        ):
            zh_response = client.post(f"/api/v1/users/{user.id}/ssh-keys/generate")
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "產生 SSH Key 失敗"
