"""Knowledge base sharing service authorization tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select, text

from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.errors import KnowledgeBaseError
from app.db import models as db_models
from app.modules.knowledge_base.access import (
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
)
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.identity.groups import UserGroupService


def _effective_role(session, *, kb_id: str, user_id: str):
    access = KnowledgeBaseAccessResolver(session).resolve(
        knowledge_base_id=kb_id,
        user_id=user_id,
    )
    return access.access_role if access is not None else None


def _create_kb(session, *, kb_id: str, owner_id: str) -> db_models.KnowledgeBase:
    kb = db_models.KnowledgeBase(
        id=kb_id,
        owner_id=owner_id,
        slug=kb_id,
        name=kb_id,
        current_size_bytes=0,
        version_control_enabled=False,
    )
    session.add(kb)
    return kb


def _create_group(
    session,
    *,
    group_id: str,
    name: str,
    member_ids: list[str],
    actor_id: str,
) -> db_models.UserGroup:
    group = db_models.UserGroup(id=group_id, name=name, description=None)
    session.add(group)
    for index, user_id in enumerate(member_ids):
        session.add(
            db_models.UserGroupMember(
                id=f"{group_id}-member-{index}",
                group_id=group_id,
                user_id=user_id,
                created_by_id=actor_id,
            )
        )
    return group


def _create_share(
    session,
    *,
    share_id: str,
    kb_id: str,
    target_type: str,
    target_id: str,
    role: str,
    granted_by_id: str,
) -> db_models.KnowledgeBaseShare:
    share = db_models.KnowledgeBaseShare(
        id=share_id,
        kb_id=kb_id,
        target_type=target_type,
        target_id=target_id,
        role=role,
        granted_by_id=granted_by_id,
    )
    session.add(share)
    return share


def test_revoke_group_share_preserves_overlapping_direct_role(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    member = create_user(id="user-1")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="Support",
            member_ids=[member.id],
            actor_id=owner.id,
        )
        _create_share(
            session,
            share_id="direct-share",
            kb_id="kb-1",
            target_type="user",
            target_id=member.id,
            role="manager",
            granted_by_id=owner.id,
        )
        group_share = _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="reader",
            granted_by_id=owner.id,
        )
        session.commit()

        KnowledgeBaseSharingService(session).revoke_share(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            share_id=group_share.id,
        )

        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            == "manager"
        )
        assert session.get(db_models.KnowledgeBaseShare, "direct-share") is not None
        assert session.get(db_models.KnowledgeBaseShare, "group-share") is None


def test_revoke_group_share_preserves_owner_role(test_app, create_user) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="Owners",
            member_ids=[owner.id],
            actor_id=owner.id,
        )
        group_share = _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="manager",
            granted_by_id=owner.id,
        )
        session.commit()

        KnowledgeBaseSharingService(session).revoke_share(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            share_id=group_share.id,
        )

        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=owner.id,
            )
            == "owner"
        )


def test_direct_share_mutations_update_effective_role(test_app, create_user) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    member = create_user(id="user-1")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        session.commit()
        sharing_service = KnowledgeBaseSharingService(session)
        kb_service = KnowledgeBaseService(session)

        share = sharing_service.grant_share(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            target_type="user",
            target_id=member.id,
            role="manager",
        )
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            == "manager"
        )

        sharing_service.update_share_role(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            share_id=share.id,
            role="reader",
        )
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            == "reader"
        )

        sharing_service.revoke_share(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            share_id=share.id,
        )
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            is None
        )
        with pytest.raises(KnowledgeBaseNotFoundError):
            kb_service.get_kb_for_operation(
                actor=AuthorizationActor(member.id, "member"),
                kb_id="kb-1",
                operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
            )


def test_group_membership_mutations_update_effective_role(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1", platform_role="admin", role_status="valid")
    member = create_user(id="user-1", platform_role="member", role_status="valid")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="Support",
            member_ids=[],
            actor_id=owner.id,
        )
        _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="manager",
            granted_by_id=owner.id,
        )
        session.commit()
        group_service = UserGroupService(session)

        added = group_service.add_members(
            group_id="group-1",
            user_ids=[member.id],
            actor_user_id=owner.id,
        )
        assert added.added_user_ids == [member.id]
        assert added.skipped_user_ids == []
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            == "manager"
        )

        removed = group_service.remove_members(
            group_id="group-1",
            user_ids=[member.id, "missing-user"],
            actor_user_id=owner.id,
        )
        assert removed.removed_user_ids == [member.id]
        assert [failure.user_id for failure in removed.failed_users] == ["missing-user"]
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            is None
        )


def test_removing_one_group_membership_preserves_overlapping_group_role(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1", platform_role="admin", role_status="valid")
    member = create_user(id="user-1", platform_role="member", role_status="valid")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        for group_id, name in (("group-1", "Support"), ("group-2", "Ops")):
            _create_group(
                session,
                group_id=group_id,
                name=name,
                member_ids=[member.id],
                actor_id=owner.id,
            )
            _create_share(
                session,
                share_id=f"share-{group_id}",
                kb_id="kb-1",
                target_type="user_group",
                target_id=group_id,
                role="reader",
                granted_by_id=owner.id,
            )
        session.commit()

        UserGroupService(session).remove_members(
            group_id="group-1",
            user_ids=[member.id],
            actor_user_id=owner.id,
        )

        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            == "reader"
        )


def test_delete_group_removes_group_share_and_access(test_app, create_user) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1", platform_role="admin", role_status="valid")
    member = create_user(id="user-1", platform_role="member", role_status="valid")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="Support",
            member_ids=[member.id],
            actor_id=owner.id,
        )
        _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="reader",
            granted_by_id=owner.id,
        )
        session.commit()

        UserGroupService(session).delete_group(
            group_id="group-1",
            actor_user_id=owner.id,
        )

        assert session.get(db_models.UserGroup, "group-1") is None
        assert session.get(db_models.KnowledgeBaseShare, "group-share") is None
        assert (
            _effective_role(
                session,
                kb_id="kb-1",
                user_id=member.id,
            )
            is None
        )


def test_grant_share_validates_target_contract(test_app, create_user) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    member = create_user(id="user-1")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        session.commit()
        service = KnowledgeBaseSharingService(session)

        with pytest.raises(KnowledgeBaseError) as invalid_type:
            service.grant_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-1",
                target_type="team",
                target_id=member.id,
                role="reader",
            )
        assert invalid_type.value.code == "KB_SHARE_INVALID_TARGET_TYPE"

        with pytest.raises(KnowledgeBaseNotFoundError) as target_not_found:
            service.grant_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-1",
                target_type="user",
                target_id="missing-user",
                role="reader",
            )
        assert target_not_found.value.code == "KB_SHARE_TARGET_NOT_FOUND"

        with pytest.raises(KnowledgeBaseConflictError) as owner_target:
            service.grant_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-1",
                target_type="user",
                target_id=owner.id,
                role="reader",
            )
        assert owner_target.value.code == "KB_SHARE_OWNER_TARGET_FORBIDDEN"

        service.grant_share(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            target_type="user",
            target_id=member.id,
            role="reader",
        )
        with pytest.raises(KnowledgeBaseConflictError) as duplicate:
            service.grant_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-1",
                target_type="user",
                target_id=member.id,
                role="manager",
            )
        assert duplicate.value.code == "KB_SHARE_DUPLICATE_TARGET"


def test_resolve_target_labels_uses_stable_user_columns(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    member = create_user(
        id="user-1",
        display_name="Amelia Chen",
        username="amelia",
        email="amelia@example.com",
    )

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="SA Team",
            member_ids=[],
            actor_id=owner.id,
        )
        user_share = _create_share(
            session,
            share_id="user-share",
            kb_id="kb-1",
            target_type="user",
            target_id=member.id,
            role="reader",
            granted_by_id=owner.id,
        )
        group_share = _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="reader",
            granted_by_id=owner.id,
        )
        session.commit()
        session.execute(text("ALTER TABLE users DROP COLUMN identity_enabled"))
        session.commit()

        labels = KnowledgeBaseSharingService(session).resolve_share_target_labels(
            [user_share, group_share]
        )

        assert labels == {
            "user-share": "Amelia Chen",
            "group-share": "SA Team",
        }


def test_candidate_groups_require_manager_and_exclude_existing_share(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    outsider = create_user(id="user-2")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="SA Team",
            member_ids=[],
            actor_id=owner.id,
        )
        _create_group(
            session,
            group_id="group-2",
            name="Ops Team",
            member_ids=[],
            actor_id=owner.id,
        )
        _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="reader",
            granted_by_id=owner.id,
        )
        session.commit()
        service = KnowledgeBaseSharingService(session)

        results = service.list_share_candidate_groups(
            actor=AuthorizationActor(owner.id, "member"),
            kb_id="kb-1",
            query="team",
            limit=1,
        )
        assert [group.id for group in results] == ["group-2"]

        with pytest.raises(KnowledgeBaseNotFoundError):
            service.list_share_candidate_groups(
                actor=AuthorizationActor(outsider.id, "member"),
                kb_id="kb-1",
                query="",
                limit=8,
            )


def test_user_group_share_grants_effective_kb_access(test_app, create_user) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-1")
    member = create_user(id="user-1")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-1", owner_id=owner.id)
        _create_group(
            session,
            group_id="group-1",
            name="Support",
            member_ids=[member.id],
            actor_id=owner.id,
        )
        _create_share(
            session,
            share_id="group-share",
            kb_id="kb-1",
            target_type="user_group",
            target_id="group-1",
            role="manager",
            granted_by_id=owner.id,
        )
        session.commit()

        _, context = KnowledgeBaseService(session).get_kb_for_operation(
            actor=AuthorizationActor(member.id, "member"),
            kb_id="kb-1",
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        assert context.access_role == "manager"


def test_direct_share_domain_failures_persist_independent_audits(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-failure")
    outsider = create_user(id="outsider-failure")
    member = create_user(id="member-failure")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-failure", owner_id=owner.id)
        session.commit()
        service = KnowledgeBaseSharingService(session)

        with pytest.raises(KnowledgeBaseError) as invalid_role:
            service.grant_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-failure",
                target_type="user",
                target_id=member.id,
                role="owner",
                correlation_id="11111111-1111-4111-8111-111111111111",
            )
        assert invalid_role.value.code == "KB_SHARE_INVALID_ROLE"

        with pytest.raises(KnowledgeBaseNotFoundError) as forbidden:
            service.grant_share(
                actor=AuthorizationActor(outsider.id, "member"),
                kb_id="kb-failure",
                target_type="user",
                target_id=member.id,
                role="reader",
                correlation_id="22222222-2222-4222-8222-222222222222",
            )
        assert forbidden.value.code == "KB_ACCESS_DENIED"

        with pytest.raises(KnowledgeBaseNotFoundError) as missing_update:
            service.update_share_role(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-failure",
                share_id="missing-update",
                role="reader",
                correlation_id="33333333-3333-4333-8333-333333333333",
            )
        assert missing_update.value.code == "KB_SHARE_TARGET_NOT_FOUND"

        with pytest.raises(KnowledgeBaseNotFoundError) as missing_delete:
            service.revoke_share(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-failure",
                share_id="missing-delete",
                correlation_id="44444444-4444-4444-8444-444444444444",
            )
        assert missing_delete.value.code == "KB_SHARE_TARGET_NOT_FOUND"

    with session_factory() as session:
        events = list(
            session.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.result == "failure"
                )
            ).all()
        )

    by_correlation_id = {event.correlation_id: event for event in events}
    assert set(by_correlation_id) == {
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
        "44444444-4444-4444-8444-444444444444",
    }
    assert (
        by_correlation_id["11111111-1111-4111-8111-111111111111"].error_code
        == "KB_SHARE_INVALID_ROLE"
    )
    assert (
        by_correlation_id["22222222-2222-4222-8222-222222222222"].error_code
        == "KB_ACCESS_DENIED"
    )
    assert (
        by_correlation_id["33333333-3333-4333-8333-333333333333"].error_code
        == "KB_SHARE_TARGET_NOT_FOUND"
    )
    assert (
        by_correlation_id["44444444-4444-4444-8444-444444444444"].error_code
        == "KB_SHARE_TARGET_NOT_FOUND"
    )
    assert (
        by_correlation_id["33333333-3333-4333-8333-333333333333"].target_type
        == "knowledge_base_share"
    )
    assert all(event.actor_type == "user" for event in events)


def test_failure_audit_error_does_not_mask_direct_share_domain_error(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="owner-audit-error")

    with session_factory() as session:
        _create_kb(session, kb_id="kb-audit-error", owner_id=owner.id)
        session.commit()
        service = KnowledgeBaseSharingService(session)
        with (
            patch(
                "app.modules.knowledge_base.access.AuditEventService.record",
                side_effect=RuntimeError("audit unavailable"),
            ),
            pytest.raises(KnowledgeBaseNotFoundError) as exc_info,
        ):
            service.update_share_role(
                actor=AuthorizationActor(owner.id, "member"),
                kb_id="kb-audit-error",
                share_id="missing-share",
                role="reader",
            )

    assert exc_info.value.code == "KB_SHARE_TARGET_NOT_FOUND"
