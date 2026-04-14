"""Workspace Runtime 國際化中間件。"""

from __future__ import annotations

import logging
from functools import partial
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.settings import get_settings
from app.services.i18n_service import get_i18n_service

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseHTTPMiddleware):
    """將請求語系注入 request state 供後續依賴使用。"""

    def __init__(self, app, *, default_language: str = "zh-TW") -> None:  # type: ignore[override]
        super().__init__(app)
        self._i18n_service = get_i18n_service()
        self._default_language = default_language
        self._app_settings = get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 語言優先順序：
        # 1. X-Language header (用戶臨時切換)
        # 2. Accept-Language header (瀏覽器語言)
        # 3. 預設語言 (en)

        header_language = request.headers.get("X-Language")

        # 決定最終語言
        preferred = (
            header_language
            or request.headers.get("Accept-Language")
            or self._default_language
        )
        language = self._i18n_service.resolve_language(preferred)

        logger.debug(
            f"I18nMiddleware: language={language} "
            f"(header={header_language}, workspace_id={self._app_settings.WORKSPACE_ID})"
        )

        request.state.language = language
        request.state.translate = partial(self._i18n_service.translate, language=language)

        response = await call_next(request)
        response.headers["Content-Language"] = language
        return response


__all__ = ["I18nMiddleware"]
