"""Automation task knowledge base metadata tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.tasks import (
    AUTOMATION_PERMISSION_MODE,
    _automation_session_create_payload,
    _knowledge_base_wiki_index_version_metadata,
)


@pytest.mark.unit
def test_wiki_index_metadata_commits_when_version_control_enabled():
    db = MagicMock()
    db.get.return_value = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        version_control_enabled=True,
    )
    changes = MagicMock(
        staged=[],
        unstaged=[type("Change", (), {"path": "wiki/index.md"})()],
        untracked=[type("Change", (), {"path": "wiki/new.md"})()],
    )

    with patch("app.services.knowledge_base_git_service.KnowledgeBaseGitService") as service_cls:
        service = service_cls.return_value
        service.get_file_changes.return_value = changes
        service.commit_all.return_value = type(
            "CommitResponse",
            (),
            {"commit": type("Commit", (), {"id": "abc1234"})()},
        )()

        metadata = _knowledge_base_wiki_index_version_metadata(
            db,
            user_id="owner-1",
            knowledge_base_id="kb-1",
        )

    service.get_file_changes.assert_called_once_with(user_id="owner-1", kb_id="kb-1")
    service.commit_all.assert_called_once_with(
        user_id="owner-1",
        kb_id="kb-1",
        message="Update knowledge base wiki index",
    )
    assert metadata == {
        "knowledgeBaseId": "kb-1",
        "versionControlEnabled": True,
        "filesChanged": ["wiki/index.md", "wiki/new.md"],
        "commitId": "abc1234",
    }


@pytest.mark.unit
def test_wiki_index_metadata_skips_commit_when_version_control_disabled():
    db = MagicMock()
    db.get.return_value = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        version_control_enabled=False,
    )

    metadata = _knowledge_base_wiki_index_version_metadata(
        db,
        user_id="owner-1",
        knowledge_base_id="kb-1",
    )

    assert metadata == {
        "knowledgeBaseId": "kb-1",
        "versionControlEnabled": False,
        "filesChanged": [],
        "commitId": None,
    }


@pytest.mark.unit
def test_automation_session_create_payload_uses_bypass_permissions():
    payload = _automation_session_create_payload(
        workspace_id="workspace-1",
        agentic_tool="claude-code",
    )

    assert payload["workspace_id"] == "workspace-1"
    assert payload["agentic_tool"] == "claude-code"
    assert payload["source"] == "automation"
    assert payload["permission_config"] == {"mode": AUTOMATION_PERMISSION_MODE}
    assert "workspace_path" not in payload
    assert AUTOMATION_PERMISSION_MODE == "bypassPermissions"


@pytest.mark.unit
def test_automation_session_create_payload_includes_wiki_index_workspace_path():
    payload = _automation_session_create_payload(
        workspace_id="workspace-1",
        agentic_tool="claude-code",
        workspace_path="/knowledge/team-docs",
    )

    assert payload["workspace_path"] == "/knowledge/team-docs"
    assert payload["permission_config"] == {"mode": AUTOMATION_PERMISSION_MODE}
