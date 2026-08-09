"""Knowledge base consumer authorization convergence tests."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor, actor_from_valid_user
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.knowledge_base.archive import KnowledgeBaseArchiveService


class _AuthorizationProbe(Exception):
    """Stop a consumer immediately after recording its authorization call."""


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "kwargs", "operation"),
    [
        (
            "create_archive_operation",
            {"paths": ["/notes"], "archive_name": None},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "get_archive_status",
            {"operation_id": "archive-1"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "resolve_archive_download",
            {"operation_id": "archive-1"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
    ],
)
def test_archive_callers_use_explicit_operation_ids(
    method_name,
    kwargs,
    operation,
) -> None:
    actor = AuthorizationActor(user_id="member-1", platform_role="member")
    service = KnowledgeBaseArchiveService.__new__(KnowledgeBaseArchiveService)
    service.file_service = type(
        "FileService",
        (),
        {
            "kb_service": type(
                "KbService",
                (),
                {
                    "get_kb_for_operation": lambda self, **call: (
                        (_ for _ in ()).throw(_AuthorizationProbe(call))
                    )
                },
            )()
        },
    )()

    with pytest.raises(_AuthorizationProbe) as probe:
        getattr(service, method_name)(actor=actor, kb_id="kb-1", **kwargs)

    assert probe.value.args[0] == {
        "actor": actor,
        "kb_id": "kb-1",
        "operation": operation,
    }


@pytest.mark.unit
def test_knowledge_base_operation_policy_uses_resource_roles_and_admin_override(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(platform_role="member", role_status="valid")
    member_reader = create_user(platform_role="member", role_status="valid")
    member_manager = create_user(platform_role="member", role_status="valid")
    admin_outsider = create_user(platform_role="admin", role_status="valid")
    kb_id = f"kb-{uuid4().hex[:8]}"

    with session_factory() as session:
        session.add(
            db_models.KnowledgeBase(
                id=kb_id,
                owner_id=owner.id,
                slug=f"policy-{uuid4().hex[:8]}",
                name="Policy Knowledge Base",
                description=None,
                current_size_bytes=0,
                quota_bytes=None,
            )
        )
        for user, role in (
            (member_reader, "reader"),
            (member_manager, "manager"),
        ):
            session.add(
                db_models.KnowledgeBaseShare(
                    id=f"share-{uuid4().hex[:8]}",
                    kb_id=kb_id,
                    target_type="user",
                    target_id=user.id,
                    role=role,
                    granted_by_id=owner.id,
                )
            )
        session.commit()

        override_audit_writer = MagicMock()
        policy = AuthorizationOperationPolicy(
            session,
            override_audit_writer=override_audit_writer,
        )
        with pytest.raises(AuthorizationOperationError) as reader_denied:
            policy.require_knowledge_base_operation(
                actor_from_valid_user(member_reader),
                kb_id,
                OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
            )
        assert (
            reader_denied.value.error_code,
            reader_denied.value.http_status,
        ) == ("KB_PERMISSION_DENIED", 403)

        manager_grant = policy.require_knowledge_base_operation(
            actor_from_valid_user(member_manager),
            kb_id,
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        admin_grant = policy.require_knowledge_base_operation(
            actor_from_valid_user(admin_outsider),
            kb_id,
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        assert manager_grant.access_role.value == "manager"
        assert admin_grant.access_role.value == "manager"
        override_audit_writer.write.assert_called_once()
