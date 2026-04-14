"""Output Styles 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import OutputStyleService


@lru_cache()
def get_output_style_service() -> OutputStyleService:
    """提供 OutputStyleService"""

    return OutputStyleService()
