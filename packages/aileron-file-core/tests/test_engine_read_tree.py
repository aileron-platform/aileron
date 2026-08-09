from pathlib import Path
from typing import Optional

import pytest

from aileron_file_core import FileCoreError
from aileron_file_core.adapters import RootedFileAdapter, StaticRootResolver
from aileron_file_core.engine import FileOperationEngine
from aileron_file_core.models import (
    FileLocator,
    ReadBytesRequest,
    ReadTextRequest,
    TreeRequest,
)
from aileron_file_core.policies import FilePolicy, FileReadPolicy, PathExclusionPolicy


def _engine(root: Path, policy: Optional[FilePolicy] = None) -> FileOperationEngine:
    return FileOperationEngine(
        adapter=RootedFileAdapter(
            root_resolver=StaticRootResolver(root),
            path_exclusion=PathExclusionPolicy.defaults(),
        ),
        policy=policy or FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
    )


def test_get_tree_scans_directory_and_excludes_generated_paths(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("hello", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("hidden", encoding="utf-8")

    tree = _engine(tmp_path).get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=2)
    )

    assert tree.total == 1
    assert tree.nodes[0].path == "docs"
    assert tree.nodes[0].has_children is True
    assert tree.nodes[0].children[0].path == "docs/readme.md"


def test_get_tree_missing_path_does_not_create_directory(tmp_path: Path) -> None:
    with pytest.raises(FileCoreError) as exc:
        _engine(tmp_path).get_tree(
            TreeRequest(locator=FileLocator("workspace", "w1"), path="missing")
        )

    assert exc.value.code == "FILE_NOT_FOUND"
    assert not (tmp_path / "missing").exists()


def test_get_tree_applies_adapter_exclusion_to_descendants(tmp_path: Path) -> None:
    (tmp_path / "visible").mkdir()
    (tmp_path / "visible" / "keep.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "visible" / ".blocked").mkdir()
    (tmp_path / "visible" / ".blocked" / "secret.txt").write_text(
        "hidden",
        encoding="utf-8",
    )

    engine = FileOperationEngine(
        adapter=RootedFileAdapter(
            root_resolver=StaticRootResolver(tmp_path),
            path_exclusion=PathExclusionPolicy.defaults(extra_names={".blocked"}),
        ),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
    )

    tree = engine.get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=3)
    )

    assert tree.nodes[0].path == "visible"
    assert [node.path for node in tree.nodes[0].children] == ["visible/keep.txt"]


def test_get_tree_has_children_ignores_excluded_descendants(tmp_path: Path) -> None:
    (tmp_path / "visible").mkdir()
    (tmp_path / "visible" / ".blocked").mkdir()
    (tmp_path / "visible" / ".blocked" / "secret.txt").write_text(
        "hidden",
        encoding="utf-8",
    )

    engine = FileOperationEngine(
        adapter=RootedFileAdapter(
            root_resolver=StaticRootResolver(tmp_path),
            path_exclusion=PathExclusionPolicy.defaults(extra_names={".blocked"}),
        ),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
    )

    tree = engine.get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=2)
    )

    assert tree.nodes[0].path == "visible"
    assert tree.nodes[0].children == ()
    assert tree.nodes[0].has_children is False


def test_get_tree_skips_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("hello", encoding="utf-8")
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)

    tree = _engine(tmp_path).get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=2)
    )

    assert [node.path for node in tree.nodes] == ["docs"]


def test_get_tree_has_children_ignores_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "escape").symlink_to(outside, target_is_directory=True)

    tree = _engine(tmp_path).get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=2)
    )

    assert tree.nodes[0].path == "docs"
    assert tree.nodes[0].children == ()
    assert tree.nodes[0].has_children is False


def test_get_tree_swallows_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    original_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == locked:
            raise PermissionError("denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    tree = _engine(tmp_path).get_tree(
        TreeRequest(locator=FileLocator("workspace", "w1"), path="/", max_depth=2)
    )

    assert tree.nodes[0].path == "locked"
    assert tree.nodes[0].children == ()


def test_read_text_returns_content_hash_version(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")

    content = _engine(tmp_path).read_text(
        ReadTextRequest(locator=FileLocator("workspace", "w1"), path="note.txt")
    )

    assert content.path == "note.txt"
    assert content.content == "hello"
    assert content.size == 5
    assert content.version_id
    assert content.content_hash == content.version_id


def test_read_text_binary_friendly_mode(tmp_path: Path) -> None:
    (tmp_path / "image.bin").write_bytes(b"\x00\xff\x00")
    engine = _engine(
        tmp_path,
        FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024,
            read_policy=FileReadPolicy(
                binary_mode="friendly-text",
                friendly_binary_message="Binary file cannot be displayed",
            ),
        ),
    )

    content = engine.read_text(
        ReadTextRequest(locator=FileLocator("workspace", "w1"), path="image.bin")
    )

    assert content.readable is False
    assert content.content == "Binary file cannot be displayed"


def test_read_text_binary_friendly_mode_allows_empty_transport_content(
    tmp_path: Path,
) -> None:
    (tmp_path / "archive.zip").write_bytes(b"\x00\xff\x00")
    engine = _engine(
        tmp_path,
        FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024,
            read_policy=FileReadPolicy(
                binary_mode="friendly-text",
                friendly_binary_message="",
            ),
        ),
    )

    content = engine.read_text(
        ReadTextRequest(locator=FileLocator("knowledge-base", "kb-1"), path="archive.zip")
    )

    assert content.readable is False
    assert content.content == ""
    assert content.metadata == {"reason": "binary"}


def test_read_text_large_file_error(tmp_path: Path) -> None:
    (tmp_path / "large.txt").write_text("too large", encoding="utf-8")
    engine = _engine(tmp_path, FilePolicy(max_read_bytes=3, max_write_bytes=1024))

    with pytest.raises(FileCoreError) as exc:
        engine.read_text(
            ReadTextRequest(
                locator=FileLocator("knowledge-base", "kb1"),
                path="large.txt",
            )
        )

    assert exc.value.code == "FILE_TOO_LARGE"


def test_read_bytes_returns_binary_content(tmp_path: Path) -> None:
    (tmp_path / "asset.bin").write_bytes(b"abc")

    content = _engine(tmp_path).read_bytes(
        ReadBytesRequest(locator=FileLocator("workspace", "w1"), path="asset.bin")
    )

    assert content.content == b"abc"
    assert content.size == 3
