import os
from pathlib import Path

import pytest

from aileron_marketplace_core.package_tree import PackageTreeError, package_tree_digest


def test_package_tree_digest_is_full_stable_sha256(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    (left / "nested").mkdir(parents=True)
    (right / "nested").mkdir(parents=True)
    (left / "nested" / "file.txt").write_text("same", encoding="utf-8")
    (right / "nested" / "file.txt").write_text("same", encoding="utf-8")

    left_digest = package_tree_digest(left)

    assert len(left_digest) == 64
    assert left_digest == package_tree_digest(right)


def test_package_tree_digest_includes_executable_mode(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    executable = package / "run.sh"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o644)
    regular_digest = package_tree_digest(package)

    executable.chmod(0o755)

    assert package_tree_digest(package) != regular_digest


def test_package_tree_digest_hashes_safe_symlink_target_without_following_it(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "target.txt").write_text("target", encoding="utf-8")
    os.symlink("target.txt", package / "link.txt")
    first = package_tree_digest(package)

    (package / "link.txt").unlink()
    os.symlink("./target.txt", package / "link.txt")

    assert package_tree_digest(package) != first


def test_package_tree_digest_rejects_symlink_escape(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    os.symlink("../outside.txt", package / "escape.txt")

    with pytest.raises(PackageTreeError, match="escapes package root"):
        package_tree_digest(package)


def test_package_tree_digest_rejects_absolute_symlink(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    os.symlink(str(tmp_path / "outside"), package / "escape")

    with pytest.raises(PackageTreeError, match="Absolute symlink"):
        package_tree_digest(package)


def test_package_tree_digest_rejects_symlink_loop(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    os.symlink("loop-b", package / "loop-a")
    os.symlink("loop-a", package / "loop-b")

    with pytest.raises(PackageTreeError, match="Invalid package symlink"):
        package_tree_digest(package)
