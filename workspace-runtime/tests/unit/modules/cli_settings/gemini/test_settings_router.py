from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cli_settings.gemini.router import get_gemini_settings_service, router
from app.modules.cli_settings.gemini.service import GeminiSettingsScope


class FakeSettingsService:
    def __init__(self) -> None:
        self.content = {"model": "gemini-2.5-pro"}
        self.reads: list[tuple[str, GeminiSettingsScope]] = []
        self.updates: list[tuple[str, GeminiSettingsScope, dict]] = []

    def get_raw_settings(self, workspace_id: str, scope: GeminiSettingsScope) -> dict:
        self.reads.append((workspace_id, scope))
        return self.content

    def update_raw_settings(
        self,
        workspace_id: str,
        scope: GeminiSettingsScope,
        content: dict,
    ) -> dict:
        self.updates.append((workspace_id, scope, content))
        self.content = content
        return content


def _client(service: FakeSettingsService) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/workspaces/{workspace_id}")
    app.dependency_overrides[get_gemini_settings_service] = lambda: service
    return TestClient(app)


def test_get_raw_settings_returns_content() -> None:
    service = FakeSettingsService()
    client = _client(service)

    response = client.get("/workspaces/ws-1/gemini/settings/raw?scope=user")

    assert response.status_code == 200
    assert response.json() == {"content": {"model": "gemini-2.5-pro"}}
    assert service.reads == [("ws-1", GeminiSettingsScope.USER)]


def test_put_raw_settings_saves_content() -> None:
    service = FakeSettingsService()
    client = _client(service)
    payload = {"content": {"general": {"preferredEditor": "vim"}}}

    response = client.put(
        "/workspaces/ws-1/gemini/settings/raw?scope=project",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json() == payload
    assert service.updates == [
        ("ws-1", GeminiSettingsScope.PROJECT, payload["content"]),
    ]


def test_raw_settings_missing_scope_returns_422() -> None:
    response = _client(FakeSettingsService()).get("/workspaces/ws-1/gemini/settings/raw")

    assert response.status_code == 422


def test_raw_settings_invalid_scope_returns_422() -> None:
    response = _client(FakeSettingsService()).put(
        "/workspaces/ws-1/gemini/settings/raw?scope=extension",
        json={"content": {}},
    )

    assert response.status_code == 422


def test_raw_settings_malformed_body_returns_422() -> None:
    response = _client(FakeSettingsService()).put(
        "/workspaces/ws-1/gemini/settings/raw?scope=user",
        json={"other": {}},
    )

    assert response.status_code == 422
