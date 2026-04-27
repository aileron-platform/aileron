"""Claude Code API test cases - Output Styles"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.output_styles.dependencies import get_output_style_service
from app.modules.claude_code.output_styles.models import (
    OutputStyleCollectionResponse,
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleDocument,
    OutputStyleDocumentResponse,
    OutputStyleScopeGroup,
    OutputStyleScopeResponse,
    OutputStyleSummary,
    OutputStyleUpdateRequest,
)

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubOutputStyleService:
    list_result: Optional[OutputStyleCollectionResponse] = None
    scope_result: Optional[OutputStyleScopeResponse] = None
    document_result: Optional[OutputStyleDocumentResponse] = None
    create_result: Optional[OutputStyleDocumentResponse] = None
    update_result: Optional[OutputStyleDocumentResponse] = None
    delete_result: Optional[OutputStyleDeleteResponse] = None

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> OutputStyleCollectionResponse:
        assert self.list_result is not None
        return self.list_result

    def get_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> OutputStyleScopeResponse:
        assert self.scope_result is not None
        return self.scope_result

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> OutputStyleDocumentResponse:
        assert self.document_result is not None
        return self.document_result

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: OutputStyleCreateRequest,
    ) -> OutputStyleDocumentResponse:
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: OutputStyleUpdateRequest,
    ) -> OutputStyleDocumentResponse:
        assert self.update_result is not None
        return self.update_result

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> OutputStyleDeleteResponse:
        assert self.delete_result is not None
        return self.delete_result


def test_os_001_list_scopes(client):
    service = StubOutputStyleService(
        list_result=OutputStyleCollectionResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                OutputStyleScopeGroup(
                    scope=DocumentScope.PROJECT,
                    documents=[
                        OutputStyleSummary(
                            fileName="markdown.json",
                            name=None,
                            description=None,
                            scope=DocumentScope.PROJECT,
                            size="100",
                        )
                    ],
                )
            ],
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles"
        )

    assert response.status_code == 200
    assert response.json()["scopes"][0]["scope"] == "project"


def test_os_002_get_scope(client):
    service = StubOutputStyleService(
        scope_result=OutputStyleScopeResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            documents=[
                OutputStyleSummary(
                    fileName="markdown.json",
                    name=None,
                    description=None,
                    scope=DocumentScope.PROJECT,
                    size="100",
                )
            ],
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/project"
        )

    assert response.status_code == 200
    assert response.json()["documents"][0]["fileName"] == "markdown.json"


def test_os_003_get_document(client):
    service = StubOutputStyleService(
        document_result=OutputStyleDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=OutputStyleDocument(
                fileName="markdown.json",
                name=None,
                description=None,
                scope=DocumentScope.PROJECT,
                size="100",
                content="{}",
            ),
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/project/markdown.json"
        )

    assert response.status_code == 200
    assert response.json()["document"]["content"] == "{}"


def test_os_004_document_not_found(client):
    from fastapi import HTTPException

    class ErrorService(StubOutputStyleService):
        def get_document(self, workspace_id: str, scope: DocumentScope, file_name: str):
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "File not found"})

    with override_dependency(get_output_style_service, lambda: ErrorService()):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/project/missing.json"
        )

    assert response.status_code == 404


def test_os_005_create_document(client):
    service = StubOutputStyleService(
        create_result=OutputStyleDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.USER,
            document=OutputStyleDocument(
                fileName="markdown.json",
                name=None,
                description=None,
                scope=DocumentScope.USER,
                size="100",
                content="{}",
            ),
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/user",
            json={"fileName": "markdown.json", "content": "{}"},
        )

    assert response.status_code == 201
    assert response.json()["document"]["fileName"] == "markdown.json"


def test_os_006_create_read_only_scope(client):
    with override_dependency(
        get_output_style_service, lambda: StubOutputStyleService()
    ):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/plugin",
            json={"fileName": "style.json", "content": "{}"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "SCOPE_READ_ONLY"


def test_os_007_update_document(client):
    service = StubOutputStyleService(
        update_result=OutputStyleDocumentResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            document=OutputStyleDocument(
                fileName="markdown.json",
                name=None,
                description=None,
                scope=DocumentScope.PROJECT,
                size="200",
                content='{"layout": "columns"}',
            ),
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/project/markdown.json",
            json={"content": '{"layout": "columns"}'},
        )

    assert response.status_code == 200
    assert response.json()["document"]["content"] == '{"layout": "columns"}'


def test_os_008_delete_document(client):
    service = StubOutputStyleService(
        delete_result=OutputStyleDeleteResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            fileName="markdown.json",
            deleted=True,
        )
    )

    with override_dependency(get_output_style_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/output-styles/project/markdown.json"
        )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
