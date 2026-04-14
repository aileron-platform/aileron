"""請求 ID 中間件"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """請求 ID 中間件"""

    async def dispatch(self, request: Request, call_next):
        # 請求 ID 中間件
        response = await call_next(request)
        return response