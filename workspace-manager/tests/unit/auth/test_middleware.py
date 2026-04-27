"""
JWT AuthenticationMiddleware的UnitTest
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, status
from starlette.responses import JSONResponse

from app.modules.auth.middleware import (
    JWTAuthenticationMiddleware,
    StrictJWTAuthenticationMiddleware,
)


class TestJWTAuthenticationMiddleware:
    """JWTAuthenticationMiddleware 類的UnitTest"""

    @pytest.fixture
    def mock_app(self):
        """模擬 FastAPI Application"""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """CreateMiddlewareInstance"""
        return JWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

    def test_initialization(self, middleware):
        """TestMiddlewareInitialize"""
        assert middleware.config is not None
        assert "/test-public" in middleware.exclude_paths
        assert "/health" in middleware.exclude_paths  # 默認Arranging除
        assert "/public/*" in middleware.exclude_patterns

    def test_is_excluded_path_exact_match(self, middleware):
        """TestRoad徑Arranging除（完全匹配）"""
        assert middleware._is_excluded_path("/test-public") is True
        assert middleware._is_excluded_path("/health") is True

    def test_is_excluded_path_pattern_match(self, middleware):
        """TestRoad徑Arranging除（Pattern匹配）"""
        assert middleware._is_excluded_path("/public/resource") is True
        assert middleware._is_excluded_path("/public/api/data") is True

    def test_is_excluded_path_no_match(self, middleware):
        """TestRoad徑Arranging除（無匹配）"""
        assert middleware._is_excluded_path("/api/workspaces") is False
        assert middleware._is_excluded_path("/protected/data") is False

    def test_extract_bearer_token_valid(self, middleware):
        """TestExtractValid的 Bearer token"""
        # Create模擬Request
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test-token-12345"}

        token = middleware._extract_bearer_token(request)
        assert token == "test-token-12345"

    def test_extract_bearer_token_missing_header(self, middleware):
        """Test缺Less Authorization header"""
        request = Mock(spec=Request)
        request.headers = {}

        token = middleware._extract_bearer_token(request)
        assert token is None

    def test_extract_bearer_token_invalid_format(self, middleware):
        """TestInvalid的 Authorization header Format"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "InvalidFormat token"}

        token = middleware._extract_bearer_token(request)
        assert token is None

    def test_extract_bearer_token_empty(self, middleware):
        """Test空的 Bearer token"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer   "}

        token = middleware._extract_bearer_token(request)
        assert token is None

    @pytest.mark.asyncio
    async def test_dispatch_auth_disabled(self, middleware, request_factory):
        """TestAuthentication未Enabled時的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            middleware.config = mock_config.return_value

            # Create模擬Request和Response
            request = request_factory("/api/test")

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # Verify
            assert request.state.auth_enabled is False
            assert request.state.current_user is None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path(self, middleware, request_factory):
        """TestArranging除Road徑的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # Create模擬Request（Arranging除Road徑）
            request = request_factory("/test-public")

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # Verify
            assert request.state.auth_enabled is True
            assert request.state.auth_exempt is True
            assert request.state.current_user is None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_no_token(self, middleware, request_factory):
        """TestNoneProvide token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # Create模擬Request（無 token）
            request = request_factory("/api/workspaces", {})

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # Verify
            assert request.state.auth_enabled is True
            assert request.state.current_user is None
            assert request.state.auth_valid is False
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_internal_token(self, middleware, request_factory):
        """TestValid internal token 可作為Within部ServiceAuthentication。"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            request = request_factory(
                "/api/workspaces",
                {"X-Internal-Token": "test-internal-token"},
            )

            call_next = AsyncMock(return_value=Mock())

            response = await middleware.dispatch(request, call_next)

            assert request.state.auth_enabled is True
            assert request.state.auth_valid is True
            assert request.state.auth_exempt is True
            assert request.state.internal_authenticated is True
            assert request.state.user_id is None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_valid_token(self, middleware, request_factory):
        """TestValid token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt, \
             patch("app.modules.auth.middleware._ensure_local_user", new_callable=AsyncMock) as mock_ensure_local_user:

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT VerifySuccess
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(return_value={
                "sub": "user-123",
                "username": "testuser",
                "email": "test@example.com",
                "roles": ["user"],
            })
            mock_jwt.return_value = mock_jwt_utils
            mock_ensure_local_user.return_value = "local-user-123"

            # Create模擬Request（Valid token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer valid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # Verify
            assert request.state.auth_enabled is True
            assert request.state.current_user is not None
            assert request.state.current_user["sub"] == "user-123"
            assert request.state.auth_valid is True
            assert request.state.user_id == "local-user-123"
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_invalid_token(self, middleware, request_factory):
        """TestInvalid token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            from app.modules.auth.jwt_utils import JWTValidationError

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT VerifyFailed
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(
                side_effect=JWTValidationError("Invalid token")
            )
            mock_jwt.return_value = mock_jwt_utils

            # Create模擬Request（Invalid token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer invalid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # Verify
            assert request.state.auth_enabled is True
            assert request.state.current_user is None
            assert request.state.auth_valid is False
            assert request.state.auth_error == "Invalid token"
            call_next.assert_called_once_with(request)


class TestStrictJWTAuthenticationMiddleware:
    """StrictJWTAuthenticationMiddleware 類的UnitTest"""

    @pytest.fixture
    def mock_app(self):
        """模擬 FastAPI Application"""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """CreateStrictPatternMiddlewareInstance"""
        return StrictJWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
        )

    @pytest.mark.asyncio
    async def test_dispatch_no_token_returns_401(self, middleware, request_factory):
        """TestNone token 時Return 401 Error"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # Create模擬Request（無 token）
            request = request_factory("/api/workspaces", {})

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # VerifyReturn 401 Error
            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_invalid_token_returns_401(self, middleware, request_factory):
        """TestInvalid token 時Return 401 Error"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            from app.modules.auth.jwt_utils import JWTValidationError

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT VerifyFailed
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(
                side_effect=JWTValidationError("Token expired")
            )
            mock_jwt.return_value = mock_jwt_utils

            # Create模擬Request（Invalid token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer expired-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # VerifyReturn 401 Error
            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_valid_token_continues(self, middleware, request_factory):
        """TestValid token 時ContinueHandleRequest"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT VerifySuccess
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(return_value={
                "sub": "user-123",
                "username": "testuser",
            })
            mock_jwt.return_value = mock_jwt_utils

            # Create模擬Request（Valid token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer valid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # VerifyContinueHandle
            assert request.state.auth_valid is True
            assert request.state.current_user is not None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path_no_auth_required(self, middleware, request_factory):
        """TestArranging除Road徑不NeedingAuthentication"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # Create模擬Request（Arranging除Road徑，無 token）
            request = request_factory("/test-public", {})

            call_next = AsyncMock(return_value=Mock())

            # ExecuteMiddleware
            response = await middleware.dispatch(request, call_next)

            # VerifyContinueHandle（不Return 401）
            assert request.state.auth_exempt is True
            call_next.assert_called_once_with(request)
