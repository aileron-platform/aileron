#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


TARGET_NAMESPACES = {
    "workspace-system",
    "aileron-turn-system",
    "aileron-identity-system",
}
TARGET_STORAGE_CLASSES = {
    "aileron-nfs-rwx-delete",
    "aileron-nfs-rwx-retain",
    "aileron-local-rwo-delete",
    "aileron-local-rwo-retain",
}
RESOURCE_IDENTITY_COLUMNS = (
    "custom-columns=API_VERSION:.apiVersion,KIND:.kind,"
    "NAMESPACE:.metadata.namespace,NAME:.metadata.name,"
    "UID:.metadata.uid,RESOURCE_VERSION:.metadata.resourceVersion"
)
RANCHER_APP_RESOURCE = "apps.catalog.cattle.io"


def _subprocess_runner(command: list[str]) -> str:
    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
    )
    return result.stdout


def _load_json_object(document: str, description: str) -> dict[str, Any]:
    value = json.loads(document)
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _required_string(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{description} must be a non-empty string")
    return value


def _rancher_app_identities(document: str) -> list[dict[str, Any]]:
    app_list = _load_json_object(document, "Kubernetes Rancher App inventory")
    items = app_list.get("items")
    if not isinstance(items, list):
        raise ValueError("Kubernetes Rancher App inventory items must be an array")
    identities: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Kubernetes Rancher App inventory item must be an object")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("Kubernetes Rancher App metadata must be an object")
        namespace = _required_string(
            metadata.get("namespace"), "Kubernetes Rancher App namespace"
        )
        if namespace not in TARGET_NAMESPACES:
            continue
        owner_references = metadata.get("ownerReferences", [])
        if not isinstance(owner_references, list):
            raise ValueError("Kubernetes Rancher App ownerReferences must be an array")
        canonical_owners = []
        for owner in owner_references:
            if not isinstance(owner, dict):
                raise ValueError("Kubernetes Rancher App owner must be an object")
            canonical_owners.append(
                {
                    "apiVersion": _required_string(
                        owner.get("apiVersion"), "Kubernetes Rancher App owner apiVersion"
                    ),
                    "kind": _required_string(
                        owner.get("kind"), "Kubernetes Rancher App owner kind"
                    ),
                    "namespace": namespace,
                    "name": _required_string(
                        owner.get("name"), "Kubernetes Rancher App owner name"
                    ),
                }
            )
        identities.append(
            {
                "apiVersion": _required_string(
                    item.get("apiVersion"), "Kubernetes Rancher App apiVersion"
                ),
                "kind": _required_string(
                    item.get("kind"), "Kubernetes Rancher App kind"
                ),
                "namespace": namespace,
                "name": _required_string(
                    metadata.get("name"), "Kubernetes Rancher App name"
                ),
                "uid": _required_string(
                    metadata.get("uid"), "Kubernetes Rancher App uid"
                ),
                "resourceVersion": _required_string(
                    metadata.get("resourceVersion"),
                    "Kubernetes Rancher App resourceVersion",
                ),
                "ownerReferences": canonical_owners,
            }
        )
    return identities


def _local_node(spec: dict[str, Any]) -> str:
    node_affinity = spec.get("nodeAffinity")
    if not isinstance(node_affinity, dict):
        raise ValueError("local PersistentVolume must identify its owning node")
    required = node_affinity.get("required")
    terms = required.get("nodeSelectorTerms") if isinstance(required, dict) else None
    nodes: set[str] = set()
    if isinstance(terms, list):
        for term in terms:
            expressions = (
                term.get("matchExpressions") if isinstance(term, dict) else None
            )
            if not isinstance(expressions, list):
                continue
            for expression in expressions:
                if not isinstance(expression, dict):
                    continue
                if expression.get("key") != "kubernetes.io/hostname":
                    continue
                if expression.get("operator") != "In":
                    continue
                values = expression.get("values")
                if isinstance(values, list):
                    nodes.update(
                        value for value in values if isinstance(value, str) and value
                    )
    if len(nodes) != 1:
        raise ValueError("local PersistentVolume must identify exactly one owning node")
    return next(iter(nodes))


def _backend_locator(spec: dict[str, Any]) -> dict[str, str]:
    locators: list[dict[str, str]] = []
    csi = spec.get("csi")
    if isinstance(csi, dict):
        locators.append(
            {
                "type": "csi",
                "driver": _required_string(csi.get("driver"), "CSI driver"),
                "volumeHandle": _required_string(
                    csi.get("volumeHandle"), "CSI volumeHandle"
                ),
            }
        )
    nfs = spec.get("nfs")
    if isinstance(nfs, dict):
        locators.append(
            {
                "type": "nfs",
                "server": _required_string(nfs.get("server"), "NFS server"),
                "path": _required_string(nfs.get("path"), "NFS path"),
            }
        )
    for source_name in ("local", "hostPath"):
        local = spec.get(source_name)
        if not isinstance(local, dict):
            continue
        locators.append(
            {
                "type": "localPath",
                "node": _local_node(spec),
                "path": _required_string(local.get("path"), "local backend path"),
                "volumeSource": source_name,
            }
        )
    if len(locators) != 1:
        raise ValueError(
            "target PersistentVolume must expose exactly one CSI, NFS, or local-path backend locator"
        )
    return locators[0]


def _persistent_volume_metadata(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        raise ValueError("PersistentVolume inventory item must be an object")
    spec = item.get("spec")
    if not isinstance(spec, dict):
        raise ValueError("PersistentVolume spec must be an object")
    claim_ref = spec.get("claimRef")
    if claim_ref is not None and not isinstance(claim_ref, dict):
        raise ValueError("PersistentVolume claimRef must be an object")
    metadata = item.get("metadata")
    status = item.get("status")
    if not isinstance(metadata, dict) or not isinstance(status, dict):
        raise ValueError("PersistentVolume metadata and status must be objects")
    labels = metadata.get("labels", {})
    if not isinstance(labels, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in labels.items()
    ):
        raise ValueError("PersistentVolume labels must be a string object")
    namespace = claim_ref.get("namespace") if isinstance(claim_ref, dict) else None
    storage_class = spec.get("storageClassName")
    if not (namespace in TARGET_NAMESPACES or storage_class in TARGET_STORAGE_CLASSES):
        return None
    values = {
        "apiVersion": item.get("apiVersion"),
        "kind": item.get("kind"),
        "name": metadata.get("name"),
        "uid": metadata.get("uid"),
        "resourceVersion": metadata.get("resourceVersion"),
        "storageClassName": spec.get("storageClassName"),
        "reclaimPolicy": spec.get("persistentVolumeReclaimPolicy"),
        "claimName": claim_ref.get("name") if isinstance(claim_ref, dict) else None,
        "claimUID": claim_ref.get("uid") if isinstance(claim_ref, dict) else None,
    }
    required_values = {
        key: value
        for key, value in values.items()
        if key not in {"claimName", "claimUID"}
    }
    if any(
        not isinstance(value, str) or not value for value in required_values.values()
    ):
        raise ValueError("PersistentVolume reset identity is incomplete")
    normalized_claim_ref = None
    if claim_ref is not None:
        if (
            namespace not in TARGET_NAMESPACES
            or not isinstance(values["claimName"], str)
            or not values["claimName"]
            or not isinstance(values["claimUID"], str)
            or not values["claimUID"]
        ):
            raise ValueError("PersistentVolume claimRef identity is incomplete")
        normalized_claim_ref = {
            "namespace": namespace,
            "name": values["claimName"],
            "uid": values["claimUID"],
        }
    phase = status.get("phase")
    if phase not in {"Available", "Bound", "Released", "Failed"}:
        raise ValueError(
            f"target PersistentVolume phase is unsupported: {values['name']}"
        )
    return {
        "apiVersion": values["apiVersion"],
        "kind": values["kind"],
        "name": values["name"],
        "uid": values["uid"],
        "resourceVersion": values["resourceVersion"],
        "labels": labels,
        "phase": phase,
        "storageClassName": values["storageClassName"],
        "reclaimPolicy": values["reclaimPolicy"],
        "claimRef": normalized_claim_ref,
        "backendLocator": _backend_locator(spec),
    }


def collect_reset_inventory(
    *,
    expected_context: str,
    kubeconfig: Path,
    runner: Callable[[list[str]], str] = _subprocess_runner,
) -> dict[str, Any]:
    if not expected_context or not kubeconfig.is_absolute():
        raise ValueError("expected context is required")
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        expected_context,
    ]
    helm = [
        "helm",
        "--kubeconfig",
        str(kubeconfig),
        "--kube-context",
        expected_context,
    ]
    current_context = runner([*kubectl, "config", "current-context"]).strip()
    if current_context != expected_context:
        raise ValueError(
            "current context does not match requested reset inventory: "
            f"expected {expected_context}, got {current_context or '<empty>'}"
        )

    namespace_document = _load_json_object(
        runner(
            [
                *kubectl,
                "get",
                "namespaces",
                "-o",
                "json",
            ]
        ),
        "Kubernetes namespace inventory",
    )
    namespace_items = namespace_document.get("items")
    if not isinstance(namespace_items, list):
        raise ValueError("Kubernetes namespace inventory items must be an array")
    namespaces: list[dict[str, Any]] = []
    for item in namespace_items:
        if not isinstance(item, dict) or not isinstance(item.get("metadata"), dict):
            raise ValueError("Kubernetes namespace metadata must be an object")
        metadata = item["metadata"]
        name = metadata.get("name")
        if name not in TARGET_NAMESPACES:
            continue
        uid = _required_string(metadata.get("uid"), "Kubernetes namespace uid")
        resource_version = _required_string(
            metadata.get("resourceVersion"), "Kubernetes namespace resourceVersion"
        )
        labels = metadata.get("labels", {})
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise ValueError("Kubernetes namespace labels must be a string object")
        namespaces.append(
            {
                "name": name,
                "uid": uid,
                "resourceVersion": resource_version,
                "labels": labels,
            }
        )
    namespaces.sort(key=lambda item: item["name"])

    release_document = json.loads(
        runner(
            [
                *helm,
                "list",
                "--all-namespaces",
                "--output",
                "json",
            ]
        )
    )
    if not isinstance(release_document, list):
        raise ValueError("Helm release inventory must be an array")
    releases: list[dict[str, str]] = []
    for item in release_document:
        if not isinstance(item, dict):
            raise ValueError("Helm release inventory item must be an object")
        name = item.get("name")
        namespace = item.get("namespace")
        if namespace not in TARGET_NAMESPACES:
            continue
        if not isinstance(name, str) or not name:
            raise ValueError("Helm release name is invalid")
        releases.append({"name": name, "namespace": namespace})
    releases.sort(key=lambda item: (item["namespace"], item["name"]))

    persistent_volume_document = _load_json_object(
        runner(
            [
                *kubectl,
                "get",
                "persistentvolumes",
                "-o",
                "json",
            ]
        ),
        "Kubernetes PersistentVolume inventory",
    )
    persistent_volume_items = persistent_volume_document.get("items")
    if not isinstance(persistent_volume_items, list):
        raise ValueError("Kubernetes PersistentVolume inventory items must be an array")
    persistent_volumes: list[dict[str, Any]] = []
    for item in persistent_volume_items:
        persistent_volume = _persistent_volume_metadata(item)
        if persistent_volume is not None:
            persistent_volumes.append(persistent_volume)
    persistent_volumes.sort(key=lambda item: item["name"])

    discovered_resources = set(
        runner(
            [
                *kubectl,
                "api-resources",
                "--namespaced=true",
                "--verbs=list",
                "-o",
                "name",
            ]
        ).splitlines()
    )
    resources: list[dict[str, Any]] = []
    resource_identities: set[tuple[str, str, str, str]] = set()
    for resource_name in sorted(discovered_resources):
        if resource_name == RANCHER_APP_RESOURCE:
            app_document = runner(
                [
                    *kubectl,
                    "get",
                    resource_name,
                    "--all-namespaces",
                    "-o",
                    "json",
                ]
            )
            for app in _rancher_app_identities(app_document):
                identity = (
                    app["apiVersion"],
                    app["kind"],
                    app["namespace"],
                    app["name"],
                )
                if identity in resource_identities:
                    continue
                resource_identities.add(identity)
                resources.append(app)
            continue
        rows = runner(
            [
                *kubectl,
                "get",
                resource_name,
                "--all-namespaces",
                "-o",
                RESOURCE_IDENTITY_COLUMNS,
                "--no-headers",
            ]
        )
        for row in rows.splitlines():
            columns = row.split()
            if len(columns) != 6:
                raise ValueError(
                    f"Kubernetes {resource_name} identity row is malformed"
                )
            api_version, kind, namespace, name, uid, resource_version = columns
            if namespace not in TARGET_NAMESPACES:
                continue
            identity = (api_version, kind, namespace, name)
            if identity in resource_identities:
                continue
            resource_identities.add(identity)
            resources.append(
                {
                    "apiVersion": api_version,
                    "kind": kind,
                    "namespace": namespace,
                    "name": name,
                    "uid": uid,
                    "resourceVersion": resource_version,
                }
            )
    resources.sort(
        key=lambda item: (
            item["namespace"],
            item["kind"],
            item["apiVersion"],
            item["name"],
        )
    )

    return {
        "context": expected_context,
        "namespaces": namespaces,
        "releases": releases,
        "persistentVolumes": persistent_volumes,
        "resources": resources,
    }


def write_inventory(path: Path, inventory: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(inventory, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect non-secret metadata for a fail-closed Aileron reset."
    )
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    inventory = collect_reset_inventory(
        expected_context=arguments.context, kubeconfig=arguments.kubeconfig
    )
    write_inventory(arguments.output, inventory)
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
