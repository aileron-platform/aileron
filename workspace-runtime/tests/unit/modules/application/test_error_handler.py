"""Tests for error handler middleware"""

import json
from unittest.mock import Mock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse, Response

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
        mock_request.url.path = "/api/v1/test"
        mock_request.state.request_id = "request-1"
        mock_request.state.translate = lambda key: {
            "errors.internal_server": "Localized internal error"
        }[key]

        async def call_next(request):
            raise ValueError("Test error")

        result = await middleware.dispatch(mock_request, call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500
        assert json.loads(result.body) == {
            "errorCode": "INTERNAL_SERVER_ERROR",
            "requestId": "request-1",
            "message": "Localized internal error",
        }
        assert b"Test error" not in result.body

    @pytest.mark.asyncio
    async def test_dispatch_logs_error(self):
        """Test dispatch logs error on exception"""
        from unittest.mock import patch

        middleware = ErrorHandlerMiddleware(app=Mock())

        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/v1/test"
        mock_request.state.request_id = "request-2"
        mock_request.state.translate = None

        async def call_next(request):
            raise RuntimeError("Critical error")

        with patch("app.middleware.error_handler.logger") as mock_logger:
            await middleware.dispatch(mock_request, call_next)

            mock_logger.error.assert_called_once()
            logged_call = str(mock_logger.error.call_args)
            assert "Unhandled runtime request error" in logged_call
            assert "RuntimeError" in logged_call
            assert "Critical error" not in logged_call
