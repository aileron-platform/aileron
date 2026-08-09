"""Manager local history adapter."""

from __future__ import annotations

from pathlib import Path

from aileron_file_core import (
    JsonLocalHistoryStore,
    LocalHistoryEntry,
    LocalHistoryService,
)


class ManagerLocalHistoryService:
    """Provide manager domain access to shared local history storage."""

    def __init__(self, *, history_root: Path) -> None:
        self._history_root = Path(history_root)
        self._store = JsonLocalHistoryStore(self._history_root)
        self._snapshot_root = self._history_root / "snapshots"

    def snapshot_file(
        self,
        *,
        domain: str,
        resource_id: str,
        source_path: Path,
        relative_path: str,
        operation: str,
        version_id_before: str | None = None,
        content_hash_before: str | None = None,
    ) -> dict | None:
        entry = self._service(domain, resource_id).snapshot_existing_file(
            source_path=source_path,
            relative_path=relative_path,
            operation=operation,
            version_id_before=version_id_before,
            content_hash_before=content_hash_before,
        )
        if entry is None:
            return None
        return self._to_response(entry)

    def list_entries(
        self,
        *,
        domain: str,
        resource_id: str,
        path: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        return [
            self._to_response(entry)
            for entry in self._service(domain, resource_id).list_entries(
                path=path,
                limit=limit,
            )
        ]

    def get_entry(
        self,
        *,
        domain: str,
        resource_id: str,
        entry_id: str,
    ) -> LocalHistoryEntry:
        return self._service(domain, resource_id).get_entry(entry_id)

    def _service(self, domain: str, resource_id: str) -> LocalHistoryService:
        return LocalHistoryService(
            store=self._store,
            snapshot_root=self._snapshot_root,
            domain=domain,
            resource_id=resource_id,
        )

    @staticmethod
    def _to_response(entry: LocalHistoryEntry) -> dict:
        return {
            "id": entry.id,
            "domain": entry.domain,
            "resourceId": entry.resource_id,
            "path": entry.path,
            "operation": entry.operation,
            "timestamp": entry.timestamp,
            "revisionBefore": entry.version_id_before,
            "revisionAfter": entry.version_id_after,
            "snapshotPath": entry.snapshot_path,
            "size": entry.size,
        }
