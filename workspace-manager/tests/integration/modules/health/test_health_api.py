"""Integration tests for the health API."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import status

from app.modules.auth.token_validation import JWKSFetchError


class TestHealthAPI:
    """Health API contracts."""

    @pytest.mark.integration
    def test_health_returns_service_status_as_json(self, test_app):
        client, _ = test_app

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "service" in data
        assert data["status"] == "healthy"
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        assert data["service"] == "workspace-manager"

    @pytest.mark.integration
    def test_health_rejects_post(self, test_app):
        client, _ = test_app

        response = client.post("/health")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.integration
    def test_oidc_health_reports_connection_failure_in_requested_locale(self, test_app):
        client, _ = test_app

        mock_config = Mock(OIDC_ISSUER_URL="https://oidc.example.com/realms/test")
        jwt_utils = Mock()
        jwt_utils.fetch_discovery = AsyncMock(
            side_effect=JWKSFetchError("OIDC discovery request failed")
        )

        with (
            patch(
                "app.modules.health.router.get_settings",
                return_value=mock_config,
            ),
            patch(
                "app.modules.health.router.get_jwt_utils",
                return_value=jwt_utils,
            ),
        ):
            en_response = client.get("/health/oidc")
            assert en_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert en_response.json()["message"] == "OIDC issuer connection failed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with (
            patch(
                "app.modules.health.router.get_settings",
                return_value=mock_config,
            ),
            patch(
                "app.modules.health.router.get_jwt_utils",
                return_value=jwt_utils,
            ),
        ):
            zh_response = client.get("/health/oidc")
            assert zh_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert zh_response.json()["message"] == "OIDC 發行者連線失敗"
