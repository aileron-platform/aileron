#!/usr/bin/env python3
"""Validate and project platform installation artifacts into Kubernetes Secrets."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Optional
from urllib.parse import urlsplit

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
SECRET_OWNER_LABEL = "platform.aileron.dev/secret-owner"
INSTALLER_OWNER = "aileron-installer"
CANONICAL_REGISTRY = (
    REPOSITORY_ROOT / "contracts/platform-installation/secret-registry.json"
)
DEFAULT_REGISTRY = CANONICAL_REGISTRY
REGISTRY_SHA256 = "4ee261ff21f2184de75808208687e53e17eabd041002368613ba9a844a5f7e5a"
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET_KEY = re.compile(r"^[A-Za-z0-9._-]+$")
ARTIFACT_FORMATS = {
    "agentTokens",
    "browserKeyring",
    "databaseUrl",
    "dockerConfigJson",
    "ed25519Jwks",
    "ed25519PrivatePem",
    "iceServers",
    "nonEmpty",
    "pemCertificate",
    "pemPrivateKey",
    "postgresUsername",
    "redisUrl",
    "urlSafeToken",
    "urlSafeToken64",
}
PLATFORM_NAMESPACES = {"workspace-system", "aileron-turn-system"}
SECRET_TYPES = {"Opaque", "kubernetes.io/dockerconfigjson", "kubernetes.io/tls"}
CONDITIONS = {
    "postgres.enabled=true",
    "postgres.enabled=false",
    "redis.enabled=true",
    "redis.enabled=false",
}


def _condition_matches(condition: str | None, selectors: dict[str, bool]) -> bool:
    if condition is None:
        return True
    if condition not in CONDITIONS:
        raise PlatformSecretApplyError("Secret registry condition is invalid")
    name, raw_value = condition.split("=", 1)
    return selectors[name] is (raw_value == "true")


def _load_module(name: str, filename: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        name,
        SCRIPT_DIRECTORY / filename,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("platform Secret private-input contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_module(
    "aileron_platform_secret_installation_state",
    "installation_state.py",
)
PRIVATE_INPUT = _load_module(
    "aileron_platform_secret_private_input",
    "private_input.py",
)
NAMESPACE_CONTRACT = _load_module(
    "aileron_platform_secret_namespace_contract",
    "namespace_contract.py",
)
INSTALLATION_TRANSACTION = _load_module(
    "aileron_platform_secret_installation_transaction",
    "installation_transaction.py",
)


class PlatformSecretApplyError(RuntimeError):
    """Raised when applying platform Secrets would violate ownership or safety."""


class CommandNotFoundError(RuntimeError):
    """Raised by a command runner when a queried Kubernetes object does not exist."""


Runner = Callable[[list[str], Optional[bytes]], bytes]


def _run_command(command: list[str], stdin: bytes | None = None) -> bytes:
    result = subprocess.run(command, input=stdin, capture_output=True, check=False)
    if result.returncode == 0:
        return result.stdout
    normalized_error = result.stderr.lower()
    if (
        "get" in command
        and "secret" in command
        and result.returncode == 1
        and (b"(notfound)" in normalized_error or b" not found" in normalized_error)
    ):
        raise CommandNotFoundError("Kubernetes Secret does not exist")
    raise PlatformSecretApplyError(
        "kubectl command failed; secret-bearing output was suppressed"
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON object key")
        document[key] = value
    return document


def _validate_registry(document: Any) -> dict[str, Any]:
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "artifacts", "secrets"}
        or document.get("version") != "platform-secret-installation/v1"
        or not isinstance(document.get("artifacts"), list)
        or not isinstance(document.get("secrets"), list)
    ):
        raise PlatformSecretApplyError("Secret registry schema is invalid")
    artifact_ids: set[str] = set()
    generated_paths: set[str] = set()
    for artifact in document["artifacts"]:
        if not isinstance(artifact, dict):
            raise PlatformSecretApplyError("Secret registry schema is invalid")
        source = artifact.get("source")
        expected_keys = {"id", "source", "format"}
        if source == "generated":
            expected_keys.add("path")
        elif source == "external":
            pass
        elif source == "selected":
            expected_keys.update({"path", "selector"})
        else:
            expected_keys = set()
        if "when" in artifact:
            expected_keys.add("when")
        artifact_id = artifact.get("id")
        if (
            set(artifact) != expected_keys
            or not isinstance(artifact_id, str)
            or IDENTIFIER.fullmatch(artifact_id) is None
            or artifact_id in artifact_ids
            or artifact.get("format") not in ARTIFACT_FORMATS
            or artifact.get("when") not in CONDITIONS | {None}
            or (
                source == "selected"
                and artifact.get("selector")
                not in {"postgres.enabled", "redis.enabled"}
            )
        ):
            raise PlatformSecretApplyError("Secret registry schema is invalid")
        artifact_ids.add(artifact_id)
        if source in {"generated", "selected"}:
            path = artifact.get("path")
            parsed = PurePosixPath(path) if isinstance(path, str) else None
            if (
                parsed is None
                or parsed.is_absolute()
                or not parsed.parts
                or any(part in {"", ".", ".."} for part in parsed.parts)
                or str(parsed) != path
                or path in generated_paths
            ):
                raise PlatformSecretApplyError("Secret registry schema is invalid")
            generated_paths.add(path)
    targets: set[tuple[str, str]] = set()
    for secret in document["secrets"]:
        if (
            not isinstance(secret, dict)
            or not set(secret).issubset(
                {"namespace", "name", "type", "data", "when", "dataWhen"}
            )
            or not {"namespace", "name", "type", "data"}.issubset(secret)
        ):
            raise PlatformSecretApplyError("Secret registry schema is invalid")
        namespace = secret.get("namespace")
        name = secret.get("name")
        data = secret.get("data")
        data_when = secret.get("dataWhen", {})
        if not isinstance(namespace, str) or not isinstance(name, str):
            raise PlatformSecretApplyError("Secret registry schema is invalid")
        target = (namespace, name)
        if (
            namespace not in PLATFORM_NAMESPACES
            or IDENTIFIER.fullmatch(name) is None
            or secret.get("type") not in SECRET_TYPES
            or target in targets
            or not isinstance(data, dict)
            or not data
            or secret.get("when") not in CONDITIONS | {None}
            or not isinstance(data_when, dict)
            or not set(data_when).issubset(data)
            or any(condition not in CONDITIONS for condition in data_when.values())
            or any(
                not isinstance(key, str)
                or SECRET_KEY.fullmatch(key) is None
                or not isinstance(artifact_id, str)
                or artifact_id not in artifact_ids
                for key, artifact_id in data.items()
            )
        ):
            raise PlatformSecretApplyError("Secret registry schema is invalid")
        targets.add(target)
    return document


def _load_registry() -> dict[str, Any]:
    try:
        if DEFAULT_REGISTRY.resolve(strict=True) != CANONICAL_REGISTRY.resolve(
            strict=True
        ):
            raise PlatformSecretApplyError("Secret registry path is not canonical")
        raw = DEFAULT_REGISTRY.read_bytes()
        if hashlib.sha256(raw).hexdigest() != REGISTRY_SHA256:
            raise PlatformSecretApplyError("Secret registry digest does not match")
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except PlatformSecretApplyError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PlatformSecretApplyError(
            "Secret registry is unreadable or invalid"
        ) from exc
    return _validate_registry(document)


def _read_private_file(
    path: Path,
    description: str,
    *,
    private_root: Path,
) -> bytes:
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=private_root,
            maximum_size=1024 * 1024,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise PlatformSecretApplyError(f"{description} is invalid") from exc


def _validate_external_format(artifact: dict[str, Any], value: bytes) -> None:
    artifact_id = artifact["id"]
    artifact_format = artifact["format"]
    if artifact_format == "pemCertificate" and (
        b"-----BEGIN CERTIFICATE-----" not in value
        or b"-----END CERTIFICATE-----" not in value
    ):
        raise PlatformSecretApplyError(
            f"External input format is invalid: {artifact_id}"
        )
    if artifact_format == "pemPrivateKey" and b"PRIVATE KEY-----" not in value:
        raise PlatformSecretApplyError(
            f"External input format is invalid: {artifact_id}"
        )
    if artifact_format == "dockerConfigJson":
        try:
            document = json.loads(value)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PlatformSecretApplyError(
                f"External input format is invalid: {artifact_id}"
            ) from exc
        if not isinstance(document, dict) or not isinstance(
            document.get("auths"), dict
        ):
            raise PlatformSecretApplyError(
                f"External input format is invalid: {artifact_id}"
            )
    if artifact_format in {"databaseUrl", "redisUrl"}:
        try:
            parsed = urlsplit(value.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise PlatformSecretApplyError(
                f"External input format is invalid: {artifact_id}"
            ) from exc
        expected_schemes = (
            {"postgresql", "postgresql+psycopg"}
            if artifact_format == "databaseUrl"
            else {"redis", "rediss"}
        )
        if (
            parsed.scheme not in expected_schemes
            or not parsed.hostname
            or not value
            or value.strip() != value
        ):
            raise PlatformSecretApplyError(
                f"External input format is invalid: {artifact_id}"
            )


def _active_artifacts(
    registry: dict[str, Any], selectors: dict[str, bool]
) -> list[dict[str, Any]]:
    active = []
    for artifact in registry["artifacts"]:
        if not _condition_matches(artifact.get("when"), selectors):
            continue
        selected = dict(artifact)
        if selected["source"] == "selected":
            selected["source"] = (
                "generated" if selectors[selected.pop("selector")] else "external"
            )
        active.append(selected)
    return active


def _artifact_values(
    registry: dict[str, Any],
    artifact_directory: Path,
    external_inputs: dict[str, Path],
    *,
    private_root: Path,
    selectors: dict[str, bool],
) -> dict[str, bytes]:
    try:
        PRIVATE_INPUT.validate_private_directory(
            artifact_directory,
            "platform artifact directory",
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise PlatformSecretApplyError(
            "Platform artifact directory is invalid"
        ) from exc
    artifacts = _active_artifacts(registry, selectors)
    external_ids = {
        artifact["id"] for artifact in artifacts if artifact["source"] == "external"
    }
    if set(external_inputs) != external_ids:
        raise PlatformSecretApplyError(
            "The complete exact external input set is required"
        )
    values: dict[str, bytes] = {}
    for artifact in artifacts:
        artifact_id = artifact["id"]
        if artifact["source"] == "generated":
            path = artifact_directory / artifact["path"]
            value = _read_private_file(
                path,
                f"Generated artifact {artifact_id}",
                private_root=private_root,
            )
        else:
            value = _read_private_file(
                external_inputs[artifact_id],
                f"External input {artifact_id}",
                private_root=private_root,
            )
            _validate_external_format(artifact, value)
        values[artifact_id] = value
    return values


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _owner_output(runner: Runner, command: list[str]) -> str:
    try:
        return runner(command, None).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise PlatformSecretApplyError(
            "kubectl returned invalid owner metadata"
        ) from exc


def _validate_ownership(
    registry: dict[str, Any],
    kubeconfig: Path,
    context: str,
    expected_namespace_uids: dict[str, str],
    runner: Runner,
) -> None:
    current_context = (
        runner(
            _kubectl(kubeconfig, context, "config", "current-context"),
            None,
        )
        .decode()
        .strip()
    )
    if current_context != context:
        raise PlatformSecretApplyError(
            "Current Kubernetes context does not match the requested context"
        )
    namespaces = sorted({secret["namespace"] for secret in registry["secrets"]})
    if set(expected_namespace_uids) != set(namespaces) or any(
        not isinstance(uid, str) or not uid or uid != uid.strip()
        for uid in expected_namespace_uids.values()
    ):
        raise PlatformSecretApplyError(
            "The exact Namespace UID binding set is required"
        )
    for namespace in namespaces:
        try:
            raw = runner(
                _kubectl(
                    kubeconfig,
                    context,
                    "get",
                    "namespace",
                    namespace,
                    "--output=json",
                ),
                None,
            )
            NAMESPACE_CONTRACT.validate_namespace_json(
                raw,
                namespace=namespace,
                expected_uid=expected_namespace_uids[namespace],
            )
        except (
            OSError,
            UnicodeDecodeError,
            NAMESPACE_CONTRACT.NamespaceContractError,
        ) as exc:
            raise PlatformSecretApplyError(
                f"Kubernetes namespace identity is invalid: {namespace}"
            ) from exc
    for secret in registry["secrets"]:
        command = _kubectl(
            kubeconfig,
            context,
            "get",
            "secret",
            secret["name"],
            "--namespace",
            secret["namespace"],
            "--output=jsonpath={.metadata.labels.platform\\.aileron\\.dev/secret-owner}",
        )
        try:
            owner = _owner_output(runner, command)
        except CommandNotFoundError:
            continue
        if owner != INSTALLER_OWNER:
            raise PlatformSecretApplyError(
                f"Existing Kubernetes Secret owner is invalid: {secret['namespace']}/{secret['name']}"
            )


def _render_secret(
    secret: dict[str, Any],
    values: dict[str, bytes],
    selectors: dict[str, bool],
) -> bytes:
    data_when = secret.get("dataWhen", {})
    document = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret["name"],
            "namespace": secret["namespace"],
            "labels": {SECRET_OWNER_LABEL: INSTALLER_OWNER},
        },
        "type": secret["type"],
        "data": {
            key: base64.b64encode(values[artifact_id]).decode("ascii")
            for key, artifact_id in secret["data"].items()
            if _condition_matches(data_when.get(key), selectors)
        },
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _apply_platform_secrets_from_snapshot(
    *,
    artifact_directory: Path,
    external_inputs: dict[str, Path],
    kubeconfig: Path,
    context: str,
    apply: bool,
    private_root: Path,
    expected_namespace_uids: dict[str, str],
    transaction_directory: Path | None,
    transaction_commit: str | None,
    transaction_identity_mode: str | None,
    selectors: dict[str, bool],
    runner: Runner,
) -> None:
    registry = _load_registry()
    values = _artifact_values(
        registry,
        artifact_directory,
        external_inputs,
        private_root=private_root,
        selectors=selectors,
    )
    selected_secrets = [
        secret
        for secret in registry["secrets"]
        if _condition_matches(secret.get("when"), selectors)
    ]
    selected_registry = {**registry, "secrets": selected_secrets}
    _validate_ownership(
        selected_registry,
        kubeconfig,
        context,
        expected_namespace_uids,
        runner,
    )
    manifests = [
        (secret, _render_secret(secret, values, selectors))
        for secret in selected_secrets
    ]
    for secret, manifest in manifests:
        _validate_ownership(
            {**registry, "secrets": [secret]},
            kubeconfig,
            context,
            {secret["namespace"]: expected_namespace_uids[secret["namespace"]]},
            runner,
        )
        runner(
            _kubectl(
                kubeconfig,
                context,
                "apply",
                "--namespace",
                secret["namespace"],
                "--dry-run=server",
                "--output=name",
                "--filename=-",
            ),
            manifest,
        )
    if apply:
        if (
            transaction_directory is None
            or transaction_commit is None
            or transaction_identity_mode not in {"bundledKeycloak", "externalOidc"}
        ):
            raise PlatformSecretApplyError(
                "A complete Secret transaction binding is required for apply"
            )

        def transaction_runner(
            command: list[str],
            *,
            environment: dict[str, str] | None = None,
            stdout_path: Path | None = None,
        ) -> str:
            del environment
            if command[0] != "kubectl":
                raise PlatformSecretApplyError("Secret transaction command is invalid")
            output = runner(
                ["kubectl", "--kubeconfig", str(kubeconfig), *command[1:]],
                None,
            )
            if stdout_path is not None:
                try:
                    PRIVATE_INPUT.write_private_snapshot(
                        destination=stdout_path,
                        content=output,
                        description="Secret post-state query result",
                        private_root=private_root,
                    )
                except PRIVATE_INPUT.PrivateInputError as exc:
                    raise PlatformSecretApplyError(
                        "Secret post-state query result cannot be recorded"
                    ) from exc
                return ""
            try:
                return output.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PlatformSecretApplyError(
                    "Secret transaction command returned invalid UTF-8"
                ) from exc

        _validate_ownership(
            registry,
            kubeconfig,
            context,
            expected_namespace_uids,
            runner,
        )
        for secret, manifest in manifests:
            _validate_ownership(
                {**registry, "secrets": [secret]},
                kubeconfig,
                context,
                {secret["namespace"]: expected_namespace_uids[secret["namespace"]]},
                runner,
            )
            mutation = INSTALLATION_TRANSACTION.prepare_secret_mutation(
                transaction_directory=transaction_directory,
                commit=transaction_commit,
                context=context,
                identity_mode=transaction_identity_mode,
                namespace=secret["namespace"],
                name=secret["name"],
                expected_manifest=manifest,
                runner=transaction_runner,
                registry_path=CANONICAL_REGISTRY,
            )
            operation = "create"
            mutation_manifest = (
                INSTALLATION_TRANSACTION.render_secret_mutation_manifest(
                    expected_manifest=manifest,
                    namespace=secret["namespace"],
                    name=secret["name"],
                    transaction_marker=mutation["transactionMarker"],
                )
            )
            if mutation["state"] == "existing":
                mutation_manifest = (
                    INSTALLATION_TRANSACTION.render_secret_mutation_manifest(
                        expected_manifest=manifest,
                        namespace=secret["namespace"],
                        name=secret["name"],
                        transaction_marker=mutation["transactionMarker"],
                        uid=mutation["uid"],
                        resource_version=mutation["resourceVersion"],
                    )
                )
                operation = "replace"
            runner(
                _kubectl(
                    kubeconfig,
                    context,
                    operation,
                    "--namespace",
                    secret["namespace"],
                    "--dry-run=server",
                    "--output=name",
                    "--filename=-",
                ),
                mutation_manifest,
            )
            INSTALLATION_TRANSACTION.validate_secret_mutation_namespace(
                transaction_directory=transaction_directory,
                commit=transaction_commit,
                context=context,
                identity_mode=transaction_identity_mode,
                namespace=secret["namespace"],
                name=secret["name"],
                runner=transaction_runner,
                registry_path=CANONICAL_REGISTRY,
            )
            runner(
                _kubectl(
                    kubeconfig,
                    context,
                    operation,
                    "--namespace",
                    secret["namespace"],
                    "--output=name",
                    "--filename=-",
                ),
                mutation_manifest,
            )
            INSTALLATION_TRANSACTION.record_secret_post_state(
                transaction_directory=transaction_directory,
                commit=transaction_commit,
                context=context,
                identity_mode=transaction_identity_mode,
                namespace=secret["namespace"],
                name=secret["name"],
                expected_manifest=manifest,
                runner=transaction_runner,
                registry_path=CANONICAL_REGISTRY,
            )


def apply_platform_secrets(
    *,
    artifact_directory: Path,
    external_inputs: dict[str, Path],
    kubeconfig: Path,
    context: str,
    expected_namespace_uids: dict[str, str],
    apply: bool,
    transaction_directory: Path | None = None,
    transaction_commit: str | None = None,
    transaction_identity_mode: str | None = None,
    values_path: Path | None = None,
    runner: Runner = _run_command,
) -> None:
    """Pin one kubeconfig copy, dry-run all Secrets, then optionally apply."""

    if not context or context != context.strip():
        raise PlatformSecretApplyError("An exact Kubernetes context is required")
    try:
        private_root = PRIVATE_INPUT.private_root_path(INSTALLATION_STATE.PRIVATE_ROOT)
        selectors = {"postgres.enabled": True, "redis.enabled": True}
        if values_path is not None:
            try:
                values_document = json.loads(
                    _read_private_file(
                        values_path,
                        "Core release values",
                        private_root=private_root,
                    )
                )
                selectors = {
                    "postgres.enabled": values_document["postgres"]["enabled"],
                    "redis.enabled": values_document["redis"]["enabled"],
                }
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
            ) as exc:
                raise PlatformSecretApplyError(
                    "Core release values are invalid"
                ) from exc
            if any(not isinstance(value, bool) for value in selectors.values()):
                raise PlatformSecretApplyError("Core release values are invalid")

        def flatten_runner(
            command: list[str],
            *,
            environment: dict[str, str] | None = None,
        ) -> str:
            del environment
            try:
                return runner(command, None).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PlatformSecretApplyError(
                    "kubectl returned invalid flattened kubeconfig"
                ) from exc

        with TemporaryDirectory(
            prefix=".apply-platform-secrets-",
            dir=private_root,
        ) as temporary:
            transaction = Path(temporary)
            transaction.chmod(0o700)
            flattened_kubeconfig = PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
                source=kubeconfig,
                raw_destination=transaction / "kubeconfig.raw",
                flattened_destination=transaction / "kubeconfig",
                context=context,
                runner=flatten_runner,
                private_root=private_root,
            )
            _apply_platform_secrets_from_snapshot(
                artifact_directory=artifact_directory,
                external_inputs=external_inputs,
                kubeconfig=flattened_kubeconfig,
                context=context,
                apply=apply,
                private_root=private_root,
                expected_namespace_uids=expected_namespace_uids,
                transaction_directory=transaction_directory,
                transaction_commit=transaction_commit,
                transaction_identity_mode=transaction_identity_mode,
                selectors=selectors,
                runner=runner,
            )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise PlatformSecretApplyError(
            "Flattened kubeconfig snapshot or context is invalid"
        ) from exc


def _external_input(value: str) -> tuple[str, Path]:
    artifact_id, separator, path = value.partition("=")
    if not separator or not artifact_id or not path:
        raise argparse.ArgumentTypeError(
            "external input must use ARTIFACT_ID=/absolute/path"
        )
    input_path = Path(path)
    if not input_path.is_absolute():
        raise argparse.ArgumentTypeError("external input path must be absolute")
    return artifact_id, input_path


def _namespace_uid(value: str) -> tuple[str, str]:
    namespace, separator, uid = value.partition("=")
    if (
        not separator
        or namespace not in PLATFORM_NAMESPACES
        or not uid
        or uid != uid.strip()
    ):
        raise argparse.ArgumentTypeError(
            "expected Namespace UID must use NAMESPACE=UID"
        )
    return namespace, uid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument(
        "--external-input", action="append", type=_external_input, default=[]
    )
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--values", type=Path, required=True)
    parser.add_argument(
        "--expected-namespace-uid",
        action="append",
        type=_namespace_uid,
        required=True,
    )
    parser.add_argument("--context", required=True)
    parser.add_argument("--transaction-directory", type=Path)
    parser.add_argument("--transaction-commit")
    parser.add_argument(
        "--transaction-identity-mode",
        choices=("bundledKeycloak", "externalOidc"),
    )
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    external_inputs = dict(arguments.external_input)
    if len(external_inputs) != len(arguments.external_input):
        parser.error("duplicate external input artifact ID")
    expected_namespace_uids = dict(arguments.expected_namespace_uid)
    if len(expected_namespace_uids) != len(arguments.expected_namespace_uid):
        parser.error("duplicate expected Namespace UID")
    transaction_fields = (
        arguments.transaction_directory,
        arguments.transaction_commit,
        arguments.transaction_identity_mode,
    )
    if arguments.apply != all(field is not None for field in transaction_fields):
        parser.error(
            "--apply requires the complete Secret transaction binding and dry-run forbids it"
        )
    try:
        apply_platform_secrets(
            artifact_directory=arguments.artifact_directory,
            external_inputs=external_inputs,
            kubeconfig=arguments.kubeconfig,
            context=arguments.context,
            expected_namespace_uids=expected_namespace_uids,
            apply=arguments.apply,
            transaction_directory=arguments.transaction_directory,
            transaction_commit=arguments.transaction_commit,
            transaction_identity_mode=arguments.transaction_identity_mode,
            values_path=arguments.values,
        )
    except PlatformSecretApplyError as exc:
        parser.error(str(exc))
    mode = "applied" if arguments.apply else "accepted by Kubernetes server dry-run"
    print(f"Core platform Secrets were {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
