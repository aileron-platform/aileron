from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aileron_git_core import OperationKind, OperationManager

from app.modules.version_control.working_tree_operations import WorkingTreeOperations


def test_execute_owns_operation_lifecycle_and_cache_invalidation(
    tmp_path: Path,
) -> None:
    invalidator = MagicMock()
    operations = WorkingTreeOperations(OperationManager(), invalidator)

    result = operations.execute(
        workspace_id="ws-1",
        operation_key="workspace:ws-1:context:primary",
        kind=OperationKind.WRITE,
        operation_name="stage",
        repo_root=tmp_path,
        callback=lambda: "done",
        cache_effects=["status", "changes"],
        stale_threshold_seconds=35,
    )

    assert result == "done"
    invalidator.invalidate_effects.assert_called_once_with(
        "ws-1",
        ["status", "changes"],
    )


def test_execute_does_not_invalidate_cache_after_failed_mutation(
    tmp_path: Path,
) -> None:
    invalidator = MagicMock()
    operations = WorkingTreeOperations(OperationManager(), invalidator)

    with pytest.raises(RuntimeError, match="failed"):
        operations.execute(
            workspace_id="ws-1",
            operation_key="workspace:ws-1:context:primary",
            kind=OperationKind.WRITE,
            operation_name="stage",
            repo_root=tmp_path,
            callback=lambda: (_ for _ in ()).throw(RuntimeError("failed")),
            cache_effects=["status"],
            stale_threshold_seconds=35,
        )

    invalidator.invalidate_effects.assert_not_called()
