"""Unit tests for product conformance service adapters."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

import httpx
from product_conformance.api import (
    ExternalOidcFixtureClient,
    ManagerClient,
    require_status,
)
from product_conformance.cluster import (
    ProductCluster,
    RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT_PATH,
    RUNTIME_GID,
    RUNTIME_UID,
    _canonical_runtime_secret_name,
    _load_runtime_platform_environment_contract,
    _require_runtime_platform_environment,
)


def _valid_runtime_platform_environment():
    from kubernetes import client

    values_by_kind = {
        "non-empty-string": "workspace-123",
        "absolute-path": "/workspace",
        "canonical-uuid": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
        "non-negative-integer": "1",
        "safe-relative-path": ".worktrees",
        "secret-file-path": "/run/secrets/credential",
        "internal-http-url": "http://service:3001",
        "public-origin": "https://aileron.example.test",
        "file-path": "/run/config/jwks.json",
        "bounded-non-empty-string": "workspace-manager",
        "dns-service-name": "workspace-runtime",
    }
    contract = _load_runtime_platform_environment_contract()
    environment = {
        item["name"]: client.V1EnvVar(
            name=item["name"],
            value=values_by_kind[item["valueKind"]],
        )
        for item in contract
    }
    return contract, environment


class ManagerClientTest(unittest.TestCase):
    def test_request_uses_opaque_session_csrf_and_canonical_api_prefix(self) -> None:
        observed: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return httpx.Response(200, json={"ok": True})

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            manager = ManagerClient(
                http,
                base_url="http://manager:3001",
                public_origin="https://aileron.example.test",
                sessions={"owner": ("opaque-session", "csrf-token")},
            )
            response = manager.owner(
                "POST",
                "/workspaces",
                json={"name": "test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(observed[0].url), "http://manager:3001/api/v1/workspaces")
        self.assertEqual(
            observed[0].headers["Cookie"], "aileron_session=opaque-session"
        )
        self.assertEqual(observed[0].headers["X-CSRF-Token"], "csrf-token")
        self.assertEqual(
            observed[0].headers["Origin"], "https://aileron.example.test"
        )
        self.assertEqual(json.loads(observed[0].content), {"name": "test"})

    def test_request_does_not_duplicate_existing_api_prefix(self) -> None:
        observed: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(str(request.url))
            return httpx.Response(204)

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            manager = ManagerClient(
                http,
                base_url="http://manager:3001",
                public_origin="https://aileron.example.test",
                sessions={"owner": ("opaque-session", "csrf-token")},
            )
            manager.owner("GET", "/api/v1/workspaces/id/runtime-access")

        self.assertEqual(
            observed,
            ["http://manager:3001/api/v1/workspaces/id/runtime-access"],
        )

    def test_require_status_includes_bounded_response_context(self) -> None:
        response = httpx.Response(409, text="conflict")

        with self.assertRaisesRegex(AssertionError, "returned 409"):
            require_status(response, 202, operation="mutation")


class ExternalOidcFixtureClientTest(unittest.TestCase):
    def test_create_user_uses_provider_neutral_fixture_api(self) -> None:
        created_user: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/test/users":
                created_user.update(json.loads(request.content))
                return httpx.Response(201, json={"id": "user-id"})
            raise AssertionError(f"Unexpected external OIDC fixture request: {request}")

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            fixture = ExternalOidcFixtureClient(
                http,
                base_url="http://oidc-fixture",
                client_id="aileron-manager",
            )
            user = fixture.create_realm_user(
                username="e2e-owner",
                email="e2e-owner@example.test",
                password="ProductE2e123!",
                realm_role="admin",
            )

        self.assertEqual(user.id, "user-id")
        self.assertEqual(created_user["realm_role"], "admin")

    def test_login_reads_the_canonical_snake_case_csrf_field(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/test/next-login":
                return httpx.Response(204)
            if request.url.path == "/api/v1/oauth2/login":
                return httpx.Response(
                    302,
                    headers={"location": "http://oidc-fixture/authorize"},
                )
            if request.url.path == "/authorize":
                return httpx.Response(
                    302,
                    headers={
                        "location": (
                            "http://manager:3001/api/v1/oauth2/callback"
                            "?code=code-1&state=state-1"
                        )
                    },
                )
            if request.url.path == "/api/v1/oauth2/callback":
                return httpx.Response(
                    303,
                    headers={"set-cookie": "aileron_session=session-1; Path=/"},
                )
            if request.url.path == "/api/v1/oauth2/session":
                self.assertEqual(
                    request.headers["Cookie"],
                    "aileron_session=session-1",
                )
                return httpx.Response(200, json={"csrf_token": "csrf-1"})
            raise AssertionError(f"Unexpected login request: {request}")

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            fixture = ExternalOidcFixtureClient(
                http,
                base_url="http://oidc-fixture",
                client_id="aileron-manager",
            )

            session = fixture.login(
                manager_url="http://manager:3001",
                username="e2e-owner",
            )

        self.assertEqual(session, ("session-1", "csrf-1"))


class ProductClusterContractTest(unittest.TestCase):
    def test_runtime_platform_contract_is_packaged_at_the_runtime_path(self) -> None:
        self.assertEqual(
            "/opt/product-conformance/contracts/runtime-platform-environment.json",
            str(RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT_PATH),
        )
        contract = json.loads(
            RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(1, contract["schemaVersion"])

    def test_workspace_component_labels_match_operator_contract(self) -> None:
        self.assertEqual(
            {
                component: ProductCluster._workspace_component_label(component)
                for component in ("runtime", "browser", "canvas")
            },
            {
                "runtime": "workspace-runtime",
                "browser": "workspace-browser",
                "canvas": "workspace-canvas",
            },
        )
        with self.assertRaisesRegex(
            AssertionError,
            "Unsupported workspace component",
        ):
            ProductCluster._workspace_component_label("terminal")

    @staticmethod
    def _ready_workspace_resource() -> dict[str, object]:
        return {
            "metadata": {
                "generation": 7,
                "resourceVersion": "11",
                "uid": "workspace-cr-uid",
            },
            "spec": {
                "runtime": {
                    "instanceId": "10000000-0000-4000-8000-000000000002",
                    "revision": 5,
                    "mountRevision": 4,
                    "accessRevision": 3,
                },
                "browser": {"revision": 6},
                "canvas": {"revision": 7},
            },
            "status": {
                "phase": "Running",
                "observedGeneration": 7,
                "components": {
                    "runtime": {
                        "observedRevision": 5,
                        "mountObservedRevision": 4,
                        "accessObservedRevision": 3,
                        "ready": True,
                        "terminalReady": True,
                        "podUid": "runtime-uid",
                    },
                    "browser": {
                        "observedRevision": 6,
                        "ready": True,
                        "podUid": "browser-uid",
                    },
                    "canvas": {
                        "observedRevision": 7,
                        "ready": True,
                        "podUid": "canvas-uid",
                    },
                },
            },
        }

    def test_ready_requires_exact_generation_revisions_and_all_components(self) -> None:
        resource = self._ready_workspace_resource()

        self.assertTrue(ProductCluster._workspace_custom_resource_ready(resource))
        stale_paths = (
            ("status", "components", "runtime", "observedRevision"),
            ("status", "components", "runtime", "mountObservedRevision"),
            ("status", "components", "runtime", "accessObservedRevision"),
            ("status", "components", "browser", "observedRevision"),
            ("status", "components", "canvas", "observedRevision"),
        )
        for path in stale_paths:
            stale = copy.deepcopy(resource)
            target = stale
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = 0
            with self.subTest(path=path):
                self.assertFalse(ProductCluster._workspace_custom_resource_ready(stale))

        missing_instance = copy.deepcopy(resource)
        missing_instance["spec"]["runtime"]["instanceId"] = ""
        self.assertFalse(
            ProductCluster._workspace_custom_resource_ready(missing_instance)
        )

    @staticmethod
    def _stopped_workspace_resource() -> dict[str, object]:
        return {
            "metadata": {"generation": 8, "uid": "workspace-cr-uid"},
            "spec": {
                "runtime": {
                    "instanceId": "10000000-0000-4000-8000-000000000002",
                    "desiredState": "Stopped",
                },
                "browser": {"desiredState": "Stopped"},
                "canvas": {"desiredState": "Stopped"},
            },
            "status": {
                "phase": "Stopped",
                "observedGeneration": 8,
            },
        }

    def test_stopped_requires_retained_generation_and_all_desired_states(self) -> None:
        resource = self._stopped_workspace_resource()
        instance_id = "10000000-0000-4000-8000-000000000002"

        self.assertTrue(
            ProductCluster._workspace_custom_resource_stopped(
                resource,
                expected_runtime_instance_id=instance_id,
            )
        )
        invalid_paths = (
            ("metadata", "generation"),
            ("spec", "runtime", "instanceId"),
            ("spec", "runtime", "desiredState"),
            ("spec", "browser", "desiredState"),
            ("spec", "canvas", "desiredState"),
            ("status", "phase"),
            ("status", "observedGeneration"),
        )
        for path in invalid_paths:
            invalid = copy.deepcopy(resource)
            target = invalid
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "invalid"
            with self.subTest(path=path):
                self.assertFalse(
                    ProductCluster._workspace_custom_resource_stopped(
                        invalid,
                        expected_runtime_instance_id=instance_id,
                    )
                )

    def test_workspace_stopped_state_keeps_pvcs_and_removes_old_pods(self) -> None:
        from kubernetes import client

        workspace_id = "11111111-1111-4111-8111-111111111111"
        instance_id = "10000000-0000-4000-8000-000000000002"
        core = Mock()
        core.list_namespaced_pod.return_value.items = []
        core.read_namespaced_persistent_volume_claim.side_effect = (
            lambda name, namespace: client.V1PersistentVolumeClaim(
                metadata=client.V1ObjectMeta(
                    name=name,
                    namespace=namespace,
                    uid=(
                        "runtime-home-pvc-uid"
                        if "runtime-home" in name
                        else "workspace-pvc-uid"
                    ),
                )
            )
        )
        custom = Mock()
        custom.get_namespaced_custom_object.return_value = (
            self._stopped_workspace_resource()
        )
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=custom,
            discovery=Mock(),
        )

        state = cluster.workspace_stopped_state(
            workspace_id,
            expected_runtime_instance_id=instance_id,
            old_pod_uids={"runtime-old", "browser-old", "canvas-old"},
        )

        self.assertTrue(state["customResourcePresent"])
        self.assertTrue(state["customResourceStopped"])
        self.assertTrue(state["oldPodUidsAbsent"])
        self.assertEqual(state["workspaceCrUid"], "workspace-cr-uid")
        self.assertEqual(state["workspacePvcUid"], "workspace-pvc-uid")
        self.assertEqual(state["runtimeHomePvcUid"], "runtime-home-pvc-uid")
        self.assertEqual(state["podUids"], [])

    def test_get_generation_reads_nested_runtime_fence_and_observed_status(
        self,
    ) -> None:
        custom = Mock()
        custom.get_namespaced_custom_object.return_value = (
            self._ready_workspace_resource()
        )
        from kubernetes import client

        core = Mock()
        core.read_namespaced_persistent_volume_claim.side_effect = (
            lambda name, namespace: client.V1PersistentVolumeClaim(
                metadata=client.V1ObjectMeta(
                    name=name,
                    namespace=namespace,
                    uid=(
                        "runtime-home-pvc-uid"
                        if "runtime-home" in name
                        else "workspace-pvc-uid"
                    ),
                )
            )
        )
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=custom,
            discovery=Mock(),
        )

        generation = cluster.get_generation("workspace-id")

        self.assertEqual(
            generation,
            {
                "generation": 7,
                "workspaceCrUid": "workspace-cr-uid",
                "workspacePvcUid": "workspace-pvc-uid",
                "runtimeHomePvcUid": "runtime-home-pvc-uid",
                "runtimeInstanceId": "10000000-0000-4000-8000-000000000002",
                "resourceVersion": "11",
                "mountRevision": 4,
                "accessRevision": 3,
                "phase": "Running",
                "podUids": {
                    "runtime": "runtime-uid",
                    "browser": "browser-uid",
                    "canvas": "canvas-uid",
                },
                "componentRevisions": {
                    "runtime": {"desired": 5, "observed": 5},
                    "browser": {"desired": 6, "observed": 6},
                    "canvas": {"desired": 7, "observed": 7},
                },
            },
        )

    def test_workspace_absence_proves_cr_and_both_pvc_uids_are_gone(self) -> None:
        from kubernetes.client.rest import ApiException

        core = Mock()
        core.read_namespaced_persistent_volume_claim.side_effect = ApiException(
            status=404
        )
        core.list_namespaced_pod.return_value.items = []
        custom = Mock()
        custom.get_namespaced_custom_object.side_effect = ApiException(status=404)
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=custom,
            discovery=Mock(),
        )
        expected_uids = {
            "workspaceCrUid": "workspace-cr-uid",
            "workspacePvcUid": "workspace-pvc-uid",
            "runtimeHomePvcUid": "runtime-home-pvc-uid",
        }

        observed = cluster.wait_workspace_absent(
            "workspace-id",
            expected_uids=expected_uids,
            timeout_seconds=1,
        )

        self.assertEqual(observed["expectedUids"], expected_uids)
        self.assertEqual(
            observed["observedUids"],
            {
                "workspaceCrUid": None,
                "workspacePvcUid": None,
                "runtimeHomePvcUid": None,
            },
        )
        self.assertTrue(observed["workspaceCrAbsent"])
        self.assertTrue(observed["workspacePvcAbsent"])
        self.assertTrue(observed["runtimeHomePvcAbsent"])
        self.assertEqual(
            [
                call.args[0]
                for call in core.read_namespaced_persistent_volume_claim.call_args_list
            ],
            [
                "workspace-pvc-workspace-id",
                "workspace-runtime-home-pvc-workspace-id",
            ],
        )

    def test_workspace_storage_markers_cover_working_tree_and_runtime_home(
        self,
    ) -> None:
        from kubernetes import client

        workspace_id = "11111111-1111-4111-8111-111111111111"
        core = Mock()
        core.list_namespaced_pod.return_value.items = [
            client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name="workspace-runtime-pod",
                    uid="runtime-pod-uid",
                ),
                status=client.V1PodStatus(
                    conditions=[
                        client.V1PodCondition(
                            type="Ready",
                            status="True",
                        )
                    ]
                ),
            )
        ]
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        expected = {
            key: hashlib.sha256(f"run:{workspace_id}:{key}".encode("utf-8")).hexdigest()
            for key in ("workingTree", "runtimeHome")
        }

        with patch(
            "product_conformance.cluster.stream",
            side_effect=[
                "",
                f"{expected['workingTree']}\n{expected['runtimeHome']}\n",
            ],
        ) as exec_stream:
            observed = cluster.write_workspace_storage_markers(workspace_id)

        self.assertEqual(observed, expected)
        self.assertEqual(exec_stream.call_count, 2)
        write_command = exec_stream.call_args_list[0].kwargs["command"]
        read_command = exec_stream.call_args_list[1].kwargs["command"]
        self.assertIn("/workspace/.aileron-product-conformance", write_command)
        self.assertIn(
            "/home/developer/.aileron-product-conformance",
            write_command,
        )
        self.assertIn("/workspace/.aileron-product-conformance", read_command)
        self.assertIn(
            "/home/developer/.aileron-product-conformance",
            read_command,
        )

    def test_workspace_urls_route_cdp_through_runtime(self) -> None:
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )

        urls = cluster.workspace_urls("workspace-id")

        self.assertEqual(
            urls["terminal"],
            "http://workspace-runtime-workspace-id.test-ns.svc.cluster.local:3004",
        )
        self.assertEqual(
            urls["browserCdp"],
            "http://workspace-runtime-workspace-id.test-ns.svc.cluster.local:3002",
        )
        self.assertEqual(
            urls["browserNeko"],
            "http://workspace-browser-workspace-id.test-ns.svc.cluster.local:6080",
        )
        self.assertEqual(
            urls["browser"],
            "http://workspace-browser-workspace-id.test-ns.svc.cluster.local:9223",
        )
        self.assertEqual(
            urls["canvas"],
            "http://workspace-canvas-workspace-id.test-ns.svc.cluster.local:3003",
        )
        self.assertEqual(
            urls["canvasApi"],
            "http://workspace-canvas-workspace-id.test-ns.svc.cluster.local:3013",
        )

    def test_scale_operator_rejects_invalid_replica_counts(self) -> None:
        apps = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=apps,
            custom=Mock(),
            discovery=Mock(),
        )

        for replicas in (True, False, -1, 1.5, "1", None):
            with (
                self.subTest(replicas=replicas),
                self.assertRaisesRegex(
                    ValueError,
                    "non-negative integer",
                ),
            ):
                cluster.scale_operator(replicas)

        apps.read_namespaced_deployment.assert_not_called()
        apps.patch_namespaced_deployment_scale.assert_not_called()

    def test_scale_operator_to_zero_waits_for_selected_pod_objects_to_disappear(
        self,
    ) -> None:
        from kubernetes import client

        selector = client.V1LabelSelector(
            match_labels={
                "app.kubernetes.io/instance": "product",
                "app.kubernetes.io/component": "workspace-operator",
            },
            match_expressions=[
                client.V1LabelSelectorRequirement(
                    key="tier",
                    operator="NotIn",
                    values=["legacy", "batch"],
                ),
                client.V1LabelSelectorRequirement(
                    key="managed",
                    operator="Exists",
                    values=[],
                ),
            ],
        )
        before = Mock()
        before.spec.replicas = 1
        before.spec.selector = selector
        scaled = Mock()
        scaled.spec.replicas = 0
        scaled.metadata.generation = 7
        scaled.status.observed_generation = 7
        scaled.status.replicas = 0
        scaled.status.ready_replicas = 0
        scaled.status.available_replicas = 0

        apps = Mock()
        apps.read_namespaced_deployment.side_effect = [before, scaled]
        terminating_pod = Mock()
        terminating_pod.metadata.deletion_timestamp = "terminating"
        core = Mock()
        core.list_namespaced_pod.side_effect = [
            Mock(items=[terminating_pod]),
            Mock(items=[]),
        ]
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=apps,
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._operator_deployment_name = Mock(return_value="workspace-operator")
        wait_descriptions: list[str] = []

        def wait_until(read, predicate, *, description, **_):
            wait_descriptions.append(description)
            for _ in range(3):
                observed = read()
                if predicate(observed):
                    return observed
            raise AssertionError(f"Test wait did not converge: {description}")

        cluster._wait = wait_until  # type: ignore[method-assign]

        result = cluster.scale_operator(0)

        expected_selector = (
            "app.kubernetes.io/component=workspace-operator,"
            "app.kubernetes.io/instance=product,"
            "managed,tier notin (batch,legacy)"
        )
        self.assertEqual(
            wait_descriptions,
            [
                "Operator workspace-operator replicas=0",
                "Operator workspace-operator Pod objects absent",
            ],
        )
        self.assertEqual(core.list_namespaced_pod.call_count, 2)
        core.list_namespaced_pod.assert_has_calls(
            [
                unittest.mock.call(
                    "test-ns",
                    label_selector=expected_selector,
                ),
                unittest.mock.call(
                    "test-ns",
                    label_selector=expected_selector,
                ),
            ]
        )
        apps.patch_namespaced_deployment_scale.assert_called_once_with(
            "workspace-operator",
            "test-ns",
            {"spec": {"replicas": 0}},
        )
        self.assertEqual(
            result,
            {
                "name": "workspace-operator",
                "previousReplicas": 1,
                "replicas": 0,
            },
        )

    def test_scale_operator_up_waits_for_ready_and_available_replicas(
        self,
    ) -> None:
        before = Mock()
        before.spec.replicas = 0
        progressing = Mock()
        progressing.spec.replicas = 2
        progressing.metadata.generation = 8
        progressing.status.observed_generation = 8
        progressing.status.ready_replicas = 1
        progressing.status.available_replicas = 1
        ready = Mock()
        ready.spec.replicas = 2
        ready.metadata.generation = 8
        ready.status.observed_generation = 8
        ready.status.ready_replicas = 2
        ready.status.available_replicas = 2

        apps = Mock()
        apps.read_namespaced_deployment.side_effect = [
            before,
            progressing,
            ready,
        ]
        core = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=apps,
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._operator_deployment_name = Mock(return_value="workspace-operator")
        wait_descriptions: list[str] = []

        def wait_until(read, predicate, *, description, **_):
            wait_descriptions.append(description)
            for _ in range(3):
                observed = read()
                if predicate(observed):
                    return observed
            raise AssertionError(f"Test wait did not converge: {description}")

        cluster._wait = wait_until  # type: ignore[method-assign]

        result = cluster.scale_operator(2)

        self.assertEqual(
            wait_descriptions,
            ["Operator workspace-operator replicas=2"],
        )
        self.assertEqual(apps.read_namespaced_deployment.call_count, 3)
        core.list_namespaced_pod.assert_not_called()
        self.assertEqual(
            result,
            {
                "name": "workspace-operator",
                "previousReplicas": 0,
                "replicas": 2,
            },
        )

    def test_operator_replica_snapshot_requires_an_observed_integer(self) -> None:
        from kubernetes import client

        apps = Mock()
        apps.read_namespaced_deployment.return_value = client.V1Deployment(
            spec=client.V1DeploymentSpec(
                replicas=2,
                selector=client.V1LabelSelector(match_labels={"app": "operator"}),
                template=client.V1PodTemplateSpec(),
            )
        )
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=apps,
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._operator_deployment_name = Mock(return_value="workspace-operator")

        self.assertEqual(cluster.operator_replicas(), 2)
        apps.read_namespaced_deployment.assert_called_once_with(
            "workspace-operator",
            "test-ns",
        )

    def test_service_port_patch_body_uses_kubernetes_camel_case(self) -> None:
        from kubernetes import client

        body = ProductCluster._service_ports_body(
            [
                client.V1ServicePort(
                    app_protocol="http",
                    name="terminal",
                    node_port=32004,
                    port=3004,
                    protocol="TCP",
                    target_port=65534,
                )
            ]
        )

        self.assertEqual(
            body,
            [
                {
                    "appProtocol": "http",
                    "name": "terminal",
                    "nodePort": 32004,
                    "port": 3004,
                    "protocol": "TCP",
                    "targetPort": 65534,
                }
            ],
        )

    def test_terminal_failure_injection_waits_for_data_plane_convergence(
        self,
    ) -> None:
        from kubernetes import client

        original = client.V1Service(
            spec=client.V1ServiceSpec(
                ports=[
                    client.V1ServicePort(
                        name="runtime",
                        port=3002,
                        protocol="TCP",
                        target_port=3002,
                    ),
                    client.V1ServicePort(
                        name="terminal",
                        port=3004,
                        protocol="TCP",
                        target_port=3004,
                    ),
                ]
            )
        )
        patched = copy.deepcopy(original)
        patched.spec.ports[1].target_port = 65534
        core = Mock()
        core.read_namespaced_service.side_effect = [
            original,
            patched,
            original,
        ]
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        barriers = Mock()
        cluster._wait_for_endpoint_slice_port = barriers.endpoint_slice
        cluster._wait_for_manager_service_port_reachability = barriers.manager_dataplane

        snapshot = cluster.patch_terminal_target_port("workspace-id", 65534)
        cluster.restore_service(snapshot)

        self.assertEqual(snapshot.name, "workspace-runtime-workspace-id")
        self.assertEqual(snapshot.terminal_service_port, 3004)
        self.assertEqual(snapshot.terminal_target_port, 3004)
        self.assertEqual(
            barriers.mock_calls,
            [
                unittest.mock.call.endpoint_slice(
                    "workspace-runtime-workspace-id",
                    expected_port=65534,
                ),
                unittest.mock.call.manager_dataplane(
                    "workspace-runtime-workspace-id",
                    3004,
                    reachable=False,
                ),
                unittest.mock.call.endpoint_slice(
                    "workspace-runtime-workspace-id",
                    expected_port=3004,
                ),
                unittest.mock.call.manager_dataplane(
                    "workspace-runtime-workspace-id",
                    3004,
                    reachable=True,
                ),
            ],
        )

        barriers.reset_mock()
        core.read_namespaced_service.side_effect = [original]
        cluster.restore_service(snapshot, wait_for_ready=False)
        self.assertEqual(barriers.mock_calls, [])

    def test_terminal_failure_injection_rolls_back_when_barrier_fails(
        self,
    ) -> None:
        from kubernetes import client

        original = client.V1Service(
            spec=client.V1ServiceSpec(
                ports=[
                    client.V1ServicePort(
                        name="runtime",
                        port=3002,
                        protocol="TCP",
                        target_port=3002,
                    ),
                    client.V1ServicePort(
                        name="terminal",
                        port=3004,
                        protocol="TCP",
                        target_port=3004,
                    ),
                ]
            )
        )
        patched = copy.deepcopy(original)
        patched.spec.ports[1].target_port = 65534
        core = Mock()
        core.read_namespaced_service.side_effect = [
            original,
            patched,
            original,
        ]
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        barriers = Mock()
        barriers.manager_dataplane.side_effect = [
            AssertionError("injection data plane did not converge"),
            None,
        ]
        cluster._wait_for_endpoint_slice_port = barriers.endpoint_slice
        cluster._wait_for_manager_service_port_reachability = barriers.manager_dataplane

        with self.assertRaisesRegex(
            AssertionError,
            "injection data plane did not converge",
        ):
            cluster.patch_terminal_target_port("workspace-id", 65534)

        self.assertEqual(core.patch_namespaced_service.call_count, 2)
        restore_body = core.patch_namespaced_service.call_args_list[1].args[2]
        self.assertEqual(
            restore_body["spec"]["ports"][1]["targetPort"],
            3004,
        )
        self.assertEqual(
            barriers.mock_calls,
            [
                unittest.mock.call.endpoint_slice(
                    "workspace-runtime-workspace-id",
                    expected_port=65534,
                ),
                unittest.mock.call.manager_dataplane(
                    "workspace-runtime-workspace-id",
                    3004,
                    reachable=False,
                ),
                unittest.mock.call.endpoint_slice(
                    "workspace-runtime-workspace-id",
                    expected_port=3004,
                ),
                unittest.mock.call.manager_dataplane(
                    "workspace-runtime-workspace-id",
                    3004,
                    reachable=True,
                ),
            ],
        )

    def test_terminal_failure_injection_rolls_back_when_post_patch_read_fails(
        self,
    ) -> None:
        from kubernetes import client

        original = client.V1Service(
            spec=client.V1ServiceSpec(
                ports=[
                    client.V1ServicePort(
                        name="runtime",
                        port=3002,
                        protocol="TCP",
                        target_port=3002,
                    ),
                    client.V1ServicePort(
                        name="terminal",
                        port=3004,
                        protocol="TCP",
                        target_port=3004,
                    ),
                ]
            )
        )
        core = Mock()
        core.read_namespaced_service.side_effect = [
            original,
            RuntimeError("post-patch Service read failed"),
            original,
        ]
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        barriers = Mock()
        cluster._wait_for_endpoint_slice_port = barriers.endpoint_slice
        cluster._wait_for_manager_service_port_reachability = barriers.manager_dataplane

        with self.assertRaisesRegex(
            RuntimeError,
            "post-patch Service read failed",
        ):
            cluster.patch_terminal_target_port("workspace-id", 65534)

        self.assertEqual(core.patch_namespaced_service.call_count, 2)
        restore_body = core.patch_namespaced_service.call_args_list[1].args[2]
        self.assertEqual(
            restore_body["spec"]["ports"][1]["targetPort"],
            3004,
        )
        self.assertEqual(
            barriers.mock_calls,
            [
                unittest.mock.call.endpoint_slice(
                    "workspace-runtime-workspace-id",
                    expected_port=3004,
                ),
                unittest.mock.call.manager_dataplane(
                    "workspace-runtime-workspace-id",
                    3004,
                    reachable=True,
                ),
            ],
        )

    def test_endpoint_slice_convergence_uses_only_active_endpoints(self) -> None:
        def endpoint_slice(
            *,
            name: str,
            port: int,
            ready: bool | None,
            terminating: bool | None,
        ) -> dict[str, object]:
            return {
                "addressType": "IPv4",
                "metadata": {"name": name},
                "endpoints": [
                    {
                        "addresses": ["10.0.0.1"],
                        "conditions": {
                            "ready": ready,
                            "terminating": terminating,
                        },
                    }
                ],
                "ports": [
                    {
                        "name": "terminal",
                        "port": port,
                        "protocol": "TCP",
                    }
                ],
            }

        current = endpoint_slice(
            name="current",
            port=65534,
            ready=None,
            terminating=None,
        )
        terminating_stale = endpoint_slice(
            name="terminating-stale",
            port=3004,
            ready=True,
            terminating=True,
        )
        not_ready_stale = endpoint_slice(
            name="not-ready-stale",
            port=3004,
            ready=False,
            terminating=False,
        )
        empty_transitional = {
            "addressType": "IPv4",
            "metadata": {"name": "empty-transitional"},
            "endpoints": None,
            "ports": None,
        }
        active_without_ports = {
            **current,
            "metadata": {"name": "active-without-ports"},
            "ports": None,
        }
        ipv6_current = {
            **current,
            "addressType": "IPv6",
            "metadata": {"name": "ipv6-current"},
            "endpoints": [
                {
                    "addresses": ["2001:db8::1"],
                    "conditions": {
                        "ready": True,
                        "terminating": False,
                    },
                }
            ],
        }

        self.assertTrue(
            ProductCluster._endpoint_slices_have_terminal_port(
                [
                    current,
                    terminating_stale,
                    not_ready_stale,
                    empty_transitional,
                ],
                expected_port=65534,
            )
        )
        self.assertTrue(
            ProductCluster._endpoint_slices_have_terminal_port(
                [current, ipv6_current],
                expected_port=65534,
            )
        )
        self.assertFalse(
            ProductCluster._endpoint_slices_have_terminal_port(
                [
                    current,
                    endpoint_slice(
                        name="active-stale",
                        port=3004,
                        ready=True,
                        terminating=False,
                    ),
                ],
                expected_port=65534,
            )
        )
        self.assertFalse(
            ProductCluster._endpoint_slices_have_terminal_port(
                [active_without_ports],
                expected_port=65534,
            )
        )
        self.assertFalse(
            ProductCluster._endpoint_slices_have_terminal_port(
                [terminating_stale, not_ready_stale, empty_transitional],
                expected_port=65534,
            )
        )

    def test_endpoint_slice_raw_adapter_handles_null_transitional_slice(
        self,
    ) -> None:
        discovery = Mock()
        response = Mock()
        response.data = json.dumps(
            {
                "apiVersion": "discovery.k8s.io/v1",
                "kind": "EndpointSliceList",
                "items": [
                    {
                        "addressType": "IPv4",
                        "metadata": {"name": "empty-transitional"},
                        "endpoints": None,
                        "ports": None,
                    }
                ],
            }
        ).encode("utf-8")
        discovery.list_namespaced_endpoint_slice.return_value = response
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=Mock(),
            discovery=discovery,
        )

        observed = cluster.list_endpoint_slices(
            service_name="workspace-runtime-workspace-id"
        )

        self.assertEqual(observed[0]["endpoints"], None)
        self.assertEqual(observed[0]["ports"], None)
        self.assertFalse(
            ProductCluster._endpoint_slices_have_terminal_port(
                observed,
                expected_port=65534,
            )
        )
        discovery.list_namespaced_endpoint_slice.assert_called_once_with(
            "test-ns",
            _preload_content=False,
            _request_timeout=(5, 10),
            label_selector=(
                "kubernetes.io/service-name=workspace-runtime-workspace-id"
            ),
        )
        response.release_conn.assert_called_once_with()

    def test_endpoint_slice_raw_adapter_bounds_preflight_request(self) -> None:
        discovery = Mock()
        response = Mock(
            data=json.dumps(
                {
                    "apiVersion": "discovery.k8s.io/v1",
                    "kind": "EndpointSliceList",
                    "items": [],
                }
            ).encode("utf-8")
        )
        discovery.list_namespaced_endpoint_slice.return_value = response
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=Mock(),
            discovery=discovery,
        )

        observed = cluster.list_endpoint_slices(limit=1)

        self.assertEqual(observed, [])
        discovery.list_namespaced_endpoint_slice.assert_called_once_with(
            "test-ns",
            _preload_content=False,
            _request_timeout=(5, 10),
            limit=1,
        )
        response.release_conn.assert_called_once_with()

    def test_endpoint_slice_raw_adapter_validates_response_contract(self) -> None:
        discovery = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=Mock(),
            discovery=discovery,
        )
        invalid_payloads = (
            {"apiVersion": "v1", "items": []},
            {
                "apiVersion": "discovery.k8s.io/v1",
                "kind": "EndpointSlice",
                "items": [],
            },
            {
                "apiVersion": "discovery.k8s.io/v1",
                "kind": "EndpointSliceList",
                "items": None,
            },
        )

        for payload in invalid_payloads:
            response = Mock(data=json.dumps(payload).encode("utf-8"))
            discovery.list_namespaced_endpoint_slice.return_value = response
            with self.subTest(payload=payload), self.assertRaises(AssertionError):
                cluster.list_endpoint_slices(limit=1)
            response.release_conn.assert_called_once_with()

        invalid_json_response = Mock(data=b"{")
        discovery.list_namespaced_endpoint_slice.return_value = invalid_json_response
        with self.assertRaisesRegex(AssertionError, "not valid JSON"):
            cluster.list_endpoint_slices(limit=1)
        invalid_json_response.release_conn.assert_called_once_with()

    def test_manager_data_plane_probe_executes_from_manager_venv(self) -> None:
        from kubernetes import client

        core = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        cluster.manager_pod = Mock(
            return_value=client.V1Pod(metadata=client.V1ObjectMeta(name="manager-pod"))
        )
        with patch(
            "product_conformance.cluster.stream",
            return_value="reachable\n",
        ) as exec_stream:
            observed = cluster._manager_service_port_reachable(
                "workspace-runtime-workspace-id",
                3004,
            )

        self.assertTrue(observed)
        exec_stream.assert_called_once()
        args, kwargs = exec_stream.call_args
        self.assertIs(args[0], core.connect_get_namespaced_pod_exec)
        self.assertEqual(args[1:3], ("manager-pod", "test-ns"))
        self.assertEqual(
            kwargs["command"][0],
            "/workspace-manager/.venv/bin/python",
        )
        self.assertEqual(
            kwargs["command"][-2:],
            [
                "workspace-runtime-workspace-id.test-ns.svc.cluster.local",
                "3004",
            ],
        )
        self.assertEqual(kwargs["container"], "workspace-manager")

    def test_manager_data_plane_wait_requires_three_consecutive_results(
        self,
    ) -> None:
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._manager_service_port_reachable = Mock(
            side_effect=[True, False, False, False]
        )
        predicate_results: list[bool] = []

        def exhaust_observations(read, predicate, **kwargs):
            for _ in range(4):
                predicate_results.append(predicate(read()))
            return False

        cluster._wait = exhaust_observations  # type: ignore[method-assign]

        cluster._wait_for_manager_service_port_reachability(
            "workspace-runtime-workspace-id",
            3004,
            reachable=False,
        )

        self.assertEqual(predicate_results, [False, False, False, True])

    def test_runtime_platform_environment_contract_rejects_secret_key_ref(
        self,
    ) -> None:
        from kubernetes import client

        contract, environment = _valid_runtime_platform_environment()
        names = {item["name"] for item in contract}
        self.assertNotIn("MANAGER_URL", names)
        self.assertNotIn("BROWSER_CONTAINER_NAME", names)
        environment["AILERON_RUNTIME_DATABASE_CONNECTION_FILE"] = client.V1EnvVar(
            name="AILERON_RUNTIME_DATABASE_CONNECTION_FILE",
            value_from=client.V1EnvVarSource(
                secret_key_ref=client.V1SecretKeySelector(
                    name="workspace-runtime-secret",
                    key="runtime-database-connection",
                )
            ),
        )

        with self.assertRaisesRegex(AssertionError, "must be a literal value"):
            _require_runtime_platform_environment(environment)

    def test_runtime_platform_environment_contract_rejects_empty_worktree_and_invalid_ports(
        self,
    ) -> None:
        from kubernetes import client

        contract, environment = _valid_runtime_platform_environment()
        _require_runtime_platform_environment(environment)

        empty_worktree = dict(environment)
        empty_worktree["AILERON_WORKTREE_SUBDIR"] = client.V1EnvVar(
            name="AILERON_WORKTREE_SUBDIR",
            value="",
        )
        with self.assertRaisesRegex(AssertionError, "safe-relative-path"):
            _require_runtime_platform_environment(empty_worktree)

        for item in contract:
            if item.get("port") is None:
                continue
            for port in (0, 65536):
                with self.subTest(name=item["name"], port=port):
                    invalid_port = dict(environment)
                    scheme = "https" if item["valueKind"] == "public-origin" else "http"
                    invalid_port[item["name"]] = client.V1EnvVar(
                        name=item["name"],
                        value=f"{scheme}://service:{port}",
                    )
                    with self.assertRaisesRegex(
                        AssertionError,
                        "invalid port|allowed range",
                    ):
                        _require_runtime_platform_environment(invalid_port)

    def test_runtime_platform_environment_must_be_absent(self) -> None:
        from kubernetes import client

        environment = {
            "DATABASE_URL": client.V1EnvVar(
                name="DATABASE_URL",
                value="postgresql://must-not-reach-runtime",
            )
        }

        with self.assertRaisesRegex(
            AssertionError,
            "forbidden platform environment.*DATABASE_URL",
        ):
            ProductCluster._require_environment_absent(
                environment,
                names=("DATABASE_URL", "REDIS_URL", "INTERNAL_API_TOKEN"),
                component="Runtime Pod",
            )

    def test_runtime_secret_data_contract_is_exact_and_complete(self) -> None:
        from kubernetes import client

        valid_data = {
            "runtime-database-connection": "cnVudGltZS1kYXRhYmFzZS1jb25uZWN0aW9u",
            "runtime-control-token": "cnVudGltZS10b2tlbg==",
            "custom-setup.sh": "cHJpbnRmIGNvbmZpZ3VyZWQ=",
        }
        ProductCluster._require_runtime_secret_data_contract(
            client.V1Secret(type="Opaque", data=valid_data)
        )

        invalid_contracts = (
            client.V1Secret(
                type="Opaque",
                data={
                    key: value
                    for key, value in valid_data.items()
                    if key != "custom-setup.sh"
                },
            ),
            client.V1Secret(
                type="Opaque",
                data={**valid_data, "internal-api-token": "Zm9yYmlkZGVu"},
            ),
            client.V1Secret(
                type="Opaque",
                data={**valid_data, "custom-setup.sh": ""},
            ),
            client.V1Secret(type="kubernetes.io/basic-auth", data=valid_data),
        )
        for secret in invalid_contracts:
            with self.subTest(secret_type=secret.type, keys=sorted(secret.data or {})):
                with self.assertRaisesRegex(
                    AssertionError,
                    "invalid data contract",
                ):
                    ProductCluster._require_runtime_secret_data_contract(secret)

    def test_workspace_contract_rejects_an_unexpected_assertion_issuer(self) -> None:
        custom = Mock()
        custom.get_namespaced_custom_object.return_value = {
            "spec": {
                "worktreeSubdir": ".worktrees",
                "runtime": {
                    "image": "runtime:test",
                    "runtimeSecretName": _canonical_runtime_secret_name("workspace-id"),
                    "assertion": {
                        "issuer": "attacker-controlled-issuer",
                        "publicKeySetSecretName": "runtime-assertion-public-jwks",
                    },
                },
                "browser": {"image": "browser:test"},
                "canvas": {"image": "canvas:test"},
            }
        }
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=custom,
            discovery=Mock(),
        )

        with self.assertRaisesRegex(AssertionError, "runtime contract mismatch"):
            cluster.assert_workspace_runtime_contract(
                "workspace-id",
                runtime_image="runtime:test",
                browser_image="browser:test",
                canvas_image="canvas:test",
                manager_url="http://manager:3001",
                assertion_secret_name="runtime-assertion-public-jwks",
                knowledge_bases_pvc_name="product-knowledge-bases-pvc",
                image_pull_secret_name=None,
            )

    def test_workspace_contract_rejects_inline_control_credentials(self) -> None:
        custom = Mock()
        custom.get_namespaced_custom_object.return_value = {
            "spec": {
                "worktreeSubdir": ".worktrees",
                "runtime": {
                    "image": "runtime:test",
                    "runtimeSecretName": _canonical_runtime_secret_name("workspace-id"),
                    "controlAssertion": "must-not-be-in-the-cr",
                    "assertion": {
                        "issuer": "workspace-manager",
                        "publicKeySetSecretName": "runtime-assertion-public-jwks",
                    },
                },
                "browser": {"image": "browser:test"},
                "canvas": {"image": "canvas:test"},
            }
        }
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=Mock(),
            apps=Mock(),
            custom=custom,
            discovery=Mock(),
        )

        with self.assertRaisesRegex(AssertionError, "must not contain"):
            cluster.assert_workspace_runtime_contract(
                "workspace-id",
                runtime_image="runtime:test",
                browser_image="browser:test",
                canvas_image="canvas:test",
                manager_url="http://manager:3001",
                assertion_secret_name="runtime-assertion-public-jwks",
                knowledge_bases_pvc_name="product-knowledge-bases-pvc",
                image_pull_secret_name=None,
            )

    def test_required_image_pull_secret_must_be_present(self) -> None:
        from kubernetes import client

        with self.assertRaisesRegex(AssertionError, "harbor-pull"):
            ProductCluster._require_image_pull_secret(
                [client.V1LocalObjectReference(name="unrelated")],
                expected_name="harbor-pull",
                component="Runtime Pod",
            )

    def test_visual_component_must_not_reference_runtime_secret(self) -> None:
        from kubernetes import client

        pod_spec = client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="browser",
                    env=[
                        client.V1EnvVar(
                            name="RUNTIME_CONTROL_TOKEN",
                            value_from=client.V1EnvVarSource(
                                secret_key_ref=client.V1SecretKeySelector(
                                    name="workspace-runtime-secret",
                                    key="runtime-control-token",
                                )
                            ),
                        )
                    ],
                )
            ]
        )

        with self.assertRaisesRegex(AssertionError, "forbidden Secret"):
            ProductCluster._require_secret_not_referenced(
                pod_spec,
                secret_name="workspace-runtime-secret",
                component="Workspace browser Pod",
            )

    def test_manager_runtime_database_credential_mount_is_exact(self) -> None:
        from kubernetes import client

        pod_spec = client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="workspace-manager",
                    volume_mounts=[
                        client.V1VolumeMount(
                            name="manager-private-secrets",
                            mount_path="/run/secrets/aileron",
                            read_only=True,
                        )
                    ],
                )
            ],
            volumes=[
                client.V1Volume(
                    name="manager-private-secrets",
                    projected=client.V1ProjectedVolumeSource(
                        sources=[
                            client.V1VolumeProjection(
                                secret=client.V1SecretProjection(
                                    name="aileron-platform-secrets",
                                    items=[
                                        client.V1KeyToPath(
                                            key="runtime-database-credential-key",
                                            path="runtime-database-credential.key",
                                        )
                                    ],
                                )
                            )
                        ]
                    ),
                )
            ],
        )

        observed = ProductCluster._require_manager_credential_mount(
            pod_spec,
            secret_name="aileron-platform-secrets",
        )

        self.assertEqual(
            observed,
            {
                "secretName": "aileron-platform-secrets",
                "secretKey": "runtime-database-credential-key",
                "path": "/run/secrets/aileron/runtime-database-credential.key",
            },
        )

    def test_static_workspace_storage_inherits_source_nfs_mount_contract(
        self,
    ) -> None:
        from kubernetes import client

        core = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._delete_pod_if_exists = Mock()  # type: ignore[method-assign]
        def wait(read, _predicate, *, description: str, timeout_seconds: float):
            del timeout_seconds
            if description.startswith("Workspace PVC"):
                return read()
            return client.V1Pod(status=client.V1PodStatus(phase="Succeeded"))

        cluster._wait = Mock(side_effect=wait)  # type: ignore[method-assign]
        def pvc(name: str, _namespace: str):
            if name == "product-workspaces-root-pvc":
                return client.V1PersistentVolumeClaim(
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteMany"],
                        volume_name="product-workspaces-root-run",
                    ),
                    status=client.V1PersistentVolumeClaimStatus(phase="Bound"),
                )
            if name == "product-runtime-homes-root-pvc":
                return client.V1PersistentVolumeClaim(
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteMany"],
                        volume_name="product-runtime-homes-root-run",
                    ),
                    status=client.V1PersistentVolumeClaimStatus(phase="Bound"),
                )
            if name.startswith("workspace-runtime-home-pvc-"):
                return client.V1PersistentVolumeClaim(
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteOnce"],
                        resources=client.V1VolumeResourceRequirements(
                            requests={"storage": "2Gi"}
                        ),
                        storage_class_name="nfs-rwo",
                    )
                )
            return client.V1PersistentVolumeClaim(
                spec=client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteMany"],
                    resources=client.V1VolumeResourceRequirements(
                        requests={"storage": "1Gi"}
                    ),
                    storage_class_name="nfs-rwx",
                )
            )

        core.read_namespaced_persistent_volume_claim.side_effect = pvc
        inherited_mount_options = [
            "vers=4.1",
            "hard",
            "timeo=321",
            "retrans=7",
        ]
        def root_volume(name: str):
            path = "/runtime-homes" if "runtime-homes" in name else "/workspaces"
            return client.V1PersistentVolume(
                spec=client.V1PersistentVolumeSpec(
                    access_modes=["ReadWriteMany"],
                    capacity={"storage": "2Gi"},
                    mount_options=inherited_mount_options,
                    nfs=client.V1NFSVolumeSource(
                        path=path,
                        server="nfs-server",
                    ),
                    storage_class_name="nfs-rwx",
                )
            )

        core.read_persistent_volume.side_effect = root_volume

        observed = cluster.ensure_workspace_storage(
            "11111111-1111-4111-8111-111111111111"
        )

        volumes = [call.args[0] for call in core.create_persistent_volume.call_args_list]
        self.assertEqual(len(volumes), 2)
        self.assertEqual(
            [volume.metadata.name for volume in volumes],
            [
                "product-workspace-11111111-1111-4111-8111-111111111111",
                "product-runtime-home-11111111-1111-4111-8111-111111111111",
            ],
        )
        self.assertEqual(
            [volume.spec.capacity["storage"] for volume in volumes],
            ["1Gi", "2Gi"],
        )
        self.assertEqual(
            [volume.spec.access_modes for volume in volumes],
            [["ReadWriteMany"], ["ReadWriteOnce"]],
        )
        self.assertEqual(
            [volume.spec.storage_class_name for volume in volumes],
            ["nfs-rwx", "nfs-rwo"],
        )
        self.assertTrue(
            all(volume.spec.mount_options == inherited_mount_options for volume in volumes)
        )
        self.assertTrue(
            all(volume.spec.nfs.server == "nfs-server" for volume in volumes)
        )
        preparer = core.create_namespaced_pod.call_args.args[1]
        self.assertEqual(
            [mount.mount_path for mount in preparer.spec.containers[0].volume_mounts],
            ["/workspaces", "/runtime-homes", "/tmp"],
        )
        self.assertEqual(observed["mode"], "static-nfs")
        self.assertEqual(
            observed["runtimeHomePv"],
            "product-runtime-home-11111111-1111-4111-8111-111111111111",
        )

    def test_static_workspace_storage_reuses_already_bound_volume(self) -> None:
        from kubernetes import client

        core = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._delete_pod_if_exists = Mock()  # type: ignore[method-assign]

        def wait(read, _predicate, *, description: str, timeout_seconds: float):
            del timeout_seconds
            if description.startswith("Workspace PVC"):
                return read()
            return client.V1Pod(status=client.V1PodStatus(phase="Succeeded"))

        cluster._wait = Mock(side_effect=wait)  # type: ignore[method-assign]

        def pvc(name: str, _namespace: str):
            if name in {
                "product-workspaces-root-pvc",
                "product-runtime-homes-root-pvc",
            }:
                return client.V1PersistentVolumeClaim(
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteMany"],
                        volume_name=f"{name}-volume",
                    ),
                    status=client.V1PersistentVolumeClaimStatus(phase="Bound"),
                )
            if name.startswith("workspace-runtime-home-pvc-"):
                return client.V1PersistentVolumeClaim(
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=["ReadWriteOnce"],
                        resources=client.V1VolumeResourceRequirements(
                            requests={"storage": "2Gi"}
                        ),
                        storage_class_name="nfs-rwo",
                        volume_name="existing-runtime-home-volume",
                    ),
                    status=client.V1PersistentVolumeClaimStatus(phase="Bound"),
                )
            return client.V1PersistentVolumeClaim(
                spec=client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteMany"],
                    resources=client.V1VolumeResourceRequirements(
                        requests={"storage": "1Gi"}
                    ),
                    storage_class_name="nfs-rwx",
                ),
                status=client.V1PersistentVolumeClaimStatus(phase="Pending"),
            )

        core.read_namespaced_persistent_volume_claim.side_effect = pvc
        core.read_persistent_volume.return_value = client.V1PersistentVolume(
            spec=client.V1PersistentVolumeSpec(
                access_modes=["ReadWriteMany"],
                capacity={"storage": "2Gi"},
                mount_options=["vers=4.1", "hard"],
                nfs=client.V1NFSVolumeSource(path="/", server="nfs-server"),
                storage_class_name="nfs-rwx",
            )
        )

        observed = cluster.ensure_workspace_storage(
            "11111111-1111-4111-8111-111111111111"
        )

        volumes = [call.args[0] for call in core.create_persistent_volume.call_args_list]
        self.assertEqual(len(volumes), 1)
        self.assertEqual(
            volumes[0].metadata.name,
            "product-workspace-11111111-1111-4111-8111-111111111111",
        )
        self.assertEqual(observed["runtimeHomePv"], "existing-runtime-home-volume")

    def test_static_workspace_cleanup_runs_as_runtime_identity(self) -> None:
        from kubernetes import client

        core = Mock()
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="nfs-rwx",
            storage_mode="static-nfs",
            nfs_server="nfs-server",
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )
        cluster._delete_pod_if_exists = Mock()  # type: ignore[method-assign]
        cluster._wait = Mock(
            side_effect=[
                client.V1Pod(status=client.V1PodStatus(phase="Succeeded")),
                [],
            ]
        )  # type: ignore[method-assign]

        cluster.delete_workspace_storage("11111111-1111-4111-8111-111111111111")

        cleanup = core.create_namespaced_pod.call_args.args[1]
        self.assertEqual(cleanup.spec.security_context.run_as_user, RUNTIME_UID)
        self.assertEqual(cleanup.spec.security_context.run_as_group, RUNTIME_GID)
        self.assertEqual(cleanup.spec.security_context.fs_group, 2000)

    def test_dynamic_workspace_storage_waits_for_csi_bound_pvc(self) -> None:
        from kubernetes import client

        core = Mock()
        core.read_namespaced_persistent_volume_claim.return_value = (
            client.V1PersistentVolumeClaim(
                spec=client.V1PersistentVolumeClaimSpec(
                    access_modes=["ReadWriteMany"],
                    storage_class_name="rwx-csi",
                    volume_name="csi-volume-id",
                ),
                status=client.V1PersistentVolumeClaimStatus(phase="Bound"),
            )
        )
        cluster = ProductCluster(
            namespace="test-ns",
            release="product",
            run_id="run",
            driver_image="driver:test",
            image_pull_policy="Never",
            storage_class="rwx-csi",
            storage_mode="dynamic",
            nfs_server=None,
            storage_gid=2000,
            core=core,
            apps=Mock(),
            custom=Mock(),
            discovery=Mock(),
        )

        observed = cluster.ensure_workspace_storage(
            "11111111-1111-4111-8111-111111111111"
        )

        self.assertEqual(
            observed,
            {
                "mode": "dynamic",
                "pv": "csi-volume-id",
                "pvc": "workspace-pvc-11111111-1111-4111-8111-111111111111",
                "storageClass": "rwx-csi",
            },
        )
        core.create_namespaced_pod.assert_not_called()
        core.create_persistent_volume.assert_not_called()
        core.read_persistent_volume.assert_not_called()


if __name__ == "__main__":
    unittest.main()
