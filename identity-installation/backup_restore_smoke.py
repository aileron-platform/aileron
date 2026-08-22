#!/usr/bin/env python3
"""Run an explicit destructive backup/restore smoke against Identity PostgreSQL."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import secrets
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

IDENTITY_JOB_TRANSACTION_ANNOTATION = "platform.aileron.dev/identity-data-transaction"
IDENTITY_JOB_TRANSACTION_PATTERN = re.compile(r"[0-9a-f]{64}")
IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS = 3
IDENTITY_JOB_READBACK_ATTEMPTS = 3
IDENTITY_JOB_READBACK_INTERVAL_SECONDS = 1
IDENTITY_JOB_CLEANUP_ABSENCE_TIMEOUT_SECONDS = 120
IDENTITY_JOB_CLEANUP_POLL_INTERVAL_SECONDS = 2
SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def _load_local_module(name: str) -> Any:
    path = SCRIPT_DIRECTORY.parent / "scripts/deploy/rke2" / f"{name}.py"
    specification = importlib.util.spec_from_file_location(
        f"identity_backup_restore_{name}",
        path,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Identity cleanup dependency is unavailable: {name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


KUBERNETES_REST = _load_local_module("kubernetes_rest")
DeleteClientLoader = Callable[..., Any]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class Config:
    context: str
    kubeconfig: Path
    namespace: str
    release: str
    expected_commit: str
    release_revision: int
    chart_version: str
    chart_digest: str
    keycloak_image: str
    keycloak_runtime_image: str
    postgres_image: str
    postgres_runtime_image: str
    confirmation: str
    timeout: str = "10m"


@dataclass(frozen=True)
class _DatabaseExecutionTarget:
    pod_name: str
    pod_uid: str
    container_name: str


@dataclass(frozen=True)
class _DatabaseJobExecutionTarget:
    template: dict


class IdentitySmokeCleanupError(RuntimeError):
    def __init__(self, failures: list[Exception]) -> None:
        self.failures = tuple(failures)
        super().__init__(
            "Identity smoke cleanup failed: "
            + "; ".join(str(failure) for failure in self.failures)
        )


def _expanded_failures(error: Exception) -> list[Exception]:
    if isinstance(error, IdentitySmokeCleanupError):
        return list(error.failures)
    return [error]


class Runner:
    def run(
        self,
        args: list[str],
        *,
        operation: str | None = None,
        stdin: str | None = None,
    ) -> str:
        completed = subprocess.run(
            args,
            input=stdin,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


class RecordingRunner(Runner):
    """Deterministic runner used by the container unit test."""

    def __init__(self, *, outputs: dict[tuple[str, ...], str] | None = None) -> None:
        self.outputs = outputs or {}
        self.operations: list[str] = []
        self.commands: list[tuple[str, ...]] = []
        self.stdins: list[str | None] = []

    def run(
        self,
        args: list[str],
        *,
        operation: str | None = None,
        stdin: str | None = None,
    ) -> str:
        if operation:
            self.operations.append(operation)
        command = tuple(args)
        self.commands.append(command)
        self.stdins.append(stdin)
        command_text = " ".join([*args, operation or ""])
        for key, output in self.outputs.items():
            if all(part in command_text for part in key):
                return output
        return "1\n" if "replicas" in " ".join(args) else ""


def _kubectl(config: Config, *args: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(config.kubeconfig),
        "--context",
        config.context,
        *args,
    ]


def _helm(config: Config, *args: str) -> list[str]:
    return [
        "helm",
        "--kubeconfig",
        str(config.kubeconfig),
        "--kube-context",
        config.context,
        *args,
    ]


def _load_job_delete_client(
    config: Config,
    loader: DeleteClientLoader,
) -> Any:
    private_root = config.kubeconfig.parent
    return loader(
        kubeconfig=config.kubeconfig,
        context=config.context,
        credential_directory=private_root,
        private_root=private_root,
    )


def _database_command(
    action: str,
    secret_directory: str = "/run/secrets/identity-postgres",
) -> str:
    secret_root = shlex.quote(secret_directory.rstrip("/"))
    common = (
        "umask 077; "
        f"username=$(cat {secret_root}/username); "
        f"password=$(cat {secret_root}/password); "
        "pgpass=/tmp/aileron-identity-smoke.pgpass; "
        "trap 'rm -f -- \"$pgpass\"' EXIT INT TERM; "
        'printf \'*:*:*:%s:%s\\n\' "$username" "$password" >"$pgpass"; '
        'chmod 0600 "$pgpass"; unset password; export PGPASSFILE="$pgpass"; '
    )
    statements = {
        "create-marker": (
            "CREATE TABLE IF NOT EXISTS aileron_backup_restore_smoke "
            "(marker text PRIMARY KEY); "
            "INSERT INTO aileron_backup_restore_smoke(marker) VALUES "
            "('identity-smoke-marker') ON CONFLICT DO NOTHING;"
        ),
        "drop-marker": "DROP TABLE aileron_backup_restore_smoke;",
        "verify-marker": (
            "SELECT marker FROM aileron_backup_restore_smoke "
            "WHERE marker = 'identity-smoke-marker';"
        ),
    }
    return common + (
        'psql --username="$username" --dbname="$DATABASE_URL" '
        f'--tuples-only --no-align --command="{statements[action]}"'
    )


def _database_job(template: dict, action: str) -> dict:
    operation = f"database-{action}"
    job = copy.deepcopy(template)
    metadata = job["metadata"]
    spec = job["spec"]
    pod_template = spec["template"]
    pod_metadata = pod_template["metadata"]
    pod_spec = pod_template["spec"]
    container = pod_spec["containers"][0]
    metadata["name"] = f"aileron-identity-{operation}"
    metadata["annotations"] = {
        key: value
        for key, value in metadata["annotations"].items()
        if not key.startswith("helm.sh/")
    }
    pod_metadata["labels"] = {
        "app.kubernetes.io/name": f"aileron-identity-{operation}",
        "platform.aileron.dev/identity-data-operation": "database-smoke",
    }
    container["name"] = operation
    container["args"] = [_database_command(action)]
    container["volumeMounts"] = [
        mount for mount in container["volumeMounts"] if mount["name"] != "backup"
    ]
    pod_spec["volumes"] = [
        volume for volume in pod_spec["volumes"] if volume["name"] != "backup"
    ]
    return job


def _validate_database_target_readback(
    config: Config,
    target: _DatabaseExecutionTarget,
    document: object,
) -> None:
    metadata = document.get("metadata") if isinstance(document, dict) else None
    spec = document.get("spec") if isinstance(document, dict) else None
    status = document.get("status") if isinstance(document, dict) else None
    containers = spec.get("containers") if isinstance(spec, dict) else None
    container_statuses = (
        status.get("containerStatuses") if isinstance(status, dict) else None
    )
    container = (
        containers[0] if isinstance(containers, list) and len(containers) == 1 else None
    )
    container_status = (
        container_statuses[0]
        if isinstance(container_statuses, list) and len(container_statuses) == 1
        else None
    )
    state = (
        container_status.get("state") if isinstance(container_status, dict) else None
    )
    running = state.get("running") if isinstance(state, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "v1"
        or document.get("kind") != "Pod"
        or not isinstance(metadata, dict)
        or metadata.get("name") != target.pod_name
        or metadata.get("uid") != target.pod_uid
        or metadata.get("namespace") != config.namespace
        or "deletionTimestamp" in metadata
        or not isinstance(container, dict)
        or container.get("name") != target.container_name
        or container.get("image") != config.postgres_image
        or not isinstance(status, dict)
        or status.get("phase") != "Running"
        or not isinstance(container_status, dict)
        or container_status.get("name") != target.container_name
        or not _container_status_image_matches_requested(
            container_status.get("image"),
            config.postgres_image,
        )
        or not _runtime_image_id_matches(
            container_status.get("imageID"),
            config.postgres_image,
            config.postgres_runtime_image,
        )
        or container_status.get("restartCount") != 0
        or container_status.get("ready") is not True
        or container_status.get("started") is not True
        or not isinstance(state, dict)
        or set(state) != {"running"}
        or not isinstance(running, dict)
        or not _utc_timestamp(running.get("startedAt"))
    ):
        raise RuntimeError("Identity PostgreSQL execution Pod changed identity")


def _exec_database(
    config: Config,
    runner: Runner,
    target: _DatabaseExecutionTarget | _DatabaseJobExecutionTarget,
    action: str,
    *,
    delete_client: Any | None = None,
    cleanup_sleeper: Sleeper = time.sleep,
    immutable_image: str | None = None,
    runtime_immutable_image: str | None = None,
) -> str:
    if isinstance(target, _DatabaseJobExecutionTarget):
        if (
            delete_client is None
            or immutable_image is None
            or runtime_immutable_image is None
        ):
            raise RuntimeError("external database smoke execution inputs are invalid")
        output: list[str] = []
        _run_job(
            config,
            runner,
            delete_client=delete_client,
            cleanup_sleeper=cleanup_sleeper,
            operation=f"database-{action}",
            expected_job=_database_job(target.template, action),
            immutable_image=immutable_image,
            runtime_immutable_image=runtime_immutable_image,
            output=output,
        )
        return output[0]
    target_raw = runner.run(
        _kubectl(
            config,
            "get",
            "pod",
            target.pod_name,
            "-n",
            config.namespace,
            "--output=json",
        )
    )
    try:
        target_document = json.loads(target_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Identity PostgreSQL execution Pod readback is invalid JSON"
        ) from exc
    _validate_database_target_readback(config, target, target_document)
    return runner.run(
        _kubectl(
            config,
            "exec",
            f"pod/{target.pod_name}",
            "-n",
            config.namespace,
            f"--container={target.container_name}",
            "--",
            "/bin/sh",
            "-ec",
            _database_command(action),
        ),
        operation=action,
    )


def _remove_known_default(document: dict, key: str, value: object) -> bool:
    if key not in document:
        return True
    if document[key] != value:
        return False
    del document[key]
    return True


def _canonical_job_spec(
    expected: object,
    actual: object,
    *,
    job_uid: str,
    job_name: str,
) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    canonical_expected = copy.deepcopy(expected)
    normalized = copy.deepcopy(actual)
    defaults = {
        "completionMode": "NonIndexed",
        "completions": 1,
        "manualSelector": False,
        "parallelism": 1,
        "suspend": False,
    }
    for document in (canonical_expected, normalized):
        if any(
            not _remove_known_default(document, key, value)
            for key, value in defaults.items()
        ):
            return False
    if (
        canonical_expected.pop("podReplacementPolicy", "TerminatingOrFailed")
        != "TerminatingOrFailed"
        or normalized.pop("podReplacementPolicy", None) != "TerminatingOrFailed"
    ):
        return False
    if canonical_expected.pop("selector", None) is not None:
        return False
    selector = normalized.pop("selector", None)
    if selector != {"matchLabels": {"batch.kubernetes.io/controller-uid": job_uid}}:
        return False
    expected_template = canonical_expected.get("template")
    actual_template = normalized.get("template")
    if not isinstance(expected_template, dict) or not isinstance(actual_template, dict):
        return False
    expected_metadata = expected_template.get("metadata")
    actual_metadata = actual_template.get("metadata")
    if not isinstance(expected_metadata, dict) or not isinstance(actual_metadata, dict):
        return False
    if not _remove_known_default(expected_metadata, "creationTimestamp", None):
        return False
    if actual_metadata.pop("creationTimestamp", None) is not None:
        return False
    expected_labels = expected_metadata.get("labels")
    if not isinstance(expected_labels, dict):
        return False
    controller_labels = {
        "batch.kubernetes.io/controller-uid": job_uid,
        "batch.kubernetes.io/job-name": job_name,
        "controller-uid": job_uid,
        "job-name": job_name,
    }
    if actual_metadata.get("labels") != {**expected_labels, **controller_labels}:
        return False
    actual_metadata["labels"] = expected_labels
    expected_pod_spec = expected_template.get("spec")
    actual_pod_spec = actual_template.get("spec")
    if not isinstance(expected_pod_spec, dict) or not isinstance(actual_pod_spec, dict):
        return False
    pod_defaults = {
        "dnsPolicy": "ClusterFirst",
        "schedulerName": "default-scheduler",
        "terminationGracePeriodSeconds": 30,
    }
    for key, value in pod_defaults.items():
        if not _remove_known_default(expected_pod_spec, key, value):
            return False
        if actual_pod_spec.pop(key, None) != value:
            return False
    expected_containers = expected_pod_spec.get("containers")
    actual_containers = actual_pod_spec.get("containers")
    if (
        not isinstance(expected_containers, list)
        or not isinstance(actual_containers, list)
        or len(expected_containers) != 1
        or len(actual_containers) != 1
        or not isinstance(expected_containers[0], dict)
        or not isinstance(actual_containers[0], dict)
    ):
        return False
    expected_container = expected_containers[0]
    actual_container = actual_containers[0]
    container_defaults = {
        "imagePullPolicy": "IfNotPresent",
        "resources": {},
        "terminationMessagePath": "/dev/termination-log",
        "terminationMessagePolicy": "File",
    }
    for key, value in container_defaults.items():
        if not _remove_known_default(expected_container, key, value):
            return False
        if actual_container.pop(key, None) != value:
            return False
    return normalized == canonical_expected


def _validate_existing_job(
    config: Config,
    expected_job: object,
    actual_job: object,
) -> str:
    expected_metadata = (
        expected_job.get("metadata") if isinstance(expected_job, dict) else None
    )
    actual_metadata = (
        actual_job.get("metadata") if isinstance(actual_job, dict) else None
    )
    expected_name = (
        expected_metadata.get("name") if isinstance(expected_metadata, dict) else None
    )
    job_uid = actual_metadata.get("uid") if isinstance(actual_metadata, dict) else None
    if (
        not isinstance(expected_job, dict)
        or expected_job.get("apiVersion") != "batch/v1"
        or expected_job.get("kind") != "Job"
        or not isinstance(expected_metadata, dict)
        or not isinstance(expected_name, str)
        or not expected_name
        or expected_metadata.get("namespace", config.namespace) != config.namespace
        or not isinstance(expected_metadata.get("labels"), dict)
        or not isinstance(expected_metadata.get("annotations"), dict)
        or expected_metadata.get("ownerReferences", []) != []
        or "deletionTimestamp" in expected_metadata
        or not isinstance(actual_job, dict)
        or actual_job.get("apiVersion") != "batch/v1"
        or actual_job.get("kind") != "Job"
        or not isinstance(actual_metadata, dict)
        or actual_metadata.get("name") != expected_name
        or actual_metadata.get("namespace") != config.namespace
        or not isinstance(job_uid, str)
        or not job_uid
        or actual_metadata.get("labels") != expected_metadata["labels"]
        or actual_metadata.get("annotations") != expected_metadata["annotations"]
        or actual_metadata.get("ownerReferences", []) != []
        or actual_metadata.get("finalizers", []) != []
        or "deletionTimestamp" in actual_metadata
        or not _canonical_job_spec(
            expected_job.get("spec"),
            actual_job.get("spec"),
            job_uid=job_uid,
            job_name=expected_name,
        )
    ):
        raise RuntimeError("existing Identity data Job identity is invalid")
    return job_uid


def _job_with_transaction(expected_job: dict, transaction_token: str) -> dict:
    if IDENTITY_JOB_TRANSACTION_PATTERN.fullmatch(transaction_token) is None:
        raise RuntimeError("Identity data Job transaction token is invalid")
    transaction_job = copy.deepcopy(expected_job)
    metadata = transaction_job.get("metadata")
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    if (
        not isinstance(metadata, dict)
        or not isinstance(annotations, dict)
        or IDENTITY_JOB_TRANSACTION_ANNOTATION in annotations
    ):
        raise RuntimeError("expected Identity data Job transaction identity is invalid")
    annotations[IDENTITY_JOB_TRANSACTION_ANNOTATION] = transaction_token
    return transaction_job


def _job_resource_version(actual_job: object) -> str:
    metadata = actual_job.get("metadata") if isinstance(actual_job, dict) else None
    resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, dict) else None
    )
    if (
        not isinstance(resource_version, str)
        or not resource_version
        or resource_version != resource_version.strip()
    ):
        raise RuntimeError("Identity data Job resourceVersion is invalid")
    return resource_version


def _validate_job_cleanup_identity(
    config: Config,
    expected_job: dict,
    actual_job: object,
    *,
    transaction_token: str,
    expected_uid: str | None = None,
) -> str:
    if IDENTITY_JOB_TRANSACTION_PATTERN.fullmatch(transaction_token) is None:
        raise RuntimeError("Identity data Job transaction token is invalid")
    _job_resource_version(actual_job)
    expected_metadata = expected_job.get("metadata")
    actual_metadata = (
        actual_job.get("metadata") if isinstance(actual_job, dict) else None
    )
    expected_labels = (
        expected_metadata.get("labels") if isinstance(expected_metadata, dict) else None
    )
    expected_annotations = (
        expected_metadata.get("annotations")
        if isinstance(expected_metadata, dict)
        else None
    )
    actual_labels = (
        actual_metadata.get("labels") if isinstance(actual_metadata, dict) else None
    )
    actual_annotations = (
        actual_metadata.get("annotations")
        if isinstance(actual_metadata, dict)
        else None
    )
    expected_name = (
        expected_metadata.get("name") if isinstance(expected_metadata, dict) else None
    )
    actual_uid = (
        actual_metadata.get("uid") if isinstance(actual_metadata, dict) else None
    )
    if (
        not isinstance(actual_job, dict)
        or actual_job.get("apiVersion") != "batch/v1"
        or actual_job.get("kind") != "Job"
        or not isinstance(expected_metadata, dict)
        or not isinstance(expected_name, str)
        or not expected_name
        or not isinstance(expected_labels, dict)
        or not isinstance(expected_annotations, dict)
        or not isinstance(actual_metadata, dict)
        or actual_metadata.get("name") != expected_name
        or actual_metadata.get("namespace") != config.namespace
        or not isinstance(actual_uid, str)
        or not actual_uid
        or (expected_uid is not None and actual_uid != expected_uid)
        or not isinstance(actual_labels, dict)
        or any(
            actual_labels.get(key) != value for key, value in expected_labels.items()
        )
        or not isinstance(actual_annotations, dict)
        or any(
            actual_annotations.get(key) != value
            for key, value in expected_annotations.items()
        )
        or actual_annotations.get(IDENTITY_JOB_TRANSACTION_ANNOTATION)
        != transaction_token
    ):
        raise RuntimeError("Identity data Job cleanup identity is invalid")
    return actual_uid


def _validate_prior_transaction_job(
    config: Config,
    expected_job: dict,
    actual_job: object,
) -> tuple[str, str]:
    metadata = actual_job.get("metadata") if isinstance(actual_job, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    transaction_token = (
        annotations.get(IDENTITY_JOB_TRANSACTION_ANNOTATION)
        if isinstance(annotations, dict)
        else None
    )
    if (
        not isinstance(transaction_token, str)
        or IDENTITY_JOB_TRANSACTION_PATTERN.fullmatch(transaction_token) is None
    ):
        raise RuntimeError("existing Identity data Job transaction identity is invalid")
    transaction_job = _job_with_transaction(expected_job, transaction_token)
    return transaction_token, _validate_existing_job(
        config,
        transaction_job,
        actual_job,
    )


def _require_empty_job_pod_inventory(
    config: Config,
    runner: Runner,
    *,
    job_name: str,
    selector: str,
) -> None:
    if not _job_pod_inventory_is_empty(
        config,
        runner,
        job_name=job_name,
        selector=selector,
    ):
        raise RuntimeError(
            f"{job_name} Pod inventory is invalid or nonempty after deletion"
        )


def _job_pod_inventory_is_empty(
    config: Config,
    runner: Runner,
    *,
    job_name: str,
    selector: str,
) -> bool:
    pod_inventory = runner.run(
        _kubectl(
            config,
            "get",
            "pods",
            "-n",
            config.namespace,
            f"--selector={selector}",
            "--output=json",
        )
    )
    try:
        pod_document = json.loads(pod_inventory)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{job_name} Pod inventory is invalid JSON") from exc
    if (
        not isinstance(pod_document, dict)
        or pod_document.get("apiVersion") != "v1"
        or pod_document.get("kind") != "List"
        or not isinstance(pod_document.get("items"), list)
    ):
        raise RuntimeError(f"{job_name} Pod inventory is invalid")
    return pod_document["items"] == []


def _require_absent_job(
    config: Config,
    runner: Runner,
    *,
    job_name: str,
) -> None:
    job_inventory = runner.run(
        _kubectl(
            config,
            "get",
            "job",
            job_name,
            "-n",
            config.namespace,
            "--ignore-not-found",
            "--output=json",
        )
    )
    if job_inventory.strip():
        raise RuntimeError(f"{job_name} Job still exists after deletion")


def _get_transaction_job_inventory(
    config: Config,
    runner: Runner,
    *,
    job_name: str,
) -> object | None:
    job_inventory = runner.run(
        _kubectl(
            config,
            "get",
            "job",
            job_name,
            "-n",
            config.namespace,
            "--ignore-not-found",
            "--output=json",
        )
    )
    if not job_inventory.strip():
        return None
    return json.loads(job_inventory)


def _validate_terminating_job_cleanup_identity(
    config: Config,
    transaction_job: dict,
    actual_job: object,
    *,
    transaction_token: str,
    job_uid: str,
) -> None:
    _validate_job_cleanup_identity(
        config,
        transaction_job,
        actual_job,
        transaction_token=transaction_token,
        expected_uid=job_uid,
    )
    metadata = actual_job.get("metadata") if isinstance(actual_job, dict) else None
    deletion_timestamp = (
        metadata.get("deletionTimestamp") if isinstance(metadata, dict) else None
    )
    if (
        not isinstance(deletion_timestamp, str)
        or not deletion_timestamp
        or deletion_timestamp != deletion_timestamp.strip()
    ):
        raise RuntimeError("Identity data Job foreground deletion state is invalid")


def _observe_bound_job_cleanup_closure(
    config: Config,
    runner: Runner,
    *,
    transaction_job: dict,
    transaction_token: str,
    job_name: str,
    job_uid: str,
) -> bool:
    actual_job = _get_transaction_job_inventory(
        config,
        runner,
        job_name=job_name,
    )
    if actual_job is not None:
        _validate_terminating_job_cleanup_identity(
            config,
            transaction_job,
            actual_job,
            transaction_token=transaction_token,
            job_uid=job_uid,
        )
    controller_pods_empty = _job_pod_inventory_is_empty(
        config,
        runner,
        job_name=job_name,
        selector=f"batch.kubernetes.io/controller-uid={job_uid}",
    )
    name_pods_empty = _job_pod_inventory_is_empty(
        config,
        runner,
        job_name=job_name,
        selector=f"batch.kubernetes.io/job-name={job_name}",
    )
    final_job = _get_transaction_job_inventory(
        config,
        runner,
        job_name=job_name,
    )
    if final_job is not None:
        _validate_terminating_job_cleanup_identity(
            config,
            transaction_job,
            final_job,
            transaction_token=transaction_token,
            job_uid=job_uid,
        )
    return (
        actual_job is None
        and controller_pods_empty
        and name_pods_empty
        and final_job is None
    )


def _wait_for_bound_job_cleanup_closure(
    config: Config,
    runner: Runner,
    *,
    transaction_job: dict,
    transaction_token: str,
    job_name: str,
    job_uid: str,
    cleanup_sleeper: Sleeper,
) -> None:
    last_transient_error: Exception | None = None
    observation_count = (
        IDENTITY_JOB_CLEANUP_ABSENCE_TIMEOUT_SECONDS
        // IDENTITY_JOB_CLEANUP_POLL_INTERVAL_SECONDS
        + 1
    )
    for observation in range(observation_count):
        try:
            closed = _observe_bound_job_cleanup_closure(
                config,
                runner,
                transaction_job=transaction_job,
                transaction_token=transaction_token,
                job_name=job_name,
                job_uid=job_uid,
            )
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            last_transient_error = exc
        else:
            if closed:
                return
        if observation + 1 < observation_count:
            cleanup_sleeper(IDENTITY_JOB_CLEANUP_POLL_INTERVAL_SECONDS)
    raise RuntimeError(
        f"{job_name} foreground deletion closure did not complete within "
        f"{IDENTITY_JOB_CLEANUP_ABSENCE_TIMEOUT_SECONDS} seconds"
    ) from last_transient_error


def _require_job_pod_absence_after_job_absence(
    config: Config,
    runner: Runner,
    *,
    job_name: str,
) -> None:
    _require_empty_job_pod_inventory(
        config,
        runner,
        job_name=job_name,
        selector=f"batch.kubernetes.io/job-name={job_name}",
    )
    _require_absent_job(config, runner, job_name=job_name)


def _delete_bound_job_and_wait_for_pods(
    config: Config,
    runner: Runner,
    *,
    delete_client: Any,
    transaction_job: dict,
    transaction_token: str,
    job_uid: str,
    cleanup_sleeper: Sleeper,
) -> None:
    metadata = transaction_job.get("metadata")
    job_name = metadata.get("name") if isinstance(metadata, dict) else None
    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError("expected Identity data Job cleanup identity is invalid")
    last_transient_error: Exception | None = None
    for _attempt in range(IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS):
        try:
            actual_job = _get_transaction_job_inventory(
                config,
                runner,
                job_name=job_name,
            )
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            last_transient_error = exc
            continue
        if actual_job is None:
            _wait_for_bound_job_cleanup_closure(
                config,
                runner,
                transaction_job=transaction_job,
                transaction_token=transaction_token,
                job_name=job_name,
                job_uid=job_uid,
                cleanup_sleeper=cleanup_sleeper,
            )
            return
        _validate_job_cleanup_identity(
            config,
            transaction_job,
            actual_job,
            transaction_token=transaction_token,
            expected_uid=job_uid,
        )
        actual_metadata = (
            actual_job.get("metadata") if isinstance(actual_job, dict) else None
        )
        if isinstance(actual_metadata, dict) and "deletionTimestamp" in actual_metadata:
            _validate_terminating_job_cleanup_identity(
                config,
                transaction_job,
                actual_job,
                transaction_token=transaction_token,
                job_uid=job_uid,
            )
            _wait_for_bound_job_cleanup_closure(
                config,
                runner,
                transaction_job=transaction_job,
                transaction_token=transaction_token,
                job_name=job_name,
                job_uid=job_uid,
                cleanup_sleeper=cleanup_sleeper,
            )
            return
        resource_version = _job_resource_version(actual_job)
        try:
            delete_client.delete(
                api_version="batch/v1",
                resource="jobs",
                namespace=config.namespace,
                name=job_name,
                uid=job_uid,
                resource_version=resource_version,
            )
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            last_transient_error = exc
            continue
        _wait_for_bound_job_cleanup_closure(
            config,
            runner,
            transaction_job=transaction_job,
            transaction_token=transaction_token,
            job_name=job_name,
            job_uid=job_uid,
            cleanup_sleeper=cleanup_sleeper,
        )
        return

    try:
        actual_job = _get_transaction_job_inventory(
            config,
            runner,
            job_name=job_name,
        )
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        last_transient_error = exc
    else:
        if actual_job is None:
            _wait_for_bound_job_cleanup_closure(
                config,
                runner,
                transaction_job=transaction_job,
                transaction_token=transaction_token,
                job_name=job_name,
                job_uid=job_uid,
                cleanup_sleeper=cleanup_sleeper,
            )
            return
        _validate_job_cleanup_identity(
            config,
            transaction_job,
            actual_job,
            transaction_token=transaction_token,
            expected_uid=job_uid,
        )
        actual_metadata = (
            actual_job.get("metadata") if isinstance(actual_job, dict) else None
        )
        if isinstance(actual_metadata, dict) and "deletionTimestamp" in actual_metadata:
            _validate_terminating_job_cleanup_identity(
                config,
                transaction_job,
                actual_job,
                transaction_token=transaction_token,
                job_uid=job_uid,
            )
            _wait_for_bound_job_cleanup_closure(
                config,
                runner,
                transaction_job=transaction_job,
                transaction_token=transaction_token,
                job_name=job_name,
                job_uid=job_uid,
                cleanup_sleeper=cleanup_sleeper,
            )
            return
    raise RuntimeError(
        f"{job_name} transaction deletion remained unresolved after "
        f"{IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS} attempts"
    ) from last_transient_error


def _delete_job_and_wait_for_pods(
    config: Config,
    runner: Runner,
    expected_job: dict,
    *,
    delete_client: Any,
    cleanup_sleeper: Sleeper,
) -> None:
    metadata = expected_job.get("metadata")
    job_name = metadata.get("name") if isinstance(metadata, dict) else None
    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError("expected Identity data Job identity is invalid")
    get_command = _kubectl(
        config,
        "get",
        "job",
        job_name,
        "-n",
        config.namespace,
        "--ignore-not-found",
        "--output=json",
    )
    job_output = runner.run(get_command)
    if job_output.strip():
        try:
            actual_job = json.loads(job_output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{job_name} Job inventory is invalid JSON") from exc
        transaction_token, job_uid = _validate_prior_transaction_job(
            config,
            expected_job,
            actual_job,
        )
        _delete_bound_job_and_wait_for_pods(
            config,
            runner,
            delete_client=delete_client,
            transaction_job=_job_with_transaction(
                expected_job,
                transaction_token,
            ),
            transaction_token=transaction_token,
            job_uid=job_uid,
            cleanup_sleeper=cleanup_sleeper,
        )
        return
    _require_job_pod_absence_after_job_absence(
        config,
        runner,
        job_name=job_name,
    )


def _delete_transaction_job_and_wait_for_pods(
    config: Config,
    runner: Runner,
    *,
    delete_client: Any,
    expected_job: dict,
    transaction_token: str,
    job_uid: str,
    cleanup_sleeper: Sleeper,
) -> None:
    metadata = expected_job.get("metadata")
    job_name = metadata.get("name") if isinstance(metadata, dict) else None
    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError("expected Identity data Job cleanup identity is invalid")
    _delete_bound_job_and_wait_for_pods(
        config,
        runner,
        delete_client=delete_client,
        transaction_job=expected_job,
        transaction_token=transaction_token,
        job_uid=job_uid,
        cleanup_sleeper=cleanup_sleeper,
    )


def _render_job(
    config: Config,
    runner: Runner,
    *,
    operation: str,
    values: str,
    chart: Path,
) -> dict:
    job_name = f"aileron-identity-{operation}"
    manifest = runner.run(
        _helm(
            config,
            "template",
            config.release,
            str(chart),
            "--namespace",
            config.namespace,
            "--values",
            "-",
            "--set",
            f"backup.enabled={'true' if operation == 'backup' else 'false'}",
            "--set",
            f"restore.enabled={'true' if operation == 'restore' else 'false'}",
            "--show-only",
            f"templates/{operation}-job.yaml",
        ),
        stdin=values,
    )
    expected_raw = runner.run(
        _kubectl(
            config,
            "create",
            "--dry-run=client",
            "--validate=false",
            "-n",
            config.namespace,
            "--filename=-",
            "--output=json",
        ),
        operation=f"normalize-{operation}",
        stdin=manifest,
    )
    try:
        expected_job = json.loads(expected_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"rendered {operation} Job is invalid JSON") from exc
    metadata = expected_job.get("metadata") if isinstance(expected_job, dict) else None
    if (
        not isinstance(expected_job, dict)
        or expected_job.get("apiVersion") != "batch/v1"
        or expected_job.get("kind") != "Job"
        or not isinstance(metadata, dict)
        or metadata.get("name") != job_name
        or metadata.get("namespace", config.namespace) != config.namespace
        or not isinstance(metadata.get("labels"), dict)
        or not isinstance(metadata.get("annotations"), dict)
        or metadata.get("ownerReferences", []) != []
        or "deletionTimestamp" in metadata
        or not isinstance(expected_job.get("spec"), dict)
    ):
        raise RuntimeError(f"rendered {operation} Job has an unexpected identity")
    return expected_job


def _timestamp(value: object, description: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError(f"{description} timestamp is invalid")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RuntimeError(f"{description} timestamp is invalid") from exc


def _utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def _validate_completed_job_status(job: dict, *, job_name: str) -> None:
    status = job.get("status") if isinstance(job, dict) else None
    allowed_status_keys = {
        "active",
        "completionTime",
        "conditions",
        "failed",
        "ready",
        "startTime",
        "succeeded",
        "terminating",
        "uncountedTerminatedPods",
    }
    if (
        not isinstance(status, dict)
        or not set(status).issubset(allowed_status_keys)
        or status.get("succeeded") != 1
        or status.get("active", 0) != 0
        or status.get("failed", 0) != 0
        or status.get("ready", 0) != 0
        or status.get("terminating", 0) != 0
        or status.get("uncountedTerminatedPods", {}) != {}
    ):
        raise RuntimeError(f"{job_name} Job completion status is invalid")
    started = _timestamp(status.get("startTime"), f"{job_name} Job start")
    completed = _timestamp(status.get("completionTime"), f"{job_name} Job completion")
    conditions = status.get("conditions")
    if started >= completed or not isinstance(conditions, list):
        raise RuntimeError(f"{job_name} Job completion status is invalid")
    condition_types: set[str] = set()
    for condition in conditions:
        if (
            not isinstance(condition, dict)
            or not {"type", "status", "lastTransitionTime"}.issubset(condition)
            or not set(condition).issubset(
                {
                    "type",
                    "status",
                    "lastProbeTime",
                    "lastTransitionTime",
                    "reason",
                    "message",
                }
            )
            or condition.get("type") not in {"Complete", "SuccessCriteriaMet"}
            or condition["type"] in condition_types
            or condition.get("status") != "True"
            or _timestamp(
                condition.get("lastTransitionTime"),
                f"{job_name} Job condition",
            )
            > completed
            or (
                "lastProbeTime" in condition
                and condition["lastProbeTime"] is not None
                and _timestamp(condition["lastProbeTime"], f"{job_name} Job probe")
                > completed
            )
            or any(
                key in condition
                and (not isinstance(condition[key], str) or not condition[key])
                for key in ("reason", "message")
            )
        ):
            raise RuntimeError(f"{job_name} Job completion status is invalid")
        condition_types.add(condition["type"])
    if "Complete" not in condition_types:
        raise RuntimeError(f"{job_name} Job completion status is invalid")


def _signed_image_pair(
    immutable_image: str,
    runtime_immutable_image: str,
    *,
    component: str,
) -> tuple[str, str]:
    pattern = r"[^\s@]+@sha256:[0-9a-f]{64}"
    if (
        re.fullmatch(pattern, immutable_image) is None
        or re.fullmatch(pattern, runtime_immutable_image) is None
        or immutable_image.rsplit("@", 1)[0]
        != runtime_immutable_image.rsplit("@", 1)[0]
        or immutable_image == runtime_immutable_image
    ):
        raise RuntimeError(f"signed {component} image pair is invalid")
    return immutable_image, runtime_immutable_image


def _runtime_image_id_matches(
    image_id: object, immutable_image: str, runtime_immutable_image: str
) -> bool:
    if not isinstance(image_id, str):
        return False
    match = re.fullmatch(
        r"(?:[a-z][a-z0-9+.-]*://)?(?P<repository>[^\s@]+)@"
        r"(?P<digest>sha256:[0-9a-f]{64})",
        image_id,
    )
    return (
        match is not None
        and match.group("repository") == immutable_image.rsplit("@", 1)[0]
        and match.group("digest")
        in {
            immutable_image.rsplit("@", 1)[1],
            runtime_immutable_image.rsplit("@", 1)[1],
        }
    )


def _container_status_image_matches_requested(
    value: object, requested_image: str
) -> bool:
    """Accept digest-only Kubernetes status images with exact Pod provenance."""
    return value == requested_image or (
        isinstance(value, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
    )


def _canonical_completed_pod_spec(expected: object, actual: object) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    normalized = copy.deepcopy(actual)
    node_name = normalized.pop("nodeName", None)
    if (
        not isinstance(node_name, str)
        or re.fullmatch(r"[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?", node_name) is None
    ):
        return False
    defaults = {
        "enableServiceLinks": True,
        "preemptionPolicy": "PreemptLowerPriority",
        "priority": 0,
        "serviceAccount": "default",
        "serviceAccountName": "default",
        "tolerations": [
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
        ],
    }
    for key, value in defaults.items():
        if key not in normalized or normalized.pop(key) != value:
            return False
    return normalized == expected


def _validate_completed_job_pod(
    *,
    config: Config,
    operation: str,
    job: dict,
    pods: object,
    immutable_image: str,
    runtime_immutable_image: str,
) -> None:
    job_metadata = job.get("metadata") if isinstance(job, dict) else None
    job_spec = job.get("spec") if isinstance(job, dict) else None
    job_status = job.get("status") if isinstance(job, dict) else None
    template = job_spec.get("template") if isinstance(job_spec, dict) else None
    template_metadata = template.get("metadata") if isinstance(template, dict) else None
    template_spec = template.get("spec") if isinstance(template, dict) else None
    items = pods.get("items") if isinstance(pods, dict) else None
    if (
        not isinstance(pods, dict)
        or pods.get("apiVersion") != "v1"
        or pods.get("kind") != "List"
        or not isinstance(items, list)
        or len(items) != 1
        or not isinstance(job_metadata, dict)
        or not isinstance(template_metadata, dict)
        or not isinstance(template_spec, dict)
        or not isinstance(job_status, dict)
    ):
        raise RuntimeError("Identity data Job execution Pod inventory is invalid")
    pod = items[0]
    metadata = pod.get("metadata") if isinstance(pod, dict) else None
    status = pod.get("status") if isinstance(pod, dict) else None
    job_name = job_metadata.get("name")
    job_uid = job_metadata.get("uid")
    owner = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "name": job_name,
        "uid": job_uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }
    if (
        not isinstance(pod, dict)
        or pod.get("apiVersion") != "v1"
        or pod.get("kind") != "Pod"
        or not isinstance(metadata, dict)
        or not isinstance(job_name, str)
        or not isinstance(job_uid, str)
        or not isinstance(metadata.get("name"), str)
        or not metadata["name"].startswith(f"{job_name}-")
        or metadata["name"] == f"{job_name}-"
        or metadata.get("generateName") != f"{job_name}-"
        or not isinstance(metadata.get("uid"), str)
        or not metadata["uid"]
        or metadata.get("namespace") != config.namespace
        or metadata.get("labels") != template_metadata.get("labels")
        or metadata.get("annotations", {}) != template_metadata.get("annotations", {})
        or metadata.get("ownerReferences") != [owner]
        or "deletionTimestamp" in metadata
        or not _canonical_completed_pod_spec(template_spec, pod.get("spec"))
        or not isinstance(status, dict)
        or status.get("phase") != "Succeeded"
        or status.get("initContainerStatuses", []) != []
    ):
        raise RuntimeError("Identity data Job execution Pod identity is invalid")
    statuses = status.get("containerStatuses")
    container_status = (
        statuses[0] if isinstance(statuses, list) and len(statuses) == 1 else None
    )
    state = (
        container_status.get("state") if isinstance(container_status, dict) else None
    )
    terminated = state.get("terminated") if isinstance(state, dict) else None
    container_id = (
        container_status.get("containerID")
        if isinstance(container_status, dict)
        else None
    )
    started = (
        _timestamp(terminated.get("startedAt"), "Identity data Job Pod start")
        if isinstance(terminated, dict)
        else None
    )
    finished = (
        _timestamp(terminated.get("finishedAt"), "Identity data Job Pod finish")
        if isinstance(terminated, dict)
        else None
    )
    job_started = _timestamp(job_status.get("startTime"), "Identity data Job start")
    job_completed = _timestamp(
        job_status.get("completionTime"), "Identity data Job completion"
    )
    if (
        not isinstance(container_status, dict)
        or container_status.get("name") != operation
        or not _container_status_image_matches_requested(
            container_status.get("image"),
            immutable_image,
        )
        or not _runtime_image_id_matches(
            container_status.get("imageID"),
            immutable_image,
            runtime_immutable_image,
        )
        or container_status.get("restartCount") != 0
        or container_status.get("ready", False) is not False
        or container_status.get("started", False) is not False
        or not isinstance(container_id, str)
        or re.fullmatch(r"containerd://[0-9a-f]{64}", container_id) is None
        or not isinstance(state, dict)
        or set(state) != {"terminated"}
        or not isinstance(terminated, dict)
        or terminated.get("containerID") != container_id
        or terminated.get("exitCode") != 0
        or terminated.get("reason") != "Completed"
        or started is None
        or finished is None
        or not (job_started <= started <= finished <= job_completed)
    ):
        raise RuntimeError("Identity data Job execution Pod provenance is invalid")


def _create_or_reconcile_transaction_job(
    config: Config,
    runner: Runner,
    *,
    operation: str,
    transaction_job: dict,
    transaction_manifest: str,
    transaction_token: str,
) -> tuple[dict, str]:
    job_name = f"aileron-identity-{operation}"
    create_error: Exception | None = None
    try:
        created_raw = runner.run(
            _kubectl(
                config,
                "create",
                "-n",
                config.namespace,
                "-f",
                "-",
                "--output=json",
            ),
            operation=operation,
            stdin=transaction_manifest,
        )
        created_job = json.loads(created_raw)
        created_uid = _validate_job_cleanup_identity(
            config,
            transaction_job,
            created_job,
            transaction_token=transaction_token,
        )
        return created_job, created_uid
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        create_error = exc

    try:
        reconciled_raw = runner.run(
            _kubectl(
                config,
                "get",
                "job",
                job_name,
                "-n",
                config.namespace,
                "--output=json",
            )
        )
        reconciled_job = json.loads(reconciled_raw)
        reconciled_uid = _validate_job_cleanup_identity(
            config,
            transaction_job,
            reconciled_job,
            transaction_token=transaction_token,
        )
        return reconciled_job, reconciled_uid
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as reconciliation_error:
        raise RuntimeError(
            f"{job_name} create and exact transaction reconciliation failed: "
            f"create={create_error}; reconciliation={reconciliation_error}"
        ) from reconciliation_error


def _recover_transaction_job_uid(
    config: Config,
    runner: Runner,
    *,
    transaction_job: dict,
    transaction_token: str,
    expected_uid: str | None = None,
) -> str | None:
    metadata = transaction_job.get("metadata")
    job_name = metadata.get("name") if isinstance(metadata, dict) else None
    if not isinstance(job_name, str) or not job_name:
        raise RuntimeError("expected Identity data Job recovery identity is invalid")
    last_transient_error: Exception | None = None
    for _attempt in range(IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS):
        try:
            recovered_job = _get_transaction_job_inventory(
                config,
                runner,
                job_name=job_name,
            )
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            last_transient_error = exc
            continue
        if recovered_job is None:
            last_transient_error = None
            continue
        return _validate_job_cleanup_identity(
            config,
            transaction_job,
            recovered_job,
            transaction_token=transaction_token,
            expected_uid=expected_uid,
        )
    if last_transient_error is not None:
        raise RuntimeError(
            f"{job_name} transaction cleanup identity remained unavailable after "
            f"{IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS} attempts"
        ) from last_transient_error
    return None


def _read_completed_job_execution(
    config: Config,
    runner: Runner,
    *,
    readback_sleeper: Sleeper,
    operation: str,
    transaction_job: dict,
    created_uid: str,
    immutable_image: str,
    runtime_immutable_image: str,
) -> str:
    job_name = f"aileron-identity-{operation}"
    last_error: Exception | None = None
    for attempt in range(IDENTITY_JOB_READBACK_ATTEMPTS):
        try:
            completed_raw = runner.run(
                _kubectl(
                    config,
                    "get",
                    "job",
                    job_name,
                    "-n",
                    config.namespace,
                    "--output=json",
                )
            )
            try:
                completed_job = json.loads(completed_raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"completed {job_name} Job identity is invalid JSON"
                ) from exc
            completed_uid = _validate_existing_job(
                config,
                transaction_job,
                completed_job,
            )
            if completed_uid != created_uid:
                raise RuntimeError(f"{job_name} Job changed identity during execution")
            _validate_completed_job_status(completed_job, job_name=job_name)
            pods_raw = runner.run(
                _kubectl(
                    config,
                    "get",
                    "pods",
                    "-n",
                    config.namespace,
                    f"--selector=batch.kubernetes.io/controller-uid={created_uid}",
                    "--sort-by=.metadata.name",
                    "--output=json",
                )
            )
            try:
                pods = json.loads(pods_raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"{job_name} execution Pod inventory is invalid JSON"
                ) from exc
            _validate_completed_job_pod(
                config=config,
                operation=operation,
                job=completed_job,
                pods=pods,
                immutable_image=immutable_image,
                runtime_immutable_image=runtime_immutable_image,
            )
            return completed_uid
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            if attempt + 1 < IDENTITY_JOB_READBACK_ATTEMPTS:
                readback_sleeper(IDENTITY_JOB_READBACK_INTERVAL_SECONDS)
    if last_error is None:
        raise RuntimeError(f"{job_name} completed execution readback is unavailable")
    raise last_error


def _run_job(
    config: Config,
    runner: Runner,
    *,
    delete_client: Any,
    cleanup_sleeper: Sleeper,
    operation: str,
    expected_job: dict,
    immutable_image: str,
    runtime_immutable_image: str,
    output: list[str] | None = None,
) -> str:
    job_name = f"aileron-identity-{operation}"
    _delete_job_and_wait_for_pods(
        config,
        runner,
        expected_job,
        delete_client=delete_client,
        cleanup_sleeper=cleanup_sleeper,
    )
    transaction_token = secrets.token_hex(32)
    transaction_job = _job_with_transaction(expected_job, transaction_token)
    transaction_manifest = (
        json.dumps(transaction_job, separators=(",", ":"), sort_keys=True) + "\n"
    )
    created_uid: str | None = None
    completed_uid: str | None = None
    try:
        created_job, created_uid = _create_or_reconcile_transaction_job(
            config,
            runner,
            operation=operation,
            transaction_job=transaction_job,
            transaction_manifest=transaction_manifest,
            transaction_token=transaction_token,
        )
        _validate_existing_job(config, transaction_job, created_job)
        runner.run(
            _kubectl(
                config,
                "wait",
                "-n",
                config.namespace,
                "--for=condition=complete",
                f"job/{job_name}",
                f"--timeout={config.timeout}",
            )
        )
        completed_uid = _read_completed_job_execution(
            config,
            runner,
            readback_sleeper=cleanup_sleeper,
            operation=operation,
            transaction_job=transaction_job,
            created_uid=created_uid,
            immutable_image=immutable_image,
            runtime_immutable_image=runtime_immutable_image,
        )
        if output is not None:
            output.append(
                runner.run(
                    _kubectl(
                        config,
                        "logs",
                        f"job/{job_name}",
                        "-n",
                        config.namespace,
                    )
                )
            )
    finally:
        primary_failure = sys.exc_info()[1]
        try:
            cleanup_uid = created_uid
            if cleanup_uid is None:
                cleanup_uid = _recover_transaction_job_uid(
                    config,
                    runner,
                    transaction_job=transaction_job,
                    transaction_token=transaction_token,
                )
            if cleanup_uid is not None:
                _delete_transaction_job_and_wait_for_pods(
                    config,
                    runner,
                    delete_client=delete_client,
                    expected_job=transaction_job,
                    transaction_token=transaction_token,
                    job_uid=cleanup_uid,
                    cleanup_sleeper=cleanup_sleeper,
                )
            else:
                metadata = transaction_job.get("metadata")
                job_name = metadata.get("name") if isinstance(metadata, dict) else None
                if not isinstance(job_name, str) or not job_name:
                    raise RuntimeError(
                        "expected Identity data Job cleanup identity is invalid"
                    )
                _require_empty_job_pod_inventory(
                    config,
                    runner,
                    job_name=job_name,
                    selector=f"batch.kubernetes.io/job-name={job_name}",
                )
                _require_absent_job(config, runner, job_name=job_name)
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
        ) as cleanup_error:
            failures = []
            if isinstance(primary_failure, Exception):
                failures.extend(_expanded_failures(primary_failure))
            failures.extend(_expanded_failures(cleanup_error))
            raise IdentitySmokeCleanupError(failures) from cleanup_error
    if completed_uid is None:
        raise RuntimeError(f"{job_name} completed Job UID is unavailable")
    return completed_uid


def _expected_confirmation(config: Config) -> str:
    return (
        f"{config.context}/{config.namespace}/{config.release}"
        f"@revision={config.release_revision},chart={config.chart_version},"
        f"commit={config.expected_commit},chartDigest={config.chart_digest}"
        f",keycloakImage={config.keycloak_image}"
        f",keycloakRuntimeImage={config.keycloak_runtime_image}"
        f",postgresImage={config.postgres_image}"
        f",postgresRuntimeImage={config.postgres_runtime_image}"
    )


def _parse_commit_chart_tree(tree_inventory: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for line in tree_inventory.splitlines():
        match = re.fullmatch(
            r"(100644|100755) blob ([0-9a-f]{40,64})\t" r"(helm/aileron-identity/.+)",
            line,
        )
        if match is None:
            raise RuntimeError("committed Identity Chart tree inventory is invalid")
        entries.append((match.group(1), match.group(2), match.group(3)))
    if not entries or len({entry[2] for entry in entries}) != len(entries):
        raise RuntimeError("committed Identity Chart tree inventory is invalid")
    return entries


def _validate_canonical_chart(config: Config, runner: Runner) -> Path:
    repository_output = runner.run(["git", "rev-parse", "--show-toplevel"]).strip()
    repository_root = Path(repository_output)
    if (
        not repository_output
        or not repository_root.is_absolute()
        or repository_root.is_symlink()
        or repository_root.resolve() != repository_root
    ):
        raise RuntimeError("Git repository root is not canonical")
    chart = repository_root / "helm/aileron-identity"
    if chart.is_symlink() or not chart.is_dir() or chart.resolve() != chart:
        raise RuntimeError(
            "canonical Identity Chart is missing or uses a symbolic link"
        )
    if any(path.is_symlink() for path in chart.rglob("*")):
        raise RuntimeError("canonical Identity Chart contains a symbolic link")

    tree_line = runner.run(
        [
            "git",
            "ls-tree",
            "-d",
            config.expected_commit,
            "--",
            "helm/aileron-identity",
        ]
    ).strip()
    tree_match = re.fullmatch(
        r"040000 tree ([0-9a-f]{40,64})\thelm/aileron-identity", tree_line
    )
    if tree_match is None:
        raise RuntimeError("full commit does not contain the canonical Identity Chart")
    committed_tree_hash = tree_match.group(1)
    resolved_tree_hash = runner.run(
        [
            "git",
            "rev-parse",
            f"{config.expected_commit}:helm/aileron-identity",
        ]
    ).strip()
    if resolved_tree_hash != committed_tree_hash:
        raise RuntimeError("Identity Chart Git tree hash is inconsistent")

    tree_inventory = runner.run(
        [
            "git",
            "ls-tree",
            "-r",
            config.expected_commit,
            "--",
            "helm/aileron-identity",
        ]
    )
    committed_entries = _parse_commit_chart_tree(tree_inventory)
    calculated_digest = "sha256:" + hashlib.sha256(tree_inventory.encode()).hexdigest()
    if (
        re.fullmatch(r"sha256:[0-9a-f]{64}", config.chart_digest) is None
        or config.chart_digest != calculated_digest
    ):
        raise RuntimeError("Identity Chart digest does not match the full commit tree")

    staged_inventory = runner.run(
        ["git", "ls-files", "--stage", "--", "helm/aileron-identity"]
    )
    staged_entries: list[tuple[str, str, str]] = []
    for line in staged_inventory.splitlines():
        match = re.fullmatch(
            r"(100644|100755) ([0-9a-f]{40,64}) 0\t" r"(helm/aileron-identity/.+)",
            line,
        )
        if match is None:
            raise RuntimeError("Identity Chart tracked content inventory is invalid")
        staged_entries.append((match.group(1), match.group(2), match.group(3)))
    if staged_entries != committed_entries:
        raise RuntimeError(
            "Identity Chart tracked content differs from the full commit"
        )
    untracked = runner.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "helm/aileron-identity",
        ]
    )
    if untracked:
        raise RuntimeError("canonical Identity Chart contains untracked content")
    actual_files = {
        path.relative_to(repository_root).as_posix()
        for path in chart.rglob("*")
        if path.is_file()
    }
    if actual_files != {entry[2] for entry in committed_entries}:
        raise RuntimeError("canonical Identity Chart file inventory is inconsistent")
    return chart


def _validate_local_release_identity(config: Config, runner: Runner) -> Path:
    if not config.context or config.context != config.context.strip():
        raise ValueError("--context must be a non-empty exact context")
    if not config.kubeconfig.is_absolute():
        raise ValueError("--kubeconfig must be an absolute path")
    if re.fullmatch(r"[0-9a-f]{40}", config.expected_commit) is None:
        raise ValueError("--commit must be a full lowercase Git SHA")
    if config.release_revision < 1:
        raise ValueError("--release-revision must be a positive integer")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", config.chart_version) is None:
        raise ValueError("--chart-version must use semantic version syntax")
    _signed_image_pair(
        config.keycloak_image,
        config.keycloak_runtime_image,
        component="Keycloak",
    )
    _signed_image_pair(
        config.postgres_image,
        config.postgres_runtime_image,
        component="PostgreSQL",
    )
    actual_commit = runner.run(["git", "rev-parse", "--verify", "HEAD"]).strip()
    if actual_commit != config.expected_commit:
        raise RuntimeError("checkout HEAD does not match --commit")
    if runner.run(["git", "status", "--porcelain", "--untracked-files=normal"]):
        raise RuntimeError("backup/restore smoke requires a clean checkout")
    chart = _validate_canonical_chart(config, runner)
    try:
        chart_document = (chart / "Chart.yaml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError("Identity Chart metadata is unreadable") from exc
    versions = re.findall(r"^version:\s*([^\s]+)\s*$", chart_document, re.MULTILINE)
    if versions != [config.chart_version]:
        raise RuntimeError("Identity Chart version does not match --chart-version")
    return chart


def _validate_release_metadata(config: Config, runner: Runner) -> None:
    output = runner.run(
        _helm(
            config,
            "list",
            "--namespace",
            config.namespace,
            "--filter",
            f"^{config.release}$",
            "--output",
            "json",
        )
    )
    try:
        releases = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed Identity release metadata is invalid") from exc
    expected_chart = f"aileron-identity-{config.chart_version}"
    if (
        not isinstance(releases, list)
        or len(releases) != 1
        or not isinstance(releases[0], dict)
        or releases[0].get("name") != config.release
        or releases[0].get("namespace") != config.namespace
        or releases[0].get("status") != "deployed"
        or releases[0].get("chart") != expected_chart
        or str(releases[0].get("revision")) != str(config.release_revision)
    ):
        raise RuntimeError(
            "installed Identity release metadata does not match confirmation"
        )
    metadata_output = runner.run(
        _helm(
            config,
            "get",
            "metadata",
            config.release,
            "--namespace",
            config.namespace,
            "--output",
            "json",
        )
    )
    try:
        metadata = json.loads(metadata_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed Identity release metadata is invalid") from exc
    if (
        not isinstance(metadata, dict)
        or metadata.get("name") != config.release
        or metadata.get("namespace") != config.namespace
        or metadata.get("status") != "deployed"
        or metadata.get("chart") != "aileron-identity"
        or str(metadata.get("version")) != config.chart_version
        or str(metadata.get("revision")) != str(config.release_revision)
    ):
        raise RuntimeError(
            "installed Identity release metadata does not match confirmation"
        )


def _normalized_manifest_digest(manifest: str) -> str:
    documents: list[str] = []
    current: list[str] = []
    for line in manifest.splitlines():
        if line.strip() == "---":
            if current:
                documents.append("\n".join(current).strip() + "\n")
                current = []
            continue
        if line.startswith("# Source:"):
            continue
        current.append(line.rstrip())
    if current and any(line for line in current):
        documents.append("\n".join(current).strip() + "\n")
    document_digests = sorted(
        hashlib.sha256(document.encode()).hexdigest()
        for document in documents
        if document.strip()
    )
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(document_digests, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _validate_installed_manifest(
    config: Config,
    runner: Runner,
    *,
    chart: Path,
    values: str,
) -> None:
    installed = runner.run(
        _helm(
            config,
            "get",
            "manifest",
            config.release,
            "--namespace",
            config.namespace,
        )
    )
    installed_hooks = runner.run(
        _helm(
            config,
            "get",
            "hooks",
            config.release,
            "--namespace",
            config.namespace,
        )
    )
    rendered = runner.run(
        _helm(
            config,
            "template",
            config.release,
            str(chart),
            "--namespace",
            config.namespace,
            "--values",
            "-",
            "--include-crds",
        ),
        stdin=values,
    )
    if _normalized_manifest_digest(
        f"{installed}\n---\n{installed_hooks}"
    ) != _normalized_manifest_digest(rendered):
        raise RuntimeError(
            "installed Identity rendered manifest differs from the canonical Chart"
        )


def _image_reference(values: dict[str, object], component: str) -> str:
    try:
        image = values["images"][component]  # type: ignore[index]
        repository = image["repository"]  # type: ignore[index]
        digest = image["digest"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"installed {component} image values are invalid") from exc
    if (
        not isinstance(repository, str)
        or not repository
        or not isinstance(digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
    ):
        raise RuntimeError(f"installed {component} image values are invalid")
    return f"{repository}@{digest}"


def _remove_required_server_default(
    expected: dict[str, object],
    actual: dict[str, object],
    key: str,
    value: object,
) -> bool:
    if not _remove_known_default(expected, key, value):
        return False
    if key not in actual or actual[key] != value:
        return False
    del actual[key]
    return True


def _canonical_template_container(expected: object, actual: object) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    canonical_expected = copy.deepcopy(expected)
    normalized = copy.deepcopy(actual)
    for key, value in {
        "terminationMessagePath": "/dev/termination-log",
        "terminationMessagePolicy": "File",
    }.items():
        if not _remove_required_server_default(
            canonical_expected, normalized, key, value
        ):
            return False

    expected_ports = canonical_expected.get("ports", [])
    actual_ports = normalized.get("ports", [])
    if (
        not isinstance(expected_ports, list)
        or not isinstance(actual_ports, list)
        or len(expected_ports) != len(actual_ports)
    ):
        return False
    for expected_port, actual_port in zip(expected_ports, actual_ports):
        if not isinstance(expected_port, dict) or not isinstance(actual_port, dict):
            return False
        if "protocol" not in expected_port:
            if actual_port.pop("protocol", None) != "TCP":
                return False
        elif expected_port.get("protocol") != "TCP":
            return False

    probe_defaults = {
        "failureThreshold": 3,
        "periodSeconds": 10,
        "successThreshold": 1,
        "timeoutSeconds": 1,
    }
    for probe_name in ("livenessProbe", "readinessProbe", "startupProbe"):
        expected_probe = canonical_expected.get(probe_name)
        actual_probe = normalized.get(probe_name)
        if expected_probe is None and actual_probe is None:
            continue
        if not isinstance(expected_probe, dict) or not isinstance(actual_probe, dict):
            return False
        for key, value in probe_defaults.items():
            if not _remove_required_server_default(
                expected_probe, actual_probe, key, value
            ):
                return False
    return normalized == canonical_expected


def _canonical_deployment_template(expected: object, actual: object) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    canonical_expected = copy.deepcopy(expected)
    normalized = copy.deepcopy(actual)
    expected_metadata = canonical_expected.get("metadata")
    actual_metadata = normalized.get("metadata")
    expected_spec = canonical_expected.get("spec")
    actual_spec = normalized.get("spec")
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(actual_metadata, dict)
        or not isinstance(expected_spec, dict)
        or not isinstance(actual_spec, dict)
        or not _remove_known_default(expected_metadata, "creationTimestamp", None)
        or actual_metadata.pop("creationTimestamp", None) is not None
    ):
        return False
    for key, value in {
        "dnsPolicy": "ClusterFirst",
        "restartPolicy": "Always",
        "schedulerName": "default-scheduler",
        "terminationGracePeriodSeconds": 30,
    }.items():
        if not _remove_required_server_default(expected_spec, actual_spec, key, value):
            return False
    for container_key in ("containers", "initContainers"):
        expected_containers = expected_spec.get(container_key, [])
        actual_containers = actual_spec.get(container_key, [])
        if (
            not isinstance(expected_containers, list)
            or not isinstance(actual_containers, list)
            or len(expected_containers) != len(actual_containers)
            or not all(
                _canonical_template_container(expected_container, actual_container)
                for expected_container, actual_container in zip(
                    expected_containers, actual_containers
                )
            )
        ):
            return False
        if container_key in expected_spec:
            actual_spec[container_key] = copy.deepcopy(expected_containers)
    return normalized == canonical_expected


def _canonical_deployment_spec(expected: object, actual: object) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    canonical_expected = copy.deepcopy(expected)
    normalized = copy.deepcopy(actual)
    for key, value in {
        "progressDeadlineSeconds": 600,
        "revisionHistoryLimit": 10,
    }.items():
        if not _remove_required_server_default(
            canonical_expected, normalized, key, value
        ):
            return False
    expected_template = canonical_expected.get("template")
    actual_template = normalized.get("template")
    if not _canonical_deployment_template(expected_template, actual_template):
        return False
    normalized["template"] = canonical_expected["template"]
    return normalized == canonical_expected


def _render_postgres_deployment(
    config: Config,
    runner: Runner,
    *,
    chart: Path,
    values: str,
) -> dict:
    manifest = runner.run(
        _helm(
            config,
            "template",
            config.release,
            str(chart),
            "--namespace",
            config.namespace,
            "--values",
            "-",
            "--show-only",
            "templates/postgres-deployment.yaml",
        ),
        stdin=values,
    )
    expected_raw = runner.run(
        _kubectl(
            config,
            "create",
            "--dry-run=client",
            "--validate=false",
            "-n",
            config.namespace,
            "--filename=-",
            "--output=json",
        ),
        operation="normalize-postgres-deployment",
        stdin=manifest,
    )
    try:
        expected = json.loads(expected_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "rendered Identity PostgreSQL Deployment is invalid JSON"
        ) from exc
    metadata = expected.get("metadata") if isinstance(expected, dict) else None
    if (
        not isinstance(expected, dict)
        or expected.get("apiVersion") != "apps/v1"
        or expected.get("kind") != "Deployment"
        or not isinstance(metadata, dict)
        or metadata.get("name") != "aileron-identity-postgres"
        or metadata.get("namespace", config.namespace) != config.namespace
        or not isinstance(metadata.get("labels"), dict)
        or metadata.get("ownerReferences", []) != []
        or "deletionTimestamp" in metadata
        or not isinstance(expected.get("spec"), dict)
    ):
        raise RuntimeError(
            "rendered Identity PostgreSQL Deployment identity is invalid"
        )
    return expected


def _validate_live_postgres_deployment(
    config: Config,
    expected: dict,
    actual: object,
) -> dict:
    expected_metadata = expected.get("metadata")
    actual_metadata = actual.get("metadata") if isinstance(actual, dict) else None
    actual_spec = actual.get("spec") if isinstance(actual, dict) else None
    status = actual.get("status") if isinstance(actual, dict) else None
    generation = (
        actual_metadata.get("generation") if isinstance(actual_metadata, dict) else None
    )
    deployment_uid = (
        actual_metadata.get("uid") if isinstance(actual_metadata, dict) else None
    )
    rendered_annotations = (
        expected_metadata.get("annotations", {})
        if isinstance(expected_metadata, dict)
        else None
    )
    actual_annotations = (
        actual_metadata.get("annotations")
        if isinstance(actual_metadata, dict)
        else None
    )
    deployment_revision = (
        actual_annotations.get("deployment.kubernetes.io/revision")
        if isinstance(actual_annotations, dict)
        else None
    )
    controller_annotations = {
        "deployment.kubernetes.io/revision": deployment_revision,
        "meta.helm.sh/release-name": config.release,
        "meta.helm.sh/release-namespace": config.namespace,
    }
    expected_annotations = (
        {**rendered_annotations, **controller_annotations}
        if isinstance(rendered_annotations, dict)
        and all(
            key not in rendered_annotations or rendered_annotations[key] == value
            for key, value in controller_annotations.items()
        )
        else None
    )
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(actual, dict)
        or actual.get("apiVersion") != "apps/v1"
        or actual.get("kind") != "Deployment"
        or not isinstance(actual_metadata, dict)
        or actual_metadata.get("name") != "aileron-identity-postgres"
        or actual_metadata.get("namespace") != config.namespace
        or not isinstance(deployment_uid, str)
        or not deployment_uid
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or actual_metadata.get("labels") != expected_metadata.get("labels")
        or not isinstance(deployment_revision, str)
        or re.fullmatch(r"[1-9][0-9]*", deployment_revision) is None
        or expected_annotations is None
        or actual_annotations != expected_annotations
        or actual_metadata.get("ownerReferences", []) != []
        or actual_metadata.get("finalizers", []) != []
        or "deletionTimestamp" in actual_metadata
        or not _canonical_deployment_spec(expected.get("spec"), actual_spec)
        or not isinstance(actual_spec, dict)
        or actual_spec.get("replicas") != 1
        or not isinstance(status, dict)
        or status.get("observedGeneration") != generation
        or status.get("replicas") != 1
        or status.get("updatedReplicas") != 1
        or status.get("readyReplicas") != 1
        or status.get("availableReplicas") != 1
        or status.get("unavailableReplicas", 0) != 0
        or status.get("collisionCount", 0) != 0
    ):
        raise RuntimeError("live Identity PostgreSQL Deployment identity is invalid")
    return actual


def _exact_owner_reference(
    metadata: object,
    *,
    api_version: str,
    kind: str,
    name: str,
    uid: str,
) -> bool:
    return isinstance(metadata, dict) and metadata.get("ownerReferences") == [
        {
            "apiVersion": api_version,
            "kind": kind,
            "name": name,
            "uid": uid,
            "controller": True,
            "blockOwnerDeletion": True,
        }
    ]


def _owner_uids(metadata: object) -> set[str]:
    references = metadata.get("ownerReferences") if isinstance(metadata, dict) else None
    if not isinstance(references, list):
        return set()
    return {
        reference["uid"]
        for reference in references
        if isinstance(reference, dict)
        and isinstance(reference.get("uid"), str)
        and reference["uid"]
    }


def _labels_match(labels: object, selector: dict[str, str]) -> bool:
    return isinstance(labels, dict) and all(
        labels.get(key) == value for key, value in selector.items()
    )


def _validate_active_postgres_replica_set(
    *,
    deployment: dict,
    replica_set: dict,
) -> None:
    deployment_metadata = deployment["metadata"]
    deployment_spec = deployment["spec"]
    metadata = replica_set.get("metadata")
    spec = replica_set.get("spec")
    status = replica_set.get("status")
    base_selector = deployment_spec["selector"].get("matchLabels")
    template = deployment_spec.get("template")
    template_metadata = template.get("metadata") if isinstance(template, dict) else None
    if (
        not isinstance(metadata, dict)
        or not isinstance(spec, dict)
        or not isinstance(status, dict)
        or not isinstance(base_selector, dict)
        or not isinstance(template_metadata, dict)
    ):
        # Malformed live state is a runtime contract failure, not caller misuse.
        raise RuntimeError(  # noqa: TRY004
            "active Identity PostgreSQL ReplicaSet is invalid"
        )
    name = metadata.get("name")
    uid = metadata.get("uid")
    generation = metadata.get("generation")
    hash_label = (
        metadata.get("labels", {}).get("pod-template-hash")
        if isinstance(metadata.get("labels"), dict)
        else None
    )
    expected_template = copy.deepcopy(template)
    expected_template["metadata"].setdefault("labels", {})[
        "pod-template-hash"
    ] = hash_label
    expected_selector = {
        "matchLabels": {**base_selector, "pod-template-hash": hash_label}
    }
    annotations = metadata.get("annotations")
    deployment_revision = deployment_metadata.get("annotations", {}).get(
        "deployment.kubernetes.io/revision"
    )
    expected_annotations = {
        **deployment_metadata.get("annotations", {}),
        "deployment.kubernetes.io/desired-replicas": "1",
        "deployment.kubernetes.io/max-replicas": "1",
        "deployment.kubernetes.io/revision": (
            annotations.get("deployment.kubernetes.io/revision")
            if isinstance(annotations, dict)
            else None
        ),
    }
    if (
        not isinstance(name, str)
        or not isinstance(hash_label, str)
        or not hash_label
        or name != f"{deployment_metadata['name']}-{hash_label}"
        or not isinstance(uid, str)
        or not uid
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or metadata.get("namespace") != deployment_metadata.get("namespace")
        or metadata.get("labels") != expected_template["metadata"]["labels"]
        or not isinstance(annotations, dict)
        or annotations != expected_annotations
        or annotations.get("deployment.kubernetes.io/revision") != deployment_revision
        or annotations.get("deployment.kubernetes.io/desired-replicas") != "1"
        or annotations.get("deployment.kubernetes.io/max-replicas") != "1"
        or re.fullmatch(
            r"[1-9][0-9]*",
            annotations.get("deployment.kubernetes.io/revision", ""),
        )
        is None
        or metadata.get("finalizers", []) != []
        or "deletionTimestamp" in metadata
        or not _exact_owner_reference(
            metadata,
            api_version="apps/v1",
            kind="Deployment",
            name=deployment_metadata["name"],
            uid=deployment_metadata["uid"],
        )
        or set(spec) != {"replicas", "selector", "template"}
        or spec.get("replicas") != 1
        or deployment_spec.get("minReadySeconds", 0) != 0
        or spec.get("selector") != expected_selector
        or spec.get("template") != expected_template
        or status.get("observedGeneration") != generation
        or status.get("replicas") != 1
        or status.get("fullyLabeledReplicas") != 1
        or status.get("readyReplicas") != 1
        or status.get("availableReplicas") != 1
    ):
        raise RuntimeError("active Identity PostgreSQL ReplicaSet is invalid")


def _bind_active_postgres_replica_set(
    *,
    config: Config,
    deployment: dict,
    inventory: object,
) -> tuple[dict, set[str]]:
    items = inventory.get("items") if isinstance(inventory, dict) else None
    deployment_metadata = deployment["metadata"]
    deployment_spec = deployment["spec"]
    selector = deployment_spec["selector"].get("matchLabels")
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or not isinstance(items, list)
        or not isinstance(selector, dict)
    ):
        raise RuntimeError("Identity PostgreSQL ReplicaSet inventory is invalid")
    candidates: list[dict] = []
    owned_uids: set[str] = set()
    for item in items:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        owned = deployment_metadata["uid"] in _owner_uids(metadata)
        selected = _labels_match(
            metadata.get("labels") if isinstance(metadata, dict) else None,
            selector,
        )
        if not owned and not selected:
            continue
        if (
            not isinstance(item, dict)
            or item.get("apiVersion") != "apps/v1"
            or item.get("kind") != "ReplicaSet"
            or not isinstance(metadata, dict)
            or metadata.get("namespace") != config.namespace
            or not isinstance(metadata.get("name"), str)
            or not isinstance(metadata.get("uid"), str)
            or not metadata["uid"]
            or "deletionTimestamp" in metadata
            or not _exact_owner_reference(
                metadata,
                api_version="apps/v1",
                kind="Deployment",
                name=deployment_metadata["name"],
                uid=deployment_metadata["uid"],
            )
        ):
            raise RuntimeError("Identity PostgreSQL ReplicaSet ownership is invalid")
        spec = item.get("spec")
        status = item.get("status")
        generation = metadata.get("generation")
        desired = spec.get("replicas") if isinstance(spec, dict) else None
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
            or isinstance(desired, bool)
            or desired not in {0, 1}
            or not isinstance(status, dict)
            or status.get("observedGeneration") != generation
            or status.get("replicas", 0) != desired
            or (
                desired == 0
                and any(
                    status.get(key, 0) != 0
                    for key in (
                        "fullyLabeledReplicas",
                        "readyReplicas",
                        "availableReplicas",
                    )
                )
            )
        ):
            raise RuntimeError("Identity PostgreSQL ReplicaSet state is invalid")
        owned_uids.add(metadata["uid"])
        if desired == 1:
            candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError("Identity PostgreSQL active ReplicaSet is ambiguous")
    _validate_active_postgres_replica_set(
        deployment=deployment,
        replica_set=candidates[0],
    )
    return candidates[0], owned_uids


def _canonical_running_pod_spec(expected: object, actual: object) -> bool:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return False
    normalized = copy.deepcopy(actual)
    node_name = normalized.pop("nodeName", None)
    if (
        not isinstance(node_name, str)
        or re.fullmatch(r"[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?", node_name) is None
    ):
        return False
    defaults = {
        "enableServiceLinks": True,
        "preemptionPolicy": "PreemptLowerPriority",
        "priority": 0,
        "serviceAccount": "default",
        "serviceAccountName": "default",
        "tolerations": [
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
        ],
    }
    for key, value in defaults.items():
        if key not in normalized or normalized.pop(key) != value:
            return False
    for container_key in ("containers", "initContainers"):
        expected_containers = expected.get(container_key, [])
        actual_containers = normalized.get(container_key, [])
        if (
            not isinstance(expected_containers, list)
            or not isinstance(actual_containers, list)
            or len(expected_containers) != len(actual_containers)
        ):
            return False
        for expected_container, actual_container in zip(
            expected_containers, actual_containers
        ):
            if (
                not isinstance(expected_container, dict)
                or not isinstance(actual_container, dict)
                or expected_container.get("name") != actual_container.get("name")
            ):
                return False
            expected_resources = expected_container.get("resources")
            actual_resources = actual_container.get("resources")
            if not isinstance(expected_resources, dict) or not isinstance(
                actual_resources, dict
            ):
                continue
            limits = expected_resources.get("limits")
            expected_requests = expected_resources.get("requests", {})
            actual_requests = actual_resources.get("requests")
            if (
                not isinstance(limits, dict)
                or not isinstance(expected_requests, dict)
                or not isinstance(actual_requests, dict)
            ):
                continue
            for resource_name, limit in limits.items():
                if (
                    resource_name not in expected_requests
                    and actual_requests.pop(resource_name, None) != limit
                ):
                    return False
            if not actual_requests and "requests" not in expected_resources:
                del actual_resources["requests"]
    return normalized == expected


def _validate_running_postgres_pod(
    *,
    config: Config,
    replica_set: dict,
    pod: object,
) -> _DatabaseExecutionTarget:
    replica_metadata = replica_set["metadata"]
    template = replica_set["spec"]["template"]
    template_metadata = template["metadata"]
    metadata = pod.get("metadata") if isinstance(pod, dict) else None
    spec = pod.get("spec") if isinstance(pod, dict) else None
    status = pod.get("status") if isinstance(pod, dict) else None
    conditions = status.get("conditions") if isinstance(status, dict) else None
    ready_conditions = (
        [
            condition
            for condition in conditions
            if isinstance(condition, dict) and condition.get("type") == "Ready"
        ]
        if isinstance(conditions, list)
        else []
    )
    containers = spec.get("containers") if isinstance(spec, dict) else None
    container = (
        containers[0] if isinstance(containers, list) and len(containers) == 1 else None
    )
    statuses = status.get("containerStatuses") if isinstance(status, dict) else None
    container_status = (
        statuses[0] if isinstance(statuses, list) and len(statuses) == 1 else None
    )
    state = (
        container_status.get("state") if isinstance(container_status, dict) else None
    )
    running = state.get("running") if isinstance(state, dict) else None
    name = metadata.get("name") if isinstance(metadata, dict) else None
    pod_uid = metadata.get("uid") if isinstance(metadata, dict) else None
    container_id = (
        container_status.get("containerID")
        if isinstance(container_status, dict)
        else None
    )
    if (
        not isinstance(pod, dict)
        or pod.get("apiVersion") != "v1"
        or pod.get("kind") != "Pod"
        or not isinstance(metadata, dict)
        or not isinstance(name, str)
        or not name.startswith(f"{replica_metadata['name']}-")
        or name == f"{replica_metadata['name']}-"
        or metadata.get("generateName") != f"{replica_metadata['name']}-"
        or not isinstance(pod_uid, str)
        or not pod_uid
        or metadata.get("namespace") != config.namespace
        or metadata.get("labels") != template_metadata.get("labels")
        or metadata.get("annotations", {}) != template_metadata.get("annotations", {})
        or metadata.get("finalizers", []) != []
        or "deletionTimestamp" in metadata
        or not _exact_owner_reference(
            metadata,
            api_version="apps/v1",
            kind="ReplicaSet",
            name=replica_metadata["name"],
            uid=replica_metadata["uid"],
        )
        or not _canonical_running_pod_spec(template.get("spec"), spec)
        or not isinstance(spec, dict)
        or spec.get("ephemeralContainers", []) != []
        or not isinstance(container, dict)
        or container.get("name") != "postgres"
        or container.get("image") != config.postgres_image
        or not isinstance(status, dict)
        or status.get("phase") != "Running"
        or status.get("initContainerStatuses", []) != []
        or status.get("ephemeralContainerStatuses", []) != []
        or len(ready_conditions) != 1
        or ready_conditions[0].get("status") != "True"
        or not isinstance(container_status, dict)
        or container_status.get("name") != "postgres"
        or not _container_status_image_matches_requested(
            container_status.get("image"),
            config.postgres_image,
        )
        or not _runtime_image_id_matches(
            container_status.get("imageID"),
            config.postgres_image,
            config.postgres_runtime_image,
        )
        or not isinstance(container_id, str)
        or re.fullmatch(r"containerd://[0-9a-f]{64}", container_id) is None
        or container_status.get("restartCount") != 0
        or container_status.get("ready") is not True
        or container_status.get("started") is not True
        or not isinstance(state, dict)
        or set(state) != {"running"}
        or not isinstance(running, dict)
        or not _utc_timestamp(running.get("startedAt"))
    ):
        raise RuntimeError("Identity PostgreSQL execution Pod identity is invalid")
    return _DatabaseExecutionTarget(
        pod_name=name,
        pod_uid=pod_uid,
        container_name="postgres",
    )


def _bind_postgres_execution_pod(
    *,
    config: Config,
    deployment: dict,
    replica_set: dict,
    replica_set_uids: set[str],
    inventory: object,
) -> _DatabaseExecutionTarget:
    items = inventory.get("items") if isinstance(inventory, dict) else None
    selector = deployment["spec"]["selector"].get("matchLabels")
    if (
        not isinstance(inventory, dict)
        or inventory.get("apiVersion") != "v1"
        or inventory.get("kind") != "List"
        or not isinstance(items, list)
        or not isinstance(selector, dict)
    ):
        raise RuntimeError("Identity PostgreSQL Pod inventory is invalid")
    candidates: list[dict] = []
    for item in items:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        owner_uids = _owner_uids(metadata)
        selected = _labels_match(
            metadata.get("labels") if isinstance(metadata, dict) else None,
            selector,
        )
        if (
            not owner_uids.intersection(
                {*replica_set_uids, deployment["metadata"]["uid"]}
            )
            and not selected
        ):
            continue
        if not isinstance(item, dict):
            # Malformed live state is a runtime contract failure, not caller misuse.
            raise RuntimeError(  # noqa: TRY004
                "Identity PostgreSQL Pod inventory is invalid"
            )
        candidates.append(item)
    if len(candidates) != 1:
        raise RuntimeError("Identity PostgreSQL execution Pod closure is invalid")
    return _validate_running_postgres_pod(
        config=config,
        replica_set=replica_set,
        pod=candidates[0],
    )


def _validate_postgres_execution_target(
    config: Config,
    runner: Runner,
    *,
    chart: Path,
    values: str,
    image_reference: str,
) -> _DatabaseExecutionTarget:
    immutable_image, _ = _signed_image_pair(
        config.postgres_image,
        config.postgres_runtime_image,
        component="postgres",
    )
    if image_reference != immutable_image:
        raise RuntimeError(
            "installed postgres image does not match signed release inventory"
        )
    expected = _render_postgres_deployment(
        config,
        runner,
        chart=chart,
        values=values,
    )
    deployment_raw = runner.run(
        _kubectl(
            config,
            "get",
            "deployment",
            "aileron-identity-postgres",
            "-n",
            config.namespace,
            "--output=json",
        )
    )
    try:
        deployment_document = json.loads(deployment_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "live Identity PostgreSQL Deployment is invalid JSON"
        ) from exc
    deployment = _validate_live_postgres_deployment(
        config,
        expected,
        deployment_document,
    )
    replica_sets_raw = runner.run(
        _kubectl(
            config,
            "get",
            "replicasets.apps",
            "-n",
            config.namespace,
            "--output=json",
        )
    )
    try:
        replica_sets = json.loads(replica_sets_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Identity PostgreSQL ReplicaSet inventory is invalid JSON"
        ) from exc
    replica_set, replica_set_uids = _bind_active_postgres_replica_set(
        config=config,
        deployment=deployment,
        inventory=replica_sets,
    )
    pods_raw = runner.run(
        _kubectl(
            config,
            "get",
            "pods",
            "-n",
            config.namespace,
            "--output=json",
        ),
        operation="postgres-pod-closure",
    )
    try:
        pods = json.loads(pods_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Identity PostgreSQL Pod inventory is invalid JSON") from exc
    target = _bind_postgres_execution_pod(
        config=config,
        deployment=deployment,
        replica_set=replica_set,
        replica_set_uids=replica_set_uids,
        inventory=pods,
    )
    return target


def _validate_workload_image(
    config: Config,
    runner: Runner,
    *,
    component: str,
    image_reference: str,
    immutable_image: str,
    runtime_immutable_image: str,
) -> None:
    immutable_image, runtime_immutable_image = _signed_image_pair(
        immutable_image,
        runtime_immutable_image,
        component=component,
    )
    if image_reference != immutable_image:
        raise RuntimeError(
            f"installed {component} image does not match signed release inventory"
        )
    pods_output = runner.run(
        _kubectl(
            config,
            "get",
            "pods",
            "-n",
            config.namespace,
            "-l",
            f"app.kubernetes.io/name=aileron-identity-{component}",
            "-o",
            "json",
        )
    )
    try:
        pods = json.loads(pods_output)["items"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{component} workload Pod inventory is invalid") from exc
    if not isinstance(pods, list) or not pods:
        raise RuntimeError(f"{component} workload has no running Pod evidence")
    for pod in pods:
        try:
            configured_images = {
                container["image"] for container in pod["spec"]["containers"]
            }
            image_ids = {
                status["imageID"] for status in pod["status"]["containerStatuses"]
            }
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"{component} workload Pod image evidence is invalid"
            ) from exc
        if (
            configured_images != {image_reference}
            or not image_ids
            or any(
                not _runtime_image_id_matches(
                    image_id, immutable_image, runtime_immutable_image
                )
                for image_id in image_ids
            )
        ):
            raise RuntimeError(
                f"{component} workload actual digest does not match installed values"
            )


def run_smoke(
    config: Config,
    runner: Runner,
    *,
    delete_client_loader: DeleteClientLoader | None = None,
    cleanup_sleeper: Sleeper = time.sleep,
) -> dict[str, object]:
    chart = _validate_local_release_identity(config, runner)
    expected_confirmation = _expected_confirmation(config)
    if config.confirmation != expected_confirmation:
        raise ValueError(
            "--confirm-destructive-restore must exactly equal "
            f"{expected_confirmation}"
        )
    current_context = runner.run(
        _kubectl(
            config,
            "config",
            "view",
            "--minify",
            "-o",
            "jsonpath={.current-context}",
        )
    ).strip()
    if current_context != config.context:
        raise RuntimeError(
            f"current kubectl context is {current_context!r}, expected {config.context!r}"
        )
    owner = runner.run(
        _kubectl(
            config,
            "get",
            "namespace",
            config.namespace,
            "-o",
            "jsonpath={.metadata.labels.platform\\.aileron\\.dev/namespace-owner}",
        )
    ).strip()
    if owner != "aileron-installer":
        raise RuntimeError("Identity namespace ownership label is invalid")
    _validate_release_metadata(config, runner)
    values = runner.run(
        _helm(
            config,
            "get",
            "values",
            config.release,
            "-n",
            config.namespace,
            "--all",
            "-o",
            "json",
        )
    )
    try:
        values_document = json.loads(values)
        claim_name = values_document["backup"]["claimName"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "installed Identity backup claim contract is invalid"
        ) from exc
    if not isinstance(claim_name, str) or not claim_name:
        raise RuntimeError("installed Identity backup claim contract is invalid")
    _validate_installed_manifest(
        config,
        runner,
        chart=chart,
        values=values,
    )
    _validate_workload_image(
        config,
        runner,
        component="keycloak",
        image_reference=_image_reference(values_document, "keycloak"),
        immutable_image=config.keycloak_image,
        runtime_immutable_image=config.keycloak_runtime_image,
    )
    runner.run(_kubectl(config, "get", "pvc", claim_name, "-n", config.namespace))
    replicas = runner.run(
        _kubectl(
            config,
            "get",
            "deployment/aileron-identity-keycloak",
            "-n",
            config.namespace,
            "-o",
            "jsonpath={.spec.replicas}",
        )
    ).strip()
    if not replicas.isdigit() or int(replicas) < 1:
        raise RuntimeError("Keycloak replica count is invalid")
    rendered_jobs = {
        operation: _render_job(
            config,
            runner,
            operation=operation,
            values=values,
            chart=chart,
        )
        for operation in ("backup", "restore")
    }
    postgres_values = values_document.get("postgres")
    postgres_enabled = (
        postgres_values.get("enabled") if isinstance(postgres_values, dict) else None
    )
    if not isinstance(postgres_enabled, bool):
        raise RuntimeError("installed Identity database mode contract is invalid")
    postgres_image_reference = _image_reference(values_document, "postgres")
    if postgres_enabled:
        database_target: _DatabaseExecutionTarget | _DatabaseJobExecutionTarget = (
            _validate_postgres_execution_target(
                config,
                runner,
                chart=chart,
                values=values,
                image_reference=postgres_image_reference,
            )
        )
    else:
        immutable_postgres_image, _ = _signed_image_pair(
            config.postgres_image,
            config.postgres_runtime_image,
            component="postgres",
        )
        if postgres_image_reference != immutable_postgres_image:
            raise RuntimeError(
                "installed postgres client image does not match signed release inventory"
            )
        database_target = _DatabaseJobExecutionTarget(rendered_jobs["backup"])
    delete_client = _load_job_delete_client(
        config,
        delete_client_loader or KUBERNETES_REST.load_kubernetes_delete_client,
    )
    backup_job_uids: list[str] = []
    restore_job_uid: str | None = None
    restore_marker: str | None = None

    def execute_database(action: str) -> str:
        return _exec_database(
            config,
            runner,
            database_target,
            action,
            delete_client=delete_client,
            cleanup_sleeper=cleanup_sleeper,
            immutable_image=config.postgres_image,
            runtime_immutable_image=config.postgres_runtime_image,
        )

    try:
        execute_database("create-marker")
        backup_job_uids.append(
            _run_job(
                config,
                runner,
                delete_client=delete_client,
                cleanup_sleeper=cleanup_sleeper,
                operation="backup",
                expected_job=rendered_jobs["backup"],
                immutable_image=config.postgres_image,
                runtime_immutable_image=config.postgres_runtime_image,
            )
        )
        execute_database("drop-marker")
        runner.run(
            _kubectl(
                config,
                "scale",
                "deployment/aileron-identity-keycloak",
                "-n",
                config.namespace,
                "--replicas=0",
            ),
            operation="scale-keycloak:0",
        )
        restore_job_uid = _run_job(
            config,
            runner,
            delete_client=delete_client,
            cleanup_sleeper=cleanup_sleeper,
            operation="restore",
            expected_job=rendered_jobs["restore"],
            immutable_image=config.postgres_image,
            runtime_immutable_image=config.postgres_runtime_image,
        )
        observed = execute_database("verify-marker").strip()
        if observed != "identity-smoke-marker":
            raise RuntimeError("restored database does not contain the smoke marker")
        restore_marker = observed
        execute_database("drop-marker")
        backup_job_uids.append(
            _run_job(
                config,
                runner,
                delete_client=delete_client,
                cleanup_sleeper=cleanup_sleeper,
                operation="backup",
                expected_job=rendered_jobs["backup"],
                immutable_image=config.postgres_image,
                runtime_immutable_image=config.postgres_runtime_image,
            )
        )
    finally:
        primary_failure = sys.exc_info()[1]
        cleanup_failures: list[Exception] = []
        try:
            runner.run(
                _kubectl(
                    config,
                    "scale",
                    "deployment/aileron-identity-keycloak",
                    "-n",
                    config.namespace,
                    f"--replicas={replicas}",
                ),
                operation=f"scale-keycloak:{replicas}",
            )
            runner.run(
                _kubectl(
                    config,
                    "rollout",
                    "status",
                    "deployment/aileron-identity-keycloak",
                    "-n",
                    config.namespace,
                    f"--timeout={config.timeout}",
                ),
                operation="rollout-keycloak-ready",
            )
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            cleanup_failures.append(exc)
        for operation in ("backup", "restore"):
            try:
                _delete_job_and_wait_for_pods(
                    config,
                    runner,
                    rendered_jobs[operation],
                    delete_client=delete_client,
                    cleanup_sleeper=cleanup_sleeper,
                )
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                cleanup_failures.append(exc)
        if cleanup_failures:
            failures = []
            if isinstance(primary_failure, Exception):
                failures.extend(_expanded_failures(primary_failure))
            for cleanup_failure in cleanup_failures:
                failures.extend(_expanded_failures(cleanup_failure))
            raise IdentitySmokeCleanupError(failures)
    if (
        len(backup_job_uids) != 2
        or restore_job_uid is None
        or restore_marker != "identity-smoke-marker"
        or len({*backup_job_uids, restore_job_uid}) != 3
    ):
        raise RuntimeError("Identity backup/restore smoke Job UID report is invalid")
    return {
        "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
        "backupJobUids": backup_job_uids,
        "restoreJobUid": restore_job_uid,
        "restoreMarker": restore_marker,
        "jobClosureVerified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--release-revision", required=True, type=int)
    parser.add_argument("--chart-version", required=True)
    parser.add_argument("--chart-digest", required=True)
    parser.add_argument("--keycloak-image", required=True)
    parser.add_argument("--keycloak-runtime-image", required=True)
    parser.add_argument("--postgres-image", required=True)
    parser.add_argument("--postgres-runtime-image", required=True)
    parser.add_argument("--timeout", default="10m")
    parser.add_argument("--confirm-destructive-restore", required=True)
    args = parser.parse_args()
    report = run_smoke(
        Config(
            context=args.context,
            kubeconfig=args.kubeconfig,
            namespace=args.namespace,
            release=args.release,
            expected_commit=args.commit,
            release_revision=args.release_revision,
            chart_version=args.chart_version,
            chart_digest=args.chart_digest,
            keycloak_image=args.keycloak_image,
            keycloak_runtime_image=args.keycloak_runtime_image,
            postgres_image=args.postgres_image,
            postgres_runtime_image=args.postgres_runtime_image,
            confirmation=args.confirm_destructive_restore,
            timeout=args.timeout,
        ),
        Runner(),
    )
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
