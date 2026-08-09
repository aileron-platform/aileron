"""Environment contracts for product conformance storage modes."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import httpx
from product_conformance.context import ProductConfig, ProductContext


class ProductConfigTest(unittest.TestCase):
    @staticmethod
    def _environment(storage_mode: str) -> dict[str, str]:
        return {
            "E2E_NAMESPACE": "workspace-e2e-run-1",
            "E2E_RUN_ID": "run-1",
            "E2E_STORAGE_MODE": storage_mode,
            "PRODUCT_MANAGER_URL": "http://manager:3001",
            "PRODUCT_OIDC_ADAPTER_URL": "https://oidc-fixture:8443",
            "PRODUCT_OIDC_ISSUER_URL": "https://oidc-fixture:8443",
            "PRODUCT_OIDC_CLIENT_ID": "aileron-manager",
            "PRODUCT_POSTGRES_DSN": "postgresql://postgres:postgres@postgres/aileron",
            "PRODUCT_DRIVER_IMAGE": "driver:test",
            "RWX_STORAGE_CLASS": "rwx-csi",
            "RUNTIME_IMAGE": "runtime:test",
            "BROWSER_IMAGE": "browser:test",
            "CANVAS_IMAGE": "canvas:test",
        }

    def test_dynamic_storage_does_not_resolve_an_nfs_server(self) -> None:
        environment = self._environment("dynamic")
        environment["NFS_SERVER"] = "must-not-be-used"
        environment["IMAGE_PULL_SECRET_NAME"] = "harbor-pull"

        with patch.dict(os.environ, environment, clear=True):
            settings = ProductConfig.from_environment()

        self.assertEqual(settings.storage_mode, "dynamic")
        self.assertIsNone(settings.nfs_server)
        self.assertEqual(settings.image_pull_secret_name, "harbor-pull")
        self.assertEqual(
            settings.oidc_discovery_url,
            "https://oidc-fixture:8443/.well-known/openid-configuration",
        )

    def test_static_nfs_requires_an_explicit_server(self) -> None:
        with (
            patch.dict(os.environ, self._environment("static-nfs"), clear=True),
            self.assertRaisesRegex(RuntimeError, "NFS_SERVER is required"),
        ):
            ProductConfig.from_environment()

    @staticmethod
    def _prerequisite_context() -> ProductContext:
        context = ProductContext.__new__(ProductContext)
        context.settings = SimpleNamespace(
            manager_url="http://manager:3001",
            namespace="test-ns",
        )
        context.http = Mock()
        context.http.get.return_value = httpx.Response(
            200,
            json={"status": "healthy"},
        )
        context.db = Mock()
        context.cluster = Mock()
        context._provision_test_actors = Mock()
        return context

    def test_prerequisites_preflight_discovery_v1_endpoint_slices(self) -> None:
        context = self._prerequisite_context()

        context.assert_prerequisites()

        context.cluster.list_endpoint_slices.assert_called_once_with(limit=1)
        context._provision_test_actors.assert_called_once_with()

    def test_prerequisites_propagate_endpoint_slice_preflight_failure(self) -> None:
        context = self._prerequisite_context()
        context.cluster.list_endpoint_slices.side_effect = RuntimeError(
            "EndpointSlice discovery denied"
        )

        with self.assertRaisesRegex(RuntimeError, "EndpointSlice discovery denied"):
            context.assert_prerequisites()

        context.cluster.wait_supervisor_processes.assert_not_called()
        context._provision_test_actors.assert_not_called()

    def test_refresh_generation_uses_nested_runtime_fence_projection(self) -> None:
        context = ProductContext.__new__(ProductContext)
        context.workspace_id = "workspace-id"
        context.runtime_instance_id = ""
        context.workspace_service_urls = {}
        context.cluster = Mock()
        context.cluster.get_generation.return_value = {
            "runtimeInstanceId": "10000000-0000-4000-8000-000000000002",
            "mountRevision": 4,
            "accessRevision": 3,
        }
        context.cluster.workspace_urls.return_value = {"runtime": "http://runtime:3002"}

        generation = context.refresh_generation()

        context.cluster.wait_workspace_ready.assert_called_once_with("workspace-id")
        context.cluster.get_generation.assert_called_once_with("workspace-id")
        self.assertEqual(
            context.runtime_instance_id,
            "10000000-0000-4000-8000-000000000002",
        )
        self.assertEqual(generation["mountRevision"], 4)
        self.assertEqual(
            context.workspace_service_urls,
            {"runtime": "http://runtime:3002"},
        )

    def test_manager_request_refreshes_an_expired_actor_session_once(self) -> None:
        context = ProductContext.__new__(ProductContext)
        context.manager = Mock()
        expired = httpx.Response(401)
        authenticated = httpx.Response(200)
        accepted = httpx.Response(202)
        context.manager.request.side_effect = [expired, authenticated, accepted]
        context.oidc_adapter = Mock()
        context.oidc_adapter.login.return_value = ("fresh-session", "fresh-csrf")
        context.sessions = {"owner": ("expired-session", "expired-csrf")}
        context.settings = SimpleNamespace(manager_url="http://manager:3001")
        context.users = {
            "owner": SimpleNamespace(username="owner", password="password")
        }

        response = context.request_owner("DELETE", "/workspaces/workspace-id")

        self.assertIs(response, accepted)
        context.oidc_adapter.login.assert_called_once_with(
            manager_url="http://manager:3001",
            username="owner",
        )
        self.assertEqual(context.sessions["owner"], ("fresh-session", "fresh-csrf"))
        self.assertEqual(
            context.manager.request.call_args_list,
            [
                call(
                    "owner",
                    "DELETE",
                    "/workspaces/workspace-id",
                ),
                call("owner", "GET", "/workspaces"),
                call(
                    "owner",
                    "DELETE",
                    "/workspaces/workspace-id",
                ),
            ],
        )

    def test_manager_request_does_not_refresh_a_non_authentication_failure(
        self,
    ) -> None:
        context = ProductContext.__new__(ProductContext)
        context.manager = Mock()
        conflict = httpx.Response(409)
        context.manager.request.return_value = conflict
        context.oidc_adapter = Mock()
        context.sessions = {"owner": ("current-session", "csrf")}
        context.users = {
            "owner": SimpleNamespace(username="owner", password="password")
        }

        response = context.request_owner("POST", "/workspaces")

        self.assertIs(response, conflict)
        context.oidc_adapter.login.assert_not_called()
        context.manager.request.assert_called_once_with(
            "owner",
            "POST",
            "/workspaces",
        )


if __name__ == "__main__":
    unittest.main()
