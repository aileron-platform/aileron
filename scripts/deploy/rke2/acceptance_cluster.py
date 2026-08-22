#!/usr/bin/env python3
"""Load the installation-owned acceptance trust root from Kubernetes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.util
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from uuid import UUID

FILE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def _load_installation_state():
    specification = importlib.util.spec_from_file_location(
        "aileron_installation_state",
        Path(__file__).resolve().parent / "installation_state.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-state contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_installation_state()


def _load_private_input():
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_cluster_private_input",
        SCRIPT_DIRECTORY / "private_input.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-input contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input()


def _load_namespace_contract():
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_cluster_namespace_contract",
        SCRIPT_DIRECTORY / "namespace_contract.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("acceptance Namespace contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


NAMESPACE_CONTRACT = _load_namespace_contract()
SECRET_NAMESPACE = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAMESPACE
SECRET_NAME = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAME
SECRET_DATA_KEY = INSTALLATION_STATE.ACCEPTANCE_SECRET_DATA_KEY
TRUST_ANCHOR_FILE = INSTALLATION_STATE.ACCEPTANCE_ANCHOR_FILE
INSTALLER_OWNER = INSTALLATION_STATE.INSTALLER_OWNER
SECRET_OWNER_LABEL = INSTALLATION_STATE.SECRET_OWNER_LABEL
CLUSTER_UID_LABEL = INSTALLATION_STATE.CLUSTER_UID_LABEL
IDENTITY_DIGEST_ANNOTATION = INSTALLATION_STATE.IDENTITY_DIGEST_ANNOTATION


class AcceptanceClusterError(RuntimeError):
    """Raised when the cluster acceptance trust root is invalid."""


class ClusterAcceptanceTrust(NamedTuple):
    key: bytes
    cluster_uid: str
    installation_identity_sha256: str
    secret_uid: str
    secret_resource_version: str
    acceptance_namespace_uid: str
    acceptance_namespace_resource_version: str


Runner = Callable[[list[str]], bytes]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON object key")
        document[key] = value
    return document


def _reject_nonstandard_constant(_value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _run_command(command: list[str]) -> bytes:
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        raise AcceptanceClusterError("kubectl trust-root query failed")
    return result.stdout


def _private_root() -> Path:
    try:
        return PRIVATE_INPUT.private_root_path(INSTALLATION_STATE.PRIVATE_ROOT)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise AcceptanceClusterError("installation private root is invalid") from exc


def _private_kubeconfig(path: Path, *, context: str) -> Path:
    private_root = _private_root()
    try:
        raw = PRIVATE_INPUT.read_private_bytes(
            path,
            "flattened kubeconfig snapshot",
            private_root=private_root,
            maximum_size=1024 * 1024,
        )
        PRIVATE_INPUT.validate_self_contained_kubeconfig(
            raw,
            expected_context=context,
            description="flattened kubeconfig snapshot",
            require_minified=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise AcceptanceClusterError(
            "flattened kubeconfig snapshot is invalid"
        ) from exc
    return path


def _stable_store() -> Path:
    path = INSTALLATION_STATE.SECRET_STORE
    try:
        return PRIVATE_INPUT.validate_private_directory(
            path,
            "installation secret store",
            expected_relative_path=Path("install-secrets/homelab"),
            private_root=_private_root(),
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise AcceptanceClusterError(
            "installation secret store is invalid"
        ) from exc


def _load_anchor(secret_store: Path) -> dict[str, object]:
    path = secret_store / TRUST_ANCHOR_FILE
    try:
        raw = PRIVATE_INPUT.read_private_bytes(
            path,
            "acceptance trust anchor",
            private_root=_private_root(),
            maximum_size=65536,
        )
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonstandard_constant,
        )
    except (
        PRIVATE_INPUT.PrivateInputError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise AcceptanceClusterError("acceptance trust anchor is invalid") from exc
    canonical = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    if not isinstance(document, dict) or raw != canonical:
        raise AcceptanceClusterError("acceptance trust anchor is invalid")
    return document


def _load_installation_identity(secret_store: Path) -> bytes:
    path = secret_store / "installation-identity.json"
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            "installation identity",
            private_root=_private_root(),
            maximum_size=65536,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise AcceptanceClusterError("installation identity is unreadable") from exc


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _text(runner: Runner, command: list[str], description: str) -> str:
    try:
        return runner(command).decode("utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise AcceptanceClusterError(f"{description} is unreadable") from exc


def _acceptance_namespace_record(
    *, runner: Runner, kubeconfig: Path, context: str
):
    try:
        raw = runner(
            _kubectl(
                kubeconfig,
                context,
                "get",
                "namespace",
                SECRET_NAMESPACE,
                "--output=json",
            )
        )
        return NAMESPACE_CONTRACT.validate_namespace_json(
            raw,
            namespace=SECRET_NAMESPACE,
            require_canonical_uid=True,
        )
    except (OSError, NAMESPACE_CONTRACT.NamespaceContractError) as exc:
        raise AcceptanceClusterError(
            "acceptance Namespace record is invalid"
        ) from exc


def load_cluster_acceptance_key(
    *,
    context: str,
    kubeconfig: Path,
    runner: Runner = _run_command,
) -> ClusterAcceptanceTrust:
    """Return the key only after validating the fixed installation-owned Secret."""

    if not context or context != context.strip():
        raise AcceptanceClusterError("an exact Kubernetes context is required")
    kubeconfig = _private_kubeconfig(kubeconfig, context=context)
    anchor = _load_anchor(_stable_store())
    cluster_uid = _text(
        runner,
        _kubectl(
            kubeconfig,
            context,
            "get",
            "namespace",
            "kube-system",
            "--output=jsonpath={.metadata.uid}",
        ),
        "Kubernetes cluster identity",
    )
    try:
        parsed_uid = UUID(cluster_uid)
    except ValueError as exc:
        raise AcceptanceClusterError("Kubernetes cluster identity is invalid") from exc
    if str(parsed_uid) != cluster_uid:
        raise AcceptanceClusterError("Kubernetes cluster identity is invalid")
    acceptance_namespace = _acceptance_namespace_record(
        runner=runner,
        kubeconfig=kubeconfig,
        context=context,
    )
    raw_secret = _text(
        runner,
        _kubectl(
            kubeconfig,
            context,
            "--namespace",
            SECRET_NAMESPACE,
            "get",
            "secret",
            SECRET_NAME,
            "--output=json",
        ),
        "acceptance signing Secret",
    )
    try:
        secret = json.loads(raw_secret)
    except json.JSONDecodeError as exc:
        raise AcceptanceClusterError(
            "acceptance signing Secret is invalid JSON"
        ) from exc
    metadata = secret.get("metadata") if isinstance(secret, dict) else None
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    identity_digest = (
        annotations.get(IDENTITY_DIGEST_ANNOTATION)
        if isinstance(annotations, dict)
        else None
    )
    if isinstance(secret, dict) and secret.get("immutable") is not True:
        raise AcceptanceClusterError("acceptance signing Secret must be immutable")
    if (
        secret.get("apiVersion") != "v1"
        or secret.get("kind") != "Secret"
        or not isinstance(metadata, dict)
        or metadata.get("name") != SECRET_NAME
        or metadata.get("namespace") != SECRET_NAMESPACE
        or not isinstance(labels, dict)
        or set(labels) != {SECRET_OWNER_LABEL, CLUSTER_UID_LABEL}
        or labels.get(SECRET_OWNER_LABEL) != INSTALLER_OWNER
        or labels.get(CLUSTER_UID_LABEL) != cluster_uid
        or not isinstance(annotations, dict)
        or set(annotations) != {IDENTITY_DIGEST_ANNOTATION}
        or not isinstance(identity_digest, str)
        or FILE_DIGEST.fullmatch(identity_digest) is None
        or secret.get("type") != "Opaque"
        or not isinstance(secret.get("data"), dict)
        or set(secret["data"]) != {SECRET_DATA_KEY}
    ):
        raise AcceptanceClusterError("acceptance signing Secret metadata is invalid")
    secret_uid = metadata.get("uid")
    secret_resource_version = metadata.get("resourceVersion")
    try:
        parsed_secret_uid = UUID(secret_uid)
    except (TypeError, ValueError) as exc:
        raise AcceptanceClusterError(
            "acceptance signing Secret metadata is invalid"
        ) from exc
    if (
        str(parsed_secret_uid) != secret_uid
        or not isinstance(secret_resource_version, str)
        or not secret_resource_version
        or secret_resource_version != secret_resource_version.strip()
    ):
        raise AcceptanceClusterError("acceptance signing Secret metadata is invalid")
    encoded_key = secret["data"][SECRET_DATA_KEY]
    if not isinstance(encoded_key, str):
        raise AcceptanceClusterError("acceptance signing key is invalid")
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AcceptanceClusterError("acceptance signing key is invalid") from exc
    if len(key) != 32:
        raise AcceptanceClusterError("acceptance signing key must contain 32 bytes")
    expected_anchor = INSTALLATION_STATE.acceptance_anchor_document(
        cluster_uid=cluster_uid,
        identity_digest=identity_digest,
        key_digest=hashlib.sha256(key).hexdigest(),
        secret_uid=secret_uid,
    )
    if anchor != expected_anchor:
        raise AcceptanceClusterError(
            "acceptance signing Secret does not match the stable-store anchor"
        )
    final_acceptance_namespace = _acceptance_namespace_record(
        runner=runner,
        kubeconfig=kubeconfig,
        context=context,
    )
    if final_acceptance_namespace != acceptance_namespace:
        raise AcceptanceClusterError(
            "acceptance Namespace record changed during trust validation"
        )
    return ClusterAcceptanceTrust(
        key,
        cluster_uid,
        identity_digest,
        secret_uid,
        secret_resource_version,
        acceptance_namespace.uid,
        acceptance_namespace.resource_version,
    )


def load_cluster_release_trust(
    *,
    context: str,
    kubeconfig: Path,
    runner: Runner = _run_command,
) -> ClusterAcceptanceTrust:
    """Validate live acceptance trust and its exact local installation identity."""

    trust = load_cluster_acceptance_key(
        context=context,
        kubeconfig=kubeconfig,
        runner=runner,
    )
    identity = _load_installation_identity(_stable_store())
    try:
        INSTALLATION_STATE.acceptance_secret_bytes(
            key=trust.key,
            identity=identity,
            cluster_uid=trust.cluster_uid,
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise AcceptanceClusterError("installation identity is invalid") from exc
    if hashlib.sha256(identity).hexdigest() != trust.installation_identity_sha256:
        raise AcceptanceClusterError(
            "installation identity does not match acceptance trust"
        )
    return trust
