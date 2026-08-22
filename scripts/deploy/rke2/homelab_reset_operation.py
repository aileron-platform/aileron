"""Orchestrate one resumable, approval-gated HomeLab reset operation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

try:
    from scripts.deploy.rke2 import acceptance_cluster as ACCEPTANCE_CLUSTER
    from scripts.deploy.rke2 import acceptance_epoch as ACCEPTANCE_EPOCH
    from scripts.deploy.rke2 import acceptance_evidence as ACCEPTANCE_EVIDENCE
    from scripts.deploy.rke2 import acceptance_private_io as ACCEPTANCE_PRIVATE_IO
    from scripts.deploy.rke2 import acceptance_producer as ACCEPTANCE_PRODUCER
    from scripts.deploy.rke2 import acceptance_snapshot as ACCEPTANCE_SNAPSHOT
    from scripts.deploy.rke2 import collect_reset_inventory as RESET_INVENTORY
    from scripts.deploy.rke2 import ensure_installation_namespaces as NAMESPACES
    from scripts.deploy.rke2 import installation_state as INSTALLATION_STATE
    from scripts.deploy.rke2 import prepare_backend_attestor as BACKEND_PREPARER
    from scripts.deploy.rke2 import private_input as PRIVATE_INPUT
    from scripts.deploy.rke2 import reset_plan as RESET_PLAN
except ModuleNotFoundError as exc:
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import acceptance_cluster as ACCEPTANCE_CLUSTER  # type: ignore[no-redef]
    import acceptance_epoch as ACCEPTANCE_EPOCH  # type: ignore[no-redef]
    import acceptance_evidence as ACCEPTANCE_EVIDENCE  # type: ignore[no-redef]
    import acceptance_private_io as ACCEPTANCE_PRIVATE_IO  # type: ignore[no-redef]
    import acceptance_producer as ACCEPTANCE_PRODUCER  # type: ignore[no-redef]
    import acceptance_snapshot as ACCEPTANCE_SNAPSHOT  # type: ignore[no-redef]
    import collect_reset_inventory as RESET_INVENTORY  # type: ignore[no-redef]
    import ensure_installation_namespaces as NAMESPACES  # type: ignore[no-redef]
    import installation_state as INSTALLATION_STATE  # type: ignore[no-redef]
    import prepare_backend_attestor as BACKEND_PREPARER  # type: ignore[no-redef]
    import private_input as PRIVATE_INPUT  # type: ignore[no-redef]
    import reset_plan as RESET_PLAN  # type: ignore[no-redef]

__all__ = [
    "ResetOperationDisposition",
    "ResetOperationError",
    "ResetOperationInput",
    "ResetOperationProfile",
    "ResetOperationRequest",
    "ResetOperationResult",
    "ResetPrerequisiteDisposition",
    "ResetSafetyOperations",
    "execute_reset_operation",
]

FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^run-[0-9a-f]{32}$")
ERROR_CODE_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]{0,63}$")

BASE_INPUT_PATHS = {
    "kubeconfig": Path("inputs/kubeconfig"),
    "backendExecutionProfile": Path("inputs/backend-execution-profile.json"),
    "harborDockerconfig": Path("inputs/docker/config.json"),
    "registryCa": Path("inputs/registry-ca.crt"),
    "appsTlsCertificate": Path("inputs/apps-tls.crt"),
    "appsTlsPrivateKey": Path("inputs/apps-tls.key"),
    "appsTlsCa": Path("inputs/apps-ca.crt"),
    "oidcCa": Path("inputs/oidc-ca.crt"),
}
MODE_INPUT_PATHS = {
    "bundledKeycloak": {
        "identityTlsCertificate": Path("inputs/identity-tls.crt"),
        "identityTlsPrivateKey": Path("inputs/identity-tls.key"),
    },
    "externalOidc": {
        "externalOidcClientSecret": Path("inputs/external-oidc-client-secret"),
    },
}
LOGIN_INPUT_PATHS = {
    "oidcLoginUsername": Path("inputs/oidc-login-username"),
    "oidcLoginPassword": Path("inputs/oidc-login-password"),
}
DATA_SERVICE_INPUT_PATHS = {
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
CORE_POSTGRES_INPUT_NAMES = {"platformDatabaseUrl", "platformDatabaseCa"}
CORE_REDIS_INPUT_NAMES = {
    "redisGeneralUrl",
    "redisJobQueueUrl",
    "redisJobResultUrl",
    "redisGeneralCa",
    "redisJobQueueCa",
    "redisJobResultCa",
}
IDENTITY_DATABASE_INPUT_NAMES = {
    "identityDatabaseUsername",
    "identityDatabasePassword",
    "identityDatabaseCa",
}
CAUSAL_ROOT_SECTIONS = ("suites", "offlineOidcConformance")
MAXIMUM_STAGED_INPUT_BYTES = 128 * 1024 * 1024
KUBECONFIG_COMMAND_TIMEOUT_SECONDS = 60
INVENTORY_COMMAND_TIMEOUT_SECONDS = 660


class ResetOperationDisposition(str, Enum):
    """Neutral result states consumed by the HomeLab execution adapter."""

    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaitingApproval"


class ResetPrerequisiteDisposition(str, Enum):
    """Exact retained prerequisite result understood by this operation."""

    READY = "ready"
    PREPARATION_REQUIRED = "preparationRequired"


class ResetOperationError(RuntimeError):
    """Expose only a stable error code at the orchestration boundary."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or ERROR_CODE_PATTERN.fullmatch(code) is None:
            code = "resetOperationFailed"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ResetOperationInput:
    """One exact run-scoped staged private input."""

    name: str
    path: Path
    digest: str


@dataclass(frozen=True)
class ResetOperationProfile:
    """Non-secret deployment values needed by the reset workflow."""

    context: str
    registry_host: str
    platform_url: str
    identity_mode: str
    issuer_url: str
    admin_console_url: str | None
    client_id: str
    acceptance_login_mode: str


@dataclass(frozen=True)
class ResetOperationRequest:
    """Complete reset identity projected from one staged HomeLab run."""

    run_id: str
    plan_digest: str
    approval_digest: str
    commit: str
    profile: ResetOperationProfile
    inputs: tuple[ResetOperationInput, ...]


@dataclass(frozen=True)
class ResetOperationResult:
    """Neutral operation result mapped to a lifecycle execution receipt."""

    disposition: ResetOperationDisposition
    reset_snapshot_digest: str
    post_reset_report_digest: str | None


class ResetSafetyOperations(Protocol):
    """Existing safety modules presented as one orchestration boundary."""

    def validate_staged_inputs(self, request: ResetOperationRequest) -> None:
        """Revalidate every staged input before cluster access."""

    def resume_pre_reset_snapshot(self, request: ResetOperationRequest) -> str | None:
        """Return the exact snapshot digest, or None before its first write."""

    def prepare_backend_attestor(
        self, request: ResetOperationRequest, *, apply: bool
    ) -> ResetPrerequisiteDisposition:
        """Validate or explicitly prepare the retained backend prerequisite."""

    def ensure_existing_namespaces(
        self, request: ResetOperationRequest, *, existing_only: bool
    ) -> None:
        """Converge only the resettable Namespaces that already exist."""

    def create_pre_reset_snapshot(self, request: ResetOperationRequest) -> str:
        """Create the signed snapshot and deployment epoch once."""

    def validate_pre_reset_snapshot(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        """Revalidate the exact signed snapshot and epoch."""

    def ensure_causal_root(
        self,
        request: ResetOperationRequest,
        *,
        section: str,
        snapshot_digest: str,
    ) -> str:
        """Create or exactly resume one signed non-mutating root report."""

    def execute_approved_reset(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        """Build and resume the canonical durable reset plan."""

    def ensure_post_reset_report(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> str:
        """Create or exactly resume the signed post-reset report."""


def _expected_input_paths(profile: ResetOperationProfile) -> dict[str, Path]:
    if profile.identity_mode not in MODE_INPUT_PATHS:
        raise ResetOperationError("resetRequestInvalid")
    if profile.acceptance_login_mode not in {"breakGlass", "files"}:
        raise ResetOperationError("resetRequestInvalid")
    if (
        profile.acceptance_login_mode == "breakGlass"
        and profile.identity_mode != "bundledKeycloak"
    ):
        raise ResetOperationError("resetRequestInvalid")
    paths = {**BASE_INPUT_PATHS, **MODE_INPUT_PATHS[profile.identity_mode]}
    if profile.acceptance_login_mode == "files":
        paths.update(LOGIN_INPUT_PATHS)
    return paths


def _https_url(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
        or any(character.isspace() or character == "\\" for character in value)
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and not parsed.netloc.endswith(":")
        and "*" not in parsed.hostname
        and (port is None or 1 <= port <= 65535)
    )


def _validate_request(request: ResetOperationRequest) -> None:
    if (
        not isinstance(request, ResetOperationRequest)
        or RUN_ID_PATTERN.fullmatch(request.run_id) is None
        or FULL_SHA_PATTERN.fullmatch(request.commit) is None
        or DIGEST_PATTERN.fullmatch(request.plan_digest) is None
        or DIGEST_PATTERN.fullmatch(request.approval_digest) is None
        or not isinstance(request.profile, ResetOperationProfile)
        or any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or any(
                ord(character) < 0x20 or ord(character) == 0x7F for character in value
            )
            for value in (
                request.profile.context,
                request.profile.registry_host,
                request.profile.platform_url,
                request.profile.issuer_url,
                request.profile.client_id,
            )
        )
    ):
        raise ResetOperationError("resetRequestInvalid")
    if (
        request.profile.identity_mode == "bundledKeycloak"
        and not _https_url(request.profile.admin_console_url)
        or request.profile.identity_mode == "externalOidc"
        and request.profile.admin_console_url is not None
    ):
        raise ResetOperationError("resetRequestInvalid")
    required = _expected_input_paths(request.profile)
    allowed = {**required, **DATA_SERVICE_INPUT_PATHS}
    if not len(required) <= len(request.inputs) <= len(allowed):
        raise ResetOperationError("resetInputMapInvalid")
    by_name: dict[str, ResetOperationInput] = {}
    for item in request.inputs:
        if (
            not isinstance(item, ResetOperationInput)
            or item.name in by_name
            or item.name not in allowed
            or not isinstance(item.path, Path)
            or not item.path.is_absolute()
            or DIGEST_PATTERN.fullmatch(item.digest) is None
        ):
            raise ResetOperationError("resetInputMapInvalid")
        by_name[item.name] = item
    names = set(by_name)
    if not set(required).issubset(names):
        raise ResetOperationError("resetInputMapInvalid")
    for group in (
        CORE_POSTGRES_INPUT_NAMES,
        CORE_REDIS_INPUT_NAMES,
        IDENTITY_DATABASE_INPUT_NAMES,
    ):
        present = names & group
        if present and present != group:
            raise ResetOperationError("resetInputMapInvalid")
    if (
        names & (CORE_POSTGRES_INPUT_NAMES | CORE_REDIS_INPUT_NAMES)
        and "coreDataServiceValues" not in names
        or names & IDENTITY_DATABASE_INPUT_NAMES
        and "identityDataServiceValues" not in names
        or request.profile.identity_mode != "bundledKeycloak"
        and names
        & ({"identityDataServiceValues"} | IDENTITY_DATABASE_INPUT_NAMES)
    ):
        raise ResetOperationError("resetInputMapInvalid")
    expected = {
        **required,
        **{
            name: DATA_SERVICE_INPUT_PATHS[name]
            for name in names & set(DATA_SERVICE_INPUT_PATHS)
        },
    }
    inputs_directory = by_name["kubeconfig"].path.parent
    run_directory = inputs_directory.parent
    if inputs_directory.name != "inputs" or run_directory.name != request.run_id:
        raise ResetOperationError("resetInputMapInvalid")
    if any(
        by_name[name].path != run_directory / relative
        for name, relative in expected.items()
    ):
        raise ResetOperationError("resetInputMapInvalid")


def _digest(value: object, *, code: str) -> str:
    if not isinstance(value, str) or DIGEST_PATTERN.fullmatch(value) is None:
        raise ResetOperationError(code)
    return value


def _input_by_name(request: ResetOperationRequest) -> dict[str, ResetOperationInput]:
    return {item.name: item for item in request.inputs}


def _artifact_exists(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    return True


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp is invalid")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if (
        parsed.tzinfo != timezone.utc
        or parsed.isoformat(timespec="seconds").replace("+00:00", "Z") != value
    ):
        raise ValueError("timestamp is invalid")
    return parsed


def _run_kubeconfig_command(command: list[str], *, environment: dict[str, str]) -> str:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            env={**os.environ, **environment},
            check=False,
            text=True,
            timeout=KUBECONFIG_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("kubeconfig snapshot command failed") from exc
    if process.returncode != 0:
        raise ValueError("kubeconfig snapshot command failed")
    return process.stdout


def _run_inventory_command(command: list[str]) -> str:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=INVENTORY_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("reset inventory command failed") from exc
    if process.returncode != 0:
        raise ValueError("reset inventory command failed")
    return process.stdout


@dataclass(frozen=True)
class _SnapshotContext:
    directory: Path
    kubeconfig: Path
    private_root: Path
    trust: Any
    snapshot: dict[str, Any]
    epoch: dict[str, Any]


class _ProductionResetSafetyOperations:
    """Route orchestration exclusively through the existing safety modules."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._clock = clock

    @staticmethod
    def _private_root() -> Path:
        return PRIVATE_INPUT.private_root_path(INSTALLATION_STATE.PRIVATE_ROOT)

    @classmethod
    def _evidence_directory(cls, request: ResetOperationRequest) -> Path:
        return ACCEPTANCE_PRIVATE_IO.evidence_directory(
            private_root=cls._private_root(),
            commit=request.commit,
            deployment_run_id=request.run_id,
            error_type=ValueError,
        )

    @classmethod
    def _reset_state_path(cls, request: ResetOperationRequest) -> Path:
        return (
            cls._private_root()
            / "reset"
            / request.commit
            / request.run_id
            / "reset-execution-state.json"
        )

    @staticmethod
    def _targets(
        request: ResetOperationRequest, *, kubeconfig: Path | None = None
    ) -> Any:
        inputs = _input_by_name(request)
        return ACCEPTANCE_PRODUCER.ProducerTargets(
            request.profile.context,
            kubeconfig or inputs["kubeconfig"].path,
            None,
            None,
            request.profile.platform_url,
            request.profile.issuer_url,
            request.profile.admin_console_url,
            request.profile.client_id,
            request.commit,
        )

    @classmethod
    def _signed_image_inventory(cls, request: ResetOperationRequest) -> Path:
        return (
            cls._private_root()
            / "install"
            / request.commit
            / "signed-image-inventory.json"
        )

    @classmethod
    def _authentication_mode(cls, request: ResetOperationRequest, trust: Any) -> str:
        raw = PRIVATE_INPUT.read_private_bytes(
            INSTALLATION_STATE.SECRET_STORE / "installation-identity.json",
            "installation identity",
            private_root=cls._private_root(),
            maximum_size=64 * 1024,
        )
        if hashlib.sha256(raw).hexdigest() != trust.installation_identity_sha256:
            raise ValueError("installation identity does not match acceptance trust")
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("installation identity is invalid") from exc
        validated = INSTALLATION_STATE.validate_installation_identity_document(
            document,
            cluster_uid=trust.cluster_uid,
        )
        expected = INSTALLATION_STATE.installation_identity_document(
            installation_id=validated["installationId"],
            identity_mode=request.profile.identity_mode,
            issuer_url=request.profile.issuer_url,
            client_id=request.profile.client_id,
            cluster_uid=trust.cluster_uid,
        )
        if validated != expected:
            raise ValueError("reset target does not match installation identity")
        return validated["identityMode"]

    @classmethod
    def _read_snapshot_digest(cls, request: ResetOperationRequest) -> str:
        raw = ACCEPTANCE_PRIVATE_IO.read_private_bytes(
            cls._evidence_directory(request) / ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME,
            "reset snapshot",
            private_root=cls._private_root(),
            error_type=ValueError,
            maximum_size=4 * 1024 * 1024,
            require_nonempty=True,
        )
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def _load_snapshot_context(
        cls,
        request: ResetOperationRequest,
        *,
        expected_snapshot_digest: str,
        repair_epoch: bool,
    ) -> _SnapshotContext:
        directory = cls._evidence_directory(request)
        private_root = cls._private_root()
        canonical_kubeconfig = ACCEPTANCE_PRIVATE_IO.validate_canonical_kubeconfig(
            directory=directory,
            private_root=private_root,
            commit=request.commit,
            deployment_run_id=request.run_id,
            context=request.profile.context,
            error_type=ValueError,
        ).path
        trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
            context=request.profile.context,
            kubeconfig=canonical_kubeconfig,
        )
        snapshot = ACCEPTANCE_SNAPSHOT.load_reset_snapshot(
            directory=directory,
            private_root=private_root,
            key=trust.key,
            context=request.profile.context,
            commit=request.commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
            expected_run_id=request.run_id,
            expected_snapshot_sha256=expected_snapshot_digest,
        )
        authentication_mode = cls._authentication_mode(request, trust)
        epoch_path = directory / ACCEPTANCE_EPOCH.EPOCH_NAME
        if not _artifact_exists(epoch_path):
            if not repair_epoch:
                raise ValueError("deployment epoch is unavailable")
            ACCEPTANCE_EPOCH.write_deployment_epoch(
                directory=directory,
                private_root=private_root,
                key=trust.key,
                deployment_run_id=request.run_id,
                commit=request.commit,
                cluster_uid=trust.cluster_uid,
                context=request.profile.context,
                installation_identity_sha256=trust.installation_identity_sha256,
                authentication_mode=authentication_mode,
                reset_snapshot_sha256=expected_snapshot_digest,
                created_at=_parse_timestamp(snapshot.get("createdAt")),
            )
        epoch = ACCEPTANCE_EPOCH.load_deployment_epoch(
            directory=directory,
            private_root=private_root,
            key=trust.key,
            commit=request.commit,
            cluster_uid=trust.cluster_uid,
            context=request.profile.context,
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=request.run_id,
        )
        if (
            epoch.get("authenticationMode") != authentication_mode
            or epoch.get("resetSnapshotSha256") != expected_snapshot_digest
            or _parse_timestamp(epoch.get("createdAt"))
            < _parse_timestamp(snapshot.get("createdAt"))
        ):
            raise ValueError("deployment epoch does not match reset snapshot")
        return _SnapshotContext(
            directory=directory,
            kubeconfig=canonical_kubeconfig,
            private_root=private_root,
            trust=trust,
            snapshot=snapshot,
            epoch=epoch,
        )

    def validate_staged_inputs(self, request: ResetOperationRequest) -> None:
        private_root = self._private_root()
        for item in request.inputs:
            content = PRIVATE_INPUT.read_private_bytes(
                item.path,
                f"staged HomeLab input {item.name}",
                private_root=private_root,
                maximum_size=MAXIMUM_STAGED_INPUT_BYTES,
                require_nonempty=True,
            )
            if hashlib.sha256(content).hexdigest() != item.digest:
                raise ValueError("staged HomeLab input digest changed")

    def resume_pre_reset_snapshot(self, request: ResetOperationRequest) -> str | None:
        directory = self._evidence_directory(request)
        snapshot_path = directory / ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME
        epoch_path = directory / ACCEPTANCE_EPOCH.EPOCH_NAME
        reset_state_path = self._reset_state_path(request)
        snapshot_exists = _artifact_exists(snapshot_path)
        if not snapshot_exists:
            unexpected = (
                epoch_path,
                directory / "suites.json",
                directory / "offlineOidcConformance.json",
                directory / "cleanReset.json",
                reset_state_path,
            )
            if any(_artifact_exists(path) for path in unexpected):
                raise ValueError("reset evidence exists without its snapshot")
            return None
        snapshot_digest = self._read_snapshot_digest(request)
        self._load_snapshot_context(
            request,
            expected_snapshot_digest=snapshot_digest,
            repair_epoch=True,
        )
        return snapshot_digest

    def prepare_backend_attestor(
        self, request: ResetOperationRequest, *, apply: bool
    ) -> ResetPrerequisiteDisposition:
        inputs = _input_by_name(request)
        result = BACKEND_PREPARER.prepare_backend_attestor(
            kubeconfig=inputs["kubeconfig"].path,
            harbor_dockerconfig=inputs["harborDockerconfig"].path,
            execution_profile=inputs["backendExecutionProfile"].path,
            context=request.profile.context,
            registry=request.profile.registry_host,
            apply=apply,
        )
        if (
            isinstance(result, dict)
            and result.get("schemaVersion")
            == BACKEND_PREPARER.EXECUTION_RESOURCES_SCHEMA
        ):
            return ResetPrerequisiteDisposition.READY
        preparation_keys = {
            "schemaVersion",
            "mode",
            "ready",
            "durablePrerequisiteRetained",
            "missingResources",
            "changedResources",
        }
        if (
            not apply
            and isinstance(result, dict)
            and set(result) == preparation_keys
            and result.get("schemaVersion")
            == BACKEND_PREPARER.PREPARATION_RESULT_SCHEMA
            and result.get("mode") == "validate"
            and result.get("ready") is False
            and result.get("durablePrerequisiteRetained") is False
            and isinstance(result.get("missingResources"), list)
            and isinstance(result.get("changedResources"), list)
            and bool(result["missingResources"] or result["changedResources"])
            and all(
                isinstance(value, str) and value
                for value in [
                    *result["missingResources"],
                    *result["changedResources"],
                ]
            )
        ):
            return ResetPrerequisiteDisposition.PREPARATION_REQUIRED
        raise ValueError("backend prerequisite result is invalid")

    def ensure_existing_namespaces(
        self, request: ResetOperationRequest, *, existing_only: bool
    ) -> None:
        if not existing_only:
            raise ValueError("reset Namespace convergence must be existing-only")
        result = NAMESPACES.ensure_installation_namespaces(
            kubeconfig=_input_by_name(request)["kubeconfig"].path,
            expected_context=request.profile.context,
            identity_mode=request.profile.identity_mode,
            existing_only=True,
        )
        if (
            not isinstance(result, dict)
            or result.get("schemaVersion") != NAMESPACES.NAMESPACE_RESULT_SCHEMA
            or result.get("mode") != "prepare"
            or result.get("ready") is not True
        ):
            raise ValueError("existing Namespace convergence result is invalid")

    def create_pre_reset_snapshot(self, request: ResetOperationRequest) -> str:
        snapshot_path = ACCEPTANCE_PRODUCER.produce(
            section="cleanReset",
            targets=self._targets(request),
            deployment_run_id=request.run_id,
            image_inventory=self._signed_image_inventory(request),
            reset_phase="pre-reset",
        )
        expected_path = (
            self._evidence_directory(request) / ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME
        )
        if snapshot_path != expected_path:
            raise ValueError("reset snapshot path is not canonical")
        digest = self._read_snapshot_digest(request)
        self._load_snapshot_context(
            request,
            expected_snapshot_digest=digest,
            repair_epoch=False,
        )
        return digest

    def validate_pre_reset_snapshot(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        if self._read_snapshot_digest(request) != snapshot_digest:
            raise ValueError("reset snapshot digest changed")
        context = self._load_snapshot_context(
            request,
            expected_snapshot_digest=snapshot_digest,
            repair_epoch=False,
        )
        if _artifact_exists(self._reset_state_path(request)):
            return
        approved_plan = RESET_PLAN.build_reset_plan(
            context.snapshot["inventory"],
            kubeconfig=context.kubeconfig,
            reset_run_id=request.run_id,
        )
        live_inventory = RESET_INVENTORY.collect_reset_inventory(
            expected_context=request.profile.context,
            kubeconfig=context.kubeconfig,
            runner=_run_inventory_command,
        )
        live_plan = RESET_PLAN.build_reset_plan(
            live_inventory,
            kubeconfig=context.kubeconfig,
            reset_run_id=request.run_id,
        )
        approved_target_set = RESET_PLAN.effective_reset_target_set(approved_plan)
        live_target_set = RESET_PLAN.effective_reset_target_set(live_plan)
        if live_target_set != approved_target_set:
            raise ValueError("live reset target set changed after snapshot")

    def _validated_report_digest(
        self,
        request: ResetOperationRequest,
        *,
        section: str,
        snapshot_digest: str,
        allow_stale_for_reset_resume: bool = False,
    ) -> str:
        context = self._load_snapshot_context(
            request,
            expected_snapshot_digest=snapshot_digest,
            repair_epoch=False,
        )
        contract = ACCEPTANCE_EVIDENCE.load_canonical_contract()
        observed_at = self._clock()
        if allow_stale_for_reset_resume:
            raw = ACCEPTANCE_PRIVATE_IO.read_private_bytes(
                context.directory / f"{section}.json",
                f"{section} report",
                private_root=context.private_root,
                error_type=ValueError,
                maximum_size=4 * 1024 * 1024,
                require_nonempty=True,
            )
            try:
                report = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("acceptance report is invalid") from exc
            observed_at = _parse_timestamp(
                report.get("finishedAt") if isinstance(report, dict) else None
            )
        validated = ACCEPTANCE_EVIDENCE.validate_report_file(
            directory=context.directory,
            section=section,
            contract=contract,
            expected_commit=request.commit,
            epoch=context.epoch,
            signing_key=context.trust.key,
            private_root=context.private_root,
            canonical_kubeconfig=context.directory / "kubeconfig",
            now=observed_at,
        )
        digest = validated.get("sha256") if isinstance(validated, dict) else None
        if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
            raise ValueError("acceptance report digest is invalid")
        return digest

    def ensure_causal_root(
        self,
        request: ResetOperationRequest,
        *,
        section: str,
        snapshot_digest: str,
    ) -> str:
        if section not in CAUSAL_ROOT_SECTIONS:
            raise ValueError("reset causal root section is invalid")
        report_path = self._evidence_directory(request) / f"{section}.json"
        reset_state_exists = _artifact_exists(self._reset_state_path(request))
        if not _artifact_exists(report_path):
            if reset_state_exists:
                raise ValueError("reset causal root is unavailable after reset start")
            produced = ACCEPTANCE_PRODUCER.produce(
                section=section,
                targets=self._targets(request),
                deployment_run_id=request.run_id,
                image_inventory=(
                    self._signed_image_inventory(request)
                    if section == "suites"
                    else None
                ),
            )
            if produced != report_path:
                raise ValueError("reset causal root path is not canonical")
        return self._validated_report_digest(
            request,
            section=section,
            snapshot_digest=snapshot_digest,
            allow_stale_for_reset_resume=reset_state_exists,
        )

    def execute_approved_reset(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        context = self._load_snapshot_context(
            request,
            expected_snapshot_digest=snapshot_digest,
            repair_epoch=False,
        )
        state_path = self._reset_state_path(request)
        PRIVATE_INPUT.ensure_private_directory(
            state_path.parent,
            "reset transaction directory",
            private_root=context.private_root,
        )
        reset_kubeconfig = PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=context.kubeconfig,
            raw_destination=(
                state_path.parent / f"reset-kubeconfig-{request.run_id}.raw.yaml"
            ),
            flattened_destination=(
                state_path.parent / f"reset-kubeconfig-{request.run_id}.flattened.json"
            ),
            context=request.profile.context,
            runner=_run_kubeconfig_command,
            private_root=context.private_root,
            allow_existing_exact=True,
        )
        plan = RESET_PLAN.build_reset_plan(
            context.snapshot["inventory"],
            kubeconfig=reset_kubeconfig,
            reset_run_id=request.run_id,
        )
        RESET_PLAN.execute_reset_plan(
            plan,
            kubeconfig=reset_kubeconfig,
            execution_state_path=state_path,
            expected_commit=request.commit,
            reset_snapshot_sha256=snapshot_digest,
            execution_lock_path=state_path.with_name(f"{state_path.name}.lock"),
            runner=_run_inventory_command,
            postcondition_interval_seconds=2.0,
        )

    def ensure_post_reset_report(
        self, request: ResetOperationRequest, *, snapshot_digest: str
    ) -> str:
        report_path = self._evidence_directory(request) / "cleanReset.json"
        if not _artifact_exists(report_path):
            produced = ACCEPTANCE_PRODUCER.produce(
                section="cleanReset",
                targets=self._targets(request),
                deployment_run_id=request.run_id,
                reset_phase="post-reset",
                expected_reset_snapshot_digest=snapshot_digest,
            )
            if produced != report_path:
                raise ValueError("post-reset report path is not canonical")
        return self._validated_report_digest(
            request,
            section="cleanReset",
            snapshot_digest=snapshot_digest,
        )


def _call(code: str, operation, /, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except ResetOperationError:
        raise
    except Exception:  # noqa: BLE001 - sanitize every dependency failure at this seam.
        raise ResetOperationError(code) from None


def execute_reset_operation(
    request: ResetOperationRequest,
    *,
    safety: ResetSafetyOperations | None = None,
) -> ResetOperationResult:
    """Advance one reset attempt without widening its approval or target set."""

    _validate_request(request)
    if safety is None:
        safety = _ProductionResetSafetyOperations()
    _call("resetInputInvalid", safety.validate_staged_inputs, request)
    snapshot_digest = _call(
        "resetSnapshotInvalid", safety.resume_pre_reset_snapshot, request
    )
    if snapshot_digest is None:
        if request.approval_digest != request.plan_digest:
            raise ResetOperationError("resetApprovalMismatch")
        prerequisite = _call(
            "resetPrerequisiteFailed",
            safety.prepare_backend_attestor,
            request,
            apply=False,
        )
        if prerequisite is ResetPrerequisiteDisposition.PREPARATION_REQUIRED:
            applied = _call(
                "resetPrerequisiteFailed",
                safety.prepare_backend_attestor,
                request,
                apply=True,
            )
            if applied is not ResetPrerequisiteDisposition.READY:
                raise ResetOperationError("resetPrerequisiteFailed")
            prerequisite = _call(
                "resetPrerequisiteFailed",
                safety.prepare_backend_attestor,
                request,
                apply=False,
            )
        if prerequisite is not ResetPrerequisiteDisposition.READY:
            raise ResetOperationError("resetPrerequisiteFailed")
        _call(
            "resetNamespaceConvergenceFailed",
            safety.ensure_existing_namespaces,
            request,
            existing_only=True,
        )
        snapshot_digest = _digest(
            _call(
                "resetSnapshotInvalid",
                safety.create_pre_reset_snapshot,
                request,
            ),
            code="resetSnapshotInvalid",
        )
    else:
        snapshot_digest = _digest(snapshot_digest, code="resetSnapshotInvalid")
        if request.approval_digest not in {request.plan_digest, snapshot_digest}:
            raise ResetOperationError("resetApprovalMismatch")

    _call(
        "resetSnapshotInvalid",
        safety.validate_pre_reset_snapshot,
        request,
        snapshot_digest=snapshot_digest,
    )
    for section in CAUSAL_ROOT_SECTIONS:
        _digest(
            _call(
                "resetCausalRootInvalid",
                safety.ensure_causal_root,
                request,
                section=section,
                snapshot_digest=snapshot_digest,
            ),
            code="resetCausalRootInvalid",
        )
        _call(
            "resetSnapshotInvalid",
            safety.validate_pre_reset_snapshot,
            request,
            snapshot_digest=snapshot_digest,
        )

    if request.approval_digest != snapshot_digest:
        return ResetOperationResult(
            disposition=ResetOperationDisposition.AWAITING_APPROVAL,
            reset_snapshot_digest=snapshot_digest,
            post_reset_report_digest=None,
        )

    _call(
        "resetExecutionFailed",
        safety.execute_approved_reset,
        request,
        snapshot_digest=snapshot_digest,
    )
    report_digest = _digest(
        _call(
            "resetPostReportInvalid",
            safety.ensure_post_reset_report,
            request,
            snapshot_digest=snapshot_digest,
        ),
        code="resetPostReportInvalid",
    )
    return ResetOperationResult(
        disposition=ResetOperationDisposition.COMPLETED,
        reset_snapshot_digest=snapshot_digest,
        post_reset_report_digest=report_digest,
    )
