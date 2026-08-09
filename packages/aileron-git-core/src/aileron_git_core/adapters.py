from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .models import FileChange


def file_change_name(change: FileChange) -> str:
    return Path(change.path).name


def paginate_changes(
    changes: Sequence[FileChange], *, page: int, page_size: int
) -> tuple[list[FileChange], int, bool]:
    if page < 1:
        raise ValueError("page must be greater than or equal to 1")
    if page_size < 1:
        raise ValueError("page_size must be greater than or equal to 1")

    total = len(changes)
    start = (page - 1) * page_size
    end = start + page_size
    return list(changes[start:end]), total, end < total


def to_change_dict(change: FileChange) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": file_change_name(change),
        "path": change.path,
        "status": change.status,
        "type": change.type,
    }
    if change.original_path is not None:
        payload["oldPath"] = change.original_path
    return payload
