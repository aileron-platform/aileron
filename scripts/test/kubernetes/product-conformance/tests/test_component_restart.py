"""Unit tests for component-scoped restart invariants."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock

from product_conformance.component_restart import (
    assert_component_recreation,
    assert_component_restart,
    component_snapshot,
)


def _snapshot() -> dict[str, object]:
    return {
        "runtimeInstanceId": "runtime-instance-1",
        "podUids": {
            "runtime": "runtime-pod-1",
            "browser": "browser-pod-1",
            "canvas": "canvas-pod-1",
        },
        "revisions": {
            component: {
                "dbDesired": 1,
                "dbObserved": 1,
                "crDesired": 1,
                "crObserved": 1,
            }
            for component in ("runtime", "browser", "canvas")
        },
    }


def _restarted(component: str) -> tuple[dict[str, object], dict[str, object]]:
    before = _snapshot()
    after = copy.deepcopy(before)
    after["podUids"][component] = f"{component}-pod-2"  # type: ignore[index]
    revisions = after["revisions"][component]  # type: ignore[index]
    for key in revisions:
        revisions[key] = 2
    if component == "runtime":
        after["runtimeInstanceId"] = "runtime-instance-2"
    return before, after


class ComponentRestartInvariantTest(unittest.TestCase):
    def test_runtime_pod_recreation_keeps_instance_and_revisions(self) -> None:
        before = _snapshot()
        after = copy.deepcopy(before)
        after["podUids"]["runtime"] = "runtime-pod-2"  # type: ignore[index]

        assert_component_recreation(before, after, "runtime")

    def test_pod_recreation_rejects_revision_change(self) -> None:
        before = _snapshot()
        after = copy.deepcopy(before)
        after["podUids"]["runtime"] = "runtime-pod-2"  # type: ignore[index]
        after["revisions"]["runtime"]["dbDesired"] = 2  # type: ignore[index]

        with self.assertRaisesRegex(AssertionError, "revisions changed"):
            assert_component_recreation(before, after, "runtime")

    def test_runtime_restart_changes_only_runtime(self) -> None:
        before, after = _restarted("runtime")

        assert_component_restart(before, after, "runtime")

    def test_browser_restart_changes_only_browser(self) -> None:
        before, after = _restarted("browser")

        assert_component_restart(before, after, "browser")

    def test_canvas_restart_changes_only_canvas(self) -> None:
        before, after = _restarted("canvas")

        assert_component_restart(before, after, "canvas")

    def test_restart_rejects_sibling_identity_change(self) -> None:
        before, after = _restarted("runtime")
        after["podUids"]["browser"] = "browser-pod-2"  # type: ignore[index]

        with self.assertRaisesRegex(AssertionError, "browser Pod identity"):
            assert_component_restart(before, after, "runtime")

    def test_restart_rejects_sibling_revision_change(self) -> None:
        before, after = _restarted("browser")
        revisions = after["revisions"]["canvas"]  # type: ignore[index]
        for key in revisions:
            revisions[key] = 2

        with self.assertRaisesRegex(AssertionError, "canvas revisions"):
            assert_component_restart(before, after, "browser")


class ComponentSnapshotTest(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_ready_generation_before_reading_fences(self) -> None:
        context = Mock()
        context.workspace_id = "workspace-id"
        context.cluster.get_generation.return_value = {
            "runtimeInstanceId": "runtime-instance-1",
            "podUids": {
                "runtime": "runtime-pod-1",
                "browser": "browser-pod-1",
                "canvas": "canvas-pod-1",
            },
            "componentRevisions": {
                component: {"desired": 1, "observed": 1}
                for component in ("runtime", "browser", "canvas")
            },
        }
        context.cluster.get_ready_component_pod_uids.return_value = {
            "runtime": "runtime-pod-1",
            "browser": "browser-pod-1",
            "canvas": "canvas-pod-1",
        }
        context.db.get_workspace.return_value = {
            f"{component}_{fence}_revision": 1
            for component in ("runtime", "browser", "canvas")
            for fence in ("desired", "observed")
        }
        context.db.get_workspace.return_value["runtime_instance_id"] = (
            "runtime-instance-1"
        )
        context.db.get_workspace.return_value["runtime_status"] = "running"
        context.db.get_workspace.return_value["knowledge_base_mount_sync_status"] = (
            "ready"
        )
        context.db.list_jobs.return_value = []
        calls: list[str] = []
        context.cluster.wait_workspace_ready.side_effect = (
            lambda *args, **kwargs: calls.append("ready")
        )
        context.cluster.get_generation.side_effect = lambda *args: (
            calls.append("generation")
            or context.cluster.get_generation.return_value
        )
        context.cluster.get_ready_component_pod_uids.side_effect = lambda *args: (
            calls.append("pods")
            or context.cluster.get_ready_component_pod_uids.return_value
        )

        snapshot = await component_snapshot(context)

        self.assertEqual(
            calls,
            ["ready", "generation", "pods"] * 3,
        )
        context.cluster.wait_workspace_ready.assert_called_with(
            "workspace-id",
            timeout_seconds=2,
        )
        self.assertEqual(context.cluster.wait_workspace_ready.call_count, 3)
        self.assertEqual(snapshot["runtimeInstanceId"], "runtime-instance-1")

    async def test_rejects_stale_cr_status_before_physical_pods_are_ready(self) -> None:
        context = Mock()
        context.workspace_id = "workspace-id"
        context.cluster.get_generation.return_value = {
            "runtimeInstanceId": "runtime-instance-1",
            "podUids": {
                "runtime": "stale-runtime-pod",
                "browser": "browser-pod-1",
                "canvas": "canvas-pod-1",
            },
            "componentRevisions": {
                component: {"desired": 1, "observed": 1}
                for component in ("runtime", "browser", "canvas")
            },
        }
        context.cluster.get_ready_component_pod_uids.return_value = {
            "runtime": "new-runtime-pod",
            "browser": "browser-pod-1",
            "canvas": "canvas-pod-1",
        }
        context.db.get_workspace.return_value = {
            f"{component}_{fence}_revision": 1
            for component in ("runtime", "browser", "canvas")
            for fence in ("desired", "observed")
        }
        context.db.get_workspace.return_value["runtime_instance_id"] = (
            "runtime-instance-1"
        )
        context.db.get_workspace.return_value["runtime_status"] = "running"
        context.db.get_workspace.return_value["knowledge_base_mount_sync_status"] = (
            "ready"
        )
        context.db.list_jobs.return_value = []

        with self.assertRaisesRegex(AssertionError, "physical Ready Pod identities"):
            await component_snapshot(context, timeout_seconds=0)

    async def test_retries_until_database_instance_matches_and_jobs_are_idle(self) -> None:
        context = Mock()
        context.workspace_id = "workspace-id"
        context.cluster.get_generation.return_value = {
            "runtimeInstanceId": "runtime-instance-2",
            "podUids": {
                "runtime": "runtime-pod-2",
                "browser": "browser-pod-1",
                "canvas": "canvas-pod-1",
            },
            "componentRevisions": {
                component: {"desired": 2, "observed": 2}
                for component in ("runtime", "browser", "canvas")
            },
        }
        context.cluster.get_ready_component_pod_uids.return_value = {
            "runtime": "runtime-pod-2",
            "browser": "browser-pod-1",
            "canvas": "canvas-pod-1",
        }
        revisions = {
            f"{component}_{fence}_revision": 2
            for component in ("runtime", "browser", "canvas")
            for fence in ("desired", "observed")
        }
        context.db.get_workspace.side_effect = [
            {
                "runtime_instance_id": "runtime-instance-1",
                "runtime_status": "running",
                "knowledge_base_mount_sync_status": "ready",
                **revisions,
            },
            *[
                {
                    "runtime_instance_id": "runtime-instance-2",
                    "runtime_status": "running",
                    "knowledge_base_mount_sync_status": "ready",
                    **revisions,
                }
                for _ in range(4)
            ],
        ]
        context.db.list_jobs.side_effect = [
            [],
            [{"id": "active-job", "status": "running"}],
            [],
            [],
            [],
        ]

        snapshot = await component_snapshot(
            context,
            timeout_seconds=1,
            poll_interval_seconds=0,
        )

        self.assertEqual(snapshot["runtimeInstanceId"], "runtime-instance-2")
        self.assertEqual(context.db.get_workspace.call_count, 5)


if __name__ == "__main__":
    unittest.main()
