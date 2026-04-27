"""Hooks Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import HookService


@lru_cache()
def get_hook_service() -> HookService:
    """Provide HookService"""

    return HookService()
