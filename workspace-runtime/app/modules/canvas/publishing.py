"""Canvas module service"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from .models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasManifestDeleteResponse,
    CanvasReviewNote,
    CanvasReviewNoteCreate,
    CanvasReviewNoteRecord,
    CanvasReviewNotesResponse,
    CanvasReviewReply,
    CanvasReviewReplyCreate,
    CanvasReviewStatus,
    CanvasRoute,
    CanvasRoutesResponse,
)

logger = logging.getLogger(__name__)

class CanvasService:
    """Manage Canvas detection, routing, health status, sync, reset, and logs."""

    def __init__(
        self,
        *,
        workspace_path: str,
        canvas_api_url: str,
        canvas_internal_url: str,
    ) -> None:
        self._workspace_base = Path(workspace_path)
        self._review_store_path = (
            self._workspace_base / ".aileron" / "canvas-review-notes.json"
        )
        self._canvas_api_url = canvas_api_url.rstrip("/")
        self._canvas_url = canvas_internal_url.rstrip("/")

    def detect(self, workspace_id: str) -> CanvasDetectResponse:
        data = self._get_json("/detect", timeout=10.0)
        if data is None:
            data = self._detect_local()

        return CanvasDetectResponse(
            workspaceId=workspace_id,
            type=data.get("type", "default"),
            kind=data.get("kind"),
            title=data.get("title"),
            owner=data.get("owner"),
            manifestStatus=data.get(
                "manifestStatus", data.get("manifest_status", "missing")
            ),
            runtimeStatus=data.get("runtimeStatus", data.get("runtime_status")),
            defaultPath=data.get("defaultPath", data.get("default_path", "/")),
            routes=self._routes_from_payload(data),
            error=data.get("error"),
            detectedAt=datetime.now(timezone.utc),
        )

    def routes(self, workspace_id: str) -> CanvasRoutesResponse:
        data = self._get_json("/routes", timeout=10.0)
        if data is None:
            data = self._detect_local()

        routes = self._routes_from_payload(data)
        return CanvasRoutesResponse(
            workspaceId=workspace_id,
            type=data.get("type", "default"),
            kind=data.get("kind"),
            title=data.get("title"),
            owner=data.get("owner"),
            manifestStatus=data.get(
                "manifestStatus", data.get("manifest_status", "missing")
            ),
            runtimeStatus=data.get("runtimeStatus", data.get("runtime_status")),
            defaultPath=data.get("defaultPath", data.get("default_path", "/")),
            routes=routes,
            total=len(routes),
            scannedAt=datetime.now(timezone.utc),
        )

    def health(self, workspace_id: str) -> CanvasHealthResponse:
        data = self._get_json("/health", timeout=5.0)
        if data is None:
            return CanvasHealthResponse(
                workspaceId=workspace_id,
                status="unhealthy",
                rendererRunning=False,
                portAvailable=False,
                message="CANVAS_MANAGEMENT_UNAVAILABLE",
            )

        return CanvasHealthResponse(
            workspaceId=workspace_id,
            status=data.get("status", "checking"),
            type=data.get("type"),
            kind=data.get("kind"),
            manifestStatus=data.get("manifestStatus", data.get("manifest_status")),
            runtimeStatus=data.get("runtimeStatus", data.get("runtime_status")),
            rendererRunning=bool(
                data.get("rendererRunning", data.get("renderer_running", False))
            ),
            portAvailable=bool(
                data.get("portAvailable", data.get("port_available", False))
            ),
            message=data.get("message", ""),
            source=data.get("source"),
            details={
                k: v
                for k, v in data.items()
                if k not in {"status", "message", "source"}
            },
        )

    def sync(self, workspace_id: str) -> CanvasActionResponse:
        return self._action(workspace_id, "/sync")

    def reset(self, workspace_id: str) -> CanvasActionResponse:
        return self._action(workspace_id, "/reset")

    def delete_manifest(self, workspace_id: str) -> CanvasManifestDeleteResponse:
        manifest_path = self._workspace_base / ".aileron" / "canvas.json"
        deleted = False
        try:
            manifest_path.unlink()
            deleted = True
        except FileNotFoundError:
            deleted = False

        data = self._post_json("/sync", timeout=60.0) or {}
        raw_detection = data.get("detection")
        detection = raw_detection if isinstance(raw_detection, dict) else data
        return CanvasManifestDeleteResponse(
            workspaceId=workspace_id,
            deleted=deleted,
            manifestStatus=detection.get(
                "manifestStatus", data.get("manifestStatus", "missing")
            ),
            runtimeStatus=detection.get("runtimeStatus", data.get("runtimeStatus")),
        )

    def logs(self, workspace_id: str) -> CanvasLogsResponse:
        data = self._get_json("/logs", timeout=10.0) or {}
        logs = self._string_list(data.get("logs"))
        renderer_logs = self._string_list(
            data.get("rendererLogs", data.get("renderer_logs", []))
        )
        return CanvasLogsResponse(
            workspaceId=workspace_id,
            logs=logs,
            rendererLogs=renderer_logs,
            total=len(logs) + len(renderer_logs),
        )

    def list_review_notes(
        self,
        workspace_id: str,
        *,
        status: CanvasReviewStatus | None = None,
        route_path: str | None = None,
    ) -> CanvasReviewNotesResponse:
        notes = [
            note.to_response()
            for note in self._read_review_notes()
            if note.workspace_id == workspace_id
        ]
        if status:
            notes = [note for note in notes if note.status == status]
        if route_path:
            notes = [note for note in notes if note.route_path == route_path]
        notes.sort(key=lambda note: note.created_at)
        return CanvasReviewNotesResponse(
            workspaceId=workspace_id,
            notes=notes,
            total=len(notes),
        )

    def create_review_note(
        self,
        workspace_id: str,
        payload: CanvasReviewNoteCreate,
    ) -> CanvasReviewNote:
        now = datetime.now(timezone.utc)
        record = CanvasReviewNoteRecord(
            workspaceId=workspace_id,
            sessionId=payload.session_id,
            routePath=payload.route_path,
            canvasUrl=payload.canvas_url,
            target=payload.target,
            instruction=payload.instruction,
            status=payload.status,
            createdAt=now,
            updatedAt=now,
        )
        notes = self._read_review_notes()
        notes.append(record)
        self._write_review_notes(notes)
        return record.to_response()

    def update_review_note_status(
        self,
        workspace_id: str,
        note_id: str,
        status: CanvasReviewStatus,
    ) -> CanvasReviewNote:
        notes = self._read_review_notes()
        record = self._find_review_note(notes, workspace_id, note_id)
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        record.resolved_at = (
            record.updated_at if status in {"applied", "dismissed"} else None
        )
        self._write_review_notes(notes)
        return record.to_response()

    def append_review_note_reply(
        self,
        workspace_id: str,
        note_id: str,
        payload: CanvasReviewReplyCreate,
    ) -> CanvasReviewNote:
        notes = self._read_review_notes()
        record = self._find_review_note(notes, workspace_id, note_id)
        record.replies.append(
            CanvasReviewReply(role=payload.role, content=payload.content)
        )
        record.updated_at = datetime.now(timezone.utc)
        self._write_review_notes(notes)
        return record.to_response()

    def delete_review_note(self, workspace_id: str, note_id: str) -> None:
        notes = self._read_review_notes()
        next_notes = [
            note
            for note in notes
            if not (note.workspace_id == workspace_id and note.id == note_id)
        ]
        if len(next_notes) == len(notes):
            raise self._not_found()
        self._write_review_notes(next_notes)

    def _action(self, workspace_id: str, path: str) -> CanvasActionResponse:
        data = self._post_json(path, timeout=60.0)
        if data is None:
            return CanvasActionResponse(
                workspaceId=workspace_id,
                status="error",
                message="CANVAS_MANAGEMENT_UNAVAILABLE",
            )

        return CanvasActionResponse(
            workspaceId=workspace_id,
            status=data.get("status", "ok"),
            type=data.get("type"),
            kind=data.get("kind"),
            manifestStatus=data.get("manifestStatus", data.get("manifest_status")),
            runtimeStatus=data.get("runtimeStatus", data.get("runtime_status")),
            message=data.get("message", ""),
            syncedAt=data.get("syncedAt", data.get("synced_at")),
            resetAt=data.get("resetAt", data.get("reset_at")),
            rendererAction=data.get("rendererAction", data.get("renderer_action")),
            rendererActionReason=data.get(
                "rendererActionReason", data.get("renderer_action_reason")
            ),
            details=data,
        )

    def _get_json(self, path: str, *, timeout: float) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self._canvas_api_url}{path}")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Canvas response must be a JSON object")
                return {str(key): value for key, value in payload.items()}
        except Exception as exc:
            logger.warning("Canvas GET %s failed: %s", path, exc)
            return None

    def _post_json(self, path: str, *, timeout: float) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self._canvas_api_url}{path}")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Canvas response must be a JSON object")
                return {str(key): value for key, value in payload.items()}
        except Exception as exc:
            logger.warning("Canvas POST %s failed: %s", path, exc)
            return None

    def _detect_local(self) -> dict[str, Any]:
        manifest_path = self._workspace_base / ".aileron" / "canvas.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                routes = (
                    data.get("routes") if isinstance(data.get("routes"), list) else []
                )
                return {
                    "type": "active",
                    "kind": data.get("kind"),
                    "title": data.get("title"),
                    "owner": data.get("owner"),
                    "manifestStatus": "valid",
                    "runtimeStatus": "unhealthy",
                    "defaultPath": data.get("defaultPath", "/"),
                    "routes": routes,
                }
            except Exception as exc:
                return {
                    "type": "default",
                    "manifestStatus": "invalid",
                    "runtimeStatus": "unhealthy",
                    "defaultPath": "/",
                    "routes": [],
                    "error": str(exc),
                }

        return {
            "type": "default",
            "manifestStatus": "missing",
            "runtimeStatus": "unhealthy",
            "defaultPath": "/",
            "routes": [{"path": "/"}],
        }

    def _routes_from_payload(self, data: dict[str, Any]) -> list[CanvasRoute]:
        routes = data.get("routes")
        if not isinstance(routes, list):
            return []

        result: list[CanvasRoute] = []
        for item in routes:
            if isinstance(item, str):
                result.append(CanvasRoute(path=item))
            elif isinstance(item, dict) and item.get("path"):
                result.append(CanvasRoute(path=item["path"], label=item.get("label")))
        return result

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _read_review_notes(self) -> list[CanvasReviewNoteRecord]:
        if not self._review_store_path.exists():
            return []
        try:
            raw = json.loads(self._review_store_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read Canvas review notes: %s", exc)
            return []
        if not isinstance(raw, list):
            return []
        records = []
        for item in raw:
            try:
                records.append(CanvasReviewNoteRecord.model_validate(item))
            except Exception as exc:
                logger.warning("Skipping invalid Canvas review note record: %s", exc)
        return records

    def _write_review_notes(self, notes: list[CanvasReviewNoteRecord]) -> None:
        self._review_store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [note.model_dump(mode="json", by_alias=True) for note in notes]
        self._review_store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_review_note(
        self,
        notes: list[CanvasReviewNoteRecord],
        workspace_id: str,
        note_id: str,
    ) -> CanvasReviewNoteRecord:
        for note in notes:
            if note.workspace_id == workspace_id and note.id == note_id:
                return note
        raise self._not_found()

    def _not_found(self) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail={"errorCode": "CANVAS_REVIEW_NOTE_NOT_FOUND"},
        )
