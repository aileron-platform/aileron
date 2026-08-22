#!/usr/bin/env python3
"""Create and verify the fixed signed HomeLab reset snapshot."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from . import namespace_policy as NAMESPACE_POLICY
else:
    try:
        from scripts.deploy.rke2 import namespace_policy as NAMESPACE_POLICY
    except ModuleNotFoundError:
        import namespace_policy as NAMESPACE_POLICY

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
SNAPSHOT_NAME = "clean-reset-snapshot.json"
SCHEMA_VERSION = "aileron-clean-reset-snapshot/v2"
TARGET_NAMESPACES = {
    "aileron-identity-system",
    "aileron-turn-system",
    "workspace-system",
}
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AcceptanceSnapshotError(RuntimeError):
    """Raised when the reset snapshot cannot establish exact provenance."""


def _load_private_io() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_snapshot_private_io",
        SCRIPT_DIRECTORY / "acceptance_private_io.py",
    )
    if specification is None or specification.loader is None:
        raise AcceptanceSnapshotError("acceptance private I/O is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_IO = _load_private_io()
RUN_ID = PRIVATE_IO.RUN_ID


def _validate_backend_attestor_binding(binding: Any) -> dict[str, Any]:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_snapshot_backend_attestor",
        SCRIPT_DIRECTORY / "backend_attestor.py",
    )
    if specification is None or specification.loader is None:
        raise AcceptanceSnapshotError("backend attestor validator is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    try:
        return module.validate_backend_attestor_snapshot_binding(binding)
    except (ValueError, module.BackendAttestorError) as exc:
        raise AcceptanceSnapshotError(str(exc)) from exc


def _canonical(value: Any) -> bytes:
    return PRIVATE_IO.canonical_json(value)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AcceptanceSnapshotError("reset snapshot timestamp must be UTC")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _validate_inventory(inventory: Any, context: str) -> None:
    if not isinstance(inventory, dict) or set(inventory) != {
        "context",
        "namespaces",
        "releases",
        "resources",
        "persistentVolumes",
    }:
        raise AcceptanceSnapshotError("reset inventory shape is invalid")
    if inventory.get("context") != context:
        raise AcceptanceSnapshotError("reset inventory context does not match")
    namespaces = inventory.get("namespaces")
    resources = inventory.get("resources")
    volumes = inventory.get("persistentVolumes")
    if not isinstance(namespaces, list):
        raise AcceptanceSnapshotError("reset inventory namespaces must be an array")
    namespace_names: set[str] = set()
    for item in namespaces:
        name = item.get("name") if isinstance(item, dict) else None
        if (
            not isinstance(name, str)
            or not name
            or name not in TARGET_NAMESPACES
            or name in namespace_names
        ):
            raise AcceptanceSnapshotError(
                "reset inventory namespaces must be a unique HomeLab target subset"
            )
        namespace_names.add(name)
    if not isinstance(resources, list) or not isinstance(volumes, list):
        raise AcceptanceSnapshotError("reset inventory target sets are invalid")
    workspaces = [
        item
        for item in resources
        if isinstance(item, dict)
        and item.get("apiVersion") == "platform.aileron.io/v1alpha1"
        and item.get("kind") == "Workspace"
        and item.get("namespace") == "workspace-system"
        and isinstance(item.get("name"), str)
        and item["name"]
    ]
    pvcs = [
        item
        for item in resources
        if isinstance(item, dict)
        and item.get("apiVersion") == "v1"
        and item.get("kind") == "PersistentVolumeClaim"
        and item.get("namespace") in TARGET_NAMESPACES
        and isinstance(item.get("name"), str)
        and item["name"]
    ]
    valid_volumes = [
        item
        for item in volumes
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and item["name"]
        and isinstance(item.get("backendLocator"), dict)
        and item["backendLocator"]
    ]
    workspace_candidates = [
        item
        for item in resources
        if isinstance(item, dict) and item.get("kind") == "Workspace"
    ]
    pvc_candidates = [
        item
        for item in resources
        if isinstance(item, dict) and item.get("kind") == "PersistentVolumeClaim"
    ]
    if (
        any(not isinstance(item, dict) for item in resources)
        or len(workspaces) != len(workspace_candidates)
        or len(pvcs) != len(pvc_candidates)
        or len(valid_volumes) != len(volumes)
    ):
        raise AcceptanceSnapshotError("reset inventory target sets are invalid")


def write_reset_snapshot(
    *,
    directory: Path,
    private_root: Path,
    inventory: dict[str, Any],
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
    run_id: str,
    backend_attestor: dict[str, Any],
    created_at: datetime,
) -> Path:
    """Write the only snapshot accepted by reset and post-reset verification."""

    if (
        len(key) != 32
        or SHA.fullmatch(commit) is None
        or DIGEST.fullmatch(installation_identity_sha256) is None
        or RUN_ID.fullmatch(run_id) is None
        or not cluster_uid
    ):
        raise AcceptanceSnapshotError("reset snapshot identity is invalid")
    _validate_inventory(inventory, context)
    PRIVATE_IO.validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=run_id,
        error_type=AcceptanceSnapshotError,
    )
    validated_backend_attestor = _validate_backend_attestor_binding(backend_attestor)
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "commit": commit,
        "clusterUid": cluster_uid,
        "context": context,
        "installationIdentitySha256": installation_identity_sha256,
        "createdAt": _timestamp(created_at),
        "inventorySha256": hashlib.sha256(_canonical(inventory)).hexdigest(),
        "inventory": inventory,
        "namespacePolicy": NAMESPACE_POLICY.namespace_policy_document(),
        "backendAttestor": validated_backend_attestor,
    }
    document["signature"] = hmac.new(
        key, _canonical(document), hashlib.sha256
    ).hexdigest()
    path = directory / SNAPSHOT_NAME
    return PRIVATE_IO.write_private_snapshot(
        destination=path,
        content=_canonical(document) + b"\n",
        description="reset snapshot",
        private_root=private_root,
        error_type=AcceptanceSnapshotError,
    )


def load_reset_snapshot(
    *,
    directory: Path,
    private_root: Path,
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
    expected_run_id: str,
    expected_snapshot_sha256: str,
) -> dict[str, Any]:
    """Verify and return the fixed reset snapshot from an acceptance directory."""

    PRIVATE_IO.validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=expected_run_id,
        error_type=AcceptanceSnapshotError,
    )
    raw_snapshot = PRIVATE_IO.read_private_bytes(
        directory / SNAPSHOT_NAME,
        "reset snapshot",
        private_root=private_root,
        error_type=AcceptanceSnapshotError,
        maximum_size=4 * 1024 * 1024,
    )
    if (
        DIGEST.fullmatch(expected_snapshot_sha256) is None
        or hashlib.sha256(raw_snapshot).hexdigest() != expected_snapshot_sha256
    ):
        raise AcceptanceSnapshotError("reset snapshot digest does not match")
    document = PRIVATE_IO.load_json_object(
        raw_snapshot,
        "reset snapshot",
        error_type=AcceptanceSnapshotError,
        require_canonical=True,
    )
    if not isinstance(document, dict) or set(document) != {
        "schemaVersion",
        "runId",
        "commit",
        "clusterUid",
        "context",
        "installationIdentitySha256",
        "createdAt",
        "inventorySha256",
        "inventory",
        "namespacePolicy",
        "backendAttestor",
        "signature",
    }:
        raise AcceptanceSnapshotError("reset snapshot shape is invalid")
    signature = document.get("signature")
    unsigned = dict(document)
    unsigned.pop("signature", None)
    expected_signature = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
    if (
        not isinstance(signature, str)
        or DIGEST.fullmatch(signature) is None
        or not hmac.compare_digest(signature, expected_signature)
    ):
        raise AcceptanceSnapshotError("reset snapshot signature does not match")
    if (
        document["schemaVersion"] != SCHEMA_VERSION
        or document["context"] != context
        or document["commit"] != commit
        or document["clusterUid"] != cluster_uid
        or document["installationIdentitySha256"] != installation_identity_sha256
        or RUN_ID.fullmatch(document["runId"]) is None
        or document["runId"] != expected_run_id
    ):
        raise AcceptanceSnapshotError("reset snapshot identity does not match")
    created_at_value = document["createdAt"]
    if not isinstance(created_at_value, str):
        raise AcceptanceSnapshotError("reset snapshot timestamp is invalid")
    try:
        created_at = datetime.fromisoformat(
            created_at_value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise AcceptanceSnapshotError("reset snapshot timestamp is invalid") from exc
    if (
        created_at.utcoffset() != timezone.utc.utcoffset(created_at)
        or created_at_value != _timestamp(created_at)
    ):
        raise AcceptanceSnapshotError("reset snapshot timestamp is invalid")
    inventory = document["inventory"]
    if document["inventorySha256"] != hashlib.sha256(_canonical(inventory)).hexdigest():
        raise AcceptanceSnapshotError("reset snapshot inventory digest does not match")
    _validate_inventory(inventory, context)
    if document["namespacePolicy"] != NAMESPACE_POLICY.namespace_policy_document():
        raise AcceptanceSnapshotError("reset snapshot Namespace policy does not match")
    _validate_backend_attestor_binding(document["backendAttestor"])
    return document
