"""使用者設定 API 整合測試。"""

from __future__ import annotations

import uuid

import pytest
from fastapi import status

from tests.helpers.fixtures import TestDataFactory, MockResponses


class TestSettingsAPI:
    """只保留目前產品實際使用的設定 CRUD 測試。"""

    @pytest.mark.integration
    def test_settings_001_get_user_settings(self, authenticated_client):
        """ST-001 可以取得既有使用者設定"""
        client, user = authenticated_client

        # 取得用戶設定
        response = client.get(f"/api/v1/users/{user.id}/settings")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        settings_data = data["data"]
        for field in ["general", "claudeCode"]:
            assert field in settings_data

    @pytest.mark.integration
    def test_settings_002_update_user_settings(self, authenticated_client):
        """ST-002 可以更新既有使用者設定"""
        client, user = authenticated_client

        # 更新用戶設定
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
        assert settings_data["git"]["userName"] == "Test User"


@pytest.fixture
def test_data_factory():
    """測試資料工廠 fixture"""
    return TestDataFactory()


@pytest.fixture
def mock_responses():
    """Mock 回應 fixture"""
    return MockResponses()
