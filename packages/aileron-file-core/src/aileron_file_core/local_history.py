from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .errors import PathOutsideRootError
from .snapshot import snapshot_file

LocalHistoryOperation = Literal[
    "write",
    "delete",
    "move",
    "copy",
    "upload",
    "extract",
    "sync",
    "discard",
    "restore",
]


@dataclass(frozen=True)
class LocalHistoryEntry:
    id: str
    domain: str
    resource_id: str
    path: str
    operation: LocalHistoryOperation
    timestamp: str
    size: int
    version_id_before: str | None = None
    version_id_after: str | None = None
    content_hash_before: str | None = None
    content_hash_after: str | None = None
    snapshot_path: str | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "LocalHistoryEntry":
        return cls(
            id=str(payload["id"]),
            domain=str(payload["domain"]),
            resource_id=str(payload["resource_id"]),
            path=str(payload["path"]),
            operation=payload["operation"],
            timestamp=str(payload["timestamp"]),
            size=int(payload["size"]),
            version_id_before=payload.get("version_id_before"),
            version_id_after=payload.get("version_id_after"),
            content_hash_before=payload.get("content_hash_before"),
            content_hash_after=payload.get("content_hash_after"),
            snapshot_path=payload.get("snapshot_path"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


class JsonLocalHistoryStore:
    def __init__(self, history_root: Path) -> None:
        self._history_root = Path(history_root)

    def append(self, entry: LocalHistoryEntry) -> LocalHistoryEntry:
        metadata_path = self._metadata_path(entry.domain, entry.resource_id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True)
            )
            handle.write("\n")
        return entry

    def list_entries(
        self,
        *,
        domain: str,
        resource_id: str,
        path: str | None = None,
        limit: int = 50,
    ) -> list[LocalHistoryEntry]:
        metadata_path = self._metadata_path(domain, resource_id)
        if not metadata_path.exists():
            return []

        entries: list[LocalHistoryEntry] = []
        with metadata_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = LocalHistoryEntry.from_dict(json.loads(line))
                if path is None or entry.path == path:
                    entries.append(entry)

        entries.reverse()
        return entries[:limit]

    def get_entry(
        self, *, domain: str, resource_id: str, entry_id: str
    ) -> LocalHistoryEntry:
        for entry in self.list_entries(
            domain=domain, resource_id=resource_id, limit=10000
        ):
            if entry.id == entry_id:
                return entry
        raise KeyError(entry_id)

    def _metadata_path(self, domain: str, resource_id: str) -> Path:
        _validate_segment(domain)
        _validate_segment(resource_id)
        return self._history_root / domain / resource_id / "entries.jsonl"


class LocalHistoryService:
    def __init__(
        self,
        *,
        store: JsonLocalHistoryStore,
        snapshot_root: Path,
        domain: str,
        resource_id: str,
    ) -> None:
        _validate_segment(domain)
        _validate_segment(resource_id)
        self._store = store
        self._snapshot_root = Path(snapshot_root)
        self._domain = domain
        self._resource_id = resource_id

    def snapshot_existing_file(
        self,
        *,
        source_path: Path,
        relative_path: str,
        operation: LocalHistoryOperation,
        version_id_before: str | None = None,
        version_id_after: str | None = None,
        content_hash_before: str | None = None,
        content_hash_after: str | None = None,
    ) -> LocalHistoryEntry | None:
        source_path = Path(source_path)
        if not source_path.exists() or not source_path.is_file():
            return None

        snapshot = snapshot_file(
            source_path=source_path,
            resource_id=self._resource_id,
            relative_path=relative_path,
            operation=operation,
            snapshot_root=self._snapshot_root / self._domain,
        )
        entry = LocalHistoryEntry(
            id=snapshot.id or uuid4().hex,
            domain=self._domain,
            resource_id=self._resource_id,
            path=relative_path,
            operation=operation,
            timestamp=datetime.now(timezone.utc).isoformat(),
            version_id_before=version_id_before,
            version_id_after=version_id_after,
            content_hash_before=content_hash_before,
            content_hash_after=content_hash_after,
            snapshot_path=str(snapshot.snapshot_path),
            size=snapshot.size,
        )
        return self._store.append(entry)

    def list_entries(
        self, *, path: str | None = None, limit: int = 50
    ) -> list[LocalHistoryEntry]:
        return self._store.list_entries(
            domain=self._domain,
            resource_id=self._resource_id,
            path=path,
            limit=limit,
        )

    def get_entry(self, entry_id: str) -> LocalHistoryEntry:
        return self._store.get_entry(
            domain=self._domain,
            resource_id=self._resource_id,
            entry_id=entry_id,
        )


def _validate_segment(value: str) -> None:
    if value in ("", ".", "..") or ".." in value or "/" in value or "\\" in value:
        raise PathOutsideRootError(value)
