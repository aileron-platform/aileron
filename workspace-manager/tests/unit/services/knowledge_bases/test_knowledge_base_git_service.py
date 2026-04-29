"""Knowledge base Git service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from git import Repo

from app.db import models as db_models
from app.models.template_git import (
    TemplateCheckoutRequest,
    TemplateDiscardRequest,
    TemplateStageRequest,
    TemplateUnstageRequest,
)
from app.services.knowledge_base_git_service import (
    KB_VERSION_CONTROL_DISABLED,
    KnowledgeBaseGitService,
)


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
        version_control_enabled=False,
        git_lfs_enabled=False,
        git_default_branch="main",
        git_last_commit_sha=None,
    )


@pytest.fixture
def git_service(mock_db_session, kb, tmp_path):
    with patch("app.services.knowledge_base_git_service.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        service = KnowledgeBaseGitService(mock_db_session)
    service.storage_root = tmp_path
    service.wiki_service.storage_root = tmp_path
    service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    return service


def _enable_existing_repo(git_service: KnowledgeBaseGitService, kb: db_models.KnowledgeBase) -> Repo:
    kb.version_control_enabled = True
    root = git_service.storage_root / kb.id
    root.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(root, initial_branch="main")
    with repo.config_writer() as config:
        config.set_value("user", "name", "KB Tester")
        config.set_value("user", "email", "kb@example.com")
    (root / "wiki").mkdir()
    (root / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
    repo.index.add(["wiki/index.md"])
    commit = repo.index.commit("initial")
    kb.git_last_commit_sha = commit.hexsha
    return repo


@pytest.mark.unit
def test_enable_initializes_team_wiki_git_repository(git_service, kb):
    status = git_service.enable(user_id="owner-1", kb_id="kb-1")

    root = git_service.storage_root / kb.id
    repo = Repo(root)

    assert status.is_git_repo is True
    assert status.current_branch == "main"
    assert kb.version_control_enabled is True
    assert kb.git_default_branch == "main"
    assert kb.git_last_commit_sha == repo.head.commit.hexsha
    assert (root / ".gitignore").read_text(encoding="utf-8") == ".aileron-kb/\n"
    assert (root / "AGENTS.md").is_file()
    assert git_service.db.commit.call_count >= 1


@pytest.mark.unit
def test_git_operation_requires_enabled_kb(git_service):
    with pytest.raises(ValueError, match=KB_VERSION_CONTROL_DISABLED):
        git_service.get_version_control_status(user_id="owner-1", kb_id="kb-1")


@pytest.mark.unit
def test_enable_lfs_writes_gitattributes_and_marks_enabled(git_service, kb):
    _enable_existing_repo(git_service, kb)

    git_service.enable_lfs(
        user_id="owner-1",
        kb_id="kb-1",
        patterns=["raw/**/*.pdf", "raw/**/*.png"],
    )

    attributes = (git_service.storage_root / kb.id / ".gitattributes").read_text(encoding="utf-8")
    assert "raw/**/*.pdf filter=lfs diff=lfs merge=lfs -text" in attributes
    assert "raw/**/*.png filter=lfs diff=lfs merge=lfs -text" in attributes
    assert kb.git_lfs_enabled is True

    changes = git_service.get_file_changes(user_id="owner-1", kb_id="kb-1")
    assert [item.path for item in changes.staged] == [".gitattributes"]


@pytest.mark.unit
def test_changes_stage_unstage_discard_and_commit(git_service, kb):
    _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "wiki" / "index.md"
    target.write_text("# Index\n\nNew line\n", encoding="utf-8")
    new_page = root / "wiki" / "new.md"
    new_page.write_text("# New\n", encoding="utf-8")

    changes = git_service.get_file_changes(user_id="owner-1", kb_id="kb-1")
    assert [item.path for item in changes.unstaged] == ["wiki/index.md"]
    assert [item.path for item in changes.untracked] == ["wiki/new.md"]

    staged = git_service.stage(
        user_id="owner-1",
        kb_id="kb-1",
        payload=TemplateStageRequest(paths=["wiki/index.md", "wiki/new.md"]),
    )
    assert staged.staged == ["wiki/index.md", "wiki/new.md"]

    status = git_service.get_version_control_status(user_id="owner-1", kb_id="kb-1")
    assert status.stagedCount == 2
    assert status.untrackedCount == 0

    unstaged = git_service.unstage(
        user_id="owner-1",
        kb_id="kb-1",
        payload=TemplateUnstageRequest(paths=["wiki/new.md"]),
    )
    assert unstaged.unstaged == ["wiki/new.md"]
    assert unstaged.remainingStaged == 1

    discarded = git_service.discard(
        user_id="owner-1",
        kb_id="kb-1",
        payload=TemplateDiscardRequest(paths=["wiki/new.md"]),
    )
    assert discarded.discarded == ["wiki/new.md"]
    assert not new_page.exists()

    response = git_service.commit(user_id="owner-1", kb_id="kb-1", message="Update index")
    assert response.commit.message == "Update index"
    assert kb.git_last_commit_sha == response.commit.id

    history = git_service.list_commits(user_id="owner-1", kb_id="kb-1")
    assert history.total == 2
    assert [item.message for item in history.items] == ["Update index", "initial"]


@pytest.mark.unit
def test_commit_all_stages_modified_untracked_and_deleted_files(git_service, kb):
    _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "wiki" / "index.md"
    target.write_text("# Index\n\nUpdated\n", encoding="utf-8")
    (root / "wiki" / "new.md").write_text("# New\n", encoding="utf-8")
    target.unlink()

    response = git_service.commit_all(user_id="owner-1", kb_id="kb-1", message="Auto wiki index")

    assert response.commit.message == "Auto wiki index"
    assert kb.git_last_commit_sha == response.commit.id
    changes = git_service.get_file_changes(user_id="owner-1", kb_id="kb-1")
    assert changes.staged == []
    assert changes.unstaged == []
    assert changes.untracked == []


@pytest.mark.unit
def test_diff_blob_branch_and_rollback(git_service, kb):
    repo = _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "wiki" / "index.md"
    initial_commit = repo.head.commit.hexsha
    target.write_text("# Index\n\nNext\n", encoding="utf-8")
    git_service.stage(
        user_id="owner-1",
        kb_id="kb-1",
        payload=TemplateStageRequest(paths=["wiki/index.md"]),
    )
    updated = git_service.commit(user_id="owner-1", kb_id="kb-1", message="Update index")

    files = git_service.get_commit_files(user_id="owner-1", kb_id="kb-1", commit_id=updated.commit.id)
    assert [item.path for item in files.files] == ["wiki/index.md"]

    blob = git_service.blob(user_id="owner-1", kb_id="kb-1", path="wiki/index.md", revision=initial_commit)
    assert blob.content == "# Index"

    diff = git_service.diff(user_id="owner-1", kb_id="kb-1", path="wiki/index.md")
    assert diff.patch == ""

    checkout = git_service.checkout_branch(
        user_id="owner-1",
        kb_id="kb-1",
        branch_name="draft",
        payload=TemplateCheckoutRequest(create=True),
    )
    assert checkout.branch == "draft"
    branches = git_service.list_branches(user_id="owner-1", kb_id="kb-1")
    assert {branch.name for branch in branches.branches} >= {"main", "draft"}

    with pytest.raises(ValueError, match="KB_GIT_ROLLBACK_CONFIRMATION_REQUIRED"):
        git_service.rollback(user_id="owner-1", kb_id="kb-1", revision=initial_commit, confirm="wrong")

    git_service.rollback(user_id="owner-1", kb_id="kb-1", revision=initial_commit, confirm="RESET_KB_GIT")
    assert target.read_text(encoding="utf-8") == "# Index\n"


@pytest.mark.unit
def test_rejects_paths_outside_repository(git_service, kb):
    _enable_existing_repo(git_service, kb)

    with pytest.raises(ValueError, match="GIT_PATH_OUTSIDE_REPOSITORY"):
        git_service.stage(
            user_id="owner-1",
            kb_id="kb-1",
            payload=TemplateStageRequest(paths=["../escape.md"]),
        )
