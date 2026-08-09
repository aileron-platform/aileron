from __future__ import annotations

from unittest.mock import MagicMock

from aileron_git_core import OperationManager

from app.modules.file_system.operations import FileService
from app.modules.version_control.working_tree_operations import WorkingTreeOperations


def test_write_file_invalidates_workspace_git_cache(tmp_path):
    invalidator = MagicMock()
    service = FileService(
        root_path=tmp_path,
        workspace_id="ws-1",
        working_tree_operations=WorkingTreeOperations(OperationManager(), invalidator),
    )

    result = service.write_file("README.md", "# Updated\n")

    assert result["path"] == "README.md"
    invalidator.invalidate_operation.assert_called_once_with("ws-1", "file_write")


def test_write_file_without_workspace_id_does_not_invalidate_git_cache(tmp_path):
    invalidator = MagicMock()
    service = FileService(
        root_path=tmp_path,
        working_tree_operations=WorkingTreeOperations(OperationManager(), invalidator),
    )

    service.write_file("README.md", "# Updated\n")

    invalidator.invalidate_operation.assert_not_called()
