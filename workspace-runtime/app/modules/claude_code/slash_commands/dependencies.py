"""Slash Commands 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import SlashCommandService


@lru_cache()
def get_slash_command_service() -> SlashCommandService:
    """提供 SlashCommandService"""

    return SlashCommandService()
