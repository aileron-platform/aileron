"""Settings Dependency Definitions"""

from __future__ import annotations

from functools import lru_cache

from .configuration import SettingsService


@lru_cache()
def get_settings_service() -> SettingsService:
    """Provide a single SettingsService instance"""

    return SettingsService()
