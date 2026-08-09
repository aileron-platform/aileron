from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from .errors import PathOutsideRootError
from .path_guard import resolve_safe_path


@dataclass(frozen=True)
class SnapshotResult:
    id: str
    resource_id: str
    relative_path: str
    operation: str
    snapshot_path: Path
    size: int
    created_at: datetime


def snapshot_file(
    *,
    source_path: Path,
    resource_id: str,
    relative_path: str,
    operation: str,
    snapshot_root: Path,
) -> SnapshotResult:
    _validate_resource_id(resource_id)
    snapshot_id = uuid4().hex
    created_at = datetime.now(timezone.utc)
    base_root = snapshot_root / resource_id / created_at.strftime("%Y%m%d") / snapshot_id
    destination = resolve_safe_path(base_root, relative_path).absolute_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(source_path, destination)
    return SnapshotResult(
        id=snapshot_id,
        resource_id=resource_id,
        relative_path=relative_path,
        operation=operation,
        snapshot_path=destination,
        size=destination.stat().st_size,
        created_at=created_at,
    )


def _validate_resource_id(resource_id: str) -> None:
    if (
        resource_id in ("", ".", "..")
        or ".." in resource_id
        or "/" in resource_id
        or "\\" in resource_id
    ):
        raise PathOutsideRootError(resource_id)
