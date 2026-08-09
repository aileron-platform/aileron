"""
Error handling middleware
"""

import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


def internal_error_content(request: Request) -> dict[str, Any]:
    """Build a localized error envelope without exposing exception details."""

    content: dict[str, Any] = {
        "errorCode": "INTERNAL_SERVER_ERROR",
        "requestId": getattr(request.state, "request_id", None),
    }
    translate = getattr(request.state, "translate", None)
    if callable(translate):
        content["message"] = translate("errors.internal_server")
    return content


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Error handling middleware"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and catch errors"""
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(
                "Unhandled runtime request error: type=%s path=%s request_id=%s",
                type(exc).__name__,
                request.url.path,
                getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=500,
                content=internal_error_content(request),
            )


__all__ = ["ErrorHandlerMiddleware", "internal_error_content"]
