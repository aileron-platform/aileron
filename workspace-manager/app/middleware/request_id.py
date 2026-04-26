"""Request ID middleware"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID middleware"""

    async def dispatch(self, request: Request, call_next):
        # Request ID middleware
        response = await call_next(request)
        return response