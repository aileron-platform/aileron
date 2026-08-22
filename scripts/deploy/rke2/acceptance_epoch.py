#!/usr/bin/env python3
"""Create and verify the signed HomeLab deployment acceptance epoch."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
EPOCH_NAME = "deployment-epoch.json"
SCHEMA_VERSION = "aileron-deployment-epoch/v1"
AUTHENTICATION_MODES = {"bundledKeycloak", "externalOidc"}
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class AcceptanceEpochError(RuntimeError):
    """Raised when an acceptance epoch cannot establish one deployment attempt."""


def _load_private_io() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_epoch_private_io",
        SCRIPT_DIRECTORY / "acceptance_private_io.py",
    )
    if specification is None or specification.loader is None:
        raise AcceptanceEpochError("acceptance private I/O is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_IO = _load_private_io()
RUN_ID = PRIVATE_IO.RUN_ID


def _canonical(value: Any) -> bytes:
    return PRIVATE_IO.canonical_json(value)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AcceptanceEpochError("deployment epoch timestamp must be UTC")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def write_deployment_epoch(
    *,
    directory: Path,
    private_root: Path,
    key: bytes,
    deployment_run_id: str,
    commit: str,
    cluster_uid: str,
    context: str,
    installation_identity_sha256: str,
    authentication_mode: str,
    reset_snapshot_sha256: str,
    created_at: datetime,
) -> Path:
    """Write the fixed epoch that binds every report to one reset attempt."""

    if (
        len(key) != 32
        or RUN_ID.fullmatch(deployment_run_id) is None
        or SHA.fullmatch(commit) is None
        or not cluster_uid
        or not context
        or DIGEST.fullmatch(installation_identity_sha256) is None
        or authentication_mode not in AUTHENTICATION_MODES
        or DIGEST.fullmatch(reset_snapshot_sha256) is None
    ):
        raise AcceptanceEpochError("deployment epoch identity is invalid")
    PRIVATE_IO.validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceEpochError,
    )
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "deploymentRunId": deployment_run_id,
        "commit": commit,
        "clusterUid": cluster_uid,
        "context": context,
        "installationIdentitySha256": installation_identity_sha256,
        "authenticationMode": authentication_mode,
        "resetSnapshotSha256": reset_snapshot_sha256,
        "createdAt": _timestamp(created_at),
    }
    document["signature"] = hmac.new(
        key, _canonical(document), hashlib.sha256
    ).hexdigest()
    path = directory / EPOCH_NAME
    return PRIVATE_IO.write_private_snapshot(
        destination=path,
        content=_canonical(document) + b"\n",
        description="deployment epoch",
        private_root=private_root,
        error_type=AcceptanceEpochError,
    )


def load_deployment_epoch(
    *,
    directory: Path,
    private_root: Path,
    key: bytes,
    commit: str,
    cluster_uid: str,
    context: str,
    installation_identity_sha256: str,
    deployment_run_id: str,
) -> dict[str, Any]:
    """Verify the fixed epoch against the current cluster trust root."""

    PRIVATE_IO.validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceEpochError,
    )
    raw = PRIVATE_IO.read_private_bytes(
        directory / EPOCH_NAME,
        "deployment epoch",
        private_root=private_root,
        error_type=AcceptanceEpochError,
        maximum_size=1024 * 1024,
    )
    document = PRIVATE_IO.load_json_object(
        raw,
        "deployment epoch",
        error_type=AcceptanceEpochError,
        require_canonical=True,
    )
    expected_keys = {
        "schemaVersion",
        "deploymentRunId",
        "commit",
        "clusterUid",
        "context",
        "installationIdentitySha256",
        "authenticationMode",
        "resetSnapshotSha256",
        "createdAt",
        "signature",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise AcceptanceEpochError("deployment epoch shape is invalid")
    signature = document.get("signature")
    unsigned = dict(document)
    unsigned.pop("signature", None)
    expected_signature = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
    if (
        len(key) != 32
        or not isinstance(signature, str)
        or DIGEST.fullmatch(signature) is None
        or not hmac.compare_digest(signature, expected_signature)
    ):
        raise AcceptanceEpochError("deployment epoch signature does not match")
    if (
        document["schemaVersion"] != SCHEMA_VERSION
        or document["commit"] != commit
        or document["clusterUid"] != cluster_uid
        or document["context"] != context
        or document["installationIdentitySha256"]
        != installation_identity_sha256
        or RUN_ID.fullmatch(document["deploymentRunId"]) is None
        or document["deploymentRunId"] != deployment_run_id
        or document["authenticationMode"] not in AUTHENTICATION_MODES
        or DIGEST.fullmatch(document["resetSnapshotSha256"]) is None
    ):
        raise AcceptanceEpochError("deployment epoch identity does not match")
    try:
        timestamp = document["createdAt"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            raise ValueError("timestamp is not canonical UTC")
        created_at = datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except (AttributeError, ValueError) as exc:
        raise AcceptanceEpochError("deployment epoch timestamp is invalid") from exc
    if created_at.tzinfo != timezone.utc or _timestamp(created_at) != timestamp:
        raise AcceptanceEpochError("deployment epoch timestamp must use canonical UTC")
    return document


def epoch_sha256(
    directory: Path,
    *,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
) -> str:
    """Return the digest of the exact mode-0600 epoch file."""

    PRIVATE_IO.validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceEpochError,
    )
    return hashlib.sha256(
        PRIVATE_IO.read_private_bytes(
            directory / EPOCH_NAME,
            "deployment epoch",
            private_root=private_root,
            error_type=AcceptanceEpochError,
            maximum_size=1024 * 1024,
        )
    ).hexdigest()
