"""Claude Code API test cases - Subagents"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.subagents.dependencies import get_subagent_service
from app.modules.claude_code.subagents.models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocument,
    SubagentDocumentResponse,
    SubagentScopeGroup,
    SubagentScopeResponse,
    SubagentSummary,
    SubagentUpdateRequest,
)

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubSubagentService:
    list_result: Optional[SubagentCollectionResponse] = None
    scope_result: Optional[SubagentScopeResponse] = None
    document_result: Optional[SubagentDocumentResponse] = None
    create_result: Optional[SubagentDocumentResponse] = None
    update_result: Optional[SubagentDocumentResponse] = None
    delete_result: Optional[SubagentDeleteResponse] = None
    list_error: Optional[Exception] = None
    scope_error: Optional[Exception] = None
    document_error: Optional[Exception] = None
    create_error: Optional[Exception] = None
    update_error: Optional[Exception] = None
    delete_error: Optional[Exception] = None

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None
    ) -> SubagentCollectionResponse:
        if self.list_error:
            raise self.list_error
        assert self.list_result is not None
        return self.list_result

    def get_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> SubagentScopeResponse:
        if self.scope_error:
            raise self.scope_error
        assert self.scope_result is not None
        return self.scope_result

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> SubagentDocumentResponse:
        if self.document_error:
            raise self.document_error
        assert self.document_result is not None
        return self.document_result

    def create_document(
        self, workspace_id: str, scope: DocumentScope, payload: SubagentCreateRequest
    ) -> SubagentDocumentResponse:
        if self.create_error:
            raise self.create_error
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: SubagentUpdateRequest,
    ) -> SubagentDocumentResponse:
        if self.update_error:
            raise self.update_error
        assert self.update_result is not None
        return self.update_result

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> None:
        if self.delete_error:
            raise self.delete_error


def test_sa_001_list_scopes(client):
    service = StubSubagentService(
        list_result=SubagentCollectionResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                SubagentScopeGroup(
                    scope=DocumentScope.PROJECT,
                    documents=[
                        SubagentSummary(
                            fileName="qa.json",
                            name="QA Subagent",
                            description="Quality check subagent",
                            scope=DocumentScope.PROJECT,
                            size="2KB",
                        )
                    ],
                )
            ],
        )
    )

    with override_dependency(get_subagent_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents"
        )

    assert response.status_code == 200
    assert response.json()["scopes"][0]["scope"] == "project"


def test_sa_002_list_filtered_scope(client):
    service = StubSubagentService(
        list_result=SubagentCollectionResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                SubagentScopeGroup(
                    scope=DocumentScope.USER,
                    documents=[
                        SubagentSummary(
                            fileName="reviewer.json",
                            name="Code Reviewer",
                            description="Code review subagent",
                            scope=DocumentScope.USER,
                            size="3KB",
                        )
                    ],
                )
            ],
        )
    )

    with override_dependency(get_subagent_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    assert len(response.json()["scopes"]) == 1
    assert response.json()["scopes"][0]["scope"] == "user"


def test_sa_003_get_scope_success(client):
    service = StubSubagentService(
        scope_result=SubagentScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            documents=[
                SubagentSummary(
                    fileName="analyzer.json",
                    name="Analyzer",
                    description="Code analysis subagent",
                    scope=DocumentScope.PROJECT,
                    size="1KB",
                )
            ],
        )
    )

    with override_dependency(get_subagent_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project"
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"
    assert len(response.json()["documents"]) == 1


def test_sa_004_get_scope_invalid_scope(client):
    with override_dependency(get_subagent_service, lambda: StubSubagentService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/local"
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"


def test_sa_005_get_document_success(client):
    service = StubSubagentService(
        document_result=SubagentDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SubagentDocument(
                fileName="analyzer.json",
                name="Analyzer",
                description="Code analysis subagent",
                scope=DocumentScope.PROJECT,
                size="1KB",
                content='{"name": "Analyzer", "description": "Code analysis subagent"}',
            ),
        )
    )

    with override_dependency(get_subagent_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project/analyzer.json"
        )

    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "analyzer.json"


def test_sa_006_get_document_not_found(client):
    from fastapi import HTTPException

    service = StubSubagentService(
        document_error=HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "File not found"})
    )

    with override_dependency(get_subagent_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project/missing.json"
        )

    assert response.status_code == 404


def test_sa_007_create_success(client):
    service = StubSubagentService(
        create_result=SubagentDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SubagentDocument(
                fileName="new-subagent.json",
                name="New Subagent",
                description="New subagent",
                scope=DocumentScope.PROJECT,
                size="2KB",
                content='{"name": "New Subagent", "description": "A new subagent"}',
            ),
        )
    )

    payload = {
        "fileName": "new-subagent.json",
        "content": '{"name": "New Subagent", "description": "A new subagent"}',
        "name": "New Subagent",
        "description": "New subagent",
    }

    with override_dependency(get_subagent_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project",
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["document"]["fileName"] == "new-subagent.json"


def test_sa_008_create_invalid_scope(client):
    with override_dependency(get_subagent_service, lambda: StubSubagentService()):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/local",
            json={"fileName": "test.json", "content": "{}"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"


def test_sa_009_create_readonly_scope(client):
    with override_dependency(get_subagent_service, lambda: StubSubagentService()):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/plugin",
            json={"fileName": "test.json", "content": "{}"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "SCOPE_READ_ONLY"


def test_sa_010_update_success(client):
    service = StubSubagentService(
        update_result=SubagentDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=SubagentDocument(
                fileName="existing.json",
                name="Updated Subagent",
                description="Updated subagent",
                scope=DocumentScope.PROJECT,
                size="3KB",
                content='{"name": "Updated Subagent", "enabled": false}',
            ),
        )
    )

    payload = {
        "content": '{"name": "Updated Subagent", "enabled": false}',
        "name": "Updated Subagent",
        "description": "Updated subagent",
    }

    with override_dependency(get_subagent_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project/existing.json",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "existing.json"


def test_sa_011_delete_success(client):
    service = StubSubagentService()

    with override_dependency(get_subagent_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/project/to-delete.json"
        )

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_sa_012_delete_invalid_scope(client):
    with override_dependency(get_subagent_service, lambda: StubSubagentService()):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/subagents/local/test.json"
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"
