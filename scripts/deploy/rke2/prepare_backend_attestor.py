#!/usr/bin/env python3
"""Prepare the retained backend-attestor Namespace and image pull Secret."""

from __future__ import annotations

import argparse
import base64
import binascii
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NamedTuple

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
NAMESPACE = "aileron-backend-attestor-system"
SECRET_NAME = "harbor-rke-creds"
SECRET_OWNER_LABEL = "platform.aileron.dev/secret-owner"
PREPARATION_RESULT_SCHEMA = "aileron-backend-attestor-preparation-result/v1"
EXECUTION_RESOURCES_SCHEMA = "aileron-backend-execution-resources-binding/v1"
REGISTRY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*(?::[0-9]{1,5})?$")
KUBECTL_TIMEOUT_SECONDS = 60
CommandRunner = Callable[..., str]


def _load_module(name: str, filename: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        name,
        SCRIPT_DIRECTORY / filename,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("backend attestor preparation dependency is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_module(
    "aileron_backend_prepare_installation_state",
    "installation_state.py",
)
PRIVATE_INPUT = _load_module(
    "aileron_backend_prepare_private_input",
    "private_input.py",
)
BACKEND_ATTESTOR = _load_module(
    "aileron_backend_prepare_backend_attestor",
    "backend_attestor.py",
)
NAMESPACE_CONTRACT = _load_module(
    "aileron_backend_prepare_namespace_contract",
    "namespace_contract.py",
)
NAMESPACE_OWNER = NAMESPACE_CONTRACT.NAMESPACE_OWNER
NAMESPACE_OWNER_LABEL = NAMESPACE_CONTRACT.NAMESPACE_OWNER_LABEL
PSA_LABELS = {
    key: value
    for key, value in NAMESPACE_CONTRACT.profile_labels(NAMESPACE).items()
    if key.startswith(NAMESPACE_CONTRACT.POD_SECURITY_LABEL_PREFIX)
}


class SecretRecord(NamedTuple):
    uid: str
    resource_version: str
    labels: dict[str, str]
    secret_type: str
    data: dict[str, str]


class BackendAttestorPreparationError(RuntimeError):
    """Raised with one safe structured failure result."""

    def __init__(
        self,
        *,
        stage: str,
        mode: str,
        namespace_created: bool = False,
    ) -> None:
        self.result = {
            "schemaVersion": PREPARATION_RESULT_SCHEMA,
            "mode": mode,
            "ready": False,
            "failureStage": stage,
            "namespaceCreated": namespace_created,
            "durablePrerequisiteRetained": namespace_created,
        }
        super().__init__(f"backend attestor preparation failed during {stage}")


class BackendAttestorResourceValidationError(RuntimeError):
    """Raised when the retained execution resources are missing or drifted."""


class _CommandError(RuntimeError):
    pass


def _run_command(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    stdin: str | None = None,
) -> str:
    try:
        process = subprocess.run(
            command,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **(environment or {})},
            text=True,
            check=False,
            timeout=KUBECTL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise _CommandError("Kubernetes command timed out") from exc
    if process.returncode != 0:
        raise _CommandError("Kubernetes command failed")
    return process.stdout


def _canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _validate_registry(registry: str) -> str:
    if REGISTRY_PATTERN.fullmatch(registry) is None:
        raise ValueError("registry must be a canonical host with an optional port")
    host, separator, port_text = registry.partition(":")
    if (
        len(host) > 253
        or host.endswith(".")
        or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            for label in host.split(".")
        )
    ):
        raise ValueError("registry must be a canonical host with an optional port")
    if separator:
        if len(port_text) > 1 and port_text.startswith("0"):
            raise ValueError("registry port is invalid")
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError("registry port is invalid")
    return registry


def _validate_context(context: str) -> str:
    if not context or context != context.strip() or any(
        ord(character) < 32 or ord(character) == 127 for character in context
    ):
        raise ValueError("an exact Kubernetes context is required")
    return context


def _dockerconfig_bytes(raw: bytes, registry: str) -> bytes:
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Harbor dockerconfig is invalid") from exc
    if not isinstance(document, dict) or set(document) != {"auths"}:
        raise ValueError("Harbor dockerconfig must contain only exact auths")
    auths = document["auths"]
    if not isinstance(auths, dict) or set(auths) != {registry}:
        raise ValueError("Harbor dockerconfig must contain the exact registry auth entry")
    credentials = auths[registry]
    if not isinstance(credentials, dict):
        raise ValueError("Harbor registry credentials are invalid")
    if set(credentials) == {"auth"}:
        encoded = credentials["auth"]
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("Harbor registry credentials are invalid")
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Harbor registry credentials are invalid") from exc
        username, separator, password = decoded.partition(":")
        if not separator or not username or not password:
            raise ValueError("Harbor registry credentials are invalid")
    elif set(credentials) == {"username", "password"}:
        if any(
            not isinstance(credentials[key], str) or not credentials[key]
            for key in ("username", "password")
        ):
            raise ValueError("Harbor registry credentials are invalid")
    else:
        raise ValueError("Harbor registry credentials are invalid")
    return raw


def _namespace_labels(existing: dict[str, str] | None = None) -> dict[str, str]:
    return NAMESPACE_CONTRACT.labels_with_exact_profile(NAMESPACE, existing or {})


def _namespace_manifest() -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": NAMESPACE, "labels": _namespace_labels()},
    }


def _secret_data(dockerconfig: bytes) -> dict[str, str]:
    return {
        ".dockerconfigjson": base64.b64encode(dockerconfig).decode("ascii")
    }


def _parse_document(raw: str, *, kind: str, name: str) -> dict[str, Any] | None:
    if not raw.strip():
        return None
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{kind} query result is invalid") from exc
    metadata = document.get("metadata") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "v1"
        or document.get("kind") != kind
        or not isinstance(metadata, dict)
        or metadata.get("name") != name
    ):
        raise ValueError(f"{kind} query result is invalid")
    return document


def _metadata(document: dict[str, Any], *, description: str) -> tuple[str, str, dict[str, str]]:
    metadata = document["metadata"]
    uid = metadata.get("uid")
    resource_version = metadata.get("resourceVersion")
    labels = metadata.get("labels", {})
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(resource_version, str)
        or not resource_version
        or not isinstance(labels, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        )
    ):
        raise ValueError(f"{description} identity is invalid")
    return uid, resource_version, labels


def _namespace_record(
    document: dict[str, Any],
) -> NAMESPACE_CONTRACT.NamespaceRecord:
    try:
        return NAMESPACE_CONTRACT.validate_namespace_document(
            document,
            namespace=NAMESPACE,
            require_profile=False,
        )
    except NAMESPACE_CONTRACT.NamespaceContractError as exc:
        raise ValueError("backend attestor Namespace is invalid") from exc


def _secret_record(document: dict[str, Any]) -> SecretRecord:
    uid, resource_version, labels = _metadata(
        document,
        description="backend attestor image pull Secret",
    )
    metadata = document["metadata"]
    data = document.get("data")
    if (
        metadata.get("namespace") != NAMESPACE
        or metadata.get("deletionTimestamp") is not None
        or labels.get(SECRET_OWNER_LABEL) != NAMESPACE_OWNER
        or not isinstance(data, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in data.items()
        )
    ):
        raise ValueError("backend attestor image pull Secret ownership is invalid")
    return SecretRecord(
        uid=uid,
        resource_version=resource_version,
        labels=labels,
        secret_type=document.get("type"),
        data=data,
    )


def _namespace_patch(
    record: NAMESPACE_CONTRACT.NamespaceRecord,
) -> list[dict[str, Any]]:
    return [
        {"op": "test", "path": "/metadata/uid", "value": record.uid},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": record.resource_version,
        },
        {
            "op": "replace",
            "path": "/metadata/labels",
            "value": _namespace_labels(record.labels),
        },
    ]


def _secret_patch(
    record: SecretRecord,
    *,
    expected_data: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        {"op": "test", "path": "/metadata/uid", "value": record.uid},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": record.resource_version,
        },
        {
            "op": "add",
            "path": "/metadata/labels",
            "value": {**record.labels, SECRET_OWNER_LABEL: NAMESPACE_OWNER},
        },
        {
            "op": "add",
            "path": "/type",
            "value": "kubernetes.io/dockerconfigjson",
        },
        {"op": "add", "path": "/data", "value": expected_data},
    ]


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _query_namespace(
    *,
    kubeconfig: Path,
    context: str,
    environment: dict[str, str],
    runner: CommandRunner,
) -> dict[str, Any] | None:
    return _parse_document(
        runner(
            _kubectl(
                kubeconfig,
                context,
                "get",
                "namespace",
                NAMESPACE,
                "--ignore-not-found",
                "--output=json",
            ),
            environment=environment,
        ),
        kind="Namespace",
        name=NAMESPACE,
    )


def _query_secret(
    *,
    kubeconfig: Path,
    context: str,
    environment: dict[str, str],
    runner: CommandRunner,
) -> dict[str, Any] | None:
    return _parse_document(
        runner(
            _kubectl(
                kubeconfig,
                context,
                "--namespace",
                NAMESPACE,
                "get",
                "secret",
                SECRET_NAME,
                "--ignore-not-found",
                "--output=json",
            ),
            environment=environment,
        ),
        kind="Secret",
        name=SECRET_NAME,
    )


def _execute(
    *,
    runner: CommandRunner,
    command: list[str],
    environment: dict[str, str],
    manifest: dict[str, Any],
) -> str:
    return runner(
        command,
        environment=environment,
        stdin=_canonical(manifest).decode("utf-8"),
    )


def _namespace_operation(
    *,
    kubeconfig: Path,
    context: str,
    existing: NAMESPACE_CONTRACT.NamespaceRecord | None,
    dry_run: bool,
) -> tuple[list[str], dict[str, Any]]:
    suffix = ["--dry-run=server"] if dry_run else []
    if existing is None:
        return (
            _kubectl(
                kubeconfig,
                context,
                "create",
                "--filename=-",
                "--output=json",
                *suffix,
            ),
            _namespace_manifest(),
        )
    return (
        _kubectl(
            kubeconfig,
            context,
            "patch",
            "namespace",
            NAMESPACE,
            "--type=json",
            "--patch-file=-",
            "--output=json",
            *suffix,
        ),
        _namespace_patch(existing),
    )


def _secret_operation(
    *,
    kubeconfig: Path,
    context: str,
    existing: SecretRecord | None,
    expected_data: dict[str, str],
    dry_run: bool,
) -> tuple[list[str], dict[str, Any]]:
    suffix = ["--dry-run=server"] if dry_run else []
    if existing is None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "namespace": NAMESPACE,
                "name": SECRET_NAME,
                "labels": {SECRET_OWNER_LABEL: NAMESPACE_OWNER},
            },
            "type": "kubernetes.io/dockerconfigjson",
            "data": expected_data,
        }
        return (
            _kubectl(
                kubeconfig,
                context,
                "--namespace",
                NAMESPACE,
                "create",
                "--filename=-",
                "--output=json",
                *suffix,
            ),
            manifest,
        )
    return (
        _kubectl(
            kubeconfig,
            context,
            "--namespace",
            NAMESPACE,
            "patch",
            "secret",
            SECRET_NAME,
            "--type=json",
            "--patch-file=-",
            "--output=json",
            *suffix,
        ),
        _secret_patch(existing, expected_data=expected_data),
    )


def _namespace_exact(record: NAMESPACE_CONTRACT.NamespaceRecord) -> bool:
    return NAMESPACE_CONTRACT.profile_matches(NAMESPACE, record.labels)


def _secret_exact(record: SecretRecord, expected_data: dict[str, str]) -> bool:
    return (
        record.secret_type == "kubernetes.io/dockerconfigjson"
        and record.data == expected_data
    )


def _guard_namespace_before_secret_mutation(
    *,
    kubeconfig: Path,
    context: str,
    environment: dict[str, str],
    expected: NAMESPACE_CONTRACT.NamespaceRecord,
    runner: CommandRunner,
) -> None:
    document = _query_namespace(
        kubeconfig=kubeconfig,
        context=context,
        environment=environment,
        runner=runner,
    )
    if document is None:
        raise ValueError("backend attestor Namespace changed before Secret mutation")
    current = _namespace_record(document)
    if (
        current.uid != expected.uid
        or current.resource_version != expected.resource_version
        or not _namespace_exact(current)
    ):
        raise ValueError("backend attestor Namespace changed before Secret mutation")


def _binding(
    namespace: NAMESPACE_CONTRACT.NamespaceRecord, secret: SecretRecord
) -> dict[str, Any]:
    return {
        "schemaVersion": EXECUTION_RESOURCES_SCHEMA,
        "namespace": {
            "name": NAMESPACE,
            "uid": namespace.uid,
            "owner": NAMESPACE_OWNER,
            "phase": namespace.phase,
            "podSecurityLabels": dict(PSA_LABELS),
        },
        "imagePullSecret": {
            "namespace": NAMESPACE,
            "name": SECRET_NAME,
            "uid": secret.uid,
            "owner": NAMESPACE_OWNER,
            "dataKeys": sorted(secret.data),
            "dataSha256": hashlib.sha256(_canonical(secret.data)).hexdigest(),
        },
    }


def _required_result(*, missing: list[str], changed: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": PREPARATION_RESULT_SCHEMA,
        "mode": "validate",
        "ready": False,
        "durablePrerequisiteRetained": False,
        "missingResources": missing,
        "changedResources": changed,
    }


@contextmanager
def _installation_lock(private_root: Path, *, mode: str) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        descriptor = os.open(
            private_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(private_root)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()
            or not stat.S_ISDIR(path_metadata.st_mode)
            or stat.S_IMODE(path_metadata.st_mode) != 0o700
            or path_metadata.st_uid != os.geteuid()
            or metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise BackendAttestorPreparationError(
                stage="installation-lock",
                mode=mode,
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise BackendAttestorPreparationError(
                    stage="installation-lock-contention",
                    mode=mode,
                ) from exc
            raise BackendAttestorPreparationError(
                stage="installation-lock",
                mode=mode,
            ) from exc
        locked = True
        yield
    except BackendAttestorPreparationError:
        raise
    except OSError as exc:
        raise BackendAttestorPreparationError(
            stage="installation-lock",
            mode=mode,
        ) from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _prepare_with_snapshots(
    *,
    kubeconfig: Path,
    harbor_dockerconfig: Path,
    execution_profile: Path,
    context: str,
    registry: str,
    apply: bool,
    private_root: Path,
    phase_directory: Path,
    runner: CommandRunner,
) -> dict[str, Any]:
    snapshots = phase_directory / "snapshots"
    try:
        flattened_kubeconfig = PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=kubeconfig,
            raw_destination=snapshots / "kubeconfig.raw",
            flattened_destination=snapshots / "kubeconfig",
            context=context,
            private_root=private_root,
            runner=runner,
        )
        dockerconfig_snapshot = PRIVATE_INPUT.snapshot_private_file(
            source=harbor_dockerconfig,
            destination=snapshots / "harbor-dockerconfig.json",
            description="Harbor dockerconfig",
            private_root=private_root,
        )
        dockerconfig = _dockerconfig_bytes(
            PRIVATE_INPUT.read_private_bytes(
                dockerconfig_snapshot,
                "Harbor dockerconfig snapshot",
                private_root=private_root,
            ),
            registry,
        )
        profile_snapshot = PRIVATE_INPUT.snapshot_private_file(
            source=execution_profile,
            destination=snapshots / "backend-execution-profile.json",
            description="backend execution profile input",
            private_root=private_root,
        )
        profile_binding = BACKEND_ATTESTOR.inspect_execution_profile(
            profile_snapshot,
            private_root=private_root,
        )
        profile_raw = PRIVATE_INPUT.read_private_bytes(
            profile_snapshot,
            "backend execution profile input snapshot",
            private_root=private_root,
        )
        fixed_profile = INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE
        expected_fixed_profile = (
            private_root / "backend-attestor/execution-profile.json"
        )
        if fixed_profile != expected_fixed_profile:
            raise ValueError("backend execution profile destination is not canonical")
        profile_missing = not fixed_profile.exists() and not fixed_profile.is_symlink()
        if not profile_missing:
            fixed_binding = BACKEND_ATTESTOR.inspect_execution_profile(
                fixed_profile,
                private_root=private_root,
            )
            fixed_raw = PRIVATE_INPUT.read_private_bytes(
                fixed_profile,
                "installed backend execution profile",
                private_root=private_root,
            )
            if fixed_binding != profile_binding or fixed_raw != profile_raw:
                raise ValueError("installed backend execution profile changed")
    except (PRIVATE_INPUT.PrivateInputError, ValueError, _CommandError) as exc:
        raise BackendAttestorPreparationError(
            stage="private-input",
            mode="apply" if apply else "validate",
        ) from exc
    environment = {"KUBECONFIG": str(flattened_kubeconfig)}
    namespace_created = False
    try:
        current_context = runner(
            _kubectl(flattened_kubeconfig, context, "config", "current-context"),
            environment=environment,
        ).strip()
        if current_context != context:
            raise ValueError("Kubernetes context does not match")

        namespace_document = _query_namespace(
            kubeconfig=flattened_kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        namespace_record = (
            _namespace_record(namespace_document)
            if namespace_document is not None
            else None
        )
        namespace_changed = namespace_record is None or not _namespace_exact(
            namespace_record
        )

        secret_document = None
        secret_record = None
        if namespace_record is not None:
            secret_document = _query_secret(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                runner=runner,
            )
            secret_record = (
                _secret_record(secret_document)
                if secret_document is not None
                else None
            )
        expected_data = _secret_data(dockerconfig)
        secret_changed = secret_record is None or not _secret_exact(
            secret_record,
            expected_data,
        )

        if namespace_changed:
            command, manifest = _namespace_operation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                existing=namespace_record,
                dry_run=True,
            )
            _execute(
                runner=runner,
                command=command,
                environment=environment,
                manifest=manifest,
            )
        if (
            namespace_record is not None
            and not namespace_changed
            and secret_changed
        ):
            _guard_namespace_before_secret_mutation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                expected=namespace_record,
                runner=runner,
            )
            command, manifest = _secret_operation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                existing=secret_record,
                expected_data=expected_data,
                dry_run=True,
            )
            _execute(
                runner=runner,
                command=command,
                environment=environment,
                manifest=manifest,
            )

        if not apply and (profile_missing or namespace_changed or secret_changed):
            missing = []
            changed = []
            if profile_missing:
                missing.append("executionProfile")
            if namespace_record is None:
                missing.append("namespace")
                missing.append("imagePullSecret")
            elif namespace_changed:
                changed.append("namespace")
            if namespace_record is not None:
                if secret_record is None:
                    missing.append("imagePullSecret")
                elif secret_changed:
                    changed.append("imagePullSecret")
            return _required_result(missing=missing, changed=changed)

        if profile_missing:
            PRIVATE_INPUT.write_private_snapshot(
                destination=fixed_profile,
                content=profile_raw,
                description="installed backend execution profile",
                private_root=private_root,
                allow_existing_exact=True,
            )
            installed_binding = BACKEND_ATTESTOR.inspect_execution_profile(
                fixed_profile,
                private_root=private_root,
            )
            if installed_binding != profile_binding:
                raise ValueError("installed backend execution profile changed")

        if namespace_changed:
            command, manifest = _namespace_operation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                existing=namespace_record,
                dry_run=False,
            )
            mutation = _parse_document(
                _execute(
                    runner=runner,
                    command=command,
                    environment=environment,
                    manifest=manifest,
                ),
                kind="Namespace",
                name=NAMESPACE,
            )
            if mutation is None:
                raise ValueError("Namespace mutation result is missing")
            mutation_record = _namespace_record(mutation)
            if namespace_record is not None and mutation_record.uid != namespace_record.uid:
                raise ValueError("Namespace UID changed during mutation")
            namespace_created = namespace_record is None
            verified = _query_namespace(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                runner=runner,
            )
            if verified is None:
                raise ValueError("Namespace verification result is missing")
            namespace_record = _namespace_record(verified)
            if (
                namespace_record.uid != mutation_record.uid
                or not _namespace_exact(namespace_record)
            ):
                raise ValueError("Namespace identity changed after mutation")

        if namespace_record is None:
            raise ValueError("Namespace is unavailable")

        if secret_document is None and namespace_created:
            secret_document = _query_secret(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                runner=runner,
            )
            secret_record = (
                _secret_record(secret_document)
                if secret_document is not None
                else None
            )
            secret_changed = secret_record is None or not _secret_exact(
                secret_record,
                expected_data,
            )
        if namespace_changed and secret_changed:
            _guard_namespace_before_secret_mutation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                expected=namespace_record,
                runner=runner,
            )
            command, manifest = _secret_operation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                existing=secret_record,
                expected_data=expected_data,
                dry_run=True,
            )
            _execute(
                runner=runner,
                command=command,
                environment=environment,
                manifest=manifest,
            )

        if secret_changed:
            _guard_namespace_before_secret_mutation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                expected=namespace_record,
                runner=runner,
            )
            command, manifest = _secret_operation(
                kubeconfig=flattened_kubeconfig,
                context=context,
                existing=secret_record,
                expected_data=expected_data,
                dry_run=False,
            )
            mutation = _parse_document(
                _execute(
                    runner=runner,
                    command=command,
                    environment=environment,
                    manifest=manifest,
                ),
                kind="Secret",
                name=SECRET_NAME,
            )
            if mutation is None:
                raise ValueError("Secret mutation result is missing")
            mutation_record = _secret_record(mutation)
            if secret_record is not None and mutation_record.uid != secret_record.uid:
                raise ValueError("Secret UID changed during mutation")
            verified_secret = _query_secret(
                kubeconfig=flattened_kubeconfig,
                context=context,
                environment=environment,
                runner=runner,
            )
            if verified_secret is None:
                raise ValueError("Secret verification result is missing")
            secret_record = _secret_record(verified_secret)
            if (
                secret_record.uid != mutation_record.uid
                or not _secret_exact(secret_record, expected_data)
            ):
                raise ValueError("Secret identity changed after mutation")

        if secret_record is None:
            raise ValueError("Secret is unavailable")
        expected_namespace_uid = namespace_record.uid
        expected_secret_uid = secret_record.uid
        final_namespace_document = _query_namespace(
            kubeconfig=flattened_kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        final_secret_document = _query_secret(
            kubeconfig=flattened_kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        if final_namespace_document is None or final_secret_document is None:
            raise ValueError("final execution resources are unavailable")
        namespace_record = _namespace_record(final_namespace_document)
        secret_record = _secret_record(final_secret_document)
        if (
            namespace_record.uid != expected_namespace_uid
            or not _namespace_exact(namespace_record)
            or secret_record.uid != expected_secret_uid
            or not _secret_exact(secret_record, expected_data)
        ):
            raise ValueError("final execution resource identity changed")
        return _binding(namespace_record, secret_record)
    except BackendAttestorPreparationError:
        raise
    except Exception as exc:
        raise BackendAttestorPreparationError(
            stage="resource-reconciliation",
            mode="apply" if apply else "validate",
            namespace_created=namespace_created,
        ) from exc


def validate_backend_attestor_resources(
    *,
    kubeconfig: Path,
    harbor_dockerconfig: Path,
    context: str,
    registry: str,
    private_root: Path,
    runner: CommandRunner = _run_command,
) -> dict[str, Any]:
    """Validate the retained resources without snapshots or cluster mutation."""

    try:
        context = _validate_context(context)
        registry = _validate_registry(registry)
        root = PRIVATE_INPUT.private_root_path(private_root)
        kubeconfig_raw = PRIVATE_INPUT.read_private_bytes(
            kubeconfig,
            "flattened kubeconfig snapshot",
            private_root=root,
        )
        PRIVATE_INPUT.validate_self_contained_kubeconfig(
            kubeconfig_raw,
            expected_context=context,
            description="flattened kubeconfig snapshot",
            require_minified=True,
        )
        dockerconfig = _dockerconfig_bytes(
            PRIVATE_INPUT.read_private_bytes(
                harbor_dockerconfig,
                "Harbor dockerconfig snapshot",
                private_root=root,
            ),
            registry,
        )
        environment = {"KUBECONFIG": str(kubeconfig)}
        current_context = runner(
            _kubectl(kubeconfig, context, "config", "current-context"),
            environment=environment,
        ).strip()
        if current_context != context:
            raise ValueError("Kubernetes context does not match")
        namespace_document = _query_namespace(
            kubeconfig=kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        secret_document = _query_secret(
            kubeconfig=kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        if namespace_document is None or secret_document is None:
            raise ValueError("retained backend attestor resources are missing")
        namespace = _namespace_record(namespace_document)
        secret = _secret_record(secret_document)
        if not _namespace_exact(namespace) or not _secret_exact(
            secret,
            _secret_data(dockerconfig),
        ):
            raise ValueError("retained backend attestor resources changed")
        expected = _binding(namespace, secret)

        final_namespace_document = _query_namespace(
            kubeconfig=kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        final_secret_document = _query_secret(
            kubeconfig=kubeconfig,
            context=context,
            environment=environment,
            runner=runner,
        )
        if final_namespace_document is None or final_secret_document is None:
            raise ValueError("retained backend attestor resources changed")
        final_namespace = _namespace_record(final_namespace_document)
        final_secret = _secret_record(final_secret_document)
        if (
            not _namespace_exact(final_namespace)
            or not _secret_exact(final_secret, _secret_data(dockerconfig))
            or _binding(final_namespace, final_secret) != expected
        ):
            raise ValueError("retained backend attestor resources changed")
        return expected
    except BackendAttestorResourceValidationError:
        raise
    except (PRIVATE_INPUT.PrivateInputError, ValueError, _CommandError) as exc:
        raise BackendAttestorResourceValidationError(
            "retained backend attestor prerequisite is invalid"
        ) from exc


def prepare_backend_attestor(
    *,
    kubeconfig: Path,
    harbor_dockerconfig: Path,
    execution_profile: Path,
    context: str,
    registry: str,
    apply: bool = False,
    runner: CommandRunner = _run_command,
) -> dict[str, Any]:
    """Validate or explicitly reconcile the pre-reset backend-attestor resources."""

    context = _validate_context(context)
    registry = _validate_registry(registry)
    private_root = PRIVATE_INPUT.private_root_path(INSTALLATION_STATE.PRIVATE_ROOT)
    mode = "apply" if apply else "validate"
    with _installation_lock(private_root, mode=mode):
        with TemporaryDirectory(
            prefix=".prepare-backend-attestor-",
            dir=private_root,
        ) as temporary:
            phase_directory = Path(temporary)
            phase_directory.chmod(0o700)
            return _prepare_with_snapshots(
                kubeconfig=kubeconfig,
                harbor_dockerconfig=harbor_dockerconfig,
                execution_profile=execution_profile,
                context=context,
                registry=registry,
                apply=apply,
                private_root=private_root,
                phase_directory=phase_directory,
                runner=runner,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare retained backend-attestor pre-reset resources."
    )
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--harbor-dockerconfig", type=Path, required=True)
    parser.add_argument("--execution-profile", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    try:
        result = prepare_backend_attestor(
            kubeconfig=arguments.kubeconfig,
            harbor_dockerconfig=arguments.harbor_dockerconfig,
            execution_profile=arguments.execution_profile,
            context=arguments.context,
            registry=arguments.registry,
            apply=arguments.apply,
        )
    except BackendAttestorPreparationError as exc:
        print(json.dumps(exc.result, separators=(",", ":"), sort_keys=True))
        return 1
    except (PRIVATE_INPUT.PrivateInputError, ValueError):
        result = BackendAttestorPreparationError(
            stage="input-validation",
            mode="apply" if arguments.apply else "validate",
        ).result
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    if result.get("schemaVersion") == PREPARATION_RESULT_SCHEMA:
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
