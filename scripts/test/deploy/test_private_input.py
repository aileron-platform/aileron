from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "private_input.py"
)
SPEC = importlib.util.spec_from_file_location("private_input", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "a" * 40


def _private_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", root)
    return root


def _private_directory(path: Path) -> Path:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _private_file(path: Path, content: bytes = b"fixture") -> Path:
    _private_directory(path.parent)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _kubeconfig_bytes(*, server: str = "https://192.0.2.10:6443") -> bytes:
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": "rke",
            "clusters": [
                {
                    "name": "rke",
                    "cluster": {
                        "server": server,
                        "certificate-authority-data": "Y2E=",
                    },
                }
            ],
            "contexts": [
                {
                    "name": "rke",
                    "context": {"cluster": "rke", "user": "rke"},
                }
            ],
            "users": [
                {
                    "name": "rke",
                    "user": {
                        "client-certificate-data": "Y2VydA==",
                        "client-key-data": "a2V5",
                    },
                }
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _flatten_raw_snapshot(
    command: list[str],
    *,
    environment: dict[str, str],
) -> str:
    raw_snapshot = Path(command[command.index("--kubeconfig") + 1])
    assert environment == {"KUBECONFIG": str(raw_snapshot)}
    return raw_snapshot.read_text(encoding="utf-8")


def test_private_root_is_a_valid_owner_controlled_private_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)

    assert (
        MODULE.validate_private_directory(
            root,
            "installation private root",
            private_root=root,
        )
        == root
    )


def test_private_root_rejects_textual_parent_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    aliased_root = root / ".." / root.name

    with pytest.raises(MODULE.PrivateInputError, match="canonical path"):
        MODULE.private_root_path(aliased_root)


def test_private_file_rejects_textual_parent_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "inputs/kubeconfig")
    aliased_source = source.parent / ".." / source.parent.name / source.name

    with pytest.raises(MODULE.PrivateInputError, match="canonical path"):
        MODULE.validate_private_file(aliased_source, "kubeconfig", private_root=root)


def test_private_directory_rejects_textual_parent_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    directory = _private_directory(root / "transactions/deploy")
    aliased_directory = directory.parent / ".." / directory.parent.name / directory.name

    with pytest.raises(MODULE.PrivateInputError, match="canonical path"):
        MODULE.validate_private_directory(
            aliased_directory,
            "transaction directory",
            private_root=root,
        )


def test_snapshot_destination_rejects_textual_parent_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    snapshot_parent = _private_directory(root / "transactions/deploy")
    aliased_destination = (
        snapshot_parent / ".." / snapshot_parent.name / "snapshots/input"
    )

    with pytest.raises(MODULE.PrivateInputError, match="canonical path"):
        MODULE.write_private_snapshot(
            destination=aliased_destination,
            content=b"private",
            description="test input",
            private_root=root,
        )


def test_snapshot_copies_one_canonical_installer_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "install" / COMMIT / "snapshots/core-values.json")
    transaction = _private_directory(root / "transactions/deploy")
    destination = transaction / "core-values.json"

    MODULE.snapshot_private_file(
        source=source,
        destination=destination,
        description="core release values",
        commit=COMMIT,
        snapshot_name="core-values.json",
    )

    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_mode & 0o777 == 0o600


def test_kubeconfig_source_replacement_after_snapshot_cannot_change_flattening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    original = _kubeconfig_bytes()
    source = _private_file(root / "kubeconfig", original)
    snapshot_directory = root / "transaction/snapshots"
    snapshot_directory.parent.mkdir(mode=0o700)
    replacement = _private_file(
        root / "replacement-kubeconfig",
        _kubeconfig_bytes(server="https://192.0.2.99:6443"),
    )
    calls: list[tuple[list[str], dict[str, str]]] = []

    def runner(
        command: list[str],
        *,
        environment: dict[str, str],
    ) -> str:
        calls.append((command, environment))
        raw_snapshot = Path(command[command.index("--kubeconfig") + 1])
        os.replace(replacement, source)
        return raw_snapshot.read_text(encoding="utf-8")

    flattened = MODULE.snapshot_self_contained_kubeconfig(
        source=source,
        raw_destination=snapshot_directory / "kubeconfig.raw",
        flattened_destination=snapshot_directory / "kubeconfig",
        context="rke",
        runner=runner,
        private_root=root,
    )

    assert source.read_bytes() != original
    assert (snapshot_directory / "kubeconfig.raw").read_bytes() == original
    assert flattened.read_bytes() == original
    assert flattened.stat().st_mode & 0o777 == 0o600
    assert calls[0][1] == {
        "KUBECONFIG": str(snapshot_directory / "kubeconfig.raw")
    }


def test_invalid_kubeconfig_is_rejected_without_publishing_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    document = json.loads(_kubeconfig_bytes())
    document["clusters"][0]["cluster"] = {
        "server": "https://192.0.2.10:6443",
        "insecure-skip-tls-verify": True,
    }
    source = _private_file(
        root / "kubeconfig",
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    )
    transaction = _private_directory(root / "transaction")
    snapshot_directory = transaction / "snapshots"

    def runner(
        _command: list[str],
        *,
        environment: dict[str, str],
    ) -> str:
        raise AssertionError(f"kubectl must not run: {environment}")

    with pytest.raises(
        MODULE.PrivateInputError,
        match="raw kubeconfig snapshot selected cluster contains unsupported fields",
    ):
        MODULE.snapshot_self_contained_kubeconfig(
            source=source,
            raw_destination=snapshot_directory / "kubeconfig.raw",
            flattened_destination=snapshot_directory / "kubeconfig",
            context="rke",
            runner=runner,
            private_root=root,
        )

    assert not snapshot_directory.exists()

    corrected = _kubeconfig_bytes()
    source.write_bytes(corrected)
    source.chmod(0o600)

    flattened = MODULE.snapshot_self_contained_kubeconfig(
        source=source,
        raw_destination=snapshot_directory / "kubeconfig.raw",
        flattened_destination=snapshot_directory / "kubeconfig",
        context="rke",
        runner=_flatten_raw_snapshot,
        private_root=root,
        allow_existing_exact=True,
    )

    assert (snapshot_directory / "kubeconfig.raw").read_bytes() == corrected
    assert flattened.read_bytes() == corrected


def test_invalid_flattened_kubeconfig_is_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    original = _kubeconfig_bytes()
    source = _private_file(root / "kubeconfig", original)
    snapshot_directory = root / "transaction/snapshots"
    snapshot_directory.parent.mkdir(mode=0o700)

    def runner(
        _command: list[str],
        *,
        environment: dict[str, str],
    ) -> str:
        assert environment == {
            "KUBECONFIG": str(snapshot_directory / "kubeconfig.raw")
        }
        return _kubeconfig_bytes(server="https://192.0.2.99:6443").decode("utf-8")

    with pytest.raises(
        MODULE.PrivateInputError,
        match="flattened kubeconfig selected identity changed",
    ):
        MODULE.snapshot_self_contained_kubeconfig(
            source=source,
            raw_destination=snapshot_directory / "kubeconfig.raw",
            flattened_destination=snapshot_directory / "kubeconfig",
            context="rke",
            runner=runner,
            private_root=root,
        )

    assert (snapshot_directory / "kubeconfig.raw").read_bytes() == original
    assert not (snapshot_directory / "kubeconfig").exists()

    flattened = MODULE.snapshot_self_contained_kubeconfig(
        source=source,
        raw_destination=snapshot_directory / "kubeconfig.raw",
        flattened_destination=snapshot_directory / "kubeconfig",
        context="rke",
        runner=_flatten_raw_snapshot,
        private_root=root,
        allow_existing_exact=True,
    )

    assert flattened.read_bytes() == original


def test_new_snapshot_directory_and_file_entries_are_fsynced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "source", b"stable-input")
    transaction = root / "transaction"
    transaction.mkdir(mode=0o700)
    snapshot_directory = transaction / "snapshots"
    destination = snapshot_directory / "input"
    real_fsync = MODULE.os.fsync
    synchronized_inodes: list[int] = []

    def capture_fsync(descriptor: int) -> None:
        synchronized_inodes.append(os.fstat(descriptor).st_ino)
        real_fsync(descriptor)

    monkeypatch.setattr(MODULE.os, "fsync", capture_fsync)

    MODULE.snapshot_private_file(
        source=source,
        destination=destination,
        description="test input",
        private_root=root,
    )

    assert transaction.stat().st_ino in synchronized_inodes
    assert snapshot_directory.stat().st_ino in synchronized_inodes
    assert destination.stat().st_ino in synchronized_inodes


def test_snapshot_retries_short_writes_until_all_bytes_are_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "source", b"complete-snapshot-content")
    snapshot_parent = _private_directory(root / "transaction")
    destination = snapshot_parent / "snapshots/input"
    real_write = MODULE.os.write
    write_calls = 0

    def short_write(descriptor: int, content: bytes | memoryview) -> int:
        nonlocal write_calls
        write_calls += 1
        maximum = max(1, len(content) // 2)
        return real_write(descriptor, content[:maximum])

    monkeypatch.setattr(MODULE.os, "write", short_write)

    MODULE.snapshot_private_file(
        source=source,
        destination=destination,
        description="test input",
        private_root=root,
    )

    assert write_calls > 1
    assert destination.read_bytes() == source.read_bytes()


def test_snapshot_rejects_noncanonical_or_drifting_installer_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "inputs/core-values.json")
    transaction = _private_directory(root / "transactions/deploy")

    with pytest.raises(MODULE.PrivateInputError, match="installer snapshot"):
        MODULE.snapshot_private_file(
            source=source,
            destination=transaction / "core-values.json",
            description="core release values",
            commit=COMMIT,
            snapshot_name="core-values.json",
        )


def test_snapshot_rejects_counterfeit_canonical_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(
        root
        / "counterfeit-prefix"
        / "install"
        / COMMIT
        / "snapshots/core-values.json"
    )
    transaction = _private_directory(root / "transactions/deploy")

    with pytest.raises(MODULE.PrivateInputError, match="installer snapshot"):
        MODULE.snapshot_private_file(
            source=source,
            destination=transaction / "core-values.json",
            description="core release values",
            commit=COMMIT,
            snapshot_name="core-values.json",
        )


@pytest.mark.parametrize("failure", ["mode", "symlink", "ancestor-symlink"])
def test_private_file_rejects_insecure_kubeconfig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    kubeconfig = _private_file(root / "kubeconfig")
    if failure == "mode":
        kubeconfig.chmod(0o644)
    elif failure == "symlink":
        target = kubeconfig
        kubeconfig = root / "kubeconfig-link"
        kubeconfig.symlink_to(target)
    else:
        real = root / "real"
        real.mkdir(mode=0o700)
        target = _private_file(real / "kubeconfig")
        linked = root / "linked"
        linked.symlink_to(real, target_is_directory=True)
        kubeconfig = linked / target.name

    with pytest.raises(MODULE.PrivateInputError):
        MODULE.validate_private_file(kubeconfig, "kubeconfig")


def test_private_file_rejects_hard_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "kubeconfig")
    linked = root / "linked-kubeconfig"
    os.link(source, linked)

    with pytest.raises(MODULE.PrivateInputError, match="regular file"):
        MODULE.validate_private_file(
            linked,
            "kubeconfig",
            private_root=root,
        )


@pytest.mark.parametrize("boundary", ["private-root", "parent-directory", "file"])
def test_private_inputs_reject_mode_correct_objects_owned_by_another_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    root = _private_root(tmp_path, monkeypatch)
    parent = _private_directory(root / "inputs")
    source = _private_file(parent / "kubeconfig")
    target = {
        "private-root": root,
        "parent-directory": parent,
        "file": source,
    }[boundary]
    os.chown(target, 65532, 65532)

    with pytest.raises(MODULE.PrivateInputError, match="owner-controlled"):
        MODULE.validate_private_file(
            source,
            "kubeconfig",
            private_root=root,
        )


def test_existing_snapshot_owned_by_another_uid_is_not_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    root = _private_root(tmp_path, monkeypatch)
    source = _private_file(root / "source", b"same-content")
    snapshot_directory = _private_directory(root / "transaction/snapshots")
    destination = _private_file(snapshot_directory / "input", b"same-content")
    os.chown(destination, 65532, 65532)

    with pytest.raises(MODULE.PrivateInputError, match="owner-controlled"):
        MODULE.snapshot_private_file(
            source=source,
            destination=destination,
            description="test input",
            private_root=root,
            allow_existing_exact=True,
        )
