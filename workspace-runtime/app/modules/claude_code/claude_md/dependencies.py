"""Claude.md 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import ClaudeMdService


@lru_cache()
def get_claude_md_service() -> ClaudeMdService:
    """提供單例 ClaudeMdService"""

    return ClaudeMdService()
