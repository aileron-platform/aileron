"""Focused regressions for Workspace product conformance scenarios."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from product_conformance.scenarios_workspace import (
    _expect_available_websocket,
    action_gate,
    error_recovery,
)


class WorkspaceScenarioTest(unittest.IsolatedAsyncioTestCase):
    async def test_available_websocket_uses_ping_without_waiting_for_app_data(
        self,
    ) -> None:
        pong = asyncio.get_running_loop().create_future()
        pong.set_result(None)
        connection = Mock()
        connection.ping = AsyncMock(return_value=pong)
        connection.close = AsyncMock()

        observed = await _expect_available_websocket(
            AsyncMock(return_value=connection)
        )

        self.assertEqual(observed, {"accepted": True})
        connection.ping.assert_awaited_once_with()
        connection.close.assert_awaited_once_with()

    async def test_action_gate_issues_grants_before_manager_outage(self) -> None:
        context = Mock()
        context.workspace_id = "workspace-id"
        context.settings.namespace = "test-namespace"
        context.settings.platform_public_origin = "https://platform.example.test"
        context.workspace_service_urls = {
            "runtime": "http://runtime:3002",
            "terminal": "http://runtime:3004",
        }
        context.cluster.manager_deployment_name = "workspace-manager"
        context.cluster.get_generation.return_value = {
            "runtimeInstanceId": "runtime-instance",
            "podUids": {
                "runtime": "runtime-pod",
                "browser": "browser-pod",
                "canvas": "canvas-pod",
            },
            "workspaceCrUid": "workspace-cr",
            "workspacePvcUid": "workspace-pvc",
            "runtimeHomePvcUid": "runtime-home-pvc",
        }

        def access_response(
            actor: str,
            _method: str,
            _path: str,
            **kwargs: object,
        ) -> Mock:
            action = kwargs["json"]["actions"][0]  # type: ignore[index]
            instance_id = kwargs["json"]["runtimeInstanceId"]  # type: ignore[index]
            response = Mock()
            if instance_id != "runtime-instance":
                response.status_code = 423
                response.json.return_value = {
                    "detail": {"errorCode": "WORKSPACE_RUNTIME_INSTANCE_MISMATCH"}
                }
            elif actor == "reader" and action != "runtime_read":
                response.status_code = 403
                response.json.return_value = {
                    "detail": {"errorCode": "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"}
                }
            else:
                response.status_code = 200
                response.json.return_value = {}
            response.text = ""
            return response

        context.request_actor.side_effect = access_response
        events: list[str] = []
        context.execution_grant.side_effect = lambda *args, **kwargs: (
            events.append("grant") or "signed-grant"
        )

        async def scale_manager(_context: object, replicas: int) -> dict[str, int]:
            events.append(f"scale:{replicas}")
            return {"previousReplicas": 1 if replicas == 0 else 0}

        with (
            patch(
                "product_conformance.scenarios_workspace.component_snapshot",
                new=AsyncMock(
                    return_value={
                        "runtimeInstanceId": "runtime-instance",
                        "podUids": {
                            "runtime": "runtime-pod",
                            "browser": "browser-pod",
                            "canvas": "canvas-pod",
                        },
                    }
                ),
            ),
            patch(
                "product_conformance.scenarios_workspace._scale_manager",
                side_effect=scale_manager,
            ),
            patch(
                "product_conformance.scenarios_workspace._expect_available_websocket",
                new=AsyncMock(return_value={"accepted": True}),
            ) as available_websocket,
        ):
            evidence = await action_gate(context)

        self.assertEqual(events[:3], ["grant", "grant", "scale:0"])
        self.assertEqual(events[-1], "scale:1")
        self.assertEqual(available_websocket.await_count, 3)
        self.assertEqual(len(evidence), 3)
        self.assertEqual(evidence[2].observed["terminal"], {"accepted": True})

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
