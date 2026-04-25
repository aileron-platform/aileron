"""Canvas 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import CanvasService


@lru_cache(maxsize=1)
def get_canvas_service() -> CanvasService:
    """取得 Canvas 服務單例"""

    return CanvasService()
