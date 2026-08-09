from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

PACKAGE_TREE_DIGEST_ALGORITHM = "package-tree-sha256-v1"


class PackageTreeError(ValueError):
    pass


@dataclass(frozen=True)
class PackageTreeEntry:
    entry_type: str
    mode: str
    relative_path: str
    payload: bytes


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _symlink_payload(package_root: Path, path: Path) -> bytes:
    try:
        target = os.readlink(path)
    except OSError as exc:
        raise PackageTreeError(f"Unable to read package symlink: {path}") from exc
    if os.path.isabs(target):
        raise PackageTreeError(f"Absolute symlink target is not allowed: {path}")
    seen: set[str] = set()
    current = path
    while current.is_symlink():
        marker = os.path.normpath(os.path.abspath(current))
        if marker in seen:
            raise PackageTreeError(f"Invalid package symlink: {path}")
        seen.add(marker)
        try:
            nested_target = os.readlink(current)
        except OSError as exc:
            raise PackageTreeError(
                f"Unable to read package symlink: {current}"
            ) from exc
        current = (
            Path(nested_target)
            if os.path.isabs(nested_target)
            else current.parent / nested_target
        )
    try:
        resolved_target = (path.parent / target).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise PackageTreeError(f"Invalid package symlink: {path}") from exc
    if not _is_within(package_root, resolved_target):
        raise PackageTreeError(f"Symlink escapes package root: {path}")
    return target.encode("utf-8", errors="surrogateescape")


def _iter_package_entries(package_root: Path) -> tuple[PackageTreeEntry, ...]:
    try:
        resolved_root = package_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PackageTreeError(f"Invalid package root: {package_root}") from exc
    if not resolved_root.is_dir():
        raise PackageTreeError(f"Package root is not a directory: {package_root}")

    entries: list[PackageTreeEntry] = []
    pending = [package_root]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise PackageTreeError(
                f"Unable to read package directory: {directory}"
            ) from exc
        for child in children:
            path = Path(child.path)
            relative_path = path.relative_to(package_root).as_posix()
            child_stat = child.stat(follow_symlinks=False)
            if stat.S_ISLNK(child_stat.st_mode):
                entries.append(
                    PackageTreeEntry(
                        entry_type="symlink",
                        mode="120000",
                        relative_path=relative_path,
                        payload=_symlink_payload(resolved_root, path),
                    )
                )
                continue
            if stat.S_ISDIR(child_stat.st_mode):
                pending.append(path)
                continue
            if stat.S_ISREG(child_stat.st_mode):
                executable_bits = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                mode = "100755" if child_stat.st_mode & executable_bits else "100644"
                try:
                    payload = path.read_bytes()
                except OSError as exc:
                    raise PackageTreeError(
                        f"Unable to read package file: {path}"
                    ) from exc
                entries.append(
                    PackageTreeEntry(
                        entry_type="file",
                        mode=mode,
                        relative_path=relative_path,
                        payload=payload,
                    )
                )
                continue
            raise PackageTreeError(f"Unsupported package entry type: {path}")
    return tuple(sorted(entries, key=lambda item: item.relative_path.encode("utf-8")))


def package_tree_digest(package_root: Path) -> str:
    digest = sha256()
    for entry in _iter_package_entries(package_root):
        for value in (
            entry.entry_type.encode("ascii"),
            entry.mode.encode("ascii"),
            entry.relative_path.encode("utf-8"),
            entry.payload,
        ):
            digest.update(len(value).to_bytes(8, byteorder="big"))
            digest.update(value)
    return digest.hexdigest()
