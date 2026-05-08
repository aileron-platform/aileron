"""Role and Permission Decorator Unit Test"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Request, status

from app.modules.auth.auth_decorators import (
    PermissionDeniedError,
    get_current_user,
    get_current_user_id,
    get_optional_current_user,
    get_user_permissions,
    has_all_permissions,
    has_any_permission,
    has_any_role,
    has_permission,
    has_role,
    load_role_mapping,
    require_all_permissions,
    require_any_permission,
    require_any_role,
    require_authenticated_user,
    require_permission,
    require_role,
)
from app.modules.auth.jwt_utils import JWTValidationError


class TestRoleMappingHelpers:
    def test_load_role_mapping_returns_empty_when_file_missing(self):
        with patch("pathlib.Path.exists", return_value=False):
            assert load_role_mapping() == {}

    def test_get_user_permissions_supports_inheritance(self):
        role_mapping = {
            "role_mappings": {
                "viewer": {"permissions": ["workspace:read"]},
                "editor": {"permissions": ["workspace:update"]},
                "admin": {"permissions": ["workspace:delete"]},
            },
            "role_inheritance": {
                "admin": {"inherits": ["editor", "viewer"]},
                "editor": {"inherits": ["viewer"]},
            },
        }

        with patch(
            "app.modules.auth.auth_decorators.load_role_mapping",
            return_value=role_mapping,
        ):
            permissions = get_user_permissions(["admin", "admin"])

        assert set(permissions) == {
            "workspace:read",
            "workspace:update",
            "workspace:delete",
        }

    def test_permission_and_role_helpers(self):
        assert has_permission("workspace:read", ["workspace:read", "workspace:update"]) is True
        assert has_permission("workspace:delete", ["workspace:all"]) is True
        assert has_permission("marketplace:manage_registry", ["*:all"]) is True
        assert has_permission("workspace:delete", ["workspace:read"]) is False
        assert has_role("admin", ["admin", "user"]) is True
        assert has_role("admin", ["user"]) is False
        assert has_any_role(["admin", "editor"], ["viewer", "editor"]) is True
        assert has_any_role(["admin"], ["viewer", "editor"]) is False
        assert has_all_permissions(["a", "b"], ["a", "b", "c"]) is True
        assert has_all_permissions(["workspace:read", "workspace:delete"], ["workspace:all"]) is True
        assert has_all_permissions(["a", "b"], ["a"]) is False
        assert has_any_permission(["a", "b"], ["c", "b"]) is True
        assert has_any_permission(["marketplace:delete", "marketplace:install"], ["marketplace:all"]) is True
        assert has_any_permission(["a", "b"], ["c"]) is False


class TestCurrentUserDependencies:
    @pytest.mark.asyncio
    async def test_get_current_user_returns_empty_when_auth_disabled(self, request_factory):
        request = request_factory("/api/test")
        config = Mock(enabled=False)

        assert await get_current_user(request, config) == {}

    @pytest.mark.asyncio
    async def test_get_current_user_requires_bearer_header(self, request_factory):
        request = request_factory("/api/test", {})
        config = Mock(enabled=True)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request, config)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.asyncio
    async def test_get_current_user_decodes_token(self, request_factory):
        request = request_factory("/api/test", {"Authorization": "Bearer token-123"})
        config = Mock(enabled=True)

        with patch("app.modules.auth.auth_decorators.get_jwt_utils") as mock_get_jwt_utils:
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token.return_value = {"sub": "user-1", "roles": ["admin"]}
            mock_get_jwt_utils.return_value = mock_jwt_utils

            payload = await get_current_user(request, config)

        assert payload["sub"] == "user-1"
        mock_jwt_utils.decode_token.assert_called_once_with("token-123")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token_raises_401(self, request_factory):
        request = request_factory("/api/test", {"Authorization": "Bearer token-123"})
        config = Mock(enabled=True)

        with patch("app.modules.auth.auth_decorators.get_jwt_utils") as mock_get_jwt_utils:
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token.side_effect = JWTValidationError("bad token")
            mock_get_jwt_utils.return_value = mock_jwt_utils

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(request, config)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token: bad token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_optional_current_user_returns_none_on_http_exception(self, request_factory):
        request = request_factory("/api/test", {})
        config = Mock(enabled=True)

        assert await get_optional_current_user(request, config) is None

    @pytest.mark.asyncio
    async def test_require_authenticated_user_handles_disabled_and_missing_sub(self):
        disabled_config = Mock(enabled=False)
        with pytest.raises(HTTPException) as disabled_exc:
            await require_authenticated_user({}, disabled_config)
        assert disabled_exc.value.status_code == status.HTTP_501_NOT_IMPLEMENTED

        enabled_config = Mock(enabled=True)
        with pytest.raises(HTTPException) as missing_sub_exc:
            await require_authenticated_user({}, enabled_config)
        assert missing_sub_exc.value.status_code == status.HTTP_401_UNAUTHORIZED

        current_user = {"sub": "user-1", "roles": ["user"]}
        assert await require_authenticated_user(current_user, enabled_config) == current_user


class TestDecoratorFactories:
    @pytest.mark.asyncio
    async def test_require_role_success_and_failure(self):
        @require_role("admin")
        async def protected_endpoint(*, current_user):
            return current_user["sub"]

        assert await protected_endpoint(current_user={"sub": "user-1", "roles": ["admin"]}) == "user-1"

        with pytest.raises(PermissionDeniedError) as exc_info:
            await protected_endpoint(current_user={"sub": "user-2", "roles": ["user"]})
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_require_any_role_and_permission_variants(self):
        @require_any_role("admin", "editor")
        async def any_role_endpoint(*, current_user):
            return "ok"

        @require_permission("workspace:create")
        async def permission_endpoint(*, current_user):
            return "ok"

        @require_any_permission("workspace:create", "workspace:update")
        async def any_permission_endpoint(*, current_user):
            return "ok"

        @require_all_permissions("workspace:create", "workspace:update")
        async def all_permissions_endpoint(*, current_user):
            return "ok"

        role_mapping = {
            "role_mappings": {
                "admin": {"permissions": ["workspace:create", "workspace:update"]},
                "editor": {"permissions": ["workspace:update"]},
            }
        }

        with patch(
            "app.modules.auth.auth_decorators.load_role_mapping",
            return_value=role_mapping,
        ):
            assert await any_role_endpoint(current_user={"roles": ["editor"]}) == "ok"
            assert await permission_endpoint(current_user={"roles": ["admin"]}) == "ok"
            assert await any_permission_endpoint(current_user={"roles": ["editor"]}) == "ok"
            assert await all_permissions_endpoint(current_user={"roles": ["admin"]}) == "ok"

            with pytest.raises(PermissionDeniedError):
                await any_role_endpoint(current_user={"roles": ["viewer"]})
            with pytest.raises(PermissionDeniedError):
                await permission_endpoint(current_user={"roles": ["viewer"]})
            with pytest.raises(PermissionDeniedError):
                await any_permission_endpoint(current_user={"roles": ["viewer"]})
            with pytest.raises(PermissionDeniedError):
                await all_permissions_endpoint(current_user={"roles": ["editor"]})

    def test_get_current_user_id_reads_request_state(self):
        request = Mock(spec=Request)
        request.state = SimpleNamespace(user_id="local-user-1")
        assert get_current_user_id(request) == "local-user-1"

        request_without_user = Mock(spec=Request)
        request_without_user.state = SimpleNamespace()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(request_without_user)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
