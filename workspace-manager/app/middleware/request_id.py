"""Correlation ID middleware."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

CORRELATION_ID_HEADER = "X-Correlation-ID"


def _resolve_correlation_id(raw_value: str | None) -> str:
    if raw_value:
        try:
            return str(UUID(raw_value))
        except (ValueError, AttributeError):
            pass
    return str(uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a valid correlation ID to request state and response headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = _resolve_correlation_id(
            request.headers.get(CORRELATION_ID_HEADER)
        )
        request.state.correlation_id = correlation_id
        request.state.request_id = correlation_id

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
