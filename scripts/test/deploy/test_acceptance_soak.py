"""Pure HomeLab soak acceptance policy tests."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.deploy.rke2 import acceptance_soak as MODULE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "scripts/deploy/rke2/deployment-acceptance-contract.json"
COMMIT = "a" * 40
DEPLOYMENT_RUN_ID = "run-deployment-20260810"
WORKSPACE_ID = "workspace-1"
WORKSPACE_UID = "workspace-uid"
OWNER_ID = "owner-1"
UTC = timezone.utc
WORKSPACE_IMAGE_PULL_SECRETS = [{"name": "workspace-registry"}]

FIXED_CONTROLLERS = (
    (
        "Deployment",
        "aileron-identity-system",
        "aileron-identity-keycloak",
        "aileron-identity-keycloak",
    ),
    (
        "Deployment",
        "aileron-identity-system",
        "aileron-identity-postgres",
        "aileron-identity-postgres",
    ),
    ("DaemonSet", "aileron-turn-system", "aileron-coturn", "coturn"),
    ("Deployment", "workspace-system", "aileron-frontend", "frontend"),
    (
        "Deployment",
        "workspace-system",
        "aileron-workspace-manager",
        "workspace-manager",
    ),
    (
        "Deployment",
        "workspace-system",
        "aileron-workspace-operator",
        "workspace-operator",
    ),
    ("StatefulSet", "workspace-system", "aileron-postgres", "postgres"),
    ("StatefulSet", "workspace-system", "aileron-redis", "redis"),
    (
        "DaemonSet",
        "workspace-system",
        "aileron-workspace-firewall-attestor",
        "workspace-firewall-attestor",
    ),
    (
        "Deployment",
        "workspace-system",
        "aileron-connectivity-evidence-gateway",
        "connectivity-evidence-gateway",
    ),
    (
        "DaemonSet",
        "workspace-system",
        "aileron-connectivity-host-agent",
        "connectivity-external-agent",
    ),
)


def _json_copy(value):
    return json.loads(json.dumps(value))


def _list(items: list[dict]) -> dict:
    return {"apiVersion": "v1", "kind": "List", "items": _json_copy(items)}


def _owner(*, api_version: str, kind: str, name: str, uid: str) -> dict:
    return {
        "apiVersion": api_version,
        "kind": kind,
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


def _immutable_image(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"registry.example/aileron@sha256:{digest}"


def _safe_kubernetes_hash(seed: str) -> str:
    alphabet = "bcdfghjklmnpqrstvwxz2456789"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return "".join(alphabet[value % len(alphabet)] for value in digest[:10])


def _kubernetes_generated_name(generate_name: str) -> str:
    return f"{generate_name[:58]}{_safe_kubernetes_hash(generate_name)[:5]}"


def _workspace_component_annotations(workspace: dict, component: str) -> dict[str, str]:
    key = component.removeprefix("workspace-")
    component_spec = workspace["spec"][key]
    annotations = {
        "aileron.io/component-revision": str(component_spec["revision"]),
        "aileron.io/component-instance-id": component_spec["instanceId"],
    }
    if key == "runtime":
        annotations.update(
            {
                "aileron.io/runtime-instance-id": component_spec["instanceId"],
                "aileron.io/runtime-access-revision": str(
                    component_spec["accessRevision"]
                ),
                "aileron.io/knowledge-base-mount-revision": str(
                    component_spec["mountRevision"]
                ),
            }
        )
    elif key == "browser":
        annotations.update(
            {
                "aileron.io/browser-credential-revision": str(
                    component_spec["credentialRevision"]
                ),
                "aileron.io/browser-credential-key-id": component_spec[
                    "credentialKeyId"
                ],
                "aileron.io/browser-credential-algorithm": component_spec[
                    "credentialAlgorithm"
                ],
            }
        )
    return annotations


def _workspace_labels(
    workspace_id: str, owner_id: str, component: str
) -> dict[str, str]:
    return {
        "app.kubernetes.io/part-of": "aileron",
        "aileron.io/workspace-id": workspace_id,
        "aileron.io/owner-id": owner_id,
        "aileron.io/component": component,
        "aileron.io/firewall-group": (
            "browser" if component == "workspace-browser" else "workspace"
        ),
    }


def _workspace_service_account(
    workspace: dict,
    *,
    image_pull_secrets: list[dict[str, str]] | None = None,
) -> dict:
    workspace_id = workspace["spec"]["workspaceId"]
    name = f"workspace-workload-{workspace_id}"
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": name,
            "namespace": "workspace-system",
            "uid": f"{name}-uid",
            "labels": _workspace_labels(
                workspace_id,
                workspace["spec"]["ownerId"],
                "workspace-workload",
            ),
            "ownerReferences": [
                _owner(
                    api_version="platform.aileron.io/v1alpha1",
                    kind="Workspace",
                    name=workspace["metadata"]["name"],
                    uid=workspace["metadata"]["uid"],
                )
            ],
        },
        "automountServiceAccountToken": False,
        "imagePullSecrets": copy.deepcopy(
            WORKSPACE_IMAGE_PULL_SECRETS
            if image_pull_secrets is None
            else image_pull_secrets
        ),
    }


def _unrelated_service_account() -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": "default",
            "namespace": "workspace-system",
            "uid": "default-service-account-uid",
        },
    }


def _set_workspace_pod_image_pull_secrets(
    documents: dict,
    image_pull_secrets: list[dict[str, str]] | None,
) -> None:
    for source in ("workspacePods", "browserPods"):
        for pod in documents[source]["items"]:
            if pod["metadata"]["labels"].get("aileron.io/workspace-id") != WORKSPACE_ID:
                continue
            if image_pull_secrets is None:
                pod["spec"].pop("imagePullSecrets", None)
            else:
                pod["spec"]["imagePullSecrets"] = copy.deepcopy(image_pull_secrets)


def _workspace(
    workspace_id: str = WORKSPACE_ID,
    uid: str = WORKSPACE_UID,
    owner_id: str = OWNER_ID,
) -> dict:
    runtime_instance = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"runtime:{workspace_id}"))
    browser_instance = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"browser:{workspace_id}"))
    canvas_instance = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"canvas:{workspace_id}"))
    component_pod_uids = {
        component: (
            f"workspace-{component}-{workspace_id}-"
            f"{_safe_kubernetes_hash(f'workspace-{component}-{workspace_id}')}-pod-uid"
        )
        for component in ("runtime", "browser", "canvas")
    }
    return {
        "apiVersion": "platform.aileron.io/v1alpha1",
        "kind": "Workspace",
        "metadata": {
            "name": f"workspace-{workspace_id}",
            "namespace": "workspace-system",
            "uid": uid,
            "generation": 4,
            "ownerReferences": [],
        },
        "spec": {
            "workspaceId": workspace_id,
            "ownerId": owner_id,
            "runtime": {
                "desiredState": "Running",
                "instanceId": runtime_instance,
                "revision": 11,
                "mountRevision": 12,
                "accessRevision": 13,
                "image": _immutable_image("1"),
            },
            "browser": {
                "enabled": True,
                "desiredState": "Running",
                "instanceId": browser_instance,
                "revision": 21,
                "image": _immutable_image("2"),
                "credentialRevision": 22,
                "credentialKeyId": "browser-key-1",
                "credentialAlgorithm": "hkdf-sha256-v1",
            },
            "canvas": {
                "enabled": True,
                "desiredState": "Running",
                "instanceId": canvas_instance,
                "revision": 31,
                "image": _immutable_image("3"),
            },
        },
        "status": {
            "observedGeneration": 4,
            "phase": "Running",
            "browserConnectivity": {
                "state": "Accepted",
                "reason": "Healthy",
                "admission": "Accepted",
                "contractVersion": "v1",
                "credentialRevision": 22,
                "observedBrowserGeneration": 4,
                "profileRevision": 7,
                "acceptedAt": "2026-08-10T00:00:00Z",
                "expiresAt": "2026-08-10T00:01:00Z",
                "backendAcceptedAt": "2026-08-10T00:00:00Z",
                "backendExpiresAt": "2026-08-10T00:01:00Z",
                "frontendAcceptedAt": "2026-08-10T00:00:00Z",
                "frontendExpiresAt": "2026-08-10T00:01:00Z",
                "lastTransitionAt": "2026-08-10T00:00:00Z",
            },
            "components": {
                "runtime": {
                    "observedInstanceId": runtime_instance,
                    "observedRevision": 11,
                    "phase": "Running",
                    "podUid": component_pod_uids["runtime"],
                    "ready": True,
                    "terminalReady": True,
                    "mountObservedRevision": 12,
                    "lastKnownGoodMountRevision": 12,
                    "accessObservedRevision": 13,
                },
                "browser": {
                    "observedInstanceId": browser_instance,
                    "observedRevision": 21,
                    "phase": "Running",
                    "podUid": component_pod_uids["browser"],
                    "ready": True,
                    "credentialObservedRevision": 22,
                    "credentialObservedKeyId": "browser-key-1",
                    "credentialObservedAlgorithm": "hkdf-sha256-v1",
                },
                "canvas": {
                    "observedInstanceId": canvas_instance,
                    "observedRevision": 31,
                    "phase": "Running",
                    "podUid": component_pod_uids["canvas"],
                    "ready": True,
                },
            },
        },
    }


def _controller_status(kind: str, replicas: int = 1) -> dict:
    status = {"observedGeneration": 1}
    if kind == "DaemonSet":
        status.update(
            {
                "desiredNumberScheduled": replicas,
                "currentNumberScheduled": replicas,
                "numberMisscheduled": 0,
                "numberReady": replicas,
                "updatedNumberScheduled": replicas,
                "numberAvailable": replicas,
                "numberUnavailable": 0,
            }
        )
    else:
        status.update(
            {
                "replicas": replicas,
                "readyReplicas": replicas,
                "availableReplicas": replicas,
            }
        )
        if kind == "Deployment":
            status.update({"updatedReplicas": replicas, "unavailableReplicas": 0})
        elif kind == "StatefulSet":
            status.update(
                {
                    "currentReplicas": replicas,
                    "updatedReplicas": replicas,
                    "currentRevision": "revision-1",
                    "updateRevision": "revision-1",
                }
            )
        elif kind == "ReplicaSet":
            status.update({"fullyLabeledReplicas": replicas})
    return status


def _controller(
    *,
    kind: str,
    namespace: str,
    name: str,
    component: str,
    workspace: dict | None = None,
) -> dict:
    annotations: dict[str, str] | None = None
    if workspace is None:
        owners: list[dict] = []
        if namespace == "aileron-identity-system":
            labels = {
                "app.kubernetes.io/part-of": "aileron-identity",
                "app.kubernetes.io/managed-by": "Helm",
                "helm.sh/chart": "aileron-identity-1.0.0",
            }
            selector_labels = {"app.kubernetes.io/name": name}
            template_labels = {
                **selector_labels,
                "app.kubernetes.io/part-of": "aileron-identity",
            }
        else:
            labels = {
                "helm.sh/chart": "aileron-1.0.0",
                "app.kubernetes.io/name": "aileron",
                "app.kubernetes.io/instance": "aileron",
                "app.kubernetes.io/version": "1.0.0",
                "app.kubernetes.io/managed-by": "Helm",
                "app.kubernetes.io/part-of": "aileron",
            }
            if component in {
                "coturn",
                "workspace-firewall-attestor",
                "connectivity-evidence-gateway",
                "connectivity-external-agent",
            }:
                labels["app.kubernetes.io/component"] = component
            selector_labels = {
                "app.kubernetes.io/name": "aileron",
                "app.kubernetes.io/instance": "aileron",
                "app.kubernetes.io/component": component,
            }
            template_labels = copy.deepcopy(selector_labels)
            if component not in {
                "connectivity-evidence-gateway",
                "connectivity-external-agent",
            }:
                template_labels["app.kubernetes.io/part-of"] = "aileron"
    else:
        workspace_id = workspace["spec"]["workspaceId"]
        labels = _workspace_labels(
            workspace_id, workspace["spec"]["ownerId"], component
        )
        owners = [
            _owner(
                api_version="platform.aileron.io/v1alpha1",
                kind="Workspace",
                name=workspace["metadata"]["name"],
                uid=workspace["metadata"]["uid"],
            )
        ]
        template_labels = copy.deepcopy(labels)
        if component == "workspace-runtime":
            template_labels["aileron.io/runtime-instance-id"] = workspace["spec"][
                "runtime"
            ]["instanceId"]
        selector_labels = copy.deepcopy(labels)
        annotations = _workspace_component_annotations(workspace, component)
    component_key = component.removeprefix("workspace-")
    image = (
        workspace["spec"][component_key]["image"]
        if workspace is not None
        else _immutable_image(name[-1] if name[-1].isalnum() else "4")
    )
    container = {
        "name": {
            "workspace-runtime": "runtime",
            "workspace-browser": "browser",
            "workspace-canvas": "canvas",
        }.get(component, component),
        "image": image,
    }
    if component == "workspace-browser":
        container["readinessProbe"] = {
            "exec": {"command": list(MODULE.BROWSER_READINESS_COMMAND)},
            "periodSeconds": 5,
            "timeoutSeconds": 2,
            "failureThreshold": 3,
            "successThreshold": 1,
        }
    template_spec: dict = {"containers": [container]}
    if workspace is not None:
        template_spec["serviceAccountName"] = (
            f"workspace-workload-{workspace['spec']['workspaceId']}"
        )
    if component == "workspace-runtime":
        template_spec["initContainers"] = [
            {"name": "runtime-home-initializer", "image": image}
        ]
    if kind == "StatefulSet":
        template_spec["automountServiceAccountToken"] = False
        container["volumeMounts"] = [{"name": "data", "mountPath": "/data"}]
    template_metadata = {
        "creationTimestamp": None,
        "labels": copy.deepcopy(template_labels),
    }
    if annotations is not None:
        template_metadata["annotations"] = copy.deepcopy(annotations)
    spec: dict = {
        "selector": {"matchLabels": copy.deepcopy(selector_labels)},
        "template": {
            "metadata": template_metadata,
            "spec": template_spec,
        },
    }
    if kind != "DaemonSet":
        spec["replicas"] = 1
    if kind == "StatefulSet":
        spec["serviceName"] = name
        spec["volumeClaimTemplates"] = [
            {
                "metadata": {"name": "data"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "1Gi"}},
                },
            }
        ]
    status = _controller_status(kind)
    if kind == "StatefulSet":
        revision_name = f"{name}-{_controller_revision_hash(name)}"
        status["currentRevision"] = revision_name
        status["updateRevision"] = revision_name
    document = {
        "apiVersion": "apps/v1",
        "kind": kind,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": f"{name}-uid",
            "generation": 1,
            "labels": copy.deepcopy(labels),
            "ownerReferences": owners,
        },
        "spec": spec,
        "status": status,
    }
    if annotations is not None:
        document["metadata"]["annotations"] = copy.deepcopy(annotations)
    return document


def _controller_revision_hash(name: str) -> str:
    return _safe_kubernetes_hash(name)


def _controller_revision(controller: dict) -> dict:
    name = controller["metadata"]["name"]
    revision_hash = _controller_revision_hash(name)
    template = copy.deepcopy(controller["spec"]["template"])
    template["$patch"] = "replace"
    if controller["kind"] == "StatefulSet":
        hash_label = "controller.kubernetes.io/hash"
    else:
        hash_label = "controller-revision-hash"
    revision_name = f"{name}-{revision_hash}"
    return {
        "apiVersion": "apps/v1",
        "kind": "ControllerRevision",
        "metadata": {
            "name": revision_name,
            "namespace": controller["metadata"]["namespace"],
            "uid": f"{revision_name}-uid",
            "labels": {
                **copy.deepcopy(controller["spec"]["template"]["metadata"]["labels"]),
                hash_label: revision_hash,
            },
            "ownerReferences": [
                _owner(
                    api_version="apps/v1",
                    kind=controller["kind"],
                    name=name,
                    uid=controller["metadata"]["uid"],
                )
            ],
        },
        "data": {"spec": {"template": template}},
        "revision": 1,
    }


def _replica_set(deployment: dict) -> dict:
    labels = copy.deepcopy(deployment["spec"]["template"]["metadata"]["labels"])
    selector_labels = copy.deepcopy(deployment["spec"]["selector"]["matchLabels"])
    pod_template_hash = _safe_kubernetes_hash(deployment["metadata"]["name"])
    labels["pod-template-hash"] = pod_template_hash
    selector_labels["pod-template-hash"] = pod_template_hash
    name = f"{deployment['metadata']['name']}-{pod_template_hash}"
    template_metadata = copy.deepcopy(deployment["spec"]["template"]["metadata"])
    template_metadata["labels"] = copy.deepcopy(labels)
    return {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": name,
            "namespace": deployment["metadata"]["namespace"],
            "uid": f"{name}-uid",
            "generation": 1,
            "labels": copy.deepcopy(labels),
            "ownerReferences": [
                _owner(
                    api_version="apps/v1",
                    kind="Deployment",
                    name=deployment["metadata"]["name"],
                    uid=deployment["metadata"]["uid"],
                )
            ],
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": selector_labels},
            "template": {
                "metadata": template_metadata,
                "spec": copy.deepcopy(deployment["spec"]["template"]["spec"]),
            },
        },
        "status": _controller_status("ReplicaSet"),
    }


def _historical_replica_set(deployment: dict) -> dict:
    replica_set = _replica_set(deployment)
    old_hash = _safe_kubernetes_hash(f"historical:{deployment['metadata']['name']}")
    old_name = f"{deployment['metadata']['name']}-{old_hash}"
    old_instance_id = str(
        uuid.uuid5(uuid.NAMESPACE_DNS, f"historical:{deployment['metadata']['name']}")
    )
    replica_set["metadata"]["name"] = old_name
    replica_set["metadata"]["uid"] = f"{old_name}-uid"
    replica_set["metadata"]["labels"]["pod-template-hash"] = old_hash
    replica_set["spec"]["selector"]["matchLabels"]["pod-template-hash"] = old_hash
    template = replica_set["spec"]["template"]
    template["metadata"]["labels"]["pod-template-hash"] = old_hash
    replica_set["metadata"]["labels"] = copy.deepcopy(template["metadata"]["labels"])
    if "aileron.io/runtime-instance-id" in template["metadata"]["labels"]:
        template["metadata"]["labels"][
            "aileron.io/runtime-instance-id"
        ] = old_instance_id
        replica_set["metadata"]["labels"][
            "aileron.io/runtime-instance-id"
        ] = old_instance_id
    template["metadata"]["annotations"] = {"historical": "true"}
    old_image = _immutable_image(f"historical:{deployment['metadata']['name']}")
    for container in [
        *template["spec"]["containers"],
        *template["spec"].get("initContainers", []),
    ]:
        container["image"] = old_image
    replica_set["spec"]["replicas"] = 0
    replica_set["status"] = _controller_status("ReplicaSet", 0)
    return replica_set


def _runtime_status(container: dict, *, terminated: bool = False) -> dict:
    image = container["image"]
    result = {
        "name": container["name"],
        "image": image,
        "imageID": f"docker-pullable://{image}",
        "containerID": "containerd://"
        + hashlib.sha256(container["name"].encode("utf-8")).hexdigest(),
        "restartCount": 0,
        "ready": True,
        "started": not terminated,
    }
    if terminated:
        result["state"] = {
            "terminated": {
                "exitCode": 0,
                "reason": "Completed",
                "startedAt": "2026-08-10T00:00:00Z",
                "finishedAt": "2026-08-10T00:00:01Z",
            }
        }
    else:
        result["state"] = {"running": {"startedAt": "2026-08-10T00:00:00Z"}}
    return result


def _pod(owner: dict) -> dict:
    template = owner["spec"]["template"]
    labels = copy.deepcopy(template["metadata"]["labels"])
    generate_name = f"{owner['metadata']['name']}-"
    pod_name = _kubernetes_generated_name(generate_name)
    if owner["kind"] == "StatefulSet":
        pod_name = f"{owner['metadata']['name']}-0"
        labels.update(
            {
                "controller-revision-hash": owner["status"]["currentRevision"],
                "statefulset.kubernetes.io/pod-name": pod_name,
                "apps.kubernetes.io/pod-index": "0",
            }
        )
    elif owner["kind"] == "DaemonSet":
        labels.update(
            {
                "controller-revision-hash": _controller_revision_hash(
                    owner["metadata"]["name"]
                ),
                "pod-template-generation": str(owner["metadata"]["generation"]),
            }
        )
    spec = copy.deepcopy(template["spec"])
    if "aileron.io/workspace-id" in labels:
        spec["imagePullSecrets"] = copy.deepcopy(WORKSPACE_IMAGE_PULL_SECRETS)
    if owner["kind"] == "StatefulSet":
        spec["hostname"] = pod_name
        spec["subdomain"] = owner["spec"]["serviceName"]
        spec.setdefault("volumes", []).append(
            {
                "name": "data",
                "persistentVolumeClaim": {"claimName": f"data-{pod_name}"},
            }
        )
    node_name = f"node-{owner['metadata']['name']}"
    spec["nodeName"] = node_name
    spec["enableServiceLinks"] = True
    pod_ip_seed = hashlib.sha256(pod_name.encode("utf-8")).digest()
    pod_ip = f"10.42.{pod_ip_seed[0]}.{1 + pod_ip_seed[1] % 254}"
    host_ip_seed = hashlib.sha256(node_name.encode("utf-8")).digest()
    host_ip = f"192.0.2.{1 + host_ip_seed[0] % 254}"
    containers = spec["containers"]
    init_containers = spec.get("initContainers", [])
    metadata = {
        "name": pod_name,
        "generateName": generate_name,
        "namespace": owner["metadata"]["namespace"],
        "uid": f"{owner['metadata']['name']}-pod-uid",
        "labels": labels,
        "ownerReferences": [
            _owner(
                api_version="apps/v1",
                kind=owner["kind"],
                name=owner["metadata"]["name"],
                uid=owner["metadata"]["uid"],
            )
        ],
    }
    template_annotations = template["metadata"].get("annotations")
    if template_annotations is not None:
        metadata["annotations"] = copy.deepcopy(template_annotations)
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": metadata,
        "spec": spec,
        "status": {
            "phase": "Running",
            "podIP": pod_ip,
            "podIPs": [{"ip": pod_ip}],
            "hostIP": host_ip,
            "hostIPs": [{"ip": host_ip}],
            "conditions": [{"type": "Ready", "status": "True"}],
            "containerStatuses": [_runtime_status(item) for item in containers],
            "initContainerStatuses": [
                _runtime_status(item, terminated=True) for item in init_containers
            ],
        },
    }


def _inject_service_account_projection(
    pod: dict, *, expiration_seconds: int = 3607, extra_mount: bool = False
) -> None:
    volume_name = "kube-api-access-bcdfg"
    pod["spec"].setdefault("volumes", []).append(
        {
            "name": volume_name,
            "projected": {
                "defaultMode": 420,
                "sources": [
                    {
                        "serviceAccountToken": {
                            "expirationSeconds": expiration_seconds,
                            "path": "token",
                        }
                    },
                    {
                        "configMap": {
                            "items": [{"key": "ca.crt", "path": "ca.crt"}],
                            "name": "kube-root-ca.crt",
                        }
                    },
                    {
                        "downwardAPI": {
                            "items": [
                                {
                                    "fieldRef": {
                                        "apiVersion": "v1",
                                        "fieldPath": "metadata.namespace",
                                    },
                                    "path": "namespace",
                                }
                            ]
                        }
                    },
                ],
            },
        }
    )
    mount = {
        "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
        "name": volume_name,
        "readOnly": True,
    }
    for container in [
        *pod["spec"]["containers"],
        *pod["spec"].get("initContainers", []),
    ]:
        container.setdefault("volumeMounts", []).append(copy.deepcopy(mount))
    if extra_mount:
        pod["spec"]["containers"][0]["volumeMounts"].append(
            {"mountPath": "/unexpected", "name": "unexpected"}
        )


def _service(component: str, workspace: dict) -> dict:
    workspace_id = workspace["spec"]["workspaceId"]
    labels = _workspace_labels(
        workspace_id, workspace["spec"]["ownerId"], f"workspace-{component}"
    )
    selector = copy.deepcopy(labels)
    if component == "runtime":
        selector["aileron.io/runtime-instance-id"] = workspace["spec"]["runtime"][
            "instanceId"
        ]
    ports = {
        "runtime": [
            {"name": "http", "port": 3002, "protocol": "TCP", "targetPort": 3002},
            {"name": "terminal", "port": 3004, "protocol": "TCP", "targetPort": 3004},
        ],
        "browser": [
            {"name": "webrtc", "port": 6080, "protocol": "TCP", "targetPort": 6080},
            {"name": "cdp", "port": 9223, "protocol": "TCP", "targetPort": 9223},
            {
                "name": "connectivity-evidence",
                "port": 8082,
                "protocol": "TCP",
                "targetPort": 8082,
            },
        ],
        "canvas": [
            {"name": "http", "port": 3003, "protocol": "TCP", "targetPort": 3003},
            {"name": "api", "port": 3013, "protocol": "TCP", "targetPort": 3013},
        ],
    }[component]
    workspace_subnet = hashlib.sha256(workspace_id.encode("utf-8")).digest()[0]
    cluster_ip = (
        f"10.43.{workspace_subnet}."
        + {
            "runtime": "11",
            "browser": "12",
            "canvas": "13",
        }[component]
    )
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": f"workspace-{component}-{workspace_id}",
            "namespace": "workspace-system",
            "uid": f"{component}-{workspace_id}-service-uid",
            "labels": copy.deepcopy(labels),
            "ownerReferences": [
                _owner(
                    api_version="platform.aileron.io/v1alpha1",
                    kind="Workspace",
                    name=workspace["metadata"]["name"],
                    uid=workspace["metadata"]["uid"],
                )
            ],
        },
        "spec": {
            "type": "ClusterIP",
            "clusterIP": cluster_ip,
            "clusterIPs": [cluster_ip],
            "internalTrafficPolicy": "Cluster",
            "ipFamilies": ["IPv4"],
            "ipFamilyPolicy": "SingleStack",
            "selector": selector,
            "ports": ports,
            "sessionAffinity": "None",
        },
    }


def _endpoint_slice(service: dict, pod: dict | None) -> dict:
    name_prefix = f"{service['metadata']['name']}-"
    name = f"{name_prefix}{_safe_kubernetes_hash(service['metadata']['uid'])[:5]}"
    endpoints = []
    ports = []
    if pod is not None:
        endpoints = [
            {
                "addresses": [pod["status"]["podIP"]],
                "conditions": {
                    "ready": True,
                    "serving": True,
                    "terminating": False,
                },
                "nodeName": pod["spec"]["nodeName"],
                "targetRef": {
                    "kind": "Pod",
                    "namespace": pod["metadata"]["namespace"],
                    "name": pod["metadata"]["name"],
                    "uid": pod["metadata"]["uid"],
                },
            }
        ]
        ports = [
            {
                "name": port["name"],
                "port": port["targetPort"],
                "protocol": port["protocol"],
            }
            for port in service["spec"]["ports"]
        ]
    return {
        "apiVersion": "discovery.k8s.io/v1",
        "kind": "EndpointSlice",
        "metadata": {
            "name": name,
            "generateName": name_prefix,
            "namespace": service["metadata"]["namespace"],
            "uid": f"{name}-uid",
            "labels": {
                **copy.deepcopy(service["metadata"]["labels"]),
                "kubernetes.io/service-name": service["metadata"]["name"],
                "endpointslice.kubernetes.io/managed-by": (
                    "endpointslice-controller.k8s.io"
                ),
            },
            "ownerReferences": [
                _owner(
                    api_version="v1",
                    kind="Service",
                    name=service["metadata"]["name"],
                    uid=service["metadata"]["uid"],
                )
            ],
        },
        "addressType": "IPv4",
        "endpoints": endpoints,
        "ports": ports,
    }


def _selected_pod(service: dict, pods: list[dict]) -> dict | None:
    selector = service["spec"]["selector"]
    matches = [
        pod
        for pod in pods
        if pod["metadata"]["namespace"] == service["metadata"]["namespace"]
        and all(
            pod["metadata"]["labels"].get(key) == value
            for key, value in selector.items()
        )
    ]
    if not matches:
        return None
    assert len(matches) == 1
    return matches[0]


def _add_workspace_graph(documents: dict, workspace: dict) -> None:
    documents["workspace"]["items"].append(_json_copy(workspace))
    documents["workspaceServiceAccounts"]["items"].append(
        _workspace_service_account(workspace)
    )
    controllers: list[dict] = []
    workspace_pods: list[dict] = []
    for component in ("workspace-runtime", "workspace-browser", "workspace-canvas"):
        controller = _controller(
            kind="Deployment",
            namespace="workspace-system",
            name=f"{component}-{workspace['spec']['workspaceId']}",
            component=component,
            workspace=workspace,
        )
        controllers.append(controller)
        replica_set = _replica_set(controller)
        documents["controllers"]["items"].extend([controller, replica_set])
        pod = _pod(replica_set)
        workspace_pods.append(pod)
        documents["workspacePods"]["items"].append(pod)
    services = [
        _service(component, workspace) for component in ("runtime", "browser", "canvas")
    ]
    documents["services"]["items"].extend(services)
    documents["endpointSlices"]["items"].extend(
        [
            _endpoint_slice(service, _selected_pod(service, workspace_pods))
            for service in services
        ]
    )


def _documents(identity_mode: str = "bundledKeycloak") -> dict[str, dict]:
    workspace = _workspace()
    controllers: list[dict] = []
    pods: list[dict] = []
    for kind, namespace, name, component in FIXED_CONTROLLERS:
        if identity_mode == "externalOidc" and namespace == "aileron-identity-system":
            continue
        controller = _controller(
            kind=kind, namespace=namespace, name=name, component=component
        )
        controllers.append(controller)
        if kind in {"StatefulSet", "DaemonSet"}:
            controllers.append(_controller_revision(controller))
        owner = controller
        if kind == "Deployment":
            owner = _replica_set(controller)
            controllers.append(owner)
        pods.append(_pod(owner))
    for component in ("workspace-runtime", "workspace-browser", "workspace-canvas"):
        controller = _controller(
            kind="Deployment",
            namespace="workspace-system",
            name=f"{component}-{WORKSPACE_ID}",
            component=component,
            workspace=workspace,
        )
        replica_set = _replica_set(controller)
        controllers.extend([controller, replica_set])
        pods.append(_pod(replica_set))
    browser_pod = next(
        item
        for item in pods
        if item["metadata"]["name"].startswith("workspace-browser-")
    )
    services = [
        _service(component, workspace) for component in ("runtime", "browser", "canvas")
    ]
    workspace_pods = [
        item for item in pods if item["metadata"]["namespace"] == "workspace-system"
    ]
    documents = {
        "identityPods": _list(
            [
                item
                for item in pods
                if item["metadata"]["namespace"] == "aileron-identity-system"
            ]
        ),
        "turnPods": _list(
            [
                item
                for item in pods
                if item["metadata"]["namespace"] == "aileron-turn-system"
            ]
        ),
        "workspacePods": _list(workspace_pods),
        "workspace": _list([workspace]),
        "workspaceServiceAccounts": _list(
            [_workspace_service_account(workspace), _unrelated_service_account()]
        ),
        "services": _list(services),
        "endpointSlices": _list(
            [
                _endpoint_slice(service, _selected_pod(service, workspace_pods))
                for service in services
            ]
        ),
        "browserPods": _list([browser_pod]),
        "controllers": _list(controllers),
    }
    return _json_copy(documents)


def _image_runtime_pairs(
    documents: dict[str, dict],
) -> dict[str, frozenset[str]]:
    images = {
        container["image"]
        for source in ("identityPods", "turnPods", "workspacePods")
        for pod in documents[source]["items"]
        for container in [
            *pod["spec"]["containers"],
            *pod["spec"].get("initContainers", []),
        ]
        if MODULE.IMMUTABLE_IMAGE.fullmatch(container["image"]) is not None
    }
    pairs = {
        image: frozenset(
            {
                image.rsplit("@sha256:", 1)[1],
                hashlib.sha256(f"runtime:{image}".encode()).hexdigest(),
            }
        )
        for image in images
    }
    dummy_index = 0
    while len(pairs) < 11:
        image = _immutable_image(f"signed-inventory-dummy-{dummy_index}")
        pairs[image] = frozenset(
            {
                image.rsplit("@sha256:", 1)[1],
                hashlib.sha256(f"runtime:{image}".encode()).hexdigest(),
            }
        )
        dummy_index += 1
    assert len(pairs) == 11
    return pairs


def _snapshot(
    documents: dict | None = None,
    *,
    identity_mode: str = "bundledKeycloak",
    image_runtime_pairs: dict[str, frozenset[str]] | None = None,
) -> dict:
    raw_documents = _documents(identity_mode) if documents is None else documents
    return MODULE.snapshot_sample(
        raw_documents,
        workspace_id=WORKSPACE_ID,
        identity_mode=identity_mode,
        commit=COMMIT,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        image_runtime_pairs=(
            _image_runtime_pairs(raw_documents)
            if image_runtime_pairs is None
            else image_runtime_pairs
        ),
    )


def _find(
    documents: dict, source: str, *, kind: str | None = None, prefix: str | None = None
) -> dict:
    for item in documents[source]["items"]:
        if kind is not None and item.get("kind") != kind:
            continue
        if prefix is not None and not item.get("metadata", {}).get(
            "name", ""
        ).startswith(prefix):
            continue
        return item
    raise AssertionError(f"fixture resource missing: {source}/{kind}/{prefix}")


def test_policy_is_fixed_production_30_minute_cadence() -> None:
    policy = MODULE.validate_policy(json.loads(CONTRACT.read_text()))
    assert policy == MODULE.SoakPolicy(1800, 60, 75, 31, 2000)


def test_browser_readiness_probe_matches_the_operator_source_exactly() -> None:
    operator_source = (
        ROOT / "workspace-operator/internal/controller/workspace_controller.go"
    ).read_text()
    operator_script = operator_source.split("const browserCompositeProbeScript = `", 1)[
        1
    ].split("`\n\nfunc browserCompositeProbe", 1)[0]

    assert MODULE.BROWSER_READINESS_SCRIPT == operator_script
    assert MODULE.BROWSER_READINESS_PROBE_LENGTH == 1731
    assert len(MODULE.BROWSER_READINESS_SCRIPT) == 1731
    assert MODULE.BROWSER_READINESS_PROBE_SHA256 == (
        "83e6cbe28dc5bde234c4a36ca6a3a872d437b54e62c25a077356dd8c7d41d082"
    )
    assert (
        hashlib.sha256(MODULE.BROWSER_READINESS_SCRIPT.encode("utf-8")).hexdigest()
        == MODULE.BROWSER_READINESS_PROBE_SHA256
    )


def test_runtime_home_initializer_matches_the_operator_source_exactly() -> None:
    operator_source = (
        ROOT / "workspace-operator/internal/controller/workspace_controller.go"
    ).read_text()
    operator_declaration = next(
        line
        for line in operator_source.splitlines()
        if line.strip().startswith("runtimeHomeInitializerName")
    )
    operator_name = operator_declaration.partition("=")[2].strip().strip('"')
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    initializer = deployment["spec"]["template"]["spec"]["initContainers"][0]

    assert operator_name == "runtime-home-initializer"
    assert initializer["name"] == operator_name

    initializer["name"] = "runtime-home-init"
    with pytest.raises(
        MODULE.SoakValidationError,
        match="Runtime initializer projection is invalid",
    ):
        _snapshot(documents)


def _execute_browser_readiness_probe(config: str, tmp_path: Path) -> int:
    browser_directory = Path("/tmp/aileron-browser")
    browser_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    browser_config = browser_directory / "neko.generated.yaml"
    browser_config.write_text(config, encoding="utf-8")
    browser_config.chmod(0o600)
    fake_curl = tmp_path / "curl"
    fake_curl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_curl.chmod(0o700)
    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    return subprocess.run(
        MODULE.BROWSER_READINESS_COMMAND,
        check=False,
        env=environment,
    ).returncode


@pytest.mark.parametrize(
    "member_body",
    [
        '  provider: "multiuser"',
        '  provider: multiuser\n  "provider": noauth',
        "  provider: multiuser\n  'provider': noauth",
        '  provider: multiuser\n  "\\u0070rovider": noauth',
        "  provider: multiuser\n  !!str provider: noauth",
        "  provider: multiuser\n  &managed provider: noauth",
        "  provider: multiuser\n  ? provider\n  : noauth",
        "  provider: multiuser\n  <<: *member_defaults",
        '  provider: multiuser\n  {"provider": noauth}',
        "  provider: multiuser\n  --- provider: noauth",
        " provider: multiuser",
        "   provider: multiuser",
        "\tprovider: multiuser",
        "  provider: multiuser\n    injected: true",
    ],
)
def test_browser_readiness_probe_rejects_noncanonical_direct_children(
    tmp_path: Path, member_body: str
) -> None:
    config = f"member:\n{member_body}\nwebrtc:\n  icelite: false\n"

    assert _execute_browser_readiness_probe(config, tmp_path) != 0


def test_browser_readiness_probe_accepts_a_nested_mapping_after_an_empty_key(
    tmp_path: Path,
) -> None:
    config = """member:
  provider: multiuser
  options:
    display_name: Browser
webrtc:
  icelite: false
  options:
    network: private
"""

    assert _execute_browser_readiness_probe(config, tmp_path) == 0


@pytest.mark.parametrize("identity_mode", ["bundledKeycloak", "externalOidc"])
def test_query_set_is_nine_namespace_closed_lists(identity_mode: str) -> None:
    queries = MODULE.build_query_commands(
        kubeconfig="/private/kubeconfig",
        context="homelab",
        workspace_id=WORKSPACE_ID,
        identity_mode=identity_mode,
    )
    assert set(queries) == {
        "identityPods",
        "turnPods",
        "workspacePods",
        "workspace",
        "workspaceServiceAccounts",
        "services",
        "endpointSlices",
        "browserPods",
        "controllers",
    }
    assert len(queries) * MODULE.SOAK_MINIMUM_SAMPLES == 279
    for source, namespace in {
        "identityPods": "aileron-identity-system",
        "turnPods": "aileron-turn-system",
        "workspacePods": "workspace-system",
    }.items():
        command = queries[source]
        assert "--all-namespaces" in command
        assert "--namespace" not in command
        index = command.index("--field-selector")
        assert command[index + 1] == f"metadata.namespace={namespace}"
    assert "--selector" not in queries["services"]
    service_account_query = queries["workspaceServiceAccounts"]
    assert service_account_query[service_account_query.index("get") + 1] == (
        "serviceaccounts"
    )
    assert (
        service_account_query[service_account_query.index("--namespace") + 1]
        == "workspace-system"
    )
    assert "--all-namespaces" not in service_account_query
    assert queries["endpointSlices"][queries["endpointSlices"].index("get") + 1] == (
        "endpointslices.discovery.k8s.io"
    )
    assert queries["workspace"].count(f"workspace-{WORKSPACE_ID}") == 0
    assert any("jobs.batch" in argument for argument in queries["controllers"])
    assert any(
        "controllerrevisions.apps" in argument for argument in queries["controllers"]
    )


def test_snapshot_fixture_round_trips_without_aliases() -> None:
    documents = _documents()
    assert documents == _json_copy(documents)
    workspace_pod = _find(documents, "workspacePods", prefix="workspace-browser-")
    browser_pod = documents["browserPods"]["items"][0]
    assert workspace_pod is not browser_pod
    assert workspace_pod["metadata"] is not browser_pod["metadata"]
    assert (
        workspace_pod["spec"]["containers"][0]
        is not browser_pod["spec"]["containers"][0]
    )
    service = documents["services"]["items"][0]
    assert service["metadata"]["labels"] is not service["spec"]["selector"]
    assert _snapshot(documents)["sha256"]


@pytest.mark.parametrize("empty_field", ["present", "absent"])
def test_workspace_service_account_allows_empty_pull_secret_projection(
    empty_field: str,
) -> None:
    documents = _documents()
    service_account = documents["workspaceServiceAccounts"]["items"][0]
    if empty_field == "present":
        service_account["imagePullSecrets"] = []
    else:
        del service_account["imagePullSecrets"]
    _set_workspace_pod_image_pull_secrets(documents, None)

    snapshot = _snapshot(documents)

    assert len(documents["workspaceServiceAccounts"]["items"]) == 2
    assert len(snapshot["serviceAccounts"]) == 1
    assert snapshot["serviceAccounts"][0]["projectionSha256"]


@pytest.mark.parametrize(
    "attack",
    ["missing", "duplicate", "owner", "labels", "automount", "legacy-secrets"],
)
def test_workspace_service_account_projection_is_closed(attack: str) -> None:
    documents = _documents()
    service_accounts = documents["workspaceServiceAccounts"]["items"]
    service_account = service_accounts[0]
    if attack == "missing":
        service_accounts.remove(service_account)
    elif attack == "duplicate":
        duplicate = _json_copy(service_account)
        duplicate["metadata"]["uid"] = "duplicate-workload-service-account-uid"
        service_accounts.append(duplicate)
    elif attack == "owner":
        service_account["metadata"]["ownerReferences"][0]["uid"] = "foreign-uid"
    elif attack == "labels":
        service_account["metadata"]["labels"][
            "aileron.io/component"
        ] = "workspace-runtime"
    elif attack == "automount":
        service_account["automountServiceAccountToken"] = True
    else:
        service_account["secrets"] = [{"name": "legacy-token"}]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "image_pull_secrets",
    [
        "not-a-list",
        [{"name": ""}],
        [{"name": "workspace-registry"}, {"name": "workspace-registry"}],
    ],
    ids=["malformed-list", "malformed-reference", "duplicate-reference"],
)
def test_workspace_service_account_pull_secret_references_are_canonical(
    image_pull_secrets: object,
) -> None:
    documents = _documents()
    documents["workspaceServiceAccounts"]["items"][0][
        "imagePullSecrets"
    ] = image_pull_secrets

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("pod_prefix", ["workspace-runtime-", "aileron-frontend-"])
def test_pod_image_pull_secret_injection_requires_exact_validated_service_account(
    pod_prefix: str,
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix=pod_prefix)
    pod["spec"]["imagePullSecrets"] = [{"name": "unrelated-registry"}]

    with pytest.raises(
        MODULE.SoakValidationError,
        match="soak Pod spec differs from owner template",
    ):
        _snapshot(documents)


@pytest.mark.parametrize("attack", ["service-account-name", "template-pull-secret"])
def test_workspace_controller_requires_service_account_inheritance(
    attack: str,
) -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    template_spec = deployment["spec"]["template"]["spec"]
    if attack == "service-account-name":
        template_spec["serviceAccountName"] = "default"
    else:
        template_spec["imagePullSecrets"] = copy.deepcopy(WORKSPACE_IMAGE_PULL_SECRETS)

    with pytest.raises(
        MODULE.SoakValidationError,
        match="Workspace controller projection is invalid",
    ):
        _snapshot(documents)


def test_workspace_service_account_projection_is_sealed_in_snapshot() -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    updated_pull_secrets = [
        *WORKSPACE_IMAGE_PULL_SECRETS,
        {"name": "workspace-registry-secondary"},
    ]
    documents["workspaceServiceAccounts"]["items"][0]["imagePullSecrets"] = (
        copy.deepcopy(updated_pull_secrets)
    )
    _set_workspace_pod_image_pull_secrets(documents, updated_pull_secrets)

    updated = _snapshot(documents)

    assert updated["sha256"] != baseline["sha256"]
    assert (
        updated["serviceAccounts"][0]["projectionSha256"]
        != baseline["serviceAccounts"][0]["projectionSha256"]
    )


@pytest.mark.parametrize(
    ("source", "mutation"),
    [
        ("workspace", lambda document: document.update({"apiVersion": "v2"})),
        (
            "services",
            lambda document: document["items"][0].update({"kind": "ConfigMap"}),
        ),
        (
            "workspaceServiceAccounts",
            lambda document: document["items"][0].update({"kind": "ConfigMap"}),
        ),
        (
            "endpointSlices",
            lambda document: document["items"][0].update({"kind": "ConfigMap"}),
        ),
        (
            "workspacePods",
            lambda document: document["items"][0].update({"apiVersion": "v2"}),
        ),
        (
            "controllers",
            lambda document: document["items"][0].update({"kind": "ConfigMap"}),
        ),
    ],
)
def test_snapshot_rejects_wrong_root_or_item_gvk(source: str, mutation) -> None:
    documents = _documents()
    mutation(documents[source])
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_external_oidc_requires_empty_identity_plane() -> None:
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(_documents("bundledKeycloak"), identity_mode="externalOidc")
    assert _snapshot(identity_mode="externalOidc")["sha256"]


def test_external_data_service_inventory_omits_bundled_controllers() -> None:
    documents = _documents()
    manager = _find(
        documents,
        "controllers",
        kind="Deployment",
        prefix="aileron-workspace-manager",
    )
    manager["spec"]["template"]["metadata"].setdefault("annotations", {}).update(
        {
            "aileron.io/platform-database-revision": "platform-v2",
            "aileron.io/redis-general-revision": "redis-general-v2",
            "aileron.io/redis-job-queue-revision": "redis-queue-v2",
            "aileron.io/redis-job-result-revision": "redis-result-v2",
        }
    )
    keycloak = _find(
        documents,
        "controllers",
        kind="Deployment",
        prefix="aileron-identity-keycloak",
    )
    keycloak["spec"]["template"]["metadata"].setdefault("annotations", {})[
        "aileron.io/identity-database-revision"
    ] = "identity-v2"

    for deployment in (manager, keycloak):
        deployment_uid = deployment["metadata"]["uid"]
        replica_set = next(
            item
            for item in documents["controllers"]["items"]
            if item.get("kind") == "ReplicaSet"
            and item.get("metadata", {}).get("ownerReferences", [{}])[0].get("uid")
            == deployment_uid
        )
        replica_set["spec"]["template"]["metadata"]["annotations"] = dict(
            deployment["spec"]["template"]["metadata"]["annotations"]
        )
        for source in ("workspacePods", "identityPods"):
            for pod in documents[source]["items"]:
                references = pod.get("metadata", {}).get("ownerReferences", [])
                if (
                    references
                    and references[0].get("uid") == replica_set["metadata"]["uid"]
                ):
                    pod["metadata"]["annotations"] = dict(
                        replica_set["spec"]["template"]["metadata"]["annotations"]
                    )

    prefixes = ("aileron-postgres", "aileron-redis", "aileron-identity-postgres")
    documents["controllers"]["items"] = [
        item
        for item in documents["controllers"]["items"]
        if not item["metadata"]["name"].startswith(prefixes)
    ]
    documents["workspacePods"]["items"] = [
        item
        for item in documents["workspacePods"]["items"]
        if not item["metadata"]["name"].startswith(
            ("aileron-postgres", "aileron-redis")
        )
    ]
    documents["identityPods"]["items"] = [
        item
        for item in documents["identityPods"]["items"]
        if not item["metadata"]["name"].startswith("aileron-identity-postgres")
    ]

    assert _snapshot(documents)["sha256"]


def test_raw_query_documents_cannot_be_swapped() -> None:
    documents = _documents()
    documents["identityPods"], documents["turnPods"] = (
        documents["turnPods"],
        documents["identityPods"],
    )
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("missing_field", ["name", "uid"])
def test_every_raw_list_item_requires_nonempty_name_and_uid(
    missing_field: str,
) -> None:
    documents = _documents()
    metadata = {
        "name": "unmanaged-service",
        "namespace": "workspace-system",
        "uid": "unmanaged-service-uid",
        "labels": {"unrelated": "true"},
        "ownerReferences": [],
    }
    metadata[missing_field] = ""
    documents["services"]["items"].append(
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": metadata,
            "spec": {},
        }
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_raw_lists_reject_duplicate_uid_even_for_unmanaged_items() -> None:
    documents = _documents()
    existing = documents["services"]["items"][0]
    documents["services"]["items"].append(
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "unmanaged-service",
                "namespace": "workspace-system",
                "uid": existing["metadata"]["uid"],
                "labels": {"unrelated": "true"},
                "ownerReferences": [],
            },
            "spec": {},
        }
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_raw_lists_reject_duplicate_service_identity_with_distinct_uids() -> None:
    documents = _documents()
    duplicate = _json_copy(_find(documents, "services", prefix="workspace-runtime-"))
    duplicate["metadata"]["uid"] = "duplicate-runtime-service-uid"
    duplicate["spec"]["clusterIP"] = "10.43.0.99"
    duplicate["spec"]["clusterIPs"] = ["10.43.0.99"]
    documents["services"]["items"].append(duplicate)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_raw_lists_reject_duplicate_fixed_statefulset_identity() -> None:
    documents = _documents()
    stateful_set = _find(
        documents, "controllers", kind="StatefulSet", prefix="aileron-postgres"
    )
    duplicate = _json_copy(stateful_set)
    duplicate["metadata"]["uid"] = "duplicate-aileron-postgres-uid"
    documents["controllers"]["items"].append(duplicate)
    pod = _json_copy(_find(documents, "workspacePods", prefix="aileron-postgres-0"))
    pod["metadata"]["name"] = "duplicate-aileron-postgres-pod"
    pod["metadata"]["uid"] = "duplicate-aileron-postgres-pod-uid"
    pod["metadata"]["ownerReferences"][0]["uid"] = duplicate["metadata"]["uid"]
    documents["workspacePods"]["items"].append(pod)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_raw_lists_reject_duplicate_running_pod_identity_with_distinct_uids() -> None:
    documents = _documents()
    stateful_set = _find(
        documents, "controllers", kind="StatefulSet", prefix="aileron-postgres"
    )
    stateful_set["spec"]["replicas"] = 2
    stateful_set["status"].update(
        {
            "replicas": 2,
            "currentReplicas": 2,
            "readyReplicas": 2,
            "updatedReplicas": 2,
            "availableReplicas": 2,
        }
    )
    pod = _find(documents, "workspacePods", prefix="aileron-postgres-0")
    duplicate = _json_copy(pod)
    duplicate["metadata"]["uid"] = "duplicate-aileron-postgres-pod-uid"
    documents["workspacePods"]["items"].append(duplicate)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def _set_workspace_stopped_status(workspace: dict) -> None:
    workspace["spec"]["runtime"]["desiredState"] = "Stopped"
    for component in ("browser", "canvas"):
        workspace["spec"][component]["enabled"] = False
        workspace["spec"][component]["desiredState"] = "Stopped"
    workspace["status"]["phase"] = "Stopped"
    workspace["status"]["components"] = {
        "runtime": {
            "observedRevision": 0,
            "phase": "Stopped",
            "ready": False,
            "reason": "RuntimeStopped",
            "mountObservedRevision": 12,
            "lastKnownGoodMountRevision": 12,
            "accessObservedRevision": 13,
        },
        "browser": {
            "observedRevision": 0,
            "phase": "Disabled",
            "ready": False,
            "reason": "BrowserDisabled",
            "credentialObservedRevision": 0,
        },
        "canvas": {
            "observedRevision": 0,
            "phase": "Disabled",
            "ready": False,
            "reason": "CanvasDisabled",
            "credentialObservedRevision": 0,
        },
    }


def _stopped_workspace_with_zero_scaled_graph(documents: dict) -> dict:
    workspace = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    _set_workspace_stopped_status(workspace)
    _add_workspace_graph(documents, workspace)
    for controller in documents["controllers"]["items"]:
        references = controller["metadata"].get("ownerReferences", [])
        owned_directly = any(
            reference.get("uid") == workspace["metadata"]["uid"]
            for reference in references
        )
        owned_by_workspace_deployment = any(
            reference.get("name", "").endswith("-workspace-2")
            for reference in references
        )
        if owned_directly or owned_by_workspace_deployment:
            controller["spec"]["replicas"] = 0
            controller["status"] = _controller_status(controller["kind"], 0)
    documents["workspacePods"]["items"] = [
        pod
        for pod in documents["workspacePods"]["items"]
        if pod["metadata"]["labels"].get("aileron.io/workspace-id") != "workspace-2"
    ]
    for endpoint_slice in documents["endpointSlices"]["items"]:
        if (
            endpoint_slice["metadata"]["labels"].get("aileron.io/workspace-id")
            == "workspace-2"
        ):
            endpoint_slice["endpoints"] = []
            endpoint_slice["ports"] = []
    return workspace


def test_raw_lists_reject_duplicate_zero_scaled_replicaset_identity() -> None:
    documents = _documents()
    _stopped_workspace_with_zero_scaled_graph(documents)
    replica_set = _find(
        documents,
        "controllers",
        kind="ReplicaSet",
        prefix="workspace-runtime-workspace-2",
    )
    duplicate = _json_copy(replica_set)
    duplicate["metadata"]["uid"] = "duplicate-zero-replicaset-uid"
    documents["controllers"]["items"].append(duplicate)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_raw_lists_reject_duplicate_non_target_workspace_graph_identity() -> None:
    documents = _documents()
    other = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    _add_workspace_graph(documents, other)
    deployment = _find(
        documents,
        "controllers",
        kind="Deployment",
        prefix="workspace-canvas-workspace-2",
    )
    duplicate_deployment = _json_copy(deployment)
    duplicate_deployment["metadata"]["uid"] = "duplicate-other-deployment-uid"
    documents["controllers"]["items"].append(duplicate_deployment)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "target",
    ["workspace", "controller", "replicaset", "pod", "service", "endpointSlice"],
)
def test_label_or_owner_hidden_workspace_resources_are_rejected(target: str) -> None:
    documents = _documents()
    if target == "workspace":
        resource = documents["workspace"]["items"][0]
        resource["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    elif target == "controller":
        resource = _find(
            documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
        )
        resource["metadata"]["labels"] = {"unrelated": "true"}
    elif target == "replicaset":
        resource = _find(
            documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
        )
        resource["metadata"]["labels"] = {"pod-template-hash": "bcdf2456"}
    elif target == "pod":
        resource = _find(documents, "workspacePods", prefix="workspace-runtime-")
        resource["metadata"]["labels"] = {"unrelated": "true"}
    elif target == "service":
        resource = _find(documents, "services", prefix="workspace-runtime-")
        resource["metadata"]["labels"] = {"unrelated": "true"}
    else:
        resource = _find(documents, "endpointSlices", prefix="workspace-runtime-")
        resource["metadata"]["labels"] = {"unrelated": "true"}
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_fixed_controller_component_selector_is_canonical() -> None:
    documents = _documents()
    controller = _find(
        documents, "controllers", kind="Deployment", prefix="aileron-frontend"
    )
    controller["spec"]["selector"]["matchLabels"][
        "app.kubernetes.io/component"
    ] = "workspace-manager"
    controller["spec"]["template"]["metadata"]["labels"][
        "app.kubernetes.io/component"
    ] = "workspace-manager"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("component", ["runtime", "browser", "canvas"])
def test_target_workspace_requires_every_component_running(component: str) -> None:
    documents = _documents()
    documents["workspace"]["items"][0]["spec"][component]["desiredState"] = "Stopped"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_workspace_zero_runtime_fence_revisions_are_valid() -> None:
    documents = _documents()
    workspace = documents["workspace"]["items"][0]
    workspace["spec"]["runtime"]["mountRevision"] = 0
    workspace["spec"]["runtime"]["accessRevision"] = 0
    workspace["status"]["components"]["runtime"].update(
        {
            "mountObservedRevision": 0,
            "lastKnownGoodMountRevision": 0,
            "accessObservedRevision": 0,
        }
    )
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )
    expected_annotations = _workspace_component_annotations(
        workspace, "workspace-runtime"
    )
    deployment["metadata"]["annotations"] = copy.deepcopy(expected_annotations)
    deployment["spec"]["template"]["metadata"]["annotations"] = copy.deepcopy(
        expected_annotations
    )
    replica_set["spec"]["template"]["metadata"]["annotations"] = copy.deepcopy(
        expected_annotations
    )
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    pod["metadata"]["annotations"] = copy.deepcopy(expected_annotations)

    _snapshot(documents)


@pytest.mark.parametrize(
    ("component", "field", "value"),
    [
        ("runtime", "instanceId", "runtime-instance-not-a-uuid"),
        ("browser", "instanceId", "browser-instance-not-a-uuid"),
        ("canvas", "instanceId", "canvas-instance-not-a-uuid"),
        ("browser", "credentialAlgorithm", "HS256"),
    ],
)
def test_workspace_cr_rejects_noncanonical_live_shape(
    component: str, field: str, value: str
) -> None:
    documents = _documents()
    documents["workspace"]["items"][0]["spec"][component][field] = value

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("component", ["runtime", "browser", "canvas"])
def test_workspace_cr_image_is_bound_to_component_deployment(component: str) -> None:
    documents = _documents()
    documents["workspace"]["items"][0]["spec"][component]["image"] = _immutable_image(
        f"new-{component}"
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("location", ["metadata", "template"])
def test_workspace_deployment_revision_annotations_are_current(location: str) -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-browser-"
    )
    annotations = (
        deployment["metadata"]["annotations"]
        if location == "metadata"
        else deployment["spec"]["template"]["metadata"]["annotations"]
    )
    annotations["aileron.io/component-revision"] = "999"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    ("component", "field", "value"),
    [
        ("runtime", "podUid", "stale-pod-uid"),
        ("runtime", "observedInstanceId", str(uuid.uuid4())),
        ("runtime", "observedRevision", 999),
        ("runtime", "terminalReady", False),
        ("runtime", "mountObservedRevision", 999),
        ("runtime", "lastKnownGoodMountRevision", 999),
        ("runtime", "accessObservedRevision", 999),
        ("browser", "podUid", "stale-pod-uid"),
        ("browser", "credentialObservedRevision", 999),
        ("browser", "credentialObservedKeyId", "stale-key"),
        ("browser", "credentialObservedAlgorithm", "stale-algorithm"),
        ("canvas", "podUid", "stale-pod-uid"),
    ],
)
def test_workspace_component_status_is_bound_to_spec_and_unique_pod(
    component: str, field: str, value: object
) -> None:
    documents = _documents()
    documents["workspace"]["items"][0]["status"]["components"][component][field] = value

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_workspace_component_status_requires_pod_uid() -> None:
    documents = _documents()
    del documents["workspace"]["items"][0]["status"]["components"]["runtime"]["podUid"]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("field", ["type", "ports", "selector"])
def test_service_contract_and_selected_target_pod_are_exact(field: str) -> None:
    documents = _documents()
    service = _find(documents, "services", prefix="workspace-browser-")
    if field == "type":
        service["spec"][field] = "LoadBalancer"
    elif field == "ports":
        service["spec"][field][0]["targetPort"] = 9999
    else:
        service["spec"][field]["aileron.io/runtime-instance-id"] = "spoof"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("externalTrafficPolicy", "Cluster"),
        ("loadBalancerIP", "192.0.2.1"),
        ("unknownField", "value"),
    ],
)
def test_service_rejects_noncanonical_api_fields(field: str, value: str) -> None:
    documents = _documents()
    service = _find(documents, "services", prefix="workspace-runtime-")
    service["spec"][field] = value

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_service_rejects_nodeport_on_clusterip_service() -> None:
    documents = _documents()
    service = _find(documents, "services", prefix="workspace-runtime-")
    service["spec"]["ports"][0]["nodePort"] = 32002

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "field",
    [
        "internalTrafficPolicy",
        "ipFamilies",
        "ipFamilyPolicy",
        "sessionAffinity",
    ],
)
def test_service_requires_every_canonical_api_default(field: str) -> None:
    documents = _documents()
    service = _find(documents, "services", prefix="workspace-runtime-")
    del service["spec"][field]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_service_ipv4_family_rejects_ipv6_cluster_ip() -> None:
    documents = _documents()
    service = _find(documents, "services", prefix="workspace-runtime-")
    service["spec"]["clusterIP"] = "fd00::11"
    service["spec"]["clusterIPs"] = ["fd00::11"]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_managed_services_require_unique_cluster_ips() -> None:
    documents = _documents()
    runtime = _find(documents, "services", prefix="workspace-runtime-")
    browser = _find(documents, "services", prefix="workspace-browser-")
    browser["spec"]["clusterIP"] = runtime["spec"]["clusterIP"]
    browser["spec"]["clusterIPs"] = copy.deepcopy(runtime["spec"]["clusterIPs"])

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "trigger_timestamp",
    [
        "2026-08-10T00:00:00Z",
        "2026-08-10T00:00:00.123456789Z",
    ],
)
def test_endpoint_slice_allows_controller_zone_hints_and_trigger_annotation(
    trigger_timestamp: str,
) -> None:
    documents = _documents()
    endpoint_slice = _find(documents, "endpointSlices", prefix="workspace-runtime-")
    endpoint_slice["metadata"]["annotations"] = {
        "endpoints.kubernetes.io/last-change-trigger-time": trigger_timestamp
    }
    endpoint_slice["endpoints"][0]["zone"] = "homelab-zone"
    endpoint_slice["endpoints"][0]["hints"] = {"forZones": [{"name": "homelab-zone"}]}

    snapshot = _snapshot(documents)

    assert snapshot["services"][0]["endpointSlices"]


def test_endpoint_slice_ports_are_an_unordered_exact_projection() -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    endpoint_slice = _find(documents, "endpointSlices", prefix="workspace-runtime-")
    endpoint_slice["ports"].reverse()

    assert _snapshot(documents) == baseline


@pytest.mark.parametrize("attack", ["duplicate", "changed"])
def test_endpoint_slice_ports_reject_duplicate_or_changed_entries(
    attack: str,
) -> None:
    documents = _documents()
    endpoint_slice = _find(documents, "endpointSlices", prefix="workspace-runtime-")
    if attack == "duplicate":
        endpoint_slice["ports"].append(copy.deepcopy(endpoint_slice["ports"][0]))
    else:
        endpoint_slice["ports"][0]["port"] = 9999

    with pytest.raises(
        MODULE.SoakValidationError,
        match="Workspace EndpointSlice ports are invalid",
    ):
        _snapshot(documents)


@pytest.mark.parametrize(
    "trigger_timestamp",
    [
        "2026-08-10T00:00:00+00:00",
        "2026-08-10T00:00:00-07:00",
        "2026-08-10 00:00:00Z",
        "2026-08-10T00:00:00z",
        "2026-08-10T00:00:00.1234567890Z",
        "2026-02-30T00:00:00Z",
    ],
)
def test_endpoint_slice_rejects_noncanonical_utc_trigger_timestamp(
    trigger_timestamp: str,
) -> None:
    documents = _documents()
    endpoint_slice = _find(documents, "endpointSlices", prefix="workspace-runtime-")
    endpoint_slice["metadata"]["annotations"] = {
        "endpoints.kubernetes.io/last-change-trigger-time": trigger_timestamp
    }

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "attack",
    [
        "owner-uid",
        "namespace",
        "service-name",
        "managed-by",
        "address-type",
        "ports",
        "pod-name",
        "pod-uid",
        "address",
        "conditions",
        "node-name",
        "missing",
        "stale-empty",
    ],
)
def test_endpoint_slice_is_exact_service_to_pod_closure(attack: str) -> None:
    documents = _documents()
    endpoint_slice = _find(documents, "endpointSlices", prefix="workspace-runtime-")
    if attack == "owner-uid":
        endpoint_slice["metadata"]["ownerReferences"][0]["uid"] = "old-service-uid"
    elif attack == "namespace":
        endpoint_slice["metadata"]["namespace"] = "other-system"
    elif attack == "service-name":
        endpoint_slice["metadata"]["labels"][
            "kubernetes.io/service-name"
        ] = "workspace-browser-workspace-1"
    elif attack == "managed-by":
        endpoint_slice["metadata"]["labels"][
            "endpointslice.kubernetes.io/managed-by"
        ] = "custom-controller"
    elif attack == "address-type":
        endpoint_slice["addressType"] = "IPv6"
    elif attack == "ports":
        endpoint_slice["ports"][0]["port"] = 9999
    elif attack == "pod-name":
        endpoint_slice["endpoints"][0]["targetRef"]["name"] = "stale-pod"
    elif attack == "pod-uid":
        endpoint_slice["endpoints"][0]["targetRef"]["uid"] = "stale-pod-uid"
    elif attack == "address":
        endpoint_slice["endpoints"][0]["addresses"] = ["10.42.255.254"]
    elif attack == "conditions":
        endpoint_slice["endpoints"][0]["conditions"]["ready"] = False
    elif attack == "node-name":
        endpoint_slice["endpoints"][0]["nodeName"] = "stale-node"
    elif attack == "missing":
        documents["endpointSlices"]["items"].remove(endpoint_slice)
    else:
        stale = _json_copy(endpoint_slice)
        stale["metadata"]["name"] = (
            f"{stale['metadata']['generateName']}"
            f"{_safe_kubernetes_hash('stale-empty')[:5]}"
        )
        stale["metadata"]["uid"] = f"{stale['metadata']['name']}-uid"
        stale["endpoints"] = []
        documents["endpointSlices"]["items"].append(stale)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_controller_and_replicaset_allow_only_pod_template_hash_delta() -> None:
    documents = _documents()
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-canvas-"
    )
    replica_set["spec"]["selector"]["matchLabels"]["unexpected"] = "value"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_runtime_replicaset_selector_uses_deployment_selector_not_template_labels() -> (
    None
):
    documents = _documents()
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )

    assert (
        "aileron.io/runtime-instance-id"
        not in replica_set["spec"]["selector"]["matchLabels"]
    )
    assert (
        "aileron.io/runtime-instance-id"
        in replica_set["spec"]["template"]["metadata"]["labels"]
    )
    _snapshot(documents)


def test_zero_scaled_historical_replicaset_may_keep_an_old_immutable_template() -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    historical = _historical_replica_set(deployment)
    documents["controllers"]["items"].append(historical)

    _snapshot(documents)


@pytest.mark.parametrize("attack", ["nonzero", "mutable-image", "selector"])
def test_historical_replicaset_must_remain_zero_scaled_and_closed(attack: str) -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    historical = _historical_replica_set(deployment)
    if attack == "nonzero":
        historical["spec"]["replicas"] = 1
        historical["status"] = _controller_status("ReplicaSet")
    elif attack == "mutable-image":
        historical["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = "registry.example/runtime:latest"
    else:
        historical["spec"]["selector"]["matchLabels"]["unexpected"] = "value"
    documents["controllers"]["items"].append(historical)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_replicaset_rejects_non_safe_pod_template_hash() -> None:
    documents = _documents()
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-canvas-"
    )
    replica_set["metadata"]["labels"]["pod-template-hash"] = "abc123"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("invalid_hash", ["a", "A", "0", "1", "3"])
def test_controller_revision_rejects_non_safe_hash_alphabet(
    invalid_hash: str,
) -> None:
    documents = _documents()
    revision = _find(
        documents,
        "controllers",
        kind="ControllerRevision",
        prefix="aileron-coturn-",
    )
    revision["metadata"]["name"] = f"aileron-coturn-{invalid_hash}"
    revision["metadata"]["labels"]["controller-revision-hash"] = invalid_hash

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_replicaset_rejects_template_metadata_annotation_drift() -> None:
    documents = _documents()
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )
    replica_set["spec"]["template"]["metadata"]["annotations"] = {"unexpected": "drift"}

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("attack", ["non-null-creation", "unknown-key"])
def test_replicaset_template_metadata_allows_only_live_null_creation_timestamp(
    attack: str,
) -> None:
    documents = _documents()
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )
    metadata = replica_set["spec"]["template"]["metadata"]
    if attack == "non-null-creation":
        metadata["creationTimestamp"] = "2026-08-10T00:00:00Z"
    else:
        metadata["generateName"] = "unexpected-"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_statefulset_requires_matching_current_and_update_revisions() -> None:
    documents = _documents()
    stateful_set = _find(
        documents, "controllers", kind="StatefulSet", prefix="aileron-postgres"
    )
    stateful_set["status"]["updateRevision"] = "revision-2"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("component", ["postgres", "redis"])
@pytest.mark.parametrize("attack", ["hostname", "subdomain", "claim-name"])
def test_statefulset_pod_identity_and_claim_projection_are_exact(
    component: str, attack: str
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix=f"aileron-{component}-0")
    if attack == "hostname":
        pod["spec"]["hostname"] = "other-pod"
    elif attack == "subdomain":
        pod["spec"]["subdomain"] = "other-service"
    else:
        claim_volume = next(
            volume for volume in pod["spec"]["volumes"] if volume["name"] == "data"
        )
        claim_volume["persistentVolumeClaim"]["claimName"] = "other-claim"

    with pytest.raises(MODULE.SoakValidationError, match="Pod spec differs"):
        _snapshot(documents)


@pytest.mark.parametrize("attack", ["wrong", "gap", "duplicate"])
def test_statefulset_pod_ordinal_set_is_exact(attack: str) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="aileron-postgres-0")
    if attack == "wrong":
        pod["metadata"]["name"] = "aileron-postgres-10"
        pod["metadata"]["labels"][
            "statefulset.kubernetes.io/pod-name"
        ] = "aileron-postgres-10"
        pod["metadata"]["labels"]["apps.kubernetes.io/pod-index"] = "10"
    elif attack == "gap":
        stateful_set = _find(
            documents,
            "controllers",
            kind="StatefulSet",
            prefix="aileron-postgres",
        )
        stateful_set["spec"]["replicas"] = 2
        stateful_set["status"] = _controller_status("StatefulSet", 2)
        stateful_set["status"]["currentRevision"] = pod["metadata"]["labels"][
            "controller-revision-hash"
        ]
        stateful_set["status"]["updateRevision"] = stateful_set["status"][
            "currentRevision"
        ]
        second = _json_copy(pod)
        second["metadata"]["name"] = "aileron-postgres-2"
        second["metadata"]["uid"] = "aileron-postgres-2-uid"
        second["metadata"]["labels"][
            "statefulset.kubernetes.io/pod-name"
        ] = "aileron-postgres-2"
        second["metadata"]["labels"]["apps.kubernetes.io/pod-index"] = "2"
        documents["workspacePods"]["items"].append(second)
    else:
        duplicate = _json_copy(pod)
        duplicate["metadata"]["uid"] = "duplicate-stateful-pod-uid"
        documents["workspacePods"]["items"].append(duplicate)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("attack", ["misscheduled", "empty-node", "duplicate-node"])
def test_daemonset_pod_node_closure_is_exact(attack: str) -> None:
    documents = _documents()
    daemon_set = _find(
        documents, "controllers", kind="DaemonSet", prefix="aileron-coturn"
    )
    pod = _find(documents, "turnPods", prefix="aileron-coturn-")
    if attack == "misscheduled":
        daemon_set["status"]["numberMisscheduled"] = 1
    elif attack == "empty-node":
        pod["spec"]["nodeName"] = ""
    else:
        daemon_set["status"] = _controller_status("DaemonSet", 2)
        duplicate = _json_copy(pod)
        duplicate["metadata"]["name"] = "aileron-coturn-other"
        duplicate["metadata"]["uid"] = "aileron-coturn-other-uid"
        documents["turnPods"]["items"].append(duplicate)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    ("prefix", "source"),
    [
        ("workspace-runtime-", "workspacePods"),
        ("aileron-postgres-0", "workspacePods"),
    ],
)
def test_every_running_pod_requires_node_assignment(prefix: str, source: str) -> None:
    documents = _documents()
    pod = _find(documents, source, prefix=prefix)
    del pod["spec"]["nodeName"]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    ("owner_kind", "attack"),
    [
        ("ReplicaSet", "name"),
        ("ReplicaSet", "generate-name"),
        ("ReplicaSet", "missing-generate-name"),
        ("ReplicaSet", "unsafe-suffix"),
        ("ReplicaSet", "short-suffix"),
        ("DaemonSet", "name"),
        ("DaemonSet", "generate-name"),
        ("DaemonSet", "missing-generate-name"),
        ("DaemonSet", "unsafe-suffix"),
        ("DaemonSet", "short-suffix"),
    ],
)
def test_controller_created_pod_name_identity_is_exact(
    owner_kind: str, attack: str
) -> None:
    documents = _documents()
    source = "turnPods" if owner_kind == "DaemonSet" else "workspacePods"
    prefix = "aileron-coturn-" if owner_kind == "DaemonSet" else "workspace-runtime-"
    pod = _find(documents, source, prefix=prefix)
    if attack == "name":
        pod["metadata"]["name"] = "arbitrary-bcdfg"
    elif attack == "generate-name":
        pod["metadata"]["generateName"] = "arbitrary-"
    elif attack == "missing-generate-name":
        del pod["metadata"]["generateName"]
    else:
        effective_base = pod["metadata"]["generateName"][:58]
        suffix = "aaaaa" if attack == "unsafe-suffix" else "bcdf"
        pod["metadata"]["name"] = f"{effective_base}{suffix}"

    with pytest.raises(MODULE.SoakValidationError, match="Pod lifecycle is invalid"):
        _snapshot(documents)


def test_controller_created_pod_accepts_long_generated_name_truncation() -> None:
    documents = _documents()
    workspace_id = "w" * 36
    _add_workspace_graph(
        documents,
        _workspace(workspace_id, "long-workspace-uid", "long-owner"),
    )
    owner_prefix = f"workspace-runtime-{workspace_id}"
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix=owner_prefix
    )
    pod = _find(documents, "workspacePods", prefix=owner_prefix)
    generate_name = f"{replica_set['metadata']['name']}-"
    suffix = pod["metadata"]["name"][58:]

    assert len(generate_name) > 58
    assert pod["metadata"]["generateName"] == generate_name
    assert pod["metadata"]["name"] == f"{generate_name[:58]}{suffix}"
    assert len(pod["metadata"]["name"]) == 63
    assert MODULE.KUBERNETES_SAFE_HASH.fullmatch(suffix) is not None
    _snapshot(documents)


def test_pod_rejects_contradictory_duplicate_ready_condition() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    pod["status"]["conditions"].append({"type": "Ready", "status": "False"})

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "failure",
    [
        "ready",
        "init",
        "ephemeral",
        "ephemeral-status",
        "started",
        "image",
        "terminating",
    ],
)
def test_pod_lifecycle_and_image_contract_is_closed(failure: str) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    if failure == "ready":
        pod["status"]["conditions"][0]["status"] = "False"
    elif failure == "init":
        pod["status"]["initContainerStatuses"][0]["state"]["terminated"]["exitCode"] = 1
    elif failure == "ephemeral":
        pod["spec"]["ephemeralContainers"] = [
            {"name": "debug", "image": _immutable_image("9")}
        ]
    elif failure == "ephemeral-status":
        pod["status"]["ephemeralContainerStatuses"] = [
            {"name": "debug", "restartCount": 0}
        ]
    elif failure == "started":
        pod["status"]["containerStatuses"][0]["started"] = False
    elif failure == "image":
        pod["spec"]["containers"][0]["image"] = "registry.example/runtime:latest"
    else:
        pod["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "attack",
    [
        "host-pid",
        "host-ipc",
        "host-users",
        "host-path",
        "service-account",
        "node-selector",
        "affinity",
        "unknown-field",
    ],
)
def test_pod_full_spec_rejects_privilege_and_owner_template_drift(
    attack: str,
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    if attack == "host-pid":
        pod["spec"]["hostPID"] = True
    elif attack == "host-ipc":
        pod["spec"]["hostIPC"] = True
    elif attack == "host-users":
        pod["spec"]["hostUsers"] = True
    elif attack == "host-path":
        pod["spec"]["volumes"] = [{"name": "host-root", "hostPath": {"path": "/"}}]
    elif attack == "service-account":
        pod["spec"]["serviceAccountName"] = "cluster-admin"
    elif attack == "node-selector":
        pod["spec"]["nodeSelector"] = {"kubernetes.io/hostname": "other-node"}
    elif attack == "affinity":
        pod["spec"]["affinity"] = {
            "nodeAffinity": {
                "requiredDuringSchedulingIgnoredDuringExecution": {
                    "nodeSelectorTerms": []
                }
            }
        }
    else:
        pod["spec"]["unknownField"] = "forged"

    with pytest.raises(MODULE.SoakValidationError, match="Pod spec differs"):
        _snapshot(documents)


@pytest.mark.parametrize("container_kind", ["main", "init"])
def test_pod_container_image_is_bound_to_owner_template(
    container_kind: str,
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    spec_key = "containers" if container_kind == "main" else "initContainers"
    status_key = (
        "containerStatuses" if container_kind == "main" else "initContainerStatuses"
    )
    replacement = _immutable_image(f"drift-{container_kind}")
    pod["spec"][spec_key][0]["image"] = replacement
    pod["status"][status_key][0]["image"] = replacement
    pod["status"][status_key][0]["imageID"] = f"docker-pullable://{replacement}"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_pod_status_image_is_bound_to_pod_spec() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-canvas-")
    pod["status"]["containerStatuses"][0]["image"] = _immutable_image("status-drift")

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_host_network_host_port_default_is_normalized_against_daemon_template() -> None:
    documents = _documents()
    controller = _find(
        documents, "controllers", kind="DaemonSet", prefix="aileron-coturn"
    )
    revision = _find(
        documents,
        "controllers",
        kind="ControllerRevision",
        prefix="aileron-coturn-",
    )
    pod = _find(documents, "turnPods", prefix="aileron-coturn-")
    template_spec = controller["spec"]["template"]["spec"]
    template_spec["hostNetwork"] = True
    template_spec["containers"][0]["ports"] = [
        {"name": "turn", "containerPort": 3478, "protocol": "UDP"}
    ]
    revision["data"]["spec"]["template"]["spec"] = copy.deepcopy(template_spec)
    pod["spec"]["hostNetwork"] = True
    pod["status"]["podIP"] = pod["status"]["hostIP"]
    pod["status"]["podIPs"] = [{"ip": pod["status"]["hostIP"]}]
    pod["spec"]["containers"][0]["ports"] = [
        {
            "name": "turn",
            "containerPort": 3478,
            "hostPort": 3478,
            "protocol": "UDP",
        }
    ]
    pod["spec"]["tolerations"] = [
        {
            "key": "node.kubernetes.io/not-ready",
            "operator": "Exists",
            "effect": "NoExecute",
        },
        {
            "key": "node.kubernetes.io/unreachable",
            "operator": "Exists",
            "effect": "NoExecute",
        },
        {
            "key": "node.kubernetes.io/disk-pressure",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
        {
            "key": "node.kubernetes.io/memory-pressure",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
        {
            "key": "node.kubernetes.io/pid-pressure",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
        {
            "key": "node.kubernetes.io/unschedulable",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
        {
            "key": "node.kubernetes.io/network-unavailable",
            "operator": "Exists",
            "effect": "NoSchedule",
        },
    ]
    pod["spec"]["affinity"] = {
        "nodeAffinity": {
            "requiredDuringSchedulingIgnoredDuringExecution": {
                "nodeSelectorTerms": [
                    {
                        "matchFields": [
                            {
                                "key": "metadata.name",
                                "operator": "In",
                                "values": [pod["spec"]["nodeName"]],
                            }
                        ]
                    }
                ]
            }
        }
    }

    _snapshot(documents)


@pytest.mark.parametrize("request_value", [None, "250m"])
def test_limit_to_request_pod_default_is_normalized_only_when_exact(
    request_value: str | None,
) -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="aileron-frontend"
    )
    replica_set = next(
        item
        for item in documents["controllers"]["items"]
        if item.get("kind") == "ReplicaSet"
        and item["metadata"]["ownerReferences"][0]["uid"]
        == deployment["metadata"]["uid"]
    )
    pod = _find(documents, "workspacePods", prefix="aileron-frontend-")
    limits = {"cpu": "200m", "memory": "128Mi"}
    deployment["spec"]["template"]["spec"]["containers"][0]["resources"] = {
        "limits": copy.deepcopy(limits)
    }
    replica_set["spec"]["template"]["spec"]["containers"][0]["resources"] = {
        "limits": copy.deepcopy(limits)
    }
    requests = copy.deepcopy(limits)
    if request_value is not None:
        requests["cpu"] = request_value
    pod["spec"]["containers"][0]["resources"] = {
        "limits": copy.deepcopy(limits),
        "requests": requests,
    }

    if request_value is None:
        _snapshot(documents)
    else:
        with pytest.raises(MODULE.SoakValidationError):
            _snapshot(documents)


@pytest.mark.parametrize(
    "attack",
    ["pod-ips", "ipv6", "noncanonical", "host-ip", "host-ips"],
)
def test_running_pod_requires_one_canonical_ipv4_status_address(attack: str) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    if attack == "pod-ips":
        pod["status"]["podIPs"] = [{"ip": "10.42.255.254"}]
    elif attack == "ipv6":
        pod["status"]["podIP"] = "fd00::1"
        pod["status"]["podIPs"] = [{"ip": "fd00::1"}]
    else:
        if attack == "noncanonical":
            pod["status"]["podIP"] = "010.042.001.001"
            pod["status"]["podIPs"] = [{"ip": "010.042.001.001"}]
        elif attack == "host-ip":
            pod["status"]["hostIP"] = "fd00::1"
            pod["status"]["hostIPs"] = [{"ip": "fd00::1"}]
        else:
            pod["status"]["hostIPs"] = [{"ip": "192.0.2.254"}]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_host_network_pod_ip_must_equal_its_host_ip() -> None:
    documents = _documents()
    controller = _find(
        documents, "controllers", kind="DaemonSet", prefix="aileron-coturn"
    )
    revision = _find(
        documents,
        "controllers",
        kind="ControllerRevision",
        prefix="aileron-coturn-",
    )
    pod = _find(documents, "turnPods", prefix="aileron-coturn-")
    controller["spec"]["template"]["spec"]["hostNetwork"] = True
    revision["data"]["spec"]["template"]["spec"]["hostNetwork"] = True
    pod["spec"]["hostNetwork"] = True

    with pytest.raises(MODULE.SoakValidationError, match="Pod lifecycle"):
        _snapshot(documents)


def test_host_network_pods_on_one_node_may_share_the_node_ip() -> None:
    documents = _documents()
    resources = [
        ("aileron-coturn", "turnPods"),
        ("aileron-workspace-firewall-attestor", "workspacePods"),
    ]
    for controller_prefix, pod_source in resources:
        controller = _find(
            documents,
            "controllers",
            kind="DaemonSet",
            prefix=controller_prefix,
        )
        revision = _find(
            documents,
            "controllers",
            kind="ControllerRevision",
            prefix=f"{controller_prefix}-",
        )
        pod = _find(documents, pod_source, prefix=f"{controller_prefix}-")
        controller["spec"]["template"]["spec"]["hostNetwork"] = True
        revision["data"]["spec"]["template"]["spec"]["hostNetwork"] = True
        pod["spec"]["hostNetwork"] = True
        pod["spec"]["nodeName"] = "shared-homelab-node"
        pod["status"]["podIP"] = "192.0.2.10"
        pod["status"]["podIPs"] = [{"ip": "192.0.2.10"}]
        pod["status"]["hostIP"] = "192.0.2.10"
        pod["status"]["hostIPs"] = [{"ip": "192.0.2.10"}]

    _snapshot(documents)


def test_host_network_pods_on_one_node_require_one_node_ip() -> None:
    documents = _documents()
    resources = [
        ("aileron-coturn", "turnPods", "192.0.2.10"),
        (
            "aileron-workspace-firewall-attestor",
            "workspacePods",
            "192.0.2.11",
        ),
    ]
    for controller_prefix, pod_source, pod_ip in resources:
        controller = _find(
            documents,
            "controllers",
            kind="DaemonSet",
            prefix=controller_prefix,
        )
        revision = _find(
            documents,
            "controllers",
            kind="ControllerRevision",
            prefix=f"{controller_prefix}-",
        )
        pod = _find(documents, pod_source, prefix=f"{controller_prefix}-")
        controller["spec"]["template"]["spec"]["hostNetwork"] = True
        revision["data"]["spec"]["template"]["spec"]["hostNetwork"] = True
        pod["spec"]["hostNetwork"] = True
        pod["spec"]["nodeName"] = "shared-homelab-node"
        pod["status"]["podIP"] = pod_ip
        pod["status"]["podIPs"] = [{"ip": pod_ip}]
        pod["status"]["hostIP"] = pod_ip
        pod["status"]["hostIPs"] = [{"ip": pod_ip}]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_signed_runtime_manifest_image_id_is_valid_for_an_index_pinned_spec() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    image_runtime_pairs = _image_runtime_pairs(documents)
    spec_image = pod["spec"]["containers"][0]["image"]
    index_digest = spec_image.rsplit("@sha256:", 1)[1]
    platform_digest = next(iter(image_runtime_pairs[spec_image] - {index_digest}))
    repository = spec_image.rsplit("@", 1)[0]
    pod["status"]["containerStatuses"][0]["imageID"] = (
        f"docker-pullable://{repository}@sha256:" + platform_digest
    )

    _snapshot(documents, image_runtime_pairs=image_runtime_pairs)


@pytest.mark.parametrize("container_kind", ["main", "init"])
def test_rke2_digest_only_status_image_is_valid_for_pinned_spec(
    container_kind: str,
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    status_key = (
        "containerStatuses" if container_kind == "main" else "initContainerStatuses"
    )
    pod["status"][status_key][0]["image"] = "sha256:" + "a" * 64

    _snapshot(documents, image_runtime_pairs=_image_runtime_pairs(documents))


@pytest.mark.parametrize("container_kind", ["main", "init"])
def test_unsigned_third_runtime_digest_is_rejected_for_every_container_kind(
    container_kind: str,
) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    status_key = (
        "containerStatuses" if container_kind == "main" else "initContainerStatuses"
    )
    pod["status"][status_key][0]["imageID"] = (
        "docker-pullable://registry.example/runtime@sha256:" + "f" * 64
    )

    with pytest.raises(
        MODULE.SoakValidationError,
        match=f"soak {container_kind} container .* is invalid",
    ):
        _snapshot(documents)


def test_signed_runtime_digest_with_a_different_repository_is_rejected() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    image_runtime_pairs = _image_runtime_pairs(documents)
    spec_image = pod["spec"]["containers"][0]["image"]
    index_digest = spec_image.rsplit("@sha256:", 1)[1]
    runtime_digest = next(iter(image_runtime_pairs[spec_image] - {index_digest}))
    pod["status"]["containerStatuses"][0]["imageID"] = (
        "docker-pullable://registry.example/foreign@sha256:" + runtime_digest
    )

    with pytest.raises(MODULE.SoakValidationError, match="runtime identity"):
        _snapshot(documents, image_runtime_pairs=image_runtime_pairs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("imageID", "docker-pullable://registry.example/runtime:latest"),
        ("containerID", "docker://not-an-rke2-container-id"),
        ("containerID", "containerd://xyz"),
    ],
)
def test_pod_runtime_identity_rejects_malformed_ids(field: str, value: str) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-canvas-")
    pod["status"]["containerStatuses"][0][field] = value

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_pod_annotations_are_bound_to_owner_template() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-browser-")
    pod["metadata"]["annotations"]["aileron.io/component-revision"] = "999"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_canonical_service_account_projection_is_normalized() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    _inject_service_account_projection(pod)

    _snapshot(documents)


def test_pod_only_enable_service_links_default_must_be_exact_true() -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    pod["spec"]["enableServiceLinks"] = False

    with pytest.raises(MODULE.SoakValidationError, match="Pod spec differs"):
        _snapshot(documents)


def test_disabled_service_account_automount_rejects_injected_projection() -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    for template_spec in (
        deployment["spec"]["template"]["spec"],
        replica_set["spec"]["template"]["spec"],
    ):
        template_spec["automountServiceAccountToken"] = False
    pod["spec"]["automountServiceAccountToken"] = False
    _inject_service_account_projection(pod)

    with pytest.raises(MODULE.SoakValidationError, match="Pod spec differs"):
        _snapshot(documents)


def test_canonical_pod_admission_defaults_are_normalized() -> None:
    documents = _documents()
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
    )
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
    )
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    service_account_name = deployment["spec"]["template"]["spec"]["serviceAccountName"]
    assert (
        replica_set["spec"]["template"]["spec"]["serviceAccountName"]
        == service_account_name
    )
    pod["spec"].update(
        {
            "preemptionPolicy": "PreemptLowerPriority",
            "priority": 0,
            "serviceAccount": service_account_name,
            "serviceAccountName": service_account_name,
            "tolerations": [
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
        }
    )
    _inject_service_account_projection(pod)

    _snapshot(documents)


@pytest.mark.parametrize("attack", ["expiration", "extra-mount"])
def test_noncanonical_service_account_projection_is_rejected(attack: str) -> None:
    documents = _documents()
    pod = _find(documents, "workspacePods", prefix="workspace-runtime-")
    _inject_service_account_projection(
        pod,
        expiration_seconds=3600 if attack == "expiration" else 3607,
        extra_mount=attack == "extra-mount",
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize("owner", ["fixed", "other-workspace"])
def test_managed_pod_labels_must_exactly_equal_owner_template(owner: str) -> None:
    documents = _documents()
    if owner == "fixed":
        pod = _find(documents, "workspacePods", prefix="aileron-frontend-")
    else:
        _add_workspace_graph(
            documents, _workspace("workspace-2", "workspace-uid-2", "owner-2")
        )
        pod = _find(documents, "workspacePods", prefix="workspace-canvas-workspace-2")
    pod["metadata"]["labels"]["unexpected"] = "spoof"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_daemonset_pod_template_generation_accepts_exact_owner_generation() -> None:
    documents = _documents()
    daemon_set = _find(
        documents, "controllers", kind="DaemonSet", prefix="aileron-coturn"
    )
    pod = _find(documents, "turnPods", prefix="aileron-coturn-")
    daemon_set["metadata"]["generation"] = 7
    daemon_set["status"]["observedGeneration"] = 7
    pod["metadata"]["labels"]["pod-template-generation"] = "7"

    assert (
        "pod-template-generation"
        not in daemon_set["spec"]["template"]["metadata"]["labels"]
    )
    _snapshot(documents)


@pytest.mark.parametrize("label_value", [None, "2"], ids=["missing", "wrong"])
def test_daemonset_pod_template_generation_must_match_owner_generation(
    label_value: str | None,
) -> None:
    documents = _documents()
    pod = _find(documents, "turnPods", prefix="aileron-coturn-")
    if label_value is None:
        pod["metadata"]["labels"].pop("pod-template-generation")
    else:
        pod["metadata"]["labels"]["pod-template-generation"] = label_value

    with pytest.raises(
        MODULE.SoakValidationError,
        match="soak Pod labels differ from its owner projection",
    ):
        _snapshot(documents)


@pytest.mark.parametrize(
    "attack",
    [
        "stateful-revision",
        "stateful-pod-name",
        "stateful-pod-index",
        "stateful-extra-label",
        "daemon-revision",
        "daemon-extra-label",
        "daemon-revision-data",
        "daemon-revision-owner",
    ],
)
def test_server_injected_pod_labels_are_bound_to_controller_revisions(
    attack: str,
) -> None:
    documents = _documents()
    if attack.startswith("stateful"):
        pod = _find(documents, "workspacePods", prefix="aileron-postgres-")
        if attack == "stateful-revision":
            pod["metadata"]["labels"]["controller-revision-hash"] = "other"
        elif attack == "stateful-pod-name":
            pod["metadata"]["labels"][
                "statefulset.kubernetes.io/pod-name"
            ] = "aileron-postgres-1"
        elif attack == "stateful-pod-index":
            pod["metadata"]["labels"]["apps.kubernetes.io/pod-index"] = "1"
        else:
            pod["metadata"]["labels"]["unexpected"] = "spoof"
    elif attack in {"daemon-revision", "daemon-extra-label"}:
        pod = _find(documents, "turnPods", prefix="aileron-coturn-")
        if attack == "daemon-revision":
            pod["metadata"]["labels"]["controller-revision-hash"] = "other"
        else:
            pod["metadata"]["labels"]["unexpected"] = "spoof"
    else:
        revision = _find(
            documents,
            "controllers",
            kind="ControllerRevision",
            prefix="aileron-coturn-",
        )
        if attack == "daemon-revision-data":
            revision["data"]["spec"]["template"]["spec"]["hostNetwork"] = True
        else:
            revision["metadata"]["ownerReferences"][0]["uid"] = "other-uid"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_controller_revision_inventory_is_included_in_the_snapshot() -> None:
    snapshot = _snapshot()

    assert {
        (item["ownerKind"], item["ownerName"])
        for item in snapshot["controllerRevisions"]
    } == {
        (kind, name)
        for kind, _, name, _ in FIXED_CONTROLLERS
        if kind in {"StatefulSet", "DaemonSet"}
    }
    assert all(item["dataSha256"] for item in snapshot["controllerRevisions"])


@pytest.mark.parametrize("spoof_source", ["fixed", "other-workspace"])
def test_service_selector_must_select_exactly_one_validated_target_pod(
    spoof_source: str,
) -> None:
    documents = _documents()
    target_service = _find(documents, "services", prefix="workspace-runtime-")
    if spoof_source == "fixed":
        pod = _find(documents, "workspacePods", prefix="aileron-frontend-")
    else:
        _add_workspace_graph(
            documents, _workspace("workspace-2", "workspace-uid-2", "owner-2")
        )
        pod = _find(documents, "workspacePods", prefix="workspace-canvas-workspace-2")
    pod["metadata"]["labels"].update(target_service["spec"]["selector"])

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


@pytest.mark.parametrize(
    "failure", ["secondary-runtime", "probe-period", "probe-shape"]
)
def test_browser_sources_and_probe_timing_are_exact(failure: str) -> None:
    documents = _documents()
    browser = documents["browserPods"]["items"][0]
    if failure == "secondary-runtime":
        browser["status"]["containerStatuses"][0]["containerID"] = (
            "containerd://" + "f" * 64
        )
    elif failure == "probe-period":
        browser["spec"]["containers"][0]["readinessProbe"]["periodSeconds"] = 6
    else:
        browser["spec"]["containers"][0]["readinessProbe"] = "ready"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_other_workspace_is_isolated_only_by_true_owner_closure() -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    _add_workspace_graph(
        documents, _workspace("workspace-2", "workspace-uid-2", "owner-2")
    )
    assert _snapshot(documents) == baseline
    other = _find(
        documents,
        "controllers",
        kind="Deployment",
        prefix="workspace-runtime-workspace-2",
    )
    other["metadata"]["ownerReferences"][0]["uid"] = "spoofed-uid"
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_running_non_target_workspace_requires_complete_component_graph() -> None:
    documents = _documents()
    workspace = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    documents["workspace"]["items"].append(workspace)
    documents["workspaceServiceAccounts"]["items"].append(
        _workspace_service_account(workspace)
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_running_non_target_workspace_requires_complete_service_graph() -> None:
    documents = _documents()
    _add_workspace_graph(
        documents, _workspace("workspace-2", "workspace-uid-2", "owner-2")
    )
    documents["services"]["items"] = [
        service
        for service in documents["services"]["items"]
        if service["metadata"]["name"] != "workspace-browser-workspace-2"
    ]

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_non_target_workspace_phase_must_match_component_status() -> None:
    documents = _documents()
    other = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    _add_workspace_graph(documents, other)
    other_document = next(
        item
        for item in documents["workspace"]["items"]
        if item["metadata"]["uid"] == "workspace-uid-2"
    )
    other_document["status"]["phase"] = "Degraded"

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_non_target_workspace_rejects_unknown_desired_state() -> None:
    documents = _documents()
    other = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    other["spec"]["runtime"]["desiredState"] = "Paused"
    documents["workspace"]["items"].append(other)

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_stopped_disabled_non_target_workspace_may_have_no_component_graph() -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    other = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    _set_workspace_stopped_status(other)
    documents["workspace"]["items"].append(other)
    documents["workspaceServiceAccounts"]["items"].append(
        _workspace_service_account(other)
    )

    assert _snapshot(documents) == baseline


def test_stopped_disabled_non_target_workspace_accepts_zero_scaled_graph() -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    _stopped_workspace_with_zero_scaled_graph(documents)

    assert _snapshot(documents) == baseline


def test_stopped_workspace_rejects_stale_pod_uid_status() -> None:
    documents = _documents()
    workspace = _workspace("workspace-2", "workspace-uid-2", "owner-2")
    _set_workspace_stopped_status(workspace)
    workspace["status"]["components"]["runtime"]["podUid"] = "stale-pod-uid"
    documents["workspace"]["items"].append(workspace)
    documents["workspaceServiceAccounts"]["items"].append(
        _workspace_service_account(workspace)
    )

    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def _add_acceptance_job(documents: dict, *, phase: str = "Succeeded") -> None:
    section = "restart"
    run_id = "run-restart-acceptance"
    labels = {
        "platform.aileron.dev/acceptance-section": section,
        "platform.aileron.dev/source-commit": COMMIT,
        "platform.aileron.dev/acceptance-run-id": run_id,
        "platform.aileron.dev/deployment-run-id": DEPLOYMENT_RUN_ID,
        "platform.aileron.dev/workspace-id": WORKSPACE_ID,
    }
    name = f"aileron-acceptance-{section}-{run_id[4:16]}"
    image = _immutable_image("8")
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": "workspace-system",
            "uid": f"{name}-uid",
            "labels": copy.deepcopy(labels),
            "ownerReferences": [],
        },
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {
                    "labels": {
                        **labels,
                        "batch.kubernetes.io/controller-uid": f"{name}-uid",
                        "batch.kubernetes.io/job-name": name,
                        "controller-uid": f"{name}-uid",
                        "job-name": name,
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{"name": "oracle", "image": image}],
                },
            },
        },
        "status": {
            "succeeded": 1 if phase == "Succeeded" else 0,
            "failed": 1 if phase == "Failed" else 0,
            "active": 1 if phase == "Running" else 0,
            "completionTime": "2026-08-10T00:00:01Z" if phase == "Succeeded" else None,
            "conditions": (
                [{"type": "Complete", "status": "True"}] if phase == "Succeeded" else []
            ),
        },
    }
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"{name}-pod",
            "namespace": "workspace-system",
            "uid": f"{name}-pod-uid",
            "labels": {
                **labels,
                "batch.kubernetes.io/controller-uid": f"{name}-uid",
                "batch.kubernetes.io/job-name": name,
                "controller-uid": f"{name}-uid",
                "job-name": name,
            },
            "ownerReferences": [
                _owner(
                    api_version="batch/v1",
                    kind="Job",
                    name=name,
                    uid=job["metadata"]["uid"],
                )
            ],
        },
        "spec": copy.deepcopy(job["spec"]["template"]["spec"]),
        "status": {
            "phase": phase,
            "containerStatuses": [
                _runtime_status({"name": "oracle", "image": image}, terminated=True)
            ],
            "initContainerStatuses": [],
        },
    }
    documents["controllers"]["items"].append(job)
    documents["workspacePods"]["items"].append(pod)


@pytest.mark.parametrize("phase", ["Succeeded", "Running", "Failed"])
def test_soak_requires_zero_jobs_and_job_owned_pods(phase: str) -> None:
    documents = _documents()
    _add_acceptance_job(documents, phase=phase)
    with pytest.raises(MODULE.SoakValidationError):
        _snapshot(documents)


def test_snapshot_digests_full_stable_specs_and_labels() -> None:
    documents = _documents()
    first = _snapshot(documents)
    service = _find(documents, "services", prefix="workspace-canvas-")
    service["spec"]["clusterIP"] = "10.43.0.33"
    service["spec"]["clusterIPs"] = ["10.43.0.33"]
    second = _snapshot(documents)
    assert first != second
    assert first["services"][2]["specSha256"] != second["services"][2]["specSha256"]

    documents = _documents()
    first = _snapshot(documents)
    controller = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-canvas-"
    )
    controller["spec"]["progressDeadlineSeconds"] = 600
    second = _snapshot(documents)
    first_controller = next(
        item
        for item in first["controllers"]
        if item["kind"] == "Deployment" and item["name"].startswith("workspace-canvas-")
    )
    second_controller = next(
        item
        for item in second["controllers"]
        if item["kind"] == "Deployment" and item["name"].startswith("workspace-canvas-")
    )
    assert first_controller["specSha256"] != second_controller["specSha256"]

    documents = _documents()
    first = _snapshot(documents)
    pod = _find(documents, "workspacePods", prefix="workspace-canvas-")
    deployment = _find(
        documents, "controllers", kind="Deployment", prefix="workspace-canvas-"
    )
    replica_set = _find(
        documents, "controllers", kind="ReplicaSet", prefix="workspace-canvas-"
    )
    deployment["spec"]["template"]["spec"]["dnsPolicy"] = "ClusterFirst"
    replica_set["spec"]["template"]["spec"]["dnsPolicy"] = "ClusterFirst"
    pod["spec"]["dnsPolicy"] = "ClusterFirst"
    documents["browserPods"] = _list(
        [_find(documents, "workspacePods", prefix="workspace-browser-")]
    )
    second = _snapshot(documents)
    first_pod = next(
        item for item in first["pods"] if item["component"] == "workspace-canvas"
    )
    second_pod = next(
        item for item in second["pods"] if item["component"] == "workspace-canvas"
    )
    assert first_pod["specSha256"] != second_pod["specSha256"]


def test_snapshots_include_full_canonical_status_digests() -> None:
    snapshot = _snapshot()

    assert snapshot["workspace"]["statusSha256"]
    assert all(item["statusSha256"] for item in snapshot["controllers"])
    assert all(item["statusSha256"] for item in snapshot["pods"])


def test_snapshot_ignores_only_workspace_browser_connectivity_lease_timestamps() -> (
    None
):
    documents = _documents()
    baseline = _snapshot(documents)
    browser_connectivity = documents["workspace"]["items"][0]["status"][
        "browserConnectivity"
    ]
    for field in (
        "acceptedAt",
        "expiresAt",
        "backendAcceptedAt",
        "backendExpiresAt",
        "frontendAcceptedAt",
        "frontendExpiresAt",
    ):
        browser_connectivity[field] = "2026-08-10T00:00:01Z"

    assert _snapshot(documents) == baseline


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", "Rejected"),
        ("reason", "Unhealthy"),
        ("admission", "Rejected"),
        ("contractVersion", "v2"),
        ("credentialRevision", 23),
        ("observedBrowserGeneration", 5),
        ("profileRevision", 8),
        ("lastTransitionAt", "2026-08-10T00:00:01Z"),
    ],
)
def test_snapshot_changes_for_semantic_browser_connectivity_drift(
    field: str, value: object
) -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    documents["workspace"]["items"][0]["status"]["browserConnectivity"][field] = value

    assert _snapshot(documents) != baseline


@pytest.mark.parametrize("resource", ["workspace", "deployment", "replicaset", "pod"])
def test_snapshot_changes_when_canonical_status_changes(resource: str) -> None:
    documents = _documents()
    baseline = _snapshot(documents)
    if resource == "workspace":
        document = documents["workspace"]["items"][0]
    elif resource == "deployment":
        document = _find(
            documents, "controllers", kind="Deployment", prefix="workspace-runtime-"
        )
    elif resource == "replicaset":
        document = _find(
            documents, "controllers", kind="ReplicaSet", prefix="workspace-runtime-"
        )
    else:
        document = _find(documents, "workspacePods", prefix="workspace-runtime-")
    document["status"]["canonicalExtra"] = "drift"

    assert _snapshot(documents) != baseline


def test_acceptance_soak_exports_no_unused_sha256_pattern() -> None:
    assert not hasattr(MODULE, "SHA256")


def test_cadence_rejects_nonfinite_or_nonincreasing_monotonic_values() -> None:
    policy = MODULE.SoakPolicy(1800, 60, 75, 31, 2000)
    started = datetime(2026, 8, 10, tzinfo=UTC)
    samples = [started + timedelta(seconds=60 * index) for index in range(31)]
    elapsed = [60_000 * index for index in range(31)]
    elapsed[8] = elapsed[7]
    with pytest.raises(MODULE.SoakValidationError):
        MODULE.validate_cadence(
            started=started,
            finished=started + timedelta(seconds=1800),
            sample_times=samples,
            sample_elapsed_milliseconds=elapsed,
            monotonic_duration_milliseconds=1_800_000,
            policy=policy,
        )
    assert not math.isfinite(float("nan"))


def test_cadence_accepts_exact_31_sample_30_minute_window() -> None:
    policy = MODULE.SoakPolicy(1800, 60, 75, 31, 2000)
    started = datetime(2026, 8, 10, tzinfo=UTC)
    samples = [started + timedelta(seconds=60 * index) for index in range(31)]
    MODULE.validate_cadence(
        started=started,
        finished=started + timedelta(seconds=1800),
        sample_times=samples,
        sample_elapsed_milliseconds=[60_000 * index for index in range(31)],
        monotonic_duration_milliseconds=1_800_000,
        policy=policy,
    )


def test_cadence_rejects_more_than_the_exact_sample_count() -> None:
    policy = MODULE.SoakPolicy(1800, 60, 75, 31, 2000)
    started = datetime(2026, 8, 10, tzinfo=UTC)
    samples = [started + timedelta(seconds=60 * index) for index in range(32)]

    with pytest.raises(MODULE.SoakValidationError, match="sample count"):
        MODULE.validate_cadence(
            started=started,
            finished=started + timedelta(seconds=1860),
            sample_times=samples,
            sample_elapsed_milliseconds=[60_000 * index for index in range(32)],
            monotonic_duration_milliseconds=1_860_000,
            policy=policy,
        )


def test_cadence_rejects_cumulative_wall_clock_drift() -> None:
    policy = MODULE.SoakPolicy(1800, 60, 75, 31, 2000)
    started = datetime(2026, 8, 10, tzinfo=UTC)
    samples = [
        started + timedelta(milliseconds=60_000 * index + 100 * index)
        for index in range(31)
    ]

    with pytest.raises(MODULE.SoakValidationError, match="clock drift"):
        MODULE.validate_cadence(
            started=started,
            finished=started + timedelta(milliseconds=1_803_000),
            sample_times=samples,
            sample_elapsed_milliseconds=[60_000 * index for index in range(31)],
            monotonic_duration_milliseconds=1_800_000,
            policy=policy,
        )
