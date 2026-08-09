"""Claude Code API test cases - Memory"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.memory.dependencies import get_memory_service
from app.modules.claude_code.memory.models import (
    MemoryCollectionResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryDocumentDetail,
    MemoryDocumentResponse,
    MemoryDocumentSummary,
    MemoryUpdateRequest,
)

from .dependency_overrides import WORKSPACE_ID, override_dependency


@dataclass
class StubMemoryService:
    list_result: Optional[MemoryCollectionResponse] = None
    document_result: Optional[MemoryDocumentResponse] = None
    create_result: Optional[MemoryDocumentResponse] = None
    update_result: Optional[MemoryDocumentResponse] = None
    delete_result: Optional[MemoryDeleteResponse] = None
    document_error: Optional[Exception] = None

    def list_documents(self, workspace_id: str) -> MemoryCollectionResponse:
        assert self.list_result is not None
        return self.list_result

    def get_document(
        self, workspace_id: str, scope: DocumentScope, path: str
    ) -> MemoryDocumentResponse:
        if self.document_error:
            raise self.document_error
        assert self.document_result is not None
        return self.document_result

    def create_document(
        self, workspace_id: str, scope: DocumentScope, payload: MemoryCreateRequest
    ) -> MemoryDocumentResponse:
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self, workspace_id: str, scope: DocumentScope, payload: MemoryUpdateRequest
    ) -> MemoryDocumentResponse:
        assert self.update_result is not None
        return self.update_result

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, path: str, revision: str
    ) -> MemoryDeleteResponse:
        assert self.delete_result is not None
        return self.delete_result


def test_memory_list_documents(client):
    service = StubMemoryService(
        list_result=MemoryCollectionResponse(
            workspaceId=WORKSPACE_ID,
            revision=compute_revision("{}"),
            items=[
                MemoryDocumentSummary(
                    path="notes/today.md",
                    scope=DocumentScope.USER,
                    name="today",
                    description="daily notes",
                    size="1KB",
                )
            ],
            availableScopes=[
                {"scope": "project", "readOnly": False},
                {"scope": "user", "readOnly": False},
            ],
        )
    )

    with override_dependency(get_memory_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory")

    assert response.status_code == 200
    assert response.json()["items"][0]["path"] == "notes/today.md"
    assert response.json()["items"][0]["scope"] == "user"
    assert response.json()["availableScopes"] == [
        {"scope": "project", "readOnly": False},
        {"scope": "user", "readOnly": False},
    ]


def test_memory_crud_endpoints(client):
    detail = MemoryDocumentDetail(
        path="notes/today.md",
        scope=DocumentScope.USER,
        name="today",
        description="daily notes",
        size="1KB",
        content="# Today",
    )
    revision = compute_revision("# Today")
    service = StubMemoryService(
        document_result=MemoryDocumentResponse(
            revision=revision, resource=detail.model_dump(by_alias=True)
        ),
        create_result=MemoryDocumentResponse(
            revision=revision, resource=detail.model_dump(by_alias=True)
        ),
        update_result=MemoryDocumentResponse(
            revision=revision, resource=detail.model_dump(by_alias=True)
        ),
        delete_result=MemoryDeleteResponse(
            revision=compute_revision("{}"),
            resource={"path": "notes/today.md", "deleted": True},
        ),
    )

    with override_dependency(get_memory_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user/content",
            params={"path": "notes/today.md"},
        )
        assert response.status_code == 200
        assert response.json()["revision"] == revision
        assert response.json()["resource"]["path"] == "notes/today.md"

        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user",
            json={
                "path": "notes/today.md",
                "content": "# Today",
                "revision": compute_revision("{}"),
            },
        )
        assert response.status_code == 200

        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user/content",
            json={"path": "notes/today.md", "content": "# Today", "revision": revision},
        )
        assert response.status_code == 200

        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user/content",
            params={"path": "notes/today.md", "revision": revision},
        )
        assert response.status_code == 200
        assert response.json()["resource"]["deleted"] is True

        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/today.md"
        )
        assert response.status_code == 403
        assert response.json()["detail"]["errorCode"] == (
            "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
        )

        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user/content",
            json={"path": "notes/today.md", "content": "# Today"},
        )
        assert response.status_code == 422


def test_memory_error_envelope(client):
    service = StubMemoryService(
        document_error=HTTPException(
            status_code=404,
            detail={"errorCode": "404_NOT_FOUND", "message": "Memory file not found"},
        )
    )

    with override_dependency(get_memory_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/user/content",
            params={"path": "missing.md"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "errorCode": "404_NOT_FOUND",
        "message": "Memory file not found",
    }
