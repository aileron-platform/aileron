"""Subagents 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_subagent_service
from .models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentUpdateRequest,
)
from .service import SubagentService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(
        f"module 'app.modules.claude_code.subagents' has no attribute {name!r}"
    )


__all__ = [
    "router",
    "SubagentService",
    "SubagentCollectionResponse",
    "SubagentScopeResponse",
    "SubagentDocumentResponse",
    "SubagentCreateRequest",
    "SubagentUpdateRequest",
    "SubagentDeleteResponse",
    "get_subagent_service",
]
