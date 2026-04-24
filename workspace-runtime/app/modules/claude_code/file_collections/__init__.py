"""File Collections 模組 - Skills / Scripts 統一管理"""

from __future__ import annotations

from .scripts_router import router as scripts_router
from .skills_router import router as skills_router

__all__ = ["scripts_router", "skills_router"]
