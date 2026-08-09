"""Claude Code Memory service tests"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.memory.models import (
    MemoryCreateRequest,
    MemoryUpdateRequest,
)
from app.modules.claude_code.memory.documents import MemoryService


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    return tmp_path / "memory"


@pytest.fixture
def service(memory_dir: Path) -> MemoryService:
    return MemoryService(memory_dir=memory_dir)


def test_list_documents_returns_empty_collection_when_directory_missing(
    service: MemoryService,
) -> None:
    result = service.list_documents("ws-1")

    assert result.workspace_id == "ws-1"
    assert result.items == []
    assert [(scope.scope, scope.read_only) for scope in result.available_scopes] == [
        (DocumentScope.PROJECT, False),
        (DocumentScope.USER, False),
    ]


def test_list_documents_ignores_non_markdown_files(
    service: MemoryService, memory_dir: Path
) -> None:
    project_dir = memory_dir / "project"
    project_dir.mkdir(parents=True)
    (project_dir / "note.md").write_text("# Note", encoding="utf-8")
    (project_dir / "ignore.txt").write_text("ignore", encoding="utf-8")

    result = service.list_documents("ws-1")

    assert [doc.path for doc in result.items] == ["note.md"]
    assert result.items[0].scope == DocumentScope.PROJECT


def test_create_document_normalizes_markdown_extension(
    service: MemoryService, memory_dir: Path
) -> None:
    result = service.create_document(
        "ws-1",
        DocumentScope.USER,
        MemoryCreateRequest(
            path="notes/today", content="# Today", revision=compute_revision("{}")
        ),
    )

    assert result.resource["path"] == "notes/today.md"
    assert result.revision == compute_revision("# Today")
    assert (memory_dir / "user" / "notes" / "today.md").read_text(
        encoding="utf-8"
    ) == "# Today"


def test_create_document_rejects_unsafe_paths(service: MemoryService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        service.create_document(
            "ws-1",
            DocumentScope.USER,
            MemoryCreateRequest(
                path="../today.md", content="# Nope", revision=compute_revision("{}")
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["errorCode"] == "INVALID_MEMORY_PATH"


def test_get_update_and_delete_document(
    service: MemoryService, memory_dir: Path
) -> None:
    target = memory_dir / "project" / "notes" / "today.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Today", encoding="utf-8")

    get_result = service.get_document("ws-1", DocumentScope.PROJECT, "notes/today.md")
    assert get_result.resource["content"] == "# Today"
    assert get_result.revision == compute_revision("# Today")

    update_result = service.update_document(
        "ws-1",
        DocumentScope.PROJECT,
        MemoryUpdateRequest(
            path="notes/today.md",
            content="# Updated",
            revision=compute_revision("# Today"),
        ),
    )
    assert update_result.resource["content"] == "# Updated"
    assert target.read_text(encoding="utf-8") == "# Updated"

    delete_result = service.delete_document(
        "ws-1",
        DocumentScope.PROJECT,
        "notes/today.md",
        compute_revision("# Updated"),
    )
    assert delete_result.resource["deleted"] is True
    assert not target.exists()


def test_same_name_across_directories_is_addressed_by_path(
    service: MemoryService,
) -> None:
    first = service.create_document(
        "ws-1",
        DocumentScope.PROJECT,
        MemoryCreateRequest(
            path="git/context.md", content="# Git", revision=compute_revision("{}")
        ),
    )
    second = service.create_document(
        "ws-1",
        DocumentScope.PROJECT,
        MemoryCreateRequest(
            path="hg/context.md",
            content="# Hg",
            revision=service.list_documents("ws-1").revision,
        ),
    )

    assert (
        service.get_document("ws-1", DocumentScope.PROJECT, "git/context.md").resource[
            "content"
        ]
        == first.resource["content"]
    )
    assert (
        service.get_document("ws-1", DocumentScope.PROJECT, "hg/context.md").resource[
            "content"
        ]
        == second.resource["content"]
    )


def test_update_rejects_stale_revision(service: MemoryService) -> None:
    created = service.create_document(
        "ws-1",
        DocumentScope.USER,
        MemoryCreateRequest(
            path="today.md", content="# Today", revision=compute_revision("{}")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.update_document(
            "ws-1",
            DocumentScope.USER,
            MemoryUpdateRequest(
                path="today.md",
                content="# Changed",
                revision=compute_revision("stale"),
            ),
        )

    assert created.revision == compute_revision("# Today")
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"


def test_get_document_not_found_raises_404(service: MemoryService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        service.get_document("ws-1", DocumentScope.USER, "missing.md")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["errorCode"] == "404_NOT_FOUND"
