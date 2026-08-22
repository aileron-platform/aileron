"""Kubernetes platform Secret apply contract tests."""

from __future__ import annotations

import base64
import copy
import importlib.util
import inspect
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "rke2"
    / "apply_platform_secrets.py"
)
SPEC = importlib.util.spec_from_file_location("apply_platform_secrets", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "platform-installation"
    / "secret-registry.json"
)
COMMIT = "a" * 40
NAMESPACE_UIDS = {
    "workspace-system": "11111111-1111-4111-8111-111111111111",
    "aileron-turn-system": "22222222-2222-4222-8222-222222222222",
}


def _namespace_document(namespace: str, uid: str, *, owner: str) -> dict:
    labels = MODULE.NAMESPACE_CONTRACT.profile_labels(namespace)
    labels[MODULE.NAMESPACE_CONTRACT.NAMESPACE_OWNER_LABEL] = owner
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
            "uid": uid,
            "resourceVersion": "17",
            "labels": labels,
        },
        "status": {"phase": "Active"},
    }


def _existing_secret(
    namespace: str,
    name: str,
    *,
    uid: str = "44444444-4444-4444-8444-444444444444",
    resource_version: str = "17",
    annotation: bool = False,
) -> dict:
    metadata: dict[str, object] = {
        "name": name,
        "namespace": namespace,
        "uid": uid,
        "resourceVersion": resource_version,
        "labels": {MODULE.SECRET_OWNER_LABEL: MODULE.INSTALLER_OWNER},
    }
    if annotation:
        metadata["annotations"] = {
            "kubectl.kubernetes.io/last-applied-configuration": "legacy-client-apply"
        }
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": metadata,
        "type": "Opaque",
        "data": {"legacy": "dmFsdWU="},
    }


def _private_root(tmp_path: Path) -> Path:
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700, exist_ok=True)
    private_root.chmod(0o700)
    MODULE.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.PRIVATE_INPUT.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    return private_root


def _kubeconfig(tmp_path: Path) -> Path:
    private_root = _private_root(tmp_path)
    path = private_root / "kubeconfig"
    path.write_text(
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": "rke",
                "clusters": [
                    {
                        "name": "rke",
                        "cluster": {
                            "server": "https://192.0.2.10:6443",
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
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _artifacts(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    private_root = _private_root(tmp_path)
    artifact_dir = private_root / "artifacts"
    artifact_dir.mkdir(mode=0o700, parents=True)
    for artifact in registry["artifacts"]:
        if artifact["source"] not in {"generated", "selected"}:
            continue
        path = artifact_dir / artifact["path"]
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(f"value-for-{artifact['id']}", encoding="utf-8")
        path.chmod(0o600)
    external: dict[str, Path] = {}
    for artifact in registry["artifacts"]:
        if artifact["source"] != "external" or artifact.get("when") is not None:
            continue
        path = private_root / "external" / artifact["id"]
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        formats = {
            "pemCertificate": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
            "pemPrivateKey": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "dockerConfigJson": '{"auths":{"harbor.example.test":{"auth":"dGVzdA=="}}}',
        }
        path.write_text(
            formats.get(artifact["format"], f"external-{artifact['id']}"),
            encoding="utf-8",
        )
        path.chmod(0o600)
        external[artifact["id"]] = path
    return artifact_dir, external


class Runner:
    def __init__(
        self,
        *,
        namespace_owner: str = "aileron-installer",
        secret_owner: str | None = None,
        source_to_replace: Path | None = None,
    ) -> None:
        self.namespace_owner = namespace_owner
        self.secret_owner = secret_owner
        self.source_to_replace = source_to_replace
        self.calls: list[tuple[list[str], bytes | None]] = []
        self.namespace_uids = dict(NAMESPACE_UIDS)
        self.namespace_reads = 0
        self.replace_namespace_on_read: int | None = None
        self.secrets: dict[tuple[str, str], dict] = {}
        self.secret_revision = 100
        self.replace_namespace_after_full_secret_get: int | None = None

    def __call__(self, command: list[str], stdin: bytes | None = None) -> bytes:
        self.calls.append((command, stdin))
        if "view" in command and "--flatten" in command:
            raw = Path(command[command.index("--kubeconfig") + 1])
            if self.source_to_replace is not None:
                replacement = json.loads(self.source_to_replace.read_bytes())
                replacement["clusters"][0]["cluster"][
                    "server"
                ] = "https://192.0.2.20:6443"
                self.source_to_replace.write_text(
                    json.dumps(
                        replacement,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                self.source_to_replace.chmod(0o600)
            return raw.read_bytes()
        if command[-2:] == ["config", "current-context"]:
            return b"rke\n"
        if "namespace" in command and "get" in command:
            namespace = command[command.index("namespace") + 1]
            self.namespace_reads += 1
            if self.replace_namespace_on_read == self.namespace_reads:
                self.namespace_uids[namespace] = "33333333-3333-4333-8333-333333333333"
            return json.dumps(
                _namespace_document(
                    namespace,
                    self.namespace_uids[namespace],
                    owner=self.namespace_owner,
                )
            ).encode()
        if "secret" in command and "get" in command:
            namespace = command[command.index("--namespace") + 1]
            name = command[command.index("secret") + 1]
            current = self.secrets.get((namespace, name))
            if any("jsonpath=" in argument for argument in command):
                if self.secret_owner is not None:
                    return self.secret_owner.encode()
                if current is None:
                    raise MODULE.CommandNotFoundError("not found")
                return current["metadata"]["labels"][MODULE.SECRET_OWNER_LABEL].encode()
            output = b"" if current is None else json.dumps(current).encode()
            if self.replace_namespace_after_full_secret_get is not None:
                offset = self.replace_namespace_after_full_secret_get
                self.replace_namespace_after_full_secret_get = None
                self.replace_namespace_on_read = self.namespace_reads + offset
            return output
        if (
            stdin is not None
            and ("create" in command or "replace" in command)
            and "--dry-run=server" not in command
        ):
            document = json.loads(stdin)
            metadata = document["metadata"]
            key = (metadata["namespace"], metadata["name"])
            current = self.secrets.get(key)
            if "create" in command:
                if current is not None:
                    raise MODULE.PlatformSecretApplyError("already exists")
                metadata["uid"] = "44444444-4444-4444-8444-444444444444"
            else:
                if current is None:
                    raise MODULE.PlatformSecretApplyError("missing")
                if (
                    metadata.get("uid") != current["metadata"]["uid"]
                    or metadata.get("resourceVersion")
                    != current["metadata"]["resourceVersion"]
                ):
                    raise MODULE.PlatformSecretApplyError("CAS conflict")
            self.secret_revision += 1
            metadata["resourceVersion"] = str(self.secret_revision)
            metadata["managedFields"] = [{"manager": "test-server"}]
            self.secrets[key] = document
            return f"secret/{key[1]}\n".encode()
        return b"accepted"


def _apply_platform_secrets(**arguments: object) -> None:
    arguments.setdefault("expected_namespace_uids", dict(NAMESPACE_UIDS))
    MODULE.apply_platform_secrets(**arguments)


def _transaction_binding(tmp_path: Path, runner: Runner) -> dict[str, object]:
    private_root = _private_root(tmp_path)
    transaction_module = MODULE.INSTALLATION_TRANSACTION
    transaction_module.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    work = private_root / "install" / COMMIT
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    work.parent.chmod(0o700)
    work.chmod(0o700)
    transaction = transaction_module.create_transaction_directory(
        work_directory=work,
        commit=COMMIT,
    )

    def transaction_runner(
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdout_path: Path | None = None,
    ) -> str:
        del environment
        output = runner(command, None)
        if stdout_path is not None:
            stdout_path.write_bytes(output)
            stdout_path.chmod(0o600)
            return ""
        return output.decode("utf-8")

    transaction_module.begin_secret_transaction(
        transaction_directory=transaction,
        commit=COMMIT,
        context="rke",
        identity_mode="externalOidc",
        expected_namespace_uids=dict(NAMESPACE_UIDS),
        runner=transaction_runner,
        registry_path=REGISTRY,
    )
    return {
        "transaction_directory": transaction,
        "transaction_commit": COMMIT,
        "transaction_identity_mode": "externalOidc",
    }


def test_server_dry_run_projects_exact_registry_secrets_without_values_on_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()

    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=kubeconfig,
        context="rke",
        apply=False,
        runner=runner,
    )

    mutation_calls = [
        (command, stdin)
        for command, stdin in runner.calls
        if ("apply" in command or "create" in command) and stdin
    ]
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    active_secrets = [
        secret for secret in registry["secrets"] if secret.get("when") is None
    ]
    assert len(mutation_calls) == len(active_secrets)
    assert all("--dry-run=server" in command for command, _ in mutation_calls)
    assert all(
        "--context" in command and "rke" in command for command, _ in runner.calls
    )
    assert all("--kubeconfig" in command for command, _ in runner.calls)
    assert all(str(kubeconfig) not in command for command, _ in runner.calls)
    cluster_paths = {
        command[command.index("--kubeconfig") + 1]
        for command, _ in runner.calls
        if "--flatten" not in command
    }
    assert len(cluster_paths) == 1
    assert ".apply-platform-secrets-" in next(iter(cluster_paths))
    rendered = [json.loads(stdin) for _, stdin in mutation_calls if stdin]
    assert {
        (item["metadata"]["namespace"], item["metadata"]["name"]) for item in rendered
    } == {(secret["namespace"], secret["name"]) for secret in active_secrets}
    assert (
        "aileron-backend-attestor-system",
        "harbor-rke-creds",
    ) not in {
        (item["metadata"]["namespace"], item["metadata"]["name"]) for item in rendered
    }
    turn_secret_values = {
        base64.b64decode(item["data"]["turn-rest-shared-secret"])
        for item in rendered
        if "turn-rest-shared-secret" in item["data"]
    }
    assert len(turn_secret_values) == 1
    captured = capsys.readouterr()
    all_values = [path.read_text() for path in external.values()]
    assert not any(
        value in captured.out or value in captured.err for value in all_values
    )


def test_external_data_service_values_project_only_external_inputs(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    private_root = MODULE.INSTALLATION_STATE.PRIVATE_ROOT
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for artifact in registry["artifacts"]:
        if artifact.get("when") not in {
            "postgres.enabled=false",
            "redis.enabled=false",
        }:
            continue
        path = private_root / "external" / artifact["id"]
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        values = {
            "pemCertificate": (
                "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n"
            ),
            "redisUrl": f"rediss://redis.example.test:6379/{len(external) % 3}",
        }
        path.write_text(values[artifact["format"]], encoding="utf-8")
        path.chmod(0o600)
        external[artifact["id"]] = path
    database_url = private_root / "external/database-url"
    database_url.write_text(
        "postgresql://platform:secret@postgres.example.test:5432/aileron",
        encoding="utf-8",
    )
    database_url.chmod(0o600)
    external["database-url"] = database_url
    values_path = private_root / "core-values.json"
    values_path.write_text(
        json.dumps({"postgres": {"enabled": False}, "redis": {"enabled": False}}),
        encoding="utf-8",
    )
    values_path.chmod(0o600)
    runner = Runner()

    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=_kubeconfig(tmp_path),
        context="rke",
        apply=False,
        values_path=values_path,
        runner=runner,
    )

    rendered = [
        json.loads(stdin)
        for command, stdin in runner.calls
        if stdin is not None and "apply" in command
    ]
    by_name = {document["metadata"]["name"]: document for document in rendered}
    assert "aileron-platform-database-ca" in by_name
    assert "aileron-external-data-services" in by_name
    assert set(by_name["aileron-platform-secrets"]["data"]) == {
        "database-url",
        "runtime-database-credential-key",
    }
    secret_get_calls = [
        command
        for command, _ in runner.calls
        if "get" in command and "secret" in command
    ]
    assert secret_get_calls
    assert all("--output=json" not in command for command in secret_get_calls)
    assert all(
        any("jsonpath=" in argument for argument in command)
        for command in secret_get_calls
    )


def test_apply_runs_only_after_all_server_dry_runs_succeed(tmp_path: Path) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()

    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=kubeconfig,
        context="rke",
        apply=True,
        runner=runner,
        **_transaction_binding(tmp_path, runner),
    )

    dry_run_calls = [
        (command, json.loads(stdin))
        for command, stdin in runner.calls
        if stdin is not None and "--dry-run=server" in command
    ]
    real_mutations = [
        command
        for command, stdin in runner.calls
        if stdin is not None
        and "--dry-run=server" not in command
        and ("create" in command or "replace" in command)
    ]
    base_dry_runs = [command for command, _ in dry_run_calls if "apply" in command]
    marker_dry_runs = [
        (command, document)
        for command, document in dry_run_calls
        if "create" in command or "replace" in command
    ]
    assert len(base_dry_runs) == len(marker_dry_runs) == len(real_mutations) > 0
    assert all(
        MODULE.INSTALLATION_TRANSACTION.TRANSACTION_MARKER_ANNOTATION
        in document["metadata"].get("annotations", {})
        for _, document in marker_dry_runs
    )
    assert all("create" in command for command in real_mutations)
    assert all("--namespace" in command for command in real_mutations)
    assert not any(
        "apply" in command and "--dry-run=server" not in command
        for command, _ in runner.calls
    )


def test_absent_concurrent_secret_is_rejected_before_real_mutation(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    transaction = _transaction_binding(tmp_path, runner)
    first = json.loads(REGISTRY.read_text(encoding="utf-8"))["secrets"][0]
    target = (first["namespace"], first["name"])
    concurrent = _existing_secret(*target)
    runner.secrets[target] = concurrent

    with pytest.raises(
        MODULE.INSTALLATION_TRANSACTION.InstallationTransactionError,
        match="absent Secret pre-state changed",
    ):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=True,
            runner=runner,
            **transaction,
        )

    assert runner.secrets[target] == concurrent
    assert not any(
        stdin is not None
        and "--dry-run=server" not in command
        and ("create" in command or "replace" in command)
        for command, stdin in runner.calls
    )


def test_existing_secret_recreation_is_rejected_before_real_mutation(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    first = json.loads(REGISTRY.read_text(encoding="utf-8"))["secrets"][0]
    target = (first["namespace"], first["name"])
    runner.secrets[target] = _existing_secret(*target)
    transaction = _transaction_binding(tmp_path, runner)
    replacement = _existing_secret(
        *target,
        uid="55555555-5555-4555-8555-555555555555",
        resource_version="29",
    )
    runner.secrets[target] = replacement

    with pytest.raises(
        MODULE.INSTALLATION_TRANSACTION.InstallationTransactionError,
        match="existing Secret pre-state changed",
    ):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=True,
            runner=runner,
            **transaction,
        )

    assert runner.secrets[target] == replacement
    assert not any(
        stdin is not None
        and "--dry-run=server" not in command
        and ("create" in command or "replace" in command)
        for command, stdin in runner.calls
    )


def test_namespace_replacement_during_prestate_validation_blocks_real_mutation(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    transaction = _transaction_binding(tmp_path, runner)
    runner.replace_namespace_after_full_secret_get = 1

    with pytest.raises(
        MODULE.INSTALLATION_TRANSACTION.InstallationTransactionError,
        match="Namespace",
    ):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=True,
            runner=runner,
            **transaction,
        )

    assert not any(
        stdin is not None
        and "--dry-run=server" not in command
        and ("create" in command or "replace" in command)
        for command, stdin in runner.calls
    )


def test_namespace_replacement_after_pending_intent_blocks_real_mutation(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    transaction = _transaction_binding(tmp_path, runner)
    runner.replace_namespace_after_full_secret_get = 2

    with pytest.raises(
        MODULE.INSTALLATION_TRANSACTION.InstallationTransactionError,
        match="Namespace",
    ):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=True,
            runner=runner,
            **transaction,
        )

    assert not any(
        stdin is not None
        and "--dry-run=server" not in command
        and ("create" in command or "replace" in command)
        for command, stdin in runner.calls
    )


def test_existing_legacy_client_apply_annotation_is_removed_by_cas_replace(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    first = json.loads(REGISTRY.read_text(encoding="utf-8"))["secrets"][0]
    target = (first["namespace"], first["name"])
    runner.secrets[target] = _existing_secret(*target, annotation=True)
    transaction = _transaction_binding(tmp_path, runner)

    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=kubeconfig,
        context="rke",
        apply=True,
        runner=runner,
        **transaction,
    )

    annotations = runner.secrets[target]["metadata"]["annotations"]
    assert "kubectl.kubernetes.io/last-applied-configuration" not in annotations
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        annotations[MODULE.INSTALLATION_TRANSACTION.TRANSACTION_MARKER_ANNOTATION],
    )
    replace_calls = [
        (command, json.loads(stdin))
        for command, stdin in runner.calls
        if stdin is not None
        and "replace" in command
        and "--dry-run=server" not in command
    ]
    assert len(replace_calls) == 1
    assert replace_calls[0][1]["metadata"]["uid"] == (
        "44444444-4444-4444-8444-444444444444"
    )
    assert replace_calls[0][1]["metadata"]["resourceVersion"] == "17"


def test_rejects_context_namespace_and_existing_secret_owner_drift(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)

    with pytest.raises(MODULE.PlatformSecretApplyError, match="context"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="another-context",
            apply=False,
            runner=Runner(),
        )

    with pytest.raises(MODULE.PlatformSecretApplyError, match="namespace identity"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=Runner(namespace_owner="someone-else"),
        )

    with pytest.raises(MODULE.PlatformSecretApplyError, match="Secret owner"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=Runner(secret_owner="someone-else"),
        )


def test_rejects_missing_or_insecure_external_input(tmp_path: Path) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    missing_key = next(iter(external))
    external.pop(missing_key)
    with pytest.raises(MODULE.PlatformSecretApplyError, match="external input"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=Runner(),
        )

    artifacts, external = _artifacts(tmp_path / "second")
    kubeconfig = _kubeconfig(tmp_path / "second")
    first_path = next(iter(external.values()))
    first_path.chmod(0o644)
    assert stat.S_IMODE(first_path.stat().st_mode) == 0o644
    with pytest.raises(MODULE.PlatformSecretApplyError, match="External input"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=Runner(),
        )


@pytest.mark.parametrize("failure", ["hardlink", "outside-root"])
def test_external_input_must_be_private_root_owned_single_link(
    tmp_path: Path,
    failure: str,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    artifact_id, original = next(iter(external.items()))
    if failure == "hardlink":
        (original.parent / "hardlink-copy").hardlink_to(original)
    else:
        outside = tmp_path / "outside-input"
        outside.write_bytes(original.read_bytes())
        outside.chmod(0o600)
        external[artifact_id] = outside

    with pytest.raises(MODULE.PlatformSecretApplyError, match="External input"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=Runner(),
        )


def test_external_input_replacement_during_read_fails_before_cluster_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    target = next(iter(external.values()))
    backup = target.with_name(f"{target.name}.original")
    original_read = os.read
    replaced = False

    def racing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        data = original_read(descriptor, size)
        if not replaced:
            descriptor_path = Path(f"/proc/self/fd/{descriptor}")
            try:
                opened = descriptor_path.resolve(strict=True)
            except OSError:
                opened = None
            if opened == target:
                target.rename(backup)
                target.write_text("replacement-private-value", encoding="utf-8")
                target.chmod(0o600)
                replaced = True
        return data

    monkeypatch.setattr(MODULE.PRIVATE_INPUT.os, "read", racing_read)
    runner = Runner()
    with pytest.raises(MODULE.PlatformSecretApplyError, match="External input"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=kubeconfig,
            context="rke",
            apply=False,
            runner=runner,
        )

    assert replaced is True
    assert not any(
        "config" not in command and ("get" in command or "apply" in command)
        for command, _ in runner.calls
    )


def test_external_input_parser_requires_absolute_path() -> None:
    with pytest.raises(Exception, match="absolute"):
        MODULE._external_input("oidc-client-secret=relative/path")


def test_cli_has_no_acceptance_trust_input_surface() -> None:
    completed = subprocess.run(
        ["python3", str(MODULE_PATH), "--help"],
        capture_output=True,
        check=True,
        text=True,
    )
    assert "--secret-store" not in completed.stdout
    assert "--private-root" not in completed.stdout
    assert "--acceptance-signing-key" not in completed.stdout
    assert "--installation-identity" not in completed.stdout
    assert "--kubeconfig" in completed.stdout
    assert "--registry" not in completed.stdout
    assert (
        "registry_path"
        not in inspect.signature(MODULE.apply_platform_secrets).parameters
    )
    assert (
        inspect.signature(MODULE.apply_platform_secrets)
        .parameters["kubeconfig"]
        .default
        is inspect.Parameter.empty
    )


def test_registry_policy_rejects_override_schema_drift_and_path_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arbitrary = tmp_path / "attacker-registry.json"
    arbitrary.write_text(REGISTRY.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(MODULE, "DEFAULT_REGISTRY", arbitrary)
    with pytest.raises(MODULE.PlatformSecretApplyError, match="path"):
        MODULE._load_registry()

    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema_drift = copy.deepcopy(document)
    schema_drift["artifacts"][0]["unexpected"] = True
    with pytest.raises(MODULE.PlatformSecretApplyError, match="schema"):
        MODULE._validate_registry(schema_drift)

    duplicate_target = copy.deepcopy(document)
    duplicate_target["secrets"].append(copy.deepcopy(duplicate_target["secrets"][0]))
    with pytest.raises(MODULE.PlatformSecretApplyError, match="schema"):
        MODULE._validate_registry(duplicate_target)

    traversal = copy.deepcopy(document)
    generated = next(
        artifact
        for artifact in traversal["artifacts"]
        if artifact["source"] == "generated"
    )
    generated["path"] = "../outside-private-root"
    with pytest.raises(MODULE.PlatformSecretApplyError, match="schema"):
        MODULE._validate_registry(traversal)


def test_ambient_or_noncanonical_kubeconfig_is_not_usable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    canonical = _kubeconfig(tmp_path)
    ambient = tmp_path / "ambient-kubeconfig"
    ambient.write_bytes(canonical.read_bytes())
    ambient.chmod(0o600)
    monkeypatch.setenv("KUBECONFIG", str(canonical))
    runner = Runner()

    with pytest.raises(MODULE.PlatformSecretApplyError, match="kubeconfig"):
        _apply_platform_secrets(
            artifact_directory=artifacts,
            external_inputs=external,
            kubeconfig=ambient,
            context="rke",
            apply=False,
            runner=runner,
        )

    assert runner.calls == []


def test_source_replacement_after_snapshot_cannot_switch_cluster_identity(
    tmp_path: Path,
) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    original = kubeconfig.read_bytes()
    runner = Runner(source_to_replace=kubeconfig)

    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=kubeconfig,
        context="rke",
        apply=False,
        runner=runner,
    )

    assert kubeconfig.read_bytes() != original
    assert all(str(kubeconfig) not in command for command, _ in runner.calls)
    cluster_paths = {
        command[command.index("--kubeconfig") + 1]
        for command, _ in runner.calls
        if "--flatten" not in command
    }
    assert len(cluster_paths) == 1


def test_apply_has_no_acceptance_secret_or_anchor_surface(tmp_path: Path) -> None:
    artifacts, external = _artifacts(tmp_path)
    kubeconfig = _kubeconfig(tmp_path)
    runner = Runner()
    _apply_platform_secrets(
        artifact_directory=artifacts,
        external_inputs=external,
        kubeconfig=kubeconfig,
        context="rke",
        apply=True,
        runner=runner,
        **_transaction_binding(tmp_path, runner),
    )

    serialized_calls = "\n".join(
        " ".join(command) + (stdin.decode("utf-8") if stdin else "")
        for command, stdin in runner.calls
    )
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "aileron-acceptance-signing" not in serialized_calls
    assert "aileron-acceptance-system" not in serialized_calls
    assert "acceptance-hmac.key" not in source
    assert "acceptance-trust-anchor.json" not in source
    assert "installation-identity.json" not in source
    actual_targets = {
        (
            json.loads(stdin)["metadata"]["namespace"],
            json.loads(stdin)["metadata"]["name"],
        )
        for command, stdin in runner.calls
        if stdin is not None
        and "create" in command
        and "--dry-run=server" not in command
    }
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert actual_targets == {
        (secret["namespace"], secret["name"])
        for secret in registry["secrets"]
        if secret.get("when") is None
    }
