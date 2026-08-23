from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import inspect
import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts/deploy/rke2/acceptance_producer.py"
SPEC = importlib.util.spec_from_file_location("acceptance_producer", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RELEASE_SPEC = importlib.util.spec_from_file_location(
    "acceptance_release", ROOT / "scripts/deploy/rke2/acceptance_release.py"
)
assert RELEASE_SPEC and RELEASE_SPEC.loader
RELEASE = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(RELEASE)

COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
IDENTITY_DOCUMENT = {
    "contractVersion": "aileron-installation-identity/v3",
    "installationId": "44444444-4444-4444-8444-444444444444",
    "clusterUid": CLUSTER_UID,
    "identityMode": "bundledKeycloak",
    "issuerUrl": "https://keycloak.apps.rke.soez.tw/realms/aileron",
    "clientId": "aileron-frontend",
}
IDENTITY_BYTES = (
    json.dumps(IDENTITY_DOCUMENT, indent=2, sort_keys=True) + "\n"
).encode()
IDENTITY_DIGEST = hashlib.sha256(IDENTITY_BYTES).hexdigest()
KEY = bytes(range(32))
SECRET_UID = "22222222-2222-4222-8222-222222222222"
ACCEPTANCE_NAMESPACE_UID = "11111111-1111-4111-8111-111111111111"
BROWSER_IMAGE_ID = f"sha256:{'c' * 64}"
MATERIALIZED_SUITE_TREE_SHA256 = (
    "888a0fba95dde74bb8838bb65a3e84cf0909af272feef2e458b478d4c96950a4"
)
BACKEND_PROFILE = {
    "schemaVersion": "aileron-backend-execution-profile/v1",
    "executionNamespace": "aileron-backend-attestor-system",
    "namespaceOwner": "aileron-installer",
    "imagePullSecret": "harbor-rke-creds",
    "nfsMountRoots": [{"server": "192.168.50.100", "path": "/volume1/okd/aileron"}],
    "localPathNodes": [],
}
REAL_LOAD_DEPLOYMENT_EPOCH = MODULE.ACCEPTANCE_EPOCH.load_deployment_epoch
REAL_MATERIALIZE_SUITE_SOURCE = MODULE._materialize_suite_source
REAL_PIN_TARGETS_KUBECONFIG = MODULE._pin_targets_kubeconfig
REAL_REQUIRE_PREDECESSOR_REPORTS = MODULE._require_predecessor_reports


def _canonical_backend_binding() -> dict:
    canonical_profile = json.dumps(
        BACKEND_PROFILE, separators=(",", ":"), sort_keys=True
    ).encode()
    return {
        "schemaVersion": "aileron-backend-attestor-snapshot-binding/v1",
        "executionProfile": {
            "schemaVersion": "aileron-backend-execution-profile-binding/v1",
            "rawSha256": hashlib.sha256(canonical_profile + b"\n").hexdigest(),
            "canonicalSha256": hashlib.sha256(canonical_profile).hexdigest(),
            "profile": BACKEND_PROFILE,
        },
        "executionResources": {
            "schemaVersion": "aileron-backend-execution-resources-binding/v1",
            "namespace": {
                "name": "aileron-backend-attestor-system",
                "uid": "namespace-uid",
                "owner": "aileron-installer",
                "phase": "Active",
                "podSecurityLabels": {
                    "pod-security.kubernetes.io/enforce": "privileged",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
            "imagePullSecret": {
                "namespace": "aileron-backend-attestor-system",
                "name": "harbor-rke-creds",
                "uid": "secret-uid",
                "owner": "aileron-installer",
                "dataKeys": [".dockerconfigjson"],
                "dataSha256": "d" * 64,
            },
        },
        "imageInventorySha256": "e" * 64,
    }


@pytest.fixture(autouse=True)
def _stable_store_anchor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_secrets = tmp_path / "install-secrets"
    install_secrets.mkdir(mode=0o700)
    store = install_secrets / "rke2"
    store.mkdir(mode=0o700)
    anchor = store / "acceptance-trust-anchor.json"
    anchor.write_text(
        json.dumps(
            {
                "contractVersion": "aileron-acceptance-trust-anchor/v2",
                "clusterUid": CLUSTER_UID,
                "installationIdentitySha256": IDENTITY_DIGEST,
                "keySha256": hashlib.sha256(KEY).hexdigest(),
                "secretName": "aileron-acceptance-signing",
                "secretNamespace": "aileron-acceptance-system",
                "secretUid": SECRET_UID,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    anchor.chmod(0o600)
    identity = store / "installation-identity.json"
    identity.write_bytes(IDENTITY_BYTES)
    identity.chmod(0o600)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE, "SECRET_STORE", store
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE, "PRIVATE_ROOT", tmp_path
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        MODULE.KUBERNETES_REST,
        "load_kubernetes_delete_client",
        lambda **_kwargs: NullKubernetesDeleteClient(),
    )
    for run_id in ("run-20260808", "run-20260808-clean"):
        MODULE.PRIVATE_IO.ensure_evidence_directory(
            private_root=tmp_path,
            commit=COMMIT,
            deployment_run_id=run_id,
            error_type=MODULE.AcceptanceProducerError,
        )

    def load_epoch(*, directory: Path, **_kwargs):
        snapshot = directory / MODULE.ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME
        if snapshot.exists():
            snapshot_document = json.loads(snapshot.read_text())
            run_id = snapshot_document["runId"]
            snapshot_sha256 = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        else:
            run_id = "run-20260808"
            snapshot_sha256 = "0" * 64
        return {
            "deploymentRunId": run_id,
            "clusterUid": CLUSTER_UID,
            "installationIdentitySha256": IDENTITY_DIGEST,
            "authenticationMode": "bundledKeycloak",
            "resetSnapshotSha256": snapshot_sha256,
            "createdAt": "2026-08-08T06:00:00Z",
            "context": "rke2-homelab",
        }

    def materialize_source(
        *,
        targets,
        directory: Path,
        run_id: str,
        section: str,
        runner,
    ):
        del runner
        archive_command = [
            "git",
            "-C",
            str(ROOT),
            "archive",
            "--format=tar.gz",
            targets.commit,
        ]
        archive_path = directory / f"{section}-source-archive.tar.gz"
        archive_path.write_bytes(b"suite archive fixture\n")
        archive_path.chmod(0o600)
        source = {
            "file": archive_path.name,
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "command": archive_command,
            "exitCode": 0,
        }
        root = (
            directory
            / f".{section}-source-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
        )
        root.mkdir(mode=0o700)
        tracked = root / "tracked.txt"
        tracked.write_text("exact source fixture\n", encoding="utf-8")
        tracked.chmod(0o400)
        readonly = root / "readonly"
        readonly.mkdir(mode=0o700)
        nested = readonly / "nested.txt"
        nested.write_text("nested immutable fixture\n", encoding="utf-8")
        nested.chmod(0o400)
        readonly.chmod(0o500)
        return MODULE.SuiteSource(
            root, MODULE._suite_tree_sha256(root), source, archive_command
        )

    monkeypatch.setattr(MODULE.ACCEPTANCE_EPOCH, "load_deployment_epoch", load_epoch)
    monkeypatch.setattr(MODULE, "_materialize_suite_source", materialize_source)
    monkeypatch.setattr(
        MODULE,
        "_pin_targets_kubeconfig",
        lambda *, targets, **_kwargs: targets,
    )
    monkeypatch.setattr(
        MODULE,
        "_require_predecessor_reports",
        lambda **_kwargs: None,
    )


def _targets(tmp_path: Path):
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_bytes(
        _self_contained_kubeconfig(
            server="https://192.0.2.10:6443", token="installer-token"
        )
    )
    kubeconfig.chmod(0o600)
    return MODULE.ProducerTargets(
        context="rke2-homelab",
        kubeconfig=kubeconfig,
        workspace_id="workspace-1",
        user_subject="subject-1",
        platform_url="https://aileron.example.test",
        issuer_url="https://keycloak.apps.rke.soez.tw/realms/aileron",
        admin_console_url=(
            "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
        ),
        client_id="aileron-frontend",
        commit=COMMIT,
    )


def _self_contained_kubeconfig(*, server: str, token: str) -> bytes:
    return (
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": "rke2-homelab",
                "clusters": [
                    {
                        "name": "homelab",
                        "cluster": {
                            "server": server,
                            "certificate-authority-data": base64.b64encode(
                                b"homelab-ca"
                            ).decode(),
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": "rke2-homelab",
                        "context": {"cluster": "homelab", "user": "installer"},
                    }
                ],
                "users": [{"name": "installer", "user": {"token": token}}],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _evidence_directory(tmp_path: Path, run_id: str = "run-20260808") -> Path:
    return tmp_path / "evidence" / COMMIT / run_id


def _browser_input_document() -> dict:
    return {
        "schemaVersion": "aileron-browser-input/v2",
        "loginDriver": {"kind": "keycloak"},
        "loginUser": {"username": "native", "password": "native-secret"},
        "breakGlassUser": {
            "username": "local-emergency-admin",
            "password": "break-glass-secret",
        },
        "adminUser": {"username": "admin", "password": "admin-secret"},
        "platformAdminUser": {
            "username": "platform-admin",
            "password": "platform-admin-secret",
        },
    }


def _write_canonical_browser_input(
    tmp_path: Path,
    *,
    run_id: str = "run-20260808",
    document: dict | None = None,
) -> Path:
    current = tmp_path
    for component in ("acceptance-inputs", COMMIT, run_id):
        current /= component
        current.mkdir(mode=0o700, exist_ok=True)
        current.chmod(0o700)
    path = current / "browser-input.json"
    path.write_bytes(
        (
            json.dumps(
                document if document is not None else _browser_input_document(),
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )
    path.chmod(0o600)
    return path


class Runner:
    def __init__(
        self,
        responses: dict[tuple[str, ...], MODULE.CommandResult],
        effects: dict[tuple[str, ...], Callable[[], None]] | None = None,
    ):
        self.responses = responses
        self.effects = effects or {}
        self.commands: list[list[str]] = []

    def __call__(
        self, command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        self.commands.append(command)
        key = tuple(command)
        if key in self.effects:
            self.effects[key]()
        if key not in self.responses:
            raise AssertionError(f"unexpected command: {command}")
        return self.responses[key]


class NullKubernetesDeleteClient:
    def __init__(self) -> None:
        self.get_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    def get(self, **kwargs) -> None:
        self.get_calls.append(kwargs)

    def delete(self, **kwargs) -> None:
        self.delete_calls.append(kwargs)


def _server_oracle_resources(
    manifest: dict,
    immutable_image: str,
    job_uid: str,
) -> tuple[dict, dict]:
    name = manifest["metadata"]["name"]
    namespace = manifest["metadata"]["namespace"]
    controller_labels = {
        "batch.kubernetes.io/controller-uid": job_uid,
        "batch.kubernetes.io/job-name": name,
        "controller-uid": job_uid,
        "job-name": name,
    }
    job_spec = json.loads(json.dumps(manifest["spec"]))
    job_spec.update(
        {
            "completionMode": "NonIndexed",
            "completions": 1,
            "manualSelector": False,
            "parallelism": 1,
            "podReplacementPolicy": "TerminatingOrFailed",
            "selector": {
                "matchLabels": {"batch.kubernetes.io/controller-uid": job_uid}
            },
            "suspend": False,
        }
    )
    job_spec["template"]["metadata"]["labels"].update(controller_labels)
    job_spec["template"]["spec"]["containers"][0].update(
        {
            "terminationMessagePath": "/dev/termination-log",
            "terminationMessagePolicy": "File",
        }
    )
    job_spec["template"]["spec"].update(
        {
            "dnsPolicy": "ClusterFirst",
            "schedulerName": "default-scheduler",
            "serviceAccount": "aileron-acceptance-oracle",
            "terminationGracePeriodSeconds": 30,
        }
    )
    pod_spec = json.loads(json.dumps(job_spec["template"]["spec"]))
    token_volume = "kube-api-access-abcde"
    pod_spec.update(
        {
            "enableServiceLinks": True,
            "nodeName": "homelab-worker-1",
            "preemptionPolicy": "PreemptLowerPriority",
            "priority": 0,
            "serviceAccount": "aileron-acceptance-oracle",
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
            "volumes": [
                *pod_spec.get("volumes", []),
                {
                    "name": token_volume,
                    "projected": {
                        "defaultMode": 420,
                        "sources": [
                            {
                                "serviceAccountToken": {
                                    "expirationSeconds": 3607,
                                    "path": "token",
                                }
                            },
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
                    },
                },
            ],
        }
    )
    pod_spec["containers"][0]["volumeMounts"] = [
        *pod_spec["containers"][0].get("volumeMounts", []),
        {
            "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
            "name": token_volume,
            "readOnly": True,
        },
    ]
    completion_time = "2026-08-08T07:00:30Z"
    started_time = "2026-08-08T07:00:00Z"
    container_id = "containerd://" + "a" * 64
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "uid": job_uid,
            "resourceVersion": "101",
            "labels": manifest["metadata"]["labels"],
            "annotations": manifest["metadata"]["annotations"],
            "ownerReferences": [],
        },
        "spec": job_spec,
        "status": {
            "active": 0,
            "succeeded": 1,
            "failed": 0,
            "completionTime": completion_time,
            "conditions": [
                {
                    "type": "Complete",
                    "status": "True",
                    "lastProbeTime": completion_time,
                    "lastTransitionTime": completion_time,
                    "reason": "CompletionsReached",
                    "message": "Reached expected number of succeeded pods",
                }
            ],
        },
    }
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"{name}-pod",
            "namespace": namespace,
            "uid": "oracle-pod-uid",
            "labels": {**manifest["metadata"]["labels"], **controller_labels},
            "ownerReferences": [
                {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "name": name,
                    "uid": job_uid,
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
                    "name": "oracle",
                    "restartCount": 0,
                    "image": immutable_image,
                    "imageID": "docker-pullable://" + immutable_image,
                    "containerID": container_id,
                    "ready": False,
                    "started": False,
                    "lastState": {},
                    "state": {
                        "terminated": {
                            "containerID": container_id,
                            "exitCode": 0,
                            "reason": "Completed",
                            "startedAt": started_time,
                            "finishedAt": completion_time,
                        }
                    },
                }
            ],
        },
    }
    return job, pod


def _identity_command(targets) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "get",
        "namespace",
        "kube-system",
        "--output=jsonpath={.metadata.uid}",
    ]


def _acceptance_namespace_command(targets) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "get",
        "namespace",
        "aileron-acceptance-system",
        "--output=json",
    ]


def test_soak_publication_error_preserves_validation_and_rollback_failures() -> None:
    validation_failure = RuntimeError("readback rejected")
    rollback_failure = OSError("rollback failed")

    error = MODULE.SoakPublicationError([validation_failure, rollback_failure])

    assert error.failures == (validation_failure, rollback_failure)
    assert str(error).endswith("readback rejected; rollback failed")


def test_atomic_private_snapshot_never_overwrites_an_existing_report(
    tmp_path: Path,
) -> None:
    destination = _evidence_directory(tmp_path) / "soak.json"
    destination.write_bytes(b"existing canonical report\n")
    destination.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceProducerError, match="already exists"):
        MODULE._publish_private_snapshot_atomic(
            destination,
            b"replacement report\n",
        )

    assert destination.read_bytes() == b"existing canonical report\n"
    assert not list(destination.parent.glob(".soak.json.tmp-*"))


def test_atomic_private_snapshot_cleans_the_temp_when_link_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = _evidence_directory(tmp_path) / "soak.json"

    def fail_link(*_args, **_kwargs) -> None:
        raise OSError("simulated atomic link failure")

    monkeypatch.setattr(MODULE.os, "link", fail_link)
    with pytest.raises(MODULE.AcceptanceProducerError, match="atomic link"):
        MODULE._publish_private_snapshot_atomic(destination, b"canonical report\n")

    assert not destination.exists()
    assert not list(destination.parent.glob(".soak.json.tmp-*"))


def test_atomic_private_snapshot_recovers_a_pre_link_crash(tmp_path: Path) -> None:
    destination = _evidence_directory(tmp_path) / "soak.json"
    content = b"canonical report\n"
    temporary = destination.parent / f".{destination.name}.tmp-{'a' * 32}"
    MODULE._write_private_snapshot(temporary, content)

    MODULE._publish_private_snapshot_atomic(destination, content)

    assert destination.read_bytes() == content
    assert destination.stat().st_nlink == 1
    assert not list(destination.parent.glob(".soak.json.tmp-*"))


def test_atomic_private_snapshot_recovers_a_post_link_crash(tmp_path: Path) -> None:
    destination = _evidence_directory(tmp_path) / "soak.json"
    content = b"canonical report\n"
    temporary = destination.parent / f".{destination.name}.tmp-{'b' * 32}"
    MODULE._write_private_snapshot(temporary, content)
    os.link(temporary, destination, follow_symlinks=False)
    MODULE._fsync_private_directory(destination.parent)
    assert destination.stat().st_nlink == 2

    MODULE._publish_private_snapshot_atomic(destination, content)

    assert destination.read_bytes() == content
    assert destination.stat().st_nlink == 1
    assert not temporary.exists()


@pytest.mark.parametrize(
    "state",
    ["unknown-name", "multiple", "mismatched-inode"],
)
def test_atomic_private_snapshot_rejects_unknown_recovery_state(
    tmp_path: Path, state: str
) -> None:
    destination = _evidence_directory(tmp_path) / "soak.json"
    content = b"canonical report\n"
    first = destination.parent / f".{destination.name}.tmp-{'c' * 32}"
    if state == "unknown-name":
        first = destination.parent / f".{destination.name}.tmp-not-canonical"
    MODULE._write_private_snapshot(first, content)
    if state == "multiple":
        MODULE._write_private_snapshot(
            destination.parent / f".{destination.name}.tmp-{'d' * 32}",
            content,
        )
    elif state == "mismatched-inode":
        MODULE._write_private_snapshot(destination, content)

    with pytest.raises(MODULE.AcceptanceProducerError, match="recovery"):
        MODULE._publish_private_snapshot_atomic(destination, content)


def test_identity_smoke_is_fixed_before_oracle(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "identity-evidence"
    evidence.mkdir(mode=0o700)
    helm_list = [
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
    chart_metadata = [
        "git",
        "show",
        f"{targets.commit}:helm/aileron-identity/Chart.yaml",
    ]
    chart_tree = [
        "git",
        "ls-tree",
        "-r",
        targets.commit,
        "--",
        "helm/aileron-identity",
    ]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "aileron-identity-system",
    ]
    delete_marker = [
        *kubectl,
        "delete",
        "configmap",
        "aileron-identity-restore-marker",
        "--ignore-not-found",
        "--wait=true",
    ]
    smoke_prefix = [
        "python3",
        "identity-installation/backup_restore_smoke.py",
        "--kubeconfig",
        str(targets.kubeconfig),
    ]
    chart_digest = (
        "sha256:"
        + hashlib.sha256(
            b"100644 blob abc\thelm/aileron-identity/Chart.yaml\n"
        ).hexdigest()
    )
    keycloak_image = "registry.example/keycloak@sha256:" + "1" * 64
    keycloak_runtime_image = "registry.example/keycloak@sha256:" + "2" * 64
    postgres_image = "registry.example/postgres@sha256:" + "3" * 64
    postgres_runtime_image = "registry.example/postgres@sha256:" + "4" * 64
    release_images = [
        {
            "component": "platform-keycloak",
            "immutableImage": keycloak_image,
            "runtimeImmutableImage": keycloak_runtime_image,
        },
        {
            "component": "platform-postgres",
            "immutableImage": postgres_image,
            "runtimeImmutableImage": postgres_runtime_image,
        },
    ]
    confirmation = (
        f"{targets.context}/aileron-identity-system/aileron-identity"
        f"@revision=2,chart=1.2.3,commit={COMMIT},chartDigest={chart_digest}"
        f",keycloakImage={keycloak_image}"
        f",keycloakRuntimeImage={keycloak_runtime_image}"
        f",postgresImage={postgres_image}"
        f",postgresRuntimeImage={postgres_runtime_image}"
    )
    smoke = [
        *smoke_prefix,
        "--context",
        targets.context,
        "--namespace",
        "aileron-identity-system",
        "--release",
        "aileron-identity",
        "--commit",
        COMMIT,
        "--release-revision",
        "2",
        "--chart-version",
        "1.2.3",
        "--chart-digest",
        chart_digest,
        "--keycloak-image",
        keycloak_image,
        "--keycloak-runtime-image",
        keycloak_runtime_image,
        "--postgres-image",
        postgres_image,
        "--postgres-runtime-image",
        postgres_runtime_image,
        "--confirm-destructive-restore",
        confirmation,
    ]
    wait = [
        *kubectl,
        "wait",
        "--for=condition=available",
        "deployment/aileron-identity-keycloak",
        "--timeout=10m",
    ]
    apply = [
        *kubectl,
        "apply",
        "--filename",
        str(evidence / "identity-restore-marker.json"),
        "--output=name",
    ]
    smoke_report = {
        "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
        "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
        "restoreJobUid": "restore-job-uid",
        "restoreMarker": "identity-smoke-marker",
        "jobClosureVerified": True,
    }
    smoke_report_raw = (
        json.dumps(smoke_report, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    responses = {
        tuple(helm_list): MODULE.CommandResult(
            b'[{"name":"aileron-identity","revision":2}]', b"", 0
        ),
        tuple(chart_metadata): MODULE.CommandResult(b"version: 1.2.3\n", b"", 0),
        tuple(chart_tree): MODULE.CommandResult(
            b"100644 blob abc\thelm/aileron-identity/Chart.yaml\n", b"", 0
        ),
        tuple(delete_marker): MODULE.CommandResult(b"", b"", 0),
        tuple(smoke): MODULE.CommandResult(smoke_report_raw, b"", 0),
        tuple(wait): MODULE.CommandResult(b"condition met\n", b"", 0),
        tuple(apply): MODULE.CommandResult(
            b"configmap/aileron-identity-restore-marker configured\n", b"", 0
        ),
    }
    runner = Runner(responses)

    sources = MODULE._prepare_identity_smoke(
        targets=targets,
        directory=evidence,
        run_id="run-20260808",
        release_images=release_images,
        runner=runner,
    )

    assert any(source["command"][:4] == smoke_prefix for source in sources)
    marker = json.loads((evidence / "identity-restore-marker.json").read_text())
    assert marker["data"] == {
        "commit": COMMIT,
        "marker": "identity-smoke-marker",
        "runId": "run-20260808",
        "smokeReport": smoke_report_raw.decode().strip(),
    }


def test_identity_smoke_rejects_legacy_text_stdout(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "identity-legacy-evidence"
    evidence.mkdir(mode=0o700)
    release_images = [
        {
            "component": "platform-keycloak",
            "immutableImage": "registry.example/keycloak@sha256:" + "1" * 64,
            "runtimeImmutableImage": "registry.example/keycloak@sha256:" + "2" * 64,
        },
        {
            "component": "platform-postgres",
            "immutableImage": "registry.example/postgres@sha256:" + "3" * 64,
            "runtimeImmutableImage": "registry.example/postgres@sha256:" + "4" * 64,
        },
    ]

    def runner(command: list[str], timeout_seconds: float | None = None):
        if command[:2] == ["helm", "--kubeconfig"]:
            return MODULE.CommandResult(
                b'[{"name":"aileron-identity","revision":2}]', b"", 0
            )
        if command[:2] == ["git", "show"]:
            return MODULE.CommandResult(b"version: 1.2.3\n", b"", 0)
        if command[:2] == ["git", "ls-tree"]:
            return MODULE.CommandResult(
                b"100644 blob abc\thelm/aileron-identity/Chart.yaml\n", b"", 0
            )
        if command[:2] == ["python3", "identity-installation/backup_restore_smoke.py"]:
            return MODULE.CommandResult(
                b"Identity backup/restore smoke passed\n", b"", 0
            )
        return MODULE.CommandResult(b"", b"", 0)

    with pytest.raises(MODULE.AcceptanceProducerError, match="smoke report"):
        MODULE._prepare_identity_smoke(
            targets=targets,
            directory=evidence,
            run_id="run-20260808",
            release_images=release_images,
            runner=runner,
        )


@pytest.mark.parametrize("invalid_uid", [" ", "restore\njob", "restore\x00job"])
def test_identity_smoke_rejects_whitespace_or_control_job_uids(
    invalid_uid: str,
) -> None:
    report = {
        "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
        "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
        "restoreJobUid": invalid_uid,
        "restoreMarker": "identity-smoke-marker",
        "jobClosureVerified": True,
    }
    raw = (json.dumps(report, separators=(",", ":"), sort_keys=True) + "\n").encode()

    with pytest.raises(MODULE.AcceptanceProducerError, match="smoke report"):
        MODULE._validate_identity_smoke_report(raw)


def _secret_command(targets) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "aileron-acceptance-system",
        "get",
        "secret",
        "aileron-acceptance-signing",
        "--output=json",
    ]


def _trust_responses(targets) -> dict[tuple[str, ...], MODULE.CommandResult]:
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "aileron-acceptance-system",
            "uid": ACCEPTANCE_NAMESPACE_UID,
            "resourceVersion": "101",
            "labels": {
                "platform.aileron.dev/namespace-owner": "aileron-installer",
                "pod-security.kubernetes.io/enforce": "restricted",
                "pod-security.kubernetes.io/audit": "restricted",
                "pod-security.kubernetes.io/warn": "restricted",
            },
        },
        "status": {"phase": "Active"},
    }
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "immutable": True,
        "metadata": {
            "name": "aileron-acceptance-signing",
            "namespace": "aileron-acceptance-system",
            "uid": SECRET_UID,
            "resourceVersion": "19",
            "labels": {
                "platform.aileron.dev/secret-owner": "aileron-installer",
                "platform.aileron.dev/cluster-uid": CLUSTER_UID,
            },
            "annotations": {
                "platform.aileron.dev/installation-identity-sha256": IDENTITY_DIGEST,
            },
        },
        "data": {"hmac-key": base64.b64encode(KEY).decode()},
        "type": "Opaque",
    }
    return {
        tuple(_identity_command(targets)): MODULE.CommandResult(
            CLUSTER_UID.encode(), b"", 0
        ),
        tuple(_acceptance_namespace_command(targets)): MODULE.CommandResult(
            json.dumps(namespace).encode(), b"", 0
        ),
        tuple(_secret_command(targets)): MODULE.CommandResult(
            json.dumps(secret).encode(), b"", 0
        ),
    }


def _trust_commands(targets) -> list[list[str]]:
    namespace_command = _acceptance_namespace_command(targets)
    return [
        _identity_command(targets),
        namespace_command,
        _secret_command(targets),
        namespace_command,
    ]


def _signed_inventory(tmp_path: Path, targets) -> Path:
    components = json.loads(
        (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
    )["publishedComponents"]
    images = [
        {
            "component": component,
            "revision": targets.commit,
            "platform": "linux/amd64",
            "taggedImage": f"harbor.example.test/library/{component}:git-{targets.commit}",
            "immutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 1:064x}"
            ),
            "runtimeImmutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 101:064x}"
            ),
        }
        for index, component in enumerate(components)
    ]
    install_directory = tmp_path / "install" / targets.commit
    install_directory.parent.mkdir(mode=0o700, exist_ok=True)
    install_directory.mkdir(mode=0o700, exist_ok=True)
    path = install_directory / "signed-image-inventory.json"
    RELEASE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=images,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    return path


def _soak_release_images(targets) -> list[dict[str, str]]:
    components = json.loads(
        (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
    )["publishedComponents"]
    required_indexes = [
        "registry.example/product@sha256:" + "1" * 64,
        "registry.example/browser@sha256:" + "2" * 64,
        "registry.example/canvas@sha256:" + "3" * 64,
    ]
    images = []
    for index, component in enumerate(components):
        immutable_image = (
            required_indexes[index]
            if index < len(required_indexes)
            else f"registry.example/{component}@sha256:{index + 1:064x}"
        )
        repository = immutable_image.rsplit("@", 1)[0]
        images.append(
            {
                "component": component,
                "revision": targets.commit,
                "platform": "linux/amd64",
                "taggedImage": f"{repository}:git-{targets.commit}",
                "immutableImage": immutable_image,
                "runtimeImmutableImage": (f"{repository}@sha256:{index + 101:064x}"),
            }
        )
    return images


def _signed_soak_inventory(tmp_path: Path, targets) -> Path:
    install_directory = tmp_path / "install" / targets.commit
    install_directory.parent.mkdir(mode=0o700, exist_ok=True)
    install_directory.mkdir(mode=0o700, exist_ok=True)
    path = install_directory / "signed-image-inventory.json"
    RELEASE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=_soak_release_images(targets),
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    return path


def _soak_image_runtime_pairs(targets) -> dict[str, frozenset[str]]:
    return MODULE.ACCEPTANCE_SOAK.release_image_runtime_pairs(
        _soak_release_images(targets)
    )


def _allowed_oracle_digests(image: dict[str, str]) -> set[str]:
    return {
        image["immutableImage"].rsplit("@", 1)[1],
        image["runtimeImmutableImage"].rsplit("@", 1)[1],
    }


def _backend_profile(tmp_path: Path) -> Path:
    directory = tmp_path / "backend-attestor"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "execution-profile.json"
    path.write_bytes(
        json.dumps(BACKEND_PROFILE, separators=(",", ":"), sort_keys=True).encode()
        + b"\n"
    )
    path.chmod(0o600)
    return path


def _backend_resource_responses(targets) -> dict[tuple[str, ...], MODULE.CommandResult]:
    prefix = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--request-timeout=30s",
    ]
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "aileron-backend-attestor-system",
            "uid": "backend-namespace-uid",
            "labels": {
                "platform.aileron.dev/namespace-owner": "aileron-installer",
                "pod-security.kubernetes.io/enforce": "privileged",
                "pod-security.kubernetes.io/audit": "restricted",
                "pod-security.kubernetes.io/warn": "restricted",
            },
        },
        "status": {"phase": "Active"},
    }
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "kubernetes.io/dockerconfigjson",
        "metadata": {
            "namespace": "aileron-backend-attestor-system",
            "name": "harbor-rke-creds",
            "uid": "backend-pull-secret-uid",
            "labels": {"platform.aileron.dev/secret-owner": "aileron-installer"},
        },
        "data": {".dockerconfigjson": "eyJhdXRocyI6e319"},
    }
    return {
        (
            *prefix,
            "get",
            "namespace",
            "aileron-backend-attestor-system",
            "--output=json",
        ): MODULE.CommandResult(json.dumps(namespace).encode(), b"", 0),
        (
            *prefix,
            "--namespace",
            "aileron-backend-attestor-system",
            "get",
            "secret",
            "harbor-rke-creds",
            "--output=json",
        ): MODULE.CommandResult(json.dumps(secret).encode(), b"", 0),
    }


def _mock_backend_post_reset(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    targets,
    run_id: str,
    snapshot_sha256: str,
    backend_targets: list[dict],
) -> tuple[dict, dict, dict[str, int]]:
    cleanup_targets = tuple(
        type(
            "CleanupTarget",
            (),
            {
                "persistent_volume_name": target["name"],
                "persistent_volume_uid": target["uid"],
                "locator_sha256": hashlib.sha256(
                    MODULE._canonical(target["locator"])
                ).hexdigest(),
            },
        )()
        for target in sorted(
            backend_targets, key=lambda item: (item["name"], item["uid"])
        )
    )
    inputs = type("SignedInputs", (), {"cleanup_targets": cleanup_targets})()
    results = [
        {
            "persistentVolume": {
                "name": target.persistent_volume_name,
                "uid": target.persistent_volume_uid,
            },
            "locatorSha256": target.locator_sha256,
            "cleanupResultSha256": "1" * 64,
            "verificationResultSha256": "2" * 64,
            "attestation": {},
        }
        for target in cleanup_targets
    ]
    cleanup = {
        "schemaVersion": "aileron-backend-cleanup-results/v1",
        "commit": targets.commit,
        "runId": run_id,
        "snapshotSha256": snapshot_sha256,
        "profileRawSha256": "3" * 64,
        "profileCanonicalSha256": "4" * 64,
        "imageInventorySha256": "5" * 64,
        "results": results,
        "allAbsent": True,
    }
    cleanup_raw = MODULE._canonical(cleanup) + b"\n"
    reset_directory = tmp_path / "reset" / targets.commit / run_id
    reset_directory.mkdir(mode=0o700, parents=True)
    for directory in (
        tmp_path / "reset",
        tmp_path / "reset" / targets.commit,
        reset_directory,
    ):
        directory.chmod(0o700)
    cleanup_path = reset_directory / "backend-cleanup-results.json"
    cleanup_path.write_bytes(cleanup_raw)
    cleanup_path.chmod(0o600)
    verification = {
        "schemaVersion": "aileron-backend-post-reset-verification/v1",
        "commit": targets.commit,
        "runId": run_id,
        "snapshotSha256": snapshot_sha256,
        "backendCleanupResultsSha256": hashlib.sha256(cleanup_raw).hexdigest(),
        "verifications": [
            {
                "persistentVolume": result["persistentVolume"],
                "locatorSha256": result["locatorSha256"],
                "verificationResultSha256": "6" * 64,
                "verification": {},
            }
            for result in results
        ],
        "allAbsent": True,
    }
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "load_signed_backend_attestor_inputs",
        lambda **_kwargs: inputs,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "load_backend_cleanup_results",
        lambda observed_inputs: cleanup if observed_inputs is inputs else None,
    )
    calls = {"verify": 0, "validate": 0}

    def verify(observed_inputs):
        assert observed_inputs is inputs
        calls["verify"] += 1
        return verification

    def validate(document, *, inputs):
        assert inputs is not None
        calls["validate"] += 1
        return document

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "verify_signed_backend_absence",
        verify,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "validate_backend_post_reset_verification",
        validate,
    )
    return cleanup, verification, calls


def _suite_git_commands(targets) -> tuple[list[str], list[str]]:
    return (
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        [
            "git",
            "-C",
            str(ROOT),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
    )


def _clean_suite_source_responses(
    targets,
) -> dict[tuple[str, ...], MODULE.CommandResult]:
    head_command, status_command = _suite_git_commands(targets)
    return {
        tuple(head_command): MODULE.CommandResult(
            f"{targets.commit}\n".encode(), b"", 0
        ),
        tuple(status_command): MODULE.CommandResult(b"", b"", 0),
    }


def _browser_probe_fixture(
    *,
    section: str,
    targets,
    evidence: Path,
    observations: dict[str, object],
    run_id: str = "run-20260808",
) -> tuple[
    dict[tuple[str, ...], MODULE.CommandResult],
    list[list[str]],
    bytes,
]:
    tracked_script = (ROOT / MODULE.BROWSER_PROBE_PATH).read_bytes()
    source_commands = MODULE.browser_source_commands(targets.commit)
    image_tag = (
        f"{MODULE.BROWSER_IMAGE_REPOSITORY}:{targets.commit}-"
        f"{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    )
    build = [
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
    inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        image_tag,
    ]
    shared_tag = [
        "docker",
        "image",
        "tag",
        BROWSER_IMAGE_ID,
        f"{MODULE.BROWSER_IMAGE_REPOSITORY}:{targets.commit}",
    ]
    cleanup_unique_tag = [
        "docker",
        "image",
        "rm",
        "--force",
        image_tag,
    ]
    image_script = [
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "node",
        BROWSER_IMAGE_ID,
        "-e",
        (
            'process.stdout.write(require("node:fs").readFileSync('
            '"/app/e2e/acceptance.mjs"))'
        ),
    ]
    run = MODULE.build_browser_probe_command(
        section=section,
        targets=targets,
        browser_input=evidence / f".browser-input-{run_id}.json",
        run_id=run_id,
        image_reference=BROWSER_IMAGE_ID,
    )
    responses = {
        **_clean_suite_source_responses(targets),
        tuple(source_commands[0]): MODULE.CommandResult(b"", b"", 0),
        tuple(source_commands[1]): MODULE.CommandResult(
            f"{targets.commit}\n".encode(), b"", 0
        ),
        tuple(source_commands[2]): MODULE.CommandResult(tracked_script, b"", 0),
        tuple(build): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect): MODULE.CommandResult(
            f"{BROWSER_IMAGE_ID}\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(shared_tag): MODULE.CommandResult(b"tagged\n", b"", 0),
        tuple(cleanup_unique_tag): MODULE.CommandResult(b"untagged\n", b"", 0),
        tuple(image_script): MODULE.CommandResult(tracked_script, b"", 0),
        tuple(run): MODULE.CommandResult(json.dumps(observations).encode(), b"", 0),
    }
    return (
        responses,
        [
            build,
            inspect,
            shared_tag,
            cleanup_unique_tag,
            source_commands[2],
            image_script,
            run,
        ],
        tracked_script,
    )


def _browser_cleanup_commands(
    run_command: list[str],
) -> tuple[list[str], list[str], str]:
    container_name = run_command[run_command.index("--name") + 1]
    return (
        ["docker", "rm", "--force", container_name],
        ["docker", "container", "inspect", "--format={{.Id}}", container_name],
        container_name,
    )


def _missing_container_result(container_name: str) -> MODULE.CommandResult:
    return MODULE.CommandResult(
        b"",
        f"Error response from daemon: No such container: {container_name}\n".encode(),
        1,
    )


def _materialized_suite_root(evidence: Path, section: str, run_id: str) -> Path:
    return evidence / (
        f".{section}-source-{hashlib.sha256(run_id.encode()).hexdigest()[:12]}"
    )


def _suite_archive_fixture(content: bytes) -> bytes:
    archive_buffer = MODULE.io.BytesIO()
    with MODULE.tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        tracked = MODULE.tarfile.TarInfo("tracked.txt")
        tracked.mode = 0o644
        tracked.size = len(content)
        archive.addfile(tracked, MODULE.io.BytesIO(content))
    return archive_buffer.getvalue()


def test_cli_has_no_arbitrary_command_or_signing_key_surface() -> None:
    parser = MODULE.build_parser()
    options = {option for action in parser._actions for option in action.option_strings}

    assert "--signing-key" not in options
    assert "--secret-store" not in options
    assert "--command" not in options
    assert "--reset-inventory" not in options
    assert "--expected-reset-run-id" not in options
    assert "--deployment-run-id" in options
    assert "--expected-commit" in options
    assert "--admin-console-url" in options
    assert "--expected-reset-snapshot-digest" in options
    assert "--browser-input" not in options
    assert "browser_input" not in inspect.signature(MODULE.produce).parameters
    assert not any(action.nargs == argparse.REMAINDER for action in parser._actions)


def test_browser_input_source_is_exact_commit_and_run_bound_path(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    decoy = tmp_path / "browser-input.json"
    decoy.write_bytes(b"{}\n")
    decoy.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceProducerError):
        MODULE._load_browser_input(
            targets=targets,
            deployment_run_id="run-20260808",
            authentication_mode="bundledKeycloak",
        )

    canonical = _write_canonical_browser_input(tmp_path)
    assert (
        MODULE._canonical_browser_input_path(
            targets=targets,
            deployment_run_id="run-20260808",
        )
        == canonical
    )
    assert (
        MODULE._load_browser_input(
            targets=targets,
            deployment_run_id="run-20260808",
            authentication_mode="bundledKeycloak",
        )
        == _browser_input_document()
    )


def test_browser_input_source_requires_strict_canonical_json(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    path = _write_canonical_browser_input(tmp_path)
    path.write_text(json.dumps(_browser_input_document()), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="schema is invalid",
    ):
        MODULE._load_browser_input(
            targets=targets,
            deployment_run_id="run-20260808",
            authentication_mode="bundledKeycloak",
        )


@pytest.mark.parametrize(
    ("authentication_mode", "mutate"),
    [
        (
            "bundledKeycloak",
            lambda document: document.pop("platformAdminUser"),
        ),
        (
            "externalOidc",
            lambda document: document.update(
                {
                    "platformAdminUser": {
                        "username": "unexpected-admin",
                        "password": "unexpected-secret",
                    }
                }
            ),
        ),
    ],
)
def test_browser_input_strictly_scopes_platform_admin_to_bundled_keycloak(
    tmp_path: Path,
    authentication_mode: str,
    mutate,
) -> None:
    targets = _targets(tmp_path)
    document = (
        _browser_input_document()
        if authentication_mode == "bundledKeycloak"
        else {
            "schemaVersion": "aileron-browser-input/v2",
            "loginDriver": {
                "kind": "form",
                "usernameSelector": "#username",
                "passwordSelector": "#password",
                "submitSelector": "#submit",
                "errorSelector": "#error",
            },
            "loginUser": {"username": "external", "password": "external-secret"},
        }
    )
    mutate(document)
    _write_canonical_browser_input(tmp_path, document=document)

    with pytest.raises(MODULE.AcceptanceProducerError, match="schema is invalid"):
        MODULE._load_browser_input(
            targets=targets,
            deployment_run_id="run-20260808",
            authentication_mode=authentication_mode,
        )


@pytest.mark.parametrize(
    ("section", "expected_keys", "excluded_secrets"),
    [
        (
            "oidcWorkspace",
            {"schemaVersion", "loginDriver", "loginUser"},
            {"break-glass-secret", "admin-secret", "platform-admin-secret"},
        ),
        (
            "adminDisableLogin",
            {
                "schemaVersion",
                "loginDriver",
                "breakGlassUser",
                "adminUser",
                "platformAdminUser",
            },
            {"native-secret"},
        ),
    ],
)
def test_browser_input_projection_contains_only_section_credentials(
    section: str,
    expected_keys: set[str],
    excluded_secrets: set[str],
) -> None:
    projected = MODULE._project_browser_input(
        section=section,
        input_document=_browser_input_document(),
    )
    document = json.loads(projected)

    assert set(document) == expected_keys
    assert projected == MODULE._canonical(document) + b"\n"
    assert all(secret not in projected.decode("utf-8") for secret in excluded_secrets)


def test_interactive_sections_use_fixed_browser_and_conformance_phases(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    browser_input = tmp_path / "browser-input.json"
    browser_input.write_text(
        json.dumps(
            {
                "schemaVersion": "aileron-browser-input/v2",
                "loginDriver": {"kind": "keycloak"},
                "loginUser": {"username": "native", "password": "native-secret"},
                "breakGlassUser": {
                    "username": "local-emergency-admin",
                    "password": "break-glass-secret",
                },
                "adminUser": {"username": "admin", "password": "admin-secret"},
                "platformAdminUser": {
                    "username": "platform-admin",
                    "password": "platform-admin-secret",
                },
            }
        )
    )
    browser_input.chmod(0o600)

    assert {
        "oidcWorkspace",
        "workspaceLifecycle",
        "adminDisableLogin",
        "offlineOidcConformance",
    }.isdisjoint(MODULE.ORACLE_SECTIONS)
    oidc_command = MODULE.build_browser_probe_command(
        section="oidcWorkspace",
        targets=targets,
        browser_input=browser_input,
        run_id="run-20260808",
    )
    assert oidc_command[:3] == ["docker", "run", "--rm"]
    assert f"ailerondocker/workspace-ui-playwright:{COMMIT}" in oidc_command
    assert "workspace-ui-playwright:test" not in oidc_command
    assert "/run/secrets/acceptance-browser.json" in " ".join(oidc_command)
    assert browser_input.read_text() not in " ".join(oidc_command)
    assert oidc_command[-2:] == ["--run-id", "run-20260808"]
    assert "--admin-console-url" not in oidc_command
    admin_command = MODULE.build_browser_probe_command(
        section="adminDisableLogin",
        targets=targets,
        browser_input=browser_input,
        run_id="run-20260808",
    )
    assert admin_command[-2:] == [
        "--admin-console-url",
        targets.admin_console_url,
    ]
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="valid HTTPS admin console URL",
    ):
        MODULE.build_browser_probe_command(
            section="adminDisableLogin",
            targets=targets._replace(admin_console_url=None),
            browser_input=browser_input,
            run_id="run-20260808",
        )
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="browser acceptance attempt identity is invalid",
    ):
        MODULE.build_browser_probe_command(
            section="oidcWorkspace",
            targets=targets,
            browser_input=browser_input,
            run_id="../untrusted-attempt",
        )

    for section in ("workspaceLifecycle", "terminal", "http", "browser", "websocket"):
        transport_command = MODULE.build_browser_probe_command(
            section=section,
            targets=targets,
            browser_input=browser_input,
            run_id="run-20260808",
        )
        assert section not in MODULE.ORACLE_SECTIONS
        assert transport_command[-2:] == ["--workspace-id", targets.workspace_id]
        assert targets.workspace_id not in browser_input.read_text()

    browser_ca = tmp_path / "browser-ca.pem"
    browser_ca.write_text("CA bundle", encoding="utf-8")
    browser_ca.chmod(0o600)
    ca_command = MODULE.build_browser_probe_command(
        section="oidcWorkspace",
        targets=targets,
        browser_input=browser_input,
        browser_ca=browser_ca,
        run_id="run-20260808",
        image_reference=BROWSER_IMAGE_ID,
    )
    assert "update-ca-certificates" in " ".join(ca_command)
    assert (
        "NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/aileron-acceptance-ca.crt"
        in " ".join(ca_command)
    )
    assert "certutil -A" in " ".join(ca_command)
    assert any(
        item.startswith("type=bind,source=")
        and "target=/usr/local/share/ca-certificates/aileron-acceptance-ca.crt" in item
        for item in ca_command
    )
    assert browser_ca.read_text() not in " ".join(ca_command)

    external = MODULE.build_offline_oidc_conformance_command(targets, "run-20260808")
    assert external.command[-5:] == [
        "run",
        "--pull",
        "never",
        "--rm",
        "product-conformance-test",
    ]
    assert external.cleanup_command[-3:] == [
        "down",
        "--volumes",
        "--remove-orphans",
    ]

    dockerfile = (ROOT / "frontend/Dockerfile.playwright").read_text()
    assert (
        "mcr.microsoft.com/playwright@sha256:"
        "5b8f294aff9041b7191c34a4bab3ac270157a28774d4b0660e9743297b697e48"
    ) in dockerfile


def test_browser_provenance_rejects_a_dirty_checkout(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    with pytest.raises(MODULE.AcceptanceProducerError, match="clean Git checkout"):
        MODULE.verify_browser_probe_source(
            targets=targets,
            runner=Runner(
                {
                    tuple(MODULE.browser_git_status_command()): MODULE.CommandResult(
                        b" M frontend/e2e/acceptance.mjs\n", b"", 0
                    )
                }
            ),
        )


def test_subprocess_runner_terminates_a_hanging_acceptance_command() -> None:
    result = MODULE._subprocess_runner(
        ["python", "-c", "import time; time.sleep(60)"],
        timeout_seconds=0.01,
    )

    assert result.returncode == 124
    assert result.stdout == b""
    assert result.stderr == b"acceptance command timed out\n"


def test_browser_provenance_binds_head_and_tracked_script(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    tracked = (ROOT / "frontend/e2e/acceptance.mjs").read_bytes()
    commands = MODULE.browser_source_commands(targets.commit)
    runner = Runner(
        {
            tuple(commands[0]): MODULE.CommandResult(b"", b"", 0),
            tuple(commands[1]): MODULE.CommandResult(f"{COMMIT}\n".encode(), b"", 0),
            tuple(commands[2]): MODULE.CommandResult(tracked, b"", 0),
        }
    )

    assert MODULE.verify_browser_probe_source(targets=targets, runner=runner) == {
        "scriptSha256": hashlib.sha256(tracked).hexdigest(),
    }


def test_oidc_workspace_producer_runs_browser_lifecycle_and_adopts_created_identity(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    _write_canonical_browser_input(tmp_path)
    evidence = _evidence_directory(tmp_path)
    staged_input = evidence / ".browser-input-run-20260808.json"
    probe_observations = {
        "flow": "authorization-code-pkce",
        "createdWorkspaceId": "created-workspace",
        "userSubject": "created-subject",
    }
    probe_responses, probe_commands, tracked_script = _browser_probe_fixture(
        section="oidcWorkspace",
        targets=targets,
        evidence=evidence,
        observations=probe_observations,
    )
    tracked_script_text = tracked_script.decode()
    assert "/api/v1/oauth2/session" in tracked_script_text
    assert "X-CSRF-Token" in tracked_script_text
    assert "session.user.subject" in tracked_script_text
    assert "detail.owner?.id" in tracked_script_text

    def assert_minimal_staged_input() -> None:
        staged_document = json.loads(staged_input.read_text())
        staged_text = staged_input.read_text()
        assert set(staged_document) == {
            "schemaVersion",
            "loginDriver",
            "loginUser",
        }
        assert "break-glass-secret" not in staged_text
        assert "admin-secret" not in staged_text

    runner = Runner(
        {
            **_trust_responses(targets),
            **probe_responses,
        },
        effects={
            tuple(probe_commands[-1]): assert_minimal_staged_input,
        },
    )

    report_path = MODULE.produce(
        section="oidcWorkspace",
        targets=targets,
        deployment_run_id="run-20260808",
        runner=runner,
        run_id_factory=lambda: "run-20260808",
    )

    report = json.loads(report_path.read_text())
    assert report["workspace"] == {
        "id": "created-workspace",
        "userSubject": "created-subject",
    }
    assert [source["command"] for source in report["sources"]] == [
        *probe_commands,
    ]
    assert all(
        Path(source["file"]).name == source["file"]
        and source["file"].startswith("oidcWorkspace-run-20260808-browser-")
        for source in report["sources"]
    )
    assert report["observations"]["browserProbe"] == {
        "imageId": BROWSER_IMAGE_ID,
        "trackedScriptSha256": hashlib.sha256(tracked_script).hexdigest(),
        "imageScriptSha256": hashlib.sha256(tracked_script).hexdigest(),
        "exactSourceMatch": True,
    }
    validator = MODULE._load_validator()
    validated = validator.validate_report_file(
        directory=evidence,
        section="oidcWorkspace",
        contract=validator.load_canonical_contract(MODULE.CONTRACT_PATH),
        expected_commit=targets.commit,
        epoch=MODULE.ACCEPTANCE_EPOCH.load_deployment_epoch(directory=evidence),
        signing_key=KEY,
        private_root=tmp_path,
        canonical_kubeconfig=targets.kubeconfig,
        workspace=report["workspace"],
        now=datetime.now(timezone.utc),
    )
    assert validated["report"] == report
    assert not staged_input.exists()
    assert "native-secret" not in report_path.read_text()


def test_external_oidc_uses_provider_neutral_form_driver_without_admin_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    browser_input = _write_canonical_browser_input(
        tmp_path,
        document={
            "schemaVersion": "aileron-browser-input/v2",
            "loginDriver": {
                "kind": "form",
                "usernameSelector": "input[name='login']",
                "passwordSelector": "input[name='secret']",
                "submitSelector": "button[type='submit']",
                "errorSelector": "[role='alert']",
            },
            "loginUser": {
                "username": "external-user",
                "password": "external-secret",
            },
        },
    )
    observations = {
        "flow": "authorization-code-pkce",
        "createdWorkspaceId": "external-workspace",
        "userSubject": "external-subject",
    }
    probe_responses, _, _ = _browser_probe_fixture(
        section="oidcWorkspace",
        targets=targets,
        evidence=evidence,
        observations=observations,
    )
    monkeypatch.setattr(
        MODULE,
        "_installation_identity_mode",
        lambda _targets, _trust: "externalOidc",
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EPOCH,
        "load_deployment_epoch",
        lambda **_kwargs: {
            "deploymentRunId": "run-20260808",
            "authenticationMode": "externalOidc",
            "resetSnapshotSha256": "0" * 64,
        },
    )

    report_path = MODULE.produce(
        section="oidcWorkspace",
        targets=targets,
        deployment_run_id="run-20260808",
        runner=Runner({**_trust_responses(targets), **probe_responses}),
        run_id_factory=lambda: "run-20260808",
    )

    report = json.loads(report_path.read_text())
    assert report["authenticationMode"] == "externalOidc"
    assert report["workspace"] == {
        "id": "external-workspace",
        "userSubject": "external-subject",
    }
    assert "adminUser" not in browser_input.read_text()
    assert "breakGlassUser" not in browser_input.read_text()
    assert "platformAdminUser" not in browser_input.read_text()
    assert "#username" not in browser_input.read_text()
    assert "external-secret" not in report_path.read_text()


@pytest.mark.parametrize(
    ("cleanup_mode", "expected_error", "expect_inspect"),
    [
        pytest.param(
            "removed",
            "browser acceptance failed; diagnostics=",
            False,
            id="successful-removal",
        ),
        pytest.param(
            "already-absent",
            "browser acceptance failed; diagnostics=",
            True,
            id="verified-already-absent",
        ),
        pytest.param(
            "ambiguous-absence",
            "browser acceptance container cleanup failed",
            True,
            id="ambiguous-absence",
        ),
        pytest.param(
            "cleanup-failure",
            "browser acceptance container cleanup failed",
            False,
            id="real-cleanup-failure",
        ),
    ],
)
def test_browser_failure_requires_named_container_cleanup_and_removes_staged_secret(
    tmp_path: Path,
    cleanup_mode: str,
    expected_error: str,
    expect_inspect: bool,
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path)
    _write_canonical_browser_input(tmp_path)
    probe_responses, probe_commands, _ = _browser_probe_fixture(
        section="oidcWorkspace",
        targets=targets,
        evidence=evidence,
        observations={},
    )
    run_command = probe_commands[-1]
    probe_responses[tuple(run_command)] = MODULE.CommandResult(
        b'{"code":"BROWSER_TIMEOUT","stage":"login"}\n', b"", 124
    )
    container_cleanup, container_inspect, container_name = _browser_cleanup_commands(
        run_command
    )
    if cleanup_mode == "removed":
        probe_responses[tuple(container_cleanup)] = MODULE.CommandResult(
            f"{container_name}\n".encode(), b"", 0
        )
    elif cleanup_mode in {"already-absent", "ambiguous-absence"}:
        probe_responses[tuple(container_cleanup)] = _missing_container_result(
            container_name
        )
        probe_responses[tuple(container_inspect)] = (
            _missing_container_result(container_name)
            if cleanup_mode == "already-absent"
            else MODULE.CommandResult(b"", b"docker daemon response was ambiguous\n", 1)
        )
    else:
        probe_responses[tuple(container_cleanup)] = MODULE.CommandResult(
            b"",
            b"Error response from daemon: removal of container is already in progress\n",
            1,
        )
    runner = Runner({**_trust_responses(targets), **probe_responses})

    with pytest.raises(
        MODULE.AcceptanceProducerError, match=expected_error
    ) as captured:
        MODULE.produce(
            section="oidcWorkspace",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: "run-20260808",
        )
    if cleanup_mode in {"ambiguous-absence", "cleanup-failure"}:
        assert isinstance(captured.value.__cause__, MODULE.AcceptanceProducerError)
        assert "browser acceptance failed; diagnostics=" in str(
            captured.value.__cause__
        )

    unique_tag_cleanup = next(
        command
        for command in probe_commands
        if command[:4] == ["docker", "image", "rm", "--force"]
    )
    assert unique_tag_cleanup in runner.commands
    assert container_cleanup in runner.commands
    assert (container_inspect in runner.commands) is expect_inspect
    assert not (evidence / ".browser-input-run-20260808.json").exists()
    assert (evidence / "oidcWorkspace-run-20260808-browser-probe-cleanup.log").is_file()
    assert (
        evidence / "oidcWorkspace-run-20260808-browser-probe-cleanup-inspect.log"
    ).is_file() is expect_inspect
    diagnostics = "".join(
        path.read_text(errors="replace")
        for path in evidence.iterdir()
        if path.is_file()
    )
    assert "native-secret" not in diagnostics
    assert "break-glass-secret" not in diagnostics
    assert "admin-secret" not in diagnostics


def test_browser_failed_attempt_can_retry_without_reusing_evidence_bytes(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path)
    _write_canonical_browser_input(tmp_path)
    attempts: list[tuple[str, list[str]]] = []
    responses = {**_trust_responses(targets)}

    for sequence, run_id in enumerate(
        ("run-browser-attempt-1", "run-browser-attempt-2"), start=1
    ):
        probe_responses, probe_commands, _ = _browser_probe_fixture(
            section="browser",
            targets=targets,
            evidence=evidence,
            observations={},
            run_id=run_id,
        )
        run_command = probe_commands[-1]
        probe_responses[tuple(run_command)] = MODULE.CommandResult(
            f"browser attempt {sequence} failed\n".encode(), b"", 1
        )
        cleanup_command, inspect_command, container_name = _browser_cleanup_commands(
            run_command
        )
        probe_responses[tuple(cleanup_command)] = _missing_container_result(
            container_name
        )
        probe_responses[tuple(inspect_command)] = _missing_container_result(
            container_name
        )
        responses.update(probe_responses)
        attempts.append((run_id, run_command))

    runner = Runner(responses)
    first_run_id, first_probe = attempts[0]
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match=f"browser acceptance failed; diagnostics=browser-{first_run_id}-",
    ):
        MODULE.produce(
            section="browser",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: first_run_id,
        )

    first_prefix = f"browser-{first_run_id}-browser-"
    first_artifacts = {
        path.name: path.read_bytes()
        for path in evidence.iterdir()
        if path.name.startswith(first_prefix)
    }
    assert len(first_artifacts) == 9
    assert first_probe in runner.commands

    second_run_id, second_probe = attempts[1]
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match=f"browser acceptance failed; diagnostics=browser-{second_run_id}-",
    ):
        MODULE.produce(
            section="browser",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: second_run_id,
        )

    second_prefix = f"browser-{second_run_id}-browser-"
    second_artifacts = {
        path.name: path.read_bytes()
        for path in evidence.iterdir()
        if path.name.startswith(second_prefix)
    }
    assert len(second_artifacts) == 9
    assert second_probe in runner.commands
    assert set(first_artifacts).isdisjoint(second_artifacts)
    assert {
        name: (evidence / name).read_bytes() for name in first_artifacts
    } == first_artifacts
    assert not list(evidence.glob(".browser-input-*.json"))
    diagnostics = b"".join([*first_artifacts.values(), *second_artifacts.values()])
    for secret in (b"native-secret", b"break-glass-secret", b"admin-secret"):
        assert secret not in diagnostics


def test_staged_browser_input_unlink_failure_preserves_probe_failure_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path)
    staged_input = evidence / ".browser-input-run-20260808.json"
    _write_canonical_browser_input(tmp_path)
    probe_responses, probe_commands, _ = _browser_probe_fixture(
        section="oidcWorkspace",
        targets=targets,
        evidence=evidence,
        observations={},
    )
    run_command = probe_commands[-1]
    probe_responses[tuple(run_command)] = MODULE.CommandResult(b"failed\n", b"", 1)
    container_cleanup = [
        "docker",
        "rm",
        "--force",
        run_command[run_command.index("--name") + 1],
    ]
    probe_responses[tuple(container_cleanup)] = MODULE.CommandResult(b"", b"", 0)
    original_unlink = Path.unlink

    def fail_staged_unlink(path: Path, *args, **kwargs) -> None:
        if path == staged_input:
            raise OSError("simulated staged input unlink failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_staged_unlink)
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="short-lived browser acceptance input could not be removed",
    ) as captured:
        MODULE.produce(
            section="oidcWorkspace",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=Runner({**_trust_responses(targets), **probe_responses}),
            run_id_factory=lambda: "run-20260808",
        )

    assert isinstance(captured.value.__cause__, MODULE.AcceptanceProducerError)
    assert "browser acceptance failed; diagnostics=" in str(captured.value.__cause__)
    monkeypatch.setattr(Path, "unlink", original_unlink)
    staged_input.unlink()


def test_workspace_lifecycle_producer_runs_authenticated_ordered_browser_probe(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    _write_canonical_browser_input(tmp_path)
    evidence = _evidence_directory(tmp_path)
    staged_input = evidence / ".browser-input-run-20260808.json"
    probe_observations = {
        "componentsRestarted": ["runtime", "browser", "canvas"],
        "stopObserved": "stopped",
        "startObserved": "ready",
    }
    probe_responses, probe_commands, tracked_script = _browser_probe_fixture(
        section="workspaceLifecycle",
        targets=targets,
        evidence=evidence,
        observations=probe_observations,
    )
    tracked_script_text = tracked_script.decode()
    for route in (
        "/components/${component}/restart",
        "/stop",
        "/start",
        "/availability",
    ):
        assert route in tracked_script_text
    assert "status?.observedRevision === command.targetRevision" in tracked_script_text
    assert "availability.availability === 'stopped'" in tracked_script_text
    assert "availability.availability === 'ready'" in tracked_script_text
    runner = Runner(
        {
            **_trust_responses(targets),
            **probe_responses,
        }
    )

    report_path = MODULE.produce(
        section="workspaceLifecycle",
        targets=targets,
        deployment_run_id="run-20260808",
        runner=runner,
        run_id_factory=lambda: "run-20260808",
    )

    report = json.loads(report_path.read_text())
    assert report["observations"] == {
        "componentsRestarted": ["runtime", "browser", "canvas"],
        "stopObserved": "stopped",
        "startObserved": "ready",
        "browserProbe": {
            "imageId": BROWSER_IMAGE_ID,
            "trackedScriptSha256": hashlib.sha256(tracked_script).hexdigest(),
            "imageScriptSha256": hashlib.sha256(tracked_script).hexdigest(),
            "exactSourceMatch": True,
        },
    }
    assert probe_commands[-1][-2:] == ["--workspace-id", targets.workspace_id]
    assert "pvc" not in json.dumps(report["observations"]).lower()
    assert "podUid" not in report["observations"]
    assert not staged_input.exists()


def test_offline_oidc_conformance_never_claims_a_live_external_provider(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    source_root = _materialized_suite_root(
        evidence, "offlineOidcConformance", "run-20260808"
    )
    suite = MODULE.build_offline_oidc_conformance_command(
        targets, "run-20260808", source_root
    )
    inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
            tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
            tuple(
                MODULE._pin_suite_command(suite.command, BROWSER_IMAGE_ID)
            ): MODULE.CommandResult(b"90 conformance tests passed", b"", 0),
            tuple(
                MODULE._pin_suite_command(suite.cleanup_command, BROWSER_IMAGE_ID)
            ): MODULE.CommandResult(b"", b"", 0),
            tuple(inspect): MODULE.CommandResult(
                f"{BROWSER_IMAGE_ID}\tamd64\t{targets.commit}\n".encode(), b"", 0
            ),
            tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
        }
    )
    report_path = MODULE.produce(
        section="offlineOidcConformance",
        targets=targets,
        deployment_run_id="run-20260808",
        runner=runner,
        run_id_factory=lambda: "run-20260808",
    )

    report = json.loads(report_path.read_text())
    assert not source_root.exists()
    archive = evidence / "offlineOidcConformance-source-archive.tar.gz"
    assert archive.read_bytes() == b"suite archive fixture\n"
    assert archive.stat().st_mode & 0o777 == 0o600
    assert runner_cleanup in runner.commands
    assert not any("--force" in command for command in runner.commands)
    assert report["observations"] == {
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
        "cleanupCommand": MODULE._pin_suite_command(
            suite.cleanup_command, BROWSER_IMAGE_ID
        ),
        "cleaned": True,
        "runner": {
            "image": suite.runner_image,
            "imageId": BROWSER_IMAGE_ID,
            "architecture": "amd64",
            "sourceRevision": targets.commit,
            "buildCommand": suite.build_command,
            "inspectCommand": inspect,
        },
        "sourceProvenance": {
            "headCommit": targets.commit,
            "targetCommit": targets.commit,
            "worktreeClean": True,
            "untrackedFilesIncluded": True,
            "archiveSha256": hashlib.sha256(b"suite archive fixture\n").hexdigest(),
            "treeSha256": MATERIALIZED_SUITE_TREE_SHA256,
            "archiveCommand": [
                "git",
                "-C",
                str(ROOT),
                "archive",
                "--format=tar.gz",
                targets.commit,
            ],
            "materializedTreeReadOnly": True,
            "treeDigestChecks": 5,
        },
    }
    assert [source["command"] for source in report["sources"]] == [
        report["observations"]["sourceProvenance"]["archiveCommand"],
        MODULE._pin_suite_command(suite.command, BROWSER_IMAGE_ID),
    ]
    assert "workspace" not in report


@pytest.mark.parametrize(
    ("run_returncode", "cleanup_returncode", "expected_phases"),
    [
        (19, 0, ["run"]),
        (0, 23, ["cleanup"]),
    ],
)
def test_offline_oidc_failure_preserves_diagnostics_and_releases_owned_resources(
    tmp_path: Path,
    run_returncode: int,
    cleanup_returncode: int,
    expected_phases: list[str],
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    run_id = f"run-offline-{run_returncode}-{cleanup_returncode}"
    source_root = _materialized_suite_root(evidence, "offlineOidcConformance", run_id)
    suite = MODULE.build_offline_oidc_conformance_command(targets, run_id, source_root)
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    run_command = MODULE._pin_suite_command(suite.command, image_id)
    compose_cleanup = MODULE._pin_suite_command(suite.cleanup_command, image_id)
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
            tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
            tuple(inspect_command): MODULE.CommandResult(
                f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
            ),
            tuple(run_command): MODULE.CommandResult(
                b"run-stream-marker", b"run-error-marker", run_returncode
            ),
            tuple(compose_cleanup): MODULE.CommandResult(
                b"cleanup-stream-marker",
                b"cleanup-error-marker",
                cleanup_returncode,
            ),
            tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
        }
    )

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="offlineOidcConformance",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"offlineOidcConformance-{run_id}-failure.json"
    artifact_raw = artifact.read_bytes()
    document = json.loads(artifact_raw)
    assert [failure["phase"] for failure in document["failures"]] == expected_phases
    assert artifact_raw == (
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert not source_root.exists()
    archive = evidence / "offlineOidcConformance-source-archive.tar.gz"
    assert archive.read_bytes() == b"suite archive fixture\n"
    assert archive.stat().st_mode & 0o777 == 0o600
    assert not (evidence / "offlineOidcConformance.json").exists()
    assert runner_cleanup in runner.commands
    assert [
        command
        for command in runner.commands
        if command[:3] == ["docker", "image", "rm"]
    ] == [runner_cleanup]
    assert captured.value.artifact == {
        "file": artifact.name,
        "sha256": hashlib.sha256(artifact_raw).hexdigest(),
    }
    error_text = str(captured.value)
    for marker in (
        "run-stream-marker",
        "run-error-marker",
        "cleanup-stream-marker",
        "cleanup-error-marker",
    ):
        assert marker not in error_text


def test_materialized_source_cleanup_failure_blocks_success_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-offline-source-cleanup-failure"
    source_root = _materialized_suite_root(evidence, "offlineOidcConformance", run_id)
    suite = MODULE.build_offline_oidc_conformance_command(targets, run_id, source_root)
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
            tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
            tuple(inspect_command): MODULE.CommandResult(
                f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
            ),
            tuple(MODULE._pin_suite_command(suite.command, image_id)): (
                MODULE.CommandResult(b"90 conformance tests passed", b"", 0)
            ),
            tuple(MODULE._pin_suite_command(suite.cleanup_command, image_id)): (
                MODULE.CommandResult(b"", b"", 0)
            ),
            tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
        }
    )

    def fail_remove(path: Path) -> None:
        assert path == source_root
        raise OSError("filesystem detail must not escape")

    monkeypatch.setattr(MODULE.shutil, "rmtree", fail_remove)

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="^materialized suite source cleanup failed$",
    ) as captured:
        MODULE.produce(
            section="offlineOidcConformance",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    assert "filesystem detail" not in str(captured.value)
    assert source_root.is_dir()
    assert (evidence / "offlineOidcConformance-source-archive.tar.gz").is_file()
    assert not (evidence / "offlineOidcConformance.json").exists()
    assert runner_cleanup in runner.commands


def test_materialized_source_files_are_readable_by_nonroot_bind_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        MODULE, "_materialize_suite_source", REAL_MATERIALIZE_SUITE_SOURCE
    )
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_id = "run-20260808"
    archive_command = [
        "git",
        "-C",
        str(ROOT),
        "archive",
        "--format=tar.gz",
        targets.commit,
    ]
    archive_buffer = MODULE.io.BytesIO()
    with MODULE.tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        init_directory = MODULE.tarfile.TarInfo("init-sql/")
        init_directory.type = MODULE.tarfile.DIRTYPE
        init_directory.mode = 0o755
        archive.addfile(init_directory)
        schema = b"create table fixture (id integer);\n"
        schema_file = MODULE.tarfile.TarInfo("init-sql/001_init_schema.sql")
        schema_file.mode = 0o644
        schema_file.size = len(schema)
        archive.addfile(schema_file, MODULE.io.BytesIO(schema))
    source = MODULE._materialize_suite_source(
        targets=targets,
        directory=evidence,
        run_id=run_id,
        section="suites",
        runner=Runner(
            {
                tuple(archive_command): MODULE.CommandResult(
                    archive_buffer.getvalue(), b"", 0
                )
            }
        ),
    )
    try:
        assert source.root.stat().st_mode & 0o777 == 0o700
        assert (source.root / "init-sql").stat().st_mode & 0o777 == 0o500
        assert (
            source.root / "init-sql/001_init_schema.sql"
        ).stat().st_mode & 0o777 == 0o444
    finally:
        MODULE._remove_materialized_suite_source(
            source=source,
            directory=evidence,
            section="suites",
            run_id=run_id,
        )


def test_suite_failure_retry_reuses_exact_archive_with_attempt_scoped_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        MODULE, "_materialize_suite_source", REAL_MATERIALIZE_SUITE_SOURCE
    )
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    archive_command = [
        "git",
        "-C",
        str(ROOT),
        "archive",
        "--format=tar.gz",
        targets.commit,
    ]
    archive_raw = _suite_archive_fixture(b"exact retry source\n")
    archive_path = evidence / "suites-source-archive.tar.gz"
    attempt_ids = ("run-suite-retry-first", "run-suite-retry-second")
    source_roots = [
        _materialized_suite_root(evidence, "suites", attempt_id)
        for attempt_id in attempt_ids
    ]
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(archive_command): MODULE.CommandResult(archive_raw, b"", 0),
    }
    effects: dict[tuple[str, ...], Callable[[], None]] = {}
    observed_roots: list[Path] = []

    def observe_materialization(root: Path) -> Callable[[], None]:
        def observe() -> None:
            assert root.is_dir()
            assert archive_path.read_bytes() == archive_raw
            observed_roots.append(root)

        return observe

    for attempt_id, source_root in zip(attempt_ids, source_roots):
        suite = MODULE.build_suite_commands(targets, attempt_id, source_root)[0]
        responses[tuple(suite.build_command)] = MODULE.CommandResult(
            b"build failed", b"cache exhausted", 33
        )
        responses[
            tuple(MODULE._pin_suite_command(suite.cleanup_command, suite.runner_image))
        ] = MODULE.CommandResult(b"", b"", 0)
        effects[tuple(suite.build_command)] = observe_materialization(source_root)

    runner = Runner(responses, effects)

    def run_failed_attempt(attempt_id: str) -> Path:
        with pytest.raises(MODULE.SuiteExecutionError) as captured:
            MODULE.produce(
                section="suites",
                targets=targets,
                deployment_run_id="run-20260808",
                image_inventory=inventory,
                runner=runner,
                run_id_factory=lambda: attempt_id,
            )
        artifact = evidence / f"suites-{attempt_id}-failure.json"
        assert captured.value.artifact["file"] == artifact.name
        assert json.loads(artifact.read_bytes())["attemptId"] == attempt_id
        return artifact

    first_artifact = run_failed_attempt(attempt_ids[0])
    first_artifact_raw = first_artifact.read_bytes()
    second_artifact = run_failed_attempt(attempt_ids[1])

    assert first_artifact != second_artifact
    assert first_artifact.read_bytes() == first_artifact_raw
    assert observed_roots == source_roots
    assert source_roots[0] != source_roots[1]
    assert all(not root.exists() for root in source_roots)
    assert archive_path.read_bytes() == archive_raw
    assert archive_path.stat().st_mode & 0o777 == 0o600
    assert runner.commands.count(archive_command) == 2


def test_materialized_source_retry_rejects_changed_canonical_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        MODULE, "_materialize_suite_source", REAL_MATERIALIZE_SUITE_SOURCE
    )
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    archive_command = [
        "git",
        "-C",
        str(ROOT),
        "archive",
        "--format=tar.gz",
        targets.commit,
    ]
    original_archive = _suite_archive_fixture(b"original source\n")
    changed_archive = _suite_archive_fixture(b"changed source\n")
    first_run_id = "run-suite-original-archive"
    first_source = MODULE._materialize_suite_source(
        targets=targets,
        directory=evidence,
        run_id=first_run_id,
        section="suites",
        runner=Runner(
            {tuple(archive_command): MODULE.CommandResult(original_archive, b"", 0)}
        ),
    )
    MODULE._remove_materialized_suite_source(
        source=first_source,
        directory=evidence,
        section="suites",
        run_id=first_run_id,
    )

    retry_run_id = "run-suite-changed-archive"
    retry_root = _materialized_suite_root(evidence, "suites", retry_run_id)
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="^acceptance evidence snapshot content changed$",
    ):
        MODULE._materialize_suite_source(
            targets=targets,
            directory=evidence,
            run_id=retry_run_id,
            section="suites",
            runner=Runner(
                {tuple(archive_command): MODULE.CommandResult(changed_archive, b"", 0)}
            ),
        )

    archive_path = evidence / "suites-source-archive.tar.gz"
    assert archive_path.read_bytes() == original_archive
    assert archive_path.stat().st_mode & 0o777 == 0o600
    assert not retry_root.exists()


@pytest.mark.parametrize("failure_phase", ["archiveExtraction", "treeHash"])
def test_materialize_failure_and_cleanup_failure_are_safely_aggregated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_phase: str,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    run_id = f"run-materialize-{failure_phase.lower()}"
    source_root = _materialized_suite_root(evidence, "offlineOidcConformance", run_id)
    archive_command = [
        "git",
        "-C",
        str(ROOT),
        "archive",
        "--format=tar.gz",
        targets.commit,
    ]
    archive_buffer = MODULE.io.BytesIO()
    with MODULE.tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        directory = MODULE.tarfile.TarInfo("readonly")
        directory.type = MODULE.tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        content = b"immutable source\n"
        tracked = MODULE.tarfile.TarInfo("readonly/tracked.txt")
        tracked.mode = 0o644
        tracked.size = len(content)
        archive.addfile(tracked, MODULE.io.BytesIO(content))

    monkeypatch.setattr(
        MODULE, "_materialize_suite_source", REAL_MATERIALIZE_SUITE_SOURCE
    )
    if failure_phase == "archiveExtraction":

        def fail_extract(
            _archive,
            path,
            *_args,
            **_kwargs,
        ) -> None:
            partial = Path(path) / "partial"
            partial.mkdir(mode=0o500)
            raise OSError("archive extraction sensitive detail")

        monkeypatch.setattr(MODULE.tarfile.TarFile, "extractall", fail_extract)
    else:
        monkeypatch.setattr(
            MODULE,
            "_suite_tree_sha256",
            lambda _root: (_ for _ in ()).throw(OSError("tree hash sensitive detail")),
        )

    def fail_remove(path: Path, *args, **kwargs) -> None:
        assert path == source_root
        if kwargs.get("ignore_errors") is True:
            return
        raise OSError("cleanup sensitive detail")

    monkeypatch.setattr(MODULE.shutil, "rmtree", fail_remove)
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
            tuple(archive_command): MODULE.CommandResult(
                archive_buffer.getvalue(), b"", 0
            ),
        }
    )

    with pytest.raises(MODULE.AcceptanceProducerError) as captured:
        MODULE.produce(
            section="offlineOidcConformance",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    prefix = "materialized suite source transaction failed: "
    assert str(captured.value).startswith(prefix)
    assert json.loads(str(captured.value)[len(prefix) :]) == {
        "failures": [
            {"errorType": "OSError", "phase": "materialization"},
            {
                "errorType": "AcceptanceProducerError",
                "phase": "materializedSourceCleanup",
            },
        ]
    }
    assert source_root.is_dir()
    assert (evidence / "offlineOidcConformance-source-archive.tar.gz").is_file()
    assert not (evidence / "offlineOidcConformance.json").exists()
    assert "sensitive detail" not in str(captured.value)


@pytest.mark.parametrize("section", ["suites", "offlineOidcConformance"])
def test_suite_failure_and_materialized_cleanup_failure_preserve_artifact_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    evidence = _evidence_directory(tmp_path)
    run_id = f"run-{section.lower()}-source-cleanup"
    source_root = _materialized_suite_root(evidence, section, run_id)
    suite = (
        MODULE.build_suite_commands(targets, run_id, source_root)[0]
        if section == "suites"
        else MODULE.build_offline_oidc_conformance_command(targets, run_id, source_root)
    )
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    run_command = MODULE._pin_suite_command(suite.command, image_id)
    compose_cleanup = MODULE._pin_suite_command(suite.cleanup_command, image_id)
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect_command): MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(run_command): MODULE.CommandResult(
            b"primary stream marker", b"primary error marker", 17
        ),
        tuple(compose_cleanup): MODULE.CommandResult(b"", b"", 0),
        tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
    }
    if suite.preflight_command is not None:
        responses[tuple(suite.preflight_command)] = MODULE.CommandResult(b"", b"", 0)
    runner = Runner(responses)

    def fail_remove(path: Path) -> None:
        assert path == source_root
        raise OSError("materialized cleanup sensitive detail")

    monkeypatch.setattr(MODULE.shutil, "rmtree", fail_remove)
    produce_arguments = {
        "section": section,
        "targets": targets,
        "deployment_run_id": "run-20260808",
        "runner": runner,
        "run_id_factory": lambda: run_id,
    }
    if section == "suites":
        produce_arguments["image_inventory"] = _signed_inventory(tmp_path, targets)

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(**produce_arguments)

    artifact = evidence / f"{section}-{run_id}-failure.json"
    artifact_raw = artifact.read_bytes()
    assert captured.value.suite_name == suite.name
    assert captured.value.artifact == {
        "file": artifact.name,
        "sha256": hashlib.sha256(artifact_raw).hexdigest(),
    }
    assert captured.value.failures == [
        {
            "errorType": "AcceptanceProducerError",
            "phase": "run",
            "exitCode": 17,
            "message": "fixed acceptance probe failed",
        },
        {
            "errorType": "AcceptanceProducerError",
            "phase": "materializedSourceCleanup",
        },
    ]
    assert [failure["phase"] for failure in json.loads(artifact_raw)["failures"]] == [
        "run"
    ]
    assert source_root.is_dir()
    assert not (evidence / f"{section}.json").exists()
    error_text = str(captured.value)
    assert artifact.name in error_text
    for marker in (
        "primary stream marker",
        "primary error marker",
        "materialized cleanup sensitive detail",
    ):
        assert marker not in error_text


def test_turn_oracle_projects_non_root_probe_credentials_without_values(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )

    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    pod_spec = manifest["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert pod_spec["securityContext"]["fsGroup"] == 10001
    assert pod_spec["securityContext"]["fsGroupChangePolicy"] == "OnRootMismatch"
    assert pod_spec["volumes"] == [
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
    assert container["volumeMounts"] == [
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
    serialized = json.dumps(manifest)
    assert "/run/secrets/turn-probe" in serialized
    assert "turn-rest-shared-secret-value" not in serialized
    assert (
        manifest["metadata"]["labels"]["platform.aileron.dev/deployment-run-id"]
        == "run-deployment-epoch"
    )


def test_oracle_job_manifest_is_explicitly_code_owned(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )

    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )

    assert (
        manifest["metadata"]["labels"]["platform.aileron.dev/acceptance-owner"]
        == "aileron-installer"
    )
    token = manifest["metadata"]["annotations"][
        MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION
    ]
    assert MODULE.FILE_DIGEST.fullmatch(token) is not None
    assert (
        MODULE.build_oracle_job_manifest(
            section="turn",
            targets=targets,
            image=image,
            run_id="run-20260808",
            deployment_run_id="run-deployment-epoch",
            signing_key=KEY,
        )["metadata"]["annotations"][MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION]
        == token
    )
    other_key_token = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=b"x" * 32,
    )["metadata"]["annotations"][MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION]
    other_context_token = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets._replace(context="rke2-other"),
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )["metadata"]["annotations"][MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION]
    assert len({token, other_key_token, other_context_token}) == 3


def test_workspace_oracle_cleanup_selector_is_workspace_closed(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)

    selector = MODULE._oracle_cleanup_selector(
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
    )

    assert (
        f"platform.aileron.dev/workspace-id={targets.workspace_id}"
        in selector.split(",")
    )


def _owned_stale_oracle_fixture(
    tmp_path: Path,
    *,
    run_id: str = "run-stale-turn01",
    job_uid: str = "stale-oracle-job-uid",
) -> tuple[object, dict, dict, dict]:
    targets = _targets(tmp_path)
    image = {"immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64}
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id=run_id,
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, _ = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job_uid,
    )
    job["status"] = {"active": 1}
    inventory = {"apiVersion": "v1", "kind": "List", "items": [job]}
    return targets, image, manifest, inventory


def test_owned_stale_oracle_inventory_accepts_a_canonical_running_job(
    tmp_path: Path,
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)

    assert MODULE._owned_oracle_jobs(
        document=inventory,
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
        namespace="workspace-system",
        image=image,
        signing_key=KEY,
    ) == [(manifest["metadata"]["name"], "stale-oracle-job-uid", manifest)]


@pytest.mark.parametrize(
    "attack",
    [
        "invalid-list-root",
        "duplicate-name",
        "duplicate-uid",
        "foreign-token",
    ],
)
def test_owned_stale_oracle_inventory_rejects_ambiguous_or_foreign_jobs(
    tmp_path: Path, attack: str
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    job = inventory["items"][0]
    if attack == "invalid-list-root":
        inventory.pop("kind")
    elif attack == "duplicate-name":
        duplicate, _ = _server_oracle_resources(
            manifest,
            image["immutableImage"],
            "other-stale-oracle-job-uid",
        )
        inventory["items"].append(duplicate)
    elif attack == "duplicate-uid":
        other_manifest = MODULE.build_oracle_job_manifest(
            section="turn",
            targets=targets,
            image=image,
            run_id="run-other-turn02",
            deployment_run_id="run-deployment-epoch",
            signing_key=KEY,
        )
        duplicate, _ = _server_oracle_resources(
            other_manifest,
            image["immutableImage"],
            "stale-oracle-job-uid",
        )
        inventory["items"].append(duplicate)
    else:
        job["metadata"]["annotations"][MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION] = (
            "f" * 64
        )

    with pytest.raises(MODULE.AcceptanceProducerError, match="inventory"):
        MODULE._owned_oracle_jobs(
            document=inventory,
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
            namespace="workspace-system",
            image=image,
            signing_key=KEY,
        )


@pytest.mark.parametrize(
    "attack",
    ["privileged-sidecar", "host-path", "changed-command"],
)
def test_owned_stale_oracle_inventory_keeps_cleanup_identity_despite_spec_drift(
    tmp_path: Path, attack: str
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    job = inventory["items"][0]
    if attack == "privileged-sidecar":
        job["spec"]["template"]["spec"]["containers"].append(
            {
                "name": "sidecar",
                "image": "busybox",
                "securityContext": {"privileged": True},
            }
        )
    elif attack == "host-path":
        job["spec"]["template"]["spec"]["volumes"] = [
            {"name": "host", "hostPath": {"path": "/", "type": "Directory"}}
        ]
    else:
        job["spec"]["template"]["spec"]["containers"][0]["command"] = [
            "/bin/sh",
            "-c",
            "true",
        ]

    assert MODULE._owned_oracle_jobs(
        document=inventory,
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
        namespace="workspace-system",
        image=image,
        signing_key=KEY,
    ) == [(manifest["metadata"]["name"], "stale-oracle-job-uid", manifest)]


@pytest.mark.parametrize(
    ("root_key", "root_value"),
    [
        ("apiVersion", "batch/v1"),
        ("kind", "PodList"),
    ],
)
def test_oracle_delete_rejects_noncanonical_empty_pod_inventory(
    tmp_path: Path,
    root_key: str,
    root_value: str,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    evidence = tmp_path / "oracle-delete-evidence"
    evidence.mkdir(mode=0o700)
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        "rke2-homelab",
        "--namespace",
        "workspace-system",
    ]
    name = manifest["metadata"]["name"]
    uid = inventory["items"][0]["metadata"]["uid"]
    pod_command = [
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
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'
    pod_inventory = {"apiVersion": "v1", "kind": "List", "items": []}
    pod_inventory[root_key] = root_value
    runner = Runner(
        {
            tuple(pod_command): MODULE.CommandResult(
                json.dumps(pod_inventory).encode(), b"", 0
            ),
            tuple(name_pod_command): MODULE.CommandResult(empty, b"", 0),
            tuple(exact_jobs): MODULE.CommandResult(empty, b"", 0),
        }
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match="Pod inventory"):
        MODULE._delete_oracle_job(
            manifest=manifest,
            kubectl=kubectl,
            directory=evidence,
            uid=uid,
            source_prefix="turn-stale-job-0000",
            delete_client=NullKubernetesDeleteClient(),
            runner=runner,
        )
    assert list(evidence.iterdir()) == []


def test_oracle_delete_uses_live_resource_version_and_rest_preconditions(
    tmp_path: Path,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    evidence = tmp_path / "oracle-rest-delete-evidence"
    evidence.mkdir(mode=0o700)
    job = inventory["items"][0]
    job["metadata"]["resourceVersion"] = "101"
    name = job["metadata"]["name"]
    uid = job["metadata"]["uid"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'
    closure_commands = [
        MODULE._oracle_exact_job_inventory_command(kubectl=kubectl, name=name),
        [
            *kubectl,
            "get",
            "pods",
            f"--selector=batch.kubernetes.io/controller-uid={uid}",
            "--output=json",
        ],
        [
            *kubectl,
            "get",
            "pods",
            f"--selector=batch.kubernetes.io/job-name={name}",
            "--output=json",
        ],
    ]
    runner = Runner(
        {
            tuple(command): MODULE.CommandResult(empty, b"", 0)
            for command in closure_commands
        }
    )

    class DeleteClient:
        def __init__(self) -> None:
            self.get_calls: list[dict] = []
            self.delete_calls: list[dict] = []

        def get(self, **kwargs):
            self.get_calls.append(kwargs)
            return job

        def delete(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    delete_client = DeleteClient()

    MODULE._delete_oracle_job(
        manifest=manifest,
        kubectl=kubectl,
        directory=evidence,
        uid=uid,
        source_prefix="turn-stale-job-0000",
        delete_client=delete_client,
        runner=runner,
    )

    identity = {
        "api_version": "batch/v1",
        "resource": "jobs",
        "namespace": "workspace-system",
        "name": name,
    }
    assert delete_client.get_calls == [identity]
    assert delete_client.delete_calls == [
        {**identity, "uid": uid, "resource_version": "101"}
    ]
    assert not any("delete" in command for command in runner.commands)
    assert runner.commands == [
        closure_commands[0],
        closure_commands[1],
        closure_commands[2],
        closure_commands[0],
    ]


def test_oracle_rest_delete_polls_terminating_job_and_pods_until_absent(
    tmp_path: Path,
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    job = inventory["items"][0]
    _unused_job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job["metadata"]["uid"],
    )
    for resource in (job, pod):
        resource["metadata"]["deletionTimestamp"] = "2026-08-11T07:00:00Z"
    evidence = tmp_path / "oracle-delete-poll-evidence"
    evidence.mkdir(mode=0o700)
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]

    def inventory_result(items: list[dict]) -> MODULE.CommandResult:
        return MODULE.CommandResult(
            json.dumps({"apiVersion": "v1", "kind": "List", "items": items}).encode(),
            b"",
            0,
        )

    empty = inventory_result([])
    responses = {
        tuple(exact_jobs): [
            inventory_result([job]),
            inventory_result([job]),
            inventory_result([job]),
            inventory_result([job]),
            empty,
            empty,
        ],
        tuple(uid_pods): [inventory_result([pod]), inventory_result([pod]), empty],
        tuple(name_pods): [inventory_result([pod]), inventory_result([pod]), empty],
    }
    commands: list[list[str]] = []

    def runner(command: list[str], timeout_seconds: float | None = None):
        commands.append(command)
        return responses[tuple(command)].pop(0)

    class DeleteClient:
        def __init__(self) -> None:
            self.delete_calls: list[dict] = []

        def get(self, **_kwargs):
            return job

        def delete(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    delete_client = DeleteClient()
    sleeps: list[float] = []

    sources = MODULE._delete_oracle_job(
        manifest=manifest,
        kubectl=kubectl,
        directory=evidence,
        uid=uid,
        source_prefix="turn-completed-job",
        delete_client=delete_client,
        runner=runner,
        sleeper=sleeps.append,
        closure_timeout_seconds=120,
        closure_poll_interval_seconds=2,
    )

    assert len(delete_client.delete_calls) == 1
    assert sleeps == [2, 2]
    assert commands == [exact_jobs, uid_pods, name_pods, exact_jobs] * 3
    assert {source["file"] for source in sources} == {
        "turn-completed-job-job-before-pods-zero.json",
        "turn-completed-job-pods-uid-zero.json",
        "turn-completed-job-pods-name-zero.json",
        "turn-completed-job-job-zero.json",
    }
    assert all(
        (evidence / source["file"]).read_bytes() == empty.stdout for source in sources
    )


def test_oracle_rest_delete_times_out_when_owned_resources_never_disappear(
    tmp_path: Path,
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    job = inventory["items"][0]
    _unused_job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job["metadata"]["uid"],
    )
    for resource in (job, pod):
        resource["metadata"]["deletionTimestamp"] = "2026-08-11T07:00:00Z"
    evidence = tmp_path / "oracle-delete-timeout-evidence"
    evidence.mkdir(mode=0o700)
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    documents = {
        tuple(exact_jobs): {"apiVersion": "v1", "kind": "List", "items": [job]},
        tuple(uid_pods): {"apiVersion": "v1", "kind": "List", "items": [pod]},
        tuple(name_pods): {"apiVersion": "v1", "kind": "List", "items": [pod]},
    }
    commands: list[list[str]] = []

    def runner(command: list[str], timeout_seconds: float | None = None):
        commands.append(command)
        return MODULE.CommandResult(
            json.dumps(documents[tuple(command)]).encode(), b"", 0
        )

    class DeleteClient:
        def __init__(self) -> None:
            self.delete_calls: list[dict] = []

        def get(self, **_kwargs):
            return job

        def delete(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    delete_client = DeleteClient()
    sleeps: list[float] = []

    with pytest.raises(MODULE.OracleDeleteClosureError, match="timed out"):
        MODULE._delete_oracle_job(
            manifest=manifest,
            kubectl=kubectl,
            directory=evidence,
            uid=uid,
            source_prefix="turn-completed-job",
            delete_client=delete_client,
            runner=runner,
            sleeper=sleeps.append,
            closure_timeout_seconds=2,
            closure_poll_interval_seconds=1,
        )

    assert len(delete_client.delete_calls) == 1
    assert sleeps == [1, 1]
    assert commands == [exact_jobs, uid_pods, name_pods, exact_jobs] * 3
    assert list(evidence.iterdir()) == []


def test_oracle_reconcile_does_not_retry_an_accepted_delete_closure_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    uid = inventory["items"][0]["metadata"]["uid"]
    delete_calls = 0

    monkeypatch.setattr(
        MODULE,
        "_recover_created_oracle_job_uid",
        lambda **_kwargs: uid,
    )

    def fail_closure(**_kwargs):
        nonlocal delete_calls
        delete_calls += 1
        raise MODULE.OracleDeleteClosureError("oracle Job deletion closure timed out")

    monkeypatch.setattr(MODULE, "_delete_oracle_job", fail_closure)

    with pytest.raises(MODULE.OracleTransactionFailure) as error:
        MODULE._reconcile_failed_oracle_transaction(
            manifest=manifest,
            kubectl=[
                "kubectl",
                "--kubeconfig",
                str(targets.kubeconfig),
                "--context",
                targets.context,
                "--namespace",
                "workspace-system",
            ],
            directory=tmp_path,
            created_uid=uid,
            source_prefix="turn-failed-job",
            delete_client=NullKubernetesDeleteClient(),
            runner=lambda _command: MODULE.CommandResult(b"", b"", 0),
        )

    assert delete_calls == 1
    assert [phase for phase, _failure in error.value.failures] == ["cleanup-1"]


@pytest.mark.parametrize("attack", ["replacement", "foreign-token", "resource-version"])
def test_oracle_rest_delete_rejects_unbound_live_identity_without_deleting(
    tmp_path: Path,
    attack: str,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    live_job = json.loads(json.dumps(inventory["items"][0]))
    live_job["metadata"]["resourceVersion"] = "101"
    if attack == "replacement":
        live_job["metadata"]["uid"] = "replacement-job-uid"
    elif attack == "foreign-token":
        live_job["metadata"]["annotations"][
            MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION
        ] = ("f" * 64)
    else:
        live_job["metadata"]["resourceVersion"] = "invalid resource version"

    class DeleteClient:
        def __init__(self) -> None:
            self.delete_calls: list[dict] = []

        def get(self, **_kwargs):
            return live_job

        def delete(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    delete_client = DeleteClient()
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]

    with pytest.raises(MODULE.AcceptanceProducerError):
        MODULE._delete_oracle_job(
            manifest=manifest,
            kubectl=kubectl,
            directory=tmp_path,
            uid=(
                inventory["items"][0]["metadata"]["uid"]
                if attack != "replacement"
                else "stale-oracle-job-uid"
            ),
            source_prefix="turn-stale-job-0000",
            delete_client=delete_client,
            runner=lambda _command: (_ for _ in ()).throw(
                AssertionError("closure must not run")
            ),
        )

    assert delete_client.delete_calls == []


@pytest.mark.parametrize("attack", ["replacement", "foreign-token"])
def test_oracle_rest_delete_stops_on_foreign_closure_without_redeleting(
    tmp_path: Path,
    attack: str,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    live_job = inventory["items"][0]
    closure_job = json.loads(json.dumps(live_job))
    closure_job["metadata"]["deletionTimestamp"] = "2026-08-11T07:00:00Z"
    if attack == "replacement":
        closure_job["metadata"]["uid"] = "replacement-job-uid"
    else:
        closure_job["metadata"]["annotations"][
            MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION
        ] = ("f" * 64)
    evidence = tmp_path / "oracle-delete-foreign-closure-evidence"
    evidence.mkdir(mode=0o700)
    name = manifest["metadata"]["name"]
    uid = live_job["metadata"]["uid"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    empty = {"apiVersion": "v1", "kind": "List", "items": []}
    documents = {
        tuple(exact_jobs): {
            "apiVersion": "v1",
            "kind": "List",
            "items": [closure_job],
        },
        tuple(uid_pods): empty,
        tuple(name_pods): empty,
    }
    commands: list[list[str]] = []

    def runner(command: list[str], timeout_seconds: float | None = None):
        commands.append(command)
        return MODULE.CommandResult(
            json.dumps(documents[tuple(command)]).encode(), b"", 0
        )

    class DeleteClient:
        def __init__(self) -> None:
            self.delete_calls: list[dict] = []

        def get(self, **_kwargs):
            return live_job

        def delete(self, **kwargs) -> None:
            self.delete_calls.append(kwargs)

    delete_client = DeleteClient()
    sleeps: list[float] = []

    with pytest.raises(MODULE.OracleDeleteClosureError, match="foreign|replaced"):
        MODULE._delete_oracle_job(
            manifest=manifest,
            kubectl=kubectl,
            directory=evidence,
            uid=uid,
            source_prefix="turn-completed-job",
            delete_client=delete_client,
            runner=runner,
            sleeper=sleeps.append,
        )

    assert len(delete_client.delete_calls) == 1
    assert sleeps == []
    assert commands == [exact_jobs]
    assert list(evidence.iterdir()) == []


def test_oracle_delete_rejects_an_exact_job_aba_after_pods_are_gone(
    tmp_path: Path,
) -> None:
    targets, _image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    evidence = tmp_path / "oracle-delete-job-evidence"
    evidence.mkdir(mode=0o700)
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        "rke2-homelab",
        "--namespace",
        "workspace-system",
    ]
    name = manifest["metadata"]["name"]
    uid = inventory["items"][0]["metadata"]["uid"]
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'
    exact_reads = 0

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal exact_reads
        if command in (uid_pods, name_pods):
            return MODULE.CommandResult(empty, b"", 0)
        if command == exact_jobs:
            exact_reads += 1
            return MODULE.CommandResult(
                (
                    empty
                    if exact_reads == 1
                    else b'{"apiVersion":"v1","kind":"List","items":[{}]}'
                ),
                b"",
                0,
            )
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(MODULE.AcceptanceProducerError, match="foreign transaction"):
        MODULE._delete_oracle_job(
            manifest=manifest,
            kubectl=kubectl,
            directory=evidence,
            uid=uid,
            source_prefix="turn-stale-job-0000",
            delete_client=NullKubernetesDeleteClient(),
            runner=runner,
        )

    assert exact_reads == 2
    assert list(evidence.iterdir()) == []


def test_oracle_cleanup_does_not_publish_unvalidated_stale_inventory(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "oracle-stale-evidence"
    evidence.mkdir(mode=0o700)
    image = {"immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64}
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    selector = MODULE._oracle_cleanup_selector(
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
    )
    inventory_command = [
        *kubectl,
        "get",
        "jobs",
        f"--selector={selector}",
        "--output=json",
    ]
    runner = Runner(
        {
            tuple(inventory_command): MODULE.CommandResult(
                b'{"apiVersion":"v1","kind":"JobList","items":[]}',
                b"",
                0,
            )
        }
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match="inventory"):
        MODULE._cleanup_stale_oracle_jobs(
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
            namespace="workspace-system",
            kubectl=kubectl,
            directory=evidence,
            image=image,
            signing_key=KEY,
            delete_client=NullKubernetesDeleteClient(),
            runner=runner,
        )

    assert list(evidence.iterdir()) == []


def test_oracle_cleanup_rejects_owned_orphan_pod_when_job_inventory_is_empty(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "oracle-orphan-evidence"
    evidence.mkdir(mode=0o700)
    image = {"immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64}
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    selector = MODULE._oracle_cleanup_selector(
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
    )
    job_command = [
        *kubectl,
        "get",
        "jobs",
        f"--selector={selector}",
        "--output=json",
    ]
    pod_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector={selector}",
        "--output=json",
    ]
    runner = Runner(
        {
            tuple(job_command): MODULE.CommandResult(
                b'{"apiVersion":"v1","kind":"List","items":[]}', b"", 0
            ),
            tuple(pod_command): MODULE.CommandResult(
                b'{"apiVersion":"v1","kind":"List","items":'
                b'[{"metadata":{"name":"orphan"}}]}',
                b"",
                0,
            ),
        }
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match="nonempty"):
        MODULE._cleanup_stale_oracle_jobs(
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
            namespace="workspace-system",
            kubectl=kubectl,
            directory=evidence,
            image=image,
            signing_key=KEY,
            delete_client=NullKubernetesDeleteClient(),
            runner=runner,
        )

    assert not any("delete" in command for command in runner.commands)


def test_oracle_cleanup_rejects_job_replacement_after_global_pods_are_zero(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "oracle-job-sandwich-evidence"
    evidence.mkdir(mode=0o700)
    image = {"immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64}
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    selector = MODULE._oracle_cleanup_selector(
        section="turn",
        targets=targets,
        deployment_run_id="run-deployment-epoch",
    )
    job_command = [
        *kubectl,
        "get",
        "jobs",
        f"--selector={selector}",
        "--output=json",
    ]
    pod_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector={selector}",
        "--output=json",
    ]
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'
    replacement = (
        b'{"apiVersion":"v1","kind":"List","items":'
        b'[{"metadata":{"name":"replacement"}}]}'
    )
    calls: list[list[str]] = []
    job_reads = 0

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal job_reads
        calls.append(command)
        if command == job_command:
            job_reads += 1
            return MODULE.CommandResult(
                empty if job_reads == 1 else replacement,
                b"",
                0,
            )
        if command == pod_command:
            return MODULE.CommandResult(empty, b"", 0)
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(MODULE.AcceptanceProducerError, match="final.*nonempty"):
        MODULE._cleanup_stale_oracle_jobs(
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
            namespace="workspace-system",
            kubectl=kubectl,
            directory=evidence,
            image=image,
            signing_key=KEY,
            delete_client=NullKubernetesDeleteClient(),
            runner=runner,
        )

    assert calls == [job_command, pod_command, job_command]


@pytest.mark.parametrize("delete_mode", ["accepted-error", "retry", "replacement"])
def test_stale_oracle_cleanup_reconciles_an_ambiguous_delete_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delete_mode: str,
) -> None:
    targets, image, manifest, inventory = _owned_stale_oracle_fixture(tmp_path)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)
    evidence = tmp_path / "stale-oracle-transaction"
    evidence.mkdir(mode=0o700)
    name = manifest["metadata"]["name"]
    uid = inventory["items"][0]["metadata"]["uid"]
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        "workspace-system",
    ]
    selectors = {
        "global": MODULE._oracle_cleanup_selector(
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
        ),
        "uid": f"batch.kubernetes.io/controller-uid={uid}",
        "name": f"batch.kubernetes.io/job-name={name}",
    }
    replacement = json.loads(json.dumps(inventory["items"][0]))
    replacement["metadata"]["uid"] = "replacement-stale-oracle-job-uid"
    state = {"job": inventory["items"][0]}
    calls: list[list[str]] = []
    inventory_reads = 0
    delete_calls: list[dict] = []

    def list_result(items: list[dict]) -> MODULE.CommandResult:
        return MODULE.CommandResult(
            json.dumps({"apiVersion": "v1", "kind": "List", "items": items}).encode(),
            b"",
            0,
        )

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal inventory_reads
        calls.append(command)
        operation = command[len(kubectl) :]
        selector = next(
            (
                argument.removeprefix("--selector=")
                for argument in operation
                if argument.startswith("--selector=")
            ),
            None,
        )
        if operation[:2] == ["get", "jobs"] and selector == selectors["global"]:
            inventory_reads += 1
            return list_result(
                inventory["items"]
                if inventory_reads == 1
                else ([state["job"]] if state["job"] is not None else [])
            )
        if operation[:2] == ["get", "jobs"]:
            assert f"--field-selector=metadata.name={name}" in operation
            return list_result([state["job"]] if state["job"] is not None else [])
        if operation[:2] == ["get", "pods"] and selector in selectors.values():
            return list_result([])
        raise AssertionError(f"unexpected command: {command}")

    class DeleteClient:
        def get(self, **_kwargs):
            return state["job"]

        def delete(self, **kwargs) -> None:
            delete_calls.append(kwargs)
            if len(delete_calls) == 1 and delete_mode == "accepted-error":
                state["job"] = None
                raise RuntimeError("delete-secret")
            if len(delete_calls) == 1 and delete_mode == "retry":
                raise RuntimeError("delete-secret")
            if len(delete_calls) == 1:
                state["job"] = replacement
                raise RuntimeError("delete-secret")
            state["job"] = None

    delete_client = DeleteClient()

    def cleanup() -> list[dict]:
        return MODULE._cleanup_stale_oracle_jobs(
            section="turn",
            targets=targets,
            deployment_run_id="run-deployment-epoch",
            namespace="workspace-system",
            kubectl=kubectl,
            directory=evidence,
            image=image,
            signing_key=KEY,
            delete_client=delete_client,
            runner=runner,
        )

    if delete_mode == "replacement":
        with pytest.raises(MODULE.OracleTransactionFailure) as error:
            cleanup()
        assert len(delete_calls) == 1
        assert "delete-secret" not in str(error.value)
        assert error.value.__suppress_context__ is True
        assert [phase for phase, _failure in error.value.failures] == [
            "stale-delete",
            "recovery-1",
        ]
        assert all(call["uid"] == uid for call in delete_calls)
        return

    cleanup()
    assert state["job"] is None
    assert len(delete_calls) == (1 if delete_mode == "accepted-error" else 2)
    assert all(
        call
        == {
            "api_version": "batch/v1",
            "resource": "jobs",
            "namespace": "workspace-system",
            "name": name,
            "uid": uid,
            "resource_version": "101",
        }
        for call in delete_calls
    )
    pod_indexes = {
        argument.removeprefix("--selector="): index
        for index, command in enumerate(calls)
        if command[len(kubectl) :][:2] == ["get", "pods"]
        for argument in command
        if argument.startswith("--selector=")
    }
    assert selectors["uid"] in pod_indexes and selectors["name"] in pod_indexes
    exact_indexes = [
        index
        for index, command in enumerate(calls)
        if f"--field-selector=metadata.name={name}" in command
    ]
    assert len(exact_indexes) == (2 if delete_mode == "accepted-error" else 3)
    assert (
        exact_indexes[-2]
        < pod_indexes[selectors["uid"]]
        < pod_indexes[selectors["name"]]
        < exact_indexes[-1]
    )


def test_oracle_section_cleans_owned_stale_and_completed_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    section = "turn"
    deployment_run_id = "run-20260808"
    current_run_id = "run-current-turn"
    stale_run_id = "run-stale-turn01"
    manifest = MODULE.build_oracle_job_manifest(
        section=section,
        targets=targets,
        image=image,
        run_id=current_run_id,
        deployment_run_id=deployment_run_id,
        signing_key=KEY,
    )
    namespace = manifest["metadata"]["namespace"]
    current_name = manifest["metadata"]["name"]
    current_uid = "current-oracle-job-uid"
    stale_uid = "stale-oracle-job-uid"
    stale_manifest = MODULE.build_oracle_job_manifest(
        section=section,
        targets=targets,
        image=image,
        run_id=stale_run_id,
        deployment_run_id=deployment_run_id,
        signing_key=KEY,
    )
    stale_name = stale_manifest["metadata"]["name"]
    selector = ",".join(
        (
            "platform.aileron.dev/acceptance-owner=aileron-installer",
            f"platform.aileron.dev/acceptance-section={section}",
            f"platform.aileron.dev/source-commit={targets.commit}",
            f"platform.aileron.dev/deployment-run-id={deployment_run_id}",
            f"platform.aileron.dev/workspace-id={targets.workspace_id}",
        )
    )
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        namespace,
    ]
    stale_inventory = [
        *kubectl,
        "get",
        "jobs",
        f"--selector={selector}",
        "--output=json",
    ]
    stale_pod_inventory = [
        *kubectl,
        "get",
        "pods",
        f"--selector={selector}",
        "--output=json",
    ]

    def pods_zero_command(uid: str) -> list[str]:
        return [
            *kubectl,
            "get",
            "pods",
            f"--selector=batch.kubernetes.io/controller-uid={uid}",
            "--output=json",
        ]

    def name_pods_zero_command(name: str) -> list[str]:
        return [
            *kubectl,
            "get",
            "pods",
            f"--selector=batch.kubernetes.io/job-name={name}",
            "--output=json",
        ]

    def job_zero_command(name: str) -> list[str]:
        return [
            *kubectl,
            "get",
            "jobs",
            f"--field-selector=metadata.name={name}",
            "--output=json",
        ]

    create = [
        *kubectl,
        "create",
        "--filename",
        str(_evidence_directory(tmp_path) / f"{section}-oracle-job.json"),
        "--output=json",
    ]
    wait = [
        *kubectl,
        "wait",
        "--for=condition=complete",
        f"job/{current_name}",
        "--timeout=5m",
    ]
    get_job = [*kubectl, "get", "job", current_name, "--output=json"]
    get_pod = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={current_uid}",
        "--sort-by=.metadata.name",
        "--output=json",
    ]
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        current_uid,
    )
    logs = [
        *kubectl,
        "logs",
        f"pod/{pod['metadata']['name']}",
        "--container=oracle",
    ]
    exact_pod = [
        *kubectl,
        "get",
        "pod",
        pod["metadata"]["name"],
        "--output=json",
    ]
    stale_job, _ = _server_oracle_resources(
        stale_manifest,
        image["immutableImage"],
        stale_uid,
    )
    stale_job["status"] = {"active": 1}
    stale_jobs = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [stale_job],
    }
    empty_pods = json.dumps({"apiVersion": "v1", "kind": "List", "items": []})
    runner = Runner(
        {
            **_trust_responses(targets),
            tuple(stale_inventory): MODULE.CommandResult(
                json.dumps(stale_jobs).encode(), b"", 0
            ),
            tuple(pods_zero_command(stale_uid)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(name_pods_zero_command(stale_name)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(job_zero_command(stale_name)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(stale_pod_inventory): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(create): MODULE.CommandResult(json.dumps(job).encode(), b"", 0),
            tuple(wait): MODULE.CommandResult(b"condition met\n", b"", 0),
            tuple(get_job): MODULE.CommandResult(json.dumps(job).encode(), b"", 0),
            tuple(get_pod): MODULE.CommandResult(
                json.dumps(
                    {"apiVersion": "v1", "kind": "List", "items": [pod]}
                ).encode(),
                b"",
                0,
            ),
            tuple(exact_pod): MODULE.CommandResult(json.dumps(pod).encode(), b"", 0),
            tuple(logs): MODULE.CommandResult(
                b'{"backendPath":"relayed","frontendPath":"relayed"}', b"", 0
            ),
            tuple(pods_zero_command(current_uid)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(name_pods_zero_command(current_name)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
            tuple(job_zero_command(current_name)): MODULE.CommandResult(
                empty_pods.encode(), b"", 0
            ),
        }
    )
    live_jobs = {stale_name: stale_job}
    rest_get_calls: list[dict] = []
    rest_delete_calls: list[dict] = []

    class DeleteClient:
        def get(self, **kwargs):
            rest_get_calls.append(kwargs)
            return live_jobs.get(kwargs["name"])

        def delete(self, **kwargs) -> None:
            rest_delete_calls.append(kwargs)
            live_jobs.pop(kwargs["name"], None)
            if kwargs["name"] == stale_name:
                runner.responses[tuple(stale_inventory)] = MODULE.CommandResult(
                    empty_pods.encode(), b"", 0
                )

    loader_calls: list[dict] = []

    def load_delete_client(**kwargs):
        loader_calls.append(kwargs)
        return DeleteClient()

    monkeypatch.setattr(
        MODULE.KUBERNETES_REST,
        "load_kubernetes_delete_client",
        load_delete_client,
    )
    runner.effects[tuple(create)] = lambda: live_jobs.__setitem__(current_name, job)

    report_path = MODULE.produce(
        section=section,
        targets=targets,
        deployment_run_id=deployment_run_id,
        image_inventory=inventory,
        runner=runner,
        run_id_factory=lambda: current_run_id,
    )

    commands = runner.commands
    stale_inventory_reads = [
        index for index, command in enumerate(commands) if command == stale_inventory
    ]
    stale_job_zero_reads = [
        index
        for index, command in enumerate(commands)
        if command == job_zero_command(stale_name)
    ]
    assert len(stale_inventory_reads) == 2
    assert len(stale_job_zero_reads) == 2
    assert (
        stale_inventory_reads[0]
        < stale_job_zero_reads[0]
        < commands.index(pods_zero_command(stale_uid))
        < commands.index(name_pods_zero_command(stale_name))
        < stale_job_zero_reads[1]
        < commands.index(stale_pod_inventory)
        < stale_inventory_reads[1]
        < commands.index(name_pods_zero_command(current_name))
        < commands.index(create)
    )
    job_reads = [index for index, command in enumerate(commands) if command == get_job]
    assert len(job_reads) == 2
    assert (
        commands.index(create)
        < job_reads[0]
        < commands.index(wait)
        < job_reads[1]
        < commands.index(get_pod)
        < commands.index(exact_pod)
        < commands.index(logs)
    )
    exact_pod_reads = [
        index for index, command in enumerate(commands) if command == exact_pod
    ]
    assert len(exact_pod_reads) == 2
    assert exact_pod_reads[0] < commands.index(logs) < exact_pod_reads[1]
    current_name_pod_reads = [
        index
        for index, command in enumerate(commands)
        if command == name_pods_zero_command(current_name)
    ]
    current_job_zero_reads = [
        index
        for index, command in enumerate(commands)
        if command == job_zero_command(current_name)
    ]
    assert len(current_name_pod_reads) == 2
    assert len(current_job_zero_reads) == 2
    assert (
        commands.index(logs)
        < current_job_zero_reads[0]
        < commands.index(pods_zero_command(current_uid))
        < current_name_pod_reads[1]
        < current_job_zero_reads[1]
    )
    report = json.loads(report_path.read_text())
    cleanup_commands = {
        tuple(stale_inventory),
        tuple(pods_zero_command(stale_uid)),
        tuple(name_pods_zero_command(stale_name)),
        tuple(job_zero_command(stale_name)),
        tuple(stale_pod_inventory),
        tuple(name_pods_zero_command(current_name)),
        tuple(pods_zero_command(current_uid)),
        tuple(name_pods_zero_command(current_name)),
        tuple(job_zero_command(current_name)),
        tuple(exact_pod),
    }
    assert cleanup_commands.issubset(
        {tuple(source["command"]) for source in report["sources"]}
    )
    assert loader_calls == [
        {
            "kubeconfig": targets.kubeconfig,
            "context": targets.context,
            "credential_directory": _evidence_directory(tmp_path),
            "private_root": tmp_path,
        }
    ]
    assert [call["name"] for call in rest_get_calls] == [stale_name, current_name]
    assert rest_delete_calls == [
        {
            "api_version": "batch/v1",
            "resource": "jobs",
            "namespace": namespace,
            "name": stale_name,
            "uid": stale_uid,
            "resource_version": "101",
        },
        {
            "api_version": "batch/v1",
            "resource": "jobs",
            "namespace": namespace,
            "name": current_name,
            "uid": current_uid,
            "resource_version": "101",
        },
    ]
    assert not any(
        command[len(kubectl) : len(kubectl) + 2] == ["delete", "job"]
        for command in commands
    )


def _direct_oracle_execution_fixture(tmp_path: Path, *, section: str = "turn"):
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    run_id = "run-ambiguous-create"
    deployment_run_id = "run-deployment-epoch"
    manifest = MODULE.build_oracle_job_manifest(
        section=section,
        targets=targets,
        image=image,
        run_id=run_id,
        deployment_run_id=deployment_run_id,
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "ambiguous-created-job-uid",
    )
    directory = tmp_path / "oracle-direct-evidence"
    directory.mkdir(mode=0o700)
    kubectl = [
        "kubectl",
        "--kubeconfig",
        str(targets.kubeconfig),
        "--context",
        targets.context,
        "--namespace",
        manifest["metadata"]["namespace"],
    ]

    class Trust:
        key = KEY
        cluster_uid = CLUSTER_UID
        installation_identity_sha256 = IDENTITY_DIGEST

    return (
        targets,
        inventory,
        image,
        manifest,
        job,
        pod,
        directory,
        kubectl,
        Trust(),
        run_id,
        deployment_run_id,
    )


def _bypass_oracle_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_cleanup_stale_oracle_jobs", lambda **_kwargs: [])
    monkeypatch.setattr(
        MODULE,
        "_require_oracle_name_pods_zero",
        lambda **_kwargs: {
            "file": "preflight.json",
            "sha256": "0" * 64,
            "command": ["preflight"],
            "exitCode": 0,
        },
    )


def test_image_release_oracle_preserves_the_full_signed_runtime_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        targets,
        inventory,
        _image,
        manifest,
        job,
        pod,
        directory,
        kubectl,
        trust,
        run_id,
        deployment_run_id,
    ) = _direct_oracle_execution_fixture(tmp_path, section="imageRelease")
    _bypass_oracle_preflight(monkeypatch)
    release_images = RELEASE.load_signed_image_inventory(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    expected_observations = {
        "images": [
            {
                "component": image["component"],
                "platform": image["platform"],
                "revision": image["revision"],
                "immutableImage": image["immutableImage"],
                "runtimeImmutableImage": image["runtimeImmutableImage"],
            }
            for image in release_images
        ]
    }
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    configmap_path = directory / "image-release-inventory-configmap.json"
    apply_command = [
        *kubectl,
        "apply",
        "--filename",
        str(configmap_path),
        "--output=name",
    ]
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(directory / "imageRelease-oracle-job.json"),
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
    pods_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--sort-by=.metadata.name",
        "--output=json",
    ]
    exact_pod_command = [
        *kubectl,
        "get",
        "pod",
        pod["metadata"]["name"],
        "--output=json",
    ]
    logs_command = [
        *kubectl,
        "logs",
        f"pod/{pod['metadata']['name']}",
        "--container=oracle",
    ]
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'

    def runner(command: list[str], timeout_seconds: float | None = None):
        if command == apply_command:
            return MODULE.CommandResult(b"configmap applied\n", b"", 0)
        if command in (create_command, job_command):
            return MODULE.CommandResult(json.dumps(job).encode(), b"", 0)
        if command == wait_command:
            return MODULE.CommandResult(b"condition met\n", b"", 0)
        if command == pods_command:
            return MODULE.CommandResult(
                json.dumps(
                    {"apiVersion": "v1", "kind": "List", "items": [pod]}
                ).encode(),
                b"",
                0,
            )
        if command == exact_pod_command:
            return MODULE.CommandResult(json.dumps(pod).encode(), b"", 0)
        if command == logs_command:
            return MODULE.CommandResult(
                json.dumps(expected_observations).encode(),
                b"",
                0,
            )
        if command in (uid_pods, name_pods, exact_jobs):
            return MODULE.CommandResult(empty, b"", 0)
        raise AssertionError(f"unexpected command: {command}")

    observations, _sources = MODULE._produce_oracle_section(
        section="imageRelease",
        targets=targets,
        directory=directory,
        image_inventory=inventory,
        trust=trust,
        runner=runner,
        run_id=run_id,
        deployment_run_id=deployment_run_id,
    )

    assert observations == expected_observations
    configmap = json.loads(configmap_path.read_text())
    assert configmap["data"]["images.tsv"].splitlines() == [
        "\t".join(
            (
                image["component"],
                image["platform"],
                image["revision"],
                image["immutableImage"],
                image["runtimeImmutableImage"],
            )
        )
        for image in release_images
    ]


@pytest.mark.parametrize(
    (
        "create_outcome",
        "recovery_mode",
        "delete_failure",
        "expected_error",
        "expected_exact_reads",
    ),
    [
        (
            MODULE.CommandResult(b"", b"client timeout", 124),
            "job",
            False,
            "fixed acceptance",
            3,
        ),
        (
            MODULE.CommandResult(b"", b"client failure", 1),
            "job",
            False,
            "fixed acceptance",
            3,
        ),
        (
            MODULE.CommandResult(b"not-json", b"", 0),
            "job",
            False,
            "invalid JSON",
            3,
        ),
        (
            MODULE.CommandResult(b"", b"client timeout", 124),
            "empty",
            False,
            "fixed acceptance",
            4,
        ),
        (
            MODULE.CommandResult(b"", b"client timeout", 124),
            "error",
            False,
            "fixed acceptance",
            4,
        ),
        (
            RuntimeError("primary-secret"),
            "exception",
            True,
            "oracle Job transaction failed",
            3,
        ),
    ],
    ids=[
        "timeout",
        "nonzero",
        "invalid-json",
        "first-recovery-empty",
        "first-recovery-error",
        "primary-recovery-cleanup-errors",
    ],
)
def test_ambiguous_oracle_create_recovers_only_the_canonical_job_and_deletes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    create_outcome: MODULE.CommandResult | Exception,
    recovery_mode: str,
    delete_failure: bool,
    expected_error: str,
    expected_exact_reads: int,
) -> None:
    (
        targets,
        inventory,
        _image,
        manifest,
        job,
        _pod,
        directory,
        kubectl,
        trust,
        run_id,
        deployment_run_id,
    ) = _direct_oracle_execution_fixture(tmp_path)
    _bypass_oracle_preflight(monkeypatch)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(directory / "turn-oracle-job.json"),
        "--output=json",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    calls: list[list[str]] = []
    exact_reads = 0
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal exact_reads
        calls.append(command)
        if command == create_command:
            if isinstance(create_outcome, Exception):
                raise create_outcome
            return create_outcome
        if command == exact_jobs:
            exact_reads += 1
            if exact_reads == 1 and recovery_mode == "error":
                return MODULE.CommandResult(b"", b"transient", 1)
            if exact_reads == 1 and recovery_mode == "exception":
                raise RuntimeError("recovery-secret")
            job_read = 1 if recovery_mode == "job" else 2
            document = {
                "apiVersion": "v1",
                "kind": "List",
                "items": ([job] if delete_failure or exact_reads == job_read else []),
            }
            return MODULE.CommandResult(json.dumps(document).encode(), b"", 0)
        if command in (uid_pods, name_pods):
            return MODULE.CommandResult(empty, b"", 0)
        raise AssertionError(f"unexpected command: {command}")

    delete_calls: list[dict] = []

    class DeleteClient:
        def get(self, **_kwargs):
            return job

        def delete(self, **kwargs) -> None:
            delete_calls.append(kwargs)
            if delete_failure:
                raise RuntimeError("cleanup-secret")

    monkeypatch.setattr(
        MODULE.KUBERNETES_REST,
        "load_kubernetes_delete_client",
        lambda **_kwargs: DeleteClient(),
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match=expected_error) as error:
        MODULE._produce_oracle_section(
            section="turn",
            targets=targets,
            directory=directory,
            image_inventory=inventory,
            trust=trust,
            runner=runner,
            run_id=run_id,
            deployment_run_id=deployment_run_id,
        )

    assert exact_reads == expected_exact_reads
    if delete_failure:
        assert isinstance(error.value, MODULE.OracleTransactionFailure)
        assert [phase for phase, _failure in error.value.failures] == [
            "primary",
            "recovery-1",
            "cleanup-2",
            "cleanup-3",
        ]
        assert [str(failure) for _phase, failure in error.value.failures] == [
            "primary-secret",
            "recovery-secret",
            "cleanup-secret",
            "cleanup-secret",
        ]
        assert all(
            secret not in str(error.value)
            for secret in ("primary-secret", "recovery-secret", "cleanup-secret")
        )
        assert error.value.__suppress_context__ is True
        assert len(delete_calls) == 2
        return

    exact_indexes = [
        index for index, command in enumerate(calls) if command == exact_jobs
    ]
    assert len(delete_calls) == 1
    assert delete_calls[0] == {
        "api_version": "batch/v1",
        "resource": "jobs",
        "namespace": "workspace-system",
        "name": name,
        "uid": uid,
        "resource_version": "101",
    }
    name_pod_indexes = [
        index for index, command in enumerate(calls) if command == name_pods
    ]
    assert exact_indexes[-2] < calls.index(uid_pods) < name_pod_indexes[-1]
    assert name_pod_indexes[-1] < exact_indexes[-1]
    if recovery_mode == "empty":
        assert exact_indexes[0] < name_pod_indexes[0] < exact_indexes[1]


def test_ambiguous_oracle_create_rejects_a_foreign_fixed_name_without_deleting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        targets,
        inventory,
        _image,
        manifest,
        job,
        _pod,
        directory,
        kubectl,
        trust,
        run_id,
        deployment_run_id,
    ) = _direct_oracle_execution_fixture(tmp_path)
    _bypass_oracle_preflight(monkeypatch)
    job["metadata"]["annotations"][MODULE.ORACLE_TRANSACTION_TOKEN_ANNOTATION] = (
        "f" * 64
    )
    name = manifest["metadata"]["name"]
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(directory / "turn-oracle-job.json"),
        "--output=json",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    calls: list[list[str]] = []

    def runner(command: list[str], timeout_seconds: float | None = None):
        calls.append(command)
        if command == create_command:
            return MODULE.CommandResult(b"", b"client timeout", 124)
        if command == exact_jobs:
            return MODULE.CommandResult(
                json.dumps(
                    {"apiVersion": "v1", "kind": "List", "items": [job]}
                ).encode(),
                b"",
                0,
            )
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(
        MODULE.OracleTransactionFailure,
        match="oracle Job transaction failed",
    ) as error:
        MODULE._produce_oracle_section(
            section="turn",
            targets=targets,
            directory=directory,
            image_inventory=inventory,
            trust=trust,
            runner=runner,
            run_id=run_id,
            deployment_run_id=deployment_run_id,
        )

    assert exact_jobs in calls
    assert not any("delete" in command for command in calls)
    assert [phase for phase, _failure in error.value.failures] == [
        "primary",
        "recovery-1",
    ]


@pytest.mark.parametrize("replacement", [False, True])
def test_successful_oracle_create_with_spec_drift_cleans_only_the_created_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: bool,
) -> None:
    (
        targets,
        inventory,
        _image,
        manifest,
        job,
        _pod,
        directory,
        kubectl,
        trust,
        run_id,
        deployment_run_id,
    ) = _direct_oracle_execution_fixture(tmp_path)
    _bypass_oracle_preflight(monkeypatch)
    drifted_job = json.loads(json.dumps(job))
    drifted_job["spec"]["template"]["spec"]["containers"][0]["command"] = [
        "/bin/sh",
        "-c",
        "true",
    ]
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(directory / "turn-oracle-job.json"),
        "--output=json",
    ]
    uid_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--output=json",
    ]
    name_pods = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    empty = b'{"apiVersion":"v1","kind":"List","items":[]}'
    replacement_job = json.loads(json.dumps(job))
    replacement_job["metadata"]["uid"] = "replacement-oracle-job-uid"
    calls: list[list[str]] = []
    exact_reads = 0

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal exact_reads
        calls.append(command)
        if command == create_command:
            return MODULE.CommandResult(json.dumps(drifted_job).encode(), b"", 0)
        if command == exact_jobs:
            exact_reads += 1
            item = replacement_job if replacement else drifted_job
            return MODULE.CommandResult(
                json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "List",
                        "items": [item] if exact_reads == 1 else [],
                    }
                ).encode(),
                b"",
                0,
            )
        if command in (uid_pods, name_pods):
            return MODULE.CommandResult(empty, b"", 0)
        raise AssertionError(f"unexpected command: {command}")

    delete_calls: list[dict] = []

    class DeleteClient:
        def get(self, **_kwargs):
            return drifted_job

        def delete(self, **kwargs) -> None:
            delete_calls.append(kwargs)

    monkeypatch.setattr(
        MODULE.KUBERNETES_REST,
        "load_kubernetes_delete_client",
        lambda **_kwargs: DeleteClient(),
    )

    expected_error = "oracle Job transaction failed" if replacement else "spec identity"
    with pytest.raises(MODULE.AcceptanceProducerError, match=expected_error):
        MODULE._produce_oracle_section(
            section="turn",
            targets=targets,
            directory=directory,
            image_inventory=inventory,
            trust=trust,
            runner=runner,
            run_id=run_id,
            deployment_run_id=deployment_run_id,
        )

    exact_indexes = [
        index for index, command in enumerate(calls) if command == exact_jobs
    ]
    assert calls.index(create_command) < exact_indexes[0]
    if replacement:
        assert delete_calls == []
    else:
        assert delete_calls == [
            {
                "api_version": "batch/v1",
                "resource": "jobs",
                "namespace": "workspace-system",
                "name": name,
                "uid": uid,
                "resource_version": "101",
            }
        ]
        assert exact_indexes[0] < exact_indexes[1]


def test_oracle_rejects_pod_uid_replacement_after_log_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        targets,
        inventory,
        _image,
        manifest,
        job,
        pod,
        directory,
        kubectl,
        trust,
        run_id,
        deployment_run_id,
    ) = _direct_oracle_execution_fixture(tmp_path)
    _bypass_oracle_preflight(monkeypatch)
    cleanup_uids: list[str] = []

    def cleanup(**kwargs):
        cleanup_uids.append(kwargs["uid"])
        return []

    monkeypatch.setattr(MODULE, "_delete_oracle_job", cleanup)
    name = manifest["metadata"]["name"]
    uid = job["metadata"]["uid"]
    create_command = [
        *kubectl,
        "create",
        "--filename",
        str(directory / "turn-oracle-job.json"),
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
    pods_command = [
        *kubectl,
        "get",
        "pods",
        f"--selector=batch.kubernetes.io/controller-uid={uid}",
        "--sort-by=.metadata.name",
        "--output=json",
    ]
    exact_pod_command = [
        *kubectl,
        "get",
        "pod",
        pod["metadata"]["name"],
        "--output=json",
    ]
    logs_command = [
        *kubectl,
        "logs",
        f"pod/{pod['metadata']['name']}",
        "--container=oracle",
    ]
    exact_jobs = MODULE._oracle_exact_job_inventory_command(
        kubectl=kubectl,
        name=name,
    )
    replacement = json.loads(json.dumps(pod))
    replacement["metadata"]["uid"] = "replacement-pod-uid"
    exact_reads = 0
    calls: list[list[str]] = []

    def runner(command: list[str], timeout_seconds: float | None = None):
        nonlocal exact_reads
        calls.append(command)
        if command in (create_command, job_command):
            return MODULE.CommandResult(json.dumps(job).encode(), b"", 0)
        if command == wait_command:
            return MODULE.CommandResult(b"condition met\n", b"", 0)
        if command == pods_command:
            return MODULE.CommandResult(
                json.dumps(
                    {"apiVersion": "v1", "kind": "List", "items": [pod]}
                ).encode(),
                b"",
                0,
            )
        if command == exact_pod_command:
            exact_reads += 1
            reread = pod if exact_reads == 1 else replacement
            return MODULE.CommandResult(json.dumps(reread).encode(), b"", 0)
        if command == logs_command:
            return MODULE.CommandResult(
                b'{"backendPath":"relayed","frontendPath":"relayed"}',
                b"",
                0,
            )
        if command == exact_jobs:
            return MODULE.CommandResult(
                json.dumps(
                    {"apiVersion": "v1", "kind": "List", "items": [job]}
                ).encode(),
                b"",
                0,
            )
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(MODULE.AcceptanceProducerError, match="changed identity"):
        MODULE._produce_oracle_section(
            section="turn",
            targets=targets,
            directory=directory,
            image_inventory=inventory,
            trust=trust,
            runner=runner,
            run_id=run_id,
            deployment_run_id=deployment_run_id,
        )

    exact_positions = [
        index for index, command in enumerate(calls) if command == exact_pod_command
    ]
    assert len(exact_positions) == 2
    assert exact_positions[0] < calls.index(logs_command) < exact_positions[1]
    assert cleanup_uids == [uid]


def test_oracle_job_identity_rejects_mutated_service_account_and_unowned_pod(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "job-uid",
    )
    job["spec"]["template"]["spec"]["serviceAccountName"] = "default"
    pod["metadata"]["ownerReferences"] = []

    with pytest.raises(MODULE.AcceptanceProducerError, match="Job spec"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )


def test_oracle_job_generation_rejects_fixed_name_uid_replacement(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-uid-binding",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    replacement, _ = _server_oracle_resources(
        manifest, image["immutableImage"], "replacement-job-uid"
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match="changed identity"):
        MODULE._require_oracle_job_generation(
            manifest=manifest,
            job=replacement,
            expected_uid="created-job-uid",
        )


@pytest.mark.parametrize(
    "mutation",
    ("initContainers", "volumes", "serviceAccountName", "hostNetwork"),
)
def test_oracle_job_identity_rejects_additional_pod_security_fields(
    tmp_path: Path,
    mutation: str,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job_uid = "job-uid"
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job_uid,
    )
    mutations = {
        "initContainers": [{"name": "untracked", "image": "busybox:latest"}],
        "volumes": [{"name": "untracked", "hostPath": {"path": "/"}}],
        "serviceAccountName": "default",
        "hostNetwork": True,
    }
    pod["spec"][mutation] = mutations[mutation]

    with pytest.raises(MODULE.AcceptanceProducerError, match="Pod spec"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )


def test_oracle_job_identity_accepts_only_known_kubernetes_defaults(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    inventory = _signed_inventory(tmp_path, targets)
    image = RELEASE.load_workspace_manager_image(
        path=inventory,
        private_root=tmp_path,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-20260808",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job_uid = "job-uid"
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job_uid,
    )

    assert (
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )
        == pod
    )


def test_oracle_job_identity_accepts_rke2_digest_only_status_image(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-rke2-status-image",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    pod["status"]["containerStatuses"][0]["image"] = "sha256:" + "a" * 64

    assert (
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )
        == pod
    )


def test_oracle_job_identity_accepts_zero_observed_duration_rke2_completion(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-rke2-zero-duration",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    terminated = pod["status"]["containerStatuses"][0]["state"]["terminated"]
    same_second = "2026-08-08T07:00:30Z"
    terminated["startedAt"] = same_second
    terminated["finishedAt"] = same_second

    assert (
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )
        == pod
    )


def test_oracle_job_identity_accepts_the_bound_linux_amd64_runtime_digest(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    index_digest = "sha256:" + "9" * 64
    runtime_digest = "sha256:" + "8" * 64
    image = {"immutableImage": f"registry.example/workspace-manager@{index_digest}"}
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-platform-digest",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    pod["status"]["containerStatuses"][0][
        "imageID"
    ] = f"docker-pullable://registry.example/workspace-manager@{runtime_digest}"

    assert (
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests={index_digest, runtime_digest},
        )
        == pod
    )


def test_oracle_job_identity_rejects_runtime_digest_from_a_foreign_repository(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    index_digest = "sha256:" + "9" * 64
    runtime_digest = "sha256:" + "8" * 64
    image = {"immutableImage": f"registry.example/workspace-manager@{index_digest}"}
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-foreign-repository",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    pod["status"]["containerStatuses"][0][
        "imageID"
    ] = f"docker-pullable://registry.example/foreign@{runtime_digest}"

    with pytest.raises(MODULE.AcceptanceProducerError, match="image"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests={index_digest, runtime_digest},
        )


@pytest.mark.parametrize("attack", ["missing", "failed"])
def test_oracle_job_identity_requires_exact_pod_replacement_default_without_policy(
    tmp_path: Path, attack: str
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-replacement-policy",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    if attack == "missing":
        job["spec"].pop("podReplacementPolicy")
    else:
        job["spec"]["podReplacementPolicy"] = "Failed"

    with pytest.raises(MODULE.AcceptanceProducerError, match="oracle Job spec"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )


@pytest.mark.parametrize(
    "attack",
    ["legacy-selector", "expected-only-template-labels", "legacy-only-pod-labels"],
)
def test_oracle_job_identity_requires_v131_controller_identity_projection(
    tmp_path: Path, attack: str
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-controller-projection",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job_uid = "oracle-job-uid"
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        job_uid,
    )
    if attack == "legacy-selector":
        job["spec"]["selector"] = {"matchLabels": {"controller-uid": job_uid}}
    elif attack == "expected-only-template-labels":
        job["spec"]["template"]["metadata"]["labels"] = manifest["metadata"]["labels"]
    else:
        pod["metadata"]["labels"].pop("batch.kubernetes.io/job-name")
        pod["metadata"]["labels"].pop("batch.kubernetes.io/controller-uid")

    with pytest.raises(MODULE.AcceptanceProducerError, match="oracle (Job|Pod)"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )


@pytest.mark.parametrize("server_shape", ["legacy", "success-criteria-met"])
def test_oracle_job_identity_accepts_kubernetes_success_condition_shapes(
    tmp_path: Path, server_shape: str
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-success-shapes",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    completion_time = job["status"]["completionTime"]
    pod["status"]["containerStatuses"][0]["state"]["terminated"][
        "finishedAt"
    ] = "2026-08-08T07:00:29Z"
    complete = job["status"]["conditions"][0]
    if server_shape == "legacy":
        complete["lastProbeTime"] = None
    else:
        complete.pop("lastProbeTime")
        job["status"]["conditions"].insert(
            0,
            {
                "type": "SuccessCriteriaMet",
                "status": "True",
                "lastTransitionTime": "2026-08-08T07:00:29Z",
                "reason": "CompletionsReached",
                "message": "Reached expected number of succeeded pods",
            },
        )

    assert complete["lastTransitionTime"] == completion_time
    assert (
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods={"apiVersion": "v1", "kind": "List", "items": [pod]},
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )
        == pod
    )


@pytest.mark.parametrize(
    "attack",
    [
        "job-api-version",
        "job-kind",
        "job-name",
        "job-namespace",
        "job-owner",
        "job-deleting",
        "job-active",
        "job-completion-time",
        "job-complete-condition",
        "job-unknown-condition",
        "job-condition-transition-after-completion",
        "job-condition-invalid-probe",
        "pods-root",
        "pod-api-version",
        "pod-kind",
        "pod-name",
        "pod-uid",
        "pod-namespace",
        "pod-deleting",
        "status-image",
        "container-id",
        "termination-exit",
        "termination-reason",
        "termination-started-at",
        "termination-finished-at",
        "termination-finished-after-completion",
    ],
)
def test_oracle_job_identity_rejects_incomplete_server_identity(
    tmp_path: Path, attack: str
) -> None:
    targets = _targets(tmp_path)
    image = {
        "immutableImage": "registry.example/workspace-manager@sha256:" + "9" * 64,
        "runtimeImmutableImage": (
            "registry.example/workspace-manager@sha256:" + "8" * 64
        ),
    }
    manifest = MODULE.build_oracle_job_manifest(
        section="turn",
        targets=targets,
        image=image,
        run_id="run-oracle-identity",
        deployment_run_id="run-deployment-epoch",
        signing_key=KEY,
    )
    job, pod = _server_oracle_resources(
        manifest,
        image["immutableImage"],
        "oracle-job-uid",
    )
    pods = {"apiVersion": "v1", "kind": "List", "items": [pod]}
    status = pod["status"]["containerStatuses"][0]
    terminated = status["state"]["terminated"]
    if attack == "job-api-version":
        job["apiVersion"] = "batch/v2"
    elif attack == "job-kind":
        job["kind"] = "CronJob"
    elif attack == "job-name":
        job["metadata"]["name"] = "other-job"
    elif attack == "job-namespace":
        job["metadata"]["namespace"] = "other-system"
    elif attack == "job-owner":
        job["metadata"]["ownerReferences"] = [{"kind": "Unknown"}]
    elif attack == "job-deleting":
        job["metadata"]["deletionTimestamp"] = "2026-08-08T07:00:31Z"
    elif attack == "job-active":
        job["status"]["active"] = 1
    elif attack == "job-completion-time":
        job["status"]["completionTime"] = "not-a-timestamp"
    elif attack == "job-complete-condition":
        job["status"]["conditions"].append(
            {
                "type": "Complete",
                "status": "False",
                "lastProbeTime": "2026-08-08T07:00:30Z",
                "lastTransitionTime": "2026-08-08T07:00:30Z",
            }
        )
    elif attack == "job-unknown-condition":
        job["status"]["conditions"].append(
            {
                "type": "Ready",
                "status": "True",
                "lastTransitionTime": "2026-08-08T07:00:30Z",
            }
        )
    elif attack == "job-condition-transition-after-completion":
        job["status"]["conditions"][0]["lastTransitionTime"] = "2026-08-08T07:00:31Z"
    elif attack == "job-condition-invalid-probe":
        job["status"]["conditions"][0]["lastProbeTime"] = "not-a-timestamp"
    elif attack == "pods-root":
        pods["kind"] = "PodList"
    elif attack == "pod-api-version":
        pod["apiVersion"] = "v2"
    elif attack == "pod-kind":
        pod["kind"] = "Job"
    elif attack == "pod-name":
        pod["metadata"]["name"] = "unrelated-pod"
    elif attack == "pod-uid":
        pod["metadata"]["uid"] = ""
    elif attack == "pod-namespace":
        pod["metadata"]["namespace"] = "other-system"
    elif attack == "pod-deleting":
        pod["metadata"]["deletionTimestamp"] = "2026-08-08T07:00:31Z"
    elif attack == "status-image":
        status["image"] = "busybox:latest"
    elif attack == "container-id":
        status["containerID"] = "docker://not-a-containerd-id"
    elif attack == "termination-exit":
        terminated["exitCode"] = 1
    elif attack == "termination-reason":
        terminated["reason"] = "Error"
    elif attack == "termination-started-at":
        terminated["startedAt"] = "not-a-timestamp"
    elif attack == "termination-finished-after-completion":
        terminated["finishedAt"] = "2026-08-08T07:00:31Z"
    else:
        terminated["finishedAt"] = "2026-08-08T06:59:59Z"

    with pytest.raises(MODULE.AcceptanceProducerError, match="oracle (Job|Pod)"):
        MODULE.validate_oracle_job_identity(
            manifest=manifest,
            job=job,
            pods=pods,
            immutable_image=image["immutableImage"],
            allowed_image_digests=_allowed_oracle_digests(image),
        )


def test_suites_execute_unique_fixed_commands_and_logs(tmp_path: Path) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-contract"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
    }
    image_id = f"sha256:{'d' * 64}"
    commands = MODULE.build_suite_commands(targets, run_id, source_root)
    expected_runner_cleanup_commands = []
    for index, run in enumerate(commands, start=1):
        responses[tuple(run.build_command)] = MODULE.CommandResult(b"built", b"", 0)
        if run.preflight_command is not None:
            responses[tuple(run.preflight_command)] = MODULE.CommandResult(b"", b"", 0)
        responses[tuple(MODULE._pin_suite_command(run.command, image_id))] = (
            MODULE.CommandResult(
                f"suite-log-{index}".encode(),
                b"",
                0,
            )
        )
        responses[tuple(MODULE._pin_suite_command(run.cleanup_command, image_id))] = (
            MODULE.CommandResult(b"", b"", 0)
        )
        inspect = [
            "docker",
            "image",
            "inspect",
            '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
            run.runner_image,
        ]
        responses[tuple(inspect)] = MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        )
        runner_cleanup = [
            "docker",
            "image",
            "rm",
            run.runner_image,
        ]
        responses[tuple(runner_cleanup)] = MODULE.CommandResult(b"untagged\n", b"", 0)
        expected_runner_cleanup_commands.append(runner_cleanup)
    runner = Runner(responses)

    report_path = MODULE.produce(
        section="suites",
        targets=targets,
        deployment_run_id="run-20260808",
        image_inventory=inventory,
        runner=runner,
        run_id_factory=lambda: run_id,
    )

    report = json.loads(report_path.read_text())
    assert not list(report_path.parent.glob("suites-*-failure.json"))
    assert not source_root.exists()
    archive = evidence / "suites-source-archive.tar.gz"
    assert archive.read_bytes() == b"suite archive fixture\n"
    assert archive.stat().st_mode & 0o777 == 0o600
    assert [
        command
        for command in runner.commands
        if command[:3] == ["docker", "image", "rm"]
    ] == expected_runner_cleanup_commands
    assert "workspace" not in report
    digests = [run["rawLogSha256"] for run in report["observations"]["runs"]]
    assert len(digests) == len(set(digests)) == 10
    assert len(report["sources"]) == 11
    assert [source["command"] for source in report["sources"]] == [
        [
            "git",
            "-C",
            str(ROOT),
            "archive",
            "--format=tar.gz",
            targets.commit,
        ],
        *[MODULE._pin_suite_command(run.command, image_id) for run in commands],
    ]
    assert report["observations"]["sourceProvenance"] == {
        "headCommit": targets.commit,
        "targetCommit": targets.commit,
        "worktreeClean": True,
        "untrackedFilesIncluded": True,
        "archiveSha256": hashlib.sha256(b"suite archive fixture\n").hexdigest(),
        "treeSha256": MATERIALIZED_SUITE_TREE_SHA256,
        "archiveCommand": [
            "git",
            "-C",
            str(ROOT),
            "archive",
            "--format=tar.gz",
            targets.commit,
        ],
        "materializedTreeReadOnly": True,
        "treeDigestChecks": 32,
    }
    assert report["observations"]["releaseInputs"] == {
        "signedImageInventorySha256": hashlib.sha256(inventory.read_bytes()).hexdigest()
    }
    assert all(command[:3] != ["docker", "image", "tag"] for command in runner.commands)
    for run in report["observations"]["runs"]:
        expected_suite = next(suite for suite in commands if suite.name == run["name"])
        assert run["runner"] == {
            "image": expected_suite.runner_image,
            "imageId": image_id,
            "architecture": "amd64",
            "sourceRevision": targets.commit,
            "buildCommand": expected_suite.build_command,
            "inspectCommand": [
                "docker",
                "image",
                "inspect",
                '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
                expected_suite.runner_image,
            ],
        }
        assert run["cleanupCommand"] == MODULE._pin_suite_command(
            expected_suite.cleanup_command, image_id
        )
        assert run["cleaned"] is True
    docker_source = report_path.parent / report["sources"][0]["file"]
    docker_log = docker_source.read_text(encoding="utf-8")
    assert "HOST_PLATFORM_SECRETS_DIR" not in docker_log
    assert "HOST_TURN_SECRETS_DIR" not in docker_log


def test_suites_use_fixed_hermetic_compose_commands(tmp_path: Path) -> None:
    commands = MODULE.build_suite_commands(_targets(tmp_path))

    assert [command.name for command in commands] == [
        "docker",
        "helm",
        "frontend",
        "manager",
        "operator",
        "identity",
        "platform-conformance",
        "kubernetes-hardening",
        "docs-zh-Hant",
        "docs-en",
    ]
    assert all(
        command.command[:4] == list(MODULE.HERMETIC_COMPOSE_ENVIRONMENT)
        for command in commands
    )
    assert all(
        command.command[command.command.index("--env-file") + 1] == "/dev/null"
        for command in commands
    )
    assert all(
        command.command[-5:-1] == ["run", "--pull", "never", "--rm"]
        for command in commands
    )
    assert all(
        command.build_command[:3] == ["docker", "build", "--platform"]
        for command in commands
    )
    assert all("linux/amd64" in command.build_command for command in commands)
    assert all(
        command.cleanup_command[-3:] == ["down", "--volumes", "--remove-orphans"]
        for command in commands
    )
    assert len({command.project_name for command in commands}) == len(commands)
    assert commands[0].preflight_command[-2:] == ["config", "--quiet"]
    assert commands[0].command[-1] == "compose-e2e-test"
    assert commands[1].command[-1] == "helm-contract-test"
    assert commands[4].command[-1] == "workspace-operator-test"
    assert commands[7].command[-1] == "kubernetes-conformance-hardening-test"
    assert commands[8].command[-1] == "docs-site-build-zh-hant"
    assert commands[9].command[-1] == "docs-site-build-en"


def test_suites_public_api_and_commands_do_not_depend_on_ambient_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    expected = MODULE.build_suite_commands(targets)

    for name in (
        "COMPOSE_FILE",
        "COMPOSE_PROFILES",
        "HOST_PROJECT_ROOT",
        "PLAYWRIGHT_IMAGE",
        "WORKSPACE_MANAGER_IMAGE",
    ):
        monkeypatch.setenv(name, f"poisoned-{name.lower()}")

    actual = MODULE.build_suite_commands(targets)
    assert actual == expected
    assert "environment" not in inspect.signature(MODULE.produce).parameters
    preflight = actual[0].preflight_command
    assert preflight is not None
    assert preflight[:4] == list(MODULE.HERMETIC_COMPOSE_ENVIRONMENT)
    assert preflight[preflight.index("--env-file") + 1] == str(ROOT / ".env.example")


def test_root_compose_example_covers_every_interpolation_input() -> None:
    compose_inputs = {
        name
        for path in (
            ROOT / "docker-compose.yml",
            ROOT / "docker-compose.bundled-data-services.yml",
            ROOT / "docker-compose.data-service-tls.yml",
        )
        for name in re.findall(r"\$\{([A-Z][A-Z0-9_]*)", path.read_text())
    }
    example_inputs = {
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    # Compose reads these itself instead of interpolating them into a service,
    # so they are declared for the operator without appearing above.
    compose_native_inputs = {"COMPOSE_PROFILES"}

    assert compose_inputs == example_inputs - compose_native_inputs


def test_compose_suite_failure_still_cleans_project_and_rechecks_source(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "suite-evidence"
    evidence.mkdir(mode=0o700)
    source = MODULE._materialize_suite_source(
        targets=targets,
        directory=evidence,
        run_id="run-suite-contract",
        section="suites",
        runner=Runner({}),
    )
    suite = MODULE.build_suite_commands(targets, "run-suite-contract", source.root)[1]
    image_id = f"sha256:{'d' * 64}"
    inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    responses = {
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect): MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(MODULE._pin_suite_command(suite.command, image_id)): MODULE.CommandResult(
            b"failed", b"", 1
        ),
        tuple(
            MODULE._pin_suite_command(suite.cleanup_command, image_id)
        ): MODULE.CommandResult(b"", b"", 0),
        tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
    }
    runner = Runner(responses)

    with pytest.raises(MODULE.AcceptanceProducerError, match="isolated Compose suite"):
        MODULE._run_isolated_compose_suite(
            item=suite,
            targets=targets,
            source=source,
            runner=runner,
            directory=evidence,
            section="suites",
            attempt_id="run-suite-contract",
        )

    assert MODULE._pin_suite_command(suite.cleanup_command, image_id) in runner.commands
    assert runner_cleanup in runner.commands
    assert MODULE._suite_tree_sha256(source.root) == source.tree_sha256


def test_failed_suite_publishes_bounded_private_canonical_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-failure"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    assert suite.preflight_command is not None
    capture_limit = 32 * 1024
    stdout = b"stdout-prefix\n" + (b"o" * (capture_limit + 97)) + b"stdout-tail\n"
    stderr = b"stderr-prefix\n" + (b"e" * (capture_limit + 53)) + b"stderr-tail\n"
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect_command): MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(suite.preflight_command): MODULE.CommandResult(b"", b"", 0),
        tuple(MODULE._pin_suite_command(suite.command, image_id)): MODULE.CommandResult(
            stdout, stderr, 23
        ),
        tuple(
            MODULE._pin_suite_command(suite.cleanup_command, image_id)
        ): MODULE.CommandResult(b"cleanup output must not be retained", b"", 0),
        tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
    }
    runner = Runner(responses)
    monkeypatch.setenv("AILERON_AMBIENT_SECRET_NAME", "ambient-secret-value")

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"suites-{run_id}-failure.json"
    artifact_raw = artifact.read_bytes()
    document = json.loads(artifact_raw)
    expected_failure = {
        "errorType": "AcceptanceProducerError",
        "exitCode": 23,
        "phase": "run",
        "stderr": {
            "byteLength": len(stderr),
            "capturedByteLength": capture_limit,
            "sha256": hashlib.sha256(stderr).hexdigest(),
            "tailBase64": base64.b64encode(stderr[-capture_limit:]).decode("ascii"),
            "truncated": True,
        },
        "stdout": {
            "byteLength": len(stdout),
            "capturedByteLength": capture_limit,
            "sha256": hashlib.sha256(stdout).hexdigest(),
            "tailBase64": base64.b64encode(stdout[-capture_limit:]).decode("ascii"),
            "truncated": True,
        },
    }
    assert document == {
        "attemptId": run_id,
        "failures": [expected_failure],
        "schemaVersion": "aileron-suite-failure/v1",
        "section": "suites",
        "suite": "docker",
    }
    assert artifact_raw == (
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    assert len(artifact_raw) <= 192 * 1024
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()
    assert not (evidence / "suites.json").exists()
    assert MODULE._pin_suite_command(suite.cleanup_command, image_id) in runner.commands
    assert runner_cleanup in runner.commands
    error_text = str(captured.value)
    assert captured.value.artifact == {
        "file": artifact.name,
        "sha256": hashlib.sha256(artifact_raw).hexdigest(),
    }
    assert captured.value.failures == [
        {
            "errorType": "AcceptanceProducerError",
            "exitCode": 23,
            "message": "fixed acceptance probe failed",
            "phase": "run",
        }
    ]
    assert "stdout-tail" not in error_text
    assert "stderr-tail" not in error_text
    assert "AILERON_AMBIENT_SECRET_NAME" not in artifact_raw.decode("ascii")
    assert "ambient-secret-value" not in artifact_raw.decode("ascii")


def test_suite_runner_inspect_failure_preserves_command_diagnostics(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-inspect-failure"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    cleanup_command = MODULE._pin_suite_command(
        suite.cleanup_command, suite.runner_image
    )
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect_command): MODULE.CommandResult(
            b"inspect-stream-marker", b"inspect-error-marker", 31
        ),
        tuple(cleanup_command): MODULE.CommandResult(b"", b"", 0),
        tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
    }
    runner = Runner(responses)

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"suites-{run_id}-failure.json"
    document = json.loads(artifact.read_bytes())
    assert document["failures"] == [
        {
            "errorType": "AcceptanceProducerError",
            "exitCode": 31,
            "phase": "runnerIdentity",
            "stderr": {
                "byteLength": len(b"inspect-error-marker"),
                "capturedByteLength": len(b"inspect-error-marker"),
                "sha256": hashlib.sha256(b"inspect-error-marker").hexdigest(),
                "tailBase64": base64.b64encode(b"inspect-error-marker").decode("ascii"),
                "truncated": False,
            },
            "stdout": {
                "byteLength": len(b"inspect-stream-marker"),
                "capturedByteLength": len(b"inspect-stream-marker"),
                "sha256": hashlib.sha256(b"inspect-stream-marker").hexdigest(),
                "tailBase64": base64.b64encode(b"inspect-stream-marker").decode(
                    "ascii"
                ),
                "truncated": False,
            },
        }
    ]
    assert cleanup_command in runner.commands
    assert runner_cleanup in runner.commands
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()
    assert not (evidence / "suites.json").exists()
    assert "inspect-stream-marker" not in str(captured.value)
    assert "inspect-error-marker" not in str(captured.value)


@pytest.mark.parametrize(
    ("failed_phase", "exit_code"),
    [("build", 33), ("preflight", 37)],
)
def test_suite_setup_command_failures_use_the_same_diagnostic_capture(
    tmp_path: Path,
    failed_phase: str,
    exit_code: int,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = f"run-suite-{failed_phase}-failure"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    assert suite.preflight_command is not None
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
    }
    if failed_phase == "build":
        responses[tuple(suite.build_command)] = MODULE.CommandResult(
            b"build-stream-marker", b"build-error-marker", exit_code
        )
        cleanup_command = MODULE._pin_suite_command(
            suite.cleanup_command, suite.runner_image
        )
    else:
        responses[tuple(suite.build_command)] = MODULE.CommandResult(b"built", b"", 0)
        responses[tuple(inspect_command)] = MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        )
        responses[tuple(suite.preflight_command)] = MODULE.CommandResult(
            b"preflight-stream-marker", b"preflight-error-marker", exit_code
        )
        cleanup_command = MODULE._pin_suite_command(suite.cleanup_command, image_id)
        responses[tuple(runner_cleanup)] = MODULE.CommandResult(b"untagged\n", b"", 0)
    responses[tuple(cleanup_command)] = MODULE.CommandResult(b"", b"", 0)
    runner = Runner(responses)

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"suites-{run_id}-failure.json"
    failure = json.loads(artifact.read_bytes())["failures"][0]
    stdout = f"{failed_phase}-stream-marker".encode()
    stderr = f"{failed_phase}-error-marker".encode()
    assert failure["phase"] == failed_phase
    assert failure["exitCode"] == exit_code
    assert base64.b64decode(failure["stdout"]["tailBase64"], validate=True) == stdout
    assert base64.b64decode(failure["stderr"]["tailBase64"], validate=True) == stderr
    assert cleanup_command in runner.commands
    assert (runner_cleanup in runner.commands) is (failed_phase == "preflight")
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()
    assert not (evidence / "suites.json").exists()
    assert stdout.decode() not in str(captured.value)
    assert stderr.decode() not in str(captured.value)


@pytest.mark.parametrize(
    ("run_returncode", "expected_phases"),
    [
        (0, ["cleanup"]),
        (17, ["run", "cleanup"]),
    ],
)
def test_suite_cleanup_failure_preserves_each_failed_phase_without_success_report(
    tmp_path: Path,
    run_returncode: int,
    expected_phases: list[str],
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = f"run-suite-cleanup-{run_returncode}"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    assert suite.preflight_command is not None
    runner_cleanup = ["docker", "image", "rm", suite.runner_image]
    capture_limit = 32 * 1024
    primary_stdout = (
        b"primary-prefix" + (b"p" * (capture_limit + 31)) + b"primary-stream-marker"
    )
    primary_stderr = (
        b"primary-error-prefix"
        + (b"q" * (capture_limit + 37))
        + b"primary-error-marker"
    )
    cleanup_stdout = (
        b"cleanup-prefix" + (b"c" * (capture_limit + 41)) + b"cleanup-stream-marker"
    )
    cleanup_stderr = (
        b"cleanup-error-prefix"
        + (b"d" * (capture_limit + 43))
        + b"cleanup-error-marker"
    )
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect_command): MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(suite.preflight_command): MODULE.CommandResult(b"", b"", 0),
        tuple(MODULE._pin_suite_command(suite.command, image_id)): MODULE.CommandResult(
            primary_stdout, primary_stderr, run_returncode
        ),
        tuple(
            MODULE._pin_suite_command(suite.cleanup_command, image_id)
        ): MODULE.CommandResult(cleanup_stdout, cleanup_stderr, 29),
        tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
    }
    runner = Runner(responses)

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"suites-{run_id}-failure.json"
    artifact_raw = artifact.read_bytes()
    document = json.loads(artifact_raw)
    failures = document["failures"]
    assert [failure["phase"] for failure in failures] == expected_phases
    assert [failure["exitCode"] for failure in failures] == (
        [29] if run_returncode == 0 else [17, 29]
    )
    expected_streams = (
        [(cleanup_stdout, cleanup_stderr)]
        if run_returncode == 0
        else [
            (primary_stdout, primary_stderr),
            (cleanup_stdout, cleanup_stderr),
        ]
    )
    decoded_streams = [
        (
            base64.b64decode(failure["stdout"]["tailBase64"], validate=True),
            base64.b64decode(failure["stderr"]["tailBase64"], validate=True),
        )
        for failure in failures
    ]
    assert decoded_streams == [
        (stdout[-capture_limit:], stderr[-capture_limit:])
        for stdout, stderr in expected_streams
    ]
    for failure, (stdout, stderr) in zip(failures, expected_streams):
        assert failure["stdout"]["byteLength"] == len(stdout)
        assert failure["stdout"]["sha256"] == hashlib.sha256(stdout).hexdigest()
        assert failure["stdout"]["truncated"] is True
        assert failure["stderr"]["byteLength"] == len(stderr)
        assert failure["stderr"]["sha256"] == hashlib.sha256(stderr).hexdigest()
        assert failure["stderr"]["truncated"] is True
    assert artifact_raw == (
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert len(artifact_raw) <= 192 * 1024
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()
    assert not (evidence / "suites.json").exists()
    assert MODULE._pin_suite_command(suite.cleanup_command, image_id) in runner.commands
    assert runner_cleanup in runner.commands
    error_text = str(captured.value)
    for marker in (
        "primary-stream-marker",
        "primary-error-marker",
        "cleanup-stream-marker",
        "cleanup-error-marker",
    ):
        assert marker not in error_text


def test_suite_maximum_failure_phases_publish_bounded_diagnostics_and_release_owned_resources(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-maximum-failure"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    image_id = f"sha256:{'d' * 64}"
    inspect_command = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    image_cleanup_command = ["docker", "image", "rm", suite.runner_image]
    assert suite.preflight_command is not None
    capture_limit = 32 * 1024

    def failure_stream(marker: bytes) -> bytes:
        return b"prefix-" + (marker[:1] * (capture_limit + 97)) + marker

    run_stdout = failure_stream(b"run-stdout-marker")
    run_stderr = failure_stream(b"run-stderr-marker")
    cleanup_stdout = failure_stream(b"cleanup-stdout-marker")
    cleanup_stderr = failure_stream(b"cleanup-stderr-marker")
    image_stdout = failure_stream(b"image-stdout-marker")
    image_stderr = failure_stream(b"image-stderr-marker")
    responses = {
        **_trust_responses(targets),
        **_clean_suite_source_responses(targets),
        tuple(suite.build_command): MODULE.CommandResult(b"built", b"", 0),
        tuple(inspect_command): MODULE.CommandResult(
            f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
        ),
        tuple(suite.preflight_command): MODULE.CommandResult(b"", b"", 0),
        tuple(MODULE._pin_suite_command(suite.command, image_id)): MODULE.CommandResult(
            run_stdout, run_stderr, 17
        ),
        tuple(
            MODULE._pin_suite_command(suite.cleanup_command, image_id)
        ): MODULE.CommandResult(cleanup_stdout, cleanup_stderr, 29),
        tuple(image_cleanup_command): MODULE.CommandResult(
            image_stdout, image_stderr, 41
        ),
    }
    runner = Runner(responses)

    with pytest.raises(MODULE.SuiteExecutionError) as captured:
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    artifact = evidence / f"suites-{run_id}-failure.json"
    artifact_raw = artifact.read_bytes()
    document = json.loads(artifact_raw)
    assert [failure["phase"] for failure in document["failures"]] == [
        "run",
        "cleanup",
        "runnerImageCleanup",
    ]
    assert [failure["exitCode"] for failure in document["failures"]] == [17, 29, 41]
    assert artifact_raw == (
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert len(artifact_raw) <= 384 * 1024
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()
    assert image_cleanup_command in runner.commands
    assert captured.value.artifact == {
        "file": artifact.name,
        "sha256": hashlib.sha256(artifact_raw).hexdigest(),
    }
    assert [failure["phase"] for failure in captured.value.failures] == [
        "run",
        "cleanup",
        "runnerImageCleanup",
    ]
    error_text = str(captured.value)
    for marker in (
        "run-stdout-marker",
        "run-stderr-marker",
        "cleanup-stdout-marker",
        "cleanup-stderr-marker",
        "image-stdout-marker",
        "image-stderr-marker",
    ):
        assert marker not in error_text


def test_suite_runner_identity_uses_actual_architecture_and_revision(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    suite = MODULE.build_suite_commands(targets)[1]
    inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        suite.runner_image,
    ]
    runner = Runner(
        {
            tuple(inspect): MODULE.CommandResult(
                f"sha256:{'d' * 64}\tarm64\t{targets.commit}\n".encode(), b"", 0
            )
        }
    )

    with pytest.raises(MODULE.AcceptanceProducerError, match="runner image provenance"):
        MODULE._inspect_runner_identity(
            result=runner(inspect),
            image=suite.runner_image,
            commit=targets.commit,
            suite_name=suite.name,
            build_command=suite.build_command,
        )


def test_suite_compose_targets_are_tracked_and_do_not_install_at_runtime(
    tmp_path: Path,
) -> None:
    for suite in MODULE.build_suite_commands(_targets(tmp_path)):
        command = suite.command
        if "run" not in command:
            continue
        manifest_path = ROOT / command[command.index("--file") + 1]
        service_name = command[-1]
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        assert service_name in manifest["services"], suite.name
        service = manifest["services"][service_name]
        assert "build" in service, suite.name
        assert service.get("platform") == "linux/amd64", suite.name
        compose_args = service["build"].get("args", {})
        for argument_name, argument_value in MODULE.SUITE_BUILD_ARGUMENTS.get(
            suite.name, ()
        ):
            assert compose_args.get(argument_name) == argument_value, (
                suite.name,
                argument_name,
            )
        if suite.name in {"frontend", "manager", "operator"}:
            image_args = {
                name: value
                for name, value in service["build"].get("args", {}).items()
                if name.endswith("_IMAGE")
            }
            assert image_args, suite.name
            assert all("@sha256:" in value for value in image_args.values()), (
                suite.name,
                image_args,
            )
        runtime_command = json.dumps(service.get("command", ""))
        for runtime_install in (
            "pip install",
            "npm ci",
            "uv sync",
            "go mod download",
            "apk add",
        ):
            assert runtime_install not in runtime_command, suite.name


def test_suite_sidecars_are_digest_and_platform_pinned(tmp_path: Path) -> None:
    manifest_paths = {
        ROOT / suite.command[suite.command.index("--file") + 1]
        for suite in MODULE.build_suite_commands(_targets(tmp_path))
        if "run" in suite.command
    }

    for manifest_path in manifest_paths:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for name, service in manifest["services"].items():
            if "build" in service:
                continue
            assert "@sha256:" in service.get("image", ""), (
                manifest_path,
                name,
            )
            assert service.get("platform") == "linux/amd64", (
                manifest_path,
                name,
            )


def test_docker_suite_is_exact_source_clean_volume_black_box(tmp_path: Path) -> None:
    suite = MODULE.build_suite_commands(_targets(tmp_path))[0]
    manifest = yaml.safe_load(
        (ROOT / "scripts/test/compose-e2e/docker-compose.acceptance.yml").read_text()
    )
    service = manifest["services"]["compose-e2e-test"]
    dockerfile = (ROOT / service["build"]["dockerfile"]).read_text()
    runner = (ROOT / "scripts/test/compose-e2e/run.sh").read_text()
    black_box = (ROOT / "scripts/test/compose-e2e/e2e.py").read_text()
    renderer = (ROOT / "scripts/test/compose-e2e/render_compose.py").read_text()

    assert suite.command[-1] == "compose-e2e-test"
    assert service["platform"] == "linux/amd64"
    assert "docker:27-cli@sha256:" in service["build"]["args"]["DOCKER_CLI_IMAGE"]
    assert "LABEL org.opencontainers.image.revision=${SOURCE_REVISION}" in dockerfile
    assert "COMPOSE_E2E_SOURCE_REVISION" in runner
    assert "docker buildx bake" in runner
    assert "*.labels.org.opencontainers.image.revision" in runner
    assert "down --volumes --remove-orphans" in runner
    assert 'if [ -f "$env_file" ] && [ -f "$compose_file" ]' in runner
    assert "remaining_volume_names" in runner
    assert "docker network ls --format '{{.Name}}'" in runner
    assert "label=com.docker.compose.project=$inventory_project" in runner
    assert "Compose image is neither digest-pinned nor exact-source" in runner
    assert "--no-build --pull never" in runner
    assert 'docker restart --time 30 "$keycloak_container"' in runner
    assert '"$keycloak_started_before" != "$keycloak_started_after"' in runner
    assert '"$keycloak_volume_before" = "$keycloak_volume_after"' in runner
    assert renderer.count("@sha256:") >= 5
    assert 'configuration["platform"] = "linux/amd64"' in renderer
    for expected in (
        "code_challenge_method",
        "/api/v1/oauth2/session",
        "/components/runtime/restart",
        "/api/v1/oauth2/logout",
        'client.request("GET", provider_logout)',
        "verify_keycloak_admin_console_login()",
        "security-admin-console",
        'KEYCLOAK_MASTER_REALM_URL = f"{KEYCLOAK_BASE_URL}/realms/master"',
        "KEYCLOAK_AILERON_AUTHORIZATION_URL",
        "OIDC_CALLBACK_URI",
        "matching_redirects",
        "/protocol/openid-connect/auth",
        "/protocol/openid-connect/token",
        "/admin/master/console/",
        "/admin/realms/master",
        "code_verifier",
        "keycloak-bootstrap-admin-password",
    ):
        assert expected in black_box


def test_compose_e2e_renderer_pins_every_literal_sidecar_image(
    tmp_path: Path,
) -> None:
    renderer_path = ROOT / "scripts/test/compose-e2e/render_compose.py"
    specification = importlib.util.spec_from_file_location(
        "compose_e2e_renderer", renderer_path
    )
    assert specification and specification.loader
    renderer_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(renderer_module)
    output = tmp_path / "compose.yml"

    renderer_module.render(
        ROOT / "docker-compose.yml",
        ROOT / "docker-compose.bundled-data-services.yml",
        output,
        "aileron-compose-e2e-test-network",
        "/exact/source",
        "/exact/state",
    )

    rendered = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert rendered["services"]["e2e-runner"]["secrets"] == [
        "local-oidc-platform-admin-password",
        "keycloak-bootstrap-admin-password",
    ]
    for name, service in rendered["services"].items():
        image = service.get("image")
        assert isinstance(image, str) and image, name
        if image.startswith("${"):
            assert "must be set" in image, name
            continue
        assert "@sha256:" in image, (name, image)


def test_compose_e2e_pulls_only_missing_digest_images() -> None:
    runner = (ROOT / "scripts/test/compose-e2e/run.sh").read_text()
    helper = runner[
        runner.index("ensure_digest_image()") : runner.index("random_hex()")
    ]

    assert 'case "$image" in' in helper
    assert "*@sha256:*)" in helper
    assert 'if ! docker image inspect "$image"' in helper
    assert 'docker pull --platform linux/amd64 "$image"' in helper
    assert "refusing to pull a mutable image reference" in helper
    assert runner.count("docker pull ") == 1
    assert '*@sha256:*) ensure_digest_image "$image" ;;' in runner
    assert runner.index('ensure_digest_image "$helper_image"') < runner.index(
        "docker run --rm --pull never"
    )
    assert "--no-build --pull never" in runner


def test_suites_require_the_signed_release_image_inventory_before_commands(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    runner = Runner(_trust_responses(targets))

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="suites require --image-inventory",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
        )

    assert runner.commands == _trust_commands(targets)


def test_suites_do_not_materialize_source_before_inventory_snapshot_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)._replace(workspace_id=None, user_subject=None)
    inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-inventory-read-failure"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    original_read = MODULE._read_private_bytes

    def fail_inventory_snapshot(
        path: Path,
        description: str,
        *,
        maximum_size: int = 4 * 1024 * 1024,
    ) -> bytes:
        if description == "signed suite image inventory":
            raise MODULE.AcceptanceProducerError(
                "signed suite image inventory snapshot is unavailable"
            )
        return original_read(path, description, maximum_size=maximum_size)

    monkeypatch.setattr(MODULE, "_read_private_bytes", fail_inventory_snapshot)
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
        }
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="^signed suite image inventory snapshot is unavailable$",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=inventory,
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    assert not source_root.exists()
    assert not (evidence / "suites.json").exists()


def test_suites_reject_dirty_source_before_any_runner_build(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    head_command = ["git", "-C", str(ROOT), "rev-parse", "HEAD"]
    status_command = [
        "git",
        "-C",
        str(ROOT),
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ]
    responses = {
        **_trust_responses(targets),
        tuple(head_command): MODULE.CommandResult(
            f"{targets.commit}\n".encode(), b"", 0
        ),
        tuple(status_command): MODULE.CommandResult(
            b"?? untracked-suite-input\n", b"", 0
        ),
    }
    runner = Runner(responses)

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="acceptance source worktree must be clean including untracked files",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=_signed_inventory(tmp_path, targets),
            runner=runner,
        )

    assert runner.commands[len(_trust_commands(targets)) :] == [
        head_command,
        status_command,
    ]


def test_suites_reject_a_head_that_does_not_match_the_target_before_any_runner_build(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    head_command, status_command = _suite_git_commands(targets)
    responses = {
        **_trust_responses(targets),
        tuple(head_command): MODULE.CommandResult(f"{'b' * 40}\n".encode(), b"", 0),
        tuple(status_command): MODULE.CommandResult(b"", b"", 0),
    }
    runner = Runner(responses)

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="acceptance source HEAD must exactly match the target commit",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=_signed_inventory(tmp_path, targets),
            runner=runner,
        )

    assert runner.commands[len(_trust_commands(targets)) :] == [
        head_command,
        status_command,
    ]


def test_suites_reject_root_compose_output_before_it_can_expose_host_paths(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path)
    run_id = "run-suite-contract"
    source_root = _materialized_suite_root(evidence, "suites", run_id)
    docker_suite = MODULE.build_suite_commands(targets, run_id, source_root)[0]
    docker_config = docker_suite.preflight_command
    assert docker_config is not None
    image_id = f"sha256:{'d' * 64}"
    inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        docker_suite.runner_image,
    ]
    runner_cleanup = ["docker", "image", "rm", docker_suite.runner_image]
    runner = Runner(
        {
            **_trust_responses(targets),
            **_clean_suite_source_responses(targets),
            tuple(docker_suite.build_command): MODULE.CommandResult(b"built", b"", 0),
            tuple(inspect): MODULE.CommandResult(
                f"{image_id}\tamd64\t{targets.commit}\n".encode(), b"", 0
            ),
            tuple(docker_config): MODULE.CommandResult(
                str(source_root).encode(), b"", 0
            ),
            tuple(
                MODULE._pin_suite_command(docker_suite.cleanup_command, image_id)
            ): MODULE.CommandResult(b"", b"", 0),
            tuple(runner_cleanup): MODULE.CommandResult(b"untagged\n", b"", 0),
        }
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="root Compose quiet validation must not emit raw output",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=_signed_inventory(tmp_path, targets),
            runner=runner,
            run_id_factory=lambda: run_id,
        )

    assert runner_cleanup in runner.commands
    assert not source_root.exists()
    assert (evidence / "suites-source-archive.tar.gz").is_file()


def _canonical_soak_query_responses(
    targets: MODULE.ProducerTargets, identity_mode: str
) -> tuple[
    object,
    dict[tuple[str, ...], MODULE.CommandResult],
    MODULE.CommandResult,
]:
    from scripts.test.deploy.test_acceptance_evidence import _soak_raw_documents

    queries = MODULE.ACCEPTANCE_SOAK.build_query_commands(
        kubeconfig=str(targets.kubeconfig),
        context=targets.context,
        workspace_id=targets.workspace_id,
        identity_mode=identity_mode,
    )
    documents = _soak_raw_documents(identity_mode)
    pod_responses = {
        tuple(command): MODULE.CommandResult(
            json.dumps(documents[query_id]).encode(), b"", 0
        )
        for query_id, command in queries.items()
        if query_id not in {"workspace", "services"}
    }
    return (
        queries,
        pod_responses,
        MODULE.CommandResult(json.dumps(documents["services"]).encode(), b"", 0),
    )


def _workspace_soak_result(observed_generation: int) -> MODULE.CommandResult:
    from scripts.test.deploy.test_acceptance_evidence import _soak_raw_documents

    document = json.loads(
        json.dumps(_soak_raw_documents("bundledKeycloak")["workspace"])
    )
    document["items"][0]["status"]["observedGeneration"] = observed_generation
    return MODULE.CommandResult(json.dumps(document).encode(), b"", 0)


def _stub_snapshot_queries(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    queries = {
        query_id: ["kubectl", "get", query_id]
        for query_id in (
            "controllers",
            "identityPods",
            "turnPods",
            "workspacePods",
            "browserPods",
            "workspace",
            "workspaceServiceAccounts",
            "services",
            "endpointSlices",
        )
    }
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "build_query_commands",
        lambda **_kwargs: queries,
    )
    return queries


def test_soak_passes_the_complete_raw_query_set_to_snapshot_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-snapshot-module"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    calls: list[tuple[dict[str, object], dict[str, str]]] = []
    sealed = {"sha256": "f" * 64, "controllers": [], "pods": []}

    def snapshot_sample(query_documents, **identity):
        calls.append((query_documents, identity))
        return sealed

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        snapshot_sample,
        raising=False,
    )
    responses = {
        tuple(command): MODULE.CommandResult(
            json.dumps({"queryId": query_id}).encode(), b"", 0
        )
        for query_id, command in queries.items()
    }
    now = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)

    observations, sources, _, _ = MODULE._produce_soak(
        targets,
        "bundledKeycloak",
        evidence,
        lambda command, timeout_seconds=None: responses[tuple(command)],
        lambda: now,
        lambda: 0.0,
        lambda _seconds: None,
        0,
        60,
        attempt_id="run-snapshot-module",
        minimum_samples=1,
        deployment_run_id="run-deployment-epoch",
        maximum_sample_gap_seconds=75,
        maximum_clock_drift_milliseconds=2000,
        image_runtime_pairs=_soak_image_runtime_pairs(targets),
    )

    assert calls == [
        (
            {query_id: {"queryId": query_id} for query_id in queries},
            {
                "workspace_id": "workspace-1",
                "identity_mode": "bundledKeycloak",
                "commit": COMMIT,
                "deployment_run_id": "run-deployment-epoch",
                "image_runtime_pairs": _soak_image_runtime_pairs(targets),
            },
        )
    ]
    assert observations["baseline"] == sealed
    assert len(sources) == 9


@pytest.mark.parametrize(
    ("monotonic_observed", "wall_seconds", "error"),
    [
        (float("nan"), 0, "monotonic clock"),
        (76.0, 76, "cadence gap"),
        (60.0, 0, "clock drift"),
    ],
)
def test_soak_clock_failures_are_fail_fast_and_leave_a_failure_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    monotonic_observed: float,
    wall_seconds: int,
    error: str,
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / f"soak-clock-{error.replace(' ', '-')}"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        tuple(command): MODULE.CommandResult(b"{}", b"", 0)
        for command in queries.values()
    }
    monotonic_values = iter((0.0, monotonic_observed))
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    wall_values = iter((started, started + timedelta(seconds=wall_seconds)))

    with pytest.raises(MODULE.AcceptanceProducerError, match=error):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            lambda command, timeout_seconds=None: responses[tuple(command)],
            lambda: next(wall_values),
            lambda: next(monotonic_values),
            lambda _seconds: None,
            1800,
            60,
            attempt_id="run-clock-failure",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    progress = json.loads(
        max(evidence.glob("soak-run-clock-failure-progress-*.json")).read_text()
    )
    assert progress["status"] == "observations-failed"
    assert len(progress["lastFailures"]) == 1
    assert error in progress["lastFailures"][0]


def test_soak_unexpected_runner_failure_leaves_a_failure_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-runner-crash"
    evidence.mkdir(mode=0o700)
    _stub_snapshot_queries(monkeypatch)
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)

    def runner(
        _command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        raise RuntimeError("simulated runner crash")

    with pytest.raises(MODULE.AcceptanceProducerError, match="simulated runner crash"):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            runner,
            lambda: started,
            lambda: 0.0,
            lambda _seconds: None,
            1800,
            60,
            attempt_id="run-runner-crash",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    progress = [
        json.loads(path.read_text())
        for path in sorted(evidence.glob("soak-run-runner-crash-progress-*.json"))
    ]
    assert [item["status"] for item in progress] == [
        "started",
        "observations-failed",
    ]


def test_soak_unexpected_sleeper_failure_leaves_a_failure_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-sleeper-crash"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        tuple(command): MODULE.CommandResult(b"{}", b"", 0)
        for command in queries.values()
    }
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)

    def sleeper(_seconds: int) -> None:
        raise RuntimeError("simulated sleeper crash")

    with pytest.raises(MODULE.AcceptanceProducerError, match="simulated sleeper crash"):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            lambda command, timeout_seconds=None: responses[tuple(command)],
            lambda: started,
            lambda: 0.0,
            sleeper,
            1800,
            60,
            attempt_id="run-sleeper-crash",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    progress = [
        json.loads(path.read_text())
        for path in sorted(evidence.glob("soak-run-sleeper-crash-progress-*.json"))
    ]
    assert [item["status"] for item in progress] == [
        "started",
        "running",
        "observations-failed",
    ]


def test_soak_rejects_cumulative_clock_drift_before_step_drift_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-cumulative-drift"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        tuple(command): MODULE.CommandResult(b"{}", b"", 0)
        for command in queries.values()
    }
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    wall_value = started
    monotonic_value = 0.0

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds, milliseconds=750)
        monotonic_value += seconds

    with pytest.raises(MODULE.AcceptanceProducerError, match="clock drift"):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            lambda command, timeout_seconds=None: responses[tuple(command)],
            lambda: wall_value,
            lambda: monotonic_value,
            sleeper,
            1800,
            60,
            attempt_id="run-cumulative-drift",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    progress = json.loads(
        max(evidence.glob("soak-run-cumulative-drift-progress-*.json")).read_text()
    )
    assert progress["status"] == "observations-failed"


def test_soak_rejects_a_32nd_sample_instead_of_extending_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-extra-sample"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        tuple(command): MODULE.CommandResult(b"{}", b"", 0)
        for command in queries.values()
    }
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    wall_value = started
    monotonic_value = 0.0

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    with pytest.raises(MODULE.AcceptanceProducerError, match="exact sample count"):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            lambda command, timeout_seconds=None: responses[tuple(command)],
            lambda: wall_value,
            lambda: monotonic_value,
            sleeper,
            1860,
            60,
            attempt_id="run-extra-sample",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    progress = json.loads(
        max(evidence.glob("soak-run-extra-sample-progress-*.json")).read_text()
    )
    assert progress["status"] == "observations-failed"
    assert progress["sampleCount"] == 31


def test_soak_progress_rejects_a_second_started_transition(tmp_path: Path) -> None:
    evidence = tmp_path / "soak-progress-transition"
    evidence.mkdir(mode=0o700)
    started = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    common = {
        "directory": evidence,
        "attempt_id": "run-progress-transition",
        "started": started,
        "observed": None,
        "elapsed_milliseconds": 0,
        "duration": 1800,
        "samples": [],
    }
    MODULE._write_soak_progress(sequence=0, status="started", **common)

    with pytest.raises(MODULE.AcceptanceProducerError, match="transition"):
        MODULE._write_soak_progress(sequence=1, status="started", **common)


def test_soak_never_rounds_a_subminimum_elapsed_duration_up_to_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-duration-floor"
    evidence.mkdir(mode=0o700)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    monotonic_value = 0.0
    wall_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    query_count = 0

    def runner(
        _command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        nonlocal monotonic_value, wall_value, query_count
        query_count += 1
        if query_count == len(queries):
            monotonic_value += 0.9999999
            wall_value += timedelta(seconds=0.9999999)
        return MODULE.CommandResult(b"{}", b"", 0)

    def sleeper(seconds: int) -> None:
        nonlocal monotonic_value, wall_value
        monotonic_value += seconds
        wall_value += timedelta(seconds=seconds)

    observations, _, _, _ = MODULE._produce_soak(
        targets,
        "bundledKeycloak",
        evidence,
        runner,
        lambda: wall_value,
        lambda: monotonic_value,
        sleeper,
        1,
        1,
        attempt_id="run-duration-floor",
        minimum_samples=2,
        deployment_run_id="run-deployment-epoch",
        maximum_sample_gap_seconds=75,
        maximum_clock_drift_milliseconds=2000,
        image_runtime_pairs=_soak_image_runtime_pairs(targets),
    )

    assert [sample["elapsedMilliseconds"] for sample in observations["samples"]] == [
        999,
        1999,
    ]


def test_soak_validates_canonical_bytes_before_publication_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        **_trust_responses(targets),
        **{
            tuple(command): MODULE.CommandResult(b"{}", b"", 0)
            for command in queries.values()
        },
    }
    validator = MODULE._load_validator()
    canonical_report = _evidence_directory(tmp_path) / "soak.json"
    reject_in_memory = True
    validation_order: list[str] = []
    validated_raw = b""

    def validate_report_bytes(*, raw: bytes, **_kwargs):
        nonlocal validated_raw
        validation_order.append("bytes")
        assert not canonical_report.exists()
        assert raw == MODULE._canonical(json.loads(raw)) + b"\n"
        validated_raw = raw
        if reject_in_memory:
            raise validator.AcceptanceEvidenceError("rejected before publication")
        return {"sha256": hashlib.sha256(raw).hexdigest()}

    def validate_report_file(**_kwargs):
        validation_order.append("file")
        assert canonical_report.read_bytes() == validated_raw
        return {"sha256": hashlib.sha256(validated_raw).hexdigest()}

    monkeypatch.setattr(validator, "validate_report_bytes", validate_report_bytes)
    monkeypatch.setattr(validator, "validate_report_file", validate_report_file)
    monkeypatch.setattr(MODULE, "_load_validator", lambda: validator)
    wall_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0

    def clock() -> datetime:
        return wall_value

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    with pytest.raises(
        MODULE.AcceptanceProducerError, match="rejected before publication"
    ):
        MODULE.produce(
            section="soak",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=image_inventory,
            runner=Runner(responses),
            clock=clock,
            monotonic_clock=lambda: monotonic_value,
            sleeper=sleeper,
            run_id_factory=lambda: "run-publish-rejected",
        )

    assert not canonical_report.exists()
    assert validation_order == ["bytes"]
    rejected_progress = json.loads(
        max(
            canonical_report.parent.glob("soak-run-publish-rejected-progress-*.json")
        ).read_text()
    )
    assert rejected_progress["status"] == "observations-failed"
    assert rejected_progress["lastFailures"] == ["rejected before publication"]
    reject_in_memory = False
    wall_value += timedelta(minutes=1)
    monotonic_value = 0.0

    report_path = MODULE.produce(
        section="soak",
        targets=targets,
        deployment_run_id="run-20260808",
        image_inventory=image_inventory,
        runner=Runner(responses),
        clock=clock,
        monotonic_clock=lambda: monotonic_value,
        sleeper=sleeper,
        run_id_factory=lambda: "run-publish-retry",
    )

    assert report_path == canonical_report
    assert validation_order == ["bytes", "bytes", "file"]
    completed = json.loads(
        max(
            canonical_report.parent.glob("soak-run-publish-retry-progress-*.json")
        ).read_text()
    )
    assert completed["status"] == "completed"
    assert (
        completed["reportSha256"]
        == hashlib.sha256(canonical_report.read_bytes()).hexdigest()
    )


def test_soak_unexpected_readback_failure_rolls_back_and_marks_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    queries = _stub_snapshot_queries(monkeypatch)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SOAK,
        "snapshot_sample",
        lambda *_args, **_kwargs: {"sha256": "f" * 64},
        raising=False,
    )
    responses = {
        **_trust_responses(targets),
        **{
            tuple(command): MODULE.CommandResult(b"{}", b"", 0)
            for command in queries.values()
        },
    }
    validator = MODULE._load_validator()
    canonical_report = _evidence_directory(tmp_path) / "soak.json"
    monkeypatch.setattr(
        validator,
        "validate_report_bytes",
        lambda *, raw, **_kwargs: {"sha256": hashlib.sha256(raw).hexdigest()},
    )

    def crash_during_readback(**_kwargs):
        raise RuntimeError("simulated readback crash")

    monkeypatch.setattr(validator, "validate_report_file", crash_during_readback)
    monkeypatch.setattr(MODULE, "_load_validator", lambda: validator)
    wall_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    with pytest.raises(MODULE.AcceptanceProducerError, match="readback crash"):
        MODULE.produce(
            section="soak",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=image_inventory,
            runner=Runner(responses),
            clock=lambda: wall_value,
            monotonic_clock=lambda: monotonic_value,
            sleeper=sleeper,
            run_id_factory=lambda: "run-readback-crash",
        )

    assert not canonical_report.exists()
    assert not list(canonical_report.parent.glob(".soak.json.tmp-*"))
    progress = json.loads(
        max(
            canonical_report.parent.glob("soak-run-readback-crash-progress-*.json")
        ).read_text()
    )
    assert progress["status"] == "observations-failed"
    assert progress["lastFailures"] == ["simulated readback crash"]


def test_soak_query_timeout_is_terminal_and_never_completed(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    evidence = tmp_path / "soak-timeout"
    evidence.mkdir(mode=0o700)
    observed_timeouts: list[float | None] = []

    def runner(
        _command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        observed_timeouts.append(timeout_seconds)
        return MODULE.CommandResult(b"", b"acceptance command timed out\n", 124)

    now = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    with pytest.raises(MODULE.AcceptanceProducerError, match="timed out"):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            runner,
            lambda: now,
            lambda: 0.0,
            lambda _seconds: None,
            1800,
            60,
            attempt_id="run-soak-timeout",
            minimum_samples=31,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )

    assert observed_timeouts == [MODULE.SOAK_QUERY_PROCESS_TIMEOUT_SECONDS]
    progress_paths = sorted(evidence.glob("soak-run-soak-timeout-progress-*.json"))
    assert progress_paths
    progress = json.loads(progress_paths[-1].read_text())
    assert progress["status"] == "observations-failed"
    assert not any(
        json.loads(path.read_text())["status"] == "completed" for path in progress_paths
    )


def test_soak_builds_samples_from_fixed_live_queries(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    canonical_kubeconfig = _evidence_directory(tmp_path) / "kubeconfig"
    canonical_kubeconfig.write_bytes(targets.kubeconfig.read_bytes())
    canonical_kubeconfig.chmod(0o600)
    targets = targets._replace(kubeconfig=canonical_kubeconfig)
    wall_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0

    def clock() -> datetime:
        return wall_value

    def monotonic_clock() -> float:
        return monotonic_value

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    queries, query_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    runner = Runner(
        {
            **_trust_responses(targets),
            **query_responses,
            tuple(queries["workspace"]): _workspace_soak_result(4),
            tuple(queries["services"]): service_response,
        }
    )

    report_path = MODULE.produce(
        section="soak",
        targets=targets,
        deployment_run_id="run-20260808",
        image_inventory=image_inventory,
        runner=runner,
        clock=clock,
        monotonic_clock=monotonic_clock,
        sleeper=sleeper,
        soak_seconds=1800,
        sample_interval=60,
        run_id_factory=lambda: "run-soak-attempt",
    )

    report = json.loads(report_path.read_text())
    observations = report["observations"]
    assert observations["mutationMode"] == "read-only"
    assert "durationSeconds" not in observations
    assert observations["monotonicDurationMilliseconds"] == 1_800_000
    assert observations["attemptId"] == "run-soak-attempt"
    assert len(observations["baseline"]["sha256"]) == 64
    assert len(observations["samples"]) == 31
    assert [sample["sequence"] for sample in observations["samples"]] == list(range(31))
    assert all(
        set(sample)
        == {"sequence", "observedAt", "elapsedMilliseconds", "queryBindings"}
        for sample in observations["samples"]
    )
    assert len(report["sources"]) == 31 * len(queries)
    assert all(
        set(source)
        == {
            "file",
            "sha256",
            "command",
            "exitCode",
            "attemptId",
            "sampleSequence",
            "queryId",
        }
        for source in report["sources"]
    )
    progress_paths = sorted(
        report_path.parent.glob("soak-run-soak-attempt-progress-*.json")
    )
    assert len(progress_paths) == 33
    progress_documents = [json.loads(path.read_text()) for path in progress_paths]
    assert [progress["status"] for progress in progress_documents] == [
        "started",
        *(["running"] * 30),
        "observations-complete",
        "completed",
    ]
    assert all(
        progress["schemaVersion"] == "aileron-soak-progress/v2"
        for progress in progress_documents
    )
    assert all(
        set(progress)
        == {
            "schemaVersion",
            "attemptId",
            "status",
            "startedAt",
            "lastObservedAt",
            "sampleCount",
            "elapsedMilliseconds",
            "targetDurationSeconds",
            "lastFailures",
            *(
                ("reportFile", "reportSha256")
                if progress["status"] == "completed"
                else ()
            ),
        }
        for progress in progress_documents
    )
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in progress_paths)
    assert not (
        {path.name for path in progress_paths}
        & {source["file"] for source in report["sources"]}
    )
    observations_complete = json.loads(progress_paths[-2].read_text())
    completed = json.loads(progress_paths[-1].read_text())
    assert observations_complete["status"] == "observations-complete"
    assert completed["status"] == "completed"
    assert completed["reportFile"] == report_path.name
    assert (
        completed["reportSha256"]
        == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )


def test_soak_rejects_stale_workspace_observed_generation(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    clock_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0

    def clock() -> datetime:
        return clock_value

    def sleeper(seconds: int) -> None:
        nonlocal clock_value, monotonic_value
        clock_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    queries, pod_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    static_responses = {
        **_trust_responses(targets),
        **pod_responses,
        tuple(queries["services"]): service_response,
    }
    workspace_queries = 0

    def runner(
        command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        nonlocal workspace_queries
        if command == queries["workspace"]:
            workspace_queries += 1
            return _workspace_soak_result(4 if workspace_queries == 1 else 3)
        try:
            return static_responses[tuple(command)]
        except KeyError as exc:
            raise AssertionError(f"unexpected command: {command}") from exc

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="soak target Workspace is not Running",
    ):
        MODULE.produce(
            section="soak",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=image_inventory,
            runner=runner,
            clock=clock,
            monotonic_clock=lambda: monotonic_value,
            sleeper=sleeper,
            soak_seconds=1800,
            sample_interval=60,
            run_id_factory=lambda: "run-stale-generation",
        )


def test_soak_keeps_31_samples_when_live_queries_consume_wall_clock(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    canonical_kubeconfig = _evidence_directory(tmp_path) / "kubeconfig"
    canonical_kubeconfig.write_bytes(targets.kubeconfig.read_bytes())
    canonical_kubeconfig.chmod(0o600)
    targets = targets._replace(kubeconfig=canonical_kubeconfig)
    clock_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0
    queries, pod_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    responses = {
        **_trust_responses(targets),
        **pod_responses,
        tuple(queries["workspace"]): _workspace_soak_result(4),
        tuple(queries["services"]): service_response,
    }

    def clock() -> datetime:
        return clock_value

    def sleeper(seconds: int) -> None:
        nonlocal clock_value, monotonic_value
        clock_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    def runner(
        command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        nonlocal clock_value, monotonic_value
        if command[:1] == ["kubectl"]:
            clock_value += timedelta(seconds=1)
            monotonic_value += 1
        try:
            return responses[tuple(command)]
        except KeyError as exc:
            raise AssertionError(f"unexpected command: {command}") from exc

    report_path = MODULE.produce(
        section="soak",
        targets=targets,
        deployment_run_id="run-20260808",
        image_inventory=image_inventory,
        runner=runner,
        clock=clock,
        monotonic_clock=lambda: monotonic_value,
        sleeper=sleeper,
        run_id_factory=lambda: "run-query-latency",
    )

    report = json.loads(report_path.read_text())
    assert len(report["observations"]["samples"]) == 31
    assert report["observations"]["monotonicDurationMilliseconds"] == 1_809_000


@pytest.mark.parametrize(
    ("field", "replacement", "failure"),
    [
        (
            "image",
            "registry.example/aileron-browser@sha256:" + "2" * 64,
            "soak Pod spec differs from owner template",
        ),
        (
            "imageID",
            "docker-pullable://registry.example/browser@sha256:" + "4" * 64,
            "soak main container runtime identity is invalid",
        ),
        (
            "containerID",
            "containerd://" + "b" * 64,
            "soak Browser raw sources do not match",
        ),
        ("restartCount", 1, "soak Browser raw sources do not match"),
        (
            "runningStartedAt",
            "2026-08-10T00:01:00Z",
            "soak Browser raw sources do not match",
        ),
    ],
)
def test_soak_detects_exact_browser_runtime_identity_drift(
    tmp_path: Path, field: str, replacement: object, failure: str
) -> None:
    targets = _targets(tmp_path)
    clock_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0
    queries, pod_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    responses = {
        **pod_responses,
        tuple(queries["workspace"]): _workspace_soak_result(4),
        tuple(queries["services"]): service_response,
    }
    browser_queries = 0

    def clock() -> datetime:
        return clock_value

    def sleeper(seconds: int) -> None:
        nonlocal clock_value, monotonic_value
        clock_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    def runner(
        command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        nonlocal browser_queries
        result = responses[tuple(command)]
        if command != queries["browserPods"]:
            return result
        browser_queries += 1
        if browser_queries == 1:
            return result
        document = json.loads(result.stdout)
        pod = document["items"][0]
        status = pod["status"]["containerStatuses"][0]
        if field == "image":
            pod["spec"]["containers"][0]["image"] = replacement
            status["image"] = replacement
        elif field == "runningStartedAt":
            status["state"]["running"]["startedAt"] = replacement
        else:
            status[field] = replacement
        return MODULE.CommandResult(json.dumps(document).encode(), b"", 0)

    evidence = tmp_path / "soak-browser-drift"
    evidence.mkdir(mode=0o700)
    with pytest.raises(MODULE.AcceptanceProducerError, match=failure):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            runner,
            clock,
            lambda: monotonic_value,
            sleeper,
            60,
            60,
            attempt_id=f"run-browser-{field.lower()}",
            minimum_samples=2,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )


def test_soak_rejects_a_terminating_exact_browser_candidate(tmp_path: Path) -> None:
    targets = _targets(tmp_path)
    queries, pod_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    browser_document = json.loads(pod_responses[tuple(queries["browserPods"])].stdout)
    browser_document["items"][0]["metadata"][
        "deletionTimestamp"
    ] = "2026-08-10T00:01:00Z"
    responses = {
        **pod_responses,
        tuple(queries["workspace"]): _workspace_soak_result(4),
        tuple(queries["services"]): service_response,
        tuple(queries["browserPods"]): MODULE.CommandResult(
            json.dumps(browser_document).encode(), b"", 0
        ),
    }
    now = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    evidence = tmp_path / "soak-browser-terminating"
    evidence.mkdir(mode=0o700)

    with pytest.raises(
        MODULE.AcceptanceProducerError, match="soak Pod lifecycle is invalid"
    ):
        MODULE._produce_soak(
            targets,
            "bundledKeycloak",
            evidence,
            lambda command, timeout_seconds=None: responses[tuple(command)],
            lambda: now,
            lambda: 0.0,
            lambda _seconds: None,
            0,
            60,
            attempt_id="run-browser-terminating",
            minimum_samples=1,
            deployment_run_id="run-deployment-epoch",
            maximum_sample_gap_seconds=75,
            maximum_clock_drift_milliseconds=2000,
            image_runtime_pairs=_soak_image_runtime_pairs(targets),
        )


def test_soak_uses_the_same_nine_cluster_queries_for_both_identity_modes(
    tmp_path: Path,
) -> None:
    targets = _targets(tmp_path)
    bundled_queries = MODULE.ACCEPTANCE_SOAK.build_query_commands(
        kubeconfig=str(targets.kubeconfig),
        context=targets.context,
        workspace_id=targets.workspace_id,
        identity_mode="bundledKeycloak",
    )
    external_queries = MODULE.ACCEPTANCE_SOAK.build_query_commands(
        kubeconfig=str(targets.kubeconfig),
        context=targets.context,
        workspace_id=targets.workspace_id,
        identity_mode="externalOidc",
    )
    assert bundled_queries == external_queries
    assert set(bundled_queries) == {
        "controllers",
        "identityPods",
        "turnPods",
        "workspacePods",
        "browserPods",
        "workspace",
        "workspaceServiceAccounts",
        "services",
        "endpointSlices",
    }
    for query_id, namespace in (
        ("identityPods", "aileron-identity-system"),
        ("turnPods", "aileron-turn-system"),
        ("workspacePods", "workspace-system"),
    ):
        command = bundled_queries[query_id]
        assert "--all-namespaces" in command
        assert "--namespace" not in command
        assert command[command.index("--field-selector") + 1] == (
            f"metadata.namespace={namespace}"
        )
    service_account_query = bundled_queries["workspaceServiceAccounts"]
    assert service_account_query[service_account_query.index("get") + 1] == (
        "serviceaccounts"
    )
    assert (
        service_account_query[service_account_query.index("--namespace") + 1]
        == "workspace-system"
    )


@pytest.mark.parametrize(
    ("soak_seconds", "sample_interval"),
    [(1799, 60), (1800, 61)],
)
def test_public_soak_producer_rejects_noncanonical_execution_policy(
    tmp_path: Path, soak_seconds: int, sample_interval: int
) -> None:
    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="soak execution policy is not canonical",
    ):
        MODULE.produce(
            section="soak",
            targets=_targets(tmp_path),
            deployment_run_id="run-20260808",
            soak_seconds=soak_seconds,
            sample_interval=sample_interval,
        )


@pytest.mark.parametrize(
    ("identity_mode", "issuer_url", "client_id"),
    [
        (
            "bundledKeycloak",
            "https://keycloak.apps.rke.soez.tw/realms/aileron",
            "aileron-frontend",
        ),
        (
            "externalOidc",
            "https://login.example.test/tenant",
            "external-client",
        ),
    ],
)
def test_soak_identity_mode_is_bound_to_canonical_installation_identity(
    tmp_path: Path,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
) -> None:
    targets = _targets(tmp_path)._replace(
        issuer_url=issuer_url,
        client_id=client_id,
    )
    identity_document = {
        **IDENTITY_DOCUMENT,
        "identityMode": identity_mode,
        "issuerUrl": issuer_url,
        "clientId": client_id,
    }
    raw = (json.dumps(identity_document, indent=2, sort_keys=True) + "\n").encode()
    identity_path = (
        MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE
        / "installation-identity.json"
    )
    identity_path.write_bytes(raw)
    identity_path.chmod(0o600)
    trust = MODULE.ACCEPTANCE_CLUSTER.ClusterAcceptanceTrust(
        KEY,
        CLUSTER_UID,
        hashlib.sha256(raw).hexdigest(),
        SECRET_UID,
        "19",
        ACCEPTANCE_NAMESPACE_UID,
        "17",
    )

    assert MODULE._installation_identity_mode(targets, trust) == identity_mode


@pytest.mark.parametrize(
    "replacement",
    [True, False],
    ids=["pod-replacement", "container-restart-delta"],
)
def test_soak_fails_closed_on_pod_replacement_or_restart_delta(
    tmp_path: Path, replacement: bool
) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_soak_inventory(tmp_path, targets)
    queries, query_responses, service_response = _canonical_soak_query_responses(
        targets, "bundledKeycloak"
    )
    responses = {
        **_trust_responses(targets),
        **query_responses,
        tuple(queries["workspace"]): _workspace_soak_result(4),
        tuple(queries["services"]): service_response,
    }
    wall_value = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    monotonic_value = 0.0
    workspace_pod_queries = 0

    def runner(
        command: list[str], timeout_seconds: float | None = None
    ) -> MODULE.CommandResult:
        nonlocal workspace_pod_queries
        result = responses[tuple(command)]
        if command != queries["workspacePods"]:
            return result
        workspace_pod_queries += 1
        if workspace_pod_queries == 1:
            return result
        document = json.loads(result.stdout)
        pod = next(
            item
            for item in document["items"]
            if item["metadata"]["labels"].get("aileron.io/component")
            == "workspace-runtime"
        )
        if replacement:
            pod["metadata"]["uid"] += "-replacement"
        else:
            pod["status"]["containerStatuses"][0]["restartCount"] = 1
        return MODULE.CommandResult(json.dumps(document).encode(), b"", 0)

    def sleeper(seconds: int) -> None:
        nonlocal wall_value, monotonic_value
        wall_value += timedelta(seconds=seconds)
        monotonic_value += seconds

    failure = (
        "Workspace component status does not bind its running Pod"
        if replacement
        else "raw snapshot drift"
    )
    with pytest.raises(MODULE.AcceptanceProducerError, match=failure):
        MODULE.produce(
            section="soak",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=image_inventory,
            runner=runner,
            clock=lambda: wall_value,
            monotonic_clock=lambda: monotonic_value,
            sleeper=sleeper,
            run_id_factory=lambda: f"run-pod-drift-{str(replacement).lower()}",
        )


def test_python39_clean_reset_separates_inventory_expected_from_live_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path)
    inventory = {
        "context": targets.context,
        "namespaces": [
            {"name": name}
            for name in [
                "aileron-identity-system",
                "aileron-turn-system",
                "workspace-system",
            ]
        ],
        "releases": [],
        "resources": [
            {
                "apiVersion": "platform.aileron.io/v1alpha1",
                "kind": "Workspace",
                "namespace": "workspace-system",
                "name": "workspace-1",
            },
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "namespace": "workspace-system",
                "name": "data-workspace-1",
            },
        ],
        "persistentVolumes": [
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-1",
                "uid": "pv-1-uid",
                "backendLocator": {
                    "type": "nfs",
                    "server": "nfs.example.test",
                    "path": "/exports/workspace-1",
                },
            }
        ],
    }
    snapshot_path = MODULE.ACCEPTANCE_SNAPSHOT.write_reset_snapshot(
        directory=evidence,
        private_root=tmp_path,
        inventory=inventory,
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id="run-20260808",
        backend_attestor=_canonical_backend_binding(),
        created_at=datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc),
    )
    responses = _trust_responses(targets)
    for command in MODULE.build_clean_reset_commands(targets):
        responses[tuple(command)] = MODULE.CommandResult(b'{"items":[]}', b"", 0)
    snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    _mock_backend_post_reset(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        targets=targets,
        run_id="run-20260808",
        snapshot_sha256=snapshot_sha256,
        backend_targets=[
            {
                "name": "pv-1",
                "uid": "pv-1-uid",
                "locator": inventory["persistentVolumes"][0]["backendLocator"],
            }
        ],
    )
    runner = Runner(responses)

    report_path = MODULE.produce(
        section="cleanReset",
        targets=targets,
        deployment_run_id="run-20260808",
        reset_phase="post-reset",
        expected_reset_snapshot_digest=snapshot_sha256,
        runner=runner,
    )

    report = json.loads(report_path.read_text())
    assert "workspace" not in report
    assert report["observations"]["expected"]["pvs"] == ["pv-1"]
    assert report["observations"]["observedAbsent"]["pvs"] == ["pv-1"]
    assert report["observations"]["expected"]["backendTargets"] == [
        {
            "persistentVolume": {"name": "pv-1", "uid": "pv-1-uid"},
            "locatorSha256": hashlib.sha256(
                MODULE._canonical(inventory["persistentVolumes"][0]["backendLocator"])
            ).hexdigest(),
        }
    ]
    assert report["observations"]["backendCleanupResults"]["allAbsent"] is True
    assert report["observations"]["backendPostResetVerification"]["allAbsent"] is True
    assert len(report["sources"]) == 8
    cleanup_source = next(
        source
        for source in report["sources"]
        if source["file"] == "clean-reset-backend-cleanup-results.json"
    )
    post_source = next(
        source
        for source in report["sources"]
        if source["file"] == "clean-reset-backend-post-reset-verification.json"
    )
    assert cleanup_source["command"][1].endswith("/reset_plan.py")
    assert "--execute" in cleanup_source["command"]
    assert "--acceptance-directory" not in cleanup_source["command"]
    assert "--inventory-output" not in cleanup_source["command"]
    assert "--execution-state-output" not in cleanup_source["command"]
    assert "--execution-lock-file" not in cleanup_source["command"]
    assert post_source["command"][0] == MODULE.PRODUCER_EXECUTABLE


def test_clean_reset_accepts_an_already_clean_empty_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = _targets(tmp_path)
    evidence = _evidence_directory(tmp_path, "run-20260808-clean")
    snapshot_path = MODULE.ACCEPTANCE_SNAPSHOT.write_reset_snapshot(
        directory=evidence,
        private_root=tmp_path,
        inventory={
            "context": targets.context,
            "namespaces": [],
            "releases": [],
            "resources": [],
            "persistentVolumes": [],
        },
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id="run-20260808-clean",
        backend_attestor=_canonical_backend_binding(),
        created_at=datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc),
    )
    responses = _trust_responses(targets)
    for command in MODULE.build_clean_reset_commands(targets):
        responses[tuple(command)] = MODULE.CommandResult(b'{"items":[]}', b"", 0)
    snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    _mock_backend_post_reset(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        targets=targets,
        run_id="run-20260808-clean",
        snapshot_sha256=snapshot_sha256,
        backend_targets=[],
    )

    report_path = MODULE.produce(
        section="cleanReset",
        targets=targets,
        deployment_run_id="run-20260808-clean",
        reset_phase="post-reset",
        expected_reset_snapshot_digest=snapshot_sha256,
        runner=Runner(responses),
    )

    report = json.loads(report_path.read_text())
    assert report["observations"]["expected"] == {
        "namespaces": [],
        "workspaceCRs": [],
        "pvcs": [],
        "pvs": [],
        "backendTargets": [],
    }
    assert report["observations"]["observedAbsent"] == {
        "namespaces": [],
        "workspaceCRs": [],
        "pvcs": [],
        "pvs": [],
    }
    assert report["observations"]["backendCleanupResults"]["targetResultDigests"] == []
    assert (
        report["observations"]["backendPostResetVerification"]["targetResultDigests"]
        == []
    )


def _empty_clean_reset_resume_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[object, str, Runner, dict[str, int]]:
    targets = _targets(tmp_path)
    run_id = "run-resume00"
    evidence = MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=targets.commit,
        deployment_run_id=run_id,
        error_type=MODULE.AcceptanceProducerError,
    )
    snapshot_path = MODULE.ACCEPTANCE_SNAPSHOT.write_reset_snapshot(
        directory=evidence,
        private_root=tmp_path,
        inventory={
            "context": targets.context,
            "namespaces": [],
            "releases": [],
            "resources": [],
            "persistentVolumes": [],
        },
        key=KEY,
        context=targets.context,
        commit=targets.commit,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=run_id,
        backend_attestor=_canonical_backend_binding(),
        created_at=datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc),
    )
    snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    responses = _trust_responses(targets)
    for command in MODULE.build_clean_reset_commands(targets):
        responses[tuple(command)] = MODULE.CommandResult(b'{"items":[]}', b"", 0)
    _, _, calls = _mock_backend_post_reset(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        targets=targets,
        run_id=run_id,
        snapshot_sha256=snapshot_sha256,
        backend_targets=[],
    )
    return targets, snapshot_sha256, Runner(responses), calls


def _produce_empty_clean_reset_post(
    *, targets, snapshot_sha256: str, runner: Runner
) -> Path:
    return MODULE.produce(
        section="cleanReset",
        targets=targets,
        deployment_run_id="run-resume00",
        reset_phase="post-reset",
        expected_reset_snapshot_digest=snapshot_sha256,
        runner=runner,
    )


def test_clean_reset_resumes_after_cleanup_source_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets, snapshot_sha256, runner, calls = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    verifier = MODULE.BACKEND_ATTESTOR.verify_signed_backend_absence

    def crash_before_post_source(_inputs):
        raise RuntimeError("simulated crash after cleanup source")

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "verify_signed_backend_absence",
        crash_before_post_source,
    )
    with pytest.raises(RuntimeError, match="after cleanup source"):
        _produce_empty_clean_reset_post(
            targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
        )
    evidence = _evidence_directory(tmp_path, "run-resume00")
    assert (evidence / "clean-reset-backend-cleanup-results.json").is_file()
    assert not (evidence / "clean-reset-backend-post-reset-verification.json").exists()

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "verify_signed_backend_absence",
        verifier,
    )
    report = _produce_empty_clean_reset_post(
        targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
    )

    assert report.is_file()
    assert calls["verify"] == 1


def test_clean_reset_resumes_after_post_source_crash_without_new_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets, snapshot_sha256, runner, calls = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    writer = MODULE._write_private_snapshot

    def crash_before_report(path: Path, content: bytes, **kwargs) -> None:
        if path.name == "cleanReset.json":
            raise RuntimeError("simulated crash after post source")
        writer(path, content, **kwargs)

    monkeypatch.setattr(MODULE, "_write_private_snapshot", crash_before_report)
    with pytest.raises(RuntimeError, match="after post source"):
        _produce_empty_clean_reset_post(
            targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
        )
    evidence = _evidence_directory(tmp_path, "run-resume00")
    assert (evidence / "clean-reset-backend-post-reset-verification.json").is_file()
    assert calls["verify"] == 1

    monkeypatch.setattr(MODULE, "_write_private_snapshot", writer)
    report = _produce_empty_clean_reset_post(
        targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
    )

    assert report.is_file()
    assert calls["verify"] == 1
    assert calls["validate"] == 2


def test_clean_reset_complete_rerun_returns_verified_existing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets, snapshot_sha256, runner, calls = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    first = _produce_empty_clean_reset_post(
        targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
    )
    original = first.read_bytes()
    first_command_count = len(runner.commands)
    validator = MODULE._load_validator()
    validate_report_file = validator.validate_report_file
    validated_sections: list[str] = []

    def capture_validation(**kwargs):
        validated_sections.append(kwargs["section"])
        return validate_report_file(**kwargs)

    monkeypatch.setattr(validator, "validate_report_file", capture_validation)
    monkeypatch.setattr(MODULE, "_load_validator", lambda: validator)

    second = _produce_empty_clean_reset_post(
        targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
    )

    assert second == first
    assert second.read_bytes() == original
    assert not any(
        command in MODULE.build_clean_reset_commands(targets)
        for command in runner.commands[first_command_count:]
    )
    assert validated_sections == ["cleanReset"]
    assert calls == {"verify": 1, "validate": 1}


def test_empty_snapshot_rejects_concurrently_created_resettable_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets, snapshot_sha256, runner, _ = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    namespace_command = MODULE.build_clean_reset_commands(targets)[0]
    runner.responses[tuple(namespace_command)] = MODULE.CommandResult(
        json.dumps(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "workspace-system",
                            "uid": "concurrent-namespace-uid",
                        }
                    }
                ]
            }
        ).encode(),
        b"",
        0,
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError, match="target resource still exists"
    ):
        _produce_empty_clean_reset_post(
            targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
        )


def test_empty_snapshot_rejects_concurrently_created_target_storage_class_pv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets, snapshot_sha256, runner, _ = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    pv_command = MODULE.build_clean_reset_commands(targets)[3]
    runner.responses[tuple(pv_command)] = MODULE.CommandResult(
        json.dumps(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "concurrent-pv",
                            "uid": "concurrent-pv-uid",
                        },
                        "spec": {
                            "storageClassName": "aileron-nfs-rwx-retain",
                        },
                    }
                ]
            }
        ).encode(),
        b"",
        0,
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError, match="target resource still exists"
    ):
        _produce_empty_clean_reset_post(
            targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
        )


@pytest.mark.parametrize("raw", (b"{not-json", b'{"items":["\xff"]}'))
def test_clean_reset_live_inventory_invalid_json_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    targets, snapshot_sha256, runner, _ = _empty_clean_reset_resume_fixture(
        tmp_path, monkeypatch
    )
    namespace_command = MODULE.build_clean_reset_commands(targets)[0]
    runner.responses[tuple(namespace_command)] = MODULE.CommandResult(raw, b"", 0)

    with pytest.raises(MODULE.AcceptanceProducerError, match="invalid JSON"):
        _produce_empty_clean_reset_post(
            targets=targets, snapshot_sha256=snapshot_sha256, runner=runner
        )


def test_clean_reset_cli_does_not_require_future_workspace_identity(
    tmp_path: Path,
) -> None:
    parser = MODULE.build_parser()

    arguments = parser.parse_args(
        [
            "--section",
            "cleanReset",
            "--deployment-run-id",
            "run-20260808",
            "--reset-phase",
            "pre-reset",
            "--context",
            "rke",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--platform-url",
            "https://apps.example.test",
            "--issuer-url",
            "https://identity.example.test/realms/aileron",
            "--client-id",
            "aileron-frontend",
            "--expected-commit",
            COMMIT,
        ]
    )

    assert arguments.workspace_id is None
    assert arguments.user_subject is None


@pytest.mark.parametrize(
    ("section", "authentication_mode", "expected_predecessor"),
    (
        ("cleanReset", "bundledKeycloak", "suites"),
        ("imageRelease", "bundledKeycloak", "cleanReset"),
        ("identity", "bundledKeycloak", "imageRelease"),
        ("oidcWorkspace", "bundledKeycloak", "imageRelease"),
        ("terminal", "bundledKeycloak", "oidcWorkspace"),
        ("http", "bundledKeycloak", "oidcWorkspace"),
        ("browser", "bundledKeycloak", "oidcWorkspace"),
        ("websocket", "bundledKeycloak", "oidcWorkspace"),
        ("turn", "bundledKeycloak", "oidcWorkspace"),
        ("workspaceLifecycle", "bundledKeycloak", "terminal"),
        ("restart", "bundledKeycloak", "workspaceLifecycle"),
        ("soak", "bundledKeycloak", "restart"),
        ("adminDisableLogin", "bundledKeycloak", "soak"),
        ("cleanReset", "externalOidc", "suites"),
        ("imageRelease", "externalOidc", "cleanReset"),
        ("oidcWorkspace", "externalOidc", "imageRelease"),
        ("terminal", "externalOidc", "oidcWorkspace"),
        ("http", "externalOidc", "oidcWorkspace"),
        ("browser", "externalOidc", "oidcWorkspace"),
        ("websocket", "externalOidc", "oidcWorkspace"),
        ("turn", "externalOidc", "oidcWorkspace"),
        ("workspaceLifecycle", "externalOidc", "terminal"),
        ("restart", "externalOidc", "workspaceLifecycle"),
        ("soak", "externalOidc", "restart"),
    ),
)
def test_every_nonroot_section_requires_its_verified_predecessor_before_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str,
    authentication_mode: str,
    expected_predecessor: str,
) -> None:
    targets = _targets(tmp_path)
    image_inventory = _signed_inventory(tmp_path, targets)
    monkeypatch.setattr(
        MODULE,
        "_require_predecessor_reports",
        REAL_REQUIRE_PREDECESSOR_REPORTS,
    )

    if authentication_mode == "externalOidc":
        monkeypatch.setattr(
            MODULE,
            "_installation_identity_mode",
            lambda *_args, **_kwargs: "externalOidc",
        )
        monkeypatch.setattr(
            MODULE.ACCEPTANCE_EPOCH,
            "load_deployment_epoch",
            lambda **_kwargs: {
                "deploymentRunId": "run-20260808",
                "authenticationMode": "externalOidc",
                "resetSnapshotSha256": "0" * 64,
                "createdAt": "2026-08-08T06:00:00Z",
            },
        )

    def reject_side_effect(*_args, **_kwargs):
        raise AssertionError(
            f"{section} side effect started before predecessor validation"
        )

    monkeypatch.setattr(MODULE, "_produce_clean_reset", reject_side_effect)
    monkeypatch.setattr(MODULE, "_produce_oracle_section", reject_side_effect)
    monkeypatch.setattr(MODULE, "_produce_browser_section", reject_side_effect)
    monkeypatch.setattr(MODULE, "_produce_soak", reject_side_effect)

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match=rf"{expected_predecessor} verified predecessor report is required",
    ):
        MODULE.produce(
            section=section,
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=image_inventory,
            reset_phase="post-reset" if section == "cleanReset" else None,
            expected_reset_snapshot_digest=(
                "0" * 64 if section == "cleanReset" else None
            ),
            runner=Runner(_trust_responses(targets)),
            clock=lambda: datetime(2026, 8, 8, 8, 0, tzinfo=timezone.utc),
            run_id_factory=lambda: "run-20260808",
        )


def test_image_release_uses_common_clean_reset_predecessor_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = _targets(tmp_path)
    monkeypatch.setattr(
        MODULE,
        "_require_predecessor_reports",
        REAL_REQUIRE_PREDECESSOR_REPORTS,
    )
    monkeypatch.setattr(
        MODULE,
        "_load_existing_clean_reset_report",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("imageRelease used the idempotent cleanReset path")
        ),
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="cleanReset verified predecessor report is required",
    ):
        MODULE.produce(
            section="imageRelease",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=_signed_inventory(tmp_path, targets),
            runner=Runner(_trust_responses(targets)),
            clock=lambda: datetime(2026, 8, 8, 8, 0, tzinfo=timezone.utc),
            run_id_factory=lambda: "run-20260808",
        )


def test_workspace_predecessors_are_validated_against_exact_workspace_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = _targets(tmp_path)
    validator = MODULE._load_validator()
    observed: list[tuple[str, dict[str, str] | None]] = []

    def capture_predecessor(**kwargs):
        observed.append((kwargs["section"], kwargs.get("workspace")))
        return {"path": kwargs["directory"] / f"{kwargs['section']}.json"}

    monkeypatch.setattr(validator, "validate_report_file", capture_predecessor)
    monkeypatch.setattr(MODULE, "_load_validator", lambda: validator)
    monkeypatch.setattr(
        MODULE,
        "_require_predecessor_reports",
        REAL_REQUIRE_PREDECESSOR_REPORTS,
    )
    monkeypatch.setattr(
        MODULE,
        "_produce_browser_section",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("workspaceLifecycle side effect reached")
        ),
    )

    with pytest.raises(AssertionError, match="side effect reached"):
        MODULE.produce(
            section="workspaceLifecycle",
            targets=targets,
            deployment_run_id="run-20260808",
            image_inventory=_signed_inventory(tmp_path, targets),
            runner=Runner(_trust_responses(targets)),
            clock=lambda: datetime(2026, 8, 8, 8, 0, tzinfo=timezone.utc),
            run_id_factory=lambda: "run-20260808",
        )

    expected_workspace = {"id": "workspace-1", "userSubject": "subject-1"}
    assert observed == [
        ("terminal", expected_workspace),
        ("http", expected_workspace),
        ("browser", expected_workspace),
        ("websocket", expected_workspace),
        ("turn", expected_workspace),
    ]


def test_legacy_manual_backend_verifier_is_fully_removed() -> None:
    legacy_name = "verify_backend" + "_absence"
    assert not (ROOT / "scripts/deploy/rke2" / f"{legacy_name}.py").exists()
    assert not (ROOT / "scripts/test/deploy" / f"test_{legacy_name}.py").exists()
    candidates = [
        *(ROOT / "scripts/deploy/rke2").glob("*.py"),
        *(ROOT / "scripts/deploy/rke2").glob("*.md"),
        *(ROOT / "docs/agents").glob("*.md"),
        *(ROOT / "docs-site/docs").rglob("*.md"),
        *(ROOT / "docs-site/i18n/en/docusaurus-plugin-content-docs/current").rglob(
            "*.md"
        ),
    ]
    assert all(
        legacy_name not in path.read_text(encoding="utf-8") for path in candidates
    )


def test_clean_reset_pre_phase_runs_fixed_collector_and_signs_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "_pin_targets_kubeconfig", REAL_PIN_TARGETS_KUBECONFIG)
    targets = _targets(tmp_path)
    _backend_profile(tmp_path)
    image_inventory = _signed_inventory(tmp_path, targets)
    evidence = _evidence_directory(tmp_path)
    canonical_targets = targets._replace(kubeconfig=evidence / "kubeconfig")
    flatten_command = [
        "kubectl",
        "--kubeconfig",
        str(evidence / "kubeconfig.raw"),
        "--context",
        targets.context,
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]
    inventory_path = evidence / "clean-reset-inventory.json"
    collector_command = [
        "python3",
        str(ROOT / "scripts/deploy/rke2/collect_reset_inventory.py"),
        "--kubeconfig",
        str(canonical_targets.kubeconfig),
        "--context",
        targets.context,
        "--output",
        str(inventory_path),
    ]

    def write_inventory() -> None:
        inventory_path.write_text(
            json.dumps(
                {
                    "context": targets.context,
                    "namespaces": [
                        {"name": name}
                        for name in [
                            "aileron-identity-system",
                            "aileron-turn-system",
                            "workspace-system",
                        ]
                    ],
                    "releases": [],
                    "resources": [
                        {
                            "apiVersion": "platform.aileron.io/v1alpha1",
                            "kind": "Workspace",
                            "namespace": "workspace-system",
                            "name": "workspace-1",
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolumeClaim",
                            "namespace": "workspace-system",
                            "name": "workspace-1-data",
                        },
                    ],
                    "persistentVolumes": [
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolume",
                            "name": "pv-1",
                            "uid": "pv-1-uid",
                            "backendLocator": {
                                "type": "nfs",
                                "server": "nfs.example.test",
                                "path": "/exports/workspace-1",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        inventory_path.chmod(0o600)

    responses = {
        tuple(flatten_command): MODULE.CommandResult(
            targets.kubeconfig.read_bytes(), b"", 0
        ),
        **_trust_responses(canonical_targets),
        **_backend_resource_responses(canonical_targets),
    }
    responses[tuple(collector_command)] = MODULE.CommandResult(b"", b"", 0)
    runner = Runner(responses, {tuple(collector_command): write_inventory})

    snapshot_path = MODULE.produce(
        section="cleanReset",
        targets=targets,
        deployment_run_id="run-20260808",
        image_inventory=image_inventory,
        reset_phase="pre-reset",
        runner=runner,
        run_id_factory=lambda: "run-20260808",
    )

    assert snapshot_path == evidence / "clean-reset-snapshot.json"
    assert collector_command in runner.commands
    snapshot = json.loads(snapshot_path.read_text())
    assert (
        snapshot["backendAttestor"]["imageInventorySha256"]
        == hashlib.sha256(image_inventory.read_bytes()).hexdigest()
    )
    assert (evidence / "backend-execution-profile.json").read_bytes() == (
        tmp_path / "backend-attestor" / "execution-profile.json"
    ).read_bytes()


def test_kubeconfig_transaction_pins_trust_to_the_canonical_flattened_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "_pin_targets_kubeconfig", REAL_PIN_TARGETS_KUBECONFIG)
    targets = _targets(tmp_path)
    source = targets.kubeconfig
    flattened = _self_contained_kubeconfig(
        server="https://192.0.2.10:6443", token="installer-token"
    )
    source.write_bytes(flattened)
    source.chmod(0o600)
    evidence = _evidence_directory(tmp_path)
    raw_snapshot = evidence / "kubeconfig.raw"
    canonical_snapshot = evidence / "kubeconfig"
    canonical_targets = targets._replace(kubeconfig=canonical_snapshot)
    flatten_command = [
        "kubectl",
        "--kubeconfig",
        str(raw_snapshot),
        "--context",
        targets.context,
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]
    runner = Runner(
        {
            tuple(flatten_command): MODULE.CommandResult(flattened, b"", 0),
            **_trust_responses(canonical_targets),
        }
    )

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="suites require --image-inventory",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
        )

    assert runner.commands[0] == flatten_command
    assert runner.commands[1:] == _trust_commands(canonical_targets)
    assert raw_snapshot.read_bytes() == flattened
    assert canonical_snapshot.read_bytes() == flattened
    assert all(
        command[command.index("--kubeconfig") + 1] == str(canonical_snapshot)
        for command in runner.commands[1:]
        if "--kubeconfig" in command
    )


def test_kubeconfig_transaction_allows_exact_resume_but_rejects_source_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "_pin_targets_kubeconfig", REAL_PIN_TARGETS_KUBECONFIG)
    targets = _targets(tmp_path)
    source = targets.kubeconfig
    flattened = _self_contained_kubeconfig(
        server="https://192.0.2.10:6443", token="installer-token"
    )
    source.write_bytes(flattened)
    source.chmod(0o600)
    evidence = _evidence_directory(tmp_path)
    raw_snapshot = evidence / "kubeconfig.raw"
    canonical_snapshot = evidence / "kubeconfig"
    canonical_targets = targets._replace(kubeconfig=canonical_snapshot)
    flatten_command = [
        "kubectl",
        "--kubeconfig",
        str(raw_snapshot),
        "--context",
        targets.context,
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]

    def exercise_exact_input() -> Runner:
        runner = Runner(
            {
                tuple(flatten_command): MODULE.CommandResult(flattened, b"", 0),
                **_trust_responses(canonical_targets),
            }
        )
        with pytest.raises(
            MODULE.AcceptanceProducerError,
            match="suites require --image-inventory",
        ):
            MODULE.produce(
                section="suites",
                targets=targets,
                deployment_run_id="run-20260808",
                runner=runner,
            )
        return runner

    first = exercise_exact_input()
    resumed = exercise_exact_input()
    assert first.commands == resumed.commands
    assert raw_snapshot.read_bytes() == flattened
    assert canonical_snapshot.read_bytes() == flattened

    source.write_bytes(
        _self_contained_kubeconfig(
            server="https://192.0.2.11:6443", token="replacement-token"
        )
    )
    rejected = Runner({})
    with pytest.raises(
        MODULE.AcceptanceProducerError, match="kubeconfig snapshot content changed"
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=rejected,
        )
    assert rejected.commands == []


def test_kubeconfig_transaction_rejects_flattened_identity_drift_before_trust(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "_pin_targets_kubeconfig", REAL_PIN_TARGETS_KUBECONFIG)
    targets = _targets(tmp_path)
    raw = _self_contained_kubeconfig(
        server="https://192.0.2.10:6443", token="installer-token"
    )
    drifted = _self_contained_kubeconfig(
        server="https://192.0.2.11:6443", token="replacement-token"
    )
    targets.kubeconfig.write_bytes(raw)
    targets.kubeconfig.chmod(0o600)
    evidence = _evidence_directory(tmp_path)
    flatten_command = [
        "kubectl",
        "--kubeconfig",
        str(evidence / "kubeconfig.raw"),
        "--context",
        targets.context,
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]
    runner = Runner({tuple(flatten_command): MODULE.CommandResult(drifted, b"", 0)})

    with pytest.raises(
        MODULE.AcceptanceProducerError,
        match="flattened kubeconfig selected identity changed",
    ):
        MODULE.produce(
            section="suites",
            targets=targets,
            deployment_run_id="run-20260808",
            runner=runner,
        )

    assert runner.commands == [flatten_command]
