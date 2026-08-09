"""Claude Code API test cases - Settings"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.settings.dependencies import get_settings_service
from app.modules.claude_code.settings.models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    PermissionMode,
    PermissionRules,
)

from .dependency_overrides import WORKSPACE_ID, override_dependency


@dataclass
class StubSettingsService:
    settings: Optional[ClaudeCodeSettings] = None
    updated: list[tuple[str, ClaudeCodeSettingsUpdateRequest, DocumentScope]] = field(
        default_factory=list
    )
    raw_content: dict | None = None
    raw_revision: str = "raw-revision"
    raw_reads: list[tuple[str, DocumentScope]] = field(default_factory=list)
    raw_updates: list[tuple[str, DocumentScope, dict, str | None]] = field(
        default_factory=list
    )

    def get_settings(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> ClaudeCodeSettings:
        assert self.settings is not None
        return self.settings

    def update_settings(
        self,
        workspace_id: str,
        payload: ClaudeCodeSettingsUpdateRequest,
        scope: DocumentScope = DocumentScope.PROJECT,
    ) -> ClaudeCodeSettings:
        self.updated.append((workspace_id, payload, scope))
        assert self.settings is not None
        return self.settings

    def get_raw_settings(self, workspace_id: str, scope: DocumentScope) -> dict:
        self.raw_reads.append((workspace_id, scope))
        return self.raw_content or {}

    def get_settings_revision(self, workspace_id: str, scope: DocumentScope) -> str:
        return self.raw_revision

    def update_raw_settings(
        self,
        workspace_id: str,
        scope: DocumentScope,
        content: dict,
        revision: str | None = None,
    ) -> dict:
        self.raw_updates.append((workspace_id, scope, content, revision))
        self.raw_content = content
        return content


def _sample_settings(
    mode: PermissionMode = PermissionMode.DEFAULT,
) -> ClaudeCodeSettings:
    return ClaudeCodeSettings(
        mode=mode,
        default_mode=mode,
        output_style=None,
        permissions=PermissionRules(),
        env={},
        model=None,
        enabled_plugins={},
        api_key_helper=None,
        cleanup_period_days=None,
        include_co_authored_by=True,
        disable_all_hooks=False,
        enable_all_project_mcp_servers=False,
        enabled_mcpjson_servers=[],
        disabled_mcpjson_servers=[],
        allowed_mcp_servers=[],
        denied_mcp_servers=[],
    )


def test_cset_001_get_all_settings(client):
    service = StubSettingsService(settings=_sample_settings(PermissionMode.DEFAULT))

    with override_dependency(get_settings_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings")

    assert response.status_code == 200
    assert response.json()["mode"] == "default"


def test_cset_002_get_scope_settings(client):
    service = StubSettingsService(
        settings=_sample_settings(PermissionMode.ACCEPT_EDITS)
    )

    with override_dependency(get_settings_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "acceptEdits"


def test_cset_003_marketplaces_endpoint_removed_and_fails_closed(client):
    response = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/marketplaces"
    )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
    )


def test_cset_004_update_settings_project(client):
    service = StubSettingsService(settings=_sample_settings(PermissionMode.PLAN))

    payload = {
        "defaultMode": "plan",
        "permissions": {
            "allow": ["read"],
            "deny": [],
            "ask": [],
            "additionalDirectories": [],
        },
    }

    with override_dependency(get_settings_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings",
            json=payload,
        )

    assert response.status_code == 200
    assert len(service.updated) == 1
    assert service.updated[0][1].default_mode == PermissionMode.PLAN
    assert service.updated[0][2] == DocumentScope.PROJECT


def test_cset_005_update_settings_user(client):
    service = StubSettingsService(
        settings=_sample_settings(PermissionMode.ACCEPT_EDITS)
    )

    payload = {
        "defaultMode": "acceptEdits",
        "permissions": {
            "allow": ["*"],
            "deny": [],
            "ask": [],
            "additionalDirectories": [],
        },
    }

    with override_dependency(get_settings_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings",
            json=payload,
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert len(service.updated) == 1
    assert service.updated[0][2] == DocumentScope.USER


def test_cset_006_get_raw_settings(client):
    service = StubSettingsService(raw_content={"model": "claude-sonnet-5"})

    with override_dependency(get_settings_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/raw",
            params={"scope": "local"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "content": {"model": "claude-sonnet-5"},
        "revision": "raw-revision",
    }
    assert service.raw_reads == [(WORKSPACE_ID, DocumentScope.LOCAL)]


def test_cset_007_put_raw_settings(client):
    service = StubSettingsService()
    payload = {"content": {"env": {"DEBUG": "1"}, "unknownField": ["kept"]}}

    with override_dependency(get_settings_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/raw",
            params={"scope": "user"},
            json=payload,
        )

    assert response.status_code == 200
    assert response.json() == {**payload, "revision": "raw-revision"}
    assert service.raw_updates == [
        (WORKSPACE_ID, DocumentScope.USER, payload["content"], None)
    ]


def test_cset_008_raw_settings_missing_scope_returns_422(client):
    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/raw")

    assert response.status_code == 422


def test_cset_009_raw_settings_invalid_scope_returns_422(client):
    response = client.put(
        f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/raw",
        params={"scope": "plugin"},
        json={"content": {}},
    )

    assert response.status_code == 422


def test_cset_010_raw_settings_malformed_body_returns_422(client):
    response = client.put(
        f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/raw",
        params={"scope": "project"},
        json={"other": {}},
    )

    assert response.status_code == 422
