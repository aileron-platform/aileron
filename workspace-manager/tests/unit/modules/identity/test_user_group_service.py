"""User group service tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db import models as db_models
from app.modules.identity.groups import UserGroupService


def _persist_group(session, group_id: str = "group-1") -> None:
    session.add(
        db_models.UserGroup(id=group_id, name=f"Group {group_id}", description=None)
    )
    session.commit()


def _persist_group_workspace_access(
    session,
    *,
    owner_id: str,
    member_id: str,
    group_id: str = "group-access",
    workspace_id: str = "workspace-access",
    direct_role: str | None = None,
) -> None:
    session.add_all(
        [
            db_models.UserGroup(id=group_id, name="Access Group"),
            db_models.UserGroupMember(
                id=f"{group_id}-member",
                group_id=group_id,
                user_id=member_id,
                created_by_id=owner_id,
            ),
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Shared Workspace",
                provisioner="docker",
                runtime_status="stopped",
            ),
        ]
    )
    session.flush()
    session.add(
        db_models.WorkspaceShare(
            id=f"{workspace_id}-group-share",
            workspace_id=workspace_id,
            target_type="user_group",
            target_id=group_id,
            role="manager",
            granted_by_user_id=owner_id,
        )
    )
    if direct_role is not None:
        session.add(
            db_models.WorkspaceShare(
                id=f"{workspace_id}-direct-share",
                workspace_id=workspace_id,
                target_type="user",
                target_id=member_id,
                role=direct_role,
                granted_by_user_id=owner_id,
            )
        )
    session.commit()


def test_add_members_uses_canonical_authorization_snapshot(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-1", platform_role="admin", role_status="valid")
    valid = create_user(id="valid", platform_role="member", role_status="valid")
    disabled = create_user(
        id="disabled",
        platform_role="member",
        role_status="valid",
        identity_enabled=False,
    )
    invalid_role = create_user(
        id="invalid-role",
        platform_role=None,
        role_status="missing",
    )
    with session_factory() as session:
        _persist_group(session)
        result = UserGroupService(session).add_members(
            group_id="group-1",
            user_ids=[valid.id, disabled.id, invalid_role.id, "missing"],
            actor_user_id="admin-1",
        )

    assert result.added_user_ids == [valid.id]
    assert [failure.model_dump(by_alias=True) for failure in result.failed_users] == [
        {
            "userId": disabled.id,
            "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE",
        },
        {
            "userId": invalid_role.id,
            "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_AUTHORIZABLE",
        },
        {"userId": "missing", "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"},
    ]


def test_add_member_skips_existing_and_rejects_duplicate_request_ids(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-1", platform_role="admin", role_status="valid")
    create_user(id="user-1", platform_role="member", role_status="valid")

    with session_factory() as session:
        _persist_group(session)
        session.add(
            db_models.UserGroupMember(
                id="member-1",
                group_id="group-1",
                user_id="user-1",
                created_by_id="admin-1",
            )
        )
        session.commit()
        service = UserGroupService(session)
        result = service.add_members(
            group_id="group-1",
            user_ids=["user-1"],
            actor_user_id="admin-1",
        )
        assert result.skipped_user_ids == ["user-1"]

        with pytest.raises(HTTPException) as exc_info:
            service.add_members(
                group_id="group-1",
                user_ids=["user-1", "user-1"],
                actor_user_id="admin-1",
            )
        assert exc_info.value.detail == "KB_GROUP_ADMIN_INVALID_REQUEST"


def test_remove_members_distinguishes_skipped_and_missing_users(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-1", platform_role="admin", role_status="valid")
    create_user(id="member-1", platform_role="member", role_status="valid")
    create_user(id="not-member", platform_role="member", role_status="valid")

    with session_factory() as session:
        _persist_group(session)
        session.add(
            db_models.UserGroupMember(
                id="membership-1",
                group_id="group-1",
                user_id="member-1",
                created_by_id="admin-1",
            )
        )
        session.commit()
        result = UserGroupService(session).remove_members(
            group_id="group-1",
            user_ids=["member-1", "not-member", "missing"],
            actor_user_id="admin-1",
        )

    assert result.removed_user_ids == ["member-1"]
    assert result.skipped_user_ids == ["not-member"]
    assert [failure.model_dump(by_alias=True) for failure in result.failed_users] == [
        {"userId": "missing", "errorCode": "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"}
    ]


def test_remove_members_recycles_workspace_only_when_effective_access_is_reduced(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="group-owner", platform_role="member", role_status="valid")
    member = create_user(id="group-member", platform_role="member", role_status="valid")

    with session_factory() as session:
        _persist_group_workspace_access(
            session,
            owner_id=owner.id,
            member_id=member.id,
        )

        UserGroupService(session).remove_members(
            group_id="group-access",
            user_ids=[member.id],
            actor_user_id=owner.id,
            correlation_id="group-member-removal",
        )

        workspace = session.get(db_models.Workspace, "workspace-access")
        jobs = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == "workspace-access",
                    db_models.WorkspaceRuntimeJob.operation
                    == "workspace_access_recycle",
                )
            ).all()
        )

    assert workspace is not None
    assert workspace.runtime_access_revision == 1
    assert len(jobs) == 1
    assert jobs[0].target_revision == 1


def test_remove_member_preserves_runtime_generation_for_overlapping_manager_access(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="overlap-owner", platform_role="member", role_status="valid")
    member = create_user(
        id="overlap-member", platform_role="member", role_status="valid"
    )

    with session_factory() as session:
        _persist_group_workspace_access(
            session,
            owner_id=owner.id,
            member_id=member.id,
            direct_role="manager",
        )

        UserGroupService(session).remove_member(
            group_id="group-access",
            user_id=member.id,
            actor_user_id=owner.id,
            correlation_id="overlapping-access-removal",
        )

        workspace = session.get(db_models.Workspace, "workspace-access")
        recycle_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == "workspace-access",
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        )

    assert workspace is not None
    assert workspace.runtime_access_revision == 0
    assert recycle_job is None


def test_remove_member_preserves_platform_admin_workspace_override(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="admin-owner", platform_role="member", role_status="valid")
    admin = create_user(id="admin-member", platform_role="admin", role_status="valid")

    with session_factory() as session:
        _persist_group_workspace_access(
            session,
            owner_id=owner.id,
            member_id=admin.id,
        )

        UserGroupService(session).remove_member(
            group_id="group-access",
            user_id=admin.id,
            actor_user_id=owner.id,
            correlation_id="platform-admin-removal",
        )

        workspace = session.get(db_models.Workspace, "workspace-access")
        recycle_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == "workspace-access",
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        )

    assert workspace is not None
    assert workspace.runtime_access_revision == 0
    assert recycle_job is None


def test_delete_group_removes_all_resource_shares_and_recycles_reduced_principals(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(id="delete-owner", platform_role="member", role_status="valid")
    member = create_user(
        id="delete-member", platform_role="member", role_status="valid"
    )

    with session_factory() as session:
        _persist_group_workspace_access(
            session,
            owner_id=owner.id,
            member_id=member.id,
        )
        session.add(
            db_models.KnowledgeBase(
                id="delete-kb",
                owner_id=owner.id,
                slug="delete-kb",
                name="Delete KB",
            )
        )
        session.flush()
        session.add(
            db_models.KnowledgeBaseShare(
                id="delete-kb-group-share",
                kb_id="delete-kb",
                target_type="user_group",
                target_id="group-access",
                role="reader",
                granted_by_id=owner.id,
            )
        )
        session.commit()

        UserGroupService(session).delete_group(
            group_id="group-access",
            actor_user_id=owner.id,
            correlation_id="group-deletion",
        )

        workspace = session.get(db_models.Workspace, "workspace-access")
        recycle_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == "workspace-access",
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        )

    with session_factory() as verification:
        assert verification.get(db_models.UserGroup, "group-access") is None
        assert (
            verification.get(db_models.WorkspaceShare, "workspace-access-group-share")
            is None
        )
        assert (
            verification.get(db_models.KnowledgeBaseShare, "delete-kb-group-share")
            is None
        )
    assert workspace is not None
    assert workspace.runtime_access_revision == 1
    assert recycle_job is not None


def test_group_page_total_and_items_use_one_query_snapshot(test_app) -> None:
    _, session_factory = test_app
    with session_factory() as session:
        session.add_all(
            [
                db_models.UserGroup(id="group-a", name="Alpha"),
                db_models.UserGroup(id="group-b", name="Bravo"),
            ]
        )
        session.commit()
        with patch.object(session, "execute", wraps=session.execute) as execute:
            result = UserGroupService(session).list_groups(page=2, page_size=1)

    assert execute.call_count == 1
    assert result.total == 2
    assert result.page == 2
    assert [item.id for item in result.items] == ["group-b"]


def test_crud_and_membership_mutations_persist_audit_events(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-audit", platform_role="admin", role_status="valid")
    create_user(id="member-audit", platform_role="member", role_status="valid")

    with session_factory() as session:
        service = UserGroupService(session)
        created = service.create_group(
            name="Audit Group",
            description=None,
            actor_user_id="admin-audit",
            correlation_id="11111111-1111-4111-8111-111111111111",
        )
        service.update_group(
            group_id=created.id,
            name="Audit Group Updated",
            description=None,
            name_provided=True,
            description_provided=False,
            actor_user_id="admin-audit",
            correlation_id="22222222-2222-4222-8222-222222222222",
        )
        service.add_members(
            group_id=created.id,
            user_ids=["member-audit"],
            actor_user_id="admin-audit",
            correlation_id="33333333-3333-4333-8333-333333333333",
        )
        service.remove_member(
            group_id=created.id,
            user_id="member-audit",
            actor_user_id="admin-audit",
            correlation_id="44444444-4444-4444-8444-444444444444",
        )
        service.delete_group(
            group_id=created.id,
            actor_user_id="admin-audit",
            correlation_id="55555555-5555-4555-8555-555555555555",
        )
        events = list(
            session.scalars(
                select(db_models.AuditEvent).order_by(
                    db_models.AuditEvent.created_at,
                    db_models.AuditEvent.id,
                )
            ).all()
        )

    assert [event.event_type for event in events] == [
        "user_group.created",
        "user_group.updated",
        "user_group.member_added",
        "user_group.member_removed",
        "user_group.deleted",
    ]
    assert [event.action for event in events] == [
        "create_group",
        "update_group",
        "add_member",
        "remove_member",
        "delete_group",
    ]
    assert all(event.actor_user_id == "admin-audit" for event in events)


def test_membership_rolls_back_and_failure_audit_persists(
    test_app, create_user
) -> None:
    _, session_factory = test_app
    create_user(id="admin-rollback", platform_role="admin", role_status="valid")
    create_user(id="member-rollback", platform_role="member", role_status="valid")

    with session_factory() as session:
        _persist_group(session, "group-rollback")
        service = UserGroupService(session)
        with (
            patch.object(session, "commit", side_effect=RuntimeError("commit failed")),
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            service.add_members(
                group_id="group-rollback",
                user_ids=["member-rollback"],
                actor_user_id="admin-rollback",
            )

    with session_factory() as session:
        assert session.scalar(select(db_models.UserGroupMember)) is None
        event = session.scalar(select(db_models.AuditEvent))
        assert event is not None
        assert event.event_type == "user_group.member_added"
        assert event.action == "add_member"
        assert event.result == "failure"
        assert event.error_code == "KB_GROUP_ADMIN_INVALID_REQUEST"
        assert event.target_type == "user"
        assert event.target_id == "member-rollback"
        assert event.event_metadata == {"group_id": "group-rollback"}


def test_group_domain_failures_persist_independent_audits(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-failure", platform_role="admin", role_status="valid")
    create_user(id="member-failure", platform_role="member", role_status="valid")

    with session_factory() as session:
        _persist_group(session, "group-existing")
        service = UserGroupService(session)
        with pytest.raises(HTTPException) as duplicate_create:
            service.create_group(
                name="Group group-existing",
                description=None,
                actor_user_id="admin-failure",
            )
        assert duplicate_create.value.detail == "KB_GROUP_ADMIN_DUPLICATE_NAME"

        with pytest.raises(HTTPException) as missing_update:
            service.update_group(
                group_id="missing-update",
                name="Updated",
                description=None,
                name_provided=True,
                description_provided=False,
                actor_user_id="admin-failure",
            )
        assert missing_update.value.detail == "KB_GROUP_ADMIN_NOT_FOUND"

        with pytest.raises(HTTPException) as missing_delete:
            service.delete_group(
                group_id="missing-delete",
                actor_user_id="admin-failure",
            )
        assert missing_delete.value.detail == "KB_GROUP_ADMIN_NOT_FOUND"

        with pytest.raises(HTTPException) as missing_add_group:
            service.add_members(
                group_id="missing-add-group",
                user_ids=["member-failure"],
                actor_user_id="admin-failure",
            )
        assert missing_add_group.value.detail == "KB_GROUP_ADMIN_NOT_FOUND"

        with pytest.raises(HTTPException) as missing_remove_group:
            service.remove_members(
                group_id="missing-remove-group",
                user_ids=["member-failure"],
                actor_user_id="admin-failure",
            )
        assert missing_remove_group.value.detail == "KB_GROUP_ADMIN_NOT_FOUND"

        with pytest.raises(HTTPException) as missing_member:
            service.remove_member(
                group_id="group-existing",
                user_id="member-failure",
                actor_user_id="admin-failure",
            )
        assert missing_member.value.detail == "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"

    with session_factory() as session:
        events = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(db_models.AuditEvent.result == "failure")
                .order_by(db_models.AuditEvent.created_at, db_models.AuditEvent.id)
            ).all()
        )

    assert [(event.event_type, event.error_code) for event in events] == [
        ("user_group.created", "KB_GROUP_ADMIN_DUPLICATE_NAME"),
        ("user_group.updated", "KB_GROUP_ADMIN_NOT_FOUND"),
        ("user_group.deleted", "KB_GROUP_ADMIN_NOT_FOUND"),
        ("user_group.member_added", "KB_GROUP_ADMIN_NOT_FOUND"),
        ("user_group.member_removed", "KB_GROUP_ADMIN_NOT_FOUND"),
        ("user_group.member_removed", "KB_GROUP_ADMIN_MEMBER_NOT_FOUND"),
    ]


def test_failure_audit_error_does_not_mask_group_domain_error(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(id="admin-audit-error", platform_role="admin", role_status="valid")

    with session_factory() as session:
        service = UserGroupService(session)
        with (
            patch(
                "app.modules.identity.groups.AuditEventService.record",
                side_effect=RuntimeError("audit unavailable"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            service.delete_group(
                group_id="missing-group",
                actor_user_id="admin-audit-error",
            )

    assert exc_info.value.detail == "KB_GROUP_ADMIN_NOT_FOUND"


def test_group_sort_is_case_insensitive_with_id_tie_breaker(test_app) -> None:
    _, session_factory = test_app
    with session_factory() as session:
        session.add_all(
            [
                db_models.UserGroup(id="group-b", name="alpha"),
                db_models.UserGroup(id="group-c", name="Bravo"),
                db_models.UserGroup(id="group-a", name="Alpha"),
            ]
        )
        session.commit()

        result = UserGroupService(session).list_groups(
            sort_by="name",
            sort_direction="asc",
        )

    assert [item.id for item in result.items] == [
        "group-a",
        "group-b",
        "group-c",
    ]


def test_candidate_string_sort_places_nulls_last(test_app, create_user) -> None:
    _, session_factory = test_app
    create_user(id="admin-sort", platform_role="admin", role_status="valid")
    create_user(
        id="candidate-email",
        email="alpha@example.com",
        platform_role="member",
        role_status="valid",
    )
    create_user(
        id="candidate-null",
        email=None,
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        _persist_group(session, "group-sort")
        session.add(
            db_models.UserGroupMember(
                id="member-admin-sort",
                group_id="group-sort",
                user_id="admin-sort",
                created_by_id="admin-sort",
            )
        )
        session.commit()

        result = UserGroupService(session).list_member_candidates(
            group_id="group-sort",
            sort_by="email",
            sort_direction="asc",
        )

    assert [item.user_id for item in result.items] == [
        "candidate-email",
        "candidate-null",
    ]
