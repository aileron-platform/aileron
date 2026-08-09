"""Kubernetes control and observation helpers for product conformance."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from kubernetes import client
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

FORMAL_RUNTIME_ASSERTION_ISSUER = "workspace-manager"
TERMINAL_PORT_NAME = "terminal"
TERMINAL_SERVICE_PORT = 3004
DATAPLANE_STABLE_OBSERVATIONS = 3
ENDPOINT_SLICE_REQUEST_TIMEOUT_SECONDS = (5, 10)
WORKSPACE_LIFETIME_UID_KEYS = (
    "workspaceCrUid",
    "workspacePvcUid",
    "runtimeHomePvcUid",
)
WORKSPACE_STORAGE_MARKER_PATHS = {
    "workingTree": "/workspace/.aileron-product-conformance",
    "runtimeHome": "/home/developer/.aileron-product-conformance",
}
RUNTIME_SECRET_DATA_KEYS = frozenset(
    {
        "state-database-url",
        "runtime-control-token",
        "custom-setup.sh",
    }
)
RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[5]
    / "contracts"
    / "platform-configuration"
    / "runtime-platform-environment.json"
)


def _load_runtime_platform_environment_contract() -> list[dict[str, Any]]:
    contract = json.loads(
        RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    if contract.get("schemaVersion") != 1:
        raise AssertionError(
            "Runtime platform environment contract schemaVersion must be 1"
        )
    required = contract.get("required")
    if not isinstance(required, list) or not required:
        raise AssertionError(
            "Runtime platform environment contract has no required entries"
        )
    names = [item.get("name") for item in required if isinstance(item, dict)]
    if len(names) != len(required) or len(set(names)) != len(names):
        raise AssertionError(
            "Runtime platform environment contract names must be unique"
        )
    return required


def _require_runtime_platform_environment(
    environment: dict[str, client.V1EnvVar],
) -> dict[str, str]:
    required = _load_runtime_platform_environment_contract()
    required_names = {item["name"] for item in required}
    observed_names = {name for name in environment if name.startswith("AILERON_")}
    if observed_names != required_names:
        raise AssertionError(
            "Runtime platform environment key mismatch: "
            f"expected={sorted(required_names)!r}, "
            f"observed={sorted(observed_names)!r}"
        )
    observed: dict[str, str] = {}
    for item in required:
        name = item["name"]
        env_var = environment[name]
        if env_var.value_from is not None or not isinstance(env_var.value, str):
            raise AssertionError(
                f"Runtime platform environment {name} must be a literal value"
            )
        if re.fullmatch(item["valuePattern"], env_var.value) is None:
            raise AssertionError(
                f"Runtime platform environment {name} does not satisfy "
                f"{item['valueKind']}"
            )
        port_contract = item.get("port")
        if port_contract is not None:
            parsed = urlsplit(env_var.value)
            try:
                port = parsed.port
            except ValueError as exc:
                raise AssertionError(
                    f"Runtime platform environment {name} has an invalid port"
                ) from exc
            if port_contract["required"] and port is None:
                raise AssertionError(
                    f"Runtime platform environment {name} requires an explicit port"
                )
            if port is not None and not (
                port_contract["minimum"] <= port <= port_contract["maximum"]
            ):
                raise AssertionError(
                    f"Runtime platform environment {name} port is outside the "
                    "allowed range"
                )
        observed[name] = env_var.value
    return observed


def _canonical_runtime_secret_name(workspace_id: str) -> str:
    digest = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()
    return f"workspace-runtime-db-{digest[:32]}"


def _workspace_directory_preparer_args(workspace_id: str) -> list[str]:
    return [
        'umask 0007; mkdir -p "$1"; chmod 2770 "$1"',
        "--",
        f"/workspaces/{workspace_id}",
    ]


@dataclass(frozen=True)
class ServiceSnapshot:
    name: str
    ports: list[client.V1ServicePort]
    terminal_service_port: int
    terminal_target_port: int


class ProductCluster:
    """Exercise and inspect only resources in the conformance namespace."""

    def __init__(
        self,
        *,
        namespace: str,
        release: str,
        run_id: str,
        driver_image: str,
        image_pull_policy: str,
        storage_class: str,
        storage_mode: str,
        nfs_server: str | None,
        storage_gid: int,
        core: client.CoreV1Api,
        apps: client.AppsV1Api,
        custom: client.CustomObjectsApi,
        discovery: client.DiscoveryV1Api,
    ) -> None:
        self.namespace = namespace
        self.release = release
        self.run_id = run_id
        self.driver_image = driver_image
        self.image_pull_policy = image_pull_policy
        self.storage_class = storage_class
        if storage_mode not in {"static-nfs", "dynamic"}:
            raise ValueError("storage_mode must be static-nfs or dynamic")
        if storage_mode == "static-nfs" and not nfs_server:
            raise ValueError("nfs_server is required for static-nfs storage")
        self.storage_mode = storage_mode
        self.nfs_server = nfs_server
        self.storage_gid = storage_gid
        self.core = core
        self.apps = apps
        self.custom = custom
        self.discovery = discovery

    @property
    def manager_deployment_name(self) -> str:
        return f"{self.release}-aileron-workspace-manager"

    def manager_pod(self, *, ready: bool = True) -> client.V1Pod:
        pods = self.core.list_namespaced_pod(
            self.namespace,
            label_selector=(
                f"app.kubernetes.io/instance={self.release},"
                "app.kubernetes.io/component=workspace-manager"
            ),
        ).items
        candidates = [pod for pod in pods if pod.metadata.deletion_timestamp is None]
        if ready:
            candidates = [pod for pod in candidates if self._pod_ready(pod)]
        if len(candidates) != 1:
            names = [pod.metadata.name for pod in candidates]
            raise AssertionError(
                f"Expected one product Manager pod, observed {names!r}"
            )
        return candidates[0]

    def wait_manager_pod(
        self,
        *,
        different_uid: str | None = None,
        timeout_seconds: float = 300,
    ) -> client.V1Pod:
        return self._wait(
            lambda: self._read_manager_candidate(different_uid=different_uid),
            lambda pod: pod is not None,
            description="a Ready product Manager pod",
            timeout_seconds=timeout_seconds,
        )

    def delete_manager_pod(self) -> str:
        pod = self.manager_pod()
        uid = str(pod.metadata.uid)
        self.core.delete_namespaced_pod(
            pod.metadata.name,
            self.namespace,
            grace_period_seconds=0,
        )
        return uid

    def supervisor(self, action: str, *processes: str) -> str:
        allowed_actions = {"start", "stop", "status"}
        if action not in allowed_actions:
            raise ValueError(f"Unsupported supervisor action: {action}")
        pod = self.manager_pod()
        command = ["supervisorctl", action, *processes]
        return stream(
            self.core.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            self.namespace,
            command=command,
            container="workspace-manager",
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )

    def wait_supervisor_processes(
        self,
        expected: dict[str, str],
        *,
        timeout_seconds: float = 120,
    ) -> dict[str, str]:
        def read() -> dict[str, str]:
            try:
                output = self.supervisor("status")
            except Exception:
                return {}
            statuses: dict[str, str] = {}
            for line in output.splitlines():
                fields = line.split()
                if len(fields) >= 2:
                    statuses[fields[0]] = fields[1]
            return statuses

        return self._wait(
            read,
            lambda statuses: all(
                statuses.get(process) == state for process, state in expected.items()
            ),
            description=f"supervisor states {expected!r}",
            timeout_seconds=timeout_seconds,
        )

    def ensure_workspace_storage(self, workspace_id: str) -> dict[str, str]:
        """Wait for CSI storage or create static NFS storage for a workspace."""

        pvc_name = f"workspace-pvc-{workspace_id}"
        if self.storage_mode == "dynamic":
            pvc = self._wait(
                lambda: self._read_namespaced_pvc(pvc_name),
                lambda item: bool(
                    item is not None
                    and item.status is not None
                    and item.status.phase == "Bound"
                ),
                description=f"dynamically provisioned workspace PVC {pvc_name}",
                timeout_seconds=300,
            )
            if pvc.spec.storage_class_name != self.storage_class:
                raise AssertionError(
                    "Workspace PVC storage class mismatch: "
                    f"{pvc.spec.storage_class_name!r} != {self.storage_class!r}"
                )
            if not pvc.spec.volume_name:
                raise AssertionError("Bound workspace PVC has no volume name")
            return {
                "mode": "dynamic",
                "pv": pvc.spec.volume_name,
                "pvc": pvc_name,
                "storageClass": self.storage_class,
            }

        root_pvc = self.core.read_namespaced_persistent_volume_claim(
            "product-workspaces-root-pvc",
            self.namespace,
        )
        if root_pvc.status is None or root_pvc.status.phase != "Bound":
            raise AssertionError("Static workspace root PVC is not Bound")
        if not root_pvc.spec.volume_name:
            raise AssertionError("Static workspace root PVC has no volume name")
        root_volume = self.core.read_persistent_volume(root_pvc.spec.volume_name)
        if root_volume.spec.nfs is None:
            raise AssertionError("Static workspace root PV is not NFS")
        if root_volume.spec.nfs.server != self.nfs_server:
            raise AssertionError("Static workspace root PV NFS server mismatch")
        mount_options = list(root_volume.spec.mount_options or [])
        if not mount_options:
            raise AssertionError("Static workspace root PV has no mount options")

        short_id = workspace_id.split("-", 1)[0]
        pod_name = f"product-workspace-dir-{short_id}"
        pv_name = f"product-workspace-{workspace_id}"
        self._delete_pod_if_exists(pod_name)
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                security_context=client.V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_user=1000860099,
                    run_as_group=1000860099,
                    fs_group=self.storage_gid,
                    fs_group_change_policy="OnRootMismatch",
                    seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
                ),
                containers=[
                    client.V1Container(
                        name="prepare",
                        image=self.driver_image,
                        image_pull_policy=self.image_pull_policy,
                        command=["/bin/sh", "-ec"],
                        args=_workspace_directory_preparer_args(workspace_id),
                        security_context=client.V1SecurityContext(
                            allow_privilege_escalation=False,
                            read_only_root_filesystem=True,
                            capabilities=client.V1Capabilities(drop=["ALL"]),
                        ),
                        volume_mounts=[
                            client.V1VolumeMount(
                                name="workspaces",
                                mount_path="/workspaces",
                            ),
                            client.V1VolumeMount(name="tmp", mount_path="/tmp"),
                        ],
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="workspaces",
                        persistent_volume_claim=(
                            client.V1PersistentVolumeClaimVolumeSource(
                                claim_name="product-workspaces-root-pvc"
                            )
                        ),
                    ),
                    client.V1Volume(
                        name="tmp",
                        empty_dir=client.V1EmptyDirVolumeSource(),
                    ),
                ],
            ),
        )
        self.core.create_namespaced_pod(self.namespace, pod)
        completed = self._wait(
            lambda: self.core.read_namespaced_pod(pod_name, self.namespace),
            lambda item: item.status.phase in {"Succeeded", "Failed"},
            description=f"workspace directory preparer {pod_name}",
            timeout_seconds=180,
        )
        if completed.status.phase != "Succeeded":
            logs = self.core.read_namespaced_pod_log(pod_name, self.namespace)
            raise AssertionError(
                f"Workspace directory preparation failed: {logs[:1000]!r}"
            )
        self.core.delete_namespaced_pod(pod_name, self.namespace)

        volume = client.V1PersistentVolume(
            metadata=client.V1ObjectMeta(
                name=pv_name,
                labels={"aileron.io/product-conformance-run": self.run_id},
            ),
            spec=client.V1PersistentVolumeSpec(
                capacity={"storage": "1Gi"},
                access_modes=["ReadWriteMany"],
                persistent_volume_reclaim_policy="Retain",
                storage_class_name=self.storage_class,
                mount_options=mount_options,
                claim_ref=client.V1ObjectReference(
                    api_version="v1",
                    kind="PersistentVolumeClaim",
                    namespace=self.namespace,
                    name=pvc_name,
                ),
                nfs=client.V1NFSVolumeSource(
                    server=str(self.nfs_server),
                    path=f"/workspaces/{workspace_id}",
                ),
            ),
        )
        try:
            self.core.create_persistent_volume(volume)
        except ApiException as exc:
            if exc.status != 409:
                raise
        return {
            "mode": "static-nfs",
            "pv": pv_name,
            "pvc": pvc_name,
            "path": f"/workspaces/{workspace_id}",
        }

    def wait_workspace_ready(
        self,
        workspace_id: str,
        *,
        timeout_seconds: float = 600,
    ) -> dict[str, Any]:
        return self._wait(
            lambda: self._read_workspace_custom_resource(workspace_id),
            self._workspace_custom_resource_ready,
            description=f"Workspace CR {workspace_id} Ready",
            timeout_seconds=timeout_seconds,
        )

    def workspace_stopped_state(
        self,
        workspace_id: str,
        *,
        expected_runtime_instance_id: str,
        old_pod_uids: set[str],
    ) -> dict[str, Any]:
        resource = self._read_workspace_custom_resource(workspace_id)
        metadata = (resource or {}).get("metadata") or {}
        spec = (resource or {}).get("spec") or {}
        status = (resource or {}).get("status") or {}
        workspace_pvc = self._read_namespaced_pvc(f"workspace-pvc-{workspace_id}")
        runtime_home_pvc = self._read_namespaced_pvc(
            f"workspace-runtime-home-pvc-{workspace_id}"
        )
        pod_uids = [
            str(pod.metadata.uid)
            for pod in self.workspace_pods(workspace_id)
            if pod.metadata.uid is not None
        ]
        return {
            "customResourcePresent": resource is not None,
            "customResourceStopped": self._workspace_custom_resource_stopped(
                resource,
                expected_runtime_instance_id=expected_runtime_instance_id,
            ),
            "workspaceCrUid": self._metadata_uid(metadata),
            "workspacePvcUid": self._object_uid(workspace_pvc),
            "runtimeHomePvcUid": self._object_uid(runtime_home_pvc),
            "generation": metadata.get("generation"),
            "observedGeneration": status.get("observedGeneration"),
            "phase": status.get("phase"),
            "runtimeInstanceId": (spec.get("runtime") or {}).get("instanceId"),
            "desiredStates": {
                component: (spec.get(component) or {}).get("desiredState")
                for component in ("runtime", "browser", "canvas")
            },
            "podUids": pod_uids,
            "oldPodUidsAbsent": set(pod_uids).isdisjoint(old_pod_uids),
        }

    def write_workspace_storage_markers(self, workspace_id: str) -> dict[str, str]:
        """Write deterministic markers to both persistent Workspace volumes."""

        markers = {
            key: hashlib.sha256(
                f"{self.run_id}:{workspace_id}:{key}".encode("utf-8")
            ).hexdigest()
            for key in WORKSPACE_STORAGE_MARKER_PATHS
        }
        pod = self._workspace_component_pod(workspace_id, "runtime")
        stream(
            self.core.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            self.namespace,
            command=[
                "/bin/sh",
                "-ec",
                (
                    'umask 0077; printf "%s\\n" "$1" > "$2"; '
                    'printf "%s\\n" "$3" > "$4"'
                ),
                "--",
                markers["workingTree"],
                WORKSPACE_STORAGE_MARKER_PATHS["workingTree"],
                markers["runtimeHome"],
                WORKSPACE_STORAGE_MARKER_PATHS["runtimeHome"],
            ],
            container="runtime",
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        observed = self.read_workspace_storage_markers(workspace_id)
        if observed != markers:
            raise AssertionError(
                "Workspace storage markers did not persist after write: "
                f"expected={markers!r}, observed={observed!r}"
            )
        return markers

    def read_workspace_storage_markers(self, workspace_id: str) -> dict[str, str]:
        """Read the working-tree and Runtime HOME persistence markers."""

        pod = self._workspace_component_pod(workspace_id, "runtime")
        output = stream(
            self.core.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            self.namespace,
            command=[
                "/bin/sh",
                "-ec",
                (
                    'test -f "$1"; test -f "$2"; '
                    'printf "%s\\n%s\\n" "$(cat "$1")" "$(cat "$2")"'
                ),
                "--",
                WORKSPACE_STORAGE_MARKER_PATHS["workingTree"],
                WORKSPACE_STORAGE_MARKER_PATHS["runtimeHome"],
            ],
            container="runtime",
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        values = str(output).splitlines()
        if len(values) != 2 or not all(values):
            raise AssertionError(
                f"Workspace storage marker output is invalid: {output!r}"
            )
        return dict(zip(WORKSPACE_STORAGE_MARKER_PATHS, values, strict=True))

    def delete_workspace_component_pod(
        self,
        workspace_id: str,
        component: str,
    ) -> dict[str, str]:
        """Delete one current component Pod to exercise controller recreation."""

        pod = self._workspace_component_pod(workspace_id, component)
        identity = {
            "name": str(pod.metadata.name),
            "uid": str(pod.metadata.uid),
        }
        self.core.delete_namespaced_pod(
            pod.metadata.name,
            self.namespace,
            grace_period_seconds=0,
        )
        return identity

    @staticmethod
    def _workspace_component_label(component: str) -> str:
        if component not in {"runtime", "browser", "canvas"}:
            raise AssertionError(f"Unsupported workspace component: {component}")
        return f"workspace-{component}"

    def assert_workspace_runtime_contract(
        self,
        workspace_id: str,
        *,
        runtime_image: str,
        browser_image: str,
        canvas_image: str,
        manager_url: str,
        assertion_secret_name: str,
        knowledge_bases_pvc_name: str,
        image_pull_secret_name: str | None,
    ) -> dict[str, Any]:
        """Prove the formal Manager and manual Operator produced the real Pods."""

        resource = self._read_workspace_custom_resource(workspace_id)
        if resource is None:
            raise AssertionError(f"Workspace CR is absent: {workspace_id}")
        spec = resource.get("spec") or {}
        runtime_spec = spec.get("runtime") or {}
        browser_spec = spec.get("browser") or {}
        canvas_spec = spec.get("canvas") or {}
        assertion_spec = runtime_spec.get("assertion") or {}
        worktree_subdir = spec.get("worktreeSubdir")
        if not isinstance(worktree_subdir, str) or not worktree_subdir:
            raise AssertionError("Workspace CR worktree subdirectory is empty")
        if "controlAssertion" in runtime_spec:
            raise AssertionError("Workspace CR must not contain a control assertion")
        runtime_secret_name = runtime_spec.get("runtimeSecretName")
        if not isinstance(runtime_secret_name, str) or not runtime_secret_name:
            raise AssertionError("Workspace CR runtime secret name is empty")
        expected_runtime_secret_name = _canonical_runtime_secret_name(workspace_id)
        if runtime_secret_name != expected_runtime_secret_name:
            raise AssertionError(
                "Workspace CR runtime secret name is not canonical: "
                f"expected={expected_runtime_secret_name!r}, "
                f"observed={runtime_secret_name!r}"
            )
        observed_cr_contract = {
            "runtimeImage": runtime_spec.get("image"),
            "browserImage": browser_spec.get("image"),
            "canvasImage": canvas_spec.get("image"),
            "assertionIssuer": assertion_spec.get("issuer"),
            "assertionSecretName": assertion_spec.get("publicKeySetSecretName"),
            "runtimeSecretName": runtime_secret_name,
        }
        expected_cr_contract = {
            "runtimeImage": runtime_image,
            "browserImage": browser_image,
            "canvasImage": canvas_image,
            "assertionIssuer": FORMAL_RUNTIME_ASSERTION_ISSUER,
            "assertionSecretName": assertion_secret_name,
            "runtimeSecretName": expected_runtime_secret_name,
        }
        if not observed_cr_contract["assertionIssuer"]:
            raise AssertionError("Workspace CR assertion issuer is empty")
        observed_static_cr_contract = {
            key: observed_cr_contract.get(key) for key in expected_cr_contract
        }
        if observed_static_cr_contract != expected_cr_contract:
            raise AssertionError(
                "Workspace CR runtime contract mismatch: "
                f"expected={expected_cr_contract!r}, "
                f"observed={observed_static_cr_contract!r}"
            )

        expected_images = {
            "runtime": runtime_image,
            "browser": browser_image,
            "canvas": canvas_image,
        }
        platform_secret_name = f"{self.release}-aileron-secrets"
        workload_service_account_name = f"workspace-workload-{workspace_id}"
        workload_service_account = self.core.read_namespaced_service_account(
            workload_service_account_name,
            self.namespace,
        )
        self._require_image_pull_secret(
            workload_service_account.image_pull_secrets,
            expected_name=image_pull_secret_name,
            component=f"{workload_service_account_name} ServiceAccount",
        )
        workload_pull_secret_names = sorted(
            reference.name
            for reference in (workload_service_account.image_pull_secrets or [])
            if reference.name is not None
        )
        observed_pods: dict[str, dict[str, Any]] = {}
        pods_by_component: dict[str, client.V1Pod] = {}
        for component, expected_image in expected_images.items():
            deployment_name = f"workspace-{component}-{workspace_id}"
            deployment = self.apps.read_namespaced_deployment(
                deployment_name,
                self.namespace,
            )
            deployment_containers = deployment.spec.template.spec.containers or []
            if len(deployment_containers) != 1:
                raise AssertionError(
                    f"{deployment_name} must have exactly one container"
                )
            if deployment_containers[0].image != expected_image:
                raise AssertionError(
                    f"{deployment_name} image mismatch: "
                    f"{deployment_containers[0].image!r} != {expected_image!r}"
                )
            if (
                deployment.spec.template.spec.service_account_name
                != workload_service_account_name
            ):
                raise AssertionError(
                    f"{deployment_name} does not use the workspace ServiceAccount"
                )
            self._require_secret_not_referenced(
                deployment.spec.template.spec,
                secret_name=platform_secret_name,
                component=f"{deployment_name} Deployment",
            )
            if component != "runtime":
                self._require_secret_not_referenced(
                    deployment.spec.template.spec,
                    secret_name=runtime_secret_name,
                    component=f"{deployment_name} Deployment",
                )
            component_label = self._workspace_component_label(component)
            pods = self.core.list_namespaced_pod(
                self.namespace,
                label_selector=(
                    f"aileron.io/workspace-id={workspace_id},"
                    f"aileron.io/component={component_label}"
                ),
            ).items
            candidates = [
                pod for pod in pods if pod.metadata.deletion_timestamp is None
            ]
            if len(candidates) != 1:
                raise AssertionError(
                    f"Expected one current {component} Pod, observed "
                    f"{[pod.metadata.name for pod in candidates]!r}"
                )
            pod = candidates[0]
            if not self._pod_ready(pod):
                raise AssertionError(f"Workspace {component} Pod is not Ready")
            if pod.spec.service_account_name != workload_service_account_name:
                raise AssertionError(
                    f"Workspace {component} Pod does not use the workspace "
                    "ServiceAccount"
                )
            containers = pod.spec.containers or []
            if len(containers) != 1 or containers[0].image != expected_image:
                raise AssertionError(
                    f"Workspace {component} Pod image contract is invalid"
                )
            self._require_image_pull_secret(
                pod.spec.image_pull_secrets,
                expected_name=image_pull_secret_name,
                component=f"Workspace {component} Pod",
            )
            self._require_secret_not_referenced(
                pod.spec,
                secret_name=platform_secret_name,
                component=f"Workspace {component} Pod",
            )
            if component != "runtime":
                self._require_secret_not_referenced(
                    pod.spec,
                    secret_name=runtime_secret_name,
                    component=f"Workspace {component} Pod",
                )
            pods_by_component[component] = pod
            observed_pods[component] = {
                "name": pod.metadata.name,
                "uid": str(pod.metadata.uid),
                "image": containers[0].image,
                "ready": True,
            }

        runtime_pod = pods_by_component["runtime"]
        runtime_container = runtime_pod.spec.containers[0]
        runtime_env = {item.name: item for item in (runtime_container.env or [])}
        observed_runtime_values = _require_runtime_platform_environment(runtime_env)
        expected_runtime_values = {
            "AILERON_WORKSPACE_ID": workspace_id,
            "AILERON_WORKSPACE_PATH": spec.get("workspacePath") or "/workspace",
            "AILERON_RUNTIME_INSTANCE_ID": str(runtime_spec.get("instanceId") or ""),
            "AILERON_RUNTIME_ACCESS_REVISION": str(
                runtime_spec.get("accessRevision")
            ),
            "AILERON_KB_MOUNT_REVISION": str(runtime_spec.get("mountRevision")),
            "AILERON_WORKTREE_SUBDIR": worktree_subdir,
            "AILERON_RUNTIME_STATE_DATABASE_URL_FILE": (
                "/etc/aileron/runtime-secrets/state-database-url"
            ),
            "AILERON_RUNTIME_CONTROL_TOKEN_FILE": (
                "/etc/aileron/runtime-secrets/runtime-control-token"
            ),
            "AILERON_MANAGER_INTERNAL_URL": manager_url,
            "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": (
                "/etc/aileron/runtime-assertions/jwks.json"
            ),
            "AILERON_RUNTIME_ASSERTION_ISSUER": FORMAL_RUNTIME_ASSERTION_ISSUER,
            "AILERON_BROWSER_SERVICE_NAME": f"workspace-browser-{workspace_id}",
            "AILERON_BROWSER_WEBRTC_INTERNAL_URL": (
                f"http://workspace-browser-{workspace_id}:6080"
            ),
            "AILERON_BROWSER_CDP_URL": (
                f"http://workspace-browser-{workspace_id}:9223"
            ),
            "AILERON_CANVAS_SERVICE_NAME": f"workspace-canvas-{workspace_id}",
            "AILERON_CANVAS_INTERNAL_URL": (
                f"http://workspace-canvas-{workspace_id}:3003"
            ),
            "AILERON_CANVAS_API_URL": (
                f"http://workspace-canvas-{workspace_id}:3013"
            ),
        }
        observed_static_runtime_values = {
            name: observed_runtime_values.get(name)
            for name in expected_runtime_values
        }
        if observed_static_runtime_values != expected_runtime_values:
            raise AssertionError(
                "Runtime Pod environment mismatch: "
                f"expected={expected_runtime_values!r}, "
                f"observed={observed_static_runtime_values!r}"
            )
        forbidden_runtime_environment = (
            "DATABASE_URL",
            "REDIS_URL",
            "INTERNAL_API_TOKEN",
            "MANAGER_CONTROL_ASSERTION",
            "MANAGER_URL",
            "BROWSER_CONTAINER_NAME",
            "BROWSER_WEBRTC_INTERNAL_URL",
            "BROWSER_CDP_URL",
            "CANVAS_CONTAINER_NAME",
            "CANVAS_INTERNAL_URL",
            "CANVAS_API_URL",
            "RUNTIME_STATE_DATABASE_URL",
            "RUNTIME_CONTROL_TOKEN",
        )
        self._require_environment_absent(
            runtime_env,
            names=forbidden_runtime_environment,
            component="Runtime Pod",
        )
        runtime_secret_volume = next(
            (
                volume
                for volume in (runtime_pod.spec.volumes or [])
                if volume.name == "runtime-secrets"
            ),
            None,
        )
        runtime_secret_mount = next(
            (
                mount
                for mount in (runtime_container.volume_mounts or [])
                if mount.name == "runtime-secrets"
            ),
            None,
        )
        if (
            runtime_secret_volume is None
            or runtime_secret_volume.secret is None
            or runtime_secret_volume.secret.secret_name != runtime_secret_name
            or runtime_secret_mount is None
            or runtime_secret_mount.mount_path != "/etc/aileron/runtime-secrets"
            or runtime_secret_mount.read_only is not True
        ):
            raise AssertionError(
                "Runtime scoped credentials must use the read-only runtime-secrets "
                "Secret volume"
            )
        observed_runtime_secret_items = {
            (item.key, item.path)
            for item in (runtime_secret_volume.secret.items or [])
        }
        expected_runtime_secret_items = {
            ("state-database-url", "state-database-url"),
            ("runtime-control-token", "runtime-control-token"),
        }
        if observed_runtime_secret_items != expected_runtime_secret_items:
            raise AssertionError(
                "Runtime scoped credential projection mismatch: "
                f"expected={sorted(expected_runtime_secret_items)!r}, "
                f"observed={sorted(observed_runtime_secret_items)!r}"
            )
        runtime_secret = self.core.read_namespaced_secret(
            runtime_secret_name,
            self.namespace,
        )
        self._require_runtime_secret_data_contract(runtime_secret)
        pod_annotations = runtime_pod.metadata.annotations or {}
        if "aileron.io/internal-api-token-revision" in pod_annotations:
            raise AssertionError(
                "Runtime Pod must not carry the platform internal token revision"
            )

        runtime_cli_probe = stream(
            self.core.connect_get_namespaced_pod_exec,
            runtime_pod.metadata.name,
            self.namespace,
            command=[
                "/bin/sh",
                "-ec",
                (
                    "command -v claude; "
                    "claude --version; "
                    "dpkg-query -W -f='${Version}\\n' claude-code"
                ),
            ],
            container=runtime_container.name,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        runtime_cli_lines = [
            line.strip() for line in runtime_cli_probe.splitlines() if line.strip()
        ]
        if len(runtime_cli_lines) != 3:
            raise AssertionError(
                f"Runtime Claude CLI probe output is invalid: {runtime_cli_probe!r}"
            )
        cli_path, cli_output, package_version = runtime_cli_lines
        cli_version = cli_output.split(maxsplit=1)[0]
        package_upstream_version = package_version.rsplit("-", maxsplit=1)[0]
        if cli_path != "/usr/bin/claude":
            raise AssertionError(
                f"Runtime Claude CLI path is not package-managed: {cli_path!r}"
            )
        if cli_version != package_upstream_version:
            raise AssertionError(
                "Runtime Claude CLI version does not match its package: "
                f"cli={cli_output!r}, package={package_version!r}"
            )

        jwks_volume = next(
            (
                volume
                for volume in (runtime_pod.spec.volumes or [])
                if volume.name == "runtime-assertion-public-jwks"
            ),
            None,
        )
        if (
            jwks_volume is None
            or jwks_volume.secret is None
            or jwks_volume.secret.secret_name != assertion_secret_name
        ):
            raise AssertionError("Runtime assertion JWKS volume is not the CR Secret")
        jwks_secret = self.core.read_namespaced_secret(
            assertion_secret_name,
            self.namespace,
        )
        if "jwks.json" not in (jwks_secret.data or {}):
            raise AssertionError("Runtime assertion JWKS Secret has no jwks.json")

        manager = self.apps.read_namespaced_deployment(
            f"{self.release}-aileron-workspace-manager",
            self.namespace,
        )
        manager_credential_mount = self._require_manager_credential_mount(
            manager.spec.template.spec,
            secret_name=platform_secret_name,
        )

        operator = self.apps.read_namespaced_deployment(
            self._operator_deployment_name(),
            self.namespace,
        )
        operator_containers = operator.spec.template.spec.containers or []
        if len(operator_containers) != 1:
            raise AssertionError("Workspace Operator must have exactly one container")
        operator_env = {item.name: item for item in (operator_containers[0].env or [])}
        expected_operator_values = {
            "AILERON_MANAGER_INTERNAL_URL": manager_url,
            "AILERON_PLATFORM_PUBLIC_ORIGIN": observed_runtime_values[
                "AILERON_PLATFORM_PUBLIC_ORIGIN"
            ],
            "KNOWLEDGE_BASES_PVC_NAME": knowledge_bases_pvc_name,
        }
        observed_operator_values = {
            name: operator_env.get(name).value if operator_env.get(name) else None
            for name in expected_operator_values
        }
        if observed_operator_values != expected_operator_values:
            raise AssertionError(
                "Workspace Operator formal service contract mismatch: "
                f"expected={expected_operator_values!r}, "
                f"observed={observed_operator_values!r}"
            )
        self._require_environment_absent(
            operator_env,
            names=(
                "PLATFORM_MANAGER_URL",
                "PLATFORM_DATABASE_URL",
                "PLATFORM_REDIS_URL",
                "PLATFORM_OIDC_CLIENT_SECRET",
                "PLATFORM_OIDC_ISSUER_URL",
                "PLATFORM_OIDC_DISCOVERY_URL",
                "PLATFORM_OIDC_CLIENT_ID",
                "PLATFORM_OIDC_SCOPES",
                "PLATFORM_INTERNAL_API_TOKEN_SECRET_NAME",
                "PLATFORM_INTERNAL_API_TOKEN_SECRET_KEY",
                "PLATFORM_INTERNAL_API_TOKEN_REVISION",
            ),
            component="Workspace Operator",
        )
        unexpected_operator_oidc = sorted(
            name for name in operator_env if name.startswith("PLATFORM_OIDC_")
        )
        if unexpected_operator_oidc:
            raise AssertionError(
                "Workspace Operator received external OIDC settings: "
                f"{unexpected_operator_oidc!r}"
            )
        return {
            "workspaceCustomResource": observed_cr_contract,
            "pods": observed_pods,
            "runtimeEnvironment": observed_runtime_values,
            "runtimeForbiddenEnvironmentAbsent": list(forbidden_runtime_environment),
            "runtimeScopedSecretFiles": {
                "stateDatabase": observed_runtime_values[
                    "AILERON_RUNTIME_STATE_DATABASE_URL_FILE"
                ],
                "controlToken": observed_runtime_values[
                    "AILERON_RUNTIME_CONTROL_TOKEN_FILE"
                ],
            },
            "runtimeSecretExcludedFromVisualComponents": ["browser", "canvas"],
            "runtimeAssertionSecret": assertion_secret_name,
            "managerRuntimeDatabaseCredentialMount": manager_credential_mount,
            "workloadServiceAccount": {
                "name": workload_service_account_name,
                "imagePullSecrets": workload_pull_secret_names,
            },
            "runtimeClaudeCli": {
                "path": cli_path,
                "versionOutput": cli_output,
                "packageVersion": package_version,
            },
            "operatorEnvironment": observed_operator_values,
        }

    @staticmethod
    def _require_environment_absent(
        environment: dict[str, client.V1EnvVar],
        *,
        names: tuple[str, ...],
        component: str,
    ) -> None:
        present = sorted(name for name in names if name in environment)
        if present:
            raise AssertionError(
                f"{component} exposes forbidden platform environment: {present!r}"
            )

    @staticmethod
    def _require_image_pull_secret(
        pull_secrets: list[client.V1LocalObjectReference] | None,
        *,
        expected_name: str | None,
        component: str,
    ) -> None:
        if expected_name is None:
            return
        observed_names = {
            item.name for item in (pull_secrets or []) if item.name is not None
        }
        if expected_name not in observed_names:
            raise AssertionError(
                f"{component} has no required image pull secret {expected_name!r}"
            )

    @staticmethod
    def _require_secret_not_referenced(
        pod_spec: client.V1PodSpec,
        *,
        secret_name: str,
        component: str,
    ) -> None:
        references: list[str] = []
        containers = list(pod_spec.init_containers or []) + list(
            pod_spec.containers or []
        )
        for container in containers:
            for env_var in container.env or []:
                secret_ref = (
                    env_var.value_from.secret_key_ref
                    if env_var.value_from is not None
                    else None
                )
                if secret_ref is not None and secret_ref.name == secret_name:
                    references.append(f"env:{container.name}:{env_var.name}")
            for env_from in container.env_from or []:
                if (
                    env_from.secret_ref is not None
                    and env_from.secret_ref.name == secret_name
                ):
                    references.append(f"envFrom:{container.name}")
        for volume in pod_spec.volumes or []:
            if volume.secret is not None and volume.secret.secret_name == secret_name:
                references.append(f"volume:{volume.name}")
            if volume.projected is not None:
                for source in volume.projected.sources or []:
                    if source.secret is not None and source.secret.name == secret_name:
                        references.append(f"projectedVolume:{volume.name}")
        if any(
            pull_secret.name == secret_name
            for pull_secret in (pod_spec.image_pull_secrets or [])
        ):
            references.append("imagePullSecret")
        if references:
            raise AssertionError(
                f"{component} references forbidden Secret: {references!r}"
            )

    @staticmethod
    def _require_manager_credential_mount(
        pod_spec: client.V1PodSpec,
        *,
        secret_name: str,
    ) -> dict[str, str]:
        containers = pod_spec.containers or []
        if len(containers) != 1:
            raise AssertionError("Workspace Manager must have exactly one container")
        manager_container = containers[0]
        mount = next(
            (
                item
                for item in (manager_container.volume_mounts or [])
                if item.name == "manager-private-secrets"
            ),
            None,
        )
        if (
            mount is None
            or mount.mount_path != "/run/secrets/aileron"
            or mount.read_only is not True
        ):
            raise AssertionError("Workspace Manager private Secret mount is invalid")
        volume = next(
            (
                item
                for item in (pod_spec.volumes or [])
                if item.name == "manager-private-secrets"
            ),
            None,
        )
        expected_projection = (
            secret_name,
            "runtime-database-credential-key",
            "runtime-database-credential.key",
        )
        observed_projections = {
            (source.secret.name, item.key, item.path)
            for source in (
                volume.projected.sources
                if volume is not None and volume.projected is not None
                else []
            )
            if source.secret is not None
            for item in (source.secret.items or [])
        }
        if expected_projection not in observed_projections:
            raise AssertionError(
                "Workspace Manager runtime database credential projection is missing"
            )
        return {
            "secretName": expected_projection[0],
            "secretKey": expected_projection[1],
            "path": f"/run/secrets/aileron/{expected_projection[2]}",
        }

    @staticmethod
    def _require_runtime_secret_data_contract(secret: client.V1Secret) -> None:
        data = secret.data or {}
        if (
            secret.type != "Opaque"
            or set(data) != RUNTIME_SECRET_DATA_KEYS
            or not all(data.values())
        ):
            raise AssertionError("Runtime scoped Secret has an invalid data contract")

    def get_generation(self, workspace_id: str) -> dict[str, Any]:
        resource = self._read_workspace_custom_resource(workspace_id)
        if resource is None:
            raise AssertionError(f"Workspace CR is absent: {workspace_id}")
        metadata = resource.get("metadata") or {}
        workspace_pvc = self._read_namespaced_pvc(f"workspace-pvc-{workspace_id}")
        runtime_home_pvc = self._read_namespaced_pvc(
            f"workspace-runtime-home-pvc-{workspace_id}"
        )
        spec = resource.get("spec") or {}
        status = resource.get("status") or {}
        components = status.get("components") or {}
        runtime_spec = spec.get("runtime") or {}
        runtime_status = components.get("runtime") or {}
        return {
            "generation": metadata.get("generation"),
            "workspaceCrUid": self._require_uid(
                self._metadata_uid(metadata),
                "Workspace CR",
            ),
            "workspacePvcUid": self._require_uid(
                self._object_uid(workspace_pvc),
                "Workspace PVC",
            ),
            "runtimeHomePvcUid": self._require_uid(
                self._object_uid(runtime_home_pvc),
                "Runtime HOME PVC",
            ),
            "runtimeInstanceId": runtime_spec.get("instanceId"),
            "resourceVersion": metadata.get("resourceVersion"),
            "mountRevision": runtime_status.get("mountObservedRevision"),
            "accessRevision": runtime_status.get("accessObservedRevision"),
            "phase": status.get("phase"),
            "podUids": {
                "runtime": (components.get("runtime") or {}).get("podUid"),
                "browser": (components.get("browser") or {}).get("podUid"),
                "canvas": (components.get("canvas") or {}).get("podUid"),
            },
            "componentRevisions": {
                component: {
                    "desired": (spec.get(component) or {}).get("revision"),
                    "observed": (components.get(component) or {}).get(
                        "observedRevision"
                    ),
                }
                for component in ("runtime", "browser", "canvas")
            },
        }

    def workspace_urls(self, workspace_id: str) -> dict[str, str]:
        runtime = f"workspace-runtime-{workspace_id}.{self.namespace}.svc.cluster.local"
        browser = f"workspace-browser-{workspace_id}.{self.namespace}.svc.cluster.local"
        canvas = f"workspace-canvas-{workspace_id}.{self.namespace}.svc.cluster.local"
        return {
            "runtime": f"http://{runtime}:3002",
            "terminal": f"http://{runtime}:3004",
            "browserCdp": f"http://{runtime}:3002",
            "browser": f"http://{browser}:9223",
            "browserNeko": f"http://{browser}:6080",
            "canvas": f"http://{canvas}:3003",
            "canvasApi": f"http://{canvas}:3013",
            "browserExtension": f"ws://{runtime}:3002/api/v1/client-browser-relay/extension",
            "threadEvents": f"ws://{runtime}:3002/api/v1/threads/events",
        }

    def workspace_pods(self, workspace_id: str) -> list[client.V1Pod]:
        return self.core.list_namespaced_pod(
            self.namespace,
            label_selector=f"aileron.io/workspace-id={workspace_id}",
        ).items

    def pod_uids_absent(self, workspace_id: str, pod_uids: list[str]) -> bool:
        present = {
            str(pod.metadata.uid)
            for pod in self.workspace_pods(workspace_id)
            if pod.metadata.uid is not None
        }
        return present.isdisjoint(pod_uids)

    def manager_log_lines(self) -> list[str]:
        pod = self.manager_pod()
        logs = self.core.read_namespaced_pod_log(
            pod.metadata.name,
            self.namespace,
            container="workspace-manager",
        )
        return str(logs).splitlines()

    def wait_workspace_absent(
        self,
        workspace_id: str,
        *,
        expected_uids: dict[str, str],
        timeout_seconds: float = 600,
    ) -> dict[str, Any]:
        if set(expected_uids) != set(WORKSPACE_LIFETIME_UID_KEYS) or not all(
            isinstance(value, str) and value for value in expected_uids.values()
        ):
            raise AssertionError("Expected Workspace lifetime UIDs are incomplete")

        def observed() -> dict[str, Any]:
            resource = self._read_workspace_custom_resource(workspace_id)
            workspace_pvc = self._read_namespaced_pvc(f"workspace-pvc-{workspace_id}")
            runtime_home_pvc = self._read_namespaced_pvc(
                f"workspace-runtime-home-pvc-{workspace_id}"
            )
            pod_uids = [
                str(pod.metadata.uid) for pod in self.workspace_pods(workspace_id)
            ]
            observed_uids = {
                "workspaceCrUid": self._metadata_uid(
                    (resource or {}).get("metadata") or {}
                ),
                "workspacePvcUid": self._object_uid(workspace_pvc),
                "runtimeHomePvcUid": self._object_uid(runtime_home_pvc),
            }
            return {
                "expectedUids": dict(expected_uids),
                "observedUids": observed_uids,
                "workspaceCrAbsent": observed_uids["workspaceCrUid"] is None,
                "workspacePvcAbsent": observed_uids["workspacePvcUid"] is None,
                "runtimeHomePvcAbsent": (observed_uids["runtimeHomePvcUid"] is None),
                "podUids": pod_uids,
            }

        return self._wait(
            observed,
            lambda state: state["workspaceCrAbsent"]
            and state["workspacePvcAbsent"]
            and state["runtimeHomePvcAbsent"]
            and not state["podUids"],
            description=f"Workspace {workspace_id} cluster resources absent",
            timeout_seconds=timeout_seconds,
        )

    def scale_operator(self, replicas: int) -> dict[str, Any]:
        if not isinstance(replicas, int) or isinstance(replicas, bool) or replicas < 0:
            raise ValueError("replicas must be a non-negative integer")
        name = self._operator_deployment_name()
        before = self.apps.read_namespaced_deployment(name, self.namespace)
        previous_replicas = self._require_observed_replica_count(
            before.spec.replicas,
            component=f"Operator {name}",
        )
        pod_label_selector = (
            self._deployment_pod_label_selector(before) if replicas == 0 else None
        )
        self.apps.patch_namespaced_deployment_scale(
            name,
            self.namespace,
            {"spec": {"replicas": replicas}},
        )

        def read() -> client.V1Deployment:
            return self.apps.read_namespaced_deployment(name, self.namespace)

        deployment = self._wait(
            read,
            lambda item: self._deployment_at_replicas(item, replicas),
            description=f"Operator {name} replicas={replicas}",
            timeout_seconds=300,
        )
        if pod_label_selector is not None:
            self._wait(
                lambda: self.core.list_namespaced_pod(
                    self.namespace,
                    label_selector=pod_label_selector,
                ).items,
                lambda pods: not pods,
                description=f"Operator {name} Pod objects absent",
                timeout_seconds=300,
            )
        return {
            "name": name,
            "previousReplicas": previous_replicas,
            "replicas": self._require_observed_replica_count(
                deployment.spec.replicas,
                component=f"Operator {name}",
            ),
        }

    def operator_replicas(self) -> int:
        name = self._operator_deployment_name()
        deployment = self.apps.read_namespaced_deployment(name, self.namespace)
        return self._require_observed_replica_count(
            deployment.spec.replicas,
            component=f"Operator {name}",
        )

    def patch_terminal_target_port(
        self,
        workspace_id: str,
        port: int,
    ) -> ServiceSnapshot:
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise AssertionError(f"Terminal targetPort must be numeric: {port!r}")
        name = f"workspace-runtime-{workspace_id}"
        service = self.core.read_namespaced_service(name, self.namespace)
        original_terminal = self._require_terminal_service_port(service.spec.ports)
        snapshot = ServiceSnapshot(
            name=name,
            ports=list(service.spec.ports),
            terminal_service_port=original_terminal.port,
            terminal_target_port=original_terminal.target_port,
        )
        patched_ports = []
        for item in service.spec.ports:
            copied = client.V1ServicePort(
                app_protocol=item.app_protocol,
                name=item.name,
                node_port=item.node_port,
                port=item.port,
                protocol=item.protocol,
                target_port=(
                    port if item.name == TERMINAL_PORT_NAME else item.target_port
                ),
            )
            patched_ports.append(copied)
        self.core.patch_namespaced_service(
            name,
            self.namespace,
            {"spec": {"ports": self._service_ports_body(patched_ports)}},
        )
        try:
            updated = self.core.read_namespaced_service(name, self.namespace)
            terminal = self._require_terminal_service_port(updated.spec.ports)
            if terminal.target_port != port:
                raise AssertionError(
                    f"Terminal targetPort patch did not persist: {terminal!r}"
                )
            self._wait_for_endpoint_slice_port(
                name,
                expected_port=port,
            )
            self._wait_for_manager_service_port_reachability(
                name,
                terminal.port,
                reachable=False,
            )
        except Exception:
            try:
                self.restore_service(snapshot)
            except Exception as rollback_error:
                raise AssertionError(
                    "Terminal targetPort injection failed and rollback did not "
                    "converge"
                ) from rollback_error
            raise
        return snapshot

    def restore_service(self, snapshot: ServiceSnapshot) -> None:
        self.core.patch_namespaced_service(
            snapshot.name,
            self.namespace,
            {"spec": {"ports": self._service_ports_body(snapshot.ports)}},
        )
        restored = self.core.read_namespaced_service(
            snapshot.name,
            self.namespace,
        )
        expected = {
            (
                item.app_protocol,
                item.name,
                item.node_port,
                item.port,
                item.protocol,
                item.target_port,
            )
            for item in snapshot.ports
        }
        observed = {
            (
                item.app_protocol,
                item.name,
                item.node_port,
                item.port,
                item.protocol,
                item.target_port,
            )
            for item in restored.spec.ports
        }
        if observed != expected:
            raise AssertionError(
                f"Service restore did not persist: expected={expected!r}, "
                f"observed={observed!r}"
            )
        terminal = self._require_terminal_service_port(restored.spec.ports)
        if (
            terminal.port != snapshot.terminal_service_port
            or terminal.target_port != snapshot.terminal_target_port
        ):
            raise AssertionError(
                "Restored Runtime Service terminal port does not match its snapshot"
            )
        self._wait_for_endpoint_slice_port(
            snapshot.name,
            expected_port=snapshot.terminal_target_port,
        )
        self._wait_for_manager_service_port_reachability(
            snapshot.name,
            snapshot.terminal_service_port,
            reachable=True,
        )

    def _wait_for_endpoint_slice_port(
        self,
        service_name: str,
        *,
        expected_port: int,
    ) -> None:
        self._wait(
            lambda: self.list_endpoint_slices(service_name=service_name),
            lambda slices: self._endpoint_slices_have_terminal_port(
                slices,
                expected_port=expected_port,
            ),
            description=(
                f"active EndpointSlices for Service {service_name} to expose "
                f"{TERMINAL_PORT_NAME}/TCP target port {expected_port}"
            ),
            timeout_seconds=60,
        )

    def list_endpoint_slices(
        self,
        *,
        service_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        request_options: dict[str, Any] = {
            "_preload_content": False,
            "_request_timeout": ENDPOINT_SLICE_REQUEST_TIMEOUT_SECONDS,
        }
        if service_name is not None:
            request_options["label_selector"] = (
                f"kubernetes.io/service-name={service_name}"
            )
        if limit is not None:
            request_options["limit"] = limit
        response = self.discovery.list_namespaced_endpoint_slice(
            self.namespace,
            **request_options,
        )
        try:
            try:
                payload = json.loads(response.data)
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
                raise AssertionError(
                    "EndpointSlice API response is not valid JSON"
                ) from exc
        finally:
            response.release_conn()
        if not isinstance(payload, dict):
            raise AssertionError("EndpointSlice API response must be an object")
        if payload.get("apiVersion") != "discovery.k8s.io/v1":
            raise AssertionError(
                "EndpointSlice API response has an unexpected apiVersion"
            )
        if payload.get("kind") != "EndpointSliceList":
            raise AssertionError("EndpointSlice API response has an unexpected kind")
        items = payload.get("items")
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise AssertionError(
                "EndpointSlice API response items must be an object array"
            )
        return items

    @staticmethod
    def _endpoint_slices_have_terminal_port(
        endpoint_slices: list[dict[str, Any]],
        *,
        expected_port: int,
    ) -> bool:
        active_endpoint_count = 0
        active_slice_count = 0
        for endpoint_slice in endpoint_slices:
            active_endpoints = [
                endpoint
                for endpoint in (endpoint_slice.get("endpoints") or [])
                if (
                    isinstance(endpoint, dict)
                    and (endpoint.get("conditions") or {}).get("ready") is not False
                    and (endpoint.get("conditions") or {}).get("terminating")
                    is not True
                )
            ]
            if not active_endpoints:
                continue
            active_slice_count += 1
            active_endpoint_count += len(active_endpoints)
            terminal_ports = [
                port
                for port in (endpoint_slice.get("ports") or [])
                if isinstance(port, dict) and port.get("name") == TERMINAL_PORT_NAME
            ]
            if len(terminal_ports) != 1:
                return False
            terminal_port = terminal_ports[0]
            if (
                terminal_port.get("protocol") != "TCP"
                or terminal_port.get("port") != expected_port
            ):
                return False
        return active_slice_count > 0 and active_endpoint_count > 0

    def _wait_for_manager_service_port_reachability(
        self,
        service_name: str,
        port: int,
        *,
        reachable: bool,
    ) -> None:
        consecutive_observations = 0

        def converged(observed: bool) -> bool:
            nonlocal consecutive_observations
            if observed is reachable:
                consecutive_observations += 1
            else:
                consecutive_observations = 0
            return consecutive_observations >= DATAPLANE_STABLE_OBSERVATIONS

        state = "reachable" if reachable else "unreachable"
        self._wait(
            lambda: self._manager_service_port_reachable(service_name, port),
            converged,
            description=(
                f"Service {service_name} port {port} to remain {state} for "
                f"{DATAPLANE_STABLE_OBSERVATIONS} Manager observations"
            ),
            timeout_seconds=60,
        )

    def _manager_service_port_reachable(
        self,
        service_name: str,
        port: int,
    ) -> bool:
        pod = self.manager_pod()
        host = f"{service_name}.{self.namespace}.svc.cluster.local"
        probe_script = "\n".join(
            (
                "import socket",
                "import sys",
                "try:",
                "    with socket.create_connection(",
                "        (sys.argv[1], int(sys.argv[2])), timeout=1",
                "    ):",
                "        pass",
                "except OSError:",
                "    print('unreachable')",
                "else:",
                "    print('reachable')",
            )
        )
        output = stream(
            self.core.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            self.namespace,
            command=[
                "/workspace-manager/.venv/bin/python",
                "-c",
                probe_script,
                host,
                str(port),
            ],
            container="workspace-manager",
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        observed = str(output).strip()
        if observed not in {"reachable", "unreachable"}:
            raise AssertionError(
                f"Manager data-plane probe returned unexpected output: {observed!r}"
            )
        return observed == "reachable"

    @staticmethod
    def _require_terminal_service_port(
        ports: list[client.V1ServicePort],
    ) -> client.V1ServicePort:
        terminal_ports = [
            port for port in (ports or []) if port.name == TERMINAL_PORT_NAME
        ]
        if len(terminal_ports) != 1:
            raise AssertionError(
                "Runtime Service must expose exactly one terminal port"
            )
        terminal = terminal_ports[0]
        if terminal.protocol != "TCP":
            raise AssertionError("Runtime Service terminal port must use TCP")
        if terminal.port != TERMINAL_SERVICE_PORT:
            raise AssertionError(
                f"Runtime Service terminal port must be {TERMINAL_SERVICE_PORT}"
            )
        if not isinstance(terminal.target_port, int) or isinstance(
            terminal.target_port, bool
        ):
            raise AssertionError("Runtime Service terminal targetPort must be numeric")
        return terminal

    def cr_knowledge_bases(self, workspace_id: str) -> list[dict[str, str]]:
        resource = self._read_workspace_custom_resource(workspace_id)
        if resource is None:
            return []
        spec = resource.get("spec") or {}
        mounts = spec.get("knowledgeBases") or []
        return [dict(item) for item in mounts if isinstance(item, dict)]

    def _read_manager_candidate(
        self,
        *,
        different_uid: str | None,
    ) -> client.V1Pod | None:
        try:
            pod = self.manager_pod(ready=True)
        except AssertionError:
            return None
        if different_uid is not None and str(pod.metadata.uid) == different_uid:
            return None
        return pod

    def _operator_deployment_name(self) -> str:
        deployments = self.apps.list_namespaced_deployment(self.namespace).items
        matches = [
            deployment.metadata.name
            for deployment in deployments
            if deployment.metadata.name == "workspace-operator"
            or (deployment.metadata.labels or {}).get("app.kubernetes.io/component")
            == "workspace-operator"
        ]
        if len(matches) != 1:
            raise AssertionError(
                f"Expected one Workspace Operator deployment, observed {matches!r}"
            )
        return matches[0]

    @staticmethod
    def _deployment_pod_label_selector(
        deployment: client.V1Deployment,
    ) -> str:
        selector = deployment.spec.selector
        if selector is None:
            raise AssertionError("Workspace Operator Deployment has no selector")

        requirements: list[str] = []
        for key, value in sorted((selector.match_labels or {}).items()):
            if not isinstance(key, str) or not key or not isinstance(value, str):
                raise AssertionError(
                    "Workspace Operator Deployment has an invalid matchLabels "
                    "selector"
                )
            requirements.append(f"{key}={value}")

        expressions: list[tuple[str, str, tuple[str, ...]]] = []
        for expression in selector.match_expressions or []:
            key = expression.key
            operator = expression.operator
            values = tuple(expression.values or [])
            if (
                not isinstance(key, str)
                or not key
                or not isinstance(operator, str)
                or not all(isinstance(value, str) for value in values)
            ):
                raise AssertionError(
                    "Workspace Operator Deployment has an invalid matchExpressions "
                    "selector"
                )
            expressions.append((key, operator, tuple(sorted(values))))

        for key, operator, values in sorted(expressions):
            if operator == "In" and values:
                requirements.append(f"{key} in ({','.join(values)})")
            elif operator == "NotIn" and values:
                requirements.append(f"{key} notin ({','.join(values)})")
            elif operator == "Exists" and not values:
                requirements.append(key)
            elif operator == "DoesNotExist" and not values:
                requirements.append(f"!{key}")
            else:
                raise AssertionError(
                    "Workspace Operator Deployment has an invalid selector "
                    f"operator contract: {operator!r}"
                )

        if not requirements:
            raise AssertionError("Workspace Operator Deployment selector is empty")
        return ",".join(requirements)

    def _read_workspace_custom_resource(
        self,
        workspace_id: str,
    ) -> dict[str, Any] | None:
        try:
            resource = self.custom.get_namespaced_custom_object(
                group="platform.aileron.io",
                version="v1alpha1",
                namespace=self.namespace,
                plural="workspaces",
                name=f"workspace-{workspace_id}",
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(resource, dict):
            raise AssertionError("Workspace custom resource response is not an object")
        return resource

    def _read_namespaced_pvc(
        self,
        name: str,
    ) -> client.V1PersistentVolumeClaim | None:
        try:
            return self.core.read_namespaced_persistent_volume_claim(
                name,
                self.namespace,
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            raise

    def _workspace_component_pod(
        self,
        workspace_id: str,
        component: str,
    ) -> client.V1Pod:
        component_label = self._workspace_component_label(component)
        pods = self.core.list_namespaced_pod(
            self.namespace,
            label_selector=(
                f"aileron.io/workspace-id={workspace_id},"
                f"aileron.io/component={component_label}"
            ),
        ).items
        candidates = [
            pod
            for pod in pods
            if pod.metadata.deletion_timestamp is None and self._pod_ready(pod)
        ]
        if len(candidates) != 1:
            raise AssertionError(
                f"Expected one Ready {component} Pod, observed "
                f"{[pod.metadata.name for pod in candidates]!r}"
            )
        return candidates[0]

    @staticmethod
    def _metadata_uid(metadata: dict[str, Any]) -> str | None:
        value = metadata.get("uid")
        return str(value) if value is not None and str(value) else None

    @staticmethod
    def _object_uid(resource: Any | None) -> str | None:
        if resource is None:
            return None
        metadata = getattr(resource, "metadata", None)
        value = getattr(metadata, "uid", None)
        return str(value) if value is not None and str(value) else None

    @staticmethod
    def _require_uid(value: str | None, resource_name: str) -> str:
        if value is None:
            raise AssertionError(f"{resource_name} has no UID")
        return value

    @staticmethod
    def _service_ports_body(
        ports: list[client.V1ServicePort],
    ) -> list[dict[str, Any]]:
        body: list[dict[str, Any]] = []
        for item in ports:
            port = {
                "name": item.name,
                "port": item.port,
                "protocol": item.protocol,
                "targetPort": item.target_port,
            }
            if item.app_protocol is not None:
                port["appProtocol"] = item.app_protocol
            if item.node_port is not None:
                port["nodePort"] = item.node_port
            body.append(port)
        return body

    @staticmethod
    def _workspace_custom_resource_ready(resource: dict[str, Any] | None) -> bool:
        if resource is None:
            return False
        metadata = resource.get("metadata") or {}
        spec = resource.get("spec") or {}
        status = resource.get("status") or {}
        components = status.get("components") or {}
        runtime_spec = spec.get("runtime") or {}
        runtime_status = components.get("runtime") or {}
        component_pairs = [
            (runtime_spec, runtime_status),
            (spec.get("browser") or {}, components.get("browser") or {}),
            (spec.get("canvas") or {}, components.get("canvas") or {}),
        ]
        required = [component_status for _, component_status in component_pairs]
        return bool(
            status.get("phase") == "Running"
            and status.get("observedGeneration") == metadata.get("generation")
            and runtime_spec.get("instanceId")
            and runtime_status.get("mountObservedRevision")
            == runtime_spec.get("mountRevision")
            and runtime_status.get("accessObservedRevision")
            == runtime_spec.get("accessRevision")
            and all(
                component_status.get("observedRevision")
                == component_spec.get("revision")
                for component_spec, component_status in component_pairs
            )
            and all(component.get("ready") is True for component in required)
            and (required[0].get("terminalReady") is True)
            and all(component.get("podUid") for component in required)
        )

    @staticmethod
    def _workspace_custom_resource_stopped(
        resource: dict[str, Any] | None,
        *,
        expected_runtime_instance_id: str,
    ) -> bool:
        if resource is None:
            return False
        metadata = resource.get("metadata") or {}
        spec = resource.get("spec") or {}
        status = resource.get("status") or {}
        runtime_spec = spec.get("runtime") or {}
        return bool(
            status.get("phase") == "Stopped"
            and status.get("observedGeneration") == metadata.get("generation")
            and runtime_spec.get("instanceId") == expected_runtime_instance_id
            and all(
                (spec.get(component) or {}).get("desiredState") == "Stopped"
                for component in ("runtime", "browser", "canvas")
            )
        )

    @staticmethod
    def _deployment_at_replicas(
        deployment: client.V1Deployment,
        replicas: int,
    ) -> bool:
        if deployment.spec.replicas != replicas:
            return False
        if deployment.status.observed_generation != deployment.metadata.generation:
            return False
        if replicas == 0:
            return not any(
                (
                    deployment.status.replicas,
                    deployment.status.ready_replicas,
                    deployment.status.available_replicas,
                )
            )
        return (deployment.status.ready_replicas or 0) >= replicas and (
            deployment.status.available_replicas or 0
        ) >= replicas

    @staticmethod
    def _require_observed_replica_count(
        replicas: Any,
        *,
        component: str,
    ) -> int:
        if not isinstance(replicas, int) or isinstance(replicas, bool) or replicas < 0:
            raise AssertionError(
                f"{component} reported an invalid replica count: {replicas!r}"
            )
        return replicas

    def _delete_pod_if_exists(self, name: str) -> None:
        try:
            self.core.delete_namespaced_pod(name, self.namespace)
        except ApiException as exc:
            if exc.status != 404:
                raise
        self._wait(
            lambda: self._pod_absent(name),
            lambda absent: absent,
            description=f"Pod {name} absent",
            timeout_seconds=120,
        )

    def _pod_absent(self, name: str) -> bool:
        try:
            self.core.read_namespaced_pod(name, self.namespace)
        except ApiException as exc:
            if exc.status == 404:
                return True
            raise
        return False

    @staticmethod
    def _pod_ready(pod: client.V1Pod) -> bool:
        return any(
            condition.type == "Ready" and condition.status == "True"
            for condition in (pod.status.conditions or [])
        )

    @staticmethod
    def _wait(
        read: Callable[[], Any],
        predicate: Callable[[Any], bool],
        *,
        description: str,
        timeout_seconds: float,
        interval_seconds: float = 1.0,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        last_value: Any = None
        while time.monotonic() < deadline:
            last_value = read()
            if predicate(last_value):
                return last_value
            time.sleep(interval_seconds)
        raise AssertionError(
            f"Timed out waiting for {description}; last observed={last_value!r}"
        )
