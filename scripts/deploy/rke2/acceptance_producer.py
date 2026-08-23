#!/usr/bin/env python3
"""Run fixed HomeLab acceptance probes and sign their canonical reports."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import importlib.util
import io
import json
import math
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
CONTRACT_PATH = SCRIPT_DIRECTORY / "deployment-acceptance-contract.json"
VALIDATOR_PATH = SCRIPT_DIRECTORY / "acceptance_evidence.py"
PRODUCER_EXECUTABLE = "scripts/deploy/rke2/acceptance_producer.py"
PRODUCER_IDS = {
    "cleanReset": "aileron-reset-verifier",
    "imageRelease": "aileron-release-verifier",
    "identity": "aileron-identity-verifier",
    "oidcWorkspace": "aileron-oidc-workspace-probe",
    "terminal": "aileron-terminal-probe",
    "http": "aileron-http-probe",
    "browser": "aileron-browser-ui-probe",
    "websocket": "aileron-websocket-probe",
    "turn": "aileron-turn-probe",
    "workspaceLifecycle": "aileron-workspace-lifecycle-probe",
    "restart": "aileron-restart-probe",
    "soak": "aileron-soak-runner",
    "adminDisableLogin": "aileron-admin-disable-probe",
    "offlineOidcConformance": "aileron-offline-oidc-conformance",
    "suites": "aileron-container-suite-verifier",
}
SHA = re.compile(r"^[0-9a-f]{40}$")
SOAK_QUERY_PROCESS_TIMEOUT_SECONDS = 20.0
FILE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
ORACLE_SECTIONS = {
    "imageRelease",
    "identity",
    "turn",
    "restart",
}
ORACLE_TRANSACTION_TOKEN_ANNOTATION = "platform.aileron.dev/job-transaction-token"
ORACLE_TRANSACTION_RECONCILE_ATTEMPTS = 3
ORACLE_TRANSACTION_RECONCILE_INTERVAL_SECONDS = 1
ORACLE_DELETE_CLOSURE_TIMEOUT_SECONDS = 120.0
ORACLE_DELETE_CLOSURE_POLL_INTERVAL_SECONDS = 2.0
IDENTITY_SMOKE_REPORT_SCHEMA = "aileron-identity-backup-restore-smoke/v1"
IDENTITY_SMOKE_REPORT_KEYS = {
    "schemaVersion",
    "backupJobUids",
    "restoreJobUid",
    "restoreMarker",
    "jobClosureVerified",
}
BROWSER_SECTIONS = {
    "oidcWorkspace",
    "workspaceLifecycle",
    "adminDisableLogin",
    "terminal",
    "http",
    "browser",
    "websocket",
}
CLUSTER_SCOPED_SECTIONS = {
    "suites",
    "offlineOidcConformance",
    "imageRelease",
    "cleanReset",
    "identity",
}
WORKSPACE_SCOPED_SECTIONS = set(PRODUCER_IDS) - CLUSTER_SCOPED_SECTIONS
BROWSER_PROBE_PATH = "frontend/e2e/acceptance.mjs"
BROWSER_IMAGE_REPOSITORY = "ailerondocker/workspace-ui-playwright"
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
KUBERNETES_STATUS_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
SUITE_RUNNER_REPOSITORIES = {
    "docker": "ailerondocker/compose-e2e-test",
    "helm": "ailerondocker/helm-contract-test",
    "frontend": "ailerondocker/workspace-ui-suite",
    "manager": "ailerondocker/workspace-manager-suite",
    "operator": "ailerondocker/workspace-operator-suite",
    "identity": "ailerondocker/deployment-contract-test",
    "platform-conformance": "ailerondocker/product-conformance-test",
    "kubernetes-hardening": "ailerondocker/kubernetes-hardening-test",
    "docs-zh-Hant": "ailerondocker/docs-site-test",
    "docs-en": "ailerondocker/docs-site-test",
}
SUITE_IMAGE_ENVIRONMENT = {
    "docker": "AILERON_COMPOSE_E2E_TEST_IMAGE",
    "helm": "AILERON_HELM_CONTRACT_TEST_IMAGE",
    "frontend": "AILERON_FRONTEND_TEST_IMAGE",
    "manager": "AILERON_MANAGER_TEST_IMAGE",
    "operator": "AILERON_OPERATOR_TEST_IMAGE",
    "identity": "AILERON_DEPLOYMENT_CONTRACT_TEST_IMAGE",
    "platform-conformance": "AILERON_PRODUCT_CONFORMANCE_TEST_IMAGE",
    "kubernetes-hardening": "AILERON_KUBERNETES_HARDENING_TEST_IMAGE",
    "docs-zh-Hant": "AILERON_DOCS_SITE_TEST_IMAGE",
    "docs-en": "AILERON_DOCS_SITE_TEST_IMAGE",
}
HERMETIC_COMPOSE_ENVIRONMENT = (
    "env",
    "-i",
    "PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
    "COMPOSE_DISABLE_ENV_FILE=1",
)
SUITE_BUILD_TARGETS = {
    "docker": (".", "scripts/test/compose-e2e/Dockerfile.acceptance", None),
    "helm": (".", "scripts/test/helm/Dockerfile", None),
    "frontend": ("frontend", "frontend/Dockerfile.dev", None),
    "manager": (".", "workspace-manager/Dockerfile", "test"),
    "operator": ("workspace-operator", "workspace-operator/Dockerfile", "test"),
    "identity": (".", "scripts/test/deploy/Dockerfile", None),
    "platform-conformance": (
        ".",
        "scripts/test/kubernetes/product-conformance/Dockerfile",
        None,
    ),
    "kubernetes-hardening": (
        ".",
        "scripts/test/kubernetes/product-conformance/Dockerfile.hardening",
        None,
    ),
    "docs-zh-Hant": ("docs-site", "docs-site/Dockerfile.test", None),
    "docs-en": ("docs-site", "docs-site/Dockerfile.test", None),
}
SUITE_BUILD_ARGUMENTS = {
    "docker": (
        (
            "DOCKER_CLI_IMAGE",
            "docker:27-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01",
        ),
    ),
    "frontend": (
        (
            "NODE_IMAGE",
            "node:24.18.0-alpine@sha256:4ba75f835bb8802193e4c114572113d4b26f95f6f094f4b5229d2a77773e0afc",
        ),
        ("NPM_VERSION", "12.0.1"),
    ),
    "manager": (
        (
            "PYTHON_IMAGE",
            "python:3.14.6-slim@sha256:b921fe7e7522f828d45197a47656ec465a9b15689b27fa8e1fba2864fca5b967",
        ),
        (
            "NODE_IMAGE",
            "node:24.18.0-slim@sha256:d45d78e7929b46875bbd4e29bea672d5bc48186c6c3588306521c815e78352d6",
        ),
        ("NPM_VERSION", "12.0.1"),
        ("UV_VERSION", "0.11.32"),
        ("CODEX_CLI_VERSION", "0.145.0"),
    ),
    "operator": (
        ("BUILDPLATFORM", "linux/amd64"),
        ("TARGETOS", "linux"),
        ("TARGETARCH", "amd64"),
        (
            "GO_IMAGE",
            "golang:1.22-alpine@sha256:6d405dfc5fdf3a45df1529cf060b920041f52ce523487e0f36f02765af294a51",
        ),
        (
            "RUNTIME_IMAGE",
            "alpine:3.20@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e",
        ),
    ),
}
SUITE_IMAGE_ID_PLACEHOLDER = "__AILERON_SUITE_RUNNER_IMAGE_ID__"
SUITE_FAILURE_SCHEMA = "aileron-suite-failure/v1"
SUITE_FAILURE_STREAM_MAXIMUM_BYTES = 32 * 1024
SUITE_FAILURE_ARTIFACT_MAXIMUM_BYTES = 384 * 1024


class AcceptanceProducerError(RuntimeError):
    """Raised when fixed live probes cannot produce trusted evidence."""


class SoakPublicationError(AcceptanceProducerError):
    """Preserve both readback validation and rollback failures."""

    def __init__(self, failures: list[Exception]) -> None:
        self.failures = tuple(failures)
        super().__init__(
            "soak report readback validation and rollback failed: "
            + "; ".join(str(failure) for failure in self.failures)
        )


class SuiteExecutionError(AcceptanceProducerError):
    """Preserve every primary, cleanup, and immutable-source suite failure."""

    def __init__(
        self,
        suite_name: str,
        failures: list[dict[str, Any]],
        artifact: dict[str, str],
    ) -> None:
        self.suite_name = suite_name
        self.failures = failures
        self.artifact = artifact
        super().__init__(
            "isolated Compose suite failed: "
            + json.dumps(
                {"artifact": artifact, "failures": failures, "suite": suite_name},
                separators=(",", ":"),
                sort_keys=True,
            )
        )


class MaterializedSuiteSourceTransactionError(AcceptanceProducerError):
    """Report materialized-source primary and cleanup failures safely."""

    def __init__(self, failures: list[tuple[str, BaseException]]) -> None:
        self.failures = tuple(
            {"errorType": type(error).__name__, "phase": phase}
            for phase, error in failures
        )
        super().__init__(
            "materialized suite source transaction failed: "
            + json.dumps(
                {"failures": self.failures},
                separators=(",", ":"),
                sort_keys=True,
            )
        )


class OracleTransactionFailure(AcceptanceProducerError):
    """Preserve transaction failures without rendering sensitive exception text."""

    def __init__(self, failures: list[tuple[str, Exception]]) -> None:
        self.failures = tuple(failures)
        super().__init__(
            "oracle Job transaction failed: "
            + json.dumps(
                [
                    {"phase": phase, "errorType": type(error).__name__}
                    for phase, error in failures
                ],
                separators=(",", ":"),
                sort_keys=True,
            )
        )


class OracleTransactionIdentityError(AcceptanceProducerError):
    """Reject a fixed-name Job that is not the bound transaction object."""


class OracleDeleteClosureError(AcceptanceProducerError):
    """Stop retries after a REST delete was accepted but closure was not proven."""


class ProducerTargets(NamedTuple):
    context: str
    kubeconfig: Path
    workspace_id: str | None
    user_subject: str | None
    platform_url: str
    issuer_url: str
    admin_console_url: str | None
    client_id: str
    commit: str


class CommandResult(NamedTuple):
    stdout: bytes
    stderr: bytes
    returncode: int


class SuiteCommand(NamedTuple):
    name: str
    locale: str
    project_name: str
    command: list[str]
    cleanup_command: list[str]
    runner_image: str
    build_command: list[str]
    preflight_command: list[str] | None


class SuiteSource(NamedTuple):
    root: Path
    tree_sha256: str
    source: dict[str, Any]
    archive_command: list[str]


Runner = Callable[..., CommandResult]
Clock = Callable[[], datetime]
MonotonicClock = Callable[[], float]
Sleeper = Callable[[int], None]


def _load_local_module(name: str):
    path = SCRIPT_DIRECTORY / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AcceptanceProducerError(f"acceptance dependency is unavailable: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACCEPTANCE_CLUSTER = _load_local_module("acceptance_cluster")
ACCEPTANCE_EPOCH = _load_local_module("acceptance_epoch")
ACCEPTANCE_RELEASE = _load_local_module("acceptance_release")
ACCEPTANCE_SNAPSHOT = _load_local_module("acceptance_snapshot")
ACCEPTANCE_SOAK = _load_local_module("acceptance_soak")
BACKEND_ATTESTOR = _load_local_module("backend_attestor")
KUBERNETES_REST = _load_local_module("kubernetes_rest")
PRIVATE_IO = _load_local_module("acceptance_private_io")
RESET_INVENTORY = _load_local_module("collect_reset_inventory")
RUN_ID = PRIVATE_IO.RUN_ID


def _subprocess_runner(
    command: list[str], timeout_seconds: float | None = None
) -> CommandResult:
    timeout = timeout_seconds
    if timeout is None:
        timeout = (
            600 if "/app/e2e/acceptance.mjs" in " ".join(command) else 3600
        )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        return CommandResult(b"", b"acceptance command timed out\n", 124)
    return CommandResult(stdout, stderr, process.returncode)


def _read_private_bytes(
    path: Path,
    description: str,
    *,
    maximum_size: int = 4 * 1024 * 1024,
) -> bytes:
    return PRIVATE_IO.read_private_bytes(
        path,
        description,
        private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
        error_type=AcceptanceProducerError,
        maximum_size=maximum_size,
    )


def _write_private_snapshot(
    path: Path, content: bytes, *, allow_existing_exact: bool = False
) -> None:
    PRIVATE_IO.write_private_snapshot(
        destination=path,
        content=content,
        description="acceptance evidence",
        private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
        error_type=AcceptanceProducerError,
        allow_existing_exact=allow_existing_exact,
    )


def _fsync_private_directory(directory: Path) -> None:
    try:
        descriptor = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise AcceptanceProducerError(
            "acceptance evidence directory cannot be synchronized"
        ) from exc


def _unlink_private_snapshot(path: Path, description: str) -> None:
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise AcceptanceProducerError(f"{description} is not a regular file")
        path.unlink()
        _fsync_private_directory(path.parent)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise AcceptanceProducerError(f"{description} cannot be removed") from exc


def _atomic_recovery_metadata(
    path: Path, *, expected_link_count: int
) -> os.stat_result:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AcceptanceProducerError(
            "acceptance report recovery snapshot is unreadable"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(path)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
            or path_metadata.st_uid != os.geteuid()
            or metadata.st_nlink != expected_link_count
            or metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise AcceptanceProducerError(
                "acceptance report recovery snapshot metadata is invalid"
            )
        after = os.fstat(descriptor)
        path_after = os.lstat(path)
        if (
            metadata != after
            or after.st_dev != path_after.st_dev
            or after.st_ino != path_after.st_ino
        ):
            raise AcceptanceProducerError(
                "acceptance report recovery snapshot metadata changed"
            )
        return metadata
    except OSError as exc:
        raise AcceptanceProducerError(
            "acceptance report recovery snapshot changed while it was read"
        ) from exc
    finally:
        os.close(descriptor)


def recover_atomic_report_publication(
    destination: Path, *, private_root: Path | None = None
) -> bool:
    """Recover one bounded pre-link or post-link report publication state."""

    recovery_root = (
        ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
        if private_root is None
        else private_root
    )
    PRIVATE_IO.validate_private_directory(
        destination.parent,
        "acceptance report recovery directory",
        private_root=recovery_root,
        error_type=AcceptanceProducerError,
    )
    prefix = f".{destination.name}.tmp-"
    candidates = sorted(
        path for path in destination.parent.iterdir() if path.name.startswith(prefix)
    )
    if len(candidates) > 1 or any(
        re.fullmatch(r"[0-9a-f]{32}", path.name[len(prefix) :]) is None
        for path in candidates
    ):
        raise AcceptanceProducerError(
            "acceptance report recovery temporary state is invalid"
        )
    try:
        final_metadata = os.lstat(destination)
    except FileNotFoundError:
        final_metadata = None
    except OSError as exc:
        raise AcceptanceProducerError(
            "acceptance report recovery final state is unreadable"
        ) from exc
    if not candidates:
        return False
    temporary = candidates[0]
    if final_metadata is None:
        _atomic_recovery_metadata(temporary, expected_link_count=1)
        _unlink_private_snapshot(
            temporary,
            "acceptance report recovery temporary snapshot",
        )
        return False
    try:
        temporary_metadata = os.lstat(temporary)
    except OSError as exc:
        raise AcceptanceProducerError(
            "acceptance report recovery temporary state is unreadable"
        ) from exc
    if (
        final_metadata.st_dev != temporary_metadata.st_dev
        or final_metadata.st_ino != temporary_metadata.st_ino
    ):
        raise AcceptanceProducerError(
            "acceptance report recovery link identity is invalid"
        )
    linked_metadata = _atomic_recovery_metadata(destination, expected_link_count=2)
    _atomic_recovery_metadata(temporary, expected_link_count=2)
    _unlink_private_snapshot(
        temporary,
        "acceptance report recovery temporary snapshot",
    )
    recovered_metadata = _atomic_recovery_metadata(destination, expected_link_count=1)
    if (
        recovered_metadata.st_dev != linked_metadata.st_dev
        or recovered_metadata.st_ino != linked_metadata.st_ino
    ):
        raise AcceptanceProducerError(
            "acceptance report recovery final link identity changed"
        )
    PRIVATE_IO.read_private_bytes(
        destination,
        "recovered acceptance report",
        private_root=recovery_root,
        error_type=AcceptanceProducerError,
        maximum_size=4 * 1024 * 1024,
    )
    return True


def _recover_atomic_private_snapshot(destination: Path, content: bytes) -> bool:
    if not recover_atomic_report_publication(destination):
        return False
    if _read_private_bytes(destination, "recovered acceptance report") != content:
        raise AcceptanceProducerError(
            "acceptance report recovery final content is invalid"
        )
    return True


def _publish_private_snapshot_atomic(destination: Path, content: bytes) -> None:
    """Publish one durable write-once snapshot through a same-directory hard link."""

    if _recover_atomic_private_snapshot(destination, content):
        return
    temporary = destination.parent / (
        f".{destination.name}.tmp-{secrets.token_hex(16)}"
    )
    _write_private_snapshot(temporary, content)
    published = False
    primary_error: AcceptanceProducerError | None = None
    try:
        os.link(temporary, destination, follow_symlinks=False)
        published = True
        _fsync_private_directory(destination.parent)
        _unlink_private_snapshot(temporary, "acceptance report temporary snapshot")
        return
    except FileExistsError as exc:
        primary_error = AcceptanceProducerError(
            "acceptance evidence snapshot already exists"
        )
        primary_error.__cause__ = exc
    except AcceptanceProducerError as exc:
        primary_error = exc
    except OSError as exc:
        primary_error = AcceptanceProducerError(
            "acceptance evidence atomic link failed"
        )
        primary_error.__cause__ = exc

    cleanup_failures: list[Exception] = []
    if published:
        try:
            _unlink_private_snapshot(destination, "acceptance report snapshot")
        except AcceptanceProducerError as exc:
            cleanup_failures.append(exc)
    try:
        _unlink_private_snapshot(temporary, "acceptance report temporary snapshot")
    except AcceptanceProducerError as exc:
        cleanup_failures.append(exc)
    if cleanup_failures:
        assert primary_error is not None
        raise SoakPublicationError(
            [primary_error, *cleanup_failures]
        ) from cleanup_failures[-1]
    assert primary_error is not None
    raise primary_error


def _canonical(document: dict[str, Any]) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


def _canonical_browser_input_path(
    *, targets: ProducerTargets, deployment_run_id: str
) -> Path:
    if SHA.fullmatch(targets.commit) is None:
        raise AcceptanceProducerError("browser input commit is invalid")
    if RUN_ID.fullmatch(deployment_run_id) is None:
        raise AcceptanceProducerError("browser input deployment run ID is invalid")
    return (
        ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
        / "acceptance-inputs"
        / targets.commit
        / deployment_run_id
        / "browser-input.json"
    )


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON object key")
        document[key] = value
    return document


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-standard JSON constant")


def _valid_browser_user(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"username", "password"}:
        return False
    username = value.get("username")
    password = value.get("password")
    return (
        isinstance(username, str)
        and 1 <= len(username) <= 256
        and username == username.strip()
        and not any(
            ord(character) < 32 or ord(character) == 127 for character in username
        )
        and isinstance(password, str)
        and 1 <= len(password) <= 4096
        and not any(
            ord(character) < 32 or ord(character) == 127 for character in password
        )
    )


def _load_browser_input(
    *,
    targets: ProducerTargets,
    deployment_run_id: str,
    authentication_mode: str,
) -> dict[str, Any]:
    path = _canonical_browser_input_path(
        targets=targets,
        deployment_run_id=deployment_run_id,
    )
    input_bytes = _read_private_bytes(
        path, "canonical private browser acceptance input"
    )
    try:
        input_document = json.loads(
            input_bytes.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AcceptanceProducerError(
            "canonical private browser acceptance input is invalid JSON"
        ) from exc
    expected_keys = {"schemaVersion", "loginDriver", "loginUser"}
    expected_users = ("loginUser",)
    if authentication_mode == "bundledKeycloak":
        expected_keys.update({"breakGlassUser", "adminUser", "platformAdminUser"})
        expected_users = (
            "loginUser",
            "breakGlassUser",
            "adminUser",
            "platformAdminUser",
        )
    login_driver = (
        input_document.get("loginDriver") if isinstance(input_document, dict) else None
    )
    driver_valid = (
        authentication_mode == "bundledKeycloak"
        and login_driver == {"kind": "keycloak"}
    ) or (
        authentication_mode == "externalOidc"
        and isinstance(login_driver, dict)
        and set(login_driver)
        == {
            "kind",
            "usernameSelector",
            "passwordSelector",
            "submitSelector",
            "errorSelector",
        }
        and login_driver.get("kind") == "form"
        and all(
            isinstance(login_driver.get(field), str)
            and 1 <= len(login_driver[field]) <= 256
            and not any(
                ord(character) < 32 or ord(character) == 127
                for character in login_driver[field]
            )
            for field in (
                "usernameSelector",
                "passwordSelector",
                "submitSelector",
                "errorSelector",
            )
        )
    )
    if (
        not isinstance(input_document, dict)
        or set(input_document) != expected_keys
        or input_document.get("schemaVersion") != "aileron-browser-input/v2"
        or not driver_valid
        or any(
            not _valid_browser_user(input_document.get(name)) for name in expected_users
        )
        or input_bytes != _canonical(input_document) + b"\n"
    ):
        raise AcceptanceProducerError(
            "canonical private browser acceptance input schema is invalid"
        )
    return input_document


def _project_browser_input(*, section: str, input_document: dict[str, Any]) -> bytes:
    credential_keys = (
        ("breakGlassUser", "adminUser", "platformAdminUser")
        if section == "adminDisableLogin"
        else ("loginUser",)
    )
    projected = {
        "schemaVersion": input_document["schemaVersion"],
        "loginDriver": input_document["loginDriver"],
        **{key: input_document[key] for key in credential_keys},
    }
    return _canonical(projected) + b"\n"


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_validator():
    spec = importlib.util.spec_from_file_location("acceptance_evidence", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise AcceptanceProducerError("acceptance validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_existing_clean_reset_report(
    *,
    path: Path,
    validator: Any,
    contract: dict[str, Any],
    targets: ProducerTargets,
    epoch: dict[str, Any],
    signing_key: bytes,
    clock: Clock,
) -> Path | None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise AcceptanceProducerError("clean reset report is unreadable") from exc
    checkpoint = clock()
    try:
        validated = validator.validate_report_file(
            directory=path.parent,
            section="cleanReset",
            contract=contract,
            expected_commit=targets.commit,
            epoch=epoch,
            signing_key=signing_key,
            private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
            canonical_kubeconfig=targets.kubeconfig,
            workspace=None,
            now=checkpoint,
            must_finish_by=checkpoint,
        )
    except validator.AcceptanceEvidenceError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    return validated["path"]


def _require_predecessor_reports(
    *,
    section: str,
    directory: Path,
    validator: Any,
    contract: dict[str, Any],
    targets: ProducerTargets,
    epoch: dict[str, Any],
    signing_key: bytes,
    clock: Clock,
) -> None:
    checkpoint = clock()
    try:
        predecessors = validator.immediate_predecessors(
            contract, section, epoch["authenticationMode"]
        )
    except validator.AcceptanceEvidenceError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    for predecessor in predecessors:
        try:
            workspace = (
                {
                    "id": targets.workspace_id,
                    "userSubject": targets.user_subject,
                }
                if validator.report_scope(contract, predecessor) == "workspace"
                else None
            )
            validator.validate_report_file(
                directory=directory,
                section=predecessor,
                contract=contract,
                expected_commit=targets.commit,
                epoch=epoch,
                signing_key=signing_key,
                private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
                canonical_kubeconfig=targets.kubeconfig,
                workspace=workspace,
                now=checkpoint,
                must_finish_by=checkpoint,
            )
        except validator.AcceptanceEvidenceError as exc:
            raise AcceptanceProducerError(
                f"{predecessor} verified predecessor report is required"
            ) from exc


def build_oracle_job_manifest(
    *,
    section: str,
    targets: ProducerTargets,
    image: dict[str, str],
    run_id: str,
    deployment_run_id: str,
    signing_key: bytes,
) -> dict[str, Any]:
    """Build the fixed Job that runs the tracked oracle from the release image."""

    if (
        section not in ORACLE_SECTIONS
        or RUN_ID.fullmatch(run_id) is None
        or RUN_ID.fullmatch(deployment_run_id) is None
        or not isinstance(signing_key, bytes)
        or len(signing_key) != 32
    ):
        raise AcceptanceProducerError("oracle Job identity is invalid")
    namespace = "workspace-system"
    name = f"aileron-acceptance-{section.lower()}-{run_id[4:16]}"
    labels = {
        "platform.aileron.dev/acceptance-owner": "aileron-installer",
        "platform.aileron.dev/acceptance-section": section,
        "platform.aileron.dev/source-commit": targets.commit,
        "platform.aileron.dev/acceptance-run-id": run_id,
        "platform.aileron.dev/deployment-run-id": deployment_run_id,
    }
    if section in WORKSPACE_SCOPED_SECTIONS:
        if not targets.workspace_id:
            raise AcceptanceProducerError(
                "Workspace identity is required for this oracle section"
            )
        labels["platform.aileron.dev/workspace-id"] = targets.workspace_id
    annotations = {
        ORACLE_TRANSACTION_TOKEN_ANNOTATION: hmac.new(
            signing_key,
            b"aileron-acceptance-oracle-job/v1\0"
            + _canonical(
                {
                    "context": targets.context,
                    "deploymentRunId": deployment_run_id,
                    "name": name,
                    "namespace": namespace,
                    "runId": run_id,
                    "section": section,
                    "sourceCommit": targets.commit,
                    "workspaceId": (
                        targets.workspace_id
                        if section in WORKSPACE_SCOPED_SECTIONS
                        else None
                    ),
                }
            ),
            hashlib.sha256,
        ).hexdigest()
    }
    arguments = [
        "--section",
        section,
        "--context",
        targets.context,
        "--platform-url",
        targets.platform_url,
        "--issuer-url",
        targets.issuer_url,
        "--client-id",
        targets.client_id,
        "--commit",
        targets.commit,
        "--run-id",
        run_id,
    ]
    if section in WORKSPACE_SCOPED_SECTIONS:
        arguments.extend(["--workspace-id", targets.workspace_id])
    container = {
        "name": "oracle",
        "image": image["immutableImage"],
        "imagePullPolicy": "IfNotPresent",
        "command": [
            "/workspace-manager/.venv/bin/python",
            "/workspace-manager/scripts/acceptance_oracle.py",
        ],
        "args": arguments,
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
    }
    pod_spec = {
        "serviceAccountName": "aileron-acceptance-oracle",
        "automountServiceAccountToken": True,
        "restartPolicy": "Never",
        "imagePullSecrets": [{"name": "harbor-rke-creds"}],
        "securityContext": {
            "runAsNonRoot": True,
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        "containers": [container],
    }
    if section == "turn":
        pod_spec["securityContext"].update(
            {"fsGroup": 10001, "fsGroupChangePolicy": "OnRootMismatch"}
        )
        container["volumeMounts"] = [
            {
                "name": "turn-probe",
                "mountPath": "/run/secrets/turn-probe/probe-username",
                "subPath": "probe-username",
                "readOnly": True,
            },
            {
                "name": "turn-probe",
                "mountPath": "/run/secrets/turn-probe/turn-rest-shared-secret",
                "subPath": "turn-rest-shared-secret",
                "readOnly": True,
            },
        ]
        pod_spec["volumes"] = [
            {
                "name": "turn-probe",
                "secret": {
                    "secretName": "aileron-turn-ice",
                    "defaultMode": 0o440,
                    "items": [
                        {"key": "probe-username", "path": "probe-username"},
                        {
                            "key": "turn-rest-shared-secret",
                            "path": "turn-rest-shared-secret",
                        },
                    ],
                },
            }
        ]
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {"labels": labels},
                "spec": pod_spec,
            },
        },
    }


def _browser_attempt_prefix(*, section: str, run_id: str) -> str:
    if section not in BROWSER_SECTIONS:
        raise AcceptanceProducerError("browser acceptance section is invalid")
    if not isinstance(run_id, str) or RUN_ID.fullmatch(run_id) is None:
        raise AcceptanceProducerError("browser acceptance attempt identity is invalid")
    return f"{section}-{run_id}-browser"


def _valid_admin_console_url(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
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


def build_browser_probe_command(
    *,
    section: str,
    targets: ProducerTargets,
    browser_input: Path,
    run_id: str,
    browser_ca: Path | None = None,
    image_reference: str | None = None,
) -> list[str]:
    """Build the fixed tracked browser lifecycle probe command."""

    _browser_attempt_prefix(section=section, run_id=run_id)
    command = [
        "docker",
        "run",
        "--rm",
        "--name",
        (
            f"aileron-acceptance-{section.lower()}-"
            f"{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
        ),
        "--network",
        "host",
        "--mount",
        (
            f"type=bind,source={browser_input},"
            "target=/run/secrets/acceptance-browser.json,readonly"
        ),
    ]
    image = image_reference or f"{BROWSER_IMAGE_REPOSITORY}:{targets.commit}"
    arguments = [
        "--section",
        section,
        "--platform-url",
        targets.platform_url,
        "--issuer-url",
        targets.issuer_url,
        "--client-id",
        targets.client_id,
        "--run-id",
        run_id,
    ]
    if section == "adminDisableLogin":
        if not _valid_admin_console_url(targets.admin_console_url):
            raise AcceptanceProducerError(
                "adminDisableLogin requires a valid HTTPS admin console URL"
            )
        arguments.extend(["--admin-console-url", targets.admin_console_url])
    if section in {"workspaceLifecycle", "terminal", "http", "browser", "websocket"}:
        if not targets.workspace_id:
            raise AcceptanceProducerError(
                "Workspace identity is required for authenticated browser probes"
            )
        arguments.extend(["--workspace-id", targets.workspace_id])
    if browser_ca is None:
        command.extend([image, "node", "/app/e2e/acceptance.mjs", *arguments])
    else:
        command.extend(
            [
                "--mount",
                (
                    f"type=bind,source={browser_ca},"
                    "target=/usr/local/share/ca-certificates/aileron-acceptance-ca.crt,readonly"
                ),
                image,
                "sh",
                "-ec",
                (
                    "update-ca-certificates >/dev/null && "
                    "export NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/aileron-acceptance-ca.crt && "
                    'mkdir -p "$HOME/.pki/nssdb" && '
                    'if [ ! -f "$HOME/.pki/nssdb/cert9.db" ]; then '
                    'certutil -N -d sql:"$HOME/.pki/nssdb" --empty-password; '
                    "fi && "
                    'certutil -D -d sql:"$HOME/.pki/nssdb" -n aileron-acceptance '
                    "2>/dev/null || true; "
                    'certutil -A -d sql:"$HOME/.pki/nssdb" '
                    "-n aileron-acceptance -t C,, -a "
                    "-i /usr/local/share/ca-certificates/aileron-acceptance-ca.crt && "
                    "exec node "
                    '/app/e2e/acceptance.mjs "$@"'
                ),
                "acceptance-browser",
                *arguments,
            ]
        )
    return command


def browser_git_status_command() -> list[str]:
    """Return the fixed clean-checkout command for browser acceptance."""

    return ["git", "status", "--porcelain=v1", "--untracked-files=all"]


def browser_source_commands(commit: str) -> list[list[str]]:
    """Return fixed commands that bind the browser probe to one Git commit."""

    return [
        browser_git_status_command(),
        ["git", "rev-parse", "HEAD"],
        ["git", "show", f"{commit}:{BROWSER_PROBE_PATH}"],
    ]


def verify_browser_probe_source(
    *, targets: ProducerTargets, runner: Runner
) -> dict[str, str]:
    """Reject mutable or cross-commit browser probe source."""

    status_command, head_command, show_command = browser_source_commands(targets.commit)
    status = _run_checked(runner, status_command)
    if status.stdout:
        raise AcceptanceProducerError(
            "browser acceptance requires a clean Git checkout"
        )
    head = _run_checked(runner, head_command).stdout.decode("utf-8").strip()
    if head != targets.commit:
        raise AcceptanceProducerError(
            "browser acceptance checkout does not match the requested commit"
        )
    tracked_script = _run_checked(runner, show_command).stdout
    local_script = (REPOSITORY_ROOT / BROWSER_PROBE_PATH).read_bytes()
    if tracked_script != local_script:
        raise AcceptanceProducerError(
            "browser acceptance script does not match the requested commit"
        )
    return {"scriptSha256": hashlib.sha256(local_script).hexdigest()}


def _compose_project_name(name: str, targets: ProducerTargets, run_id: str) -> str:
    if RUN_ID.fullmatch(run_id) is None:
        raise AcceptanceProducerError("suite run identity is invalid")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    run_digest = hashlib.sha256(run_id.encode()).hexdigest()[:8]
    return f"aileron-{slug}-{targets.commit[:12]}-{run_digest}"[:63].rstrip("-")


def _suite_runner_image(name: str, targets: ProducerTargets, run_id: str) -> str:
    suffix = hashlib.sha256(f"{run_id}:{name}".encode()).hexdigest()[:12]
    return f"{SUITE_RUNNER_REPOSITORIES[name]}:{targets.commit}-{suffix}"


def _compose_suite_command(
    *,
    name: str,
    locale: str,
    targets: ProducerTargets,
    run_id: str,
    compose_file: str,
    service: str,
    source_root: Path | None = None,
    preflight_command: list[str] | None = None,
) -> SuiteCommand:
    project_name = _compose_project_name(name, targets, run_id)
    runner_image = _suite_runner_image(name, targets, run_id)
    root = source_root or REPOSITORY_ROOT
    build_context, dockerfile, target = SUITE_BUILD_TARGETS[name]
    build_command = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--file",
        str(root / dockerfile),
        "--tag",
        runner_image,
        "--build-arg",
        f"SOURCE_REVISION={targets.commit}",
    ]
    for argument_name, argument_value in SUITE_BUILD_ARGUMENTS.get(name, ()):
        build_command.extend(["--build-arg", f"{argument_name}={argument_value}"])
    if target is not None:
        build_command.extend(["--target", target])
    build_command.append(str((root / build_context).resolve()))
    environment = [
        *HERMETIC_COMPOSE_ENVIRONMENT,
        f"AILERON_SOURCE_REVISION={targets.commit}",
        f"AILERON_SUITE_SOURCE_ROOT={root}",
        f"{SUITE_IMAGE_ENVIRONMENT[name]}={SUITE_IMAGE_ID_PLACEHOLDER}",
    ]
    compose = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        project_name,
        "--file",
        str(root / compose_file),
    ]
    return SuiteCommand(
        name,
        locale,
        project_name,
        [*environment, *compose, "run", "--pull", "never", "--rm", service],
        [*environment, *compose, "down", "--volumes", "--remove-orphans"],
        runner_image,
        build_command,
        preflight_command,
    )


def build_offline_oidc_conformance_command(
    targets: ProducerTargets, run_id: str, source_root: Path | None = None
) -> SuiteCommand:
    """Return the isolated provider-neutral offline OIDC contract test."""

    return _compose_suite_command(
        name="platform-conformance",
        locale="none",
        targets=targets,
        run_id=run_id,
        compose_file=(
            "scripts/test/kubernetes/product-conformance/docker-compose.test.yml"
        ),
        service="product-conformance-test",
        source_root=source_root,
    )


def _remove_known_default(document: dict[str, Any], key: str, value: Any) -> bool:
    if key not in document:
        return True
    if document[key] != value:
        return False
    del document[key]
    return True


def _normalize_pod_spec_defaults(spec: dict[str, Any]) -> bool:
    defaults = {
        "dnsPolicy": "ClusterFirst",
        "schedulerName": "default-scheduler",
        "terminationGracePeriodSeconds": 30,
    }
    if any(
        not _remove_known_default(spec, key, value) for key, value in defaults.items()
    ):
        return False
    containers = spec.get("containers")
    if not isinstance(containers, list):
        return False
    for container in containers:
        if not isinstance(container, dict):
            return False
        if not _remove_known_default(
            container, "terminationMessagePath", "/dev/termination-log"
        ) or not _remove_known_default(container, "terminationMessagePolicy", "File"):
            return False
        if not _remove_known_default(container, "resources", {}):
            return False
    return True


def _canonical_job_spec(
    expected: dict[str, Any], actual: Any, *, job_uid: str, job_name: str
) -> bool:
    if not isinstance(actual, dict):
        return False
    normalized = copy.deepcopy(actual)
    defaults = {
        "completionMode": "NonIndexed",
        "completions": 1,
        "manualSelector": False,
        "parallelism": 1,
        "suspend": False,
    }
    if any(
        not _remove_known_default(normalized, key, value)
        for key, value in defaults.items()
    ):
        return False
    if normalized.pop("podReplacementPolicy", None) != "TerminatingOrFailed":
        return False
    selector = normalized.pop("selector", None)
    if selector != {"matchLabels": {"batch.kubernetes.io/controller-uid": job_uid}}:
        return False
    template = normalized.get("template")
    if not isinstance(template, dict):
        return False
    metadata = template.get("metadata")
    if not isinstance(metadata, dict):
        return False
    if not _remove_known_default(metadata, "creationTimestamp", None):
        return False
    labels = metadata.get("labels")
    expected_labels = expected["template"]["metadata"]["labels"]
    controller_labels = {
        "batch.kubernetes.io/controller-uid": job_uid,
        "batch.kubernetes.io/job-name": job_name,
        "controller-uid": job_uid,
        "job-name": job_name,
    }
    if labels != {**expected_labels, **controller_labels}:
        return False
    metadata["labels"] = expected_labels
    pod_spec = template.get("spec")
    if not isinstance(pod_spec, dict) or not _normalize_pod_spec_defaults(pod_spec):
        return False
    service_account = pod_spec.get("serviceAccountName")
    if (
        not isinstance(service_account, str)
        or not service_account
        or not _remove_known_default(pod_spec, "serviceAccount", service_account)
    ):
        return False
    return normalized == expected


def _remove_service_account_projection(spec: dict[str, Any]) -> bool:
    service_account = spec.get("serviceAccountName")
    if not isinstance(service_account, str) or not service_account:
        return False
    if not _remove_known_default(spec, "serviceAccount", service_account):
        return False
    volumes = spec.pop("volumes", None)
    containers = spec.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        return False
    container = containers[0]
    if not isinstance(container, dict):
        return False
    mounts = container.pop("volumeMounts", None)
    if mounts is not None and not isinstance(mounts, list):
        return False
    if volumes is None:
        return mounts is None
    if not isinstance(volumes, list):
        return False
    projection_indexes = [
        index
        for index, volume in enumerate(volumes)
        if isinstance(volume, dict)
        and isinstance(volume.get("name"), str)
        and re.fullmatch(r"kube-api-access-[a-z0-9]{5}", volume["name"])
    ]
    if len(projection_indexes) != 1:
        return False
    projection = volumes[projection_indexes[0]]
    name = projection["name"]
    expected_projection = {
        "defaultMode": 420,
        "sources": [
            {"serviceAccountToken": {"expirationSeconds": 3607, "path": "token"}},
            {
                "configMap": {
                    "items": [{"key": "ca.crt", "path": "ca.crt"}],
                    "name": "kube-root-ca.crt",
                }
            },
            {
                "downwardAPI": {
                    "items": [
                        {
                            "fieldRef": {
                                "apiVersion": "v1",
                                "fieldPath": "metadata.namespace",
                            },
                            "path": "namespace",
                        }
                    ]
                }
            },
        ],
    }
    if projection.get("projected") != expected_projection or set(projection) != {
        "name",
        "projected",
    }:
        return False
    del volumes[projection_indexes[0]]
    if volumes:
        spec["volumes"] = volumes
    if mounts is None:
        return False
    service_account_mount = {
        "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
        "name": name,
        "readOnly": True,
    }
    mount_indexes = [
        index for index, mount in enumerate(mounts) if mount == service_account_mount
    ]
    if len(mount_indexes) != 1:
        return False
    del mounts[mount_indexes[0]]
    if mounts:
        container["volumeMounts"] = mounts
    return True


def _canonical_pod_spec(expected: dict[str, Any], actual: Any) -> bool:
    if not isinstance(actual, dict):
        return False
    normalized = copy.deepcopy(actual)
    if not _normalize_pod_spec_defaults(normalized):
        return False
    defaults = {
        "enableServiceLinks": True,
        "preemptionPolicy": "PreemptLowerPriority",
        "priority": 0,
    }
    if any(
        not _remove_known_default(normalized, key, value)
        for key, value in defaults.items()
    ):
        return False
    node_name = normalized.pop("nodeName", None)
    if node_name is not None and (not isinstance(node_name, str) or not node_name):
        return False
    default_tolerations = [
        {
            "effect": "NoExecute",
            "key": "node.kubernetes.io/not-ready",
            "operator": "Exists",
            "tolerationSeconds": 300,
        },
        {
            "effect": "NoExecute",
            "key": "node.kubernetes.io/unreachable",
            "operator": "Exists",
            "tolerationSeconds": 300,
        },
    ]
    if not _remove_known_default(normalized, "tolerations", default_tolerations):
        return False
    if not _remove_service_account_projection(normalized):
        return False
    return normalized == expected


def _oracle_timestamp(value: Any) -> datetime | None:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z",
            value,
        )
        is None
    ):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return None
    return parsed


def _oracle_job_completion_time(status: Any) -> tuple[str, datetime] | None:
    if not isinstance(status, dict):
        return None
    succeeded = status.get("succeeded")
    active = status.get("active", 0)
    failed = status.get("failed", 0)
    completion_time = status.get("completionTime")
    parsed_completion = _oracle_timestamp(completion_time)
    conditions = status.get("conditions")
    if (
        isinstance(succeeded, bool)
        or succeeded != 1
        or isinstance(active, bool)
        or active != 0
        or isinstance(failed, bool)
        or failed != 0
        or parsed_completion is None
        or not isinstance(conditions, list)
        or len(conditions) not in (1, 2)
    ):
        return None
    allowed_condition_keys = {
        "type",
        "status",
        "lastProbeTime",
        "lastTransitionTime",
        "reason",
        "message",
    }
    allowed_condition_types = {"Complete", "SuccessCriteriaMet"}
    condition_types: set[str] = set()
    for condition in conditions:
        if not isinstance(condition, dict):
            return None
        condition_type = condition.get("type")
        transition_time = _oracle_timestamp(condition.get("lastTransitionTime"))
        probe_time = condition.get("lastProbeTime")
        if (
            not {"type", "status", "lastTransitionTime"}.issubset(condition)
            or not set(condition).issubset(allowed_condition_keys)
            or condition_type not in allowed_condition_types
            or condition_type in condition_types
            or condition.get("status") != "True"
            or transition_time is None
            or transition_time > parsed_completion
            or (probe_time is not None and _oracle_timestamp(probe_time) is None)
            or any(
                key in condition
                and (not isinstance(condition[key], str) or not condition[key])
                for key in ("reason", "message")
            )
        ):
            return None
        condition_types.add(condition_type)
    if "Complete" not in condition_types:
        return None
    return completion_time, parsed_completion


def _validate_oracle_job_cleanup_identity(*, manifest: dict[str, Any], job: Any) -> str:
    """Return the UID only for this HMAC-bound oracle transaction."""

    expected_metadata = manifest.get("metadata")
    metadata = job.get("metadata") if isinstance(job, dict) else None
    expected_labels = (
        expected_metadata.get("labels") if isinstance(expected_metadata, dict) else None
    )
    expected_annotations = (
        expected_metadata.get("annotations")
        if isinstance(expected_metadata, dict)
        else None
    )
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    uid = metadata.get("uid") if isinstance(metadata, dict) else None
    expected_token = (
        expected_annotations.get(ORACLE_TRANSACTION_TOKEN_ANNOTATION)
        if isinstance(expected_annotations, dict)
        else None
    )
    actual_token = (
        annotations.get(ORACLE_TRANSACTION_TOKEN_ANNOTATION)
        if isinstance(annotations, dict)
        else None
    )
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(expected_labels, dict)
        or not isinstance(expected_token, str)
        or FILE_DIGEST.fullmatch(expected_token) is None
        or not isinstance(job, dict)
        or job.get("apiVersion") != "batch/v1"
        or job.get("kind") != "Job"
        or not isinstance(metadata, dict)
        or metadata.get("name") != expected_metadata.get("name")
        or metadata.get("namespace") != expected_metadata.get("namespace")
        or not isinstance(uid, str)
        or not uid
        or not isinstance(labels, dict)
        or any(labels.get(key) != value for key, value in expected_labels.items())
        or not isinstance(annotations, dict)
        or not isinstance(actual_token, str)
        or not hmac.compare_digest(actual_token, expected_token)
    ):
        raise AcceptanceProducerError("oracle Job cleanup identity is invalid")
    return uid


def _validate_oracle_job_spec_identity(
    *, manifest: dict[str, Any], job: dict[str, Any]
) -> str:
    expected_labels = manifest["metadata"]["labels"]
    expected_annotations = manifest["metadata"]["annotations"]
    job_metadata = job.get("metadata") if isinstance(job, dict) else None
    job_uid = _validate_oracle_job_cleanup_identity(
        manifest=manifest,
        job=job,
    )
    if (
        not isinstance(job, dict)
        or job.get("apiVersion") != "batch/v1"
        or job.get("kind") != "Job"
        or not isinstance(job_metadata, dict)
        or job_metadata.get("name") != manifest["metadata"]["name"]
        or job_metadata.get("namespace") != manifest["metadata"]["namespace"]
        or job_metadata.get("labels") != expected_labels
        or job_metadata.get("annotations") != expected_annotations
        or job_metadata.get("ownerReferences", []) != []
        or "deletionTimestamp" in job_metadata
        or not _canonical_job_spec(
            manifest["spec"],
            job.get("spec"),
            job_uid=job_uid,
            job_name=manifest["metadata"]["name"],
        )
    ):
        raise AcceptanceProducerError("oracle Job spec identity is invalid")
    return job_uid


def _require_oracle_job_generation(
    *, manifest: dict[str, Any], job: dict[str, Any], expected_uid: str
) -> None:
    if (
        not isinstance(expected_uid, str)
        or not expected_uid
        or _validate_oracle_job_spec_identity(manifest=manifest, job=job)
        != expected_uid
    ):
        raise AcceptanceProducerError("oracle Job changed identity during execution")


def _oracle_exact_job_inventory_command(*, kubectl: list[str], name: str) -> list[str]:
    return [
        *kubectl,
        "get",
        "jobs",
        f"--field-selector=metadata.name={name}",
        "--output=json",
    ]


def _recover_created_oracle_job_uid(
    *,
    manifest: dict[str, Any],
    kubectl: list[str],
    runner: Runner,
) -> str | None:
    """Recover only this transaction-owned Job after an ambiguous create result."""

    command = _oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=manifest["metadata"]["name"],
    )
    result = _run_checked(runner, command)
    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "ambiguous oracle create Job inventory is invalid JSON"
        ) from exc
    items = inventory.get("items") if isinstance(inventory, dict) else None
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or not isinstance(items, list)
        or len(items) > 1
    ):
        raise AcceptanceProducerError(
            "ambiguous oracle create Job inventory is invalid"
        )
    if not items:
        return None
    try:
        return _validate_oracle_job_cleanup_identity(
            manifest=manifest,
            job=items[0],
        )
    except AcceptanceProducerError as exc:
        raise OracleTransactionIdentityError(
            "ambiguous oracle create belongs to a foreign transaction"
        ) from exc


def _require_oracle_pod_selector_absent(
    *,
    kubectl: list[str],
    selector: str,
    runner: Runner,
) -> None:
    command = [*kubectl, "get", "pods", f"--selector={selector}", "--output=json"]
    result = _run_checked(runner, command)
    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "oracle transaction Pod absence inventory is invalid JSON"
        ) from exc
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or inventory.get("items") != []
    ):
        raise AcceptanceProducerError(
            "oracle transaction Pod absence inventory is invalid or nonempty"
        )


def _reconcile_failed_oracle_transaction(
    *,
    manifest: dict[str, Any],
    kubectl: list[str],
    directory: Path,
    created_uid: str | None,
    source_prefix: str,
    delete_client: Any,
    runner: Runner,
) -> list[dict[str, Any]]:
    """Bound retries while deleting only the exact transaction-owned Job UID."""

    name = manifest["metadata"]["name"]
    bound_uid = created_uid
    failures: list[tuple[str, Exception]] = []
    for attempt in range(1, ORACLE_TRANSACTION_RECONCILE_ATTEMPTS + 1):
        phase = f"recovery-{attempt}"
        try:
            observed_uid = _recover_created_oracle_job_uid(
                manifest=manifest,
                kubectl=kubectl,
                runner=runner,
            )
            if observed_uid is not None:
                if bound_uid is not None and observed_uid != bound_uid:
                    raise OracleTransactionIdentityError(
                        "oracle Job was replaced before transaction cleanup"
                    )
                bound_uid = observed_uid
                phase = f"cleanup-{attempt}"
                return _delete_oracle_job(
                    manifest=manifest,
                    kubectl=kubectl,
                    directory=directory,
                    uid=bound_uid,
                    source_prefix=source_prefix,
                    delete_client=delete_client,
                    runner=runner,
                )

            phase = f"absence-{attempt}"
            if bound_uid is not None:
                _require_oracle_pod_selector_absent(
                    kubectl=kubectl,
                    selector=f"batch.kubernetes.io/controller-uid={bound_uid}",
                    runner=runner,
                )
            _require_oracle_pod_selector_absent(
                kubectl=kubectl,
                selector=f"batch.kubernetes.io/job-name={name}",
                runner=runner,
            )
            phase = f"recovery-confirmation-{attempt}"
            confirmed_uid = _recover_created_oracle_job_uid(
                manifest=manifest,
                kubectl=kubectl,
                runner=runner,
            )
            if confirmed_uid is None:
                return []
            if bound_uid is not None and confirmed_uid != bound_uid:
                raise OracleTransactionIdentityError(
                    "oracle Job was replaced during transaction cleanup"
                )
            bound_uid = confirmed_uid
            phase = f"cleanup-{attempt}"
            return _delete_oracle_job(
                manifest=manifest,
                kubectl=kubectl,
                directory=directory,
                uid=bound_uid,
                source_prefix=source_prefix,
                delete_client=delete_client,
                runner=runner,
            )
        except OracleDeleteClosureError as exc:
            raise OracleTransactionFailure([*failures, (phase, exc)]) from None
        except OracleTransactionIdentityError as exc:
            raise OracleTransactionFailure([*failures, (phase, exc)]) from None
        except Exception as exc:  # noqa: BLE001
            failures.append((phase, exc))
            if attempt < ORACLE_TRANSACTION_RECONCILE_ATTEMPTS:
                time.sleep(ORACLE_TRANSACTION_RECONCILE_INTERVAL_SECONDS)
    raise OracleTransactionFailure(failures) from None


def validate_oracle_job_identity(
    *,
    manifest: dict[str, Any],
    job: dict[str, Any],
    pods: dict[str, Any],
    immutable_image: str,
    allowed_image_digests: set[str],
) -> dict[str, Any]:
    """Return the sole owned Pod after validating the fixed Job identity."""

    expected_labels = manifest["metadata"]["labels"]
    job_uid = _validate_oracle_job_spec_identity(manifest=manifest, job=job)
    completion = _oracle_job_completion_time(job.get("status"))
    if completion is None:
        raise AcceptanceProducerError("oracle Job completion identity is invalid")

    pod_items = pods.get("items") if isinstance(pods, dict) else None
    if (
        not isinstance(pods, dict)
        or pods.get("apiVersion") != "v1"
        or pods.get("kind") != "List"
        or not isinstance(pod_items, list)
        or len(pod_items) != 1
    ):
        raise AcceptanceProducerError("oracle Job must own exactly one Pod")
    pod = pod_items[0]
    metadata = pod.get("metadata") if isinstance(pod, dict) else None
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    owner_references = (
        metadata.get("ownerReferences") if isinstance(metadata, dict) else None
    )
    expected_owner = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "name": manifest["metadata"]["name"],
        "uid": job_uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }
    expected_pod_labels = {
        **expected_labels,
        "job-name": manifest["metadata"]["name"],
        "controller-uid": job_uid,
    }
    server_pod_labels = {
        **expected_pod_labels,
        "batch.kubernetes.io/job-name": manifest["metadata"]["name"],
        "batch.kubernetes.io/controller-uid": job_uid,
    }
    statuses = pod.get("status", {}).get("containerStatuses")
    image_digest = immutable_image.rsplit("@", 1)[1]
    if (
        re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        or not isinstance(allowed_image_digests, set)
        or len(allowed_image_digests) != 2
        or image_digest not in allowed_image_digests
        or any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            for digest in allowed_image_digests
        )
    ):
        raise AcceptanceProducerError("oracle signed image digest set is invalid")
    status = statuses[0] if isinstance(statuses, list) and len(statuses) == 1 else None
    state = status.get("state") if isinstance(status, dict) else None
    terminated = state.get("terminated") if isinstance(state, dict) else None
    container_id = status.get("containerID") if isinstance(status, dict) else None
    terminated_started = (
        _oracle_timestamp(terminated.get("startedAt"))
        if isinstance(terminated, dict)
        else None
    )
    terminated_finished = (
        _oracle_timestamp(terminated.get("finishedAt"))
        if isinstance(terminated, dict)
        else None
    )
    if (
        not isinstance(pod, dict)
        or pod.get("apiVersion") != "v1"
        or pod.get("kind") != "Pod"
        or not isinstance(metadata, dict)
        or not isinstance(metadata.get("name"), str)
        or not metadata["name"].startswith(f"{manifest['metadata']['name']}-")
        or not isinstance(metadata.get("uid"), str)
        or not metadata["uid"]
        or metadata.get("namespace") != manifest["metadata"]["namespace"]
        or "deletionTimestamp" in metadata
        or not isinstance(labels, dict)
        or labels != server_pod_labels
        or owner_references != [expected_owner]
        or not _canonical_pod_spec(
            manifest["spec"]["template"]["spec"], pod.get("spec")
        )
        or pod.get("status", {}).get("phase") != "Succeeded"
        or not isinstance(status, dict)
        or status.get("name") != "oracle"
        or status.get("restartCount") != 0
        or not _container_status_image_matches_requested(
            status.get("image"), immutable_image
        )
        or not isinstance(status.get("imageID"), str)
        or (
            image_id_match := re.fullmatch(
                r"(?:[a-z][a-z0-9+.-]*://)?(?P<repository>[^\s@]+)@"
                r"(?P<digest>sha256:[0-9a-f]{64})",
                status["imageID"],
            )
        )
        is None
        or image_id_match.group("repository") != immutable_image.rsplit("@", 1)[0]
        or image_id_match.group("digest") not in allowed_image_digests
        or not isinstance(container_id, str)
        or re.fullmatch(r"containerd://[0-9a-f]{64}", container_id) is None
        or not isinstance(state, dict)
        or set(state) != {"terminated"}
        or not isinstance(terminated, dict)
        or set(terminated)
        != {"containerID", "exitCode", "reason", "startedAt", "finishedAt"}
        or terminated.get("containerID") != container_id
        or terminated.get("exitCode") != 0
        or terminated.get("reason") != "Completed"
        or terminated_started is None
        or terminated_finished is None
        or terminated_started > terminated_finished
        or terminated_finished > completion[1]
    ):
        raise AcceptanceProducerError(
            "oracle Pod spec, ownership, image, or completion identity is invalid"
        )
    return pod


def _container_status_image_matches_requested(value: Any, requested_image: str) -> bool:
    """Accept Kubernetes' digest-only status image representation.

    RKE2/containerd can expose the image config digest in
    ``containerStatuses[].image`` while ``imageID`` retains the repository and
    signed manifest digest. The Pod spec and imageID checks remain the
    authoritative request and runtime provenance checks.
    """

    return value == requested_image or (
        isinstance(value, str) and KUBERNETES_STATUS_IMAGE.fullmatch(value) is not None
    )


def _require_oracle_pod_generation(
    *,
    manifest: dict[str, Any],
    job: dict[str, Any],
    pod: dict[str, Any],
    expected_uid: str,
    immutable_image: str,
    allowed_image_digests: set[str],
) -> dict[str, Any]:
    validated = validate_oracle_job_identity(
        manifest=manifest,
        job=job,
        pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
        immutable_image=immutable_image,
        allowed_image_digests=allowed_image_digests,
    )
    metadata = validated.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("uid") != expected_uid:
        raise AcceptanceProducerError(
            "oracle Pod changed identity during log collection"
        )
    return validated


def _oracle_cleanup_selector(
    *,
    section: str,
    targets: ProducerTargets,
    deployment_run_id: str,
) -> str:
    labels = [
        "platform.aileron.dev/acceptance-owner=aileron-installer",
        f"platform.aileron.dev/acceptance-section={section}",
        f"platform.aileron.dev/source-commit={targets.commit}",
        f"platform.aileron.dev/deployment-run-id={deployment_run_id}",
    ]
    if section in WORKSPACE_SCOPED_SECTIONS:
        if not targets.workspace_id:
            raise AcceptanceProducerError(
                "Workspace identity is required for oracle cleanup"
            )
        labels.append(f"platform.aileron.dev/workspace-id={targets.workspace_id}")
    return ",".join(labels)


def _owned_oracle_jobs(
    *,
    document: Any,
    section: str,
    targets: ProducerTargets,
    deployment_run_id: str,
    namespace: str,
    image: dict[str, str],
    signing_key: bytes,
) -> list[tuple[str, str, dict[str, Any]]]:
    items = document.get("items") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "v1"
        or document.get("kind") != "List"
        or not isinstance(items, list)
    ):
        raise AcceptanceProducerError("owned oracle Job inventory is invalid")
    jobs: list[tuple[str, str, dict[str, Any]]] = []
    names: set[str] = set()
    uids: set[str] = set()
    for item in items:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        labels = metadata.get("labels") if isinstance(metadata, dict) else None
        run_id = (
            labels.get("platform.aileron.dev/acceptance-run-id")
            if isinstance(labels, dict)
            else None
        )
        name = metadata.get("name") if isinstance(metadata, dict) else None
        uid = metadata.get("uid") if isinstance(metadata, dict) else None
        expected_manifest = (
            build_oracle_job_manifest(
                section=section,
                targets=targets,
                image=image,
                run_id=run_id,
                deployment_run_id=deployment_run_id,
                signing_key=signing_key,
            )
            if isinstance(run_id, str) and RUN_ID.fullmatch(run_id) is not None
            else None
        )
        if (
            not isinstance(item, dict)
            or not isinstance(metadata, dict)
            or item.get("apiVersion") != "batch/v1"
            or item.get("kind") != "Job"
            or metadata.get("namespace") != namespace
            or not isinstance(uid, str)
            or not uid
            or name in names
            or uid in uids
            or expected_manifest is None
        ):
            raise AcceptanceProducerError("owned oracle Job inventory is invalid")
        try:
            cleanup_uid = _validate_oracle_job_cleanup_identity(
                manifest=expected_manifest,
                job=item,
            )
        except AcceptanceProducerError as exc:
            raise AcceptanceProducerError(
                "owned oracle Job inventory is invalid"
            ) from exc
        if cleanup_uid != uid:
            raise AcceptanceProducerError("owned oracle Job inventory is invalid")
        names.add(name)
        uids.add(uid)
        jobs.append((name, uid, expected_manifest))
    return sorted(jobs, key=lambda job: job[:2])


def _oracle_delete_closure_items(
    *,
    result: CommandResult,
    description: str,
) -> list[dict[str, Any]]:
    inventory_description = (
        "deleted oracle Job inventory"
        if description == "Job"
        else "deleted oracle Job Pod inventory"
    )
    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            f"{inventory_description} is invalid JSON"
        ) from exc
    items = inventory.get("items") if isinstance(inventory, dict) else None
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or not isinstance(items, list)
        or any(not isinstance(item, dict) for item in items)
    ):
        raise AcceptanceProducerError(f"{inventory_description} is invalid")
    return items


def _oracle_delete_closure_job_absent(
    *,
    result: CommandResult,
    manifest: dict[str, Any],
    expected_uid: str,
) -> bool:
    items = _oracle_delete_closure_items(result=result, description="Job")
    if len(items) > 1:
        raise AcceptanceProducerError(
            "deleted oracle Job inventory is invalid or ambiguous"
        )
    if not items:
        return True
    try:
        observed_uid = _validate_oracle_job_cleanup_identity(
            manifest=manifest,
            job=items[0],
        )
    except AcceptanceProducerError as exc:
        raise OracleTransactionIdentityError(
            "deleted oracle Job belongs to a foreign transaction"
        ) from exc
    if observed_uid != expected_uid:
        raise OracleTransactionIdentityError(
            "deleted oracle Job was replaced during closure"
        )
    deletion_timestamp = items[0]["metadata"].get("deletionTimestamp")
    if deletion_timestamp is not None and _oracle_timestamp(deletion_timestamp) is None:
        raise AcceptanceProducerError(
            "deleted oracle Job termination identity is invalid"
        )
    return False


def _oracle_delete_closure_pods_absent(
    *,
    result: CommandResult,
    manifest: dict[str, Any],
    expected_uid: str,
) -> bool:
    items = _oracle_delete_closure_items(result=result, description="Pod")
    expected_labels = manifest["metadata"]["labels"]
    name = manifest["metadata"]["name"]
    namespace = manifest["metadata"]["namespace"]
    expected_owner = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "name": name,
        "uid": expected_uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }
    identities: set[tuple[str, str]] = set()
    for pod in items:
        metadata = pod.get("metadata")
        labels = metadata.get("labels") if isinstance(metadata, dict) else None
        pod_name = metadata.get("name") if isinstance(metadata, dict) else None
        pod_uid = metadata.get("uid") if isinstance(metadata, dict) else None
        deletion_timestamp = (
            metadata.get("deletionTimestamp") if isinstance(metadata, dict) else None
        )
        identity = (pod_name, pod_uid)
        if (
            pod.get("apiVersion") != "v1"
            or pod.get("kind") != "Pod"
            or not isinstance(metadata, dict)
            or metadata.get("namespace") != namespace
            or not isinstance(pod_name, str)
            or not pod_name
            or not isinstance(pod_uid, str)
            or not pod_uid
            or identity in identities
            or not isinstance(labels, dict)
            or any(labels.get(key) != value for key, value in expected_labels.items())
            or labels.get("batch.kubernetes.io/controller-uid") != expected_uid
            or labels.get("batch.kubernetes.io/job-name") != name
            or labels.get("controller-uid") != expected_uid
            or labels.get("job-name") != name
            or metadata.get("ownerReferences") != [expected_owner]
            or (
                deletion_timestamp is not None
                and _oracle_timestamp(deletion_timestamp) is None
            )
        ):
            raise OracleTransactionIdentityError(
                "deleted oracle Job Pod belongs to a foreign transaction"
            )
        identities.add(identity)
    return not items


def _oracle_delete_closure_bounds(
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[float, float]:
    for value, description in (
        (timeout_seconds, "timeout"),
        (poll_interval_seconds, "poll interval"),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise AcceptanceProducerError(
                f"oracle Job deletion closure {description} is invalid"
            )
    return float(timeout_seconds), float(poll_interval_seconds)


def _poll_oracle_job_delete_closure(
    *,
    manifest: dict[str, Any],
    kubectl: list[str],
    uid: str,
    runner: Runner,
    sleeper: Callable[[float], None],
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> tuple[list[CommandResult], list[tuple[str, CommandResult, list[str]]]]:
    name = manifest["metadata"]["name"]
    job_inventory_command = _oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    uid_pod_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pod_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    remaining_seconds = timeout_seconds
    while True:
        job_before_result = _run_checked(runner, job_inventory_command)
        job_before_absent = _oracle_delete_closure_job_absent(
            result=job_before_result,
            manifest=manifest,
            expected_uid=uid,
        )
        uid_pod_result = _run_checked(runner, uid_pod_command)
        uid_pods_absent = _oracle_delete_closure_pods_absent(
            result=uid_pod_result,
            manifest=manifest,
            expected_uid=uid,
        )
        name_pod_result = _run_checked(runner, name_pod_command)
        name_pods_absent = _oracle_delete_closure_pods_absent(
            result=name_pod_result,
            manifest=manifest,
            expected_uid=uid,
        )
        job_after_result = _run_checked(runner, job_inventory_command)
        job_after_absent = _oracle_delete_closure_job_absent(
            result=job_after_result,
            manifest=manifest,
            expected_uid=uid,
        )
        job_results = [job_before_result, job_after_result]
        pod_results = [
            ("uid", uid_pod_result, uid_pod_command),
            ("name", name_pod_result, name_pod_command),
        ]
        if (
            job_before_absent
            and uid_pods_absent
            and name_pods_absent
            and job_after_absent
        ):
            return job_results, pod_results
        if remaining_seconds <= 0:
            raise AcceptanceProducerError("oracle Job deletion closure timed out")
        delay_seconds = min(poll_interval_seconds, remaining_seconds)
        sleeper(delay_seconds)
        remaining_seconds -= delay_seconds


def _delete_oracle_job(
    *,
    manifest: dict[str, Any],
    kubectl: list[str],
    directory: Path,
    uid: str,
    source_prefix: str,
    delete_client: Any,
    runner: Runner,
    sleeper: Callable[[float], None] | None = None,
    closure_timeout_seconds: float = ORACLE_DELETE_CLOSURE_TIMEOUT_SECONDS,
    closure_poll_interval_seconds: float = ORACLE_DELETE_CLOSURE_POLL_INTERVAL_SECONDS,
) -> list[dict[str, Any]]:
    timeout_seconds, poll_interval_seconds = _oracle_delete_closure_bounds(
        timeout_seconds=closure_timeout_seconds,
        poll_interval_seconds=closure_poll_interval_seconds,
    )
    if sleeper is not None and not callable(sleeper):
        raise AcceptanceProducerError("oracle Job deletion closure sleeper is invalid")
    sleep = sleeper or time.sleep
    name = manifest["metadata"]["name"]
    namespace = manifest["metadata"]["namespace"]
    resource_identity = {
        "api_version": "batch/v1",
        "resource": "jobs",
        "namespace": namespace,
        "name": name,
    }
    delete_accepted = False
    live_job = delete_client.get(**resource_identity)
    if live_job is not None:
        try:
            live_uid = _validate_oracle_job_cleanup_identity(
                manifest=manifest,
                job=live_job,
            )
        except AcceptanceProducerError as exc:
            raise OracleTransactionIdentityError(
                "oracle Job belongs to a foreign transaction before cleanup"
            ) from exc
        if live_uid != uid:
            raise OracleTransactionIdentityError(
                "oracle Job was replaced before transaction cleanup"
            )
        metadata = live_job.get("metadata")
        resource_version = (
            metadata.get("resourceVersion") if isinstance(metadata, dict) else None
        )
        if (
            not isinstance(resource_version, str)
            or KUBERNETES_REST.IDENTITY_PATTERN.fullmatch(resource_version) is None
            or not isinstance(uid, str)
            or KUBERNETES_REST.IDENTITY_PATTERN.fullmatch(uid) is None
        ):
            raise AcceptanceProducerError(
                "oracle Job resourceVersion is invalid before cleanup"
            )
        delete_client.delete(
            **resource_identity,
            uid=uid,
            resource_version=resource_version,
        )
        delete_accepted = True
    try:
        job_results, pod_results = _poll_oracle_job_delete_closure(
            manifest=manifest,
            kubectl=kubectl,
            uid=uid,
            runner=runner,
            sleeper=sleep,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except Exception as exc:
        if not delete_accepted:
            raise
        message = (
            str(exc)
            if isinstance(exc, AcceptanceProducerError)
            else "oracle Job deletion closure probe failed"
        )
        raise OracleDeleteClosureError(message) from exc
    job_inventory_command = _oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    sources = [
        _write_source(
            directory,
            f"{source_prefix}-job-before-pods-zero.json",
            job_results[0],
            job_inventory_command,
        ),
    ]
    sources.extend(
        _write_source(
            directory,
            f"{source_prefix}-pods-{identity}-zero.json",
            result,
            command,
        )
        for identity, result, command in pod_results
    )
    sources.append(
        _write_source(
            directory,
            f"{source_prefix}-job-zero.json",
            job_results[1],
            job_inventory_command,
        )
    )
    return sources


def _require_oracle_name_pods_zero(
    *,
    kubectl: list[str],
    directory: Path,
    name: str,
    section: str,
    runner: Runner,
) -> dict[str, Any]:
    command = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    result = _run_checked(runner, command)
    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "current oracle Job Pod inventory is invalid JSON"
        ) from exc
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or inventory.get("items") != []
    ):
        raise AcceptanceProducerError(
            "current oracle Job Pod inventory is invalid or nonempty"
        )
    return _write_source(
        directory,
        f"{section}-current-name-pods-zero.json",
        result,
        command,
    )


def _cleanup_stale_oracle_jobs(
    *,
    section: str,
    targets: ProducerTargets,
    deployment_run_id: str,
    namespace: str,
    kubectl: list[str],
    directory: Path,
    image: dict[str, str],
    signing_key: bytes,
    delete_client: Any,
    runner: Runner,
) -> list[dict[str, Any]]:
    selector = _oracle_cleanup_selector(
        section=section,
        targets=targets,
        deployment_run_id=deployment_run_id,
    )
    inventory_command = [
        *kubectl,
        "get",
        "jobs",
        f"--selector={selector}",
        "--output=json",
    ]
    inventory_result = _run_checked(runner, inventory_command)
    try:
        inventory = json.loads(inventory_result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "owned oracle Job inventory is invalid JSON"
        ) from exc
    jobs = _owned_oracle_jobs(
        document=inventory,
        section=section,
        targets=targets,
        deployment_run_id=deployment_run_id,
        namespace=namespace,
        image=image,
        signing_key=signing_key,
    )
    sources = [
        _write_source(
            directory,
            f"{section}-stale-jobs.json",
            inventory_result,
            inventory_command,
        )
    ]
    for sequence, (name, uid, manifest) in enumerate(jobs):
        source_prefix = f"{section}-stale-job-{sequence:04d}"
        try:
            cleanup_sources = _delete_oracle_job(
                manifest=manifest,
                kubectl=kubectl,
                directory=directory,
                uid=uid,
                source_prefix=source_prefix,
                delete_client=delete_client,
                runner=runner,
            )
        except OracleDeleteClosureError:
            raise
        except Exception as primary_error:  # noqa: BLE001
            try:
                cleanup_sources = _reconcile_failed_oracle_transaction(
                    manifest=manifest,
                    kubectl=kubectl,
                    directory=directory,
                    created_uid=uid,
                    source_prefix=source_prefix,
                    delete_client=delete_client,
                    runner=runner,
                )
            except OracleTransactionFailure as cleanup_error:
                raise OracleTransactionFailure(
                    [("stale-delete", primary_error), *cleanup_error.failures]
                ) from None
        sources.extend(cleanup_sources)
    pod_inventory_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector={selector}",
        "--output=json",
    ]
    pod_inventory_result = _run_checked(runner, pod_inventory_command)
    try:
        pod_inventory = json.loads(pod_inventory_result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "owned oracle Pod inventory is invalid JSON"
        ) from exc
    if (
        not isinstance(pod_inventory, dict)
        or pod_inventory.get("apiVersion") != "v1"
        or pod_inventory.get("kind") != "List"
        or pod_inventory.get("items") != []
    ):
        raise AcceptanceProducerError(
            "owned oracle Pod inventory is invalid or nonempty after cleanup"
        )
    sources.append(
        _write_source(
            directory,
            f"{section}-stale-pods-zero.json",
            pod_inventory_result,
            pod_inventory_command,
        )
    )
    final_inventory_result = _run_checked(runner, inventory_command)
    try:
        final_inventory = json.loads(final_inventory_result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "final owned oracle Job inventory is invalid JSON"
        ) from exc
    if (
        not isinstance(final_inventory, dict)
        or final_inventory.get("apiVersion") != "v1"
        or final_inventory.get("kind") != "List"
        or final_inventory.get("items") != []
    ):
        raise AcceptanceProducerError(
            "final owned oracle Job inventory is invalid or nonempty after cleanup"
        )
    sources.append(
        _write_source(
            directory,
            f"{section}-stale-jobs-zero.json",
            final_inventory_result,
            inventory_command,
        )
    )
    return sources


def build_clean_reset_commands(targets: ProducerTargets) -> list[list[str]]:
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
    ]
    return [
        [*kubectl, "get", "namespaces", "--output=json"],
        [
            *kubectl,
            "get",
            "workspaces.platform.aileron.io",
            "--all-namespaces",
            "--output=json",
        ],
        [
            *kubectl,
            "get",
            "persistentvolumeclaims",
            "--all-namespaces",
            "--output=json",
        ],
        [*kubectl, "get", "persistentvolumes", "--output=json"],
    ]


def _root_compose_preflight_command(
    *, project_name: str, source_root: Path
) -> list[str]:
    return [
        *HERMETIC_COMPOSE_ENVIRONMENT,
        "docker",
        "compose",
        "--env-file",
        str(source_root / ".env.example"),
        "--project-name",
        project_name,
        "--file",
        str(source_root / "docker-compose.yml"),
        "config",
        "--quiet",
    ]


def build_suite_commands(
    targets: ProducerTargets,
    run_id: str = "run-suite-contract",
    source_root: Path | None = None,
) -> list[SuiteCommand]:
    specifications = [
        (
            "docker",
            "none",
            "scripts/test/compose-e2e/docker-compose.acceptance.yml",
            "compose-e2e-test",
        ),
        (
            "helm",
            "none",
            "scripts/test/helm/docker-compose.test.yml",
            "helm-contract-test",
        ),
        ("frontend", "none", "frontend/docker-compose.test.yml", "frontend-test"),
        (
            "manager",
            "none",
            "workspace-manager/docker-compose.test.yml",
            "workspace-manager-test",
        ),
        (
            "operator",
            "none",
            "workspace-operator/docker-compose.test.yml",
            "workspace-operator-test",
        ),
        (
            "identity",
            "none",
            "scripts/test/deploy/docker-compose.test.yml",
            "deployment-contract-test",
        ),
        (
            "platform-conformance",
            "none",
            "scripts/test/kubernetes/product-conformance/docker-compose.test.yml",
            "product-conformance-test",
        ),
        (
            "kubernetes-hardening",
            "none",
            "scripts/test/kubernetes/product-conformance/docker-compose.test.yml",
            "kubernetes-conformance-hardening-test",
        ),
        (
            "docs-zh-Hant",
            "zh-Hant",
            "docs-site/docker-compose.test.yml",
            "docs-site-build-zh-hant",
        ),
        (
            "docs-en",
            "en",
            "docs-site/docker-compose.test.yml",
            "docs-site-build-en",
        ),
    ]
    commands = []
    root = source_root or REPOSITORY_ROOT
    for name, locale, compose_file, service in specifications:
        project_name = _compose_project_name(name, targets, run_id)
        preflight = None
        if name == "docker":
            preflight = _root_compose_preflight_command(
                project_name=project_name,
                source_root=root,
            )
        commands.append(
            _compose_suite_command(
                name=name,
                locale=locale,
                targets=targets,
                run_id=run_id,
                compose_file=compose_file,
                service=service,
                source_root=root,
                preflight_command=preflight,
            )
        )
    return commands


def _assert_exact_clean_source(targets: ProducerTargets, runner: Runner) -> str:
    head = (
        _run_checked(
            runner,
            ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
        )
        .stdout.decode("utf-8", errors="strict")
        .strip()
    )
    status = _run_checked(
        runner,
        [
            "git",
            "-C",
            str(REPOSITORY_ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
    ).stdout
    if status:
        raise AcceptanceProducerError(
            "acceptance source worktree must be clean including untracked files"
        )
    if head != targets.commit:
        raise AcceptanceProducerError(
            "acceptance source HEAD must exactly match the target commit"
        )
    return head


def _suite_tree_sha256(root: Path) -> str:
    records = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise AcceptanceProducerError(
                "immutable suite source contains a symbolic link"
            )
        if stat.S_ISDIR(metadata.st_mode):
            records.append(
                f"d {stat.S_IMODE(metadata.st_mode):04o} {relative}\n".encode()
            )
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise AcceptanceProducerError(
                "immutable suite source contains a special file"
            )
        records.append(
            (
                f"f {stat.S_IMODE(metadata.st_mode):04o} "
                f"{hashlib.sha256(path.read_bytes()).hexdigest()} {relative}\n"
            ).encode()
        )
    digest = hashlib.sha256()
    for record in records:
        digest.update(record)
    return digest.hexdigest()


def _materialize_suite_source(
    *,
    targets: ProducerTargets,
    directory: Path,
    run_id: str,
    section: str,
    runner: Runner,
) -> SuiteSource:
    archive_command = [
        "git",
        "-C",
        str(REPOSITORY_ROOT),
        "archive",
        "--format=tar.gz",
        targets.commit,
    ]
    result = _run_checked(runner, archive_command)
    if result.stderr or not result.stdout:
        raise AcceptanceProducerError("immutable suite source archive is invalid")
    archive_source = _write_source(
        directory,
        f"{section}-source-archive.tar.gz",
        result,
        archive_command,
        allow_existing_exact=True,
    )
    root = directory / (
        f".{section}-source-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    )
    root.mkdir(mode=0o700)
    try:
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                member_path = Path(member.name)
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or any(part in {".venv", "venv"} for part in member_path.parts)
                    or not (member.isdir() or member.isfile())
                ):
                    raise AcceptanceProducerError(
                        "immutable suite source archive contains an unsafe member"
                    )
            archive.extractall(root, members=members, filter="data")
        for path in sorted(root.rglob("*"), reverse=True):
            metadata = os.lstat(path)
            if stat.S_ISDIR(metadata.st_mode):
                path.chmod(0o500)
            elif stat.S_ISREG(metadata.st_mode):
                # Suite sources are bind-mounted into containers whose
                # processes may drop root privileges (for example, the
                # Postgres entrypoint runs init SQL as the postgres user).
                # Keep the materialization immutable while allowing those
                # users to read the source files.
                path.chmod(0o555 if metadata.st_mode & 0o111 else 0o444)
            else:
                raise AcceptanceProducerError(
                    "immutable suite source materialization is invalid"
                )
        tree_sha256 = _suite_tree_sha256(root)
    except BaseException as primary_error:
        try:
            _remove_materialized_suite_root(root)
        except BaseException as cleanup_error:  # noqa: BLE001
            raise MaterializedSuiteSourceTransactionError(
                [
                    ("materialization", primary_error),
                    ("materializedSourceCleanup", cleanup_error),
                ]
            ) from None
        raise
    return SuiteSource(root, tree_sha256, archive_source, archive_command)


def _assert_suite_source(source: SuiteSource) -> None:
    if (
        not source.root.is_absolute()
        or source.root.resolve(strict=True) != source.root
        or stat.S_IMODE(os.lstat(source.root).st_mode) != 0o700
        or _suite_tree_sha256(source.root) != source.tree_sha256
    ):
        raise AcceptanceProducerError("immutable suite source digest changed")


def _remove_materialized_suite_root(root: Path) -> None:
    try:
        metadata = os.lstat(root)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise AcceptanceProducerError(
                "materialized suite source cleanup target is invalid"
            )
        root.chmod(0o700)
        for current, directories, _files in os.walk(
            root, topdown=True, followlinks=False
        ):
            current_path = Path(current)
            current_metadata = os.lstat(current_path)
            if not stat.S_ISDIR(current_metadata.st_mode) or stat.S_ISLNK(
                current_metadata.st_mode
            ):
                raise AcceptanceProducerError(
                    "materialized suite source cleanup target is invalid"
                )
            current_path.chmod(0o700)
            for name in directories:
                child = current_path / name
                child_metadata = os.lstat(child)
                if stat.S_ISLNK(child_metadata.st_mode):
                    continue
                if not stat.S_ISDIR(child_metadata.st_mode):
                    raise AcceptanceProducerError(
                        "materialized suite source cleanup target is invalid"
                    )
                child.chmod(0o700)
        shutil.rmtree(root)
    except AcceptanceProducerError:
        raise
    except OSError as exc:
        raise AcceptanceProducerError(
            "materialized suite source cleanup failed"
        ) from exc


def _remove_materialized_suite_source(
    *,
    source: SuiteSource,
    directory: Path,
    section: str,
    run_id: str,
) -> None:
    expected_root = directory / (
        f".{section}-source-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    )
    if (
        section not in {"suites", "offlineOidcConformance"}
        or RUN_ID.fullmatch(run_id) is None
        or not directory.is_absolute()
        or source.root != expected_root
        or source.root.parent != directory
        or source.root.is_symlink()
    ):
        raise AcceptanceProducerError(
            "materialized suite source cleanup target is invalid"
        )
    _remove_materialized_suite_root(source.root)


def _remove_materialized_suite_source_after_execution(
    *,
    source: SuiteSource,
    directory: Path,
    section: str,
    run_id: str,
    primary_error: BaseException | None,
) -> None:
    try:
        _remove_materialized_suite_source(
            source=source,
            directory=directory,
            section=section,
            run_id=run_id,
        )
    except BaseException as cleanup_error:
        cleanup_summary = {
            "errorType": type(cleanup_error).__name__,
            "phase": "materializedSourceCleanup",
        }
        if isinstance(primary_error, SuiteExecutionError):
            raise SuiteExecutionError(
                primary_error.suite_name,
                [*primary_error.failures, cleanup_summary],
                primary_error.artifact,
            ) from None
        if primary_error is not None:
            raise MaterializedSuiteSourceTransactionError(
                [
                    ("sectionExecution", primary_error),
                    ("materializedSourceCleanup", cleanup_error),
                ]
            ) from None
        raise


def _preflight_suite_release_inputs(
    *,
    image_inventory: Path | None,
    targets: ProducerTargets,
    trust,
    runner: Runner,
    directory: Path,
    run_id: str,
) -> tuple[dict[str, Any], SuiteSource]:
    if image_inventory is None:
        raise AcceptanceProducerError("suites require --image-inventory")
    try:
        ACCEPTANCE_RELEASE.load_signed_image_inventory(
            path=image_inventory,
            private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
            key=trust.key,
            context=targets.context,
            commit=targets.commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
        )
    except ACCEPTANCE_RELEASE.AcceptanceReleaseError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    inventory_raw = _read_private_bytes(image_inventory, "signed suite image inventory")
    head = _assert_exact_clean_source(targets, runner)
    suite_source = _materialize_suite_source(
        targets=targets,
        directory=directory,
        run_id=run_id,
        section="suites",
        runner=runner,
    )
    return {
        "releaseInputs": {
            "signedImageInventorySha256": hashlib.sha256(inventory_raw).hexdigest(),
        },
        "sourceProvenance": {
            "headCommit": head,
            "targetCommit": targets.commit,
            "worktreeClean": True,
            "untrackedFilesIncluded": True,
            "archiveSha256": suite_source.source["sha256"],
            "treeSha256": suite_source.tree_sha256,
            "archiveCommand": suite_source.archive_command,
            "materializedTreeReadOnly": True,
            "treeDigestChecks": 1,
        },
    }, suite_source


def _validate_targets(targets: ProducerTargets, runner: Runner):
    if SHA.fullmatch(targets.commit) is None or not targets.context:
        raise AcceptanceProducerError("producer target identity is invalid")
    try:
        return ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
            context=targets.context,
            kubeconfig=targets.kubeconfig,
            runner=lambda command: _run_checked(runner, command).stdout,
        )
    except ACCEPTANCE_CLUSTER.AcceptanceClusterError as exc:
        raise AcceptanceProducerError(str(exc)) from exc


def _pin_targets_kubeconfig(
    *,
    targets: ProducerTargets,
    directory: Path,
    deployment_run_id: str,
    runner: Runner,
) -> ProducerTargets:
    """Pin every acceptance cluster call to one run-bound flattened snapshot."""

    raw_snapshot = directory / PRIVATE_IO.RAW_KUBECONFIG_NAME

    def flatten_runner(command: list[str], *, environment: Mapping[str, str]) -> str:
        if environment != {"KUBECONFIG": str(raw_snapshot)}:
            raise AcceptanceProducerError(
                "kubeconfig flatten environment does not match the raw snapshot"
            )
        result = _run_checked(runner, command)
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AcceptanceProducerError(
                "flattened kubeconfig output is not UTF-8"
            ) from exc

    snapshot = PRIVATE_IO.snapshot_canonical_kubeconfig(
        source=targets.kubeconfig,
        directory=directory,
        private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
        commit=targets.commit,
        deployment_run_id=deployment_run_id,
        context=targets.context,
        runner=flatten_runner,
        error_type=AcceptanceProducerError,
    )
    return targets._replace(kubeconfig=snapshot.path)


def _installation_identity_mode(targets: ProducerTargets, trust) -> str:
    installation_state = ACCEPTANCE_CLUSTER.INSTALLATION_STATE
    raw = _read_private_bytes(
        installation_state.SECRET_STORE / "installation-identity.json",
        "installation identity",
    )
    if hashlib.sha256(raw).hexdigest() != trust.installation_identity_sha256:
        raise AcceptanceProducerError(
            "installation identity does not match the acceptance trust root"
        )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceProducerError("installation identity is invalid") from exc
    try:
        document = installation_state.validate_installation_identity_document(
            document,
            cluster_uid=trust.cluster_uid,
        )
        identity_mode = document["identityMode"]
        expected = installation_state.installation_identity_document(
            installation_id=document["installationId"],
            identity_mode=identity_mode,
            issuer_url=targets.issuer_url,
            client_id=targets.client_id,
            cluster_uid=trust.cluster_uid,
        )
    except installation_state.InstallationStateContractError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    if document != expected:
        raise AcceptanceProducerError(
            "acceptance target does not match the installation identity"
        )
    return identity_mode


def _run_checked(runner: Runner, command: list[str]) -> CommandResult:
    result = runner(command)
    if result.returncode != 0:
        raise AcceptanceProducerError("fixed acceptance probe failed")
    return result


def _write_source(
    directory: Path,
    name: str,
    result: CommandResult,
    command: list[str],
    *,
    allow_existing_exact: bool = False,
) -> dict[str, Any]:
    content = result.stdout + result.stderr
    path = directory / name
    _write_private_snapshot(path, content, allow_existing_exact=allow_existing_exact)
    return {
        "file": path.name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "command": command,
        "exitCode": result.returncode,
    }


def _valid_identity_job_uid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and all(
            character.isprintable() and not character.isspace() for character in value
        )
    )


def _validate_identity_smoke_report(raw: bytes) -> dict[str, Any]:
    try:
        report = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceProducerError("Identity smoke report is invalid JSON") from exc
    backup_job_uids = report.get("backupJobUids") if isinstance(report, dict) else None
    restore_job_uid = report.get("restoreJobUid") if isinstance(report, dict) else None
    if (
        not isinstance(report, dict)
        or set(report) != IDENTITY_SMOKE_REPORT_KEYS
        or report.get("schemaVersion") != IDENTITY_SMOKE_REPORT_SCHEMA
        or not isinstance(backup_job_uids, list)
        or len(backup_job_uids) != 2
        or any(not _valid_identity_job_uid(uid) for uid in backup_job_uids)
        or len(set(backup_job_uids)) != 2
        or not _valid_identity_job_uid(restore_job_uid)
        or restore_job_uid in backup_job_uids
        or report.get("restoreMarker") != "identity-smoke-marker"
        or report.get("jobClosureVerified") is not True
        or raw != _canonical(report) + b"\n"
    ):
        raise AcceptanceProducerError("Identity smoke report is invalid")
    return report


def _prepare_identity_smoke(
    *,
    targets: ProducerTargets,
    directory: Path,
    run_id: str,
    release_images: list[dict[str, str]],
    runner: Runner,
) -> list[dict[str, Any]]:
    """Run the destructive Identity backup/restore smoke before the oracle Job."""

    helm_list_command = [
        "helm",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--kube-context",
        targets.context,
        "list",
        "--namespace",
        "aileron-identity-system",
        "--filter",
        "^aileron-identity$",
        "--output",
        "json",
    ]
    helm_list = _run_checked(runner, helm_list_command)
    try:
        releases = json.loads(helm_list.stdout)
        release = next(
            item
            for item in releases
            if isinstance(item, dict) and item.get("name") == "aileron-identity"
        )
        release_revision = int(release["revision"])
    except (
        KeyError,
        TypeError,
        ValueError,
        StopIteration,
        json.JSONDecodeError,
    ) as exc:
        raise AcceptanceProducerError(
            "installed Identity release metadata is invalid"
        ) from exc

    chart_metadata_command = [
        "git",
        "show",
        f"{targets.commit}:helm/aileron-identity/Chart.yaml",
    ]
    chart_metadata = _run_checked(runner, chart_metadata_command)
    version_match = re.search(
        rb"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
        chart_metadata.stdout,
        re.MULTILINE,
    )
    if version_match is None:
        raise AcceptanceProducerError("Identity Chart version is invalid")
    chart_version = version_match.group(1).decode("ascii")

    chart_tree_command = [
        "git",
        "ls-tree",
        "-r",
        targets.commit,
        "--",
        "helm/aileron-identity",
    ]
    chart_tree = _run_checked(runner, chart_tree_command)
    chart_digest = f"sha256:{hashlib.sha256(chart_tree.stdout).hexdigest()}"
    identity_images = {
        item["component"]: item
        for item in release_images
        if item["component"] in {"platform-keycloak", "platform-postgres"}
    }
    if set(identity_images) != {"platform-keycloak", "platform-postgres"}:
        raise AcceptanceProducerError(
            "signed image inventory has no exact Identity image pair"
        )
    keycloak_image = identity_images["platform-keycloak"]
    postgres_image = identity_images["platform-postgres"]
    confirmation = (
        f"{targets.context}/aileron-identity-system/aileron-identity"
        f"@revision={release_revision},chart={chart_version},"
        f"commit={targets.commit},chartDigest={chart_digest}"
        f",keycloakImage={keycloak_image['immutableImage']}"
        f",keycloakRuntimeImage={keycloak_image['runtimeImmutableImage']}"
        f",postgresImage={postgres_image['immutableImage']}"
        f",postgresRuntimeImage={postgres_image['runtimeImmutableImage']}"
    )
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "aileron-identity-system",
    ]
    marker_name = "aileron-identity-restore-marker"
    sources = [
        _write_source(
            directory,
            "identity-release-list.json",
            helm_list,
            helm_list_command,
        ),
        _write_source(
            directory,
            "identity-chart-metadata.log",
            chart_metadata,
            chart_metadata_command,
        ),
        _write_source(
            directory,
            "identity-chart-tree.log",
            chart_tree,
            chart_tree_command,
        ),
    ]
    delete_marker_command = [
        *kubectl,
        "delete",
        "configmap",
        marker_name,
        "--ignore-not-found",
        "--wait=true",
    ]
    sources.append(
        _write_source(
            directory,
            "identity-restore-marker-delete.log",
            _run_checked(runner, delete_marker_command),
            delete_marker_command,
        )
    )
    smoke_command = [
        "python3",
        "identity-installation/backup_restore_smoke.py",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "aileron-identity-system",
        "--release",
        "aileron-identity",
        "--commit",
        targets.commit,
        "--release-revision",
        str(release_revision),
        "--chart-version",
        chart_version,
        "--chart-digest",
        chart_digest,
        "--keycloak-image",
        keycloak_image["immutableImage"],
        "--keycloak-runtime-image",
        keycloak_image["runtimeImmutableImage"],
        "--postgres-image",
        postgres_image["immutableImage"],
        "--postgres-runtime-image",
        postgres_image["runtimeImmutableImage"],
        "--confirm-destructive-restore",
        confirmation,
    ]
    smoke_result = _run_checked(runner, smoke_command)
    smoke_report = _validate_identity_smoke_report(smoke_result.stdout)
    sources.append(
        _write_source(
            directory,
            "identity-backup-restore-smoke.log",
            smoke_result,
            smoke_command,
        )
    )
    rollout_wait_command = [
        *kubectl,
        "wait",
        "--for=condition=available",
        "deployment/aileron-identity-keycloak",
        "--timeout=10m",
    ]
    sources.append(
        _write_source(
            directory,
            "identity-rollout-wait.log",
            _run_checked(runner, rollout_wait_command),
            rollout_wait_command,
        )
    )
    marker = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": marker_name,
            "namespace": "aileron-identity-system",
            "labels": {
                "platform.aileron.dev/acceptance-owner": "aileron-installer",
                "platform.aileron.dev/acceptance-run-id": run_id,
                "platform.aileron.dev/source-commit": targets.commit,
            },
        },
        "data": {
            "marker": "identity-smoke-marker",
            "commit": targets.commit,
            "runId": run_id,
            "smokeReport": _canonical(smoke_report).decode("utf-8"),
        },
    }
    marker_raw = _canonical(marker) + b"\n"
    marker_path = directory / "identity-restore-marker.json"
    _write_private_snapshot(marker_path, marker_raw)
    apply_marker_command = [
        *kubectl,
        "apply",
        "--filename",
        str(marker_path),
        "--output=name",
    ]
    sources.append(
        {
            "file": marker_path.name,
            "sha256": hashlib.sha256(marker_raw).hexdigest(),
            "command": apply_marker_command,
            "exitCode": 0,
        }
    )
    sources.append(
        _write_source(
            directory,
            "identity-restore-marker-apply.log",
            _run_checked(runner, apply_marker_command),
            apply_marker_command,
        )
    )
    return sources


def _produce_oracle_section(
    *,
    section: str,
    targets: ProducerTargets,
    directory: Path,
    image_inventory: Path,
    trust,
    runner: Runner,
    run_id: str,
    deployment_run_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        release_images = ACCEPTANCE_RELEASE.load_signed_image_inventory(
            path=image_inventory,
            private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
            key=trust.key,
            context=targets.context,
            commit=targets.commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
        )
    except ACCEPTANCE_RELEASE.AcceptanceReleaseError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    manager_images = [
        item for item in release_images if item["component"] == "workspace-manager"
    ]
    if len(manager_images) != 1:
        raise AcceptanceProducerError(
            "signed image inventory has no exact Workspace Manager image"
        )
    image = manager_images[0]
    manifest = build_oracle_job_manifest(
        section=section,
        targets=targets,
        image=image,
        run_id=run_id,
        deployment_run_id=deployment_run_id,
        signing_key=trust.key,
    )
    manifest_raw = _canonical(manifest) + b"\n"
    manifest_path = directory / f"{section}-oracle-job.json"
    _write_private_snapshot(manifest_path, manifest_raw)
    namespace = manifest["metadata"]["namespace"]
    name = manifest["metadata"]["name"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        namespace,
    ]
    delete_client = KUBERNETES_REST.load_kubernetes_delete_client(
        kubeconfig=targets.kubeconfig,
        context=targets.context,
        credential_directory=directory,
        private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
    )
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(manifest_path),
        "--output=json",
    ]
    wait_command = [
        *kubectl,
        "wait",
        "--for=condition=complete",
        f"job/{name}",
        "--timeout=5m",
    ]
    job_command = [*kubectl, "get", "job", name, "--output=json"]
    sources = _cleanup_stale_oracle_jobs(
        section=section,
        targets=targets,
        deployment_run_id=deployment_run_id,
        namespace=namespace,
        kubectl=kubectl,
        directory=directory,
        image=image,
        signing_key=trust.key,
        delete_client=delete_client,
        runner=runner,
    )
    sources.append(
        _require_oracle_name_pods_zero(
            kubectl=kubectl,
            directory=directory,
            name=name,
            section=section,
            runner=runner,
        )
    )
    if section == "identity":
        sources.extend(
            _prepare_identity_smoke(
                targets=targets,
                directory=directory,
                run_id=run_id,
                release_images=release_images,
                runner=runner,
            )
        )
    if section == "imageRelease":
        rows = "\n".join(
            "\t".join(
                (
                    item["component"],
                    item["platform"],
                    item["revision"],
                    item["immutableImage"],
                    item["runtimeImmutableImage"],
                )
            )
            for item in release_images
        )
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "aileron-image-release-inventory",
                "namespace": namespace,
                "labels": {
                    "platform.aileron.dev/acceptance-owner": "aileron-installer",
                    "platform.aileron.dev/source-commit": targets.commit,
                    "platform.aileron.dev/cluster-uid": trust.cluster_uid,
                },
            },
            "data": {"images.tsv": rows + "\n"},
        }
        configmap_raw = _canonical(configmap) + b"\n"
        configmap_path = directory / "image-release-inventory-configmap.json"
        _write_private_snapshot(configmap_path, configmap_raw)
        apply_command = [
            *kubectl,
            "apply",
            "--filename",
            str(configmap_path),
            "--output=name",
        ]
        sources.append(
            {
                "file": configmap_path.name,
                "sha256": hashlib.sha256(configmap_raw).hexdigest(),
                "command": apply_command,
                "exitCode": 0,
            }
        )
        sources.append(
            _write_source(
                directory,
                "image-release-inventory-apply.log",
                _run_checked(runner, apply_command),
                apply_command,
            )
        )
    sources.append(
        {
            "file": manifest_path.name,
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "command": create_command,
            "exitCode": 0,
        }
    )
    created_uid: str | None = None
    deleted = False
    try:
        create_result = _run_checked(runner, create_command)
        sources.append(
            _write_source(
                directory,
                f"{section}-create.json",
                create_result,
                create_command,
            )
        )
        try:
            created_job = json.loads(create_result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError(
                "created oracle Job identity is invalid JSON"
            ) from exc
        created_uid = _validate_oracle_job_cleanup_identity(
            manifest=manifest, job=created_job
        )
        _validate_oracle_job_spec_identity(manifest=manifest, job=created_job)
        created_result = _run_checked(runner, job_command)
        sources.append(
            _write_source(
                directory,
                f"{section}-created-job.json",
                created_result,
                job_command,
            )
        )
        try:
            reread_job = json.loads(created_result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError(
                "reread oracle Job identity is invalid JSON"
            ) from exc
        _require_oracle_job_generation(
            manifest=manifest,
            job=reread_job,
            expected_uid=created_uid,
        )
        sources.append(
            _write_source(
                directory,
                f"{section}-wait.log",
                _run_checked(runner, wait_command),
                wait_command,
            )
        )
        job_result = _run_checked(runner, job_command)
        sources.append(
            _write_source(directory, f"{section}-job.json", job_result, job_command)
        )
        try:
            job = json.loads(job_result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError(
                "completed oracle Job identity is invalid JSON"
            ) from exc
        _require_oracle_job_generation(
            manifest=manifest,
            job=job,
            expected_uid=created_uid,
        )
        pod_command = [
            *kubectl,
            "get",
            "pods",
            f"--selector=batch.kubernetes.io/controller-uid={created_uid}",
            "--sort-by=.metadata.name",
            "--output=json",
        ]
        pod_result = _run_checked(runner, pod_command)
        sources.append(
            _write_source(directory, f"{section}-pod.json", pod_result, pod_command)
        )
        try:
            pods = json.loads(pod_result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError(
                "oracle Pod inventory is invalid JSON"
            ) from exc
        allowed_image_digests = {
            image["immutableImage"].rsplit("@", 1)[1],
            image["runtimeImmutableImage"].rsplit("@", 1)[1],
        }
        pod = validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods=pods,
            immutable_image=image["immutableImage"],
            allowed_image_digests=allowed_image_digests,
        )
        pod_name = pod["metadata"]["name"]
        pod_uid = pod["metadata"]["uid"]
        exact_pod_command = [
            *kubectl,
            "get",
            "pod",
            pod_name,
            "--output=json",
        ]

        def reread_exact_pod(stage: str) -> None:
            result = _run_checked(runner, exact_pod_command)
            sources.append(
                _write_source(
                    directory,
                    f"{section}-pod-{stage}.json",
                    result,
                    exact_pod_command,
                )
            )
            try:
                reread_pod = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise AcceptanceProducerError(
                    "reread oracle Pod identity is invalid JSON"
                ) from exc
            _require_oracle_pod_generation(
                manifest=manifest,
                job=job,
                pod=reread_pod,
                expected_uid=pod_uid,
                immutable_image=image["immutableImage"],
                allowed_image_digests=allowed_image_digests,
            )

        reread_exact_pod("before-logs")
        logs_command = [
            *kubectl,
            "logs",
            f"pod/{pod_name}",
            "--container=oracle",
        ]
        logs_result = _run_checked(runner, logs_command)
        reread_exact_pod("after-logs")
        sources.append(
            _write_source(directory, f"{section}-oracle.log", logs_result, logs_command)
        )
        try:
            observations = json.loads(logs_result.stdout)
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError(
                "tracked oracle returned invalid JSON"
            ) from exc
        if not isinstance(observations, dict):
            raise AcceptanceProducerError("tracked oracle result must be an object")
        if section == "imageRelease":
            expected_observations = {
                "images": [
                    {
                        "component": item["component"],
                        "platform": item["platform"],
                        "revision": item["revision"],
                        "immutableImage": item["immutableImage"],
                        "runtimeImmutableImage": item["runtimeImmutableImage"],
                    }
                    for item in release_images
                ]
            }
            if observations != expected_observations:
                raise AcceptanceProducerError(
                    "tracked image oracle does not match signed release inventory"
                )
        sources.extend(
            _delete_oracle_job(
                manifest=manifest,
                kubectl=kubectl,
                directory=directory,
                uid=created_uid,
                source_prefix=f"{section}-completed-job",
                delete_client=delete_client,
                runner=runner,
            )
        )
        deleted = True
    except OracleDeleteClosureError:
        raise
    except Exception as primary_error:
        if not deleted:
            try:
                _reconcile_failed_oracle_transaction(
                    manifest=manifest,
                    kubectl=kubectl,
                    directory=directory,
                    created_uid=created_uid,
                    source_prefix=f"{section}-failed-job",
                    delete_client=delete_client,
                    runner=runner,
                )
            except OracleTransactionFailure as cleanup_error:
                raise OracleTransactionFailure(
                    [("primary", primary_error), *cleanup_error.failures]
                ) from None
        raise
    return observations, sources


def _is_exact_missing_container_result(
    result: CommandResult, *, container_name: str
) -> bool:
    return result == CommandResult(
        b"",
        f"Error response from daemon: No such container: {container_name}\n".encode(),
        1,
    )


def _cleanup_failed_browser_container(
    *,
    directory: Path,
    artifact_prefix: str,
    run_command: list[str],
    runner: Runner,
    probe_error: AcceptanceProducerError,
) -> None:
    container_name = run_command[run_command.index("--name") + 1]
    cleanup_command = ["docker", "rm", "--force", container_name]
    try:
        cleanup_result = runner(cleanup_command)
        _write_source(
            directory,
            f"{artifact_prefix}-probe-cleanup.log",
            cleanup_result,
            cleanup_command,
        )
    except (AcceptanceProducerError, OSError):
        raise AcceptanceProducerError(
            "browser acceptance container cleanup failed"
        ) from probe_error
    if cleanup_result.returncode == 0:
        return
    if not _is_exact_missing_container_result(
        cleanup_result, container_name=container_name
    ):
        raise AcceptanceProducerError(
            "browser acceptance container cleanup failed"
        ) from probe_error

    inspect_command = [
        "docker",
        "container",
        "inspect",
        "--format={{.Id}}",
        container_name,
    ]
    try:
        inspect_result = runner(inspect_command)
        _write_source(
            directory,
            f"{artifact_prefix}-probe-cleanup-inspect.log",
            inspect_result,
            inspect_command,
        )
    except (AcceptanceProducerError, OSError):
        raise AcceptanceProducerError(
            "browser acceptance container cleanup failed"
        ) from probe_error
    if not _is_exact_missing_container_result(
        inspect_result, container_name=container_name
    ):
        raise AcceptanceProducerError(
            "browser acceptance container cleanup failed"
        ) from probe_error


def _produce_browser_section(
    *,
    section: str,
    targets: ProducerTargets,
    directory: Path,
    deployment_run_id: str,
    browser_ca: Path | None,
    runner: Runner,
    run_id: str,
    authentication_mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifact_prefix = _browser_attempt_prefix(section=section, run_id=run_id)
    input_document = _load_browser_input(
        targets=targets,
        deployment_run_id=deployment_run_id,
        authentication_mode=authentication_mode,
    )
    if browser_ca is not None:
        _read_private_bytes(browser_ca, "browser CA bundle")
    provenance = verify_browser_probe_source(targets=targets, runner=runner)
    image_tag = (
        f"{BROWSER_IMAGE_REPOSITORY}:{targets.commit}-"
        f"{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    )
    build_command = [
        "docker",
        "build",
        "--file",
        "frontend/Dockerfile.playwright",
        "--tag",
        image_tag,
        "--label",
        f"org.opencontainers.image.revision={targets.commit}",
        "--pull=false",
        "frontend",
    ]
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        image_tag,
    ]
    build_result = _run_checked(runner, build_command)
    sources: list[dict[str, Any]] = []
    shared_image_tag = f"{BROWSER_IMAGE_REPOSITORY}:{targets.commit}"
    unique_tag_cleanup_command = [
        "docker",
        "image",
        "rm",
        "--force",
        image_tag,
    ]
    try:
        sources.append(
            _write_source(
                directory,
                f"{artifact_prefix}-image-build.log",
                build_result,
                build_command,
            )
        )
        inspect_result = _run_checked(runner, inspect_command)
        inspect_fields = inspect_result.stdout.decode("utf-8").strip().split("\t")
        if (
            len(inspect_fields) != 2
            or IMAGE_ID.fullmatch(inspect_fields[0]) is None
            or inspect_fields[1] != targets.commit
        ):
            raise AcceptanceProducerError("browser acceptance image ID is invalid")
        image_id = inspect_fields[0]
        sources.append(
            _write_source(
                directory,
                f"{artifact_prefix}-image-inspect.log",
                inspect_result,
                inspect_command,
            )
        )
        shared_tag_command = [
            "docker",
            "image",
            "tag",
            image_id,
            shared_image_tag,
        ]
        sources.append(
            _write_source(
                directory,
                f"{artifact_prefix}-image-shared-tag.log",
                _run_checked(runner, shared_tag_command),
                shared_tag_command,
            )
        )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_result = runner(unique_tag_cleanup_command)
        sources.append(
            _write_source(
                directory,
                f"{artifact_prefix}-image-unique-tag-cleanup.log",
                cleanup_result,
                unique_tag_cleanup_command,
            )
        )
        if cleanup_result.returncode != 0:
            cleanup_error = AcceptanceProducerError(
                "browser acceptance unique image tag could not be removed"
            )
            if active_error is not None:
                raise cleanup_error from active_error
            raise cleanup_error
    _assert_exact_clean_source(targets, runner)
    tracked_command = ["git", "show", f"{targets.commit}:{BROWSER_PROBE_PATH}"]
    tracked_result = _run_checked(runner, tracked_command)
    tracked_script = tracked_result.stdout
    if (
        tracked_result.stderr
        or tracked_script != (REPOSITORY_ROOT / BROWSER_PROBE_PATH).read_bytes()
        or hashlib.sha256(tracked_script).hexdigest() != provenance["scriptSha256"]
    ):
        raise AcceptanceProducerError(
            "browser acceptance source changed during image build"
        )
    sources.append(
        _write_source(
            directory,
            f"{artifact_prefix}-tracked-script.mjs",
            tracked_result,
            tracked_command,
        )
    )
    image_script_command = [
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "node",
        image_id,
        "-e",
        (
            'process.stdout.write(require("node:fs").readFileSync('
            '"/app/e2e/acceptance.mjs"))'
        ),
    ]
    image_script_result = _run_checked(runner, image_script_command)
    if image_script_result.stderr or image_script_result.stdout != tracked_script:
        raise AcceptanceProducerError(
            "browser acceptance image script does not exactly match tracked source"
        )
    image_script_source = _write_source(
        directory,
        f"{artifact_prefix}-image-script.mjs",
        image_script_result,
        image_script_command,
    )
    sources.append(image_script_source)
    staged_input = directory / f".browser-input-{run_id}.json"
    _write_private_snapshot(
        staged_input,
        _project_browser_input(section=section, input_document=input_document),
    )
    run_command = build_browser_probe_command(
        section=section,
        targets=targets,
        browser_input=staged_input,
        browser_ca=browser_ca,
        run_id=run_id,
        image_reference=image_id,
    )
    try:
        result = runner(run_command)
        if result.returncode != 0:
            failure_source = _write_source(
                directory,
                f"{artifact_prefix}-probe-failure.log",
                result,
                run_command,
            )
            probe_error = AcceptanceProducerError(
                f"browser acceptance failed; diagnostics={failure_source['file']}"
            )
            _cleanup_failed_browser_container(
                directory=directory,
                artifact_prefix=artifact_prefix,
                run_command=run_command,
                runner=runner,
                probe_error=probe_error,
            )
            raise probe_error
    finally:
        active_error = sys.exc_info()[1]
        try:
            staged_input.unlink()
        except OSError as exc:
            unlink_error = AcceptanceProducerError(
                "short-lived browser acceptance input could not be removed"
            )
            if active_error is not None:
                raise unlink_error from active_error
            raise unlink_error from exc
    sources.append(
        _write_source(
            directory,
            f"{artifact_prefix}-probe.log",
            result,
            run_command,
        )
    )
    _assert_exact_clean_source(targets, runner)
    try:
        observations = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError(
            "tracked browser lifecycle probe returned invalid JSON"
        ) from exc
    if not isinstance(observations, dict):
        raise AcceptanceProducerError(
            "tracked browser lifecycle probe returned invalid observations"
        )
    observations["browserProbe"] = {
        "imageId": image_id,
        "trackedScriptSha256": provenance["scriptSha256"],
        "imageScriptSha256": image_script_source["sha256"],
        "exactSourceMatch": True,
    }
    return observations, sources


def _produce_offline_oidc_conformance(
    *,
    targets: ProducerTargets,
    directory: Path,
    runner: Runner,
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    head = _assert_exact_clean_source(targets, runner)
    suite_source = _materialize_suite_source(
        targets=targets,
        directory=directory,
        run_id=run_id,
        section="offlineOidcConformance",
        runner=runner,
    )
    try:
        suite = build_offline_oidc_conformance_command(
            targets, run_id, suite_source.root
        )
        result, identity, run_command, cleanup_command = _run_isolated_compose_suite(
            item=suite,
            targets=targets,
            source=suite_source,
            runner=runner,
            directory=directory,
            section="offlineOidcConformance",
            attempt_id=run_id,
        )
        _assert_suite_source(suite_source)
        source = _write_source(
            directory,
            "external-oidc-product-conformance.log",
            result,
            run_command,
        )
        return (
            {
                "mode": "offline",
                "scope": "provider-neutral-oidc-contract",
                "authenticationMode": "oidc-without-ldap",
                "capabilities": [
                    "authorizationCodePkce",
                    "jitProvisioning",
                    "providerNeutralIssuer",
                ],
                "result": "passed",
                "projectName": suite.project_name,
                "cleanupCommand": cleanup_command,
                "cleaned": True,
                "runner": identity,
                "sourceProvenance": {
                    "headCommit": head,
                    "targetCommit": targets.commit,
                    "worktreeClean": True,
                    "untrackedFilesIncluded": True,
                    "archiveSha256": suite_source.source["sha256"],
                    "treeSha256": suite_source.tree_sha256,
                    "archiveCommand": suite_source.archive_command,
                    "materializedTreeReadOnly": True,
                    "treeDigestChecks": 5,
                },
            },
            [suite_source.source, source],
        )
    finally:
        primary_error = sys.exc_info()[1]
        _remove_materialized_suite_source_after_execution(
            source=suite_source,
            directory=directory,
            section="offlineOidcConformance",
            run_id=run_id,
            primary_error=primary_error,
        )


def _write_soak_progress(
    *,
    directory: Path,
    attempt_id: str,
    sequence: int,
    status: str,
    started: datetime,
    observed: datetime | None,
    elapsed_milliseconds: int,
    duration: int,
    samples: list[dict[str, Any]],
    failures: list[str] | None = None,
    report_file: str | None = None,
    report_sha256: str | None = None,
) -> None:
    progress = {
        "schemaVersion": "aileron-soak-progress/v2",
        "attemptId": attempt_id,
        "status": status,
        "startedAt": _timestamp(started),
        "lastObservedAt": _timestamp(observed) if observed is not None else None,
        "sampleCount": len(samples),
        "elapsedMilliseconds": elapsed_milliseconds,
        "targetDurationSeconds": duration,
        "lastFailures": failures if failures is not None else [],
    }
    if status == "completed":
        if (
            not isinstance(report_file, str)
            or not report_file
            or FILE_DIGEST.fullmatch(report_sha256 or "") is None
        ):
            raise AcceptanceProducerError("completed soak progress report is invalid")
        progress["reportFile"] = report_file
        progress["reportSha256"] = report_sha256
    elif report_file is not None or report_sha256 is not None:
        raise AcceptanceProducerError("non-completed soak progress has report identity")
    prefix = f"soak-{attempt_id}-progress-"
    progress_paths = sorted(directory.glob(f"{prefix}*.json"))
    sequences: list[int] = []
    for path in progress_paths:
        suffix = path.name[len(prefix) : -len(".json")]
        if (
            not path.name.startswith(prefix)
            or not path.name.endswith(".json")
            or re.fullmatch(r"[0-9]{4}", suffix) is None
        ):
            raise AcceptanceProducerError("soak progress history is invalid")
        sequences.append(int(suffix))
    if sequences != list(range(len(progress_paths))) or sequence != len(progress_paths):
        raise AcceptanceProducerError("soak progress sequence is not monotonic")
    if not progress_paths:
        if status not in {"started", "observations-failed"}:
            raise AcceptanceProducerError("soak progress transition is invalid")
    else:
        try:
            previous = json.loads(
                _read_private_bytes(progress_paths[-1], "soak progress history")
            )
        except json.JSONDecodeError as exc:
            raise AcceptanceProducerError("soak progress history is invalid") from exc
        previous_status = previous.get("status") if isinstance(previous, dict) else None
        transitions = {
            "started": {"running", "observations-complete", "observations-failed"},
            "running": {"running", "observations-complete", "observations-failed"},
            "observations-complete": {"completed", "observations-failed"},
            "observations-failed": set(),
            "completed": set(),
        }
        if (
            previous_status not in transitions
            or status not in transitions[previous_status]
            or previous.get("attemptId") != attempt_id
            or previous.get("startedAt") != progress["startedAt"]
            or previous.get("targetDurationSeconds") != duration
            or not isinstance(previous.get("sampleCount"), int)
            or previous["sampleCount"] > progress["sampleCount"]
            or not isinstance(previous.get("elapsedMilliseconds"), int)
            or previous["elapsedMilliseconds"] > elapsed_milliseconds
        ):
            raise AcceptanceProducerError("soak progress transition is invalid")
    _write_private_snapshot(
        directory / f"soak-{attempt_id}-progress-{sequence:04d}.json",
        _canonical(progress) + b"\n",
    )


def _run_soak_query(runner: Runner, command: list[str]) -> CommandResult:
    result = runner(command, timeout_seconds=SOAK_QUERY_PROCESS_TIMEOUT_SECONDS)
    if result.returncode == 124:
        raise AcceptanceProducerError("fixed soak query timed out")
    if result.returncode != 0:
        raise AcceptanceProducerError("fixed soak query failed")
    if result.stderr:
        raise AcceptanceProducerError("fixed soak query emitted stderr")
    return result


def _write_soak_source(
    *,
    directory: Path,
    attempt_id: str,
    sequence: int,
    query_id: str,
    command: list[str],
    result: CommandResult,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = PRIVATE_IO.load_json_object(
        result.stdout,
        "soak live query",
        error_type=AcceptanceProducerError,
        require_canonical=False,
    )
    name = f"soak-{attempt_id}-{sequence:04d}-{query_id}.json"
    path = directory / name
    _write_private_snapshot(path, result.stdout)
    digest = hashlib.sha256(result.stdout).hexdigest()
    return (
        {
            "file": name,
            "sha256": digest,
            "command": command,
            "exitCode": 0,
            "attemptId": attempt_id,
            "sampleSequence": sequence,
            "queryId": query_id,
        },
        document,
    )


def _produce_soak_impl(
    targets: ProducerTargets,
    identity_mode: str,
    directory: Path,
    runner: Runner,
    clock: Clock,
    monotonic_clock: MonotonicClock,
    sleeper: Sleeper,
    duration: int,
    interval: int,
    *,
    attempt_id: str,
    minimum_samples: int,
    deployment_run_id: str,
    maximum_sample_gap_seconds: int,
    maximum_clock_drift_milliseconds: int,
    image_runtime_pairs: Mapping[str, frozenset[str]],
):
    if RUN_ID.fullmatch(attempt_id) is None:
        raise AcceptanceProducerError("soak attempt identity is invalid")
    if targets.workspace_id is None:
        raise AcceptanceProducerError("soak requires a target Workspace")
    try:
        queries = ACCEPTANCE_SOAK.build_query_commands(
            kubeconfig=str(targets.kubeconfig),
            context=targets.context,
            workspace_id=targets.workspace_id,
            identity_mode=identity_mode,
        )
    except ACCEPTANCE_SOAK.SoakValidationError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    started = clock()
    if not isinstance(
        started, datetime
    ) or started.utcoffset() != timezone.utc.utcoffset(started):
        raise AcceptanceProducerError("soak wall clock is invalid")
    samples: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    index = 0
    baseline: dict[str, Any] = {}
    try:
        monotonic_started = monotonic_clock()
        if (
            isinstance(monotonic_started, bool)
            or not isinstance(monotonic_started, (int, float))
            or not math.isfinite(monotonic_started)
        ):
            raise AcceptanceProducerError("soak monotonic clock is invalid")
    except AcceptanceProducerError as exc:
        _write_soak_progress(
            directory=directory,
            attempt_id=attempt_id,
            sequence=0,
            status="observations-failed",
            started=started,
            observed=started,
            elapsed_milliseconds=0,
            duration=duration,
            samples=samples,
            failures=[str(exc)],
        )
        raise
    last_observed = started
    last_elapsed_milliseconds = 0
    _write_soak_progress(
        directory=directory,
        attempt_id=attempt_id,
        sequence=0,
        status="started",
        started=started,
        observed=None,
        elapsed_milliseconds=0,
        duration=duration,
        samples=samples,
    )
    while True:
        try:
            results = {
                query_id: _run_soak_query(runner, command)
                for query_id, command in queries.items()
            }
            sample_sources = []
            query_documents = {}
            query_bindings = []
            for query_id, command in queries.items():
                source, document = _write_soak_source(
                    directory=directory,
                    attempt_id=attempt_id,
                    sequence=index,
                    query_id=query_id,
                    command=command,
                    result=results[query_id],
                )
                sample_sources.append(source)
                query_documents[query_id] = document
                query_bindings.append(
                    {
                        "queryId": query_id,
                        "file": source["file"],
                        "sha256": source["sha256"],
                    }
                )
            current_baseline = ACCEPTANCE_SOAK.snapshot_sample(
                query_documents,
                workspace_id=targets.workspace_id,
                identity_mode=identity_mode,
                commit=targets.commit,
                deployment_run_id=deployment_run_id,
                image_runtime_pairs=image_runtime_pairs,
            )
            if not baseline:
                baseline = current_baseline
            elif current_baseline != baseline:
                raise AcceptanceProducerError("soak raw snapshot drift is invalid")
            observed = clock()
            if not isinstance(
                observed, datetime
            ) or observed.utcoffset() != timezone.utc.utcoffset(observed):
                raise AcceptanceProducerError("soak wall clock is invalid")
            monotonic_observed = monotonic_clock()
            if (
                isinstance(monotonic_observed, bool)
                or not isinstance(monotonic_observed, (int, float))
                or not math.isfinite(monotonic_observed)
                or monotonic_observed < monotonic_started
            ):
                raise AcceptanceProducerError("soak monotonic clock is invalid")
            elapsed_milliseconds = int((monotonic_observed - monotonic_started) * 1000)
            monotonic_step = elapsed_milliseconds - last_elapsed_milliseconds
            if monotonic_step < 0 or (samples and monotonic_step == 0):
                raise AcceptanceProducerError(
                    "soak monotonic elapsed time is not increasing"
                )
            if monotonic_step > maximum_sample_gap_seconds * 1000:
                raise AcceptanceProducerError("soak cadence gap exceeds policy")
            wall_step_milliseconds = round(
                (observed - last_observed).total_seconds() * 1000
            )
            if (
                wall_step_milliseconds < 0
                or abs(wall_step_milliseconds - monotonic_step)
                > maximum_clock_drift_milliseconds
            ):
                raise AcceptanceProducerError(
                    "soak wall and monotonic clock drift is invalid"
                )
            cumulative_wall_milliseconds = round(
                (observed - started).total_seconds() * 1000
            )
            if (
                cumulative_wall_milliseconds < 0
                or abs(cumulative_wall_milliseconds - elapsed_milliseconds)
                > maximum_clock_drift_milliseconds
            ):
                raise AcceptanceProducerError(
                    "soak wall and monotonic clock drift is invalid"
                )
        except (AcceptanceProducerError, ACCEPTANCE_SOAK.SoakValidationError) as exc:
            _write_soak_progress(
                directory=directory,
                attempt_id=attempt_id,
                sequence=len(samples) + 1,
                status="observations-failed",
                started=started,
                observed=last_observed,
                elapsed_milliseconds=last_elapsed_milliseconds,
                duration=duration,
                samples=samples,
                failures=[str(exc)],
            )
            if isinstance(exc, AcceptanceProducerError):
                raise
            raise AcceptanceProducerError(str(exc)) from exc
        sources.extend(sample_sources)
        samples.append(
            {
                "sequence": index,
                "observedAt": _timestamp(observed),
                "elapsedMilliseconds": elapsed_milliseconds,
                "queryBindings": query_bindings,
            }
        )
        last_observed = observed
        last_elapsed_milliseconds = elapsed_milliseconds
        complete = (
            elapsed_milliseconds >= duration * 1000 and len(samples) == minimum_samples
        )
        if len(samples) == minimum_samples and not complete:
            failure = AcceptanceProducerError(
                "soak exact sample count ended before the target duration"
            )
            _write_soak_progress(
                directory=directory,
                attempt_id=attempt_id,
                sequence=index + 1,
                status="observations-failed",
                started=started,
                observed=observed,
                elapsed_milliseconds=elapsed_milliseconds,
                duration=duration,
                samples=samples,
                failures=[str(failure)],
            )
            raise failure
        _write_soak_progress(
            directory=directory,
            attempt_id=attempt_id,
            sequence=index + 1,
            status="observations-complete" if complete else "running",
            started=started,
            observed=observed,
            elapsed_milliseconds=elapsed_milliseconds,
            duration=duration,
            samples=samples,
        )
        if complete:
            return (
                {
                    "identityMode": identity_mode,
                    "mutationMode": "read-only",
                    "monotonicDurationMilliseconds": elapsed_milliseconds,
                    "attemptId": attempt_id,
                    "baseline": baseline,
                    "samples": samples,
                },
                sources,
                started,
                observed,
            )
        index += 1
        next_due = monotonic_started + interval * index
        try:
            before_sleep = monotonic_clock()
            if (
                isinstance(before_sleep, bool)
                or not isinstance(before_sleep, (int, float))
                or not math.isfinite(before_sleep)
                or before_sleep < monotonic_started
            ):
                raise AcceptanceProducerError("soak monotonic clock is invalid")
            delay = next_due - before_sleep
            if delay > 0:
                sleeper(math.ceil(delay))
                after_sleep = monotonic_clock()
                if (
                    isinstance(after_sleep, bool)
                    or not isinstance(after_sleep, (int, float))
                    or not math.isfinite(after_sleep)
                ):
                    raise AcceptanceProducerError("soak monotonic clock is invalid")
                if after_sleep <= before_sleep:
                    raise AcceptanceProducerError(
                        "soak monotonic clock did not advance"
                    )
        except AcceptanceProducerError as exc:
            _write_soak_progress(
                directory=directory,
                attempt_id=attempt_id,
                sequence=len(samples) + 1,
                status="observations-failed",
                started=started,
                observed=last_observed,
                elapsed_milliseconds=last_elapsed_milliseconds,
                duration=duration,
                samples=samples,
                failures=[str(exc)],
            )
            raise


def _latest_soak_progress(
    *, directory: Path, attempt_id: str
) -> tuple[int, dict[str, Any] | None]:
    prefix = f"soak-{attempt_id}-progress-"
    paths = sorted(directory.glob(f"{prefix}*.json"))
    if not paths:
        return 0, None
    expected_names = [f"{prefix}{index:04d}.json" for index in range(len(paths))]
    if [path.name for path in paths] != expected_names:
        raise AcceptanceProducerError("soak progress history is invalid")
    try:
        document = json.loads(_read_private_bytes(paths[-1], "soak progress history"))
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError("soak progress history is invalid") from exc
    if not isinstance(document, dict):
        raise AcceptanceProducerError("soak progress history is invalid")
    return len(paths), document


def _record_unexpected_soak_failure(
    *,
    directory: Path,
    attempt_id: str,
    duration: int,
    failure: Exception,
) -> None:
    if RUN_ID.fullmatch(attempt_id) is None:
        return
    sequence, previous = _latest_soak_progress(
        directory=directory,
        attempt_id=attempt_id,
    )
    if previous is not None and previous.get("status") == "observations-failed":
        return
    now = datetime.now(timezone.utc)
    started = now
    observed: datetime | None = now
    elapsed_milliseconds = 0
    samples: list[dict[str, Any]] = []
    if previous is not None:
        try:
            started = datetime.fromisoformat(
                previous["startedAt"].replace("Z", "+00:00")
            )
            observed_raw = previous.get("lastObservedAt")
            observed = (
                datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
                if isinstance(observed_raw, str)
                else started
            )
            elapsed_milliseconds = previous["elapsedMilliseconds"]
            samples = [{} for _ in range(previous["sampleCount"])]
        except (KeyError, TypeError, ValueError) as exc:
            raise AcceptanceProducerError("soak progress history is invalid") from exc
    message = str(failure) or failure.__class__.__name__
    _write_soak_progress(
        directory=directory,
        attempt_id=attempt_id,
        sequence=sequence,
        status="observations-failed",
        started=started,
        observed=observed,
        elapsed_milliseconds=elapsed_milliseconds,
        duration=duration,
        samples=samples,
        failures=[message],
    )


def _produce_soak(
    targets: ProducerTargets,
    identity_mode: str,
    directory: Path,
    runner: Runner,
    clock: Clock,
    monotonic_clock: MonotonicClock,
    sleeper: Sleeper,
    duration: int,
    interval: int,
    *,
    attempt_id: str,
    minimum_samples: int,
    deployment_run_id: str,
    maximum_sample_gap_seconds: int,
    maximum_clock_drift_milliseconds: int,
    image_runtime_pairs: Mapping[str, frozenset[str]],
):
    try:
        return _produce_soak_impl(
            targets,
            identity_mode,
            directory,
            runner,
            clock,
            monotonic_clock,
            sleeper,
            duration,
            interval,
            attempt_id=attempt_id,
            minimum_samples=minimum_samples,
            deployment_run_id=deployment_run_id,
            maximum_sample_gap_seconds=maximum_sample_gap_seconds,
            maximum_clock_drift_milliseconds=maximum_clock_drift_milliseconds,
            image_runtime_pairs=image_runtime_pairs,
        )
    except Exception as exc:
        try:
            _record_unexpected_soak_failure(
                directory=directory,
                attempt_id=attempt_id,
                duration=duration,
                failure=exc,
            )
        except AcceptanceProducerError as marker_exc:
            if isinstance(exc, AcceptanceProducerError):
                raise SoakPublicationError([exc, marker_exc]) from marker_exc
            converted = AcceptanceProducerError(str(exc) or exc.__class__.__name__)
            raise SoakPublicationError([converted, marker_exc]) from marker_exc
        if isinstance(exc, AcceptanceProducerError):
            raise
        raise AcceptanceProducerError(str(exc) or exc.__class__.__name__) from exc


def _suite_runner_inspect_command(image: str) -> list[str]:
    return [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        image,
    ]


def _suite_runner_cleanup_command(image: str) -> list[str]:
    return ["docker", "image", "rm", image]


def _inspect_runner_identity(
    *,
    result: CommandResult,
    image: str,
    commit: str,
    suite_name: str,
    build_command: list[str],
) -> dict[str, Any]:
    inspect_command = _suite_runner_inspect_command(image)
    if result.returncode != 0:
        raise AcceptanceProducerError("fixed acceptance probe failed")
    fields = result.stdout.decode("utf-8", errors="strict").strip().split("\t")
    if (
        len(fields) != 3
        or IMAGE_ID.fullmatch(fields[0]) is None
        or fields[1] != "amd64"
        or fields[2] != commit
    ):
        raise AcceptanceProducerError(
            f"suite runner image provenance is invalid for {suite_name}"
        )
    return {
        "image": image,
        "imageId": fields[0],
        "architecture": fields[1],
        "sourceRevision": fields[2],
        "buildCommand": build_command,
        "inspectCommand": inspect_command,
    }


def _pin_suite_command(command: list[str], image_id: str) -> list[str]:
    return [
        argument.replace(SUITE_IMAGE_ID_PLACEHOLDER, image_id) for argument in command
    ]


def _bounded_suite_failure_stream(content: bytes) -> dict[str, Any]:
    captured = content[-SUITE_FAILURE_STREAM_MAXIMUM_BYTES:]
    return {
        "byteLength": len(content),
        "capturedByteLength": len(captured),
        "sha256": hashlib.sha256(content).hexdigest(),
        "tailBase64": base64.b64encode(captured).decode("ascii"),
        "truncated": len(captured) != len(content),
    }


def _suite_failure_entry(
    *, phase: str, error: BaseException, result: CommandResult | None
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "errorType": type(error).__name__,
        "phase": phase,
    }
    if result is not None:
        failure.update(
            {
                "exitCode": result.returncode,
                "stderr": _bounded_suite_failure_stream(result.stderr),
                "stdout": _bounded_suite_failure_stream(result.stdout),
            }
        )
    return failure


def _write_suite_failure_artifact(
    *,
    directory: Path,
    section: str,
    attempt_id: str,
    suite_name: str,
    failures: list[dict[str, Any]],
) -> dict[str, str]:
    if section not in {"suites", "offlineOidcConformance"}:
        raise AcceptanceProducerError("suite failure section is invalid")
    if RUN_ID.fullmatch(attempt_id) is None:
        raise AcceptanceProducerError("suite failure attempt identity is invalid")
    document = {
        "attemptId": attempt_id,
        "failures": failures,
        "schemaVersion": SUITE_FAILURE_SCHEMA,
        "section": section,
        "suite": suite_name,
    }
    raw = _canonical(document) + b"\n"
    if len(raw) > SUITE_FAILURE_ARTIFACT_MAXIMUM_BYTES:
        raise AcceptanceProducerError("suite failure artifact exceeds its size bound")
    path = directory / f"{section}-{attempt_id}-failure.json"
    _write_private_snapshot(path, raw)
    return {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def _run_isolated_compose_suite(
    *,
    item: SuiteCommand,
    targets: ProducerTargets,
    source: SuiteSource,
    runner: Runner,
    directory: Path,
    section: str,
    attempt_id: str,
) -> tuple[CommandResult, dict[str, Any], list[str], list[str]]:
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    runner_image_cleanup_error: BaseException | None = None
    source_error: BaseException | None = None
    primary_phase = "immutableSourceBeforeBuild"
    primary_result: CommandResult | None = None
    cleanup_result: CommandResult | None = None
    runner_image_cleanup_result: CommandResult | None = None
    runner_image_built = False
    result: CommandResult | None = None
    identity: dict[str, Any] | None = None
    run_command = _pin_suite_command(item.command, item.runner_image)
    cleanup_command = _pin_suite_command(item.cleanup_command, item.runner_image)
    try:
        _assert_suite_source(source)
        primary_phase = "build"
        build_result = runner(item.build_command)
        if build_result.returncode != 0:
            primary_result = build_result
            raise AcceptanceProducerError("fixed acceptance probe failed")
        runner_image_built = True
        primary_phase = "immutableSourceAfterBuild"
        _assert_suite_source(source)
        primary_phase = "runnerIdentity"
        primary_result = runner(_suite_runner_inspect_command(item.runner_image))
        if primary_result.returncode != 0:
            raise AcceptanceProducerError("fixed acceptance probe failed")
        identity = _inspect_runner_identity(
            result=primary_result,
            image=item.runner_image,
            commit=targets.commit,
            suite_name=item.name,
            build_command=item.build_command,
        )
        primary_result = None
        run_command = _pin_suite_command(item.command, identity["imageId"])
        cleanup_command = _pin_suite_command(item.cleanup_command, identity["imageId"])
        if item.preflight_command is not None:
            primary_phase = "preflight"
            preflight = runner(item.preflight_command)
            if preflight.returncode != 0:
                primary_result = preflight
                raise AcceptanceProducerError("fixed acceptance probe failed")
            if preflight.stdout or preflight.stderr:
                primary_result = preflight
                raise AcceptanceProducerError(
                    "root Compose quiet validation must not emit raw output"
                )
        primary_phase = "run"
        result = runner(run_command)
        if result.returncode != 0:
            primary_result = result
            raise AcceptanceProducerError("fixed acceptance probe failed")
    except BaseException as exc:  # noqa: BLE001
        primary_error = exc
    try:
        cleanup_result = runner(cleanup_command)
        if cleanup_result.returncode != 0:
            cleanup_error = AcceptanceProducerError(
                f"isolated Compose cleanup failed for {item.name}"
            )
    except BaseException as exc:  # noqa: BLE001
        cleanup_error = exc
    try:
        _assert_suite_source(source)
    except BaseException as exc:  # noqa: BLE001
        source_error = exc
    if runner_image_built:
        try:
            runner_image_cleanup_result = runner(
                _suite_runner_cleanup_command(item.runner_image)
            )
            if runner_image_cleanup_result.returncode != 0:
                runner_image_cleanup_error = AcceptanceProducerError(
                    f"suite runner image cleanup failed for {item.name}"
                )
        except BaseException as exc:  # noqa: BLE001
            runner_image_cleanup_error = exc
    failure_contexts = [
        (phase, error, phase_result)
        for phase, error, phase_result in (
            (primary_phase, primary_error, primary_result),
            ("cleanup", cleanup_error, cleanup_result),
            ("immutableSourceAfterCleanup", source_error, None),
            (
                "runnerImageCleanup",
                runner_image_cleanup_error,
                runner_image_cleanup_result,
            ),
        )
        if error is not None
    ]
    artifact_failures = [
        _suite_failure_entry(phase=phase, error=error, result=phase_result)
        for phase, error, phase_result in failure_contexts
    ]
    if artifact_failures:
        artifact = _write_suite_failure_artifact(
            directory=directory,
            section=section,
            attempt_id=attempt_id,
            suite_name=item.name,
            failures=artifact_failures,
        )
        failure_summaries = []
        for phase, error, phase_result in failure_contexts:
            summary = {"errorType": type(error).__name__, "phase": phase}
            if phase_result is not None:
                summary["exitCode"] = phase_result.returncode
            if phase in {"build", "run"} or (
                phase == "preflight"
                and phase_result is not None
                and phase_result.returncode != 0
            ):
                summary["message"] = "fixed acceptance probe failed"
            elif phase == "preflight" and phase_result is not None:
                summary["message"] = (
                    "root Compose quiet validation must not emit raw output"
                )
            elif phase == "cleanup" and isinstance(error, AcceptanceProducerError):
                summary["message"] = f"isolated Compose cleanup failed for {item.name}"
            elif phase == "runnerImageCleanup" and isinstance(
                error, AcceptanceProducerError
            ):
                summary["message"] = (
                    f"suite runner image cleanup failed for {item.name}"
                )
            failure_summaries.append(summary)
        raise SuiteExecutionError(item.name, failure_summaries, artifact)
    if result is None:
        raise AcceptanceProducerError("isolated Compose suite returned no result")
    if identity is None:
        raise AcceptanceProducerError("suite runner identity is missing")
    return result, identity, run_command, cleanup_command


def _produce_suites(
    targets: ProducerTargets,
    directory: Path,
    runner: Runner,
    clock: Clock,
    suite_preflight: dict[str, Any],
    suite_source: SuiteSource,
    run_id: str,
):
    runs = []
    sources = [suite_source.source]
    suite_commands = build_suite_commands(targets, run_id, suite_source.root)
    for index, item in enumerate(suite_commands):
        started = clock()
        result, identity, run_command, cleanup_command = _run_isolated_compose_suite(
            item=item,
            targets=targets,
            source=suite_source,
            runner=runner,
            directory=directory,
            section="suites",
            attempt_id=run_id,
        )
        finished = clock()
        source = _write_source(
            directory, f"suite-{index}-{item.name}.log", result, run_command
        )
        sources.append(source)
        run = {
            "name": item.name,
            "command": run_command,
            "locale": item.locale,
            "exitCode": 0,
            "startedAt": _timestamp(started),
            "finishedAt": _timestamp(finished),
            "rawLogSha256": source["sha256"],
            "projectName": item.project_name,
            "cleanupCommand": cleanup_command,
            "cleaned": True,
            "runner": identity,
        }
        if item.preflight_command is not None:
            run["preflightCommand"] = item.preflight_command
        if item.name.startswith("docs-"):
            run["linksVerified"] = True
        runs.append(run)
    _assert_suite_source(suite_source)
    suite_preflight["sourceProvenance"]["treeDigestChecks"] = (
        len(suite_commands) * 3 + 2
    )
    return {
        "containerSuites": [
            item.name for item in suite_commands if not item.name.startswith("docs-")
        ],
        "runs": runs,
        **suite_preflight,
    }, sources


def _live_reset_target_names(
    document: dict[str, Any], *, resource: str, signed_pvs: set[str]
) -> set[str]:
    items = document.get("items")
    if not isinstance(items, list):
        raise AcceptanceProducerError("clean reset live inventory is invalid")
    observed: set[str] = set()
    for item in items:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        name = metadata.get("name") if isinstance(metadata, dict) else None
        if not isinstance(name, str) or not name:
            raise AcceptanceProducerError("clean reset live inventory is invalid")
        if resource == "namespaces":
            if name in ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES:
                observed.add(name)
            continue
        namespace = metadata.get("namespace")
        if resource in {"workspaces", "pvcs"}:
            if not isinstance(namespace, str) or not namespace:
                raise AcceptanceProducerError("clean reset live inventory is invalid")
            if (resource == "workspaces" and namespace == "workspace-system") or (
                resource == "pvcs"
                and namespace in ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES
            ):
                observed.add(f"{namespace}/{name}")
            continue
        if resource != "pvs":
            raise AcceptanceProducerError("clean reset command contract is invalid")
        spec = item.get("spec")
        if not isinstance(spec, dict):
            raise AcceptanceProducerError("clean reset live inventory is invalid")
        claim_ref = spec.get("claimRef")
        claim_namespace = (
            claim_ref.get("namespace") if isinstance(claim_ref, dict) else None
        )
        storage_class = spec.get("storageClassName")
        if (
            name in signed_pvs
            or claim_namespace in ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES
            or storage_class in RESET_INVENTORY.TARGET_STORAGE_CLASSES
        ):
            observed.add(name)
    return observed


def _backend_cleanup_summary(
    *,
    document: dict[str, Any],
    source_file: str,
    source_sha256: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": document["schemaVersion"],
        "sourceFile": source_file,
        "sourceSha256": source_sha256,
        "commit": document["commit"],
        "runId": document["runId"],
        "snapshotSha256": document["snapshotSha256"],
        "allAbsent": document["allAbsent"],
        "targetResultDigests": [
            {
                "persistentVolume": result["persistentVolume"],
                "locatorSha256": result["locatorSha256"],
                "cleanupResultSha256": result["cleanupResultSha256"],
                "verificationResultSha256": result["verificationResultSha256"],
            }
            for result in document["results"]
        ],
    }


def _backend_post_reset_summary(
    *,
    document: dict[str, Any],
    source_file: str,
    source_sha256: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": document["schemaVersion"],
        "sourceFile": source_file,
        "sourceSha256": source_sha256,
        "commit": document["commit"],
        "runId": document["runId"],
        "snapshotSha256": document["snapshotSha256"],
        "backendCleanupResultsSha256": document["backendCleanupResultsSha256"],
        "allAbsent": document["allAbsent"],
        "targetResultDigests": [
            {
                "persistentVolume": result["persistentVolume"],
                "locatorSha256": result["locatorSha256"],
                "verificationResultSha256": result["verificationResultSha256"],
            }
            for result in document["verifications"]
        ],
    }


def _load_existing_backend_post_reset(
    *, path: Path, backend_inputs: Any
) -> tuple[dict[str, Any], bytes] | None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise AcceptanceProducerError(
            "backend post-reset verification source is unreadable"
        ) from exc
    raw = _read_private_bytes(path, "backend post-reset verification source")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceProducerError(
            "backend post-reset verification source is invalid JSON"
        ) from exc
    if not isinstance(document, dict) or raw != _canonical(document) + b"\n":
        raise AcceptanceProducerError(
            "backend post-reset verification source is not canonical"
        )
    try:
        validated = BACKEND_ATTESTOR.validate_backend_post_reset_verification(
            document, inputs=backend_inputs
        )
    except (ValueError, BACKEND_ATTESTOR.BackendAttestorError) as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    return validated, raw


def _produce_clean_reset(
    targets: ProducerTargets,
    directory: Path,
    snapshot: dict[str, Any],
    runner: Runner,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inventory = snapshot["inventory"]
    namespaces = [item.get("name") for item in inventory.get("namespaces", [])]
    workspaces = [
        item.get("name")
        for item in inventory.get("resources", [])
        if item.get("kind") == "Workspace"
    ]
    pvcs = [
        f"{item.get('namespace')}/{item.get('name')}"
        for item in inventory.get("resources", [])
        if item.get("kind") == "PersistentVolumeClaim"
    ]
    pvs = [item.get("name") for item in inventory.get("persistentVolumes", [])]
    if (
        any(not isinstance(namespace, str) or not namespace for namespace in namespaces)
        or len(namespaces) != len(set(namespaces))
        or not set(namespaces).issubset(ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES)
        or any(
            not isinstance(value, str) or not value
            for value in [*workspaces, *pvcs, *pvs]
        )
    ):
        raise AcceptanceProducerError(
            "canonical reset inventory target sets are invalid"
        )
    sources = []
    inventory_raw = _canonical(inventory)
    inventory_copy = directory / "clean-reset-inventory-source.json"
    _write_private_snapshot(inventory_copy, inventory_raw, allow_existing_exact=True)
    inventory_digest = hashlib.sha256(inventory_raw).hexdigest()
    sources.append(
        {
            "file": inventory_copy.name,
            "sha256": inventory_digest,
            "command": [
                "python3",
                str(SCRIPT_DIRECTORY / "collect_reset_inventory.py"),
                "--kubeconfig",
                str(targets.kubeconfig),
                "--context",
                targets.context,
                "--output",
                str(directory / "clean-reset-inventory.json"),
            ],
            "exitCode": 0,
        }
    )
    snapshot_path = directory / ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME
    snapshot_raw = _read_private_bytes(snapshot_path, "signed clean reset snapshot")
    sources.append(
        {
            "file": snapshot_path.name,
            "sha256": hashlib.sha256(snapshot_raw).hexdigest(),
            "command": [
                PRODUCER_EXECUTABLE,
                "--section",
                "cleanReset",
                "--reset-phase",
                "pre-reset",
            ],
            "exitCode": 0,
        }
    )
    live_commands = build_clean_reset_commands(targets)
    resources = ("namespaces", "workspaces", "pvcs", "pvs")
    if len(live_commands) != len(resources):
        raise AcceptanceProducerError("clean reset command contract is invalid")
    for index, (command, resource) in enumerate(zip(live_commands, resources)):
        result = _run_checked(runner, command)
        try:
            document = json.loads(result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceProducerError(
                "clean reset live inventory is invalid JSON"
            ) from exc
        if _live_reset_target_names(document, resource=resource, signed_pvs=set(pvs)):
            raise AcceptanceProducerError("clean reset target resource still exists")
        sources.append(
            _write_source(
                directory,
                f"clean-reset-live-{index}.json",
                result,
                command,
                allow_existing_exact=True,
            )
        )
    snapshot_sha256 = hashlib.sha256(snapshot_raw).hexdigest()
    try:
        backend_inputs = BACKEND_ATTESTOR.load_signed_backend_attestor_inputs(
            context=targets.context,
            commit=targets.commit,
            expected_run_id=snapshot["runId"],
            expected_snapshot_sha256=snapshot_sha256,
        )
        backend_cleanup = BACKEND_ATTESTOR.load_backend_cleanup_results(backend_inputs)
    except (ValueError, BACKEND_ATTESTOR.BackendAttestorError) as exc:
        raise AcceptanceProducerError(str(exc)) from exc

    reset_cleanup_path = (
        ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
        / "reset"
        / targets.commit
        / snapshot["runId"]
        / "backend-cleanup-results.json"
    )
    reset_cleanup_raw = _read_private_bytes(
        reset_cleanup_path, "backend cleanup aggregate"
    )
    canonical_cleanup_raw = _canonical(backend_cleanup) + b"\n"
    if reset_cleanup_raw != canonical_cleanup_raw:
        raise AcceptanceProducerError("backend cleanup aggregate is not canonical")
    cleanup_source_path = directory / "clean-reset-backend-cleanup-results.json"
    _write_private_snapshot(
        cleanup_source_path, reset_cleanup_raw, allow_existing_exact=True
    )
    cleanup_source_sha256 = hashlib.sha256(reset_cleanup_raw).hexdigest()

    post_reset_source_path = (
        directory / "clean-reset-backend-post-reset-verification.json"
    )
    existing_post_reset = _load_existing_backend_post_reset(
        path=post_reset_source_path, backend_inputs=backend_inputs
    )
    if existing_post_reset is None:
        try:
            backend_post_reset = BACKEND_ATTESTOR.verify_signed_backend_absence(
                backend_inputs
            )
            backend_post_reset = (
                BACKEND_ATTESTOR.validate_backend_post_reset_verification(
                    backend_post_reset, inputs=backend_inputs
                )
            )
        except (ValueError, BACKEND_ATTESTOR.BackendAttestorError) as exc:
            raise AcceptanceProducerError(str(exc)) from exc
        post_reset_raw = _canonical(backend_post_reset) + b"\n"
        _write_private_snapshot(post_reset_source_path, post_reset_raw)
    else:
        backend_post_reset, post_reset_raw = existing_post_reset
    post_reset_source_sha256 = hashlib.sha256(post_reset_raw).hexdigest()
    reset_directory = reset_cleanup_path.parent
    cleanup_source_command = [
        "python3",
        str(SCRIPT_DIRECTORY / "reset_plan.py"),
        "--expected-commit",
        targets.commit,
        "--expected-reset-run-id",
        snapshot["runId"],
        "--expected-reset-snapshot-digest",
        snapshot_sha256,
        "--context",
        targets.context,
        "--kubeconfig",
        str(reset_directory / f"reset-kubeconfig-{snapshot['runId']}.flattened.json"),
        "--execute",
        "--confirm-delete-all-aileron-data",
    ]
    post_reset_source_command = [
        PRODUCER_EXECUTABLE,
        "--section",
        "cleanReset",
        "--deployment-run-id",
        snapshot["runId"],
        "--reset-phase",
        "post-reset",
        "--expected-reset-snapshot-digest",
        snapshot_sha256,
        "--context",
        targets.context,
        "--kubeconfig",
        str(targets.kubeconfig),
        "--platform-url",
        targets.platform_url,
        "--issuer-url",
        targets.issuer_url,
        "--client-id",
        targets.client_id,
        "--expected-commit",
        targets.commit,
    ]
    sources.extend(
        [
            {
                "file": cleanup_source_path.name,
                "sha256": cleanup_source_sha256,
                "command": cleanup_source_command,
                "exitCode": 0,
            },
            {
                "file": post_reset_source_path.name,
                "sha256": post_reset_source_sha256,
                "command": post_reset_source_command,
                "exitCode": 0,
            },
        ]
    )
    backend_targets = [
        {
            "persistentVolume": {
                "name": target.persistent_volume_name,
                "uid": target.persistent_volume_uid,
            },
            "locatorSha256": target.locator_sha256,
        }
        for target in backend_inputs.cleanup_targets
    ]
    expected = {
        "namespaces": namespaces,
        "workspaceCRs": workspaces,
        "pvcs": pvcs,
        "pvs": pvs,
        "backendTargets": backend_targets,
    }
    return {
        "resetRunId": snapshot["runId"],
        "inventorySha256": inventory_digest,
        "fixedResetTargets": {
            "namespaces": sorted(ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES),
            "storageClasses": sorted(RESET_INVENTORY.TARGET_STORAGE_CLASSES),
        },
        "expected": expected,
        "observedAbsent": {
            key: expected[key] for key in ("namespaces", "workspaceCRs", "pvcs", "pvs")
        },
        "backendCleanupResults": _backend_cleanup_summary(
            document=backend_cleanup,
            source_file=cleanup_source_path.name,
            source_sha256=cleanup_source_sha256,
        ),
        "backendPostResetVerification": _backend_post_reset_summary(
            document=backend_post_reset,
            source_file=post_reset_source_path.name,
            source_sha256=post_reset_source_sha256,
        ),
    }, sources


def _prepare_clean_reset_snapshot(
    *,
    targets: ProducerTargets,
    directory: Path,
    trust,
    runner: Runner,
    clock: Clock,
    run_id: str,
    image_inventory: Path | None,
) -> Path:
    private_root = ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
    expected_image_inventory = (
        private_root / "install" / targets.commit / "signed-image-inventory.json"
    )
    if image_inventory is not None and image_inventory != expected_image_inventory:
        raise AcceptanceProducerError(
            "signed image inventory is not the canonical installation snapshot"
        )
    image_inventory = expected_image_inventory
    try:
        ACCEPTANCE_RELEASE.load_signed_image_inventory(
            path=image_inventory,
            private_root=private_root,
            key=trust.key,
            context=targets.context,
            commit=targets.commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
        )
    except ACCEPTANCE_RELEASE.AcceptanceReleaseError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    profile_source = private_root / "backend-attestor" / "execution-profile.json"
    profile_snapshot = directory / "backend-execution-profile.json"
    _write_private_snapshot(
        profile_snapshot,
        _read_private_bytes(profile_source, "backend execution profile"),
    )
    try:
        profile_binding = BACKEND_ATTESTOR.inspect_execution_profile(
            profile_snapshot,
            private_root=private_root,
        )
        resource_binding = BACKEND_ATTESTOR.inspect_execution_resources(
            execution_profile_path=profile_snapshot,
            kubeconfig=targets.kubeconfig,
            context=targets.context,
            private_root=private_root,
            runner=runner,
        )
        backend_attestor_binding = (
            BACKEND_ATTESTOR.validate_backend_attestor_snapshot_binding(
                {
                    "schemaVersion": (
                        BACKEND_ATTESTOR.BACKEND_ATTESTOR_SNAPSHOT_BINDING_SCHEMA
                    ),
                    "executionProfile": profile_binding,
                    "executionResources": resource_binding,
                    "imageInventorySha256": hashlib.sha256(
                        _read_private_bytes(image_inventory, "signed image inventory")
                    ).hexdigest(),
                }
            )
        )
    except (ValueError, BACKEND_ATTESTOR.BackendAttestorError) as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    inventory_path = directory / "clean-reset-inventory.json"
    command = [
        "python3",
        str(SCRIPT_DIRECTORY / "collect_reset_inventory.py"),
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--output",
        str(inventory_path),
    ]
    _run_checked(runner, command)
    try:
        inventory = json.loads(
            _read_private_bytes(inventory_path, "canonical reset inventory")
        )
    except json.JSONDecodeError as exc:
        raise AcceptanceProducerError("canonical reset inventory is invalid") from exc
    try:
        return ACCEPTANCE_SNAPSHOT.write_reset_snapshot(
            directory=directory,
            private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
            inventory=inventory,
            key=trust.key,
            context=targets.context,
            commit=targets.commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
            run_id=run_id,
            backend_attestor=backend_attestor_binding,
            created_at=clock(),
        )
    except ACCEPTANCE_SNAPSHOT.AcceptanceSnapshotError as exc:
        raise AcceptanceProducerError(str(exc)) from exc


def produce(
    *,
    section: str,
    targets: ProducerTargets,
    deployment_run_id: str,
    image_inventory: Path | None = None,
    browser_ca: Path | None = None,
    reset_phase: str | None = None,
    expected_reset_snapshot_digest: str | None = None,
    runner: Runner = _subprocess_runner,
    clock: Clock = lambda: datetime.now(timezone.utc),
    monotonic_clock: MonotonicClock = time.monotonic,
    sleeper: Sleeper = time.sleep,
    soak_seconds: int = 1800,
    sample_interval: int = 60,
    run_id_factory: Callable[[], str] = lambda: f"run-{secrets.token_hex(8)}",
) -> Path:
    private_root = ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
    evidence_directory = PRIVATE_IO.evidence_directory(
        private_root=private_root,
        commit=targets.commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceProducerError,
    )
    if section not in PRODUCER_IDS:
        raise AcceptanceProducerError("unknown producer section")
    validator = _load_validator()
    try:
        contract = validator.load_canonical_contract(CONTRACT_PATH)
        scope = validator.report_scope(contract, section)
    except validator.AcceptanceEvidenceError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    if section == "soak":
        try:
            soak_policy = ACCEPTANCE_SOAK.validate_policy(contract)
        except ACCEPTANCE_SOAK.SoakValidationError as exc:
            raise AcceptanceProducerError(str(exc)) from exc
        if (
            soak_seconds != soak_policy.duration_seconds
            or sample_interval != soak_policy.sample_interval_seconds
        ):
            raise AcceptanceProducerError("soak execution policy is not canonical")
    if (
        scope == "workspace"
        and section != "oidcWorkspace"
        and (not targets.workspace_id or not targets.user_subject)
    ):
        raise AcceptanceProducerError(
            "Workspace acceptance sections require Workspace identity"
        )
    evidence_directory = PRIVATE_IO.ensure_evidence_directory(
        private_root=private_root,
        commit=targets.commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceProducerError,
    )
    targets = _pin_targets_kubeconfig(
        targets=targets,
        directory=evidence_directory,
        deployment_run_id=deployment_run_id,
        runner=runner,
    )
    trust = _validate_targets(targets, runner)
    if section == "cleanReset" and reset_phase == "pre-reset":
        snapshot_path = _prepare_clean_reset_snapshot(
            targets=targets,
            directory=evidence_directory,
            trust=trust,
            runner=runner,
            clock=clock,
            run_id=deployment_run_id,
            image_inventory=image_inventory,
        )
        authentication_mode = _installation_identity_mode(targets, trust)
        try:
            ACCEPTANCE_EPOCH.write_deployment_epoch(
                directory=evidence_directory,
                private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
                key=trust.key,
                deployment_run_id=deployment_run_id,
                commit=targets.commit,
                cluster_uid=trust.cluster_uid,
                context=targets.context,
                installation_identity_sha256=trust.installation_identity_sha256,
                authentication_mode=authentication_mode,
                reset_snapshot_sha256=hashlib.sha256(
                    _read_private_bytes(snapshot_path, "signed clean reset snapshot")
                ).hexdigest(),
                created_at=clock(),
            )
        except ACCEPTANCE_EPOCH.AcceptanceEpochError as exc:
            raise AcceptanceProducerError(str(exc)) from exc
        return snapshot_path
    PRIVATE_IO.validate_evidence_directory(
        evidence_directory,
        private_root=private_root,
        commit=targets.commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceProducerError,
    )
    if section == "cleanReset" and reset_phase != "post-reset":
        raise AcceptanceProducerError(
            "cleanReset requires --reset-phase pre-reset or post-reset"
        )
    if section != "cleanReset" and reset_phase is not None:
        raise AcceptanceProducerError("reset phase is valid only for cleanReset")
    if section == "cleanReset" and expected_reset_snapshot_digest is None:
        raise AcceptanceProducerError(
            "post-reset requires the approved reset snapshot digest"
        )
    try:
        epoch = ACCEPTANCE_EPOCH.load_deployment_epoch(
            directory=evidence_directory,
            private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
            key=trust.key,
            commit=targets.commit,
            cluster_uid=trust.cluster_uid,
            context=targets.context,
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=deployment_run_id,
        )
    except ACCEPTANCE_EPOCH.AcceptanceEpochError as exc:
        raise AcceptanceProducerError(str(exc)) from exc
    authentication_mode = _installation_identity_mode(targets, trust)
    if epoch["authenticationMode"] != authentication_mode:
        raise AcceptanceProducerError(
            "deployment epoch authentication mode does not match the installation"
        )
    if (
        section in {"identity", "adminDisableLogin"}
        and authentication_mode != "bundledKeycloak"
    ):
        raise AcceptanceProducerError(
            f"{section} is valid only for bundled Keycloak acceptance"
        )
    if section == "cleanReset" and (
        expected_reset_snapshot_digest != epoch["resetSnapshotSha256"]
    ):
        raise AcceptanceProducerError(
            "post-reset approval does not match the signed deployment epoch"
        )
    if section == "cleanReset":
        existing_report = _load_existing_clean_reset_report(
            path=evidence_directory / "cleanReset.json",
            validator=validator,
            contract=contract,
            targets=targets,
            epoch=epoch,
            signing_key=trust.key,
            clock=clock,
        )
        if existing_report is not None:
            return existing_report
    _require_predecessor_reports(
        section=section,
        directory=evidence_directory,
        validator=validator,
        contract=contract,
        targets=targets,
        epoch=epoch,
        signing_key=trust.key,
        clock=clock,
    )
    started: datetime
    if section != "soak":
        started = clock()
    report_workspace = None
    if scope == "workspace" and section != "oidcWorkspace":
        report_workspace = {
            "id": targets.workspace_id,
            "userSubject": targets.user_subject,
        }
    if section == "suites":
        suite_run_id = run_id_factory()
        suite_preflight, suite_source = _preflight_suite_release_inputs(
            image_inventory=image_inventory,
            targets=targets,
            trust=trust,
            runner=runner,
            directory=evidence_directory,
            run_id=suite_run_id,
        )
        try:
            observations, sources = _produce_suites(
                targets,
                evidence_directory,
                runner,
                clock,
                suite_preflight,
                suite_source,
                suite_run_id,
            )
        finally:
            primary_error = sys.exc_info()[1]
            _remove_materialized_suite_source_after_execution(
                source=suite_source,
                directory=evidence_directory,
                section="suites",
                run_id=suite_run_id,
                primary_error=primary_error,
            )
        finished = clock()
    elif section == "soak":
        identity_mode = _installation_identity_mode(targets, trust)
        expected_image_inventory = (
            private_root / "install" / targets.commit / "signed-image-inventory.json"
        )
        if image_inventory != expected_image_inventory:
            raise AcceptanceProducerError(
                "soak requires the canonical signed image inventory snapshot"
            )
        try:
            release_images = ACCEPTANCE_RELEASE.load_signed_image_inventory(
                path=image_inventory,
                private_root=private_root,
                key=trust.key,
                context=targets.context,
                commit=targets.commit,
                cluster_uid=trust.cluster_uid,
                installation_identity_sha256=(trust.installation_identity_sha256),
            )
            image_runtime_pairs = ACCEPTANCE_SOAK.release_image_runtime_pairs(
                release_images
            )
        except (
            ACCEPTANCE_RELEASE.AcceptanceReleaseError,
            ACCEPTANCE_SOAK.SoakValidationError,
        ) as exc:
            raise AcceptanceProducerError(str(exc)) from exc
        observations, sources, started, finished = _produce_soak(
            targets,
            identity_mode,
            evidence_directory,
            runner,
            clock,
            monotonic_clock,
            sleeper,
            soak_seconds,
            sample_interval,
            attempt_id=run_id_factory(),
            minimum_samples=soak_policy.minimum_samples,
            deployment_run_id=epoch["deploymentRunId"],
            maximum_sample_gap_seconds=soak_policy.maximum_sample_gap_seconds,
            maximum_clock_drift_milliseconds=(
                soak_policy.maximum_clock_drift_milliseconds
            ),
            image_runtime_pairs=image_runtime_pairs,
        )
    elif section == "cleanReset":
        try:
            snapshot = ACCEPTANCE_SNAPSHOT.load_reset_snapshot(
                directory=evidence_directory,
                private_root=ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT,
                key=trust.key,
                context=targets.context,
                commit=targets.commit,
                cluster_uid=trust.cluster_uid,
                installation_identity_sha256=trust.installation_identity_sha256,
                expected_run_id=deployment_run_id,
                expected_snapshot_sha256=expected_reset_snapshot_digest,
            )
        except ACCEPTANCE_SNAPSHOT.AcceptanceSnapshotError as exc:
            raise AcceptanceProducerError(str(exc)) from exc
        observations, sources = _produce_clean_reset(
            targets, evidence_directory, snapshot, runner
        )
        finished = clock()
    elif section in BROWSER_SECTIONS:
        observations, sources = _produce_browser_section(
            section=section,
            targets=targets,
            directory=evidence_directory,
            deployment_run_id=deployment_run_id,
            browser_ca=browser_ca,
            runner=runner,
            run_id=run_id_factory(),
            authentication_mode=authentication_mode,
        )
        if section == "oidcWorkspace":
            report_workspace = {
                "id": observations.get("createdWorkspaceId"),
                "userSubject": observations.get("userSubject"),
            }
        finished = clock()
    elif section == "offlineOidcConformance":
        observations, sources = _produce_offline_oidc_conformance(
            targets=targets,
            directory=evidence_directory,
            runner=runner,
            run_id=run_id_factory(),
        )
        finished = clock()
    else:
        if image_inventory is None:
            raise AcceptanceProducerError(
                "live oracle sections require --image-inventory"
            )
        observations, sources = _produce_oracle_section(
            section=section,
            targets=targets,
            directory=evidence_directory,
            image_inventory=image_inventory,
            trust=trust,
            runner=runner,
            run_id=run_id_factory(),
            deployment_run_id=deployment_run_id,
        )
        finished = clock()
    report = {
        "schemaVersion": contract["reportSchemaVersion"],
        "section": section,
        "commit": targets.commit,
        "deploymentRunId": epoch["deploymentRunId"],
        "authenticationMode": authentication_mode,
        "startedAt": _timestamp(started),
        "finishedAt": _timestamp(finished),
        "producer": {
            "id": PRODUCER_IDS[section],
            "executable": PRODUCER_EXECUTABLE,
            "version": contract["producerVersion"],
        },
        "probe": {
            "id": f"homelab-{section}",
            "kind": (
                "offline"
                if section == "offlineOidcConformance"
                else "container"
                if section == "suites"
                else "live"
            ),
        },
        "sources": sources,
        "observations": observations,
    }
    if report_workspace is not None:
        report["workspace"] = report_workspace
    report["signature"] = hmac.new(
        trust.key, _canonical(report), hashlib.sha256
    ).hexdigest()
    report_path = evidence_directory / f"{section}.json"
    report_raw = _canonical(report) + b"\n"
    if section != "soak":
        _write_private_snapshot(report_path, report_raw)
        return report_path

    published = False
    try:
        validator.validate_report_bytes(
            raw=report_raw,
            directory=evidence_directory,
            section="soak",
            contract=contract,
            expected_commit=targets.commit,
            epoch=epoch,
            signing_key=trust.key,
            private_root=private_root,
            canonical_kubeconfig=targets.kubeconfig,
            workspace=report_workspace,
            now=clock(),
        )
        _publish_private_snapshot_atomic(report_path, report_raw)
        published = True
        validated = validator.validate_report_file(
            directory=evidence_directory,
            section="soak",
            contract=contract,
            expected_commit=targets.commit,
            epoch=epoch,
            signing_key=trust.key,
            private_root=private_root,
            canonical_kubeconfig=targets.kubeconfig,
            workspace=report_workspace,
            now=clock(),
        )
        _write_soak_progress(
            directory=evidence_directory,
            attempt_id=observations["attemptId"],
            sequence=len(observations["samples"]) + 1,
            status="completed",
            started=started,
            observed=finished,
            elapsed_milliseconds=observations["monotonicDurationMilliseconds"],
            duration=soak_seconds,
            samples=observations["samples"],
            report_file=report_path.name,
            report_sha256=validated["sha256"],
        )
    except Exception as exc:
        rollback_failure: Exception | None = None
        if published:
            try:
                if not stat.S_ISREG(os.lstat(report_path).st_mode):
                    raise AcceptanceProducerError(
                        "newly published soak report is not a regular file"
                    )
                if (
                    _read_private_bytes(report_path, "newly published soak report")
                    != report_raw
                ):
                    raise AcceptanceProducerError(
                        "newly published soak report changed before rollback"
                    )
                _unlink_private_snapshot(
                    report_path,
                    "newly published soak report",
                )
            except (AcceptanceProducerError, OSError) as rollback_exc:
                rollback_failure = rollback_exc
        failures = [str(exc) or exc.__class__.__name__]
        if rollback_failure is not None:
            failures.append(str(rollback_failure))
        marker_failure: Exception | None = None
        try:
            _write_soak_progress(
                directory=evidence_directory,
                attempt_id=observations["attemptId"],
                sequence=len(observations["samples"]) + 1,
                status="observations-failed",
                started=started,
                observed=finished,
                elapsed_milliseconds=observations["monotonicDurationMilliseconds"],
                duration=soak_seconds,
                samples=observations["samples"],
                failures=failures,
            )
        except Exception as marker_exc:  # noqa: BLE001
            marker_failure = marker_exc
        secondary_failures = [
            failure
            for failure in (rollback_failure, marker_failure)
            if failure is not None
        ]
        if secondary_failures:
            raise SoakPublicationError(
                [exc, *secondary_failures]
            ) from secondary_failures[-1]
        if isinstance(exc, AcceptanceProducerError):
            raise
        if isinstance(exc, validator.AcceptanceEvidenceError):
            raise AcceptanceProducerError(str(exc)) from exc
        raise AcceptanceProducerError(str(exc) or exc.__class__.__name__) from exc
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=sorted(PRODUCER_IDS), required=True)
    parser.add_argument("--deployment-run-id", required=True)
    parser.add_argument("--image-inventory", type=Path)
    parser.add_argument("--browser-ca", type=Path)
    parser.add_argument("--reset-phase", choices=("pre-reset", "post-reset"))
    parser.add_argument("--expected-reset-snapshot-digest")
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--workspace-id")
    parser.add_argument("--user-subject")
    parser.add_argument("--platform-url", required=True)
    parser.add_argument("--issuer-url", required=True)
    parser.add_argument("--admin-console-url")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    targets = ProducerTargets(
        arguments.context,
        arguments.kubeconfig,
        arguments.workspace_id,
        arguments.user_subject,
        arguments.platform_url,
        arguments.issuer_url,
        arguments.admin_console_url,
        arguments.client_id,
        arguments.expected_commit,
    )
    try:
        produce(
            section=arguments.section,
            targets=targets,
            deployment_run_id=arguments.deployment_run_id,
            image_inventory=arguments.image_inventory,
            browser_ca=arguments.browser_ca,
            reset_phase=arguments.reset_phase,
            expected_reset_snapshot_digest=arguments.expected_reset_snapshot_digest,
        )
    except AcceptanceProducerError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
