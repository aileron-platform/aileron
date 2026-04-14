"""Keycloak profile sync 單元測試"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.modules.auth.keycloak_profile_sync import (
    KeycloakProfileSync,
    get_keycloak_profile_sync,
)


class TestKeycloakProfileSync:
    @pytest.fixture
    def service(self):
        sync = KeycloakProfileSync()
        sync.config = Mock(enabled=True, server_url="https://keycloak.example.com/realms/test")
        return sync

    def test_get_keycloak_profile_sync_singleton(self):
        assert get_keycloak_profile_sync() is get_keycloak_profile_sync()

    @pytest.mark.asyncio
    async def test_sync_profile_skips_when_auth_disabled(self, service):
        service.config.enabled = False
        assert await service.sync_profile_to_keycloak("token", first_name="A") is True

    @pytest.mark.asyncio
    async def test_sync_profile_returns_true_when_no_payload(self, service):
        assert await service.sync_profile_to_keycloak("token") is True

    @pytest.mark.asyncio
    async def test_sync_profile_merges_existing_profile(self, service, httpx_response_factory):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                return_value=Mock(
                    is_success=True,
                    json=Mock(return_value={"email": "user@example.com", "attributes": {"lang": ["zh-TW"]}}),
                    status_code=200,
                )
            )
            mock_client.post = AsyncMock(return_value=Mock(is_success=True, status_code=204, text=""))
            mock_client_class.return_value = mock_client

            result = await service.sync_profile_to_keycloak("token", first_name="New", last_name="Name")

        assert result is True
        _, kwargs = mock_client.post.await_args
        assert kwargs["json"]["firstName"] == "New"
        assert kwargs["json"]["lastName"] == "Name"
        assert kwargs["json"]["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_sync_profile_continues_when_get_profile_fails(self, service):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=Mock(is_success=False, status_code=500))
            mock_client.post = AsyncMock(return_value=Mock(is_success=True, status_code=200, text=""))
            mock_client_class.return_value = mock_client

            result = await service.sync_profile_to_keycloak("token", first_name="Only")

        assert result is True
        _, kwargs = mock_client.post.await_args
        assert kwargs["json"] == {"firstName": "Only"}

    @pytest.mark.asyncio
    async def test_sync_profile_returns_false_on_post_failure(self, service):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=Mock(is_success=True, json=Mock(return_value={}), status_code=200))
            mock_client.post = AsyncMock(return_value=Mock(is_success=False, status_code=400, text="bad request"))
            mock_client_class.return_value = mock_client

            result = await service.sync_profile_to_keycloak("token", first_name="Bad")

        assert result is False

    @pytest.mark.asyncio
    async def test_sync_profile_returns_false_on_httpx_error(self, service):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
            mock_client_class.return_value = mock_client

            result = await service.sync_profile_to_keycloak("token", first_name="Err")

        assert result is False

    @pytest.mark.asyncio
    async def test_sync_profile_returns_false_on_unexpected_error(self, service):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected"))
            mock_client_class.return_value = mock_client

            result = await service.sync_profile_to_keycloak("token", first_name="Err")

        assert result is False
