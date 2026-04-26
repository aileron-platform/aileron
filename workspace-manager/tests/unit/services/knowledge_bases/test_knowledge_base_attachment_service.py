"""Knowledge base attachment service 單元測試。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.db import models as db_models
from app.services.knowledge_base_attachment_service import KnowledgeBaseAttachmentService
from app.services.knowledge_base_service import KnowledgeBaseConflictError, KnowledgeBaseNotFoundError


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.scalar = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture
def attachment_service(mock_db_session):
    service = KnowledgeBaseAttachmentService(mock_db_session)
    service.workspace_service._require_workspace_access = MagicMock()
    return service


@pytest.mark.unit
def test_attach_uses_suffix_for_conflicting_default_alias(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.side_effect = [workspace]
    mock_db_session.scalar.side_effect = [None, object(), None]
    attachment_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "editor"})())
    )

    attachment = attachment_service.attach(
        user_id="owner-1",
        workspace_id="ws-1",
        kb_id="kb-1",
    )

    assert attachment.mount_alias == "docs-2"
    assert attachment.mode == "rw"


@pytest.mark.unit
def test_attach_forces_viewer_to_read_only(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-2",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.side_effect = [workspace]
    mock_db_session.scalar.side_effect = [None, None]
    attachment_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )

    attachment = attachment_service.attach(
        user_id="user-2",
        workspace_id="ws-1",
        kb_id="kb-1",
        mode="rw",
    )

    assert attachment.mount_alias == "docs"
    assert attachment.mode == "ro"


@pytest.mark.unit
def test_attach_rejects_duplicate_attachment(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.side_effect = [workspace]
    mock_db_session.scalar.return_value = object()
    attachment_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "editor"})())
    )

    with pytest.raises(KnowledgeBaseConflictError, match="already attached to this workspace"):
        attachment_service.attach(
            user_id="owner-1",
            workspace_id="ws-1",
            kb_id="kb-1",
        )


@pytest.mark.unit
def test_attach_rejects_explicit_alias_conflict(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.side_effect = [workspace]
    mock_db_session.scalar.side_effect = [None, object()]
    attachment_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "editor"})())
    )

    with pytest.raises(KnowledgeBaseConflictError, match="mount alias already exists"):
        attachment_service.attach(
            user_id="owner-1",
            workspace_id="ws-1",
            kb_id="kb-1",
            mount_alias="docs",
        )


@pytest.mark.unit
def test_attach_checks_workspace_and_kb_permissions(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )
    mock_db_session.get.side_effect = [workspace]
    mock_db_session.scalar.side_effect = [None, None]
    attachment_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "editor"})())
    )

    attachment_service.attach(
        user_id="owner-1",
        workspace_id="ws-1",
        kb_id="kb-1",
        mode="rw",
    )

    attachment_service.workspace_service._require_workspace_access.assert_called_once_with(
        workspace,
        current_user_id="owner-1",
        minimum_role="editor",
    )
    attachment_service.kb_service.get_kb.assert_called_once_with(
        user_id="owner-1",
        kb_id="kb-1",
        minimum_role="viewer",
    )


@pytest.mark.unit
def test_attach_propagates_tombstoned_kb_error(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    mock_db_session.get.side_effect = [workspace]
    attachment_service.kb_service.get_kb = MagicMock(
        side_effect=KnowledgeBaseNotFoundError("知識庫does not exist")
    )

    with pytest.raises(KnowledgeBaseNotFoundError, match="知識庫does not exist"):
        attachment_service.attach(
            user_id="owner-1",
            workspace_id="ws-1",
            kb_id="kb-1",
        )


@pytest.mark.unit
def test_reconcile_on_start_removes_tombstoned_attachments(
    attachment_service,
    mock_db_session,
):
    workspace = db_models.Workspace(
        id="ws-1",
        owner_id="owner-1",
        name="Workspace",
        runtime="universal",
        provisioner="docker",
    )
    active_attachment = MagicMock()
    active_attachment.kb_id = "kb-1"
    active_attachment.mount_alias = "docs"
    active_attachment.mode = "rw"
    active_attachment.knowledge_base = MagicMock(id="kb-1", tombstoned_at=None)

    tombstoned_attachment = MagicMock()
    tombstoned_attachment.kb_id = "kb-2"
    tombstoned_attachment.mount_alias = "old-docs"
    tombstoned_attachment.mode = "ro"
    tombstoned_attachment.knowledge_base = MagicMock(
        id="kb-2",
        tombstoned_at=datetime.utcnow(),
    )
    workspace.knowledge_base_attachments = [active_attachment, tombstoned_attachment]
    mock_db_session.get.return_value = workspace

    signature = attachment_service.reconcile_on_start(workspace_id="ws-1")

    assert isinstance(signature, str)
    assert len(signature) == 64
    mock_db_session.delete.assert_called_once_with(tombstoned_attachment)
    mock_db_session.flush.assert_called_once()
