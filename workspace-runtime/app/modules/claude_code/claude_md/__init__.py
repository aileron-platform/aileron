"""Claude.md 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_claude_md_service
from .models import ClaudeMdDocument, ClaudeMdUpdateRequest, ClaudeMdUpdateResponse
from .service import ClaudeMdService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(f"module 'app.modules.claude_code.claude_md' has no attribute {name!r}")


__all__ = [
    "router",
    "ClaudeMdService",
    "ClaudeMdDocument",
    "ClaudeMdUpdateRequest",
    "ClaudeMdUpdateResponse",
    "get_claude_md_service",
]
