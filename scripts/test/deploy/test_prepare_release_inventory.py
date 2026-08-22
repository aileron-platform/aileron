from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy/rke2/prepare_release_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_release_inventory", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = json.loads(
    (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
)
COMMIT = "a" * 40
KEY = bytes(range(32))
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
IDENTITY_DIGEST = "b" * 64


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


def _private(path: Path, content: str) -> Path:
    _private_directory(path.parent)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
    return path


def _inventory(
    path: Path,
    *,
    first_digest: str = "1" * 64,
    first_runtime_digest: str | None = None,
) -> Path:
    rows = []
    for index, component in enumerate(CONTRACT["publishedComponents"]):
        repository = f"harbor.example.test/library/{component}"
        digest = first_digest if index == 0 else f"{index + 1:064x}"
        runtime_digest = (
            first_runtime_digest
            if index == 0 and first_runtime_digest is not None
            else f"{index + 101:064x}"
        )
        rows.append(
            f"{component}\t{COMMIT}\tlinux/amd64\t"
            f"{repository}:git-{COMMIT}\t{repository}@sha256:{digest}\t"
            f"{repository}@sha256:{runtime_digest}\n"
        )
    return _private(path, "".join(rows))


def _kubeconfig_content(*, server: str = "https://192.0.2.10:6443") -> str:
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
    )


def _kubeconfig(path: Path) -> Path:
    return _private(path, _kubeconfig_content())


def _docker_config_path(private_root: Path) -> Path:
    return private_root / "inputs/docker/config.json"


class Runner:
    def __init__(self, *, dirty: bool = False, head: str = COMMIT) -> None:
        self.dirty = dirty
        self.head = head
        self.calls: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(command)
        if command == ["git", "status", "--porcelain"]:
            return "M dirty\n" if self.dirty else ""
        if command == ["git", "rev-parse", "--verify", "HEAD"]:
            return f"{self.head}\n"
        if command[0] == "kubectl" and command[-6:] == [
            "config",
            "view",
            "--raw",
            "--flatten",
            "--minify",
            "--output=json",
        ]:
            raw = Path(command[command.index("--kubeconfig") + 1])
            return raw.read_text(encoding="utf-8")
        if command[:4] == ["docker", "buildx", "imagetools", "inspect"]:
            assert environment is not None
            assert environment["DOCKER_CONFIG"].endswith("/inputs/docker")
            tagged_image = command[4]
            component = tagged_image.rsplit("/", 1)[1].split(":", 1)[0]
            index = CONTRACT["publishedComponents"].index(component)
            index_digest = "1" * 64 if index == 0 else f"{index + 1:064x}"
            runtime_digest = f"{index + 101:064x}"
            return json.dumps(
                {
                    "name": tagged_image,
                    "image": {
                        "os": "linux",
                        "architecture": "amd64",
                        "config": {
                            "Labels": {
                                "org.opencontainers.image.revision": COMMIT,
                            }
                        },
                    },
                    "manifest": {
                        "mediaType": "application/vnd.oci.image.index.v1+json",
                        "digest": f"sha256:{index_digest}",
                        "manifests": [
                            {
                                "mediaType": (
                                    "application/vnd.oci.image.manifest.v1+json"
                                ),
                                "digest": f"sha256:{runtime_digest}",
                                "platform": {
                                    "os": "linux",
                                    "architecture": "amd64",
                                },
                            },
                            {
                                "mediaType": (
                                    "application/vnd.oci.image.manifest.v1+json"
                                ),
                                "digest": f"sha256:{index + 201:064x}",
                                "platform": {
                                    "os": "unknown",
                                    "architecture": "unknown",
                                },
                                "annotations": {
                                    "vnd.docker.reference.type": (
                                        "attestation-manifest"
                                    ),
                                    "vnd.docker.reference.digest": (
                                        f"sha256:{runtime_digest}"
                                    ),
                                },
                            },
                        ],
                    },
                },
                separators=(",", ":"),
            )
        raise AssertionError(f"unexpected command: {command}")


class ReplacingSourceRunner(Runner):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> str:
        if command[0] == "kubectl" and "--flatten" in command:
            self.source.write_text(
                _kubeconfig_content(server="https://192.0.2.20:6443"),
                encoding="utf-8",
            )
            self.source.chmod(0o600)
        return super().__call__(command, environment=environment)


class FlattenIdentityDriftRunner(Runner):
    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> str:
        if command[0] == "kubectl" and "--flatten" in command:
            self.calls.append(command)
            raw = Path(command[command.index("--kubeconfig") + 1])
            document = json.loads(raw.read_bytes())
            document["clusters"][0]["cluster"]["server"] = (
                "https://192.0.2.30:6443"
            )
            return json.dumps(document, separators=(",", ":"), sort_keys=True)
        return super().__call__(command, environment=environment)


@pytest.fixture
def prepared_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, list[dict]]:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    secret_store = _private_directory(
        private_root / "install-secrets" / "homelab"
    )
    MODULE.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.INSTALLATION_STATE.SECRET_STORE = secret_store
    MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE = secret_store
    trust_calls: list[dict] = []

    def load_trust(**arguments):
        trust_calls.append(arguments)
        return SimpleNamespace(
            key=KEY,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_release_trust",
        load_trust,
    )
    _private(
        _docker_config_path(private_root),
        '{"auths":{"harbor.example.test":{}}}\n',
    )
    return (
        private_root,
        _kubeconfig(private_root / "inputs/kubeconfig"),
        _inventory(private_root / "release/images.tsv"),
        trust_calls,
    )


def test_cli_has_no_output_or_trust_store_override() -> None:
    completed = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--help"],
        capture_output=True,
        check=True,
        text=True,
    )

    for option in (
        "--commit",
        "--context",
        "--kubeconfig",
        "--inventory",
        "--docker-config",
        "--registry",
        "--project",
    ):
        assert option in completed.stdout
    for forbidden in ("--output", "--private-root", "--secret-store", "--key"):
        assert forbidden not in completed.stdout


def test_prepares_fixed_write_once_inventory_from_live_trust(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs
    runner = Runner()

    first = MODULE.prepare_release_inventory(
        commit=COMMIT,
        context="rke",
        kubeconfig=kubeconfig,
        inventory=inventory,
        docker_config=_docker_config_path(private_root),
        registry="harbor.example.test",
        project="library",
        runner=runner,
    )
    second = MODULE.prepare_release_inventory(
        commit=COMMIT,
        context="rke",
        kubeconfig=kubeconfig,
        inventory=inventory,
        docker_config=_docker_config_path(private_root),
        registry="harbor.example.test",
        project="library",
        runner=runner,
    )

    signed = private_root / "install" / COMMIT / "signed-image-inventory.json"
    preparation = private_root / "install" / COMMIT / "release-preparation"
    assert signed.is_file()
    assert stat.S_IMODE(signed.stat().st_mode) == 0o600
    assert first["created"] is True
    assert second == {**first, "created": False}
    assert first["imageCount"] == 11
    assert len(trust_calls) == 2
    assert all(call["kubeconfig"] == preparation / "kubeconfig" for call in trust_calls)
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in preparation.iterdir()
    )
    assert not any(
        command[0] == "kubectl" and any(
            verb in command for verb in ("apply", "create", "delete", "patch")
        )
        for command in runner.calls
    )


def test_rejects_changed_unsigned_inventory_without_replacing_signed_envelope(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, _ = prepared_inputs
    runner = Runner()
    MODULE.prepare_release_inventory(
        commit=COMMIT,
        context="rke",
        kubeconfig=kubeconfig,
        inventory=inventory,
        docker_config=_docker_config_path(private_root),
        registry="harbor.example.test",
        project="library",
        runner=runner,
    )
    signed = private_root / "install" / COMMIT / "signed-image-inventory.json"
    original = signed.read_bytes()
    _inventory(inventory, first_runtime_digest="f" * 64)

    with pytest.raises(
        MODULE.ReleaseInventoryPreparationError,
        match="published release inputs are invalid",
    ):
        MODULE.prepare_release_inventory(
            commit=COMMIT,
            context="rke",
            kubeconfig=kubeconfig,
            inventory=inventory,
            docker_config=_docker_config_path(private_root),
            registry="harbor.example.test",
            project="library",
            runner=runner,
        )

    assert signed.read_bytes() == original


def test_rejects_unsigned_digest_pair_not_observed_in_registry(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs
    _inventory(inventory, first_runtime_digest="f" * 64)

    with pytest.raises(
        MODULE.ReleaseInventoryPreparationError,
        match="published registry provenance is invalid",
    ):
        MODULE.prepare_release_inventory(
            commit=COMMIT,
            context="rke",
            kubeconfig=kubeconfig,
            inventory=inventory,
            docker_config=_docker_config_path(private_root),
            registry="harbor.example.test",
            project="library",
            runner=Runner(),
        )

    assert trust_calls == []
    assert not (
        private_root / "install" / COMMIT / "signed-image-inventory.json"
    ).exists()


def test_dirty_checkout_creates_no_commit_release_directory(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs

    with pytest.raises(
        MODULE.ReleaseInventoryPreparationError,
        match="clean Git checkout",
    ):
        MODULE.prepare_release_inventory(
            commit=COMMIT,
            context="rke",
            kubeconfig=kubeconfig,
            inventory=inventory,
            docker_config=_docker_config_path(private_root),
            registry="harbor.example.test",
            project="library",
            runner=Runner(dirty=True),
        )

    assert not (private_root / "install").exists()
    assert trust_calls == []


def test_global_private_root_lock_contention_creates_no_release_state(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs
    descriptor = os.open(
        private_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(
            MODULE.ReleaseInventoryPreparationError,
            match="another installation operation",
        ):
            MODULE.prepare_release_inventory(
                commit=COMMIT,
                context="rke",
                kubeconfig=kubeconfig,
                inventory=inventory,
                docker_config=_docker_config_path(private_root),
                registry="harbor.example.test",
                project="library",
                runner=Runner(),
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    assert not (private_root / "install").exists()
    assert trust_calls == []


def test_source_replacement_after_raw_snapshot_cannot_change_release_identity(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs
    original = kubeconfig.read_bytes()

    result = MODULE.prepare_release_inventory(
        commit=COMMIT,
        context="rke",
        kubeconfig=kubeconfig,
        inventory=inventory,
        docker_config=_docker_config_path(private_root),
        registry="harbor.example.test",
        project="library",
        runner=ReplacingSourceRunner(kubeconfig),
    )

    raw_snapshot = (
        private_root
        / "install"
        / COMMIT
        / "release-preparation"
        / "kubeconfig.raw"
    )
    assert result["imageCount"] == 11
    assert kubeconfig.read_bytes() != original
    assert raw_snapshot.read_bytes() == original
    assert len(trust_calls) == 1


def test_flattened_kubeconfig_identity_drift_fails_before_trust_loading(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
) -> None:
    private_root, kubeconfig, inventory, trust_calls = prepared_inputs

    with pytest.raises(
        MODULE.ReleaseInventoryPreparationError,
        match="published release inputs are invalid",
    ):
        MODULE.prepare_release_inventory(
            commit=COMMIT,
            context="rke",
            kubeconfig=kubeconfig,
            inventory=inventory,
            docker_config=_docker_config_path(private_root),
            registry="harbor.example.test",
            project="library",
            runner=FlattenIdentityDriftRunner(),
        )

    assert trust_calls == []
    assert not (
        private_root / "install" / COMMIT / "signed-image-inventory.json"
    ).exists()


@pytest.mark.parametrize("tamper", ["canonical", "invalid-utf8"])
def test_existing_signed_inventory_tamper_fails_with_safe_error(
    prepared_inputs: tuple[Path, Path, Path, list[dict]],
    tamper: str,
) -> None:
    private_root, kubeconfig, inventory, _ = prepared_inputs
    runner = Runner()
    MODULE.prepare_release_inventory(
        commit=COMMIT,
        context="rke",
        kubeconfig=kubeconfig,
        inventory=inventory,
        docker_config=_docker_config_path(private_root),
        registry="harbor.example.test",
        project="library",
        runner=runner,
    )
    signed = private_root / "install" / COMMIT / "signed-image-inventory.json"
    if tamper == "canonical":
        document = json.loads(signed.read_bytes())
        document["clusterUid"] = "99999999-9999-4999-8999-999999999999"
        signed.write_bytes(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
            + b"\n"
        )
    else:
        signed.write_bytes(b"{\"schemaVersion\":\xff}\n")
    signed.chmod(0o600)

    with pytest.raises(
        MODULE.ReleaseInventoryPreparationError,
        match="signed image inventory is invalid",
    ):
        MODULE.prepare_release_inventory(
            commit=COMMIT,
            context="rke",
            kubeconfig=kubeconfig,
            inventory=inventory,
            docker_config=_docker_config_path(private_root),
            registry="harbor.example.test",
            project="library",
            runner=runner,
        )


def test_main_prints_only_structured_non_secret_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = {
        "schemaVersion": MODULE.RESULT_SCHEMA,
        "commit": COMMIT,
        "context": "rke",
        "imageCount": 11,
        "created": True,
        "signedInventorySha256": "c" * 64,
    }
    monkeypatch.setattr(MODULE, "prepare_release_inventory", lambda **_args: expected)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_release_inventory.py",
            "--commit",
            COMMIT,
            "--context",
            "rke",
            "--kubeconfig",
            "/private/kubeconfig",
            "--inventory",
            "/private/images.tsv",
            "--docker-config",
            "/private/docker/config.json",
            "--registry",
            "harbor.example.test",
            "--project",
            "library",
        ],
    )

    assert MODULE.main() == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_main_reports_only_safe_preparation_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(**_arguments):
        raise MODULE.ReleaseInventoryPreparationError(
            "signed image inventory is invalid"
        )

    monkeypatch.setattr(MODULE, "prepare_release_inventory", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_release_inventory.py",
            "--commit",
            COMMIT,
            "--context",
            "rke",
            "--kubeconfig",
            "/private/kubeconfig",
            "--inventory",
            "/private/images.tsv",
            "--docker-config",
            "/private/docker/config.json",
            "--registry",
            "harbor.example.test",
            "--project",
            "library",
        ],
    )

    assert MODULE.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "signed image inventory is invalid\n"
