"""OpenSpec module dependencies."""

from __future__ import annotations

from functools import lru_cache

from .service import OpenSpecService


@lru_cache(maxsize=1)
def get_openspec_service() -> OpenSpecService:
    """Get OpenSpec service singleton."""
    return OpenSpecService()
