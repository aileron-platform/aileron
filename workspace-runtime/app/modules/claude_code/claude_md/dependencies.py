"""Claude.md Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import ClaudeMdService


@lru_cache()
def get_claude_md_service() -> ClaudeMdService:
    """Provide singleton ClaudeMdService"""

    return ClaudeMdService()
