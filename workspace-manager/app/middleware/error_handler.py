"""錯誤處理中間件"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """錯誤處理中間件"""

    async def dispatch(self, request: Request, call_next):
        # 錯誤處理中間件
        response = await call_next(request)
        return response