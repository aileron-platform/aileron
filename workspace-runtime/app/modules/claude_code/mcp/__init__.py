"""MCP 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_mcp_service
from .models import (
    McpImportRequest,
    McpImportResponse,
    McpImportUploadRequest,
    McpScopeResponse,
    McpServerCollectionResponse,
    McpServerConfig,
    McpServerCreateRequest,
    McpServerDeleteResponse,
    McpServerExportResponse,
    McpServerRuntime,
    McpServerUpdateRequest,
    McpTransportType,
)
from .service import McpService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(
        f"module 'app.modules.claude_code.mcp' has no attribute {name!r}"
    )


__all__ = [
    "router",
    "McpService",
    "McpTransportType",
    "McpServerConfig",
    "McpServerRuntime",
    "McpServerCollectionResponse",
    "McpScopeResponse",
    "McpServerCreateRequest",
    "McpServerUpdateRequest",
    "McpServerDeleteResponse",
    "McpServerExportResponse",
    "McpImportRequest",
    "McpImportResponse",
    "McpImportUploadRequest",
    "get_mcp_service",
]
