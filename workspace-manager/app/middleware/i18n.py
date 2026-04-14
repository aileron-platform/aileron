"""多語系處理中間件。"""

from __future__ import annotations

from functools import partial
from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services import get_i18n_service


class I18nMiddleware(BaseHTTPMiddleware):
    """根據使用者系統設定決定語系，並設定翻譯環境。"""

    def __init__(self, app, *, default_language: str = "en") -> None:  # type: ignore[override]
        super().__init__(app)
        self._i18n_service = get_i18n_service()
        self._default_language = default_language

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 優先從使用者設定中讀取語言
        language = self._default_language

        # 如果使用者已登入，從使用者設定中取得語言偏好
        if hasattr(request.state, "user") and request.state.user:
            try:
                # 從使用者物件中取得設定
                user = request.state.user
                if hasattr(user, "settings") and user.settings:
                    # 從資料庫的 additional_settings 中取得語言設定
                    additional_settings = getattr(user.settings, "additional_settings", {}) or {}
                    general_settings = additional_settings.get("general", {})
                    user_language = general_settings.get("language")

                    if user_language:
                        language = user_language
            except Exception:
                # 如果取得使用者語言設定失敗，使用預設語言
                pass

        # 如果沒有使用者設定，則回退到 header（用於未登入的端點）
        if language == self._default_language:
            header_language = request.headers.get("X-Language") or request.headers.get("Accept-Language")
            if header_language:
                language = header_language

        # 解析並驗證語言
        language = self._i18n_service.resolve_language(language)

        request.state.language = language
        request.state.translate = partial(self._i18n_service.translate, language=language)

        response = await call_next(request)
        response.headers["Content-Language"] = language
        return response


__all__ = ["I18nMiddleware"]
