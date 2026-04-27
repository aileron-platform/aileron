"""Canvas module service"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasRoute,
    CanvasRoutesResponse,
)

logger = logging.getLogger(__name__)

CANVAS_API_URL = os.getenv("CANVAS_API_URL", "http://localhost:3013")
CANVAS_INTERNAL_URL = os.getenv("CANVAS_INTERNAL_URL", "http://localhost:3003")


class CanvasService:
    """Manage Canvas detection, routing, health status, sync, reset, and logs."""

    def __init__(self) -> None:
        self._workspace_base = Path("/workspace")
        self._canvas_api_url = CANVAS_API_URL.rstrip("/")
        self._canvas_url = CANVAS_INTERNAL_URL.rstrip("/")

    def detect(self, workspace_id: str) -> CanvasDetectResponse:
        data = self._get_json("/detect", timeout=10.0)
        if data is None:
            data = self._detect_local()

        return CanvasDetectResponse(
            workspaceId=workspace_id,
            type=data.get("type", "default"),
            manifestStatus=data.get("manifestStatus", data.get("manifest_status", "missing")),
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
            manifestStatus=data.get("manifestStatus", data.get("manifest_status", "missing")),
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
            manifestStatus=data.get("manifestStatus", data.get("manifest_status")),
            rendererRunning=bool(data.get("rendererRunning", data.get("renderer_running", False))),
            portAvailable=bool(data.get("portAvailable", data.get("port_available", False))),
            message=data.get("message", ""),
            source=data.get("source"),
            details={k: v for k, v in data.items() if k not in {"status", "message", "source"}},
        )

    def sync(self, workspace_id: str) -> CanvasActionResponse:
        return self._action(workspace_id, "/sync")

    def reset(self, workspace_id: str) -> CanvasActionResponse:
        return self._action(workspace_id, "/reset")

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
            manifestStatus=data.get("manifestStatus", data.get("manifest_status")),
            message=data.get("message", ""),
            details=data,
        )

    def _get_json(self, path: str, *, timeout: float) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self._canvas_api_url}{path}")
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("Canvas GET %s failed: %s", path, exc)
            return None

    def _post_json(self, path: str, *, timeout: float) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self._canvas_api_url}{path}")
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("Canvas POST %s failed: %s", path, exc)
            return None

    def _detect_local(self) -> dict[str, Any]:
        manifest_path = self._workspace_base / "route.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                routes = data.get("routes") if isinstance(data.get("routes"), list) else []
                return {
                    "type": data.get("type", "default"),
                    "manifestStatus": "valid",
                    "defaultPath": data.get("defaultPath", "/"),
                    "routes": routes,
                }
            except Exception as exc:
                return {
                    "type": "default",
                    "manifestStatus": "invalid",
                    "defaultPath": "/",
                    "routes": [],
                    "error": str(exc),
                }

        html_files = sorted(self._workspace_base.glob("*.html"))
        if html_files:
            routes = [
                {"path": "/" if item.name == "index.html" else f"/{item.stem}", "file": item.name}
                for item in html_files
            ]
            return {
                "type": "html",
                "manifestStatus": "missing",
                "defaultPath": routes[0]["path"],
                "routes": routes,
            }

        package_json = self._workspace_base / "package.json"
        if package_json.exists() and "next" in package_json.read_text(encoding="utf-8", errors="ignore"):
            return {
                "type": "nextjs",
                "manifestStatus": "missing",
                "defaultPath": "/",
                "routes": [{"path": "/"}],
            }

        return {
            "type": "default",
            "manifestStatus": "missing",
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
                result.append(CanvasRoute(path=item["path"], file=item.get("file")))
        return result

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]
