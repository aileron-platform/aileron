"""Gemini raw settings service."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any

from app.config.settings import get_workspace_path
from app.modules.cli_settings.mcp.config_strategies import JsonConfigStrategy

logger = logging.getLogger(__name__)


class GeminiSettingsScope(str, Enum):
    """Editable Gemini settings scopes."""

    USER = "user"
    PROJECT = "project"


class GeminiSettingsService:
    """Read and write Gemini settings.json files."""

    def __init__(self, user_settings_file: Path | None = None) -> None:
        self._user_settings_file = user_settings_file or Path.home() / ".gemini" / "settings.json"
        self._strategy = JsonConfigStrategy()

    def get_raw_settings(
        self,
        workspace_id: str,
        scope: GeminiSettingsScope,
    ) -> dict[str, Any]:
        return self._strategy.read(self._settings_file(workspace_id, scope))

    def update_raw_settings(
        self,
        workspace_id: str,
        scope: GeminiSettingsScope,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        settings_file = self._settings_file(workspace_id, scope)
        if content:
            try:
                self._strategy.write(settings_file, content)
            except (IOError, OSError, PermissionError) as error:
                logger.error(
                    "Failed to save Gemini raw settings file",
                    extra={
                        "file_path": str(settings_file),
                        "error": str(error),
                        "error_type": type(error).__name__,
                        "workspace_id": workspace_id,
                        "scope": scope.value,
                    },
                )
                raise
        elif settings_file.exists():
            try:
                settings_file.unlink()
            except (IOError, OSError, PermissionError) as error:
                logger.error(
                    "Failed to delete Gemini raw settings file",
                    extra={
                        "file_path": str(settings_file),
                        "error": str(error),
                        "error_type": type(error).__name__,
                        "workspace_id": workspace_id,
                        "scope": scope.value,
                    },
                )
                raise
        return content

    def _settings_file(self, workspace_id: str, scope: GeminiSettingsScope) -> Path:
        if scope == GeminiSettingsScope.USER:
            return self._user_settings_file
        return Path(get_workspace_path()) / ".gemini" / "settings.json"
