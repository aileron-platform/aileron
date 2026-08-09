"""Claude Code API test cases - Slash Commands"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.slash_commands.dependencies import (
    get_slash_command_service,
)
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandDeleteResponse,
    SlashCommandDocumentDetail,
    SlashCommandDocumentResponse,
    SlashCommandDocumentSummary,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)

from .dependency_overrides import WORKSPACE_ID, override_dependency


REVISION = "test-revision"


@dataclass
class StubSlashCommandService:
    list_result: Optional[SlashCommandScopesResponse] = None
    scope_result: Optional[SlashCommandScopeResponse] = None
    document_result: Optional[SlashCommandDocumentResponse] = None
    create_result: Optional[SlashCommandDocumentResponse] = None
    update_result: Optional[SlashCommandDocumentResponse] = None
    delete_result: Optional[SlashCommandDeleteResponse] = None
    list_error: Optional[Exception] = None
    scope_error: Optional[Exception] = None
    document_error: Optional[Exception] = None
    create_error: Optional[Exception] = None
    update_error: Optional[Exception] = None
    delete_error: Optional[Exception] = None

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None
    ) -> SlashCommandScopesResponse:
        if self.list_error:
            raise self.list_error
        assert self.list_result is not None
        return self.list_result

    def get_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> SlashCommandScopeResponse:
        if self.scope_error:
            raise self.scope_error
        assert self.scope_result is not None
        return self.scope_result

    def get_document(
        self, workspace_id: str, scope: DocumentScope, path: str
    ) -> SlashCommandDocumentResponse:
        if self.document_error:
            raise self.document_error
        assert self.document_result is not None
        return self.document_result

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SlashCommandCreateRequest,
    ) -> SlashCommandDocumentResponse:
        if self.create_error:
            raise self.create_error
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SlashCommandUpdateRequest,
    ) -> SlashCommandDocumentResponse:
        if self.update_error:
            raise self.update_error
        assert self.update_result is not None
        return self.update_result

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, path: str, revision: str
    ) -> SlashCommandDeleteResponse:
        if self.delete_error:
            raise self.delete_error
        if self.delete_result is not None:
            return self.delete_result
        return SlashCommandDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            path=path,
            revision=REVISION,
            deleted=True,
        )


def test_sc_001_list_scopes(client):
    service = StubSlashCommandService(
        list_result=SlashCommandScopesResponse(
            workspaceId=WORKSPACE_ID,
            items=[
                SlashCommandDocumentSummary(
                    path="deploy.md",
                    description="Deployment command",
                    scope=DocumentScope.PROJECT,
                    size="1KB",
                )
            ],
            availableScopes=[{"scope": "project", "readOnly": False}],
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands"
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["scope"] == "project"
    assert response.json()["availableScopes"] == [
        {"scope": "project", "readOnly": False}
    ]


def test_sc_002_list_filtered_scope(client):
    service = StubSlashCommandService(
        list_result=SlashCommandScopesResponse(
            workspaceId=WORKSPACE_ID,
            items=[
                SlashCommandDocumentSummary(
                    path="user-cmd.md",
                    description="User command",
                    scope=DocumentScope.USER,
                    size="2KB",
                )
            ],
            availableScopes=[{"scope": "user", "readOnly": False}],
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["scope"] == "user"
    assert response.json()["availableScopes"] == [{"scope": "user", "readOnly": False}]


def test_sc_003_get_scope_success(client):
    service = StubSlashCommandService(
        scope_result=SlashCommandScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            revision=REVISION,
            documents=[
                SlashCommandDocumentSummary(
                    path="build.md",
                    description="Build command",
                    scope=DocumentScope.PROJECT,
                    size="3KB",
                )
            ],
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project"
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"
    assert len(response.json()["documents"]) == 1


def test_sc_004_get_scope_invalid_scope(client):
    with override_dependency(
        get_slash_command_service, lambda: StubSlashCommandService()
    ):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local"
        )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"


def test_sc_005_get_document_success(client):
    service = StubSlashCommandService(
        document_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            revision=REVISION,
            document=SlashCommandDocumentDetail(
                path="team/build.md",
                description="Build command",
                scope=DocumentScope.PROJECT,
                size="1KB",
                content="# Build Command\n\nThis is a build command.",
            ),
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/content",
            params={"path": "team/build.md"},
        )

    assert response.status_code == 200
    assert response.json()["document"]["path"] == "team/build.md"


def test_sc_006_get_document_not_found(client):
    from fastapi import HTTPException

    service = StubSlashCommandService(
        document_error=HTTPException(
            status_code=404,
            detail={"errorCode": "NOT_FOUND", "message": "File not found"},
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/content",
            params={"path": "missing.md"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "errorCode": "NOT_FOUND",
        "message": "File not found",
    }


def test_sc_007_create_success(client):
    service = StubSlashCommandService(
        create_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            revision=REVISION,
            document=SlashCommandDocumentDetail(
                path="team/new-cmd.md",
                description="New command",
                scope=DocumentScope.PROJECT,
                size="1KB",
                content="# New Command\n\nContent here.",
            ),
        )
    )

    payload = {
        "path": "team/new-cmd.md",
        "content": "# New Command\n\nContent here.",
        "description": "New command",
        "revision": REVISION,
    }

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project",
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["document"]["path"] == "team/new-cmd.md"


def test_sc_008_create_invalid_scope(client):
    with override_dependency(
        get_slash_command_service, lambda: StubSlashCommandService()
    ):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local",
            json={"path": "test.md", "content": "# Test", "revision": REVISION},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"


def test_sc_009_create_readonly_scope(client):
    with override_dependency(
        get_slash_command_service, lambda: StubSlashCommandService()
    ):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/plugin",
            json={"path": "test.md", "content": "# Test", "revision": REVISION},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == "SCOPE_READ_ONLY"


def test_sc_010_update_success(client):
    service = StubSlashCommandService(
        update_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            revision=REVISION,
            document=SlashCommandDocumentDetail(
                path="team/existing.md",
                description="Updated command",
                scope=DocumentScope.PROJECT,
                size="2KB",
                content="# Updated Command\n\nNew content.",
            ),
        )
    )

    payload = {
        "path": "team/existing.md",
        "content": "# Updated Command\n\nNew content.",
        "description": "Updated command",
        "revision": REVISION,
    }

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/content",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["document"]["path"] == "team/existing.md"


def test_sc_011_delete_success(client):
    service = StubSlashCommandService()

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/content",
            params={"path": "team/to-delete.md", "revision": REVISION},
        )

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_sc_012_delete_invalid_scope(client):
    with override_dependency(
        get_slash_command_service, lambda: StubSlashCommandService()
    ):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local/content",
            params={"path": "test.md", "revision": REVISION},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"
