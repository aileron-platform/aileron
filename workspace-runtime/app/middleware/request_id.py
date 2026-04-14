"""
請求 ID 中介軟體
"""

import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """請求 ID 中介軟體"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """為每個請求添加唯一 ID"""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response