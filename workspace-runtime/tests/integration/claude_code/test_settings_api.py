"""Claude Code API test cases - Settings"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.settings.dependencies import get_settings_service
from app.modules.claude_code.settings.models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    PermissionMode,
    PermissionRules,
)

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubSettingsService:
    settings: Optional[ClaudeCodeSettings] = None
    updated: list[tuple[str, ClaudeCodeSettingsUpdateRequest, DocumentScope]] = field(
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


def _sample_settings(mode: PermissionMode = PermissionMode.DEFAULT) -> ClaudeCodeSettings:
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
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings"
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "default"


def test_cset_002_get_scope_settings(client):
    service = StubSettingsService(settings=_sample_settings(PermissionMode.ACCEPT_EDITS))

    with override_dependency(get_settings_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "acceptEdits"


def test_cset_003_marketplaces_endpoint_removed(client):
    response = client.get(
        f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/settings/marketplaces"
    )

    assert response.status_code in {404, 405}


def test_cset_004_update_settings_project(client):
    service = StubSettingsService(settings=_sample_settings(PermissionMode.PLAN))

    payload = {
        "defaultMode": "plan",
        "permissions": {"allow": ["read"], "deny": [], "ask": [], "additionalDirectories": []},
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
    service = StubSettingsService(settings=_sample_settings(PermissionMode.ACCEPT_EDITS))

    payload = {
        "defaultMode": "acceptEdits",
        "permissions": {"allow": ["*"], "deny": [], "ask": [], "additionalDirectories": []},
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
