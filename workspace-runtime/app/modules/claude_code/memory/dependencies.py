"""Claude Code Memory 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import MemoryService


@lru_cache()
def get_memory_service() -> MemoryService:
    """提供 MemoryService"""

    return MemoryService()
