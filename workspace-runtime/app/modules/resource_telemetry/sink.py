"""Manager transport adapter for resource telemetry batches."""

from __future__ import annotations

from typing import Protocol

import httpx

from .models import TelemetryBatch


class ResourceTelemetrySink(Protocol):
    async def publish_batch(self, batch: TelemetryBatch) -> None: ...

    async def close(self) -> None: ...


class ManagerResourceTelemetryClient:
    def __init__(
        self,
        *,
        manager_url: str,
        runtime_control_token: str,
        workspace_id: str,
        runtime_instance_id: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self._url = (
            f"{manager_url.rstrip('/')}/api/v1/internal/workspaces/{workspace_id}"
            "/resource-telemetry/batches"
        )
        self._headers = {
            "Authorization": f"Bearer {runtime_control_token}",
            "Content-Type": "application/json",
            "X-Workspace-ID": workspace_id,
            "X-Runtime-Instance-ID": runtime_instance_id,
        }
        self._http = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http = http_client is None

    async def publish_batch(self, batch: TelemetryBatch) -> None:
        response = await self._http.post(
            self._url,
            headers=self._headers,
            json=batch.to_wire(),
        )
        response.raise_for_status()

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()


__all__ = ["ManagerResourceTelemetryClient", "ResourceTelemetrySink"]
