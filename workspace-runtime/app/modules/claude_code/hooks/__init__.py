"""Hooks 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_hook_service
from .models import (
    HookDeleteResponse,
    HookExportResponse,
    HookImportRequest,
    HookImportResponse,
    HookScopeResponse,
    HookScopeUpsertRequest,
    HookScopesResponse,
)
from .service import HookService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(f"module 'app.modules.claude_code.hooks' has no attribute {name!r}")


__all__ = [
    "router",
    "HookService",
    "HookScopesResponse",
    "HookScopeResponse",
    "HookScopeUpsertRequest",
    "HookExportResponse",
    "HookImportRequest",
    "HookImportResponse",
    "HookDeleteResponse",
    "get_hook_service",
]
