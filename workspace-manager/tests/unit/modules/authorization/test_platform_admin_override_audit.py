"""Platform Admin cross-resource override audit contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.admin_override_audit import (
    IndependentPlatformAdminOverrideAuditWriter,
    PlatformAdminOverrideAuditRecord,
)
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)


@dataclass
class CapturingAuditWriter:
    records: list[PlatformAdminOverrideAuditRecord] = field(default_factory=list)

    def write(self, record: PlatformAdminOverrideAuditRecord) -> None:
        self.records.append(record)


def _add_workspace(session, *, owner_id: str) -> str:
    workspace_id = f"workspace-{uuid4().hex[:8]}"
    session.add(
        db_models.Workspace(
            id=workspace_id,
            owner_id=owner_id,
            name="Admin Override Workspace",
            runtime="universal",
            provisioner="docker",
            runtime_status="stopped",
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
    )
    return workspace_id


def _add_knowledge_base(session, *, owner_id: str) -> str:
    kb_id = f"kb-{uuid4().hex[:8]}"
    session.add(
        db_models.KnowledgeBase(
            id=kb_id,
            owner_id=owner_id,
            slug=kb_id,
            name="Admin Override Knowledge Base",
            description=None,
            current_size_bytes=0,
            quota_bytes=None,
        )
    )
    return kb_id


@pytest.mark.parametrize(
    ("target_type", "success_operation", "denied_operation", "denied_code"),
    (
        (
            "workspace",
            OperationId.WORKSPACE_CONTENT_WRITE,
            OperationId.WORKSPACE_DELETE,
            "WORKSPACE_OPERATION_DENIED",
        ),
        (
            "knowledge_base",
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
            OperationId.KNOWLEDGE_BASE_DELETE,
            "KB_PERMISSION_DENIED",
        ),
    ),
)
def test_admin_cross_resource_override_audits_success_and_denial(
    test_app,
    create_user,
    target_type: str,
    success_operation: OperationId,
    denied_operation: OperationId,
    denied_code: str,
) -> None:
    _, session_factory = test_app
    owner = create_user(platform_role="member", role_status="valid")
    admin = create_user(platform_role="admin", role_status="valid")
    writer = CapturingAuditWriter()

    with session_factory() as session:
        target_id = (
            _add_workspace(session, owner_id=owner.id)
            if target_type == "workspace"
            else _add_knowledge_base(session, owner_id=owner.id)
        )
        session.commit()
        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=writer,
        )
        actor = actor_from_valid_user(admin)
        require_operation = (
            policy.require_workspace_operation
            if target_type == "workspace"
            else policy.require_knowledge_base_operation
        )

        require_operation(actor, target_id, success_operation)
        with pytest.raises(AuthorizationOperationError) as denied:
            require_operation(actor, target_id, denied_operation)

    assert denied.value.error_code == denied_code
    assert writer.records == [
        PlatformAdminOverrideAuditRecord(
            actor_user_id=admin.id,
            target_type=target_type,
            target_id=target_id,
            operation=success_operation.value,
            result="success",
            error_code=None,
        ),
        PlatformAdminOverrideAuditRecord(
            actor_user_id=admin.id,
            target_type=target_type,
            target_id=target_id,
            operation=denied_operation.value,
            result="failure",
            error_code=denied_code,
        ),
    ]


def test_admin_direct_manager_or_owner_access_does_not_audit_override(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner_admin = create_user(platform_role="admin", role_status="valid")
    manager_admin = create_user(platform_role="admin", role_status="valid")
    writer = CapturingAuditWriter()

    with session_factory() as session:
        workspace_id = _add_workspace(session, owner_id=owner_admin.id)
        session.add(
            db_models.WorkspaceShare(
                id=f"share-{uuid4().hex[:8]}",
                workspace_id=workspace_id,
                target_type="user",
                target_id=manager_admin.id,
                granted_by_user_id=owner_admin.id,
                role="manager",
            )
        )
        session.commit()
        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=writer,
        )

        policy.require_workspace_operation(
            actor_from_valid_user(owner_admin),
            workspace_id,
            OperationId.WORKSPACE_DELETE,
        )
        policy.require_workspace_operation(
            actor_from_valid_user(manager_admin),
            workspace_id,
            OperationId.WORKSPACE_CONTENT_WRITE,
        )
        with pytest.raises(AuthorizationOperationError):
            policy.require_workspace_operation(
                actor_from_valid_user(manager_admin),
                workspace_id,
                OperationId.WORKSPACE_DELETE,
            )

    assert writer.records == []


@pytest.mark.parametrize(
    ("target_type", "operation", "error_code"),
    (
        (
            "workspace",
            OperationId.WORKSPACE_DETAIL_READ,
            "WORKSPACE_ACCESS_DENIED",
        ),
        (
            "knowledge_base",
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            "KB_ACCESS_DENIED",
        ),
    ),
)
def test_admin_missing_resource_denial_is_audited_without_ending_caller_transaction(
    test_app,
    create_user,
    target_type: str,
    operation: OperationId,
    error_code: str,
) -> None:
    _, session_factory = test_app
    admin = create_user(platform_role="admin", role_status="valid")
    writer = CapturingAuditWriter()
    target_id = f"missing-{target_type}-{uuid4().hex[:8]}"

    with session_factory() as session:
        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=writer,
        )
        require_operation = (
            policy.require_workspace_operation
            if target_type == "workspace"
            else policy.require_knowledge_base_operation
        )
        with (
            patch.object(session, "commit", wraps=session.commit) as commit,
            patch.object(session, "rollback", wraps=session.rollback) as rollback,
            pytest.raises(AuthorizationOperationError) as denied,
        ):
            require_operation(
                actor_from_valid_user(admin),
                target_id,
                operation,
            )

        commit.assert_not_called()
        rollback.assert_not_called()

    assert (denied.value.error_code, denied.value.http_status) == (error_code, 404)
    assert writer.records == [
        PlatformAdminOverrideAuditRecord(
            actor_user_id=admin.id,
            target_type=target_type,
            target_id=target_id,
            operation=operation.value,
            result="failure",
            error_code=error_code,
        )
    ]


def test_policy_never_commits_or_rolls_back_caller_session(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(platform_role="member", role_status="valid")
    admin = create_user(platform_role="admin", role_status="valid")
    writer = CapturingAuditWriter()

    with session_factory() as session:
        workspace_id = _add_workspace(session, owner_id=owner.id)
        session.commit()
        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=writer,
        )
        with (
            patch.object(session, "commit", wraps=session.commit) as commit,
            patch.object(session, "rollback", wraps=session.rollback) as rollback,
        ):
            policy.require_workspace_operation(
                actor_from_valid_user(admin),
                workspace_id,
                OperationId.WORKSPACE_CONTENT_WRITE,
            )

        commit.assert_not_called()
        rollback.assert_not_called()


@pytest.mark.parametrize(
    ("result", "error_code"),
    (("success", None), ("failure", "WORKSPACE_OPERATION_DENIED")),
)
def test_independent_writer_persists_outside_caller_transaction(
    test_app,
    create_user,
    result: str,
    error_code: str | None,
) -> None:
    _, session_factory = test_app
    admin = create_user(platform_role="admin", role_status="valid")
    writer = IndependentPlatformAdminOverrideAuditWriter(
        session_factory=session_factory
    )
    target_id = f"workspace-{uuid4().hex[:8]}"

    with session_factory() as caller_session:
        writer.write(
            PlatformAdminOverrideAuditRecord(
                actor_user_id=admin.id,
                target_type="workspace",
                target_id=target_id,
                operation=OperationId.WORKSPACE_CONTENT_WRITE.value,
                result=result,
                error_code=error_code,
            )
        )
        caller_session.rollback()

    with session_factory() as verification_session:
        event = verification_session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.target_id == target_id
            )
        )

    assert event is not None
    assert event.event_type == "authorization.platform_admin_override"
    assert event.target_type == "workspace"
    assert event.target_id == target_id
    assert event.action == OperationId.WORKSPACE_CONTENT_WRITE.value
    assert event.result == result
    assert event.error_code == error_code
