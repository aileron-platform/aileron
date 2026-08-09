from __future__ import annotations

from pathlib import Path

from aileron_file_core import (
    JsonLocalHistoryStore,
    LocalHistoryEntry,
    LocalHistoryOperation,
    LocalHistoryService,
)


class WorkspaceLocalHistory:
    def __init__(self, *, history_root: Path, workspace_id: str) -> None:
        self._service = LocalHistoryService(
            store=JsonLocalHistoryStore(Path(history_root)),
            snapshot_root=Path(history_root) / "snapshots",
            domain="workspace",
            resource_id=workspace_id,
        )

    def snapshot_file(
        self,
        *,
        source_path: Path,
        relative_path: str,
        operation: str,
        revision_before: str | None = None,
    ) -> None:
        normalized_operation = self._normalize_operation(operation)
        self._service.snapshot_existing_file(
            source_path=source_path,
            relative_path=relative_path,
            operation=normalized_operation,
            version_id_before=revision_before,
            content_hash_before=revision_before,
        )

    def list_entries(self, *, path: str | None = None, limit: int = 50) -> list[dict]:
        return [
            self._to_response(entry)
            for entry in self._service.list_entries(path=path, limit=limit)
        ]

    def get_entry(self, entry_id: str) -> LocalHistoryEntry:
        return self._service.get_entry(entry_id)

    @staticmethod
    def _normalize_operation(operation: str) -> LocalHistoryOperation:
        match operation:
            case "write":
                return "write"
            case "delete":
                return "delete"
            case "move":
                return "move"
            case "copy":
                return "copy"
            case "upload":
                return "upload"
            case "extract":
                return "extract"
            case "sync":
                return "sync"
            case "discard":
                return "discard"
            case "restore":
                return "restore"
            case _:
                raise ValueError(f"Unsupported local history operation: {operation}")

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
