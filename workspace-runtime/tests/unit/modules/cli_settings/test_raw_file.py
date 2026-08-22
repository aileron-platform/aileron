from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from app.modules.cli_settings import raw_file


def _failure(error: pytest.ExceptionInfo[raw_file.RawFileError]) -> str:
    return error.value.failure.value


def test_raw_file_exact_limit_and_one_byte_over(tmp_path: Path) -> None:
    root = tmp_path / "root"
    target = root / "preview.bin"
    root.mkdir()
    target.write_bytes(b"x" * 8)

    assert raw_file.read_raw_file(root, "preview.bin", 8) == b"x" * 8

    target.write_bytes(b"x" * 9)
    with pytest.raises(raw_file.RawFileError) as exc_info:
        raw_file.read_raw_file(root, "preview.bin", 8)
    assert _failure(exc_info) == "too_large"


def test_raw_file_rejects_static_symlinks_and_non_regular_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"secret")
    (root / "file-link.bin").symlink_to(outside / "secret.bin")
    (root / "ancestor-link").symlink_to(outside, target_is_directory=True)
    (root / "directory.bin").mkdir()
    os.mkfifo(root / "pipe.bin")

    for path in (
        "file-link.bin",
        "ancestor-link/secret.bin",
        "directory.bin",
        "pipe.bin",
    ):
        with pytest.raises(raw_file.RawFileError) as exc_info:
            raw_file.read_raw_file(root, path, 32)
        assert _failure(exc_info) == "not_found"


def test_raw_file_rejects_symlink_ancestors_in_the_root_path(tmp_path: Path) -> None:
    physical_parent = tmp_path / "physical-parent"
    physical_root = physical_parent / "root"
    physical_root.mkdir(parents=True)
    (physical_root / "preview.bin").write_bytes(b"outside")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(physical_parent, target_is_directory=True)

    with pytest.raises(raw_file.RawFileError) as exc_info:
        raw_file.read_raw_file(linked_parent / "root", "preview.bin", 32)

    assert _failure(exc_info) == "not_found"


def test_raw_file_keeps_open_ancestor_pinned_during_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    assets = root / "review" / "assets"
    pinned_assets = root / "review" / "pinned-assets"
    outside = tmp_path / "outside"
    assets.mkdir(parents=True)
    outside.mkdir()
    (assets / "logo.bin").write_bytes(b"inside")
    (outside / "logo.bin").write_bytes(b"outside")
    original_open = raw_file._open_descriptor
    swapped = False

    def swapping_open(
        path: str | Path,
        flags: int,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        descriptor = original_open(path, flags, dir_fd=dir_fd)
        if path == "assets" and dir_fd is not None and not swapped:
            swapped = True
            assets.rename(pinned_assets)
            assets.symlink_to(outside, target_is_directory=True)
        return descriptor

    monkeypatch.setattr(raw_file, "_open_descriptor", swapping_open)

    content = raw_file.read_raw_file(root, "review/assets/logo.bin", 32)

    assert swapped is True
    assert content == b"inside"
    assert (root / "review" / "assets" / "logo.bin").read_bytes() == b"outside"


def test_raw_file_short_reads_share_one_limit_plus_one_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "preview.bin").write_bytes(b"unused")
    source = b"x" * 9
    cursor = 0
    requested_sizes: list[int] = []

    def short_read(_descriptor: int, size: int) -> bytes:
        nonlocal cursor
        requested_sizes.append(size)
        chunk = source[cursor : cursor + min(size, 2)]
        cursor += len(chunk)
        return chunk

    monkeypatch.setattr(raw_file, "_read_descriptor", short_read)

    with pytest.raises(raw_file.RawFileError) as exc_info:
        raw_file.read_raw_file(root, "preview.bin", 8)

    assert _failure(exc_info) == "too_large"
    assert requested_sizes == [9, 7, 5, 3, 1]
    assert cursor == 9


def test_raw_file_maps_descriptor_failures_without_physical_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "sensitive-root"
    root.mkdir()
    (root / "preview.bin").write_bytes(b"data")

    def failed_stat(_descriptor: int):
        raise OSError(errno.EIO, f"failed under {root}")

    monkeypatch.setattr(raw_file, "_stat_descriptor", failed_stat)

    with pytest.raises(raw_file.RawFileError) as exc_info:
        raw_file.read_raw_file(root, "preview.bin", 8)

    assert _failure(exc_info) == "internal"
    assert str(root) not in str(exc_info.value)


@pytest.mark.parametrize("path", ["", ".", "../secret.bin", "/tmp/secret.bin"])
def test_raw_file_rejects_invalid_relative_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(raw_file.RawFileError) as exc_info:
        raw_file.read_raw_file(tmp_path, path, 8)
    assert _failure(exc_info) == "invalid_path"
