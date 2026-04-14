"""Hooks 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import HookService


@lru_cache()
def get_hook_service() -> HookService:
    """提供 HookService"""

    return HookService()
