"""CLI Slash Commands module dependency injection"""

from __future__ import annotations

from typing import Callable

from .config import SlashCommandTool, get_slash_command_config
from .service import CliSlashCommandService


def make_slash_command_service_dependency(
    tool: SlashCommandTool,
) -> Callable[[], CliSlashCommandService]:
    def _get_service() -> CliSlashCommandService:
        config = get_slash_command_config(tool)
        return CliSlashCommandService(config)

    return _get_service
