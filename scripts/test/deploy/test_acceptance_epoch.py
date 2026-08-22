from __future__ import annotations

import importlib.util
import hashlib
import hmac
import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts/deploy/rke2/acceptance_epoch.py"
SPEC = importlib.util.spec_from_file_location("acceptance_epoch", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

KEY = bytes(range(32))
COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
IDENTITY_DIGEST = "b" * 64
RESET_DIGEST = "c" * 64
RUN_ID = "run-20260808"


def _directory(tmp_path: Path) -> Path:
    tmp_path.chmod(0o700)
    return MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=RUN_ID,
        error_type=MODULE.AcceptanceEpochError,
    )


def _write(directory: Path, *, private_root: Path | None = None) -> Path:
    return MODULE.write_deployment_epoch(
        directory=directory,
        private_root=private_root or directory.parents[2],
        key=KEY,
        deployment_run_id=RUN_ID,
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        context="rke2-homelab",
        installation_identity_sha256=IDENTITY_DIGEST,
        authentication_mode="bundledKeycloak",
        reset_snapshot_sha256=RESET_DIGEST,
        created_at=datetime(2026, 8, 8, 6, 1, tzinfo=UTC),
    )


def test_epoch_is_atomically_published_mode_0600_and_bound_to_trust(
    tmp_path: Path,
) -> None:
    directory = _directory(tmp_path)
    path = _write(directory)

    assert path == directory / MODULE.EPOCH_NAME
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(directory.glob(f".{MODULE.EPOCH_NAME}.*.tmp"))
    document = MODULE.load_deployment_epoch(
        directory=directory,
        private_root=directory.parents[2],
        key=KEY,
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        context="rke2-homelab",
        installation_identity_sha256=IDENTITY_DIGEST,
        deployment_run_id=RUN_ID,
    )
    assert document["deploymentRunId"] == RUN_ID
    assert document["authenticationMode"] == "bundledKeycloak"
    assert document["resetSnapshotSha256"] == RESET_DIGEST
    assert MODULE.epoch_sha256(
        directory,
        private_root=directory.parents[2],
        commit=COMMIT,
        deployment_run_id=RUN_ID,
    )


def test_epoch_rejects_tampering_and_cross_attempt_overwrite(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    path = _write(directory)
    original = path.read_bytes()

    with pytest.raises(
        MODULE.AcceptanceEpochError, match="already exists"
    ):
        _write(directory)
    assert path.read_bytes() == original
    assert not list(directory.glob(f".{MODULE.EPOCH_NAME}.*.tmp"))

    document = json.loads(original)
    document["deploymentRunId"] = "run-different-attempt"
    path.write_bytes(MODULE._canonical(document) + b"\n")
    path.chmod(0o600)
    with pytest.raises(MODULE.AcceptanceEpochError, match="signature"):
        MODULE.load_deployment_epoch(
            directory=directory,
            private_root=directory.parents[2],
            key=KEY,
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            context="rke2-homelab",
            installation_identity_sha256=IDENTITY_DIGEST,
            deployment_run_id=RUN_ID,
        )


def test_epoch_rejects_non_private_or_noncanonical_directory(tmp_path: Path) -> None:
    public = _directory(tmp_path)
    public.chmod(0o755)
    with pytest.raises(MODULE.AcceptanceEpochError, match="owner-controlled"):
        _write(public, private_root=tmp_path)
    public.chmod(0o700)

    alias = tmp_path / "evidence-link"
    alias.symlink_to(public, target_is_directory=True)
    with pytest.raises(MODULE.AcceptanceEpochError, match="identity"):
        _write(alias, private_root=tmp_path)


def test_epoch_rejects_signed_noncanonical_utc_timestamp(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    path = _write(directory)
    document = json.loads(path.read_bytes())
    document["createdAt"] = "2026-08-08T06:01:00+00:00"
    unsigned = dict(document)
    unsigned.pop("signature")
    document["signature"] = hmac.new(
        KEY, MODULE._canonical(unsigned), hashlib.sha256
    ).hexdigest()
    path.write_bytes(MODULE._canonical(document) + b"\n")
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceEpochError, match="timestamp"):
        MODULE.load_deployment_epoch(
            directory=directory,
            private_root=directory.parents[2],
            key=KEY,
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            context="rke2-homelab",
            installation_identity_sha256=IDENTITY_DIGEST,
            deployment_run_id=RUN_ID,
        )


@pytest.mark.parametrize(
    ("variant", "expected_error"),
    (
        ("duplicate", "invalid JSON"),
        ("whitespace", "not canonical JSON"),
        ("order", "not canonical JSON"),
        ("missing-newline", "not canonical JSON"),
        ("invalid-utf8", "invalid JSON"),
    ),
)
def test_epoch_rejects_ambiguous_or_noncanonical_raw_json(
    tmp_path: Path, variant: str, expected_error: str
) -> None:
    directory = _directory(tmp_path)
    path = _write(directory)
    document = json.loads(path.read_bytes())
    if variant == "duplicate":
        raw = (
            b'{"commit":'
            + json.dumps(document["commit"]).encode()
            + b","
            + path.read_bytes()[1:]
        )
    elif variant == "whitespace":
        raw = json.dumps(document, indent=2, sort_keys=True).encode() + b"\n"
    elif variant == "order":
        raw = json.dumps(
            dict(reversed(list(document.items()))),
            separators=(",", ":"),
        ).encode() + b"\n"
    elif variant == "missing-newline":
        raw = MODULE._canonical(document)
    else:
        raw = b'{"schemaVersion":"aileron-deployment-epoch/v1","bad":"\xff"}\n'
    path.write_bytes(raw)
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceEpochError, match=expected_error):
        MODULE.load_deployment_epoch(
            directory=directory,
            private_root=directory.parents[2],
            key=KEY,
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            context="rke2-homelab",
            installation_identity_sha256=IDENTITY_DIGEST,
            deployment_run_id=RUN_ID,
        )


@pytest.mark.parametrize(
    ("run_id", "accepted"),
    (
        ("run-a------z", True),
        ("run-" + "a" * 59, True),
        ("run-abcdefg", False),
        ("run-" + "a" * 60, False),
        ("run-Uppercase01", False),
        ("run-trailing01-", False),
    ),
)
def test_shared_run_id_accepts_only_canonical_kubernetes_label_lengths(
    tmp_path: Path, run_id: str, accepted: bool
) -> None:
    tmp_path.chmod(0o700)
    if not accepted:
        with pytest.raises(MODULE.AcceptanceEpochError, match="identity"):
            MODULE.PRIVATE_IO.evidence_directory(
                private_root=tmp_path,
                commit=COMMIT,
                deployment_run_id=run_id,
                error_type=MODULE.AcceptanceEpochError,
            )
        return

    directory = MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=run_id,
        error_type=MODULE.AcceptanceEpochError,
    )
    assert len(run_id) <= 63
    assert directory == tmp_path / "evidence" / COMMIT / run_id


def test_same_commit_runs_coexist_and_cross_identity_is_rejected(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    first_run = "run-first000"
    second_run = "run-second00"
    first = MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=first_run,
        error_type=MODULE.AcceptanceEpochError,
    )
    second = MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=second_run,
        error_type=MODULE.AcceptanceEpochError,
    )

    assert first != second
    assert first.is_dir() and second.is_dir()
    with pytest.raises(MODULE.AcceptanceEpochError, match="does not match"):
        MODULE.PRIVATE_IO.validate_evidence_directory(
            first,
            private_root=tmp_path,
            commit=COMMIT,
            deployment_run_id=second_run,
            error_type=MODULE.AcceptanceEpochError,
        )
    with pytest.raises(MODULE.AcceptanceEpochError, match="does not match"):
        MODULE.PRIVATE_IO.validate_evidence_directory(
            first,
            private_root=tmp_path,
            commit="b" * 40,
            deployment_run_id=first_run,
            error_type=MODULE.AcceptanceEpochError,
        )
