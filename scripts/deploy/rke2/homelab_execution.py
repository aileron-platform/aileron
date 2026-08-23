#!/usr/bin/env python3
"""Execute the production HomeLab lifecycle behind one typed port."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import socket
import ssl
import stat
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

import yaml

try:
    from scripts.deploy.rke2 import install as INSTALL
    from scripts.deploy.rke2 import new_installation as NEW_INSTALLATION
    from scripts.deploy.rke2 import (
        prepare_release_inventory as PREPARE_RELEASE_INVENTORY,
    )
except ModuleNotFoundError as exc:  # Direct deployment-host script execution.
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import install as INSTALL
    import new_installation as NEW_INSTALLATION
    import prepare_release_inventory as PREPARE_RELEASE_INVENTORY


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILD_PUSH_SCRIPT = Path("scripts/deploy/rke2/build-push-images.sh")
RECEIPT_SCHEMA = "aileron-homelab-execution-receipt/v1"
NEW_INSTALLATION_SCHEMA = "aileron-new-installation-transaction/v1"
RELEASE_RESULT_SCHEMA = "aileron-release-inventory-preparation-result/v1"
SHA256_LENGTH = 64
MAXIMUM_PRIVATE_INPUT_BYTES = 1024 * 1024
DOCKER_CERTIFICATE_ROOT = Path("/etc/docker/certs.d")

INPUT_PATHS = {
    "kubeconfig": Path("inputs/kubeconfig"),
    "backendExecutionProfile": Path("inputs/backend-execution-profile.json"),
    "harborDockerconfig": Path("inputs/docker/config.json"),
    "registryCa": Path("inputs/registry-ca.crt"),
    "appsTlsCertificate": Path("inputs/apps-tls.crt"),
    "appsTlsPrivateKey": Path("inputs/apps-tls.key"),
    "appsTlsCa": Path("inputs/apps-ca.crt"),
    "oidcCa": Path("inputs/oidc-ca.crt"),
    "identityTlsCertificate": Path("inputs/identity-tls.crt"),
    "identityTlsPrivateKey": Path("inputs/identity-tls.key"),
    "externalOidcClientSecret": Path("inputs/external-oidc-client-secret"),
    "oidcLoginUsername": Path("inputs/oidc-login-username"),
    "oidcLoginPassword": Path("inputs/oidc-login-password"),
    "coreDataServiceValues": Path("inputs/core-data-service-values.yaml"),
    "identityDataServiceValues": Path("inputs/identity-data-service-values.yaml"),
    "platformDatabaseUrl": Path("inputs/platform-database-url"),
    "platformDatabaseCa": Path("inputs/platform-database-ca.crt"),
    "redisGeneralUrl": Path("inputs/redis-general-url"),
    "redisJobQueueUrl": Path("inputs/redis-job-queue-url"),
    "redisJobResultUrl": Path("inputs/redis-job-result-url"),
    "redisGeneralCa": Path("inputs/redis-general-ca.crt"),
    "redisJobQueueCa": Path("inputs/redis-job-queue-ca.crt"),
    "redisJobResultCa": Path("inputs/redis-job-result-ca.crt"),
    "identityDatabaseUsername": Path("inputs/identity-database-username"),
    "identityDatabasePassword": Path("inputs/identity-database-password"),
    "identityDatabaseCa": Path("inputs/identity-database-ca.crt"),
}
BASE_INPUT_NAMES = {
    "kubeconfig",
    "backendExecutionProfile",
    "harborDockerconfig",
    "registryCa",
    "appsTlsCertificate",
    "appsTlsPrivateKey",
    "appsTlsCa",
    "oidcCa",
}
CORE_POSTGRES_INPUTS = {"platformDatabaseUrl", "platformDatabaseCa"}
CORE_REDIS_INPUTS = {
    "redisGeneralUrl",
    "redisJobQueueUrl",
    "redisJobResultUrl",
    "redisGeneralCa",
    "redisJobQueueCa",
    "redisJobResultCa",
}
IDENTITY_DATABASE_INPUTS = {
    "identityDatabaseUsername",
    "identityDatabasePassword",
    "identityDatabaseCa",
}
DATA_SERVICE_INPUTS = (
    {"coreDataServiceValues", "identityDataServiceValues"}
    | CORE_POSTGRES_INPUTS
    | CORE_REDIS_INPUTS
    | IDENTITY_DATABASE_INPUTS
)
CORE_DATA_SERVICE_ARTIFACTS = {
    "platformDatabaseUrl": "database-url",
    "platformDatabaseCa": "platform-database-ca",
    "redisGeneralUrl": "redis-general-url",
    "redisJobQueueUrl": "redis-job-queue-url",
    "redisJobResultUrl": "redis-job-result-url",
    "redisGeneralCa": "redis-general-ca",
    "redisJobQueueCa": "redis-job-queue-ca",
    "redisJobResultCa": "redis-job-result-ca",
}
NEW_INSTALLATION_RECEIPT_KEYS = {
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
STEP_FAILURE_CODES = {
    "newInstallation": "newInstallationFailed",
    "releasePreparation": "releasePreparationFailed",
    "reset": "resetFailed",
    "install": "installFailed",
    "acceptance": "acceptanceFailed",
}
RESET_OPERATION_CALLABLES = (
    "ResetOperationRequest",
    "ResetOperationProfile",
    "ResetOperationInput",
    "ResetOperationResult",
    "ResetOperationError",
    "execute_reset_operation",
)
ACCEPTANCE_OPERATION_CALLABLES = (
    "AcceptanceOperationRequest",
    "AcceptanceOperationResult",
    "AcceptanceOperationError",
    "BrowserLoginDriver",
    "WorkspaceIdentity",
    "execute_acceptance_operation",
)


class SourceInspector(Protocol):
    """Read the current repository identity without mutating it."""

    def inspect(self) -> object:
        """Return an object with ``head_commit`` and ``clean`` fields."""


class OperationPort(Protocol):
    """Neutral module boundary for reset or acceptance execution."""

    def __getattr__(self, name: str) -> object:
        """Expose operation-owned request, result, and execute types."""


CommandRunner = Callable[..., str]
RegistryTrustValidator = Callable[..., None]
KeywordOperation = Callable[..., dict[str, Any]]


class _ExecutionFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _SourceState:
    head_commit: str
    clean: bool


class _GitSourceInspector:
    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root

    def inspect(self) -> _SourceState:
        head = self._run(["rev-parse", "--verify", "HEAD"]).strip()
        status = self._run(["status", "--porcelain=v1", "--untracked-files=all"])
        return _SourceState(head_commit=head, clean=status == "")

    def _run(self, arguments: list[str]) -> str:
        try:
            completed = subprocess.run(
                [
                    "git",
                    "--no-optional-locks",
                    "-C",
                    str(self._repository_root),
                    *arguments,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError as exc:
            raise _ExecutionFailure("sourceInspectionFailed") from exc
        if completed.returncode != 0:
            raise _ExecutionFailure("sourceInspectionFailed")
        return completed.stdout


def _run_command(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env={**os.environ, **(environment or {})},
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as exc:
        raise _ExecutionFailure("releaseBuildFailed") from exc
    if completed.returncode != 0:
        raise _ExecutionFailure("releaseBuildFailed")
    return ""


def _sha256_file(path: Path, *, maximum_size: int) -> str:
    digest = hashlib.sha256()
    total = 0
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(path)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or not stat.S_ISREG(path_metadata.st_mode)
            or metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise _ExecutionFailure("executionInputsInvalid")
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_size:
                raise _ExecutionFailure("executionInputsInvalid")
            digest.update(chunk)
    except _ExecutionFailure:
        raise
    except OSError as exc:
        raise _ExecutionFailure("executionInputsInvalid") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if total == 0:
        raise _ExecutionFailure("executionInputsInvalid")
    return digest.hexdigest()


def _regular_file(path: Path, *, private: bool, maximum_size: int) -> str:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ExecutionFailure("executionInputsInvalid") from exc
    expected_mode = 0o600 if private else None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or path.is_symlink()
        or metadata.st_uid != os.geteuid()
        or (
            expected_mode is not None
            and stat.S_IMODE(metadata.st_mode) != expected_mode
        )
    ):
        raise _ExecutionFailure("executionInputsInvalid")
    return _sha256_file(path, maximum_size=maximum_size)


def _private_directory(path: Path, *, create: bool) -> Path:
    if create and not path.exists() and not path.is_symlink():
        try:
            path.mkdir(mode=0o700)
        except OSError as exc:
            raise _ExecutionFailure("executionInputsInvalid") from exc
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _ExecutionFailure("executionInputsInvalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or path.is_symlink()
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise _ExecutionFailure("executionInputsInvalid")
    return path


def _validate_registry_trust(
    *,
    registry_host: str,
    registry_ca: Path,
    docker_certificate_root: Path = DOCKER_CERTIFICATE_ROOT,
) -> None:
    """Verify live registry TLS and Docker's exact CA identity."""

    host, separator, raw_port = registry_host.partition(":")
    port = int(raw_port) if separator else 443
    docker_ca = docker_certificate_root / registry_host / "ca.crt"
    try:
        staged_digest = _sha256_file(
            registry_ca,
            maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
        )
    except _ExecutionFailure as exc:
        raise _ExecutionFailure("registryTlsTrustInvalid") from exc
    try:
        docker_digest = _sha256_file(
            docker_ca,
            maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
        )
        docker_metadata = docker_ca.lstat()
        if (
            docker_ca.is_symlink()
            or not stat.S_ISREG(docker_metadata.st_mode)
            or staged_digest != docker_digest
        ):
            raise _ExecutionFailure("registryDockerTrustMismatch")
    except _ExecutionFailure as exc:
        if exc.code == "registryDockerTrustMismatch":
            raise
        raise _ExecutionFailure("registryDockerTrustMismatch") from exc
    try:
        context = ssl.create_default_context(cafile=str(registry_ca))
        with (
            socket.create_connection((host, port), timeout=15) as connection,
            context.wrap_socket(connection, server_hostname=host) as secure,
        ):
            if not secure.getpeercert():
                raise _ExecutionFailure("registryTlsTrustInvalid")
    except _ExecutionFailure:
        raise
    except (OSError, ssl.SSLError, ValueError) as exc:
        raise _ExecutionFailure("registryTlsTrustInvalid") from exc


def _canonical_digest(document: Mapping[str, Any]) -> str:
    try:
        content = json.dumps(
            document,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _ExecutionFailure("executionReceiptInvalid") from exc
    return hashlib.sha256(content).hexdigest()


def _safe_operation_code(value: object) -> str | None:
    if (
        isinstance(value, str)
        and 1 <= len(value) <= 64
        and value.isascii()
        and value[0].islower()
        and value.isalnum()
    ):
        return value
    return None


def _expected_input_names(profile: object, present_names: set[str]) -> set[str]:
    names = set(BASE_INPUT_NAMES)
    if getattr(profile, "identity_mode", None) == "bundledKeycloak":
        names.update({"identityTlsCertificate", "identityTlsPrivateKey"})
    elif getattr(profile, "identity_mode", None) == "externalOidc":
        names.add("externalOidcClientSecret")
    else:
        raise _ExecutionFailure("executionInputsInvalid")
    if getattr(profile, "acceptance_login_mode", None) == "files":
        names.update({"oidcLoginUsername", "oidcLoginPassword"})
    elif getattr(profile, "acceptance_login_mode", None) != "breakGlass":
        raise _ExecutionFailure("executionInputsInvalid")
    allowed = names | DATA_SERVICE_INPUTS
    if not names.issubset(present_names) or not present_names.issubset(allowed):
        raise _ExecutionFailure("executionInputsInvalid")
    for group in (CORE_POSTGRES_INPUTS, CORE_REDIS_INPUTS, IDENTITY_DATABASE_INPUTS):
        present = group & present_names
        if present and present != group:
            raise _ExecutionFailure("executionInputsInvalid")
    if (
        (
            (CORE_POSTGRES_INPUTS | CORE_REDIS_INPUTS) & present_names
            and "coreDataServiceValues" not in present_names
        )
        or (
            IDENTITY_DATABASE_INPUTS & present_names
            and "identityDataServiceValues" not in present_names
        )
        or (
            getattr(profile, "identity_mode", None) != "bundledKeycloak"
            and ({"identityDataServiceValues"} | IDENTITY_DATABASE_INPUTS)
            & present_names
        )
    ):
        raise _ExecutionFailure("executionInputsInvalid")
    return present_names


@dataclass(frozen=True)
class _ValidatedInputs:
    run_directory: Path
    private_root: Path
    paths: dict[str, Path]


def _omitted_image_components(inputs: _ValidatedInputs) -> frozenset[str]:
    values_path = inputs.paths.get("coreDataServiceValues")
    if values_path is None:
        return frozenset()
    try:
        values = yaml.safe_load(values_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise _ExecutionFailure("executionInputsInvalid") from exc
    if not isinstance(values, dict):
        raise _ExecutionFailure("executionInputsInvalid")
    redis = values.get("redis", {})
    if not isinstance(redis, dict):
        raise _ExecutionFailure("executionInputsInvalid")
    enabled = redis.get("enabled", True)
    if not isinstance(enabled, bool):
        raise _ExecutionFailure("executionInputsInvalid")
    return frozenset({"platform-redis"} if not enabled else set())


def _validated_inputs(request: object, facade: ModuleType) -> _ValidatedInputs:
    raw_inputs = getattr(request, "inputs", None)
    if not isinstance(raw_inputs, tuple) or not raw_inputs:
        raise _ExecutionFailure("executionInputsInvalid")
    records: dict[str, object] = {}
    for item in raw_inputs:
        if not isinstance(item, facade.StagedInput) or item.name in records:
            raise _ExecutionFailure("executionInputsInvalid")
        records[item.name] = item
    if set(records) != _expected_input_names(request.profile, set(records)):
        raise _ExecutionFailure("executionInputsInvalid")
    kubeconfig = records["kubeconfig"].path
    if not isinstance(kubeconfig, Path) or not kubeconfig.is_absolute():
        raise _ExecutionFailure("executionInputsInvalid")
    run_directory = kubeconfig.parent.parent
    if (
        run_directory.name != request.run_id
        or run_directory.parent.name != "runs"
        or run_directory.parent.parent.name != "homelab"
    ):
        raise _ExecutionFailure("executionInputsInvalid")
    _private_directory(run_directory, create=False)
    _private_directory(run_directory / "inputs", create=False)
    paths: dict[str, Path] = {}
    for name, item in records.items():
        expected = run_directory / INPUT_PATHS[name]
        path = item.path
        if (
            not isinstance(path, Path)
            or path != expected
            or not isinstance(item.digest, str)
            or len(item.digest) != SHA256_LENGTH
            or any(character not in "0123456789abcdef" for character in item.digest)
        ):
            raise _ExecutionFailure("executionInputsInvalid")
        if name == "harborDockerconfig":
            _private_directory(path.parent, create=False)
        if (
            _regular_file(
                path,
                private=True,
                maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
            )
            != item.digest
        ):
            raise _ExecutionFailure("executionInputsInvalid")
        paths[name] = path
    return _ValidatedInputs(
        run_directory=run_directory,
        private_root=run_directory.parents[2],
        paths=paths,
    )


def _load_optional_operation_module(module_name: str) -> ModuleType:
    package_name = f"scripts.deploy.rke2.{module_name}"
    try:
        return importlib.import_module(package_name)
    except ModuleNotFoundError as exc:
        if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
            raise
        return importlib.import_module(module_name)


def _validate_operation_module(
    module: OperationPort,
    required_callables: tuple[str, ...],
) -> None:
    if any(not callable(getattr(module, name, None)) for name in required_callables):
        raise TypeError("operation module interface is unavailable")


def _canonical_signed_inventory(inputs: _ValidatedInputs, commit: str) -> Path:
    inventory = inputs.private_root / "install" / commit / "signed-image-inventory.json"
    _regular_file(
        inventory,
        private=True,
        maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
    )
    return inventory


def _identity_artifacts_directory(
    inputs: _ValidatedInputs,
    *,
    identity_mode: str,
) -> Path | None:
    if identity_mode == "externalOidc":
        return None
    if identity_mode != "bundledKeycloak":
        raise _ExecutionFailure("executionInputsInvalid")
    directory = inputs.private_root / "install-secrets/rke2/identity-artifacts"
    if "identityDatabaseUsername" in inputs.paths:
        directory = directory / "postgres-disabled"
    return directory


@dataclass
class ProductionExecutionPort:
    """Dispatch the five production lifecycle steps through explicit modules."""

    facade: ModuleType
    repository_root: Path = REPOSITORY_ROOT
    source_inspector: SourceInspector | None = None
    new_installation_operation: KeywordOperation = NEW_INSTALLATION.new_installation
    release_inventory_operation: KeywordOperation = (
        PREPARE_RELEASE_INVENTORY.prepare_release_inventory
    )
    command_runner: CommandRunner = _run_command
    registry_trust_validator: RegistryTrustValidator = _validate_registry_trust
    install_module: Any = INSTALL
    reset_module: OperationPort = field(
        default_factory=lambda: _load_optional_operation_module(
            "homelab_reset_operation"
        )
    )
    acceptance_module: OperationPort = field(
        default_factory=lambda: _load_optional_operation_module(
            "homelab_acceptance_operation"
        )
    )

    def __post_init__(self) -> None:
        _validate_operation_module(self.reset_module, RESET_OPERATION_CALLABLES)
        _validate_operation_module(
            self.acceptance_module,
            ACCEPTANCE_OPERATION_CALLABLES,
        )
        if self.source_inspector is None:
            self.source_inspector = _GitSourceInspector(self.repository_root)

    def execute(self, request: object) -> object:
        """Execute one exact-HEAD step and return a facade-owned receipt."""

        step_value = getattr(getattr(request, "step", None), "value", None)
        failure_code = STEP_FAILURE_CODES.get(step_value, "executionRequestInvalid")
        try:
            if not isinstance(request, self.facade.ExecutionRequest):
                raise _ExecutionFailure("executionRequestInvalid")
            self._validate_source(request)
            inputs = _validated_inputs(request, self.facade)
            handlers = {
                "newInstallation": self._new_installation,
                "releasePreparation": self._release_preparation,
                "reset": self._reset,
                "install": self._install,
                "acceptance": self._acceptance,
            }
            handler = handlers.get(request.step.value)
            if handler is None:
                raise _ExecutionFailure("executionRequestInvalid")
            return handler(request, inputs)
        except _ExecutionFailure as exc:
            raise self.facade.ExecutionPortError(exc.code) from None
        except Exception:  # noqa: BLE001 - sanitize every operation failure.
            raise self.facade.ExecutionPortError(failure_code) from None

    def _validate_source(self, request: object) -> None:
        assert self.source_inspector is not None
        try:
            snapshot = self.source_inspector.inspect()
        except _ExecutionFailure:
            raise
        except Exception as exc:
            raise _ExecutionFailure("sourceInspectionFailed") from exc
        if getattr(snapshot, "clean", None) is not True:
            raise _ExecutionFailure("sourceCheckoutNotClean")
        if getattr(snapshot, "head_commit", None) != request.commit:
            raise _ExecutionFailure("sourceCommitMismatch")

    def _receipt(
        self,
        request: object,
        result: Mapping[str, Any],
        *,
        disposition: str = "completed",
    ) -> object:
        try:
            selected_disposition = self.facade.ExecutionDisposition(disposition)
        except ValueError as exc:
            raise _ExecutionFailure("executionReceiptInvalid") from exc
        digest = _canonical_digest(
            {
                "schemaVersion": RECEIPT_SCHEMA,
                "runId": request.run_id,
                "planDigest": request.plan_digest,
                "commit": request.commit,
                "step": request.step.value,
                "result": result,
            }
        )
        return self.facade.ExecutionReceipt(
            step=request.step,
            disposition=selected_disposition,
            digest=digest,
        )

    def _new_installation(
        self,
        request: object,
        inputs: _ValidatedInputs,
    ) -> object:
        result = self.new_installation_operation(
            commit=request.commit,
            kubeconfig=inputs.paths["kubeconfig"],
            context=request.profile.context,
            identity_mode=request.profile.identity_mode,
            issuer_url=request.profile.issuer_url,
            client_id=request.profile.client_id,
            confirm_forward_only=True,
        )
        if (
            not isinstance(result, dict)
            or set(result) != NEW_INSTALLATION_RECEIPT_KEYS
            or result.get("schemaVersion") != NEW_INSTALLATION_SCHEMA
            or result.get("commit") != request.commit
            or result.get("context") != request.profile.context
            or result.get("identityMode") != request.profile.identity_mode
            or result.get("issuerUrl") != request.profile.issuer_url
            or result.get("clientId") != request.profile.client_id
            or result.get("operation")
            not in {"initialBootstrap", "replacement", "noOp"}
            or result.get("state") != "completed"
        ):
            raise _ExecutionFailure("newInstallationReceiptInvalid")
        return self._receipt(request, result)

    def _release_preparation(
        self,
        request: object,
        inputs: _ValidatedInputs,
    ) -> object:
        self.registry_trust_validator(
            registry_host=request.profile.registry_host,
            registry_ca=inputs.paths["registryCa"],
        )
        release_directory = _private_directory(
            inputs.run_directory / "release",
            create=True,
        )
        inventory = release_directory / "images.tsv"
        if inventory.exists() or inventory.is_symlink():
            _regular_file(
                inventory,
                private=True,
                maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
            )
        script = self.repository_root / BUILD_PUSH_SCRIPT
        omitted_components = _omitted_image_components(inputs)
        self.command_runner(
            [str(script)],
            environment={
                "DOCKER_CONFIG": str(inputs.paths["harborDockerconfig"].parent),
                "HARBOR_REGISTRY": request.profile.registry_host,
                "HARBOR_PROJECT": request.profile.registry_project,
                "EXPECTED_COMMIT": request.commit,
                "OUTPUT_FILE": str(inventory),
                "OMIT_IMAGE_COMPONENTS": ",".join(sorted(omitted_components)),
            },
        )
        _regular_file(
            inventory,
            private=True,
            maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
        )
        result = self.release_inventory_operation(
            commit=request.commit,
            context=request.profile.context,
            kubeconfig=inputs.paths["kubeconfig"],
            inventory=inventory,
            docker_config=inputs.paths["harborDockerconfig"],
            registry=request.profile.registry_host,
            project=request.profile.registry_project,
            omitted_components=omitted_components,
        )
        if (
            not isinstance(result, dict)
            or set(result)
            != {
                "schemaVersion",
                "commit",
                "context",
                "imageCount",
                "created",
                "signedInventorySha256",
            }
            or result.get("schemaVersion") != RELEASE_RESULT_SCHEMA
            or result.get("commit") != request.commit
            or result.get("context") != request.profile.context
            or isinstance(result.get("imageCount"), bool)
            or not isinstance(result.get("imageCount"), int)
            or result["imageCount"] <= 0
            or not isinstance(result.get("created"), bool)
            or not isinstance(result.get("signedInventorySha256"), str)
            or len(result["signedInventorySha256"]) != SHA256_LENGTH
            or any(
                character not in "0123456789abcdef"
                for character in result["signedInventorySha256"]
            )
        ):
            raise _ExecutionFailure("releasePreparationReceiptInvalid")
        stable_result = {
            key: value for key, value in result.items() if key != "created"
        }
        return self._receipt(request, stable_result)

    def _reset(self, request: object, inputs: _ValidatedInputs) -> object:
        module = self.reset_module
        operation_request = module.ResetOperationRequest(
            run_id=request.run_id,
            plan_digest=request.plan_digest,
            approval_digest=request.approval_digest,
            commit=request.commit,
            profile=module.ResetOperationProfile(
                context=request.profile.context,
                registry_host=request.profile.registry_host,
                platform_url=request.profile.platform_url,
                identity_mode=request.profile.identity_mode,
                issuer_url=request.profile.issuer_url,
                admin_console_url=request.profile.admin_console_url,
                client_id=request.profile.client_id,
                acceptance_login_mode=request.profile.acceptance_login_mode,
            ),
            inputs=tuple(
                module.ResetOperationInput(
                    name=item.name,
                    path=inputs.paths[item.name],
                    digest=item.digest,
                )
                for item in request.inputs
            ),
        )
        try:
            result = module.execute_reset_operation(operation_request)
        except Exception as exc:
            if isinstance(exc, module.ResetOperationError):
                code = _safe_operation_code(getattr(exc, "code", None))
                if code is not None:
                    raise _ExecutionFailure(code) from exc
            raise
        if not isinstance(result, module.ResetOperationResult):
            raise _ExecutionFailure("resetReceiptInvalid")
        disposition = getattr(result.disposition, "value", None)
        snapshot_digest = result.reset_snapshot_digest
        report_digest = result.post_reset_report_digest
        if (
            not isinstance(snapshot_digest, str)
            or len(snapshot_digest) != SHA256_LENGTH
            or any(character not in "0123456789abcdef" for character in snapshot_digest)
            or disposition not in {"completed", "awaitingApproval"}
            or (disposition == "awaitingApproval" and report_digest is not None)
            or (
                disposition == "completed"
                and (
                    not isinstance(report_digest, str)
                    or len(report_digest) != SHA256_LENGTH
                    or any(
                        character not in "0123456789abcdef"
                        for character in report_digest
                    )
                )
            )
        ):
            raise _ExecutionFailure("resetReceiptInvalid")
        if disposition == "awaitingApproval":
            return self.facade.ExecutionReceipt(
                step=request.step,
                disposition=self.facade.ExecutionDisposition.AWAITING_APPROVAL,
                digest=snapshot_digest,
            )
        return self._receipt(
            request,
            {
                "schemaVersion": "aileron-homelab-reset-result/v1",
                "resetSnapshotDigest": snapshot_digest,
                "postResetReportDigest": report_digest,
            },
        )

    def _install(self, request: object, inputs: _ValidatedInputs) -> object:
        release_directory = _private_directory(
            inputs.run_directory / "release",
            create=False,
        )
        inventory = release_directory / "images.tsv"
        _regular_file(
            inventory,
            private=True,
            maximum_size=MAXIMUM_PRIVATE_INPUT_BYTES,
        )
        _canonical_signed_inventory(inputs, request.commit)
        identity_mode = request.profile.identity_mode
        common = {
            "expected_commit": request.commit,
            "context": request.profile.context,
            "identity_mode": identity_mode,
            "inventory_path": inventory,
            "execution_profile": inputs.paths["backendExecutionProfile"],
            "work_directory": inputs.private_root / "install" / request.commit,
            "kubeconfig": inputs.paths["kubeconfig"],
            "registry": request.profile.registry_host,
            "project": request.profile.registry_project,
            "platform_url": request.profile.platform_url,
            "harbor_dockerconfig": inputs.paths["harborDockerconfig"],
            "apps_tls_cert": inputs.paths["appsTlsCertificate"],
            "apps_tls_key": inputs.paths["appsTlsPrivateKey"],
            "apps_tls_ca": inputs.paths["appsTlsCa"],
            "oidc_ca": inputs.paths["oidcCa"],
            "turn_url": request.profile.turn_url,
            "core_data_service_values": inputs.paths.get("coreDataServiceValues"),
            "identity_data_service_values": inputs.paths.get(
                "identityDataServiceValues"
            ),
            "core_data_service_inputs": tuple(
                (artifact_id, inputs.paths[input_name])
                for input_name, artifact_id in CORE_DATA_SERVICE_ARTIFACTS.items()
                if input_name in inputs.paths
            ),
            "identity_database_username": inputs.paths.get("identityDatabaseUsername"),
            "identity_database_password": inputs.paths.get("identityDatabasePassword"),
            "identity_database_ca": inputs.paths.get("identityDatabaseCa"),
            "identity_tls_cert": (
                inputs.paths.get("identityTlsCertificate")
                if identity_mode == "bundledKeycloak"
                else None
            ),
            "identity_tls_key": (
                inputs.paths.get("identityTlsPrivateKey")
                if identity_mode == "bundledKeycloak"
                else None
            ),
            "external_oidc_client_secret": (
                inputs.paths.get("externalOidcClientSecret")
                if identity_mode == "externalOidc"
                else None
            ),
            "external_oidc_issuer_url": (
                request.profile.issuer_url if identity_mode == "externalOidc" else None
            ),
            "external_oidc_client_id": (
                request.profile.client_id if identity_mode == "externalOidc" else None
            ),
        }

        def run_phase(phase: str, *, confirm: bool = False) -> None:
            self.install_module.install_rke2(
                **common,
                phase=phase,
                confirm_create_namespaces=confirm,
            )

        try:
            run_phase("validate")
        except self.install_module.InstallationPrerequisiteError as exc:
            if getattr(exc, "exit_code", None) != 78:
                raise
            run_phase("prepare-cluster", confirm=True)
            run_phase("validate")
        run_phase("apply")
        return self._receipt(
            request,
            {
                "schemaVersion": "aileron-homelab-install-result/v1",
                "phases": ["validate", "prepare-cluster-if-required", "apply"],
            },
        )

    def _acceptance(self, request: object, inputs: _ValidatedInputs) -> object:
        module = self.acceptance_module
        signed_inventory = _canonical_signed_inventory(inputs, request.commit)
        driver = request.profile.acceptance_login_driver
        operation_request = module.AcceptanceOperationRequest(
            expected_commit=request.commit,
            deployment_run_id=request.run_id,
            authentication_mode=request.profile.identity_mode,
            context=request.profile.context,
            kubeconfig=inputs.paths["kubeconfig"],
            platform_url=request.profile.platform_url,
            issuer_url=request.profile.issuer_url,
            admin_console_url=request.profile.admin_console_url,
            client_id=request.profile.client_id,
            image_inventory=signed_inventory,
            reset_snapshot_digest=request.approval_digest,
            apps_ca=inputs.paths["appsTlsCa"],
            oidc_ca=inputs.paths["oidcCa"],
            identity_artifacts_directory=_identity_artifacts_directory(
                inputs,
                identity_mode=request.profile.identity_mode,
            ),
            browser_login_mode=request.profile.acceptance_login_mode,
            browser_login_driver=module.BrowserLoginDriver(
                kind=driver.kind,
                username_selector=driver.username_selector,
                password_selector=driver.password_selector,
                submit_selector=driver.submit_selector,
                error_selector=driver.error_selector,
            ),
            browser_login_username=inputs.paths.get("oidcLoginUsername"),
            browser_login_password=inputs.paths.get("oidcLoginPassword"),
        )
        try:
            result = module.execute_acceptance_operation(operation_request)
        except Exception as exc:
            if isinstance(exc, module.AcceptanceOperationError):
                code = _safe_operation_code(getattr(exc, "code", None))
                if code is not None:
                    raise _ExecutionFailure(code) from exc
            raise
        if not isinstance(result, module.AcceptanceOperationResult):
            raise _ExecutionFailure("acceptanceReceiptInvalid")
        workspace = result.workspace
        completed_sections = result.completed_sections
        if (
            not isinstance(result.bundle_sha256, str)
            or len(result.bundle_sha256) != SHA256_LENGTH
            or any(
                character not in "0123456789abcdef"
                for character in result.bundle_sha256
            )
            or not isinstance(workspace, module.WorkspaceIdentity)
            or not isinstance(workspace.id, str)
            or not workspace.id
            or not isinstance(workspace.user_subject, str)
            or not workspace.user_subject
            or not isinstance(completed_sections, tuple)
            or not completed_sections
            or any(
                not isinstance(section, str) or not section
                for section in completed_sections
            )
        ):
            raise _ExecutionFailure("acceptanceReceiptInvalid")
        return self._receipt(
            request,
            {
                "schemaVersion": "aileron-homelab-acceptance-result/v1",
                "bundleSha256": result.bundle_sha256,
                "workspace": {
                    "id": workspace.id,
                    "userSubject": workspace.user_subject,
                },
                "completedSections": list(completed_sections),
            },
        )


def create_production_execution_port(
    *,
    facade: ModuleType,
    repository_root: Path = REPOSITORY_ROOT,
    **dependencies: Any,
) -> ProductionExecutionPort:
    """Create the production port without importing a second facade identity."""

    return ProductionExecutionPort(
        facade=facade,
        repository_root=repository_root,
        **dependencies,
    )
