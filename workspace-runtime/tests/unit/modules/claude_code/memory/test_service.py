"""Claude Code Memory 服務測試"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.modules.claude_code.memory.models import MemoryCreateRequest, MemoryUpdateRequest
from app.modules.claude_code.memory.service import MemoryService


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    return tmp_path / "memory"


@pytest.fixture
def service(memory_dir: Path) -> MemoryService:
    return MemoryService(memory_dir=memory_dir)


def test_list_documents_returns_empty_collection_when_directory_missing(service: MemoryService) -> None:
    result = service.list_documents("ws-1")

    assert result.workspace_id == "ws-1"
    assert result.documents == []


def test_list_documents_ignores_non_markdown_files(service: MemoryService, memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True)
    (memory_dir / "note.md").write_text("# Note", encoding="utf-8")
    (memory_dir / "ignore.txt").write_text("ignore", encoding="utf-8")

    result = service.list_documents("ws-1")

    assert [doc.file_name for doc in result.documents] == ["note.md"]


def test_create_document_normalizes_markdown_extension(service: MemoryService, memory_dir: Path) -> None:
    result = service.create_document(
        "ws-1",
        MemoryCreateRequest(fileName="today", content="# Today"),
    )

    assert result.document.file_name == "today.md"
    assert (memory_dir / "today.md").read_text(encoding="utf-8") == "# Today"


def test_create_document_rejects_nested_paths(service: MemoryService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        service.create_document(
            "ws-1",
            MemoryCreateRequest(fileName="notes/today.md", content="# Nope"),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "INVALID_FILE_NAME"


def test_get_update_and_delete_document(service: MemoryService, memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True)
    target = memory_dir / "today.md"
    target.write_text("# Today", encoding="utf-8")

    get_result = service.get_document("ws-1", "today.md")
    assert get_result.document.content == "# Today"

    update_result = service.update_document(
        "ws-1",
        "today",
        MemoryUpdateRequest(content="# Updated"),
    )
    assert update_result.document.content == "# Updated"
    assert target.read_text(encoding="utf-8") == "# Updated"

    delete_result = service.delete_document("ws-1", "today.md")
    assert delete_result.deleted is True
    assert not target.exists()


def test_get_document_not_found_raises_404(service: MemoryService) -> None:
    with pytest.raises(HTTPException) as exc_info:
        service.get_document("ws-1", "missing.md")

    assert exc_info.value.status_code == 404
