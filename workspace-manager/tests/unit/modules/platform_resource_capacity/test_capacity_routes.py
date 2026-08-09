"""HTTP seam tests for capacity governance."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import models as db_models
from tests.helpers.manager_session import authenticate_client_as


def test_capacity_routes_expose_query_quota_and_expansion_contracts(
    test_app,
    create_user,
) -> None:
    client, session_factory = test_app
    admin = create_user(
        id="capacity-route-admin",
        platform_role="admin",
        role_status="valid",
    )
    owner = create_user(
        id="capacity-route-owner",
        platform_role="member",
        role_status="valid",
    )
    observed_at = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add_all(
            [
                db_models.Workspace(
                    id="capacity-route-workspace",
                    owner_id=owner.id,
                    name="Capacity Route Workspace",
                    provisioner="kubernetes",
                    runtime_status="running",
                ),
                db_models.ResourceCapacityObservation(
                    resource_type="workspace",
                    resource_id="capacity-route-workspace",
                    storage_kind="workspace_data",
                    used_bytes=5 * 1024**3,
                    allocated_bytes=20 * 1024**3,
                    provisioner="kubernetes",
                    measured_at=observed_at,
                    received_at=observed_at,
                    measurement_source="runtime",
                ),
                db_models.WorkspaceStorageAllocation(
                    workspace_id="capacity-route-workspace",
                    storage_kind="workspace_data",
                    desired_bytes=20 * 1024**3,
                    observed_bytes=20 * 1024**3,
                    revision=1,
                    observed_revision=1,
                    expansion_supported=True,
                    phase="completed",
                ),
                db_models.KnowledgeBase(
                    id="capacity-route-kb",
                    slug="capacity-route-kb",
                    name="Capacity Route KB",
                    owner_id=owner.id,
                    current_size_bytes=10,
                ),
            ]
        )
        session.commit()

    authenticate_client_as(client, owner)
    capacity = client.get(
        "/api/v1/workspaces/capacity-route-workspace/capacity?range=7d"
    )
    assert capacity.status_code == 200
    item = capacity.json()["items"][0]
    assert item["storageKind"] == "workspace_data"
    assert item["utilizationPercent"] == 25
    assert item["history"] == []

    authenticate_client_as(client, admin)
    quota = client.put(
        "/api/v1/platform-resources/knowledge-bases/capacity-route-kb/quota",
        json={"quotaBytes": 100},
    )
    assert quota.status_code == 200
    assert quota.json()["effectiveQuotaBytes"] == 100

    expansion = client.post(
        "/api/v1/platform-resources/workspaces/capacity-route-workspace/capacity-expansions",
        json={
            "storageKind": "workspace_data",
            "requestedBytes": 21 * 1024**3,
        },
    )
    assert expansion.status_code == 202
    assert expansion.json()["phase"] == "pending"
