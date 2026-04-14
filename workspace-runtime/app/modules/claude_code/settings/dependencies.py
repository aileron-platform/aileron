"""Settings 相依性定義"""

from __future__ import annotations

from functools import lru_cache

from .service import SettingsService


@lru_cache()
def get_settings_service() -> SettingsService:
    """提供單一 SettingsService 實例"""

    return SettingsService()
