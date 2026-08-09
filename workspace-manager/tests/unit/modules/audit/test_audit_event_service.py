"""Audit event service contract tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.audit.events import AuditEventService


def _record_event(
    service: AuditEventService,
    **overrides: object,
) -> db_models.AuditEvent:
    values: dict[str, Any] = {
        "event_type": "workspace.knowledge_base_attached",
        "actor_type": "user",
        "actor_id": "user-1",
        "actor_user_id": "user-1",
        "target_type": "workspace",
        "target_id": "workspace-1",
        "action": "attach_knowledge_base",
        "result": "success",
        "error_code": None,
        "correlation_id": "11111111-1111-4111-8111-111111111111",
        "root_correlation_id": "11111111-1111-4111-8111-111111111111",
        "metadata": {
            "workspace_id": "workspace-1",
            "kb_id": "kb-1",
            "desired_mount_revision": 1,
            "reason": "workspace_access_revoked",
        },
    }
    values.update(overrides)
    return service.record(**values)


def test_record_only_adds_and_flushes() -> None:
    session = MagicMock(spec=Session)
    service = AuditEventService(session)

    event = _record_event(service)

    assert event.actor_type == "user"
    assert event.target_type == "workspace"
    assert event.result == "success"
    session.add.assert_called_once_with(event)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("result", "error_code"),
    [
        ("success", "UNEXPECTED_ERROR"),
        ("failure", None),
        ("compensation_required", ""),
        ("unknown", None),
    ],
)
def test_record_rejects_invalid_result_error_combinations(
    result: str,
    error_code: str | None,
) -> None:
    service = AuditEventService(MagicMock(spec=Session))

    with pytest.raises(ValueError):
        _record_event(service, result=result, error_code=error_code)


@pytest.mark.parametrize(
    ("actor_type", "actor_user_id"),
    [
        ("user", None),
        ("service", "user-1"),
        ("unknown", None),
    ],
)
def test_record_rejects_invalid_actor_identity(
    actor_type: str,
    actor_user_id: str | None,
) -> None:
    service = AuditEventService(MagicMock(spec=Session))

    with pytest.raises(ValueError):
        _record_event(
            service,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
        )


def test_record_accepts_service_actor_without_user_foreign_key() -> None:
    service = AuditEventService(MagicMock(spec=Session))

    event = _record_event(
        service,
        actor_type="service",
        actor_id="knowledge_base_mount_reconciler",
        actor_user_id=None,
    )

    assert event.actor_user_id is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"temporary_password": "secret"},
        {"request_body": {"role": "admin"}},
        {"exception_payload": "trace"},
        {"before": {"credential": "secret"}},
        {"reason": "not a stable enum"},
        {"attempt": True},
    ],
)
def test_record_rejects_metadata_outside_safe_allowlist(metadata: dict) -> None:
    service = AuditEventService(MagicMock(spec=Session))

    with pytest.raises(ValueError):
        _record_event(service, metadata=metadata)


def test_record_accepts_safe_metadata_shapes() -> None:
    service = AuditEventService(MagicMock(spec=Session))

    event = _record_event(
        service,
        metadata={
            "changed_fields": ["platform_role", "role_status"],
            "before": "reader",
            "after": "developer",
            "group_id": "group-1",
            "runtime_instance_id": "22222222-2222-4222-8222-222222222222",
            "previous_runtime_instance_id": "33333333-3333-4333-8333-333333333333",
            "new_runtime_instance_id": "44444444-4444-4444-8444-444444444444",
            "target_revision": 3,
            "observed_mount_revision": 2,
            "runtime_access_revision": 4,
            "retry_attempt": 1,
            "reason": "oidc_user_missing",
        },
    )

    assert event.event_metadata["after"] == "developer"
    assert event.event_metadata["retry_attempt"] == 1


def test_query_helpers_return_attempt_and_root_lineage(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(
        id="audit-user",
        platform_role="admin",
        role_status="valid",
    )

    with session_factory() as session:
        service = AuditEventService(session)
        first = _record_event(
            service,
            actor_id="audit-user",
            actor_user_id="audit-user",
            correlation_id="55555555-5555-4555-8555-555555555555",
            root_correlation_id="55555555-5555-4555-8555-555555555555",
        )
        session.commit()
        second = _record_event(
            service,
            event_type="runtime.mount_sync_failed",
            actor_type="service",
            actor_id="knowledge_base_mount_reconciler",
            actor_user_id=None,
            action="reconcile_knowledge_base_mount",
            result="failure",
            error_code="WORKSPACE_KB_MOUNT_RECONCILE_FAILED",
            correlation_id="66666666-6666-4666-8666-666666666666",
            root_correlation_id="55555555-5555-4555-8555-555555555555",
            metadata={
                "workspace_id": "workspace-1",
                "target_revision": 1,
                "reason": "mount_reconcile_failed",
            },
        )
        session.commit()

        attempt_events = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(db_models.AuditEvent.correlation_id == second.correlation_id)
                .order_by(db_models.AuditEvent.created_at, db_models.AuditEvent.id)
            ).all()
        )
        lineage_events = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(
                    db_models.AuditEvent.root_correlation_id
                    == first.root_correlation_id
                )
                .order_by(db_models.AuditEvent.created_at, db_models.AuditEvent.id)
            ).all()
        )
        attempt_event_ids = [event.id for event in attempt_events]
        lineage_event_ids = {event.id for event in lineage_events}
        first_id = first.id
        second_id = second.id

    assert attempt_event_ids == [second_id]
    assert lineage_event_ids == {first_id, second_id}


def test_caller_rollback_removes_flushed_audit_event(test_app, create_user) -> None:
    _, session_factory = test_app
    create_user(id="rollback-user")
    correlation_id = "77777777-7777-4777-8777-777777777777"

    with session_factory() as session:
        service = AuditEventService(session)
        _record_event(
            service,
            actor_id="rollback-user",
            actor_user_id="rollback-user",
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
        )
        session.rollback()

        events = list(
            session.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.correlation_id == correlation_id
                )
            ).all()
        )
        assert events == []
