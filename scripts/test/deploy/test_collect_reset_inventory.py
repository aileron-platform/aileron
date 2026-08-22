from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "rke2"
    / "collect_reset_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("collect_reset_inventory", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
KUBECONFIG = Path("/private/rke2-homelab.yaml")


def _runner_fixture() -> tuple[list[list[str]], object]:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> str:
        commands.append(command)
        if command == [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            "rke2-homelab",
            "config",
            "current-context",
        ]:
            return "rke2-homelab\n"
        if command == [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            "rke2-homelab",
            "get",
            "namespaces",
            "-o",
            "json",
        ]:
            return json.dumps(
                {
                    "items": [
                        {
                            "metadata": {
                                "name": "workspace-system",
                                "uid": "namespace-uid-workspace",
                                "resourceVersion": "501",
                                "labels": {
                                    "platform.aileron.dev/namespace-owner": "aileron-installer"
                                },
                            }
                        },
                        {"metadata": {"name": "kube-system", "labels": {}}},
                    ]
                }
            )
        if command == [
            "helm",
            "--kubeconfig",
            str(KUBECONFIG),
            "--kube-context",
            "rke2-homelab",
            "list",
            "--all-namespaces",
            "--output",
            "json",
        ]:
            return json.dumps(
                [
                    {"name": "aileron", "namespace": "workspace-system"},
                    {"name": "rke2-cilium", "namespace": "kube-system"},
                ]
            )
        if command == [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            "rke2-homelab",
            "get",
            "persistentvolumes",
            "-o",
            "json",
        ]:
            return json.dumps(
                {
                    "items": [
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolume",
                            "metadata": {
                                "name": "pv-cleared-csi",
                                "uid": "pv-uid-csi",
                                "resourceVersion": "99",
                            },
                            "spec": {
                                "storageClassName": "aileron-nfs-rwx-delete",
                                "persistentVolumeReclaimPolicy": "Delete",
                                "csi": {
                                    "driver": "nfs.csi.k8s.io",
                                    "volumeHandle": "10.0.0.12#/exports#pv-cleared-csi",
                                },
                            },
                            "status": {"phase": "Available"},
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolume",
                            "metadata": {
                                "name": "pv-workspace",
                                "uid": "pv-uid-1",
                                "resourceVersion": "101",
                                "labels": {"app.kubernetes.io/part-of": "aileron"},
                            },
                            "spec": {
                                "storageClassName": "aileron-nfs-rwx-retain",
                                "persistentVolumeReclaimPolicy": "Retain",
                                "claimRef": {
                                    "namespace": "workspace-system",
                                    "name": "workspace-data",
                                    "uid": "pvc-uid-1",
                                },
                                "nfs": {
                                    "server": "10.0.0.12",
                                    "path": "/exports/pv-workspace",
                                },
                            },
                            "status": {"phase": "Bound"},
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolume",
                            "metadata": {
                                "name": "pv-orphan",
                                "uid": "pv-uid-0",
                                "resourceVersion": "100",
                            },
                            "spec": {
                                "storageClassName": "aileron-local-rwo-retain",
                                "persistentVolumeReclaimPolicy": "Delete",
                                "claimRef": {
                                    "namespace": "workspace-system",
                                    "name": "deleted-manager-state",
                                    "uid": "pvc-uid-0",
                                },
                                "hostPath": {"path": "/var/lib/aileron/pv-orphan"},
                                "nodeAffinity": {
                                    "required": {
                                        "nodeSelectorTerms": [
                                            {
                                                "matchExpressions": [
                                                    {
                                                        "key": "kubernetes.io/hostname",
                                                        "operator": "In",
                                                        "values": ["rke2-worker-1"],
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                },
                            },
                            "status": {"phase": "Released"},
                        },
                        {
                            "apiVersion": "v1",
                            "kind": "PersistentVolume",
                            "metadata": {"name": "pv-unrelated", "uid": "pv-uid-2"},
                            "spec": {
                                "storageClassName": "shared-storage",
                                "persistentVolumeReclaimPolicy": "Retain",
                                "claimRef": {
                                    "namespace": "shared-service",
                                    "name": "shared-data",
                                    "uid": "pvc-uid-2",
                                },
                            },
                            "status": {"phase": "Bound"},
                        },
                    ]
                }
            )
        if command == [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            "rke2-homelab",
            "api-resources",
            "--namespaced=true",
            "--verbs=list",
            "-o",
            "name",
        ]:
            return "apps.catalog.cattle.io\ndeployments.apps\nsecrets\nwidgets.example.io\n"
        if command[-5:] == [
            "get",
            "apps.catalog.cattle.io",
            "--all-namespaces",
            "-o",
            "json",
        ]:
            return json.dumps(
                {
                    "items": [
                        {
                            "apiVersion": "catalog.cattle.io/v1",
                            "kind": "App",
                            "metadata": {
                                "namespace": "workspace-system",
                                "name": "aileron",
                                "uid": "app-uid-aileron",
                                "resourceVersion": "701",
                                "ownerReferences": [
                                    {
                                        "apiVersion": "v1",
                                        "kind": "Secret",
                                        "name": "sh.helm.release.v1.aileron.v6",
                                    }
                                ],
                            },
                        }
                    ]
                }
            )
        if "deployments.apps" in command:
            return (
                "apps/v1\tDeployment\tworkspace-system\t"
                "aileron-workspace-manager\tdeployment-uid\t702\n"
                "apps/v1\tDeployment\tkube-system\trke2-cilium\t"
                "cilium-uid\t703\n"
            )
        if "secrets" in command:
            return (
                "v1\tSecret\tworkspace-system\taileron-platform-secrets\t"
                "secret-uid\t704\n"
            )
        if "widgets.example.io" in command:
            return (
                "example.io/v1\tWidget\tworkspace-system\tunexpected-widget\t"
                "widget-uid\t705\n"
            )
        raise AssertionError(f"unexpected command: {command}")

    return commands, runner


def test_collector_keeps_all_target_namespace_identity_metadata() -> None:
    commands, runner = _runner_fixture()

    inventory = MODULE.collect_reset_inventory(
        expected_context="rke2-homelab", kubeconfig=KUBECONFIG, runner=runner
    )

    assert inventory == {
        "context": "rke2-homelab",
        "namespaces": [
            {
                "name": "workspace-system",
                "uid": "namespace-uid-workspace",
                "resourceVersion": "501",
                "labels": {"platform.aileron.dev/namespace-owner": "aileron-installer"},
            }
        ],
        "releases": [{"name": "aileron", "namespace": "workspace-system"}],
        "persistentVolumes": [
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-cleared-csi",
                "uid": "pv-uid-csi",
                "resourceVersion": "99",
                "labels": {},
                "phase": "Available",
                "storageClassName": "aileron-nfs-rwx-delete",
                "reclaimPolicy": "Delete",
                "claimRef": None,
                "backendLocator": {
                    "type": "csi",
                    "driver": "nfs.csi.k8s.io",
                    "volumeHandle": "10.0.0.12#/exports#pv-cleared-csi",
                },
            },
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-orphan",
                "uid": "pv-uid-0",
                "resourceVersion": "100",
                "labels": {},
                "phase": "Released",
                "storageClassName": "aileron-local-rwo-retain",
                "reclaimPolicy": "Delete",
                "claimRef": {
                    "namespace": "workspace-system",
                    "name": "deleted-manager-state",
                    "uid": "pvc-uid-0",
                },
                "backendLocator": {
                    "type": "localPath",
                    "node": "rke2-worker-1",
                    "path": "/var/lib/aileron/pv-orphan",
                    "volumeSource": "hostPath",
                },
            },
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-workspace",
                "uid": "pv-uid-1",
                "resourceVersion": "101",
                "labels": {"app.kubernetes.io/part-of": "aileron"},
                "phase": "Bound",
                "storageClassName": "aileron-nfs-rwx-retain",
                "reclaimPolicy": "Retain",
                "claimRef": {
                    "namespace": "workspace-system",
                    "name": "workspace-data",
                    "uid": "pvc-uid-1",
                },
                "backendLocator": {
                    "type": "nfs",
                    "server": "10.0.0.12",
                    "path": "/exports/pv-workspace",
                },
            },
        ],
        "resources": [
            {
                "apiVersion": "catalog.cattle.io/v1",
                "kind": "App",
                "namespace": "workspace-system",
                "name": "aileron",
                "uid": "app-uid-aileron",
                "resourceVersion": "701",
                "ownerReferences": [
                    {
                        "apiVersion": "v1",
                        "kind": "Secret",
                        "namespace": "workspace-system",
                        "name": "sh.helm.release.v1.aileron.v6",
                    }
                ],
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "namespace": "workspace-system",
                "name": "aileron-workspace-manager",
                "uid": "deployment-uid",
                "resourceVersion": "702",
            },
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "namespace": "workspace-system",
                "name": "aileron-platform-secrets",
                "uid": "secret-uid",
                "resourceVersion": "704",
            },
            {
                "apiVersion": "example.io/v1",
                "kind": "Widget",
                "namespace": "workspace-system",
                "name": "unexpected-widget",
                "uid": "widget-uid",
                "resourceVersion": "705",
            },
        ],
    }
    assert all(command[0] in {"kubectl", "helm"} for command in commands)
    assert all(
        command[1:5] == ["--kubeconfig", str(KUBECONFIG), "--context", "rke2-homelab"]
        for command in commands
        if command[0] == "kubectl"
    )
    assert all(
        command[1:5]
        == ["--kubeconfig", str(KUBECONFIG), "--kube-context", "rke2-homelab"]
        for command in commands
        if command[0] == "helm"
    )
    assert not any("delete" in command or "apply" in command for command in commands)
    secret_commands = [command for command in commands if "secrets" in command]
    assert len(secret_commands) == 1
    assert "json" not in secret_commands[0]
    assert all(
        "custom-columns=" in " ".join(command)
        or (
            "apps.catalog.cattle.io" in command
            and command[-2:] == ["-o", "json"]
        )
        for command in commands
        if "--all-namespaces" in command and command[0] == "kubectl"
    )


def test_collector_rejects_context_mismatch_before_inventory_reads() -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> str:
        commands.append(command)
        return "wrong-context\n"

    with pytest.raises(ValueError, match="current context does not match"):
        MODULE.collect_reset_inventory(
            expected_context="rke2-homelab", kubeconfig=KUBECONFIG, runner=runner
        )

    assert commands == [
        [
            "kubectl",
            "--kubeconfig",
            str(KUBECONFIG),
            "--context",
            "rke2-homelab",
            "config",
            "current-context",
        ]
    ]


def test_collector_records_csi_locator_without_secret_attributes() -> None:
    persistent_volume = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {
            "name": "pv-csi",
            "uid": "pv-uid-csi",
            "resourceVersion": "202",
        },
        "spec": {
            "storageClassName": "aileron-nfs-rwx-delete",
            "persistentVolumeReclaimPolicy": "Delete",
            "claimRef": {
                "namespace": "workspace-system",
                "name": "workspace-csi-data",
                "uid": "pvc-uid-csi",
            },
            "csi": {
                "driver": "storage.example.io",
                "volumeHandle": "volume-123",
                "nodeStageSecretRef": {
                    "name": "must-not-be-recorded",
                    "namespace": "storage-system",
                },
            },
        },
        "status": {"phase": "Bound"},
    }

    result = MODULE._persistent_volume_metadata(persistent_volume)

    assert result is not None
    assert result["backendLocator"] == {
        "type": "csi",
        "driver": "storage.example.io",
        "volumeHandle": "volume-123",
    }
    assert result["labels"] == {}
    assert "must-not-be-recorded" not in json.dumps(result)


def test_collector_rejects_target_pv_without_verifiable_backend_locator() -> None:
    persistent_volume = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {
            "name": "pv-unsupported",
            "uid": "pv-uid-unsupported",
            "resourceVersion": "203",
        },
        "spec": {
            "storageClassName": "aileron-nfs-rwx-delete",
            "persistentVolumeReclaimPolicy": "Delete",
            "claimRef": {
                "namespace": "workspace-system",
                "name": "unsupported-data",
                "uid": "pvc-uid-unsupported",
            },
            "rbd": {"image": "unverifiable"},
        },
        "status": {"phase": "Bound"},
    }

    with pytest.raises(ValueError, match="backend locator"):
        MODULE._persistent_volume_metadata(persistent_volume)


@pytest.mark.parametrize(
    ("storage_class", "labels", "driver"),
    [
        ("aileron-future-delete", {}, "unrelated.csi.example"),
        (
            "shared-storage",
            {"platform.aileron.dev/storage-owner": "aileron-installer"},
            "unrelated.csi.example",
        ),
        ("shared-storage", {}, "nfs.csi.k8s.io"),
    ],
)
def test_collector_does_not_treat_prefix_owner_or_provisioner_as_pv_identity(
    storage_class: str, labels: dict[str, str], driver: str
) -> None:
    persistent_volume = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {
            "name": "pv-unowned",
            "uid": "pv-uid-unowned",
            "resourceVersion": "204",
            "labels": labels,
        },
        "spec": {
            "storageClassName": storage_class,
            "persistentVolumeReclaimPolicy": "Delete",
            "csi": {"driver": driver, "volumeHandle": "volume-204"},
        },
        "status": {"phase": "Available"},
    }

    assert MODULE._persistent_volume_metadata(persistent_volume) is None


def test_collector_writes_atomic_private_evidence(tmp_path: Path) -> None:
    _, runner = _runner_fixture()
    inventory = MODULE.collect_reset_inventory(
        expected_context="rke2-homelab", kubeconfig=KUBECONFIG, runner=runner
    )
    output = tmp_path / "reset-inventory.json"

    MODULE.write_inventory(output, inventory)

    assert json.loads(output.read_text(encoding="utf-8")) == inventory
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [output]
