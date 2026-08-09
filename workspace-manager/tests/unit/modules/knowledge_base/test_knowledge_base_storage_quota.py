"""Focused tests for shared knowledge base storage and quota helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.file_management import FileManagementException
from app.modules.knowledge_base import files as file_service_module
from app.modules.knowledge_base import git as git_service_module
from app.modules.knowledge_base import query as query_service_module
from app.modules.knowledge_base import sources as source_service_module
from app.modules.knowledge_base.files import (
    KB_OWNER_QUOTA_EXCEEDED_MESSAGE,
    KB_QUOTA_EXCEEDED_MESSAGE,
    KnowledgeBaseFileService,
)
from app.modules.knowledge_base.git import KnowledgeBaseGitService
from app.modules.knowledge_base.query import KnowledgeBaseQueryService
from app.modules.knowledge_base.quota import (
    enforce_knowledge_base_storage_quota,
)
from app.modules.knowledge_base.sources import (
    KB_SOURCE_OWNER_QUOTA_EXCEEDED_MESSAGE,
    KB_SOURCE_QUOTA_EXCEEDED_MESSAGE,
    KnowledgeBaseSourceService,
)
from app.modules.knowledge_base.storage import (
    ensure_knowledge_base_storage_root,
)

pytestmark = pytest.mark.unit


def _knowledge_base(
    *,
    current_size_bytes: int = 10,
    quota_bytes: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="kb-1",
        owner_id="owner-1",
        current_size_bytes=current_size_bytes,
        quota_bytes=quota_bytes,
    )


def test_ensure_knowledge_base_storage_root_is_idempotent(tmp_path: Path) -> None:
    expected = tmp_path / "kb-1"

    first = ensure_knowledge_base_storage_root(tmp_path, "kb-1")
    second = ensure_knowledge_base_storage_root(tmp_path, "kb-1")

    assert first == expected
    assert second == expected
    assert expected.is_dir()


@pytest.mark.parametrize(
    ("service_type", "service_module"),
    [
        (KnowledgeBaseFileService, file_service_module),
        (KnowledgeBaseSourceService, source_service_module),
        (KnowledgeBaseQueryService, query_service_module),
        (KnowledgeBaseGitService, git_service_module),
    ],
)
def test_service_kb_root_wrappers_use_shared_storage_helper(
    monkeypatch,
    tmp_path: Path,
    service_type,
    service_module,
) -> None:
    expected = tmp_path / "resolved" / "kb-1"
    shared_helper = MagicMock(return_value=expected)
    monkeypatch.setattr(
        service_module,
        "ensure_knowledge_base_storage_root",
        shared_helper,
    )
    service = object.__new__(service_type)
    service.storage_root = tmp_path

    assert service._kb_root("kb-1") == expected
    shared_helper.assert_called_once_with(tmp_path, "kb-1")


def test_quota_helper_ignores_non_positive_delta_without_querying_owner() -> None:
    db = MagicMock()

    enforce_knowledge_base_storage_quota(
        db=db,
        knowledge_base=_knowledge_base(),
        delta_bytes=0,
        default_knowledge_base_quota_bytes=100,
        default_owner_quota_bytes=200,
        knowledge_base_quota_message="kb quota",
        owner_quota_message="owner quota",
    )

    db.scalar.assert_not_called()


def test_quota_helper_preserves_knowledge_base_error_payload() -> None:
    db = MagicMock()

    with pytest.raises(FileManagementException) as raised:
        enforce_knowledge_base_storage_quota(
            db=db,
            knowledge_base=_knowledge_base(
                current_size_bytes=90,
                quota_bytes=100,
            ),
            delta_bytes=11,
            default_knowledge_base_quota_bytes=500,
            default_owner_quota_bytes=1_000,
            knowledge_base_quota_message="service-specific KB quota message",
            owner_quota_message="service-specific owner quota message",
        )

    error = raised.value
    assert error.code == "KB_QUOTA_EXCEEDED"
    assert error.message == "service-specific KB quota message"
    assert error.details == {
        "kbId": "kb-1",
        "currentSizeBytes": 90,
        "deltaBytes": 11,
        "quotaBytes": 100,
    }
    assert error.status_code == 409
    db.scalar.assert_not_called()


def test_quota_helper_preserves_owner_error_payload() -> None:
    db = MagicMock()
    db.scalar.return_value = 95

    with pytest.raises(FileManagementException) as raised:
        enforce_knowledge_base_storage_quota(
            db=db,
            knowledge_base=_knowledge_base(
                current_size_bytes=10,
                quota_bytes=500,
            ),
            delta_bytes=6,
            default_knowledge_base_quota_bytes=500,
            default_owner_quota_bytes=100,
            knowledge_base_quota_message="service-specific KB quota message",
            owner_quota_message="service-specific owner quota message",
        )

    error = raised.value
    assert error.code == "USER_KB_QUOTA_EXCEEDED"
    assert error.message == "service-specific owner quota message"
    assert error.details == {
        "ownerId": "owner-1",
        "currentTotalBytes": 95,
        "deltaBytes": 6,
        "quotaBytes": 100,
    }
    assert error.status_code == 409
    db.scalar.assert_called_once()


@pytest.mark.parametrize(
    (
        "service_type",
        "service_module",
        "knowledge_base_message",
        "owner_message",
    ),
    [
        (
            KnowledgeBaseFileService,
            file_service_module,
            KB_QUOTA_EXCEEDED_MESSAGE,
            KB_OWNER_QUOTA_EXCEEDED_MESSAGE,
        ),
        (
            KnowledgeBaseSourceService,
            source_service_module,
            KB_SOURCE_QUOTA_EXCEEDED_MESSAGE,
            KB_SOURCE_OWNER_QUOTA_EXCEEDED_MESSAGE,
        ),
    ],
)
def test_service_quota_wrappers_preserve_messages_and_limits(
    monkeypatch,
    service_type,
    service_module,
    knowledge_base_message: str,
    owner_message: str,
) -> None:
    shared_helper = MagicMock()
    monkeypatch.setattr(
        service_module,
        "enforce_knowledge_base_storage_quota",
        shared_helper,
    )
    service = object.__new__(service_type)
    service.db = MagicMock()
    service.settings = SimpleNamespace(
        DEFAULT_KB_QUOTA_BYTES=500,
        DEFAULT_USER_KB_QUOTA_BYTES=1_000,
    )
    knowledge_base = _knowledge_base()

    service._check_quota(knowledge_base, 7)

    shared_helper.assert_called_once_with(
        db=service.db,
        knowledge_base=knowledge_base,
        delta_bytes=7,
        default_knowledge_base_quota_bytes=500,
        default_owner_quota_bytes=1_000,
        knowledge_base_quota_message=knowledge_base_message,
        owner_quota_message=owner_message,
    )
