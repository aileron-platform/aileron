"""OpenSpec module dependencies."""

from __future__ import annotations

from functools import lru_cache

from .service import OpenSpecService


@lru_cache(maxsize=1)
def get_openspec_service() -> OpenSpecService:
    """取得 OpenSpec service 單例。"""
    return OpenSpecService()
