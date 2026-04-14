"""Claude Code API 測試案例 - Hooks"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.hooks.dependencies import get_hook_service
from app.modules.claude_code.hooks.models import (
    HookDeleteResponse,
    HookExportResponse,
    HookImportRequest,
    HookImportResponse,
    HookScopeDocument,
    HookScopeResponse,
    HookScopeUpsertRequest,
    HookScopesResponse,
)

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubHookService:
    list_result: Optional[HookScopesResponse] = None
    export_result: Optional[HookExportResponse] = None
    scope_result: Optional[HookScopeResponse] = None
    update_result: Optional[HookScopeResponse] = None
    delete_result: Optional[HookDeleteResponse] = None
    import_result: Optional[HookImportResponse] = None

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None
    ) -> HookScopesResponse:
        assert self.list_result is not None
        return self.list_result

    def export_scopes(
        self, workspace_id: str, scope_filter: Iterable[DocumentScope] | None
    ) -> HookExportResponse:
        assert self.export_result is not None
        return self.export_result

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> HookScopeResponse:
        assert self.scope_result is not None
        return self.scope_result

    def update_scope(
        self, workspace_id: str, scope: DocumentScope, payload: HookScopeUpsertRequest
    ) -> HookScopeResponse:
        assert self.update_result is not None
        return self.update_result

    def delete_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> HookDeleteResponse:
        assert self.delete_result is not None
        return self.delete_result

    def import_scopes(
        self, workspace_id: str, payload: HookImportRequest
    ) -> HookImportResponse:
        assert self.import_result is not None
        return self.import_result


def test_hook_001_list_all_scopes(client):
    service = StubHookService(
        list_result=HookScopesResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                HookScopeDocument(
                    scope=DocumentScope.PROJECT,
                    hooks={},
                )
            ],
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks"
        )

    assert response.status_code == 200
    assert response.json()["scopes"][0]["scope"] == "project"


def test_hook_002_filter_scope(client):
    service = StubHookService(
        list_result=HookScopesResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                HookScopeDocument(
                    scope=DocumentScope.USER,
                    hooks={},
                )
            ],
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert response.json()["scopes"][0]["scope"] == "user"


def test_hook_003_export_hooks(client):
    from datetime import datetime, timezone

    service = StubHookService(
        export_result=HookExportResponse(
            workspaceId=WORKSPACE_ID,
            exportedAt=datetime.now(timezone.utc),
            scopes=[],
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks/export"
        )

    assert response.status_code == 200
    assert response.json()["workspaceId"] == WORKSPACE_ID


def test_hook_004_get_scope(client):
    service = StubHookService(
        scope_result=HookScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            hooks={},
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks/project"
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"


def test_hook_005_update_scope(client):
    service = StubHookService(
        update_result=HookScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            hooks={},
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks/project",
            json={"hooks": {}},
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"


def test_hook_006_delete_scope(client):
    from datetime import datetime, timezone

    service = StubHookService(
        delete_result=HookDeleteResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            deleted=True,
            deletedAt=datetime.now(timezone.utc),
        )
    )

    with override_dependency(get_hook_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks/project"
        )

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_hook_007_import_hooks(client):
    from app.modules.claude_code.hooks.models import HookImportMode

    service = StubHookService(
        import_result=HookImportResponse(
            workspaceId=WORKSPACE_ID,
            mode=HookImportMode.MERGE,
            imported=1,
            updated=0,
            skipped=0,
        )
    )

    payload = {
        "mode": "merge",
        "scopes": [
            {
                "scope": "project",
                "hooks": {},
            }
        ],
    }

    with override_dependency(get_hook_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/hooks/import",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
