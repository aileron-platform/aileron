"""Prompt Invocation Catalog dependency injection."""

from collections.abc import Callable

from .catalog import PromptInvocationCatalogService
from .config import PromptInvocationTool


def make_prompt_invocation_catalog_dependency(
    tool: PromptInvocationTool,
) -> Callable[[], PromptInvocationCatalogService]:
    def _get_service() -> PromptInvocationCatalogService:
        return PromptInvocationCatalogService(tool)

    return _get_service
