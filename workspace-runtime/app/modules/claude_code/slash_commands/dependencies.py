"""Slash Commands Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import SlashCommandService


@lru_cache()
def get_slash_command_service() -> SlashCommandService:
    """Provide SlashCommandService"""

    return SlashCommandService()
