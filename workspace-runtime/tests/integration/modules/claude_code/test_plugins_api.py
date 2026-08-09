"""Claude Code plugin API tests."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.modules.claude_code.plugins.catalog import get_claude_plugins_service

from .dependency_overrides import WORKSPACE_ID, override_dependency


class StubPluginsService:
    def get_plugin_detail(self, workspace_id: str, plugin_id: str):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id},
        )


def test_claude_plugin_detail_uses_unified_error_envelope(client):
    with override_dependency(get_claude_plugins_service, lambda: StubPluginsService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/plugins/missing@local"
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == {
        "errorCode": "PLUGIN_NOT_FOUND",
        "message": "missing@local",
    }
