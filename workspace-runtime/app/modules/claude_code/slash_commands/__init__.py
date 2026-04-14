"""Slash Commands 子模組"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_slash_command_service
from .models import (
    SlashCommandCreateRequest,
    SlashCommandDeleteResponse,
    SlashCommandDocumentResponse,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)
from .service import SlashCommandService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(
        f"module 'app.modules.claude_code.slash_commands' has no attribute {name!r}"
    )


__all__ = [
    "router",
    "SlashCommandService",
    "SlashCommandScopesResponse",
    "SlashCommandScopeResponse",
    "SlashCommandDocumentResponse",
    "SlashCommandCreateRequest",
    "SlashCommandUpdateRequest",
    "SlashCommandDeleteResponse",
    "get_slash_command_service",
]
