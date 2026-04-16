"""
JWT 認證中間件的單元測試
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
    """JWTAuthenticationMiddleware 類的單元測試"""

    @pytest.fixture
    def mock_app(self):
        """模擬 FastAPI 應用"""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """創建中間件實例"""
        return JWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

    def test_initialization(self, middleware):
        """測試中間件初始化"""
        assert middleware.config is not None
        assert "/test-public" in middleware.exclude_paths
        assert "/health" in middleware.exclude_paths  # 默認排除
        assert "/public/*" in middleware.exclude_patterns

    def test_is_excluded_path_exact_match(self, middleware):
        """測試路徑排除（完全匹配）"""
        assert middleware._is_excluded_path("/test-public") is True
        assert middleware._is_excluded_path("/health") is True

    def test_is_excluded_path_pattern_match(self, middleware):
        """測試路徑排除（模式匹配）"""
        assert middleware._is_excluded_path("/public/resource") is True
        assert middleware._is_excluded_path("/public/api/data") is True

    def test_is_excluded_path_no_match(self, middleware):
        """測試路徑排除（無匹配）"""
        assert middleware._is_excluded_path("/api/workspaces") is False
        assert middleware._is_excluded_path("/protected/data") is False

    def test_extract_bearer_token_valid(self, middleware):
        """測試提取有效的 Bearer token"""
        # 創建模擬請求
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer test-token-12345"}

        token = middleware._extract_bearer_token(request)
        assert token == "test-token-12345"

    def test_extract_bearer_token_missing_header(self, middleware):
        """測試缺少 Authorization header"""
        request = Mock(spec=Request)
        request.headers = {}

        token = middleware._extract_bearer_token(request)
        assert token is None

    def test_extract_bearer_token_invalid_format(self, middleware):
        """測試無效的 Authorization header 格式"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "InvalidFormat token"}

        token = middleware._extract_bearer_token(request)
        assert token is None

    def test_extract_bearer_token_empty(self, middleware):
        """測試空的 Bearer token"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer   "}

        token = middleware._extract_bearer_token(request)
        assert token is None

    @pytest.mark.asyncio
    async def test_dispatch_auth_disabled(self, middleware, request_factory):
        """測試認證未啟用時的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            middleware.config = mock_config.return_value

            # 創建模擬請求和響應
            request = request_factory("/api/test")

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證
            assert request.state.auth_enabled is False
            assert request.state.current_user is None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path(self, middleware, request_factory):
        """測試排除路徑的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 創建模擬請求（排除路徑）
            request = request_factory("/test-public")

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證
            assert request.state.auth_enabled is True
            assert request.state.auth_exempt is True
            assert request.state.current_user is None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_no_token(self, middleware, request_factory):
        """測試沒有提供 token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 創建模擬請求（無 token）
            request = request_factory("/api/workspaces", {})

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證
            assert request.state.auth_enabled is True
            assert request.state.current_user is None
            assert request.state.auth_valid is False
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_internal_token(self, middleware, request_factory):
        """測試有效 internal token 可作為內部服務認證。"""
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
        """測試有效 token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt, \
             patch("app.modules.auth.middleware._ensure_local_user", new_callable=AsyncMock) as mock_ensure_local_user:

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT 驗證成功
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(return_value={
                "sub": "user-123",
                "username": "testuser",
                "email": "test@example.com",
                "roles": ["user"],
            })
            mock_jwt.return_value = mock_jwt_utils
            mock_ensure_local_user.return_value = "local-user-123"

            # 創建模擬請求（有效 token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer valid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證
            assert request.state.auth_enabled is True
            assert request.state.current_user is not None
            assert request.state.current_user["sub"] == "user-123"
            assert request.state.auth_valid is True
            assert request.state.user_id == "local-user-123"
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_invalid_token(self, middleware, request_factory):
        """測試無效 token 的行為"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            from app.modules.auth.jwt_utils import JWTValidationError

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT 驗證失敗
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(
                side_effect=JWTValidationError("Invalid token")
            )
            mock_jwt.return_value = mock_jwt_utils

            # 創建模擬請求（無效 token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer invalid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證
            assert request.state.auth_enabled is True
            assert request.state.current_user is None
            assert request.state.auth_valid is False
            assert request.state.auth_error == "Invalid token"
            call_next.assert_called_once_with(request)


class TestStrictJWTAuthenticationMiddleware:
    """StrictJWTAuthenticationMiddleware 類的單元測試"""

    @pytest.fixture
    def mock_app(self):
        """模擬 FastAPI 應用"""
        return Mock()

    @pytest.fixture
    def middleware(self, mock_app):
        """創建嚴格模式中間件實例"""
        return StrictJWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
        )

    @pytest.mark.asyncio
    async def test_dispatch_no_token_returns_401(self, middleware, request_factory):
        """測試沒有 token 時返回 401 錯誤"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 創建模擬請求（無 token）
            request = request_factory("/api/workspaces", {})

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證返回 401 錯誤
            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_invalid_token_returns_401(self, middleware, request_factory):
        """測試無效 token 時返回 401 錯誤"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            from app.modules.auth.jwt_utils import JWTValidationError

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT 驗證失敗
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(
                side_effect=JWTValidationError("Token expired")
            )
            mock_jwt.return_value = mock_jwt_utils

            # 創建模擬請求（無效 token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer expired-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證返回 401 錯誤
            assert isinstance(response, JSONResponse)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_valid_token_continues(self, middleware, request_factory):
        """測試有效 token 時繼續處理請求"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config, \
             patch("app.modules.auth.middleware.get_jwt_utils") as mock_jwt:

            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 模擬 JWT 驗證成功
            mock_jwt_utils = Mock()
            mock_jwt_utils.decode_token_async = AsyncMock(return_value={
                "sub": "user-123",
                "username": "testuser",
            })
            mock_jwt.return_value = mock_jwt_utils

            # 創建模擬請求（有效 token）
            request = request_factory(
                "/api/workspaces", {"Authorization": "Bearer valid-token"}
            )

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證繼續處理
            assert request.state.auth_valid is True
            assert request.state.current_user is not None
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path_no_auth_required(self, middleware, request_factory):
        """測試排除路徑不需要認證"""
        with patch("app.modules.auth.middleware.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True)
            middleware.config = mock_config.return_value

            # 創建模擬請求（排除路徑，無 token）
            request = request_factory("/test-public", {})

            call_next = AsyncMock(return_value=Mock())

            # 執行中間件
            response = await middleware.dispatch(request, call_next)

            # 驗證繼續處理（不返回 401）
            assert request.state.auth_exempt is True
            call_next.assert_called_once_with(request)
