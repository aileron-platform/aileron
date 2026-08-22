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
    / "ensure_installation_namespaces.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ensure_installation_namespaces", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REAL_SNAPSHOT_SELF_CONTAINED_KUBECONFIG = (
    MODULE.PRIVATE_INPUT.snapshot_self_contained_kubeconfig
)
CONTEXT = "rke2-homelab"
SOURCE_KUBECONFIG = Path("/private/rke2-homelab.source.kubeconfig")
KUBECONFIG = Path("/private/rke2-homelab.flattened.kubeconfig")
NAMESPACE_OWNER_LABEL = MODULE.NAMESPACE_CONTRACT.NAMESPACE_OWNER_LABEL
NAMESPACE_OWNER = MODULE.NAMESPACE_CONTRACT.NAMESPACE_OWNER


def _profile_labels(namespace: str) -> dict[str, str]:
    return MODULE.NAMESPACE_CONTRACT.profile_labels(namespace)


@pytest.fixture(autouse=True)
def _immutable_kubeconfig_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)

    def snapshot_self_contained_kubeconfig(**arguments: object) -> Path:
        assert arguments["source"] == SOURCE_KUBECONFIG
        assert arguments["context"] == CONTEXT
        assert arguments["private_root"] == private_root
        raw_destination = arguments["raw_destination"]
        flattened_destination = arguments["flattened_destination"]
        assert isinstance(raw_destination, Path)
        assert isinstance(flattened_destination, Path)
        assert raw_destination.parent == flattened_destination.parent
        assert raw_destination.parent.parent == private_root
        return KUBECONFIG

    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        snapshot_self_contained_kubeconfig,
    )


def _kubectl(*arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(KUBECONFIG),
        "--context",
        CONTEXT,
        *arguments,
    ]


def _build_namespace_installation_plan(
    namespace_document: dict, **arguments: object
) -> list:
    return MODULE.build_namespace_installation_plan(
        namespace_document,
        kubeconfig=KUBECONFIG,
        **arguments,
    )


def _ensure_installation_namespaces(**arguments: object) -> dict:
    return MODULE.ensure_installation_namespaces(
        kubeconfig=SOURCE_KUBECONFIG,
        **arguments,
    )


def _namespace(
    name: str,
    owner: str = "aileron-installer",
    *,
    uid: str | None = None,
    resource_version: str = "17",
) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": name,
            "uid": uid or f"uid-{name}",
            "resourceVersion": resource_version,
            "labels": {NAMESPACE_OWNER_LABEL: owner},
        },
        "status": {"phase": "Active"},
    }


def _real_kubeconfig(path: Path, *, token: str = "original-token") -> Path:
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.parent.chmod(0o700)
    path.write_text(
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": CONTEXT,
                "clusters": [
                    {
                        "name": "cluster",
                        "cluster": {
                            "server": "https://192.0.2.10:6443",
                            "certificate-authority-data": "Y2E=",
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": CONTEXT,
                        "context": {"cluster": "cluster", "user": "user"},
                    }
                ],
                "users": [{"name": "user", "user": {"token": token}}],
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _exact_external_namespaces() -> list[dict]:
    namespaces = []
    for namespace in MODULE.CORE_NAMESPACE_NAMES:
        item = _namespace(namespace)
        item["metadata"]["labels"] = _profile_labels(namespace)
        namespaces.append(item)
    return namespaces


def test_real_snapshot_retargets_every_command_to_one_flattened_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "real-private"
    private_root.mkdir(mode=0o700)
    source = _real_kubeconfig(private_root / "inputs" / "kubeconfig")
    replacement = _real_kubeconfig(
        private_root / "inputs" / "replacement", token="replacement-token"
    ).read_bytes()
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        REAL_SNAPSHOT_SELF_CONTAINED_KUBECONFIG,
    )
    commands: list[list[str]] = []
    flattened_paths: list[Path] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        assert stdin is None
        commands.append(command)
        kubeconfig = Path(command[command.index("--kubeconfig") + 1])
        if command[-6:] == [
            "config",
            "view",
            "--raw",
            "--flatten",
            "--minify",
            "--output=json",
        ]:
            raw = kubeconfig.read_text(encoding="utf-8")
            source.write_bytes(replacement)
            source.chmod(0o600)
            return raw
        flattened_paths.append(kubeconfig)
        if command[-2:] == ["config", "current-context"]:
            return f"{CONTEXT}\n"
        if command[-4:] == ["get", "namespaces", "-o", "json"]:
            return json.dumps({"items": _exact_external_namespaces()})
        raise AssertionError(f"unexpected command: {command}")

    result = MODULE.ensure_installation_namespaces(
        kubeconfig=source,
        expected_context=CONTEXT,
        identity_mode="externalOidc",
        validate_only=True,
        runner=runner,
    )

    assert result["ready"] is True
    assert source.read_bytes() == replacement
    assert len(set(flattened_paths)) == 1
    assert flattened_paths[0].name == "kubeconfig.flattened.json"
    assert flattened_paths[0] != source
    assert not flattened_paths[0].exists()
    assert not any(
        path.name.startswith(".ensure-installation-namespaces-")
        for path in private_root.iterdir()
    )


def test_real_snapshot_rejects_flattened_identity_drift_before_cluster_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "drift-private"
    private_root.mkdir(mode=0o700)
    source = _real_kubeconfig(private_root / "inputs" / "kubeconfig")
    drift = _real_kubeconfig(
        private_root / "inputs" / "drift", token="different-token"
    ).read_text(encoding="utf-8")
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        REAL_SNAPSHOT_SELF_CONTAINED_KUBECONFIG,
    )
    commands: list[list[str]] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        assert stdin is None
        commands.append(command)
        if command[-6:] == [
            "config",
            "view",
            "--raw",
            "--flatten",
            "--minify",
            "--output=json",
        ]:
            return drift
        raise AssertionError("cluster access must not occur after identity drift")

    with pytest.raises(ValueError, match="selected identity changed"):
        MODULE.ensure_installation_namespaces(
            kubeconfig=source,
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
            runner=runner,
        )

    assert len(commands) == 1
    assert not any(
        path.name.startswith(".ensure-installation-namespaces-")
        for path in private_root.iterdir()
    )


def test_real_snapshot_rejects_hard_linked_source_before_kubectl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "hardlink-private"
    private_root.mkdir(mode=0o700)
    source = _real_kubeconfig(private_root / "inputs" / "kubeconfig")
    os.link(source, source.with_name("kubeconfig-link"))
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", private_root)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        REAL_SNAPSHOT_SELF_CONTAINED_KUBECONFIG,
    )
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="owner-controlled mode-0600"):
        MODULE.ensure_installation_namespaces(
            kubeconfig=source,
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
            runner=lambda command, _stdin=None: commands.append(command) or "",
        )

    assert commands == []


def test_namespace_plan_requires_an_absolute_kubeconfig() -> None:
    with pytest.raises(ValueError, match="absolute Kubernetes kubeconfig"):
        MODULE.build_namespace_installation_plan(
            {"items": []},
            kubeconfig=Path("relative-kubeconfig"),
            expected_context=CONTEXT,
            identity_mode="externalOidc",
        )


def test_bundled_keycloak_installer_creates_all_owned_namespaces() -> None:
    operations = _build_namespace_installation_plan(
        {"items": []},
        expected_context=CONTEXT,
        identity_mode="bundledKeycloak",
    )

    validation = [
        operation for operation in operations if "--dry-run=server" in operation.command
    ]
    mutations = [
        operation
        for operation in operations
        if "--dry-run=server" not in operation.command
    ]
    created = [
        json.loads(operation.manifest)["metadata"]["name"]
        for operation in mutations
    ]
    assert created == [
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
        "aileron-identity-system",
    ]
    assert len(validation) == len(mutations) == 4
    assert operations == [*validation, *mutations]
    for operation in operations:
        assert operation.command[:6] == _kubectl("create")
        manifest = json.loads(operation.manifest)
        assert (
            manifest["metadata"]["labels"][NAMESPACE_OWNER_LABEL]
            == NAMESPACE_OWNER
        )
    workspace = json.loads(mutations[0].manifest)
    assert workspace["metadata"]["labels"] == {
        NAMESPACE_OWNER_LABEL: NAMESPACE_OWNER,
        "pod-security.kubernetes.io/enforce": "privileged",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
    backend = json.loads(mutations[2].manifest)
    assert backend["metadata"]["labels"] == workspace["metadata"]["labels"]


def test_external_oidc_installer_does_not_create_identity_namespace() -> None:
    operations = _build_namespace_installation_plan(
        {"items": []}, expected_context=CONTEXT, identity_mode="externalOidc"
    )

    manifests = [
        json.loads(operation.manifest)
        for operation in operations
        if operation.manifest is not None
    ]
    assert {
        manifest["metadata"]["name"] for manifest in manifests
    } == {
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    }


def test_validate_requires_the_retained_backend_attestor_namespace() -> None:
    existing = []
    for namespace in MODULE.CORE_NAMESPACE_NAMES[:2]:
        item = _namespace(namespace)
        item["metadata"]["labels"] = _profile_labels(namespace)
        existing.append(item)

    operations = _build_namespace_installation_plan(
        {"items": existing},
        expected_context=CONTEXT,
        identity_mode="externalOidc",
        validate_only=True,
    )

    assert len(operations) == 1
    assert json.loads(operations[0].manifest)["metadata"] == {
        "name": "aileron-backend-attestor-system",
        "labels": _profile_labels("aileron-backend-attestor-system"),
    }


def test_backend_attestor_namespace_must_be_active_and_not_terminating() -> None:
    backend = _namespace("aileron-backend-attestor-system")
    backend["metadata"]["labels"] = _profile_labels(
        "aileron-backend-attestor-system"
    )
    backend["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    backend["status"]["phase"] = "Terminating"

    with pytest.raises(
        ValueError,
        match="exactly Active: aileron-backend-attestor-system",
    ):
        _build_namespace_installation_plan(
            {"items": [backend]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
        )


def test_backend_attestor_namespace_owner_or_psa_drift_fails_closed() -> None:
    backend = _namespace("aileron-backend-attestor-system")
    backend["metadata"]["labels"] = _profile_labels(
        "aileron-backend-attestor-system"
    )
    backend["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] = (
        "baseline"
    )

    with pytest.raises(ValueError, match="namespace profile mismatch"):
        _build_namespace_installation_plan(
            {"items": [backend]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
        )


def test_existing_only_converges_present_targets_without_creating_missing_ones() -> (
    None
):
    operations = _build_namespace_installation_plan(
        {"items": [_namespace("workspace-system")]},
        expected_context=CONTEXT,
        identity_mode="bundledKeycloak",
        existing_only=True,
    )

    assert len(operations) == 2
    assert operations[0].command[:8] == _kubectl(
        "patch", "namespace", "workspace-system"
    )
    assert "--dry-run=server" in operations[0].command
    assert operations[1].command[:8] == _kubectl(
        "patch", "namespace", "workspace-system"
    )
    assert "--dry-run=server" not in operations[1].command
    patch = json.loads(operations[1].manifest)
    assert patch[:2] == [
        {"op": "test", "path": "/metadata/uid", "value": "uid-workspace-system"},
        {"op": "test", "path": "/metadata/resourceVersion", "value": "17"},
    ]
    assert patch[2]["op"] == "replace"
    assert patch[2]["value"] == _profile_labels("workspace-system")
    assert not any(
        operation.command[:7] == _kubectl("create", "namespace")
        for operation in operations
    )


def test_existing_namespace_patch_removes_unmanaged_psa_labels() -> None:
    workspace = _namespace("workspace-system")
    workspace["metadata"]["labels"].update(
        {
            "application.example/retained": "true",
            "pod-security.kubernetes.io/enforce": "privileged",
            "pod-security.kubernetes.io/audit": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
            "pod-security.kubernetes.io/enforce-version": "latest",
        }
    )

    operations = _build_namespace_installation_plan(
        {"items": [workspace]},
        expected_context=CONTEXT,
        identity_mode="externalOidc",
        existing_only=True,
    )

    assert len(operations) == 2
    patch = json.loads(operations[1].manifest)
    assert patch[2]["value"] == {
        NAMESPACE_OWNER_LABEL: NAMESPACE_OWNER,
        "application.example/retained": "true",
        "pod-security.kubernetes.io/enforce": "privileged",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }


def test_validate_only_rejects_unmanaged_psa_labels() -> None:
    workspace = _namespace("workspace-system")
    workspace["metadata"]["labels"].update(
        {
            **_profile_labels("workspace-system"),
            "pod-security.kubernetes.io/enforce-version": "latest",
        }
    )

    with pytest.raises(ValueError, match="namespace profile mismatch"):
        _build_namespace_installation_plan(
            {"items": [workspace]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
        )


def test_prepare_result_records_removal_of_unmanaged_psa_label_as_change() -> None:
    initial_documents = _exact_external_namespaces()
    initial_documents[0]["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce-version"
    ] = "latest"
    verified_documents = _exact_external_namespaces()

    result = MODULE._namespace_result(
        identity_mode="externalOidc",
        validate_only=False,
        initial_inventory=MODULE.NAMESPACE_CONTRACT.namespace_inventory(
            {"items": initial_documents}
        ),
        verified_inventory=MODULE.NAMESPACE_CONTRACT.namespace_inventory(
            {"items": verified_documents}
        ),
    )

    assert result["changedNamespaces"] == ["workspace-system"]


def test_existing_only_verifies_only_the_original_present_subset() -> None:
    namespace = _namespace("workspace-system")
    calls: list[list[str]] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        calls.append(command)
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps({"items": [namespace]})
        if command[:8] == _kubectl("patch", "namespace", "workspace-system"):
            assert stdin is not None
            patch = json.loads(stdin)
            assert patch[0]["value"] == namespace["metadata"]["uid"]
            assert patch[1]["value"] == namespace["metadata"]["resourceVersion"]
            if "--dry-run=server" in command:
                return ""
            namespace["metadata"]["labels"] = patch[2]["value"]
            namespace["metadata"]["resourceVersion"] = "18"
            return json.dumps(namespace)
        raise AssertionError(f"unexpected command: {command}")

    _ensure_installation_namespaces(
        expected_context=CONTEXT,
        identity_mode="bundledKeycloak",
        existing_only=True,
        runner=runner,
    )

    assert namespace["metadata"]["labels"][
        "pod-security.kubernetes.io/enforce"
    ] == "privileged"
    assert not any(command[:7] == _kubectl("create", "namespace") for command in calls)


def test_existing_patch_rejects_same_name_replacement_after_server_dry_run() -> None:
    live = _namespace("workspace-system", uid="original-uid")
    replacement: dict | None = None

    def runner(command: list[str], stdin: str | None = None) -> str:
        nonlocal live, replacement
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps({"items": [live]})
        if command[:8] == _kubectl("patch", "namespace", "workspace-system"):
            assert stdin is not None
            patch = json.loads(stdin)
            if "--dry-run=server" in command:
                assert patch[0]["value"] == "original-uid"
                assert patch[1]["value"] == "17"
                return ""
            replacement = _namespace(
                "workspace-system",
                uid="replacement-uid",
                resource_version="29",
            )
            live = replacement
            if (
                patch[0]["value"] != live["metadata"]["uid"]
                or patch[1]["value"] != live["metadata"]["resourceVersion"]
            ):
                raise RuntimeError("JSON Patch test operation failed")
            raise AssertionError("replacement namespace must not be patched")
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(RuntimeError, match="JSON Patch test operation failed"):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="bundledKeycloak",
            existing_only=True,
            runner=runner,
        )

    assert replacement is not None
    assert replacement["metadata"]["labels"] == {
        NAMESPACE_OWNER_LABEL: NAMESPACE_OWNER
    }


def test_installer_fails_closed_instead_of_adopting_namespace() -> None:
    with pytest.raises(ValueError, match="Namespace owner is invalid"):
        _build_namespace_installation_plan(
            {"items": [_namespace("workspace-system", owner="shared-owner")]},
            expected_context=CONTEXT,
            identity_mode="bundledKeycloak",
        )


def test_external_oidc_rejects_stale_identity_namespace() -> None:
    with pytest.raises(ValueError, match="must be absent"):
        _build_namespace_installation_plan(
            {"items": [_namespace("aileron-identity-system")]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
        )


def test_external_oidc_rejects_terminating_stale_identity_namespace() -> None:
    identity = _namespace("aileron-identity-system")
    identity["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    identity["status"]["phase"] = "Terminating"

    with pytest.raises(ValueError, match="must be absent"):
        _build_namespace_installation_plan(
            {"items": [identity]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
        )


@pytest.mark.parametrize(
    "appeared_namespace",
    ["aileron-turn-system", "aileron-identity-system"],
)
def test_namespace_appearing_after_dry_run_is_rejected_before_mutation(
    appeared_namespace: str,
) -> None:
    workspace = _namespace("workspace-system")
    inventory_reads = 0
    persistent_mutations = 0

    def runner(command: list[str], stdin: str | None = None) -> str:
        nonlocal inventory_reads, persistent_mutations
        if command == _kubectl("config", "current-context"):
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            inventory_reads += 1
            items = [workspace]
            if inventory_reads > 1:
                items.append(_namespace(appeared_namespace))
            return json.dumps({"items": items})
        if command[:8] == _kubectl("patch", "namespace", "workspace-system"):
            assert stdin is not None
            if "--dry-run=server" in command:
                return ""
            persistent_mutations += 1
            raise AssertionError("drift must be rejected before mutation")
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(ValueError, match="namespace inventory changed before mutation"):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            existing_only=True,
            runner=runner,
        )

    assert persistent_mutations == 0


@pytest.mark.parametrize("validate_only", [False, True])
def test_target_namespace_must_be_exactly_active(validate_only: bool) -> None:
    workspace = _namespace("workspace-system")
    workspace["metadata"]["labels"] = _profile_labels("workspace-system")
    workspace["metadata"]["deletionTimestamp"] = "2026-08-10T00:00:00Z"
    workspace["status"]["phase"] = "Terminating"

    with pytest.raises(ValueError, match="exactly Active: workspace-system"):
        _build_namespace_installation_plan(
            {"items": [workspace]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=validate_only,
        )


def test_installer_verifies_owner_labels_after_creation() -> None:
    namespaces: dict[str, dict] = {}
    commands: list[list[str]] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        commands.append(command)
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return "rke2-homelab\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps(
                {
                    "items": [
                        namespace for namespace in namespaces.values()
                    ]
                }
            )
        if command[:6] == _kubectl("create") and "--filename=-" in command:
            assert stdin is not None
            manifest = json.loads(stdin)
            if "--dry-run=server" in command:
                return ""
            name = manifest["metadata"]["name"]
            manifest["metadata"].update(
                {"uid": f"uid-{name}", "resourceVersion": "1"}
            )
            manifest["status"] = {"phase": "Active"}
            namespaces[name] = manifest
            return json.dumps(manifest)
        raise AssertionError(f"unexpected command: {command}")

    _ensure_installation_namespaces(
        expected_context="rke2-homelab",
        identity_mode="externalOidc",
        runner=runner,
    )

    assert set(namespaces) == {
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    }
    assert commands[-1] == _kubectl("get", "namespaces", "-o", "json")
    assert all(
        command[1:5]
        == ["--kubeconfig", str(KUBECONFIG), "--context", CONTEXT]
        for command in commands
    )
    create_commands = [
        command
        for command in commands
        if command[:6] == _kubectl("create") and "--filename=-" in command
    ]
    assert len(create_commands) == 6
    assert all("--dry-run=server" in command for command in create_commands[:3])
    assert all("--dry-run=server" not in command for command in create_commands[3:])


def test_exact_existing_namespaces_are_noop_and_only_reverified() -> None:
    namespaces = {
        namespace: _namespace(namespace)
        for namespace in MODULE.CORE_NAMESPACE_NAMES
    }
    for namespace in MODULE.CORE_NAMESPACE_NAMES:
        namespaces[namespace]["metadata"]["labels"] = _profile_labels(namespace)
    calls: list[list[str]] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        assert stdin is None
        calls.append(command)
        if command == _kubectl("config", "current-context"):
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            return json.dumps(
                {
                    "items": [
                        namespace for namespace in namespaces.values()
                    ]
                }
            )
        raise AssertionError(f"unexpected command: {command}")

    result = _ensure_installation_namespaces(
        expected_context=CONTEXT,
        identity_mode="externalOidc",
        runner=runner,
    )

    assert calls == [
        _kubectl("config", "current-context"),
        _kubectl("get", "namespaces", "-o", "json"),
        _kubectl("get", "namespaces", "-o", "json"),
    ]
    assert result == {
        "schemaVersion": MODULE.NAMESPACE_RESULT_SCHEMA,
        "mode": "prepare",
        "ready": True,
        "targetNamespaces": [
            "workspace-system",
            "aileron-turn-system",
            "aileron-backend-attestor-system",
        ],
        "targetNamespaceIdentities": [
            {"name": "workspace-system", "uid": "uid-workspace-system"},
            {"name": "aileron-turn-system", "uid": "uid-aileron-turn-system"},
            {
                "name": "aileron-backend-attestor-system",
                "uid": "uid-aileron-backend-attestor-system",
            },
        ],
        "initiallyMissingNamespaces": [],
        "changedNamespaces": [],
    }


def test_signal_after_first_create_preserves_the_safe_namespace() -> None:
    namespaces: dict[str, dict] = {}
    persistent_creates = 0

    def runner(command: list[str], stdin: str | None = None) -> str:
        nonlocal persistent_creates
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps(
                {
                    "items": [
                        namespace for namespace in namespaces.values()
                    ]
                }
            )
        if command[:6] == _kubectl("create") and "--filename=-" in command:
            assert stdin is not None
            if "--dry-run=server" in command:
                return ""
            persistent_creates += 1
            if persistent_creates == 2:
                raise KeyboardInterrupt
            manifest = json.loads(stdin)
            name = manifest["metadata"]["name"]
            manifest["metadata"].update(
                {"uid": f"uid-{name}", "resourceVersion": "1"}
            )
            manifest["status"] = {"phase": "Active"}
            namespaces[name] = manifest
            return json.dumps(manifest)
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(KeyboardInterrupt):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )

    assert set(namespaces) == {"workspace-system"}
    assert namespaces["workspace-system"]["metadata"][
        "labels"
    ] == _profile_labels("workspace-system")


def test_namespace_reverification_rejects_post_create_profile_drift() -> None:
    namespaces: dict[str, dict] = {}

    def runner(command: list[str], stdin: str | None = None) -> str:
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps(
                {
                    "items": [
                        namespace for namespace in namespaces.values()
                    ]
                }
            )
        if command[:6] == _kubectl("create") and "--filename=-" in command:
            assert stdin is not None
            if "--dry-run=server" in command:
                return ""
            manifest = json.loads(stdin)
            labels = dict(manifest["metadata"]["labels"])
            name = manifest["metadata"]["name"]
            if name == "workspace-system":
                labels["pod-security.kubernetes.io/enforce"] = "baseline"
            manifest["metadata"].update(
                {"uid": f"uid-{name}", "resourceVersion": "1", "labels": labels}
            )
            manifest["status"] = {"phase": "Active"}
            namespaces[name] = manifest
            return json.dumps(manifest)
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(ValueError, match="Namespace profile is invalid"):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )


def test_namespace_reverification_rejects_namespace_that_started_terminating() -> (
    None
):
    namespaces: dict[str, dict] = {}
    inventory_reads = 0

    def runner(command: list[str], stdin: str | None = None) -> str:
        nonlocal inventory_reads
        if command == _kubectl("config", "current-context"):
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            inventory_reads += 1
            result = json.loads(json.dumps(list(namespaces.values())))
            if inventory_reads > 2:
                workspace = next(
                    item
                    for item in result
                    if item["metadata"]["name"] == "workspace-system"
                )
                workspace["metadata"]["deletionTimestamp"] = (
                    "2026-08-10T00:00:00Z"
                )
                workspace["status"]["phase"] = "Terminating"
            return json.dumps({"items": result})
        if command[:6] == _kubectl("create") and "--filename=-" in command:
            assert stdin is not None
            if "--dry-run=server" in command:
                return ""
            manifest = json.loads(stdin)
            name = manifest["metadata"]["name"]
            manifest["metadata"].update(
                {"uid": f"uid-{name}", "resourceVersion": "1"}
            )
            manifest["status"] = {"phase": "Active"}
            namespaces[name] = manifest
            return json.dumps(manifest)
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(ValueError, match="exactly Active: workspace-system"):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )


def test_namespace_reverification_rejects_post_create_uid_replacement() -> None:
    namespaces: dict[str, dict] = {}
    persistent_creates = 0

    def runner(command: list[str], stdin: str | None = None) -> str:
        nonlocal persistent_creates
        if command == _kubectl("config", "current-context"):
            assert stdin is None
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            assert stdin is None
            return json.dumps({"items": list(namespaces.values())})
        if command[:6] == _kubectl("create") and "--filename=-" in command:
            assert stdin is not None
            if "--dry-run=server" in command:
                return ""
            persistent_creates += 1
            manifest = json.loads(stdin)
            name = manifest["metadata"]["name"]
            original = json.loads(json.dumps(manifest))
            original["metadata"].update(
                {"uid": f"uid-{name}", "resourceVersion": "1"}
            )
            original["status"] = {"phase": "Active"}
            namespaces[name] = original
            if persistent_creates == 2:
                replacement = json.loads(json.dumps(original))
                replacement["metadata"].update(
                    {"uid": f"replacement-{name}", "resourceVersion": "2"}
                )
                namespaces[name] = replacement
            return json.dumps(original)
        raise AssertionError(f"unexpected command: {command}")

    with pytest.raises(ValueError, match="identity verification failed"):
        _ensure_installation_namespaces(
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            runner=runner,
        )


def test_validate_only_server_dry_runs_only_missing_allowlisted_namespaces() -> None:
    workspace = _namespace("workspace-system")
    workspace["metadata"]["labels"].update(
        {
            "pod-security.kubernetes.io/enforce": "privileged",
            "pod-security.kubernetes.io/audit": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
        }
    )
    turn = _namespace("aileron-turn-system")
    turn["metadata"]["labels"].update(
        {
            "pod-security.kubernetes.io/enforce": "privileged",
            "pod-security.kubernetes.io/audit": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
        }
    )
    backend = _namespace("aileron-backend-attestor-system")
    backend["metadata"]["labels"].update(
        {
            "pod-security.kubernetes.io/enforce": "privileged",
            "pod-security.kubernetes.io/audit": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
        }
    )
    document = {"items": [workspace, turn, backend]}

    operations = _build_namespace_installation_plan(
        document,
        expected_context=CONTEXT,
        identity_mode="bundledKeycloak",
        validate_only=True,
    )

    assert len(operations) == 1
    operation = operations[0]
    assert operation.command == _kubectl(
        "create", "--dry-run=server", "--output=name", "--filename=-"
    )
    assert json.loads(operation.manifest) == {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "aileron-identity-system",
            "labels": {
                NAMESPACE_OWNER_LABEL: NAMESPACE_OWNER,
                "pod-security.kubernetes.io/enforce": "restricted",
                "pod-security.kubernetes.io/audit": "restricted",
                "pod-security.kubernetes.io/warn": "restricted",
            },
        },
    }


@pytest.mark.parametrize(
    ("label", "value"),
    [
        (NAMESPACE_OWNER_LABEL, "shared-owner"),
        ("pod-security.kubernetes.io/enforce", "baseline"),
        ("pod-security.kubernetes.io/audit", "baseline"),
        ("pod-security.kubernetes.io/warn", "baseline"),
    ],
)
def test_validate_only_rejects_existing_namespace_owner_or_profile_drift(
    label: str, value: str
) -> None:
    namespace = _namespace("workspace-system")
    namespace["metadata"]["labels"].update(
        {
            "pod-security.kubernetes.io/enforce": "privileged",
            "pod-security.kubernetes.io/audit": "restricted",
            "pod-security.kubernetes.io/warn": "restricted",
            label: value,
        }
    )

    with pytest.raises(
        ValueError,
        match="(Namespace owner is invalid|namespace profile mismatch)",
    ):
        _build_namespace_installation_plan(
            {"items": [namespace]},
            expected_context=CONTEXT,
            identity_mode="externalOidc",
            validate_only=True,
        )


def test_validate_only_executes_server_dry_run_without_persistent_mutation() -> None:
    calls: list[tuple[list[str], str | None]] = []

    def runner(command: list[str], stdin: str | None = None) -> str:
        calls.append((command, stdin))
        if command == _kubectl("config", "current-context"):
            return f"{CONTEXT}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            return '{"items":[]}'
        if "--dry-run=server" in command and stdin is not None:
            return "namespace accepted (server dry run)"
        raise AssertionError(f"unexpected command: {command}")

    _ensure_installation_namespaces(
        expected_context=CONTEXT,
        identity_mode="externalOidc",
        validate_only=True,
        runner=runner,
    )

    dry_runs = [(command, stdin) for command, stdin in calls if stdin is not None]
    assert len(dry_runs) == 3
    assert all("--dry-run=server" in command for command, _ in dry_runs)
    assert {json.loads(stdin)["metadata"]["name"] for _, stdin in dry_runs} == {
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    }
    assert not any(
        stdin is None
        and any(action in command for action in ("create", "apply", "label"))
        for command, stdin in calls
    )
