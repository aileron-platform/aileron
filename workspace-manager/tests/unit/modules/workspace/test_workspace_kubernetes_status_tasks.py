"""Kubernetes Workspace status task unit tests."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import app.modules.workspace.tasks as tasks


def test_reconcile_kubernetes_workspace_status_uses_configured_batch_size() -> None:
    expected = {
        "candidates": 1,
        "observed": 1,
        "skipped": 0,
        "not_found": 0,
        "failed": 0,
    }

    with (
        patch.object(
            tasks,
            "get_settings",
            return_value=SimpleNamespace(
                KUBERNETES_STATUS_RECONCILIATION_BATCH_SIZE=37
            ),
        ),
        patch.object(
            tasks,
            "WorkspaceKubernetesStatusReconcileService",
        ) as service_type,
        patch.object(
            tasks,
            "task_lease",
            return_value=nullcontext(True),
        ),
    ):
        service_type.return_value.reconcile_batch.return_value = expected
        result = tasks.reconcile_kubernetes_workspace_status.run()

    assert result == {**expected, "overlap_skipped": 0}
    service_type.return_value.reconcile_batch.assert_called_once_with(limit=37)


def test_reconcile_kubernetes_workspace_status_skips_overlapping_scan() -> None:
    with (
        patch.object(
            tasks,
            "get_settings",
            return_value=SimpleNamespace(
                KUBERNETES_STATUS_RECONCILIATION_BATCH_SIZE=37
            ),
        ),
        patch.object(
            tasks,
            "WorkspaceKubernetesStatusReconcileService",
        ) as service_type,
        patch.object(
            tasks,
            "task_lease",
            return_value=nullcontext(False),
        ),
    ):
        result = tasks.reconcile_kubernetes_workspace_status.run()

    assert result == {
        "candidates": 0,
        "observed": 0,
        "skipped": 0,
        "not_found": 0,
        "failed": 0,
        "overlap_skipped": 1,
    }
    service_type.assert_not_called()
