"""Output Styles Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from ..plugins.loader import get_plugin_loader
from ..settings.dependencies import get_settings_service
from .catalog import OutputStyleService


@lru_cache()
def get_output_style_service() -> OutputStyleService:
    """Provide OutputStyleService"""

    return OutputStyleService(
        plugin_loader=get_plugin_loader(get_settings_service()),
    )
