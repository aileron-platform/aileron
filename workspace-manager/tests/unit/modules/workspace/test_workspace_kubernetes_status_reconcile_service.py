"""Kubernetes Workspace status reconciliation unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceStatusSnapshot,
)
from app.modules.workspace.kubernetes_status import (
    WorkspaceKubernetesStatusReconcileService,
)


def _session_with_candidates(workspace_ids: list[str]) -> MagicMock:
    db = MagicMock(spec=Session)
    db.scalars.return_value.all.return_value = workspace_ids
    return db


def _snapshot(workspace_id: str) -> WorkspaceCustomResourceStatusSnapshot:
    return WorkspaceCustomResourceStatusSnapshot(
        workspace_id=workspace_id,
        resource_name=f"workspace-{workspace_id}",
        namespace="workspace-system",
        custom_resource={},
    )


def test_reconcile_batch_closes_candidate_session_before_kubernetes_io() -> None:
    candidate_db = _session_with_candidates(["workspace-1", "workspace-2"])
    workspace_1_db = MagicMock(spec=Session)
    workspace_2_db = MagicMock(spec=Session)
    sessions = iter([candidate_db, workspace_1_db, workspace_2_db])
    candidate_closed = False

    def mark_candidate_closed() -> None:
        nonlocal candidate_closed
        candidate_closed = True

    candidate_db.close.side_effect = mark_candidate_closed
    workspace_1_service = MagicMock()
    workspace_2_service = MagicMock()

    def fetch_workspace_1(workspace_id: str):
        assert candidate_closed is True
        return _snapshot(workspace_id)

    workspace_1_service.fetch_workspace_status_snapshot.side_effect = fetch_workspace_1
    workspace_1_service.apply_workspace_status_snapshot.return_value = True
    workspace_2_service.fetch_workspace_status_snapshot.return_value = _snapshot(
        "workspace-2"
    )
    workspace_2_service.apply_workspace_status_snapshot.return_value = False

    with patch(
        "app.modules.workspace.kubernetes_status.WorkspaceCustomResourceService",
        side_effect=[workspace_1_service, workspace_2_service],
    ):
        result = WorkspaceKubernetesStatusReconcileService(
            session_factory=lambda: next(sessions),
        ).reconcile_batch(limit=25)

    assert result == {
        "candidates": 2,
        "observed": 1,
        "skipped": 1,
        "not_found": 0,
        "failed": 0,
    }
    candidate_db.close.assert_called_once()
    workspace_1_db.close.assert_called_once()
    workspace_2_db.close.assert_called_once()


def test_reconcile_batch_isolates_missing_resources_and_failures() -> None:
    candidate_db = _session_with_candidates(["workspace-1", "workspace-2"])
    workspace_1_db = MagicMock(spec=Session)
    workspace_2_db = MagicMock(spec=Session)
    sessions = iter([candidate_db, workspace_1_db, workspace_2_db])
    workspace_1_service = MagicMock()
    workspace_1_service.fetch_workspace_status_snapshot.return_value = None
    workspace_2_service = MagicMock()
    workspace_2_service.fetch_workspace_status_snapshot.side_effect = RuntimeError(
        "Kubernetes API unavailable"
    )

    with patch(
        "app.modules.workspace.kubernetes_status.WorkspaceCustomResourceService",
        side_effect=[workspace_1_service, workspace_2_service],
    ):
        result = WorkspaceKubernetesStatusReconcileService(
            session_factory=lambda: next(sessions),
        ).reconcile_batch(limit=25)

    assert result == {
        "candidates": 2,
        "observed": 0,
        "skipped": 0,
        "not_found": 1,
        "failed": 1,
    }
    workspace_1_db.rollback.assert_not_called()
    workspace_2_db.rollback.assert_called_once()
    workspace_1_db.close.assert_called_once()
    workspace_2_db.close.assert_called_once()
