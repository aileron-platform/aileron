"""Claude Code Settings Submodule"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .dependencies import get_settings_service
from .models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    PermissionMode,
    PermissionRules,
)
from .service import SettingsService

if TYPE_CHECKING:
    from fastapi import APIRouter


def __getattr__(name: str):
    if name == "router":
        from .router import router as module_router

        return module_router
    raise AttributeError(
        f"module 'app.modules.claude_code.settings' has no attribute {name!r}"
    )


__all__ = [
    "router",
    "SettingsService",
    "get_settings_service",
    "ClaudeCodeSettings",
    "ClaudeCodeSettingsUpdateRequest",
    "PermissionMode",
    "PermissionRules",
]
