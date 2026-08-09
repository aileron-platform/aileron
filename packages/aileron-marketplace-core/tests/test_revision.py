import re
from pathlib import Path

from aileron_marketplace_core.revision import revision_for_package_paths


def test_revision_is_full_lowercase_sha256(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "plugin.json").write_text('{"name":"demo"}', encoding="utf-8")

    revision = revision_for_package_paths([package])

    assert len(revision) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", revision) is not None


def test_revision_changes_when_file_content_changes_without_size_change(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    config = package / "plugin.json"
    config.write_text('{"name":"demo","a":1}', encoding="utf-8")

    first = revision_for_package_paths([package])
    config.write_text('{"name":"demo","a":2}', encoding="utf-8")

    assert revision_for_package_paths([package]) != first


def test_revision_is_stable_for_same_content_written_later(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    config = package / "plugin.json"
    config.write_text('{"name":"demo"}', encoding="utf-8")

    first = revision_for_package_paths([package])
    config.write_text('{"name":"demo"}', encoding="utf-8")

    assert revision_for_package_paths([package]) == first


def test_revision_uses_package_relative_paths(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    (left / "nested").mkdir(parents=True)
    (right / "nested").mkdir(parents=True)
    (left / "nested" / "a.txt").write_text("same", encoding="utf-8")
    (right / "nested" / "a.txt").write_text("same", encoding="utf-8")

    assert revision_for_package_paths([left]) == revision_for_package_paths([right])
