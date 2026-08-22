#!/usr/bin/env python3
"""Probe or remove one pre-authorized backend path without following symlinks."""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import stat
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "aileron-backend-storage-probe/v1"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^run-[a-z0-9][a-z0-9-]{6,57}[a-z0-9]$")
PATH_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MOUNTINFO_PATH = Path("/proc/self/mountinfo")
MOUNTINFO_MAX_BYTES = 16 * 1024 * 1024
MOUNTINFO_ESCAPES = {
    "040": " ",
    "011": "\t",
    "012": "\n",
    "134": "\\",
}


def _relative_parts(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or str(path) != value
        or any(
            part in {"", ".", ".."} or PATH_COMPONENT_PATTERN.fullmatch(part) is None
            for part in path.parts
        )
    ):
        raise ValueError("backend relative path is invalid")
    return path.parts


def _decode_mountinfo_path(value: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            decoded.append(value[index])
            index += 1
            continue
        escape = value[index + 1 : index + 4]
        if len(escape) != 3 or escape not in MOUNTINFO_ESCAPES:
            raise ValueError("backend mountinfo contains an invalid path escape")
        decoded.append(MOUNTINFO_ESCAPES[escape])
        index += 4
    result = "".join(decoded)
    path = PurePosixPath(result)
    if (
        not result.startswith("/")
        or "\x00" in result
        or (result != "/" and str(path) != result.rstrip("/"))
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise ValueError("backend mountinfo path is invalid")
    return str(path)


def _mount_points(path: Path) -> tuple[PurePosixPath, ...]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError("backend mountinfo is unreadable") from exc
    try:
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MOUNTINFO_MAX_BYTES:
                raise ValueError("backend mountinfo is too large")
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    try:
        lines = b"".join(chunks).decode().splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("backend mountinfo is invalid UTF-8") from exc
    points: list[PurePosixPath] = []
    for line in lines:
        fields = line.split(" ")
        try:
            separator = fields.index("-")
        except ValueError as exc:
            raise ValueError("backend mountinfo record is malformed") from exc
        if (
            separator < 6
            or len(fields) < separator + 4
            or not fields[0].isdigit()
            or not fields[1].isdigit()
            or re.fullmatch(r"[0-9]+:[0-9]+", fields[2]) is None
        ):
            raise ValueError("backend mountinfo record is malformed")
        _decode_mountinfo_path(fields[3])
        points.append(PurePosixPath(_decode_mountinfo_path(fields[4])))
    if not points:
        raise ValueError("backend mountinfo contains no mounts")
    return tuple(points)


def _reject_nested_mounts(
    *,
    mount_root: Path,
    relative_parts: tuple[str, ...],
    mountinfo_path: Path,
) -> None:
    root = PurePosixPath(str(mount_root))
    if not mount_root.is_absolute() or str(root) != str(mount_root).rstrip("/"):
        raise ValueError("backend mount root must be a canonical absolute path")
    target = root.joinpath(*relative_parts)
    for mount_point in _mount_points(mountinfo_path):
        if mount_point == root:
            continue
        if root in mount_point.parents and (
            mount_point == target
            or mount_point in target.parents
            or target in mount_point.parents
        ):
            raise ValueError("backend target contains a nested mount")


def _open_directory(name: str, *, parent_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        if parent_fd is None:
            return os.open(name, flags)
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ValueError("backend path contains a symbolic link parent") from exc
        raise


def _open_absolute_directory(path: Path) -> int:
    current_fd = _open_directory("/")
    try:
        for component in PurePosixPath(str(path)).parts[1:]:
            next_fd = _open_directory(component, parent_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _remove_entry(parent_fd: int, name: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(metadata.st_mode):
        child_fd = _open_directory(name, parent_fd=parent_fd)
        try:
            for child in os.listdir(child_fd):
                _remove_entry(child_fd, child)
        finally:
            os.close(child_fd)
        os.rmdir(name, dir_fd=parent_fd)
        return
    os.unlink(name, dir_fd=parent_fd)


def _target_state(
    *, mount_root: Path, relative_parts: tuple[str, ...]
) -> tuple[bool, int, str]:
    if not mount_root.is_absolute():
        raise ValueError("backend mount root must be absolute")
    root_fd = _open_absolute_directory(mount_root)
    current_fd = root_fd
    try:
        for component in relative_parts[:-1]:
            try:
                next_fd = _open_directory(component, parent_fd=current_fd)
            except FileNotFoundError:
                return False, os.dup(current_fd), relative_parts[-1]
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        try:
            os.stat(relative_parts[-1], dir_fd=current_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False, os.dup(current_fd), relative_parts[-1]
        return True, os.dup(current_fd), relative_parts[-1]
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def probe_backend(
    *,
    action: str,
    mount_root: Path,
    relative_path: str,
    locator_sha256: str,
    profile_raw_sha256: str,
    profile_canonical_sha256: str,
    run_id: str,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    mountinfo_path: Path = MOUNTINFO_PATH,
) -> dict[str, Any]:
    """Return a typed observation after probing one exact backend child."""

    if (
        action not in {"cleanup", "verify"}
        or DIGEST_PATTERN.fullmatch(locator_sha256) is None
        or DIGEST_PATTERN.fullmatch(profile_raw_sha256) is None
        or DIGEST_PATTERN.fullmatch(profile_canonical_sha256) is None
        or RUN_ID_PATTERN.fullmatch(run_id) is None
    ):
        raise ValueError("backend probe identity is invalid")
    parts = _relative_parts(relative_path)
    _reject_nested_mounts(
        mount_root=mount_root,
        relative_parts=parts,
        mountinfo_path=mountinfo_path,
    )
    present, parent_fd, leaf = _target_state(
        mount_root=mount_root, relative_parts=parts
    )
    cleanup_performed = False
    try:
        if action == "cleanup" and present:
            _remove_entry(parent_fd, leaf)
            try:
                os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                present = False
                cleanup_performed = True
            else:
                raise ValueError("backend target remained after cleanup")
    finally:
        os.close(parent_fd)
    checked_at = clock()
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("backend probe clock must be timezone-aware")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "action": action,
        "runId": run_id,
        "locatorSha256": locator_sha256,
        "profileRawSha256": profile_raw_sha256,
        "profileCanonicalSha256": profile_canonical_sha256,
        "state": "present" if present else "absent",
        "cleanupPerformed": cleanup_performed,
        "checkedAt": checked_at.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=("cleanup", "verify"))
    parser.add_argument("--mount-root", required=True, type=Path)
    parser.add_argument("--relative-path", required=True)
    parser.add_argument("--locator-sha256", required=True)
    parser.add_argument("--profile-raw-sha256", required=True)
    parser.add_argument("--profile-canonical-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    arguments = parser.parse_args()
    try:
        result = probe_backend(
            action=arguments.action,
            mount_root=arguments.mount_root,
            relative_path=arguments.relative_path,
            locator_sha256=arguments.locator_sha256,
            profile_raw_sha256=arguments.profile_raw_sha256,
            profile_canonical_sha256=arguments.profile_canonical_sha256,
            run_id=arguments.run_id,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
