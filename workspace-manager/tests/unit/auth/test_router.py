"""OAuth2 auth router UnitTest"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse

from app.modules.auth.router import (
    CallbackRequest,
    LoginURLResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserInfo,
    callback,
    get_auth_config,
    get_current_user,
    login,
    login_redirect,
    logout,
    refresh_token,
    require_auth_enabled,
)
from app.modules.auth.jwt_utils import JWTValidationError


class TestAuthRouterHelpers:
    @pytest.mark.asyncio
    async def test_require_auth_enabled_raises_when_disabled(self):
        with patch("app.modules.auth.router.get_keycloak_config", return_value=Mock(enabled=False)):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth_enabled()

        assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED


class TestAuthRouterEndpoints:
    @pytest.fixture
    def config(self):
        return Mock(
            enabled=True,
            server_url="http://keycloak.internal:8080/realms/test",
            external_server_url="https://keycloak.example.com/realms/test",
            client_id="client-id",
            client_secret="secret",
            jwt_access_token_expire_minutes=30,
        )

    @pytest.mark.asyncio
    async def test_login_uses_referer_when_redirect_uri_missing(self, request_factory, config):
        request = request_factory(
            "/oauth2/login",
            {"referer": "https://frontend.example.com/workspaces/123"},
        )

        with patch("secrets.token_urlsafe", return_value="state-123"):
            response = await login(request, None, config)

        assert isinstance(response, LoginURLResponse)
        assert response.state == "state-123"
        assert "redirect_uri=https://frontend.example.com/" in response.authorization_url
        assert response.authorization_url.startswith(
            "https://keycloak.example.com/realms/test/protocol/openid-connect/auth"
        )

    @pytest.mark.asyncio
    async def test_login_falls_back_to_default_redirect(self, request_factory, config):
        request = request_factory("/oauth2/login")

        with patch("secrets.token_urlsafe", return_value="state-456"):
            response = await login(request, None, config)

        assert "redirect_uri=http://localhost:8082/" in response.authorization_url

    @pytest.mark.asyncio
    async def test_login_redirect_returns_302(self, request_factory, config):
        request = request_factory("/oauth2/login/redirect")

        with patch("secrets.token_urlsafe", return_value="state-789"):
            response = await login_redirect(request, "https://frontend.example.com/callback", config)

        assert isinstance(response, RedirectResponse)
        assert response.status_code == status.HTTP_302_FOUND
        assert "state=state-789" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_raises_on_oauth_error(self, request_factory, config):
        request = request_factory("/oauth2/callback")

        with pytest.raises(HTTPException) as exc_info:
            await callback(request, "code", error="access_denied", error_description="Denied", config=config)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_for_token(self, request_factory, config, httpx_response_factory):
        request = request_factory("/oauth2/callback")
        request.url_for = Mock(return_value="https://api.example.com/oauth2/callback")
        token_payload = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid profile email",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=httpx_response_factory(json_data=token_payload))
            mock_client_class.return_value = mock_client

            response = await callback(request, "oauth-code", config=config)

        assert isinstance(response, TokenResponse)
        assert response.access_token == "access-token"
        assert response.refresh_token == "refresh-token"
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_callback_wraps_http_error(self, request_factory, config):
        request = request_factory("/oauth2/callback")
        request.url_for = Mock(return_value="https://api.example.com/oauth2/callback")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await callback(request, "oauth-code", config=config)

        assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, config, httpx_response_factory):
        request = RefreshTokenRequest(refresh_token="refresh-token")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value=httpx_response_factory(
                    json_data={
                        "access_token": "new-access",
                        "token_type": "Bearer",
                    }
                )
            )
            mock_client_class.return_value = mock_client

            response = await refresh_token(request, config)

        assert response.access_token == "new-access"
        assert response.refresh_token == "refresh-token"
        assert response.expires_in == 1800

    @pytest.mark.asyncio
    async def test_refresh_token_wraps_http_error(self, config):
        request = RefreshTokenRequest(refresh_token="refresh-token")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.HTTPError("bad refresh"))
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(request, config)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_logout_is_placeholder(self, request_factory, config):
        request = request_factory("/oauth2/logout")
        assert await logout(request, config) == {"message": "Logout endpoint - implementation pending"}

    @pytest.mark.asyncio
    async def test_get_current_user_requires_bearer_header(self, request_factory, config):
        request = request_factory("/oauth2/me")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request, config)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_returns_user_info_and_local_user_id(self, request_factory, config):
        request = request_factory("/oauth2/me", {"Authorization": "Bearer access-token"})
        payload = {
            "sub": "keycloak-user-1",
            "preferred_username": "tester",
            "email": "tester@example.com",
            "given_name": "Test",
            "family_name": "User",
            "realm_access": {"roles": ["admin", "user"]},
        }

        with patch("app.modules.auth.router.get_jwt_utils") as mock_get_jwt_utils, \
             patch("app.db.database.SessionLocal") as mock_session_local, \
             patch("app.services.user_service.UserService") as mock_user_service:
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token.return_value = payload
            mock_get_jwt_utils.return_value = mock_jwt_utils

            db = Mock()
            mock_session_local.return_value = db
            user_service = Mock()
            user_service.get_by_keycloak_id.return_value = Mock(id="local-user-1")
            mock_user_service.return_value = user_service

            response = await get_current_user(request, config)

        assert isinstance(response, UserInfo)
        assert response.sub == "keycloak-user-1"
        assert response.roles == ["admin", "user"]
        assert response.local_user_id == "local-user-1"
        db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_user_tolerates_local_db_errors(self, request_factory, config):
        request = request_factory("/oauth2/me", {"Authorization": "Bearer access-token"})
        payload = {
            "sub": "keycloak-user-1",
            "preferred_username": "tester",
            "realm_access": {"roles": ["user"]},
        }

        with patch("app.modules.auth.router.get_jwt_utils") as mock_get_jwt_utils, \
             patch("app.db.database.SessionLocal", side_effect=RuntimeError("db down")):
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token.return_value = payload
            mock_get_jwt_utils.return_value = mock_jwt_utils

            response = await get_current_user(request, config)

        assert response.local_user_id is None

    @pytest.mark.asyncio
    async def test_get_current_user_wraps_validation_error(self, request_factory, config):
        request = request_factory("/oauth2/me", {"Authorization": "Bearer access-token"})

        with patch("app.modules.auth.router.get_jwt_utils") as mock_get_jwt_utils:
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token.side_effect = JWTValidationError("bad token")
            mock_get_jwt_utils.return_value = mock_jwt_utils

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, config)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_auth_config_returns_public_settings(self, config):
        enabled_response = await get_auth_config(config)
        assert enabled_response["enabled"] is True
        assert enabled_response["authority"] == "https://keycloak.example.com/realms/test"
        assert enabled_response["clientId"] == "client-id"

        disabled_response = await get_auth_config(Mock(enabled=False))
        assert disabled_response == {"enabled": False}
