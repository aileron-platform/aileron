"""Identity backup and restore smoke orchestration tests."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backup_restore_smoke import (
    IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS,
    IDENTITY_JOB_TRANSACTION_ANNOTATION,
    Config,
    IdentitySmokeCleanupError,
    RecordingRunner,
    _DatabaseJobExecutionTarget,
    _database_command,
    _database_job,
    _exec_database,
    _run_job,
    _validate_completed_job_pod,
    main,
)
from backup_restore_smoke import _delete_job_and_wait_for_pods as _delete_job
from backup_restore_smoke import run_smoke as _run_smoke

COMMIT = "a" * 40
INDEX_KEYCLOAK = "sha256:" + "b" * 64
INDEX_POSTGRES = "sha256:" + "c" * 64
RUNTIME_KEYCLOAK = "sha256:" + "d" * 64
RUNTIME_POSTGRES = "sha256:" + "e" * 64
TREE_HASH = "1" * 40
CHART_TREE = (
    f"100644 blob {'2' * 40}\thelm/aileron-identity/Chart.yaml\n"
    f"100644 blob {'3' * 40}\thelm/aileron-identity/templates/backup-job.yaml\n"
    f"100644 blob {'4' * 40}\thelm/aileron-identity/templates/restore-job.yaml\n"
)
CHART_DIGEST = "sha256:" + hashlib.sha256(CHART_TREE.encode()).hexdigest()
RELEASE_MANIFEST = """---
# Source: aileron-identity/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: aileron-identity
"""
POSTGRES_DEPLOYMENT_UID = "identity-postgres-deployment-uid"
POSTGRES_REPLICA_SET_NAME = "aileron-identity-postgres-7f6c8d9b5f"
POSTGRES_REPLICA_SET_UID = "identity-postgres-replica-set-uid"
POSTGRES_POD_NAME = f"{POSTGRES_REPLICA_SET_NAME}-abcde"
POSTGRES_POD_UID = "identity-postgres-pod-uid"
PRIOR_TRANSACTION_TOKEN = "7" * 64


def _no_sleep(_seconds: float) -> None:
    return None


def run_smoke(config: Config, runner) -> dict[str, object]:
    return _run_smoke(
        config,
        runner,
        delete_client_loader=runner.delete_client_loader,
        cleanup_sleeper=_no_sleep,
    )


def _delete_job_and_wait_for_pods(
    config: Config,
    runner,
    expected_job: dict,
    *,
    delete_client,
    cleanup_sleeper,
) -> None:
    _delete_job(
        config,
        runner,
        expected_job,
        delete_client=delete_client,
        cleanup_sleeper=cleanup_sleeper,
    )


def _expected_job(operation: str) -> dict:
    job_name = f"aileron-identity-{operation}"
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "labels": {
                "app.kubernetes.io/part-of": "aileron-identity",
                "app.kubernetes.io/managed-by": "Helm",
                "helm.sh/chart": "aileron-identity-0.1.0",
            },
            "annotations": {
                "helm.sh/hook": (
                    "pre-upgrade"
                    if operation == "backup"
                    else "post-install,post-upgrade"
                ),
                "helm.sh/hook-delete-policy": ("before-hook-creation,hook-succeeded"),
            },
        },
        "spec": {
            "backoffLimit": 1,
            "template": {
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/name": job_name,
                        "platform.aileron.dev/identity-data-operation": operation,
                    }
                },
                "spec": {
                    "automountServiceAccountToken": False,
                    "restartPolicy": "Never",
                    "securityContext": {
                        "runAsNonRoot": True,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": operation,
                            "image": (
                                "registry.example.test/postgres@" + INDEX_POSTGRES
                            ),
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "command": ["/bin/sh", "-ec"],
                            "args": [f"run-{operation}"],
                        }
                    ],
                },
            },
        },
    }


def _server_job(operation: str, uid: str = "identity-job-uid") -> tuple[dict, dict]:
    expected = _expected_job(operation)
    actual = copy.deepcopy(expected)
    name = expected["metadata"]["name"]
    actual["metadata"].update(
        {
            "namespace": "aileron-identity-system",
            "uid": uid,
            "resourceVersion": f"{uid}-rv",
            "ownerReferences": [],
        }
    )
    actual["spec"].update(
        {
            "completionMode": "NonIndexed",
            "completions": 1,
            "manualSelector": False,
            "parallelism": 1,
            "podReplacementPolicy": "TerminatingOrFailed",
            "selector": {"matchLabels": {"batch.kubernetes.io/controller-uid": uid}},
            "suspend": False,
        }
    )
    actual["spec"]["template"]["metadata"].update({"creationTimestamp": None})
    actual["spec"]["template"]["metadata"]["labels"].update(
        {
            "batch.kubernetes.io/controller-uid": uid,
            "batch.kubernetes.io/job-name": name,
            "controller-uid": uid,
            "job-name": name,
        }
    )
    pod_spec = actual["spec"]["template"]["spec"]
    pod_spec.update(
        {
            "dnsPolicy": "ClusterFirst",
            "schedulerName": "default-scheduler",
            "terminationGracePeriodSeconds": 30,
        }
    )
    pod_spec["containers"][0].update(
        {
            "imagePullPolicy": "IfNotPresent",
            "resources": {},
            "terminationMessagePath": "/dev/termination-log",
            "terminationMessagePolicy": "File",
        }
    )
    actual["status"] = {
        "startTime": "2026-08-10T01:00:00Z",
        "completionTime": "2026-08-10T01:00:03Z",
        "succeeded": 1,
        "conditions": [
            {
                "type": "Complete",
                "status": "True",
                "lastTransitionTime": "2026-08-10T01:00:03Z",
                "reason": "CompletionsReached",
                "message": "Job completed",
            }
        ],
    }
    return expected, actual


def _add_transaction(job: dict, token: str = PRIOR_TRANSACTION_TOKEN) -> dict:
    transaction_job = copy.deepcopy(job)
    transaction_job["metadata"]["annotations"][
        IDENTITY_JOB_TRANSACTION_ANNOTATION
    ] = token
    return transaction_job


def _replace_job_uid(job: dict, uid: str) -> dict:
    replacement = copy.deepcopy(job)
    replacement["metadata"]["uid"] = uid
    replacement["metadata"]["resourceVersion"] = f"{uid}-rv"
    replacement["spec"]["selector"]["matchLabels"][
        "batch.kubernetes.io/controller-uid"
    ] = uid
    labels = replacement["spec"]["template"]["metadata"]["labels"]
    labels["batch.kubernetes.io/controller-uid"] = uid
    labels["controller-uid"] = uid
    return replacement


class FakeKubernetesDeleteClient:
    def __init__(self, runner) -> None:
        self.runner = runner
        self.calls: list[dict] = []

    def delete(self, **request) -> None:
        self.calls.append(copy.deepcopy(request))
        self.runner.delete_job(**request)


class FakeDeleteClientLoader:
    def __init__(self, client: FakeKubernetesDeleteClient) -> None:
        self.client = client
        self.calls: list[dict] = []

    def __call__(self, **request) -> FakeKubernetesDeleteClient:
        self.calls.append(copy.deepcopy(request))
        return self.client


class TransactionRecordingRunner(RecordingRunner):
    def __init__(
        self,
        *,
        outputs: dict[tuple[str, ...], str],
        live_jobs: dict[str, dict | None],
        job_templates: dict[str, dict],
    ) -> None:
        super().__init__(outputs=outputs)
        self.live_jobs = copy.deepcopy(live_jobs)
        self.job_templates = copy.deepcopy(job_templates)
        self.create_counts = {"backup": 0, "restore": 0}
        self.delete_client = FakeKubernetesDeleteClient(self)
        self.delete_client_loader = FakeDeleteClientLoader(self.delete_client)

    def delete_job(self, **request) -> None:
        name = request["name"]
        current = self.live_jobs.get(name)
        metadata = current.get("metadata") if isinstance(current, dict) else None
        if (
            request.get("api_version") != "batch/v1"
            or request.get("resource") != "jobs"
            or request.get("namespace") != "aileron-identity-system"
            or not isinstance(metadata, dict)
            or request.get("uid") != metadata.get("uid")
            or request.get("resource_version") != metadata.get("resourceVersion")
        ):
            raise RuntimeError("fake Kubernetes delete precondition rejected")
        self.live_jobs[name] = None

    def run(self, args, *, operation=None, stdin=None):
        command = tuple(args)
        if (
            "create" in command
            and "--dry-run=client" not in command
            and operation in {"backup", "restore"}
        ):
            super().run(args, operation=operation, stdin=stdin)
            transaction_job = json.loads(stdin)
            name = transaction_job["metadata"]["name"]
            actual = copy.deepcopy(self.job_templates[operation])
            self.create_counts[operation] += 1
            if self.create_counts[operation] > 1:
                actual = _replace_job_uid(
                    actual,
                    f"{actual['metadata']['uid']}-{self.create_counts[operation]}",
                )
            actual["metadata"]["annotations"] = copy.deepcopy(
                transaction_job["metadata"]["annotations"]
            )
            self.live_jobs[name] = actual
            return json.dumps(actual)
        if (
            "get" in command
            and "pods" in command
            and "--sort-by=.metadata.name" in command
            and any(
                "batch.kubernetes.io/controller-uid=identity-backup-job-uid-2" in part
                for part in command
            )
        ):
            super().run(args, operation=operation, stdin=stdin)
            job = self.live_jobs["aileron-identity-backup"]
            return json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "List",
                    "items": [_completed_pod("backup", job, RUNTIME_POSTGRES)],
                }
            )
        if "get" in command and "job" in command:
            super().run(args, operation=operation, stdin=stdin)
            name = command[command.index("job") + 1]
            job = self.live_jobs.get(name)
            return json.dumps(job) if job is not None else ""
        return super().run(args, operation=operation, stdin=stdin)


class TransactionScenarioRunner(TransactionRecordingRunner):
    def __init__(
        self,
        delegate: TransactionRecordingRunner,
        *,
        scenario: str,
    ) -> None:
        super().__init__(
            outputs=delegate.outputs,
            live_jobs=delegate.live_jobs,
            job_templates=delegate.job_templates,
        )
        self.scenario = scenario
        self.create_accepted = False
        self.exact_reconciliation_failures = 0
        self.cleanup_identity_reads = 0
        self.delete_attempts = 0

    def delete_job(self, **request) -> None:
        self.delete_attempts += 1
        if self.scenario == "delete-not-accepted" and self.delete_attempts == 1:
            raise RuntimeError("delete request was not accepted")
        if self.scenario in {"delete-accepted-error", "delete-replacement"}:
            current = self.live_jobs["aileron-identity-backup"]
            super().delete_job(**request)
            if self.scenario == "delete-replacement":
                _, replacement = _server_job("backup", "replacement-backup-job-uid")
                replacement["metadata"]["annotations"] = copy.deepcopy(
                    current["metadata"]["annotations"]
                )
                self.live_jobs["aileron-identity-backup"] = replacement
            raise RuntimeError("delete response was lost")
        super().delete_job(**request)

    def run(self, args, *, operation=None, stdin=None):
        command = tuple(args)
        output = super().run(args, operation=operation, stdin=stdin)
        is_create = (
            "create" in command
            and "--dry-run=client" not in command
            and operation == "backup"
        )
        if is_create:
            self.create_accepted = True
            if self.scenario.startswith("admission-drift"):
                job = self.live_jobs["aileron-identity-backup"]
                job["spec"]["template"]["spec"]["containers"].append(
                    {
                        "name": "admission-sidecar",
                        "image": "registry.example.test/sidecar@sha256:" + "9" * 64,
                    }
                )
                output = json.dumps(job)
            if self.scenario in {
                "ambiguous-create",
                "reconciliation-failure",
                "cleanup-exhausted",
            }:
                raise RuntimeError("create response was lost")
            return output

        is_target_get = (
            self.create_accepted
            and "get" in command
            and "job" in command
            and "aileron-identity-backup" in command
        )
        if (
            is_target_get
            and "--ignore-not-found" not in command
            and self.scenario in {"reconciliation-failure", "cleanup-exhausted"}
        ):
            self.exact_reconciliation_failures += 1
            raise RuntimeError("first reconciliation was unavailable")
        if is_target_get and "--ignore-not-found" in command:
            self.cleanup_identity_reads += 1
            if self.scenario == "cleanup-exhausted":
                raise RuntimeError("final recovery was unavailable")
            if self.cleanup_identity_reads == 1:
                if self.scenario == "admission-drift-transport":
                    raise RuntimeError("cleanup identity transport unavailable")
                if self.scenario == "admission-drift-invalid-json":
                    return "{"

        if self.create_accepted and "wait" in command:
            current = self.live_jobs["aileron-identity-backup"]
            if self.scenario == "foreign-token":
                current["metadata"]["annotations"][
                    IDENTITY_JOB_TRANSACTION_ANNOTATION
                ] = ("8" * 64)
                raise RuntimeError("execution wait failed")
            if self.scenario == "replacement-uid":
                _, replacement = _server_job("backup", "replacement-backup-job-uid")
                replacement["metadata"]["annotations"] = copy.deepcopy(
                    current["metadata"]["annotations"]
                )
                self.live_jobs["aileron-identity-backup"] = replacement
                raise RuntimeError("execution wait failed")
        return output


class DelayedForegroundDeletionRunner(TransactionRecordingRunner):
    def __init__(
        self,
        delegate: TransactionRecordingRunner,
        *,
        closure_after_rounds: int | None,
    ) -> None:
        super().__init__(
            outputs=delegate.outputs,
            live_jobs=delegate.live_jobs,
            job_templates=delegate.job_templates,
        )
        self.closure_after_rounds = closure_after_rounds
        self.closure_round = 0
        self.delete_accepted = False

    def delete_job(self, **request) -> None:
        if self.delete_accepted:
            raise RuntimeError("foreground delete was repeated")
        current = copy.deepcopy(self.live_jobs[request["name"]])
        super().delete_job(**request)
        current["metadata"]["deletionTimestamp"] = "2026-08-11T01:00:00Z"
        current["metadata"]["resourceVersion"] = f"{request['uid']}-terminating-rv"
        self.live_jobs[request["name"]] = current
        self.delete_accepted = True

    def run(self, args, *, operation=None, stdin=None):
        command = tuple(args)
        if (
            self.delete_accepted
            and "get" in command
            and "job" in command
            and self.closure_after_rounds is not None
            and self.closure_round >= self.closure_after_rounds
        ):
            self.live_jobs["aileron-identity-backup"] = None
        output = super().run(args, operation=operation, stdin=stdin)
        if self.delete_accepted and "get" in command and "pods" in command:
            still_terminating = (
                self.closure_after_rounds is None
                or self.closure_round < self.closure_after_rounds
            )
            output = json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "List",
                    "items": (
                        [
                            {
                                "apiVersion": "v1",
                                "kind": "Pod",
                                "metadata": {
                                    "name": "aileron-identity-backup-terminating",
                                    "namespace": "aileron-identity-system",
                                    "deletionTimestamp": "2026-08-11T01:00:00Z",
                                },
                            }
                        ]
                        if still_terminating
                        else []
                    ),
                }
            )
            if any(
                "batch.kubernetes.io/job-name=aileron-identity-backup" in part
                for part in command
            ):
                self.closure_round += 1
        return output


class LastAttemptAmbiguousDeletionRunner(DelayedForegroundDeletionRunner):
    def __init__(self, delegate: TransactionRecordingRunner) -> None:
        super().__init__(delegate, closure_after_rounds=2)
        self.delete_attempts = 0

    def delete_job(self, **request) -> None:
        self.delete_attempts += 1
        if self.delete_attempts < IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS:
            raise RuntimeError("delete request was not accepted")
        super().delete_job(**request)
        raise RuntimeError("delete response was lost")


def _completed_pod(operation: str, job: dict, image_id_digest: str) -> dict:
    name = job["metadata"]["name"]
    uid = job["metadata"]["uid"]
    pod_spec = copy.deepcopy(job["spec"]["template"]["spec"])
    pod_spec.update(
        {
            "enableServiceLinks": True,
            "nodeName": "homelab-worker-1",
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
    )
    container_id = "containerd://" + "f" * 64
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"{name}-abcde",
            "generateName": f"{name}-",
            "namespace": "aileron-identity-system",
            "uid": f"{operation}-pod-uid",
            "labels": copy.deepcopy(job["spec"]["template"]["metadata"]["labels"]),
            "ownerReferences": [
                {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "name": name,
                    "uid": uid,
                    "controller": True,
                    "blockOwnerDeletion": True,
                }
            ],
        },
        "spec": pod_spec,
        "status": {
            "phase": "Succeeded",
            "containerStatuses": [
                {
                    "name": operation,
                    "image": f"registry.example.test/postgres@{INDEX_POSTGRES}",
                    "imageID": (f"registry.example.test/postgres@{image_id_digest}"),
                    "containerID": container_id,
                    "ready": False,
                    "restartCount": 0,
                    "started": False,
                    "state": {
                        "terminated": {
                            "containerID": container_id,
                            "exitCode": 0,
                            "reason": "Completed",
                            "startedAt": "2026-08-10T01:00:01Z",
                            "finishedAt": "2026-08-10T01:00:02Z",
                        }
                    },
                }
            ],
        },
    }


def _pod_document(
    image: str,
    image_id_digest: str,
    *,
    image_id_repository: str | None = None,
) -> str:
    runtime_repository = image_id_repository or image.rsplit("@", 1)[0]
    return json.dumps(
        {
            "items": [
                {
                    "spec": {"containers": [{"name": "service", "image": image}]},
                    "status": {
                        "containerStatuses": [
                            {
                                "name": "service",
                                "imageID": f"{runtime_repository}@{image_id_digest}",
                            }
                        ]
                    },
                }
            ]
        }
    )


def _expected_postgres_deployment() -> dict:
    labels = {
        "app.kubernetes.io/managed-by": "Helm",
        "app.kubernetes.io/part-of": "aileron-identity",
        "helm.sh/chart": "aileron-identity-0.1.0",
    }
    pod_labels = {
        "app.kubernetes.io/name": "aileron-identity-postgres",
        "app.kubernetes.io/part-of": "aileron-identity",
    }
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "aileron-identity-postgres",
            "labels": labels,
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {"app.kubernetes.io/name": "aileron-identity-postgres"}
            },
            "strategy": {"type": "Recreate"},
            "template": {
                "metadata": {"labels": pod_labels},
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "fsGroup": 70,
                        "fsGroupChangePolicy": "OnRootMismatch",
                        "runAsGroup": 70,
                        "runAsNonRoot": True,
                        "runAsUser": 70,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "postgres",
                            "image": f"registry.example.test/postgres@{INDEX_POSTGRES}",
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [{"name": "postgres", "containerPort": 5432}],
                            "readinessProbe": {
                                "exec": {"command": ["/bin/sh", "-ec", "pg_isready"]}
                            },
                            "resources": {},
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                        }
                    ],
                },
            },
        },
    }


def _server_postgres_deployment() -> tuple[dict, dict]:
    expected = _expected_postgres_deployment()
    actual = copy.deepcopy(expected)
    actual["metadata"].update(
        {
            "namespace": "aileron-identity-system",
            "uid": POSTGRES_DEPLOYMENT_UID,
            "generation": 3,
            "annotations": {
                "deployment.kubernetes.io/revision": "3",
                "meta.helm.sh/release-name": "aileron-identity",
                "meta.helm.sh/release-namespace": "aileron-identity-system",
            },
            "ownerReferences": [],
        }
    )
    actual["spec"].update(
        {
            "progressDeadlineSeconds": 600,
            "revisionHistoryLimit": 10,
        }
    )
    template = actual["spec"]["template"]
    template["metadata"]["creationTimestamp"] = None
    pod_spec = template["spec"]
    pod_spec.update(
        {
            "dnsPolicy": "ClusterFirst",
            "restartPolicy": "Always",
            "schedulerName": "default-scheduler",
            "terminationGracePeriodSeconds": 30,
        }
    )
    container = pod_spec["containers"][0]
    container.update(
        {
            "terminationMessagePath": "/dev/termination-log",
            "terminationMessagePolicy": "File",
        }
    )
    container["ports"][0]["protocol"] = "TCP"
    container["readinessProbe"].update(
        {
            "failureThreshold": 3,
            "periodSeconds": 10,
            "successThreshold": 1,
            "timeoutSeconds": 1,
        }
    )
    actual["status"] = {
        "observedGeneration": 3,
        "replicas": 1,
        "updatedReplicas": 1,
        "readyReplicas": 1,
        "availableReplicas": 1,
    }
    return expected, actual


def _active_postgres_replica_set(deployment: dict) -> dict:
    template = copy.deepcopy(deployment["spec"]["template"])
    template["metadata"]["labels"]["pod-template-hash"] = "7f6c8d9b5f"
    return {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": POSTGRES_REPLICA_SET_NAME,
            "namespace": "aileron-identity-system",
            "uid": POSTGRES_REPLICA_SET_UID,
            "generation": 1,
            "labels": {
                **template["metadata"]["labels"],
                "pod-template-hash": "7f6c8d9b5f",
            },
            "annotations": {
                **deployment["metadata"]["annotations"],
                "deployment.kubernetes.io/desired-replicas": "1",
                "deployment.kubernetes.io/max-replicas": "1",
                "deployment.kubernetes.io/revision": "3",
            },
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "aileron-identity-postgres",
                    "uid": POSTGRES_DEPLOYMENT_UID,
                    "controller": True,
                    "blockOwnerDeletion": True,
                }
            ],
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {
                    "app.kubernetes.io/name": "aileron-identity-postgres",
                    "pod-template-hash": "7f6c8d9b5f",
                }
            },
            "template": template,
        },
        "status": {
            "observedGeneration": 1,
            "replicas": 1,
            "fullyLabeledReplicas": 1,
            "readyReplicas": 1,
            "availableReplicas": 1,
        },
    }


def _running_postgres_pod(replica_set: dict) -> dict:
    pod_spec = copy.deepcopy(replica_set["spec"]["template"]["spec"])
    pod_spec.update(
        {
            "enableServiceLinks": True,
            "nodeName": "homelab-worker-1",
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
    )
    container_id = "containerd://" + "f" * 64
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": POSTGRES_POD_NAME,
            "generateName": f"{POSTGRES_REPLICA_SET_NAME}-",
            "namespace": "aileron-identity-system",
            "uid": POSTGRES_POD_UID,
            "labels": copy.deepcopy(
                replica_set["spec"]["template"]["metadata"]["labels"]
            ),
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "ReplicaSet",
                    "name": POSTGRES_REPLICA_SET_NAME,
                    "uid": POSTGRES_REPLICA_SET_UID,
                    "controller": True,
                    "blockOwnerDeletion": True,
                }
            ],
        },
        "spec": pod_spec,
        "status": {
            "phase": "Running",
            "conditions": [{"type": "Ready", "status": "True"}],
            "containerStatuses": [
                {
                    "name": "postgres",
                    "image": f"registry.example.test/postgres@{INDEX_POSTGRES}",
                    "imageID": f"registry.example.test/postgres@{RUNTIME_POSTGRES}",
                    "containerID": container_id,
                    "ready": True,
                    "restartCount": 0,
                    "started": True,
                    "state": {"running": {"startedAt": "2026-08-10T00:00:00Z"}},
                }
            ],
            "initContainerStatuses": [],
        },
    }


class BackupRestoreSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository_root = Path(self.temporary_directory.name)
        chart = self.repository_root / "helm/aileron-identity"
        (chart / "templates").mkdir(parents=True)
        (chart / "Chart.yaml").write_text(
            "apiVersion: v2\nname: aileron-identity\nversion: 0.1.0\n",
            encoding="utf-8",
        )
        (chart / "templates/backup-job.yaml").write_text("backup\n", encoding="utf-8")
        (chart / "templates/restore-job.yaml").write_text("restore\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def config(self, *, confirmation: str | None = None) -> Config:
        keycloak_image = f"registry.example.test/keycloak@{INDEX_KEYCLOAK}"
        keycloak_runtime_image = f"registry.example.test/keycloak@{RUNTIME_KEYCLOAK}"
        postgres_image = f"registry.example.test/postgres@{INDEX_POSTGRES}"
        postgres_runtime_image = f"registry.example.test/postgres@{RUNTIME_POSTGRES}"
        expected = (
            "rke2-207-homelab/aileron-identity-system/aileron-identity"
            f"@revision=7,chart=0.1.0,commit={COMMIT},chartDigest={CHART_DIGEST}"
            f",keycloakImage={keycloak_image}"
            f",keycloakRuntimeImage={keycloak_runtime_image}"
            f",postgresImage={postgres_image}"
            f",postgresRuntimeImage={postgres_runtime_image}"
        )
        return Config(
            context="rke2-207-homelab",
            kubeconfig=Path("/private/acceptance/kubeconfig"),
            namespace="aileron-identity-system",
            release="aileron-identity",
            expected_commit=COMMIT,
            release_revision=7,
            chart_version="0.1.0",
            chart_digest=CHART_DIGEST,
            keycloak_image=keycloak_image,
            keycloak_runtime_image=keycloak_runtime_image,
            postgres_image=postgres_image,
            postgres_runtime_image=postgres_runtime_image,
            confirmation=expected if confirmation is None else confirmation,
        )

    def runner(self) -> TransactionRecordingRunner:
        keycloak_image = f"registry.example.test/keycloak@{INDEX_KEYCLOAK}"
        postgres_image = f"registry.example.test/postgres@{INDEX_POSTGRES}"
        postgres_expected, postgres_deployment = _server_postgres_deployment()
        postgres_replica_set = _active_postgres_replica_set(postgres_deployment)
        postgres_pod = _running_postgres_pod(postgres_replica_set)
        backup_expected, backup_actual = _server_job(
            "backup", "identity-backup-job-uid"
        )
        restore_expected, restore_actual = _server_job(
            "restore", "identity-restore-job-uid"
        )
        return TransactionRecordingRunner(
            outputs={
                ("git", "rev-parse", "HEAD"): f"{COMMIT}\n",
                ("git", "rev-parse", "--show-toplevel"): f"{self.repository_root}\n",
                (
                    "git",
                    "rev-parse",
                    f"{COMMIT}:helm/aileron-identity",
                ): f"{TREE_HASH}\n",
                ("git", "ls-tree", "-d"): (
                    f"040000 tree {TREE_HASH}\thelm/aileron-identity\n"
                ),
                ("git", "ls-tree", "-r"): CHART_TREE,
                ("git", "ls-files", "--stage"): CHART_TREE.replace(
                    " blob ", " "
                ).replace("\thelm", " 0\thelm"),
                ("git", "ls-files", "--others"): "",
                ("kubectl", "config", "view"): "rke2-207-homelab\n",
                ("kubectl", "get", "namespace"): "aileron-installer",
                ("helm", "list"): json.dumps(
                    [
                        {
                            "name": "aileron-identity",
                            "namespace": "aileron-identity-system",
                            "revision": "7",
                            "status": "deployed",
                            "chart": "aileron-identity-0.1.0",
                        }
                    ]
                ),
                ("helm", "get", "metadata"): json.dumps(
                    {
                        "name": "aileron-identity",
                        "namespace": "aileron-identity-system",
                        "revision": 7,
                        "status": "deployed",
                        "chart": "aileron-identity",
                        "version": "0.1.0",
                    }
                ),
                ("helm", "get", "manifest"): RELEASE_MANIFEST,
                ("helm", "template", "--include-crds"): RELEASE_MANIFEST,
                ("helm", "get", "values"): json.dumps(
                    {
                        "backup": {"enabled": False, "claimName": "identity-backup"},
                        "postgres": {"enabled": True},
                        "images": {
                            "keycloak": {
                                "repository": "registry.example.test/keycloak",
                                "digest": INDEX_KEYCLOAK,
                            },
                            "postgres": {
                                "repository": "registry.example.test/postgres",
                                "digest": INDEX_POSTGRES,
                            },
                        },
                    }
                ),
                ("kubectl", "get", "pods", "aileron-identity-keycloak"): _pod_document(
                    keycloak_image, RUNTIME_KEYCLOAK
                ),
                ("kubectl", "get", "pods", "aileron-identity-postgres"): _pod_document(
                    postgres_image, RUNTIME_POSTGRES
                ),
                (
                    "helm",
                    "template",
                    "templates/postgres-deployment.yaml",
                ): (
                    "kind: Deployment\n"
                    "metadata:\n  name: aileron-identity-postgres\n"
                ),
                ("normalize-postgres-deployment",): json.dumps(postgres_expected),
                (
                    "kubectl",
                    "get",
                    "deployment",
                    "aileron-identity-postgres",
                    "--output=json",
                ): json.dumps(postgres_deployment),
                (
                    "kubectl",
                    "get",
                    "replicasets.apps",
                    "--output=json",
                ): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [postgres_replica_set],
                    }
                ),
                ("postgres-pod-closure",): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [postgres_pod],
                    }
                ),
                (
                    "kubectl",
                    "get",
                    "pod",
                    POSTGRES_POD_NAME,
                    "--output=json",
                ): json.dumps(postgres_pod),
                ("kubectl", "get", "deployment/aileron-identity-keycloak"): "1\n",
                ("helm", "template", "templates/backup-job.yaml"): (
                    "kind: Job\nmetadata:\n  name: aileron-identity-backup\n"
                ),
                ("helm", "template", "templates/restore-job.yaml"): (
                    "kind: Job\nmetadata:\n  name: aileron-identity-restore\n"
                ),
                ("normalize-backup",): json.dumps(backup_expected),
                ("normalize-restore",): json.dumps(restore_expected),
                (
                    " get job ",
                    "aileron-identity-backup",
                ): json.dumps(backup_actual),
                (
                    " get job ",
                    "aileron-identity-restore",
                ): json.dumps(restore_actual),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/controller-uid=identity-backup-job-uid",
                    "--sort-by=.metadata.name",
                ): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [
                            _completed_pod("backup", backup_actual, RUNTIME_POSTGRES)
                        ],
                    }
                ),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/controller-uid=identity-restore-job-uid",
                    "--sort-by=.metadata.name",
                ): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [
                            _completed_pod("restore", restore_actual, RUNTIME_POSTGRES)
                        ],
                    }
                ),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/controller-uid=identity-backup-job-uid",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/controller-uid=identity-restore-job-uid",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/job-name=aileron-identity-backup",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                (
                    "kubectl",
                    "get",
                    "pods",
                    "batch.kubernetes.io/job-name=aileron-identity-restore",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                ("kubectl", "exec", "verify-marker"): "identity-smoke-marker\n",
            },
            live_jobs={
                backup_actual["metadata"]["name"]: _add_transaction(backup_actual),
                restore_actual["metadata"]["name"]: _add_transaction(restore_actual),
            },
            job_templates={
                "backup": backup_actual,
                "restore": restore_actual,
            },
        )

    def transaction_runner(self, scenario: str) -> TransactionScenarioRunner:
        delegate = self.runner()
        delegate.live_jobs["aileron-identity-backup"] = None
        return TransactionScenarioRunner(delegate, scenario=scenario)

    def run_backup_job(self, runner: TransactionRecordingRunner) -> None:
        config = self.config()
        _run_job(
            config,
            runner,
            delete_client=runner.delete_client,
            cleanup_sleeper=_no_sleep,
            operation="backup",
            expected_job=_expected_job("backup"),
            immutable_image=config.postgres_image,
            runtime_immutable_image=config.postgres_runtime_image,
        )

    def assert_backup_job_deleted_once(
        self,
        runner: TransactionRecordingRunner,
    ) -> None:
        delete_calls = [
            request
            for request in runner.delete_client.calls
            if request["name"] == "aileron-identity-backup"
        ]
        self.assertEqual(len(delete_calls), 1)
        self.assertEqual(
            delete_calls[0]["uid"],
            "identity-backup-job-uid",
        )
        self.assertIsNone(runner.live_jobs["aileron-identity-backup"])

    def test_database_password_uses_only_mode_0600_pgpassfile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            secret_directory = temporary / "identity-postgres"
            secret_directory.mkdir(parents=True, exist_ok=True)
            (secret_directory / "username").write_text(
                "identity-user", encoding="utf-8"
            )
            (secret_directory / "password").write_text(
                "SENTINEL_DATABASE_PASSWORD", encoding="utf-8"
            )
            command = _database_command("create-marker", str(secret_directory))
            self.assertIn("umask 077", command)
            self.assertIn("chmod 0600", command)
            self.assertIn("PGPASSFILE=", command)
            self.assertNotIn("PGPASSWORD", command)
            self.assertNotIn("--password", command)
            self.assertNotIn("SENTINEL_DATABASE_PASSWORD", command)
            fake_psql = temporary / "psql"
            fake_psql.write_text(
                """#!/bin/sh
set -eu
printf '%s\n' "$*" >"${CAPTURE}.argv"
env >"${CAPTURE}.env"
cp "${PGPASSFILE}" "${CAPTURE}.pgpass"
stat -c '%a' "${PGPASSFILE}" >"${CAPTURE}.mode"
""",
                encoding="utf-8",
            )
            fake_psql.chmod(0o755)
            capture = temporary / "capture"
            subprocess.run(
                ["/bin/sh", "-ec", command],
                check=True,
                env=os.environ
                | {
                    "PATH": f"{temporary}:{os.environ['PATH']}",
                    "DATABASE_URL": "postgresql://identity-postgres:5432/keycloak",
                    "CAPTURE": str(capture),
                },
            )

            argv = capture.with_suffix(".argv").read_text(encoding="utf-8")
            environment = capture.with_suffix(".env").read_text(encoding="utf-8")
            pgpass = capture.with_suffix(".pgpass").read_text(encoding="utf-8")
            mode = capture.with_suffix(".mode").read_text(encoding="utf-8").strip()

        self.assertNotIn("SENTINEL_DATABASE_PASSWORD", argv)
        self.assertNotIn("SENTINEL_DATABASE_PASSWORD", environment)
        self.assertEqual(
            pgpass,
            "*:*:*:identity-user:SENTINEL_DATABASE_PASSWORD\n",
        )
        self.assertEqual(mode, "600")

    def test_external_database_marker_runs_in_ephemeral_postgres_client_job(
        self,
    ) -> None:
        template = _expected_job("backup")
        template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = [
            {"name": "backup", "mountPath": "/backup"},
            {"name": "postgres-secret", "mountPath": "/run/secrets"},
        ]
        template["spec"]["template"]["spec"]["volumes"] = [
            {"name": "backup", "persistentVolumeClaim": {"claimName": "backup"}},
            {"name": "postgres-secret", "secret": {"secretName": "postgres"}},
        ]
        expected = _database_job(template, "verify-marker")

        self.assertEqual(
            "aileron-identity-database-verify-marker",
            expected["metadata"]["name"],
        )
        self.assertFalse(
            any(
                key.startswith("helm.sh/")
                for key in expected["metadata"]["annotations"]
            )
        )
        pod_spec = expected["spec"]["template"]["spec"]
        self.assertFalse(
            any(volume["name"] == "backup" for volume in pod_spec["volumes"])
        )
        command = pod_spec["containers"][0]["args"][0]
        self.assertIn('--dbname="$DATABASE_URL"', command)
        self.assertIn("SELECT marker", command)

        with mock.patch("backup_restore_smoke._run_job") as run_job:
            run_job.side_effect = lambda *args, **kwargs: kwargs["output"].append(
                "identity-smoke-marker\n"
            )
            observed = _exec_database(
                self.config(),
                RecordingRunner(),
                _DatabaseJobExecutionTarget(template),
                "verify-marker",
                delete_client=object(),
                immutable_image=self.config().postgres_image,
                runtime_immutable_image=self.config().postgres_runtime_image,
            )

        self.assertEqual("identity-smoke-marker\n", observed)
        self.assertEqual(
            "database-verify-marker", run_job.call_args.kwargs["operation"]
        )

    def test_requires_commit_revision_and_chart_bound_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "confirm-destructive-restore"):
            run_smoke(self.config(confirmation="no"), self.runner())

    def test_cli_has_no_arbitrary_chart_path_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "backup_restore_smoke.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('add_argument("--chart",', source)

    def test_cli_prints_only_canonical_smoke_report_json(self) -> None:
        report = {
            "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
            "backupJobUids": ["backup-uid-1", "backup-uid-2"],
            "restoreJobUid": "restore-uid",
            "restoreMarker": "identity-smoke-marker",
            "jobClosureVerified": True,
        }
        arguments = [
            "backup_restore_smoke.py",
            "--context",
            "context",
            "--kubeconfig",
            "/private/kubeconfig",
            "--namespace",
            "namespace",
            "--release",
            "release",
            "--commit",
            COMMIT,
            "--release-revision",
            "7",
            "--chart-version",
            "0.1.0",
            "--chart-digest",
            CHART_DIGEST,
            "--keycloak-image",
            f"registry.example.test/keycloak@{INDEX_KEYCLOAK}",
            "--keycloak-runtime-image",
            f"registry.example.test/keycloak@{RUNTIME_KEYCLOAK}",
            "--postgres-image",
            f"registry.example.test/postgres@{INDEX_POSTGRES}",
            "--postgres-runtime-image",
            f"registry.example.test/postgres@{RUNTIME_POSTGRES}",
            "--confirm-destructive-restore",
            "confirmation",
        ]
        output = io.StringIO()
        with (
            mock.patch("sys.argv", arguments),
            mock.patch("backup_restore_smoke.run_smoke", return_value=report),
            redirect_stdout(output),
        ):
            self.assertEqual(main(), 0)

        self.assertEqual(
            output.getvalue(),
            json.dumps(report, separators=(",", ":"), sort_keys=True) + "\n",
        )

    def test_job_cleanup_validates_identity_and_deletes_by_observed_uid(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        uid = actual["metadata"]["uid"]
        runner = TransactionRecordingRunner(
            outputs={
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/controller-uid={uid}",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/job-name={name}",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
            },
            live_jobs={name: actual},
            job_templates={},
        )

        _delete_job_and_wait_for_pods(
            config,
            runner,
            expected,
            delete_client=runner.delete_client,
            cleanup_sleeper=_no_sleep,
        )

        prefix = (
            "kubectl",
            "--kubeconfig",
            "/private/acceptance/kubeconfig",
            "--context",
            "rke2-207-homelab",
        )
        job_get = (
            *prefix,
            "get",
            "job",
            name,
            "-n",
            "aileron-identity-system",
            "--ignore-not-found",
            "--output=json",
        )
        controller_pods = (
            *prefix,
            "get",
            "pods",
            "-n",
            "aileron-identity-system",
            f"--selector=batch.kubernetes.io/controller-uid={uid}",
            "--output=json",
        )
        name_pods = (
            *prefix,
            "get",
            "pods",
            "-n",
            "aileron-identity-system",
            f"--selector=batch.kubernetes.io/job-name={name}",
            "--output=json",
        )
        self.assertEqual(
            runner.commands,
            [
                job_get,
                job_get,
                job_get,
                controller_pods,
                name_pods,
                job_get,
            ],
        )
        self.assertEqual(
            runner.delete_client.calls,
            [
                {
                    "api_version": "batch/v1",
                    "resource": "jobs",
                    "namespace": "aileron-identity-system",
                    "name": name,
                    "uid": uid,
                    "resource_version": f"{uid}-rv",
                }
            ],
        )
        self.assertFalse(
            any(
                "--preconditions" in part
                for command in runner.commands
                for part in command
            )
        )

    def test_job_cleanup_waits_for_delayed_foreground_deletion_closure(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        runner = DelayedForegroundDeletionRunner(
            TransactionRecordingRunner(
                outputs={},
                live_jobs={name: actual},
                job_templates={},
            ),
            closure_after_rounds=2,
        )
        sleeps: list[float] = []

        _delete_job_and_wait_for_pods(
            config,
            runner,
            expected,
            delete_client=runner.delete_client,
            cleanup_sleeper=sleeps.append,
        )

        self.assertEqual(len(runner.delete_client.calls), 1)
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(runner.closure_round, 3)
        self.assertEqual(
            sum(
                "get" in command
                and "job" in command
                and "aileron-identity-backup" in command
                for command in runner.commands
            ),
            8,
        )
        self.assertEqual(
            sum(
                "get" in command
                and "pods" in command
                and any(
                    "batch.kubernetes.io/controller-uid=identity-job-uid" in part
                    for part in command
                )
                for command in runner.commands
            ),
            3,
        )
        self.assertEqual(
            sum(
                "get" in command
                and "pods" in command
                and any(
                    "batch.kubernetes.io/job-name=aileron-identity-backup" in part
                    for part in command
                )
                for command in runner.commands
            ),
            3,
        )

    def test_job_cleanup_times_out_when_foreground_deletion_never_closes(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        runner = DelayedForegroundDeletionRunner(
            TransactionRecordingRunner(
                outputs={},
                live_jobs={name: actual},
                job_templates={},
            ),
            closure_after_rounds=None,
        )
        sleeps: list[float] = []

        with self.assertRaisesRegex(RuntimeError, "120 seconds"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=runner.delete_client,
                cleanup_sleeper=sleeps.append,
            )

        self.assertEqual(len(runner.delete_client.calls), 1)
        self.assertEqual(len(sleeps), 60)
        self.assertEqual(runner.closure_round, 61)

    def test_job_cleanup_rejects_missing_resource_version_before_delete(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        del actual["metadata"]["resourceVersion"]
        name = expected["metadata"]["name"]
        runner = RecordingRunner(outputs={(" get job ", name): json.dumps(actual)})

        with self.assertRaisesRegex(RuntimeError, "resourceVersion"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=mock.Mock(),
                cleanup_sleeper=_no_sleep,
            )

        self.assertFalse(any("delete" in command for command in runner.commands))

    def test_v131_job_template_accepts_pod_only_defaults_on_execution_pod(
        self,
    ) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        self.assertEqual(runner.operations.count("backup"), 2)
        self.assertEqual(runner.operations.count("restore"), 1)

    def test_job_cleanup_accepts_absent_fixed_job_only_when_name_pods_are_zero(
        self,
    ) -> None:
        config = self.config()
        expected = _expected_job("restore")
        name = expected["metadata"]["name"]
        runner = RecordingRunner(
            outputs={
                (" get job ", name): "",
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/job-name={name}",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
            }
        )

        _delete_job_and_wait_for_pods(
            config,
            runner,
            expected,
            delete_client=mock.Mock(),
            cleanup_sleeper=_no_sleep,
        )

        self.assertEqual(len(runner.commands), 3)
        self.assertIn("get", runner.commands[0])
        self.assertNotIn("delete", runner.commands[0])
        self.assertIn(
            f"--selector=batch.kubernetes.io/job-name={name}",
            runner.commands[1],
        )
        self.assertIn("job", runner.commands[2])

    def test_job_cleanup_rejects_orphan_name_pod_when_fixed_job_is_absent(
        self,
    ) -> None:
        config = self.config()
        expected = _expected_job("restore")
        name = expected["metadata"]["name"]
        runner = RecordingRunner(
            outputs={
                (" get job ", name): "",
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/job-name={name}",
                ): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [{"metadata": {"name": "orphan"}}],
                    }
                ),
            }
        )

        with self.assertRaisesRegex(RuntimeError, "Pod inventory"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=mock.Mock(),
                cleanup_sleeper=_no_sleep,
            )

        self.assertFalse(any("delete" in command for command in runner.commands))

    def test_job_cleanup_times_out_on_old_name_orphan_after_uid_pods_are_zero(
        self,
    ) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        uid = actual["metadata"]["uid"]
        runner = TransactionRecordingRunner(
            outputs={
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/controller-uid={uid}",
                ): json.dumps({"apiVersion": "v1", "kind": "List", "items": []}),
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/job-name={name}",
                ): json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [{"metadata": {"name": "old-orphan"}}],
                    }
                ),
            },
            live_jobs={name: actual},
            job_templates={},
        )

        with self.assertRaisesRegex(RuntimeError, "120 seconds"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=runner.delete_client,
                cleanup_sleeper=_no_sleep,
            )

        self.assertEqual(len(runner.delete_client.calls), 1)

    def test_job_cleanup_rejects_unknown_fixed_name_job_without_delete(self) -> None:
        config = self.config()
        attacks = (
            "labels",
            "annotations",
            "owner",
            "sidecar",
            "hostPath",
            "serviceAccountName",
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                expected, actual = _server_job("backup")
                actual = _add_transaction(actual)
                name = expected["metadata"]["name"]
                if attack == "labels":
                    actual["metadata"]["labels"]["unknown"] = "true"
                elif attack == "annotations":
                    actual["metadata"]["annotations"]["unknown"] = "true"
                elif attack == "owner":
                    actual["metadata"]["ownerReferences"] = [{"kind": "Unknown"}]
                elif attack == "sidecar":
                    actual["spec"]["template"]["spec"]["containers"].append(
                        {
                            "name": "sidecar",
                            "image": "busybox:latest",
                            "securityContext": {"privileged": True},
                        }
                    )
                elif attack == "hostPath":
                    actual["spec"]["template"]["spec"]["volumes"] = [
                        {"name": "host", "hostPath": {"path": "/"}}
                    ]
                else:
                    actual["spec"]["template"]["spec"][
                        "serviceAccountName"
                    ] = "privileged"
                runner = RecordingRunner(
                    outputs={(" get job ", name): json.dumps(actual)}
                )

                with self.assertRaisesRegex(RuntimeError, "identity"):
                    _delete_job_and_wait_for_pods(
                        config,
                        runner,
                        expected,
                        delete_client=mock.Mock(),
                        cleanup_sleeper=_no_sleep,
                    )

                self.assertFalse(
                    any("delete" in command for command in runner.commands)
                )

    def test_job_cleanup_rejects_noncanonical_empty_pod_inventory(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        uid = actual["metadata"]["uid"]
        runner = TransactionRecordingRunner(
            outputs={
                (
                    "kubectl",
                    "get",
                    "pods",
                    f"batch.kubernetes.io/controller-uid={uid}",
                ): json.dumps({"apiVersion": "v1", "kind": "PodList", "items": []}),
            },
            live_jobs={name: actual},
            job_templates={},
        )

        with self.assertRaisesRegex(RuntimeError, "Pod inventory"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=runner.delete_client,
                cleanup_sleeper=_no_sleep,
            )

    def test_job_cleanup_uid_precondition_fails_closed_on_replacement(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        uid = actual["metadata"]["uid"]
        runner = TransactionScenarioRunner(
            TransactionRecordingRunner(
                outputs={},
                live_jobs={name: actual},
                job_templates={},
            ),
            scenario="delete-replacement",
        )

        with self.assertRaisesRegex(RuntimeError, "cleanup identity"):
            _delete_job_and_wait_for_pods(
                config,
                runner,
                expected,
                delete_client=runner.delete_client,
                cleanup_sleeper=_no_sleep,
            )

        self.assertEqual(len(runner.delete_client.calls), 1)
        self.assertEqual(runner.delete_client.calls[0]["uid"], uid)
        self.assertEqual(
            runner.delete_client.calls[0]["resource_version"],
            f"{uid}-rv",
        )
        self.assertFalse(any("pods" in command for command in runner.commands))

    def test_job_cleanup_rejects_missing_or_malformed_prior_transaction(self) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        name = expected["metadata"]["name"]
        attacks = (None, "0" * 63)

        for transaction_token in attacks:
            with self.subTest(transaction_token=transaction_token):
                candidate = copy.deepcopy(actual)
                if transaction_token is not None:
                    candidate["metadata"]["annotations"][
                        IDENTITY_JOB_TRANSACTION_ANNOTATION
                    ] = transaction_token
                runner = RecordingRunner(
                    outputs={(" get job ", name): json.dumps(candidate)}
                )

                with self.assertRaisesRegex(RuntimeError, "transaction identity"):
                    _delete_job_and_wait_for_pods(
                        config,
                        runner,
                        expected,
                        delete_client=mock.Mock(),
                        cleanup_sleeper=_no_sleep,
                    )

                self.assertFalse(
                    any("delete" in command for command in runner.commands)
                )

    def test_run_job_reconciles_ambiguous_create_by_exact_transaction(self) -> None:
        runner = self.transaction_runner("ambiguous-create")
        self.run_backup_job(runner)

        create_index = next(
            index
            for index, command in enumerate(runner.commands)
            if "create" in command and "--dry-run=client" not in command
        )
        transaction_manifest = json.loads(runner.stdins[create_index])
        transaction_token = transaction_manifest["metadata"]["annotations"][
            IDENTITY_JOB_TRANSACTION_ANNOTATION
        ]
        self.assertRegex(transaction_token, r"^[0-9a-f]{64}$")
        self.assertIn("--output=json", runner.commands[create_index])
        self.assertEqual(runner.operations.count("backup"), 1)
        self.assert_backup_job_deleted_once(runner)
        self.assertTrue(
            any(
                "get" in command
                and "job" in command
                and "aileron-identity-backup" in command
                and "--ignore-not-found" not in command
                for command in runner.commands[create_index + 1 :]
            )
        )

    def test_run_job_retries_completed_execution_readback_until_pod_is_visible(
        self,
    ) -> None:
        delegate = self.runner()
        delegate.live_jobs["aileron-identity-backup"] = None

        class DelayedCompletedPodRunner(TransactionRecordingRunner):
            def __init__(self) -> None:
                super().__init__(
                    outputs=delegate.outputs,
                    live_jobs=delegate.live_jobs,
                    job_templates=delegate.job_templates,
                )
                self.completed_pod_reads = 0

            def run(self, args, *, operation=None, stdin=None):
                output = super().run(args, operation=operation, stdin=stdin)
                command = tuple(args)
                if (
                    "get" in command
                    and "pods" in command
                    and "--sort-by=.metadata.name" in command
                    and any(
                        "batch.kubernetes.io/controller-uid=" in part
                        for part in command
                    )
                ):
                    self.completed_pod_reads += 1
                    if self.completed_pod_reads == 1:
                        return json.dumps(
                            {"apiVersion": "v1", "kind": "List", "items": []}
                        )
                return output

        runner = DelayedCompletedPodRunner()

        self.run_backup_job(runner)

        self.assertEqual(runner.completed_pod_reads, 2)
        self.assert_backup_job_deleted_once(runner)

    def test_run_job_finally_recovers_after_first_reconciliation_failure(self) -> None:
        runner = self.transaction_runner("reconciliation-failure")

        with self.assertRaisesRegex(
            RuntimeError,
            "create and exact transaction reconciliation failed",
        ) as raised:
            self.run_backup_job(runner)

        self.assertNotIsInstance(raised.exception, IdentitySmokeCleanupError)
        self.assertEqual(runner.exact_reconciliation_failures, 1)
        self.assertEqual(runner.cleanup_identity_reads, 4)
        self.assert_backup_job_deleted_once(runner)
        self.assertFalse(any("wait" in command for command in runner.commands))

    def test_run_job_preserves_primary_when_final_recovery_retries_are_exhausted(
        self,
    ) -> None:
        runner = self.transaction_runner("cleanup-exhausted")

        with self.assertRaises(IdentitySmokeCleanupError) as raised:
            self.run_backup_job(runner)

        self.assertEqual(len(raised.exception.failures), 2)
        self.assertIn(
            "create and exact transaction reconciliation failed",
            str(raised.exception.failures[0]),
        )
        self.assertIn(
            "transaction cleanup identity remained unavailable after 3 attempts",
            str(raised.exception.failures[1]),
        )
        self.assertEqual(
            runner.cleanup_identity_reads,
            IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS,
        )
        self.assertEqual(runner.exact_reconciliation_failures, 1)
        self.assertIsNotNone(runner.live_jobs["aileron-identity-backup"])
        self.assertFalse(
            any("delete" in command and "job" in command for command in runner.commands)
        )

    def test_run_job_cleans_admission_drift_after_transient_identity_reads(
        self,
    ) -> None:
        cases = (
            ("admission-drift", 3),
            ("admission-drift-transport", 4),
            ("admission-drift-invalid-json", 4),
        )
        for scenario, expected_reads in cases:
            with self.subTest(scenario=scenario):
                runner = self.transaction_runner(scenario)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "existing Identity data Job identity",
                ) as raised:
                    self.run_backup_job(runner)

                self.assertNotIsInstance(
                    raised.exception,
                    IdentitySmokeCleanupError,
                )
                self.assertEqual(runner.cleanup_identity_reads, expected_reads)
                self.assertEqual(runner.delete_attempts, 1)
                self.assert_backup_job_deleted_once(runner)
                self.assertFalse(any("wait" in command for command in runner.commands))

    def test_run_job_does_not_retry_foreign_or_replacement_cleanup_identity(
        self,
    ) -> None:
        for scenario in ("foreign-token", "replacement-uid"):
            with self.subTest(scenario=scenario):
                runner = self.transaction_runner(scenario)

                with self.assertRaises(IdentitySmokeCleanupError) as raised:
                    self.run_backup_job(runner)

                self.assertEqual(len(raised.exception.failures), 2)
                self.assertEqual(
                    str(raised.exception.failures[0]),
                    "execution wait failed",
                )
                self.assertEqual(
                    str(raised.exception.failures[1]),
                    "Identity data Job cleanup identity is invalid",
                )
                self.assertEqual(runner.cleanup_identity_reads, 1)
                self.assertEqual(runner.delete_attempts, 0)
                self.assertIsNotNone(runner.live_jobs["aileron-identity-backup"])
                self.assertFalse(
                    any(
                        "delete" in command and "job" in command
                        for command in runner.commands
                    )
                )

    def test_run_job_reconciles_ambiguous_delete(self) -> None:
        cases = (
            ("delete-accepted-error", 1, 4),
            ("delete-not-accepted", 2, 4),
        )
        for scenario, delete_attempts, identity_reads in cases:
            with self.subTest(scenario=scenario):
                runner = self.transaction_runner(scenario)
                self.run_backup_job(runner)

                self.assertEqual(runner.delete_attempts, delete_attempts)
                self.assertEqual(runner.cleanup_identity_reads, identity_reads)
                self.assertIsNone(runner.live_jobs["aileron-identity-backup"])

    def test_job_cleanup_waits_after_last_ambiguous_delete_was_accepted(
        self,
    ) -> None:
        config = self.config()
        expected, actual = _server_job("backup")
        actual = _add_transaction(actual)
        name = expected["metadata"]["name"]
        runner = LastAttemptAmbiguousDeletionRunner(
            TransactionRecordingRunner(
                outputs={},
                live_jobs={name: actual},
                job_templates={},
            )
        )
        sleeps: list[float] = []

        _delete_job_and_wait_for_pods(
            config,
            runner,
            expected,
            delete_client=runner.delete_client,
            cleanup_sleeper=sleeps.append,
        )

        self.assertEqual(
            len(runner.delete_client.calls),
            IDENTITY_JOB_CLEANUP_RECONCILE_ATTEMPTS,
        )
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(runner.closure_round, 3)

    def test_run_job_rejects_replacement_after_ambiguous_delete(self) -> None:
        runner = self.transaction_runner("delete-replacement")

        with self.assertRaises(IdentitySmokeCleanupError) as raised:
            self.run_backup_job(runner)

        self.assertEqual(len(raised.exception.failures), 1)
        self.assertEqual(
            str(raised.exception.failures[0]),
            "Identity data Job cleanup identity is invalid",
        )
        self.assertEqual(runner.delete_attempts, 1)
        self.assertEqual(runner.cleanup_identity_reads, 2)
        self.assertEqual(
            runner.live_jobs["aileron-identity-backup"]["metadata"]["uid"],
            "replacement-backup-job-uid",
        )

    def test_rejects_symlinked_canonical_chart_before_cluster_reads(self) -> None:
        chart = self.repository_root / "helm/aileron-identity"
        replacement = self.repository_root / "replacement-chart"
        chart.rename(replacement)
        chart.symlink_to(replacement, target_is_directory=True)
        runner = self.runner()

        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            run_smoke(self.config(), runner)

        self.assertFalse(
            any(command[0] in {"helm", "kubectl"} for command in runner.commands)
        )

    def test_rejects_untracked_chart_content_before_cluster_reads(self) -> None:
        runner = self.runner()
        runner.outputs[("git", "ls-files", "--others")] = (
            "helm/aileron-identity/templates/untracked.yaml\n"
        )

        with self.assertRaisesRegex(RuntimeError, "untracked"):
            run_smoke(self.config(), runner)

        self.assertFalse(
            any(command[0] in {"helm", "kubectl"} for command in runner.commands)
        )

    def test_rejects_same_version_modified_chart_tree_before_cluster_reads(
        self,
    ) -> None:
        runner = self.runner()
        runner.outputs[("git", "ls-files", "--stage")] = (
            CHART_TREE.replace("3" * 40, "9" * 40)
            .replace(" blob ", " ")
            .replace("\thelm", " 0\thelm")
        )

        with self.assertRaisesRegex(RuntimeError, "tracked content"):
            run_smoke(self.config(), runner)

        self.assertFalse(
            any(command[0] in {"helm", "kubectl"} for command in runner.commands)
        )

    def test_rejects_installed_manifest_drift_before_mutation(self) -> None:
        runner = self.runner()
        runner.outputs[("helm", "get", "manifest")] = RELEASE_MANIFEST.replace(
            "name: aileron-identity", "name: drifted"
        )

        with self.assertRaisesRegex(RuntimeError, "rendered manifest"):
            run_smoke(self.config(), runner)

        self.assertNotIn("backup", runner.operations)
        self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_run_smoke_returns_exact_job_closure_report(self) -> None:
        runner = self.runner()

        report = run_smoke(self.config(), runner)

        self.assertEqual(
            report,
            {
                "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
                "backupJobUids": [
                    "identity-backup-job-uid",
                    "identity-backup-job-uid-2",
                ],
                "restoreJobUid": "identity-restore-job-uid",
                "restoreMarker": "identity-smoke-marker",
                "jobClosureVerified": True,
            },
        )
        self.assertEqual(
            runner.delete_client_loader.calls,
            [
                {
                    "kubeconfig": Path("/private/acceptance/kubeconfig"),
                    "context": "rke2-207-homelab",
                    "credential_directory": Path("/private/acceptance"),
                    "private_root": Path("/private/acceptance"),
                }
            ],
        )

    def test_runs_verified_backup_restore_with_every_cluster_command_pinned(
        self,
    ) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        self.assertEqual(runner.operations.count("backup"), 2)
        self.assertEqual(runner.operations.count("restore"), 1)
        self.assertIn("verify-marker", runner.operations)
        self.assertEqual(runner.operations[-1], "rollout-keycloak-ready")
        self.assertEqual(
            [request["uid"] for request in runner.delete_client.calls],
            [
                "identity-backup-job-uid",
                "identity-backup-job-uid",
                "identity-restore-job-uid",
                "identity-restore-job-uid",
                "identity-backup-job-uid-2",
            ],
        )
        for request in runner.delete_client.calls:
            self.assertEqual(request["api_version"], "batch/v1")
            self.assertEqual(request["resource"], "jobs")
            self.assertEqual(request["namespace"], "aileron-identity-system")
            self.assertEqual(
                request["resource_version"],
                f"{request['uid']}-rv",
            )
        self.assertFalse(
            any("delete" in command and "job" in command for command in runner.commands)
        )
        restored_replicas = (
            "kubectl",
            "--kubeconfig",
            "/private/acceptance/kubeconfig",
            "--context",
            "rke2-207-homelab",
            "scale",
            "deployment/aileron-identity-keycloak",
            "-n",
            "aileron-identity-system",
            "--replicas=1",
        )
        rollout_ready = (
            "kubectl",
            "--kubeconfig",
            "/private/acceptance/kubeconfig",
            "--context",
            "rke2-207-homelab",
            "rollout",
            "status",
            "deployment/aileron-identity-keycloak",
            "-n",
            "aileron-identity-system",
            "--timeout=10m",
        )
        self.assertLess(
            runner.commands.index(restored_replicas),
            runner.commands.index(rollout_ready),
        )
        cluster_commands = [
            command
            for command in runner.commands
            if command and command[0] in {"helm", "kubectl"}
        ]
        self.assertTrue(cluster_commands)
        for command in cluster_commands:
            flag = "--kube-context" if command[0] == "helm" else "--context"
            self.assertIn(flag, command)
            self.assertEqual(command[command.index(flag) + 1], "rke2-207-homelab")
            self.assertIn("--kubeconfig", command)
            self.assertEqual(
                command[command.index("--kubeconfig") + 1],
                "/private/acceptance/kubeconfig",
            )

    def test_execution_pod_is_verified_before_the_first_destructive_drop(self) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        completed_pod_query = next(
            index
            for index, command in enumerate(runner.commands)
            if "--sort-by=.metadata.name" in command
            and "--selector=batch.kubernetes.io/controller-uid="
            "identity-backup-job-uid" in command
        )
        first_drop = next(
            index
            for index, command in enumerate(runner.commands)
            if any(
                "DROP TABLE aileron_backup_restore_smoke" in part for part in command
            )
        )
        self.assertLess(completed_pod_query, first_drop)

    def test_database_exec_is_pinned_to_validated_postgres_pod_and_container(
        self,
    ) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        exec_indexes = [
            index for index, command in enumerate(runner.commands) if "exec" in command
        ]
        self.assertEqual(len(exec_indexes), 4)
        expected_readback = (
            "kubectl",
            "--kubeconfig",
            "/private/acceptance/kubeconfig",
            "--context",
            "rke2-207-homelab",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "-n",
            "aileron-identity-system",
            "--output=json",
        )
        for index in exec_indexes:
            command = runner.commands[index]
            self.assertEqual(runner.commands[index - 1], expected_readback)
            self.assertIn(f"pod/{POSTGRES_POD_NAME}", command)
            self.assertNotIn("deployment/aileron-identity-postgres", command)
            self.assertIn("--container=postgres", command)

    def test_live_deployment_accepts_helm_ownership_and_omitted_zero_defaults(
        self,
    ) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_live_deployment_accepts_omitted_template_creation_timestamp(
        self,
    ) -> None:
        output_key = (
            "kubectl",
            "get",
            "deployment",
            "aileron-identity-postgres",
            "--output=json",
        )
        runner = self.runner()
        deployment = json.loads(runner.outputs[output_key])
        deployment["spec"]["template"]["metadata"].pop("creationTimestamp")
        runner.outputs[output_key] = json.dumps(deployment)
        replica_set_key = (
            "kubectl",
            "get",
            "replicasets.apps",
            "--output=json",
        )
        replica_set_inventory = json.loads(runner.outputs[replica_set_key])
        replica_set_inventory["items"][0]["spec"]["template"]["metadata"].pop(
            "creationTimestamp"
        )
        runner.outputs[replica_set_key] = json.dumps(replica_set_inventory)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_rejects_non_null_template_creation_timestamp_before_database_mutation(
        self,
    ) -> None:
        output_key = (
            "kubectl",
            "get",
            "deployment",
            "aileron-identity-postgres",
            "--output=json",
        )
        runner = self.runner()
        deployment = json.loads(runner.outputs[output_key])
        deployment["spec"]["template"]["metadata"][
            "creationTimestamp"
        ] = "2026-08-12T00:00:00Z"
        runner.outputs[output_key] = json.dumps(deployment)

        with self.assertRaisesRegex(RuntimeError, "Deployment"):
            run_smoke(self.config(), runner)

        self.assertNotIn("create-marker", runner.operations)
        self.assertNotIn("backup", runner.operations)

    def test_rejects_postgres_deployment_drift_before_database_mutation(
        self,
    ) -> None:
        output_key = (
            "kubectl",
            "get",
            "deployment",
            "aileron-identity-postgres",
            "--output=json",
        )
        for attack in (
            "owner",
            "revision",
            "selector",
            "template",
            "status",
            "image",
        ):
            with self.subTest(attack=attack):
                runner = self.runner()
                deployment = json.loads(runner.outputs[output_key])
                if attack == "owner":
                    deployment["metadata"]["ownerReferences"] = [
                        {"kind": "Unknown", "uid": "unknown"}
                    ]
                elif attack == "revision":
                    deployment["metadata"]["annotations"][
                        "deployment.kubernetes.io/revision"
                    ] = "invalid"
                elif attack == "selector":
                    deployment["spec"]["selector"]["matchLabels"] = {
                        "app.kubernetes.io/name": "foreign"
                    }
                elif attack == "template":
                    deployment["spec"]["template"]["spec"]["containers"].append(
                        {
                            "name": "sidecar",
                            "image": "registry.example.test/sidecar@sha256:" + "f" * 64,
                        }
                    )
                elif attack == "status":
                    deployment["status"]["readyReplicas"] = 0
                else:
                    deployment["spec"]["template"]["spec"]["containers"][0]["image"] = (
                        "registry.example.test/postgres@sha256:" + "f" * 64
                    )
                runner.outputs[output_key] = json.dumps(deployment)

                with self.assertRaisesRegex(RuntimeError, "Deployment"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("create-marker", runner.operations)
                self.assertNotIn("backup", runner.operations)

    def test_rejects_postgres_replicaset_drift_or_active_ambiguity(self) -> None:
        output_key = (
            "kubectl",
            "get",
            "replicasets.apps",
            "--output=json",
        )
        for attack in (
            "owner",
            "multi-owner-hidden",
            "revision",
            "template",
            "status",
            "extra-active",
        ):
            with self.subTest(attack=attack):
                runner = self.runner()
                inventory = json.loads(runner.outputs[output_key])
                replica_set = inventory["items"][0]
                if attack == "owner":
                    replica_set["metadata"]["ownerReferences"][0]["uid"] = "unknown"
                elif attack == "multi-owner-hidden":
                    replica_set["metadata"]["labels"] = {}
                    replica_set["metadata"]["ownerReferences"].append(
                        {
                            "apiVersion": "v1",
                            "kind": "ConfigMap",
                            "name": "foreign",
                            "uid": "foreign-owner-uid",
                        }
                    )
                elif attack == "revision":
                    replica_set["metadata"]["annotations"][
                        "deployment.kubernetes.io/revision"
                    ] = "4"
                elif attack == "template":
                    replica_set["spec"]["template"]["spec"]["containers"][0][
                        "image"
                    ] = ("registry.example.test/postgres@sha256:" + "f" * 64)
                elif attack == "status":
                    replica_set["status"]["availableReplicas"] = 0
                else:
                    duplicate = copy.deepcopy(replica_set)
                    duplicate["metadata"]["name"] += "-duplicate"
                    duplicate["metadata"]["uid"] = "duplicate-active-rs-uid"
                    inventory["items"].append(duplicate)
                runner.outputs[output_key] = json.dumps(inventory)

                with self.assertRaisesRegex(RuntimeError, "ReplicaSet"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("create-marker", runner.operations)
                self.assertNotIn("backup", runner.operations)

    def test_accepts_zero_scaled_postgres_replicaset_history(self) -> None:
        runner = self.runner()
        output_key = (
            "kubectl",
            "get",
            "replicasets.apps",
            "--output=json",
        )
        inventory = json.loads(runner.outputs[output_key])
        historical = copy.deepcopy(inventory["items"][0])
        historical["metadata"]["name"] = "aileron-identity-postgres-4b5c6d7f8g"
        historical["metadata"]["uid"] = "historical-postgres-rs-uid"
        historical["metadata"]["labels"]["pod-template-hash"] = "4b5c6d7f8g"
        historical["spec"]["replicas"] = 0
        historical["spec"]["selector"]["matchLabels"][
            "pod-template-hash"
        ] = "4b5c6d7f8g"
        historical["spec"]["template"]["metadata"]["labels"][
            "pod-template-hash"
        ] = "4b5c6d7f8g"
        historical["status"] = {"observedGeneration": 1, "replicas": 0}
        inventory["items"].append(historical)
        runner.outputs[output_key] = json.dumps(inventory)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_rejects_hidden_or_untrusted_postgres_execution_pods(self) -> None:
        for attack in (
            "hidden-owner",
            "multi-owner-hidden",
            "deployment-owner",
            "foreign-owner",
            "sidecar",
            "runtime-image",
            "runtime-repository",
            "restart",
            "deleting",
        ):
            with self.subTest(attack=attack):
                runner = self.runner()
                inventory = json.loads(runner.outputs[("postgres-pod-closure",)])
                pod = inventory["items"][0]
                if attack in {
                    "hidden-owner",
                    "multi-owner-hidden",
                    "deployment-owner",
                }:
                    duplicate = copy.deepcopy(pod)
                    duplicate["metadata"]["name"] += "-duplicate"
                    duplicate["metadata"]["uid"] += "-duplicate"
                    duplicate["metadata"]["labels"] = {}
                    if attack == "deployment-owner":
                        duplicate["metadata"]["ownerReferences"][0].update(
                            {
                                "kind": "Deployment",
                                "name": "aileron-identity-postgres",
                                "uid": POSTGRES_DEPLOYMENT_UID,
                            }
                        )
                    elif attack == "multi-owner-hidden":
                        duplicate["metadata"]["ownerReferences"].append(
                            {
                                "apiVersion": "v1",
                                "kind": "ConfigMap",
                                "name": "foreign",
                                "uid": "foreign-owner-uid",
                            }
                        )
                    inventory["items"].append(duplicate)
                elif attack == "foreign-owner":
                    pod["metadata"]["ownerReferences"][0]["uid"] = "unknown"
                elif attack == "sidecar":
                    pod["spec"]["containers"].append(
                        {
                            "name": "sidecar",
                            "image": "registry.example.test/sidecar@sha256:" + "f" * 64,
                        }
                    )
                elif attack == "runtime-image":
                    pod["status"]["containerStatuses"][0]["imageID"] = (
                        "registry.example.test/postgres@sha256:" + "f" * 64
                    )
                elif attack == "runtime-repository":
                    pod["status"]["containerStatuses"][0][
                        "imageID"
                    ] = f"attacker.invalid/postgres@{RUNTIME_POSTGRES}"
                elif attack == "restart":
                    pod["status"]["containerStatuses"][0]["restartCount"] = 1
                else:
                    pod["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:01Z"
                runner.outputs[("postgres-pod-closure",)] = json.dumps(inventory)

                with self.assertRaisesRegex(RuntimeError, "Pod"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("create-marker", runner.operations)
                self.assertNotIn("backup", runner.operations)

    def test_database_target_readback_rejects_identity_or_runtime_drift(
        self,
    ) -> None:
        output_key = (
            "kubectl",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "--output=json",
        )
        for attack in (
            "uid",
            "deleting",
            "image",
            "repository",
            "ready",
            "sidecar",
        ):
            with self.subTest(attack=attack):
                runner = self.runner()
                pod = json.loads(runner.outputs[output_key])
                if attack == "uid":
                    pod["metadata"]["uid"] = "replacement-postgres-pod-uid"
                elif attack == "deleting":
                    pod["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:01Z"
                elif attack == "image":
                    pod["status"]["containerStatuses"][0]["imageID"] = (
                        "registry.example.test/postgres@sha256:" + "f" * 64
                    )
                elif attack == "repository":
                    pod["status"]["containerStatuses"][0][
                        "imageID"
                    ] = f"attacker.invalid/postgres@{RUNTIME_POSTGRES}"
                elif attack == "ready":
                    pod["status"]["containerStatuses"][0]["ready"] = False
                else:
                    pod["spec"]["containers"].append(
                        {
                            "name": "sidecar",
                            "image": "registry.example.test/sidecar@sha256:" + "f" * 64,
                        }
                    )
                runner.outputs[output_key] = json.dumps(pod)

                with self.assertRaisesRegex(RuntimeError, "changed identity"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("create-marker", runner.operations)
                self.assertNotIn("backup", runner.operations)
                self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_each_database_exec_rechecks_the_same_pod_before_exec(self) -> None:
        delegate = self.runner()
        output_key = (
            "kubectl",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "--output=json",
        )

        class ReplaceBeforeSecondExec(TransactionRecordingRunner):
            def __init__(self) -> None:
                super().__init__(
                    outputs=delegate.outputs,
                    live_jobs=delegate.live_jobs,
                    job_templates=delegate.job_templates,
                )
                self.commands = delegate.commands
                self.operations = delegate.operations
                self.stdins = delegate.stdins
                self.target_reads = 0

            def run(self, args, *, operation=None, stdin=None):
                command = tuple(args)
                if all(part in command for part in output_key):
                    if operation:
                        self.operations.append(operation)
                    self.commands.append(command)
                    self.stdins.append(stdin)
                    self.target_reads += 1
                    pod = json.loads(delegate.outputs[output_key])
                    if self.target_reads == 2:
                        pod["metadata"]["uid"] = "replacement-postgres-pod-uid"
                    return json.dumps(pod)
                return super().run(args, operation=operation, stdin=stdin)

        runner = ReplaceBeforeSecondExec()

        with self.assertRaisesRegex(RuntimeError, "changed identity"):
            run_smoke(self.config(), runner)

        self.assertEqual(runner.operations.count("create-marker"), 1)
        self.assertEqual(runner.operations.count("backup"), 1)
        self.assertNotIn("drop-marker", runner.operations)
        self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_postgres_execution_pod_accepts_signed_index_digest(self) -> None:
        runner = self.runner()
        closure = json.loads(runner.outputs[("postgres-pod-closure",)])
        closure["items"][0]["status"]["containerStatuses"][0][
            "imageID"
        ] = f"registry.example.test/postgres@{INDEX_POSTGRES}"
        runner.outputs[("postgres-pod-closure",)] = json.dumps(closure)
        output_key = (
            "kubectl",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "--output=json",
        )
        readback = json.loads(runner.outputs[output_key])
        readback["status"]["containerStatuses"][0][
            "imageID"
        ] = f"registry.example.test/postgres@{INDEX_POSTGRES}"
        runner.outputs[output_key] = json.dumps(readback)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_postgres_execution_pod_accepts_digest_only_status_image(self) -> None:
        runner = self.runner()
        closure = json.loads(runner.outputs[("postgres-pod-closure",)])
        closure["items"][0]["status"]["containerStatuses"][0]["image"] = INDEX_POSTGRES
        runner.outputs[("postgres-pod-closure",)] = json.dumps(closure)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_database_target_readback_accepts_digest_only_status_image(self) -> None:
        runner = self.runner()
        output_key = (
            "kubectl",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "--output=json",
        )
        readback = json.loads(runner.outputs[output_key])
        readback["status"]["containerStatuses"][0]["image"] = INDEX_POSTGRES
        runner.outputs[output_key] = json.dumps(readback)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_rejects_malformed_or_repository_qualified_status_image(self) -> None:
        for status_image in (
            "sha256:" + "f" * 63,
            "sha256:" + "F" * 64,
            f"attacker.invalid/postgres@{INDEX_POSTGRES}",
        ):
            with self.subTest(status_image=status_image):
                runner = self.runner()
                closure = json.loads(runner.outputs[("postgres-pod-closure",)])
                closure["items"][0]["status"]["containerStatuses"][0][
                    "image"
                ] = status_image
                runner.outputs[("postgres-pod-closure",)] = json.dumps(closure)

                with self.assertRaisesRegex(RuntimeError, "Pod"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("create-marker", runner.operations)
                self.assertNotIn("backup", runner.operations)

    def test_postgres_pod_accepts_v131_limit_to_request_default(self) -> None:
        runner = self.runner()
        limits = {"cpu": "500m", "memory": "512Mi"}
        normalized_key = ("normalize-postgres-deployment",)
        expected = json.loads(runner.outputs[normalized_key])
        expected["spec"]["template"]["spec"]["containers"][0]["resources"] = {
            "limits": copy.deepcopy(limits)
        }
        runner.outputs[normalized_key] = json.dumps(expected)

        deployment_key = (
            "kubectl",
            "get",
            "deployment",
            "aileron-identity-postgres",
            "--output=json",
        )
        deployment = json.loads(runner.outputs[deployment_key])
        deployment["spec"]["template"]["spec"]["containers"][0]["resources"] = {
            "limits": copy.deepcopy(limits)
        }
        runner.outputs[deployment_key] = json.dumps(deployment)

        replica_set_key = (
            "kubectl",
            "get",
            "replicasets.apps",
            "--output=json",
        )
        replica_sets = json.loads(runner.outputs[replica_set_key])
        replica_sets["items"][0]["spec"]["template"]["spec"]["containers"][0][
            "resources"
        ] = {"limits": copy.deepcopy(limits)}
        runner.outputs[replica_set_key] = json.dumps(replica_sets)

        closure = json.loads(runner.outputs[("postgres-pod-closure",)])
        closure["items"][0]["spec"]["containers"][0]["resources"] = {
            "limits": copy.deepcopy(limits),
            "requests": copy.deepcopy(limits),
        }
        runner.outputs[("postgres-pod-closure",)] = json.dumps(closure)
        readback_key = (
            "kubectl",
            "get",
            "pod",
            POSTGRES_POD_NAME,
            "--output=json",
        )
        readback = json.loads(runner.outputs[readback_key])
        readback["spec"]["containers"][0]["resources"] = {
            "limits": copy.deepcopy(limits),
            "requests": copy.deepcopy(limits),
        }
        runner.outputs[readback_key] = json.dumps(readback)

        run_smoke(self.config(), runner)

        self.assertIn("create-marker", runner.operations)

    def test_rejects_untrusted_execution_pod_before_followup_mutation(self) -> None:
        for attack in (
            "owner",
            "generate-name",
            "image",
            "repository",
            "root",
            "multiple",
        ):
            with self.subTest(attack=attack):
                runner = self.runner()
                _, backup_job = _server_job("backup", "identity-backup-job-uid")
                pod = _completed_pod("backup", backup_job, RUNTIME_POSTGRES)
                document = {"apiVersion": "v1", "kind": "List", "items": [pod]}
                if attack == "owner":
                    pod["metadata"]["ownerReferences"][0]["uid"] = "unknown"
                elif attack == "generate-name":
                    pod["metadata"]["generateName"] = "foreign-"
                elif attack == "image":
                    pod["status"]["containerStatuses"][0]["imageID"] = (
                        "registry.example.test/postgres@sha256:" + "f" * 64
                    )
                elif attack == "repository":
                    pod["status"]["containerStatuses"][0][
                        "imageID"
                    ] = f"attacker.invalid/postgres@{RUNTIME_POSTGRES}"
                else:
                    if attack == "root":
                        document["kind"] = "PodList"
                    else:
                        document["items"].append(copy.deepcopy(pod))
                runner.outputs[
                    (
                        "kubectl",
                        "get",
                        "pods",
                        "batch.kubernetes.io/controller-uid=identity-backup-job-uid",
                        "--sort-by=.metadata.name",
                    )
                ] = json.dumps(document)

                with self.assertRaisesRegex(RuntimeError, "execution Pod"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("drop-marker", runner.operations)
                self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_rejects_job_uid_change_before_followup_mutation(self) -> None:
        delegate = self.runner()

        class ReplacedAfterWaitRunner(TransactionRecordingRunner):
            def __init__(self) -> None:
                super().__init__(
                    outputs=delegate.outputs,
                    live_jobs=delegate.live_jobs,
                    job_templates=delegate.job_templates,
                )
                self.commands = delegate.commands
                self.operations = delegate.operations
                self.stdins = delegate.stdins

            def run(self, args, *, operation=None, stdin=None):
                command = tuple(args)
                if (
                    "get" in command
                    and "job" in command
                    and "aileron-identity-backup" in command
                    and "--ignore-not-found" not in command
                ):
                    if operation:
                        self.operations.append(operation)
                    self.commands.append(command)
                    self.stdins.append(stdin)
                    _, replaced = _server_job("backup", "replacement-backup-job-uid")
                    replaced["metadata"]["annotations"] = copy.deepcopy(
                        self.live_jobs["aileron-identity-backup"]["metadata"][
                            "annotations"
                        ]
                    )
                    self.live_jobs["aileron-identity-backup"] = replaced
                    return json.dumps(replaced)
                return super().run(args, operation=operation, stdin=stdin)

        runner = ReplacedAfterWaitRunner()

        with self.assertRaisesRegex(RuntimeError, "changed identity"):
            run_smoke(self.config(), runner)

        self.assertNotIn("drop-marker", runner.operations)
        self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_completed_job_pod_accepts_signed_index_digest(self) -> None:
        runner = self.runner()
        _, backup_job = _server_job("backup", "identity-backup-job-uid")
        runner.outputs[
            (
                "kubectl",
                "get",
                "pods",
                "batch.kubernetes.io/controller-uid=identity-backup-job-uid",
                "--sort-by=.metadata.name",
            )
        ] = json.dumps(
            {
                "apiVersion": "v1",
                "kind": "List",
                "items": [_completed_pod("backup", backup_job, INDEX_POSTGRES)],
            }
        )

        run_smoke(self.config(), runner)

    def test_completed_job_pod_accepts_digest_only_status_image(self) -> None:
        runner = self.runner()
        _, backup_job = _server_job("backup", "identity-backup-job-uid")
        pod = _completed_pod("backup", backup_job, RUNTIME_POSTGRES)
        pod["status"]["containerStatuses"][0]["image"] = INDEX_POSTGRES
        runner.outputs[
            (
                "kubectl",
                "get",
                "pods",
                "batch.kubernetes.io/controller-uid=identity-backup-job-uid",
                "--sort-by=.metadata.name",
            )
        ] = json.dumps({"apiVersion": "v1", "kind": "List", "items": [pod]})

        run_smoke(self.config(), runner)

    def test_completed_job_pod_accepts_equal_container_timestamps(self) -> None:
        config = self.config()
        _, backup_job = _server_job("backup", "identity-backup-job-uid")
        pod = _completed_pod("backup", backup_job, RUNTIME_POSTGRES)
        terminated = pod["status"]["containerStatuses"][0]["state"]["terminated"]
        terminated["finishedAt"] = terminated["startedAt"]

        _validate_completed_job_pod(
            config=config,
            operation="backup",
            job=backup_job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=config.postgres_image,
            runtime_immutable_image=config.postgres_runtime_image,
        )

    def test_completed_job_pod_rejects_reversed_container_timestamps(self) -> None:
        config = self.config()
        _, backup_job = _server_job("backup", "identity-backup-job-uid")
        pod = _completed_pod("backup", backup_job, RUNTIME_POSTGRES)
        terminated = pod["status"]["containerStatuses"][0]["state"]["terminated"]
        terminated["startedAt"] = "2026-08-10T01:00:02Z"
        terminated["finishedAt"] = "2026-08-10T01:00:01Z"

        with self.assertRaisesRegex(RuntimeError, "Pod provenance is invalid"):
            _validate_completed_job_pod(
                config=config,
                operation="backup",
                job=backup_job,
                pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
                immutable_image=config.postgres_image,
                runtime_immutable_image=config.postgres_runtime_image,
            )

    def test_cleanup_attempts_every_target_and_preserves_all_failures(self) -> None:
        delegate = self.runner()

        class FailingCleanupRunner(TransactionRecordingRunner):
            def __init__(self) -> None:
                super().__init__(
                    outputs=delegate.outputs,
                    live_jobs=delegate.live_jobs,
                    job_templates=delegate.job_templates,
                )
                self.commands = delegate.commands
                self.operations = delegate.operations
                self.stdins = delegate.stdins
                self.delete_counts = {
                    "aileron-identity-backup": 0,
                    "aileron-identity-restore": 0,
                }
                self.reject_deletes = False

            def delete_job(self, **request) -> None:
                job_name = request["name"]
                if self.reject_deletes:
                    self.delete_counts[job_name] += 1
                    raise RuntimeError(f"failed to delete {job_name}")
                super().delete_job(**request)

            def run(self, args, *, operation=None, stdin=None):
                output = super().run(args, operation=operation, stdin=stdin)
                if operation == "scale-keycloak:1":
                    self.live_jobs["aileron-identity-backup"] = _add_transaction(
                        self.job_templates["backup"]
                    )
                    self.live_jobs["aileron-identity-restore"] = _add_transaction(
                        self.job_templates["restore"]
                    )
                    self.reject_deletes = True
                    raise RuntimeError("failed to restore Keycloak replicas")
                return output

        runner = FailingCleanupRunner()

        with self.assertRaises(IdentitySmokeCleanupError) as raised:
            run_smoke(self.config(), runner)

        self.assertEqual(
            [str(error) for error in raised.exception.failures],
            [
                "failed to restore Keycloak replicas",
                (
                    "aileron-identity-backup transaction deletion remained unresolved "
                    "after 3 attempts"
                ),
                (
                    "aileron-identity-restore transaction deletion remained unresolved "
                    "after 3 attempts"
                ),
            ],
        )
        self.assertEqual(
            runner.delete_counts,
            {
                "aileron-identity-backup": 3,
                "aileron-identity-restore": 3,
            },
        )

    def test_cleanup_failure_group_preserves_the_primary_smoke_failure(self) -> None:
        delegate = self.runner()

        class PrimaryAndCleanupFailingRunner(TransactionRecordingRunner):
            def __init__(self) -> None:
                super().__init__(
                    outputs=delegate.outputs,
                    live_jobs=delegate.live_jobs,
                    job_templates=delegate.job_templates,
                )
                self.commands = delegate.commands
                self.operations = delegate.operations
                self.stdins = delegate.stdins
                self.backup_deletes = 0
                self.restore_deletes = 0
                self.reject_backup_deletes = False

            def delete_job(self, **request) -> None:
                job_name = request["name"]
                if self.reject_backup_deletes and job_name == "aileron-identity-backup":
                    self.backup_deletes += 1
                    raise RuntimeError("failed final backup Job cleanup")
                if job_name == "aileron-identity-restore":
                    self.restore_deletes += 1
                super().delete_job(**request)

            def run(self, args, *, operation=None, stdin=None):
                output = super().run(args, operation=operation, stdin=stdin)
                if operation == "verify-marker":
                    self.live_jobs["aileron-identity-backup"] = _add_transaction(
                        self.job_templates["backup"]
                    )
                    self.reject_backup_deletes = True
                    raise RuntimeError("restore verification failed")
                return output

        runner = PrimaryAndCleanupFailingRunner()

        with self.assertRaises(IdentitySmokeCleanupError) as raised:
            run_smoke(self.config(), runner)

        self.assertEqual(
            [str(error) for error in raised.exception.failures],
            [
                "restore verification failed",
                (
                    "aileron-identity-backup transaction deletion remained unresolved "
                    "after 3 attempts"
                ),
            ],
        )
        self.assertEqual(runner.backup_deletes, 3)
        self.assertEqual(runner.restore_deletes, 2)

    def test_rejects_installed_image_outside_signed_pair_before_mutation(self) -> None:
        runner = self.runner()
        runner.outputs[("helm", "get", "values")] = json.dumps(
            {
                "backup": {"enabled": False, "claimName": "identity-backup"},
                "postgres": {"enabled": True},
                "images": {
                    "keycloak": {
                        "repository": "registry.example.test/keycloak",
                        "digest": "sha256:" + "f" * 64,
                    },
                    "postgres": {
                        "repository": "registry.example.test/postgres",
                        "digest": INDEX_POSTGRES,
                    },
                },
            }
        )

        with self.assertRaisesRegex(RuntimeError, "signed release inventory"):
            run_smoke(self.config(), runner)

        self.assertNotIn("backup", runner.operations)
        self.assertNotIn("restore", runner.operations)
        self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_uses_signed_runtime_pair_without_registry_reads(self) -> None:
        runner = self.runner()

        run_smoke(self.config(), runner)

        self.assertFalse(
            any(command and command[0] == "docker" for command in runner.commands)
        )

    def test_rejects_pod_actual_digest_or_repository_drift_before_mutation(
        self,
    ) -> None:
        keycloak_image = f"registry.example.test/keycloak@{INDEX_KEYCLOAK}"
        for attack in ("digest", "repository"):
            with self.subTest(attack=attack):
                runner = self.runner()
                runner.outputs[
                    ("kubectl", "get", "pods", "aileron-identity-keycloak")
                ] = _pod_document(
                    keycloak_image,
                    "sha256:" + "f" * 64 if attack == "digest" else RUNTIME_KEYCLOAK,
                    image_id_repository=(
                        "attacker.invalid/keycloak" if attack == "repository" else None
                    ),
                )

                with self.assertRaisesRegex(RuntimeError, "actual digest"):
                    run_smoke(self.config(), runner)

                self.assertNotIn("backup", runner.operations)
                self.assertNotIn("scale-keycloak:0", runner.operations)

    def test_accepts_pod_index_digest_reported_by_containerd(self) -> None:
        runner = self.runner()
        keycloak_image = f"registry.example.test/keycloak@{INDEX_KEYCLOAK}"
        runner.outputs[("kubectl", "get", "pods", "aileron-identity-keycloak")] = (
            _pod_document(
                keycloak_image,
                INDEX_KEYCLOAK,
                image_id_repository="docker-pullable://registry.example.test/keycloak",
            )
        )

        run_smoke(self.config(), runner)

    def test_rejects_installed_release_revision_drift_before_mutation(self) -> None:
        runner = self.runner()
        runner.outputs[("helm", "list")] = json.dumps(
            [
                {
                    "name": "aileron-identity",
                    "namespace": "aileron-identity-system",
                    "revision": "8",
                    "status": "deployed",
                    "chart": "aileron-identity-0.1.0",
                }
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "release metadata"):
            run_smoke(self.config(), runner)

        self.assertNotIn("backup", runner.operations)
        self.assertNotIn("scale-keycloak:0", runner.operations)


if __name__ == "__main__":
    unittest.main()
