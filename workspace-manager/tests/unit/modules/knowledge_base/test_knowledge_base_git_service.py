"""Knowledge base Git service unit tests."""

from __future__ import annotations

import inspect
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aileron_git_core import (
    GitOperationInProgressError,
    GitStaleLockError,
    LockScope,
    OperationKind,
    RemoteBranchList,
    VersionControlError,
)
from aileron_git_core.testkit import GitCommandError, Repo

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.git import (
    KB_VERSION_CONTROL_DISABLED,
    KnowledgeBaseGitService,
)
from app.modules.knowledge_base.git_operations import (
    KB_GIT_OPERATION_IN_PROGRESS,
)
from app.modules.knowledge_base.models import KnowledgeBaseGitCloneRequest
from app.modules.version_control.models import (
    DiscardRequest,
    RemoteRequest,
    StageRequest,
    UnstageRequest,
)

OWNER_ACTOR = AuthorizationActor(user_id="owner-1", platform_role="member")


class _AuthorizationProbe(Exception):
    """Stop a Git consumer after its operation authorization call."""


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
    )


@pytest.fixture
def git_service(mock_db_session, kb, tmp_path):
    with patch("app.modules.knowledge_base.git.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        mock_settings.return_value.GIT_STALE_LOCK_THRESHOLD_SECONDS = 35
        service = KnowledgeBaseGitService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    return service


def _enable_existing_repo(
    git_service: KnowledgeBaseGitService, kb: db_models.KnowledgeBase
) -> Repo:
    kb.version_control_enabled = True
    root = git_service.storage_root / kb.id
    root.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(root, initial_branch="main")
    with repo.config_writer() as config:
        config.set_value("user", "name", "KB Tester")
        config.set_value("user", "email", "kb@example.com")
    (root / "notes").mkdir()
    (root / "notes" / "index.md").write_text("# Index\n", encoding="utf-8")
    repo.index.add(["notes/index.md"])
    repo.index.commit("initial")
    return repo


def _create_notes_conflict(repo: Repo, root: Path) -> None:
    target = root / "notes" / "index.md"
    repo.git.checkout("-b", "feature")
    target.write_text("# Index\n\nFeature\n", encoding="utf-8")
    repo.index.add(["notes/index.md"])
    repo.index.commit("feature update")

    repo.git.checkout("main")
    target.write_text("# Index\n\nMain\n", encoding="utf-8")
    repo.index.add(["notes/index.md"])
    repo.index.commit("main update")

    with pytest.raises(GitCommandError):
        repo.git.merge("feature")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "event_type"),
    [
        ("fetch", "version_control_fetched"),
        ("pull", "version_control_pulled"),
        ("push", "version_control_pushed"),
    ],
)
def test_successful_remote_sync_commits_low_sensitivity_activity(
    git_service,
    kb,
    mock_db_session,
    method_name,
    event_type,
):
    repo = _enable_existing_repo(git_service, kb)
    repo.create_remote("origin", "https://example.invalid/repo.git")
    git_service.version_control.execute = MagicMock()

    with patch(
        "app.modules.knowledge_base.git.user_git_environment",
        return_value=nullcontext({}),
    ):
        getattr(git_service, method_name)(
            actor=OWNER_ACTOR,
            kb_id=kb.id,
            payload=RemoteRequest(),
        )

    activity = [
        call.args[0]
        for call in mock_db_session.add.call_args_list
        if isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
    ]
    assert [event.event_type for event in activity] == [event_type]
    mock_db_session.commit.assert_called_once_with()


@pytest.mark.unit
def test_failed_remote_sync_does_not_record_or_commit_activity(
    git_service,
    kb,
    mock_db_session,
):
    repo = _enable_existing_repo(git_service, kb)
    repo.create_remote("origin", "https://example.invalid/repo.git")
    git_service.version_control.execute = MagicMock(
        side_effect=ValueError("fetch failed")
    )

    with (
        patch(
            "app.modules.knowledge_base.git.user_git_environment",
            return_value=nullcontext({}),
        ),
        pytest.raises(ValueError, match="fetch failed"),
    ):
        git_service.fetch(
            actor=OWNER_ACTOR,
            kb_id=kb.id,
            payload=RemoteRequest(),
        )

    assert not any(
        isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
        for call in mock_db_session.add.call_args_list
    )
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "kwargs", "operation"),
    [
        ("enable", {}, OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE),
        (
            "clone",
            {
                "payload": KnowledgeBaseGitCloneRequest(
                    remoteUrl="https://example.invalid/docs.git"
                )
            },
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        (
            "remote_branches",
            {"remote_url": "https://example.invalid/docs.git"},
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        ("update_lfs_patterns", {}, OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE),
        ("repository_status", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "get_version_control_status",
            {},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        ("get_file_changes", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "get_file_changes_numstat",
            {"staged_paths": [], "unstaged_paths": []},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "stage",
            {"payload": StageRequest(paths=["notes.md"])},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "unstage",
            {"payload": UnstageRequest(paths=["notes.md"])},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "discard",
            {"payload": DiscardRequest(paths=["notes.md"])},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "commit",
            {"message": "Update notes"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        ("list_commits", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "get_commit_files",
            {"commit_id": "HEAD"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "diff",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "blob",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        ("list_branches", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "create_branch_and_switch",
            {"name": "feature", "start_point": "HEAD", "upstream": None},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "set_remote_url",
            {"url": "https://example.invalid/repo.git"},
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        (
            "fetch",
            {"payload": RemoteRequest()},
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        (
            "pull",
            {"payload": RemoteRequest()},
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        (
            "push",
            {"payload": RemoteRequest()},
            OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        ),
        (
            "revert_commit",
            {"commit_id": "HEAD"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        ("force_unlock", {}, OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE),
        ("get_operation_status", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
    ],
)
def test_git_callers_use_explicit_operation_ids(
    git_service,
    method_name,
    kwargs,
    operation,
):
    def stop_after_authorization(**call):
        raise _AuthorizationProbe(call)

    git_service.kb_service.get_kb_for_operation.side_effect = stop_after_authorization

    with pytest.raises(_AuthorizationProbe) as probe:
        getattr(git_service, method_name)(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            **kwargs,
        )

    assert probe.value.args[0] == {
        "actor": OWNER_ACTOR,
        "kb_id": "kb-1",
        "operation": operation,
    }


@pytest.mark.unit
def test_enable_initializes_git_repository_and_persists_status(git_service, kb):
    status = git_service.enable(actor=OWNER_ACTOR, kb_id="kb-1")

    root = git_service.storage_root / kb.id
    repo = Repo(root)

    assert status.isInitialized is True
    assert status.currentBranch == "main"
    assert kb.version_control_enabled is True
    assert repo.active_branch.name == "main"
    with pytest.raises(GitCommandError):
        _ = repo.head.commit
    assert not (root / ".gitignore").exists()
    assert not (root / "AGENTS.md").exists()
    assert git_service.db.commit.call_count >= 1


@pytest.mark.unit
def test_repository_status_allows_clone_only_for_empty_root(git_service):
    empty_status = git_service.repository_status(actor=OWNER_ACTOR, kb_id="kb-1")

    root = git_service.storage_root / "kb-1"
    (root / "notes.md").write_text("# Existing\n", encoding="utf-8")
    occupied_status = git_service.repository_status(actor=OWNER_ACTOR, kb_id="kb-1")

    assert empty_status.can_clone_safely is True
    assert empty_status.clone_blocked_reason is None
    assert occupied_status.can_clone_safely is False
    assert occupied_status.clone_blocked_reason == "VC_CLONE_TARGET_NOT_EMPTY"


@pytest.mark.unit
def test_clone_rejects_non_empty_root_without_overwriting_content(git_service):
    root = git_service.storage_root / "kb-1"
    root.mkdir(parents=True)
    existing = root / "notes.md"
    existing.write_text("# Existing\n", encoding="utf-8")

    with pytest.raises(ValueError, match="VC_CLONE_TARGET_NOT_EMPTY"):
        git_service.clone(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            payload=KnowledgeBaseGitCloneRequest(
                remoteUrl="https://example.invalid/docs.git"
            ),
        )

    assert existing.read_text(encoding="utf-8") == "# Existing\n"
    assert not (root / ".git").exists()


@pytest.mark.unit
def test_remote_branches_uses_user_credentials_and_returns_default_branch(
    git_service,
    monkeypatch,
):
    captured: dict[str, object] = {}

    def fake_discover(db, *, user_id, repo_root, remote_url):
        captured.update(
            {
                "db": db,
                "user_id": user_id,
                "repo_root": repo_root,
                "remote_url": remote_url,
            }
        )
        return RemoteBranchList(
            branches=["main", "develop"],
            default_branch="main",
        )

    monkeypatch.setattr(
        "app.modules.knowledge_base.git.discover_remote_branches",
        fake_discover,
    )

    result = git_service.remote_branches(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        remote_url="git@example.com:team/docs.git",
    )

    assert result.branches == ["main", "develop"]
    assert result.default_branch == "main"
    assert captured == {
        "db": git_service.db,
        "user_id": OWNER_ACTOR.user_id,
        "repo_root": git_service.storage_root / "kb-1",
        "remote_url": "git@example.com:team/docs.git",
    }


@pytest.mark.unit
def test_clone_removes_published_checkout_when_database_commit_fails(
    git_service, kb, tmp_path, monkeypatch
):
    source_root = tmp_path / "source"
    source_repo = Repo.init(source_root, initial_branch="main")
    (source_root / "notes.md").write_text("# Remote\n", encoding="utf-8")
    source_repo.index.add(["notes.md"])
    source_repo.index.commit("initial")

    monkeypatch.setattr(
        "app.modules.knowledge_base.git.validate_clone_remote_url",
        lambda _remote_url: str(source_root),
    )
    monkeypatch.setattr(
        "app.modules.knowledge_base.git.user_git_environment",
        lambda *_args, **_kwargs: nullcontext({}),
    )
    git_service.db.commit.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        git_service.clone(
            actor=OWNER_ACTOR,
            kb_id=kb.id,
            payload=KnowledgeBaseGitCloneRequest(
                remoteUrl="https://example.invalid/docs.git"
            ),
        )

    root = git_service.storage_root / kb.id
    assert list(root.iterdir()) == []
    git_service.db.rollback.assert_called_once()


@pytest.mark.unit
def test_git_operation_requires_enabled_kb(git_service):
    with pytest.raises(ValueError, match=KB_VERSION_CONTROL_DISABLED):
        git_service.get_version_control_status(actor=OWNER_ACTOR, kb_id="kb-1")


@pytest.mark.unit
def test_update_lfs_patterns_writes_gitattributes(git_service, kb):
    _enable_existing_repo(git_service, kb)

    git_service.update_lfs_patterns(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        patterns=["raw/**/*.pdf", "raw/**/*.png"],
    )

    attributes = (git_service.storage_root / kb.id / ".gitattributes").read_text(
        encoding="utf-8"
    )
    assert "raw/**/*.pdf filter=lfs diff=lfs merge=lfs -text" in attributes
    assert "raw/**/*.png filter=lfs diff=lfs merge=lfs -text" in attributes
    assert not hasattr(kb, "git_lfs_enabled")

    changes = git_service.get_file_changes(actor=OWNER_ACTOR, kb_id="kb-1")
    assert [item.path for item in changes.staged.items] == [".gitattributes"]


@pytest.mark.unit
def test_changes_stage_unstage_discard_and_commit(git_service, kb):
    repo = _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "notes" / "index.md"
    target.write_text("# Index\n\nNew line\n", encoding="utf-8")
    new_page = root / "notes" / "new.md"
    new_page.write_text("# New\n", encoding="utf-8")

    changes = git_service.get_file_changes(actor=OWNER_ACTOR, kb_id="kb-1")
    assert [item.path for item in changes.unstaged.items] == ["notes/index.md"]
    assert [item.path for item in changes.untracked.items] == ["notes/new.md"]
    assert changes.unstaged.items[0].additions == 2
    assert changes.unstaged.items[0].deletions == 0
    assert changes.conflicts.items == []

    staged = git_service.stage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=StageRequest(paths=["notes/index.md", "notes/new.md"]),
    )
    assert staged.staged == ["notes/index.md", "notes/new.md"]

    status = git_service.get_version_control_status(actor=OWNER_ACTOR, kb_id="kb-1")
    assert status.stagedTotal == 2
    assert status.untrackedTotal == 0
    changes = git_service.get_file_changes(actor=OWNER_ACTOR, kb_id="kb-1")
    staged_by_path = {item.path: item for item in changes.staged.items}
    assert staged_by_path["notes/index.md"].additions == 2
    assert staged_by_path["notes/index.md"].deletions == 0

    unstaged = git_service.unstage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=UnstageRequest(paths=["notes/new.md"]),
    )
    assert unstaged.unstaged == ["notes/new.md"]
    assert unstaged.remainingStaged == 0

    discarded = git_service.discard(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=DiscardRequest(paths=["notes/new.md"]),
    )
    assert discarded.discarded == ["notes/new.md"]
    assert not new_page.exists()

    response = git_service.commit(
        actor=OWNER_ACTOR, kb_id="kb-1", message="Update index"
    )
    assert response.commit.message == "Update index"
    assert repo.head.commit.hexsha == response.commit.id

    history = git_service.list_commits(actor=OWNER_ACTOR, kb_id="kb-1")
    assert history.total == 2
    assert [item.message for item in history.items] == ["Update index", "initial"]


@pytest.mark.unit
def test_stage_and_unstage_all_changes(git_service, kb):
    _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "notes" / "index.md"
    target.write_text("# Index\n\nNew line\n", encoding="utf-8")
    new_page = root / "notes" / "all.md"
    new_page.write_text("# All\n", encoding="utf-8")

    staged = git_service.stage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=StageRequest(all=True),
    )
    assert staged.staged == []
    assert staged.unstaged == []

    status = git_service.get_version_control_status(actor=OWNER_ACTOR, kb_id="kb-1")
    assert status.stagedTotal == 2
    assert status.untrackedTotal == 0

    unstaged = git_service.unstage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=UnstageRequest(all=True),
    )
    assert unstaged.unstaged == []
    assert unstaged.remainingStaged == 0

    status = git_service.get_version_control_status(actor=OWNER_ACTOR, kb_id="kb-1")
    assert status.stagedTotal == 0
    assert status.unstagedTotal == 1
    assert status.untrackedTotal == 1


@pytest.mark.unit
def test_commit_preserves_untracked_files(git_service, kb):
    _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    (root / "notes" / "index.md").write_text("# Index\n\nCommitted\n", encoding="utf-8")
    (root / "notes" / "untracked.md").write_text("# Untracked\n", encoding="utf-8")
    git_service.stage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=StageRequest(paths=["notes/index.md"]),
    )

    response = git_service.commit(
        actor=OWNER_ACTOR, kb_id="kb-1", message="Commit staged file"
    )

    assert response.commit.message == "Commit staged file"
    assert (root / "notes" / "untracked.md").exists()


@pytest.mark.unit
def test_file_changes_preserves_rename_old_path_from_shared_status_adapter(
    git_service, kb
):
    repo = _enable_existing_repo(git_service, kb)
    repo.git.mv("notes/index.md", "notes/renamed.md")

    changes = git_service.get_file_changes(actor=OWNER_ACTOR, kb_id="kb-1")

    assert [
        (item.path, item.oldPath, item.status, item.type)
        for item in changes.staged.items
    ] == [("notes/renamed.md", "notes/index.md", "R", "renamed")]


@pytest.mark.unit
def test_file_changes_reports_conflicts_without_duplicate_regular_changes(
    git_service, kb
):
    repo = _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    _create_notes_conflict(repo, root)

    changes = git_service.get_file_changes(actor=OWNER_ACTOR, kb_id="kb-1")

    assert [(item.path, item.status, item.type) for item in changes.conflicts.items] == [
        ("notes/index.md", "UU", "unmerged")
    ]
    assert [item.path for item in changes.staged.items] == []
    assert [item.path for item in changes.unstaged.items] == []
    assert [item.path for item in changes.untracked.items] == []

    status = git_service.get_version_control_status(actor=OWNER_ACTOR, kb_id="kb-1")
    assert status.hasConflicts is True
    assert status.stagedTotal == 0
    assert status.unstagedTotal == 0
    assert status.untrackedTotal == 0


@pytest.mark.unit
def test_diff_blob_and_branch_workflow(git_service, kb):
    repo = _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "notes" / "index.md"
    initial_commit = repo.head.commit.hexsha
    target.write_text("# Index\n\nNext\n", encoding="utf-8")
    git_service.stage(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=StageRequest(paths=["notes/index.md"]),
    )
    updated = git_service.commit(
        actor=OWNER_ACTOR, kb_id="kb-1", message="Update index"
    )

    files = git_service.get_commit_files(
        actor=OWNER_ACTOR, kb_id="kb-1", commit_id=updated.commit.id
    )
    assert [item.path for item in files.files] == ["notes/index.md"]

    blob = git_service.blob(
        actor=OWNER_ACTOR, kb_id="kb-1", path="notes/index.md", revision=initial_commit
    )
    assert blob.content == "# Index\n"

    diff = git_service.diff(actor=OWNER_ACTOR, kb_id="kb-1", path="notes/index.md")
    assert diff.patch == ""

    checkout = git_service.create_branch_and_switch(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        name="draft",
        start_point="HEAD",
        upstream=None,
    )
    assert checkout.branch == "draft"
    branches = git_service.list_branches(actor=OWNER_ACTOR, kb_id="kb-1")
    assert {branch.name for branch in branches.branches} >= {"main", "draft"}

@pytest.mark.unit
def test_get_commit_files_reports_raw_utf8_paths_for_non_ascii_filenames(
    git_service, kb
):
    # Git's default core.quotepath=true wraps non-ASCII filenames in double
    # quotes with C-style octal escapes (e.g. "\346\224\271...") in porcelain
    # output that isn't NUL-terminated or otherwise quotepath-disabled. That
    # mangled string is unusable as a path for a later blob() lookup.
    repo = _enable_existing_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "測試檔案.md"
    target.write_text("test content\n", encoding="utf-8")
    repo.index.add(["測試檔案.md"])
    commit = repo.index.commit("add test file")

    files = git_service.get_commit_files(
        actor=OWNER_ACTOR, kb_id="kb-1", commit_id=commit.hexsha
    )

    assert [item.path for item in files.files] == ["測試檔案.md"]

    blob = git_service.blob(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path=files.files[0].path,
        revision=commit.hexsha,
    )
    assert blob.content == "test content\n"


@pytest.mark.unit
def test_rejects_paths_outside_repository(git_service, kb):
    _enable_existing_repo(git_service, kb)

    with pytest.raises(ValueError, match="GIT_PATH_OUTSIDE_REPOSITORY"):
        git_service.stage(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            payload=StageRequest(paths=["../escape.md"]),
        )


@pytest.mark.unit
def test_scoped_kb_git_mutations_do_not_use_gitpython_execution_api():
    scoped_methods = [
        KnowledgeBaseGitService.stage,
        KnowledgeBaseGitService.unstage,
        KnowledgeBaseGitService.discard,
        KnowledgeBaseGitService.commit,
        KnowledgeBaseGitService.list_commits,
        KnowledgeBaseGitService.create_branch_and_switch,
        KnowledgeBaseGitService.switch_branch,
        KnowledgeBaseGitService.rename_branch,
        KnowledgeBaseGitService.delete_branch,
        KnowledgeBaseGitService.publish_branch,
        KnowledgeBaseGitService.set_remote_url,
        KnowledgeBaseGitService.fetch,
        KnowledgeBaseGitService.pull,
        KnowledgeBaseGitService.push,
        KnowledgeBaseGitService._commit_staged,
    ]
    forbidden = [
        ".index.",
        ".git.",
        ".remote(",
        ".remotes",
        "iter_commits",
    ]

    violations = []
    for method in scoped_methods:
        source = inspect.getsource(method)
        violations.extend(
            f"{method.__name__}: {pattern}"
            for pattern in forbidden
            if pattern in source
        )

    assert violations == []


@pytest.mark.unit
def test_kb_git_service_uses_shared_runner_for_scoped_git_paths():
    source = Path("app/modules/knowledge_base/git.py").read_text(encoding="utf-8")
    forbidden = [
        "from git import",
        "import git",
        "Repo(",
        ".index.",
        ".remote(",
        ".remotes",
        ".git.",
        "iter_commits",
        "unmerged_blobs",
        "subprocess.run",
    ]

    assert [pattern for pattern in forbidden if pattern in source] == []


@pytest.mark.unit
def test_run_operation_maps_stale_lock_error_to_stale_conflict(
    git_service, monkeypatch
):
    """A stale Git lock maps to the shared version-control error contract."""
    captured = {}

    def fake_runner(*args, **kwargs):
        captured["repo_root"] = kwargs["repo_root"]
        captured["threshold"] = kwargs["stale_threshold_seconds"]
        raise GitStaleLockError("stale on-disk lock")

    monkeypatch.setattr(
        "app.modules.knowledge_base.git.run_operation",
        fake_runner,
    )

    with pytest.raises(VersionControlError) as exc_info:
        git_service._run_operation(
            kb_id="kb-1",
            kind=OperationKind.WRITE,
            operation_name="stage",
            callback=lambda: None,
        )

    assert exc_info.value.error_code == KB_GIT_OPERATION_IN_PROGRESS
    assert exc_info.value.blocking_scope is LockScope.COMMON_REPOSITORY
    assert exc_info.value.stale is True
    assert exc_info.value.can_force_unlock is True


@pytest.mark.unit
def test_run_operation_maps_acquire_collision_to_non_stale_conflict(
    git_service, monkeypatch
):
    """An acquire() collision (GitOperationInProgressError) maps to a non-stale conflict."""
    from app.modules.knowledge_base.git import KB_GIT_OPERATION_MANAGER

    def boom(*_args, **_kwargs):
        raise GitOperationInProgressError("already running")

    monkeypatch.setattr(KB_GIT_OPERATION_MANAGER, "acquire", boom)

    with pytest.raises(VersionControlError) as exc_info:
        git_service._run_operation(
            kb_id="kb-1",
            kind=OperationKind.WRITE,
            operation_name="stage",
            callback=lambda: None,
        )

    assert exc_info.value.error_code == KB_GIT_OPERATION_IN_PROGRESS
    assert exc_info.value.blocking_scope is LockScope.COMMON_REPOSITORY
    assert exc_info.value.stale is False
    assert exc_info.value.can_force_unlock is False


@pytest.mark.unit
def test_run_operation_resolves_repo_root_internally(git_service, monkeypatch):
    """repo_root is resolved internally via _kb_root; the recovery wrapper receives that path."""
    expected_root = git_service.storage_root / "kb-1"
    received = {}

    def spy_runner(*args, **kwargs):
        received["repo_root"] = kwargs["repo_root"]
        return "done"

    monkeypatch.setattr(git_service, "_kb_root", lambda kb_id: expected_root)
    monkeypatch.setattr(
        "app.modules.knowledge_base.git.run_operation",
        spy_runner,
    )

    result = git_service._run_operation(
        kb_id="kb-1",
        kind=OperationKind.WRITE,
        operation_name="commit",
        callback=lambda: "unused",
    )

    assert result == "done"
    assert received["repo_root"] == expected_root


@pytest.mark.unit
def test_get_operation_status_idle_when_no_active_operation(git_service):
    """get_operation_status reports inactive when no mutating op is in flight."""
    # Ensure no leftover operation is registered for this key.
    from app.modules.knowledge_base.git import KB_GIT_OPERATION_MANAGER
    from app.modules.knowledge_base.git_operations import kb_git_operation_key

    assert (
        KB_GIT_OPERATION_MANAGER.active_operation(kb_git_operation_key("kb-1")) is None
    )

    result = git_service.get_operation_status(actor=OWNER_ACTOR, kb_id="kb-1")

    assert result.isActive is False
    assert result.operation is None
    assert result.startedAt is None


@pytest.mark.unit
def test_get_operation_status_active_reports_in_flight_operation(git_service):
    """get_operation_status reports the active op name/kind/start while held."""
    from app.modules.knowledge_base.git import KB_GIT_OPERATION_MANAGER
    from app.modules.knowledge_base.git_operations import kb_git_operation_key

    with KB_GIT_OPERATION_MANAGER.acquire(
        kb_git_operation_key("kb-1"),
        OperationKind.WRITE,
        operation_name="commit",
    ):
        result = git_service.get_operation_status(actor=OWNER_ACTOR, kb_id="kb-1")

    assert result.isActive is True
    assert result.operation == "commit"
    assert result.startedAt  # ISO8601 string populated by the manager
