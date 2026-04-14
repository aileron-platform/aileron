"""預覽模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import PreviewService


@lru_cache(maxsize=1)
def get_preview_service() -> PreviewService:
    """取得預覽服務單例"""

    return PreviewService()
