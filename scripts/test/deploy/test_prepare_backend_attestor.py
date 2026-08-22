"""Retained backend-attestor prerequisite regression tests."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "rke2"
    / "prepare_backend_attestor.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_backend_attestor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CONTEXT = "rke"
REGISTRY = "harbor.rke.soez.tw"
USERNAME = "robot-installer"
PASSWORD = "private-password"


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


def _kubeconfig_bytes() -> bytes:
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": CONTEXT,
            "clusters": [
                {
                    "name": CONTEXT,
                    "cluster": {
                        "server": "https://192.0.2.10:6443",
                        "certificate-authority-data": "Y2E=",
                    },
                }
            ],
            "contexts": [
                {
                    "name": CONTEXT,
                    "context": {"cluster": CONTEXT, "user": CONTEXT},
                }
            ],
            "users": [
                {
                    "name": CONTEXT,
                    "user": {
                        "client-certificate-data": "Y2VydA==",
                        "client-key-data": "a2V5",
                    },
                }
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _dockerconfig_bytes(*, registry: str = REGISTRY) -> bytes:
    encoded = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
    return json.dumps(
        {"auths": {registry: {"auth": encoded}}},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _execution_profile_bytes() -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": "aileron-backend-execution-profile/v1",
                "executionNamespace": MODULE.NAMESPACE,
                "namespaceOwner": MODULE.NAMESPACE_OWNER,
                "imagePullSecret": MODULE.SECRET_NAME,
                "nfsMountRoots": [
                    {"server": "192.0.2.20", "path": "/volume1/okd"}
                ],
                "localPathNodes": [],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _expected_secret_data(dockerconfig: bytes) -> dict[str, str]:
    return {
        ".dockerconfigjson": base64.b64encode(dockerconfig).decode("ascii")
    }


def _namespace(
    *,
    owner: str = MODULE.NAMESPACE_OWNER,
    phase: str = "Active",
    uid: str = "namespace-uid",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": MODULE.NAMESPACE,
            "uid": uid,
            "resourceVersion": "17",
            "labels": {
                MODULE.NAMESPACE_OWNER_LABEL: owner,
                **(labels if labels is not None else MODULE.PSA_LABELS),
            },
        },
        "status": {"phase": phase},
    }


def _secret(
    dockerconfig: bytes,
    *,
    owner: str = MODULE.NAMESPACE_OWNER,
    uid: str = "secret-uid",
    data: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "namespace": MODULE.NAMESPACE,
            "name": MODULE.SECRET_NAME,
            "uid": uid,
            "resourceVersion": "23",
            "labels": {MODULE.SECRET_OWNER_LABEL: owner},
        },
        "type": "kubernetes.io/dockerconfigjson",
        "data": data if data is not None else _expected_secret_data(dockerconfig),
    }


class FakeRunner:
    def __init__(
        self,
        *,
        namespace: dict[str, Any] | None = None,
        secret: dict[str, Any] | None = None,
    ) -> None:
        self.namespace = copy.deepcopy(namespace)
        self.secret = copy.deepcopy(secret)
        self.calls: list[dict[str, Any]] = []
        self.namespace_gets = 0
        self.secret_gets = 0
        self.fail_secret_mutation = False
        self.replace_namespace_before_patch = False
        self.replace_secret_before_patch = False
        self.replace_namespace_on_get: int | None = None
        self.replace_secret_on_get: int | None = None

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "command": list(command),
                "environment": dict(environment or {}),
                "stdin": stdin,
            }
        )
        if command[0] != "kubectl":
            raise AssertionError(command)
        if "view" in command and "--flatten" in command:
            raw = Path(command[command.index("--kubeconfig") + 1])
            return raw.read_text(encoding="utf-8")
        if command[-2:] == ["config", "current-context"]:
            return CONTEXT
        if "get" in command and "namespace" in command:
            self.namespace_gets += 1
            if self.replace_namespace_on_get == self.namespace_gets:
                self.namespace = _namespace(uid="replacement-namespace-uid")
            return "" if self.namespace is None else json.dumps(self.namespace)
        if "get" in command and "secret" in command:
            self.secret_gets += 1
            if self.replace_secret_on_get == self.secret_gets:
                assert self.secret is not None
                self.secret = {
                    **copy.deepcopy(self.secret),
                    "metadata": {
                        **copy.deepcopy(self.secret["metadata"]),
                        "uid": "replacement-secret-uid",
                    },
                }
            return "" if self.secret is None else json.dumps(self.secret)
        if stdin is None:
            raise AssertionError(command)
        document = json.loads(stdin)
        dry_run = "--dry-run=server" in command
        if dry_run:
            return "{}"
        if "create" in command:
            if document.get("kind") == "Namespace":
                document["metadata"].update(
                    {"uid": "created-namespace-uid", "resourceVersion": "1"}
                )
                document["status"] = {"phase": "Active"}
                self.namespace = document
                return json.dumps(document)
            if document.get("kind") == "Secret":
                if self.fail_secret_mutation:
                    raise RuntimeError(
                        f"transport failed for {USERNAME}:{PASSWORD}"
                    )
                document["metadata"].update(
                    {"uid": "created-secret-uid", "resourceVersion": "1"}
                )
                self.secret = document
                return json.dumps(document)
            raise AssertionError(document)
        if "patch" in command:
            resource = command[command.index("patch") + 1]
            if resource == "namespace":
                if self.replace_namespace_before_patch:
                    self.namespace = _namespace(uid="replacement-namespace-uid")
                assert self.namespace is not None
                self._apply_patch_tests(self.namespace, document)
                self.namespace["metadata"]["labels"] = copy.deepcopy(
                    document[-1]["value"]
                )
                self.namespace["metadata"]["resourceVersion"] = "18"
                return json.dumps(self.namespace)
            if resource == "secret":
                if self.replace_secret_before_patch:
                    assert self.secret is not None
                    self.secret["metadata"]["uid"] = "replacement-secret-uid"
                assert self.secret is not None
                self._apply_patch_tests(self.secret, document)
                if self.fail_secret_mutation:
                    raise RuntimeError(
                        f"conflict contains {USERNAME}:{PASSWORD}"
                    )
                for operation in document[2:]:
                    key = operation["path"].removeprefix("/")
                    if key == "metadata/labels":
                        self.secret["metadata"]["labels"] = copy.deepcopy(
                            operation["value"]
                        )
                    else:
                        self.secret[key] = copy.deepcopy(operation["value"])
                self.secret["metadata"]["resourceVersion"] = "24"
                return json.dumps(self.secret)
        raise AssertionError(command)

    @staticmethod
    def _apply_patch_tests(
        current: dict[str, Any],
        patch: list[dict[str, Any]],
    ) -> None:
        expected = current["metadata"]
        if patch[:2] != [
            {"op": "test", "path": "/metadata/uid", "value": expected["uid"]},
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": expected["resourceVersion"],
            },
        ]:
            raise RuntimeError("Kubernetes JSON Patch conflict")

    def mutations(self, resource: str | None = None) -> list[dict[str, Any]]:
        result = [
            call
            for call in self.calls
            if "--dry-run=server" not in call["command"]
            and ("create" in call["command"] or "patch" in call["command"])
        ]
        if resource is None:
            return result
        filtered = []
        for call in result:
            document = json.loads(call["stdin"])
            kind = document.get("kind", "") if isinstance(document, dict) else ""
            if resource in call["command"] or kind.lower() == resource:
                filtered.append(call)
        return filtered


def _inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    dockerconfig: bytes | None = None,
) -> tuple[Path, Path, Path, bytes]:
    private_root = _directory(tmp_path / "private")
    content = dockerconfig if dockerconfig is not None else _dockerconfig_bytes()
    kubeconfig = _private(private_root / "inputs/kubeconfig", _kubeconfig_bytes())
    dockerconfig_path = _private(
        private_root / "inputs/harbor-dockerconfig.json",
        content,
    )
    _private(
        private_root / "inputs/backend-execution-profile.json",
        _execution_profile_bytes(),
    )
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)
    monkeypatch.setattr(
        MODULE.INSTALLATION_STATE,
        "BACKEND_ATTESTOR_PROFILE",
        private_root / "backend-attestor/execution-profile.json",
    )
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    return private_root, kubeconfig, dockerconfig_path, content


def _prepare(
    kubeconfig: Path,
    dockerconfig: Path,
    runner: FakeRunner,
    *,
    apply: bool = False,
    registry: str = REGISTRY,
) -> dict[str, Any]:
    return MODULE.prepare_backend_attestor(
        kubeconfig=kubeconfig,
        harbor_dockerconfig=dockerconfig,
        execution_profile=kubeconfig.parent / "backend-execution-profile.json",
        context=CONTEXT,
        registry=registry,
        apply=apply,
        runner=runner,
    )


def _relative_tree(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def _install_profile(private_root: Path) -> Path:
    return _private(
        private_root / "backend-attestor/execution-profile.json",
        _execution_profile_bytes(),
    )


def test_validate_missing_namespace_server_dry_runs_without_stable_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, dockerconfig, _ = _inputs(tmp_path, monkeypatch)
    before = _relative_tree(private_root)
    runner = FakeRunner()

    result = _prepare(kubeconfig, dockerconfig, runner)

    assert result == {
        "schemaVersion": MODULE.PREPARATION_RESULT_SCHEMA,
        "mode": "validate",
        "ready": False,
        "durablePrerequisiteRetained": False,
        "missingResources": [
            "executionProfile",
            "namespace",
            "imagePullSecret",
        ],
        "changedResources": [],
    }
    assert runner.mutations() == []
    dry_runs = [
        call for call in runner.calls if "--dry-run=server" in call["command"]
    ]
    assert len(dry_runs) == 1
    assert json.loads(dry_runs[0]["stdin"])["kind"] == "Namespace"
    assert _relative_tree(private_root) == before
    serialized_commands = json.dumps([call["command"] for call in runner.calls])
    assert str(kubeconfig) not in serialized_commands
    assert str(dockerconfig) not in serialized_commands
    assert USERNAME not in json.dumps(result)
    assert PASSWORD not in json.dumps(result)


def test_validate_ready_returns_digest_only_execution_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, dockerconfig_path, dockerconfig = _inputs(
        tmp_path,
        monkeypatch,
    )
    _install_profile(private_root)
    runner = FakeRunner(
        namespace=_namespace(),
        secret=_secret(dockerconfig),
    )

    result = _prepare(kubeconfig, dockerconfig_path, runner)

    assert result["schemaVersion"] == MODULE.EXECUTION_RESOURCES_SCHEMA
    assert result["namespace"] == {
        "name": MODULE.NAMESPACE,
        "uid": "namespace-uid",
        "owner": MODULE.NAMESPACE_OWNER,
        "phase": "Active",
        "podSecurityLabels": MODULE.PSA_LABELS,
    }
    assert result["imagePullSecret"] == {
        "namespace": MODULE.NAMESPACE,
        "name": MODULE.SECRET_NAME,
        "uid": "secret-uid",
        "owner": MODULE.NAMESPACE_OWNER,
        "dataKeys": [".dockerconfigjson"],
        "dataSha256": hashlib.sha256(
            MODULE._canonical(_expected_secret_data(dockerconfig))
        ).hexdigest(),
    }
    assert runner.mutations() == []
    assert USERNAME not in json.dumps(result)
    assert PASSWORD not in json.dumps(result)


def test_apply_creates_retained_namespace_before_secret_and_is_retry_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner()

    result = _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert result["schemaVersion"] == MODULE.EXECUTION_RESOURCES_SCHEMA
    assert runner.namespace is not None
    assert runner.namespace["metadata"]["labels"] == {
        MODULE.NAMESPACE_OWNER_LABEL: MODULE.NAMESPACE_OWNER,
        **MODULE.PSA_LABELS,
    }
    assert runner.secret is not None
    installed_profile = (
        MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE
    )
    assert installed_profile.read_bytes() == _execution_profile_bytes()
    assert installed_profile.stat().st_mode & 0o777 == 0o600
    operations = [
        (
            "dry-run" if "--dry-run=server" in call["command"] else "apply",
            json.loads(call["stdin"])["kind"],
        )
        for call in runner.calls
        if call["stdin"] is not None
    ]
    assert operations == [
        ("dry-run", "Namespace"),
        ("apply", "Namespace"),
        ("dry-run", "Secret"),
        ("apply", "Secret"),
    ]

    second = _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert second == result
    assert len(runner.mutations()) == 2


def test_execution_profile_input_must_be_canonical_before_cluster_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    profile_input = kubeconfig.parent / "backend-execution-profile.json"
    profile_input.write_text(
        json.dumps(json.loads(_execution_profile_bytes()), indent=2) + "\n",
        encoding="utf-8",
    )
    profile_input.chmod(0o600)
    runner = FakeRunner()

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "private-input"
    assert runner.mutations() == []
    assert len(runner.calls) == 1


def test_installed_execution_profile_is_write_once_and_must_match_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    changed = json.loads(_execution_profile_bytes())
    changed["nfsMountRoots"][0]["server"] = "192.0.2.21"
    changed_raw = (
        json.dumps(changed, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    installed = _private(
        private_root / "backend-attestor/execution-profile.json",
        changed_raw,
    )
    runner = FakeRunner()

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "private-input"
    assert installed.read_bytes() == changed_raw
    assert runner.mutations() == []


@pytest.mark.parametrize("invalid_state", ["wrong-owner", "terminating"])
def test_namespace_owner_and_active_state_fail_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_state: str,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    namespace = (
        _namespace(owner="other-controller")
        if invalid_state == "wrong-owner"
        else _namespace(phase="Terminating")
    )
    if invalid_state == "terminating":
        namespace["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    runner = FakeRunner(namespace=namespace, secret=_secret(dockerconfig))

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "resource-reconciliation"
    assert raised.value.result["namespaceCreated"] is False
    assert runner.mutations() == []


def test_owned_namespace_psa_drift_uses_uid_and_resource_version_patch_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    namespace = _namespace(
        labels={
            "pod-security.kubernetes.io/enforce": "restricted",
            "unrelated.example/label": "preserved",
        }
    )
    runner = FakeRunner(namespace=namespace, secret=_secret(dockerconfig))

    result = _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert result["namespace"]["uid"] == "namespace-uid"
    patch_calls = runner.mutations("namespace")
    assert len(patch_calls) == 1
    patch = json.loads(patch_calls[0]["stdin"])
    assert patch[:2] == [
        {"op": "test", "path": "/metadata/uid", "value": "namespace-uid"},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": "17",
        },
    ]
    assert runner.namespace["metadata"]["labels"] == {
        MODULE.NAMESPACE_OWNER_LABEL: MODULE.NAMESPACE_OWNER,
        "unrelated.example/label": "preserved",
        **MODULE.PSA_LABELS,
    }


def test_owned_secret_drift_uses_guarded_patch_and_digest_only_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner(
        namespace=_namespace(),
        secret=_secret(dockerconfig, data={"stale": "c3RhbGU="}),
    )

    result = _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    patch_calls = runner.mutations("secret")
    assert len(patch_calls) == 1
    patch = json.loads(patch_calls[0]["stdin"])
    assert patch[:2] == [
        {"op": "test", "path": "/metadata/uid", "value": "secret-uid"},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": "23",
        },
    ]
    assert result["imagePullSecret"]["dataSha256"] == hashlib.sha256(
        MODULE._canonical(_expected_secret_data(dockerconfig))
    ).hexdigest()
    assert USERNAME not in json.dumps(result)
    assert PASSWORD not in json.dumps(result)


def test_secret_wrong_owner_fails_closed_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner(
        namespace=_namespace(),
        secret=_secret(dockerconfig, owner="unknown-controller"),
    )

    with pytest.raises(MODULE.BackendAttestorPreparationError):
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert runner.mutations() == []


def test_secret_failure_after_namespace_create_keeps_durable_prerequisite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner()
    runner.fail_secret_mutation = True

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result == {
        "schemaVersion": MODULE.PREPARATION_RESULT_SCHEMA,
        "mode": "apply",
        "ready": False,
        "failureStage": "resource-reconciliation",
        "namespaceCreated": True,
        "durablePrerequisiteRetained": True,
    }
    assert runner.namespace is not None
    assert runner.secret is None
    assert all("delete" not in call["command"] for call in runner.calls)
    serialized = json.dumps(raised.value.result)
    assert USERNAME not in serialized
    assert PASSWORD not in serialized


def test_namespace_create_requery_rejects_uid_replacement_before_secret_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner()
    runner.replace_namespace_on_get = 2

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["durablePrerequisiteRetained"] is True
    assert runner.secret is None
    assert runner.mutations("secret") == []


def test_existing_namespace_replacement_before_secret_request_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner(
        namespace=_namespace(),
        secret=_secret(dockerconfig, data={"stale": "c3RhbGU="}),
    )
    runner.replace_namespace_on_get = 2

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "resource-reconciliation"
    assert [
        call
        for call in runner.calls
        if call["stdin"] is not None
        and json.loads(call["stdin"]).get("kind") == "Secret"
    ] == []
    assert runner.mutations("secret") == []


def test_namespace_patch_uid_conflict_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner(
        namespace=_namespace(
            labels={"pod-security.kubernetes.io/enforce": "restricted"}
        ),
        secret=_secret(dockerconfig),
    )
    runner.replace_namespace_before_patch = True

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["namespaceCreated"] is False
    assert runner.mutations("secret") == []


def test_final_secret_requery_rejects_aba_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kubeconfig, dockerconfig_path, dockerconfig = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner(namespace=_namespace(), secret=_secret(dockerconfig))
    runner.replace_secret_on_get = 2

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "resource-reconciliation"
    assert runner.mutations() == []


@pytest.mark.parametrize(
    "registry",
    [
        "https://harbor.rke.soez.tw",
        "Harbor.rke.soez.tw",
        "harbor..rke.soez.tw",
        "harbor.rke.soez.tw.",
        "harbor.rke.soez.tw:0443",
        "harbor.rke.soez.tw:65536",
    ],
)
def test_registry_must_be_exact_canonical_host_before_private_or_cluster_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    registry: str,
) -> None:
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    runner = FakeRunner()

    with pytest.raises(ValueError):
        _prepare(
            kubeconfig,
            dockerconfig_path,
            runner,
            apply=True,
            registry=registry,
        )

    assert runner.calls == []


def test_dockerconfig_requires_only_the_exact_registry_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = json.dumps(
        {
            "auths": {
                REGISTRY: {
                    "auth": base64.b64encode(
                        f"{USERNAME}:{PASSWORD}".encode()
                    ).decode()
                },
                "other.registry.example": {"auth": "b3RoZXI6cHJpdmF0ZQ=="},
            }
        }
    ).encode()
    _, kubeconfig, dockerconfig_path, _ = _inputs(
        tmp_path,
        monkeypatch,
        dockerconfig=invalid,
    )
    runner = FakeRunner()

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "private-input"
    assert runner.calls[0]["command"][-6:] == [
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]
    assert len(runner.calls) == 1
    serialized = json.dumps(raised.value.result)
    assert USERNAME not in serialized
    assert PASSWORD not in serialized


def test_private_input_wrong_owner_is_rejected_before_cluster_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    _, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    os.chown(dockerconfig_path, 65532, 65532)
    runner = FakeRunner()

    with pytest.raises(MODULE.BackendAttestorPreparationError) as raised:
        _prepare(kubeconfig, dockerconfig_path, runner, apply=True)

    assert raised.value.result["failureStage"] == "private-input"
    assert runner.mutations() == []


def test_cross_process_private_root_lock_has_no_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root, kubeconfig, dockerconfig_path, _ = _inputs(tmp_path, monkeypatch)
    before = _relative_tree(private_root)
    script = """
import importlib.util
import json
import pathlib
import sys

spec = importlib.util.spec_from_file_location("prepare_backend_child", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
root = pathlib.Path(sys.argv[2])
module.INSTALLATION_STATE.PRIVATE_ROOT = root
module.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE = (
    root / "backend-attestor/execution-profile.json"
)
module.PRIVATE_INPUT.INSTALLATION_STATE.PRIVATE_ROOT = root
try:
    module.prepare_backend_attestor(
        kubeconfig=root / "inputs/kubeconfig",
        harbor_dockerconfig=root / "inputs/harbor-dockerconfig.json",
        execution_profile=root / "inputs/backend-execution-profile.json",
        context="rke",
        registry="harbor.rke.soez.tw",
        apply=True,
    )
except module.BackendAttestorPreparationError as error:
    print(json.dumps(error.result, sort_keys=True))
    raise SystemExit(0)
raise SystemExit(2)
"""
    with MODULE._installation_lock(private_root, mode="apply"):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(MODULE_PATH), str(private_root)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["failureStage"] == "installation-lock-contention"
    assert result["mode"] == "apply"
    assert _relative_tree(private_root) == before
    assert kubeconfig.exists()
    assert dockerconfig_path.exists()


def test_default_kubectl_runner_has_bounded_subprocess_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def completed(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        captured.update(options)
        return subprocess.CompletedProcess(command, 0, stdout="ready", stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", completed)

    assert MODULE._run_command(["kubectl", "version"]) == "ready"
    assert captured["timeout"] == MODULE.KUBECTL_TIMEOUT_SECONDS


def test_default_kubectl_runner_reports_timeout_without_command_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        del options
        raise subprocess.TimeoutExpired(command, MODULE.KUBECTL_TIMEOUT_SECONDS)

    monkeypatch.setattr(MODULE.subprocess, "run", timeout)

    with pytest.raises(MODULE._CommandError) as raised:
        MODULE._run_command(["kubectl", "private-value"])

    assert str(raised.value) == "Kubernetes command timed out"
    assert "private-value" not in str(raised.value)


def test_default_cli_validate_returns_exit_78_for_missing_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = MODULE._required_result(
        missing=["executionProfile", "namespace", "imagePullSecret"],
        changed=[],
    )
    monkeypatch.setattr(
        MODULE,
        "prepare_backend_attestor",
        lambda **kwargs: expected,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(MODULE_PATH),
            "--kubeconfig",
            "/private/kubeconfig",
            "--harbor-dockerconfig",
            "/private/dockerconfig.json",
            "--execution-profile",
            "/private/backend-execution-profile.json",
            "--context",
            CONTEXT,
            "--registry",
            REGISTRY,
        ],
    )

    assert MODULE.main() == 78
    assert json.loads(capsys.readouterr().out) == expected


def test_execution_profile_has_one_fixed_private_source_path() -> None:
    assert MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE == (
        MODULE.INSTALLATION_STATE.PRIVATE_ROOT
        / "backend-attestor/execution-profile.json"
    )
