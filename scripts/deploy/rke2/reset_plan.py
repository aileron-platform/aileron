#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

NAMESPACE_OWNER_LABEL = "platform.aileron.dev/namespace-owner"
NAMESPACE_OWNER = "aileron-installer"

RESET_TARGETS = (
    ("workspace-system", "aileron"),
    ("aileron-turn-system", "aileron-turn"),
    ("aileron-identity-system", "aileron-identity"),
)

PV_DELETE_TIMEOUT = "10m"
PV_RESET_UID_LABEL = "platform.aileron.dev/reset-pv-uid"
NAMESPACE_RESET_UID_LABEL = "platform.aileron.dev/reset-namespace-uid"
NAMESPACE_RESET_RUN_LABEL = "platform.aileron.dev/reset-run-id"
EXECUTION_STATE_SCHEMA = "aileron-reset-execution-state/v3"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
KUBERNETES_LABEL_VALUE_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[-_.A-Za-z0-9]{0,61}[A-Za-z0-9])?$"
)

ALLOWED_NAMESPACED_RESOURCES = {
    ("v1", "ConfigMap"),
    ("v1", "Endpoints"),
    ("v1", "Event"),
    ("v1", "PersistentVolumeClaim"),
    ("v1", "Pod"),
    ("v1", "Secret"),
    ("v1", "Service"),
    ("v1", "ServiceAccount"),
    ("apps/v1", "DaemonSet"),
    ("apps/v1", "Deployment"),
    ("apps/v1", "ControllerRevision"),
    ("apps/v1", "ReplicaSet"),
    ("apps/v1", "StatefulSet"),
    ("batch/v1", "Job"),
    ("cilium.io/v2", "CiliumEndpoint"),
    ("cilium.io/v2", "CiliumEndpointSlice"),
    ("cilium.io/v2", "CiliumNetworkPolicy"),
    ("coordination.k8s.io/v1", "Lease"),
    ("discovery.k8s.io/v1", "EndpointSlice"),
    ("events.k8s.io/v1", "Event"),
    ("metrics.k8s.io/v1beta1", "PodMetrics"),
    ("networking.k8s.io/v1", "Ingress"),
    ("networking.k8s.io/v1", "NetworkPolicy"),
    ("platform.aileron.io/v1alpha1", "Workspace"),
    ("rbac.authorization.k8s.io/v1", "Role"),
    ("rbac.authorization.k8s.io/v1", "RoleBinding"),
}
RANCHER_APP_IDENTITY = ("catalog.cattle.io/v1", "App")
RESET_TARGET_RESOURCE_IDENTITIES = {
    RANCHER_APP_IDENTITY,
    ("platform.aileron.io/v1alpha1", "Workspace"),
}

SECRET_MATERIAL_KEYS = {
    "data",
    "stringData",
    "token",
    "password",
    "clientSecret",
    "privateKey",
}

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
RESET_INVENTORY_KEYS = (
    "namespaces",
    "releases",
    "resources",
    "persistentVolumes",
)
RESET_TARGET_SET_KEYS = (
    "context",
    "resetRunId",
    "namespaces",
    "releases",
    "resources",
    "persistentVolumes",
    "backendVerificationRequired",
    "actions",
)
CAUSAL_ROOT_REPORT_SECTIONS = ("suites", "offlineOidcConformance")


def _load_inventory_contract() -> tuple[Callable[..., dict[str, Any]], frozenset[str]]:
    module_path = SCRIPT_DIRECTORY / "collect_reset_inventory.py"
    spec = importlib.util.spec_from_file_location(
        "collect_reset_inventory", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reset inventory collector: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.collect_reset_inventory, frozenset(module.TARGET_STORAGE_CLASSES)


COLLECT_RESET_INVENTORY, TARGET_STORAGE_CLASSES = _load_inventory_contract()


def _load_local_module(name: str):
    module_path = SCRIPT_DIRECTORY / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reset dependency: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACCEPTANCE_CLUSTER = _load_local_module("acceptance_cluster")
ACCEPTANCE_EPOCH = _load_local_module("acceptance_epoch")
ACCEPTANCE_EVIDENCE = _load_local_module("acceptance_evidence")
ACCEPTANCE_SNAPSHOT = _load_local_module("acceptance_snapshot")
ACCEPTANCE_PRIVATE_IO = _load_local_module("acceptance_private_io")
KUBERNETES_REST = _load_local_module("kubernetes_rest")
PRIVATE_INPUT = _load_local_module("private_input")
BACKEND_ATTESTOR = _load_local_module("backend_attestor")
RUN_ID_PATTERN = ACCEPTANCE_PRIVATE_IO.RUN_ID


class ResetTransactionPaths(NamedTuple):
    acceptance_directory: Path
    transaction_directory: Path
    inventory_output: Path
    execution_state: Path
    execution_lock: Path


def _require_string(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{description} must be a non-empty string")
    return value


def _require_list(value: Any, description: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{description} must be an array")
    return value


def _format_utc_timestamp(value: datetime, description: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{description} must be an RFC3339 UTC timestamp")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _parse_utc_timestamp(value: Any, description: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{description} must be an RFC3339 UTC timestamp")
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{description} is invalid") from exc
    if (
        observed.tzinfo != timezone.utc
        or _format_utc_timestamp(observed, description) != value
    ):
        raise ValueError(f"{description} must use canonical UTC seconds")
    return observed


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _reject_secret_material(value: Any, path: str = "inventory") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in SECRET_MATERIAL_KEYS:
                raise ValueError(
                    f"{path} must contain non-secret metadata only; remove {key}"
                )
            _reject_secret_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_material(child, f"{path}[{index}]")


def _reject_symlink_components(path: Path, description: str) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"{description} is unreadable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{description} must not contain a symbolic link")


def _persistent_volume_identity(
    item: Any, *, target_namespaces: set[str]
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise TypeError("PersistentVolume inventory entries must be objects")
    if item.get("apiVersion") != "v1" or item.get("kind") != "PersistentVolume":
        raise ValueError("PersistentVolume identity must use v1/PersistentVolume")
    name = _require_string(item.get("name"), "PersistentVolume name")
    uid = _require_string(item.get("uid"), "PersistentVolume uid")
    resource_version = _require_string(
        item.get("resourceVersion"), "PersistentVolume resourceVersion"
    )
    labels = item.get("labels")
    if not isinstance(labels, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in labels.items()
    ):
        raise ValueError("PersistentVolume labels must be a string object")
    phase = _require_string(item.get("phase"), "PersistentVolume phase")
    if phase not in {"Available", "Bound", "Released", "Failed"}:
        raise ValueError(f"PersistentVolume phase is unsupported: {name}")
    storage_class_name = _require_string(
        item.get("storageClassName"), "PersistentVolume StorageClass"
    )
    if storage_class_name not in TARGET_STORAGE_CLASSES:
        raise ValueError(
            f"PersistentVolume StorageClass is not allowlisted: {storage_class_name}"
        )
    reclaim_policy = _require_string(
        item.get("reclaimPolicy"), "PersistentVolume reclaimPolicy"
    )
    if reclaim_policy not in {"Retain", "Delete"}:
        raise ValueError(
            "PersistentVolume reclaimPolicy must be Retain or Delete before reset: "
            f"{name}"
        )
    claim_ref = item.get("claimRef")
    normalized_claim_ref = None
    if claim_ref is not None:
        if not isinstance(claim_ref, dict):
            raise TypeError(f"PersistentVolume claimRef is invalid: {name}")
        claim_namespace = _require_string(
            claim_ref.get("namespace"), "PersistentVolume claimRef namespace"
        )
        if claim_namespace not in target_namespaces:
            raise ValueError(
                f"PersistentVolume claimRef must use a target namespace: {name}"
            )
        normalized_claim_ref = {
            "namespace": claim_namespace,
            "name": _require_string(
                claim_ref.get("name"), "PersistentVolume claimRef name"
            ),
            "uid": _require_string(
                claim_ref.get("uid"), "PersistentVolume claimRef uid"
            ),
        }
    backend_locator = item.get("backendLocator")
    if not isinstance(backend_locator, dict):
        raise TypeError(f"PersistentVolume backendLocator is required: {name}")
    locator_type = _require_string(
        backend_locator.get("type"), "PersistentVolume backendLocator type"
    )
    if locator_type == "csi":
        normalized_locator = {
            "type": "csi",
            "driver": _require_string(
                backend_locator.get("driver"), "CSI backend driver"
            ),
            "volumeHandle": _require_string(
                backend_locator.get("volumeHandle"), "CSI backend volumeHandle"
            ),
        }
    elif locator_type == "nfs":
        normalized_locator = {
            "type": "nfs",
            "server": _require_string(
                backend_locator.get("server"), "NFS backend server"
            ),
            "path": _require_string(backend_locator.get("path"), "NFS backend path"),
        }
    elif locator_type == "localPath":
        volume_source = _require_string(
            backend_locator.get("volumeSource"), "local backend volumeSource"
        )
        if volume_source not in {"local", "hostPath"}:
            raise ValueError("local backend volumeSource must be local or hostPath")
        normalized_locator = {
            "type": "localPath",
            "node": _require_string(backend_locator.get("node"), "local backend node"),
            "path": _require_string(backend_locator.get("path"), "local backend path"),
            "volumeSource": volume_source,
        }
    else:
        raise ValueError(f"PersistentVolume backendLocator type is unsupported: {name}")
    if backend_locator != normalized_locator:
        raise ValueError(f"PersistentVolume backendLocator is malformed: {name}")
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "name": name,
        "uid": uid,
        "resourceVersion": resource_version,
        "labels": labels,
        "phase": phase,
        "storageClassName": storage_class_name,
        "reclaimPolicy": reclaim_policy,
        "claimRef": normalized_claim_ref,
        "backendLocator": normalized_locator,
    }


def build_reset_plan(
    inventory: dict[str, Any],
    *,
    kubeconfig: Path,
    reset_run_id: str,
    allow_reset_guards: bool = False,
) -> dict[str, Any]:
    if not isinstance(inventory, dict):
        raise TypeError("inventory must be a JSON object")
    _reject_secret_material(inventory)

    context = _require_string(inventory.get("context"), "inventory context")
    if (
        RUN_ID_PATTERN.fullmatch(reset_run_id) is None
        or KUBERNETES_LABEL_VALUE_PATTERN.fullmatch(reset_run_id) is None
    ):
        raise ValueError("reset run ID is invalid")
    namespaces = _require_list(inventory.get("namespaces"), "inventory namespaces")
    releases = _require_list(inventory.get("releases"), "inventory releases")
    persistent_volume_entries = _require_list(
        inventory.get("persistentVolumes"), "inventory persistentVolumes"
    )
    resources = _require_list(inventory.get("resources"), "inventory resources")

    namespace_by_name: dict[str, dict[str, Any]] = {}
    target_namespaces = {namespace for namespace, _ in RESET_TARGETS}
    for item in namespaces:
        if not isinstance(item, dict):
            raise TypeError("namespace inventory entries must be objects")
        if set(item) != {"name", "uid", "resourceVersion", "labels"}:
            raise ValueError("namespace inventory identity is malformed")
        name = _require_string(item.get("name"), "namespace name")
        if name not in target_namespaces:
            raise ValueError(f"namespace is not an Aileron reset target: {name}")
        if name in namespace_by_name:
            raise ValueError(f"namespace inventory contains duplicate: {name}")
        uid = _require_string(item.get("uid"), "namespace uid")
        resource_version = _require_string(
            item.get("resourceVersion"), "namespace resourceVersion"
        )
        labels = item.get("labels")
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise ValueError("namespace labels must be a string object")
        if not allow_reset_guards and {
            NAMESPACE_RESET_UID_LABEL,
            NAMESPACE_RESET_RUN_LABEL,
        }.intersection(labels):
            raise ValueError("namespace inventory already contains reset guard labels")
        namespace_by_name[name] = {
            "name": name,
            "uid": uid,
            "resourceVersion": resource_version,
            "labels": labels,
        }

    existing_targets = target_namespaces.intersection(namespace_by_name)
    for namespace in existing_targets:
        labels = namespace_by_name[namespace]["labels"]
        if labels.get(NAMESPACE_OWNER_LABEL) != NAMESPACE_OWNER:
            raise ValueError(
                f"namespace ownership mismatch: {namespace} must be owned by "
                f"{NAMESPACE_OWNER}"
            )

    release_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_releases = {(namespace, release) for namespace, release in RESET_TARGETS}
    for item in releases:
        if not isinstance(item, dict):
            raise TypeError("release inventory entries must be objects")
        if set(item) != {"name", "namespace"}:
            raise ValueError("release inventory identity is malformed")
        name = _require_string(item.get("name"), "release name")
        namespace = _require_string(item.get("namespace"), "release namespace")
        if namespace not in target_namespaces:
            raise ValueError(
                f"release namespace is not an Aileron reset target: {namespace}"
            )
        identity = (namespace, name)
        if identity in release_by_identity:
            raise ValueError(
                f"release inventory contains duplicate: {namespace}/{name}"
            )
        release_by_identity[identity] = item
        if namespace in existing_targets and identity not in allowed_releases:
            raise ValueError(
                f"release is not allowlisted for reset: {namespace}/{name}"
            )

    canonical_resources: list[dict[str, Any]] = []
    resource_identities: set[tuple[str, str, str, str]] = set()
    for item in resources:
        if not isinstance(item, dict):
            raise TypeError("resource inventory entries must be objects")
        base_keys = {
            "apiVersion",
            "kind",
            "namespace",
            "name",
            "uid",
            "resourceVersion",
        }
        identity_hint = (item.get("apiVersion"), item.get("kind"))
        expected_keys = (
            base_keys | {"ownerReferences"}
            if identity_hint == RANCHER_APP_IDENTITY
            else base_keys
        )
        if set(item) != expected_keys:
            if identity_hint == RANCHER_APP_IDENTITY:
                raise ValueError("Rancher App resource identity is malformed")
            raise ValueError("resource inventory identity is malformed")
        api_version = _require_string(item.get("apiVersion"), "resource apiVersion")
        kind = _require_string(item.get("kind"), "resource kind")
        name = _require_string(item.get("name"), "resource name")
        namespace = _require_string(item.get("namespace"), "resource namespace")
        uid = _require_string(item.get("uid"), "resource uid")
        resource_version = _require_string(
            item.get("resourceVersion"), "resource resourceVersion"
        )
        if namespace not in existing_targets:
            raise ValueError(
                f"resource namespace is not an existing Aileron reset target: {namespace}"
            )
        identity = (api_version, kind, namespace, name)
        if identity in resource_identities:
            raise ValueError(
                f"resource inventory contains duplicate: {api_version}/{kind}/{namespace}/{name}"
            )
        resource_identities.add(identity)
        canonical_resource: dict[str, Any] = {
            "apiVersion": api_version,
            "kind": kind,
            "namespace": namespace,
            "name": name,
            "uid": uid,
            "resourceVersion": resource_version,
        }
        if (api_version, kind) == RANCHER_APP_IDENTITY:
            owners = item.get("ownerReferences")
            if (
                (namespace, name) not in allowed_releases
                or (namespace, name) not in release_by_identity
                or not isinstance(owners, list)
                or len(owners) != 1
            ):
                raise ValueError("Rancher App is not bound to an allowlisted release")
            owner = owners[0]
            if not isinstance(owner, dict) or set(owner) != {
                "apiVersion",
                "kind",
                "namespace",
                "name",
            }:
                raise ValueError("Rancher App Helm owner identity is malformed")
            owner_name = _require_string(owner.get("name"), "Rancher App owner name")
            owner_prefix = f"sh.helm.release.v1.{name}.v"
            revision = owner_name.removeprefix(owner_prefix)
            if (
                owner.get("apiVersion") != "v1"
                or owner.get("kind") != "Secret"
                or owner.get("namespace") != namespace
                or not owner_name.startswith(owner_prefix)
                or not revision.isdigit()
                or int(revision) < 1
            ):
                raise ValueError("Rancher App Helm release Secret owner is invalid")
            canonical_resource["ownerReferences"] = [
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "namespace": namespace,
                    "name": owner_name,
                }
            ]
        elif (api_version, kind) not in ALLOWED_NAMESPACED_RESOURCES:
            raise ValueError(
                "resource kind is not allowlisted for Aileron reset: "
                f"{api_version}/{kind}"
            )
        canonical_resources.append(canonical_resource)
    canonical_resources.sort(
        key=lambda item: (
            item["namespace"],
            item["kind"],
            item["apiVersion"],
            item["name"],
        )
    )

    persistent_volumes: list[dict[str, Any]] = []
    persistent_volume_names: set[str] = set()
    for item in persistent_volume_entries:
        persistent_volume = _persistent_volume_identity(
            item, target_namespaces=target_namespaces
        )
        if persistent_volume["name"] in persistent_volume_names:
            raise ValueError(
                "PersistentVolume inventory contains duplicate: "
                f"{persistent_volume['name']}"
            )
        persistent_volume_names.add(persistent_volume["name"])
        persistent_volumes.append(persistent_volume)
    persistent_volumes.sort(key=lambda item: item["name"])

    for persistent_volume in persistent_volumes:
        if not allow_reset_guards and PV_RESET_UID_LABEL in persistent_volume["labels"]:
            raise ValueError(
                "PersistentVolume inventory already contains reset guard label"
            )

    actions: list[dict[str, str]] = []
    for persistent_volume in persistent_volumes:
        actions.append(
            {
                "id": f"guardPersistentVolume/{persistent_volume['name']}",
                "kind": "guardPersistentVolume",
                "name": persistent_volume["name"],
            }
        )
    for namespace in sorted(existing_targets):
        actions.append(
            {
                "id": f"guardNamespace/{namespace}",
                "kind": "guardNamespace",
                "name": namespace,
            }
        )
    for persistent_volume in persistent_volumes:
        if persistent_volume["phase"] in {"Available", "Released", "Failed"}:
            actions.append(
                {
                    "id": f"requestDeletePersistentVolume/{persistent_volume['name']}",
                    "kind": "requestDeletePersistentVolume",
                    "name": persistent_volume["name"],
                }
            )
    for resource in canonical_resources:
        if (
            resource["namespace"] == "workspace-system"
            and resource["apiVersion"] == "platform.aileron.io/v1alpha1"
            and resource["kind"] == "Workspace"
        ):
            actions.append(
                {
                    "id": (f"deleteWorkspace/workspace-system/{resource['name']}"),
                    "kind": "deleteWorkspace",
                    "name": resource["name"],
                    "namespace": "workspace-system",
                }
            )
    for namespace, _ in RESET_TARGETS:
        if namespace in existing_targets:
            actions.append(
                {
                    "id": f"deleteNamespace/{namespace}",
                    "kind": "deleteNamespace",
                    "name": namespace,
                }
            )
    for persistent_volume in persistent_volumes:
        actions.append(
            {
                "id": f"waitPersistentVolumeAbsent/{persistent_volume['name']}",
                "kind": "waitPersistentVolumeAbsent",
                "name": persistent_volume["name"],
            }
        )

    return {
        "context": context,
        "resetRunId": reset_run_id,
        "namespaces": [namespace_by_name[name] for name in sorted(existing_targets)],
        "releases": [
            {"name": name, "namespace": namespace}
            for namespace, name in sorted(release_by_identity)
            if namespace in existing_targets
        ],
        "resources": canonical_resources,
        "persistentVolumes": persistent_volumes,
        "backendVerificationRequired": [
            {
                "persistentVolume": persistent_volume["name"],
                "uid": persistent_volume["uid"],
                "storageClassName": persistent_volume["storageClassName"],
                "backendLocator": persistent_volume["backendLocator"],
            }
            for persistent_volume in persistent_volumes
        ],
        "actions": actions,
    }


def effective_reset_target_set(plan: dict[str, Any]) -> dict[str, Any]:
    """Return reset identities that must remain stable before mutation.

    The signed plan retains the complete inventory for auditability, but
    controller-owned resources such as Pods, Events, and metrics naturally
    churn while causal-root checks run.  Namespace deletion already scopes
    those resources, so only resources with an explicit reset action are part
    of the pre-mutation target set.
    """

    def without_resource_version(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "resourceVersion"}

    explicit_resources = [
        without_resource_version(item)
        for item in plan["resources"]
        if (item["apiVersion"], item["kind"]) in RESET_TARGET_RESOURCE_IDENTITIES
    ]
    explicit_resources.sort(
        key=lambda item: (
            item["namespace"],
            item["kind"],
            item["apiVersion"],
            item["name"],
        )
    )

    return {
        "context": plan["context"],
        "resetRunId": plan["resetRunId"],
        "namespaces": [
            {key: item[key] for key in ("name", "uid", "labels")}
            for item in plan["namespaces"]
        ],
        "releases": [dict(item) for item in plan["releases"]],
        "resources": explicit_resources,
        "persistentVolumes": [
            without_resource_version(item) for item in plan["persistentVolumes"]
        ],
        "backendVerificationRequired": [
            dict(item) for item in plan["backendVerificationRequired"]
        ],
        "actions": [dict(item) for item in plan["actions"]],
    }


def _subprocess_runner(
    command: list[str], *, environment: dict[str, str] | None = None
) -> str:
    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        timeout=660,
        env={**os.environ, **(environment or {})},
    )
    return result.stdout


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _plan_sha256(plan: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(plan)).hexdigest()


def _action_by_id(plan: dict[str, Any]) -> dict[str, dict[str, str]]:
    actions = _require_list(plan.get("actions"), "plan actions")
    by_id: dict[str, dict[str, str]] = {}
    allowed_shapes = {
        "guardPersistentVolume": {"id", "kind", "name"},
        "guardNamespace": {"id", "kind", "name"},
        "requestDeletePersistentVolume": {"id", "kind", "name"},
        "deleteWorkspace": {"id", "kind", "name", "namespace"},
        "deleteNamespace": {"id", "kind", "name"},
        "waitPersistentVolumeAbsent": {"id", "kind", "name"},
    }
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("reset action must be an object")
        kind = action.get("kind")
        action_id = action.get("id")
        if (
            kind not in allowed_shapes
            or set(action) != allowed_shapes[kind]
            or not isinstance(action_id, str)
            or not action_id
            or any(not isinstance(value, str) or not value for value in action.values())
            or action_id in by_id
        ):
            raise ValueError("reset action identity is invalid")
        by_id[action_id] = action
    return by_id


def _canonical_approved_plan(
    plan: dict[str, Any], *, kubeconfig: Path
) -> dict[str, Any]:
    reset_run_id = _require_string(plan.get("resetRunId"), "plan reset run ID")
    inventory = {
        "context": plan.get("context"),
        **{key: plan.get(key) for key in RESET_INVENTORY_KEYS},
    }
    canonical = build_reset_plan(
        inventory,
        kubeconfig=kubeconfig,
        reset_run_id=reset_run_id,
    )
    if canonical != plan:
        raise ValueError("reset plan does not match its canonical signed inventory")
    _action_by_id(canonical)
    return canonical


def _load_signed_backend_inputs(
    *,
    plan: dict[str, Any],
    kubeconfig: Path,
    expected_commit: str,
    reset_snapshot_sha256: str,
) -> Any:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("reset backend cleanup commit is invalid")
    inputs = BACKEND_ATTESTOR.load_signed_backend_attestor_inputs(
        context=plan["context"],
        commit=expected_commit,
        expected_run_id=plan["resetRunId"],
        expected_snapshot_sha256=reset_snapshot_sha256,
    )
    if inputs.kubeconfig != kubeconfig:
        raise ValueError("signed backend cleanup kubeconfig identity changed")
    expected_targets = [
        (
            persistent_volume["name"],
            persistent_volume["uid"],
            BACKEND_ATTESTOR.locator_sha256(persistent_volume["backendLocator"]),
        )
        for persistent_volume in plan["persistentVolumes"]
    ]
    observed_targets = [
        (
            target.persistent_volume_name,
            target.persistent_volume_uid,
            target.locator_sha256,
        )
        for target in inputs.cleanup_targets
    ]
    if observed_targets != expected_targets:
        raise ValueError("signed backend cleanup target set does not match reset plan")
    BACKEND_ATTESTOR.validate_signed_backend_cleanup_preconditions(inputs)
    return inputs


def _backend_target_state_documents(inputs: Any) -> list[dict[str, Any]]:
    return [
        {
            "persistentVolume": {
                "name": target.persistent_volume_name,
                "uid": target.persistent_volume_uid,
            },
            "locatorSha256": target.locator_sha256,
            "status": "pending",
            "result": None,
        }
        for target in inputs.cleanup_targets
    ]


def _backend_cleanup_aggregate(
    *,
    inputs: Any,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schemaVersion": "aileron-backend-cleanup-results/v1",
        "commit": inputs.commit,
        "runId": inputs.run_id,
        "snapshotSha256": inputs.snapshot_sha256,
        "profileRawSha256": inputs.profile.raw_sha256,
        "profileCanonicalSha256": inputs.profile.canonical_sha256,
        "imageInventorySha256": inputs.image.inventory_sha256,
        "results": results,
        "allAbsent": all(
            result.get("attestation", {}).get("absent") is True for result in results
        ),
    }


def _execution_state_document(
    *,
    plan: dict[str, Any],
    reset_snapshot_sha256: str,
    backend_inputs: Any,
    causal_root_reports: dict[str, Any],
) -> dict[str, Any]:
    _validate_causal_root_receipt(causal_root_reports)
    return {
        "schemaVersion": EXECUTION_STATE_SCHEMA,
        "context": plan["context"],
        "resetRunId": plan["resetRunId"],
        "resetSnapshotSha256": reset_snapshot_sha256,
        "planSha256": _plan_sha256(plan),
        "causalRootReports": causal_root_reports,
        "actions": {action["id"]: {"status": "pending"} for action in plan["actions"]},
        "backendCleanup": {
            "targets": _backend_target_state_documents(backend_inputs),
            "aggregate": {"status": "pending", "sha256": None},
        },
    }


def _validate_causal_root_receipt(receipt: Any) -> datetime:
    expected_keys = {"validatedAt", *CAUSAL_ROOT_REPORT_SECTIONS}
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise ValueError("reset causal root receipt shape is invalid")
    validated_at = _parse_utc_timestamp(
        receipt.get("validatedAt"),
        "reset causal root receipt validatedAt",
    )
    for section in CAUSAL_ROOT_REPORT_SECTIONS:
        report = receipt.get(section)
        if (
            not isinstance(report, dict)
            or set(report) != {"sha256", "finishedAt"}
            or not isinstance(report.get("sha256"), str)
            or DIGEST_PATTERN.fullmatch(report["sha256"]) is None
        ):
            raise ValueError("reset causal root receipt report shape is invalid")
        finished_at = _parse_utc_timestamp(
            report.get("finishedAt"),
            f"reset causal root receipt {section} finishedAt",
        )
        if finished_at > validated_at:
            raise ValueError("reset causal root receipt finishedAt exceeds validatedAt")
    return validated_at


def _read_execution_state(path: Path) -> dict[str, Any] | None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("reset execution state is unreadable") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
    ):
        raise ValueError(
            "reset execution state must be an owner-controlled mode 0600 regular file"
        )
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        raw = os.read(descriptor, 4 * 1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("reset execution state is too large")
    try:
        state = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("reset execution state is invalid JSON") from exc
    if not isinstance(state, dict):
        raise ValueError("reset execution state shape is invalid")
    return state


def _validate_execution_state_identity(
    state: dict[str, Any],
    *,
    plan: dict[str, Any],
    reset_snapshot_sha256: str,
) -> datetime:
    expected_keys = {
        "schemaVersion",
        "context",
        "resetRunId",
        "resetSnapshotSha256",
        "planSha256",
        "causalRootReports",
        "actions",
        "backendCleanup",
    }
    if set(state) != expected_keys:
        raise ValueError("reset execution state shape is invalid")
    expected_identity = {
        "schemaVersion": EXECUTION_STATE_SCHEMA,
        "context": plan["context"],
        "resetRunId": plan["resetRunId"],
        "resetSnapshotSha256": reset_snapshot_sha256,
        "planSha256": _plan_sha256(plan),
    }
    for key, expected_value in expected_identity.items():
        if state.get(key) != expected_value:
            raise ValueError("reset execution state identity does not match")
    return _validate_causal_root_receipt(state.get("causalRootReports"))


def _validate_execution_state_document(
    state: dict[str, Any],
    *,
    plan: dict[str, Any],
    reset_snapshot_sha256: str,
    backend_inputs: Any,
    causal_root_reports: dict[str, Any],
) -> dict[str, Any]:
    expected = _execution_state_document(
        plan=plan,
        reset_snapshot_sha256=reset_snapshot_sha256,
        backend_inputs=backend_inputs,
        causal_root_reports=causal_root_reports,
    )
    _validate_execution_state_identity(
        state,
        plan=plan,
        reset_snapshot_sha256=reset_snapshot_sha256,
    )
    if state.get("causalRootReports") != expected["causalRootReports"]:
        raise ValueError("reset causal root receipt does not match")
    actions = state.get("actions")
    if not isinstance(actions, dict) or set(actions) != set(expected["actions"]):
        raise ValueError("reset execution state action set does not match")
    for progress in actions.values():
        if (
            not isinstance(progress, dict)
            or set(progress) != {"status"}
            or progress["status"] not in {"pending", "started", "completed"}
        ):
            raise ValueError("reset execution state action status is invalid")
    backend_cleanup = state.get("backendCleanup")
    expected_cleanup = expected["backendCleanup"]
    if (
        not isinstance(backend_cleanup, dict)
        or set(backend_cleanup) != {"targets", "aggregate"}
        or not isinstance(backend_cleanup.get("targets"), list)
        or len(backend_cleanup["targets"]) != len(expected_cleanup["targets"])
    ):
        raise ValueError("reset backend cleanup journal shape is invalid")
    for actual, expected_target in zip(
        backend_cleanup["targets"],
        expected_cleanup["targets"],
    ):
        if (
            not isinstance(actual, dict)
            or set(actual) != {"persistentVolume", "locatorSha256", "status", "result"}
            or actual.get("persistentVolume") != expected_target["persistentVolume"]
            or actual.get("locatorSha256") != expected_target["locatorSha256"]
            or actual.get("status") not in {"pending", "started", "completed"}
        ):
            raise ValueError("reset backend cleanup target journal is invalid")
        if actual["status"] == "completed":
            actual["result"] = BACKEND_ATTESTOR.validate_backend_cleanup_target_result(
                actual.get("result"),
                inputs=backend_inputs,
                persistent_volume_name=actual["persistentVolume"]["name"],
                persistent_volume_uid=actual["persistentVolume"]["uid"],
            )
        elif actual.get("result") is not None:
            raise ValueError("incomplete backend cleanup target has a result")
    aggregate = backend_cleanup.get("aggregate")
    if (
        not isinstance(aggregate, dict)
        or set(aggregate) != {"status", "sha256"}
        or aggregate.get("status") not in {"pending", "completed"}
    ):
        raise ValueError("reset backend cleanup aggregate journal is invalid")
    aggregate_status = aggregate["status"]
    aggregate_sha256 = aggregate.get("sha256")
    valid_pending = aggregate_status == "pending" and aggregate_sha256 is None
    valid_completed = (
        aggregate_status == "completed"
        and isinstance(aggregate_sha256, str)
        and DIGEST_PATTERN.fullmatch(aggregate_sha256) is not None
    )
    if not valid_pending and not valid_completed:
        raise ValueError("reset backend cleanup aggregate journal is invalid")
    return state


def _execution_state_has_durable_progress(state: dict[str, Any]) -> bool:
    return (
        any(
            progress["status"] in {"started", "completed"}
            for progress in state["actions"].values()
        )
        or any(
            target["status"] in {"started", "completed"}
            for target in state["backendCleanup"]["targets"]
        )
        or state["backendCleanup"]["aggregate"]["status"] == "completed"
    )


def _progress_started(state: dict[str, Any], action_id: str) -> bool:
    return state["actions"][action_id]["status"] in {"started", "completed"}


def _phase_progression(original: str, current: str) -> bool:
    allowed = {
        "Available": {"Available", "Failed"},
        "Bound": {"Bound", "Released", "Failed"},
        "Released": {"Released", "Failed"},
        "Failed": {"Failed"},
    }
    return current in allowed[original]


def _reconcile_live_progress(
    *, plan: dict[str, Any], live_plan: dict[str, Any], state: dict[str, Any]
) -> None:
    approved_namespaces = {item["name"]: item for item in plan["namespaces"]}
    live_namespaces = {item["name"]: item for item in live_plan["namespaces"]}
    if not set(live_namespaces).issubset(approved_namespaces):
        raise ValueError("live reset inventory contains an unapproved target namespace")
    for name, approved in approved_namespaces.items():
        action_id = f"guardNamespace/{name}"
        started = _progress_started(state, action_id)
        live = live_namespaces.get(name)
        if live is None:
            if not started:
                raise ValueError("unstarted reset namespace is absent")
            continue
        if live["uid"] != approved["uid"]:
            raise ValueError("reset namespace UID was replaced")
        if not started:
            if live != approved:
                raise ValueError("unguarded reset namespace drifted")
            continue
        guarded = {
            **approved,
            "resourceVersion": live["resourceVersion"],
            "labels": {
                **approved["labels"],
                NAMESPACE_RESET_UID_LABEL: approved["uid"],
                NAMESPACE_RESET_RUN_LABEL: plan["resetRunId"],
            },
        }
        status = state["actions"][action_id]["status"]
        if live != guarded and not (status == "started" and live == approved):
            raise ValueError("guarded reset namespace identity drifted")

    approved_pvs = {item["name"]: item for item in plan["persistentVolumes"]}
    live_pvs = {item["name"]: item for item in live_plan["persistentVolumes"]}
    if not set(live_pvs).issubset(approved_pvs):
        raise ValueError("live reset inventory contains an unapproved PersistentVolume")
    for name, approved in approved_pvs.items():
        action_id = f"guardPersistentVolume/{name}"
        started = _progress_started(state, action_id)
        live = live_pvs.get(name)
        if live is None:
            if not started:
                raise ValueError("unstarted reset PersistentVolume is absent")
            continue
        if not started:
            if live != approved:
                raise ValueError("unguarded reset PersistentVolume drifted")
            continue
        immutable_keys = (
            "apiVersion",
            "kind",
            "name",
            "uid",
            "storageClassName",
            "claimRef",
            "backendLocator",
        )
        if any(live[key] != approved[key] for key in immutable_keys):
            raise ValueError("guarded reset PersistentVolume identity drifted")
        expected_labels = {
            **approved["labels"],
            PV_RESET_UID_LABEL: approved["uid"],
        }
        guarded = (
            live["labels"] == expected_labels
            and live["reclaimPolicy"] == "Delete"
            and _phase_progression(approved["phase"], live["phase"])
        )
        status = state["actions"][action_id]["status"]
        if not guarded and not (status == "started" and live == approved):
            raise ValueError("guarded reset PersistentVolume state drifted")

    approved_resources = plan["resources"]
    live_resources = live_plan["resources"]
    approved_releases = plan["releases"]
    live_releases = live_plan["releases"]
    approved_target_resources = effective_reset_target_set(plan)["resources"]
    live_target_resources = effective_reset_target_set(live_plan)["resources"]
    for namespace in approved_namespaces:
        namespace_guarded = _progress_started(state, f"guardNamespace/{namespace}")
        if namespace_guarded:
            continue
        approved_targets = [
            item for item in approved_target_resources if item["namespace"] == namespace
        ]
        live_targets = [
            item for item in live_target_resources if item["namespace"] == namespace
        ]
        if live_targets != approved_targets:
            raise ValueError("unguarded reset namespace resources drifted")
        if [item for item in live_releases if item["namespace"] == namespace] != [
            item for item in approved_releases if item["namespace"] == namespace
        ]:
            raise ValueError("unguarded reset namespace releases drifted")

    approved_workspaces = {
        (item["namespace"], item["name"]): item
        for item in approved_resources
        if item["apiVersion"] == "platform.aileron.io/v1alpha1"
        and item["kind"] == "Workspace"
    }
    for live in live_resources:
        if (
            live["apiVersion"] != "platform.aileron.io/v1alpha1"
            or live["kind"] != "Workspace"
        ):
            continue
        approved = approved_workspaces.get((live["namespace"], live["name"]))
        if approved is not None and live["uid"] != approved["uid"]:
            raise ValueError("signed reset Workspace UID was replaced")


def _persistent_volume(plan: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in plan["persistentVolumes"] if item["name"] == name]
    if len(matches) != 1:
        raise ValueError("reset action PersistentVolume target is invalid")
    return matches[0]


def _namespace(plan: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in plan["namespaces"] if item["name"] == name]
    if len(matches) != 1:
        raise ValueError("reset action namespace target is invalid")
    return matches[0]


def _workspace(plan: dict[str, Any], *, namespace: str, name: str) -> dict[str, Any]:
    matches = [
        item
        for item in plan["resources"]
        if item["apiVersion"] == "platform.aileron.io/v1alpha1"
        and item["kind"] == "Workspace"
        and item["namespace"] == namespace
        and item["name"] == name
    ]
    if len(matches) != 1:
        raise ValueError("reset action Workspace target is invalid")
    return matches[0]


def _command_for_action(
    action: dict[str, str], *, plan: dict[str, Any], kubeconfig: Path
) -> list[str]:
    context = plan["context"]
    kubectl = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context]
    kind = action["kind"]
    name = action["name"]
    if kind == "guardPersistentVolume":
        persistent_volume = _persistent_volume(plan, name)
        labels = {
            **persistent_volume["labels"],
            PV_RESET_UID_LABEL: persistent_volume["uid"],
        }
        patch: list[dict[str, Any]] = [
            {"op": "test", "path": "/metadata/uid", "value": persistent_volume["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": persistent_volume["resourceVersion"],
            },
            {"op": "add", "path": "/metadata/labels", "value": labels},
        ]
        if persistent_volume["reclaimPolicy"] == "Retain":
            patch.append(
                {
                    "op": "replace",
                    "path": "/spec/persistentVolumeReclaimPolicy",
                    "value": "Delete",
                }
            )
        return [
            *kubectl,
            "patch",
            "persistentvolume",
            name,
            "--type=json",
            "--patch",
            json.dumps(patch, separators=(",", ":"), sort_keys=True),
        ]
    if kind == "guardNamespace":
        namespace = _namespace(plan, name)
        labels = {
            **namespace["labels"],
            NAMESPACE_RESET_UID_LABEL: namespace["uid"],
            NAMESPACE_RESET_RUN_LABEL: plan["resetRunId"],
        }
        patch = [
            {"op": "test", "path": "/metadata/uid", "value": namespace["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": namespace["resourceVersion"],
            },
            {"op": "add", "path": "/metadata/labels", "value": labels},
        ]
        return [
            *kubectl,
            "patch",
            "namespace",
            name,
            "--type=json",
            "--patch",
            json.dumps(patch, separators=(",", ":"), sort_keys=True),
        ]
    if kind in {
        "requestDeletePersistentVolume",
        "deleteWorkspace",
        "deleteNamespace",
    }:
        raise ValueError("reset delete action must use Kubernetes REST")
    if kind == "waitPersistentVolumeAbsent":
        return [
            *kubectl,
            "wait",
            "--for=delete",
            f"persistentvolume/{name}",
            f"--timeout={PV_DELETE_TIMEOUT}",
        ]
    raise ValueError("reset action kind is unsupported")


def _action_satisfied(
    action: dict[str, str], *, plan: dict[str, Any], live_plan: dict[str, Any]
) -> bool:
    kind = action["kind"]
    name = action["name"]
    if kind == "guardNamespace":
        approved = _namespace(plan, name)
        live = next(
            (item for item in live_plan["namespaces"] if item["name"] == name), None
        )
        return live is None or live["labels"] == {
            **approved["labels"],
            NAMESPACE_RESET_UID_LABEL: approved["uid"],
            NAMESPACE_RESET_RUN_LABEL: plan["resetRunId"],
        }
    if kind == "guardPersistentVolume":
        approved = _persistent_volume(plan, name)
        live = next(
            (item for item in live_plan["persistentVolumes"] if item["name"] == name),
            None,
        )
        return live is None or (
            live["labels"]
            == {**approved["labels"], PV_RESET_UID_LABEL: approved["uid"]}
            and live["reclaimPolicy"] == "Delete"
        )
    if kind in {"requestDeletePersistentVolume", "waitPersistentVolumeAbsent"}:
        return not any(item["name"] == name for item in live_plan["persistentVolumes"])
    if kind == "deleteWorkspace":
        approved = _workspace(plan, namespace=action["namespace"], name=name)
        return not any(
            item["apiVersion"] == approved["apiVersion"]
            and item["kind"] == approved["kind"]
            and item["namespace"] == approved["namespace"]
            and item["name"] == approved["name"]
            and item["uid"] == approved["uid"]
            for item in live_plan["resources"]
        )
    if kind == "deleteNamespace":
        return not any(item["name"] == name for item in live_plan["namespaces"])
    raise ValueError("reset action kind is unsupported")


def _prepare_private_execution_directory(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("reset execution path must be absolute")
    parent = path.parent
    _reject_symlink_components(parent, "reset execution directory")
    if not parent.exists():
        if not parent.parent.is_dir():
            raise ValueError("reset execution directory parent is unavailable")
        try:
            parent.mkdir(mode=0o700)
        except OSError as exc:
            raise ValueError("reset execution directory could not be created") from exc
    _reject_symlink_components(parent, "reset execution directory")
    try:
        metadata = os.lstat(parent)
        canonical = parent.resolve(strict=True) == parent
    except OSError as exc:
        raise ValueError("reset execution directory is unreadable") from exc
    if (
        not canonical
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise ValueError(
            "reset execution directory must be canonical, owner-controlled, and mode 0700"
        )


def _execution_lock_path(execution_state_path: Path) -> Path:
    return execution_state_path.with_name(f"{execution_state_path.name}.lock")


def _acquire_execution_lock(path: Path) -> int:
    _reject_symlink_components(path, "reset execution lock")
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ValueError("reset execution lock could not be opened") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
        ):
            raise ValueError(
                "reset execution lock must be an owner-controlled mode 0600 regular file"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another reset executor holds the execution lock") from exc
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _verify_reset_causal_roots(
    *,
    plan: dict[str, Any],
    kubeconfig: Path,
    expected_commit: str,
    reset_snapshot_sha256: str,
    validation_checkpoint: datetime | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    private_root = ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
    directory = private_root / "evidence" / expected_commit / plan["resetRunId"]
    try:
        trust = ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
            context=plan["context"],
            kubeconfig=kubeconfig,
        )
        epoch = ACCEPTANCE_EPOCH.load_deployment_epoch(
            directory=directory,
            private_root=private_root,
            key=trust.key,
            commit=expected_commit,
            cluster_uid=trust.cluster_uid,
            context=plan["context"],
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=plan["resetRunId"],
        )
        if epoch["resetSnapshotSha256"] != reset_snapshot_sha256:
            raise ValueError("reset causal root epoch snapshot does not match")
        checkpoint_timestamp = _format_utc_timestamp(
            validation_checkpoint if validation_checkpoint is not None else clock(),
            "reset causal root validatedAt",
        )
        checkpoint = _parse_utc_timestamp(
            checkpoint_timestamp,
            "reset causal root validatedAt",
        )
        epoch_created_at = _parse_utc_timestamp(
            epoch.get("createdAt"),
            "deployment epoch createdAt",
        )
        if checkpoint < epoch_created_at:
            raise ValueError("reset causal root validatedAt predates deployment epoch")
        ACCEPTANCE_SNAPSHOT.load_reset_snapshot(
            directory=directory,
            private_root=private_root,
            key=trust.key,
            context=plan["context"],
            commit=expected_commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
            expected_run_id=plan["resetRunId"],
            expected_snapshot_sha256=reset_snapshot_sha256,
        )
        contract = ACCEPTANCE_EVIDENCE.load_canonical_contract()
        receipt: dict[str, Any] = {"validatedAt": checkpoint_timestamp}
        for section in CAUSAL_ROOT_REPORT_SECTIONS:
            validated = ACCEPTANCE_EVIDENCE.validate_report_file(
                directory=directory,
                section=section,
                contract=contract,
                expected_commit=expected_commit,
                epoch=epoch,
                signing_key=trust.key,
                private_root=private_root,
                canonical_kubeconfig=directory / "kubeconfig",
                now=checkpoint,
                must_finish_by=checkpoint,
            )
            receipt[section] = {
                "sha256": validated["sha256"],
                "finishedAt": validated["finishedAt"],
            }
        _validate_causal_root_receipt(receipt)
        return receipt
    except (
        ACCEPTANCE_CLUSTER.AcceptanceClusterError,
        ACCEPTANCE_EPOCH.AcceptanceEpochError,
        ACCEPTANCE_SNAPSHOT.AcceptanceSnapshotError,
        ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
    ) as exc:
        raise ValueError("reset causal root reports are invalid") from exc


def execute_reset_plan(
    plan: dict[str, Any],
    *,
    kubeconfig: Path,
    execution_state_path: Path,
    expected_commit: str,
    reset_snapshot_sha256: str,
    execution_lock_path: Path | None = None,
    runner: Callable[[list[str]], str] = _subprocess_runner,
    delete_client: Any | None = None,
    postcondition_attempts: int = 6,
    postcondition_interval_seconds: float = 0.0,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("reset backend cleanup commit is invalid")
    if DIGEST_PATTERN.fullmatch(reset_snapshot_sha256) is None:
        raise ValueError("reset snapshot digest is invalid")
    if not execution_state_path.is_absolute():
        raise ValueError("reset execution state path must be absolute")
    lock_path = execution_lock_path or _execution_lock_path(execution_state_path)
    if not lock_path.is_absolute() or lock_path.parent != execution_state_path.parent:
        raise ValueError(
            "reset execution lock must be an absolute state-directory peer"
        )
    _prepare_private_execution_directory(execution_state_path)
    _reject_symlink_components(execution_state_path, "reset execution state path")
    descriptor = _acquire_execution_lock(lock_path)
    try:
        _execute_reset_plan_locked(
            plan,
            kubeconfig=kubeconfig,
            execution_state_path=execution_state_path,
            expected_commit=expected_commit,
            reset_snapshot_sha256=reset_snapshot_sha256,
            runner=runner,
            delete_client=delete_client,
            postcondition_attempts=postcondition_attempts,
            postcondition_interval_seconds=postcondition_interval_seconds,
            sleeper=sleeper,
            clock=clock,
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _execute_reset_plan_locked(
    plan: dict[str, Any],
    *,
    kubeconfig: Path,
    execution_state_path: Path,
    expected_commit: str,
    reset_snapshot_sha256: str,
    runner: Callable[[list[str]], str],
    delete_client: Any | None,
    postcondition_attempts: int,
    postcondition_interval_seconds: float,
    sleeper: Callable[[float], None],
    clock: Callable[[], datetime],
) -> None:
    if postcondition_attempts < 1 or postcondition_interval_seconds < 0:
        raise ValueError("reset postcondition polling configuration is invalid")
    plan = _canonical_approved_plan(plan, kubeconfig=kubeconfig)
    state = _read_execution_state(execution_state_path)
    validation_checkpoint = None
    backend_inputs = None
    causal_root_clock = clock
    durable_progress = False
    if state is not None:
        stored_validation_checkpoint = _validate_execution_state_identity(
            state,
            plan=plan,
            reset_snapshot_sha256=reset_snapshot_sha256,
        )
        resumed_at = _parse_utc_timestamp(
            _format_utc_timestamp(clock(), "reset resume clock"),
            "reset resume clock",
        )
        if stored_validation_checkpoint > resumed_at:
            raise ValueError("reset causal root validatedAt is in the future")
        backend_inputs = _load_signed_backend_inputs(
            plan=plan,
            kubeconfig=kubeconfig,
            expected_commit=expected_commit,
            reset_snapshot_sha256=reset_snapshot_sha256,
        )
        state = _validate_execution_state_document(
            state,
            plan=plan,
            reset_snapshot_sha256=reset_snapshot_sha256,
            backend_inputs=backend_inputs,
            causal_root_reports=state["causalRootReports"],
        )
        durable_progress = _execution_state_has_durable_progress(state)
        if durable_progress:
            validation_checkpoint = stored_validation_checkpoint

        def causal_root_clock() -> datetime:
            return resumed_at

    causal_root_reports = _verify_reset_causal_roots(
        plan=plan,
        kubeconfig=kubeconfig,
        expected_commit=expected_commit,
        reset_snapshot_sha256=reset_snapshot_sha256,
        validation_checkpoint=validation_checkpoint,
        clock=causal_root_clock,
    )
    if backend_inputs is None:
        backend_inputs = _load_signed_backend_inputs(
            plan=plan,
            kubeconfig=kubeconfig,
            expected_commit=expected_commit,
            reset_snapshot_sha256=reset_snapshot_sha256,
        )
    if state is not None:
        if durable_progress:
            state = _validate_execution_state_document(
                state,
                plan=plan,
                reset_snapshot_sha256=reset_snapshot_sha256,
                backend_inputs=backend_inputs,
                causal_root_reports=causal_root_reports,
            )
        else:
            state["causalRootReports"] = causal_root_reports
            state = _validate_execution_state_document(
                state,
                plan=plan,
                reset_snapshot_sha256=reset_snapshot_sha256,
                backend_inputs=backend_inputs,
                causal_root_reports=causal_root_reports,
            )
            _write_evidence(execution_state_path, state)
    live_inventory = COLLECT_RESET_INVENTORY(
        expected_context=plan["context"],
        kubeconfig=kubeconfig,
        runner=runner,
    )
    live_plan = build_reset_plan(
        live_inventory,
        kubeconfig=kubeconfig,
        reset_run_id=plan["resetRunId"],
        allow_reset_guards=True,
    )
    if state is None:
        approved_target_set = effective_reset_target_set(plan)
        live_target_set = effective_reset_target_set(live_plan)
        for target_key in RESET_TARGET_SET_KEYS:
            if live_target_set[target_key] != approved_target_set[target_key]:
                raise ValueError(
                    f"live reset target set drift before mutation: {target_key}"
                )
        state = _execution_state_document(
            plan=plan,
            reset_snapshot_sha256=reset_snapshot_sha256,
            backend_inputs=backend_inputs,
            causal_root_reports=causal_root_reports,
        )
        _write_evidence(execution_state_path, state)
    else:
        _reconcile_live_progress(plan=plan, live_plan=live_plan, state=state)

    for action in plan["actions"]:
        progress = state["actions"][action["id"]]
        if progress["status"] == "completed":
            continue
        if progress["status"] == "started" and _action_satisfied(
            action, plan=plan, live_plan=live_plan
        ):
            progress["status"] = "completed"
            _write_evidence(execution_state_path, state)
            continue
        progress["status"] = "started"
        _write_evidence(execution_state_path, state)
        action_error: Exception | None = None
        try:
            if action["kind"] in {
                "requestDeletePersistentVolume",
                "deleteWorkspace",
                "deleteNamespace",
            }:
                if delete_client is None:
                    delete_client = KUBERNETES_REST.load_kubernetes_delete_client(
                        kubeconfig=kubeconfig,
                        context=plan["context"],
                        credential_directory=execution_state_path.parent,
                        private_root=backend_inputs.private_root,
                    )
                _delete_with_preconditions(
                    action,
                    plan=plan,
                    live_plan=live_plan,
                    delete_client=delete_client,
                )
            else:
                runner(_command_for_action(action, plan=plan, kubeconfig=kubeconfig))
        except Exception as exc:
            action_error = exc
        current_plan: dict[str, Any] | None = None
        postcondition_error: Exception | None = None
        postcondition_proven = False
        attempts = (
            postcondition_attempts
            if action["kind"]
            in {"requestDeletePersistentVolume", "deleteWorkspace", "deleteNamespace"}
            else 1
        )
        for attempt in range(attempts):
            try:
                current_inventory = COLLECT_RESET_INVENTORY(
                    expected_context=plan["context"],
                    kubeconfig=kubeconfig,
                    runner=runner,
                )
                current_plan = build_reset_plan(
                    current_inventory,
                    kubeconfig=kubeconfig,
                    reset_run_id=plan["resetRunId"],
                    allow_reset_guards=True,
                )
                _reconcile_live_progress(plan=plan, live_plan=current_plan, state=state)
                if _action_satisfied(action, plan=plan, live_plan=current_plan):
                    postcondition_proven = True
                    break
            except Exception as exc:
                postcondition_error = exc
            if attempt + 1 < attempts:
                sleeper(postcondition_interval_seconds)
        if current_plan is None or not postcondition_proven:
            raise ValueError(
                "reset action failed without an authoritative postcondition: "
                f"{action['id']}"
            ) from (action_error or postcondition_error)
        live_plan = current_plan
        progress["status"] = "completed"
        _write_evidence(execution_state_path, state)

    remaining = {key: live_plan[key] for key in RESET_INVENTORY_KEYS if live_plan[key]}
    if remaining:
        raise ValueError(
            "backend cleanup requires authoritative Kubernetes reset absence"
        )
    _execute_backend_cleanup(
        inputs=backend_inputs,
        state=state,
        execution_state_path=execution_state_path,
    )


def _backend_cleanup_results_path(
    *,
    inputs: Any,
    execution_state_path: Path,
) -> Path:
    expected = (
        inputs.private_root
        / "reset"
        / inputs.commit
        / inputs.run_id
        / "backend-cleanup-results.json"
    )
    actual = execution_state_path.with_name("backend-cleanup-results.json")
    if actual != expected:
        raise ValueError("backend cleanup aggregate path is not canonical")
    return actual


def _write_backend_cleanup_aggregate(
    *,
    inputs: Any,
    execution_state_path: Path,
    aggregate: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    path = _backend_cleanup_results_path(
        inputs=inputs,
        execution_state_path=execution_state_path,
    )
    content = _canonical_bytes(aggregate) + b"\n"
    PRIVATE_INPUT.write_private_snapshot(
        destination=path,
        content=content,
        description="backend cleanup aggregate",
        private_root=inputs.private_root,
        allow_existing_exact=True,
    )
    validated = BACKEND_ATTESTOR.load_backend_cleanup_results(inputs)
    if validated != aggregate:
        raise ValueError("backend cleanup aggregate read-back changed")
    return validated, hashlib.sha256(content).hexdigest()


def _execute_backend_cleanup(
    *,
    inputs: Any,
    state: dict[str, Any],
    execution_state_path: Path,
) -> None:
    cleanup_state = state["backendCleanup"]
    target_states = cleanup_state["targets"]
    if cleanup_state["aggregate"]["status"] == "completed":
        if any(target["status"] != "completed" for target in target_states):
            raise ValueError(
                "completed backend cleanup aggregate has incomplete targets"
            )
        aggregate = _backend_cleanup_aggregate(
            inputs=inputs,
            results=[target["result"] for target in target_states],
        )
        aggregate = BACKEND_ATTESTOR.validate_backend_cleanup_results(
            aggregate,
            inputs=inputs,
        )
        loaded = BACKEND_ATTESTOR.load_backend_cleanup_results(inputs)
        content_sha256 = hashlib.sha256(_canonical_bytes(loaded) + b"\n").hexdigest()
        if (
            loaded != aggregate
            or content_sha256 != cleanup_state["aggregate"]["sha256"]
        ):
            raise ValueError("completed backend cleanup aggregate changed")
        return

    for target_state in target_states:
        if target_state["status"] == "completed":
            continue
        target_state["status"] = "started"
        target_state["result"] = None
        _write_evidence(execution_state_path, state)
        persistent_volume = target_state["persistentVolume"]
        result = BACKEND_ATTESTOR.execute_signed_backend_cleanup_target(
            inputs,
            persistent_volume_name=persistent_volume["name"],
            persistent_volume_uid=persistent_volume["uid"],
        )
        result = BACKEND_ATTESTOR.validate_backend_cleanup_target_result(
            result,
            inputs=inputs,
            persistent_volume_name=persistent_volume["name"],
            persistent_volume_uid=persistent_volume["uid"],
        )
        target_state["result"] = result
        target_state["status"] = "completed"
        _write_evidence(execution_state_path, state)

    aggregate = _backend_cleanup_aggregate(
        inputs=inputs,
        results=[target["result"] for target in target_states],
    )
    aggregate = BACKEND_ATTESTOR.validate_backend_cleanup_results(
        aggregate,
        inputs=inputs,
    )
    _, aggregate_sha256 = _write_backend_cleanup_aggregate(
        inputs=inputs,
        execution_state_path=execution_state_path,
        aggregate=aggregate,
    )
    cleanup_state["aggregate"] = {
        "status": "completed",
        "sha256": aggregate_sha256,
    }
    _write_evidence(execution_state_path, state)


def _delete_with_preconditions(
    action: dict[str, str],
    *,
    plan: dict[str, Any],
    live_plan: dict[str, Any],
    delete_client: Any,
) -> None:
    kind = action["kind"]
    name = action["name"]
    if kind == "requestDeletePersistentVolume":
        approved = _persistent_volume(plan, name)
        live = _persistent_volume(live_plan, name)
        if live["uid"] != approved["uid"]:
            raise ValueError("reset PersistentVolume UID was replaced")
        delete_client.delete(
            api_version="v1",
            resource="persistentvolumes",
            namespace=None,
            name=name,
            uid=live["uid"],
            resource_version=live["resourceVersion"],
        )
        return
    if kind == "deleteWorkspace":
        approved = _workspace(plan, namespace=action["namespace"], name=name)
        live = _workspace(live_plan, namespace=action["namespace"], name=name)
        if live["uid"] != approved["uid"]:
            raise ValueError("signed reset Workspace UID was replaced")
        delete_client.delete(
            api_version="platform.aileron.io/v1alpha1",
            resource="workspaces",
            namespace=action["namespace"],
            name=name,
            uid=live["uid"],
            resource_version=live["resourceVersion"],
        )
        return
    if kind == "deleteNamespace":
        approved = _namespace(plan, name)
        live = _namespace(live_plan, name)
        if live["uid"] != approved["uid"]:
            raise ValueError("reset namespace UID was replaced")
        delete_client.delete(
            api_version="v1",
            resource="namespaces",
            namespace=None,
            name=name,
            uid=live["uid"],
            resource_version=live["resourceVersion"],
        )
        return
    raise ValueError("reset action is not a delete action")


def _write_evidence(path: Path, document: dict[str, Any]) -> None:
    if not path.is_absolute():
        raise ValueError("reset evidence path must be absolute")
    _reject_symlink_components(path, "reset evidence path")
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path.parent, "reset evidence directory")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _derive_reset_transaction_paths(
    *,
    expected_commit: str,
    expected_run_id: str,
    expected_snapshot_digest: str,
    context: str,
) -> ResetTransactionPaths:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected reset commit is invalid")
    if (
        RUN_ID_PATTERN.fullmatch(expected_run_id) is None
        or KUBERNETES_LABEL_VALUE_PATTERN.fullmatch(expected_run_id) is None
    ):
        raise ValueError("expected reset run ID is invalid")
    if DIGEST_PATTERN.fullmatch(expected_snapshot_digest) is None:
        raise ValueError("expected reset snapshot digest is invalid")
    if (
        not isinstance(context, str)
        or not context
        or context != context.strip()
        or len(context) > 253
        or any(ord(character) < 33 or ord(character) == 127 for character in context)
    ):
        raise ValueError("expected reset context is invalid")
    private_root = PRIVATE_INPUT.private_root_path()
    expected_acceptance_directory = (
        private_root / "evidence" / expected_commit / expected_run_id
    )
    transaction_directory = private_root / "reset" / expected_commit / expected_run_id
    execution_state = transaction_directory / "reset-execution-state.json"
    return ResetTransactionPaths(
        acceptance_directory=expected_acceptance_directory,
        transaction_directory=transaction_directory,
        inventory_output=transaction_directory / "reset-execution-evidence.json",
        execution_state=execution_state,
        execution_lock=_execution_lock_path(execution_state),
    )


def _prepare_reset_transaction_directory(path: Path) -> None:
    private_root = PRIVATE_INPUT.private_root_path()
    try:
        relative = path.relative_to(private_root)
    except ValueError as exc:
        raise ValueError("reset transaction directory is not installer-owned") from exc
    if len(relative.parts) != 3 or relative.parts[0] != "reset":
        raise ValueError("reset transaction directory is not canonical")
    current = private_root
    for component in relative.parts:
        current = current / component
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        PRIVATE_INPUT.validate_private_directory(
            current,
            "reset transaction directory",
            private_root=private_root,
        )


def _write_approval_evidence(path: Path, document: dict[str, Any]) -> None:
    PRIVATE_INPUT.write_private_snapshot(
        destination=path,
        content=json.dumps(document, indent=2, sort_keys=True).encode() + b"\n",
        description="reset inventory approval evidence",
        allow_existing_exact=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and execute the fail-closed Aileron HomeLab reset plan."
    )
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-reset-run-id", required=True)
    parser.add_argument("--expected-reset-snapshot-digest", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-delete-all-aileron-data", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()

    paths = _derive_reset_transaction_paths(
        expected_commit=arguments.expected_commit,
        expected_run_id=arguments.expected_reset_run_id,
        expected_snapshot_digest=arguments.expected_reset_snapshot_digest,
        context=arguments.context,
    )
    if arguments.execute and not arguments.confirm_delete_all_aileron_data:
        raise ValueError("--execute requires --confirm-delete-all-aileron-data")
    _prepare_reset_transaction_directory(paths.transaction_directory)

    kubeconfig_snapshot_directory = paths.transaction_directory
    flattened_kubeconfig = PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
        source=arguments.kubeconfig,
        raw_destination=(
            kubeconfig_snapshot_directory
            / f"reset-kubeconfig-{arguments.expected_reset_run_id}.raw.yaml"
        ),
        flattened_destination=(
            kubeconfig_snapshot_directory
            / f"reset-kubeconfig-{arguments.expected_reset_run_id}.flattened.json"
        ),
        context=arguments.context,
        runner=_subprocess_runner,
        allow_existing_exact=True,
    )

    trust = ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
        context=arguments.context, kubeconfig=flattened_kubeconfig
    )
    snapshot = ACCEPTANCE_SNAPSHOT.load_reset_snapshot(
        directory=paths.acceptance_directory,
        private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
        key=trust.key,
        context=arguments.context,
        commit=arguments.expected_commit,
        cluster_uid=trust.cluster_uid,
        installation_identity_sha256=trust.installation_identity_sha256,
        expected_run_id=arguments.expected_reset_run_id,
        expected_snapshot_sha256=arguments.expected_reset_snapshot_digest,
    )
    inventory = snapshot["inventory"]
    plan = build_reset_plan(
        inventory,
        kubeconfig=flattened_kubeconfig,
        reset_run_id=snapshot["runId"],
    )
    evidence = {
        "resetSnapshotRunId": snapshot["runId"],
        "resetSnapshotSha256": arguments.expected_reset_snapshot_digest,
        "inventory": inventory,
        "plan": plan,
    }
    _write_approval_evidence(paths.inventory_output, evidence)
    print(json.dumps(plan, indent=2, sort_keys=True))

    if arguments.execute:
        execute_reset_plan(
            plan,
            kubeconfig=flattened_kubeconfig,
            execution_state_path=paths.execution_state,
            expected_commit=arguments.expected_commit,
            reset_snapshot_sha256=arguments.expected_reset_snapshot_digest,
            execution_lock_path=paths.execution_lock,
            postcondition_interval_seconds=2.0,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
