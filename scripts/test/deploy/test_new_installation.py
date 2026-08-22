"""Forward-only new-installation transaction public contract tests."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts.deploy.rke2 import acceptance_cluster as ACCEPTANCE_CLUSTER
from scripts.deploy.rke2 import bootstrap_acceptance_trust as BOOTSTRAP
from scripts.deploy.rke2 import kubernetes_rest as KUBERNETES_REST
from scripts.deploy.rke2 import new_installation as MODULE

COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
OLD_INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
NEW_INSTALLATION_ID = "33333333-3333-4333-8333-333333333333"
NAMESPACE_UID = "44444444-4444-4444-8444-444444444444"
OLD_SECRET_UID = "55555555-5555-4555-8555-555555555555"
NEW_SECRET_UID = "66666666-6666-4666-8666-666666666666"
DRIFT_SECRET_UID = "88888888-8888-4888-8888-888888888888"
DRIFT_INSTALLATION_ID = "99999999-9999-4999-8999-999999999999"
OLD_KEY = bytes(range(32))
NEW_KEY = b"n" * 32


class _TLSContext:
    def load_cert_chain(self, _certificate: Path, _private_key: Path) -> None:
        raise AssertionError("token kubeconfig must not load a client certificate")


def _kubeconfig(context: str = "rke") -> bytes:
    return (
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": context,
                "clusters": [
                    {
                        "name": "homelab",
                        "cluster": {
                            "server": "https://207.example.test:6443",
                            "certificate-authority-data": base64.b64encode(
                                b"test-ca"
                            ).decode(),
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": context,
                        "context": {"cluster": "homelab", "user": "operator"},
                    }
                ],
                "users": [{"name": "operator", "user": {"token": "secret"}}],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _namespace() -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "aileron-acceptance-system",
            "uid": NAMESPACE_UID,
            "resourceVersion": "17",
            "labels": BOOTSTRAP.NAMESPACE_CONTRACT.profile_labels(
                "aileron-acceptance-system"
            ),
        },
        "status": {"phase": "Active"},
    }


class Runner:
    def __init__(self, old_secret: dict) -> None:
        self.secret: dict | None = old_secret
        self.secret_reads = 0
        self.calls: list[list[str]] = []
        self.commit = COMMIT

    def __call__(
        self,
        command: list[str],
        stdin: bytes | None = None,
        *,
        environment: dict[str, str] | None = None,
    ) -> bytes:
        self.calls.append(command)
        if command[:2] == ["git", "status"]:
            return b""
        if command[:2] == ["git", "rev-parse"]:
            return f"{self.commit}\n".encode()
        if "config" in command and "view" in command:
            assert environment is not None
            return Path(environment["KUBECONFIG"]).read_bytes()
        if command[-2:] == ["config", "current-context"]:
            return b"rke\n"
        if "kube-system" in command:
            return CLUSTER_UID.encode()
        if "get" in command and "namespace" in command:
            return json.dumps(_namespace()).encode()
        if "get" in command and "secret" in command:
            self.secret_reads += 1
            if self.secret is None:
                raise BOOTSTRAP.CommandNotFoundError("not found")
            return json.dumps(self.secret).encode()
        if "--dry-run=server" in command:
            return b"accepted"
        if "create" in command and stdin is not None:
            created = json.loads(stdin)
            if created["kind"] == "Namespace":
                raise AssertionError(
                    "retained acceptance Namespace must not be recreated"
                )
            created["metadata"].update({"uid": NEW_SECRET_UID, "resourceVersion": "31"})
            self.secret = created
            return json.dumps(created).encode()
        raise AssertionError(f"unexpected command: {command}")


def _private_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tmp_path.chmod(0o700)
    private_root = tmp_path / "aileron-private"
    private_root.mkdir(mode=0o700)
    kubeconfig = private_root / "kubeconfig"
    kubeconfig.write_bytes(_kubeconfig())
    kubeconfig.chmod(0o600)
    store = private_root / "install-secrets" / "homelab"
    store.mkdir(mode=0o700, parents=True)
    (private_root / "install-secrets").chmod(0o700)
    identity_document = {
        "contractVersion": "aileron-installation-identity/v2",
        "clusterUid": CLUSTER_UID,
        "context": "rke",
        "namespaces": [
            "aileron-acceptance-system",
            "aileron-identity-system",
            "aileron-turn-system",
            "workspace-system",
        ],
        "realm": "aileron",
        "issuerUrl": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        "clientId": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
    }
    identity = (json.dumps(identity_document, indent=2, sort_keys=True) + "\n").encode()
    identity_path = store / "installation-identity.json"
    identity_path.write_bytes(identity)
    identity_path.chmod(0o600)
    key_path = store / "acceptance-hmac.key"
    key_path.write_bytes(OLD_KEY)
    key_path.chmod(0o600)
    identity_digest = hashlib.sha256(identity).hexdigest()
    anchor = {
        "contractVersion": "aileron-acceptance-trust-anchor/v1",
        "clusterUid": CLUSTER_UID,
        "context": "rke",
        "installationIdentitySha256": identity_digest,
        "keySha256": hashlib.sha256(OLD_KEY).hexdigest(),
        "secretName": "aileron-acceptance-signing",
        "secretNamespace": "aileron-acceptance-system",
        "secretUid": OLD_SECRET_UID,
    }
    anchor_path = store / "acceptance-trust-anchor.json"
    anchor_path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n")
    anchor_path.chmod(0o600)
    old_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "immutable": True,
        "metadata": {
            "name": "aileron-acceptance-signing",
            "namespace": "aileron-acceptance-system",
            "labels": {
                "platform.aileron.dev/secret-owner": "aileron-installer",
                "platform.aileron.dev/cluster-uid": CLUSTER_UID,
            },
            "annotations": {
                "platform.aileron.dev/context": "rke",
                "platform.aileron.dev/installation-identity-sha256": identity_digest,
            },
        },
        "type": "Opaque",
        "data": {"hmac-key": base64.b64encode(OLD_KEY).decode()},
    }
    old_secret["metadata"].update({"uid": OLD_SECRET_UID, "resourceVersion": "19"})
    for state_module in (
        MODULE.INSTALLATION_STATE,
        BOOTSTRAP.INSTALLATION_STATE,
        ACCEPTANCE_CLUSTER.INSTALLATION_STATE,
    ):
        monkeypatch.setattr(state_module, "PRIVATE_ROOT", private_root)
        monkeypatch.setattr(state_module, "SECRET_STORE", store)
    monkeypatch.setattr(
        KUBERNETES_REST.ssl,
        "create_default_context",
        lambda *, cadata: _TLSContext(),
    )
    return private_root, kubeconfig, store, Runner(old_secret)


def _replace_with_v3_trust(store: Path, runner: Runner) -> tuple[bytes, bytes, bytes]:
    identity_document = MODULE.INSTALLATION_STATE.installation_identity_document(
        installation_id=OLD_INSTALLATION_ID,
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        cluster_uid=CLUSTER_UID,
    )
    identity = (json.dumps(identity_document, indent=2, sort_keys=True) + "\n").encode()
    identity_path = store / "installation-identity.json"
    identity_path.write_bytes(identity)
    identity_path.chmod(0o600)
    key_path = store / "acceptance-hmac.key"
    key_path.write_bytes(OLD_KEY)
    key_path.chmod(0o600)
    secret = json.loads(
        MODULE.INSTALLATION_STATE.acceptance_secret_bytes(
            key=OLD_KEY,
            identity=identity,
            cluster_uid=CLUSTER_UID,
        )
    )
    secret["metadata"].update({"uid": OLD_SECRET_UID, "resourceVersion": "19"})
    runner.secret = secret
    anchor = MODULE.INSTALLATION_STATE.acceptance_anchor_document(
        cluster_uid=CLUSTER_UID,
        identity_digest=hashlib.sha256(identity).hexdigest(),
        key_digest=hashlib.sha256(OLD_KEY).hexdigest(),
        secret_uid=OLD_SECRET_UID,
    )
    anchor_bytes = (json.dumps(anchor, indent=2, sort_keys=True) + "\n").encode()
    anchor_path = store / "acceptance-trust-anchor.json"
    anchor_path.write_bytes(anchor_bytes)
    anchor_path.chmod(0o600)
    return identity, OLD_KEY, anchor_bytes


def _complete_replacement(*, kubeconfig: Path, runner: Runner) -> dict[str, object]:
    def get_transport(**_kwargs):
        runner.secret = None
        return 404, b'{"apiVersion":"v1","kind":"Status","reason":"NotFound"}'

    return MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: NEW_KEY,
        installation_id_factory=lambda: NEW_INSTALLATION_ID,
        delete_transport=lambda **_kwargs: (
            202,
            b'{"apiVersion":"v1","kind":"Status"}',
        ),
        get_transport=get_transport,
        sleeper=lambda _seconds: None,
        maximum_get_attempts=2,
    )


def test_completely_absent_trust_runs_initial_v3_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    for filename in MODULE.QUARANTINED_TRUST_FILES:
        (store / filename).unlink()
    runner.secret = None
    delete_called = False

    def reject_delete(**_kwargs):
        nonlocal delete_called
        delete_called = True
        raise AssertionError("initial bootstrap must not delete trust")

    result = MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: NEW_KEY,
        installation_id_factory=lambda: NEW_INSTALLATION_ID,
        delete_transport=reject_delete,
        get_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("initial bootstrap must not use the delete REST client")
        ),
    )

    assert result["operation"] == "initialBootstrap"
    assert result["state"] == "completed"
    assert result["pointOfNoReturn"] is False
    assert result["oldInstallationId"] is None
    assert result["oldSecret"] is None
    assert result["quarantine"] == {}
    assert result["newInstallationId"] == NEW_INSTALLATION_ID
    assert result["acceptanceNamespace"] == {
        "uid": NAMESPACE_UID,
        "resourceVersion": "17",
    }
    assert delete_called is False
    assert json.loads((store / "installation-identity.json").read_text()) == (
        MODULE.INSTALLATION_STATE.installation_identity_document(
            installation_id=NEW_INSTALLATION_ID,
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            cluster_uid=CLUSTER_UID,
        )
    )
    journal_bytes = MODULE.canonical_journal_bytes(result)
    journal_path = private_root / "new-installation" / "journal.json"
    assert journal_path.read_bytes() == journal_bytes
    assert hashlib.sha256(journal_bytes).hexdigest()
    assert base64.b64encode(OLD_KEY) not in journal_bytes
    assert base64.b64encode(NEW_KEY) not in journal_bytes
    assert b'"hmac-key"' not in journal_bytes


def test_exact_v3_trust_is_full_readback_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    original_files = _replace_with_v3_trust(store, runner)

    result = MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: (_ for _ in ()).throw(
            AssertionError("v3 no-op must not generate a key")
        ),
        installation_id_factory=lambda: (_ for _ in ()).throw(
            AssertionError("v3 no-op must not generate an installation ID")
        ),
        delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("v3 no-op must not delete trust")
        ),
        get_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("v3 no-op must not use the delete REST client")
        ),
    )

    assert result == {
        "schemaVersion": MODULE.NEW_INSTALLATION_SCHEMA,
        "operation": "noOp",
        "commit": COMMIT,
        "context": "rke",
        "clusterUid": CLUSTER_UID,
        "identityMode": "bundledKeycloak",
        "issuerUrl": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        "clientId": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        "oldInstallationId": OLD_INSTALLATION_ID,
        "newInstallationId": OLD_INSTALLATION_ID,
        "oldSecret": {"uid": OLD_SECRET_UID, "resourceVersion": "19"},
        "resultSecret": {"uid": OLD_SECRET_UID, "resourceVersion": "19"},
        "acceptanceNamespace": {"uid": NAMESPACE_UID, "resourceVersion": "17"},
        "quarantine": {},
        "state": "completed",
        "pointOfNoReturn": False,
    }
    assert (
        tuple(
            (store / filename).read_bytes()
            for filename in MODULE.QUARANTINED_TRUST_FILES
        )
        == original_files
    )
    assert runner.secret_reads == 1
    assert not (private_root / "new-installation" / "quarantine").exists()
    assert (
        private_root / "new-installation" / "journal.json"
    ).read_bytes() == MODULE.canonical_journal_bytes(result)


def test_partial_stable_trust_stops_before_cluster_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    (store / "acceptance-hmac.key").unlink()

    with pytest.raises(MODULE.NewInstallationError, match="partially present"):
        MODULE.new_installation(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            confirm_forward_only=True,
            runner=runner,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("partial trust must not generate a key")
            ),
            installation_id_factory=lambda: (_ for _ in ()).throw(
                AssertionError("partial trust must not generate an installation ID")
            ),
            delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("partial trust must not delete")
            ),
        )

    assert runner.secret_reads == 0
    assert not (private_root / "new-installation" / "journal.json").exists()


def test_cross_operation_resume_state_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    _replace_with_v3_trust(store, runner)
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        "client_id": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        "confirm_forward_only": True,
        "runner": runner,
    }
    result = MODULE.new_installation(**arguments)
    result["state"] = "secretAbsent"
    journal_path = private_root / "new-installation" / "journal.json"
    journal_path.write_bytes(MODULE.canonical_journal_bytes(result))
    journal_path.chmod(0o600)

    with pytest.raises(MODULE.NewInstallationError, match="journal is invalid"):
        MODULE.new_installation(
            **arguments,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("invalid no-op journal must not bootstrap")
            ),
        )


def test_resume_validates_quarantine_before_cluster_read_or_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, _store, runner = _private_state(tmp_path, monkeypatch)
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        "client_id": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        "confirm_forward_only": True,
        "runner": runner,
        "key_factory": lambda: NEW_KEY,
        "installation_id_factory": lambda: NEW_INSTALLATION_ID,
        "delete_transport": lambda **_kwargs: (
            202,
            b'{"apiVersion":"v1","kind":"Status"}',
        ),
        "sleeper": lambda _seconds: None,
        "maximum_get_attempts": 1,
    }

    with pytest.raises(MODULE.NewInstallationError, match="did not complete"):
        MODULE.new_installation(
            **arguments,
            get_transport=lambda **_kwargs: (
                200,
                json.dumps(runner.secret).encode(),
            ),
        )

    quarantine_key = (
        private_root / "new-installation" / "quarantine" / "acceptance-hmac.key"
    )
    quarantine_key.write_bytes(b"corrupt")
    quarantine_key.chmod(0o600)
    with pytest.raises(MODULE.NewInstallationError, match="quarantine digest"):
        MODULE.new_installation(
            **arguments,
            get_transport=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("corrupt quarantine must stop before cluster read")
            ),
        )


def test_readback_verified_resume_completes_after_partial_quarantine_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    old_trust = {
        filename: (store / filename).read_bytes()
        for filename in MODULE.QUARANTINED_TRUST_FILES
    }
    completed = _complete_replacement(kubeconfig=kubeconfig, runner=runner)
    completed["state"] = "readbackVerified"
    journal_path = private_root / "new-installation" / "journal.json"
    journal_path.write_bytes(MODULE.canonical_journal_bytes(completed))
    journal_path.chmod(0o600)
    quarantine = private_root / "new-installation" / "quarantine"
    quarantine.mkdir(mode=0o700)
    for filename in (
        "acceptance-hmac.key",
        "acceptance-trust-anchor.json",
    ):
        path = quarantine / filename
        path.write_bytes(old_trust[filename])
        path.chmod(0o600)

    def resume() -> dict[str, object]:
        return MODULE.new_installation(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            confirm_forward_only=True,
            runner=runner,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("readback-verified resume must not generate a key")
            ),
            installation_id_factory=lambda: (_ for _ in ()).throw(
                AssertionError("readback-verified resume must not generate an ID")
            ),
            delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("readback-verified resume must not delete live trust")
            ),
        )

    quarantine_key = quarantine / "acceptance-hmac.key"
    quarantine_key.chmod(0o644)
    with pytest.raises(MODULE.NewInstallationError, match="mode-0600"):
        resume()
    quarantine_key.chmod(0o600)
    quarantine_key.write_bytes(b"corrupt")
    with pytest.raises(MODULE.NewInstallationError, match="quarantine digest"):
        resume()
    quarantine_key.write_bytes(old_trust["acceptance-hmac.key"])
    unexpected = quarantine / "unexpected"
    unexpected.write_bytes(b"unexpected")
    unexpected.chmod(0o600)
    with pytest.raises(MODULE.NewInstallationError, match="quarantine inventory"):
        resume()
    unexpected.unlink()

    resumed = resume()

    assert resumed["state"] == "completed"
    assert not quarantine.exists()
    assert journal_path.read_bytes() == MODULE.canonical_journal_bytes(resumed)


def test_readback_verified_resume_completes_after_quarantine_directory_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, _store, runner = _private_state(tmp_path, monkeypatch)
    completed = _complete_replacement(kubeconfig=kubeconfig, runner=runner)
    completed["state"] = "readbackVerified"
    journal_path = private_root / "new-installation" / "journal.json"
    journal_path.write_bytes(MODULE.canonical_journal_bytes(completed))
    journal_path.chmod(0o600)
    quarantine = private_root / "new-installation" / "quarantine"
    assert not quarantine.exists()

    resumed = MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: (_ for _ in ()).throw(
            AssertionError("readback-verified resume must not generate a key")
        ),
        installation_id_factory=lambda: (_ for _ in ()).throw(
            AssertionError("readback-verified resume must not generate an ID")
        ),
        delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("readback-verified resume must not delete live trust")
        ),
    )

    assert resumed["state"] == "completed"
    assert not quarantine.exists()
    assert journal_path.read_bytes() == MODULE.canonical_journal_bytes(resumed)


def test_completed_replacement_is_history_and_new_commit_gets_current_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, _store, runner = _private_state(tmp_path, monkeypatch)
    completed = _complete_replacement(kubeconfig=kubeconfig, runner=runner)
    assert completed["operation"] == "replacement"
    journal_path = private_root / "new-installation" / "journal.json"
    completed_history = journal_path.read_bytes()
    next_commit = "b" * 40
    runner.commit = next_commit

    current = MODULE.new_installation(
        commit=next_commit,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: (_ for _ in ()).throw(
            AssertionError("completed history readback must not generate a key")
        ),
        installation_id_factory=lambda: (_ for _ in ()).throw(
            AssertionError("completed history readback must not generate an ID")
        ),
        delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("completed history readback must not delete")
        ),
    )

    assert current["operation"] == "noOp"
    assert current["commit"] == next_commit
    assert current["newInstallationId"] == NEW_INSTALLATION_ID
    assert journal_path.read_bytes() == completed_history


def test_completed_history_allows_same_cluster_equivalent_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, _store, runner = _private_state(tmp_path, monkeypatch)
    _complete_replacement(kubeconfig=kubeconfig, runner=runner)
    journal_path = private_root / "new-installation" / "journal.json"
    completed_history = journal_path.read_bytes()
    kubeconfig.write_bytes(_kubeconfig("rke-equivalent"))
    kubeconfig.chmod(0o600)

    current = MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke-equivalent",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: (_ for _ in ()).throw(
            AssertionError("completed history readback must not generate a key")
        ),
        installation_id_factory=lambda: (_ for _ in ()).throw(
            AssertionError("completed history readback must not generate an ID")
        ),
        delete_transport=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("completed history readback must not delete")
        ),
    )

    assert current["operation"] == "noOp"
    assert current["context"] == "rke-equivalent"
    assert current["clusterUid"] == CLUSTER_UID
    assert journal_path.read_bytes() == completed_history


@pytest.mark.parametrize("drift", ["secretUid", "installationId"])
def test_completed_history_rejects_valid_but_different_live_trust(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    _complete_replacement(kubeconfig=kubeconfig, runner=runner)
    assert runner.secret is not None
    anchor_path = store / "acceptance-trust-anchor.json"
    anchor = json.loads(anchor_path.read_text())
    if drift == "secretUid":
        runner.secret["metadata"].update(
            {"uid": DRIFT_SECRET_UID, "resourceVersion": "41"}
        )
        anchor["secretUid"] = DRIFT_SECRET_UID
    else:
        identity_document = MODULE.INSTALLATION_STATE.installation_identity_document(
            installation_id=DRIFT_INSTALLATION_ID,
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            cluster_uid=CLUSTER_UID,
        )
        identity = (
            json.dumps(identity_document, indent=2, sort_keys=True) + "\n"
        ).encode()
        identity_path = store / "installation-identity.json"
        identity_path.write_bytes(identity)
        identity_path.chmod(0o600)
        replacement = json.loads(
            MODULE.INSTALLATION_STATE.acceptance_secret_bytes(
                key=NEW_KEY,
                identity=identity,
                cluster_uid=CLUSTER_UID,
            )
        )
        replacement["metadata"].update({"uid": NEW_SECRET_UID, "resourceVersion": "31"})
        runner.secret = replacement
        anchor["installationIdentitySha256"] = hashlib.sha256(identity).hexdigest()
    anchor_path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n")
    anchor_path.chmod(0o600)

    with pytest.raises(MODULE.NewInstallationError, match="completed history"):
        MODULE.new_installation(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            confirm_forward_only=True,
            runner=runner,
        )

    assert (
        private_root / "new-installation" / "journal.json"
    ).read_text() == MODULE.canonical_journal_bytes(
        json.loads((private_root / "new-installation" / "journal.json").read_text())
    ).decode()


def test_noncompleted_transaction_rejects_new_commit_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _private_root, kubeconfig, _store, runner = _private_state(tmp_path, monkeypatch)
    arguments = {
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        "client_id": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        "confirm_forward_only": True,
        "runner": runner,
        "installation_id_factory": lambda: NEW_INSTALLATION_ID,
        "delete_transport": lambda **_kwargs: (
            202,
            b'{"apiVersion":"v1","kind":"Status"}',
        ),
        "get_transport": lambda **_kwargs: (
            200,
            json.dumps(runner.secret).encode(),
        ),
        "sleeper": lambda _seconds: None,
        "maximum_get_attempts": 1,
    }
    with pytest.raises(MODULE.NewInstallationError, match="did not complete"):
        MODULE.new_installation(commit=COMMIT, kubeconfig=kubeconfig, **arguments)

    next_commit = "b" * 40
    runner.commit = next_commit
    with pytest.raises(MODULE.NewInstallationError, match="resume input"):
        MODULE.new_installation(
            commit=next_commit,
            kubeconfig=kubeconfig,
            **arguments,
        )


@pytest.mark.parametrize("delete_status", [200, 202])
def test_207_retired_v2_trust_is_one_locked_forward_only_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delete_status: int,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    get_count = 0

    def delete_transport(*, url, headers, body, tls_context, timeout):
        journal = json.loads(
            (private_root / "new-installation" / "journal.json").read_text()
        )
        assert journal["pointOfNoReturn"] is True
        assert journal["state"] == "secretDeleteStarted"
        assert runner.secret_reads == 1
        assert url.endswith(
            "/api/v1/namespaces/aileron-acceptance-system/"
            "secrets/aileron-acceptance-signing"
        )
        assert json.loads(body)["preconditions"] == {
            "uid": OLD_SECRET_UID,
            "resourceVersion": "19",
        }
        return delete_status, b'{"apiVersion":"v1","kind":"Status"}'

    def get_transport(*, url, headers, tls_context, timeout):
        nonlocal get_count
        get_count += 1
        if get_count == 1:
            deleting = json.loads(json.dumps(runner.secret))
            deleting["metadata"].update(
                {
                    "resourceVersion": "20",
                    "deletionTimestamp": "2026-08-10T00:00:00Z",
                }
            )
            return 200, json.dumps(deleting).encode()
        runner.secret = None
        return 404, b'{"apiVersion":"v1","kind":"Status","reason":"NotFound"}'

    result = MODULE.new_installation(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        confirm_forward_only=True,
        runner=runner,
        key_factory=lambda: NEW_KEY,
        installation_id_factory=lambda: NEW_INSTALLATION_ID,
        delete_transport=delete_transport,
        get_transport=get_transport,
        sleeper=lambda _seconds: None,
        maximum_get_attempts=3,
    )

    assert result["state"] == "completed"
    assert result["pointOfNoReturn"] is True
    assert result["oldSecret"] == {
        "uid": OLD_SECRET_UID,
        "resourceVersion": "19",
    }
    assert result["newInstallationId"] == NEW_INSTALLATION_ID
    assert result["oldInstallationId"] is None
    assert (
        json.loads((store / "installation-identity.json").read_text())["installationId"]
        == NEW_INSTALLATION_ID
    )
    assert runner.secret is not None
    assert runner.secret["metadata"]["uid"] == NEW_SECRET_UID
    assert runner.secret_reads == 4
    assert get_count == 2
    assert not (private_root / "new-installation" / "quarantine").exists()


def test_replacement_secret_uid_stops_without_rollback_or_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, store, runner = _private_state(tmp_path, monkeypatch)
    replacement_uid = "77777777-7777-4777-8777-777777777777"

    def delete_transport(**_kwargs):
        return 202, b'{"apiVersion":"v1","kind":"Status"}'

    def get_transport(**_kwargs):
        replacement = json.loads(json.dumps(runner.secret))
        replacement["metadata"]["uid"] = replacement_uid
        return 200, json.dumps(replacement).encode()

    with pytest.raises(MODULE.NewInstallationError, match="different UID"):
        MODULE.new_installation(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            confirm_forward_only=True,
            runner=runner,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("new key must not be generated")
            ),
            installation_id_factory=lambda: NEW_INSTALLATION_ID,
            delete_transport=delete_transport,
            get_transport=get_transport,
            sleeper=lambda _seconds: None,
            maximum_get_attempts=2,
        )

    journal = json.loads(
        (private_root / "new-installation" / "journal.json").read_text()
    )
    assert journal["pointOfNoReturn"] is True
    assert journal["state"] == "secretDeleteAccepted"
    assert not (store / "installation-identity.json").exists()
    assert (private_root / "new-installation" / "quarantine").is_dir()
