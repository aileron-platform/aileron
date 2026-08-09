"""Canvas module dependencies"""

from __future__ import annotations

from functools import lru_cache

from app.config.settings import get_settings

from .publishing import CanvasService


@lru_cache(maxsize=1)
def get_canvas_service() -> CanvasService:
    """Get Canvas service singleton"""

    settings = get_settings()
    return CanvasService(
        workspace_path=settings.AILERON_WORKSPACE_PATH,
        canvas_api_url=settings.AILERON_CANVAS_API_URL,
        canvas_internal_url=settings.AILERON_CANVAS_INTERNAL_URL,
    )
