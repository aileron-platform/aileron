import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aileron_git_core import (
    GitOperationInProgressError,
    OperationKind,
    OperationManager,
)
from app.modules.file_system.base_operations import BaseFileService, FileSystemError
from app.modules.version_control.working_tree_operations import WorkingTreeOperations


class BarrierFileService(BaseFileService):
    def resolve_scope_path(self, scope: str | None, relative_path: str) -> Path:
        return self._root_path / relative_path

    def validate_scope(self, scope: str | None) -> bool:
        return True

    def is_readonly_scope(self, scope: str | None) -> bool:
        return False


def _operations(manager: OperationManager) -> WorkingTreeOperations:
    return WorkingTreeOperations(manager, MagicMock())


def test_write_file_rejects_when_working_tree_operation_is_active(tmp_path):
    manager = OperationManager()
    service = BarrierFileService(
        tmp_path, working_tree_operations=_operations(manager), workspace_id="ws-1"
    )
    (tmp_path / "note.txt").write_text("old", encoding="utf-8")
    started = threading.Event()
    release = threading.Event()

    def pull_operation() -> None:
        with manager.acquire(
            "workspace:ws-1:context:primary",
            OperationKind.WORKING_TREE,
            operation_name="pull",
        ):
            started.set()
            assert release.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pull_operation)
        assert started.wait(timeout=5)
        with pytest.raises(FileSystemError) as exc:
            service.write_file("note.txt", "new")
        release.set()
        future.result(timeout=5)

    assert exc.value.status_code == 409
    assert exc.value.error_code == "VC_OPERATION_IN_PROGRESS"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "old"


def test_write_file_allows_remote_operation(tmp_path):
    manager = OperationManager()
    service = BarrierFileService(
        tmp_path, working_tree_operations=_operations(manager), workspace_id="ws-1"
    )
    (tmp_path / "note.txt").write_text("old", encoding="utf-8")

    with manager.acquire(
        "workspace:ws-1:context:primary",
        OperationKind.REMOTE,
        operation_name="fetch",
    ):
        service.write_file("note.txt", "new")

    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "new"


def test_file_write_barrier_blocks_working_tree_operation_until_write_finishes(
    tmp_path,
):
    manager = OperationManager()
    service = BarrierFileService(
        tmp_path, working_tree_operations=_operations(manager), workspace_id="ws-1"
    )

    def pull_operation() -> None:
        with manager.acquire(
            "workspace:ws-1:context:primary",
            OperationKind.WORKING_TREE,
            operation_name="pull",
        ):
            pass

    with service._git_file_write_barrier():
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(pull_operation).result(timeout=1)
