from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.file_system.models import (
    FileContentResponse,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileExtractExecutionRequest,
    FileCreateRequest,
    FileNode,
    FileTreeRequest,
    FileTreeResponse,
)


def test_file_node_and_tree_response_round_trip() -> None:
    node = FileNode(
        id="src/main.py",
        name="main.py",
        path="src/main.py",
        type="file",
        updatedAt="2026-03-28T00:00:00Z",
        extension=".py",
        fileType="python",
    )
    response = FileTreeResponse(path="/", nodes=[node], total=1)

    assert response.total == 1
    assert response.nodes[0].extension == ".py"
    assert response.model_dump()["nodes"][0]["fileType"] == "python"


def test_file_tree_response_fills_missing_node_ids_from_paths() -> None:
    response = FileTreeResponse(
        path="/",
        nodes=[
            {
                "name": "src",
                "path": "/src",
                "type": "directory",
                "updatedAt": "2026-03-28T00:00:00Z",
                "children": [
                    {
                        "name": "main.py",
                        "path": "/src/main.py",
                        "type": "file",
                        "updatedAt": "2026-03-28T00:00:00Z",
                    }
                ],
            }
        ],
        total=1,
    )

    assert response.nodes[0].id == "/src"
    assert response.nodes[0].children[0].id == "/src/main.py"


def test_file_tree_request_validates_depth_range() -> None:
    with pytest.raises(ValidationError):
        FileTreeRequest(maxDepth=0)

    request = FileTreeRequest(maxDepth=3)
    assert request.maxDepth == 3


def test_file_create_request_supports_base64_encoding() -> None:
    request = FileCreateRequest(path="demo.txt", type="file", encoding="base64")

    assert request.encoding == "base64"


def test_file_content_response_and_conflict_contracts_are_exact() -> None:
    content = FileContentResponse(
        path="README.md",
        content="# Demo",
        size=6,
        updatedAt="2026-03-28T00:00:00Z",
    )
    assert content.revision is None
    assert set(FileConflictPreflightRequest.model_fields) == {
        "operation",
        "targetPath",
        "sources",
        "archivePath",
    }
    assert set(FileConflictExecutionRequest.model_fields) == {
        "targetPath",
        "sources",
        "defaultStrategy",
        "resolutions",
    }
    assert set(FileExtractExecutionRequest.model_fields) == {
        "archivePath",
        "targetPath",
        "defaultStrategy",
        "resolutions",
    }
    assert set(FileConflictBatchResult.model_fields) == {
        "items",
        "total",
        "succeeded",
        "skipped",
        "failed",
    }


def test_conflict_execution_rejects_legacy_and_missing_fields() -> None:
    with pytest.raises(ValidationError):
        FileConflictExecutionRequest.model_validate(
            {
                "targetPath": "/target",
                "sources": [{"sourcePath": "/a", "entryType": "file"}],
                "conflictStrategy": "rename",
            }
        )

    with pytest.raises(ValidationError):
        FileExtractExecutionRequest.model_validate(
            {
                "archivePath": "/archive.zip",
                "targetPath": "/target",
                "defaultStrategy": "overwrite",
                "resolutions": [],
            }
        )
