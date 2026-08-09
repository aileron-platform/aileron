"""Knowledge base service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor, actor_from_valid_user
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.access import (
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
    normalize_kb_slug,
)
from app.modules.knowledge_base.errors import KnowledgeBaseError


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.scalar = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.delete = MagicMock()
    session.execute = MagicMock()
    session.scalars = MagicMock()
    return session


@pytest.fixture
def knowledge_base_service(mock_db_session):
    return KnowledgeBaseService(mock_db_session)


@pytest.fixture
def sharing_service(mock_db_session):
    service = KnowledgeBaseSharingService(mock_db_session)
    service._persist_failure_audit = MagicMock()
    return service


@pytest.mark.unit
def test_normalize_kb_slug_converts_to_dash_case() -> None:
    assert normalize_kb_slug(" API Docs v2 ") == "api-docs-v2"


@pytest.mark.unit
def test_create_kb_persists_normalized_slug(
    knowledge_base_service,
    mock_db_session,
    user_factory,
):
    mock_db_session.scalar.side_effect = [1, None, None]

    kb = knowledge_base_service.create_kb(
        actor=AuthorizationActor("owner-1", "member"),
        name="API Docs",
        slug=" API Docs ",
        description="shared docs",
    )

    assert isinstance(kb, db_models.KnowledgeBase)
    assert kb.owner_id == "owner-1"
    assert kb.slug == "api-docs"
    assert kb.current_size_bytes == 0
    assert kb in [call.args[0] for call in mock_db_session.add.call_args_list]
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(kb)


@pytest.mark.unit
def test_create_kb_checks_owner_with_stable_columns(
    knowledge_base_service,
    mock_db_session,
):
    mock_db_session.scalar.side_effect = [1, None, None]

    knowledge_base_service.create_kb(
        actor=AuthorizationActor("owner-1", "member"),
        name="API Docs",
        slug="api-docs",
        description="shared docs",
    )

    owner_query = mock_db_session.scalar.call_args_list[0].args[0]
    compiled = str(owner_query.compile(compile_kwargs={"literal_binds": True}))
    assert "count" in compiled.lower()
    assert "users.id" in compiled
    assert "identity_enabled" not in compiled


@pytest.mark.unit
def test_create_kb_rejects_duplicate_slug(
    knowledge_base_service,
    mock_db_session,
    user_factory,
):
    mock_db_session.get.return_value = user_factory(id="owner-1")
    mock_db_session.scalar.return_value = object()

    with pytest.raises(KnowledgeBaseConflictError, match="slug already exists"):
        knowledge_base_service.create_kb(
            actor=AuthorizationActor("owner-1", "member"),
            name="Docs",
            slug="docs",
        )


def _create_delete_test_user(create_user, *, user_id: str) -> db_models.User:
    return create_user(
        id=user_id,
        platform_role="member",
        role_status="valid",
    )


def _add_delete_test_knowledge_base(
    session,
    *,
    kb_id: str,
    owner_id: str,
) -> db_models.KnowledgeBase:
    knowledge_base = db_models.KnowledgeBase(
        id=kb_id,
        owner_id=owner_id,
        slug=kb_id,
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    session.add(knowledge_base)
    return knowledge_base


def _add_delete_test_workspace(
    session,
    *,
    workspace_id: str,
    owner_id: str,
    name: str,
) -> db_models.Workspace:
    workspace = db_models.Workspace(
        id=workspace_id,
        owner_id=owner_id,
        name=name,
        runtime="universal",
        provisioner="docker",
    )
    session.add(workspace)
    return workspace


def _add_delete_test_attachment(
    session,
    *,
    attachment_id: str,
    workspace_id: str,
    kb_id: str,
    actor_id: str,
    mount_alias: str,
) -> db_models.WorkspaceKnowledgeBaseAttachment:
    attachment = db_models.WorkspaceKnowledgeBaseAttachment(
        id=attachment_id,
        workspace_id=workspace_id,
        kb_id=kb_id,
        mount_alias=mount_alias,
        attached_by_id=actor_id,
    )
    session.add(attachment)
    return attachment


@pytest.mark.unit
def test_delete_kb_without_attachments_is_permanent(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = _create_delete_test_user(create_user, user_id="owner-delete-empty")

    with session_factory() as session:
        _add_delete_test_knowledge_base(
            session,
            kb_id="kb-delete-empty",
            owner_id=owner.id,
        )
        session.commit()

        service = KnowledgeBaseService(session)
        kb_root = service.storage_root / "kb-delete-empty"
        kb_root.mkdir(parents=True)
        (kb_root / "document.md").write_text("permanent", encoding="utf-8")

        deleted = service.delete_kb(
            actor=actor_from_valid_user(owner),
            kb_id="kb-delete-empty",
            confirmation_name="Docs",
        )

        assert deleted.id == "kb-delete-empty"
        assert not kb_root.exists()

    with session_factory() as session:
        persisted = session.get(db_models.KnowledgeBase, "kb-delete-empty")
        assert persisted is None
        event = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.event_type == "knowledge_base.deleted",
                db_models.AuditEvent.target_id == "kb-delete-empty",
            )
        )
        assert event is not None
        assert event.result == "success"


@pytest.mark.unit
def test_delete_kb_rejects_active_reference(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = _create_delete_test_user(
        create_user,
        user_id="owner-delete-active",
    )
    workspace_id = "workspace-delete-active"
    attachment_id = "attachment-delete-active"

    with session_factory() as session:
        _add_delete_test_knowledge_base(
            session,
            kb_id="kb-delete-active",
            owner_id=owner.id,
        )
        _add_delete_test_workspace(
            session,
            workspace_id=workspace_id,
            owner_id=owner.id,
            name="Visible Workspace",
        )
        session.flush()
        _add_delete_test_attachment(
            session,
            attachment_id=attachment_id,
            workspace_id=workspace_id,
            kb_id="kb-delete-active",
            actor_id=owner.id,
            mount_alias="docs",
        )
        session.commit()

        with pytest.raises(
            KnowledgeBaseConflictError,
            match="still mounted by workspace",
        ) as exc_info:
            KnowledgeBaseService(session).delete_kb(
                actor=actor_from_valid_user(owner),
                kb_id="kb-delete-active",
                confirmation_name="Docs",
            )

        assert exc_info.value.code == "KB_DELETE_ATTACHMENT_CONFLICT"
        assert exc_info.value.params == {
            "attachmentCount": 1,
            "visibleWorkspaces": [
                {
                    "attachmentId": attachment_id,
                    "workspaceId": workspace_id,
                    "workspaceName": "Visible Workspace",
                    "mountAlias": "docs",
                    "attachmentStatus": "active",
                }
            ],
            "hiddenWorkspaceCount": 0,
        }

    with session_factory() as session:
        persisted = session.get(
            db_models.KnowledgeBase,
            "kb-delete-active",
        )
        assert persisted is not None
        assert (
            session.get(db_models.WorkspaceKnowledgeBaseAttachment, attachment_id)
            is not None
        )


@pytest.mark.unit
def test_delete_kb_masks_inaccessible_workspace_details(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = _create_delete_test_user(create_user, user_id="owner-delete-masking")
    visible_owner = create_user(id="visible-workspace-owner")
    hidden_owner = create_user(id="hidden-workspace-owner")

    with session_factory() as session:
        _add_delete_test_knowledge_base(
            session,
            kb_id="kb-delete-masking",
            owner_id=owner.id,
        )
        _add_delete_test_workspace(
            session,
            workspace_id="workspace-visible",
            owner_id=visible_owner.id,
            name="Visible Workspace",
        )
        _add_delete_test_workspace(
            session,
            workspace_id="workspace-hidden",
            owner_id=hidden_owner.id,
            name="Hidden Workspace",
        )
        session.flush()
        session.add(
            db_models.WorkspaceShare(
                id="workspace-visible-share",
                workspace_id="workspace-visible",
                target_type="user",
                target_id=owner.id,
                role="reader",
                granted_by_user_id=visible_owner.id,
            )
        )
        _add_delete_test_attachment(
            session,
            attachment_id="attachment-visible",
            workspace_id="workspace-visible",
            kb_id="kb-delete-masking",
            actor_id=owner.id,
            mount_alias="visible-docs",
        )
        _add_delete_test_attachment(
            session,
            attachment_id="attachment-hidden",
            workspace_id="workspace-hidden",
            kb_id="kb-delete-masking",
            actor_id=owner.id,
            mount_alias="hidden-docs",
        )
        session.commit()

        with pytest.raises(KnowledgeBaseConflictError) as exc_info:
            KnowledgeBaseService(session).delete_kb(
                actor=actor_from_valid_user(owner),
                kb_id="kb-delete-masking",
                confirmation_name="Docs",
            )

        assert exc_info.value.code == "KB_DELETE_ATTACHMENT_CONFLICT"
        assert exc_info.value.params == {
            "attachmentCount": 2,
            "visibleWorkspaces": [
                {
                    "attachmentId": "attachment-visible",
                    "workspaceId": "workspace-visible",
                    "workspaceName": "Visible Workspace",
                    "mountAlias": "visible-docs",
                    "attachmentStatus": "active",
                }
            ],
            "hiddenWorkspaceCount": 1,
        }
        serialized = repr(exc_info.value.params)
        assert "workspace-hidden" not in serialized
        assert "Hidden Workspace" not in serialized
        assert "hidden-docs" not in serialized
        assert "attachment-hidden" not in serialized


@pytest.mark.unit
def test_delete_kb_rolls_back_permanent_delete_when_commit_fails(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = _create_delete_test_user(create_user, user_id="owner-delete-rollback")

    with session_factory() as session:
        _add_delete_test_knowledge_base(
            session,
            kb_id="kb-delete-rollback",
            owner_id=owner.id,
        )
        session.commit()

        service = KnowledgeBaseService(session)
        kb_root = service.storage_root / "kb-delete-rollback"
        kb_root.mkdir(parents=True)
        (kb_root / "document.md").write_text("restore", encoding="utf-8")

        with (
            patch.object(session, "commit", side_effect=RuntimeError("commit failed")),
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            service.delete_kb(
                actor=actor_from_valid_user(owner),
                kb_id="kb-delete-rollback",
                confirmation_name="Docs",
            )

        assert (kb_root / "document.md").read_text(encoding="utf-8") == "restore"

    with session_factory() as session:
        persisted = session.get(db_models.KnowledgeBase, "kb-delete-rollback")
        assert persisted is not None


@pytest.mark.unit
def test_delete_kb_reports_storage_cleanup_failure_and_audits_it(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = _create_delete_test_user(create_user, user_id="owner-delete-cleanup")

    with session_factory() as session:
        _add_delete_test_knowledge_base(
            session,
            kb_id="kb-delete-cleanup",
            owner_id=owner.id,
        )
        session.commit()

        service = KnowledgeBaseService(session)
        kb_root = service.storage_root / "kb-delete-cleanup"
        kb_root.mkdir(parents=True)
        (kb_root / "document.md").write_text("cleanup", encoding="utf-8")

        with (
            patch(
                "app.modules.knowledge_base.access.shutil.rmtree",
                side_effect=OSError("busy"),
            ),
            pytest.raises(KnowledgeBaseError) as exc_info,
        ):
            service.delete_kb(
                actor=actor_from_valid_user(owner),
                kb_id="kb-delete-cleanup",
                confirmation_name="Docs",
                correlation_id="55555555-5555-4555-8555-555555555555",
            )

        assert exc_info.value.code == "KB_DELETE_STORAGE_CLEANUP_FAILED"

    with session_factory() as session:
        assert session.get(db_models.KnowledgeBase, "kb-delete-cleanup") is None
        events = list(
            session.scalars(
                select(db_models.AuditEvent)
                .where(
                    db_models.AuditEvent.target_id == "kb-delete-cleanup",
                    db_models.AuditEvent.event_type == "knowledge_base.deleted",
                )
                .order_by(db_models.AuditEvent.created_at)
            ).all()
        )
        assert [event.result for event in events] == ["success", "failure"]
        assert events[-1].error_code == "KB_DELETE_STORAGE_CLEANUP_FAILED"


@pytest.mark.unit
def test_update_visibility_uses_manager_operation_and_persists_public(
    knowledge_base_service,
    mock_db_session,
) -> None:
    knowledge_base = db_models.KnowledgeBase(
        id="kb-public",
        owner_id="owner-1",
        slug="public-docs",
        name="Public Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
        visibility="private",
    )
    access = object()
    knowledge_base_service.get_kb_for_operation = MagicMock(
        return_value=(knowledge_base, access)
    )

    result = knowledge_base_service.update_visibility(
        actor=AuthorizationActor("owner-1", "member"),
        kb_id=knowledge_base.id,
        visibility="public",
    )

    assert result.visibility == "public"
    knowledge_base_service.get_kb_for_operation.assert_called_once_with(
        actor=AuthorizationActor("owner-1", "member"),
        kb_id=knowledge_base.id,
        operation=OperationId.KNOWLEDGE_BASE_VISIBILITY_MANAGE,
    )
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(knowledge_base)


@pytest.mark.unit
def test_public_to_private_visibility_stages_mounted_consumer_revocation(
    knowledge_base_service,
    mock_db_session,
) -> None:
    knowledge_base = db_models.KnowledgeBase(
        id="kb-private",
        owner_id="owner-1",
        slug="private-docs",
        name="Private Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
        visibility="public",
    )
    knowledge_base_service.get_kb_for_operation = MagicMock(
        return_value=(knowledge_base, object())
    )

    with patch(
        "app.modules.knowledge_base.attachments."
        "KnowledgeBaseAttachmentService.revoke_knowledge_base_mounts"
    ) as revoke_mounts:
        knowledge_base_service.update_visibility(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id=knowledge_base.id,
            visibility="private",
            correlation_id="visibility-private",
        )

    revoke_mounts.assert_called_once()
    assert knowledge_base.visibility == "private"
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_grant_share_rejects_owner_target(
    sharing_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.return_value = kb
    mock_db_session.scalar.return_value = None
    sharing_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, object())
    )

    with pytest.raises(
        KnowledgeBaseConflictError, match="share knowledge base with owner"
    ):
        sharing_service.grant_share(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id="kb-1",
            target_type="user",
            target_id="owner-1",
            role="reader",
        )


@pytest.mark.unit
def test_grant_share_rejects_duplicate_share(
    sharing_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    sharing_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, object())
    )
    mock_db_session.scalar.return_value = object()

    with pytest.raises(
        KnowledgeBaseConflictError, match="Knowledge base share already exists"
    ):
        sharing_service.grant_share(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id="kb-1",
            target_type="user",
            target_id="user-2",
            role="reader",
        )


@pytest.mark.unit
def test_grant_share_rejects_invalid_role(
    sharing_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    sharing_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, object())
    )
    mock_db_session.scalar.return_value = None

    with pytest.raises(KnowledgeBaseError, match="Invalid knowledge base sharing role"):
        sharing_service.grant_share(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id="kb-1",
            target_type="user",
            target_id="user-2",
            role="owner",
        )


@pytest.mark.unit
def test_list_shares_requires_manager_access(
    sharing_service,
):
    sharing_service.kb_service.get_kb_for_operation = MagicMock()

    actor = AuthorizationActor("user-1", "member")
    sharing_service.list_shares(actor=actor, kb_id="kb-1")

    sharing_service.kb_service.get_kb_for_operation.assert_called_once_with(
        actor=actor,
        kb_id="kb-1",
        operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
    )


@pytest.mark.unit
def test_resolve_role_includes_user_group_share(
    knowledge_base_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    group_share = db_models.KnowledgeBaseShare(
        id="share-1",
        kb_id="kb-1",
        target_type="user_group",
        target_id="group-1",
        role="manager",
        granted_by_id="owner-1",
    )
    mock_db_session.get.return_value = kb
    mock_db_session.scalar.return_value = None
    mock_db_session.scalars.return_value.all.return_value = [group_share]

    assert knowledge_base_service._resolve_role(kb, user_id="user-2") == "manager"


@pytest.mark.unit
def test_update_share_role_rejects_missing_share(
    sharing_service,
    mock_db_session,
):
    kb = object()
    sharing_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, object())
    )
    mock_db_session.scalar.return_value = None

    with pytest.raises(
        KnowledgeBaseNotFoundError,
        match="Knowledge base share target does not exist",
    ) as exc_info:
        sharing_service.update_share_role(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id="kb-1",
            share_id="share-1",
            role="manager",
        )
    assert exc_info.value.code == "KB_SHARE_TARGET_NOT_FOUND"


@pytest.mark.unit
def test_update_share_role_rejects_invalid_role(
    sharing_service,
    mock_db_session,
):
    share = db_models.KnowledgeBaseShare(
        id="share-1",
        kb_id="kb-1",
        target_type="user",
        target_id="user-2",
        role="reader",
        granted_by_id="owner-1",
    )
    mock_db_session.scalar.return_value = share
    sharing_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(object(), object())
    )

    with pytest.raises(KnowledgeBaseError, match="Invalid knowledge base sharing role"):
        sharing_service.update_share_role(
            actor=AuthorizationActor("owner-1", "member"),
            kb_id="kb-1",
            share_id="share-1",
            role="owner",
        )


def test_direct_share_mutations_persist_audit_events_in_their_transactions(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="owner-audit",
        platform_role="member",
        role_status="valid",
    )
    member = create_user(
        id="member-audit",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        session.add(
            db_models.KnowledgeBase(
                id="kb-audit",
                owner_id=owner.id,
                slug="audit-docs",
                name="Audit Docs",
                description=None,
                current_size_bytes=0,
                quota_bytes=None,
            )
        )
        session.commit()
        service = KnowledgeBaseSharingService(session)
        share = service.grant_share(
            actor=actor_from_valid_user(owner),
            kb_id="kb-audit",
            target_type="user",
            target_id=member.id,
            role="reader",
            correlation_id="11111111-1111-4111-8111-111111111111",
            root_correlation_id="11111111-1111-4111-8111-111111111111",
        )
        service.update_share_role(
            actor=actor_from_valid_user(owner),
            kb_id="kb-audit",
            share_id=share.id,
            role="manager",
            correlation_id="22222222-2222-4222-8222-222222222222",
            root_correlation_id="22222222-2222-4222-8222-222222222222",
        )
        service.revoke_share(
            actor=actor_from_valid_user(owner),
            kb_id="kb-audit",
            share_id=share.id,
            correlation_id="33333333-3333-4333-8333-333333333333",
            root_correlation_id="33333333-3333-4333-8333-333333333333",
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
        "knowledge_base.share_created",
        "knowledge_base.share_updated",
        "knowledge_base.share_deleted",
    ]
    assert [event.action for event in events] == [
        "create_share",
        "update_share",
        "delete_share",
    ]
    assert [event.correlation_id for event in events] == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
    ]
    assert all(event.actor_user_id == owner.id for event in events)
    assert all(event.target_id == member.id for event in events)
    assert events[1].event_metadata == {
        "kb_id": "kb-audit",
        "before": "reader",
        "after": "manager",
    }


def test_direct_share_rolls_back_and_failure_audit_persists(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    owner = create_user(
        id="owner-rollback",
        platform_role="member",
        role_status="valid",
    )
    member = create_user(
        id="member-rollback",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        session.add(
            db_models.KnowledgeBase(
                id="kb-rollback",
                owner_id=owner.id,
                slug="rollback-docs",
                name="Rollback Docs",
                description=None,
                current_size_bytes=0,
                quota_bytes=None,
            )
        )
        session.commit()
        service = KnowledgeBaseSharingService(session)
        with (
            patch.object(session, "commit", side_effect=RuntimeError("commit failed")),
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            service.grant_share(
                actor=actor_from_valid_user(owner),
                kb_id="kb-rollback",
                target_type="user",
                target_id=member.id,
                role="reader",
            )

    with session_factory() as session:
        assert session.scalar(select(db_models.KnowledgeBaseShare)) is None
        event = session.scalar(select(db_models.AuditEvent))
        assert event is not None
        assert event.event_type == "knowledge_base.share_created"
        assert event.action == "create_share"
        assert event.result == "failure"
        assert event.error_code == "KB_SHARE_FORBIDDEN"
        assert event.target_type == "user"
        assert event.target_id == member.id
        assert event.event_metadata == {"kb_id": "kb-rollback"}
