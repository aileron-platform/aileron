#!/usr/bin/env python3
"""Protect installer-owned Kubernetes Secret and Core deployment transactions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
PLATFORM_SECRET_REGISTRY = (
    REPOSITORY_ROOT / "contracts/platform-installation/secret-registry.json"
)
IDENTITY_SECRET_APPLY_SCRIPT = (
    REPOSITORY_ROOT / "identity-installation/apply_secrets.sh"
)
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
TRANSACTION_NAME_PATTERN = re.compile(r"^install\.[0-9a-f]{16}$")
DEPLOY_TRANSACTION_NAME_PATTERN = re.compile(r"^deploy\.[A-Za-z0-9]{6}$")
SECRET_TRANSACTION_SCHEMA = "aileron-installation-secret-transaction/v2"
CORE_RESULT_SCHEMA = "aileron-core-deployment-result/v1"
INSTALL_RECOVERY_RESULT_SCHEMA = "aileron-installation-recovery-result/v1"
CRD_TRANSACTION_SCHEMA = "aileron-core-crd-transaction/v1"
SAFE_STAGE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 -]{0,127}$")
WORKSPACE_CRD_NAME = "workspaces.platform.aileron.io"
TRANSACTION_MARKER_ANNOTATION = "platform.aileron.dev/installation-transaction-marker"
TRANSACTION_MARKER_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SERVER_METADATA_FIELDS = {
    "creationTimestamp",
    "deletionGracePeriodSeconds",
    "deletionTimestamp",
    "generation",
    "managedFields",
    "resourceVersion",
    "selfLink",
    "uid",
}
IDENTITY_SECRET_REFERENCES = (
    ("aileron-identity-system", "identity-postgres"),
    ("aileron-identity-system", "aileron-identity-database-ca"),
    ("aileron-identity-system", "keycloak-bootstrap-admin"),
    ("aileron-identity-system", "keycloak-platform-admin"),
    ("aileron-identity-system", "keycloak-break-glass"),
    ("aileron-identity-system", "keycloak-realm-import"),
    ("aileron-identity-system", "harbor-rke-creds"),
    ("aileron-identity-system", "keycloak-apps-tls"),
)


def _load_installation_state() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_transaction_installation_state",
        SCRIPT_DIRECTORY / "installation_state.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-state contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_installation_state()


def _load_private_input() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_transaction_private_input",
        SCRIPT_DIRECTORY / "private_input.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-input contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input()


def _load_namespace_contract() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_transaction_namespace_contract",
        SCRIPT_DIRECTORY / "namespace_contract.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation Namespace contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


NAMESPACE_CONTRACT = _load_namespace_contract()
CommandRunner = Callable[..., str]


class InstallationTransactionError(RuntimeError):
    """Raised when a private installation transaction cannot be trusted."""


def _reject_symlinks(path: Path, description: str) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise InstallationTransactionError(f"{description} is unreadable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise InstallationTransactionError(
                f"{description} must not contain a symbolic link"
            )


def _private_root() -> Path:
    root = INSTALLATION_STATE.PRIVATE_ROOT
    if not root.is_absolute():
        raise InstallationTransactionError(
            "installation private root must use an absolute path"
        )
    _reject_symlinks(root, "installation private root")
    try:
        metadata = os.lstat(root)
    except OSError as exc:
        raise InstallationTransactionError(
            "installation private root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise InstallationTransactionError(
            "installation private root must be an owner-controlled mode-0700 directory"
        )
    return root


def _validate_commit(commit: str) -> None:
    if FULL_SHA_PATTERN.fullmatch(commit) is None:
        raise InstallationTransactionError("installation commit is invalid")


def _canonical_work_directory(commit: str) -> Path:
    _validate_commit(commit)
    return _private_root() / "install" / commit


def _validate_mode_directory(path: Path, description: str) -> None:
    _reject_symlinks(path, description)
    root = _private_root()
    try:
        relative_parent = path.parent.resolve(strict=True).relative_to(
            root.resolve(strict=True)
        )
    except (OSError, ValueError) as exc:
        raise InstallationTransactionError(
            f"{description} parent must be within the installation private root"
        ) from exc
    current = root
    for component in relative_parent.parts:
        current /= component
        try:
            parent_metadata = os.lstat(current)
        except OSError as exc:
            raise InstallationTransactionError(
                f"{description} parent is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(parent_metadata.st_mode)
            or stat.S_IMODE(parent_metadata.st_mode) != 0o700
            or parent_metadata.st_uid != os.geteuid()
        ):
            raise InstallationTransactionError(
                f"{description} parent must be an owner-controlled mode-0700 directory"
            )
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise InstallationTransactionError(f"{description} is unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise InstallationTransactionError(
            f"{description} must be an owner-controlled mode-0700 directory"
        )


def _validate_transaction_directory(path: Path, commit: str) -> Path:
    expected_parent = _canonical_work_directory(commit) / "transactions"
    _validate_mode_directory(expected_parent, "installation transactions directory")
    _validate_mode_directory(path, "installation transaction directory")
    try:
        exact_parent = path.parent.resolve(strict=True) == expected_parent.resolve(
            strict=True
        )
    except OSError as exc:
        raise InstallationTransactionError(
            "installation transaction directory is invalid"
        ) from exc
    if not exact_parent or TRANSACTION_NAME_PATTERN.fullmatch(path.name) is None:
        raise InstallationTransactionError(
            "installation transaction directory is not installer-owned"
        )
    return path


def _validate_deploy_transaction_directory(path: Path) -> Path:
    expected_parent = _private_root() / "transactions"
    _validate_mode_directory(expected_parent, "deployment transactions directory")
    _validate_mode_directory(path, "deployment transaction directory")
    try:
        exact_parent = path.parent.resolve(strict=True) == expected_parent.resolve(
            strict=True
        )
    except OSError as exc:
        raise InstallationTransactionError(
            "deployment transaction directory is invalid"
        ) from exc
    if not exact_parent or DEPLOY_TRANSACTION_NAME_PATTERN.fullmatch(path.name) is None:
        raise InstallationTransactionError(
            "deployment transaction directory is not installer-owned"
        )
    return path


def create_transaction_directory(*, work_directory: Path, commit: str) -> Path:
    expected_work = _canonical_work_directory(commit)
    _validate_mode_directory(work_directory, "installation work directory")
    try:
        exact_work = work_directory.resolve(strict=True) == expected_work.resolve(
            strict=True
        )
    except OSError as exc:
        raise InstallationTransactionError(
            "installation work directory is invalid"
        ) from exc
    if not exact_work:
        raise InstallationTransactionError(
            "installation work directory is not canonical"
        )
    transactions = work_directory / "transactions"
    if transactions.exists() or transactions.is_symlink():
        _validate_mode_directory(transactions, "installation transactions directory")
    else:
        try:
            transactions.mkdir(mode=0o700)
        except OSError as exc:
            raise InstallationTransactionError(
                "installation transactions directory cannot be created"
            ) from exc
    for _ in range(16):
        transaction = transactions / f"install.{secrets.token_hex(8)}"
        try:
            transaction.mkdir(mode=0o700)
        except FileExistsError:
            continue
        except OSError as exc:
            raise InstallationTransactionError(
                "installation transaction directory cannot be created"
            ) from exc
        return _validate_transaction_directory(transaction, commit)
    raise InstallationTransactionError(
        "installation transaction directory cannot be allocated"
    )


def _read_private_file(
    path: Path, description: str, *, maximum_size: int = 32 * 1024 * 1024
) -> bytes:
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=_private_root(),
            require_nonempty=False,
            maximum_size=maximum_size,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationTransactionError(str(exc)) from exc


def _write_new_private_file(path: Path, content: bytes, description: str) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
    except OSError as exc:
        raise InstallationTransactionError(f"{description} cannot be created") from exc
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise InstallationTransactionError(f"{description} cannot be written")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
    except OSError as exc:
        raise InstallationTransactionError(f"{description} cannot be written") from exc
    finally:
        os.close(descriptor)


def _replace_private_file(path: Path, content: bytes, description: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    _write_new_private_file(temporary, content, description)
    try:
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise InstallationTransactionError(f"{description} cannot be replaced") from exc


def _load_platform_secret_references(registry_path: Path) -> list[tuple[str, str]]:
    try:
        if registry_path.resolve(strict=True) != PLATFORM_SECRET_REGISTRY.resolve(
            strict=True
        ):
            raise InstallationTransactionError(
                "platform Secret registry is not canonical"
            )
        document = json.loads(registry_path.read_text(encoding="utf-8"))
    except InstallationTransactionError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "platform Secret registry is unavailable or invalid"
        ) from exc
    if document.get("version") != "platform-secret-installation/v1" or not isinstance(
        document.get("secrets"), list
    ):
        raise InstallationTransactionError("platform Secret registry is invalid")
    references: list[tuple[str, str]] = []
    for item in document["secrets"]:
        if not isinstance(item, dict):
            raise InstallationTransactionError("platform Secret registry is invalid")
        namespace = item.get("namespace")
        name = item.get("name")
        if not isinstance(namespace, str) or not isinstance(name, str):
            raise InstallationTransactionError("platform Secret registry is invalid")
        references.append((namespace, name))
    if len(set(references)) != len(references):
        raise InstallationTransactionError(
            "platform Secret registry contains duplicate targets"
        )
    return references


def _validate_identity_secret_references() -> None:
    try:
        script = IDENTITY_SECRET_APPLY_SCRIPT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallationTransactionError(
            "Identity Secret apply contract is unavailable"
        ) from exc
    actual_names = re.findall(
        r"^[ \t]*apply_secret ([a-z0-9][a-z0-9-]*)(?:[ \t]|$)", script, re.M
    )
    expected_names = [name for _, name in IDENTITY_SECRET_REFERENCES]
    if actual_names != expected_names:
        raise InstallationTransactionError(
            "Identity Secret apply contract does not match the transaction allowlist"
        )


def secret_references(
    *, identity_mode: str, registry_path: Path = PLATFORM_SECRET_REGISTRY
) -> list[tuple[str, str]]:
    if identity_mode == "bundledKeycloak":
        _validate_identity_secret_references()
        references = [
            *IDENTITY_SECRET_REFERENCES,
            *_load_platform_secret_references(registry_path),
        ]
    elif identity_mode == "externalOidc":
        references = _load_platform_secret_references(registry_path)
    else:
        raise InstallationTransactionError("identity mode is invalid")
    if len(set(references)) != len(references):
        raise InstallationTransactionError(
            "installation Secret allowlist contains duplicate targets"
        )
    return references


def _normalize_namespace_bindings(
    *,
    references: list[tuple[str, str]],
    expected_namespace_uids: dict[str, str],
) -> list[dict[str, str]]:
    expected_namespaces = sorted({namespace for namespace, _ in references})
    if set(expected_namespace_uids) != set(expected_namespaces) or any(
        not isinstance(uid, str)
        or not uid
        or uid != uid.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in uid)
        for uid in expected_namespace_uids.values()
    ):
        raise InstallationTransactionError("installation Namespace binding is invalid")
    return [
        {"name": namespace, "uid": expected_namespace_uids[namespace]}
        for namespace in expected_namespaces
    ]


def _validate_namespace(
    *,
    context: str,
    namespace: str,
    expected_uid: str,
    runner: CommandRunner,
) -> Any:
    try:
        raw = runner(
            [
                "kubectl",
                "--context",
                context,
                "get",
                "namespace",
                namespace,
                "--output=json",
            ]
        )
        return NAMESPACE_CONTRACT.validate_namespace_json(
            raw,
            namespace=namespace,
            expected_uid=expected_uid,
        )
    except Exception as exc:
        raise InstallationTransactionError(
            "installation Namespace validation failed"
        ) from exc


def _validate_namespace_bindings(
    *,
    context: str,
    bindings: list[dict[str, str]],
    runner: CommandRunner,
) -> None:
    for binding in bindings:
        _validate_namespace(
            context=context,
            namespace=binding["name"],
            expected_uid=binding["uid"],
            runner=runner,
        )


def _validate_secret_document(
    raw: bytes, *, namespace: str, name: str, description: str
) -> dict[str, Any]:
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(f"{description} is invalid") from exc
    if not isinstance(document, dict):
        raise InstallationTransactionError(f"{description} is invalid")
    metadata = document.get("metadata")
    if (
        document.get("apiVersion") != "v1"
        or document.get("kind") != "Secret"
        or not isinstance(metadata, dict)
        or metadata.get("namespace") != namespace
        or metadata.get("name") != name
    ):
        raise InstallationTransactionError(f"{description} is invalid")
    return document


def _query_secret(
    *,
    context: str,
    namespace: str,
    name: str,
    destination: Path,
    runner: CommandRunner,
) -> dict[str, Any] | None:
    runner(
        [
            "kubectl",
            "--context",
            context,
            "--namespace",
            namespace,
            "get",
            "secret",
            name,
            "--ignore-not-found",
            "--output=json",
        ],
        stdout_path=destination,
    )
    raw = _read_private_file(destination, "Kubernetes Secret query result")
    if not raw.strip():
        destination.unlink()
        return None
    return _validate_secret_document(
        raw,
        namespace=namespace,
        name=name,
        description="Kubernetes Secret query result",
    )


def begin_secret_transaction(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    expected_namespace_uids: dict[str, str],
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> None:
    """Snapshot the exact installer Secret allowlist before any mutation."""

    _validate_transaction_directory(transaction_directory, commit)
    references = secret_references(
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    namespace_bindings = _normalize_namespace_bindings(
        references=references,
        expected_namespace_uids=expected_namespace_uids,
    )
    binding_by_name = {
        binding["name"]: binding["uid"] for binding in namespace_bindings
    }
    secret_directory = transaction_directory / "secrets"
    secret_directory.mkdir(mode=0o700)
    entries: list[dict[str, Any]] = []
    for index, (namespace, name) in enumerate(references):
        _validate_namespace(
            context=context,
            namespace=namespace,
            expected_uid=binding_by_name[namespace],
            runner=runner,
        )
        snapshot = secret_directory / f"{index:03d}.json"
        document = _query_secret(
            context=context,
            namespace=namespace,
            name=name,
            destination=snapshot,
            runner=runner,
        )
        if document is None:
            entries.append({"namespace": namespace, "name": name, "state": "absent"})
            continue
        raw = _read_private_file(snapshot, "Kubernetes Secret snapshot")
        entries.append(
            {
                "namespace": namespace,
                "name": name,
                "state": "existing",
                "snapshot": snapshot.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    _validate_namespace_bindings(
        context=context,
        bindings=namespace_bindings,
        runner=runner,
    )
    inventory = {
        "schemaVersion": SECRET_TRANSACTION_SCHEMA,
        "commit": commit,
        "context": context,
        "identityMode": identity_mode,
        "namespaceBindings": namespace_bindings,
        "secrets": entries,
    }
    _write_new_private_file(
        transaction_directory / "secret-inventory.json",
        (json.dumps(inventory, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        "Secret transaction inventory",
    )


def _load_inventory(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    registry_path: Path,
) -> dict[str, Any]:
    _validate_transaction_directory(transaction_directory, commit)
    raw = _read_private_file(
        transaction_directory / "secret-inventory.json",
        "Secret transaction inventory",
    )
    try:
        inventory = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "Secret transaction inventory is invalid"
        ) from exc
    expected_references = secret_references(
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    expected_header = {
        "schemaVersion": SECRET_TRANSACTION_SCHEMA,
        "commit": commit,
        "context": context,
        "identityMode": identity_mode,
    }
    if (
        not isinstance(inventory, dict)
        or set(inventory)
        != {
            *expected_header,
            "namespaceBindings",
            "secrets",
        }
        or any(inventory.get(key) != value for key, value in expected_header.items())
    ):
        raise InstallationTransactionError("Secret transaction inventory is invalid")
    entries = inventory.get("secrets")
    bindings = inventory.get("namespaceBindings")
    expected_namespaces = sorted({namespace for namespace, _ in expected_references})
    if (
        not isinstance(bindings, list)
        or len(bindings) != len(expected_namespaces)
        or [binding.get("name") for binding in bindings if isinstance(binding, dict)]
        != expected_namespaces
        or any(
            not isinstance(binding, dict)
            or set(binding) != {"name", "uid"}
            or not isinstance(binding.get("uid"), str)
            or not binding["uid"]
            for binding in bindings
        )
    ):
        raise InstallationTransactionError(
            "Secret transaction Namespace binding is invalid"
        )
    if (
        not isinstance(entries, list)
        or [
            (entry.get("namespace"), entry.get("name"))
            for entry in entries
            if isinstance(entry, dict)
        ]
        != expected_references
        or len(entries) != len(expected_references)
    ):
        raise InstallationTransactionError(
            "Secret transaction allowlist does not match"
        )
    for index, entry in enumerate(entries):
        state = entry.get("state")
        post_state = entry.get("postState")
        pending_mutation = entry.get("pendingMutation")
        if post_state is not None and pending_mutation is not None:
            raise InstallationTransactionError(
                "Secret transaction mutation state is invalid"
            )
        if post_state is not None and (
            not isinstance(post_state, dict)
            or set(post_state) != {"uid", "semanticSha256", "transactionMarker"}
            or not isinstance(post_state.get("uid"), str)
            or not post_state["uid"]
            or post_state["uid"] != post_state["uid"].strip()
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in post_state["uid"]
            )
            or re.fullmatch(r"[0-9a-f]{64}", str(post_state.get("semanticSha256")))
            is None
            or TRANSACTION_MARKER_PATTERN.fullmatch(
                str(post_state.get("transactionMarker"))
            )
            is None
        ):
            raise InstallationTransactionError(
                "Secret transaction post-state is invalid"
            )
        if pending_mutation is not None:
            if (
                not isinstance(pending_mutation, dict)
                or set(pending_mutation)
                != {
                    "expectedSemanticSha256",
                    "preState",
                    "transactionMarker",
                }
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(pending_mutation.get("expectedSemanticSha256")),
                )
                is None
                or TRANSACTION_MARKER_PATTERN.fullmatch(
                    str(pending_mutation.get("transactionMarker"))
                )
                is None
                or not isinstance(pending_mutation.get("preState"), dict)
            ):
                raise InstallationTransactionError(
                    "Secret transaction pending mutation is invalid"
                )
            pending_pre_state = pending_mutation["preState"]
            if state == "absent":
                if pending_pre_state != {"state": "absent"}:
                    raise InstallationTransactionError(
                        "Secret transaction pending mutation is invalid"
                    )
            elif (
                set(pending_pre_state) != {"state", "uid", "resourceVersion"}
                or pending_pre_state.get("state") != "existing"
                or any(
                    not isinstance(pending_pre_state.get(key), str)
                    or not pending_pre_state[key]
                    or pending_pre_state[key] != pending_pre_state[key].strip()
                    or any(
                        ord(character) < 32 or ord(character) == 127
                        for character in pending_pre_state[key]
                    )
                    for key in ("uid", "resourceVersion")
                )
            ):
                raise InstallationTransactionError(
                    "Secret transaction pending mutation is invalid"
                )
        if state == "absent":
            if set(entry) not in (
                {"namespace", "name", "state"},
                {"namespace", "name", "state", "pendingMutation"},
                {"namespace", "name", "state", "postState"},
            ):
                raise InstallationTransactionError(
                    "Secret transaction inventory is invalid"
                )
        elif state == "existing":
            if (
                set(entry)
                not in (
                    {"namespace", "name", "state", "snapshot", "sha256"},
                    {
                        "namespace",
                        "name",
                        "state",
                        "snapshot",
                        "sha256",
                        "pendingMutation",
                    },
                    {
                        "namespace",
                        "name",
                        "state",
                        "snapshot",
                        "sha256",
                        "postState",
                    },
                )
                or entry.get("snapshot") != f"{index:03d}.json"
                or re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256"))) is None
            ):
                raise InstallationTransactionError(
                    "Secret transaction inventory is invalid"
                )
        else:
            raise InstallationTransactionError(
                "Secret transaction inventory is invalid"
            )
    return inventory


def validate_secret_transaction_namespaces(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> None:
    """Revalidate the transaction Namespace UIDs before Secret mutation."""

    inventory = _load_inventory(
        transaction_directory=transaction_directory,
        commit=commit,
        context=context,
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    _validate_namespace_bindings(
        context=context,
        bindings=inventory["namespaceBindings"],
        runner=runner,
    )


def validate_secret_mutation_namespace(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    namespace: str,
    name: str,
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> None:
    """Revalidate the exact Namespace immediately before one Secret mutation."""

    inventory = _load_inventory(
        transaction_directory=transaction_directory,
        commit=commit,
        context=context,
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    matching = [
        entry
        for entry in inventory["secrets"]
        if entry["namespace"] == namespace and entry["name"] == name
    ]
    if len(matching) != 1 or matching[0].get("pendingMutation") is None:
        raise InstallationTransactionError(
            "Secret mutation target has no durable pending intent"
        )
    namespace_uids = {
        binding["name"]: binding["uid"] for binding in inventory["namespaceBindings"]
    }
    _validate_namespace(
        context=context,
        namespace=namespace,
        expected_uid=namespace_uids[namespace],
        runner=runner,
    )


def prepare_secret_mutation(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    namespace: str,
    name: str,
    expected_manifest: bytes,
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> dict[str, str]:
    """Bind one upcoming create or replace to the exact snapshotted pre-state."""

    inventory = _load_inventory(
        transaction_directory=transaction_directory,
        commit=commit,
        context=context,
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    matching = [
        (index, entry)
        for index, entry in enumerate(inventory["secrets"])
        if entry["namespace"] == namespace and entry["name"] == name
    ]
    if len(matching) != 1:
        raise InstallationTransactionError(
            "Secret mutation target is outside the transaction allowlist"
        )
    index, entry = matching[0]
    if entry.get("postState") is not None or entry.get("pendingMutation") is not None:
        raise InstallationTransactionError(
            "Secret mutation target already has a durable mutation state"
        )
    expected = _validate_secret_document(
        expected_manifest,
        namespace=namespace,
        name=name,
        description="expected Secret mutation manifest",
    )
    transaction_marker = secrets.token_hex(32)
    expected_digest = _semantic_secret_sha256(
        _secret_with_transaction_marker(expected, transaction_marker)
    )
    namespace_uids = {
        binding["name"]: binding["uid"] for binding in inventory["namespaceBindings"]
    }
    before = _validate_namespace(
        context=context,
        namespace=namespace,
        expected_uid=namespace_uids[namespace],
        runner=runner,
    )
    live_path = transaction_directory / f"pre-live-{index:03d}.json"
    try:
        current = _query_secret(
            context=context,
            namespace=namespace,
            name=name,
            destination=live_path,
            runner=runner,
        )
        if entry["state"] == "absent":
            if current is not None:
                raise InstallationTransactionError(
                    "absent Secret pre-state changed before mutation"
                )
            result = {"state": "absent"}
        else:
            if current is None:
                raise InstallationTransactionError(
                    "existing Secret pre-state disappeared before mutation"
                )
            snapshot = transaction_directory / "secrets" / entry["snapshot"]
            raw = _read_private_file(snapshot, "Kubernetes Secret snapshot")
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise InstallationTransactionError("Secret snapshot integrity failed")
            original = _validate_secret_document(
                raw,
                namespace=namespace,
                name=name,
                description="Kubernetes Secret snapshot",
            )
            original_uid, original_resource_version = _secret_cas_identity(original)
            current_uid, current_resource_version = _secret_cas_identity(current)
            if (
                current_uid != original_uid
                or current_resource_version != original_resource_version
                or _semantic_secret(current) != _semantic_secret(original)
            ):
                raise InstallationTransactionError(
                    "existing Secret pre-state changed before mutation"
                )
            result = {
                "state": "existing",
                "uid": current_uid,
                "resourceVersion": current_resource_version,
            }
        after = _validate_namespace(
            context=context,
            namespace=namespace,
            expected_uid=namespace_uids[namespace],
            runner=runner,
        )
        if after != before:
            raise InstallationTransactionError(
                "installation Namespace changed during Secret pre-state validation"
            )
        entry["pendingMutation"] = {
            "expectedSemanticSha256": expected_digest,
            "preState": dict(result),
            "transactionMarker": transaction_marker,
        }
        _replace_private_file(
            transaction_directory / "secret-inventory.json",
            (
                json.dumps(inventory, separators=(",", ":"), sort_keys=True) + "\n"
            ).encode("utf-8"),
            "Secret transaction inventory",
        )
        return {**result, "transactionMarker": transaction_marker}
    finally:
        try:
            live_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise InstallationTransactionError(
                "Secret pre-state query result cannot be removed"
            ) from exc


def _semantic_secret(document: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in document["metadata"].items()
        if key not in SERVER_METADATA_FIELDS
    }
    return {
        key: value
        for key, value in {**document, "metadata": metadata}.items()
        if key != "status"
    }


def _secret_with_transaction_marker(
    document: dict[str, Any], marker: str
) -> dict[str, Any]:
    if TRANSACTION_MARKER_PATTERN.fullmatch(marker) is None:
        raise InstallationTransactionError("Secret transaction marker is invalid")
    marked = copy.deepcopy(_semantic_secret(document))
    metadata = marked["metadata"]
    annotations = metadata.get("annotations")
    if annotations is None:
        annotations = {}
    if not isinstance(annotations, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in annotations.items()
    ):
        raise InstallationTransactionError(
            "expected Secret mutation annotations are invalid"
        )
    if TRANSACTION_MARKER_ANNOTATION in annotations:
        raise InstallationTransactionError(
            "expected Secret mutation uses a reserved annotation"
        )
    annotations[TRANSACTION_MARKER_ANNOTATION] = marker
    metadata["annotations"] = annotations
    return marked


def _secret_transaction_marker(document: dict[str, Any]) -> str | None:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return None
    marker = annotations.get(TRANSACTION_MARKER_ANNOTATION)
    return marker if isinstance(marker, str) else None


def render_secret_mutation_manifest(
    *,
    expected_manifest: bytes,
    namespace: str,
    name: str,
    transaction_marker: str,
    uid: str | None = None,
    resource_version: str | None = None,
) -> bytes:
    """Render the exact marker-bound create or compare-and-swap manifest."""

    expected = _validate_secret_document(
        expected_manifest,
        namespace=namespace,
        name=name,
        description="expected Secret mutation manifest",
    )
    marked = _secret_with_transaction_marker(expected, transaction_marker)
    if (uid is None) != (resource_version is None):
        raise InstallationTransactionError("Secret mutation CAS identity is incomplete")
    if uid is not None and resource_version is not None:
        marked["metadata"]["uid"] = uid
        marked["metadata"]["resourceVersion"] = resource_version
    return json.dumps(marked, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _semantic_secret_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            _semantic_secret(document),
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def record_secret_post_state(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    namespace: str,
    name: str,
    expected_manifest: bytes,
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> None:
    """Durably bind one successful Secret apply to its exact live post-state."""

    inventory = _load_inventory(
        transaction_directory=transaction_directory,
        commit=commit,
        context=context,
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    entries = inventory["secrets"]
    matching = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry["namespace"] == namespace and entry["name"] == name
    ]
    if len(matching) != 1:
        raise InstallationTransactionError(
            "Secret post-state target is outside the transaction allowlist"
        )
    index, entry = matching[0]
    namespace_uids = {
        binding["name"]: binding["uid"] for binding in inventory["namespaceBindings"]
    }
    expected = _validate_secret_document(
        expected_manifest,
        namespace=namespace,
        name=name,
        description="expected Secret post-state manifest",
    )
    pending_mutation = entry.get("pendingMutation")
    post_state = entry.get("postState")
    if pending_mutation is None and post_state is None:
        raise InstallationTransactionError(
            "Secret mutation target has no durable mutation intent"
        )
    transaction_marker = (
        pending_mutation["transactionMarker"]
        if pending_mutation is not None
        else post_state["transactionMarker"]
    )
    expected_digest = _semantic_secret_sha256(
        _secret_with_transaction_marker(expected, transaction_marker)
    )
    if pending_mutation is not None and (
        pending_mutation["expectedSemanticSha256"] != expected_digest
    ):
        raise InstallationTransactionError(
            "Secret mutation manifest changed after durable intent"
        )
    if post_state is not None and post_state["semanticSha256"] != expected_digest:
        raise InstallationTransactionError(
            "Secret post-state manifest changed after durable recording"
        )
    before = _validate_namespace(
        context=context,
        namespace=namespace,
        expected_uid=namespace_uids[namespace],
        runner=runner,
    )
    live_path = transaction_directory / f"post-live-{index:03d}.json"
    try:
        current = _query_secret(
            context=context,
            namespace=namespace,
            name=name,
            destination=live_path,
            runner=runner,
        )
        if current is None:
            raise InstallationTransactionError(
                "applied Kubernetes Secret post-state is missing"
            )
        uid, _ = _secret_cas_identity(current)
        if (
            _secret_transaction_marker(current) != transaction_marker
            or _semantic_secret_sha256(current) != expected_digest
        ):
            raise InstallationTransactionError(
                "applied Kubernetes Secret post-state is not exact"
            )
        if pending_mutation is not None:
            pending_pre_state = pending_mutation["preState"]
            if (
                pending_pre_state["state"] == "existing"
                and uid != pending_pre_state["uid"]
            ):
                raise InstallationTransactionError(
                    "applied Kubernetes Secret ownership changed"
                )
        elif uid != post_state["uid"]:
            raise InstallationTransactionError(
                "applied Kubernetes Secret ownership changed"
            )
        after = _validate_namespace(
            context=context,
            namespace=namespace,
            expected_uid=namespace_uids[namespace],
            runner=runner,
        )
        if after != before:
            raise InstallationTransactionError(
                "installation Namespace changed during Secret post-state recording"
            )
    finally:
        try:
            live_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise InstallationTransactionError(
                "Secret post-state query result cannot be removed"
            ) from exc
    recorded_post_state = {
        "uid": uid,
        "semanticSha256": expected_digest,
        "transactionMarker": transaction_marker,
    }
    if post_state is not None and post_state != recorded_post_state:
        raise InstallationTransactionError(
            "Secret transaction post-state is already bound differently"
        )
    if post_state == recorded_post_state:
        return
    entry.pop("pendingMutation")
    entry["postState"] = recorded_post_state
    _replace_private_file(
        transaction_directory / "secret-inventory.json",
        (json.dumps(inventory, separators=(",", ":"), sort_keys=True) + "\n").encode(
            "utf-8"
        ),
        "Secret transaction inventory",
    )


def _secret_cas_identity(document: dict[str, Any]) -> tuple[str, str]:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise InstallationTransactionError(
            "live Kubernetes Secret CAS metadata is invalid"
        )
    uid = metadata.get("uid")
    resource_version = metadata.get("resourceVersion")
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(resource_version, str)
        or not resource_version
    ):
        raise InstallationTransactionError(
            "live Kubernetes Secret CAS metadata is invalid"
        )
    return uid, resource_version


def _run_kubectl(command: list[str], *, stdout_path: Path | None = None) -> None:
    temporary: Path | None = None
    output_handle: Any = subprocess.DEVNULL
    try:
        if stdout_path is not None:
            temporary = stdout_path.with_name(
                f".{stdout_path.name}.{secrets.token_hex(8)}.tmp"
            )
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            output_handle = os.fdopen(descriptor, "wb")
        result = subprocess.run(
            command,
            stdout=output_handle,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as exc:
        raise InstallationTransactionError(
            "Kubernetes CRD transaction command is unavailable"
        ) from exc
    finally:
        if stdout_path is not None and output_handle is not subprocess.DEVNULL:
            output_handle.close()
    if result.returncode != 0:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        raise InstallationTransactionError("Kubernetes CRD transaction command failed")
    if temporary is not None:
        try:
            os.replace(temporary, stdout_path)
            stdout_path.chmod(0o600)
        except OSError as exc:
            raise InstallationTransactionError(
                "Kubernetes CRD transaction output cannot be recorded"
            ) from exc


def _validate_crd_document(raw: bytes, description: str) -> dict[str, Any]:
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(f"{description} is invalid") from exc
    metadata = document.get("metadata") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "apiextensions.k8s.io/v1"
        or document.get("kind") != "CustomResourceDefinition"
        or not isinstance(metadata, dict)
        or metadata.get("name") != WORKSPACE_CRD_NAME
    ):
        raise InstallationTransactionError(f"{description} is invalid")
    return document


def _semantic_cluster_object(document: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in document["metadata"].items()
        if key not in SERVER_METADATA_FIELDS
    }
    return {
        key: value
        for key, value in {**document, "metadata": metadata}.items()
        if key != "status"
    }


def _crd_cas_identity(document: dict[str, Any]) -> tuple[str, str]:
    metadata = document.get("metadata")
    uid = metadata.get("uid") if isinstance(metadata, dict) else None
    resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, dict) else None
    )
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(resource_version, str)
        or not resource_version
    ):
        raise InstallationTransactionError("live Workspace CRD CAS metadata is invalid")
    return uid, resource_version


def prepare_crd_transaction(*, transaction_directory: Path, context: str) -> None:
    """Snapshot the Workspace CRD before the direct deployment mutates it."""

    _validate_deploy_transaction_directory(transaction_directory)
    if not context or context != context.strip():
        raise InstallationTransactionError("Kubernetes context is invalid")
    snapshot = transaction_directory / "workspace-crd-before.json"
    _run_kubectl(
        [
            "kubectl",
            "--context",
            context,
            "get",
            "customresourcedefinition",
            WORKSPACE_CRD_NAME,
            "--ignore-not-found",
            "--output=json",
        ],
        stdout_path=snapshot,
    )
    raw = _read_private_file(snapshot, "Workspace CRD pre-state")
    inventory: dict[str, Any] = {
        "schemaVersion": CRD_TRANSACTION_SCHEMA,
        "context": context,
    }
    if raw.strip():
        _validate_crd_document(raw, "Workspace CRD pre-state")
        inventory.update(
            {
                "state": "existing",
                "snapshot": snapshot.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    else:
        snapshot.unlink()
        inventory["state"] = "absent"
    _write_new_private_file(
        transaction_directory / "workspace-crd-transaction.json",
        (json.dumps(inventory, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        "Workspace CRD transaction inventory",
    )


def _load_crd_transaction(
    *, transaction_directory: Path, context: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _validate_deploy_transaction_directory(transaction_directory)
    raw_inventory = _read_private_file(
        transaction_directory / "workspace-crd-transaction.json",
        "Workspace CRD transaction inventory",
    )
    try:
        inventory = json.loads(raw_inventory)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "Workspace CRD transaction inventory is invalid"
        ) from exc
    if (
        not isinstance(inventory, dict)
        or inventory.get("schemaVersion") != CRD_TRANSACTION_SCHEMA
        or inventory.get("context") != context
    ):
        raise InstallationTransactionError(
            "Workspace CRD transaction inventory is invalid"
        )
    if inventory.get("state") == "absent":
        if set(inventory) != {"schemaVersion", "context", "state"}:
            raise InstallationTransactionError(
                "Workspace CRD transaction inventory is invalid"
            )
        return inventory, None
    if (
        inventory.get("state") != "existing"
        or set(inventory) != {"schemaVersion", "context", "state", "snapshot", "sha256"}
        or inventory.get("snapshot") != "workspace-crd-before.json"
        or re.fullmatch(r"[0-9a-f]{64}", str(inventory.get("sha256"))) is None
    ):
        raise InstallationTransactionError(
            "Workspace CRD transaction inventory is invalid"
        )
    raw_snapshot = _read_private_file(
        transaction_directory / inventory["snapshot"],
        "Workspace CRD pre-state",
    )
    if hashlib.sha256(raw_snapshot).hexdigest() != inventory["sha256"]:
        raise InstallationTransactionError("Workspace CRD pre-state integrity failed")
    return inventory, _validate_crd_document(raw_snapshot, "Workspace CRD pre-state")


def _write_crd_recovery_artifact(
    path: Path, document: dict[str, Any], description: str
) -> None:
    _reject_symlinks(path, description)
    content = (
        json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    if path.exists():
        _replace_private_file(path, content, description)
    else:
        _write_new_private_file(path, content, description)


def restore_crd_transaction(*, transaction_directory: Path, context: str) -> None:
    """Restore the exact pre-deployment Workspace CRD state with CAS."""

    inventory, original = _load_crd_transaction(
        transaction_directory=transaction_directory,
        context=context,
    )
    current_path = transaction_directory / "workspace-crd-current.json"
    _run_kubectl(
        [
            "kubectl",
            "--context",
            context,
            "get",
            "customresourcedefinition",
            WORKSPACE_CRD_NAME,
            "--ignore-not-found",
            "--output=json",
        ],
        stdout_path=current_path,
    )
    raw_current = _read_private_file(current_path, "live Workspace CRD")
    current = (
        _validate_crd_document(raw_current, "live Workspace CRD")
        if raw_current.strip()
        else None
    )
    if inventory["state"] == "absent":
        if current is None:
            return
        uid, resource_version = _crd_cas_identity(current)
        delete_options = {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {
                "uid": uid,
                "resourceVersion": resource_version,
            },
        }
        options_path = transaction_directory / "workspace-crd-delete-options.json"
        _write_crd_recovery_artifact(
            options_path, delete_options, "Workspace CRD DeleteOptions"
        )
        _run_kubectl(
            [
                "kubectl",
                "--context",
                context,
                "delete",
                "--raw",
                (
                    "/apis/apiextensions.k8s.io/v1/"
                    f"customresourcedefinitions/{WORKSPACE_CRD_NAME}"
                ),
                "--filename",
                str(options_path),
            ]
        )
        return
    assert original is not None
    original_uid, _ = _crd_cas_identity(original)
    if current is None:
        raise InstallationTransactionError("existing Workspace CRD ownership changed")
    current_uid, resource_version = _crd_cas_identity(current)
    if current_uid != original_uid:
        raise InstallationTransactionError("existing Workspace CRD ownership changed")
    if _semantic_cluster_object(current) == _semantic_cluster_object(original):
        return
    restore_document = _semantic_cluster_object(original)
    restore_document["metadata"]["resourceVersion"] = resource_version
    restore_path = transaction_directory / "workspace-crd-restore.json"
    _write_crd_recovery_artifact(
        restore_path, restore_document, "Workspace CRD restore manifest"
    )
    _run_kubectl(
        [
            "kubectl",
            "--context",
            context,
            "replace",
            "--filename",
            str(restore_path),
        ]
    )


def restore_secret_transaction(
    *,
    transaction_directory: Path,
    commit: str,
    context: str,
    identity_mode: str,
    runner: CommandRunner,
    registry_path: Path = PLATFORM_SECRET_REGISTRY,
) -> None:
    """Restore only the exact Secret states captured by this transaction."""

    inventory = _load_inventory(
        transaction_directory=transaction_directory,
        commit=commit,
        context=context,
        identity_mode=identity_mode,
        registry_path=registry_path,
    )
    failures = 0
    namespace_uids = {
        binding["name"]: binding["uid"] for binding in inventory["namespaceBindings"]
    }
    secret_directory = transaction_directory / "secrets"
    _validate_mode_directory(secret_directory, "Secret snapshot directory")
    for index, entry in enumerate(inventory["secrets"]):
        namespace = entry["namespace"]
        name = entry["name"]
        live_path = transaction_directory / f"live-{index:03d}.json"
        try:
            _validate_namespace(
                context=context,
                namespace=namespace,
                expected_uid=namespace_uids[namespace],
                runner=runner,
            )
            current = _query_secret(
                context=context,
                namespace=namespace,
                name=name,
                destination=live_path,
                runner=runner,
            )
            if entry.get("state") == "absent":
                if set(entry) not in (
                    {"namespace", "name", "state"},
                    {"namespace", "name", "state", "pendingMutation"},
                    {"namespace", "name", "state", "postState"},
                ):
                    raise InstallationTransactionError(
                        "Secret snapshot state is invalid"
                    )
                if current is not None:
                    post_state = entry.get("postState")
                    pending_mutation = entry.get("pendingMutation")
                    if post_state is None and pending_mutation is None:
                        raise InstallationTransactionError(
                            "new Kubernetes Secret has no trusted transaction mutation state"
                        )
                    current_uid, current_resource_version = _secret_cas_identity(
                        current
                    )
                    expected_digest = (
                        post_state["semanticSha256"]
                        if post_state is not None
                        else pending_mutation["expectedSemanticSha256"]
                    )
                    expected_marker = (
                        post_state["transactionMarker"]
                        if post_state is not None
                        else pending_mutation["transactionMarker"]
                    )
                    if (
                        post_state is not None and current_uid != post_state["uid"]
                    ) or (
                        _secret_transaction_marker(current) != expected_marker
                        or _semantic_secret_sha256(current) != expected_digest
                    ):
                        raise InstallationTransactionError(
                            "new Kubernetes Secret no longer matches its transaction mutation state"
                        )
                    if pending_mutation is not None and pending_mutation[
                        "preState"
                    ] != {"state": "absent"}:
                        raise InstallationTransactionError(
                            "new Kubernetes Secret pending mutation is invalid"
                        )
                    delete_options_path = (
                        transaction_directory / f"delete-{index:03d}.json"
                    )
                    _write_new_private_file(
                        delete_options_path,
                        (
                            json.dumps(
                                {
                                    "apiVersion": "v1",
                                    "kind": "DeleteOptions",
                                    "preconditions": {
                                        "uid": current_uid,
                                        "resourceVersion": current_resource_version,
                                    },
                                },
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                            + "\n"
                        ).encode(),
                        "Secret DeleteOptions",
                    )
                    _validate_namespace(
                        context=context,
                        namespace=namespace,
                        expected_uid=namespace_uids[namespace],
                        runner=runner,
                    )
                    runner(
                        [
                            "kubectl",
                            "--context",
                            context,
                            "--namespace",
                            namespace,
                            "delete",
                            "--raw",
                            (
                                "/api/v1/namespaces/"
                                f"{quote(namespace, safe='')}/secrets/"
                                f"{quote(name, safe='')}"
                            ),
                            "--filename",
                            str(delete_options_path),
                        ]
                    )
                continue
            if entry.get("state") != "existing" or set(entry) not in (
                {"namespace", "name", "state", "snapshot", "sha256"},
                {
                    "namespace",
                    "name",
                    "state",
                    "snapshot",
                    "sha256",
                    "pendingMutation",
                },
                {
                    "namespace",
                    "name",
                    "state",
                    "snapshot",
                    "sha256",
                    "postState",
                },
            ):
                raise InstallationTransactionError("Secret snapshot state is invalid")
            snapshot = secret_directory / entry["snapshot"]
            raw = _read_private_file(snapshot, "Kubernetes Secret snapshot")
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise InstallationTransactionError("Secret snapshot integrity failed")
            original = _validate_secret_document(
                raw,
                namespace=namespace,
                name=name,
                description="Kubernetes Secret snapshot",
            )
            original_uid, _ = _secret_cas_identity(original)
            if current is None:
                raise InstallationTransactionError(
                    "existing Kubernetes Secret ownership changed"
                )
            current_uid, current_resource_version = _secret_cas_identity(current)
            if current_uid != original_uid:
                raise InstallationTransactionError(
                    "existing Kubernetes Secret ownership changed"
                )
            if _semantic_secret(current) == _semantic_secret(original):
                continue
            post_state = entry.get("postState")
            pending_mutation = entry.get("pendingMutation")
            if post_state is None and pending_mutation is None:
                raise InstallationTransactionError(
                    "changed Kubernetes Secret has no trusted transaction mutation state"
                )
            if post_state is not None:
                trusted_uid = post_state["uid"]
                expected_digest = post_state["semanticSha256"]
                expected_marker = post_state["transactionMarker"]
            else:
                pending_pre_state = pending_mutation["preState"]
                if pending_pre_state["state"] != "existing":
                    raise InstallationTransactionError(
                        "changed Kubernetes Secret pending mutation is invalid"
                    )
                trusted_uid = pending_pre_state["uid"]
                expected_digest = pending_mutation["expectedSemanticSha256"]
                expected_marker = pending_mutation["transactionMarker"]
            if (
                current_uid != trusted_uid
                or _secret_transaction_marker(current) != expected_marker
                or _semantic_secret_sha256(current) != expected_digest
            ):
                raise InstallationTransactionError(
                    "changed Kubernetes Secret no longer matches its transaction mutation state"
                )
            restore_path = transaction_directory / f"restore-{index:03d}.json"
            restore_document = _semantic_secret(original)
            restore_document["metadata"]["resourceVersion"] = current_resource_version
            restore_document["metadata"]["uid"] = current_uid
            _write_new_private_file(
                restore_path,
                (
                    json.dumps(
                        restore_document,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode(),
                "Secret restore manifest",
            )
            command = [
                "kubectl",
                "--context",
                context,
                "--namespace",
                namespace,
                "replace",
            ]
            command.extend(["--filename", str(restore_path)])
            _validate_namespace(
                context=context,
                namespace=namespace,
                expected_uid=namespace_uids[namespace],
                runner=runner,
            )
            runner(command)
        except Exception:
            failures += 1
        finally:
            for temporary in (
                live_path,
                transaction_directory / f"restore-{index:03d}.json",
                transaction_directory / f"delete-{index:03d}.json",
            ):
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    failures += 1
    if failures:
        raise InstallationTransactionError(
            "one or more installer-owned Secret states could not be restored"
        )


def _core_result_path(transaction_directory: Path) -> Path:
    return transaction_directory / "core-deploy-result.json"


def prepare_core_result(*, transaction_directory: Path, commit: str) -> Path:
    _validate_transaction_directory(transaction_directory, commit)
    path = _core_result_path(transaction_directory)
    pending = {
        "schemaVersion": CORE_RESULT_SCHEMA,
        "state": "pending",
        "commit": commit,
    }
    _write_new_private_file(
        path,
        (json.dumps(pending, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        "Core deployment result sidecar",
    )
    return path


def validate_pending_core_result(*, path: Path, commit: str) -> None:
    transaction_directory = _validate_transaction_directory(path.parent, commit)
    if path != _core_result_path(transaction_directory):
        raise InstallationTransactionError(
            "Core deployment result path is not canonical"
        )
    raw = _read_private_file(path, "Core deployment result sidecar")
    try:
        pending = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "Core deployment result sidecar is invalid"
        ) from exc
    if pending != {
        "schemaVersion": CORE_RESULT_SCHEMA,
        "state": "pending",
        "commit": commit,
    }:
        raise InstallationTransactionError(
            "Core deployment result sidecar is not pending"
        )


def write_core_result(
    *,
    path: Path,
    commit: str,
    primary_exit_code: int,
    core_rollback_attempted: bool,
    core_rollback_succeeded: bool,
) -> None:
    validate_pending_core_result(path=path, commit=commit)
    if not 0 <= primary_exit_code <= 255:
        raise InstallationTransactionError("Core deployment exit code is invalid")
    if not core_rollback_attempted and core_rollback_succeeded:
        raise InstallationTransactionError(
            "Core rollback result is internally inconsistent"
        )
    completed = {
        "schemaVersion": CORE_RESULT_SCHEMA,
        "state": "completed",
        "commit": commit,
        "primaryExitCode": primary_exit_code,
        "coreRollbackAttempted": core_rollback_attempted,
        "coreRollbackSucceeded": core_rollback_succeeded,
    }
    _replace_private_file(
        path,
        (json.dumps(completed, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        "Core deployment result sidecar",
    )


def read_core_result(*, path: Path, commit: str) -> dict[str, Any]:
    transaction_directory = _validate_transaction_directory(path.parent, commit)
    if path != _core_result_path(transaction_directory):
        raise InstallationTransactionError(
            "Core deployment result path is not canonical"
        )
    raw = _read_private_file(path, "Core deployment result sidecar")
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "Core deployment result sidecar is invalid"
        ) from exc
    expected_keys = {
        "schemaVersion",
        "state",
        "commit",
        "primaryExitCode",
        "coreRollbackAttempted",
        "coreRollbackSucceeded",
    }
    if (
        not isinstance(result, dict)
        or set(result) != expected_keys
        or result.get("schemaVersion") != CORE_RESULT_SCHEMA
        or result.get("state") != "completed"
        or result.get("commit") != commit
        or type(result.get("primaryExitCode")) is not int
        or not 0 <= result["primaryExitCode"] <= 255
        or type(result.get("coreRollbackAttempted")) is not bool
        or type(result.get("coreRollbackSucceeded")) is not bool
        or not result["coreRollbackAttempted"]
        and result["coreRollbackSucceeded"]
    ):
        raise InstallationTransactionError("Core deployment result sidecar is invalid")
    return result


def _validate_recovery_operation(operation: dict[str, Any], description: str) -> None:
    if set(operation) != {"attempted", "succeeded", "skipped"} or any(
        type(operation.get(field)) is not bool
        for field in ("attempted", "succeeded", "skipped")
    ):
        raise InstallationTransactionError(f"{description} is invalid")
    if (
        operation["succeeded"]
        and not operation["attempted"]
        or operation["skipped"]
        and (operation["attempted"] or operation["succeeded"])
    ):
        raise InstallationTransactionError(f"{description} is invalid")


def write_install_recovery_result(
    *,
    transaction_directory: Path,
    commit: str,
    primary_stage: str,
    primary_exit_code: int | None,
    secret_restore: dict[str, Any],
    core_rollback: dict[str, Any],
    identity_recovery: dict[str, Any],
) -> Path:
    """Write one safe combined result for a failed installation transaction."""

    _validate_transaction_directory(transaction_directory, commit)
    if SAFE_STAGE_PATTERN.fullmatch(primary_stage) is None:
        raise InstallationTransactionError(
            "installation recovery primary stage is invalid"
        )
    if primary_exit_code is not None and (
        type(primary_exit_code) is not int or not 1 <= primary_exit_code <= 255
    ):
        raise InstallationTransactionError(
            "installation recovery primary exit code is invalid"
        )
    for operation, description in (
        (secret_restore, "Secret restore result"),
        (core_rollback, "Core rollback result"),
        (identity_recovery, "Identity recovery result"),
    ):
        _validate_recovery_operation(operation, description)
    result = {
        "schemaVersion": INSTALL_RECOVERY_RESULT_SCHEMA,
        "state": "failed",
        "commit": commit,
        "primaryFailure": {
            "stage": primary_stage,
            "exitCode": primary_exit_code,
        },
        "secretRestore": secret_restore,
        "coreRollback": core_rollback,
        "identityRecovery": identity_recovery,
    }
    path = transaction_directory / "install-recovery-result.json"
    _write_new_private_file(
        path,
        (json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n").encode(),
        "installation recovery result",
    )
    return path


def read_install_recovery_result(
    *, transaction_directory: Path, commit: str
) -> dict[str, Any]:
    _validate_transaction_directory(transaction_directory, commit)
    raw = _read_private_file(
        transaction_directory / "install-recovery-result.json",
        "installation recovery result",
    )
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationTransactionError(
            "installation recovery result is invalid"
        ) from exc
    if (
        not isinstance(result, dict)
        or set(result)
        != {
            "schemaVersion",
            "state",
            "commit",
            "primaryFailure",
            "secretRestore",
            "coreRollback",
            "identityRecovery",
        }
        or result.get("schemaVersion") != INSTALL_RECOVERY_RESULT_SCHEMA
        or result.get("state") != "failed"
        or result.get("commit") != commit
    ):
        raise InstallationTransactionError("installation recovery result is invalid")
    primary = result.get("primaryFailure")
    if (
        not isinstance(primary, dict)
        or set(primary) != {"stage", "exitCode"}
        or not isinstance(primary.get("stage"), str)
        or SAFE_STAGE_PATTERN.fullmatch(primary["stage"]) is None
        or primary.get("exitCode") is not None
        and (
            type(primary["exitCode"]) is not int or not 1 <= primary["exitCode"] <= 255
        )
    ):
        raise InstallationTransactionError("installation recovery result is invalid")
    for field, description in (
        ("secretRestore", "Secret restore result"),
        ("coreRollback", "Core rollback result"),
        ("identityRecovery", "Identity recovery result"),
    ):
        operation = result.get(field)
        if not isinstance(operation, dict):
            raise InstallationTransactionError(
                "installation recovery result is invalid"
            )
        _validate_recovery_operation(operation, description)
    return result


def discard_transaction(*, transaction_directory: Path, commit: str) -> None:
    _validate_transaction_directory(transaction_directory, commit)
    for entry in transaction_directory.rglob("*"):
        if entry.is_symlink():
            raise InstallationTransactionError(
                "installation transaction contains a symbolic link"
            )
    try:
        shutil.rmtree(transaction_directory)
    except OSError as exc:
        raise InstallationTransactionError(
            "installation transaction cannot be removed"
        ) from exc


def _boolean(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("boolean value must be true or false")


def _pinned_cli_runner(kubeconfig: Path) -> CommandRunner:
    def run(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdout_path: Path | None = None,
    ) -> str:
        del environment
        if command[0] != "kubectl":
            raise InstallationTransactionError("Secret transaction command is invalid")
        pinned = [
            "kubectl",
            "--kubeconfig",
            str(kubeconfig),
            *command[1:],
        ]
        if stdout_path is not None:
            _run_kubectl(pinned, stdout_path=stdout_path)
            return ""
        try:
            result = subprocess.run(
                pinned,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError as exc:
            raise InstallationTransactionError(
                "Secret transaction command is unavailable"
            ) from exc
        if result.returncode != 0:
            raise InstallationTransactionError("Secret transaction command failed")
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InstallationTransactionError(
                "Secret transaction command returned invalid UTF-8"
            ) from exc

    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "validate-core-result",
            "write-core-result",
            "prepare-crd-transaction",
            "restore-crd-transaction",
            "prepare-secret-mutation",
            "record-secret-post-state",
        ),
    )
    parser.add_argument("--path", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--transaction-directory", type=Path)
    parser.add_argument("--context")
    parser.add_argument("--kubeconfig", type=Path)
    parser.add_argument("--identity-mode", choices=("bundledKeycloak", "externalOidc"))
    parser.add_argument("--namespace")
    parser.add_argument("--name")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--primary-exit-code", type=int)
    parser.add_argument("--core-rollback-attempted", type=_boolean)
    parser.add_argument("--core-rollback-succeeded", type=_boolean)
    arguments = parser.parse_args()
    try:
        if arguments.action in {
            "prepare-secret-mutation",
            "record-secret-post-state",
        }:
            if any(
                value is None
                for value in (
                    arguments.transaction_directory,
                    arguments.commit,
                    arguments.context,
                    arguments.kubeconfig,
                    arguments.identity_mode,
                    arguments.namespace,
                    arguments.name,
                    arguments.manifest,
                )
            ) or any(
                value is not None
                for value in (
                    arguments.path,
                    arguments.primary_exit_code,
                    arguments.core_rollback_attempted,
                    arguments.core_rollback_succeeded,
                )
            ):
                parser.error(
                    f"{arguments.action} requires only its exact transaction, cluster, target, and manifest inputs"
                )
            assert arguments.kubeconfig is not None
            if not arguments.kubeconfig.is_absolute():
                parser.error("record-secret-post-state kubeconfig must be absolute")

            pinned_runner = _pinned_cli_runner(arguments.kubeconfig)
            if arguments.action == "prepare-secret-mutation":
                mutation = prepare_secret_mutation(
                    transaction_directory=arguments.transaction_directory,
                    commit=arguments.commit,
                    context=arguments.context,
                    identity_mode=arguments.identity_mode,
                    namespace=arguments.namespace,
                    name=arguments.name,
                    expected_manifest=_read_private_file(
                        arguments.manifest, "expected Secret mutation manifest"
                    ),
                    runner=pinned_runner,
                )
                print(json.dumps(mutation, separators=(",", ":"), sort_keys=True))
            else:
                assert arguments.manifest is not None
                record_secret_post_state(
                    transaction_directory=arguments.transaction_directory,
                    commit=arguments.commit,
                    context=arguments.context,
                    identity_mode=arguments.identity_mode,
                    namespace=arguments.namespace,
                    name=arguments.name,
                    expected_manifest=_read_private_file(
                        arguments.manifest, "expected Secret post-state manifest"
                    ),
                    runner=pinned_runner,
                )
        elif arguments.action in {"prepare-crd-transaction", "restore-crd-transaction"}:
            if (
                arguments.transaction_directory is None
                or arguments.context is None
                or any(
                    value is not None
                    for value in (
                        arguments.path,
                        arguments.commit,
                        arguments.primary_exit_code,
                        arguments.core_rollback_attempted,
                        arguments.core_rollback_succeeded,
                    )
                )
            ):
                parser.error(
                    f"{arguments.action} requires only transaction directory and context"
                )
            if arguments.action == "prepare-crd-transaction":
                prepare_crd_transaction(
                    transaction_directory=arguments.transaction_directory,
                    context=arguments.context,
                )
            else:
                restore_crd_transaction(
                    transaction_directory=arguments.transaction_directory,
                    context=arguments.context,
                )
        elif arguments.action == "validate-core-result":
            if arguments.path is None or arguments.commit is None:
                parser.error("validate-core-result requires path and commit")
            if any(
                value is not None
                for value in (
                    arguments.primary_exit_code,
                    arguments.core_rollback_attempted,
                    arguments.core_rollback_succeeded,
                )
            ):
                parser.error("validate-core-result does not accept result fields")
            validate_pending_core_result(
                path=arguments.path,
                commit=arguments.commit,
            )
        else:
            if arguments.path is None or arguments.commit is None:
                parser.error("write-core-result requires path and commit")
            if any(
                value is None
                for value in (
                    arguments.primary_exit_code,
                    arguments.core_rollback_attempted,
                    arguments.core_rollback_succeeded,
                )
            ):
                parser.error("write-core-result requires every result field")
            write_core_result(
                path=arguments.path,
                commit=arguments.commit,
                primary_exit_code=arguments.primary_exit_code,
                core_rollback_attempted=arguments.core_rollback_attempted,
                core_rollback_succeeded=arguments.core_rollback_succeeded,
            )
    except InstallationTransactionError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
