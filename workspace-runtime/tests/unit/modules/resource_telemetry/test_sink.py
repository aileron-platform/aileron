from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.modules.resource_telemetry.models import (
    CapacityMeasurement,
    ResourceActivityEvent,
    TelemetryBatch,
)
from app.modules.resource_telemetry.sink import ManagerResourceTelemetryClient


@pytest.mark.asyncio
async def test_manager_sink_publishes_stable_batch_contract_and_runtime_identity() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202)

    observed_at = datetime(2026, 8, 1, 3, 4, 5, tzinfo=timezone.utc)
    batch = TelemetryBatch(
        batch_id="batch-1",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        observed_at=observed_at,
        events=(
            ResourceActivityEvent(
                event_id="event-1",
                event_type="runtime_started",
                occurred_at=observed_at,
            ),
        ),
        capacity_measurements=(
            CapacityMeasurement(
                storage_kind="workspace_data",
                used_bytes=12,
                capacity_bytes=100,
                available_bytes=88,
                observed_at=observed_at,
            ),
        ),
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ManagerResourceTelemetryClient(
            manager_url="http://manager/",
            runtime_control_token="scoped-token",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            http_client=http,
        )
        await client.publish_batch(batch)

    assert len(requests) == 1
    request = requests[0]
    assert request.url == httpx.URL(
        "http://manager/api/v1/internal/workspaces/workspace-1/resource-telemetry/batches"
    )
    assert request.headers["Authorization"] == "Bearer scoped-token"
    assert request.headers["X-Workspace-ID"] == "workspace-1"
    assert (
        request.headers["X-Runtime-Instance-ID"]
        == "11111111-1111-4111-8111-111111111111"
    )
    assert json.loads(request.content) == {
        "schemaVersion": 1,
        "batchId": "batch-1",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "observedAt": "2026-08-01T03:04:05Z",
        "events": [
            {
                "eventId": "event-1",
                "eventType": "runtime_started",
                "occurredAt": "2026-08-01T03:04:05Z",
            }
        ],
        "capacityMeasurements": [
            {
                "storageKind": "workspace_data",
                "usedBytes": 12,
                "capacityBytes": 100,
                "availableBytes": 88,
                "observedAt": "2026-08-01T03:04:05Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_manager_sink_rejects_non_success_without_hiding_http_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ManagerResourceTelemetryClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            http_client=http,
        )
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.publish_batch(
                TelemetryBatch(
                    batch_id="batch-1",
                    workspace_id="workspace-1",
                    runtime_instance_id="11111111-1111-4111-8111-111111111111",
                    observed_at=datetime.now(timezone.utc),
                    events=(),
                    capacity_measurements=(),
                )
            )

    assert error.value.response.status_code == 503
