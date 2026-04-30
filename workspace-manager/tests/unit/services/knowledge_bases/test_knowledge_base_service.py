"""Knowledge base service unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db import models as db_models
from app.services.knowledge_base_service import (
    KnowledgeBaseConflictError,
    KnowledgeBaseError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
    compute_attachment_signature,
    normalize_kb_slug,
)


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
    service = KnowledgeBaseService(mock_db_session)
    service.wiki_service = MagicMock()
    return service


@pytest.fixture
def sharing_service(mock_db_session):
    return KnowledgeBaseSharingService(mock_db_session)


@pytest.mark.unit
def test_normalize_kb_slug_converts_to_dash_case() -> None:
    assert normalize_kb_slug(" API Docs v2 ") == "api-docs-v2"


@pytest.mark.unit
def test_create_kb_persists_normalized_slug(
    knowledge_base_service,
    mock_db_session,
    user_factory,
):
    owner = user_factory(id="owner-1")
    mock_db_session.get.return_value = owner
    mock_db_session.scalar.return_value = None

    kb = knowledge_base_service.create_kb(
        owner_id=owner.id,
        name="API Docs",
        slug=" API Docs ",
        description="shared docs",
    )

    assert isinstance(kb, db_models.KnowledgeBase)
    assert kb.owner_id == owner.id
    assert kb.slug == "api-docs"
    assert kb.current_size_bytes == 0
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(kb)
    knowledge_base_service.wiki_service.initialize.assert_called_once_with(kb)


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
            owner_id="owner-1",
            name="Docs",
            slug="docs",
        )


@pytest.mark.unit
def test_delete_kb_force_marks_tombstone(
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
    mock_db_session.get.return_value = kb
    mock_db_session.scalar.return_value = 2

    deleted = knowledge_base_service.delete_kb(
        user_id="owner-1",
        kb_id="kb-1",
        force=True,
    )

    assert deleted.tombstoned_at is not None
    mock_db_session.delete.assert_not_called()


@pytest.mark.unit
def test_delete_kb_rejects_when_attached_without_force(
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
    mock_db_session.get.return_value = kb
    mock_db_session.scalar.return_value = 1

    with pytest.raises(KnowledgeBaseConflictError, match="still mounted by workspace"):
        knowledge_base_service.delete_kb(
            user_id="owner-1",
            kb_id="kb-1",
            force=False,
        )


@pytest.mark.unit
def test_update_quota_persists_valid_quota(
    knowledge_base_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=10,
        quota_bytes=None,
    )
    mock_db_session.get.return_value = kb

    updated = knowledge_base_service.update_quota(
        user_id="owner-1",
        kb_id="kb-1",
        quota_bytes=20,
    )

    assert updated.quota_bytes == 20
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(kb)


@pytest.mark.unit
def test_update_quota_clears_explicit_quota(
    knowledge_base_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=10,
        quota_bytes=100,
    )
    mock_db_session.get.return_value = kb

    updated = knowledge_base_service.update_quota(
        user_id="owner-1",
        kb_id="kb-1",
        quota_bytes=None,
    )

    assert updated.quota_bytes is None
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(kb)


@pytest.mark.unit
def test_update_quota_rejects_negative_quota(
    knowledge_base_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=10,
        quota_bytes=100,
    )
    mock_db_session.get.return_value = kb

    with pytest.raises(KnowledgeBaseError, match="quota is invalid") as exc_info:
        knowledge_base_service.update_quota(
            user_id="owner-1",
            kb_id="kb-1",
            quota_bytes=-1,
        )

    assert exc_info.value.code == "KB_INVALID_QUOTA"
    assert kb.quota_bytes == 100
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
def test_update_quota_rejects_quota_below_current_usage(
    knowledge_base_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=10,
        quota_bytes=100,
    )
    mock_db_session.get.return_value = kb

    with pytest.raises(KnowledgeBaseError, match="lower than current usage") as exc_info:
        knowledge_base_service.update_quota(
            user_id="owner-1",
            kb_id="kb-1",
            quota_bytes=9,
        )

    assert exc_info.value.code == "KB_QUOTA_BELOW_USAGE"
    assert exc_info.value.params["currentSizeBytes"] == 10
    assert kb.quota_bytes == 100
    mock_db_session.commit.assert_not_called()


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

    with pytest.raises(KnowledgeBaseConflictError, match="share knowledge base with owner"):
        sharing_service.grant_share(
            user_id="owner-1",
            kb_id="kb-1",
            target_user_id="owner-1",
            role="viewer",
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
    sharing_service.kb_service.get_kb = MagicMock(return_value=(kb, object()))
    mock_db_session.scalar.return_value = object()

    with pytest.raises(KnowledgeBaseConflictError, match="Knowledge base share already exists"):
        sharing_service.grant_share(
            user_id="owner-1",
            kb_id="kb-1",
            target_user_id="user-2",
            role="viewer",
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
    sharing_service.kb_service.get_kb = MagicMock(return_value=(kb, object()))
    mock_db_session.scalar.return_value = None

    with pytest.raises(KnowledgeBaseError, match="Invalid knowledge base sharing role"):
        sharing_service.grant_share(
            user_id="owner-1",
            kb_id="kb-1",
            target_user_id="user-2",
            role="owner",
        )


@pytest.mark.unit
def test_list_shares_requires_manager_access(
    sharing_service,
):
    sharing_service.kb_service.get_kb = MagicMock()

    sharing_service.list_shares(user_id="user-1", kb_id="kb-1")

    sharing_service.kb_service.get_kb.assert_called_once_with(
        user_id="user-1",
        kb_id="kb-1",
        minimum_role="manager",
    )


@pytest.mark.unit
def test_update_share_role_rejects_missing_share(
    sharing_service,
    mock_db_session,
):
    mock_db_session.get.return_value = None

    with pytest.raises(KnowledgeBaseNotFoundError, match="Knowledge base share does not exist"):
        sharing_service.update_share_role(
            user_id="owner-1",
            share_id="share-1",
            role="editor",
        )


@pytest.mark.unit
def test_update_share_role_rejects_invalid_role(
    sharing_service,
    mock_db_session,
):
    share = db_models.KnowledgeBaseShare(
        id="share-1",
        kb_id="kb-1",
        user_id="user-2",
        role="viewer",
        granted_by_id="owner-1",
    )
    mock_db_session.get.return_value = share
    sharing_service.kb_service.get_kb = MagicMock(return_value=(object(), object()))

    with pytest.raises(KnowledgeBaseError, match="Invalid knowledge base sharing role"):
        sharing_service.update_share_role(
            user_id="owner-1",
            share_id="share-1",
            role="owner",
        )


@pytest.mark.unit
def test_compute_attachment_signature_is_stable() -> None:
    left = [
        SimpleNamespace(kb_id="kb-2", mount_alias="beta", mode="ro"),
        SimpleNamespace(kb_id="kb-1", mount_alias="alpha", mode="rw"),
    ]
    right = list(reversed(left))

    assert compute_attachment_signature(left) == compute_attachment_signature(right)
