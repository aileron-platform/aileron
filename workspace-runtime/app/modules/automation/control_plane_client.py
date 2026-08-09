"""HTTP client for the Manager Automation control plane."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx

from .schemas import ClaimResponse, CompletionRequest, CompletionResponse


class ControlPlaneConflict(Exception):
    def __init__(self, code: str, *, payload: dict[str, Any]) -> None:
        super().__init__(code)
        self.code = code
        self.payload = payload


class AutomationControlPlaneClient:
    def __init__(
        self,
        *,
        manager_url: str,
        runtime_control_token: str,
        runtime_instance_id: str,
        workspace_id: str,
        http_client: httpx.AsyncClient | None = None,
        retry_delays: Sequence[float] = (0.25, 0.5, 1, 2, 5),
    ) -> None:
        self._base_url = manager_url.rstrip("/")
        self._workspace_id = workspace_id
        self._headers = {
            "Authorization": f"Bearer {runtime_control_token}",
            "Content-Type": "application/json",
            "X-Workspace-ID": workspace_id,
            "X-Runtime-Instance-ID": runtime_instance_id,
        }
        self._http = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http_client is None
        self._retry_delays = tuple(retry_delays) or (0,)
        self._interrupted = asyncio.Event()

    async def claim(
        self, *, runner_instance_id: UUID, claim_request_id: UUID
    ) -> ClaimResponse | None:
        body = self._encode(
            {
                "workspaceId": self._workspace_id,
                "runnerInstanceId": str(runner_instance_id),
                "claimRequestId": str(claim_request_id),
            }
        )
        response = await self._request_with_retry(
            "POST", "/api/v1/internal/automation/executions/claim", body
        )
        if response.status_code == 204:
            return None
        self._raise_for_status(response)
        return ClaimResponse.model_validate(response.json())

    async def complete(
        self, *, execution_id: str, payload: CompletionRequest
    ) -> CompletionResponse:
        body = payload.model_dump_json(by_alias=True).encode()
        response = await self._request_with_retry(
            "POST",
            f"/api/v1/internal/automation/executions/{execution_id}/complete",
            body,
        )
        self._raise_for_status(response)
        return CompletionResponse.model_validate(response.json())

    async def reconcile_restart(self, *, new_runner_instance_id: UUID) -> None:
        body = self._encode(
            {
                "workspaceId": self._workspace_id,
                "newRunnerInstanceId": str(new_runner_instance_id),
            }
        )
        response = await self._request_with_retry(
            "POST",
            f"/api/v1/internal/automation/workspaces/{self._workspace_id}/reconcile-restart",
            body,
        )
        self._raise_for_status(response)

    async def close(self) -> None:
        self.interrupt()
        if self._owns_http:
            await self._http.aclose()

    def interrupt(self) -> None:
        """Interrupt transport retries during whole-Runtime shutdown."""
        self._interrupted.set()

    async def _request_with_retry(
        self, method: str, path: str, body: bytes
    ) -> httpx.Response:
        attempt = 0
        while True:
            if self._interrupted.is_set():
                raise asyncio.CancelledError
            try:
                response = await self._http.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    content=body,
                )
                if response.status_code < 500:
                    return response
            except httpx.TransportError:
                pass
            delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
            attempt += 1
            try:
                await asyncio.wait_for(self._interrupted.wait(), timeout=delay)
            except TimeoutError:
                continue
            raise asyncio.CancelledError

    @staticmethod
    def _encode(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 409:
            payload = response.json()
            detail = payload.get("detail", payload)
            code = detail.get("code", "automation_conflict")
            raise ControlPlaneConflict(str(code), payload=payload)
        response.raise_for_status()


__all__ = ["AutomationControlPlaneClient", "ControlPlaneConflict"]
