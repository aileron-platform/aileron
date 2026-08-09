"""HTTP seam tests for platform resource analytics."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import models as db_models
from app.modules.workspace.runtime.control_token import issue_runtime_control_token
from tests.helpers.manager_session import authenticate_client_as


def test_admin_summary_route_exposes_stable_shape(
    test_app,
    create_user,
) -> None:
    client, session_factory = test_app
    admin = create_user(id="route-admin", platform_role="admin", role_status="valid")
    owner = create_user(id="route-owner", platform_role="member", role_status="valid")
    observed_at = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id="route-workspace",
                owner_id=owner.id,
                name="Route Workspace",
                provisioner="kubernetes",
                runtime_status="running",
            )
        )
        session.add(
            db_models.ResourceCapacityObservation(
                resource_type="workspace",
                resource_id="route-workspace",
                storage_kind="workspace_data",
                used_bytes=5 * 1024**3,
                allocated_bytes=20 * 1024**3,
                provisioner="kubernetes",
                measured_at=observed_at,
                received_at=observed_at,
                measurement_source="runtime",
            )
        )
        session.commit()

    authenticate_client_as(client, admin)
    summary = client.get(
        "/api/v1/platform-resources/workspaces/statistics/summary?range=30d&refresh=true"
    )
    assert summary.status_code == 200
    assert summary.json()["metrics"]["total"]["value"] == 1
    assert summary.json()["distributions"] == [
        {"key": "running", "count": 1},
        {"key": "transitioning", "count": 0},
        {"key": "stopped", "count": 0},
        {"key": "error", "count": 0},
    ]


def test_runtime_telemetry_route_reuses_generation_identity_and_deduplicates(
    test_app,
    create_user,
) -> None:
    client, session_factory = test_app
    owner = create_user(
        id="runtime-route-owner", platform_role="member", role_status="valid"
    )
    issued = issue_runtime_control_token()
    instance_id = "00000000-0000-4000-8000-000000000123"
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id="runtime-route-workspace",
                owner_id=owner.id,
                name="Runtime Route Workspace",
                provisioner="docker",
                runtime_status="running",
                runtime_control_instance_id=instance_id,
                runtime_control_token_hash=issued.digest,
            )
        )
        session.commit()

    payload = {
        "schemaVersion": 1,
        "batchId": "runtime-route-batch",
        "workspaceId": "runtime-route-workspace",
        "runtimeInstanceId": instance_id,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "events": [
            {
                "eventId": "runtime-route-event",
                "eventType": "agent_session_started",
                "occurredAt": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "capacityMeasurements": [
            {
                "storageKind": "workspace_data",
                "usedBytes": 1024,
                "capacityBytes": 3072,
                "availableBytes": 2048,
                "observedAt": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {issued.value}",
        "X-Workspace-ID": "runtime-route-workspace",
        "X-Runtime-Instance-ID": str(instance_id),
    }
    first = client.post(
        "/api/v1/internal/workspaces/runtime-route-workspace/resource-telemetry/batches",
        json=payload,
        headers=headers,
    )
    duplicate = client.post(
        "/api/v1/internal/workspaces/runtime-route-workspace/resource-telemetry/batches",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 200
    assert first.json()["acceptedEvents"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["deduplicatedEvents"] == 1

    mismatched_payload = {**payload, "workspaceId": "other-workspace"}
    mismatch = client.post(
        "/api/v1/internal/workspaces/runtime-route-workspace/resource-telemetry/batches",
        json=mismatched_payload,
        headers=headers,
    )
    assert mismatch.status_code == 403
    assert mismatch.json()["detail"]["code"] == "workspace_identity_mismatch"

    with session_factory() as session:
        observation = session.scalar(
            select(db_models.ResourceCapacityObservation).where(
                db_models.ResourceCapacityObservation.resource_id
                == "runtime-route-workspace",
                db_models.ResourceCapacityObservation.storage_kind == "workspace_data",
            )
        )
        assert observation is not None
        assert observation.provisioner == "docker"
        assert observation.allocated_bytes is None
        assert observation.host_available_bytes == 2048
