"""Canvas module dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import CanvasService


@lru_cache(maxsize=1)
def get_canvas_service() -> CanvasService:
    """Get Canvas service singleton"""

    return CanvasService()
