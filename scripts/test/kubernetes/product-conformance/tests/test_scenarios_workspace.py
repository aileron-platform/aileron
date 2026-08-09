"""Focused regressions for Workspace product conformance scenarios."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from product_conformance.scenarios_workspace import error_recovery


class WorkspaceScenarioTest(unittest.IsolatedAsyncioTestCase):
    async def test_error_recovery_uses_full_rebuild_and_proves_persistence(
        self,
    ) -> None:
        context = Mock()
        context.workspace_id = "workspace-id"
        context.cluster.scale_operator.side_effect = [
            {"name": "workspace-operator", "previousReplicas": 1},
            {"name": "workspace-operator", "previousReplicas": 0},
        ]
        context.db.wait_job.side_effect = [
            {"id": "failed-job", "error_code": "WORKSPACE_NOT_READY"},
            {"id": "recovery-job", "status": "succeeded"},
        ]
        context.db.wait_workspace.side_effect = [
            {"runtime_status": "error"},
            {
                "runtime_status": "running",
                "runtime_instance_id": "runtime-instance-new",
            },
        ]
        baseline = {
            "runtimeInstanceId": "runtime-instance-old",
            "podUids": {
                "runtime": "runtime-old",
                "browser": "browser-stable",
                "canvas": "canvas-stable",
            },
            "revisions": {
                "runtime": {"dbDesired": 1},
                "browser": {"dbDesired": 1},
                "canvas": {"dbDesired": 1},
            },
        }
        recovered = {
            "runtimeInstanceId": "runtime-instance-new",
            "podUids": {
                "runtime": "runtime-new",
                "browser": "browser-new",
                "canvas": "canvas-new",
            },
            "revisions": {
                "runtime": {"dbDesired": 2},
                "browser": {"dbDesired": 2},
                "canvas": {"dbDesired": 2},
            },
        }
        persistence = {
            "uids": {
                "workspaceCrUid": "workspace-cr-uid",
                "workspacePvcUid": "workspace-pvc-uid",
                "runtimeHomePvcUid": "runtime-home-pvc-uid",
            },
            "markers": {
                "workingTree": "working-tree-marker",
                "runtimeHome": "runtime-home-marker",
            },
        }

        with (
            patch(
                "product_conformance.scenarios_workspace.component_snapshot",
                new=AsyncMock(return_value=baseline),
            ),
            patch(
                "product_conformance.scenarios_workspace._wait_new_generation",
                new=AsyncMock(return_value=recovered),
            ) as wait_generation,
            patch(
                "product_conformance.scenarios_workspace._assert_workspace_persistence",
                return_value=persistence,
            ) as assert_persistence,
            patch(
                "product_conformance.scenarios_workspace._request_component_restart",
                return_value=(Mock(), "failed-job"),
            ),
            patch(
                "product_conformance.scenarios_workspace._request_full_rebuild",
                return_value=(Mock(), "recovery-job"),
            ),
        ):
            evidence = await error_recovery(context)

        wait_generation.assert_awaited_once_with(
            context,
            baseline,
        )
        assert_persistence.assert_called_once_with(
            context,
            operation="Workspace full rebuild",
        )
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[1].observed["after"], recovered)
        self.assertEqual(evidence[1].observed["persistence"], persistence)


if __name__ == "__main__":
    unittest.main()
