"""OAuth API Integration Tests (Complete Version)"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import status


class TestOAuthAPI:
    """OAuth API Test Cases - Complete Version, Tests Actual OAuth Route Endpoints"""

    # ============ Test Actual OAuth Route Endpoints ============

    @pytest.mark.integration
    def test_oauth_new_001_get_oauth_info_success(self, authenticated_client):
        """OAuth-NEW-001 Get OAuth configuration info successfully"""
        client, _ = authenticated_client

        response = client.get("/api/v1/oauth/info")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        required_fields = ["client_id", "authorization_url", "redirect_uri", "scope"]
        for field in required_fields:
            assert field in data, f"OAuth info should contain {field} field"

        # Verify data format
        assert isinstance(data["client_id"], str)
        assert isinstance(data["authorization_url"], str)
        assert isinstance(data["redirect_uri"], str)
        assert isinstance(data["scope"], str)
        assert data["authorization_url"].startswith("http")

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.exchange_code")
    def test_oauth_new_002_exchange_code_success(
        self, mock_exchange: AsyncMock, authenticated_client
    ):
        """OAuth-NEW-002 Exchange OAuth authorization code successfully"""
        client, _ = authenticated_client

        # Mock OAuth exchange response
        from app.modules.identity.oauth import OAuthExchangeResult

        mock_exchange.return_value = OAuthExchangeResult(
            access_token="mock_access_token_123",
            refresh_token="mock_refresh_token_456",
            expires_at=1234567890000,
        )

        exchange_data = {
            "authCode": "test_auth_code_123",
            "verifier": "test_verifier_456",
        }

        response = client.post("/api/v1/oauth/exchange", json=exchange_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        required_fields = ["accessToken", "refreshToken", "expiresAt"]
        for field in required_fields:
            assert (
                field in data
            ), f"OAuth exchange response should contain {field} field"

        # Verify tokens are not empty
        assert len(data["accessToken"]) > 0
        assert len(data["refreshToken"]) > 0
        assert isinstance(data["expiresAt"], int)

    @pytest.mark.integration
    def test_oauth_new_003_exchange_code_missing_fields(self, authenticated_client):
        """OAuth-NEW-003 Exchange authorization code missing required fields"""
        client, _ = authenticated_client

        # Missing verifier
        exchange_data = {"authCode": "test_auth_code_123"}

        response = client.post("/api/v1/oauth/exchange", json=exchange_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.exchange_code")
    @patch("app.modules.identity.oauth.OAuthService.get_account_info")
    def test_oauth_new_004_authenticate_and_save_success(
        self,
        mock_account_info: AsyncMock,
        mock_exchange: AsyncMock,
        authenticated_client,
    ):
        """OAuth-NEW-004 OAuth authentication and save successfully"""
        client, user = authenticated_client

        # Mock OAuth exchange response
        from app.modules.identity.oauth import OAuthAccountInfo, OAuthExchangeResult

        mock_exchange.return_value = OAuthExchangeResult(
            access_token="mock_access_token_123",
            refresh_token="mock_refresh_token_456",
            expires_at=1234567890000,
        )

        # Mock account info response
        mock_account_info.return_value = OAuthAccountInfo(
            account_uuid="test_account_uuid",
            email_address="test@example.com",
            organization_uuid="test_org_uuid",
            display_name="Test User",
            organization_billing_type="free",
            organization_role="admin",
            workspace_role="member",
            organization_name="Test Org",
        )

        exchange_data = {
            "authCode": "test_auth_code_123",
            "verifier": "test_verifier_456",
        }

        response = client.post("/api/v1/oauth/authenticate", json=exchange_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert data["success"] is True
        assert "accessToken" in data
        assert "refreshToken" in data
        assert "expiresAt" in data
        assert "oauthAccount" in data

        # Verify account info
        account = data["oauthAccount"]
        assert account["emailAddress"] == "test@example.com"
        assert account["displayName"] == "Test User"

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.refresh_access_token")
    def test_oauth_new_005_refresh_token_success(
        self, mock_refresh: AsyncMock, authenticated_client
    ):
        """OAuth-NEW-005 Refresh access token successfully"""
        client, _ = authenticated_client

        # Mock refresh token response
        from app.modules.identity.oauth import OAuthExchangeResult

        mock_refresh.return_value = OAuthExchangeResult(
            access_token="new_access_token_789",
            refresh_token="new_refresh_token_012",
            expires_at=1234567890000,
        )

        refresh_data = {"refreshToken": "old_refresh_token_456"}

        response = client.post("/api/v1/oauth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        required_fields = ["accessToken", "refreshToken", "expiresAt"]
        for field in required_fields:
            assert field in data, f"OAuth refresh response should contain {field} field"

        # Verify tokens are not empty
        assert len(data["accessToken"]) > 0
        assert len(data["refreshToken"]) > 0

    @pytest.mark.integration
    def test_oauth_new_006_refresh_token_missing_token(self, authenticated_client):
        """OAuth-NEW-006 Refresh token missing refresh token"""
        client, _ = authenticated_client

        response = client.post("/api/v1/oauth/refresh", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_oauth_new_007_health_check_success(self, authenticated_client):
        """OAuth-NEW-007 OAuth health check successful"""
        client, _ = authenticated_client

        response = client.get("/api/v1/oauth/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify health check response
        assert "status" in data
        assert data["status"] == "healthy"
        assert "service" in data
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert (
            data["description"]
            == "OAuth authentication service providing code exchange and token refresh"
        )

    @pytest.mark.integration
    def test_oauth_new_008_health_check_localizes_description(self, authenticated_client):
        """OAuth-NEW-008 OAuth health check switches description based on locale"""
        client, _ = authenticated_client
        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})

        response = client.get("/api/v1/oauth/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert (
            data["description"]
            == "OAuth 認證服務，提供 code exchange 和 token refresh 功能"
        )

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.exchange_code")
    def test_oauth_new_009_exchange_provider_error_is_localized(
        self, mock_exchange: AsyncMock, authenticated_client
    ):
        """OAuth-NEW-009 OAuth exchange provider error is localized"""
        client, _ = authenticated_client

        request = httpx.Request("POST", "https://example.com/oauth")
        response = httpx.Response(400, request=request)
        mock_exchange.side_effect = httpx.HTTPStatusError(
            "provider boom", request=request, response=response
        )

        exchange_data = {
            "authCode": "test_auth_code_123",
            "verifier": "test_verifier_456",
        }

        en_response = client.post("/api/v1/oauth/exchange", json=exchange_data)
        assert en_response.status_code == status.HTTP_502_BAD_GATEWAY
        assert en_response.json()["detail"] == "OAuth provider error"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/oauth/exchange", json=exchange_data)
        assert zh_response.status_code == status.HTTP_502_BAD_GATEWAY
        assert zh_response.json()["detail"] == "OAuth provider 錯誤"

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.exchange_code")
    def test_oauth_new_010_exchange_internal_error_is_localized(
        self, mock_exchange: AsyncMock, authenticated_client
    ):
        """OAuth-NEW-010 OAuth exchange internal error is localized"""
        client, _ = authenticated_client
        mock_exchange.side_effect = RuntimeError("unexpected boom")

        exchange_data = {
            "authCode": "test_auth_code_123",
            "verifier": "test_verifier_456",
        }

        en_response = client.post("/api/v1/oauth/exchange", json=exchange_data)
        assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert en_response.json()["detail"] == "Failed to exchange OAuth code"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/oauth/exchange", json=exchange_data)
        assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert zh_response.json()["detail"] == "交換 OAuth 認證碼失敗"

    @pytest.mark.integration
    @patch("app.modules.identity.oauth.OAuthService.refresh_access_token")
    def test_oauth_new_011_refresh_internal_error_is_localized(
        self, mock_refresh: AsyncMock, authenticated_client
    ):
        """OAuth-NEW-011 OAuth refresh internal error is localized"""
        client, _ = authenticated_client
        mock_refresh.side_effect = RuntimeError("refresh boom")

        refresh_data = {"refreshToken": "old_refresh_token_456"}

        en_response = client.post("/api/v1/oauth/refresh", json=refresh_data)
        assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert en_response.json()["detail"] == "Failed to refresh OAuth token"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        zh_response = client.post("/api/v1/oauth/refresh", json=refresh_data)
        assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert zh_response.json()["detail"] == "更新 OAuth Token 失敗"
