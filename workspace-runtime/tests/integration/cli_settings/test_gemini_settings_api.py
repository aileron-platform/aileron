from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.cli_settings.gemini.router import get_gemini_settings_service
from app.modules.cli_settings.gemini.service import GeminiSettingsScope

from tests.integration.claude_code.helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubGeminiSettingsService:
    content: dict = field(default_factory=dict)
    reads: list[tuple[str, GeminiSettingsScope]] = field(default_factory=list)
    updates: list[tuple[str, GeminiSettingsScope, dict]] = field(default_factory=list)

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


def test_gemini_settings_raw_get(client) -> None:
    service = StubGeminiSettingsService(content={"model": "gemini-2.5-pro"})

    with override_dependency(get_gemini_settings_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/gemini/settings/raw",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert response.json() == {"content": {"model": "gemini-2.5-pro"}}
    assert service.reads == [(WORKSPACE_ID, GeminiSettingsScope.USER)]


def test_gemini_settings_raw_put(client) -> None:
    service = StubGeminiSettingsService()
    payload = {"content": {"general": {"preferredEditor": "vim"}}}

    with override_dependency(get_gemini_settings_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/gemini/settings/raw",
            params={"scope": "project"},
            json=payload,
        )

    assert response.status_code == 200
    assert response.json() == payload
    assert service.updates == [
        (WORKSPACE_ID, GeminiSettingsScope.PROJECT, payload["content"]),
    ]


def test_gemini_settings_raw_missing_scope_returns_422(client) -> None:
    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/gemini/settings/raw")

    assert response.status_code == 422


def test_gemini_settings_raw_invalid_scope_returns_422(client) -> None:
    response = client.put(
        f"/api/v1/workspaces/{WORKSPACE_ID}/gemini/settings/raw",
        params={"scope": "extension"},
        json={"content": {}},
    )

    assert response.status_code == 422
