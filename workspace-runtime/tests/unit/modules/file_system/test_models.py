from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.file_system.models import (
    FileContentResponse,
    FileCreateRequest,
    FileNode,
    FileTreeRequest,
    FileTreeResponse,
    UploadResponse,
    UploadResult,
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


def test_file_tree_request_validates_depth_range() -> None:
    with pytest.raises(ValidationError):
        FileTreeRequest(maxDepth=0)

    request = FileTreeRequest(maxDepth=3)
    assert request.maxDepth == 3


def test_file_create_request_supports_base64_encoding() -> None:
    request = FileCreateRequest(path="demo.txt", type="file", encoding="base64")

    assert request.encoding == "base64"


def test_file_content_response_and_upload_response_defaults() -> None:
    content = FileContentResponse(
        path="README.md",
        content="# Demo",
        size=6,
        updatedAt="2026-03-28T00:00:00Z",
    )
    upload = UploadResponse(
        uploaded=[
            UploadResult(
                path="README.md",
                size=6,
                lastModified="2026-03-28T00:00:00Z",
            )
        ]
    )

    assert content.versionId is None
    assert upload.skipped == []
