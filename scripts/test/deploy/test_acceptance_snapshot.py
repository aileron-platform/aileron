from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.deploy.rke2 import namespace_policy

MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy/rke2/acceptance_snapshot.py"
SPEC = importlib.util.spec_from_file_location("acceptance_snapshot", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

KEY = bytes(range(32))
COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
IDENTITY_DIGEST = "b" * 64
CREATED_AT = datetime(2026, 8, 8, 7, 0, tzinfo=UTC)
RUN_ID = "run-20260808"
PROFILE = {
    "schemaVersion": "aileron-backend-execution-profile/v1",
    "executionNamespace": "aileron-backend-attestor-system",
    "namespaceOwner": "aileron-installer",
    "imagePullSecret": "harbor-rke-creds",
    "nfsMountRoots": [
        {"server": "192.168.50.100", "path": "/volume1/okd/aileron"}
    ],
    "localPathNodes": [],
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _backend_attestor() -> dict:
    canonical_profile = _canonical(PROFILE)
    return {
        "schemaVersion": "aileron-backend-attestor-snapshot-binding/v1",
        "executionProfile": {
            "schemaVersion": "aileron-backend-execution-profile-binding/v1",
            "rawSha256": hashlib.sha256(canonical_profile + b"\n").hexdigest(),
            "canonicalSha256": hashlib.sha256(canonical_profile).hexdigest(),
            "profile": PROFILE,
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
                "dataSha256": "c" * 64,
            },
        },
        "imageInventorySha256": "d" * 64,
    }


def _directory(tmp_path: Path) -> Path:
    tmp_path.chmod(0o700)
    return MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=RUN_ID,
        error_type=MODULE.AcceptanceSnapshotError,
    )


def _inventory() -> dict:
    return {
        "context": "rke2-homelab",
        "namespaces": [
            {"name": "aileron-identity-system"},
            {"name": "aileron-turn-system"},
            {"name": "workspace-system"},
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
                "name": "pv-1",
                "backendLocator": {
                    "type": "nfs",
                    "server": "nfs.example.test",
                    "path": "/exports/workspace-1",
                },
            }
        ],
    }


def test_writes_and_loads_fixed_signed_reset_snapshot(tmp_path: Path) -> None:
    path = MODULE.write_reset_snapshot(
        directory=_directory(tmp_path),
        private_root=tmp_path,
        inventory=_inventory(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )
    approved_digest = hashlib.sha256(path.read_bytes()).hexdigest()

    assert path == _directory(tmp_path) / "clean-reset-snapshot.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    snapshot = MODULE.load_reset_snapshot(
        directory=_directory(tmp_path),
        private_root=tmp_path,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        expected_run_id=RUN_ID,
        expected_snapshot_sha256=approved_digest,
    )
    assert snapshot["runId"] == RUN_ID
    assert snapshot["namespacePolicy"] == namespace_policy.namespace_policy_document()
    assert snapshot["backendAttestor"] == _backend_attestor()
    assert snapshot["inventory"] == _inventory()


def test_allows_already_clean_empty_homelab_reset_target_sets(tmp_path: Path) -> None:
    inventory = _inventory()
    inventory["resources"] = []
    inventory["persistentVolumes"] = []

    path = MODULE.write_reset_snapshot(
        directory=_directory(tmp_path),
        private_root=tmp_path,
        inventory=inventory,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )

    assert json.loads(path.read_text())["inventory"] == inventory


@pytest.mark.parametrize(
    "namespaces",
    [
        [],
        [{"name": "workspace-system"}],
        [{"name": "workspace-system"}, {"name": "workspace-system"}],
        [{"name": "unknown-system"}],
        ["workspace-system"],
        [{}],
    ],
)
def test_namespace_inventory_accepts_only_unique_target_subsets(
    tmp_path: Path, namespaces: list,
) -> None:
    inventory = _inventory()
    inventory["namespaces"] = namespaces
    inventory["resources"] = []
    inventory["persistentVolumes"] = []
    valid = namespaces in ([], [{"name": "workspace-system"}])

    if not valid:
        with pytest.raises(MODULE.AcceptanceSnapshotError, match="namespaces"):
            MODULE.write_reset_snapshot(
                directory=_directory(tmp_path),
                private_root=tmp_path,
                inventory=inventory,
                key=KEY,
                context="rke2-homelab",
                commit=COMMIT,
                cluster_uid=CLUSTER_UID,
                installation_identity_sha256=IDENTITY_DIGEST,
                run_id=RUN_ID,
                backend_attestor=_backend_attestor(),
                created_at=CREATED_AT,
            )
        return

    path = MODULE.write_reset_snapshot(
        directory=_directory(tmp_path),
        private_root=tmp_path,
        inventory=inventory,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )
    assert json.loads(path.read_text())["inventory"]["namespaces"] == namespaces


@pytest.mark.parametrize("kind", ["Workspace", "PersistentVolumeClaim"])
def test_rejects_malformed_nonempty_resource_set(tmp_path: Path, kind: str) -> None:
    inventory = _inventory()
    inventory["resources"] = [
        {"apiVersion": "v1", "kind": kind, "namespace": "workspace-system"}
    ]
    inventory["persistentVolumes"] = []

    with pytest.raises(MODULE.AcceptanceSnapshotError, match="target sets"):
        MODULE.write_reset_snapshot(
            directory=_directory(tmp_path),
            private_root=tmp_path,
            inventory=inventory,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
            run_id=RUN_ID,
            backend_attestor=_backend_attestor(),
            created_at=CREATED_AT,
        )


def test_rejects_tampered_reset_snapshot(tmp_path: Path) -> None:
    path = MODULE.write_reset_snapshot(
        directory=_directory(tmp_path),
        private_root=tmp_path,
        inventory=_inventory(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )
    approved_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = json.loads(path.read_text())
    document["inventory"]["resources"] = []
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceSnapshotError, match="digest"):
        MODULE.load_reset_snapshot(
            directory=_directory(tmp_path),
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
            expected_run_id=RUN_ID,
            expected_snapshot_sha256=approved_digest,
        )


def test_rejects_snapshot_with_invalid_utf8_as_invalid_json(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    path = directory / MODULE.SNAPSHOT_NAME
    raw = b'{"schemaVersion":"aileron-clean-reset-snapshot/v1","bad":"\xff"}\n'
    path.write_bytes(raw)
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceSnapshotError, match="invalid JSON"):
        MODULE.load_reset_snapshot(
            directory=directory,
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
            expected_run_id=RUN_ID,
            expected_snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        )


@pytest.mark.parametrize(
    "variant",
    ("duplicate", "whitespace", "order", "missing-newline"),
)
def test_rejects_ambiguous_or_noncanonical_signed_snapshot_json(
    tmp_path: Path, variant: str
) -> None:
    directory = _directory(tmp_path)
    path = MODULE.write_reset_snapshot(
        directory=directory,
        private_root=tmp_path,
        inventory=_inventory(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )
    document = json.loads(path.read_bytes())
    if variant == "duplicate":
        raw = (
            b'{"commit":'
            + json.dumps(document["commit"]).encode()
            + b","
            + path.read_bytes()[1:]
        )
        expected_error = "invalid JSON"
    elif variant == "whitespace":
        raw = json.dumps(document, indent=2, sort_keys=True).encode() + b"\n"
        expected_error = "not canonical JSON"
    elif variant == "order":
        raw = json.dumps(
            dict(reversed(list(document.items()))),
            separators=(",", ":"),
        ).encode() + b"\n"
        expected_error = "not canonical JSON"
    else:
        raw = _canonical(document)
        expected_error = "not canonical JSON"
    path.write_bytes(raw)
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceSnapshotError, match=expected_error):
        MODULE.load_reset_snapshot(
            directory=directory,
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
            expected_run_id=RUN_ID,
            expected_snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_rejects_signed_noncanonical_utc_timestamp(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    path = MODULE.write_reset_snapshot(
        directory=directory,
        private_root=tmp_path,
        inventory=_inventory(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=RUN_ID,
        backend_attestor=_backend_attestor(),
        created_at=CREATED_AT,
    )
    document = json.loads(path.read_bytes())
    document["createdAt"] = "2026-08-08T07:00:00+00:00"
    unsigned = dict(document)
    unsigned.pop("signature")
    document["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(document) + b"\n"
    path.write_bytes(raw)
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceSnapshotError, match="timestamp"):
        MODULE.load_reset_snapshot(
            directory=directory,
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
            expected_run_id=RUN_ID,
            expected_snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        )
