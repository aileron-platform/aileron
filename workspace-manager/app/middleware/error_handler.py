"""Error handling middleware"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Error handling middleware"""

    async def dispatch(self, request: Request, call_next):
        # Error handling middleware
        response = await call_next(request)
        return response