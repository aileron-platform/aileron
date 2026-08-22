from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cli_settings.prompt_invocations.config import PromptInvocationTool
from app.modules.cli_settings.prompt_invocations.catalog import (
    PromptInvocationCatalogUnavailableError,
)
from app.modules.cli_settings.prompt_invocations.models import (
    PromptInvocationSourceError,
)
from app.modules.cli_settings.prompt_invocations.router import (
    create_prompt_invocations_router,
)


class FakePromptInvocationCatalogService:
    def list_catalog(self, workspace_id: str):
        return {
            "workspaceId": workspace_id,
            "agenticTool": "codex",
            "completeness": "complete",
            "revision": "catalog-revision",
            "availableScopes": ["project", "user", "plugin"],
            "sourceErrors": [],
            "items": [
                {
                    "id": "codex:skill:project:review/SKILL.md",
                    "sourceKey": "review/SKILL.md",
                    "fileName": "SKILL.md",
                    "kind": "skill",
                    "scope": "project",
                    "displayName": "review",
                    "category": "project",
                    "description": "Review the current changes",
                    "invocation": "$review",
                    "tags": [],
                }
            ],
        }


class UnavailablePromptInvocationCatalogService:
    def list_catalog(self, workspace_id: str):
        raise PromptInvocationCatalogUnavailableError(
            [
                PromptInvocationSourceError(
                    source="slash-commands",
                    errorCode="PROMPT_INVOCATION_SOURCE_UNAVAILABLE",
                    message="commands unavailable",
                )
            ]
        )


def _client(monkeypatch, service=None) -> TestClient:
    service = service or FakePromptInvocationCatalogService()
    monkeypatch.setattr(
        "app.modules.cli_settings.prompt_invocations.router.make_prompt_invocation_catalog_dependency",
        lambda tool: (lambda: service),
    )
    app = FastAPI()
    app.include_router(
        create_prompt_invocations_router(PromptInvocationTool.CODEX),
        prefix="/workspaces/{workspace_id}",
    )
    return TestClient(app)


def test_prompt_invocation_catalog_returns_invocation_ready_items(monkeypatch) -> None:
    response = _client(monkeypatch).get(
        "/workspaces/ws-1/cli-settings/codex/prompt-invocations"
    )

    assert response.status_code == 200
    assert response.json() == {
        "workspaceId": "ws-1",
        "agenticTool": "codex",
        "completeness": "complete",
        "revision": "catalog-revision",
        "availableScopes": ["project", "user", "plugin"],
        "sourceErrors": [],
        "items": [
            {
                "id": "codex:skill:project:review/SKILL.md",
                "sourceKey": "review/SKILL.md",
                "fileName": "SKILL.md",
                "kind": "skill",
                "scope": "project",
                "pluginName": None,
                "namespace": None,
                "displayName": "review",
                "category": "project",
                "description": "Review the current changes",
                "invocation": "$review",
                "tags": [],
            }
        ],
    }


def test_prompt_invocation_catalog_returns_503_when_every_source_fails(
    monkeypatch,
) -> None:
    response = _client(
        monkeypatch,
        UnavailablePromptInvocationCatalogService(),
    ).get("/workspaces/ws-1/cli-settings/codex/prompt-invocations")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "errorCode": "PROMPT_INVOCATION_CATALOG_UNAVAILABLE",
        "message": "Every Prompt Invocation source is unavailable",
        "sourceErrors": [
            {
                "source": "slash-commands",
                "errorCode": "PROMPT_INVOCATION_SOURCE_UNAVAILABLE",
                "message": "commands unavailable",
            }
        ],
    }
