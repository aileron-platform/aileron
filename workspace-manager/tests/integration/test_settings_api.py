"""User Settings API Integration Test."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import status

from tests.helpers.fixtures import TestDataFactory, MockResponses


class TestSettingsAPI:
    """Only keep Settings CRUD tests currently used by the product."""

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
        assert settings_data["codex"]["loginStatus"] == "notConnected"
        assert settings_data["codex"]["model"] == "gpt-5.3-codex"

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
                "model": "claude-3-7-sonnet-20250219",
                "selectedProvider": "anthropic",
            },
            "codex": {
                "loginStatus": "connected",
                "account": {
                    "accountId": "codex-account-1",
                    "email": "codex@example.com",
                    "planType": "pro",
                },
                "model": "gpt-5.3-codex",
                "environmentVariables": [
                    {"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"}
                ],
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
        assert settings_data["claudeCode"]["model"] == "claude-3-7-sonnet-20250219"
        assert settings_data["claudeCode"]["selectedProvider"] == "anthropic"
        assert settings_data["codex"]["loginStatus"] == "connected"
        assert settings_data["codex"]["account"]["email"] == "codex@example.com"
        assert settings_data["codex"]["environmentVariables"][0]["key"] == "OPENAI_BASE_URL"
        assert settings_data["git"]["userName"] == "Test User"

    @pytest.mark.integration
    def test_settings_003_sync_errors_are_localized(self, authenticated_client):
        client, user = authenticated_client

        with patch(
            "app.services.sync_service.SyncService.sync_to_all_workspaces",
            side_effect=RuntimeError("sync exploded"),
        ):
            en_response = client.post(f"/api/v1/users/{user.id}/settings/sync")
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Sync failed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.services.sync_service.SyncService.sync_to_all_workspaces",
            side_effect=RuntimeError("sync exploded"),
        ):
            zh_response = client.post(f"/api/v1/users/{user.id}/settings/sync")
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "同步失敗"

    @pytest.mark.integration
    def test_settings_004_generate_ssh_key_error_is_localized(self, authenticated_client):
        client, user = authenticated_client

        with patch(
            "app.routers.settings.SettingsService.generate_and_save_ssh_keys",
            side_effect=RuntimeError("ssh exploded"),
        ):
            en_response = client.post(f"/api/v1/users/{user.id}/ssh-keys/generate")
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Failed to generate SSH Key"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.settings.SettingsService.generate_and_save_ssh_keys",
            side_effect=RuntimeError("ssh exploded"),
        ):
            zh_response = client.post(f"/api/v1/users/{user.id}/ssh-keys/generate")
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "產生 SSH Key 失敗"


@pytest.fixture
def test_data_factory():
    """Test data factory fixture"""
    return TestDataFactory()


@pytest.fixture
def mock_responses():
    """Mock Response fixture"""
    return MockResponses()
