"""Pre-reset acceptance trust bootstrap contract tests."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "rke2"
    / "bootstrap_acceptance_trust.py"
)
RKE2_DIRECTORY = MODULE_PATH.parent
SPEC = importlib.util.spec_from_file_location("bootstrap_acceptance_trust", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
NAMESPACE_UID = "33333333-3333-4333-8333-333333333333"
REPLACEMENT_NAMESPACE_UID = "44444444-4444-4444-8444-444444444444"
SECRET_UID = "22222222-2222-4222-8222-222222222222"
INSTALLATION_ID = "66666666-6666-4666-8666-666666666666"
REPLACEMENT_SECRET_UID = "55555555-5555-4555-8555-555555555555"
BUNDLED_ISSUER = "https://keycloak.apps.rke.soez.tw/realms/aileron"


def _acceptance_namespace_document(
    *,
    uid: str = NAMESPACE_UID,
    resource_version: str = "17",
) -> dict:
    document = json.loads(MODULE._acceptance_namespace_manifest())
    document["metadata"].update(
        {"uid": uid, "resourceVersion": resource_version}
    )
    document["status"] = {"phase": "Active"}
    return document


def test_acceptance_trust_uses_a_non_resettable_installer_namespace() -> None:
    collect_spec = importlib.util.spec_from_file_location(
        "collect_reset_inventory_scope", RKE2_DIRECTORY / "collect_reset_inventory.py"
    )
    plan_spec = importlib.util.spec_from_file_location(
        "reset_plan_scope", RKE2_DIRECTORY / "reset_plan.py"
    )
    assert collect_spec and collect_spec.loader and plan_spec and plan_spec.loader
    collect_module = importlib.util.module_from_spec(collect_spec)
    plan_module = importlib.util.module_from_spec(plan_spec)
    collect_spec.loader.exec_module(collect_module)
    plan_spec.loader.exec_module(plan_module)

    assert MODULE.SECRET_NAMESPACE == "aileron-acceptance-system"
    assert MODULE.SECRET_NAMESPACE not in collect_module.TARGET_NAMESPACES
    assert MODULE.SECRET_NAMESPACE not in {
        namespace for namespace, _ in plan_module.RESET_TARGETS
    }


class Runner:
    def __init__(
        self,
        *,
        head: str = COMMIT,
        dirty: bytes = b"",
        current_context: str = "rke",
        cluster_uid: str = CLUSTER_UID,
        flattened_kubeconfig: bytes | None = None,
        after_flatten: object | None = None,
        replace_namespace_after_secret_dry_run: bool = False,
        drift_after_secret_create: str | None = None,
        drift_after_existing_secret_read: str | None = None,
    ) -> None:
        self.head = head
        self.dirty = dirty
        self.current_context = current_context
        self.cluster_uid = cluster_uid
        self.flattened_kubeconfig = flattened_kubeconfig
        self.after_flatten = after_flatten
        self.replace_namespace_after_secret_dry_run = (
            replace_namespace_after_secret_dry_run
        )
        self.drift_after_secret_create = drift_after_secret_create
        self.drift_after_existing_secret_read = drift_after_existing_secret_read
        self.calls: list[tuple[list[str], bytes | None]] = []
        self.environments: list[dict[str, str] | None] = []
        self.acceptance_namespace: dict | None = None
        self.acceptance_secret: dict | None = None

    def __call__(
        self,
        command: list[str],
        stdin: bytes | None = None,
        *,
        environment: dict[str, str] | None = None,
    ) -> bytes:
        self.calls.append((command, stdin))
        self.environments.append(environment)
        if command[:2] == ["git", "status"]:
            return self.dirty
        if command[:2] == ["git", "rev-parse"]:
            return f"{self.head}\n".encode()
        if "config" in command and "view" in command:
            raw_path = Path(command[command.index("--kubeconfig") + 1])
            flattened = self.flattened_kubeconfig or raw_path.read_bytes()
            if callable(self.after_flatten):
                self.after_flatten()
            return flattened
        if command[-2:] == ["config", "current-context"]:
            return f"{self.current_context}\n".encode()
        if "kube-system" in command:
            return self.cluster_uid.encode()
        if "get" in command and "namespace" in command:
            if self.acceptance_namespace is None:
                raise MODULE.CommandNotFoundError("not found")
            return json.dumps(self.acceptance_namespace).encode()
        if "get" in command and "secret" in command:
            if self.acceptance_secret is None:
                raise MODULE.CommandNotFoundError("not found")
            result = json.dumps(self.acceptance_secret).encode()
            if self.drift_after_existing_secret_read is not None:
                drift = self.drift_after_existing_secret_read
                self.drift_after_existing_secret_read = None
                if drift == "namespace":
                    self.acceptance_namespace = _acceptance_namespace_document(
                        uid=REPLACEMENT_NAMESPACE_UID,
                        resource_version="18",
                    )
                elif drift == "secret":
                    replacement = json.loads(json.dumps(self.acceptance_secret))
                    replacement["metadata"]["uid"] = REPLACEMENT_SECRET_UID
                    self.acceptance_secret = replacement
                else:
                    raise AssertionError(f"unsupported resource drift: {drift}")
            return result
        if "--dry-run=server" in command:
            if (
                self.replace_namespace_after_secret_dry_run
                and stdin is not None
                and json.loads(stdin).get("kind") == "Secret"
            ):
                self.acceptance_namespace = _acceptance_namespace_document(
                    uid=REPLACEMENT_NAMESPACE_UID,
                    resource_version="18",
                )
            return b"accepted"
        if "create" in command and stdin is not None:
            created = json.loads(stdin)
            if created["kind"] == "Namespace":
                created["metadata"].update(
                    {"uid": NAMESPACE_UID, "resourceVersion": "17"}
                )
                created["status"] = {"phase": "Active"}
                self.acceptance_namespace = created
                return json.dumps(created).encode()
            created["metadata"]["uid"] = SECRET_UID
            self.acceptance_secret = json.loads(json.dumps(created))
            if self.drift_after_secret_create == "namespace":
                self.acceptance_namespace = _acceptance_namespace_document(
                    uid=REPLACEMENT_NAMESPACE_UID,
                    resource_version="18",
                )
            elif self.drift_after_secret_create == "secret":
                self.acceptance_secret["metadata"]["uid"] = REPLACEMENT_SECRET_UID
            elif self.drift_after_secret_create is not None:
                raise AssertionError(
                    f"unsupported resource drift: {self.drift_after_secret_create}"
                )
            return json.dumps(created).encode()
        raise AssertionError(f"unexpected command: {command}")


def _kubeconfig(*, token: str = "bootstrap-token") -> bytes:
    return (
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": "rke",
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
                        "name": "rke",
                        "context": {"cluster": "homelab", "user": "bootstrap"},
                    }
                ],
                "users": [{"name": "bootstrap", "user": {"token": token}}],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _private_root(tmp_path: Path) -> tuple[Path, Path]:
    private_root = tmp_path / "aileron-private"
    private_root.mkdir(mode=0o700)
    kubeconfig = private_root / "kubeconfig"
    kubeconfig.write_bytes(_kubeconfig())
    kubeconfig.chmod(0o600)
    MODULE.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.INSTALLATION_STATE.SECRET_STORE = (
        private_root / "install-secrets" / "rke2"
    )
    return private_root, kubeconfig


def test_fresh_bootstrap_creates_every_private_directory_as_owner_only(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    previous_umask = os.umask(0o022)
    try:
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=False,
            runner=Runner(),
            key_factory=lambda: bytes(range(32)),
        )
    finally:
        os.umask(previous_umask)

    for directory in (
        private_root / "install-secrets",
        private_root / "install-secrets" / "rke2",
        private_root / "acceptance-bootstrap",
        private_root / "acceptance-bootstrap" / COMMIT,
    ):
        metadata = directory.stat()
        assert stat.S_IMODE(metadata.st_mode) == 0o700
        assert metadata.st_uid == os.geteuid()
        MODULE.PRIVATE_INPUT.validate_private_directory(
            directory,
            "bootstrap private directory",
            private_root=private_root,
        )


def test_bootstrap_rejects_a_hard_linked_existing_signing_key(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    install_secrets = private_root / "install-secrets"
    install_secrets.mkdir(mode=0o700)
    store = install_secrets / "rke2"
    store.mkdir(mode=0o700)
    source = store / "shared-key-source"
    source.write_bytes(bytes(range(32)))
    source.chmod(0o600)
    os.link(source, store / "acceptance-hmac.key")

    with pytest.raises(MODULE.BootstrapError, match="owner-controlled"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=False,
            runner=Runner(),
        )


def test_bootstrap_fails_before_private_or_cluster_work_on_lock_contention(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    descriptor = os.open(private_root, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(MODULE.BootstrapError, match="already running"):
            MODULE.bootstrap_acceptance_trust(
                commit=COMMIT,
                kubeconfig=kubeconfig,
                context="rke",
                identity_mode="bundledKeycloak",
                issuer_url=BUNDLED_ISSUER,
                client_id="aileron-frontend",
                apply=False,
                runner=runner,
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    assert not (private_root / "install-secrets").exists()
    assert not (private_root / "acceptance-bootstrap").exists()
    assert all(command[0] == "git" for command, _ in runner.calls)


def test_bootstrap_rejects_a_noncanonical_secret_store_before_creating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    noncanonical_store = private_root / "other-secret-store"
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "SECRET_STORE", noncanonical_store)

    with pytest.raises(MODULE.BootstrapError, match="canonical"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=False,
            runner=Runner(),
        )

    assert not noncanonical_store.exists()


def test_cli_exposes_only_identity_and_cluster_selection() -> None:
    completed = subprocess.run(
        ["python3", str(MODULE_PATH), "--help"],
        capture_output=True,
        check=True,
        text=True,
    )

    for option in (
        "--commit",
        "--kubeconfig",
        "--context",
        "--identity-mode",
        "--issuer-url",
        "--client-id",
        "--apply",
    ):
        assert option in completed.stdout
    for forbidden in (
        "--private-root",
        "--secret-store",
        "--signing-key",
        "--anchor",
        "--rotate",
    ):
        assert forbidden not in completed.stdout


def test_dry_run_bootstraps_only_local_trust_state_and_server_validates_secret(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    runner = Runner()

    MODULE.bootstrap_acceptance_trust(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=BUNDLED_ISSUER,
        client_id="aileron-frontend",
        apply=False,
        runner=runner,
        key_factory=lambda: bytes(range(32)),
        installation_id_factory=lambda: INSTALLATION_ID,
    )

    store = private_root / "install-secrets" / "rke2"
    key = store / "acceptance-hmac.key"
    identity = store / "installation-identity.json"
    assert key.read_bytes() == bytes(range(32))
    assert key.stat().st_mode & 0o777 == 0o600
    assert json.loads(identity.read_text(encoding="utf-8")) == {
        "clientId": "aileron-frontend",
        "clusterUid": CLUSTER_UID,
        "contractVersion": "aileron-installation-identity/v3",
        "identityMode": "bundledKeycloak",
        "installationId": INSTALLATION_ID,
        "issuerUrl": BUNDLED_ISSUER,
    }
    assert identity.stat().st_mode & 0o777 == 0o600
    assert not (store / "acceptance-trust-anchor.json").exists()
    kubectl = [command for command, _ in runner.calls if command[0] == "kubectl"]
    transaction = private_root / "acceptance-bootstrap" / COMMIT
    raw_kubeconfig = transaction / "kubeconfig.raw"
    flattened_kubeconfig = transaction / "kubeconfig.flattened.json"
    assert raw_kubeconfig.read_bytes() == kubeconfig.read_bytes()
    assert flattened_kubeconfig.read_bytes() == kubeconfig.read_bytes()
    assert raw_kubeconfig.stat().st_mode & 0o777 == 0o600
    assert flattened_kubeconfig.stat().st_mode & 0o777 == 0o600
    flatten_commands = [command for command in kubectl if "view" in command]
    assert len(flatten_commands) == 1
    flatten_call_index = next(
        index
        for index, (command, _) in enumerate(runner.calls)
        if command == flatten_commands[0]
    )
    assert runner.environments[flatten_call_index] == {
        "KUBECONFIG": str(raw_kubeconfig)
    }
    assert flatten_commands[0][1:5] == [
        "--kubeconfig",
        str(raw_kubeconfig),
        "--context",
        "rke",
    ]
    assert all(
        command[1:5]
        == ["--kubeconfig", str(flattened_kubeconfig), "--context", "rke"]
        for command in kubectl
        if "view" not in command
    )
    creates = [command for command in kubectl if "create" in command]
    assert len(creates) == 1
    assert "--dry-run=server" in creates[0]
    manifests = [json.loads(stdin) for _, stdin in runner.calls if stdin is not None]
    assert [(item["kind"], item["metadata"]["name"]) for item in manifests] == [
        ("Namespace", "aileron-acceptance-system")
    ]


def test_source_kubeconfig_replacement_cannot_retarget_cluster_commands(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)

    def replace_source() -> None:
        kubeconfig.write_bytes(_kubeconfig(token="replacement-token"))
        kubeconfig.chmod(0o600)

    runner = Runner(after_flatten=replace_source)
    MODULE.bootstrap_acceptance_trust(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=BUNDLED_ISSUER,
        client_id="aileron-frontend",
        apply=False,
        runner=runner,
        key_factory=lambda: bytes(range(32)),
    )

    flattened = (
        private_root
        / "acceptance-bootstrap"
        / COMMIT
        / "kubeconfig.flattened.json"
    )
    assert flattened.read_bytes() == _kubeconfig()
    assert kubeconfig.read_bytes() == _kubeconfig(token="replacement-token")
    cluster_commands = [
        command
        for command, _ in runner.calls
        if command[0] == "kubectl" and "view" not in command
    ]
    assert cluster_commands
    assert all(
        command[command.index("--kubeconfig") + 1] == str(flattened)
        for command in cluster_commands
    )


def test_rejects_flattened_selected_identity_drift_before_cluster_access(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner(flattened_kubeconfig=_kubeconfig(token="other-token"))

    with pytest.raises(MODULE.BootstrapError, match="selected identity changed"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
        )

    assert runner.acceptance_namespace is None
    assert runner.acceptance_secret is None
    assert not (
        private_root / "install-secrets" / "rke2" / "installation-identity.json"
    ).exists()
    assert [
        command for command, _ in runner.calls if command[0] == "kubectl"
    ] == [
        next(
            command
            for command, _ in runner.calls
            if command[0] == "kubectl" and "view" in command
        )
    ]


def test_commit_bound_snapshot_resume_rejects_changed_source_bytes(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "runner": runner,
    }
    MODULE.bootstrap_acceptance_trust(
        **arguments,
        apply=False,
        key_factory=lambda: bytes(range(32)),
    )
    transaction = private_root / "acceptance-bootstrap" / COMMIT
    original_raw = (transaction / "kubeconfig.raw").read_bytes()
    original_flattened = (transaction / "kubeconfig.flattened.json").read_bytes()
    calls_before_resume = len(runner.calls)
    kubeconfig.write_bytes(_kubeconfig(token="changed-token"))
    kubeconfig.chmod(0o600)

    with pytest.raises(MODULE.BootstrapError, match="snapshot content changed"):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            apply=True,
            key_factory=lambda: b"x" * 32,
        )

    assert (transaction / "kubeconfig.raw").read_bytes() == original_raw
    assert (
        transaction / "kubeconfig.flattened.json"
    ).read_bytes() == original_flattened
    assert all(
        command[0] == "git" for command, _ in runner.calls[calls_before_resume:]
    )
    assert runner.acceptance_secret is None


@pytest.mark.parametrize(
    "variant",
    ("duplicate-key", "whitespace", "reordered", "invalid-utf8"),
)
def test_pre_secret_resume_requires_exact_installation_identity_bytes(
    tmp_path: Path,
    variant: str,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "runner": runner,
    }
    MODULE.bootstrap_acceptance_trust(
        **arguments,
        apply=False,
        key_factory=lambda: bytes(range(32)),
    )
    identity_path = (
        private_root / "install-secrets" / "rke2" / "installation-identity.json"
    )
    canonical = identity_path.read_bytes()
    document = json.loads(canonical)
    if variant == "duplicate-key":
        changed = canonical.replace(
            b'{\n  "clientId":',
            b'{\n  "clientId": "attacker",\n  "clientId":',
            1,
        )
    elif variant == "whitespace":
        changed = canonical.replace(b"{\n", b"{ \n", 1)
    elif variant == "reordered":
        changed = (
            json.dumps(
                dict(reversed(tuple(document.items()))),
                indent=2,
                sort_keys=False,
            )
            + "\n"
        ).encode()
    else:
        changed = b"\xff"
    assert changed != canonical
    identity_path.write_bytes(changed)
    identity_path.chmod(0o600)
    calls_before_resume = len(runner.calls)

    with pytest.raises(MODULE.BootstrapError, match="installation identity"):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            apply=True,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("must not rotate the key")
            ),
        )

    assert runner.acceptance_secret is None
    assert not any(
        "create" in command and "--dry-run=server" not in command
        for command, _ in runner.calls[calls_before_resume:]
    )


def test_apply_creates_immutable_secret_after_dry_run_and_binds_anchor(
    tmp_path: Path,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()

    MODULE.bootstrap_acceptance_trust(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="externalOidc",
        issuer_url="https://identity.example.test/application/o/aileron/",
        client_id="aileron-client",
        apply=True,
        runner=runner,
        key_factory=lambda: b"k" * 32,
    )

    create_calls = [
        (command, json.loads(stdin))
        for command, stdin in runner.calls
        if "create" in command and stdin is not None
    ]
    assert len(create_calls) == 4
    assert "--dry-run=server" in create_calls[0][0]
    assert "--dry-run=server" not in create_calls[1][0]
    assert create_calls[0][1] == create_calls[1][1]
    assert create_calls[0][1]["kind"] == "Namespace"
    assert "--dry-run=server" in create_calls[2][0]
    assert "--dry-run=server" not in create_calls[3][0]
    assert create_calls[2][1] == create_calls[3][1]
    assert create_calls[3][1]["immutable"] is True
    assert create_calls[3][1]["metadata"]["name"] == "aileron-acceptance-signing"
    anchor_path = (
        private_root
        / "install-secrets"
        / "rke2"
        / "acceptance-trust-anchor.json"
    )
    anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    assert anchor == {
        "clusterUid": CLUSTER_UID,
        "contractVersion": "aileron-acceptance-trust-anchor/v2",
        "installationIdentitySha256": create_calls[3][1]["metadata"][
            "annotations"
        ]["platform.aileron.dev/installation-identity-sha256"],
        "keySha256": hashlib.sha256(b"k" * 32).hexdigest(),
        "secretName": "aileron-acceptance-signing",
        "secretNamespace": "aileron-acceptance-system",
        "secretUid": SECRET_UID,
    }
    assert anchor_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("drift", ("namespace", "secret"))
def test_fresh_anchor_bind_rejects_live_resource_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner(drift_after_secret_create=drift)

    with pytest.raises(MODULE.BootstrapError):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
            key_factory=lambda: b"k" * 32,
        )

    anchor_path = (
        private_root
        / "install-secrets"
        / "rke2"
        / "acceptance-trust-anchor.json"
    )
    assert json.loads(anchor_path.read_bytes())["secretUid"] is None


def test_bootstrap_fsyncs_stable_private_store_publications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    fsynced_directories: set[tuple[int, int]] = set()
    fsynced_regular_files: set[tuple[int, int]] = set()
    real_fsync = os.fsync

    def tracking_fsync(descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        if stat.S_ISDIR(metadata.st_mode):
            fsynced_directories.add((metadata.st_dev, metadata.st_ino))
        elif stat.S_ISREG(metadata.st_mode):
            fsynced_regular_files.add((metadata.st_dev, metadata.st_ino))
        real_fsync(descriptor)

    monkeypatch.setattr(MODULE.os, "fsync", tracking_fsync)
    MODULE.bootstrap_acceptance_trust(
        commit=COMMIT,
        kubeconfig=kubeconfig,
        context="rke",
        identity_mode="bundledKeycloak",
        issuer_url=BUNDLED_ISSUER,
        client_id="aileron-frontend",
        apply=True,
        runner=Runner(),
        key_factory=lambda: b"k" * 32,
    )

    store = private_root / "install-secrets" / "rke2"
    store_metadata = store.stat()
    assert (store_metadata.st_dev, store_metadata.st_ino) in fsynced_directories
    for filename in (
        "installation-identity.json",
        "acceptance-hmac.key",
        "acceptance-trust-anchor.json",
    ):
        metadata = (store / filename).stat()
        assert (metadata.st_dev, metadata.st_ino) in fsynced_regular_files


def test_anchor_binding_resumes_after_atomic_replace_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "apply": True,
        "runner": runner,
    }
    real_replace = os.replace

    def interrupted_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated interruption before atomic publication")

    monkeypatch.setattr(MODULE.os, "replace", interrupted_replace)
    with pytest.raises(MODULE.BootstrapError, match="could not be bound"):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            key_factory=lambda: b"k" * 32,
        )

    anchor_path = (
        MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    )
    pending = json.loads(anchor_path.read_bytes())
    assert pending["secretUid"] is None
    assert anchor_path.with_name(f".{anchor_path.name}.tmp").is_file()

    monkeypatch.setattr(MODULE.os, "replace", real_replace)
    MODULE.bootstrap_acceptance_trust(
        **arguments,
        key_factory=lambda: (_ for _ in ()).throw(AssertionError("rotated key")),
    )

    assert json.loads(anchor_path.read_bytes())["secretUid"] == SECRET_UID
    assert not anchor_path.with_name(f".{anchor_path.name}.tmp").exists()


@pytest.mark.parametrize("drift", ("namespace", "secret"))
def test_pending_anchor_resume_rejects_live_resource_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "apply": True,
        "runner": runner,
    }
    real_replace = os.replace

    def interrupted_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated interruption before atomic publication")

    monkeypatch.setattr(MODULE.os, "replace", interrupted_replace)
    with pytest.raises(MODULE.BootstrapError, match="could not be bound"):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            key_factory=lambda: b"k" * 32,
        )
    monkeypatch.setattr(MODULE.os, "replace", real_replace)
    anchor_path = (
        MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    )
    pending_anchor = anchor_path.read_bytes()
    assert json.loads(pending_anchor)["secretUid"] is None
    runner.drift_after_existing_secret_read = drift

    with pytest.raises(MODULE.BootstrapError):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("must not rotate the key")
            ),
        )

    assert anchor_path.read_bytes() == pending_anchor


def test_secret_create_rejects_a_namespace_replacement_after_server_dry_run(
    tmp_path: Path,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner(replace_namespace_after_secret_dry_run=True)
    runner.acceptance_namespace = _acceptance_namespace_document()

    with pytest.raises(MODULE.BootstrapError, match="namespace identity changed"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
            key_factory=lambda: b"k" * 32,
        )

    assert runner.acceptance_secret is None


def test_rejects_existing_acceptance_namespace_with_invalid_security_profile(
    tmp_path: Path,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    runner.acceptance_namespace = _acceptance_namespace_document()
    runner.acceptance_namespace["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce"
    ] = "privileged"

    with pytest.raises(MODULE.BootstrapError, match="namespace ownership"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
            key_factory=lambda: b"k" * 32,
        )

    assert runner.acceptance_secret is None


def test_rejects_existing_acceptance_namespace_with_extra_psa_label(
    tmp_path: Path,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    runner.acceptance_namespace = _acceptance_namespace_document()
    runner.acceptance_namespace["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce-version"
    ] = "latest"

    with pytest.raises(MODULE.BootstrapError, match="namespace ownership"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
            key_factory=lambda: b"k" * 32,
        )

    assert runner.acceptance_secret is None


@pytest.mark.parametrize(
    "drift,error",
    (
        ("missing-uid", "namespace ownership is invalid"),
        ("missing-resource-version", "namespace ownership is invalid"),
        ("terminating", "namespace ownership is invalid"),
        ("deletion-timestamp", "namespace ownership is invalid"),
    ),
)
def test_rejects_incomplete_or_non_active_acceptance_namespace_record(
    tmp_path: Path,
    drift: str,
    error: str,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    namespace = _acceptance_namespace_document()
    if drift == "missing-uid":
        namespace["metadata"].pop("uid")
    elif drift == "missing-resource-version":
        namespace["metadata"].pop("resourceVersion")
    elif drift == "terminating":
        namespace["status"]["phase"] = "Terminating"
    else:
        namespace["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    runner.acceptance_namespace = namespace

    with pytest.raises(MODULE.BootstrapError, match=error):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
            key_factory=lambda: b"k" * 32,
        )

    assert runner.acceptance_secret is None


def test_cli_executes_the_same_bootstrap_contract(tmp_path: Path) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()

    result = MODULE.main(
        [
            "--commit",
            COMMIT,
            "--kubeconfig",
            str(kubeconfig),
            "--context",
            "rke",
            "--identity-mode",
            "bundledKeycloak",
            "--issuer-url",
            BUNDLED_ISSUER,
            "--client-id",
            "aileron-frontend",
            "--apply",
        ],
        runner=runner,
        key_factory=lambda: b"z" * 32,
    )

    assert result == 0
    assert runner.acceptance_secret is not None


def test_matching_existing_trust_is_idempotent(tmp_path: Path) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "apply": True,
        "runner": runner,
    }
    MODULE.bootstrap_acceptance_trust(
        **arguments, key_factory=lambda: bytes(range(32))
    )
    first_anchor = (
        MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    ).read_bytes()

    MODULE.bootstrap_acceptance_trust(
        **arguments,
        key_factory=lambda: (_ for _ in ()).throw(AssertionError("rotated key")),
    )

    actual_creates = [
        command
        for command, _ in runner.calls
        if "create" in command and "--dry-run=server" not in command
    ]
    assert len(actual_creates) == 2
    assert (
        MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    ).read_bytes() == first_anchor


@pytest.mark.parametrize(
    "variant",
    ("duplicate-key", "whitespace", "reordered", "invalid-utf8"),
)
def test_existing_anchor_requires_exact_deterministic_json_bytes(
    tmp_path: Path,
    variant: str,
) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "apply": True,
        "runner": runner,
    }
    MODULE.bootstrap_acceptance_trust(
        **arguments,
        key_factory=lambda: bytes(range(32)),
    )
    anchor_path = (
        MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    )
    canonical = anchor_path.read_bytes()
    document = json.loads(canonical)
    if variant == "duplicate-key":
        changed = canonical.replace(
            b'{\n  "clusterUid":',
            b'{\n  "clusterUid": "attacker",\n  "clusterUid":',
            1,
        )
    elif variant == "whitespace":
        changed = canonical.replace(b"{\n", b"{ \n", 1)
    elif variant == "reordered":
        changed = (
            json.dumps(
                dict(reversed(tuple(document.items()))),
                indent=2,
                sort_keys=False,
            )
            + "\n"
        ).encode()
    else:
        changed = b"\xff"
    assert changed != canonical
    anchor_path.write_bytes(changed)
    anchor_path.chmod(0o600)

    with pytest.raises(MODULE.BootstrapError, match="anchor is invalid"):
        MODULE.bootstrap_acceptance_trust(
            **arguments,
            key_factory=lambda: (_ for _ in ()).throw(
                AssertionError("must not rotate the key")
            ),
        )


@pytest.mark.parametrize("component", ["identity", "key", "secret", "anchor"])
def test_rejects_any_existing_trust_drift(tmp_path: Path, component: str) -> None:
    _, kubeconfig = _private_root(tmp_path)
    runner = Runner()
    arguments = {
        "commit": COMMIT,
        "kubeconfig": kubeconfig,
        "context": "rke",
        "identity_mode": "bundledKeycloak",
        "issuer_url": BUNDLED_ISSUER,
        "client_id": "aileron-frontend",
        "apply": True,
        "runner": runner,
    }
    MODULE.bootstrap_acceptance_trust(
        **arguments, key_factory=lambda: bytes(range(32))
    )
    store = MODULE.INSTALLATION_STATE.SECRET_STORE
    if component == "identity":
        identity_path = store / "installation-identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["clientId"] = "different-client"
        identity_path.write_text(json.dumps(identity), encoding="utf-8")
        identity_path.chmod(0o600)
    elif component == "key":
        key_path = store / "acceptance-hmac.key"
        key_path.write_bytes(b"x" * 32)
        key_path.chmod(0o600)
    elif component == "secret":
        assert runner.acceptance_secret is not None
        runner.acceptance_secret["data"]["hmac-key"] = base64.b64encode(
            b"x" * 32
        ).decode()
    else:
        anchor_path = store / "acceptance-trust-anchor.json"
        anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        anchor["keySha256"] = "f" * 64
        anchor_path.write_text(json.dumps(anchor), encoding="utf-8")
        anchor_path.chmod(0o600)

    with pytest.raises(MODULE.BootstrapError):
        MODULE.bootstrap_acceptance_trust(
            **arguments, key_factory=lambda: b"y" * 32
        )

    actual_creates = [
        command
        for command, _ in runner.calls
        if "create" in command and "--dry-run=server" not in command
    ]
    assert len(actual_creates) == 2


@pytest.mark.parametrize(
    "runner,error",
    [
        (Runner(dirty=b" M tracked.py\n"), "clean"),
        (Runner(head="b" * 40), "HEAD"),
    ],
)
def test_rejects_untrusted_source_before_private_or_cluster_access(
    tmp_path: Path, runner: Runner, error: str
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)

    with pytest.raises(MODULE.BootstrapError, match=error):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
        )

    assert not (private_root / "install-secrets").exists()
    assert all(command[0] == "git" for command, _ in runner.calls)


@pytest.mark.parametrize(
    "runner,error",
    [
        (Runner(current_context="other"), "current context"),
        (Runner(cluster_uid="not-a-uid"), "cluster identity"),
    ],
)
def test_rejects_context_or_cluster_identity_drift(
    tmp_path: Path, runner: Runner, error: str
) -> None:
    _, kubeconfig = _private_root(tmp_path)

    with pytest.raises(MODULE.BootstrapError, match=error):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=True,
            runner=runner,
        )

    assert runner.acceptance_secret is None


def test_rejects_private_state_permission_or_kubeconfig_escape(tmp_path: Path) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    private_root.chmod(0o755)

    with pytest.raises(MODULE.BootstrapError, match="0700"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=False,
            runner=Runner(),
        )

    private_root.chmod(0o700)
    outside = tmp_path / "outside-kubeconfig"
    outside.write_text("fixture", encoding="utf-8")
    outside.chmod(0o600)
    with pytest.raises(MODULE.BootstrapError, match="private root"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=outside,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=BUNDLED_ISSUER,
            client_id="aileron-frontend",
            apply=False,
            runner=Runner(),
        )


@pytest.mark.parametrize(
    "issuer_url,client_id",
    [
        ("https://other.example.test/realms/aileron", "aileron-frontend"),
        (BUNDLED_ISSUER, "other-client"),
    ],
)
def test_rejects_noncanonical_bundled_identity_before_private_state_write(
    tmp_path: Path, issuer_url: str, client_id: str
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()

    with pytest.raises(MODULE.BootstrapError, match="bundled Keycloak identity"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="bundledKeycloak",
            issuer_url=issuer_url,
            client_id=client_id,
            apply=False,
            runner=runner,
        )

    assert not (private_root / "install-secrets").exists()
    assert all(command[0] == "git" for command, _ in runner.calls)


@pytest.mark.parametrize(
    "issuer_url",
    [
        "https://user@identity.example.test/realms/aileron",
        "https://identity.example.test/realms/aileron?tenant=one",
        "https://identity.example.test/realms/aileron#fragment",
        "https://:443/issuer",
        "https://host:bad/issuer",
        "https://host/\nissuer",
        "https://identity.example.test",
        "https://identity.example.test/",
    ],
)
def test_rejects_ambiguous_external_issuer_before_private_or_cluster_access(
    tmp_path: Path, issuer_url: str
) -> None:
    private_root, kubeconfig = _private_root(tmp_path)
    runner = Runner()

    with pytest.raises(MODULE.BootstrapError, match="issuer URL"):
        MODULE.bootstrap_acceptance_trust(
            commit=COMMIT,
            kubeconfig=kubeconfig,
            context="rke",
            identity_mode="externalOidc",
            issuer_url=issuer_url,
            client_id="external-client",
            apply=False,
            runner=runner,
        )

    assert not (private_root / "install-secrets").exists()
    assert all(command[0] == "git" for command, _ in runner.calls)
