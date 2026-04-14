"""
JWT 認證中間件

提供基於 JWT token 的請求認證中間件，自動驗證 Bearer token 並注入用戶信息。
整合用戶同步服務，自動在本地資料庫創建或更新用戶記錄。
"""

import time
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTValidationError, get_jwt_utils
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _ensure_local_user(payload: dict) -> str | None:
    """JWT 驗證成功後，確保 local DB 有對應的 user 記錄，並自動加入 default-workspace。

    Returns:
        str | None: local DB user ID，若失敗則返回 None
    """
    keycloak_id = payload.get("sub")
    if not keycloak_id:
        return None
    try:
        from app.db.database import SessionLocal
        from app.services.user_service import UserService

        db = SessionLocal()
        try:
            user_service = UserService(db)
            existing = user_service.get_by_keycloak_id(keycloak_id)
            if not existing:
                existing = user_service.create_from_jwt_payload(payload)
                logger.info(f"Auto-created local user for keycloak_id={keycloak_id}")
            return existing.id if existing else None
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"User sync failed for keycloak_id={keycloak_id}: {e}")
        return None


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    JWT 認證中間件

    自動從請求中提取 Bearer token，驗證其有效性，並將用戶信息注入到 request.state。

    功能：
    - 從 Authorization header 提取 Bearer token
    - 驗證 token 簽名、過期時間、issuer、audience
    - 將解碼後的用戶信息注入到 request.state.current_user
    - 支持認證未啟用時的跳過邏輯
    - 支持可選的路徑排除（如 /health, /public/*）

    使用示例：
        app.add_middleware(
            JWTAuthenticationMiddleware,
            exclude_paths=["/health", "/docs", "/redoc"],
        )
    """

    def __init__(
        self,
        app,
        exclude_paths: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        初始化 JWT 認證中間件

        Args:
            app: FastAPI 應用實例
            exclude_paths: 要排除的完整路徑列表
            exclude_patterns: 要排除的路徑模式列表（支持前綴匹配）
        """
        super().__init__(app)
        self.config = get_keycloak_config()
        self.exclude_paths = set(exclude_paths or [])
        self.exclude_patterns = exclude_patterns or []

        # 添加默認排除路徑
        default_excludes = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
        ]
        for path in default_excludes:
            self.exclude_paths.add(path)

    def _is_excluded_path(self, path: str) -> bool:
        """
        檢查路徑是否應該排除認證

        Args:
            path: 請求路徑

        Returns:
            True 如果路徑應該排除認證
        """
        # 完全匹配排除
        if path in self.exclude_paths:
            return True

        # 前綴匹配排除（支持 * 通配符）
        for pattern in self.exclude_patterns:
            # 處理 * 通配符
            if pattern.endswith("*"):
                # 移除 * 並檢查前綴
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return True
            else:
                # 沒有通配符，使用精確前綴匹配
                if path.startswith(pattern):
                    return True

        return False

    async def dispatch(self, request: Request, call_next):
        """
        處理每個請求，提取並驗證 JWT token

        Args:
            request: FastAPI 請求對象
            call_next: 下一個中間件/路由處理器

        Returns:
            HTTP 響應
        """
        if not self.config.enabled:
            request.state.auth_enabled = False
            request.state.current_user = None
            request.state.auth_valid = False
            return await call_next(request)

        request.state.auth_enabled = True

        # 檢查路徑是否排除認證
        if self._is_excluded_path(request.url.path):
            logger.debug(f"路徑 {request.url.path} 排除認證")
            request.state.current_user = None
            request.state.auth_exempt = True
            return await call_next(request)

        # 提取 Bearer token
        token = self._extract_bearer_token(request)

        if not token:
            # 沒有提供 token，將 current_user 設為 None
            # 注意：這裡不直接返回 401，而是讓路由決定是否需要認證
            request.state.current_user = None
            request.state.auth_valid = False
            logger.debug(f"Authentication skipped: no token provided for {request.url.path}")
            return await call_next(request)

        # 記錄認證嘗試（不記錄完整 token）
        token_preview = f"{token[:20]}..." if len(token) > 20 else token
        logger.info(f"Authentication attempt: {request.method} {request.url.path}, token={token_preview}")

        # 驗證 token（計時）
        validation_start = time.perf_counter()
        try:
            user_info = await self._validate_token(token)
            validation_duration = time.perf_counter() - validation_start

            request.state.current_user = user_info
            request.state.auth_valid = True
            request.state.auth_validation_duration = validation_duration

            # User sync：確保本地 DB 有對應記錄，若不存在則自動建立並加入 default-workspace
            # 回傳 local DB user ID，以便後續 API 正確查詢
            local_user_id = await _ensure_local_user(user_info)

            # 設置 user_id（優先用 local DB ID，fallback 到 Keycloak sub）
            keycloak_id = user_info.get('sub')
            request.state.user_id = local_user_id or keycloak_id

            # 認證成功日誌（包含性能指標）
            logger.info(f"Authentication successful: user_id={request.state.user_id}, path={request.url.path}, duration={validation_duration*1000:.2f}ms")

        except JWTValidationError as e:
            validation_duration = time.perf_counter() - validation_start
            # 認證失敗日誌（不記錄完整錯誤堆疊，避免日誌注入攻擊）
            logger.warning(f"Authentication failed: {request.url.path}, reason={str(e)}, duration={validation_duration*1000:.2f}ms")
            request.state.current_user = None
            request.state.auth_valid = False
            request.state.auth_error = str(e)

            # 不直接返回 401，讓路由決定如何處理
            # 如果路由需要認證，會使用 require_authenticated_user 依賴

        except Exception as e:
            validation_duration = time.perf_counter() - validation_start
            logger.error(f"認證過程中發生未預期的錯誤: {e}, duration={validation_duration*1000:.2f}ms")
            request.state.current_user = None
            request.state.auth_valid = False
            request.state.auth_error = f"Authentication error: {str(e)}"

        return await call_next(request)

    def _extract_bearer_token(self, request: Request) -> Optional[str]:
        """
        從 Authorization header 提取 Bearer token

        Args:
            request: FastAPI 請求對象

        Returns:
            Bearer token 字符串，如果不存在則返回 None
        """
        authorization = request.headers.get("Authorization")

        if not authorization:
            return None

        # 檢查是否為 Bearer token
        if not authorization.startswith("Bearer "):
            logger.warning(f"Authorization header 格式錯誤: {authorization[:20]}...")
            return None

        # 提取 token
        token = authorization.split(" ", 1)[1].strip()

        if not token:
            logger.warning("Authorization header 為空")
            return None

        return token

    async def _validate_token(self, token: str) -> dict:
        """
        驗證 JWT token

        驗證項目：
        - 簽名驗證（使用 JWKS 公鑰）
        - 過期時間檢查（exp claim）
        - 簽發者檢查（iss claim）
        - 受眾檢查（aud claim）

        Args:
            token: JWT token 字符串

        Returns:
            解碼後的 token payload（用戶信息）

        Raises:
            JWTValidationError: Token 驗證失敗
        """
        jwt_utils = get_jwt_utils()

        # 使用 async 版本的 decode_token，避免在 async FastAPI 環境中
        # 呼叫 loop.run_until_complete() 導致 "this event loop is already running" 錯誤
        payload = await jwt_utils.decode_token_async(token)

        # 驗證必要的 claims
        if not payload.get("sub"):
            raise JWTValidationError("Token missing 'sub' claim")

        return payload


class StrictJWTAuthenticationMiddleware(JWTAuthenticationMiddleware):
    """
    嚴格模式的 JWT 認證中間件

    與標準中間件的區別：
    - 如果 token 驗證失敗，直接返回 401 錯誤
    - 不允許路由決定是否需要認證
    - 適用於所有路由都需要認證的場景

    使用示例：
        app.add_middleware(StrictJWTAuthenticationMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        """
        處理每個請求，強制要求有效 token

        Args:
            request: FastAPI 請求對象
            call_next: 下一個中間件/路由處理器

        Returns:
            HTTP 響應 或 401 錯誤
        """
        if not self.config.enabled:
            request.state.auth_enabled = False
            request.state.current_user = None
            request.state.auth_valid = False
            return await call_next(request)

        request.state.auth_enabled = True

        # 檢查路徑是否排除認證
        if self._is_excluded_path(request.url.path):
            logger.debug(f"路徑 {request.url.path} 排除認證")
            request.state.current_user = None
            request.state.auth_exempt = True
            return await call_next(request)

        # 提取 Bearer token
        token = self._extract_bearer_token(request)

        if not token:
            logger.warning("缺少 Authorization header")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing Authorization header",
                    "message": "Authentication required",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 驗證 token
        try:
            user_info = await self._validate_token(token)
            request.state.current_user = user_info
            request.state.auth_valid = True
            logger.debug(f"用戶 {user_info.get('sub')} 認證成功")

        except JWTValidationError as e:
            logger.warning(f"Token 驗證失敗: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": str(e),
                    "message": "Invalid or expired token",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        except Exception as e:
            logger.error(f"認證過程中發生未預期的錯誤: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": "Authentication failed",
                },
            )

        return await call_next(request)
