"""Installer-owned Secret and Core result transaction regression tests."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "rke2"
    / "installation_transaction.py"
)
SPEC = importlib.util.spec_from_file_location("installation_transaction", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "a" * 40
CONTEXT = "rke"
NAMESPACE_UIDS = {
    "workspace-system": "11111111-1111-4111-8111-111111111111",
    "aileron-turn-system": "22222222-2222-4222-8222-222222222222",
    "aileron-identity-system": "33333333-3333-4333-8333-333333333333",
}


def _namespace_document(namespace: str, uid: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
            "uid": uid,
            "resourceVersion": "17",
            "labels": MODULE.NAMESPACE_CONTRACT.profile_labels(namespace),
        },
        "status": {"phase": "Active"},
    }


def _namespace_uids(identity_mode: str) -> dict[str, str]:
    references = MODULE.secret_references(identity_mode=identity_mode)
    return {
        namespace: NAMESPACE_UIDS[namespace]
        for namespace in {namespace for namespace, _ in references}
    }


def _directory(path: Path) -> Path:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _private(path: Path, content: bytes) -> Path:
    _directory(path.parent)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _secret(namespace: str, name: str, value: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "resourceVersion": "17",
            "uid": "11111111-1111-4111-8111-111111111111",
            "labels": {"platform.aileron.dev/secret-owner": "aileron-installer"},
        },
        "type": "Opaque",
        "data": {"private": value},
    }


class FakeRunner:
    def __init__(self, existing: dict[tuple[str, str], dict] | None = None) -> None:
        self.secrets = dict(existing or {})
        self.commands: list[list[str]] = []
        self.fail_restore_for: tuple[str, str] | None = None
        self.cas_conflict_for: tuple[str, str] | None = None
        self.restore_manifests: list[dict] = []
        self.delete_options: list[dict] = []
        self.namespace_uids = dict(NAMESPACE_UIDS)
        self.namespace_reads = 0
        self.replace_namespace_on_read: int | None = None
        self.secret_gets = 0
        self.replace_namespace_after_secret_get: int | None = None

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdout_path: Path | None = None,
    ) -> str:
        del environment
        self.commands.append(command)
        if command[0] != "kubectl":
            raise AssertionError(command)
        if "get" in command and "namespace" in command:
            namespace_name = command[command.index("namespace") + 1]
            self.namespace_reads += 1
            if self.replace_namespace_on_read == self.namespace_reads:
                self.namespace_uids[namespace_name] = (
                    "44444444-4444-4444-8444-444444444444"
                )
            return json.dumps(
                _namespace_document(
                    namespace_name,
                    self.namespace_uids[namespace_name],
                )
            )
        namespace = command[command.index("--namespace") + 1]
        if "get" in command:
            name = command[command.index("secret") + 1]
            document = self.secrets.get((namespace, name))
            assert stdout_path is not None
            stdout_path.write_text(
                "" if document is None else json.dumps(document),
                encoding="utf-8",
            )
            stdout_path.chmod(0o600)
            self.secret_gets += 1
            if self.replace_namespace_after_secret_get == self.secret_gets:
                self.namespace_uids[namespace] = (
                    "44444444-4444-4444-8444-444444444444"
                )
            return ""
        if "delete" in command and "--raw" in command:
            raw_path = command[command.index("--raw") + 1]
            name = raw_path.rsplit("/", 1)[-1]
            options_path = Path(command[command.index("--filename") + 1])
            options = json.loads(options_path.read_text(encoding="utf-8"))
            self.delete_options.append(options)
            if self.fail_restore_for == (namespace, name):
                raise RuntimeError("private stderr must not escape")
            current = self.secrets.get((namespace, name))
            if current is None or self.cas_conflict_for == (namespace, name):
                raise RuntimeError("Kubernetes Secret CAS conflict")
            preconditions = options["preconditions"]
            if (
                preconditions["uid"] != current["metadata"]["uid"]
                or preconditions["resourceVersion"]
                != current["metadata"]["resourceVersion"]
            ):
                raise RuntimeError("Kubernetes Secret CAS conflict")
            self.secrets.pop((namespace, name), None)
            return ""
        if "create" in command or "replace" in command:
            manifest_path = Path(command[command.index("--filename") + 1])
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.restore_manifests.append(document)
            metadata = document["metadata"]
            key = (metadata["namespace"], metadata["name"])
            if self.fail_restore_for == key:
                raise RuntimeError("private manifest must not escape")
            if "replace" in command:
                assert "--force" not in command
                current = self.secrets.get(key)
                if current is None or self.cas_conflict_for == key:
                    raise RuntimeError("Kubernetes Secret CAS conflict")
                if (
                    metadata.get("resourceVersion")
                    != current["metadata"]["resourceVersion"]
                ):
                    raise RuntimeError("Kubernetes Secret CAS conflict")
                metadata["uid"] = current["metadata"]["uid"]
            else:
                metadata.setdefault("resourceVersion", "1")
                metadata.setdefault("uid", "22222222-2222-4222-8222-222222222222")
            self.secrets[key] = document
            return ""
        raise AssertionError(command)


def _transaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    private_root = _directory(tmp_path / "private")
    work = _directory(private_root / "install" / COMMIT)
    secret_store = _directory(private_root / "install-secrets/homelab")
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "SECRET_STORE", secret_store)
    return (
        MODULE.create_transaction_directory(
            work_directory=work,
            commit=COMMIT,
        ),
        secret_store,
    )


def _apply_and_record_post_state(
    *,
    transaction: Path,
    identity_mode: str,
    reference: tuple[str, str],
    document: dict,
    runner: FakeRunner,
) -> None:
    expected_manifest = json.dumps(document).encode()
    binding = MODULE.prepare_secret_mutation(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode=identity_mode,
        namespace=reference[0],
        name=reference[1],
        expected_manifest=expected_manifest,
        runner=runner,
    )
    mutation_manifest = MODULE.render_secret_mutation_manifest(
        expected_manifest=expected_manifest,
        namespace=reference[0],
        name=reference[1],
        transaction_marker=binding["transactionMarker"],
        uid=binding.get("uid"),
        resource_version=binding.get("resourceVersion"),
    )
    applied = json.loads(mutation_manifest)
    applied["metadata"].setdefault("uid", document["metadata"]["uid"])
    applied["metadata"].setdefault(
        "resourceVersion", document["metadata"]["resourceVersion"]
    )
    runner.secrets[reference] = applied
    MODULE.record_secret_post_state(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode=identity_mode,
        namespace=reference[0],
        name=reference[1],
        expected_manifest=expected_manifest,
        runner=runner,
    )


@pytest.mark.parametrize(
    "boundary",
    [
        "private-root",
        "install-root",
        "transactions-parent",
        "transaction",
        "snapshot-file",
    ],
)
def test_transaction_rejects_mode_correct_state_owned_by_another_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    transaction, _ = _transaction(tmp_path, monkeypatch)
    private_root = MODULE.INSTALLATION_STATE.PRIVATE_ROOT
    snapshot = _private(transaction / "snapshot.json", b"{}\n")
    target = {
        "private-root": private_root,
        "install-root": private_root / "install",
        "transactions-parent": transaction.parent,
        "transaction": transaction,
        "snapshot-file": snapshot,
    }[boundary]
    os.chown(target, 65532, 65532)

    with pytest.raises(MODULE.InstallationTransactionError, match="owner-controlled"):
        if boundary == "snapshot-file":
            MODULE._read_private_file(snapshot, "transaction snapshot")
        else:
            MODULE._validate_transaction_directory(transaction, COMMIT)


def test_secret_transaction_snapshots_only_exact_allowlist_without_plaintext_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    references = MODULE.secret_references(identity_mode="bundledKeycloak")
    assert (
        "aileron-identity-system",
        "keycloak-platform-admin",
    ) in references
    existing_ref = references[0]
    unrelated_ref = ("workspace-system", "unrelated-private-secret")
    runner = FakeRunner(
        {
            existing_ref: _secret(*existing_ref, "existing-private-value"),
            unrelated_ref: _secret(*unrelated_ref, "unrelated-private-value"),
        }
    )
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="bundledKeycloak",
        expected_namespace_uids=_namespace_uids("bundledKeycloak"),
        runner=runner,
    )

    queried = {
        (
            command[command.index("--namespace") + 1],
            command[command.index("secret") + 1],
        )
        for command in runner.commands
        if "--namespace" in command and "secret" in command
    }
    assert queried == set(references)
    assert unrelated_ref not in queried
    inventory_path = transaction / "secret-inventory.json"
    inventory_text = inventory_path.read_text(encoding="utf-8")
    assert inventory_path.stat().st_mode & 0o777 == 0o600
    assert "existing-private-value" not in inventory_text
    assert "unrelated-private-value" not in inventory_text
    snapshots = [path for path in (transaction / "secrets").iterdir() if path.is_file()]
    assert len(snapshots) == 1
    assert snapshots[0].stat().st_mode & 0o777 == 0o600


def test_secret_transaction_excludes_retained_backend_attestor_pull_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = ("aileron-backend-attestor-system", "harbor-rke-creds")
    references = MODULE.secret_references(identity_mode="externalOidc")
    assert reference not in references
    assert (
        MODULE.INSTALLATION_STATE.ACCEPTANCE_SECRET_NAMESPACE,
        MODULE.INSTALLATION_STATE.ACCEPTANCE_SECRET_NAME,
    ) not in references
    runner = FakeRunner(
        {reference: _secret(*reference, "backend-pull-private-value")}
    )

    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )

    inventory = json.loads(
        (transaction / "secret-inventory.json").read_text(encoding="utf-8")
    )
    assert reference not in {
        (entry["namespace"], entry["name"])
        for entry in inventory["secrets"]
    }
    MODULE.restore_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        runner=runner,
    )
    assert reference in runner.secrets
    assert all(
        not (
            "--namespace" in command
            and command[command.index("--namespace") + 1] == reference[0]
            and "secret" in command
            and command[command.index("secret") + 1] == reference[1]
        )
        for command in runner.commands
    )


def test_secret_transaction_restores_changed_existing_and_deletes_new_exact_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    references = MODULE.secret_references(identity_mode="externalOidc")
    existing_ref = references[0]
    originally_absent_ref = references[1]
    unrelated_ref = ("workspace-system", "unrelated-private-secret")
    original = _secret(*existing_ref, "original-private-value")
    runner = FakeRunner(
        {
            existing_ref: original,
            unrelated_ref: _secret(*unrelated_ref, "unrelated-private-value"),
        }
    )
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )

    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=existing_ref,
        document=_secret(*existing_ref, "mutated-private-value"),
        runner=runner,
    )
    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=originally_absent_ref,
        document=_secret(*originally_absent_ref, "new-private-value"),
        runner=runner,
    )
    MODULE.restore_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        runner=runner,
    )

    assert runner.secrets[existing_ref]["data"] == original["data"]
    assert originally_absent_ref not in runner.secrets
    assert runner.secrets[unrelated_ref]["data"]["private"] == (
        "unrelated-private-value"
    )
    replace_command = next(
        command for command in runner.commands if "replace" in command
    )
    assert "--force" not in replace_command
    restored_manifest = next(
        document
        for document in runner.restore_manifests
        if document["metadata"]["name"] == existing_ref[1]
    )
    assert restored_manifest["metadata"]["resourceVersion"] == "17"
    raw_delete = next(
        command
        for command in runner.commands
        if "delete" in command and "--raw" in command
    )
    assert raw_delete[raw_delete.index("--raw") + 1] == (
        f"/api/v1/namespaces/{originally_absent_ref[0]}"
        f"/secrets/{originally_absent_ref[1]}"
    )
    assert runner.delete_options == [
        {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {
                "uid": "11111111-1111-4111-8111-111111111111",
                "resourceVersion": "17",
            },
        }
    ]


@pytest.mark.parametrize("original_state", ["existing", "absent"])
def test_secret_transaction_cas_conflict_fails_without_overwriting_concurrent_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    original_state: str,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    original = _secret(*reference, "original-private-value")
    runner = FakeRunner({reference: original} if original_state == "existing" else {})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    concurrent = _secret(*reference, "concurrent-private-value")
    concurrent["metadata"]["resourceVersion"] = "29"
    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=reference,
        document=concurrent,
        runner=runner,
    )
    runner.cas_conflict_for = reference

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="could not be restored",
    ):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference]["data"]["private"] == ("concurrent-private-value")


def test_existing_secret_uid_change_fails_before_semantic_accept_or_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    original = _secret(*reference, "same-private-value")
    runner = FakeRunner({reference: original})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    recreated = _secret(*reference, "same-private-value")
    recreated["metadata"]["uid"] = "33333333-3333-4333-8333-333333333333"
    recreated["metadata"]["resourceVersion"] = "29"
    runner.secrets[reference] = recreated

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="could not be restored",
    ):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference] == recreated
    assert runner.restore_manifests == []
    assert not any("delete" in command for command in runner.commands)


def test_secret_transaction_reports_safe_aggregate_and_continues_exact_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    references = MODULE.secret_references(identity_mode="externalOidc")
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    for reference in references[:2]:
        _apply_and_record_post_state(
            transaction=transaction,
            identity_mode="externalOidc",
            reference=reference,
            document=_secret(*reference, "private-value"),
            runner=runner,
        )
    runner.fail_restore_for = references[0]

    with pytest.raises(MODULE.InstallationTransactionError) as caught:
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert str(caught.value) == (
        "one or more installer-owned Secret states could not be restored"
    )
    assert "private" not in repr(caught.value)
    assert references[1] not in runner.secrets


def test_namespace_replacement_during_snapshot_fails_before_any_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    runner = FakeRunner()
    runner.replace_namespace_after_secret_get = 1

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="Namespace validation failed",
    ):
        MODULE.begin_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            expected_namespace_uids=_namespace_uids("externalOidc"),
            runner=runner,
        )

    assert runner.secret_gets == 1
    assert not any(
        "delete" in command or "replace" in command for command in runner.commands
    )


def test_absent_secret_without_durable_post_state_is_preserved_on_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    created = _secret(*reference, "created-before-recorder-crash")
    runner.secrets[reference] = created

    with pytest.raises(MODULE.InstallationTransactionError, match="could not be restored"):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference] == created
    assert not any("delete" in command for command in runner.commands)


@pytest.mark.parametrize("original_state", ["absent", "existing"])
def test_pending_mutation_recovers_crash_after_cluster_mutation_before_post_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    original_state: str,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    original = _secret(*reference, "original-private-value")
    runner = FakeRunner({reference: original} if original_state == "existing" else {})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    desired = _secret(*reference, "transaction-private-value")
    expected_manifest = json.dumps(desired).encode()

    binding = MODULE.prepare_secret_mutation(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        namespace=reference[0],
        name=reference[1],
        expected_manifest=expected_manifest,
        runner=runner,
    )
    assert binding["state"] == original_state
    applied = json.loads(
        MODULE.render_secret_mutation_manifest(
            expected_manifest=expected_manifest,
            namespace=reference[0],
            name=reference[1],
            transaction_marker=binding["transactionMarker"],
            uid=binding.get("uid"),
            resource_version=binding.get("resourceVersion"),
        )
    )
    applied["metadata"]["resourceVersion"] = "29"
    applied["metadata"].setdefault(
        "uid", "55555555-5555-4555-8555-555555555555"
    )
    runner.secrets[reference] = applied

    inventory = json.loads(
        (transaction / "secret-inventory.json").read_text(encoding="utf-8")
    )
    entry = inventory["secrets"][0]
    assert "postState" not in entry
    assert entry["pendingMutation"]["preState"]["state"] == original_state
    assert "transaction-private-value" not in json.dumps(entry)

    MODULE.restore_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        runner=runner,
    )

    if original_state == "absent":
        assert reference not in runner.secrets
    else:
        assert runner.secrets[reference]["data"] == original["data"]


@pytest.mark.parametrize("original_state", ["absent", "existing"])
def test_pending_mutation_preserves_concurrent_exact_unmarked_secret_after_cas_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    original_state: str,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    original = _secret(*reference, "original-private-value")
    runner = FakeRunner({reference: original} if original_state == "existing" else {})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    desired = _secret(*reference, "transaction-private-value")
    MODULE.prepare_secret_mutation(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        namespace=reference[0],
        name=reference[1],
        expected_manifest=json.dumps(desired).encode(),
        runner=runner,
    )
    concurrent = _secret(*reference, "transaction-private-value")
    concurrent["metadata"]["resourceVersion"] = "29"
    if original_state == "absent":
        concurrent["metadata"]["uid"] = "55555555-5555-4555-8555-555555555555"
    runner.secrets[reference] = concurrent

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="could not be restored",
    ):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference] == concurrent
    assert not any(
        "delete" in command or "replace" in command for command in runner.commands
    )


def test_namespace_replacement_immediately_before_rollback_delete_preserves_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=reference,
        document=_secret(*reference, "transaction-created"),
        runner=runner,
    )
    runner.replace_namespace_on_read = runner.namespace_reads + 2

    with pytest.raises(MODULE.InstallationTransactionError, match="could not be restored"):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert reference in runner.secrets
    assert not any("delete" in command for command in runner.commands)


def test_absent_secret_replacement_before_rollback_is_not_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=reference,
        document=_secret(*reference, "transaction-created"),
        runner=runner,
    )
    replacement = _secret(*reference, "external-replacement")
    replacement["metadata"]["uid"] = "55555555-5555-4555-8555-555555555555"
    replacement["metadata"]["resourceVersion"] = "29"
    runner.secrets[reference] = replacement

    with pytest.raises(MODULE.InstallationTransactionError, match="could not be restored"):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference] == replacement
    assert not any("delete" in command for command in runner.commands)


def test_existing_secret_recreation_is_rejected_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    original = _secret(*reference, "original")
    runner = FakeRunner({reference: original})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    replacement = _secret(*reference, "replacement")
    replacement["metadata"]["uid"] = "55555555-5555-4555-8555-555555555555"
    replacement["metadata"]["resourceVersion"] = "29"
    runner.secrets[reference] = replacement

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="pre-state changed before mutation",
    ):
        MODULE.prepare_secret_mutation(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            namespace=reference[0],
            name=reference[1],
            expected_manifest=json.dumps(
                _secret(*reference, "transaction-output")
            ).encode(),
            runner=runner,
        )

    assert runner.secrets[reference] == replacement
    assert not any(
        "create" in command or "replace" in command or "delete" in command
        for command in runner.commands
    )


def test_absent_secret_concurrent_create_is_rejected_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    concurrent = _secret(*reference, "concurrent")
    runner.secrets[reference] = concurrent

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="absent Secret pre-state changed before mutation",
    ):
        MODULE.prepare_secret_mutation(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            namespace=reference[0],
            name=reference[1],
            expected_manifest=json.dumps(
                _secret(*reference, "transaction-output")
            ).encode(),
            runner=runner,
        )

    assert runner.secrets[reference] == concurrent
    assert not any(
        "create" in command or "replace" in command or "delete" in command
        for command in runner.commands
    )


def test_prepare_rejects_caller_supplied_reserved_transaction_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner()
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    expected = _secret(*reference, "transaction-output")
    expected["metadata"]["annotations"] = {
        MODULE.TRANSACTION_MARKER_ANNOTATION: "a" * 64
    }

    with pytest.raises(
        MODULE.InstallationTransactionError,
        match="reserved annotation",
    ):
        MODULE.prepare_secret_mutation(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            namespace=reference[0],
            name=reference[1],
            expected_manifest=json.dumps(expected).encode(),
            runner=runner,
        )


def test_existing_secret_same_uid_semantic_drift_is_preserved_on_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    reference = MODULE.secret_references(identity_mode="externalOidc")[0]
    runner = FakeRunner({reference: _secret(*reference, "original")})
    MODULE.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context=CONTEXT,
        identity_mode="externalOidc",
        expected_namespace_uids=_namespace_uids("externalOidc"),
        runner=runner,
    )
    _apply_and_record_post_state(
        transaction=transaction,
        identity_mode="externalOidc",
        reference=reference,
        document=_secret(*reference, "transaction-output"),
        runner=runner,
    )
    concurrent = _secret(*reference, "third-party-update")
    concurrent["metadata"]["resourceVersion"] = "29"
    runner.secrets[reference] = concurrent

    with pytest.raises(MODULE.InstallationTransactionError, match="could not be restored"):
        MODULE.restore_secret_transaction(
            transaction_directory=transaction,
            commit=COMMIT,
            context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert runner.secrets[reference] == concurrent
    assert not any("replace" in command for command in runner.commands)


def test_core_result_sidecar_is_canonical_mode_0600_and_structured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    result_path = MODULE.prepare_core_result(
        transaction_directory=transaction,
        commit=COMMIT,
    )

    MODULE.write_core_result(
        path=result_path,
        commit=COMMIT,
        primary_exit_code=23,
        core_rollback_attempted=True,
        core_rollback_succeeded=False,
    )

    assert result_path.stat().st_mode & 0o777 == 0o600
    assert MODULE.read_core_result(path=result_path, commit=COMMIT) == {
        "schemaVersion": MODULE.CORE_RESULT_SCHEMA,
        "state": "completed",
        "commit": COMMIT,
        "primaryExitCode": 23,
        "coreRollbackAttempted": True,
        "coreRollbackSucceeded": False,
    }


def test_core_result_rejects_counterfeit_transaction_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)
    result_path = MODULE.prepare_core_result(
        transaction_directory=transaction,
        commit=COMMIT,
    )
    counterfeit = _directory(
        MODULE.INSTALLATION_STATE.PRIVATE_ROOT
        / "counterfeit"
        / "install"
        / COMMIT
        / "transactions"
        / transaction.name
    )
    counterfeit_result = _private(
        counterfeit / result_path.name,
        result_path.read_bytes(),
    )

    with pytest.raises(MODULE.InstallationTransactionError, match="installer-owned"):
        MODULE.write_core_result(
            path=counterfeit_result,
            commit=COMMIT,
            primary_exit_code=1,
            core_rollback_attempted=False,
            core_rollback_succeeded=False,
        )


def test_install_recovery_result_is_safe_combined_mode_0600_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction, _ = _transaction(tmp_path, monkeypatch)

    result_path = MODULE.write_install_recovery_result(
        transaction_directory=transaction,
        commit=COMMIT,
        primary_stage="core deployment",
        primary_exit_code=23,
        secret_restore={"attempted": True, "succeeded": True, "skipped": False},
        core_rollback={"attempted": True, "succeeded": False, "skipped": False},
        identity_recovery={"attempted": False, "succeeded": False, "skipped": True},
    )

    assert result_path.name == "install-recovery-result.json"
    assert result_path.stat().st_mode & 0o777 == 0o600
    result = MODULE.read_install_recovery_result(
        transaction_directory=transaction,
        commit=COMMIT,
    )
    assert result == {
        "schemaVersion": "aileron-installation-recovery-result/v1",
        "state": "failed",
        "commit": COMMIT,
        "primaryFailure": {"stage": "core deployment", "exitCode": 23},
        "secretRestore": {
            "attempted": True,
            "succeeded": True,
            "skipped": False,
        },
        "coreRollback": {
            "attempted": True,
            "succeeded": False,
            "skipped": False,
        },
        "identityRecovery": {
            "attempted": False,
            "succeeded": False,
            "skipped": True,
        },
    }
    serialized = result_path.read_text(encoding="utf-8")
    assert "stderr" not in serialized
    assert "private" not in serialized
    assert str(tmp_path) not in serialized
