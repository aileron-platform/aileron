"""Claude Code API test cases - Slash Commands"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.slash_commands.dependencies import get_slash_command_service
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandDeleteResponse,
    SlashCommandDocumentDetail,
    SlashCommandDocumentResponse,
    SlashCommandDocumentSummary,
    SlashCommandScopeGroup,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)

from .helpers import WORKSPACE_ID, override_dependency


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
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> SlashCommandDocumentResponse:
        if self.document_error:
            raise self.document_error
        assert self.document_result is not None
        return self.document_result

    def create_document(
        self, workspace_id: str, scope: DocumentScope, payload: SlashCommandCreateRequest
    ) -> SlashCommandDocumentResponse:
        if self.create_error:
            raise self.create_error
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: SlashCommandUpdateRequest,
    ) -> SlashCommandDocumentResponse:
        if self.update_error:
            raise self.update_error
        assert self.update_result is not None
        return self.update_result

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> None:
        if self.delete_error:
            raise self.delete_error


def test_sc_001_list_scopes(client):
    service = StubSlashCommandService(
        list_result=SlashCommandScopesResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                SlashCommandScopeGroup(
                    scope=DocumentScope.PROJECT,
                    documents=[
                        SlashCommandDocumentSummary(
                            fileName="deploy.md",
                            description="Deployment command",
                            scope=DocumentScope.PROJECT,
                            size="1KB",
                        )
                    ],
                )
            ],
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands"
        )

    assert response.status_code == 200
    assert response.json()["scopes"][0]["scope"] == "project"


def test_sc_002_list_filtered_scope(client):
    service = StubSlashCommandService(
        list_result=SlashCommandScopesResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                SlashCommandScopeGroup(
                    scope=DocumentScope.USER,
                    documents=[
                        SlashCommandDocumentSummary(
                            fileName="user-cmd.md",
                            description="User command",
                            scope=DocumentScope.USER,
                            size="2KB",
                        )
                    ],
                )
            ],
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert len(response.json()["scopes"]) == 1
    assert response.json()["scopes"][0]["scope"] == "user"


def test_sc_003_get_scope_success(client):
    service = StubSlashCommandService(
        scope_result=SlashCommandScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            documents=[
                SlashCommandDocumentSummary(
                    fileName="build.md",
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
    with override_dependency(get_slash_command_service, lambda: StubSlashCommandService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local"
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"


def test_sc_005_get_document_success(client):
    service = StubSlashCommandService(
        document_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SlashCommandDocumentDetail(
                fileName="build.md",
                description="Build command",
                scope=DocumentScope.PROJECT,
                size="1KB",
                content="# Build Command\n\nThis is a build command.",
            ),
        )
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/build.md"
        )

    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "build.md"


def test_sc_006_get_document_not_found(client):
    from fastapi import HTTPException

    service = StubSlashCommandService(
        document_error=HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "File not found"})
    )

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/missing.md"
        )

    assert response.status_code == 404


def test_sc_007_create_success(client):
    service = StubSlashCommandService(
        create_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SlashCommandDocumentDetail(
                fileName="new-cmd.md",
                description="New command",
                scope=DocumentScope.PROJECT,
                size="1KB",
                content="# New Command\n\nContent here.",
            ),
        )
    )

    payload = {
        "fileName": "new-cmd.md",
        "content": "# New Command\n\nContent here.",
        "description": "New command",
    }

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project",
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["document"]["fileName"] == "new-cmd.md"


def test_sc_008_create_invalid_scope(client):
    with override_dependency(get_slash_command_service, lambda: StubSlashCommandService()):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local",
            json={"fileName": "test.md", "content": "# Test"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"


def test_sc_009_create_readonly_scope(client):
    with override_dependency(get_slash_command_service, lambda: StubSlashCommandService()):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/plugin",
            json={"fileName": "test.md", "content": "# Test"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "SCOPE_READ_ONLY"


def test_sc_010_update_success(client):
    service = StubSlashCommandService(
        update_result=SlashCommandDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SlashCommandDocumentDetail(
                fileName="existing.md",
                description="Updated command",
                scope=DocumentScope.PROJECT,
                size="2KB",
                content="# Updated Command\n\nNew content.",
            ),
        )
    )

    payload = {
        "content": "# Updated Command\n\nNew content.",
        "description": "Updated command",
    }

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/existing.md",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "existing.md"


def test_sc_011_delete_success(client):
    service = StubSlashCommandService()

    with override_dependency(get_slash_command_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/project/to-delete.md"
        )

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_sc_012_delete_invalid_scope(client):
    with override_dependency(get_slash_command_service, lambda: StubSlashCommandService()):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/slash-commands/local/test.md"
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"
