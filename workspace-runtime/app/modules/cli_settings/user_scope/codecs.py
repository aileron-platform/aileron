"""Shared codecs and atomic file operations for user-scope resources."""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 runtime fallback
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

import tomli_w

from app.core.revision import compute_revision


logger = logging.getLogger(__name__)


def read_text(path: Path, default: str = "") -> str:
    """Read UTF-8 text or return the supplied value for a missing file."""

    return path.read_text(encoding="utf-8") if path.is_file() else default


def read_bytes(path: Path, default: bytes = b"") -> bytes:
    """Read file bytes or return the supplied value for a missing file."""

    return path.read_bytes() if path.is_file() else default


def fsync_directory(path: Path) -> None:
    """Durably persist directory entry changes."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """Atomically replace one file while preserving its existing mode."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = (
        stat.S_IMODE(path.stat().st_mode) if path.exists() and path.is_file() else None
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            os.chmod(temporary_path, existing_mode)
        os.replace(temporary_path, path)
        fsync_directory(path.parent)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_text_atomic(path: Path, content: str) -> None:
    """Atomically replace one UTF-8 text file."""

    write_bytes_atomic(path, content.encode("utf-8"))


def remove_file_exact(path: Path) -> bool:
    """Remove exactly one file or symlink without recursive cleanup."""

    try:
        path.unlink()
    except FileNotFoundError:
        return False
    fsync_directory(path.parent)
    return True


def text_revision(content: str) -> str:
    """Return the canonical revision for text content."""

    return compute_revision(content)


def file_revision(path: Path) -> str:
    """Return the canonical revision for a UTF-8 file or missing content."""

    return text_revision(read_text(path))


def file_bytes_revision(path: Path) -> str:
    """Return the canonical revision for exact file bytes."""

    return compute_revision(read_bytes(path))


def directory_tree_revision(root: Path) -> str:
    """Hash exact directory entry types, modes, paths, and bytes."""

    if not root.is_dir():
        return compute_revision(b"")
    digest = sha256()
    entries = sorted(
        root.rglob("*"),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in entries:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        path_stat = path.lstat()
        mode = stat.S_IMODE(path_stat.st_mode)
        if path.is_symlink():
            entry_type = b"symlink"
            content = os.readlink(path).encode("utf-8")
        elif path.is_dir():
            entry_type = b"directory"
            content = b""
        elif path.is_file():
            entry_type = b"file"
            content = path.read_bytes()
        else:
            raise ValueError(f"Unsupported directory entry: {relative!r}")
        for field in (
            entry_type,
            f"{mode:o}".encode("ascii"),
            relative,
            content,
        ):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def mapping_revision(value: Mapping[str, Any]) -> str:
    """Return a deterministic revision for a mapping."""

    content = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return text_revision(content)


def merge_mapping_entries(
    document: Mapping[str, Any],
    key_path: tuple[str, ...],
    entries: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge named entries into one nested mapping without mutating the input."""

    result = deepcopy(dict(document))
    target = _nested_mapping(result, key_path)
    assert target is not None
    for key, value in entries.items():
        target[str(key)] = deepcopy(value)
    return result


def remove_mapping_entry(
    document: Mapping[str, Any],
    key_path: tuple[str, ...],
    entry_id: str,
) -> tuple[dict[str, Any], bool]:
    """Remove one exact nested mapping entry while preserving every sibling."""

    result = deepcopy(dict(document))
    target = _nested_mapping(result, key_path, create=False)
    if target is None or entry_id not in target:
        return result, False
    del target[entry_id]
    return result, True


def _nested_mapping(
    document: dict[str, Any],
    key_path: tuple[str, ...],
    *,
    create: bool = True,
) -> dict[str, Any] | None:
    target = document
    for key in key_path:
        value = target.get(key)
        if not isinstance(value, dict):
            if not create:
                return None
            value = {}
            target[key] = value
        target = value
    return target


def strip_json_comments(text: str) -> str:
    """Remove JSONC comments while preserving comment markers in strings."""

    result: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character in ('"', "'"):
            quote = character
            result.append(character)
            index += 1
            while index < len(text):
                current = text[index]
                result.append(current)
                index += 1
                if current == "\\" and index < len(text):
                    result.append(text[index])
                    index += 1
                elif current == quote:
                    break
        elif character == "/" and index + 1 < len(text) and text[index + 1] == "/":
            index += 2
            while index < len(text) and text[index] != "\n":
                index += 1
        elif character == "/" and index + 1 < len(text) and text[index + 1] == "*":
            index += 2
            while index + 1 < len(text) and not (
                text[index] == "*" and text[index + 1] == "/"
            ):
                index += 1
            index += 2
        else:
            result.append(character)
            index += 1
    return "".join(result)


@dataclass(frozen=True)
class JsonDocumentCodec:
    """Read and atomically write JSON mapping documents."""

    allow_comments: bool = False
    invalid_as_empty: bool = True

    def parse(self, content: str) -> dict[str, Any]:
        source = strip_json_comments(content) if self.allow_comments else content
        payload = json.loads(source)
        if not isinstance(payload, dict):
            raise ValueError("JSON document root must be an object")
        return {str(key): value for key, value in payload.items()}

    def read(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return self.parse(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            if not self.invalid_as_empty:
                raise
            logger.warning(
                "Failed to parse JSON document %s: %s. Treating as empty.",
                path,
                exc,
            )
            return {}

    def serialize(self, document: Mapping[str, Any]) -> str:
        return json.dumps(dict(document), indent=2, ensure_ascii=False)

    def write(self, path: Path, document: Mapping[str, Any]) -> None:
        write_text_atomic(path, self.serialize(document))

    def revision(self, path: Path) -> str:
        return file_revision(path)


@dataclass(frozen=True)
class TomlDocumentCodec:
    """Read and atomically write TOML mapping documents."""

    invalid_as_empty: bool = True

    def parse(self, content: str) -> dict[str, Any]:
        return dict(tomllib.loads(content))

    def read(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return self.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            if not self.invalid_as_empty:
                raise
            logger.warning(
                "Failed to parse TOML document %s: %s. Treating as empty.",
                path,
                exc,
            )
            return {}

    def serialize(self, document: Mapping[str, Any]) -> str:
        return tomli_w.dumps(dict(document))

    def write(self, path: Path, document: Mapping[str, Any]) -> None:
        write_text_atomic(path, self.serialize(document))

    def revision(self, path: Path) -> str:
        return file_revision(path)


@dataclass(frozen=True)
class MarkdownDirectoryCodec:
    """Read, revise, write, and remove Markdown directory entries."""

    suffix: str = ".md"

    def files(self, root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(path for path in root.rglob(f"*{self.suffix}") if path.is_file())

    def read(self, path: Path) -> str:
        return read_text(path)

    def write(self, path: Path, content: str) -> None:
        write_text_atomic(path, content)

    def remove(self, path: Path) -> bool:
        return remove_file_exact(path)

    def revision(self, path: Path) -> str:
        return file_revision(path)

    def directory_revision(self, root: Path) -> str:
        content_by_path = {
            path.relative_to(root).as_posix(): read_text(path)
            for path in self.files(root)
        }
        return mapping_revision(content_by_path)
