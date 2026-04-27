"""Claude Code Memory Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import MemoryService


@lru_cache()
def get_memory_service() -> MemoryService:
    """Provide MemoryService"""

    return MemoryService()
