"""Platform resource administration contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.authorization.platform_resources import (
    DatabaseOwnershipNotificationPublisher,
    OwnerReassignment,
    OwnerReassignmentError,
    OwnerReassignmentRequest,
    PlatformResourceInventory,
)


@dataclass
class RecordingNotificationPublisher:
    calls: list[dict[str, str]] = field(default_factory=list)

    def publish_owner_reassigned(self, **payload: str) -> None:
        self.calls.append(payload)


@dataclass
class RecordingAccessRecyclePublisher:
    calls: list[dict[str, str]] = field(default_factory=list)

    def publish_access_recycle(self, **payload: str) -> None:
        self.calls.append(payload)


class FailingNotificationPublisher:
    def publish_owner_reassigned(self, **_payload: str) -> None:
        raise RuntimeError("notification transport unavailable")


def _actor(user: db_models.User):
    return actor_from_valid_user(user)


def _workspace(*, workspace_id: str, owner_id: str, name: str) -> db_models.Workspace:
    return db_models.Workspace(
        id=workspace_id,
        owner_id=owner_id,
        name=name,
        provisioner="docker",
        runtime_status="stopped",
    )


def _knowledge_base(
    *, kb_id: str, owner_id: str, name: str, visibility: str = "private"
) -> db_models.KnowledgeBase:
    return db_models.KnowledgeBase(
        id=kb_id,
        owner_id=owner_id,
        slug=kb_id,
        name=name,
        visibility=visibility,
    )


def test_default_owner_notification_is_persisted_for_previous_owner(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    previous_owner = create_user(
        id="notification-owner",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        DatabaseOwnershipNotificationPublisher(session).publish_owner_reassigned(
            resource_type="workspace",
            resource_id="workspace-notification",
            previous_owner_id=previous_owner.id,
            new_owner_id="next-owner",
            reason="Ownership rotation",
        )

        event = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type
                == "platform_resource.owner_reassigned_notification"
            )
        )
        assert event is not None
        assert event.target_type == "user"
        assert event.target_id == previous_owner.id
        assert event.event_metadata["new_owner_id"] == "next-owner"


def test_platform_resource_lists_are_admin_only_paginated_safe_summaries(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="admin", platform_role="admin", role_status="valid")
    member = create_user(id="member", platform_role="member", role_status="valid")
    owner = create_user(id="owner", platform_role="member", role_status="valid")

    with session_factory() as session:
        session.add_all(
            [
                _workspace(
                    workspace_id="workspace-alpha",
                    owner_id=owner.id,
                    name="Alpha Workspace",
                ),
                _workspace(
                    workspace_id="workspace-beta",
                    owner_id=owner.id,
                    name="Beta Workspace",
                ),
                _knowledge_base(
                    kb_id="kb-alpha",
                    owner_id=owner.id,
                    name="Alpha Knowledge",
                    visibility="public",
                ),
            ]
        )
        session.commit()
        inventory = PlatformResourceInventory(session)

        workspaces = inventory.list_workspaces(
            actor=_actor(admin), q="alpha", page=1, page_size=10
        )
        knowledge_bases = inventory.list_knowledge_bases(
            actor=_actor(admin), q=None, page=1, page_size=10
        )

        assert workspaces.total == 1
        assert [item.id for item in workspaces.items] == ["workspace-alpha"]
        assert workspaces.items[0].owner.id == owner.id
        assert workspaces.items[0].runtime_status == "stopped"
        assert not hasattr(workspaces.items[0], "env_vars")
        assert knowledge_bases.items[0].visibility == "public"
        assert not hasattr(knowledge_bases.items[0], "git_last_commit_sha")

        with pytest.raises(AuthorizationOperationError):
            inventory.list_workspaces(
                actor=_actor(member), q=None, page=1, page_size=10
            )


def test_workspace_owner_reassignment_is_atomic_audited_and_published_after_commit(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="admin", platform_role="admin", role_status="valid")
    owner = create_user(id="owner", platform_role="member", role_status="valid")
    target = create_user(id="target", platform_role="member", role_status="valid")
    notifications = RecordingNotificationPublisher()
    recycle = RecordingAccessRecyclePublisher()

    with session_factory() as session:
        session.add(
            _workspace(
                workspace_id="workspace-1",
                owner_id=owner.id,
                name="Workspace One",
            )
        )
        session.add(
            db_models.WorkspaceShare(
                id="target-share",
                workspace_id="workspace-1",
                target_type="user",
                target_id=target.id,
                role="manager",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()
        owner_reassignment = OwnerReassignment(
            session,
            notification_publisher=notifications,
            access_recycle_publisher=recycle,
        )

        result = owner_reassignment.reassign_workspace_owner(
            actor=_actor(admin),
            workspace_id="workspace-1",
            payload=OwnerReassignmentRequest(
                targetUserId=target.id,
                reason="Operational ownership change",
            ),
            correlation_id="11111111-1111-4111-8111-111111111111",
            root_correlation_id="11111111-1111-4111-8111-111111111111",
        )

        assert result.owner.id == target.id
        workspace = session.get(db_models.Workspace, "workspace-1")
        assert workspace is not None and workspace.owner_id == target.id
        shares = list(
            session.scalars(
                select(db_models.WorkspaceShare).where(
                    db_models.WorkspaceShare.workspace_id == "workspace-1"
                )
            ).all()
        )
        assert [(share.target_id, share.role) for share in shares] == [
            (owner.id, "manager")
        ]
        event = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type
                == "platform_resource.workspace_owner_reassigned"
            )
        )
        assert event is not None
        assert event.event_metadata["previous_owner_id"] == owner.id
        assert event.event_metadata["new_owner_id"] == target.id
        assert event.event_metadata["owner_reassignment_reason"] == (
            "Operational ownership change"
        )

    assert notifications.calls == [
        {
            "resource_type": "workspace",
            "resource_id": "workspace-1",
            "previous_owner_id": owner.id,
            "new_owner_id": target.id,
            "reason": "Operational ownership change",
        }
    ]
    assert recycle.calls == [
        {
            "resource_type": "workspace",
            "resource_id": "workspace-1",
            "actor_user_id": admin.id,
            "correlation_id": "11111111-1111-4111-8111-111111111111",
            "root_correlation_id": "11111111-1111-4111-8111-111111111111",
        }
    ]


def test_reassignment_rejects_target_without_effective_manager_access(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="admin", platform_role="admin", role_status="valid")
    owner = create_user(id="owner", platform_role="member", role_status="valid")
    reader = create_user(id="reader", platform_role="member", role_status="valid")

    with session_factory() as session:
        session.add(
            _workspace(
                workspace_id="workspace-1",
                owner_id=owner.id,
                name="Workspace One",
            )
        )
        session.add(
            db_models.WorkspaceShare(
                id="reader-share",
                workspace_id="workspace-1",
                target_type="user",
                target_id=reader.id,
                role="reader",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

        with pytest.raises(OwnerReassignmentError) as denied:
            OwnerReassignment(session).reassign_workspace_owner(
                actor=_actor(admin),
                workspace_id="workspace-1",
                payload=OwnerReassignmentRequest(
                    targetUserId=reader.id,
                    reason="Operational ownership change",
                ),
                correlation_id="22222222-2222-4222-8222-222222222222",
                root_correlation_id="22222222-2222-4222-8222-222222222222",
            )

        assert denied.value.error_code == "PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED"
        workspace = session.get(db_models.Workspace, "workspace-1")
        assert workspace is not None and workspace.owner_id == owner.id


def test_reassignment_does_not_treat_target_admin_override_as_manager(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor_admin = create_user(
        id="actor-admin", platform_role="admin", role_status="valid"
    )
    target_admin = create_user(
        id="target-admin", platform_role="admin", role_status="valid"
    )
    owner = create_user(id="owner", platform_role="member", role_status="valid")

    with session_factory() as session:
        session.add(
            _workspace(
                workspace_id="workspace-1",
                owner_id=owner.id,
                name="Workspace One",
            )
        )
        session.commit()

        with pytest.raises(OwnerReassignmentError) as denied:
            OwnerReassignment(session).reassign_workspace_owner(
                actor=_actor(actor_admin),
                workspace_id="workspace-1",
                payload=OwnerReassignmentRequest(
                    targetUserId=target_admin.id,
                    reason="Operational ownership change",
                ),
                correlation_id="33333333-3333-4333-8333-333333333333",
                root_correlation_id="33333333-3333-4333-8333-333333333333",
            )

        assert denied.value.error_code == "PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED"
        workspace = session.get(db_models.Workspace, "workspace-1")
        assert workspace is not None and workspace.owner_id == owner.id


def test_post_commit_notification_failure_does_not_rollback_ownership(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="admin", platform_role="admin", role_status="valid")
    owner = create_user(id="owner", platform_role="member", role_status="valid")
    target = create_user(id="target", platform_role="member", role_status="valid")

    with session_factory() as session:
        session.add(
            _workspace(
                workspace_id="workspace-1",
                owner_id=owner.id,
                name="Workspace One",
            )
        )
        session.add(
            db_models.WorkspaceShare(
                id="target-share",
                workspace_id="workspace-1",
                target_type="user",
                target_id=target.id,
                role="manager",
                granted_by_user_id=owner.id,
            )
        )
        session.commit()

        result = OwnerReassignment(
            session,
            notification_publisher=FailingNotificationPublisher(),
        ).reassign_workspace_owner(
            actor=_actor(admin),
            workspace_id="workspace-1",
            payload=OwnerReassignmentRequest(
                targetUserId=target.id,
                reason="Operational ownership change",
            ),
            correlation_id="44444444-4444-4444-8444-444444444444",
            root_correlation_id="44444444-4444-4444-8444-444444444444",
        )

        assert result.owner.id == target.id
        workspace = session.get(db_models.Workspace, "workspace-1")
        assert workspace is not None
        assert workspace.owner_id == target.id
        assert workspace.runtime_access_revision == 1
        recycle_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == "workspace-1",
                db_models.WorkspaceRuntimeJob.operation == "workspace_access_recycle",
            )
        )
        assert recycle_job is not None
        delivery_failure = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type
                == "platform_resource.owner_reassignment_notification_failed"
            )
        )
        assert delivery_failure is not None
        assert (
            delivery_failure.error_code == "PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED"
        )


def test_kb_owner_reassignment_accepts_group_manager_and_drops_disabled_old_owner(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    admin = create_user(id="admin", platform_role="admin", role_status="valid")
    old_owner = create_user(
        id="disabled-owner",
        platform_role="member",
        role_status="valid",
        is_active=False,
    )
    target = create_user(id="target", platform_role="member", role_status="valid")

    with session_factory() as session:
        session.add_all(
            [
                db_models.UserGroup(id="group-1", name="Managers"),
                _knowledge_base(
                    kb_id="kb-1",
                    owner_id=old_owner.id,
                    name="Knowledge One",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                db_models.UserGroupMember(
                    id="membership-1",
                    group_id="group-1",
                    user_id=target.id,
                    created_by_id=admin.id,
                ),
                db_models.KnowledgeBaseShare(
                    id="group-share",
                    kb_id="kb-1",
                    target_type="user_group",
                    target_id="group-1",
                    role="manager",
                    granted_by_id=old_owner.id,
                ),
            ]
        )
        session.commit()

        result = OwnerReassignment(session).reassign_knowledge_base_owner(
            actor=_actor(admin),
            kb_id="kb-1",
            payload=OwnerReassignmentRequest(
                targetUserId=target.id,
                reason="Owner account deactivated",
            ),
            correlation_id="33333333-3333-4333-8333-333333333333",
            root_correlation_id="33333333-3333-4333-8333-333333333333",
        )

        assert result.owner.id == target.id
        direct_old_owner_share = session.scalar(
            select(db_models.KnowledgeBaseShare).where(
                db_models.KnowledgeBaseShare.kb_id == "kb-1",
                db_models.KnowledgeBaseShare.target_type == "user",
                db_models.KnowledgeBaseShare.target_id == old_owner.id,
            )
        )
        assert direct_old_owner_share is None
