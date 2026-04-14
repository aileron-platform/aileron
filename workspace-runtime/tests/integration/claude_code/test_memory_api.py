"""Claude Code API 測試案例 - Memory"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubMemoryService:
    list_result: Optional[MemoryCollectionResponse] = None
    document_result: Optional[MemoryDocumentResponse] = None
    create_result: Optional[MemoryDocumentResponse] = None
    update_result: Optional[MemoryDocumentResponse] = None
    delete_result: Optional[MemoryDeleteResponse] = None

    def list_documents(self, workspace_id: str) -> MemoryCollectionResponse:
        assert self.list_result is not None
        return self.list_result

    def get_document(self, workspace_id: str, file_name: str) -> MemoryDocumentResponse:
        assert self.document_result is not None
        return self.document_result

    def create_document(self, workspace_id: str, payload: MemoryCreateRequest) -> MemoryDocumentResponse:
        assert self.create_result is not None
        return self.create_result

    def update_document(
        self, workspace_id: str, file_name: str, payload: MemoryUpdateRequest
    ) -> MemoryDocumentResponse:
        assert self.update_result is not None
        return self.update_result

    def delete_document(self, workspace_id: str, file_name: str) -> MemoryDeleteResponse:
        assert self.delete_result is not None
        return self.delete_result


def test_memory_list_documents(client):
    service = StubMemoryService(
        list_result=MemoryCollectionResponse(
            workspaceId=WORKSPACE_ID,
            documents=[
                MemoryDocumentSummary(
                    fileName="today.md",
                    name="today",
                    description="daily notes",
                    size="1KB",
                )
            ],
        )
    )

    with override_dependency(get_memory_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory")

    assert response.status_code == 200
    assert response.json()["documents"][0]["fileName"] == "today.md"


def test_memory_crud_endpoints(client):
    detail = MemoryDocumentDetail(
        fileName="today.md",
        name="today",
        description="daily notes",
        size="1KB",
        content="# Today",
    )
    service = StubMemoryService(
        document_result=MemoryDocumentResponse(workspaceId=WORKSPACE_ID, document=detail),
        create_result=MemoryDocumentResponse(workspaceId=WORKSPACE_ID, document=detail),
        update_result=MemoryDocumentResponse(workspaceId=WORKSPACE_ID, document=detail),
        delete_result=MemoryDeleteResponse(workspaceId=WORKSPACE_ID, fileName="today.md", deleted=True),
    )

    with override_dependency(get_memory_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/today.md")
        assert response.status_code == 200

        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory",
            json={"fileName": "today.md", "content": "# Today"},
        )
        assert response.status_code == 200

        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/today.md",
            json={"content": "# Today"},
        )
        assert response.status_code == 200

        response = client.delete(f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/memory/today.md")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
