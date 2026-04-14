"""認證中間件"""

import logging
import os
from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import get_auth_service
from app.utils.datetime_utils import utcnow

# 從環境變數讀取內部 API token（僅用於開發/測試環境）
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN")

logger = logging.getLogger(__name__)


def get_current_user_id(request: Request) -> str:
    """
    從請求中取得當前用戶 ID

    這個函數用於 FastAPI 的 Depends 依賴注入

    Args:
        request: FastAPI Request 物件

    Returns:
        str: 用戶 ID

    Raises:
        HTTPException: 當用戶未認證時
    """
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: User not authenticated",
        )
    return request.state.user_id


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Token 驗證中間件"""

    PUBLIC_PATHS = {
        "/",
        "/favicon.ico",
    }
    PUBLIC_PREFIXES = (
        "/docs",
        "/openapi",
        "/redoc",
        "/health",
        "/static",
        "/api/v1/client-browser-relay",  # dev-browser client relay API (無需 token 驗證)
        "/api/v1/oauth2",  # Keycloak OAuth2 endpoints (handled by JWT middleware in workspace-manager)
    )
    INTERNAL_API_PREFIXES = (
        "/api/v1/internal/",  # 內部 API 使用不同的認證機制
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        normalized_path = path.rstrip("/") or "/"

        # 跳過公開路徑和 OPTIONS 請求
        if request.method == "OPTIONS" or self._is_public(path, normalized_path):
            return await call_next(request)

        # 跳過 WebSocket 升級請求
        # 設計決策：WebSocket 連線無法透過 HTTP middleware 進行認證，因為
        # middleware 無法在 handshake 前拒絕連線並傳送 WebSocket close frame。
        # 需要認證的 WS endpoint（如 agent-session）在 accept 後自行呼叫
        # authenticate_websocket()；不需認證的 WS endpoint（如 terminal、
        # browser-relay）依賴 container 網路隔離作為安全邊界。
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # 內部 API 路徑跳過認證中間件（由 router 的 dependency 處理）
        if self._is_internal_api(path):
            return await call_next(request)

        # 檢查內部 API token（用於測試和內部服務調用）
        # 只有在設定環境變數 INTERNAL_API_TOKEN 時才啟用此功能
        if INTERNAL_API_TOKEN:
            internal_token = request.headers.get("X-Internal-Token")
            if internal_token and internal_token == INTERNAL_API_TOKEN:
                # 為內部 API token 創建一個測試用戶
                class TestUser:
                    def __init__(self):
                        self.id = 'internal-test-user'
                        self.user_id = 'internal-test-user'

                request.state.user = TestUser()
                request.state.user_id = 'internal-test-user'
                logger.debug(f"Internal token auth successful for {path}")
                return await call_next(request)

        # 檢查 Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.lower().startswith("bearer "):
            logger.warning(f"Missing or invalid auth header for {path}")
            return self._unauthorized("Missing or invalid Authorization header", "MISSING_AUTH_HEADER")

        try:
            token = auth_header.split(" ", 1)[1].strip()

            if not token:
                logger.warning(f"Empty token for {path}")
                return self._unauthorized("Empty authentication token", "EMPTY_TOKEN")

            # 驗證 token
            service = get_auth_service()
            user = await service.validate_access_token(token)

            if not user:
                logger.warning(f"Invalid or expired token for {path}, token: {token[:20]}...")
                return self._unauthorized(
                    "Token expired or invalid. Please refresh your token or login again.",
                    "TOKEN_EXPIRED"
                )

            # 設置用戶信息到請求狀態
            request.state.user = user
            request.state.user_id = user.id
            logger.debug(f"Auth successful for {path}: user_id={user.id}")
            return await call_next(request)
        except Exception as e:
            logger.error(f"Auth error for {path}: {e}", exc_info=True)
            return self._unauthorized("Authentication failed", "AUTH_ERROR")

    def _is_public(self, path: str, normalized_path: str) -> bool:
        """判斷是否為公開路徑"""
        if normalized_path in self.PUBLIC_PATHS:
            return True

        return any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES)

    def _is_internal_api(self, path: str) -> bool:
        """判斷是否為內部 API 路徑"""
        return any(path.startswith(prefix) for prefix in self.INTERNAL_API_PREFIXES)

    @staticmethod
    def _unauthorized(message: str = "Unauthorized", error_code: str = "UNAUTHORIZED") -> JSONResponse:
        """回傳未授權回應，包含錯誤代碼以便前端處理"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": message,
                "error_code": error_code,
                "timestamp": utcnow().isoformat()
            },
            headers={"WWW-Authenticate": "Bearer"},
        )