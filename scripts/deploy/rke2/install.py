#!/usr/bin/env python3
"""Orchestrate a clean, ordered RKE2 Identity and core platform installation."""

from __future__ import annotations

import argparse
import errno
import fcntl
import importlib.util
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
IDENTITY_PROFILE_SCHEMA = (
    REPOSITORY_ROOT / "contracts/identity-installation/profile.schema.json"
)

try:
    from scripts.deploy.rke2 import (
        acceptance_cluster as ACCEPTANCE_CLUSTER,
        installation_state as INSTALLATION_STATE,
        installation_preparation as INSTALLATION_PREPARATION,
        private_input as PRIVATE_INPUT,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import acceptance_cluster as ACCEPTANCE_CLUSTER
    import installation_state as INSTALLATION_STATE
    import installation_preparation as INSTALLATION_PREPARATION
    import private_input as PRIVATE_INPUT


class InstallationError(RuntimeError):
    """Raised when installation validation or orchestration fails."""


class InstallationPhase(str, Enum):
    """Expose the three durable installation workflow phases."""

    VALIDATE = "validate"
    PREPARE_CLUSTER = "prepare-cluster"
    APPLY = "apply"


class InstallationPrerequisiteError(InstallationError):
    """Report a missing prerequisite without claiming validation passed."""

    exit_code = 78


class InstallationCommandError(
    InstallationError,
    INSTALLATION_PREPARATION.InstallationRunnerError,
):
    """Raised when a child command fails without exposing its output."""

    def __init__(self, *, command_identity: str, exit_code: int | None) -> None:
        self.command_identity = command_identity
        self.exit_code = exit_code
        if exit_code is None:
            self.safe_summary = f"command {command_identity} could not start"
        elif exit_code == 0:
            self.safe_summary = (
                f"command {command_identity} returned invalid text after exit code 0"
            )
        else:
            self.safe_summary = (
                f"command {command_identity} exited with code {exit_code}"
            )
        super().__init__(f"installation {self.safe_summary}")


class InstallationInterrupted(InstallationError):
    """Convert a catchable process signal into a transactional failure."""

    def __init__(self, signal_number: int) -> None:
        self.signal_number = signal_number
        self.exit_code = 128 + signal_number
        super().__init__("installation was interrupted")


class InstallationProcessQuiescenceError(InstallationError):
    """Preserve an interruption when its command process group cannot stop."""

    def __init__(self, interruption: InstallationInterrupted) -> None:
        self.interruption = interruption
        self.exit_code = interruption.exit_code
        super().__init__("interrupted command process group did not quiesce")


CommandRunner = Callable[..., str]
CANONICAL_SUBJECT_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _platform_admin_subject(core_values: Path) -> str:
    try:
        document = yaml.safe_load(core_values.read_text(encoding="utf-8"))
        subject = document["bootstrap"]["admin"]["subject"]
    except (OSError, UnicodeDecodeError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise InstallationPrerequisiteError(
            "core bootstrap administrator subject is unavailable"
        ) from exc
    if (
        not isinstance(subject, str)
        or CANONICAL_SUBJECT_PATTERN.fullmatch(subject) is None
    ):
        raise InstallationPrerequisiteError(
            "core bootstrap administrator subject is invalid"
        )
    return subject


def _postgres_enabled(values: Path, description: str) -> bool:
    try:
        document = yaml.safe_load(values.read_text(encoding="utf-8"))
        enabled = document["postgres"]["enabled"]
    except (OSError, UnicodeDecodeError, TypeError, KeyError, yaml.YAMLError) as exc:
        raise InstallationPrerequisiteError(
            f"{description} postgres.enabled is unavailable"
        ) from exc
    if not isinstance(enabled, bool):
        raise InstallationPrerequisiteError(
            f"{description} postgres.enabled is invalid"
        )
    return enabled


def _command_identity(command: list[str]) -> str:
    executable = Path(command[0]).name
    identity = executable
    if executable in {"python", "python3", "sh"} and len(command) > 1:
        script_identity = Path(command[1]).name
        if script_identity.endswith((".py", ".sh")):
            identity = script_identity
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identity) is None:
        return "unknown"
    return identity


def _safe_stage_failure(stage: str, error: Exception) -> str:
    message = f"installation failed during {stage}"
    if isinstance(error, InstallationCommandError):
        message += f" ({error.safe_summary})"
    return message


class InstallationRecoveryError(InstallationError):
    """Preserve a primary failure and every safe recovery failure."""

    def __init__(
        self,
        *,
        stage: str,
        primary_cause: Exception,
        core_rollback_cause: Exception | None = None,
        identity_recovery_cause: Exception | None = None,
        secret_restore_cause: Exception | None = None,
        process_quiescence_cause: Exception | None = None,
        transaction_cleanup_cause: Exception | None = None,
        recovery_result_cause: Exception | None = None,
        identity_recovery_skipped: bool = False,
    ) -> None:
        self.primary_cause = primary_cause
        self.core_rollback_cause = core_rollback_cause
        self.identity_recovery_cause = identity_recovery_cause
        self.secret_restore_cause = secret_restore_cause
        self.process_quiescence_cause = process_quiescence_cause
        self.transaction_cleanup_cause = transaction_cleanup_cause
        self.recovery_result_cause = recovery_result_cause
        self.identity_recovery_skipped = identity_recovery_skipped
        message = _safe_stage_failure(stage, primary_cause)
        if core_rollback_cause is not None:
            message += "; Core rollback failed"
        if secret_restore_cause is not None:
            message += "; installer-owned Secret restore failed"
        if identity_recovery_cause is not None:
            message += "; Identity recovery failed"
            if isinstance(identity_recovery_cause, InstallationCommandError):
                message += f" ({identity_recovery_cause.safe_summary})"
        if process_quiescence_cause is not None:
            message += "; interrupted command process group did not quiesce"
        if transaction_cleanup_cause is not None:
            message += "; installer private transaction cleanup failed"
        if recovery_result_cause is not None:
            message += "; installation recovery result could not be recorded"
        if identity_recovery_skipped:
            message += "; Identity recovery was skipped"
        super().__init__(message)


def _load_backend_preparer() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_install_backend_preparer",
        SCRIPT_DIRECTORY / "prepare_backend_attestor.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("backend attestor prerequisite validator is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


BACKEND_PREPARER = _load_backend_preparer()


def _load_installation_transaction() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_installation_transaction",
        SCRIPT_DIRECTORY / "installation_transaction.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation transaction contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_TRANSACTION = _load_installation_transaction()


def _process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process_group(process_group: int, signal_number: int) -> None:
    try:
        os.killpg(process_group, signal_number)
    except ProcessLookupError:
        pass


def _quiesce_interrupted_process(
    process: subprocess.Popen[bytes],
    interruption: InstallationInterrupted,
) -> None:
    """Stop an interrupted command tree before transactional recovery starts."""

    try:
        _signal_process_group(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if process.poll() is None or _process_group_exists(process.pid):
            _signal_process_group(process.pid, signal.SIGKILL)
            process.communicate(timeout=2)
        deadline = time.monotonic() + 2
        while _process_group_exists(process.pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        if process.poll() is None or _process_group_exists(process.pid):
            raise InstallationProcessQuiescenceError(interruption)
    except InstallationProcessQuiescenceError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallationProcessQuiescenceError(interruption) from exc


def _run_command(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    stdout_path: Path | None = None,
) -> str:
    command_identity = _command_identity(command)
    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    output_handle = None
    process: subprocess.Popen[bytes] | None = None
    try:
        if stdout_path is not None:
            output_handle = stdout_path.open("wb")
            os.fchmod(output_handle.fileno(), 0o600)
        process = subprocess.Popen(
            command,
            stdout=output_handle or subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=process_environment,
            cwd=REPOSITORY_ROOT,
            start_new_session=True,
        )
        stdout, _ = process.communicate()
    except InstallationInterrupted as exc:
        if process is not None:
            _quiesce_interrupted_process(process, exc)
        raise
    except OSError as exc:
        raise InstallationCommandError(
            command_identity=command_identity,
            exit_code=None,
        ) from exc
    finally:
        if output_handle is not None:
            output_handle.close()
    assert process is not None
    if process.returncode != 0:
        raise InstallationCommandError(
            command_identity=command_identity,
            exit_code=process.returncode,
        )
    if stdout_path is not None:
        stdout_path.chmod(0o600)
        return ""
    try:
        assert stdout is not None
        return stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallationCommandError(
            command_identity=command_identity,
            exit_code=process.returncode,
        ) from exc


def _reject_symlink_components(path: Path, description: str) -> None:
    try:
        PRIVATE_INPUT.reject_symlink_components(path, description)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationError(str(exc)) from exc


def _prepare_private_root(path: Path) -> None:
    try:
        PRIVATE_INPUT.validate_installation_private_root(
            path,
            repository_root=REPOSITORY_ROOT,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationError(str(exc)) from exc


@contextmanager
def _installation_lock(private_root: Path) -> Iterator[None]:
    """Lock the canonical private-root directory without creating an artifact."""

    _reject_symlink_components(private_root, "installation private root")
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
            raise InstallationError(
                "installation private root lock must be the canonical owner-controlled mode-0700 directory"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise InstallationError(
                    "another installation is already running"
                ) from exc
            raise InstallationError("installation lock is unavailable") from exc
        locked = True
        yield
    except InstallationError:
        raise
    except OSError as exc:
        raise InstallationError("installation lock is unavailable") from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


@contextmanager
def _installation_signal_boundary() -> Iterator[None]:
    """Turn SIGINT and SIGTERM into controlled transactional failures."""

    previous_handlers: dict[int, Any] = {}
    interruption_started = False

    def interrupt(signal_number: int, _: Any) -> None:
        nonlocal interruption_started
        if interruption_started:
            # The first signal owns quiescence and transactional recovery.
            return
        interruption_started = True
        raise InstallationInterrupted(signal_number)

    try:
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signal_number] = signal.getsignal(signal_number)
            signal.signal(signal_number, interrupt)
    except (OSError, ValueError) as exc:
        for signal_number, previous_handler in previous_handlers.items():
            signal.signal(signal_number, previous_handler)
        raise InstallationError("installation signal boundary is unavailable") from exc
    try:
        yield
    finally:
        for signal_number, previous_handler in previous_handlers.items():
            signal.signal(signal_number, previous_handler)


def _private_input(path: Path | None, description: str, private_root: Path) -> Path:
    try:
        if path is None:
            raise PRIVATE_INPUT.PrivateInputError(
                f"{description} must use an absolute path"
            )
        return PRIVATE_INPUT.validate_private_file(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationError(str(exc)) from exc


def _read_private_text(path: Path, description: str, private_root: Path) -> str:
    try:
        return PRIVATE_INPUT.read_private_text(
            path,
            description,
            private_root=private_root,
            maximum_size=1024 * 1024,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationError(str(exc)) from exc


def _validate_installation_identity(
    *,
    secret_store: Path,
    private_root: Path,
    context: str,
    cluster_uid: str,
    identity_profile: dict[str, Any],
) -> None:
    selected = identity_profile[identity_profile["mode"]]
    manifest_path = secret_store / "installation-identity.json"
    try:
        actual = json.loads(
            _read_private_text(
                manifest_path,
                "installation identity manifest",
                private_root,
            )
        )
    except json.JSONDecodeError as exc:
        raise InstallationError("installation identity manifest is invalid") from exc
    try:
        validated = INSTALLATION_STATE.validate_installation_identity_document(
            actual,
            cluster_uid=cluster_uid,
        )
        expected = INSTALLATION_STATE.installation_identity_document(
            installation_id=validated["installationId"],
            identity_mode=identity_profile["mode"],
            issuer_url=selected["issuerUrl"],
            client_id=selected["clientId"],
            cluster_uid=cluster_uid,
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise InstallationError(str(exc)) from exc
    if actual != expected:
        raise InstallationError("installation identity manifest does not match")


def _identity_release_inventory(
    *, context: str, environment: dict[str, str], runner: CommandRunner
) -> dict[str, Any] | None:
    output = runner(
        [
            "helm",
            "list",
            "--all",
            "--namespace",
            "aileron-identity-system",
            "--filter",
            "^aileron-identity$",
            "--output",
            "json",
            "--kube-context",
            context,
        ],
        environment=environment,
    )
    try:
        releases = json.loads(output)
    except json.JSONDecodeError as exc:
        raise InstallationError("Identity release inventory is invalid") from exc
    if not isinstance(releases, list) or len(releases) > 1:
        raise InstallationError("Identity release inventory is invalid")
    if not releases:
        return None
    release = releases[0]
    if not isinstance(release, dict) or release.get("name") != "aileron-identity":
        raise InstallationError("Identity release inventory is invalid")
    try:
        revision = int(release["revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InstallationError("Identity release revision is invalid") from exc
    status = release.get("status")
    if revision < 1 or not isinstance(status, str) or not status:
        raise InstallationError("Identity release revision is invalid")
    return {**release, "revision": revision, "status": status.lower()}


def _identity_release_history(
    *, context: str, environment: dict[str, str], runner: CommandRunner
) -> list[dict[str, Any]]:
    output = runner(
        [
            "helm",
            "history",
            "aileron-identity",
            "--namespace",
            "aileron-identity-system",
            "--output",
            "json",
            "--kube-context",
            context,
        ],
        environment=environment,
    )
    try:
        history = json.loads(output)
    except json.JSONDecodeError as exc:
        raise InstallationError("Identity release history is invalid") from exc
    if not isinstance(history, list) or not history:
        raise InstallationError("Identity release history is invalid")
    normalized: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            raise InstallationError("Identity release history is invalid")
        try:
            revision = int(item["revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InstallationError("Identity release history is invalid") from exc
        status = item.get("status")
        if revision < 1 or not isinstance(status, str) or not status:
            raise InstallationError("Identity release history is invalid")
        normalized.append({**item, "revision": revision, "status": status.lower()})
    return normalized


def _identity_previous_revision(
    *, context: str, environment: dict[str, str], runner: CommandRunner
) -> int | None:
    release = _identity_release_inventory(
        context=context,
        environment=environment,
        runner=runner,
    )
    if release is None:
        return None
    history = _identity_release_history(
        context=context,
        environment=environment,
        runner=runner,
    )
    deployed = [item["revision"] for item in history if item["status"] == "deployed"]
    if not deployed:
        raise InstallationError(
            "Identity release has no rollback-safe deployed revision"
        )
    return max(deployed)


def _recover_identity(
    *,
    previous_revision: int | None,
    context: str,
    environment: dict[str, str],
    runner: CommandRunner,
) -> None:
    release = _identity_release_inventory(
        context=context,
        environment=environment,
        runner=runner,
    )
    if previous_revision is None:
        if release is None:
            return
        runner(
            [
                "helm",
                "uninstall",
                "aileron-identity",
                "--namespace",
                "aileron-identity-system",
                "--kube-context",
                context,
                "--wait",
                "--timeout",
                "20m",
            ],
            environment=environment,
        )
        if (
            _identity_release_inventory(
                context=context,
                environment=environment,
                runner=runner,
            )
            is not None
        ):
            raise InstallationError("new Identity release still exists after recovery")
        return

    if release is None:
        raise InstallationError("previous Identity release disappeared during recovery")
    if release["revision"] == previous_revision and release["status"] == "deployed":
        return
    history = _identity_release_history(
        context=context,
        environment=environment,
        runner=runner,
    )
    if not any(item["revision"] == previous_revision for item in history):
        raise InstallationError(
            "previous Identity revision is unavailable for recovery"
        )
    runner(
        [
            "helm",
            "rollback",
            "aileron-identity",
            str(previous_revision),
            "--namespace",
            "aileron-identity-system",
            "--kube-context",
            context,
            "--wait",
            "--cleanup-on-fail",
            "--timeout",
            "20m",
        ],
        environment=environment,
    )
    recovered = _identity_release_inventory(
        context=context,
        environment=environment,
        runner=runner,
    )
    if recovered is None or recovered["status"] != "deployed":
        raise InstallationError("Identity release recovery did not converge")


def _set_tree_ownership(path: Path, uid: int, gid: int) -> None:
    entries = [path, *path.rglob("*")]
    if any(entry.is_symlink() for entry in entries):
        raise InstallationError(
            "platform artifact tree must not contain symbolic links"
        )
    for entry in entries:
        os.chown(entry, uid, gid, follow_symlinks=False)


def _recovery_operation(
    *, attempted: bool, succeeded: bool, skipped: bool
) -> dict[str, bool]:
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "skipped": skipped,
    }


def _primary_exit_status(error: Exception) -> int | None:
    exit_code = (
        error.exit_code
        if isinstance(error, (InstallationCommandError, InstallationInterrupted))
        else None
    )
    if isinstance(exit_code, int) and 1 <= exit_code <= 255:
        return exit_code
    return None


def _core_rollback_assessment(
    *, result_path: Path | None, expected_commit: str, primary_cause: Exception
) -> tuple[Exception | None, dict[str, bool]]:
    unknown = _recovery_operation(
        attempted=False,
        succeeded=False,
        skipped=False,
    )
    if result_path is None:
        return (
            InstallationError("Core deployment rollback state is unavailable"),
            unknown,
        )
    try:
        result = INSTALLATION_TRANSACTION.read_core_result(
            path=result_path,
            commit=expected_commit,
        )
    except Exception:
        return (
            InstallationError("Core deployment rollback state is unavailable"),
            unknown,
        )
    operation = _recovery_operation(
        attempted=result["coreRollbackAttempted"],
        succeeded=result["coreRollbackSucceeded"],
        skipped=not result["coreRollbackAttempted"],
    )
    expected_exit_code = (
        primary_cause.exit_code
        if isinstance(primary_cause, InstallationCommandError)
        else None
    )
    if (
        result["primaryExitCode"] == 0
        or expected_exit_code is not None
        and result["primaryExitCode"] != expected_exit_code
    ):
        return (
            InstallationError("Core deployment rollback state is inconsistent"),
            operation,
        )
    if result["coreRollbackAttempted"] and not result["coreRollbackSucceeded"]:
        return (
            InstallationError("Core release rollback did not succeed"),
            operation,
        )
    return None, operation


def _expected_namespace_targets(identity_mode: str) -> list[str]:
    targets = [
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    ]
    if identity_mode == "bundledKeycloak":
        targets.append("aileron-identity-system")
    return targets


def _parse_namespace_result(
    value: str,
    *,
    identity_mode: str,
    validate_only: bool,
) -> dict[str, Any]:
    try:
        document = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InstallationError("namespace phase result is invalid") from exc
    expected_keys = {
        "schemaVersion",
        "mode",
        "ready",
        "targetNamespaces",
        "targetNamespaceIdentities",
        "initiallyMissingNamespaces",
        "changedNamespaces",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise InstallationError("namespace phase result is invalid")
    expected_targets = _expected_namespace_targets(identity_mode)
    expected_mode = "validate" if validate_only else "prepare"
    if (
        document["schemaVersion"] != "aileron-installation-namespace-result/v2"
        or document["mode"] != expected_mode
        or document["targetNamespaces"] != expected_targets
        or not isinstance(document["ready"], bool)
    ):
        raise InstallationError("namespace phase result is inconsistent")
    for key in ("initiallyMissingNamespaces", "changedNamespaces"):
        values = document[key]
        if (
            not isinstance(values, list)
            or any(not isinstance(item, str) for item in values)
            or len(values) != len(set(values))
            or any(item not in expected_targets for item in values)
        ):
            raise InstallationError("namespace phase result is invalid")
    identities = document["targetNamespaceIdentities"]
    if not isinstance(identities, list):
        raise InstallationError("namespace phase result is invalid")
    identity_names: list[str] = []
    identity_uids: list[str] = []
    for identity in identities:
        if (
            not isinstance(identity, dict)
            or set(identity) != {"name", "uid"}
            or not isinstance(identity["name"], str)
            or not isinstance(identity["uid"], str)
            or not identity["uid"]
        ):
            raise InstallationError("namespace phase result is invalid")
        identity_names.append(identity["name"])
        identity_uids.append(identity["uid"])
    if len(identity_names) != len(set(identity_names)) or len(identity_uids) != len(
        set(identity_uids)
    ):
        raise InstallationError("namespace phase result is invalid")
    expected_identity_names = [
        namespace
        for namespace in expected_targets
        if namespace not in document["initiallyMissingNamespaces"]
    ]
    if validate_only:
        if identity_names != expected_identity_names:
            raise InstallationError("namespace phase result is inconsistent")
    elif identity_names != expected_targets:
        raise InstallationError("namespace phase result is inconsistent")
    if validate_only:
        if document["changedNamespaces"] or document["ready"] != (
            not document["initiallyMissingNamespaces"]
        ):
            raise InstallationError("namespace phase result is inconsistent")
    elif not document["ready"]:
        raise InstallationError("namespace preparation did not become ready")
    return document


def _run_namespace_phase(
    *,
    context: str,
    kubeconfig: Path,
    identity_mode: str,
    phase: InstallationPhase,
    environment: dict[str, str],
    runner: CommandRunner,
) -> dict[str, Any]:
    validate_only = phase is not InstallationPhase.PREPARE_CLUSTER
    command = [
        "python3",
        str(SCRIPT_DIRECTORY / "ensure_installation_namespaces.py"),
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        "--identity-mode",
        identity_mode,
    ]
    if validate_only:
        command.append("--validate-only")
    result = _parse_namespace_result(
        runner(command, environment=environment),
        identity_mode=identity_mode,
        validate_only=validate_only,
    )
    if not result["ready"]:
        missing = ", ".join(result["initiallyMissingNamespaces"])
        raise InstallationPrerequisiteError(
            "installation validation is incomplete because required namespaces "
            f"are absent ({missing}); no Kubernetes resources were created; run "
            "the prepare-cluster phase"
        )
    return result


def _namespace_uid_identity(result: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (identity["name"], identity["uid"])
        for identity in result["targetNamespaceIdentities"]
    )


def _install_rke2_locked(
    *,
    prepared: INSTALLATION_PREPARATION.PreparedInstallation,
    runner: CommandRunner = _run_command,
) -> None:
    """Execute one installation from an immutable prepared input boundary."""

    expected_commit = prepared.expected_commit
    context = prepared.context
    identity_mode = prepared.identity_mode
    work_directory = prepared.work_directory
    kubeconfig = prepared.snapshots.kubeconfig
    registry = prepared.registry
    project = prepared.project
    platform_url = prepared.platform_url
    harbor_dockerconfig = prepared.snapshots.harbor_dockerconfig
    apps_tls_cert = prepared.snapshots.apps_tls_cert
    apps_tls_key = prepared.snapshots.apps_tls_key
    apps_tls_ca = prepared.snapshots.apps_tls_ca
    oidc_ca = prepared.snapshots.oidc_ca
    turn_url = prepared.turn_url
    identity_tls_cert = prepared.snapshots.identity_tls_cert
    identity_tls_key = prepared.snapshots.identity_tls_key
    external_oidc_client_secret = prepared.snapshots.external_oidc_client_secret
    external_oidc_issuer_url = prepared.external_oidc_issuer_url
    phase = InstallationPhase(prepared.phase)
    private_root = prepared.private_root
    secret_store = prepared.secret_store
    snapshot_directory = prepared.snapshots.directory
    core_values_snapshot = prepared.snapshots.core_values
    identity_values_snapshot = prepared.snapshots.identity_values
    core_data_service_inputs = dict(prepared.snapshots.core_data_service_inputs)
    identity_database_username = prepared.snapshots.identity_database_username
    identity_database_password = prepared.snapshots.identity_database_password
    identity_database_ca = prepared.snapshots.identity_database_ca
    acceptance_trust = prepared.acceptance_trust
    workspace_manager_image = prepared.workspace_manager_image
    environment = {"KUBECONFIG": str(kubeconfig)}
    INSTALLATION_TRANSACTION.INSTALLATION_STATE.PRIVATE_ROOT = private_root

    def transaction_runner(
        command: list[str],
        *,
        stdout_path: Path | None = None,
    ) -> str:
        """Pin transaction Kubernetes calls to the flattened kubeconfig snapshot."""

        return runner(
            command,
            environment=environment,
            stdout_path=stdout_path,
        )

    def acceptance_runner(command: list[str]) -> bytes:
        try:
            return runner(command, environment=environment).encode("utf-8")
        except InstallationCommandError as exc:
            raise ACCEPTANCE_CLUSTER.AcceptanceClusterError(
                "live acceptance trust query failed"
            ) from exc

    def load_live_acceptance_trust(
        error_message: str,
    ) -> INSTALLATION_PREPARATION.PreparedAcceptanceTrust:
        try:
            trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
                context=context,
                kubeconfig=kubeconfig,
                runner=acceptance_runner,
            )
        except ACCEPTANCE_CLUSTER.AcceptanceClusterError as exc:
            raise InstallationError(error_message) from exc
        return INSTALLATION_PREPARATION.PreparedAcceptanceTrust(
            key=trust.key,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
            secret_uid=trust.secret_uid,
        )

    namespace_result = _run_namespace_phase(
        context=context,
        kubeconfig=kubeconfig,
        identity_mode=identity_mode,
        phase=phase,
        environment=environment,
        runner=runner,
    )
    namespace_uid_by_name = dict(_namespace_uid_identity(namespace_result))

    def backend_resource_runner(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> str:
        del stdin
        try:
            return runner(command, environment=environment)
        except InstallationCommandError as exc:
            raise BACKEND_PREPARER.BackendAttestorResourceValidationError(
                "retained backend attestor Kubernetes query failed"
            ) from exc

    def load_retained_backend_resources() -> dict[str, Any]:
        try:
            return BACKEND_PREPARER.validate_backend_attestor_resources(
                kubeconfig=kubeconfig,
                harbor_dockerconfig=harbor_dockerconfig,
                context=context,
                registry=registry,
                private_root=private_root,
                runner=backend_resource_runner,
            )
        except BACKEND_PREPARER.BackendAttestorResourceValidationError as exc:
            raise InstallationPrerequisiteError(
                "retained backend attestor prerequisite is invalid"
            ) from exc

    backend_resource_binding = load_retained_backend_resources()

    identity_manifest = snapshot_directory / "identity-rendered.yaml"
    previous_identity_revision: int | None = None
    identity_recovery_armed = False
    transaction_directory: Path | None = None
    secret_transaction_active = False
    core_result_path: Path | None = None
    core_deploy_invoked = False
    current_stage = "installation preparation"
    identity_secret_apply_command: list[str] | None = None
    try:
        if identity_mode == "bundledKeycloak":
            assert identity_values_snapshot is not None
            platform_admin_subject = _platform_admin_subject(core_values_snapshot)
            identity_postgres_enabled = _postgres_enabled(
                identity_values_snapshot,
                "Identity release values",
            )
            identity_artifacts = secret_store / "identity-artifacts"
            if not identity_postgres_enabled:
                identity_artifacts = identity_artifacts / "postgres-disabled"
            runner(
                [
                    "python3",
                    str(REPOSITORY_ROOT / "identity-installation/generate_secrets.py"),
                    "--output-dir",
                    str(identity_artifacts),
                    "--private-root",
                    str(private_root),
                    "--realm",
                    "aileron",
                    "--platform-origin",
                    platform_url,
                    "--client-id",
                    INSTALLATION_STATE.BUNDLED_CLIENT_ID,
                    "--platform-admin-subject",
                    platform_admin_subject,
                    "--homelab-insecure-defaults",
                    "--values",
                    str(identity_values_snapshot),
                ],
                environment=environment,
            )
            bundled_client_secret = _private_input(
                identity_artifacts / "aileron-oidc-client/client-secret",
                "bundled OIDC client Secret artifact",
                private_root,
            )
            identity_secret_apply_command = [
                "sh",
                str(REPOSITORY_ROOT / "identity-installation/apply_secrets.sh"),
                "--artifact-dir",
                str(identity_artifacts),
                "--private-root",
                str(private_root),
                "--context",
                context,
                "--kubeconfig",
                str(kubeconfig),
                "--namespace",
                "aileron-identity-system",
                "--expected-namespace-uid",
                namespace_uid_by_name["aileron-identity-system"],
                "--image-pull-secret-file",
                str(harbor_dockerconfig),
                "--tls-cert-file",
                str(identity_tls_cert),
                "--tls-key-file",
                str(identity_tls_key),
                "--values",
                str(identity_values_snapshot),
            ]
            if not identity_postgres_enabled:
                if any(
                    value is None
                    for value in (
                        identity_database_username,
                        identity_database_password,
                        identity_database_ca,
                    )
                ):
                    raise InstallationPrerequisiteError(
                        "External Identity database inputs are incomplete"
                    )
                identity_secret_apply_command.extend(
                    [
                        "--postgres-username-file",
                        str(identity_database_username),
                        "--postgres-password-file",
                        str(identity_database_password),
                        "--postgres-ca-file",
                        str(identity_database_ca),
                    ]
                )
            elif any(
                value is not None
                for value in (
                    identity_database_username,
                    identity_database_password,
                    identity_database_ca,
                )
            ):
                raise InstallationPrerequisiteError(
                    "Bundled Identity database forbids external database inputs"
                )
            runner(
                [*identity_secret_apply_command, "--dry-run"],
                environment=environment,
            )

            identity_values = [
                "--values",
                str(REPOSITORY_ROOT / "helm/values-rke2-207-homelab-identity.yaml"),
                "--values",
                str(identity_values_snapshot),
            ]
            runner(
                [
                    "helm",
                    "lint",
                    str(REPOSITORY_ROOT / "helm/aileron-identity"),
                    "--namespace",
                    "aileron-identity-system",
                    *identity_values,
                ],
                environment=environment,
            )
            runner(
                [
                    "helm",
                    "template",
                    "aileron-identity",
                    str(REPOSITORY_ROOT / "helm/aileron-identity"),
                    "--namespace",
                    "aileron-identity-system",
                    *identity_values,
                ],
                environment=environment,
                stdout_path=identity_manifest,
            )
            runner(
                [
                    "helm",
                    "upgrade",
                    "--install",
                    "aileron-identity",
                    str(REPOSITORY_ROOT / "helm/aileron-identity"),
                    "--namespace",
                    "aileron-identity-system",
                    "--kube-context",
                    context,
                    *identity_values,
                    "--dry-run=server",
                ],
                environment=environment,
            )
            oidc_client_secret = bundled_client_secret
            selected_oidc_issuer = INSTALLATION_STATE.BUNDLED_ISSUER_URL
        else:
            oidc_client_secret = external_oidc_client_secret
            selected_oidc_issuer = external_oidc_issuer_url

        platform_artifacts = secret_store / "platform-artifacts"
        platform_artifacts.mkdir(mode=0o700, exist_ok=True)
        platform_artifacts.chmod(0o700)
        manager_image = workspace_manager_image
        generator_uid = os.getuid() if os.getuid() != 0 else 65532
        generator_gid = os.getgid() if os.getuid() != 0 else 65532
        platform_registry = (
            REPOSITORY_ROOT / "contracts/platform-installation/secret-registry.json"
        )
        try:
            if os.geteuid() == 0:
                _set_tree_ownership(
                    platform_artifacts, generator_uid, generator_gid
                )
                os.chown(
                    core_values_snapshot,
                    generator_uid,
                    generator_gid,
                    follow_symlinks=False,
                )
            runner(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--user",
                    f"{generator_uid}:{generator_gid}",
                    "--volume",
                    f"{platform_artifacts}:/output",
                    "--volume",
                    f"{platform_registry}:/installation-contract/secret-registry.json:ro",
                    "--volume",
                    f"{core_values_snapshot}:/installation-contract/core-values.json:ro",
                    manager_image,
                    "/workspace-manager/.venv/bin/python",
                    "/workspace-manager/scripts/generate_platform_installation_secrets.py",
                    "/output",
                    "--registry",
                    "/installation-contract/secret-registry.json",
                    "--turn-url",
                    turn_url,
                    "--values",
                    "/installation-contract/core-values.json",
                ],
                environment=environment,
            )
        finally:
            if os.geteuid() == 0:
                os.chown(
                    core_values_snapshot,
                    0,
                    0,
                    follow_symlinks=False,
                )
                _set_tree_ownership(platform_artifacts, 0, 0)
        platform_apply_command = [
            "python3",
            str(SCRIPT_DIRECTORY / "apply_platform_secrets.py"),
            "--artifact-directory",
            str(platform_artifacts),
            "--context",
            context,
            "--kubeconfig",
            str(kubeconfig),
            "--expected-namespace-uid",
            f"workspace-system={namespace_uid_by_name['workspace-system']}",
            "--expected-namespace-uid",
            f"aileron-turn-system={namespace_uid_by_name['aileron-turn-system']}",
            "--external-input",
            f"oidc-client-secret={oidc_client_secret}",
            "--external-input",
            f"oidc-ca={oidc_ca}",
            "--external-input",
            f"apps-tls-cert={apps_tls_cert}",
            "--external-input",
            f"apps-tls-key={apps_tls_key}",
            "--external-input",
            f"apps-tls-ca={apps_tls_ca}",
            "--external-input",
            f"harbor-dockerconfig={harbor_dockerconfig}",
            "--values",
            str(core_values_snapshot),
        ]
        for artifact_id, path in sorted(core_data_service_inputs.items()):
            platform_apply_command.extend(["--external-input", f"{artifact_id}={path}"])
        runner(platform_apply_command, environment=environment)

        core_environment = {
            **environment,
            "IDENTITY_MODE": identity_mode,
        }
        if identity_mode == "bundledKeycloak":
            core_environment["IDENTITY_RENDERED_MANIFEST"] = str(identity_manifest)

        current_stage = "core preflight"
        runner(
            [
                str(SCRIPT_DIRECTORY / "preflight.sh"),
                "--commit",
                expected_commit,
                "--registry",
                registry,
                "--project",
                project,
                "--values",
                str(core_values_snapshot),
                "--harbor-dockerconfig",
                str(harbor_dockerconfig),
                "--apps-tls-cert",
                str(apps_tls_cert),
                "--platform-artifacts",
                str(platform_artifacts),
                "--kubeconfig",
                str(kubeconfig),
                "--context",
                context,
                "--namespace",
                "workspace-system",
            ],
            environment=core_environment,
        )

        if phase is InstallationPhase.APPLY:
            current_stage = "namespace mutation guard"
            guarded_namespace_result = _run_namespace_phase(
                context=context,
                kubeconfig=kubeconfig,
                identity_mode=identity_mode,
                phase=InstallationPhase.VALIDATE,
                environment=environment,
                runner=runner,
            )
            if _namespace_uid_identity(
                guarded_namespace_result
            ) != _namespace_uid_identity(namespace_result):
                raise InstallationError(
                    "namespace identity changed after installation validation"
                )

            current_stage = "acceptance trust mutation guard"
            guarded_acceptance_trust = load_live_acceptance_trust(
                "live acceptance trust changed after installation validation"
            )
            if guarded_acceptance_trust != acceptance_trust:
                raise InstallationError(
                    "live acceptance trust changed after installation validation"
                )

            current_stage = "retained backend attestor mutation guard"
            guarded_backend_resources = load_retained_backend_resources()
            if guarded_backend_resources != backend_resource_binding:
                raise InstallationPrerequisiteError(
                    "retained backend attestor prerequisite changed after validation"
                )

            current_stage = "installer Secret transaction snapshot"
            transaction_directory = (
                INSTALLATION_TRANSACTION.create_transaction_directory(
                    work_directory=work_directory,
                    commit=expected_commit,
                )
            )
            transaction_references = INSTALLATION_TRANSACTION.secret_references(
                identity_mode=identity_mode,
                registry_path=platform_registry,
            )
            transaction_namespaces = {
                namespace for namespace, _ in transaction_references
            }
            INSTALLATION_TRANSACTION.begin_secret_transaction(
                transaction_directory=transaction_directory,
                commit=expected_commit,
                context=context,
                identity_mode=identity_mode,
                expected_namespace_uids={
                    namespace: namespace_uid_by_name[namespace]
                    for namespace in transaction_namespaces
                },
                runner=transaction_runner,
                registry_path=platform_registry,
            )
            secret_transaction_active = True
            INSTALLATION_TRANSACTION.validate_secret_transaction_namespaces(
                transaction_directory=transaction_directory,
                commit=expected_commit,
                context=context,
                identity_mode=identity_mode,
                runner=transaction_runner,
                registry_path=platform_registry,
            )

            if identity_secret_apply_command is not None:
                current_stage = "bundled Identity Secret apply"
                runner(
                    [
                        *identity_secret_apply_command,
                        "--transaction-directory",
                        str(transaction_directory),
                        "--transaction-commit",
                        expected_commit,
                    ],
                    environment=environment,
                )
            current_stage = "platform Secret apply"
            runner(
                [
                    *platform_apply_command,
                    "--transaction-directory",
                    str(transaction_directory),
                    "--transaction-commit",
                    expected_commit,
                    "--transaction-identity-mode",
                    identity_mode,
                    "--apply",
                ],
                environment=environment,
            )

        if phase is InstallationPhase.APPLY and identity_mode == "bundledKeycloak":
            current_stage = "bundled Identity deployment"
            previous_identity_revision = _identity_previous_revision(
                context=context, environment=environment, runner=runner
            )
            identity_recovery_armed = True
            runner(
                [
                    "helm",
                    "upgrade",
                    "--install",
                    "aileron-identity",
                    str(REPOSITORY_ROOT / "helm/aileron-identity"),
                    "--namespace",
                    "aileron-identity-system",
                    "--kube-context",
                    context,
                    *identity_values,
                    "--atomic",
                    "--wait",
                    "--timeout",
                    "20m",
                    "--history-max",
                    "10",
                ],
                environment=environment,
            )
            current_stage = "bundled Identity rollout"
            runner(
                [
                    "kubectl",
                    "--context",
                    context,
                    "--namespace",
                    "aileron-identity-system",
                    "rollout",
                    "status",
                    "deployment/aileron-identity-keycloak",
                    "--timeout=10m",
                ],
                environment=environment,
            )

        if phase is InstallationPhase.APPLY:
            current_stage = "OIDC discovery readiness"
            runner(
                [
                    "python3",
                    str(SCRIPT_DIRECTORY / "wait_for_oidc.py"),
                    "--issuer-url",
                    str(selected_oidc_issuer),
                    "--ca-file",
                    str(oidc_ca),
                    "--timeout-seconds",
                    "600",
                ],
                environment=environment,
            )

        if phase is not InstallationPhase.APPLY:
            core_manifest = work_directory / "core-rendered.yaml"
            core_values = [
                "--values",
                str(REPOSITORY_ROOT / "helm/values-rke2-207-homelab.yaml"),
                "--values",
                str(core_values_snapshot),
            ]
            runner(
                [
                    "helm",
                    "lint",
                    str(REPOSITORY_ROOT / "helm/aileron"),
                    "--namespace",
                    "workspace-system",
                    *core_values,
                ],
                environment=environment,
            )
            runner(
                [
                    "helm",
                    "template",
                    "aileron",
                    str(REPOSITORY_ROOT / "helm/aileron"),
                    "--namespace",
                    "workspace-system",
                    "--include-crds",
                    *core_values,
                ],
                environment=environment,
                stdout_path=core_manifest,
            )
            runner(
                [
                    "helm",
                    "upgrade",
                    "--install",
                    "aileron",
                    str(REPOSITORY_ROOT / "helm/aileron"),
                    "--namespace",
                    "workspace-system",
                    "--kube-context",
                    context,
                    *core_values,
                    "--skip-crds",
                    "--dry-run=server",
                ],
                environment=environment,
            )
        else:
            current_stage = "core deployment"
            assert transaction_directory is not None
            core_result_path = INSTALLATION_TRANSACTION.prepare_core_result(
                transaction_directory=transaction_directory,
                commit=expected_commit,
            )
            core_deploy_invoked = True
            runner(
                [
                    str(SCRIPT_DIRECTORY / "deploy.sh"),
                    "--commit",
                    expected_commit,
                    "--registry",
                    registry,
                    "--project",
                    project,
                    "--values",
                    str(core_values_snapshot),
                    "--kubeconfig",
                    str(kubeconfig),
                    "--context",
                    context,
                    "--namespace",
                    "workspace-system",
                    "--identity-mode",
                    identity_mode,
                    *(
                        ["--identity-manifest", str(identity_manifest)]
                        if identity_mode == "bundledKeycloak"
                        else []
                    ),
                    "--harbor-dockerconfig",
                    str(harbor_dockerconfig),
                    "--apps-tls-cert",
                    str(apps_tls_cert),
                    "--oidc-issuer",
                    str(selected_oidc_issuer),
                    "--oidc-ca",
                    str(oidc_ca),
                    "--platform-artifacts",
                    str(platform_artifacts),
                    "--result-sidecar",
                    str(core_result_path),
                ],
                environment=core_environment,
            )
            core_result = INSTALLATION_TRANSACTION.read_core_result(
                path=core_result_path,
                commit=expected_commit,
            )
            if (
                core_result["primaryExitCode"] != 0
                or core_result["coreRollbackAttempted"]
                or core_result["coreRollbackSucceeded"]
            ):
                raise InstallationError(
                    "Core deployment result sidecar is inconsistent"
                )
    except Exception as exc:
        if isinstance(exc, InstallationProcessQuiescenceError):
            skipped_recovery = _recovery_operation(
                attempted=False,
                succeeded=False,
                skipped=True,
            )
            recovery_result_error: Exception | None = None
            if transaction_directory is not None:
                try:
                    INSTALLATION_TRANSACTION.write_install_recovery_result(
                        transaction_directory=transaction_directory,
                        commit=expected_commit,
                        primary_stage=current_stage,
                        primary_exit_code=_primary_exit_status(exc.interruption),
                        secret_restore=dict(skipped_recovery),
                        core_rollback=dict(skipped_recovery),
                        identity_recovery=dict(skipped_recovery),
                    )
                except Exception as result_error:
                    recovery_result_error = result_error
            raise InstallationRecoveryError(
                stage=current_stage,
                primary_cause=exc.interruption,
                process_quiescence_cause=exc,
                recovery_result_cause=recovery_result_error,
                identity_recovery_skipped=identity_recovery_armed,
            ) from exc.interruption
        if core_deploy_invoked:
            core_rollback_error, core_rollback_result = _core_rollback_assessment(
                result_path=core_result_path,
                expected_commit=expected_commit,
                primary_cause=exc,
            )
        else:
            core_rollback_error = None
            core_rollback_result = _recovery_operation(
                attempted=False,
                succeeded=False,
                skipped=True,
            )
        secret_restore_error: Exception | None = None
        secret_restored = False
        secret_restore_result = _recovery_operation(
            attempted=False,
            succeeded=False,
            skipped=not secret_transaction_active,
        )
        if secret_transaction_active:
            assert transaction_directory is not None
            secret_restore_result = _recovery_operation(
                attempted=True,
                succeeded=False,
                skipped=False,
            )
            try:
                INSTALLATION_TRANSACTION.restore_secret_transaction(
                    transaction_directory=transaction_directory,
                    commit=expected_commit,
                    context=context,
                    identity_mode=identity_mode,
                    runner=transaction_runner,
                    registry_path=platform_registry,
                )
                secret_restored = True
                secret_restore_result["succeeded"] = True
            except Exception as restore_error:
                secret_restore_error = restore_error

        identity_recovery_error: Exception | None = None
        identity_recovered = False
        identity_recovery_allowed = (
            identity_recovery_armed
            and core_rollback_error is None
            and (not secret_transaction_active or secret_restored)
        )
        identity_recovery_skipped = (
            identity_recovery_armed and not identity_recovery_allowed
        )
        identity_recovery_result = _recovery_operation(
            attempted=False,
            succeeded=False,
            skipped=not identity_recovery_allowed,
        )
        if identity_recovery_allowed:
            identity_recovery_result = _recovery_operation(
                attempted=True,
                succeeded=False,
                skipped=False,
            )
            try:
                _recover_identity(
                    previous_revision=previous_identity_revision,
                    context=context,
                    environment=environment,
                    runner=runner,
                )
                identity_recovered = True
                identity_recovery_result["succeeded"] = True
            except Exception as recovery_error:
                identity_recovery_error = recovery_error

        recovery_result_error: Exception | None = None
        if transaction_directory is not None:
            try:
                INSTALLATION_TRANSACTION.write_install_recovery_result(
                    transaction_directory=transaction_directory,
                    commit=expected_commit,
                    primary_stage=current_stage,
                    primary_exit_code=_primary_exit_status(exc),
                    secret_restore=secret_restore_result,
                    core_rollback=core_rollback_result,
                    identity_recovery=identity_recovery_result,
                )
            except Exception as result_error:
                recovery_result_error = result_error

        if any(
            error is not None
            for error in (
                core_rollback_error,
                identity_recovery_error,
                secret_restore_error,
                recovery_result_error,
            )
        ):
            raise InstallationRecoveryError(
                stage=current_stage,
                primary_cause=exc,
                core_rollback_cause=core_rollback_error,
                identity_recovery_cause=identity_recovery_error,
                secret_restore_cause=secret_restore_error,
                recovery_result_cause=recovery_result_error,
                identity_recovery_skipped=identity_recovery_skipped,
            ) from exc

        recovered = []
        if secret_restored:
            recovered.append("installer-owned Secret state was restored")
        if identity_recovered:
            recovered.append("Identity release was recovered")
        if recovered:
            raise InstallationError(
                _safe_stage_failure(current_stage, exc) + "; " + "; ".join(recovered)
            ) from exc
        if isinstance(exc, InstallationError):
            raise
        raise InstallationError("installation failed before release mutation") from exc

    if transaction_directory is not None:
        try:
            INSTALLATION_TRANSACTION.discard_transaction(
                transaction_directory=transaction_directory,
                commit=expected_commit,
            )
        except Exception as cleanup_error:
            current_stage = "installation transaction cleanup"
            recovery_result_error: Exception | None = None
            skipped_recovery = _recovery_operation(
                attempted=False,
                succeeded=False,
                skipped=True,
            )
            try:
                INSTALLATION_TRANSACTION.write_install_recovery_result(
                    transaction_directory=transaction_directory,
                    commit=expected_commit,
                    primary_stage=current_stage,
                    primary_exit_code=None,
                    secret_restore=dict(skipped_recovery),
                    core_rollback=dict(skipped_recovery),
                    identity_recovery=dict(skipped_recovery),
                )
            except Exception as result_error:
                recovery_result_error = result_error
            raise InstallationRecoveryError(
                stage=current_stage,
                primary_cause=cleanup_error,
                transaction_cleanup_cause=cleanup_error,
                recovery_result_cause=recovery_result_error,
            ) from cleanup_error


def install_rke2(
    *,
    expected_commit: str,
    context: str,
    identity_mode: str,
    inventory_path: Path,
    execution_profile: Path,
    work_directory: Path,
    kubeconfig: Path,
    registry: str,
    project: str,
    platform_url: str,
    harbor_dockerconfig: Path,
    apps_tls_cert: Path,
    apps_tls_key: Path,
    apps_tls_ca: Path,
    oidc_ca: Path,
    turn_url: str,
    identity_tls_cert: Path | None,
    identity_tls_key: Path | None,
    external_oidc_client_secret: Path | None,
    external_oidc_issuer_url: str | None,
    external_oidc_client_id: str | None,
    core_data_service_values: Path | None = None,
    identity_data_service_values: Path | None = None,
    core_data_service_inputs: tuple[tuple[str, Path], ...] = (),
    identity_database_username: Path | None = None,
    identity_database_password: Path | None = None,
    identity_database_ca: Path | None = None,
    phase: InstallationPhase = InstallationPhase.APPLY,
    confirm_create_namespaces: bool = False,
    runner: CommandRunner = _run_command,
) -> None:
    """Run one installation phase while holding the global installation lock."""

    try:
        selected_phase = InstallationPhase(phase)
    except ValueError as exc:
        raise InstallationError("installation phase is invalid") from exc
    if (
        selected_phase is InstallationPhase.PREPARE_CLUSTER
        and not confirm_create_namespaces
    ):
        raise InstallationError("prepare-cluster requires --confirm-create-namespaces")
    if (
        selected_phase is not InstallationPhase.PREPARE_CLUSTER
        and confirm_create_namespaces
    ):
        raise InstallationError(
            "--confirm-create-namespaces is only valid for prepare-cluster"
        )
    private_root = INSTALLATION_STATE.PRIVATE_ROOT
    _prepare_private_root(private_root)
    request = INSTALLATION_PREPARATION.InstallationPreparationRequest(
        expected_commit=expected_commit,
        context=context,
        registry=registry,
        project=project,
        platform_url=platform_url,
        turn_url=turn_url,
        phase=selected_phase.value,
        work_directory=work_directory,
        identity_profile_schema=IDENTITY_PROFILE_SCHEMA,
        sources=INSTALLATION_PREPARATION.InstallationSources(
            inventory=inventory_path,
            execution_profile=execution_profile,
            kubeconfig=kubeconfig,
            harbor_dockerconfig=harbor_dockerconfig,
            apps_tls_cert=apps_tls_cert,
            apps_tls_key=apps_tls_key,
            apps_tls_ca=apps_tls_ca,
            oidc_ca=oidc_ca,
            core_data_service_values=core_data_service_values,
            identity_data_service_values=identity_data_service_values,
            core_data_service_inputs=core_data_service_inputs,
            identity_database_username=identity_database_username,
            identity_database_password=identity_database_password,
            identity_database_ca=identity_database_ca,
        ),
        identity=INSTALLATION_PREPARATION.IdentitySelection(
            mode=identity_mode,
            tls_cert=identity_tls_cert,
            tls_key=identity_tls_key,
            external_client_secret=external_oidc_client_secret,
            external_issuer_url=external_oidc_issuer_url,
            external_client_id=external_oidc_client_id,
        ),
    )

    with _installation_lock(private_root):
        with _installation_signal_boundary():
            try:
                with INSTALLATION_PREPARATION.prepare_installation(
                    request,
                    runner,
                    _validate_installation_identity,
                ) as prepared:
                    _install_rke2_locked(
                        prepared=prepared,
                        runner=runner,
                    )
            except INSTALLATION_PREPARATION.InstallationPreparationError as exc:
                if exc.__cause__ is None:
                    raise InstallationError(str(exc)) from None
                raise InstallationError(str(exc)) from exc.__cause__


def _path(value: str) -> Path:
    return Path(value)


def _core_data_service_input(value: str) -> tuple[str, Path]:
    artifact_id, separator, raw_path = value.partition("=")
    if (
        separator != "="
        or re.fullmatch(r"[a-z0-9][a-z0-9-]*", artifact_id) is None
        or not raw_path
    ):
        raise argparse.ArgumentTypeError(
            "Core data-service input must use ARTIFACT_ID=/absolute/path"
        )
    path = Path(raw_path)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "Core data-service input path must be absolute"
        )
    return artifact_id, path


def _safe_failure_exit_code(error: InstallationError) -> int:
    primary = (
        error.primary_cause if isinstance(error, InstallationRecoveryError) else error
    )
    if isinstance(primary, InstallationPrerequisiteError):
        return primary.exit_code
    if (
        isinstance(primary, InstallationCommandError)
        and isinstance(primary.exit_code, int)
        and 1 <= primary.exit_code <= 125
    ):
        return primary.exit_code
    return 70


def _add_installation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--commit", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument(
        "--identity-mode", choices=("bundledKeycloak", "externalOidc"), required=True
    )
    parser.add_argument("--inventory", type=_path, required=True)
    parser.add_argument("--execution-profile", type=_path, required=True)
    parser.add_argument("--work-directory", type=_path, required=True)
    parser.add_argument("--kubeconfig", type=_path, required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--platform-url", required=True)
    parser.add_argument("--harbor-dockerconfig", type=_path, required=True)
    parser.add_argument("--apps-tls-cert", type=_path, required=True)
    parser.add_argument("--apps-tls-key", type=_path, required=True)
    parser.add_argument("--apps-tls-ca", type=_path, required=True)
    parser.add_argument("--oidc-ca", type=_path, required=True)
    parser.add_argument("--turn-url", required=True)
    parser.add_argument("--identity-tls-cert", type=_path)
    parser.add_argument("--identity-tls-key", type=_path)
    parser.add_argument("--external-oidc-client-secret", type=_path)
    parser.add_argument("--external-oidc-issuer-url")
    parser.add_argument("--external-oidc-client-id")
    parser.add_argument("--core-data-service-values", type=_path)
    parser.add_argument("--identity-data-service-values", type=_path)
    parser.add_argument(
        "--core-data-service-input",
        action="append",
        type=_core_data_service_input,
        default=[],
    )
    parser.add_argument("--identity-database-username", type=_path)
    parser.add_argument("--identity-database-password", type=_path)
    parser.add_argument("--identity-database-ca", type=_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="phase", required=True)
    for phase in InstallationPhase:
        phase_parser = subparsers.add_parser(phase.value)
        _add_installation_arguments(phase_parser)
        if phase is InstallationPhase.PREPARE_CLUSTER:
            phase_parser.add_argument(
                "--confirm-create-namespaces",
                action="store_true",
                required=True,
            )
    arguments = parser.parse_args()
    phase = InstallationPhase(arguments.phase)
    try:
        install_rke2(
            expected_commit=arguments.commit,
            context=arguments.context,
            identity_mode=arguments.identity_mode,
            inventory_path=arguments.inventory,
            execution_profile=arguments.execution_profile,
            work_directory=arguments.work_directory,
            kubeconfig=arguments.kubeconfig,
            registry=arguments.registry,
            project=arguments.project,
            platform_url=arguments.platform_url,
            harbor_dockerconfig=arguments.harbor_dockerconfig,
            apps_tls_cert=arguments.apps_tls_cert,
            apps_tls_key=arguments.apps_tls_key,
            apps_tls_ca=arguments.apps_tls_ca,
            oidc_ca=arguments.oidc_ca,
            turn_url=arguments.turn_url,
            identity_tls_cert=arguments.identity_tls_cert,
            identity_tls_key=arguments.identity_tls_key,
            external_oidc_client_secret=arguments.external_oidc_client_secret,
            external_oidc_issuer_url=arguments.external_oidc_issuer_url,
            external_oidc_client_id=arguments.external_oidc_client_id,
            core_data_service_values=arguments.core_data_service_values,
            identity_data_service_values=arguments.identity_data_service_values,
            core_data_service_inputs=tuple(arguments.core_data_service_input),
            identity_database_username=arguments.identity_database_username,
            identity_database_password=arguments.identity_database_password,
            identity_database_ca=arguments.identity_database_ca,
            phase=phase,
            confirm_create_namespaces=getattr(
                arguments, "confirm_create_namespaces", False
            ),
        )
    except InstallationError as exc:
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return _safe_failure_exit_code(exc)
    success_messages = {
        InstallationPhase.VALIDATE: "installation-validation=passed",
        InstallationPhase.PREPARE_CLUSTER: (
            "installation-preparation=passed persisted=namespaces-only"
        ),
        InstallationPhase.APPLY: "installation=passed",
    }
    print(success_messages[phase])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
