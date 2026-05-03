"""Unit tests for GeminiOAuthService."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.gemini_oauth_service import GeminiOAuthService, GeminiTokenResult, GeminiUserInfo


@pytest.mark.unit
@pytest.mark.auth
class TestGeminiOAuthService:
    """Gemini OAuth service tests."""

    @pytest.mark.asyncio
    async def test_exchange_code_uses_settings_credentials(self, monkeypatch: pytest.MonkeyPatch):
        """Exchange code should use OAuth settings values."""
        monkeypatch.setattr(
            "app.services.gemini_oauth_service.get_settings",
            lambda: SimpleNamespace(
                GEMINI_GOOGLE_CLIENT_ID="google-client-id",
                GEMINI_GOOGLE_CLIENT_SECRET="google-client-secret",
                GEMINI_GOOGLE_REDIRECT_URI="https://example.com/oauth/callback",
            ),
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": "id-token",
            "expires_in": 1800,
            "scope": "openid email",
            "token_type": "Bearer",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            before_ms = int(time.time() * 1000)
            result = await GeminiOAuthService.exchange_code("auth-code", "pkce-verifier")

        assert isinstance(result, GeminiTokenResult)
        assert result.access_token == "access-token"
        assert result.refresh_token == "refresh-token"
        assert result.id_token == "id-token"
        assert result.scope == "openid email"
        assert result.token_type == "Bearer"
        assert before_ms + 1800 * 1000 - 5000 <= result.expires_at <= before_ms + 1800 * 1000 + 5000

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://oauth2.googleapis.com/token"
        assert call_args[1]["data"] == {
            "code": "auth-code",
            "client_id": "google-client-id",
            "client_secret": "google-client-secret",
            "redirect_uri": "https://example.com/oauth/callback",
            "grant_type": "authorization_code",
            "code_verifier": "pkce-verifier",
        }

    def test_exchange_code_requires_google_oauth_credentials(self, monkeypatch: pytest.MonkeyPatch):
        """Exchange code should fail when credentials are missing."""
        monkeypatch.setattr(
            "app.services.gemini_oauth_service.get_settings",
            lambda: SimpleNamespace(
                GEMINI_GOOGLE_CLIENT_ID="",
                GEMINI_GOOGLE_CLIENT_SECRET="",
                GEMINI_GOOGLE_REDIRECT_URI="https://example.com/oauth/callback",
            ),
        )

        with pytest.raises(ValueError, match="credentials are not configured"):
            GeminiOAuthService._get_google_oauth_config()

    @pytest.mark.asyncio
    async def test_get_userinfo_returns_email_and_name(self):
        """Get userinfo should map response fields."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"email": "user@example.com", "name": "Gemini User"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await GeminiOAuthService.get_userinfo("access-token")

        assert isinstance(result, GeminiUserInfo)
        assert result.email == "user@example.com"
        assert result.name == "Gemini User"
