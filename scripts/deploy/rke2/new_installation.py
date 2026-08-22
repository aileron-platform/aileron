#!/usr/bin/env python3
"""Replace prerelease HomeLab installation trust with a forward-only transaction."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID, uuid4

if __package__:
    from . import acceptance_cluster as ACCEPTANCE_CLUSTER
    from . import bootstrap_acceptance_trust as BOOTSTRAP
    from . import installation_state as INSTALLATION_STATE
    from . import kubernetes_rest as KUBERNETES_REST
    from . import namespace_contract as NAMESPACE_CONTRACT
    from . import private_input as PRIVATE_INPUT
else:
    import acceptance_cluster as ACCEPTANCE_CLUSTER
    import bootstrap_acceptance_trust as BOOTSTRAP
    import installation_state as INSTALLATION_STATE
    import kubernetes_rest as KUBERNETES_REST
    import namespace_contract as NAMESPACE_CONTRACT
    import private_input as PRIVATE_INPUT


class NewInstallationError(RuntimeError):
    """Raised when the forward-only new-installation transaction cannot proceed."""


Runner = Callable[..., bytes]
KeyFactory = Callable[[], bytes]
InstallationIdFactory = Callable[[], str]

FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SECRET_NAMESPACE = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAMESPACE
SECRET_NAME = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAME
ANCHOR_FILE = INSTALLATION_STATE.ACCEPTANCE_ANCHOR_FILE
NEW_INSTALLATION_DIRECTORY_NAME = "new-installation"
NEW_INSTALLATION_JOURNAL_NAME = "journal.json"
NEW_INSTALLATION_SCHEMA = "aileron-new-installation-transaction/v1"
NEW_INSTALLATION_STATES = {
    "prepared",
    "quarantineReady",
    "secretDeleteStarted",
    "secretDeleteAccepted",
    "secretAbsent",
    "trustBootstrapped",
    "readbackVerified",
    "completed",
}
QUARANTINED_TRUST_FILES = (
    "installation-identity.json",
    "acceptance-hmac.key",
    ANCHOR_FILE,
)
RETIRED_V2_NAMESPACES = [
    "aileron-acceptance-system",
    "aileron-identity-system",
    "aileron-turn-system",
    "workspace-system",
]


class _OldTrust(NamedTuple):
    cluster_uid: str
    secret_uid: str
    secret_resource_version: str
    acceptance_namespace_uid: str
    acceptance_namespace_resource_version: str


class _Request(NamedTuple):
    commit: str
    kubeconfig: Path
    context: str
    identity_mode: str
    issuer_url: str
    client_id: str


def _ensure_private_directory(
    path: Path,
    description: str,
    *,
    private_root: Path,
) -> Path:
    try:
        return PRIVATE_INPUT.ensure_private_directory(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise NewInstallationError(str(exc)) from exc


def _private_file(path: Path, description: str, private_root: Path) -> bytes:
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=private_root,
            require_nonempty=True,
            maximum_size=1024 * 1024,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise NewInstallationError(str(exc)) from exc


def _write_new_private_file(
    path: Path,
    value: bytes,
    description: str,
    *,
    private_root: Path,
    allow_existing_exact: bool = False,
) -> None:
    try:
        PRIVATE_INPUT.write_private_snapshot(
            destination=path,
            content=value,
            description=description,
            private_root=private_root,
            allow_existing_exact=allow_existing_exact,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise NewInstallationError(str(exc)) from exc


def canonical_journal_bytes(document: dict[str, Any]) -> bytes:
    """Return the canonical, hashable representation of a public journal."""

    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"


def _new_installation_root(private_root: Path) -> Path:
    operation_root = private_root / NEW_INSTALLATION_DIRECTORY_NAME
    _ensure_private_directory(
        operation_root,
        "new installation transaction directory",
        private_root=private_root,
    )
    return operation_root


def _write_new_installation_journal(
    *,
    operation_root: Path,
    private_root: Path,
    document: dict[str, Any],
) -> None:
    state = document.get("state")
    if state not in NEW_INSTALLATION_STATES:
        raise NewInstallationError("new installation journal state is invalid")
    content = canonical_journal_bytes(document)
    temporary = operation_root / f".{NEW_INSTALLATION_JOURNAL_NAME}.{state}.tmp"
    destination = operation_root / NEW_INSTALLATION_JOURNAL_NAME
    _write_new_private_file(
        temporary,
        content,
        "new installation journal replacement",
        private_root=private_root,
        allow_existing_exact=True,
    )
    try:
        os.replace(temporary, destination)
        descriptor = os.open(
            operation_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise NewInstallationError(
            "new installation journal could not be published"
        ) from exc
    if (
        _private_file(
            destination,
            "new installation journal",
            private_root,
        )
        != content
    ):
        raise NewInstallationError("new installation journal publication changed")


def _load_new_installation_journal(
    *, operation_root: Path, private_root: Path
) -> dict[str, Any] | None:
    path = operation_root / NEW_INSTALLATION_JOURNAL_NAME
    if not path.exists():
        return None
    raw = _private_file(path, "new installation journal", private_root)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        document = json.loads(raw, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise NewInstallationError("new installation journal is invalid") from exc
    expected_keys = {
        "schemaVersion",
        "operation",
        "commit",
        "context",
        "clusterUid",
        "identityMode",
        "issuerUrl",
        "clientId",
        "oldInstallationId",
        "newInstallationId",
        "oldSecret",
        "resultSecret",
        "acceptanceNamespace",
        "quarantine",
        "state",
        "pointOfNoReturn",
    }
    if (
        not isinstance(document, dict)
        or set(document) != expected_keys
        or document.get("schemaVersion") != NEW_INSTALLATION_SCHEMA
        or document.get("state") not in NEW_INSTALLATION_STATES
        or not isinstance(document.get("pointOfNoReturn"), bool)
        or raw != canonical_journal_bytes(document)
        or not _journal_shape_is_valid(document)
    ):
        raise NewInstallationError("new installation journal is invalid")
    return document


def _canonical_uuid_is_valid(value: Any) -> bool:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        return False
    return str(parsed) == value


def _resource_record_is_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"uid", "resourceVersion"}
        and _canonical_uuid_is_valid(value.get("uid"))
        and isinstance(value.get("resourceVersion"), str)
        and bool(value["resourceVersion"])
        and value["resourceVersion"] == value["resourceVersion"].strip()
    )


def _journal_shape_is_valid(document: dict[str, Any]) -> bool:
    operation = document.get("operation")
    state = document.get("state")
    try:
        INSTALLATION_STATE.validate_identity_selection(
            identity_mode=document.get("identityMode"),
            issuer_url=document.get("issuerUrl"),
            client_id=document.get("clientId"),
        )
    except INSTALLATION_STATE.InstallationStateContractError:
        return False
    common_valid = (
        operation in {"initialBootstrap", "noOp", "replacement"}
        and FULL_SHA_PATTERN.fullmatch(document.get("commit", "")) is not None
        and isinstance(document.get("context"), str)
        and bool(document["context"])
        and document["context"] == document["context"].strip()
        and _canonical_uuid_is_valid(document.get("clusterUid"))
        and _canonical_uuid_is_valid(document.get("newInstallationId"))
        and isinstance(document.get("quarantine"), dict)
    )
    if not common_valid:
        return False
    if operation == "initialBootstrap":
        namespace_valid = document.get("acceptanceNamespace") is None
        result_secret_valid = document.get("resultSecret") is None
        if state in {"readbackVerified", "completed"}:
            namespace_valid = _resource_record_is_valid(
                document.get("acceptanceNamespace")
            )
            result_secret_valid = _resource_record_is_valid(
                document.get("resultSecret")
            )
        return (
            state
            in {"secretAbsent", "trustBootstrapped", "readbackVerified", "completed"}
            and document.get("pointOfNoReturn") is False
            and document.get("oldInstallationId") is None
            and document.get("oldSecret") is None
            and document.get("quarantine") == {}
            and namespace_valid
            and result_secret_valid
        )
    if operation == "noOp":
        return (
            state == "completed"
            and document.get("pointOfNoReturn") is False
            and _canonical_uuid_is_valid(document.get("oldInstallationId"))
            and document.get("oldInstallationId") == document.get("newInstallationId")
            and _resource_record_is_valid(document.get("oldSecret"))
            and document.get("resultSecret") == document.get("oldSecret")
            and _resource_record_is_valid(document.get("acceptanceNamespace"))
            and document.get("quarantine") == {}
        )
    quarantine = document.get("quarantine")
    result_secret_valid = document.get("resultSecret") is None
    if state in {"readbackVerified", "completed"}:
        result_secret_valid = _resource_record_is_valid(document.get("resultSecret"))
    return (
        document.get("oldInstallationId") is None
        and _resource_record_is_valid(document.get("oldSecret"))
        and result_secret_valid
        and _resource_record_is_valid(document.get("acceptanceNamespace"))
        and set(quarantine) == set(QUARANTINED_TRUST_FILES)
        and all(
            isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest) is not None
            for digest in quarantine.values()
        )
        and (
            state in {"prepared", "quarantineReady"}
            and document.get("pointOfNoReturn") is False
            or state
            in {
                "secretDeleteStarted",
                "secretDeleteAccepted",
                "secretAbsent",
                "trustBootstrapped",
                "readbackVerified",
                "completed",
            }
            and document.get("pointOfNoReturn") is True
        )
    )


def _advance_new_installation(
    *,
    operation_root: Path,
    private_root: Path,
    journal: dict[str, Any],
    state: str,
    point_of_no_return: bool | None = None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    advanced = dict(journal)
    advanced["state"] = state
    if point_of_no_return is not None:
        advanced["pointOfNoReturn"] = point_of_no_return
    if updates is not None:
        advanced.update(updates)
    _write_new_installation_journal(
        operation_root=operation_root,
        private_root=private_root,
        document=advanced,
    )
    return advanced


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _quarantine_old_trust(
    *,
    operation_root: Path,
    private_root: Path,
    secret_store: Path,
    expected_digests: dict[str, str],
) -> None:
    if set(expected_digests) != set(QUARANTINED_TRUST_FILES):
        raise NewInstallationError("new installation quarantine inventory is invalid")
    quarantine = operation_root / "quarantine"
    _ensure_private_directory(
        quarantine,
        "new installation quarantine",
        private_root=private_root,
    )
    unexpected = {path.name for path in quarantine.iterdir()} - set(expected_digests)
    if unexpected:
        raise NewInstallationError(
            "new installation quarantine contains unexpected files"
        )
    for filename in QUARANTINED_TRUST_FILES:
        source = secret_store / filename
        destination = quarantine / filename
        source_exists = source.exists() or source.is_symlink()
        destination_exists = destination.exists() or destination.is_symlink()
        if source_exists and destination_exists:
            raise NewInstallationError(
                "new installation quarantine has duplicate trust state"
            )
        candidate = destination if destination_exists else source
        if not candidate.exists():
            raise NewInstallationError(
                "new installation quarantine trust state is missing"
            )
        content = _private_file(candidate, f"quarantined {filename}", private_root)
        if hashlib.sha256(content).hexdigest() != expected_digests[filename]:
            raise NewInstallationError(
                "new installation quarantine digest does not match"
            )
        if source_exists:
            try:
                os.replace(source, destination)
                _fsync_directory(secret_store)
                _fsync_directory(quarantine)
            except OSError as exc:
                raise NewInstallationError(
                    "old installation trust could not be quarantined"
                ) from exc


def _validate_exact_quarantine(
    *,
    operation_root: Path,
    private_root: Path,
    expected_digests: dict[str, str],
    allow_missing_files: bool = False,
) -> None:
    quarantine = operation_root / "quarantine"
    try:
        metadata = os.lstat(quarantine)
    except FileNotFoundError:
        if allow_missing_files:
            return
        raise NewInstallationError(
            "new installation quarantine is unavailable"
        ) from None
    except OSError as exc:
        raise NewInstallationError(
            "new installation quarantine is unavailable"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise NewInstallationError("new installation quarantine is unavailable")
    present = {path.name: path for path in quarantine.iterdir()}
    if set(present) - set(expected_digests) or (
        not allow_missing_files and set(present) != set(expected_digests)
    ):
        raise NewInstallationError(
            "new installation quarantine inventory does not match"
        )
    for filename, path in present.items():
        content = _private_file(
            path,
            f"quarantined {filename}",
            private_root,
        )
        if hashlib.sha256(content).hexdigest() != expected_digests[filename]:
            raise NewInstallationError(
                "new installation quarantine digest does not match"
            )


def _delete_exact_quarantine(
    *,
    operation_root: Path,
    private_root: Path,
    expected_digests: dict[str, str],
) -> None:
    quarantine = operation_root / "quarantine"
    try:
        metadata = os.lstat(quarantine)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise NewInstallationError(
            "new installation quarantine is unavailable"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise NewInstallationError("new installation quarantine is unavailable")
    unexpected = {path.name for path in quarantine.iterdir()} - set(expected_digests)
    if unexpected:
        raise NewInstallationError(
            "new installation quarantine contains unexpected files"
        )
    for filename in QUARANTINED_TRUST_FILES:
        path = quarantine / filename
        if not path.exists():
            continue
        content = _private_file(path, f"quarantined {filename}", private_root)
        if hashlib.sha256(content).hexdigest() != expected_digests[filename]:
            raise NewInstallationError(
                "new installation quarantine digest does not match"
            )
        try:
            path.unlink()
            _fsync_directory(quarantine)
        except OSError as exc:
            raise NewInstallationError(
                "new installation quarantine cleanup failed"
            ) from exc
    try:
        quarantine.rmdir()
        _fsync_directory(operation_root)
    except OSError as exc:
        raise NewInstallationError(
            "new installation quarantine cleanup failed"
        ) from exc


def _canonical_private_json(raw: bytes, description: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise ValueError("non-standard constant")

    try:
        document = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise NewInstallationError(f"{description} is invalid") from exc
    canonical = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    if not isinstance(document, dict) or raw != canonical:
        raise NewInstallationError(f"{description} is invalid")
    return document


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _selected_cluster_uid(*, kubeconfig: Path, context: str, runner: Runner) -> str:
    try:
        cluster_uid = (
            runner(
                _kubectl(
                    kubeconfig,
                    context,
                    "get",
                    "namespace",
                    "kube-system",
                    "--output=jsonpath={.metadata.uid}",
                ),
                None,
            )
            .decode()
            .strip()
        )
        parsed_cluster_uid = UUID(cluster_uid)
    except (UnicodeDecodeError, ValueError) as exc:
        raise NewInstallationError("selected cluster UID is invalid") from exc
    if str(parsed_cluster_uid) != cluster_uid:
        raise NewInstallationError("selected cluster UID is invalid")
    return cluster_uid


def _retired_v2_identity(
    *,
    raw: bytes,
    context: str,
    cluster_uid: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
) -> dict[str, Any]:
    document = _canonical_private_json(raw, "retired v2 installation identity")
    expected = {
        "contractVersion": "aileron-installation-identity/v2",
        "clusterUid": cluster_uid,
        "context": context,
        "namespaces": RETIRED_V2_NAMESPACES,
        "realm": "aileron" if identity_mode == "bundledKeycloak" else None,
        "issuerUrl": issuer_url,
        "clientId": client_id,
    }
    if document != expected:
        raise NewInstallationError("retired v2 installation identity does not match")
    return document


def _load_retired_v2_trust(
    *,
    identity_raw: bytes,
    secret_store: Path,
    private_root: Path,
    kubeconfig: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
) -> tuple[_OldTrust, dict[str, Any], dict[str, str]]:
    cluster_uid = _selected_cluster_uid(
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    identity = _retired_v2_identity(
        raw=identity_raw,
        context=context,
        cluster_uid=cluster_uid,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
    )
    identity_digest = hashlib.sha256(identity_raw).hexdigest()
    key = _private_file(
        secret_store / "acceptance-hmac.key",
        "retired v2 acceptance signing key",
        private_root,
    )
    if len(key) != 32:
        raise NewInstallationError("retired v2 acceptance signing key is invalid")
    anchor_raw = _private_file(
        secret_store / ANCHOR_FILE,
        "retired v2 acceptance trust anchor",
        private_root,
    )
    anchor = _canonical_private_json(
        anchor_raw,
        "retired v2 acceptance trust anchor",
    )
    expected_anchor_without_uid = {
        "contractVersion": "aileron-acceptance-trust-anchor/v1",
        "clusterUid": cluster_uid,
        "context": context,
        "installationIdentitySha256": identity_digest,
        "keySha256": hashlib.sha256(key).hexdigest(),
        "secretName": SECRET_NAME,
        "secretNamespace": SECRET_NAMESPACE,
    }
    if set(anchor) != {*expected_anchor_without_uid, "secretUid"} or any(
        anchor.get(key_name) != value
        for key_name, value in expected_anchor_without_uid.items()
    ):
        raise NewInstallationError("retired v2 acceptance trust anchor does not match")
    try:
        parsed_anchor_uid = UUID(anchor.get("secretUid"))
    except (TypeError, ValueError) as exc:
        raise NewInstallationError(
            "retired v2 acceptance trust anchor is invalid"
        ) from exc
    if str(parsed_anchor_uid) != anchor["secretUid"]:
        raise NewInstallationError("retired v2 acceptance trust anchor is invalid")

    def read_namespace() -> Any:
        try:
            raw_namespace = runner(
                _kubectl(
                    kubeconfig,
                    context,
                    "get",
                    "namespace",
                    SECRET_NAMESPACE,
                    "--output=json",
                ),
                None,
            )
            return NAMESPACE_CONTRACT.validate_namespace_json(
                raw_namespace,
                namespace=SECRET_NAMESPACE,
                require_canonical_uid=True,
            )
        except (UnicodeDecodeError, NAMESPACE_CONTRACT.NamespaceContractError) as exc:
            raise NewInstallationError(
                "retired v2 acceptance Namespace is invalid"
            ) from exc

    namespace_record = read_namespace()
    try:
        secret = json.loads(
            runner(
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
                None,
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NewInstallationError("retired v2 acceptance Secret is invalid") from exc
    metadata = secret.get("metadata") if isinstance(secret, dict) else None
    secret_uid = metadata.get("uid") if isinstance(metadata, dict) else None
    resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, dict) else None
    )
    expected_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "immutable": True,
        "metadata": {
            "name": SECRET_NAME,
            "namespace": SECRET_NAMESPACE,
            "labels": {
                "platform.aileron.dev/secret-owner": "aileron-installer",
                "platform.aileron.dev/cluster-uid": cluster_uid,
            },
            "annotations": {
                "platform.aileron.dev/context": context,
                "platform.aileron.dev/installation-identity-sha256": identity_digest,
            },
        },
        "type": "Opaque",
        "data": {"hmac-key": base64.b64encode(key).decode("ascii")},
    }
    actual_secret = {
        "apiVersion": secret.get("apiVersion") if isinstance(secret, dict) else None,
        "kind": secret.get("kind") if isinstance(secret, dict) else None,
        "immutable": secret.get("immutable") if isinstance(secret, dict) else None,
        "metadata": {
            "name": metadata.get("name") if isinstance(metadata, dict) else None,
            "namespace": metadata.get("namespace")
            if isinstance(metadata, dict)
            else None,
            "labels": metadata.get("labels") if isinstance(metadata, dict) else None,
            "annotations": metadata.get("annotations")
            if isinstance(metadata, dict)
            else None,
        },
        "type": secret.get("type") if isinstance(secret, dict) else None,
        "data": secret.get("data") if isinstance(secret, dict) else None,
    }
    try:
        parsed_secret_uid = UUID(secret_uid)
    except (TypeError, ValueError) as exc:
        raise NewInstallationError("retired v2 acceptance Secret is invalid") from exc
    if (
        actual_secret != expected_secret
        or str(parsed_secret_uid) != secret_uid
        or secret_uid != anchor["secretUid"]
        or not isinstance(resource_version, str)
        or not resource_version
        or resource_version != resource_version.strip()
    ):
        raise NewInstallationError("retired v2 acceptance Secret does not match")
    if read_namespace() != namespace_record:
        raise NewInstallationError(
            "retired v2 acceptance Namespace changed during validation"
        )
    old_trust = (
        _OldTrust(
            cluster_uid=cluster_uid,
            secret_uid=secret_uid,
            secret_resource_version=resource_version,
            acceptance_namespace_uid=namespace_record.uid,
            acceptance_namespace_resource_version=namespace_record.resource_version,
        ),
        identity,
    )
    return (
        *old_trust,
        {
            "installation-identity.json": hashlib.sha256(identity_raw).hexdigest(),
            "acceptance-hmac.key": hashlib.sha256(key).hexdigest(),
            ANCHOR_FILE: hashlib.sha256(anchor_raw).hexdigest(),
        },
    )


def _secret_uid(document: dict[str, Any]) -> tuple[str, str, bool]:
    metadata = document.get("metadata") if isinstance(document, dict) else None
    uid = metadata.get("uid") if isinstance(metadata, dict) else None
    resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, dict) else None
    )
    if (
        document.get("apiVersion") != "v1"
        or document.get("kind") != "Secret"
        or not isinstance(metadata, dict)
        or metadata.get("name") != SECRET_NAME
        or metadata.get("namespace") != SECRET_NAMESPACE
        or not isinstance(uid, str)
        or not isinstance(resource_version, str)
        or not resource_version
    ):
        raise NewInstallationError("acceptance signing Secret readback is invalid")
    try:
        parsed_uid = UUID(uid)
    except ValueError as exc:
        raise NewInstallationError(
            "acceptance signing Secret readback is invalid"
        ) from exc
    if str(parsed_uid) != uid:
        raise NewInstallationError("acceptance signing Secret readback is invalid")
    return uid, resource_version, metadata.get("deletionTimestamp") is not None


def _live_acceptance_secret_exists(
    *, kubeconfig: Path, context: str, runner: Runner
) -> bool:
    try:
        runner(
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
            None,
        )
    except BOOTSTRAP.CommandNotFoundError:
        return False
    except BOOTSTRAP.BootstrapError as exc:
        raise NewInstallationError(
            "live acceptance Secret presence check failed"
        ) from exc
    return True


def _generate_installation_id(
    *,
    installation_id_factory: InstallationIdFactory,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    cluster_uid: str,
) -> str:
    installation_id = installation_id_factory()
    try:
        INSTALLATION_STATE.installation_identity_document(
            installation_id=installation_id,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            cluster_uid=cluster_uid,
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise NewInstallationError("installation identity is invalid") from exc
    return installation_id


def _base_journal(
    *,
    operation: str,
    commit: str,
    context: str,
    cluster_uid: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    old_installation_id: str | None,
    new_installation_id: str,
    old_secret: dict[str, str] | None,
    result_secret: dict[str, str] | None,
    acceptance_namespace: dict[str, str] | None,
    quarantine: dict[str, str],
    state: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": NEW_INSTALLATION_SCHEMA,
        "operation": operation,
        "commit": commit,
        "context": context,
        "clusterUid": cluster_uid,
        "identityMode": identity_mode,
        "issuerUrl": issuer_url,
        "clientId": client_id,
        "oldInstallationId": old_installation_id,
        "newInstallationId": new_installation_id,
        "oldSecret": old_secret,
        "resultSecret": result_secret,
        "acceptanceNamespace": acceptance_namespace,
        "quarantine": quarantine,
        "state": state,
        "pointOfNoReturn": False,
    }


def _write_initial_bootstrap_journal(
    *,
    operation_root: Path,
    private_root: Path,
    commit: str,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
    installation_id_factory: InstallationIdFactory,
) -> dict[str, Any]:
    if _live_acceptance_secret_exists(
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    ):
        raise NewInstallationError(
            "stable trust is absent while the live acceptance Secret exists"
        )
    cluster_uid = _selected_cluster_uid(
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    new_installation_id = _generate_installation_id(
        installation_id_factory=installation_id_factory,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        cluster_uid=cluster_uid,
    )
    journal = _base_journal(
        operation="initialBootstrap",
        commit=commit,
        context=context,
        cluster_uid=cluster_uid,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        old_installation_id=None,
        new_installation_id=new_installation_id,
        old_secret=None,
        result_secret=None,
        acceptance_namespace=None,
        quarantine={},
        state="secretAbsent",
    )
    _write_new_installation_journal(
        operation_root=operation_root,
        private_root=private_root,
        document=journal,
    )
    return journal


def _write_v3_no_op_journal(
    *,
    identity_raw: bytes,
    identity_document: dict[str, Any],
    secret_store: Path,
    operation_root: Path,
    private_root: Path,
    commit: str,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
    publish: bool = True,
) -> dict[str, Any]:
    try:
        trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
            context=context,
            kubeconfig=kubeconfig,
            runner=lambda command: runner(command, None),
        )
        identity = INSTALLATION_STATE.validate_installation_identity_document(
            identity_document,
            cluster_uid=trust.cluster_uid,
        )
        expected_identity = INSTALLATION_STATE.installation_identity_document(
            installation_id=identity["installationId"],
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            cluster_uid=trust.cluster_uid,
        )
    except (
        ACCEPTANCE_CLUSTER.AcceptanceClusterError,
        INSTALLATION_STATE.InstallationStateContractError,
    ) as exc:
        raise NewInstallationError(
            "existing v3 installation trust chain is invalid"
        ) from exc
    if (
        identity != expected_identity
        or _private_file(
            secret_store / "installation-identity.json",
            "installation identity readback",
            private_root,
        )
        != identity_raw
    ):
        raise NewInstallationError("installation identity selection does not match")
    journal = _base_journal(
        operation="noOp",
        commit=commit,
        context=context,
        cluster_uid=trust.cluster_uid,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        old_installation_id=identity["installationId"],
        new_installation_id=identity["installationId"],
        old_secret={
            "uid": trust.secret_uid,
            "resourceVersion": trust.secret_resource_version,
        },
        result_secret={
            "uid": trust.secret_uid,
            "resourceVersion": trust.secret_resource_version,
        },
        acceptance_namespace={
            "uid": trust.acceptance_namespace_uid,
            "resourceVersion": trust.acceptance_namespace_resource_version,
        },
        quarantine={},
        state="completed",
    )
    if publish:
        _write_new_installation_journal(
            operation_root=operation_root,
            private_root=private_root,
            document=journal,
        )
    return journal


def _write_replacement_journal(
    *,
    identity_raw: bytes,
    secret_store: Path,
    operation_root: Path,
    private_root: Path,
    commit: str,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
    installation_id_factory: InstallationIdFactory,
) -> dict[str, Any]:
    old_trust, _old_identity, quarantine_digests = _load_retired_v2_trust(
        identity_raw=identity_raw,
        secret_store=secret_store,
        private_root=private_root,
        kubeconfig=kubeconfig,
        context=context,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        runner=runner,
    )
    new_installation_id = _generate_installation_id(
        installation_id_factory=installation_id_factory,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        cluster_uid=old_trust.cluster_uid,
    )
    journal = _base_journal(
        operation="replacement",
        commit=commit,
        context=context,
        cluster_uid=old_trust.cluster_uid,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        old_installation_id=None,
        new_installation_id=new_installation_id,
        old_secret={
            "uid": old_trust.secret_uid,
            "resourceVersion": old_trust.secret_resource_version,
        },
        result_secret=None,
        acceptance_namespace={
            "uid": old_trust.acceptance_namespace_uid,
            "resourceVersion": old_trust.acceptance_namespace_resource_version,
        },
        quarantine=quarantine_digests,
        state="prepared",
    )
    _write_new_installation_journal(
        operation_root=operation_root,
        private_root=private_root,
        document=journal,
    )
    return journal


def _classify_new_transaction(
    *,
    secret_store: Path,
    operation_root: Path,
    private_root: Path,
    commit: str,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
    installation_id_factory: InstallationIdFactory,
) -> dict[str, Any]:
    presence = {
        filename: (secret_store / filename).exists()
        or (secret_store / filename).is_symlink()
        for filename in QUARANTINED_TRUST_FILES
    }
    if any(presence.values()) and not all(presence.values()):
        raise NewInstallationError("stable installation trust is partially present")
    if not any(presence.values()):
        return _write_initial_bootstrap_journal(
            operation_root=operation_root,
            private_root=private_root,
            commit=commit,
            context=context,
            kubeconfig=kubeconfig,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            runner=runner,
            installation_id_factory=installation_id_factory,
        )

    identity_raw = _private_file(
        secret_store / "installation-identity.json",
        "installation identity",
        private_root,
    )
    identity_document = _canonical_private_json(identity_raw, "installation identity")
    version = identity_document.get("contractVersion")
    if version == "aileron-installation-identity/v3":
        return _write_v3_no_op_journal(
            identity_raw=identity_raw,
            identity_document=identity_document,
            secret_store=secret_store,
            operation_root=operation_root,
            private_root=private_root,
            commit=commit,
            context=context,
            kubeconfig=kubeconfig,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            runner=runner,
        )
    if version == "aileron-installation-identity/v2":
        return _write_replacement_journal(
            identity_raw=identity_raw,
            secret_store=secret_store,
            operation_root=operation_root,
            private_root=private_root,
            commit=commit,
            context=context,
            kubeconfig=kubeconfig,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            runner=runner,
            installation_id_factory=installation_id_factory,
        )
    raise NewInstallationError("installation identity contract version is unsupported")


def _classify_completed_history_current_state(
    *,
    history: dict[str, Any],
    secret_store: Path,
    operation_root: Path,
    private_root: Path,
    commit: str,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
) -> dict[str, Any]:
    presence = {
        filename: (secret_store / filename).exists()
        or (secret_store / filename).is_symlink()
        for filename in QUARANTINED_TRUST_FILES
    }
    try:
        if not all(presence.values()):
            raise NewInstallationError("stable trust is not complete")
        identity_raw = _private_file(
            secret_store / "installation-identity.json",
            "installation identity",
            private_root,
        )
        identity_document = _canonical_private_json(
            identity_raw,
            "installation identity",
        )
        if (
            identity_document.get("contractVersion")
            != "aileron-installation-identity/v3"
        ):
            raise NewInstallationError("current installation identity is not v3")
        current = _write_v3_no_op_journal(
            identity_raw=identity_raw,
            identity_document=identity_document,
            secret_store=secret_store,
            operation_root=operation_root,
            private_root=private_root,
            commit=commit,
            context=context,
            kubeconfig=kubeconfig,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            runner=runner,
            publish=False,
        )
    except NewInstallationError as exc:
        raise NewInstallationError(
            "completed history does not match current trust"
        ) from exc
    comparable_fields = {
        "clusterUid",
        "identityMode",
        "issuerUrl",
        "clientId",
        "newInstallationId",
        "resultSecret",
        "acceptanceNamespace",
    }
    if any(history.get(field) != current.get(field) for field in comparable_fields):
        raise NewInstallationError("completed history does not match current trust")
    return current


def _read_secret_with_delete_client(
    *, client: Any, query: dict[str, str], get_transport: Any
) -> dict[str, Any] | None:
    if get_transport is None:
        return client.get(**query)
    return client.get(**query, transport=get_transport)


def _drive_replacement_to_secret_absent(
    *,
    journal: dict[str, Any],
    fresh_transaction: bool,
    operation_root: Path,
    private_root: Path,
    secret_store: Path,
    kubeconfig: Path,
    context: str,
    delete_transport: Any,
    get_transport: Any,
    sleeper: Callable[[float], None],
    maximum_get_attempts: int,
) -> dict[str, Any]:
    client = KUBERNETES_REST.load_kubernetes_delete_client(
        kubeconfig=kubeconfig,
        context=context,
        credential_directory=operation_root,
        private_root=private_root,
    )
    query = {
        "api_version": "v1",
        "resource": "secrets",
        "namespace": SECRET_NAMESPACE,
        "name": SECRET_NAME,
    }
    if journal["state"] == "prepared":
        _quarantine_old_trust(
            operation_root=operation_root,
            private_root=private_root,
            secret_store=secret_store,
            expected_digests=journal["quarantine"],
        )
        journal = _advance_new_installation(
            operation_root=operation_root,
            private_root=private_root,
            journal=journal,
            state="quarantineReady",
        )

    if journal["state"] == "quarantineReady":
        if not fresh_transaction:
            current = _read_secret_with_delete_client(
                client=client,
                query=query,
                get_transport=get_transport,
            )
            if current is None:
                journal = _advance_new_installation(
                    operation_root=operation_root,
                    private_root=private_root,
                    journal=journal,
                    state="secretAbsent",
                    point_of_no_return=True,
                )
            else:
                uid, resource_version, deleting = _secret_uid(current)
                if uid != journal["oldSecret"]["uid"]:
                    raise NewInstallationError(
                        "acceptance signing Secret has a different UID"
                    )
                if (
                    resource_version != journal["oldSecret"]["resourceVersion"]
                    or deleting
                ):
                    raise NewInstallationError(
                        "acceptance signing Secret changed before delete"
                    )
        if journal["state"] == "quarantineReady":
            journal = _advance_new_installation(
                operation_root=operation_root,
                private_root=private_root,
                journal=journal,
                state="secretDeleteStarted",
                point_of_no_return=True,
            )

    if journal["state"] == "secretDeleteStarted":
        if not fresh_transaction:
            current = _read_secret_with_delete_client(
                client=client,
                query=query,
                get_transport=get_transport,
            )
            if current is None:
                journal = _advance_new_installation(
                    operation_root=operation_root,
                    private_root=private_root,
                    journal=journal,
                    state="secretAbsent",
                )
            else:
                uid, resource_version, deleting = _secret_uid(current)
                if uid != journal["oldSecret"]["uid"]:
                    raise NewInstallationError(
                        "acceptance signing Secret has a different UID"
                    )
                if deleting:
                    journal = _advance_new_installation(
                        operation_root=operation_root,
                        private_root=private_root,
                        journal=journal,
                        state="secretDeleteAccepted",
                    )
                elif resource_version != journal["oldSecret"]["resourceVersion"]:
                    raise NewInstallationError(
                        "acceptance signing Secret changed before delete"
                    )
        if journal["state"] == "secretDeleteStarted":
            delete_arguments = {
                **query,
                "uid": journal["oldSecret"]["uid"],
                "resource_version": journal["oldSecret"]["resourceVersion"],
            }
            if delete_transport is None:
                client.delete(**delete_arguments)
            else:
                client.delete(**delete_arguments, transport=delete_transport)
            journal = _advance_new_installation(
                operation_root=operation_root,
                private_root=private_root,
                journal=journal,
                state="secretDeleteAccepted",
            )

    if journal["state"] == "secretDeleteAccepted":
        for attempt in range(maximum_get_attempts):
            current = _read_secret_with_delete_client(
                client=client,
                query=query,
                get_transport=get_transport,
            )
            if current is None:
                return _advance_new_installation(
                    operation_root=operation_root,
                    private_root=private_root,
                    journal=journal,
                    state="secretAbsent",
                )
            uid, _resource_version, _deleting = _secret_uid(current)
            if uid != journal["oldSecret"]["uid"]:
                raise NewInstallationError(
                    "acceptance signing Secret has a different UID"
                )
            if attempt + 1 < maximum_get_attempts:
                sleeper(1.0)
        raise NewInstallationError(
            "acceptance signing Secret deletion did not complete"
        )
    return journal


def _verify_new_trust_readback(
    *,
    journal: dict[str, Any],
    operation_root: Path,
    private_root: Path,
    secret_store: Path,
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> dict[str, Any]:
    try:
        final_trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
            context=context,
            kubeconfig=kubeconfig,
            runner=lambda command: runner(command, None),
        )
        final_identity_document = _canonical_private_json(
            _private_file(
                secret_store / "installation-identity.json",
                "new installation identity",
                private_root,
            ),
            "new installation identity",
        )
        final_identity = INSTALLATION_STATE.validate_installation_identity_document(
            final_identity_document,
            cluster_uid=journal["clusterUid"],
        )
        expected_identity = INSTALLATION_STATE.installation_identity_document(
            installation_id=journal["newInstallationId"],
            identity_mode=journal["identityMode"],
            issuer_url=journal["issuerUrl"],
            client_id=journal["clientId"],
            cluster_uid=journal["clusterUid"],
        )
    except (
        ACCEPTANCE_CLUSTER.AcceptanceClusterError,
        INSTALLATION_STATE.InstallationStateContractError,
    ) as exc:
        raise NewInstallationError("new installation trust readback failed") from exc
    if (
        final_identity != expected_identity
        or final_trust.cluster_uid != journal["clusterUid"]
    ):
        raise NewInstallationError("new installation trust readback does not match")

    acceptance_namespace = {
        "uid": final_trust.acceptance_namespace_uid,
        "resourceVersion": final_trust.acceptance_namespace_resource_version,
    }
    if journal["operation"] == "replacement" and (
        final_trust.secret_uid == journal["oldSecret"]["uid"]
        or acceptance_namespace != journal["acceptanceNamespace"]
    ):
        raise NewInstallationError("new installation trust readback does not match")
    return _advance_new_installation(
        operation_root=operation_root,
        private_root=private_root,
        journal=journal,
        state="readbackVerified",
        updates={
            "acceptanceNamespace": acceptance_namespace,
            "resultSecret": {
                "uid": final_trust.secret_uid,
                "resourceVersion": final_trust.secret_resource_version,
            },
        },
    )


def _execute_new_transaction(
    *,
    journal: dict[str, Any],
    fresh_transaction: bool,
    bootstrap_port: BOOTSTRAP.LockedBootstrapPort,
    operation_root: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    runner: Runner,
    key_factory: KeyFactory,
    delete_transport: Any,
    get_transport: Any,
    sleeper: Callable[[float], None],
    maximum_get_attempts: int,
) -> dict[str, Any]:
    private_root = bootstrap_port.private_root
    secret_store = bootstrap_port.secret_store
    kubeconfig = bootstrap_port.kubeconfig
    if journal["operation"] == "replacement":
        if journal["state"] != "prepared":
            _validate_exact_quarantine(
                operation_root=operation_root,
                private_root=private_root,
                expected_digests=journal["quarantine"],
                allow_missing_files=journal["state"] == "readbackVerified",
            )
        journal = _drive_replacement_to_secret_absent(
            journal=journal,
            fresh_transaction=fresh_transaction,
            operation_root=operation_root,
            private_root=private_root,
            secret_store=secret_store,
            kubeconfig=kubeconfig,
            context=context,
            delete_transport=delete_transport,
            get_transport=get_transport,
            sleeper=sleeper,
            maximum_get_attempts=maximum_get_attempts,
        )

    if journal["state"] == "secretAbsent":
        try:
            bootstrap_port.bootstrap(
                identity_mode=identity_mode,
                issuer_url=issuer_url,
                client_id=client_id,
                key_factory=key_factory,
                installation_id_factory=lambda: journal["newInstallationId"],
            )
        except BOOTSTRAP.BootstrapError as exc:
            raise NewInstallationError(
                "new installation trust bootstrap failed"
            ) from exc
        journal = _advance_new_installation(
            operation_root=operation_root,
            private_root=private_root,
            journal=journal,
            state="trustBootstrapped",
        )

    if journal["state"] == "trustBootstrapped":
        journal = _verify_new_trust_readback(
            journal=journal,
            operation_root=operation_root,
            private_root=private_root,
            secret_store=secret_store,
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
        )

    if journal["state"] == "readbackVerified":
        if journal["operation"] == "replacement":
            _delete_exact_quarantine(
                operation_root=operation_root,
                private_root=private_root,
                expected_digests=journal["quarantine"],
            )
        journal = _advance_new_installation(
            operation_root=operation_root,
            private_root=private_root,
            journal=journal,
            state="completed",
        )
    return journal


def _validate_request(
    *,
    commit: str,
    kubeconfig: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    confirm_forward_only: bool,
    maximum_get_attempts: int,
    runner: Runner,
) -> _Request:
    if confirm_forward_only is not True:
        raise NewInstallationError(
            "new installation requires explicit forward-only confirmation"
        )
    if (
        FULL_SHA_PATTERN.fullmatch(commit) is None
        or not context
        or context != context.strip()
        or not isinstance(maximum_get_attempts, int)
        or not 1 <= maximum_get_attempts <= 120
    ):
        raise NewInstallationError("new installation input is invalid")
    try:
        INSTALLATION_STATE.validate_identity_selection(
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise NewInstallationError(str(exc)) from exc
    if runner(["git", "status", "--porcelain", "--untracked-files=all"], None):
        raise NewInstallationError("source checkout must be clean")
    try:
        head = runner(["git", "rev-parse", "HEAD"], None).decode().strip()
    except UnicodeDecodeError as exc:
        raise NewInstallationError("source HEAD is invalid") from exc
    if head != commit:
        raise NewInstallationError("source HEAD does not match commit")
    return _Request(
        commit=commit,
        kubeconfig=kubeconfig,
        context=context,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
    )


def _run_locked_request(
    *,
    request: _Request,
    bootstrap_port: BOOTSTRAP.LockedBootstrapPort,
    runner: Runner,
    key_factory: KeyFactory,
    installation_id_factory: InstallationIdFactory,
    delete_transport: Any,
    get_transport: Any,
    sleeper: Callable[[float], None],
    maximum_get_attempts: int,
) -> dict[str, Any]:
    private_root = bootstrap_port.private_root
    operation_root = _new_installation_root(private_root)
    journal = _load_new_installation_journal(
        operation_root=operation_root,
        private_root=private_root,
    )
    fresh_transaction = journal is None
    if journal is None:
        journal = _classify_new_transaction(
            secret_store=bootstrap_port.secret_store,
            operation_root=operation_root,
            private_root=private_root,
            commit=request.commit,
            context=request.context,
            kubeconfig=bootstrap_port.kubeconfig,
            identity_mode=request.identity_mode,
            issuer_url=request.issuer_url,
            client_id=request.client_id,
            runner=runner,
            installation_id_factory=installation_id_factory,
        )
    elif journal["state"] == "completed":
        return _classify_completed_history_current_state(
            history=journal,
            secret_store=bootstrap_port.secret_store,
            operation_root=operation_root,
            private_root=private_root,
            commit=request.commit,
            context=request.context,
            kubeconfig=bootstrap_port.kubeconfig,
            identity_mode=request.identity_mode,
            issuer_url=request.issuer_url,
            client_id=request.client_id,
            runner=runner,
        )
    else:
        expected_resume = {
            "commit": request.commit,
            "context": request.context,
            "identityMode": request.identity_mode,
            "issuerUrl": request.issuer_url,
            "clientId": request.client_id,
        }
        if any(journal.get(key) != value for key, value in expected_resume.items()):
            raise NewInstallationError("new installation resume input does not match")
    return _execute_new_transaction(
        journal=journal,
        fresh_transaction=fresh_transaction,
        bootstrap_port=bootstrap_port,
        operation_root=operation_root,
        context=request.context,
        identity_mode=request.identity_mode,
        issuer_url=request.issuer_url,
        client_id=request.client_id,
        runner=runner,
        key_factory=key_factory,
        delete_transport=delete_transport,
        get_transport=get_transport,
        sleeper=sleeper,
        maximum_get_attempts=maximum_get_attempts,
    )


def new_installation(
    *,
    commit: str,
    kubeconfig: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    confirm_forward_only: bool,
    runner: Runner = BOOTSTRAP.run_command,
    key_factory: KeyFactory = lambda: secrets.token_bytes(32),
    installation_id_factory: InstallationIdFactory = lambda: str(uuid4()),
    delete_transport: Any = None,
    get_transport: Any = None,
    sleeper: Callable[[float], None] = time.sleep,
    maximum_get_attempts: int = 30,
) -> dict[str, Any]:
    """Classify and safely prepare prerelease installation trust under one lock."""

    request = _validate_request(
        commit=commit,
        kubeconfig=kubeconfig,
        context=context,
        identity_mode=identity_mode,
        issuer_url=issuer_url,
        client_id=client_id,
        confirm_forward_only=confirm_forward_only,
        maximum_get_attempts=maximum_get_attempts,
        runner=runner,
    )
    with BOOTSTRAP.locked_bootstrap_port(
        commit=request.commit,
        kubeconfig=request.kubeconfig,
        context=request.context,
        runner=runner,
    ) as bootstrap_port:
        return _run_locked_request(
            request=request,
            bootstrap_port=bootstrap_port,
            runner=runner,
            key_factory=key_factory,
            installation_id_factory=installation_id_factory,
            delete_transport=delete_transport,
            get_transport=get_transport,
            sleeper=sleeper,
            maximum_get_attempts=maximum_get_attempts,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument(
        "--identity-mode",
        choices=("bundledKeycloak", "externalOidc"),
        required=True,
    )
    parser.add_argument("--issuer-url", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--confirm-forward-only", action="store_true")
    return parser


def main(
    argv: list[str] | None = None, *, runner: Runner = BOOTSTRAP.run_command
) -> int:
    arguments = build_parser().parse_args(argv)
    journal = new_installation(
        commit=arguments.commit,
        kubeconfig=arguments.kubeconfig,
        context=arguments.context,
        identity_mode=arguments.identity_mode,
        issuer_url=arguments.issuer_url,
        client_id=arguments.client_id,
        confirm_forward_only=arguments.confirm_forward_only,
        runner=runner,
    )
    print(canonical_journal_bytes(journal).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NewInstallationError as exc:
        print(f"new installation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
