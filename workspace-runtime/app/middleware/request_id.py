"""
Request ID middleware
"""

import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID middleware"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add unique ID to each request"""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response