"""Public seam tests for platform resource analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.platform_resources import PlatformResourceInventory
from app.modules.knowledge_base.access import KnowledgeBaseService
from app.modules.platform_resource_analytics.analytics import (
    PlatformResourceCapacityMetrics,
)
from app.modules.platform_resource_analytics.ingestion import (
    PlatformResourceTelemetryIngestion,
    RuntimeTelemetryIdentity,
)
from app.modules.platform_resource_analytics.models import (
    CapacityMeasurementInput,
    RuntimeActivityEventInput,
    RuntimeTelemetryBatch,
)
from app.modules.platform_resource_analytics.projection import PlatformResourceAnalytics
from app.modules.platform_resource_capacity.errors import PlatformResourceError
from app.modules.platform_resource_capacity.query import PlatformResourceCapacityQuery


def _workspace(*, workspace_id: str, owner_id: str, provisioner: str = "kubernetes"):
    return db_models.Workspace(
        id=workspace_id,
        owner_id=owner_id,
        name=workspace_id,
        provisioner=provisioner,
        runtime_status="running",
    )


def test_knowledge_base_summary_handles_zero_quota_through_capacity_policy(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="zero-quota-admin", platform_role="admin")
    owner = create_user(id="zero-quota-owner", platform_role="member")
    with session_factory() as session:
        session.add(
            db_models.KnowledgeBase(
                id="zero-quota-kb",
                slug="zero-quota-kb",
                name="Zero quota KB",
                owner_id=owner.id,
                current_size_bytes=0,
                quota_bytes=0,
            )
        )
        session.commit()

        summary = PlatformResourceAnalytics(session).get_summary(
            actor=actor_from_valid_user(admin),
            resource_type="knowledge_base",
            range_value="30d",
            refresh=True,
        )

        assert summary.metrics.near_limit.value == 0


def test_runtime_batch_is_idempotent_and_exposes_latest_workspace_capacity(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="capacity-owner", platform_role="member", role_status="valid"
    )
    observed_at = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(_workspace(workspace_id="workspace-capacity", owner_id=owner.id))
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(session)
        batch = RuntimeTelemetryBatch(
            schemaVersion=1,
            batchId="batch-capacity-1",
            workspaceId="workspace-capacity",
            runtimeInstanceId="runtime-instance-capacity",
            observedAt=observed_at,
            events=[
                RuntimeActivityEventInput(
                    eventId="event-session-1",
                    eventType="agent_session_started",
                    occurredAt=observed_at,
                )
            ],
            capacityMeasurements=[
                CapacityMeasurementInput(
                    storageKind="workspace_data",
                    usedBytes=8 * 1024**3,
                    capacityBytes=20 * 1024**3,
                    availableBytes=12 * 1024**3,
                    observedAt=observed_at,
                ),
                CapacityMeasurementInput(
                    storageKind="runtime_home",
                    usedBytes=1024**3,
                    capacityBytes=2 * 1024**3,
                    availableBytes=1024**3,
                    observedAt=observed_at,
                ),
            ],
        )

        identity = RuntimeTelemetryIdentity(
            route_workspace_id="workspace-capacity",
            header_workspace_id="workspace-capacity",
            authenticated_runtime_instance_id="runtime-instance-capacity",
            expected_runtime_instance_id="runtime-instance-capacity",
        )
        first = ingestion.ingest(identity=identity, batch=batch)
        duplicate = ingestion.ingest(identity=identity, batch=batch)
        capacity = PlatformResourceCapacityQuery(session).get_workspace_capacity(
            actor=actor_from_valid_user(owner),
            workspace_id="workspace-capacity",
            range_value="7d",
        )

        assert first.accepted_events == 1
        assert first.deduplicated_events == 0
        assert duplicate.accepted_events == 0
        assert duplicate.deduplicated_events == 1
        assert duplicate.accepted_measurements == 0
        assert [(item.storage_kind, item.used_bytes) for item in capacity.items] == [
            ("workspace_data", 8 * 1024**3),
            ("runtime_home", 1024**3),
        ]
        assert capacity.items[0].risk == "normal"
        assert capacity.items[0].stale is False


def test_runtime_ingestion_rejects_reused_batch_id_with_different_payload(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="batch-conflict-owner", platform_role="member", role_status="valid"
    )
    observed_at = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(
            _workspace(workspace_id="batch-conflict-workspace", owner_id=owner.id)
        )
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(session)
        identity = RuntimeTelemetryIdentity(
            route_workspace_id="batch-conflict-workspace",
            header_workspace_id="batch-conflict-workspace",
            authenticated_runtime_instance_id="runtime-batch-conflict",
            expected_runtime_instance_id="runtime-batch-conflict",
        )
        first_batch = RuntimeTelemetryBatch(
            schemaVersion=1,
            batchId="batch-conflict",
            workspaceId="batch-conflict-workspace",
            runtimeInstanceId="runtime-batch-conflict",
            observedAt=observed_at,
            events=[],
            capacityMeasurements=[],
        )
        conflicting_batch = first_batch.model_copy(
            update={"observed_at": observed_at.replace(microsecond=1)}
        )

        ingestion.ingest(identity=identity, batch=first_batch)

        with pytest.raises(PlatformResourceError) as error:
            ingestion.ingest(identity=identity, batch=conflicting_batch)

        assert getattr(error.value, "error_code") == "batch_identity_conflict"


def test_workspace_capacity_preserves_last_good_value_and_marks_it_stale(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="stale-owner", platform_role="member", role_status="valid")
    stale_at = datetime.now(timezone.utc) - timedelta(hours=3)

    with session_factory() as session:
        session.add(_workspace(workspace_id="workspace-stale", owner_id=owner.id))
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(session)
        ingestion.ingest(
            identity=RuntimeTelemetryIdentity(
                route_workspace_id="workspace-stale",
                header_workspace_id="workspace-stale",
                authenticated_runtime_instance_id="runtime-instance-stale",
                expected_runtime_instance_id="runtime-instance-stale",
            ),
            batch=RuntimeTelemetryBatch(
                schemaVersion=1,
                batchId="batch-stale-1",
                workspaceId="workspace-stale",
                runtimeInstanceId="runtime-instance-stale",
                observedAt=stale_at,
                capacityMeasurements=[
                    CapacityMeasurementInput(
                        storageKind="workspace_data",
                        usedBytes=19 * 1024**3,
                        capacityBytes=20 * 1024**3,
                        availableBytes=1024**3,
                        observedAt=stale_at,
                    )
                ],
            ),
        )

        capacity = PlatformResourceCapacityQuery(session).get_workspace_capacity(
            actor=actor_from_valid_user(owner),
            workspace_id="workspace-stale",
            range_value="7d",
        )

        assert capacity.items[0].used_bytes == 19 * 1024**3
        assert capacity.items[0].stale is True
        assert capacity.items[0].risk == "stale"


def test_capacity_threshold_crossings_and_recovery_emit_low_sensitivity_events(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="threshold-owner", platform_role="member", role_status="valid"
    )
    started_at = datetime.now(timezone.utc)
    metrics = PlatformResourceCapacityMetrics()

    with session_factory() as session:
        session.add(_workspace(workspace_id="workspace-threshold", owner_id=owner.id))
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(
            session, capacity_metrics=metrics
        )

        for index, used_bytes in enumerate(
            (
                15 * 1024**3,
                17 * 1024**3,
                20 * 1024**3,
                18 * 1024**3,
                10 * 1024**3,
            )
        ):
            observed_at = started_at + timedelta(minutes=index)
            ingestion.ingest(
                identity=RuntimeTelemetryIdentity(
                    route_workspace_id="workspace-threshold",
                    header_workspace_id="workspace-threshold",
                    authenticated_runtime_instance_id="threshold-runtime",
                    expected_runtime_instance_id="threshold-runtime",
                ),
                batch=RuntimeTelemetryBatch(
                    schemaVersion=1,
                    batchId=f"threshold-batch-{index}",
                    workspaceId="workspace-threshold",
                    runtimeInstanceId="threshold-runtime",
                    observedAt=observed_at,
                    capacityMeasurements=[
                        CapacityMeasurementInput(
                            storageKind="workspace_data",
                            usedBytes=used_bytes,
                            capacityBytes=20 * 1024**3,
                            availableBytes=max(0, 20 * 1024**3 - used_bytes),
                            observedAt=observed_at,
                        )
                    ],
                ),
            )

        event_types = session.scalars(
            select(db_models.PlatformResourceActivityEvent.event_type)
            .where(
                db_models.PlatformResourceActivityEvent.resource_id
                == "workspace-threshold",
                db_models.PlatformResourceActivityEvent.event_type.like(
                    "capacity_threshold_%"
                ),
            )
            .order_by(db_models.PlatformResourceActivityEvent.occurred_at)
        ).all()

    assert event_types == [
        "capacity_threshold_warning",
        "capacity_threshold_critical",
        "capacity_threshold_recovered",
        "capacity_threshold_recovered",
    ]
    assert metrics.snapshot() == {
        "capacity_threshold_warning:workspace_data:kubernetes": 1,
        "capacity_threshold_critical:workspace_data:kubernetes": 1,
        "capacity_threshold_recovered:workspace_data:kubernetes": 2,
    }


def test_runtime_ingestion_rejects_identity_before_mutating_storage(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="identity-owner", platform_role="member", role_status="valid"
    )

    with session_factory() as session:
        session.add(_workspace(workspace_id="identity-workspace", owner_id=owner.id))
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(session)

        with pytest.raises(PlatformResourceError) as error:
            ingestion.ingest(
                identity=RuntimeTelemetryIdentity(
                    route_workspace_id="identity-workspace",
                    header_workspace_id="other-workspace",
                    authenticated_runtime_instance_id="runtime-identity",
                    expected_runtime_instance_id="runtime-identity",
                ),
                batch=RuntimeTelemetryBatch(
                    schemaVersion=1,
                    batchId="identity-batch",
                    workspaceId="identity-workspace",
                    runtimeInstanceId="runtime-identity",
                    observedAt=datetime.now(timezone.utc),
                ),
            )

        assert getattr(error.value, "error_code") == "workspace_identity_mismatch"
        assert session.scalar(
            select(db_models.PlatformResourceActivityEvent).where(
                db_models.PlatformResourceActivityEvent.event_id == "identity-event"
            )
        ) is None


def test_runtime_ingestion_rejects_duplicate_capacity_storage_kind(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="validation-owner", platform_role="member", role_status="valid"
    )
    observed_at = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(_workspace(workspace_id="validation-workspace", owner_id=owner.id))
        session.commit()
        ingestion = PlatformResourceTelemetryIngestion(session)
        identity = RuntimeTelemetryIdentity(
            route_workspace_id="validation-workspace",
            header_workspace_id="validation-workspace",
            authenticated_runtime_instance_id="runtime-validation",
            expected_runtime_instance_id="runtime-validation",
        )
        batch = RuntimeTelemetryBatch(
            schemaVersion=1,
            batchId="validation-batch",
            workspaceId="validation-workspace",
            runtimeInstanceId="runtime-validation",
            observedAt=observed_at,
            capacityMeasurements=[
                CapacityMeasurementInput(
                    storageKind="workspace_data",
                    usedBytes=1,
                    capacityBytes=10,
                    availableBytes=9,
                    observedAt=observed_at,
                ),
                CapacityMeasurementInput(
                    storageKind="workspace_data",
                    usedBytes=2,
                    capacityBytes=10,
                    availableBytes=8,
                    observedAt=observed_at,
                ),
            ],
        )

        with pytest.raises(PlatformResourceError) as error:
            ingestion.ingest(identity=identity, batch=batch)

        assert getattr(error.value, "error_code") == "duplicate_capacity_storage_kind"
        assert session.scalar(
            select(db_models.ResourceCapacityObservation).where(
                db_models.ResourceCapacityObservation.resource_id
                == "validation-workspace"
            )
        ) is None


def test_runtime_ingestion_invalidates_projection_only_after_successful_commit(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="invalidation-owner", platform_role="member", role_status="valid"
    )
    observed_at = datetime.now(timezone.utc)

    class RecordingCache:
        def __init__(self) -> None:
            self.invalidated: list[str] = []

        def invalidate(self, resource_type: str) -> None:
            self.invalidated.append(resource_type)

    with session_factory() as session:
        session.add(_workspace(workspace_id="invalidation-workspace", owner_id=owner.id))
        session.commit()
        cache = RecordingCache()
        ingestion = PlatformResourceTelemetryIngestion(session, cache=cache)

        ingestion.ingest(
            identity=RuntimeTelemetryIdentity(
                route_workspace_id="invalidation-workspace",
                header_workspace_id="invalidation-workspace",
                authenticated_runtime_instance_id="runtime-invalidation",
                expected_runtime_instance_id="runtime-invalidation",
            ),
            batch=RuntimeTelemetryBatch(
                schemaVersion=1,
                batchId="invalidation-batch",
                workspaceId="invalidation-workspace",
                runtimeInstanceId="runtime-invalidation",
                observedAt=observed_at,
                capacityMeasurements=[
                    CapacityMeasurementInput(
                        storageKind="workspace_data",
                        usedBytes=1,
                        capacityBytes=10,
                        availableBytes=9,
                        observedAt=observed_at,
                    )
                ],
            ),
        )

        assert cache.invalidated == ["workspace"]


def test_knowledge_base_create_commits_semantic_activity_with_the_resource(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="activity-owner", platform_role="member", role_status="valid"
    )

    with session_factory() as session:
        created = KnowledgeBaseService(session).create_kb(
            actor=actor_from_valid_user(owner),
            name="Activity KB",
            slug="activity-kb",
        )
        events = session.scalars(
            select(db_models.PlatformResourceActivityEvent).where(
                db_models.PlatformResourceActivityEvent.resource_id == created.id
            )
        ).all()

        assert [(event.resource_type, event.event_type) for event in events] == [
            ("knowledge_base", "created")
        ]


def test_inventory_filters_and_sorts_capacity_using_server_side_projection(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(
        id="inventory-admin", platform_role="admin", role_status="valid"
    )
    owner = create_user(
        id="inventory-owner", platform_role="member", role_status="valid"
    )
    measured_at = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add_all(
            [
                _workspace(workspace_id="workspace-warning", owner_id=owner.id),
                _workspace(workspace_id="workspace-normal", owner_id=owner.id),
                db_models.ResourceCapacityObservation(
                    resource_type="workspace",
                    resource_id="workspace-warning",
                    storage_kind="workspace_data",
                    used_bytes=18 * 1024**3,
                    allocated_bytes=20 * 1024**3,
                    provisioner="kubernetes",
                    measured_at=measured_at,
                    received_at=measured_at,
                    measurement_source="runtime",
                ),
                db_models.ResourceCapacityObservation(
                    resource_type="workspace",
                    resource_id="workspace-normal",
                    storage_kind="workspace_data",
                    used_bytes=2 * 1024**3,
                    allocated_bytes=20 * 1024**3,
                    provisioner="kubernetes",
                    measured_at=measured_at,
                    received_at=measured_at,
                    measurement_source="runtime",
                ),
                db_models.WorkspaceStorageAllocation(
                    workspace_id="workspace-warning",
                    storage_kind="workspace_data",
                    desired_bytes=20 * 1024**3,
                    observed_bytes=20 * 1024**3,
                    revision=1,
                    observed_revision=1,
                    expansion_supported=True,
                    phase="completed",
                ),
            ]
        )
        session.commit()

        result = PlatformResourceInventory(session).list_workspaces(
            actor=actor_from_valid_user(admin),
            q=None,
            page=1,
            page_size=25,
            capacity_risk="warning",
            sort="usedBytes",
            order="desc",
        )

        assert [item.id for item in result.items] == ["workspace-warning"]
        assert result.items[0].workspace_data is not None
        assert result.items[0].workspace_data.utilization_percent == 90
        assert result.items[0].workspace_data.expansion_supported is True
        assert result.items[0].capacity_risk == "warning"
