from __future__ import annotations

from dataclasses import dataclass

from app.modules.cli_settings.prompt_invocations.catalog import (
    PromptInvocationCatalogUnavailableError,
    PromptInvocationCatalogService,
)
from app.modules.cli_settings.prompt_invocations.config import PromptInvocationTool
from app.modules.cli_settings.prompt_invocations.models import (
    PromptInvocationItem,
    PromptInvocationKind,
    PromptInvocationScope,
)


@dataclass
class StaticSource:
    source_id: str
    scopes: tuple[PromptInvocationScope, ...]
    items: list[PromptInvocationItem]
    error: Exception | None = None

    def load(self, workspace_id: str) -> list[PromptInvocationItem]:
        if self.error is not None:
            raise self.error
        return self.items


def _skill_item() -> PromptInvocationItem:
    return PromptInvocationItem(
        id="codex:skill:project:review/SKILL.md",
        sourceKey="review/SKILL.md",
        fileName="SKILL.md",
        kind=PromptInvocationKind.SKILL,
        scope=PromptInvocationScope.PROJECT,
        displayName="review",
        category="project",
        description="Review the current changes",
        invocation="$review",
    )


def test_catalog_returns_available_items_when_one_source_fails() -> None:
    service = PromptInvocationCatalogService(
        PromptInvocationTool.CODEX,
        sources=[
            StaticSource(
                source_id="slash-commands",
                scopes=(PromptInvocationScope.PROJECT, PromptInvocationScope.USER),
                items=[],
                error=RuntimeError("commands unavailable"),
            ),
            StaticSource(
                source_id="project-skills",
                scopes=(PromptInvocationScope.PROJECT,),
                items=[_skill_item()],
            ),
        ],
    )

    catalog = service.list_catalog("ws-1")

    assert catalog.completeness == "degraded"
    assert catalog.items == [_skill_item()]
    assert catalog.available_scopes == [
        PromptInvocationScope.PROJECT,
        PromptInvocationScope.USER,
    ]
    assert [error.model_dump(by_alias=True) for error in catalog.source_errors] == [
        {
            "source": "slash-commands",
            "errorCode": "PROMPT_INVOCATION_SOURCE_UNAVAILABLE",
            "message": "commands unavailable",
        }
    ]


def test_catalog_is_unavailable_when_every_source_fails() -> None:
    service = PromptInvocationCatalogService(
        PromptInvocationTool.OPENCODE,
        sources=[
            StaticSource(
                source_id="slash-commands",
                scopes=(PromptInvocationScope.PROJECT,),
                items=[],
                error=RuntimeError("commands unavailable"),
            ),
            StaticSource(
                source_id="project-skills",
                scopes=(PromptInvocationScope.PROJECT,),
                items=[],
                error=RuntimeError("skills unavailable"),
            ),
        ],
    )

    try:
        service.list_catalog("ws-1")
    except PromptInvocationCatalogUnavailableError as error:
        assert [source_error.source for source_error in error.source_errors] == [
            "project-skills",
            "slash-commands",
        ]
    else:
        raise AssertionError("Expected the Catalog to be unavailable")
