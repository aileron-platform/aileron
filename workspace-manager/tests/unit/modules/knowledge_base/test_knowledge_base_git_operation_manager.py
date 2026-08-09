"""Knowledge base Git operation manager integration tests."""

from __future__ import annotations

import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from aileron_git_core import OperationKind, OperationManager, VersionControlError
from aileron_git_core.testkit import Repo
from fastapi import HTTPException

from app.core.file_management import (
    FileConflictExecutionRequest,
    FileConflictSource,
    FileExtractExecutionRequest,
)
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.knowledge_base import git as kb_git_service_module
from app.modules.knowledge_base import (
    git_operations as kb_git_operation_manager_module,
)
from app.modules.knowledge_base.archive import KnowledgeBaseArchiveService
from app.modules.knowledge_base.files import KnowledgeBaseFileService
from app.modules.knowledge_base.git import KnowledgeBaseGitService
from app.modules.knowledge_base.git_operations import kb_git_operation_key
from app.modules.knowledge_base.router import _raise_kb_error
from app.modules.knowledge_base.sources import KnowledgeBaseSourceService
from app.modules.version_control.models import StageRequest

ACTOR = AuthorizationActor(user_id="owner-1", platform_role="member")


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.scalar = MagicMock(return_value=0)
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def kb_git_operation_manager(monkeypatch):
    manager = OperationManager()
    monkeypatch.setattr(
        kb_git_operation_manager_module, "KB_GIT_OPERATION_MANAGER", manager
    )
    monkeypatch.setattr(kb_git_service_module, "KB_GIT_OPERATION_MANAGER", manager)
    return manager


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
        version_control_enabled=True,
    )


@pytest.fixture
def git_service(mock_db_session, kb, tmp_path, kb_git_operation_manager):
    service = KnowledgeBaseGitService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    return service


@pytest.fixture
def file_service(mock_db_session, kb, tmp_path, kb_git_operation_manager):
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 100
    service.settings.DEFAULT_KB_QUOTA_BYTES = 1000
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 1000
    return service


@pytest.fixture
def source_service(mock_db_session, kb, tmp_path, kb_git_operation_manager):
    service = KnowledgeBaseSourceService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_ALLOWED_EXTENSIONS = [".md", ".txt", ".png"]
    service.settings.DEFAULT_KB_QUOTA_BYTES = 1000
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 1000
    mock_db_session.get.return_value = kb
    return service


@pytest.fixture
def archive_service(mock_db_session, kb, tmp_path, kb_git_operation_manager):
    service = KnowledgeBaseArchiveService(mock_db_session)
    service.file_service.storage_root = tmp_path
    service.file_service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = kb
    return service


def _enable_repo(service: KnowledgeBaseGitService, kb: db_models.KnowledgeBase) -> Repo:
    root = service.storage_root / kb.id
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


@pytest.mark.unit
def test_stage_is_rejected_during_active_blocking_operation_without_repo_mutation(
    git_service,
    kb,
    kb_git_operation_manager,
):
    repo = _enable_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    (root / "notes" / "new.md").write_text("# New\n", encoding="utf-8")

    def stage_file() -> None:
        git_service.stage(
            actor=ACTOR,
            kb_id=kb.id,
            payload=StageRequest(paths=["notes/new.md"]),
        )

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="checkout_branch",
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(VersionControlError) as exc_info:
                executor.submit(stage_file).result(timeout=1)

    assert exc_info.value.error_code == "operation_locked"

    assert repo.git.diff("--cached", "--name-only") == ""
    assert repo.untracked_files == ["notes/new.md"]


@pytest.mark.unit
def test_operation_lock_releases_after_operation_failure(
    git_service, kb, kb_git_operation_manager
):
    _enable_repo(git_service, kb)

    def fail_operation():
        raise RuntimeError("stage failed")

    with pytest.raises(RuntimeError, match="stage failed"):
        git_service._run_operation(
            kb_id=kb.id,
            kind=OperationKind.WRITE,
            operation_name="stage",
            callback=fail_operation,
        )

    assert (
        kb_git_operation_manager.active_operation(kb_git_operation_key(kb.id)) is None
    )
    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id), OperationKind.WRITE, operation_name="stage"
    ):
        assert (
            kb_git_operation_manager.active_operation(kb_git_operation_key(kb.id))
            is not None
        )


@pytest.mark.unit
def test_cancel_requests_active_cancellable_operation_without_read_lock(
    git_service,
    kb,
    kb_git_operation_manager,
):
    _enable_repo(git_service, kb)

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="lfs.snapshot.convert",
        cancellable=True,
    ):
        response = git_service.cancel_operation(actor=ACTOR, kb_id=kb.id)
        active = kb_git_operation_manager.active_operation(kb_git_operation_key(kb.id))

        assert response.command_id == "operation.cancel"
        assert active is not None
        assert active.cancel_requested is True


@pytest.mark.unit
def test_file_write_is_rejected_during_working_tree_operation_and_keeps_file_unchanged(
    file_service,
    kb,
    kb_git_operation_manager,
):
    target = file_service.storage_root / kb.id / "notes/index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("current", encoding="utf-8")

    def write_file() -> None:
        file_service.write_file(
            actor=ACTOR,
            kb_id=kb.id,
            path="notes/index.md",
            content="new",
        )

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="pull",
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(ValueError, match="KB_GIT_OPERATION_IN_PROGRESS"):
                executor.submit(write_file).result(timeout=1)

    assert target.read_text(encoding="utf-8") == "current"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("operation_name", "call"),
    [
        (
            "create_entry",
            lambda service, kb: service.create_entry(
                actor=ACTOR,
                kb_id=kb.id,
                path="notes/new.md",
                entry_type="file",
                content="new",
            ),
        ),
        (
            "delete_entry",
            lambda service, kb: service.delete_entry(
                actor=ACTOR,
                kb_id=kb.id,
                path="notes/index.md",
            ),
        ),
        (
            "move_entry",
            lambda service, kb: service.move_entry(
                actor=ACTOR,
                kb_id=kb.id,
                source_path="notes/index.md",
                dest_path="notes/moved.md",
            ),
        ),
        (
            "paste_entries",
            lambda service, kb: service.paste_entries(
                actor=ACTOR,
                kb_id=kb.id,
                payload=FileConflictExecutionRequest(
                    targetPath="notes/copies",
                    sources=[
                        FileConflictSource(
                            sourcePath="notes/index.md", entryType="file"
                        )
                    ],
                    defaultStrategy="cancel",
                    resolutions=[],
                ),
            ),
        ),
    ],
)
def test_file_mutation_is_rejected_during_working_tree_operation(
    file_service,
    kb,
    kb_git_operation_manager,
    operation_name,
    call,
):
    target = file_service.storage_root / kb.id / "notes/index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("current", encoding="utf-8")

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="pull",
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(ValueError, match="KB_GIT_OPERATION_IN_PROGRESS"):
                executor.submit(call, file_service, kb).result(timeout=1)

    assert target.read_text(encoding="utf-8") == "current"


@pytest.mark.unit
def test_remote_operation_does_not_block_file_write(
    file_service, kb, kb_git_operation_manager
):
    target = file_service.storage_root / kb.id / "notes/index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("current", encoding="utf-8")

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.REMOTE,
        operation_name="fetch",
    ):
        result = file_service.write_file(
            actor=ACTOR,
            kb_id=kb.id,
            path="notes/index.md",
            content="new",
        )

    assert result["size"] == 3
    assert target.read_text(encoding="utf-8") == "new"


@pytest.mark.unit
def test_source_import_is_rejected_during_working_tree_operation(
    source_service,
    kb,
    tmp_path,
    kb_git_operation_manager,
):
    source = tmp_path / "source.md"
    source.write_text("# Source\n", encoding="utf-8")

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="pull",
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(ValueError, match="KB_GIT_OPERATION_IN_PROGRESS"):
                executor.submit(
                    source_service.import_file,
                    actor=ACTOR,
                    kb_id=kb.id,
                    source_file=source,
                ).result(timeout=1)

    assert not (source_service.storage_root / kb.id / "raw/sources/source.md").exists()


@pytest.mark.unit
def test_archive_extract_is_rejected_during_working_tree_operation(
    archive_service,
    kb,
    tmp_path,
    kb_git_operation_manager,
):
    archive_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extracted.md", "# Extracted\n")
    kb_root = archive_service.file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    stored_archive = kb_root / archive_path.name
    stored_archive.write_bytes(archive_path.read_bytes())

    with kb_git_operation_manager.acquire(
        kb_git_operation_key(kb.id),
        OperationKind.WORKING_TREE,
        operation_name="pull",
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(ValueError, match="KB_GIT_OPERATION_IN_PROGRESS"):
                executor.submit(
                    archive_service.file_service.extract_archive,
                    actor=ACTOR,
                    kb_id=kb.id,
                    payload=FileExtractExecutionRequest(
                        archivePath=archive_path.name,
                        targetPath="/notes",
                        defaultStrategy="replace",
                        resolutions=[],
                    ),
                ).result(timeout=1)

    assert not (
        archive_service.file_service.storage_root / kb.id / "notes/extracted.md"
    ).exists()


@pytest.mark.unit
def test_stage_allows_same_thread_reentrant_read_helper(git_service, kb):
    _enable_repo(git_service, kb)
    root = git_service.storage_root / kb.id
    target = root / "notes" / "index.md"
    target.write_text("# Index\n\nUpdated\n", encoding="utf-8")

    response = git_service.stage(
        actor=ACTOR,
        kb_id=kb.id,
        payload=StageRequest(paths=["notes/index.md"]),
    )

    assert response.staged == ["notes/index.md"]
    assert response.unstaged == []


@pytest.mark.unit
def test_operation_in_progress_maps_to_409_response():
    request = MagicMock()
    request.state.translate = lambda key, **params: key

    with pytest.raises(HTTPException) as exc:
        _raise_kb_error(request, ValueError("KB_GIT_OPERATION_IN_PROGRESS"))

    assert exc.value.status_code == 409
    assert exc.value.detail["errorCode"] == "KB_GIT_OPERATION_IN_PROGRESS"
    assert exc.value.detail["message"] == "knowledge_base.git.operation_in_progress"
