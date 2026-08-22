"""Prompt Invocation Catalog aggregation service."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from app.core.revision import compute_revision

from .config import PromptInvocationTool
from .models import (
    CatalogCompleteness,
    PromptInvocationCatalogResponse,
    PromptInvocationItem,
    PromptInvocationScope,
    PromptInvocationSourceError,
)


class PromptInvocationSource(Protocol):
    """One independently loadable Prompt Invocation source."""

    source_id: str
    scopes: tuple[PromptInvocationScope, ...]

    def load(self, workspace_id: str) -> list[PromptInvocationItem]: ...


class PromptInvocationCatalogUnavailableError(RuntimeError):
    """Every configured Prompt Invocation source failed."""

    def __init__(
        self,
        source_errors: Sequence[PromptInvocationSourceError],
    ) -> None:
        super().__init__("Every Prompt Invocation source is unavailable")
        self.source_errors = tuple(source_errors)


class PromptInvocationCatalogService:
    """Build one Agentic Tool-specific Prompt Invocation Catalog."""

    def __init__(
        self,
        tool: PromptInvocationTool,
        sources: Sequence[PromptInvocationSource] | None = None,
    ) -> None:
        self._tool = tool
        if sources is None:
            from .sources import build_prompt_invocation_sources

            sources = build_prompt_invocation_sources(tool)
        self._sources = tuple(sources)

    def list_catalog(self, workspace_id: str) -> PromptInvocationCatalogResponse:
        items_by_id: dict[str, PromptInvocationItem] = {}
        source_errors: list[PromptInvocationSourceError] = []
        available_scopes: set[PromptInvocationScope] = set()
        successful_source_count = 0

        for source in self._sources:
            available_scopes.update(source.scopes)
            try:
                for item in source.load(workspace_id):
                    items_by_id.setdefault(item.id, item)
                successful_source_count += 1
            except Exception as error:
                source_errors.append(
                    PromptInvocationSourceError(
                        source=source.source_id,
                        errorCode="PROMPT_INVOCATION_SOURCE_UNAVAILABLE",
                        message=str(error),
                    )
                )

        items = sorted(
            items_by_id.values(),
            key=lambda item: (item.display_name.casefold(), item.id),
        )
        source_errors.sort(key=lambda error: error.source)
        if successful_source_count == 0:
            raise PromptInvocationCatalogUnavailableError(source_errors)
        scope_order = {
            PromptInvocationScope.PROJECT: 0,
            PromptInvocationScope.USER: 1,
            PromptInvocationScope.PLUGIN: 2,
        }
        scopes = sorted(available_scopes, key=scope_order.__getitem__)
        completeness = (
            CatalogCompleteness.DEGRADED
            if source_errors
            else CatalogCompleteness.COMPLETE
        )
        revision_payload = {
            "items": [item.model_dump(by_alias=True) for item in items],
            "sourceErrors": [
                error.model_dump(by_alias=True) for error in source_errors
            ],
        }

        return PromptInvocationCatalogResponse(
            workspaceId=workspace_id,
            agenticTool=self._tool,
            completeness=completeness,
            revision=compute_revision(
                json.dumps(revision_payload, sort_keys=True, separators=(",", ":"))
            ),
            availableScopes=scopes,
            sourceErrors=source_errors,
            items=items,
        )
