"""Public seam tests for Manager-owned capacity governance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.authorization.platform_resources import PlatformResourceInventory
from app.modules.platform_resource_capacity.errors import PlatformResourceError
from app.modules.platform_resource_capacity.lifecycle import (
    PlatformResourceCapacityAdministration,
)
from app.modules.platform_resource_capacity.models import (
    KnowledgeBaseQuotaRequest,
    StorageObservation,
    WorkspaceStorageDesiredState,
    WorkspaceStorageObservation,
)
from app.modules.platform_resource_capacity.policy import CapacityGovernancePolicy


def _workspace(*, workspace_id: str, owner_id: str) -> db_models.Workspace:
    return db_models.Workspace(
        id=workspace_id,
        owner_id=owner_id,
        name=workspace_id,
        provisioner="kubernetes",
        runtime_status="running",
    )


def _observation(
    *, workspace_id: str, storage_kind: str, used: int, measured_at: datetime
) -> db_models.ResourceCapacityObservation:
    return db_models.ResourceCapacityObservation(
        resource_type="workspace",
        resource_id=workspace_id,
        storage_kind=storage_kind,
        used_bytes=used,
        allocated_bytes=100,
        provisioner="kubernetes",
        measured_at=measured_at,
        received_at=measured_at,
        measurement_source="runtime",
    )


def _operator_observation(
    *,
    storage_kind: str,
    allocated_bytes: int,
    observed_revision: int,
    expansion_supported: bool = True,
    error_code: str | None = None,
) -> WorkspaceStorageObservation:
    return WorkspaceStorageObservation(
        items=(
            StorageObservation(
                storage_kind=storage_kind,  # type: ignore[arg-type]
                allocated_bytes=allocated_bytes,
                observed_revision=observed_revision,
                expansion_supported=expansion_supported,
                error_code=error_code,
                observed_at=None,
            ),
        )
    )


def test_inventory_capacity_filter_matches_authoritative_projection(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="capacity-policy-admin", platform_role="admin")
    owner = create_user(id="capacity-policy-owner", platform_role="member")
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add_all(
            [
                _workspace(workspace_id="critical-with-stale", owner_id=owner.id),
                _workspace(workspace_id="warning", owner_id=owner.id),
                _workspace(workspace_id="stale", owner_id=owner.id),
                _workspace(workspace_id="unknown", owner_id=owner.id),
                _observation(
                    workspace_id="critical-with-stale",
                    storage_kind="workspace_data",
                    used=95,
                    measured_at=now,
                ),
                _observation(
                    workspace_id="critical-with-stale",
                    storage_kind="runtime_home",
                    used=10,
                    measured_at=now - timedelta(hours=3),
                ),
                _observation(
                    workspace_id="warning",
                    storage_kind="workspace_data",
                    used=80,
                    measured_at=now,
                ),
                _observation(
                    workspace_id="stale",
                    storage_kind="workspace_data",
                    used=95,
                    measured_at=now - timedelta(hours=3),
                ),
                db_models.WorkspaceStorageAllocation(
                    workspace_id="critical-with-stale",
                    storage_kind="workspace_data",
                    desired_bytes=100,
                    observed_bytes=100,
                    revision=1,
                    observed_revision=1,
                    expansion_supported=True,
                    phase="completed",
                ),
                db_models.WorkspaceStorageAllocation(
                    workspace_id="warning",
                    storage_kind="workspace_data",
                    desired_bytes=100,
                    observed_bytes=100,
                    revision=1,
                    observed_revision=1,
                    expansion_supported=False,
                    phase="completed",
                ),
            ]
        )
        session.commit()
        inventory = PlatformResourceInventory(session)

        expected = {
            "critical": ["critical-with-stale"],
            "warning": ["warning"],
            "stale": ["stale"],
            "unknown": ["unknown"],
        }
        for risk, workspace_ids in expected.items():
            result = inventory.list_workspaces(
                actor=actor_from_valid_user(admin),
                q=None,
                page=1,
                page_size=25,
                capacity_risk=risk,
                sort="name",
                order="asc",
            )
            assert [item.id for item in result.items] == workspace_ids
            assert all(item.capacity_risk == risk for item in result.items)
            if risk == "critical":
                assert result.items[0].workspace_data is not None
                assert result.items[0].workspace_data.expansion_supported is True
            if risk == "warning":
                assert result.items[0].workspace_data is not None
                assert result.items[0].workspace_data.expansion_supported is False


def test_policy_owns_thresholds_and_freshness() -> None:
    now = datetime.now(timezone.utc)

    assert (
        CapacityGovernancePolicy.assess(
            used_bytes=79,
            allocated_bytes=100,
            measured_at=now,
            now=now,
        ).risk
        == "normal"
    )
    assert (
        CapacityGovernancePolicy.assess(
            used_bytes=80,
            allocated_bytes=100,
            measured_at=now,
            now=now,
        ).risk
        == "warning"
    )
    assert (
        CapacityGovernancePolicy.assess(
            used_bytes=95,
            allocated_bytes=100,
            measured_at=now,
            now=now,
        ).risk
        == "critical"
    )
    assert (
        CapacityGovernancePolicy.assess(
            used_bytes=95,
            allocated_bytes=100,
            measured_at=now - timedelta(hours=2, seconds=1),
            now=now,
        ).risk
        == "stale"
    )


def test_quota_admin_can_override_and_reset_to_platform_default(
    test_app, create_user
) -> None:
    _, session_factory = test_app
    admin = create_user(id="capacity-quota-admin", platform_role="admin")
    owner = create_user(id="capacity-quota-owner", platform_role="member")
    with session_factory() as session:
        knowledge_base = db_models.KnowledgeBase(
            id="capacity-quota-kb",
            slug="capacity-quota-kb",
            name="Capacity quota KB",
            owner_id=owner.id,
            current_size_bytes=10,
            quota_bytes=None,
        )
        session.add(knowledge_base)
        session.commit()
        administration = PlatformResourceCapacityAdministration(session)

        custom = administration.set_knowledge_base_quota(
            actor=actor_from_valid_user(admin),
            knowledge_base_id=knowledge_base.id,
            payload=KnowledgeBaseQuotaRequest(quotaBytes=100),
        )
        inherited = administration.set_knowledge_base_quota(
            actor=actor_from_valid_user(admin),
            knowledge_base_id=knowledge_base.id,
            payload=KnowledgeBaseQuotaRequest(quotaBytes=None),
        )

        assert custom.quota_source == "custom"
        assert custom.effective_quota_bytes == 100
        assert inherited.quota_source == "platform_default"
        assert inherited.quota_bytes is None
        assert (
            inherited.effective_quota_bytes
            == administration.settings.DEFAULT_KB_QUOTA_BYTES
        )


def test_quota_rejects_member_and_value_below_current_usage(
    test_app, create_user
) -> None:
    _, session_factory = test_app
    admin = create_user(id="capacity-quota-denial-admin", platform_role="admin")
    member = create_user(id="capacity-quota-denial-member", platform_role="member")
    with session_factory() as session:
        knowledge_base = db_models.KnowledgeBase(
            id="capacity-quota-denial-kb",
            slug="capacity-quota-denial-kb",
            name="Capacity quota denial KB",
            owner_id=member.id,
            current_size_bytes=100,
        )
        session.add(knowledge_base)
        session.commit()
        administration = PlatformResourceCapacityAdministration(session)

        with pytest.raises(AuthorizationOperationError):
            administration.set_knowledge_base_quota(
                actor=actor_from_valid_user(member),
                knowledge_base_id=knowledge_base.id,
                payload=KnowledgeBaseQuotaRequest(quotaBytes=200),
            )
        with pytest.raises(PlatformResourceError) as below_usage:
            administration.set_knowledge_base_quota(
                actor=actor_from_valid_user(admin),
                knowledge_base_id=knowledge_base.id,
                payload=KnowledgeBaseQuotaRequest(quotaBytes=99),
            )
        assert below_usage.value.error_code == "KNOWLEDGE_BASE_QUOTA_BELOW_USAGE"


def test_expansion_request_persists_allocation_request_and_revision_atomically(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="capacity-request-admin", platform_role="admin")
    owner = create_user(id="capacity-request-owner", platform_role="member")
    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(_workspace(workspace_id="capacity-request", owner_id=owner.id))
        session.add(
            _observation(
                workspace_id="capacity-request",
                storage_kind="workspace_data",
                used=20,
                measured_at=now,
            )
        )
        session.commit()
        lifecycle = PlatformResourceCapacityAdministration(session)

        response = lifecycle.request_workspace_expansion(
            actor=actor_from_valid_user(admin),
            workspace_id="capacity-request",
            storage_kind="workspace_data",
            requested_bytes=2 * 1024**3,
        )

        allocation = session.scalar(
            select(db_models.WorkspaceStorageAllocation).where(
                db_models.WorkspaceStorageAllocation.workspace_id == "capacity-request",
                db_models.WorkspaceStorageAllocation.storage_kind == "workspace_data",
            )
        )
        request = session.get(
            db_models.WorkspaceCapacityExpansionRequest, response.request_id
        )
        assert allocation is not None
        assert request is not None
        assert allocation.revision == 1
        assert allocation.observed_revision == 0
        assert request.target_revision == allocation.revision
        with pytest.raises(PlatformResourceError) as in_flight:
            lifecycle.request_workspace_expansion(
                actor=actor_from_valid_user(admin),
                workspace_id="capacity-request",
                storage_kind="workspace_data",
                requested_bytes=3 * 1024**3,
            )
        assert in_flight.value.error_code == "WORKSPACE_CAPACITY_EXPANSION_IN_FLIGHT"


def test_operator_status_requires_current_revision_and_observed_capacity(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="capacity-revision-owner", platform_role="member")

    with session_factory() as session:
        session.add(_workspace(workspace_id="capacity-revision", owner_id=owner.id))
        allocation = db_models.WorkspaceStorageAllocation(
            workspace_id="capacity-revision",
            storage_kind="workspace_data",
            desired_bytes=30,
            observed_bytes=20,
            revision=2,
            observed_revision=1,
            phase="applying",
        )
        request = db_models.WorkspaceCapacityExpansionRequest(
            id="revision-request",
            workspace_id="capacity-revision",
            storage_kind="workspace_data",
            previous_bytes=20,
            requested_bytes=30,
            target_revision=2,
            requested_by_user_id=owner.id,
            phase="applying",
        )
        session.add_all([allocation, request])
        session.commit()
        lifecycle = PlatformResourceCapacityAdministration(session)

        stale_changed = lifecycle.reconcile_operator_observation(
            workspace_id="capacity-revision",
            observation=_operator_observation(
                storage_kind="workspace_data",
                allocated_bytes=20,
                observed_revision=1,
            ),
        )
        assert stale_changed is False
        assert allocation.phase == "applying"
        assert request.phase == "applying"

        applying_changed = lifecycle.reconcile_operator_observation(
            workspace_id="capacity-revision",
            observation=_operator_observation(
                storage_kind="workspace_data",
                allocated_bytes=25,
                observed_revision=2,
            ),
        )
        assert applying_changed is True
        assert allocation.phase == "applying"
        assert request.phase == "applying"
        assert allocation.observed_revision == 2
        assert allocation.expansion_supported is True

        completed_changed = lifecycle.reconcile_operator_observation(
            workspace_id="capacity-revision",
            observation=_operator_observation(
                storage_kind="workspace_data",
                allocated_bytes=30,
                observed_revision=2,
            ),
        )
        assert completed_changed is True
        assert allocation.phase == "completed"
        assert request.phase == "completed"

        assert (
            lifecycle.reconcile_operator_observation(
                workspace_id="capacity-revision",
                observation=_operator_observation(
                    storage_kind="workspace_data",
                    allocated_bytes=25,
                    observed_revision=2,
                    error_code="STORAGE_CLASS_EXPANSION_UNSUPPORTED",
                ),
            )
            is False
        )
        assert allocation.phase == "completed"
        assert request.phase == "completed"


def test_expansion_request_fails_closed_when_operator_reports_unsupported(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="capacity-unsupported-admin", platform_role="admin")
    owner = create_user(id="capacity-unsupported-owner", platform_role="member")
    with session_factory() as session:
        session.add_all(
            [
                _workspace(
                    workspace_id="capacity-unsupported",
                    owner_id=owner.id,
                ),
                db_models.WorkspaceStorageAllocation(
                    workspace_id="capacity-unsupported",
                    storage_kind="workspace_data",
                    desired_bytes=1024**3,
                    observed_bytes=1024**3,
                    revision=1,
                    observed_revision=1,
                    expansion_supported=False,
                    phase="completed",
                ),
            ]
        )
        session.commit()

        with pytest.raises(PlatformResourceError) as unsupported:
            PlatformResourceCapacityAdministration(session).request_workspace_expansion(
                actor=actor_from_valid_user(admin),
                workspace_id="capacity-unsupported",
                storage_kind="workspace_data",
                requested_bytes=2 * 1024**3,
            )

        assert unsupported.value.error_code == (
            "WORKSPACE_CAPACITY_EXPANSION_UNSUPPORTED"
        )


def test_manager_derives_failed_phase_and_keeps_it_terminal(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="capacity-failure-owner", platform_role="member")
    admin = create_user(id="capacity-failure-admin", platform_role="admin")

    with session_factory() as session:
        session.add(_workspace(workspace_id="capacity-failure", owner_id=owner.id))
        allocation = db_models.WorkspaceStorageAllocation(
            workspace_id="capacity-failure",
            storage_kind="runtime_home",
            desired_bytes=2 * 1024**3,
            observed_bytes=1024**3,
            revision=4,
            observed_revision=3,
            phase="applying",
        )
        request = db_models.WorkspaceCapacityExpansionRequest(
            id="failure-request",
            workspace_id="capacity-failure",
            storage_kind="runtime_home",
            previous_bytes=1024**3,
            requested_bytes=2 * 1024**3,
            target_revision=4,
            requested_by_user_id=owner.id,
            phase="applying",
        )
        session.add_all([allocation, request])
        session.commit()
        lifecycle = PlatformResourceCapacityAdministration(session)

        assert (
            lifecycle.reconcile_operator_observation(
                workspace_id="capacity-failure",
                observation=_operator_observation(
                    storage_kind="runtime_home",
                    allocated_bytes=1024**3,
                    observed_revision=4,
                ),
            )
            is True
        )
        assert allocation.phase == "applying"
        assert allocation.operator_error_code is None

        assert (
            lifecycle.reconcile_operator_observation(
                workspace_id="capacity-failure",
                observation=_operator_observation(
                    storage_kind="runtime_home",
                    allocated_bytes=1024**3,
                    observed_revision=4,
                    expansion_supported=False,
                    error_code="STORAGE_CLASS_EXPANSION_UNSUPPORTED",
                ),
            )
            is True
        )
        assert allocation.phase == "failed"
        assert request.phase == "failed"
        assert allocation.operator_error_code == ("STORAGE_CLASS_EXPANSION_UNSUPPORTED")
        assert allocation.expansion_supported is False
        session.commit()

        with pytest.raises(PlatformResourceError) as unsupported:
            lifecycle.request_workspace_expansion(
                actor=actor_from_valid_user(admin),
                workspace_id="capacity-failure",
                storage_kind="runtime_home",
                requested_bytes=2 * 1024**3,
            )
        assert unsupported.value.error_code == (
            "WORKSPACE_CAPACITY_EXPANSION_UNSUPPORTED"
        )
        session.rollback()

        assert (
            lifecycle.reconcile_operator_observation(
                workspace_id="capacity-failure",
                observation=_operator_observation(
                    storage_kind="runtime_home",
                    allocated_bytes=1024**3,
                    observed_revision=4,
                ),
            )
            is True
        )
        assert allocation.phase == "failed"
        assert request.phase == "failed"
        assert allocation.expansion_supported is True
        session.commit()

        next_request = lifecycle.request_workspace_expansion(
            actor=actor_from_valid_user(admin),
            workspace_id="capacity-failure",
            storage_kind="runtime_home",
            requested_bytes=2 * 1024**3,
        )
        assert next_request.previous_bytes == 1024**3
        assert allocation.revision == 5
        assert allocation.phase == "pending"
        assert request.phase == "failed"

        assert (
            lifecycle.reconcile_operator_observation(
                workspace_id="capacity-failure",
                observation=_operator_observation(
                    storage_kind="runtime_home",
                    allocated_bytes=2 * 1024**3,
                    observed_revision=5,
                ),
            )
            is True
        )
        refreshed_next = session.get(
            db_models.WorkspaceCapacityExpansionRequest, next_request.request_id
        )
        assert refreshed_next is not None
        assert allocation.phase == "completed"
        assert refreshed_next.phase == "completed"
        assert request.phase == "failed"


def test_delivery_failure_remains_pending_for_idempotent_retry(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="capacity-delivery-owner", platform_role="member")

    with session_factory() as session:
        workspace = _workspace(workspace_id="capacity-delivery", owner_id=owner.id)
        allocation = db_models.WorkspaceStorageAllocation(
            workspace_id=workspace.id,
            storage_kind="workspace_data",
            desired_bytes=30 * 1024**3,
            observed_bytes=20 * 1024**3,
            revision=2,
            observed_revision=1,
            phase="pending",
        )
        session.add_all([workspace, allocation])
        session.commit()
        lifecycle = PlatformResourceCapacityAdministration(session)

        def fail_delivery(
            _workspace: db_models.Workspace, _spec: WorkspaceStorageDesiredState
        ) -> None:
            raise RuntimeError("temporary transport failure")

        assert lifecycle.deliver_reconciling(fail_delivery) == 0
        assert allocation.phase == "pending"
        assert allocation.operator_error_code is None

        delivered_specs: list[WorkspaceStorageDesiredState] = []
        delivered = lifecycle.deliver_reconciling(
            lambda _workspace, spec: delivered_specs.append(spec)
        )

        assert delivered == 2
        assert allocation.phase == "applying"
        assert delivered_specs[0].workspace_data.capacity_bytes == 30 * 1024**3
        assert delivered_specs[0].workspace_data.revision == 2

        assert (
            lifecycle.deliver_reconciling(
                lambda _workspace, spec: delivered_specs.append(spec)
            )
            == 2
        )
        assert delivered_specs[1] == delivered_specs[0]
