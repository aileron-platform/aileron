"""
錯誤處理中介軟體
"""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """錯誤處理中介軟體"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """處理請求並捕獲錯誤"""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"未處理的錯誤: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": "內部伺服器錯誤", "detail": str(e)}
            )