"""Knowledge base attachment transaction tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.modules.authorization.actor import actor_from_valid_user
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.knowledge_base.errors import KnowledgeBaseError
from app.modules.knowledge_base.mount_contract import validate_mount_alias
from app.db import models as db_models
from app.modules.knowledge_base.attachments import (
    KnowledgeBaseAttachmentService,
)
from app.modules.knowledge_base.access import (
    KnowledgeBaseConflictError,
)

WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
KNOWLEDGE_BASE_ID = "22222222-2222-4222-8222-222222222222"


def _valid_user(create_user, *, user_id: str, role: str = "member"):
    return create_user(
        id=user_id,
        platform_role=role,
        role_status="valid",
        identity_enabled=True,
        sync_status="synced",
        is_active=True,
    )


def _seed_workspace_and_kb(
    session,
    *,
    workspace_owner_id: str,
    kb_owner_id: str,
    workspace_id: str = WORKSPACE_ID,
    kb_id: str = KNOWLEDGE_BASE_ID,
    runtime_status: str = "running",
) -> tuple[db_models.Workspace, db_models.KnowledgeBase]:
    workspace = db_models.Workspace(
        id=workspace_id,
        owner_id=workspace_owner_id,
        name="Workspace",
        runtime="universal",
        provisioner="docker",
        runtime_status=runtime_status,
        knowledge_base_mount_active_revision=0,
        knowledge_base_mount_desired_revision=0,
        knowledge_base_mount_observed_revision=0,
        knowledge_base_mount_sync_status="ready",
        knowledge_base_mount_active_snapshot=[],
        knowledge_base_mount_candidate_snapshot=None,
        knowledge_base_mount_failed_snapshot=None,
        runtime_access_revision=0,
        runtime_access_observed_revision=0,
    )
    kb = db_models.KnowledgeBase(
        id=kb_id,
        owner_id=kb_owner_id,
        slug=f"docs-{kb_id}",
        name="Docs",
        current_size_bytes=0,
    )
    session.add_all([workspace, kb])
    session.commit()
    return workspace, kb


def _share_kb(
    session,
    *,
    kb_id: str,
    user_id: str,
    granted_by_id: str,
    role: str = "manager",
) -> None:
    session.add(
        db_models.KnowledgeBaseShare(
            id=f"kb-share-{kb_id}-{user_id}",
            kb_id=kb_id,
            target_type="user",
            target_id=user_id,
            role=role,
            granted_by_id=granted_by_id,
        )
    )
    session.commit()


@pytest.mark.parametrize(
    "alias",
    (
        "a",
        "a" + "1" * 62,
        "product-docs",
    ),
)
def test_validate_mount_alias_accepts_only_canonical_values(alias: str) -> None:
    assert validate_mount_alias(alias) == alias


@pytest.mark.parametrize(
    "alias",
    (
        "",
        "a" + "1" * 63,
        "Product",
        "文件",
        " docs",
        "docs ",
        "system",
        "runtime",
        "workspace",
        "tmp",
        "lost-found",
        ".",
        "..",
        "docs/api",
        "docs\\api",
        "docs\napi",
        "/docs",
        "%2fdocs",
    ),
)
def test_validate_mount_alias_rejects_noncanonical_values(alias: str) -> None:
    with pytest.raises(KnowledgeBaseError) as exc_info:
        validate_mount_alias(alias)

    assert exc_info.value.code == "KB_MOUNT_ALIAS_INVALID"


def test_attach_manager_creates_revision_job_and_audit_in_one_transaction(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")
    kb_owner = _valid_user(create_user, user_id="kb-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=kb_owner.id,
        )
        _share_kb(
            session,
            kb_id=kb.id,
            user_id=actor.id,
            granted_by_id=kb_owner.id,
        )

        result = KnowledgeBaseAttachmentService(session).attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="product",
            correlation_id="11111111-1111-4111-8111-111111111111",
        )

        assert result.attachment.status == "pending"
        assert result.attachment.mount_alias == "product"
        assert result.workspace.knowledge_base_mount_active_revision == 0
        assert result.workspace.knowledge_base_mount_desired_revision == 1
        assert result.workspace.knowledge_base_mount_observed_revision == 0
        assert result.workspace.knowledge_base_mount_sync_status == "preflighting"
        assert result.workspace.knowledge_base_mount_active_snapshot == []
        assert result.workspace.knowledge_base_mount_candidate_snapshot == [
            {
                "attachmentId": result.attachment.id,
                "knowledgeBaseId": kb.id,
                "mountAlias": "product",
                "attachedById": actor.id,
            }
        ]
        assert result.job.status == "queued"
        assert result.job.target_revision == 1
        assert result.job.strategy == "docker"
        assert result.job.correlation_id == "11111111-1111-4111-8111-111111111111"

        events = list(
            session.scalars(
                select(db_models.AuditEvent).where(
                    db_models.AuditEvent.correlation_id
                    == "11111111-1111-4111-8111-111111111111"
                )
            ).all()
        )
        assert [event.event_type for event in events] == [
            "workspace.knowledge_base_attached"
        ]


def test_attach_requires_kb_manager(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")
    kb_owner = _valid_user(create_user, user_id="kb-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=kb_owner.id,
        )
        _share_kb(
            session,
            kb_id=kb.id,
            user_id=actor.id,
            granted_by_id=kb_owner.id,
            role="reader",
        )

        with pytest.raises(AuthorizationOperationError) as exc_info:
            KnowledgeBaseAttachmentService(session).attach(
                actor=actor_from_valid_user(actor),
                workspace_id=workspace.id,
                kb_id=kb.id,
                mount_alias="docs",
            )

        assert exc_info.value.error_code == "KB_PERMISSION_DENIED"


def test_attach_public_kb_requires_only_workspace_manager(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner-public")
    kb_owner = _valid_user(create_user, user_id="kb-owner-public")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=kb_owner.id,
        )
        kb.visibility = "public"
        session.commit()

        result = KnowledgeBaseAttachmentService(session).attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="public-docs",
        )

        assert result.attachment.status == "pending"


def test_private_transition_keeps_non_public_reader_and_removes_public_only_reader(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    workspace_owner = _valid_user(create_user, user_id="workspace-owner-private")
    kb_owner = _valid_user(create_user, user_id="kb-owner-private")
    direct_reader = _valid_user(create_user, user_id="direct-reader-private")
    public_reader = _valid_user(create_user, user_id="public-reader-private")

    with session_factory() as session:
        _, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=workspace_owner.id,
            kb_owner_id=kb_owner.id,
            workspace_id="workspace-private-transition",
            kb_id="kb-private-transition",
        )
        kb.visibility = "public"
        session.commit()
        _share_kb(
            session,
            kb_id=kb.id,
            user_id=direct_reader.id,
            granted_by_id=kb_owner.id,
            role="reader",
        )

        service = KnowledgeBaseAttachmentService(session)
        assert service._mount_principal_can_keep_private(
            kb_id=kb.id,
            user_id=direct_reader.id,
        )
        assert not service._mount_principal_can_keep_private(
            kb_id=kb.id,
            user_id=public_reader.id,
        )


def test_alias_update_and_detach_do_not_recheck_direct_kb_access(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")
    kb_owner = _valid_user(create_user, user_id="kb-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=kb_owner.id,
        )
        _share_kb(
            session,
            kb_id=kb.id,
            user_id=actor.id,
            granted_by_id=kb_owner.id,
        )
        service = KnowledgeBaseAttachmentService(session)
        attached = service.attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="docs",
            correlation_id="attach-correlation",
        )
        active_snapshot = list(workspace.knowledge_base_mount_candidate_snapshot)
        workspace.knowledge_base_mount_active_snapshot = active_snapshot
        workspace.knowledge_base_mount_active_revision = 1
        workspace.knowledge_base_mount_observed_revision = 1
        workspace.knowledge_base_mount_candidate_snapshot = None
        workspace.knowledge_base_mount_sync_status = "ready"
        attached.job.status = "succeeded"
        attached.job.finished_at = datetime.utcnow()
        session.add(
            db_models.WorkspaceKnowledgeBaseAttachment(
                id=attached.attachment.id,
                workspace_id=workspace.id,
                kb_id=kb.id,
                mount_alias="docs",
                attached_by_id=actor.id,
            )
        )
        session.commit()
        share = session.scalar(
            select(db_models.KnowledgeBaseShare).where(
                db_models.KnowledgeBaseShare.kb_id == kb.id,
                db_models.KnowledgeBaseShare.target_id == actor.id,
            )
        )
        session.delete(share)
        session.commit()

        updated = service.update_attachment(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            attachment_id=attached.attachment.id,
            mount_alias="runbook",
            correlation_id="update-correlation",
        )
        renamed_projection = service.list_attachments_for_workspace(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
        )
        detached = service.detach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            attachment_id=attached.attachment.id,
            correlation_id="detach-correlation",
        )
        removal_projection = service.list_attachments_for_workspace(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
        )

        assert updated.attachment.mount_alias == "runbook"
        assert updated.attachment.status == "pending"
        assert len(renamed_projection) == 1
        assert renamed_projection[0].status == "pending"
        assert renamed_projection[0].mount_alias == "runbook"
        assert detached.attachment.status == "pending_removal"
        assert len(removal_projection) == 1
        assert removal_projection[0].status == "pending_removal"
        assert removal_projection[0].mount_alias == "docs"
        assert detached.job.job_metadata["mutation_action"] == "detach"
        assert detached.workspace.knowledge_base_mount_desired_revision == 3
        assert detached.workspace.knowledge_base_mount_candidate_snapshot == []

        superseded = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.status == "superseded")
                .order_by(db_models.WorkspaceRuntimeJob.target_revision)
            ).all()
        )
        assert [job.target_revision for job in superseded] == [2]
        assert [job.correlation_id for job in superseded] == ["update-correlation"]


def test_pending_candidate_is_visible_after_workspace_and_kb_list_reload(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="aggregate-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=actor.id,
        )
        result = KnowledgeBaseAttachmentService(session).attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="docs",
        )
        workspace_id = workspace.id
        kb_id = kb.id
        attachment_id = result.attachment.id

    with session_factory() as session:
        service = KnowledgeBaseAttachmentService(session)
        workspace_items = service.list_attachments_for_workspace(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace_id,
        )
        kb_usage = service.list_attachments_for_kb(
            actor=actor_from_valid_user(actor),
            kb_id=kb_id,
        )

        assert len(workspace_items) == 1
        assert workspace_items[0].id == attachment_id
        assert workspace_items[0].status == "pending"
        assert len(kb_usage.visible_attachments) == 1
        assert kb_usage.visible_attachments[0].id == attachment_id
        assert kb_usage.visible_attachments[0].status == "pending"
        assert kb_usage.attachment_count == 1


def test_attachment_path_with_missing_workspace_returns_workspace_not_found(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=actor.id,
        )
        attached = KnowledgeBaseAttachmentService(session).attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="docs",
        )

        with pytest.raises(AuthorizationOperationError) as exc_info:
            KnowledgeBaseAttachmentService(session).update_attachment(
                actor=actor_from_valid_user(actor),
                workspace_id="another-workspace",
                attachment_id=attached.attachment.id,
                mount_alias="runbook",
            )

        assert exc_info.value.error_code == "WORKSPACE_ACCESS_DENIED"


def test_stopped_detach_uses_offline_candidate_promotion(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=actor.id,
            runtime_status="stopped",
        )
        attached = KnowledgeBaseAttachmentService(session).attach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias="docs",
        )

        detached = KnowledgeBaseAttachmentService(session).detach(
            actor=actor_from_valid_user(actor),
            workspace_id=workspace.id,
            attachment_id=attached.attachment.id,
        )

        assert detached.attachment.status == "pending_removal"
        assert detached.job.job_metadata["offline_promotion"] is True
        assert detached.workspace.knowledge_base_mount_candidate_snapshot == []
        assert (
            session.get(
                db_models.WorkspaceKnowledgeBaseAttachment,
                attached.attachment.id,
            )
            is None
        )


def test_mutation_rollback_removes_attachment_revision_job_and_audit(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id="workspace-owner")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=actor.id,
        )
        service = KnowledgeBaseAttachmentService(session)

        def fail_audit(**_kwargs):
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr(service.audit_events, "record", fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            service.attach(
                actor=actor_from_valid_user(actor),
                workspace_id=workspace.id,
                kb_id=kb.id,
                mount_alias="docs",
            )

        persisted_workspace = session.get(db_models.Workspace, workspace.id)
        assert persisted_workspace.knowledge_base_mount_desired_revision == 0
        assert persisted_workspace.knowledge_base_mount_candidate_snapshot is None
        assert (
            session.scalar(select(db_models.WorkspaceKnowledgeBaseAttachment)) is None
        )
        assert session.scalar(select(db_models.WorkspaceRuntimeJob)) is None
        assert session.scalar(select(db_models.AuditEvent)) is None


@pytest.mark.parametrize("runtime_status", ("stopping", "deleting"))
def test_attachment_mutation_rejects_stopping_and_deleting_workspaces(
    test_app,
    create_user,
    runtime_status: str,
) -> None:
    _, session_factory = test_app
    actor = _valid_user(create_user, user_id=f"owner-{runtime_status}")

    with session_factory() as session:
        workspace, kb = _seed_workspace_and_kb(
            session,
            workspace_owner_id=actor.id,
            kb_owner_id=actor.id,
            workspace_id=(
                "33333333-3333-4333-8333-333333333333"
                if runtime_status == "stopping"
                else "44444444-4444-4444-8444-444444444444"
            ),
            kb_id=(
                "55555555-5555-4555-8555-555555555555"
                if runtime_status == "stopping"
                else "66666666-6666-4666-8666-666666666666"
            ),
            runtime_status=runtime_status,
        )

        with pytest.raises(KnowledgeBaseConflictError) as exc_info:
            KnowledgeBaseAttachmentService(session).attach(
                actor=actor_from_valid_user(actor),
                workspace_id=workspace.id,
                kb_id=kb.id,
                mount_alias="docs",
            )

        assert exc_info.value.code == "WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS"
