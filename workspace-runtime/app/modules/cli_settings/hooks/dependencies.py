"""CLI Hooks module dependency injection"""

from __future__ import annotations

from typing import Callable

from .config import HookTool, get_hook_tool_config
from .service import CliHookService


def make_hooks_service_dependency(
    tool: HookTool,
) -> Callable[[], CliHookService]:
    def _get_service() -> CliHookService:
        config = get_hook_tool_config(tool)
        return CliHookService(config)

    return _get_service
