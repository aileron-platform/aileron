"""Descriptor-pinned, bounded reads for raw settings previews."""

from __future__ import annotations

import errno
import os
import stat
from enum import StrEnum
from pathlib import Path
from typing import NoReturn


class RawFileFailure(StrEnum):
    """Stable failure categories exposed by the raw-preview services."""

    INVALID_PATH = "invalid_path"
    NOT_FOUND = "not_found"
    TOO_LARGE = "too_large"
    INTERNAL = "internal"


class RawFileError(Exception):
    """Path-free raw-preview failure."""

    def __init__(self, failure: RawFileFailure) -> None:
        self.failure = failure
        super().__init__(failure.value)


_NOT_FOUND_ERRNOS = {
    errno.ENOENT,
    errno.ENOTDIR,
    errno.ELOOP,
    errno.ENXIO,
    errno.ENODEV,
    errno.EISDIR,
    getattr(errno, "ESTALE", -1),
}
_INVALID_PATH_ERRNOS = {errno.ENAMETOOLONG}
_DIRECTORY_OPEN_FLAGS = (
    getattr(os, "O_PATH", os.O_RDONLY) | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
)
_FILE_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def raw_file_parts(relative_path: str) -> tuple[str, ...]:
    """Validate a relative file locator without resolving filesystem objects."""

    if not relative_path or "\x00" in relative_path:
        raise RawFileError(RawFileFailure.INVALID_PATH)
    try:
        path = Path(relative_path)
    except (TypeError, ValueError) as exc:
        raise RawFileError(RawFileFailure.INVALID_PATH) from exc
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RawFileError(RawFileFailure.INVALID_PATH)
    return path.parts


def _raise_os_failure(error: OSError) -> NoReturn:
    if error.errno in _NOT_FOUND_ERRNOS:
        raise RawFileError(RawFileFailure.NOT_FOUND) from error
    if error.errno in _INVALID_PATH_ERRNOS:
        raise RawFileError(RawFileFailure.INVALID_PATH) from error
    raise RawFileError(RawFileFailure.INTERNAL) from error


def _close_quietly(descriptor: int | None) -> None:
    if descriptor is None:
        return
    try:
        os.close(descriptor)
    except OSError:
        pass


def _open_descriptor(
    path: str | Path,
    flags: int,
    *,
    dir_fd: int | None = None,
) -> int:
    if dir_fd is None:
        return os.open(path, flags)
    return os.open(path, flags, dir_fd=dir_fd)


def _stat_descriptor(descriptor: int) -> os.stat_result:
    return os.fstat(descriptor)


def _read_descriptor(descriptor: int, size: int) -> bytes:
    return os.read(descriptor, size)


def _open_root_descriptor(root: Path) -> int:
    if not root.is_absolute() or ".." in root.parts:
        raise RawFileError(RawFileFailure.INTERNAL)
    descriptor = _open_descriptor(Path(root.anchor), _DIRECTORY_OPEN_FLAGS)
    try:
        for component in root.parts[1:]:
            next_descriptor = _open_descriptor(
                component,
                _DIRECTORY_OPEN_FLAGS,
                dir_fd=descriptor,
            )
            _close_quietly(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        _close_quietly(descriptor)
        raise


def read_raw_file(root: Path, relative_path: str, limit: int) -> bytes:
    """Read one regular file beneath a descriptor-pinned directory root."""

    if limit < 0:
        raise ValueError("Raw file limit must be non-negative")
    parts = raw_file_parts(relative_path)
    directory_descriptor: int | None = None
    file_descriptor: int | None = None
    try:
        try:
            directory_descriptor = _open_root_descriptor(root)
        except OSError as exc:
            _raise_os_failure(exc)
        except (TypeError, ValueError) as exc:
            raise RawFileError(RawFileFailure.INTERNAL) from exc

        for component in parts[:-1]:
            try:
                next_descriptor = _open_descriptor(
                    component,
                    _DIRECTORY_OPEN_FLAGS,
                    dir_fd=directory_descriptor,
                )
            except OSError as exc:
                _raise_os_failure(exc)
            except (TypeError, ValueError) as exc:
                raise RawFileError(RawFileFailure.INVALID_PATH) from exc
            _close_quietly(directory_descriptor)
            directory_descriptor = next_descriptor

        try:
            file_descriptor = _open_descriptor(
                parts[-1],
                _FILE_OPEN_FLAGS,
                dir_fd=directory_descriptor,
            )
        except OSError as exc:
            _raise_os_failure(exc)
        except (TypeError, ValueError) as exc:
            raise RawFileError(RawFileFailure.INVALID_PATH) from exc

        try:
            file_stat = _stat_descriptor(file_descriptor)
        except OSError as exc:
            _raise_os_failure(exc)
        if not stat.S_ISREG(file_stat.st_mode):
            raise RawFileError(RawFileFailure.NOT_FOUND)

        remaining = limit + 1
        chunks: list[bytes] = []
        while remaining:
            try:
                chunk = _read_descriptor(file_descriptor, remaining)
            except OSError as exc:
                _raise_os_failure(exc)
            if not chunk:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > limit:
            raise RawFileError(RawFileFailure.TOO_LARGE)
        return content
    finally:
        _close_quietly(file_descriptor)
        _close_quietly(directory_descriptor)
