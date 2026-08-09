"""Focused regressions for realtime fencing cleanup order."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from product_conformance import scenarios_realtime


class ForcedTerminationScenarioTest(unittest.IsolatedAsyncioTestCase):
    async def test_operator_pause_wraps_service_failure_injection(self) -> None:
        events: list[str] = []
        cluster = Mock()

        def scale_operator(replicas: int) -> dict[str, int | str]:
            events.append(f"operator:{replicas}")
            return {
                "name": "workspace-operator",
                "previousReplicas": 2 if replicas == 0 else 0,
                "replicas": replicas,
            }

        service_snapshot = object()
        cluster.operator_replicas.side_effect = (
            lambda: events.append("operator-snapshot") or 2
        )
        cluster.scale_operator.side_effect = scale_operator
        cluster.patch_terminal_target_port.side_effect = lambda workspace_id, port: (
            events.append(f"service-patch:{workspace_id}:{port}") or service_snapshot
        )
        cluster.restore_service.side_effect = lambda snapshot: events.append(
            "service-restore"
        )
        terminal = Mock()
        terminal.close = AsyncMock(side_effect=lambda: events.append("terminal-close"))
        context = SimpleNamespace(
            workspace_id="workspace-id",
            cluster=cluster,
            runtime_instance_id="runtime-old",
        )
        previous = {"runtimeInstanceId": "runtime-old"}
        current = {"runtimeInstanceId": "runtime-new"}
        drain_counts = {"acknowledged": 1, "failed": 1}

        async def wait_job(*args, **kwargs):
            events.append("wait-job")
            return {"id": "access-job"}

        async def wait_generation(*args, **kwargs):
            events.append("wait-generation")
            return current

        with patch.multiple(
            scenarios_realtime,
            _removable_actor=Mock(return_value=("reader", "share-id")),
            _terminal_grant=Mock(return_value="reader-token"),
            _get_generation=AsyncMock(return_value=previous),
            _open_terminal=AsyncMock(return_value=terminal),
            _assert_live=AsyncMock(),
            _issue_pairing_assertion=AsyncMock(
                return_value={
                    "assertion": "old-pairing",
                    "runtimeInstanceId": "runtime-old",
                }
            ),
            _manager_logs=AsyncMock(
                side_effect=[
                    ["before"],
                    ["before", "acknowledged", "failed"],
                ]
            ),
            _latest_job=AsyncMock(return_value=None),
            _request_owner=AsyncMock(
                return_value=SimpleNamespace(status_code=204, text="")
            ),
            _wait_drain_log_count=AsyncMock(
                return_value=(
                    ["before", "acknowledged", "failed"],
                    drain_counts,
                )
            ),
            _wait_new_job_succeeded=AsyncMock(side_effect=wait_job),
            _wait_new_generation=AsyncMock(side_effect=wait_generation),
            _wait_closed=AsyncMock(return_value={"code": 1012}),
            _assert_exact_drain_counts=Mock(return_value=drain_counts),
        ):
            evidence = await scenarios_realtime.run_forced_termination_proof(context)

        self.assertEqual(
            events,
            [
                "operator-snapshot",
                "operator:0",
                "service-patch:workspace-id:65534",
                "service-restore",
                "operator:2",
                "wait-job",
                "wait-generation",
                "terminal-close",
            ],
        )
        pause_evidence = next(
            item for item in evidence if "temporarily paused" in item.assertion
        )
        self.assertTrue(pause_evidence.observed["serviceRestoredBeforeOperator"])
        self.assertEqual(
            pause_evidence.observed["restore"]["replicas"],
            2,
        )

    async def test_cleanup_attempts_operator_and_terminal_when_service_restore_fails(
        self,
    ) -> None:
        events: list[str] = []
        cluster = Mock()

        def scale_operator(replicas: int) -> dict[str, int | str]:
            events.append(f"operator:{replicas}")
            if replicas == 1:
                raise RuntimeError("Operator restore failed")
            return {
                "name": "workspace-operator",
                "previousReplicas": 1 if replicas == 0 else 0,
                "replicas": replicas,
            }

        cluster.operator_replicas.side_effect = (
            lambda: events.append("operator-snapshot") or 1
        )
        cluster.scale_operator.side_effect = scale_operator
        cluster.patch_terminal_target_port.side_effect = lambda workspace_id, port: (
            events.append(f"service-patch:{workspace_id}:{port}") or object()
        )

        def fail_restore(snapshot: object) -> None:
            events.append("service-restore")
            raise RuntimeError("Service restore failed")

        cluster.restore_service.side_effect = fail_restore
        terminal = Mock()
        terminal.close = AsyncMock(side_effect=lambda: events.append("terminal-close"))
        context = SimpleNamespace(
            workspace_id="workspace-id",
            cluster=cluster,
        )

        with patch.multiple(
            scenarios_realtime,
            _removable_actor=Mock(return_value=("reader", "share-id")),
            _terminal_grant=Mock(return_value="reader-token"),
            _get_generation=AsyncMock(
                return_value={"runtimeInstanceId": "runtime-old"}
            ),
            _open_terminal=AsyncMock(return_value=terminal),
            _assert_live=AsyncMock(),
            _issue_pairing_assertion=AsyncMock(
                return_value={
                    "assertion": "old-pairing",
                    "runtimeInstanceId": "runtime-old",
                }
            ),
            _manager_logs=AsyncMock(return_value=["before"]),
            _latest_job=AsyncMock(return_value=None),
            _request_owner=AsyncMock(
                return_value=SimpleNamespace(status_code=204, text="")
            ),
            _wait_drain_log_count=AsyncMock(
                side_effect=AssertionError("drain evidence failed")
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Operator restore failed"):
                await scenarios_realtime.run_forced_termination_proof(context)

        self.assertEqual(
            events,
            [
                "operator-snapshot",
                "operator:0",
                "service-patch:workspace-id:65534",
                "service-restore",
                "operator:1",
                "terminal-close",
            ],
        )

    async def test_invalid_pause_result_still_restores_operator(self) -> None:
        events: list[str] = []
        cluster = Mock()
        cluster.operator_replicas.side_effect = (
            lambda: events.append("operator-snapshot") or 1
        )

        def scale_operator(replicas: int) -> dict[str, int | str]:
            events.append(f"operator:{replicas}")
            if replicas == 0:
                return {
                    "name": "workspace-operator",
                    "previousReplicas": 99,
                    "replicas": 0,
                }
            return {
                "name": "workspace-operator",
                "previousReplicas": 0,
                "replicas": replicas,
            }

        cluster.scale_operator.side_effect = scale_operator
        terminal = Mock()
        terminal.close = AsyncMock(side_effect=lambda: events.append("terminal-close"))
        context = SimpleNamespace(
            workspace_id="workspace-id",
            cluster=cluster,
        )

        with patch.multiple(
            scenarios_realtime,
            _removable_actor=Mock(return_value=("reader", "share-id")),
            _terminal_grant=Mock(return_value="reader-token"),
            _get_generation=AsyncMock(
                return_value={"runtimeInstanceId": "runtime-old"}
            ),
            _open_terminal=AsyncMock(return_value=terminal),
            _assert_live=AsyncMock(),
            _issue_pairing_assertion=AsyncMock(
                return_value={
                    "assertion": "old-pairing",
                    "runtimeInstanceId": "runtime-old",
                }
            ),
            _manager_logs=AsyncMock(return_value=["before"]),
        ):
            with self.assertRaisesRegex(
                AssertionError,
                "invalid scale result",
            ):
                await scenarios_realtime.run_forced_termination_proof(context)

        self.assertEqual(
            events,
            [
                "operator-snapshot",
                "operator:0",
                "operator:1",
                "terminal-close",
            ],
        )
        cluster.patch_terminal_target_port.assert_not_called()
        cluster.restore_service.assert_not_called()

    async def test_terminal_patch_failure_still_restores_operator(self) -> None:
        events: list[str] = []
        cluster = Mock()
        cluster.operator_replicas.side_effect = (
            lambda: events.append("operator-snapshot") or 1
        )

        def scale_operator(replicas: int) -> dict[str, int | str]:
            events.append(f"operator:{replicas}")
            return {
                "name": "workspace-operator",
                "previousReplicas": 1 if replicas == 0 else 0,
                "replicas": replicas,
            }

        cluster.scale_operator.side_effect = scale_operator

        def fail_patch(workspace_id: str, port: int) -> None:
            events.append(f"service-patch:{workspace_id}:{port}")
            raise RuntimeError("Terminal Service patch failed")

        cluster.patch_terminal_target_port.side_effect = fail_patch
        terminal = Mock()
        terminal.close = AsyncMock(side_effect=lambda: events.append("terminal-close"))
        context = SimpleNamespace(
            workspace_id="workspace-id",
            cluster=cluster,
        )

        with patch.multiple(
            scenarios_realtime,
            _removable_actor=Mock(return_value=("reader", "share-id")),
            _terminal_grant=Mock(return_value="reader-token"),
            _get_generation=AsyncMock(
                return_value={"runtimeInstanceId": "runtime-old"}
            ),
            _open_terminal=AsyncMock(return_value=terminal),
            _assert_live=AsyncMock(),
            _issue_pairing_assertion=AsyncMock(
                return_value={
                    "assertion": "old-pairing",
                    "runtimeInstanceId": "runtime-old",
                }
            ),
            _manager_logs=AsyncMock(return_value=["before"]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Terminal Service patch failed",
            ):
                await scenarios_realtime.run_forced_termination_proof(context)

        self.assertEqual(
            events,
            [
                "operator-snapshot",
                "operator:0",
                "service-patch:workspace-id:65534",
                "operator:1",
                "terminal-close",
            ],
        )
        cluster.restore_service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
