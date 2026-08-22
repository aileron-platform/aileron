#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NamedTuple


NAMESPACE_RESULT_SCHEMA = "aileron-installation-namespace-result/v2"
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
CORE_NAMESPACE_NAMES = (
    "workspace-system",
    "aileron-turn-system",
    "aileron-backend-attestor-system",
)
IDENTITY_NAMESPACE_NAME = "aileron-identity-system"


def _load_local_module(name: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        f"aileron_ensure_namespaces_{name}",
        SCRIPT_DIRECTORY / f"{name}.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"namespace installation {name} contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_local_module("private_input")
INSTALLATION_STATE = _load_local_module("installation_state")
NAMESPACE_CONTRACT = _load_local_module("namespace_contract")


class NamespaceOperation(NamedTuple):
    command: list[str]
    manifest: str | None = None


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _subprocess_runner(command: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=stdin,
        check=True,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
    )
    return result.stdout


def _target_namespaces(identity_mode: str) -> tuple[str, ...]:
    if identity_mode == "bundledKeycloak":
        return (*CORE_NAMESPACE_NAMES, IDENTITY_NAMESPACE_NAME)
    if identity_mode == "externalOidc":
        return CORE_NAMESPACE_NAMES
    raise ValueError("identity mode must be bundledKeycloak or externalOidc")


def _namespace_manifest(namespace: str) -> str:
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": NAMESPACE_CONTRACT.profile_labels(namespace),
            },
        },
        sort_keys=True,
    )


def _namespace_label_patch(
    record: NAMESPACE_CONTRACT.NamespaceRecord,
    *,
    namespace: str,
) -> str:
    return json.dumps(
        [
            {
                "op": "test",
                "path": "/metadata/uid",
                "value": record.uid,
            },
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": record.resource_version,
            },
            {
                "op": "replace",
                "path": "/metadata/labels",
                "value": NAMESPACE_CONTRACT.labels_with_exact_profile(
                    namespace, record.labels
                ),
            },
        ],
        sort_keys=True,
    )


def build_namespace_installation_plan(
    namespace_document: dict[str, Any],
    *,
    kubeconfig: Path,
    expected_context: str,
    identity_mode: str,
    validate_only: bool = False,
    existing_only: bool = False,
) -> list[NamespaceOperation]:
    if not kubeconfig.is_absolute():
        raise ValueError("an absolute Kubernetes kubeconfig is required")
    if not expected_context or expected_context != expected_context.strip():
        raise ValueError("an exact Kubernetes context is required")
    if validate_only and existing_only:
        raise ValueError("validate-only and existing-only are mutually exclusive")
    inventory = NAMESPACE_CONTRACT.namespace_inventory(namespace_document)
    target_namespaces = _target_namespaces(identity_mode)
    if identity_mode == "externalOidc" and "aileron-identity-system" in inventory:
        raise ValueError("aileron-identity-system must be absent in externalOidc mode")

    validation_operations: list[NamespaceOperation] = []
    mutation_operations: list[NamespaceOperation] = []
    for namespace in target_namespaces:
        existing = inventory.get(namespace)
        if existing is not None:
            NAMESPACE_CONTRACT.validate_namespace_record(
                namespace, existing, require_profile=False
            )
            profile_matches = NAMESPACE_CONTRACT.profile_matches(
                namespace, existing.labels
            )
            if validate_only and not profile_matches:
                raise ValueError(f"namespace profile mismatch: {namespace}")
            if not validate_only and not profile_matches:
                patch = _namespace_label_patch(
                    existing,
                    namespace=namespace,
                )
                patch_arguments = [
                    "patch",
                    "namespace",
                    namespace,
                    "--type=json",
                    "--patch-file=-",
                ]
                validation_operations.append(
                    NamespaceOperation(
                        _kubectl(
                            kubeconfig,
                            expected_context,
                            *patch_arguments,
                            "--dry-run=server",
                            "--output=name",
                        ),
                        patch,
                    )
                )
                mutation_operations.append(
                    NamespaceOperation(
                        _kubectl(
                            kubeconfig,
                            expected_context,
                            *patch_arguments,
                            "--output=json",
                        ),
                        patch,
                    )
                )
        else:
            if existing_only:
                continue
            manifest = _namespace_manifest(namespace)
            validation_operations.append(
                NamespaceOperation(
                    command=_kubectl(
                        kubeconfig,
                        expected_context,
                        "create",
                        "--dry-run=server",
                        "--output=name",
                        "--filename=-",
                    ),
                    manifest=manifest,
                )
            )
            if not validate_only:
                mutation_operations.append(
                    NamespaceOperation(
                        command=_kubectl(
                            kubeconfig,
                            expected_context,
                            "create",
                            "--output=json",
                            "--filename=-",
                        ),
                        manifest=manifest,
                    )
                )
    return validation_operations + mutation_operations


def _require_unchanged_pre_mutation_inventory(
    *,
    initial_inventory: dict[str, NAMESPACE_CONTRACT.NamespaceRecord],
    current_inventory: dict[str, NAMESPACE_CONTRACT.NamespaceRecord],
    identity_mode: str,
) -> None:
    if (
        identity_mode == "externalOidc"
        and "aileron-identity-system" in current_inventory
    ):
        raise ValueError("namespace inventory changed before mutation")
    for namespace in _target_namespaces(identity_mode):
        if current_inventory.get(namespace) != initial_inventory.get(namespace):
            raise ValueError("namespace inventory changed before mutation")


def _namespace_result(
    *,
    identity_mode: str,
    validate_only: bool,
    initial_inventory: dict[str, NAMESPACE_CONTRACT.NamespaceRecord],
    verified_inventory: dict[str, NAMESPACE_CONTRACT.NamespaceRecord] | None = None,
) -> dict[str, Any]:
    targets = list(_target_namespaces(identity_mode))
    initially_missing = [
        namespace for namespace in targets if namespace not in initial_inventory
    ]
    changed: list[str] = []
    if not validate_only:
        for namespace in _target_namespaces(identity_mode):
            existing = initial_inventory.get(namespace)
            if existing is None or not NAMESPACE_CONTRACT.profile_matches(
                namespace, existing.labels
            ):
                changed.append(namespace)
    result_inventory = (
        initial_inventory if validate_only else verified_inventory
    )
    if result_inventory is None:
        raise ValueError("verified namespace inventory is required")
    return {
        "schemaVersion": NAMESPACE_RESULT_SCHEMA,
        "mode": "validate" if validate_only else "prepare",
        "ready": not validate_only or not initially_missing,
        "targetNamespaces": targets,
        "targetNamespaceIdentities": [
            {"name": namespace, "uid": result_inventory[namespace].uid}
            for namespace in targets
            if namespace in result_inventory
        ],
        "initiallyMissingNamespaces": initially_missing,
        "changedNamespaces": changed,
    }


def _ensure_installation_namespaces_with_snapshot(
    *,
    kubeconfig: Path,
    expected_context: str,
    identity_mode: str,
    validate_only: bool = False,
    existing_only: bool = False,
    runner: Callable[[list[str], str | None], str] = _subprocess_runner,
) -> dict[str, Any]:
    if not kubeconfig.is_absolute():
        raise ValueError("an absolute Kubernetes kubeconfig is required")
    current_context = runner(
        _kubectl(kubeconfig, expected_context, "config", "current-context"), None
    ).strip()
    if current_context != expected_context:
        raise ValueError(
            "current context does not match namespace installation target: "
            f"expected {expected_context}, got {current_context or '<empty>'}"
        )
    namespace_document = json.loads(
        runner(
            _kubectl(
                kubeconfig, expected_context, "get", "namespaces", "-o", "json"
            ),
            None,
        )
    )
    if not isinstance(namespace_document, dict):
        raise ValueError("Kubernetes namespace inventory must be a JSON object")
    initial_inventory = NAMESPACE_CONTRACT.namespace_inventory(namespace_document)
    initial_namespaces = set(initial_inventory)
    operations = build_namespace_installation_plan(
        namespace_document,
        kubeconfig=kubeconfig,
        expected_context=expected_context,
        identity_mode=identity_mode,
        validate_only=validate_only,
        existing_only=existing_only,
    )
    validation_operations = [
        operation
        for operation in operations
        if "--dry-run=server" in operation.command
    ]
    mutation_operations = [
        operation
        for operation in operations
        if "--dry-run=server" not in operation.command
    ]
    for operation in validation_operations:
        runner(operation.command, operation.manifest)

    if mutation_operations:
        pre_mutation_document = json.loads(
            runner(
                _kubectl(
                    kubeconfig,
                    expected_context,
                    "get",
                    "namespaces",
                    "-o",
                    "json",
                ),
                None,
            )
        )
        if not isinstance(pre_mutation_document, dict):
            raise ValueError("pre-mutation namespace inventory must be a JSON object")
        _require_unchanged_pre_mutation_inventory(
            initial_inventory=initial_inventory,
            current_inventory=NAMESPACE_CONTRACT.namespace_inventory(
                pre_mutation_document
            ),
            identity_mode=identity_mode,
        )

    mutation_uids: dict[str, str] = {}
    for operation in mutation_operations:
        output = runner(operation.command, operation.manifest)
        try:
            mutation_document = json.loads(output)
        except json.JSONDecodeError as exc:
            raise ValueError("namespace mutation result is invalid") from exc
        if not isinstance(mutation_document, dict):
            raise ValueError("namespace mutation result must be a JSON object")
        mutation_inventory = NAMESPACE_CONTRACT.namespace_inventory(
            {"items": [mutation_document]}
        )
        if len(mutation_inventory) != 1:
            raise ValueError("namespace mutation result is inconsistent")
        name, record = next(iter(mutation_inventory.items()))
        expected_name = (
            json.loads(operation.manifest)["metadata"]["name"]
            if operation.command[:6]
            == _kubectl(kubeconfig, expected_context, "create")
            else operation.command[7]
        )
        if name != expected_name:
            raise ValueError("namespace mutation result is inconsistent")
        initial = initial_inventory.get(name)
        if initial is not None and record.uid != initial.uid:
            raise ValueError(f"namespace identity changed during mutation: {name}")
        mutation_uids[name] = record.uid

    if validate_only:
        return _namespace_result(
            identity_mode=identity_mode,
            validate_only=True,
            initial_inventory=initial_inventory,
        )

    verified_document = json.loads(
        runner(
            _kubectl(
                kubeconfig, expected_context, "get", "namespaces", "-o", "json"
            ),
            None,
        )
    )
    if not isinstance(verified_document, dict):
        raise ValueError("verified namespace inventory must be a JSON object")
    verified_inventory = NAMESPACE_CONTRACT.namespace_inventory(verified_document)
    if (
        identity_mode == "externalOidc"
        and "aileron-identity-system" in verified_inventory
    ):
        raise ValueError("aileron-identity-system must be absent in externalOidc mode")
    for namespace in _target_namespaces(identity_mode):
        verified = verified_inventory.get(namespace)
        if existing_only and namespace not in initial_namespaces:
            if verified is not None:
                raise ValueError(
                    f"unexpected target namespace appeared during operation: {namespace}"
                )
            continue
        if verified is None:
            raise ValueError(f"namespace profile verification failed: {namespace}")
        expected_uid = (
            initial_inventory[namespace].uid
            if namespace in initial_inventory
            else mutation_uids.get(namespace)
        )
        if expected_uid is None or verified is None or verified.uid != expected_uid:
            raise ValueError(f"namespace identity verification failed: {namespace}")
        NAMESPACE_CONTRACT.validate_namespace_record(
            namespace,
            verified,
            expected_uid=expected_uid,
        )
    return _namespace_result(
        identity_mode=identity_mode,
        validate_only=False,
        initial_inventory=initial_inventory,
        verified_inventory=verified_inventory,
    )


def ensure_installation_namespaces(
    *,
    kubeconfig: Path,
    expected_context: str,
    identity_mode: str,
    validate_only: bool = False,
    existing_only: bool = False,
    runner: Callable[[list[str], str | None], str] = _subprocess_runner,
) -> dict[str, Any]:
    """Use one immutable, self-contained kubeconfig for the complete operation.

    The installer parent already holds the private-root lock. Standalone calls use a
    unique private snapshot and Kubernetes UID/resourceVersion compare-and-swap guards.
    """

    if not kubeconfig.is_absolute():
        raise ValueError("an absolute Kubernetes kubeconfig is required")
    try:
        private_root = PRIVATE_INPUT.private_root_path(
            INSTALLATION_STATE.PRIVATE_ROOT
        )
        with TemporaryDirectory(
            prefix=".ensure-installation-namespaces-",
            dir=private_root,
        ) as temporary:
            transaction_directory = Path(temporary)
            transaction_directory.chmod(0o700)

            def flatten_runner(
                command: list[str], *, environment: dict[str, str] | None = None
            ) -> str:
                del environment
                return runner(command, None)

            flattened_kubeconfig = (
                PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
                    source=kubeconfig,
                    raw_destination=transaction_directory / "kubeconfig.raw",
                    flattened_destination=transaction_directory
                    / "kubeconfig.flattened.json",
                    context=expected_context,
                    runner=flatten_runner,
                    private_root=private_root,
                )
            )
            return _ensure_installation_namespaces_with_snapshot(
                kubeconfig=flattened_kubeconfig,
                expected_context=expected_context,
                identity_mode=identity_mode,
                validate_only=validate_only,
                existing_only=existing_only,
                runner=runner,
            )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise ValueError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or verify installation-owned Aileron namespaces."
    )
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument(
        "--identity-mode",
        required=True,
        choices=("bundledKeycloak", "externalOidc"),
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--existing-only", action="store_true")
    arguments = parser.parse_args()
    result = ensure_installation_namespaces(
        kubeconfig=arguments.kubeconfig,
        expected_context=arguments.context,
        identity_mode=arguments.identity_mode,
        validate_only=arguments.validate_only,
        existing_only=arguments.existing_only,
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
