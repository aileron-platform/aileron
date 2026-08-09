"""Multilingual processing middleware."""

from __future__ import annotations

from functools import partial
from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.modules.localization.translator import get_i18n_service


class I18nMiddleware(BaseHTTPMiddleware):
    """Determine language based on user system settings and set up translation environment."""

    def __init__(self, app, *, default_language: str = "en") -> None:  # type: ignore[override]
        super().__init__(app)
        self._i18n_service = get_i18n_service()
        self._default_language = default_language

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Prioritize reading language from user settings
        language = self._default_language

        # If user is logged in, get language preference from user settings
        if hasattr(request.state, "user") and request.state.user:
            try:
                # Get settings from user object
                user = request.state.user
                if hasattr(user, "settings") and user.settings:
                    # Get language settings from additional_settings in database
                    additional_settings = (
                        getattr(user.settings, "additional_settings", {}) or {}
                    )
                    general_settings = additional_settings.get("general", {})
                    user_language = general_settings.get("language")

                    if user_language:
                        language = user_language
            except Exception:
                # If getting user language settings fails, use default language
                pass

        # If no user settings, fallback to header (for endpoints without login)
        if language == self._default_language:
            header_language = request.headers.get("X-Language") or request.headers.get(
                "Accept-Language"
            )
            if header_language:
                language = header_language

        # Parse and verify language
        language = self._i18n_service.resolve_language(language)

        request.state.language = language
        request.state.translate = partial(
            self._i18n_service.translate, language=language
        )

        response = await call_next(request)
        response.headers["Content-Language"] = language
        return response


__all__ = ["I18nMiddleware"]
