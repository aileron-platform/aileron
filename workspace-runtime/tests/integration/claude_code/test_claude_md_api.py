"""Claude Code API 測試案例 - Claude.md"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from app.modules.claude_code.claude_md.dependencies import get_claude_md_service
from app.modules.claude_code.claude_md.models import (
    ClaudeMdDocument,
    ClaudeMdScope,
    ClaudeMdUpdateRequest,
    ClaudeMdUpdateResponse,
)

from .helpers import WORKSPACE_ID, override_dependency


class StubClaudeMdService:
    def __init__(self) -> None:
        self.get_document_call: Optional[tuple[str, ClaudeMdScope]] = None
        self.update_request: Optional[tuple[str, ClaudeMdUpdateRequest]] = None
        self.document: Optional[ClaudeMdDocument] = None
        self.update_response: Optional[ClaudeMdUpdateResponse] = None
        self.get_error: Optional[Exception] = None
        self.update_error: Optional[Exception] = None

    def get_document(self, workspace_id: str, scope: ClaudeMdScope) -> ClaudeMdDocument:
        self.get_document_call = (workspace_id, scope)
        if self.get_error:
            raise self.get_error
        assert self.document is not None
        return self.document

    def update_document(
        self, workspace_id: str, payload: ClaudeMdUpdateRequest
    ) -> ClaudeMdUpdateResponse:
        self.update_request = (workspace_id, payload)
        if self.update_error:
            raise self.update_error
        assert self.update_response is not None
        return self.update_response


def test_cmd_001_get_claude_md_success(client):
    service = StubClaudeMdService()
    service.document = ClaudeMdDocument(
        workspaceId=WORKSPACE_ID, scope=ClaudeMdScope.PROJECT, content="# Claude"
    )

    with override_dependency(get_claude_md_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/claude-md",
            params={"scope": ClaudeMdScope.PROJECT.value},
        )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["content"] == "# Claude"
    assert payload["scope"] == "project"


def test_cmd_002_get_claude_md_not_found(client):
    service = StubClaudeMdService()
    service.get_error = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "404_NOT_FOUND", "message": "missing"},
    )

    with override_dependency(get_claude_md_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/claude-md",
            params={"scope": ClaudeMdScope.PROJECT.value},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"]["error"] == "404_NOT_FOUND"


def test_cmd_003_update_claude_md_success(client):
    service = StubClaudeMdService()
    service.update_response = ClaudeMdUpdateResponse(
        workspaceId=WORKSPACE_ID, scope=ClaudeMdScope.PROJECT
    )

    with override_dependency(get_claude_md_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/claude-md",
            json={"scope": "project", "content": "# Updated"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["scope"] == "project"
    assert service.update_request is not None
    assert service.update_request[1].content == "# Updated"


def test_cmd_004_update_claude_md_line_limit(client):
    service = StubClaudeMdService()
    service.update_error = HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error": "MAX_LINES_EXCEEDED"},
    )

    with override_dependency(get_claude_md_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/claude-md",
            json={"scope": "project", "content": "too many"},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"]["error"] == "MAX_LINES_EXCEEDED"
