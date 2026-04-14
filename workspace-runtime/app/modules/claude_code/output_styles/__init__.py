"""Output Styles 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_output_style_service
from .models import (
    OutputStyleCollectionResponse,
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleDocumentResponse,
    OutputStyleScopeResponse,
    OutputStyleUpdateRequest,
)
from .service import OutputStyleService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(
        f"module 'app.modules.claude_code.output_styles' has no attribute {name!r}"
    )


__all__ = [
    "router",
    "OutputStyleService",
    "OutputStyleCollectionResponse",
    "OutputStyleScopeResponse",
    "OutputStyleDocumentResponse",
    "OutputStyleCreateRequest",
    "OutputStyleUpdateRequest",
    "OutputStyleDeleteResponse",
    "get_output_style_service",
]
