"""Tests for error handler middleware"""
from unittest.mock import Mock, AsyncMock
import pytest
from fastapi import Request
from fastapi.responses import Response, JSONResponse

from app.middleware.error_handler import ErrorHandlerMiddleware


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware"""

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        """Test dispatch returns response on success"""
        middleware = ErrorHandlerMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_response = Mock(spec=Response)

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_handles_exception(self):
        """Test dispatch handles exception and returns error response"""
        middleware = ErrorHandlerMiddleware(app=Mock())

        mock_request = Mock(spec=Request)

        async def call_next(request):
            raise ValueError("Test error")

        result = await middleware.dispatch(mock_request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_dispatch_logs_error(self):
        """Test dispatch logs error on exception"""
        from unittest.mock import patch

        middleware = ErrorHandlerMiddleware(app=Mock())

        mock_request = Mock(spec=Request)

        async def call_next(request):
            raise RuntimeError("Critical error")

        with patch('app.middleware.error_handler.logger') as mock_logger:
            result = await middleware.dispatch(mock_request, call_next)

            mock_logger.error.assert_called_once()
            assert "未處理的錯誤" in str(mock_logger.error.call_args)
