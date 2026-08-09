from pathlib import Path

import pytest

from aileron_file_core import PathOutsideRootError, resolve_safe_path


def test_resolve_safe_path_normalizes_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    result = resolve_safe_path(root, "docs/../README.md")

    assert result.root == root.resolve()
    assert result.relative_path == "README.md"
    assert result.absolute_path == root.resolve() / "README.md"


def test_resolve_safe_path_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(PathOutsideRootError) as exc_info:
        resolve_safe_path(root, "../outside.txt")

    assert exc_info.value.path == "../outside.txt"


def test_resolve_safe_path_rejects_leading_slash(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(PathOutsideRootError) as exc_info:
        resolve_safe_path(root, "/docs/file.txt")

    assert exc_info.value.path == "/docs/file.txt"


def test_resolve_safe_path_normalizes_backslash_separator(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    result = resolve_safe_path(root, "docs\\note.md")

    assert result.relative_path == "docs/note.md"
    assert result.absolute_path == root.resolve() / "docs" / "note.md"


def test_resolve_safe_path_preserves_filename_whitespace(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    result = resolve_safe_path(root, " spaced name.txt ")

    assert result.relative_path == " spaced name.txt "
    assert result.absolute_path == root.resolve() / " spaced name.txt "


def test_resolve_safe_path_rejects_same_prefix_sibling_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    sibling = tmp_path / "root-sibling"
    root.mkdir()
    sibling.mkdir()
    (sibling / "file.txt").write_text("outside", encoding="utf-8")
    (root / "link").symlink_to(sibling)

    with pytest.raises(PathOutsideRootError) as exc_info:
        resolve_safe_path(root, "link/file.txt")

    assert exc_info.value.path == "link/file.txt"


def test_resolve_safe_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    (root / "link").symlink_to(outside)

    with pytest.raises(PathOutsideRootError) as exc_info:
        resolve_safe_path(root, "link/secret.txt")

    assert exc_info.value.path == "link/secret.txt"
