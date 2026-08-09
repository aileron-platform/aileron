from pathlib import Path

import pytest

from aileron_file_core import PathOutsideRootError, snapshot_file


def test_snapshot_file_copies_content_to_snapshot_root(tmp_path: Path) -> None:
    source = tmp_path / "repo" / "docs" / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("important", encoding="utf-8")
    snapshot_root = tmp_path / "history"

    result = snapshot_file(
        source_path=source,
        resource_id="workspace-1",
        relative_path="docs/note.md",
        operation="write",
        snapshot_root=snapshot_root,
    )

    assert result.snapshot_path.exists()
    assert result.snapshot_path.read_text(encoding="utf-8") == "important"
    assert result.size == len("important")
    assert result.operation == "write"


@pytest.mark.parametrize(
    "relative_path",
    [
        "/tmp/evil.txt",
        "../../outside.txt",
        "..\\..\\outside.txt",
    ],
)
def test_snapshot_file_rejects_unsafe_relative_path(
    tmp_path: Path,
    relative_path: str,
) -> None:
    source = tmp_path / "repo" / "docs" / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("important", encoding="utf-8")

    with pytest.raises(PathOutsideRootError) as exc_info:
        snapshot_file(
            source_path=source,
            resource_id="workspace-1",
            relative_path=relative_path,
            operation="write",
            snapshot_root=tmp_path / "history",
        )

    assert exc_info.value.path == relative_path


@pytest.mark.parametrize(
    "resource_id",
    [
        "",
        ".",
        "..",
        "../workspace",
        "workspace/one",
        "workspace\\one",
    ],
)
def test_snapshot_file_rejects_unsafe_resource_id(
    tmp_path: Path,
    resource_id: str,
) -> None:
    source = tmp_path / "repo" / "docs" / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("important", encoding="utf-8")

    with pytest.raises(PathOutsideRootError) as exc_info:
        snapshot_file(
            source_path=source,
            resource_id=resource_id,
            relative_path="docs/note.md",
            operation="write",
            snapshot_root=tmp_path / "history",
        )

    assert exc_info.value.path == resource_id
