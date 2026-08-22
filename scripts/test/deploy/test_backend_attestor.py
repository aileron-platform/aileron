from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deploy/rke2/backend_attestor.py"
SPEC = importlib.util.spec_from_file_location("backend_attestor", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

RELEASE_PATH = ROOT / "deploy/rke2/acceptance_release.py"
RELEASE_SPEC = importlib.util.spec_from_file_location(
    "acceptance_release_for_backend_attestor_test", RELEASE_PATH
)
assert RELEASE_SPEC and RELEASE_SPEC.loader
RELEASE = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(RELEASE)

IMAGE = "harbor.rke.soez.tw/library/workspace-manager@sha256:" + "1" * 64
RUNTIME_IMAGE = "harbor.rke.soez.tw/library/workspace-manager@sha256:" + "2" * 64
COMMIT = "a" * 40
RUN_ID = "run-20260808"
KEY = b"k" * 32
CONTEXT = "rke2-homelab"
CLUSTER_UID = "cluster-uid"
INSTALLATION_SHA256 = "9" * 64
PULL_SECRET_DATA = {".dockerconfigjson": "eyJhdXRocyI6e319"}
PROFILE_DOCUMENT = {
    "schemaVersion": "aileron-backend-execution-profile/v1",
    "executionNamespace": "aileron-backend-attestor-system",
    "namespaceOwner": "aileron-installer",
    "imagePullSecret": "harbor-rke-creds",
    "nfsMountRoots": [{"server": "192.168.50.100", "path": "/volume1/okd/aileron"}],
    "localPathNodes": [
        {
            "hostname": "node3",
            "nodeUid": "087d8c89-bc44-4bd1-a449-b2b86de511b1",
            "mountRoots": ["/var/lib/rancher/rke2/storage"],
        }
    ],
}
LOCAL_LOCATOR = {
    "type": "localPath",
    "node": "node3",
    "path": "/var/lib/rancher/rke2/storage/pvc-workspace-1",
    "volumeSource": "local",
}
NFS_LOCATOR = {
    "type": "nfs",
    "server": "192.168.50.100",
    "path": "/volume1/okd/aileron/workspace-data",
}


class _FakeDeleteClient:
    def __init__(self, runner) -> None:
        self.runner = runner

    def delete(self, **arguments) -> None:
        result = self.runner(
            ["kubectl", "delete", "job", arguments["name"]]
        )
        if result.returncode != 0:
            raise RuntimeError("injected preconditioned delete failure")


@pytest.fixture(autouse=True)
def _private_input_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        MODULE,
        "_load_job_delete_client",
        lambda **arguments: _FakeDeleteClient(arguments["runner"]),
    )


def _execution_binding() -> dict:
    return {
        "schemaVersion": "aileron-backend-execution-resources-binding/v1",
        "namespace": {
            "name": "aileron-backend-attestor-system",
            "uid": "execution-namespace-uid",
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
            "uid": "pull-secret-uid",
            "owner": "aileron-installer",
            "dataKeys": [".dockerconfigjson"],
            "dataSha256": hashlib.sha256(_canonical(PULL_SECRET_DATA)).hexdigest(),
        },
    }


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _write_private(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _profile(tmp_path: Path, document: dict | None = None) -> tuple[object, dict, Path]:
    selected = copy.deepcopy(document or PROFILE_DOCUMENT)
    path = _write_private(
        tmp_path / "backend-profile.json", _canonical(selected) + b"\n"
    )
    binding = MODULE.inspect_execution_profile(path, private_root=tmp_path)
    return (
        MODULE._load_execution_profile(
            path=path, snapshot_binding=binding, private_root=tmp_path
        ),
        binding,
        path,
    )


def test_capture_and_pure_validation_build_one_canonical_snapshot_binding(
    tmp_path: Path,
) -> None:
    _, profile_binding, profile_path = _profile(tmp_path)

    resources = MODULE.inspect_execution_resources(
        execution_profile_path=profile_path,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        private_root=tmp_path,
        runner=_identity_runner,
    )
    candidate = {
        "schemaVersion": "aileron-backend-attestor-snapshot-binding/v1",
        "executionProfile": profile_binding,
        "executionResources": resources,
        "imageInventorySha256": "8" * 64,
    }
    validated = MODULE.validate_backend_attestor_snapshot_binding(candidate)
    candidate["executionProfile"]["profile"]["nfsMountRoots"][0]["path"] = "/"

    assert validated["executionResources"] == _execution_binding()
    assert validated["executionProfile"]["profile"] == PROFILE_DOCUMENT


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("executionNamespace", "workspace-system"),
        ("namespaceOwner", "other-installer"),
        ("imagePullSecret", "other-secret"),
    ],
)
def test_profile_rejects_caller_selected_execution_identity(
    tmp_path: Path, field: str, value: str
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    document[field] = value
    path = _write_private(
        tmp_path / f"invalid-{field}.json", _canonical(document) + b"\n"
    )

    with pytest.raises(ValueError, match="identity is not fixed"):
        MODULE.inspect_execution_profile(path, private_root=tmp_path)


@pytest.mark.parametrize(
    "run_id",
    (
        "20260808",
        "run-short",
        "run-Uppercase01",
        "run--leading01",
        "run-trailing01-",
        "run-under_score01",
    ),
)
def test_public_signed_loader_rejects_noncanonical_shared_run_identity(
    run_id: str,
) -> None:
    with pytest.raises(ValueError, match="signed snapshot identity is invalid"):
        MODULE.load_signed_backend_attestor_inputs(
            context=CONTEXT,
            commit=COMMIT,
            expected_run_id=run_id,
            expected_snapshot_sha256="8" * 64,
        )


def test_backend_uses_shared_kubernetes_label_run_id_boundaries() -> None:
    assert MODULE.RUN_ID_PATTERN is MODULE.ACCEPTANCE_PRIVATE_IO.RUN_ID
    assert MODULE.RUN_ID_PATTERN.fullmatch("run-" + "a" * 59) is not None
    assert MODULE.RUN_ID_PATTERN.fullmatch("run-" + "a" * 60) is None


def _image_inventory(tmp_path: Path) -> tuple[object, Path]:
    contract = json.loads(
        (ROOT / "deploy/rke2/image-release-contract.json").read_text()
    )
    images = []
    for index, component in enumerate(contract["publishedComponents"], start=1):
        repository = f"harbor.rke.soez.tw/library/{component}"
        digest = f"{index:064x}"
        images.append(
            {
                "component": component,
                "revision": COMMIT,
                "platform": "linux/amd64",
                "taggedImage": f"{repository}:git-{COMMIT}",
                "immutableImage": f"{repository}@sha256:{digest}",
                "runtimeImmutableImage": f"{repository}@sha256:{index + 100:064x}",
            }
        )
    manager = next(item for item in images if item["component"] == "workspace-manager")
    manager["immutableImage"] = IMAGE
    manager["runtimeImmutableImage"] = RUNTIME_IMAGE
    inventory_path = tmp_path / "signed-image-inventory.json"
    RELEASE.write_signed_image_inventory(
        path=inventory_path,
        private_root=tmp_path,
        images=images,
        key=KEY,
        context=CONTEXT,
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=INSTALLATION_SHA256,
    )
    image = MODULE._load_attestor_image(
        path=inventory_path,
        key=KEY,
        context=CONTEXT,
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=INSTALLATION_SHA256,
        private_root=tmp_path,
    )
    return image, inventory_path


def _kubeconfig(tmp_path: Path) -> Path:
    return _write_private(tmp_path / "kubeconfig", b"apiVersion: v1\n")


def _node_result(
    *,
    name: str = "node3",
    uid: str = "087d8c89-bc44-4bd1-a449-b2b86de511b1",
    hostname: str = "node3",
    os_label: str = "linux",
    arch: str = "amd64",
    returncode: int = 0,
) -> object:
    document = {
        "apiVersion": "v1",
        "kind": "Node",
        "metadata": {
            "name": name,
            "uid": uid,
            "labels": {
                "kubernetes.io/hostname": hostname,
                "kubernetes.io/os": os_label,
                "kubernetes.io/arch": arch,
            },
        },
    }
    return MODULE.CommandResult(
        stdout=_canonical(document), stderr=b"node error", returncode=returncode
    )


def _namespace_result(
    *,
    uid: str = "execution-namespace-uid",
    owner: str = "aileron-installer",
    enforce: str = "privileged",
    audit: str = "restricted",
    warn: str = "restricted",
    extra_labels: dict[str, str] | None = None,
    phase: str = "Active",
    returncode: int = 0,
) -> object:
    return MODULE.CommandResult(
        stdout=_canonical(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": "aileron-backend-attestor-system",
                    "uid": uid,
                    "labels": {
                        "platform.aileron.dev/namespace-owner": owner,
                        "pod-security.kubernetes.io/enforce": enforce,
                        "pod-security.kubernetes.io/audit": audit,
                        "pod-security.kubernetes.io/warn": warn,
                        **(extra_labels or {}),
                    },
                },
                "status": {"phase": phase},
            }
        ),
        stderr=b"namespace error",
        returncode=returncode,
    )


def _secret_result(
    *,
    uid: str = "pull-secret-uid",
    data: dict | None = None,
    owner: str = "aileron-installer",
    returncode: int = 0,
) -> object:
    return MODULE.CommandResult(
        stdout=_canonical(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": "harbor-rke-creds",
                    "namespace": "aileron-backend-attestor-system",
                    "uid": uid,
                    "labels": {
                        "platform.aileron.dev/secret-owner": owner,
                    },
                },
                "type": "kubernetes.io/dockerconfigjson",
                "data": PULL_SECRET_DATA if data is None else data,
            }
        ),
        stderr=b"secret error",
        returncode=returncode,
    )


def _identity_runner(
    command: list[str], *, node_result: object | None = None
) -> object:
    resource = command[command.index("get") + 1] if "get" in command else ""
    if resource == "namespace":
        return _namespace_result()
    if resource == "secret":
        return _secret_result()
    if resource == "node":
        return node_result or _node_result()
    raise AssertionError(command)


def _build_local_manifest(
    tmp_path: Path, *, action: str = "verify"
) -> tuple[dict, object, object, list[list[str]]]:
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )
    commands: list[list[str]] = []

    def runner(command: list[str]) -> object:
        commands.append(command)
        return _identity_runner(command)

    cleanup_authorization = None
    if action == "cleanup":
        cleanup_binding = MODULE._load_cleanup_target_binding(
            locator=LOCAL_LOCATOR,
            run_id=RUN_ID,
            snapshot_binding=_cleanup_binding(),
        )
        cleanup_authorization = MODULE._authorize_backend_cleanup(
            binding=cleanup_binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=lambda _command: MODULE.CommandResult(
                stdout=_canonical({"apiVersion": "v1", "kind": "List", "items": []}),
                stderr=b"",
                returncode=0,
            ),
        )

    manifest = MODULE.build_attestor_job_manifest(
        action=action,
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        run_id=RUN_ID,
        runner=runner,
        cleanup_authorization=cleanup_authorization,
    )
    return manifest, profile, image, commands


def _build_nfs_manifest(
    tmp_path: Path, *, action: str = "verify"
) -> tuple[dict, object, object, list[list[str]]]:
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )
    commands: list[list[str]] = []

    def runner(command: list[str]) -> object:
        commands.append(command)
        return _identity_runner(command)

    cleanup_authorization = None
    if action == "cleanup":
        cleanup_binding_document = _cleanup_binding()
        cleanup_binding_document["locatorSha256"] = MODULE.locator_sha256(NFS_LOCATOR)
        cleanup_binding = MODULE._load_cleanup_target_binding(
            locator=NFS_LOCATOR,
            run_id=RUN_ID,
            snapshot_binding=cleanup_binding_document,
        )
        cleanup_authorization = MODULE._authorize_backend_cleanup(
            binding=cleanup_binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=lambda _command: MODULE.CommandResult(
                stdout=_canonical({"apiVersion": "v1", "kind": "List", "items": []}),
                stderr=b"",
                returncode=0,
            ),
        )

    manifest = MODULE.build_attestor_job_manifest(
        action=action,
        locator=NFS_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        run_id=RUN_ID,
        runner=runner,
        cleanup_authorization=cleanup_authorization,
    )
    return manifest, profile, image, commands


def test_profile_requires_mode_0600_canonical_bytes_and_snapshot_binding(
    tmp_path: Path,
) -> None:
    path = tmp_path / "backend-profile.json"
    path.write_text(json.dumps(PROFILE_DOCUMENT, indent=2) + "\n")
    with pytest.raises(ValueError, match="mode-0600"):
        MODULE.inspect_execution_profile(path, private_root=tmp_path)

    path.chmod(0o600)
    with pytest.raises(ValueError, match="canonical"):
        MODULE.inspect_execution_profile(path, private_root=tmp_path)

    path.write_bytes(_canonical(PROFILE_DOCUMENT) + b"\n")
    binding = MODULE.inspect_execution_profile(path, private_root=tmp_path)
    assert binding == {
        "schemaVersion": "aileron-backend-execution-profile-binding/v1",
        "rawSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "canonicalSha256": hashlib.sha256(_canonical(PROFILE_DOCUMENT)).hexdigest(),
        "profile": PROFILE_DOCUMENT,
    }
    for changed_key in ("rawSha256", "canonicalSha256", "profile"):
        changed = copy.deepcopy(binding)
        changed[changed_key] = (
            "f" * 64 if changed_key != "profile" else {**PROFILE_DOCUMENT, "x": True}
        )
        with pytest.raises(ValueError, match="snapshot binding"):
            MODULE._load_execution_profile(
                path=path, snapshot_binding=changed, private_root=tmp_path
            )


def test_profile_accepts_dns_subdomain_for_fixed_node_identity(
    tmp_path: Path,
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    document["localPathNodes"][0]["hostname"] = "node." + "h" * 63
    profile, _, _ = _profile(tmp_path, document)

    assert profile.document["localPathNodes"][0]["hostname"] == "node." + "h" * 63


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("executionNamespace", "storage.system"),
        ("imagePullSecret", "s" * 64 + ".registry"),
        ("hostname", "h" * 64 + ".node"),
        ("namespaceOwner", "owner/invalid"),
        ("namespaceOwner", "o" * 64),
    ],
)
def test_profile_rejects_invalid_kubernetes_names_and_label_values(
    tmp_path: Path, field: str, value: str
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    if field == "hostname":
        document["localPathNodes"][0]["hostname"] = value
    else:
        document[field] = value
    path = _write_private(
        tmp_path / "invalid-profile.json", _canonical(document) + b"\n"
    )

    with pytest.raises(ValueError):
        MODULE.inspect_execution_profile(path, private_root=tmp_path)


@pytest.mark.parametrize(
    ("server", "path_value", "accepted"),
    [
        ("192.168.50.100", "/volume1/okd/aileron", True),
        ("nfs.example.test", "/volume1/okd/aileron", False),
        ("2001:db8::1", "/volume1/okd/aileron", False),
        ("192.168.050.100", "/volume1/okd/aileron", False),
        ("256.168.50.100", "/volume1/okd/aileron", False),
        ("192.168.50.100", "/volume1/../aileron", False),
        ("192.168.50.100", "/volume1/./aileron", False),
        ("192.168.50.100", "/volume1//aileron", False),
        ("192.168.50.100", "/volume1/aileron/", False),
    ],
)
def test_profile_schema_and_runtime_accept_the_same_pinned_nfs_contract(
    tmp_path: Path, server: str, path_value: str, accepted: bool
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    document["nfsMountRoots"] = [{"server": server, "path": path_value}]
    schema = json.loads(
        (ROOT / "deploy/rke2/backend-execution-profile.schema.json").read_text()
    )
    schema_accepted = Draft202012Validator(schema).is_valid(document)
    profile_path = _write_private(
        tmp_path / "profile.json", _canonical(document) + b"\n"
    )
    try:
        MODULE.inspect_execution_profile(profile_path, private_root=tmp_path)
    except ValueError:
        runtime_accepted = False
    else:
        runtime_accepted = True

    assert schema_accepted is accepted
    assert runtime_accepted is accepted


def test_profile_resolves_only_strict_descendants_and_profile_owned_node_identity(
    tmp_path: Path,
) -> None:
    profile, _, _ = _profile(tmp_path)

    csi = MODULE.resolve_backend_target(
        {
            "type": "csi",
            "driver": "nfs.csi.k8s.io",
            "volumeHandle": (
                "192.168.50.100#volume1/okd/aileron#"
                "workspace-system-data-pv-1#pv-1#retain"
            ),
        },
        profile=profile,
    )
    local = MODULE.resolve_backend_target(LOCAL_LOCATOR, profile=profile)

    assert csi == {
        "backend": "csi:nfs.csi.k8s.io",
        "mount": {
            "type": "nfs",
            "server": "192.168.50.100",
            "path": "/volume1/okd/aileron",
        },
        "relativePath": "workspace-system-data-pv-1",
    }
    assert local == {
        "backend": "localPath",
        "mount": {
            "type": "localPath",
            "node": "node3",
            "nodeUid": "087d8c89-bc44-4bd1-a449-b2b86de511b1",
            "path": "/var/lib/rancher/rke2/storage",
        },
        "relativePath": "pvc-workspace-1",
    }


@pytest.mark.parametrize(
    "locator",
    [
        {
            "type": "nfs",
            "server": "192.168.50.100",
            "path": "/volume1/okd/aileron",
        },
        {
            "type": "nfs",
            "server": "192.168.50.100",
            "path": "/volume1/other/unsafe",
        },
        {
            **LOCAL_LOCATOR,
            "node": "unapproved-node",
        },
        {
            **LOCAL_LOCATOR,
            "path": "/etc/aileron",
        },
        {
            "type": "csi",
            "driver": "other.csi.example",
            "volumeHandle": "192.168.50.100#/volume1/okd/aileron#pv-1",
        },
    ],
)
def test_profile_rejects_root_deletion_outside_root_and_unapproved_node(
    tmp_path: Path, locator: dict
) -> None:
    profile, _, _ = _profile(tmp_path)

    with pytest.raises(ValueError):
        MODULE.resolve_backend_target(locator, profile=profile)


def test_local_manifest_requires_live_pinned_node_uid_before_render(
    tmp_path: Path,
) -> None:
    manifest, profile, image, commands = _build_local_manifest(tmp_path)

    assert commands == [
        [
            "kubectl",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--context",
            CONTEXT,
            "--request-timeout=30s",
            "get",
            "namespace",
            "aileron-backend-attestor-system",
            "--output=json",
        ],
        [
            "kubectl",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--context",
            CONTEXT,
            "--request-timeout=30s",
            "--namespace",
            "aileron-backend-attestor-system",
            "get",
            "secret",
            "harbor-rke-creds",
            "--output=json",
        ],
        [
            "kubectl",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--context",
            CONTEXT,
            "--request-timeout=30s",
            "get",
            "node",
            "node3",
            "--output=json",
        ],
    ]
    assert manifest["spec"]["template"]["spec"]["nodeSelector"] == {
        "kubernetes.io/hostname": "node3",
        "kubernetes.io/os": "linux",
        "kubernetes.io/arch": "amd64",
    }
    assert profile.document["localPathNodes"][0]["nodeUid"] in json.dumps(manifest)
    assert (
        image.immutable_image
        == manifest["spec"]["template"]["spec"]["containers"][0]["image"]
    )


@pytest.mark.parametrize(
    "node_result",
    [
        _node_result(uid="wrong-node-uid"),
        _node_result(name="replacement-node"),
        _node_result(hostname="wrong-hostname"),
        _node_result(os_label="windows"),
        _node_result(arch="arm64"),
        _node_result(returncode=1),
        MODULE.CommandResult(stdout=b"not-json", stderr=b"", returncode=0),
    ],
)
def test_local_manifest_fails_closed_for_node_replacement_or_transport_failure(
    tmp_path: Path, node_result: object
) -> None:
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )

    with pytest.raises(MODULE.BackendAttestorError, match="Node"):
        MODULE.build_attestor_job_manifest(
            action="verify",
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            run_id=RUN_ID,
            runner=lambda command: _identity_runner(command, node_result=node_result),
        )


@pytest.mark.parametrize(
    "drift_result",
    [
        _namespace_result(uid="replacement-namespace-uid"),
        _namespace_result(owner="other-owner"),
        _namespace_result(enforce="baseline"),
        _namespace_result(phase="Terminating"),
        _namespace_result(
            extra_labels={"pod-security.kubernetes.io/enforce-version": "v1.30"}
        ),
        _namespace_result(returncode=1),
        _secret_result(uid="replacement-secret-uid"),
        _secret_result(owner="other-installer"),
        _secret_result(data={".dockerconfigjson": "different"}),
        _secret_result(
            data={".dockerconfigjson": "different", "extra": "retained"}
        ),
        _secret_result(returncode=1),
    ],
)
def test_manifest_fails_closed_for_execution_namespace_or_pull_secret_drift(
    tmp_path: Path, drift_result: object
) -> None:
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )

    def runner(command: list[str]) -> object:
        resource = command[command.index("get") + 1] if "get" in command else ""
        if resource == "namespace" and (
            getattr(drift_result, "stdout", b"").find(b'"kind":"Namespace"') >= 0
            or getattr(drift_result, "returncode", 0) != 0
        ):
            return drift_result
        if resource == "secret" and (
            getattr(drift_result, "stdout", b"").find(b'"kind":"Secret"') >= 0
            or getattr(drift_result, "returncode", 0) != 0
        ):
            return drift_result
        return _identity_runner(command)

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.build_attestor_job_manifest(
            action="verify",
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            run_id=RUN_ID,
            runner=runner,
        )


def _cleanup_binding() -> dict:
    return {
        "schemaVersion": "aileron-backend-cleanup-target-binding/v1",
        "snapshotSha256": "8" * 64,
        "runId": RUN_ID,
        "locatorSha256": MODULE.locator_sha256(LOCAL_LOCATOR),
        "namespaces": ["workspace-system", "aileron-identity-system"],
        "persistentVolumeClaims": [
            {"namespace": "workspace-system", "name": "workspace-data"}
        ],
        "persistentVolume": {"name": "workspace-pv", "uid": "workspace-pv-uid"},
    }


def test_public_signed_loader_derives_every_path_and_target_from_live_trust(
    tmp_path: Path,
) -> None:
    acceptance_directory = tmp_path / "evidence" / COMMIT / RUN_ID
    install_directory = tmp_path / "install" / COMMIT
    reset_directory = tmp_path / "reset" / COMMIT / RUN_ID
    for directory in (
        tmp_path / "evidence",
        tmp_path / "evidence" / COMMIT,
        acceptance_directory,
        tmp_path / "install",
        install_directory,
        tmp_path / "reset",
        tmp_path / "reset" / COMMIT,
        reset_directory,
    ):
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
    _, profile_binding, source_profile = _profile(tmp_path)
    profile_path = _write_private(
        acceptance_directory / "backend-execution-profile.json",
        source_profile.read_bytes(),
    )
    _, source_inventory = _image_inventory(tmp_path)
    image_inventory_path = _write_private(
        install_directory / "signed-image-inventory.json",
        source_inventory.read_bytes(),
    )
    kubeconfig = _write_private(
        reset_directory / f"reset-kubeconfig-{RUN_ID}.flattened.json",
        b"apiVersion: v1\n",
    )
    observed: dict[str, object] = {}

    def trust_loader(*, context: str, kubeconfig: Path):
        observed["trust"] = (context, kubeconfig)
        return type(
            "Trust",
            (),
            {
                "key": KEY,
                "cluster_uid": CLUSTER_UID,
                "installation_identity_sha256": INSTALLATION_SHA256,
            },
        )()

    snapshot = {
        "runId": RUN_ID,
        "commit": COMMIT,
        "context": CONTEXT,
        "clusterUid": CLUSTER_UID,
        "installationIdentitySha256": INSTALLATION_SHA256,
        "backendAttestor": {
            "schemaVersion": "aileron-backend-attestor-snapshot-binding/v1",
            "executionProfile": profile_binding,
            "executionResources": _execution_binding(),
            "imageInventorySha256": hashlib.sha256(
                image_inventory_path.read_bytes()
            ).hexdigest(),
        },
        "inventory": {
            "namespaces": [{"name": "workspace-system"}],
            "resources": [
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolumeClaim",
                    "namespace": "workspace-system",
                    "name": "workspace-data",
                }
            ],
            "persistentVolumes": [
                    {
                        "apiVersion": "v1",
                        "kind": "PersistentVolume",
                        "name": "workspace-pv",
                        "uid": "workspace-pv-uid",
                        "backendLocator": LOCAL_LOCATOR,
                    }
            ],
        },
    }

    def snapshot_loader(**arguments):
        observed["snapshot"] = arguments
        return copy.deepcopy(snapshot)

    inputs = MODULE._load_signed_backend_attestor_inputs(
        context=CONTEXT,
        commit=COMMIT,
        expected_run_id=RUN_ID,
        expected_snapshot_sha256="8" * 64,
        _trust_loader=trust_loader,
        _snapshot_loader=snapshot_loader,
    )

    assert observed["trust"] == (CONTEXT, kubeconfig)
    assert observed["snapshot"]["directory"] == acceptance_directory
    assert observed["snapshot"]["key"] == KEY
    assert inputs.profile.path == profile_path
    assert inputs.image.path == image_inventory_path
    assert len(inputs.cleanup_targets) == 1
    assert inputs.cleanup_targets[0].locator == LOCAL_LOCATOR
    assert inputs.cleanup_targets[0].persistent_volume_name == "workspace-pv"
    assert inputs.cleanup_targets[0].persistent_volume_uid == "workspace-pv-uid"
    public_parameters = inspect.signature(
        MODULE.load_signed_backend_attestor_inputs
    ).parameters
    assert not {
        "key",
        "locator",
        "snapshot_binding",
        "acceptance_directory",
        "image_inventory_path",
        "execution_profile_path",
        "kubeconfig",
    }.intersection(public_parameters)

    snapshot["inventory"] = {
        "namespaces": [],
        "resources": [],
        "persistentVolumes": [],
    }
    empty_inputs = MODULE._load_signed_backend_attestor_inputs(
        context=CONTEXT,
        commit=COMMIT,
        expected_run_id=RUN_ID,
        expected_snapshot_sha256="8" * 64,
        _trust_loader=trust_loader,
        _snapshot_loader=snapshot_loader,
    )
    assert empty_inputs.cleanup_targets == ()


def test_cleanup_authorization_queries_all_signed_target_kinds_and_requires_absence(
    tmp_path: Path,
) -> None:
    profile, _, _ = _profile(tmp_path)
    binding = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    commands: list[list[str]] = []

    def runner(command: list[str]) -> object:
        commands.append(command)
        resource = command[command.index("get") + 1]
        items = []
        if resource != "persistentvolumes":
            items = [{"metadata": {"name": "unrelated", "namespace": "other"}}]
        return MODULE.CommandResult(
            stdout=_canonical(
                {
                    "apiVersion": "v1",
                    "kind": "List",
                    "items": items,
                }
            ),
            stderr=b"",
            returncode=0,
        )

    authorization = MODULE._authorize_backend_cleanup(
        binding=binding,
        profile=profile,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        runner=runner,
    )

    assert authorization.locator_sha256 == MODULE.locator_sha256(LOCAL_LOCATOR)
    assert [command[6:9] for command in commands] == [
        ["get", "namespaces", "--output=json"],
        ["get", "persistentvolumeclaims", "--all-namespaces"],
        ["get", "persistentvolumes", "--output=json"],
    ]


@pytest.mark.parametrize(
    "items",
    [
        [{"metadata": {"name": "workspace-system"}}],
        [
            {
                "metadata": {
                    "namespace": "workspace-system",
                    "name": "workspace-data",
                }
            }
        ],
        [{"metadata": {"name": "workspace-pv"}}],
    ],
)
def test_cleanup_authorization_rejects_any_signed_target_still_present(
    tmp_path: Path, items: list[dict]
) -> None:
    profile, _, _ = _profile(tmp_path)
    binding = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )

    def runner(command: list[str]) -> object:
        resource = command[7] if command[6] == "get" else ""
        selected = []
        if resource == "namespaces" and "namespace" not in items[0]["metadata"]:
            selected = items
        elif (
            resource == "persistentvolumeclaims" and "namespace" in items[0]["metadata"]
        ):
            selected = items
        elif (
            resource == "persistentvolumes"
            and items[0]["metadata"].get("name") == "workspace-pv"
        ):
            selected = items
        return MODULE.CommandResult(
            stdout=_canonical({"apiVersion": "v1", "kind": "List", "items": selected}),
            stderr=b"",
            returncode=0,
        )

    with pytest.raises(MODULE.BackendAttestorError, match="still exists"):
        MODULE._authorize_backend_cleanup(
            binding=binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=runner,
        )


def _local_node_affinity(hostname: str = "node3") -> dict:
    return {
        "required": {
            "nodeSelectorTerms": [
                {
                    "matchExpressions": [
                        {
                            "key": "kubernetes.io/hostname",
                            "operator": "In",
                            "values": [hostname],
                        }
                    ]
                }
            ]
        }
    }


@pytest.mark.parametrize(
    ("locator", "live_spec"),
    [
        (
            {
                "type": "nfs",
                "server": "192.168.50.100",
                "path": "/volume1/okd/aileron/workspace-data",
            },
            {
                "nfs": {
                    "server": "192.168.50.100",
                    "path": "/volume1/okd/aileron/workspace-data",
                }
            },
        ),
        (
            {
                "type": "nfs",
                "server": "192.168.50.100",
                "path": "/volume1/okd/aileron/workspace-data",
            },
            {
                "csi": {
                    "driver": "nfs.csi.k8s.io",
                    "volumeHandle": (
                        "192.168.50.100#volume1/okd/aileron#workspace-data"
                    ),
                }
            },
        ),
        (
            LOCAL_LOCATOR,
            {
                "hostPath": {"path": "/var/lib/rancher/rke2/storage/pvc-workspace-1"},
                "nodeAffinity": _local_node_affinity(),
            },
        ),
    ],
)
def test_cleanup_authorization_rejects_new_pv_rebinding_same_physical_backend(
    tmp_path: Path, locator: dict, live_spec: dict
) -> None:
    binding_document = _cleanup_binding()
    binding_document["locatorSha256"] = MODULE.locator_sha256(locator)
    binding = MODULE._load_cleanup_target_binding(
        locator=locator,
        run_id=RUN_ID,
        snapshot_binding=binding_document,
    )
    profile, _, _ = _profile(tmp_path)

    def runner(command: list[str]) -> object:
        resource = command[command.index("get") + 1]
        items = []
        if resource == "persistentvolumes":
            items = [
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolume",
                    "metadata": {"name": "new-rebound-pv", "uid": "new-pv-uid"},
                    "spec": live_spec,
                }
            ]
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "List", "items": items}),
            b"",
            0,
        )

    with pytest.raises(MODULE.BackendAttestorError, match="backend.*rebound"):
        MODULE._authorize_backend_cleanup(
            binding=binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=runner,
        )


def test_cleanup_authorization_allows_unrelated_live_pv_backend(
    tmp_path: Path,
) -> None:
    locator = {
        "type": "nfs",
        "server": "192.168.50.100",
        "path": "/volume1/okd/aileron/workspace-data",
    }
    binding_document = _cleanup_binding()
    binding_document["locatorSha256"] = MODULE.locator_sha256(locator)
    binding = MODULE._load_cleanup_target_binding(
        locator=locator,
        run_id=RUN_ID,
        snapshot_binding=binding_document,
    )
    profile, _, _ = _profile(tmp_path)

    def runner(command: list[str]) -> object:
        resource = command[command.index("get") + 1]
        items = []
        if resource == "persistentvolumes":
            items = [
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolume",
                    "metadata": {"name": "unrelated-pv", "uid": "other-pv-uid"},
                    "spec": {
                        "nfs": {
                            "server": "192.168.50.100",
                            "path": "/volume1/okd/aileron/other-data",
                        }
                    },
                }
            ]
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "List", "items": items}),
            b"",
            0,
        )

    authorization = MODULE._authorize_backend_cleanup(
        binding=binding,
        profile=profile,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        runner=runner,
    )

    assert authorization.locator_sha256 == MODULE.locator_sha256(locator)


@pytest.mark.parametrize(
    ("locator", "live_spec"),
    [
        (
            {
                "type": "nfs",
                "server": "192.168.50.100",
                "path": "/volume1/okd/aileron/workspace-data",
            },
            {
                "nfs": {
                    "server": "192.168.50.100",
                    "path": "/volume1/okd/aileron/workspace-data/active-child",
                }
            },
        ),
        (
            {
                "type": "csi",
                "driver": "nfs.csi.k8s.io",
                "volumeHandle": (
                    "192.168.50.100#volume1/okd/aileron#workspace-data/active-child"
                ),
            },
            {
                "nfs": {
                    "server": "192.168.50.100",
                    "path": "/volume1/okd/aileron/workspace-data",
                }
            },
        ),
        (
            LOCAL_LOCATOR,
            {
                "hostPath": {
                    "path": (
                        "/var/lib/rancher/rke2/storage/"
                        "pvc-workspace-1/active-child"
                    )
                },
                "nodeAffinity": _local_node_affinity(),
            },
        ),
    ],
)
def test_cleanup_authorization_rejects_overlapping_live_pv_backend(
    tmp_path: Path, locator: dict, live_spec: dict
) -> None:
    binding_document = _cleanup_binding()
    binding_document["locatorSha256"] = MODULE.locator_sha256(locator)
    binding = MODULE._load_cleanup_target_binding(
        locator=locator,
        run_id=RUN_ID,
        snapshot_binding=binding_document,
    )
    profile, _, _ = _profile(tmp_path)

    def runner(command: list[str]) -> object:
        resource = command[command.index("get") + 1]
        items = []
        if resource == "persistentvolumes":
            items = [
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolume",
                    "metadata": {"name": "overlapping-pv", "uid": "overlap-uid"},
                    "spec": live_spec,
                }
            ]
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "List", "items": items}),
            b"",
            0,
        )

    with pytest.raises(MODULE.BackendAttestorError, match="backend.*overlap"):
        MODULE._authorize_backend_cleanup(
            binding=binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=runner,
        )


def test_snapshot_cleanup_target_set_rejects_duplicate_or_overlapping_backends(
    tmp_path: Path,
) -> None:
    profile, _, _ = _profile(tmp_path)
    locators = [
        {
            "type": "nfs",
            "server": "192.168.50.100",
            "path": "/volume1/okd/aileron/workspace-data",
        },
        {
            "type": "csi",
            "driver": "nfs.csi.k8s.io",
            "volumeHandle": (
                "192.168.50.100#volume1/okd/aileron#workspace-data/child"
            ),
        },
    ]
    bindings = []
    for index, locator in enumerate(locators):
        document = _cleanup_binding()
        document["locatorSha256"] = MODULE.locator_sha256(locator)
        document["persistentVolume"] = {
            "name": f"workspace-pv-{index}",
            "uid": f"workspace-pv-uid-{index}",
        }
        bindings.append(
            MODULE._load_cleanup_target_binding(
                locator=locator,
                run_id=RUN_ID,
                snapshot_binding=document,
            )
        )

    with pytest.raises(ValueError, match="cleanup backend targets overlap"):
        MODULE.validate_cleanup_target_set(bindings=bindings, profile=profile)


def test_snapshot_target_set_rejects_job_name_prefix_collision_before_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, _, _ = _profile(tmp_path)
    bindings = []
    for index, path in enumerate(("workspace-a", "workspace-b")):
        locator = {
            "type": "nfs",
            "server": "192.168.50.100",
            "path": f"/volume1/okd/aileron/{path}",
        }
        document = _cleanup_binding()
        document["locatorSha256"] = MODULE.locator_sha256(locator)
        document["persistentVolume"] = {
            "name": f"workspace-pv-{index}",
            "uid": f"workspace-pv-uid-{index}",
        }
        bindings.append(
            MODULE._load_cleanup_target_binding(
                locator=locator, run_id=RUN_ID, snapshot_binding=document
            )
        )
    bindings[0].locator_sha256 = "a" * 12 + "1" * 52
    bindings[1].locator_sha256 = "a" * 12 + "2" * 52
    monkeypatch.setattr(
        MODULE,
        "locator_sha256",
        lambda locator: (
            "a" * 12 + "1" * 52
            if locator["path"].endswith("workspace-a")
            else "a" * 12 + "2" * 52
        ),
    )

    with pytest.raises(ValueError, match="Job names collide"):
        MODULE.validate_cleanup_target_set(bindings=bindings, profile=profile)


@pytest.mark.parametrize("action", ("cleanup", "verify"))
def test_job_manifest_uses_only_calculated_profile_and_signed_image_identity(
    tmp_path: Path, action: str
) -> None:
    profile, binding, _ = _profile(tmp_path)
    image, inventory_path = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )
    cleanup_authorization = None
    if action == "cleanup":
        cleanup_binding = MODULE._load_cleanup_target_binding(
            locator=LOCAL_LOCATOR,
            run_id=RUN_ID,
            snapshot_binding={
                "schemaVersion": "aileron-backend-cleanup-target-binding/v1",
                "snapshotSha256": "8" * 64,
                "runId": RUN_ID,
                "locatorSha256": MODULE.locator_sha256(LOCAL_LOCATOR),
                "namespaces": ["workspace-system"],
                "persistentVolumeClaims": [
                    {"namespace": "workspace-system", "name": "workspace-data"}
                ],
                "persistentVolume": {
                    "name": "workspace-pv",
                    "uid": "workspace-pv-uid",
                },
            },
        )
        cleanup_authorization = MODULE._authorize_backend_cleanup(
            binding=cleanup_binding,
            profile=profile,
            kubeconfig=_kubeconfig(tmp_path),
            context=CONTEXT,
            runner=lambda command: MODULE.CommandResult(
                stdout=_canonical({"apiVersion": "v1", "kind": "List", "items": []}),
                stderr=b"",
                returncode=0,
            ),
        )
    manifest = MODULE.build_attestor_job_manifest(
        action=action,
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        kubeconfig=_kubeconfig(tmp_path),
        context=CONTEXT,
        run_id=RUN_ID,
        runner=lambda command: _identity_runner(command),
        cleanup_authorization=cleanup_authorization,
    )

    parameters = inspect.signature(MODULE.build_attestor_job_manifest).parameters
    assert "profile_sha256" not in parameters
    assert "node_uid" not in parameters
    assert "immutable_image" not in parameters
    assert "source_commit" not in parameters
    annotations = manifest["metadata"]["annotations"]
    assert (
        annotations["platform.aileron.dev/backend-profile-raw-sha256"]
        == binding["rawSha256"]
    )
    assert (
        annotations["platform.aileron.dev/backend-profile-canonical-sha256"]
        == binding["canonicalSha256"]
    )
    assert (
        annotations["platform.aileron.dev/image-inventory-sha256"]
        == hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    )
    assert (
        manifest["metadata"]["labels"]["platform.aileron.dev/source-commit"] == COMMIT
    )
    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["imagePullSecrets"] == [
        {"name": "harbor-rke-creds"}
    ]
    assert pod_spec["volumes"] == [
        {
            "name": "backend",
            "hostPath": {
                "path": "/var/lib/rancher/rke2/storage",
                "type": "Directory",
            },
        }
    ]
    container = pod_spec["containers"][0]
    assert container["image"] == IMAGE
    assert container["command"] == [
        "/workspace-manager/.venv/bin/python",
        "/workspace-manager/scripts/backend_storage_probe.py",
    ]
    assert container["volumeMounts"] == [
        {
            "name": "backend",
            "mountPath": "/backend",
            "readOnly": action == "verify",
        }
    ]
    assert binding["rawSha256"] in container["args"]
    assert binding["canonicalSha256"] in container["args"]
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": (
            {"drop": ["ALL"], "add": ["DAC_OVERRIDE"]}
            if action == "cleanup"
            else {"drop": ["ALL"]}
        ),
        "runAsUser": 0,
        "runAsGroup": 0,
    }
    assert "sh" not in json.dumps(container["command"])


@pytest.mark.parametrize("action", ("cleanup", "verify"))
def test_nfs_manifest_uses_exact_approved_root_and_read_only_verification(
    tmp_path: Path, action: str
) -> None:
    locator = {
        "type": "nfs",
        "server": "192.168.50.100",
        "path": "/volume1/okd/aileron/workspace-data",
    }
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )
    kubeconfig = _kubeconfig(tmp_path)
    authorization = None
    if action == "cleanup":
        binding_document = _cleanup_binding()
        binding_document["locatorSha256"] = MODULE.locator_sha256(locator)
        binding = MODULE._load_cleanup_target_binding(
            locator=locator,
            run_id=RUN_ID,
            snapshot_binding=binding_document,
        )
        authorization = MODULE._authorize_backend_cleanup(
            binding=binding,
            profile=profile,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            runner=lambda _command: MODULE.CommandResult(
                _canonical({"apiVersion": "v1", "kind": "List", "items": []}),
                b"",
                0,
            ),
        )
    commands: list[list[str]] = []

    def runner(command: list[str]) -> object:
        commands.append(command)
        return _identity_runner(command)

    manifest = MODULE.build_attestor_job_manifest(
        action=action,
        locator=locator,
        profile=profile,
        image=image,
        execution_resources=resources,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        runner=runner,
        cleanup_authorization=authorization,
    )

    pod_spec = manifest["spec"]["template"]["spec"]
    assert pod_spec["nodeSelector"] == {
        "kubernetes.io/os": "linux",
        "kubernetes.io/arch": "amd64",
    }
    assert all("node" not in command for command in commands)
    assert pod_spec["volumes"] == [
        {
            "name": "backend",
            "nfs": {
                "server": "192.168.50.100",
                "path": "/volume1/okd/aileron",
                "readOnly": action == "verify",
            },
        }
    ]
    assert pod_spec["containers"][0]["volumeMounts"][0]["readOnly"] is (
        action == "verify"
    )


def _runtime_objects(manifest: dict, image: object) -> tuple[dict, dict]:
    job = copy.deepcopy(manifest)
    job["metadata"]["uid"] = "job-uid"
    job["metadata"]["resourceVersion"] = "701"
    controller_labels = {
        "batch.kubernetes.io/controller-uid": "job-uid",
        "batch.kubernetes.io/job-name": manifest["metadata"]["name"],
        "controller-uid": "job-uid",
        "job-name": manifest["metadata"]["name"],
    }
    job["spec"]["selector"] = {
        "matchLabels": {"batch.kubernetes.io/controller-uid": "job-uid"}
    }
    job["spec"]["manualSelector"] = False
    job["spec"]["template"]["metadata"]["labels"].update(controller_labels)
    job["status"] = {
        "succeeded": 1,
        "conditions": [{"type": "Complete", "status": "True"}],
    }
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": f"{manifest['metadata']['name']}-abcde",
            "namespace": manifest["metadata"]["namespace"],
            "uid": "pod-uid",
            "labels": {
                **manifest["spec"]["template"]["metadata"]["labels"],
                **controller_labels,
            },
            "annotations": manifest["spec"]["template"]["metadata"]["annotations"],
            "ownerReferences": [
                {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "name": manifest["metadata"]["name"],
                    "uid": "job-uid",
                    "controller": True,
                    "blockOwnerDeletion": True,
                }
            ],
        },
        "spec": {
            **copy.deepcopy(manifest["spec"]["template"]["spec"]),
            "serviceAccount": "default",
            "nodeName": "node3",
            "preemptionPolicy": "PreemptLowerPriority",
            "priority": 0,
            "tolerations": [
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
        },
        "status": {
            "phase": "Succeeded",
            "containerStatuses": [
                {
                    "name": "backend-attestor",
                    "image": image.immutable_image,
                    "imageID": "docker-pullable://" + image.immutable_image,
                    "ready": False,
                    "restartCount": 0,
                    "state": {"terminated": {"exitCode": 0, "reason": "Completed"}},
                }
            ],
        },
    }
    return job, {"apiVersion": "v1", "kind": "PodList", "items": [pod]}


class _FakeAttestorCluster:
    def __init__(
        self,
        *,
        image: object,
        verify_state: str = "absent",
        fail_operation: str | None = None,
    ) -> None:
        self.image = image
        self.verify_state = verify_state
        self.fail_operation = fail_operation
        self.commands: list[list[str]] = []
        self.manifests: dict[str, dict] = {}
        self.deleted: set[str] = set()
        self.logs_read = False

    @staticmethod
    def _success(document: object | None = None) -> object:
        stdout = b"" if document is None else _canonical(document)
        return MODULE.CommandResult(stdout=stdout, stderr=b"", returncode=0)

    @staticmethod
    def _failure() -> object:
        return MODULE.CommandResult(stdout=b"", stderr=b"injected", returncode=1)

    def _manifest_for_name(self, name: str) -> dict:
        if name.startswith("job/") or name.startswith("pod/"):
            name = name.split("/", 1)[1]
        if name in self.manifests:
            return self.manifests[name]
        for manifest in self.manifests.values():
            if name.startswith(manifest["metadata"]["name"]):
                return manifest
        raise AssertionError(name)

    def __call__(self, command: list[str]) -> object:
        self.commands.append(command)
        if "create" in command:
            manifest_path = Path(command[command.index("--filename") + 1])
            manifest = json.loads(manifest_path.read_text())
            name = manifest["metadata"]["name"]
            if self.fail_operation == "create-spec-drift":
                manifest["spec"]["backoffLimit"] = 99
            self.manifests[name] = manifest
            if self.fail_operation == "create":
                return self._failure()
            job, _ = _runtime_objects(manifest, self.image)
            return self._success(job)
        if "wait" in command:
            if self.fail_operation == "wait":
                return self._failure()
            return self._success()
        if "logs" in command:
            if self.fail_operation == "logs":
                return self._failure()
            manifest = self._manifest_for_name(command[command.index("logs") + 1])
            action = manifest["metadata"]["labels"][
                "platform.aileron.dev/backend-action"
            ]
            annotations = manifest["metadata"]["annotations"]
            observation = {
                "schemaVersion": "aileron-backend-storage-probe/v1",
                "action": action,
                "runId": RUN_ID,
                "locatorSha256": annotations[
                    "platform.aileron.dev/backend-locator-sha256"
                ],
                "profileRawSha256": annotations[
                    "platform.aileron.dev/backend-profile-raw-sha256"
                ],
                "profileCanonicalSha256": annotations[
                    "platform.aileron.dev/backend-profile-canonical-sha256"
                ],
                "state": self.verify_state if action == "verify" else "absent",
                "cleanupPerformed": action == "cleanup",
                "checkedAt": "2026-08-09T09:00:00Z",
            }
            if self.fail_operation == "logs-json":
                return MODULE.CommandResult(b"not-json", b"", 0)
            self.logs_read = True
            return self._success(observation)
        if "delete" in command:
            name = command[command.index("delete") + 2]
            if self.fail_operation == "delete":
                return self._failure()
            self.deleted.add(name)
            return self._success()
        if "get" not in command:
            raise AssertionError(command)
        resource = command[command.index("get") + 1]
        if resource == "namespace":
            return _namespace_result()
        if resource == "secret":
            return _secret_result()
        if resource == "node":
            return _node_result()
        if resource in {"namespaces", "persistentvolumeclaims", "persistentvolumes"}:
            return self._success({"apiVersion": "v1", "kind": "List", "items": []})
        if resource == "job":
            name = command[command.index("get") + 2]
            if "--ignore-not-found=true" in command:
                if self.fail_operation == "post-delete" and name in self.deleted:
                    return self._failure()
                if name in self.deleted or name not in self.manifests:
                    return self._success()
                job, _ = _runtime_objects(self.manifests[name], self.image)
                return self._success(job)
            if self.fail_operation == "get-job":
                return self._failure()
            manifest = self.manifests[name]
            job, _ = _runtime_objects(manifest, self.image)
            return self._success(job)
        if resource == "pods":
            selector = (
                command[command.index("--selector") + 1]
                if "--selector" in command
                else None
            )
            names = [
                name for name in self.manifests if name not in self.deleted
            ]
            if selector is not None:
                job_names = [
                    value.split("=", 1)[1]
                    for value in selector.split(",")
                    if value.startswith(
                        ("job-name=", "batch.kubernetes.io/job-name=")
                    )
                ]
                if job_names:
                    names = [name for name in names if name == job_names[0]]
            if not names:
                if self.fail_operation == "post-delete-pods":
                    return self._failure()
                return self._success(
                    {"apiVersion": "v1", "kind": "PodList", "items": []}
                )
            if self.fail_operation == "get-pods":
                return self._failure()
            pods = {"apiVersion": "v1", "kind": "PodList", "items": []}
            for name in names:
                _, runtime_pods = _runtime_objects(
                    self.manifests[name], self.image
                )
                pods["items"].extend(runtime_pods["items"])
            if (
                self.fail_operation == "logs-replacement"
                and self.logs_read
                and pods["items"]
            ):
                pods["items"][0]["metadata"]["uid"] = "replacement-pod-uid"
            return self._success(pods)
        raise AssertionError(command)


def _orchestration_inputs(tmp_path: Path) -> tuple[object, object, object, Path, Path]:
    profile, _, _ = _profile(tmp_path)
    image, _ = _image_inventory(tmp_path)
    resources = MODULE._load_execution_resource_binding(
        profile=profile, snapshot_binding=_execution_binding()
    )
    kubeconfig = _kubeconfig(tmp_path)
    evidence = tmp_path / "reset" / COMMIT / RUN_ID
    for directory in (tmp_path / "reset", tmp_path / "reset" / COMMIT, evidence):
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
    return profile, image, resources, kubeconfig, evidence


def test_cleanup_and_verify_use_distinct_jobs_read_only_verify_and_final_absence(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)

    result = MODULE._cleanup_and_verify_backend(
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=targets,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        evidence_directory=evidence,
        runner=cluster,
    )

    assert result["schemaVersion"] == "aileron-backend-attestation/v1"
    assert result["absent"] is True
    assert result["cleanup"]["observation"]["state"] == "absent"
    assert result["verification"]["observation"]["state"] == "absent"
    assert result["trustBoundary"] == {
        "atomicWithPersistentVolumeInventory": False,
        "exclusiveOperationalControlRequired": True,
        "postDeleteCollisionChecks": True,
        "description": MODULE.BACKEND_CLEANUP_TRUST_BOUNDARY,
    }
    assert len(cluster.manifests) == 2
    cleanup = next(
        item
        for item in cluster.manifests.values()
        if item["metadata"]["labels"]["platform.aileron.dev/backend-action"]
        == "cleanup"
    )
    verification = next(
        item
        for item in cluster.manifests.values()
        if item["metadata"]["labels"]["platform.aileron.dev/backend-action"] == "verify"
    )
    assert cleanup["metadata"]["name"] != verification["metadata"]["name"]
    cleanup_mount = cleanup["spec"]["template"]["spec"]["containers"][0][
        "volumeMounts"
    ][0]
    verification_mount = verification["spec"]["template"]["spec"]["containers"][0][
        "volumeMounts"
    ][0]
    assert cleanup_mount["readOnly"] is False
    assert verification_mount["readOnly"] is True
    assert cluster.deleted == set(cluster.manifests)
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in evidence.iterdir())
    assert MODULE.validate_backend_attestation(
        result,
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_sha256="8" * 64,
        evidence_directory=evidence,
    ) == result

    tampered = copy.deepcopy(result)
    tampered["verification"]["imageInventorySha256"] = "f" * 64
    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.validate_backend_attestation(
            tampered,
            locator=LOCAL_LOCATOR,
            run_id=RUN_ID,
            snapshot_sha256="8" * 64,
            evidence_directory=evidence,
        )


def test_target_result_aggregate_is_strict_and_post_reset_api_only_runs_verify(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, reset_directory = _orchestration_inputs(
        tmp_path
    )
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    inputs = MODULE.SignedBackendAttestorInputs(
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=(target,),
        snapshot_sha256="8" * 64,
        run_id=RUN_ID,
        commit=COMMIT,
        context=CONTEXT,
        kubeconfig=kubeconfig,
        private_root=tmp_path,
        _token=MODULE._SIGNED_INPUTS_TOKEN,
    )
    cluster = _FakeAttestorCluster(image=image)

    target_result = MODULE._execute_signed_backend_cleanup_target(
        inputs,
        persistent_volume_name=target.persistent_volume_name,
        persistent_volume_uid=target.persistent_volume_uid,
        runner=cluster,
    )
    aggregate = {
        "schemaVersion": "aileron-backend-cleanup-results/v1",
        "commit": inputs.commit,
        "runId": inputs.run_id,
        "snapshotSha256": inputs.snapshot_sha256,
        "profileRawSha256": inputs.profile.raw_sha256,
        "profileCanonicalSha256": inputs.profile.canonical_sha256,
        "imageInventorySha256": inputs.image.inventory_sha256,
        "results": [target_result],
        "allAbsent": target_result["attestation"]["absent"],
    }

    assert MODULE.validate_backend_cleanup_results(
        aggregate, inputs=inputs
    ) == aggregate
    assert aggregate["results"][0]["persistentVolume"] == {
        "name": "workspace-pv",
        "uid": "workspace-pv-uid",
    }
    assert aggregate["results"][0]["locatorSha256"] == MODULE.locator_sha256(
        LOCAL_LOCATOR
    )
    tampered = copy.deepcopy(aggregate)
    tampered["results"][0]["verificationResultSha256"] = "f" * 64
    with pytest.raises(MODULE.BackendAttestorError, match="digest"):
        MODULE.validate_backend_cleanup_results(tampered, inputs=inputs)

    MODULE.PRIVATE_INPUT.write_private_snapshot(
        destination=reset_directory / "backend-cleanup-results.json",
        content=_canonical(aggregate) + b"\n",
        description="backend cleanup aggregate",
        private_root=tmp_path,
    )
    acceptance_directory = tmp_path / "evidence" / COMMIT / RUN_ID
    for directory in (
        tmp_path / "evidence",
        tmp_path / "evidence" / COMMIT,
        acceptance_directory,
    ):
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)

    verification_cluster = _FakeAttestorCluster(image=image)
    post_reset = MODULE._verify_signed_backend_absence(
        inputs, runner=verification_cluster
    )
    rerun_post_reset = MODULE._verify_signed_backend_absence(
        inputs, runner=_FakeAttestorCluster(image=image)
    )

    assert post_reset["allAbsent"] is True
    assert len(post_reset["verifications"]) == 1
    assert rerun_post_reset == post_reset
    assert MODULE.validate_backend_post_reset_verification(
        post_reset, inputs=inputs
    ) == post_reset
    tampered_verification = copy.deepcopy(post_reset)
    tampered_verification["verifications"][0]["verificationResultSha256"] = (
        "f" * 64
    )
    with pytest.raises(MODULE.BackendAttestorError, match="digest"):
        MODULE.validate_backend_post_reset_verification(
            tampered_verification, inputs=inputs
        )
    assert all(
        manifest["metadata"]["labels"]["platform.aileron.dev/backend-action"]
        == "verify"
        for path, manifest in (
            (path, json.loads(path.read_text()))
            for path in acceptance_directory.glob("*.json")
        )
    )
    public_parameters = inspect.signature(
        MODULE.execute_signed_backend_cleanup_target
    ).parameters
    assert "locator" not in public_parameters
    assert "runner" not in public_parameters


def test_verify_present_fails_after_both_jobs_are_deleted(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image, verify_state="present")

    with pytest.raises(MODULE.BackendAttestorError, match="verification.*present"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=cluster,
        )

    assert cluster.deleted == set(cluster.manifests)


def test_cleanup_rechecks_pv_rebind_immediately_before_job_create(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    pv_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal pv_queries
        if (
            "get" in command
            and command[command.index("get") + 1] == "persistentvolumes"
        ):
            pv_queries += 1
            if pv_queries == 2:
                cluster.commands.append(command)
                return MODULE.CommandResult(
                    _canonical(
                        {
                            "apiVersion": "v1",
                            "kind": "List",
                            "items": [
                                {
                                    "apiVersion": "v1",
                                    "kind": "PersistentVolume",
                                    "metadata": {
                                        "name": "raced-rebound-pv",
                                        "uid": "raced-pv-uid",
                                    },
                                    "spec": {
                                        "local": {"path": LOCAL_LOCATOR["path"]},
                                        "nodeAffinity": _local_node_affinity(),
                                    },
                                }
                            ],
                        }
                    ),
                    b"",
                    0,
                )
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError, match="backend.*rebound"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert pv_queries == 2
    assert not any("create" in command for command in cluster.commands)


@pytest.mark.parametrize("replacement", ("node", "namespace", "secret"))
def test_cleanup_rechecks_execution_identity_after_final_pv_refresh_before_create(
    tmp_path: Path, replacement: str
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    pv_queries = 0
    replacement_active = False

    def runner(command: list[str]) -> object:
        nonlocal pv_queries, replacement_active
        if "get" in command:
            resource = command[command.index("get") + 1]
            if resource == "persistentvolumes":
                pv_queries += 1
                if pv_queries == 2:
                    replacement_active = True
            if replacement_active and resource == replacement:
                if replacement == "node":
                    return _node_result(uid="replacement-node-uid")
                if replacement == "namespace":
                    return _namespace_result(uid="replacement-namespace-uid")
                return _secret_result(uid="replacement-secret-uid")
        return cluster(command)

    expected = {
        "node": "Node identity",
        "namespace": "Namespace identity",
        "secret": "Secret identity",
    }[replacement]
    with pytest.raises(MODULE.BackendAttestorError, match=expected):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert pv_queries == 2
    assert not any("create" in command for command in cluster.commands)


def test_cleanup_rechecks_execution_identity_after_probe_before_accepting_result(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    logs_observed = False
    pv_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal logs_observed, pv_queries
        if (
            "get" in command
            and command[command.index("get") + 1] == "persistentvolumes"
        ):
            pv_queries += 1
        if "logs" in command:
            logs_observed = True
        if (
            logs_observed
            and "get" in command
            and command[command.index("get") + 1] == "node"
        ):
            return _node_result(uid="replacement-node-uid")
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError, match="Node identity"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert len(cluster.manifests) == 1
    assert cluster.deleted == set(cluster.manifests)
    assert pv_queries == 2


def test_post_cleanup_pv_rebind_is_detected_without_claiming_data_recovery(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    pv_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal pv_queries
        if (
            "get" in command
            and command[command.index("get") + 1] == "persistentvolumes"
        ):
            pv_queries += 1
            if pv_queries == 3:
                cluster.commands.append(command)
                return MODULE.CommandResult(
                    _canonical(
                        {
                            "apiVersion": "v1",
                            "kind": "List",
                            "items": [
                                {
                                    "apiVersion": "v1",
                                    "kind": "PersistentVolume",
                                    "metadata": {
                                        "name": "post-delete-rebound-pv",
                                        "uid": "post-delete-pv-uid",
                                    },
                                    "spec": {
                                        "hostPath": {"path": LOCAL_LOCATOR["path"]},
                                        "nodeAffinity": _local_node_affinity(),
                                    },
                                }
                            ],
                        }
                    ),
                    b"",
                    0,
                )
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError, match="backend.*rebound"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert pv_queries == 3
    assert len(cluster.manifests) == 1
    assert cluster.deleted == set(cluster.manifests)
    assert "execution Namespace" in MODULE.BACKEND_CLEANUP_TRUST_BOUNDARY
    assert "image pull Secret" in MODULE.BACKEND_CLEANUP_TRUST_BOUNDARY
    assert "local-path Node identity" in MODULE.BACKEND_CLEANUP_TRUST_BOUNDARY
    assert "backend deletion are not atomic" in MODULE.BACKEND_CLEANUP_TRUST_BOUNDARY


@pytest.mark.parametrize(
    "operation",
    (
        "create",
        "create-spec-drift",
        "wait",
        "get-job",
        "get-pods",
        "logs",
        "logs-json",
        "logs-replacement",
        "delete",
        "post-delete",
        "post-delete-pods",
    ),
)
def test_job_operation_failure_is_not_hidden_and_final_cleanup_is_attempted(
    tmp_path: Path, operation: str
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    targets = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image, fail_operation=operation)

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=targets,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=cluster,
        )

    assert any("delete" in command for command in cluster.commands)
    assert not any(
        manifest["metadata"]["labels"]["platform.aileron.dev/backend-action"]
        == "verify"
        for manifest in cluster.manifests.values()
    )


def test_final_cleanup_rejects_residual_owned_pod_after_all_labels_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    monkeypatch.setattr(MODULE, "JOB_DELETE_POLL_ATTEMPTS", 2)
    monkeypatch.setattr(MODULE, "JOB_DELETE_POLL_INTERVAL_SECONDS", 0)

    def runner(command: list[str]) -> object:
        if (
            "get" in command
            and command[command.index("get") + 1] == "pods"
            and cluster.deleted
            and "--selector" not in command
        ):
            cluster.commands.append(command)
            name = next(iter(cluster.deleted))
            _, pods = _runtime_objects(cluster.manifests[name], image)
            pods["items"][0]["metadata"]["labels"] = {"drifted": "true"}
            return MODULE.CommandResult(_canonical(pods), b"", 0)
        if (
            "get" in command
            and command[command.index("get") + 1] == "pods"
            and cluster.deleted
            and "--selector" in command
            and command[command.index("--selector") + 1].startswith(
                "batch.kubernetes.io/"
            )
        ):
            cluster.commands.append(command)
            return MODULE.CommandResult(
                _canonical({"apiVersion": "v1", "kind": "PodList", "items": []}),
                b"",
                0,
            )
        return cluster(command)

    with pytest.raises(
        MODULE.BackendAttestorError, match="Job or Pod deletion did not complete"
    ):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    selectors = {
        command[command.index("--selector") + 1]
        for command in cluster.commands
        if "get" in command
        and command[command.index("get") + 1] == "pods"
        and "--selector" in command
    }
    assert "batch.kubernetes.io/controller-uid=job-uid" in selectors
    assert any(
        selector.startswith("batch.kubernetes.io/job-name=")
        for selector in selectors
    )
    assert any(
        "get" in command
        and command[command.index("get") + 1] == "pods"
        and "--selector" not in command
        for command in cluster.commands
    )


def test_invalid_create_response_retries_transient_final_get_and_deletes_owned_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    final_get_attempts = 0
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_ATTEMPTS", 2)
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_INTERVAL_SECONDS", 0)

    def runner(command: list[str]) -> object:
        nonlocal final_get_attempts
        if "create" in command:
            cluster(command)
            return MODULE.CommandResult(b"not-json", b"", 0)
        if (
            "get" in command
            and command[command.index("get") + 1] == "job"
            and "--ignore-not-found=true" in command
            and cluster.manifests
            and not cluster.deleted
        ):
            final_get_attempts += 1
            if final_get_attempts == 1:
                cluster.commands.append(command)
                return MODULE.CommandResult(b"", b"transient", 1)
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError) as error:
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert "create response identity is invalid JSON" in str(error.value)
    assert "finalCleanup" not in str(error.value)
    assert final_get_attempts >= 2
    assert cluster.deleted == set(cluster.manifests)


def test_invalid_create_response_retries_invalid_final_job_json_before_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    final_get_attempts = 0
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_ATTEMPTS", 2)
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_INTERVAL_SECONDS", 0)

    def runner(command: list[str]) -> object:
        nonlocal final_get_attempts
        if "create" in command:
            cluster(command)
            return MODULE.CommandResult(b"not-json", b"", 0)
        if (
            "get" in command
            and command[command.index("get") + 1] == "job"
            and "--ignore-not-found=true" in command
            and cluster.manifests
            and not cluster.deleted
        ):
            final_get_attempts += 1
            if final_get_attempts == 1:
                cluster.commands.append(command)
                return MODULE.CommandResult(b"invalid-json", b"", 0)
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError) as error:
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert "create response identity is invalid JSON" in str(error.value)
    assert "finalCleanup" not in str(error.value)
    assert final_get_attempts == 2
    assert cluster.deleted == set(cluster.manifests)


def test_unexpected_primary_and_cleanup_failure_are_safely_aggregated(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image, fail_operation="delete")
    malformed_sent = False

    def runner(command: list[str]) -> object:
        nonlocal malformed_sent
        if (
            not malformed_sent
            and "get" in command
            and command[command.index("get") + 1] == "pods"
        ):
            malformed_sent = True
            cluster.commands.append(command)
            return MODULE.CommandResult(
                _canonical(["private-marker-must-not-leak"]), b"", 0
            )
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError) as error:
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    message = str(error.value)
    assert '"phase":"primary"' in message
    assert "unexpected AttributeError" in message
    assert '"phase":"finalCleanup"' in message
    assert "preconditioned Job delete outcome is ambiguous" in message
    assert "private-marker-must-not-leak" not in message


def test_failed_job_retry_reuses_only_byte_exact_private_manifest(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    with pytest.raises(MODULE.BackendAttestorError):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=_FakeAttestorCluster(image=image, fail_operation="wait"),
        )

    result = MODULE._cleanup_and_verify_backend(
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=target,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        evidence_directory=evidence,
        runner=_FakeAttestorCluster(image=image),
    )
    assert result["absent"] is True


def test_existing_manifest_must_be_private_and_byte_exact(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    document = {"schemaVersion": "test/v1", "value": "fixed"}
    first = MODULE._write_private_manifest(
        path, document, private_root=tmp_path
    )
    second = MODULE._write_private_manifest(
        path, document, private_root=tmp_path
    )
    assert second == first

    with pytest.raises(ValueError, match="content changed"):
        MODULE._write_private_manifest(
            path,
            {"schemaVersion": "test/v1", "value": "replacement"},
            private_root=tmp_path,
        )


def test_job_replacement_before_delete_is_not_deleted_by_name(
    tmp_path: Path,
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)

    def runner(command: list[str]) -> object:
        if (
            "get" in command
            and command[command.index("get") + 1] == "job"
            and "--ignore-not-found=true" in command
            and cluster.manifests
        ):
            cluster.commands.append(command)
            manifest = next(iter(cluster.manifests.values()))
            replacement, _ = _runtime_objects(manifest, image)
            replacement["metadata"]["uid"] = "replacement-job-uid"
            replacement["spec"]["selector"]["matchLabels"][
                "batch.kubernetes.io/controller-uid"
            ] = "replacement-job-uid"
            labels = replacement["spec"]["template"]["metadata"]["labels"]
            labels["batch.kubernetes.io/controller-uid"] = "replacement-job-uid"
            labels["controller-uid"] = "replacement-job-uid"
            return MODULE.CommandResult(_canonical(replacement), b"", 0)
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError, match="replaced before deletion"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )
    assert not any("delete" in command for command in cluster.commands)


def test_job_delete_uses_uid_and_resource_version_preconditions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    deletes: list[dict] = []

    class RecordingClient(_FakeDeleteClient):
        def delete(self, **arguments) -> None:
            deletes.append(arguments)
            super().delete(**arguments)

    monkeypatch.setattr(
        MODULE,
        "_load_job_delete_client",
        lambda **arguments: RecordingClient(arguments["runner"]),
    )
    MODULE._cleanup_and_verify_backend(
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=target,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        evidence_directory=evidence,
        runner=cluster,
    )

    assert len(deletes) == 2
    assert all(item["uid"] == "job-uid" for item in deletes)
    assert all(item["resource_version"] == "701" for item in deletes)
    assert all(item["api_version"] == "batch/v1" for item in deletes)


def test_accepted_delete_with_client_error_reconciles_to_final_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    delete_calls: list[dict] = []
    ambiguous = True
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_INTERVAL_SECONDS", 0)

    class AcceptedButAmbiguousClient(_FakeDeleteClient):
        def delete(self, **arguments) -> None:
            nonlocal ambiguous
            delete_calls.append(arguments)
            if ambiguous:
                ambiguous = False
                super().delete(**arguments)
                raise TimeoutError("private-delete-timeout")
            super().delete(**arguments)

    monkeypatch.setattr(
        MODULE,
        "_load_job_delete_client",
        lambda **arguments: AcceptedButAmbiguousClient(arguments["runner"]),
    )

    result = MODULE._cleanup_and_verify_backend(
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=target,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        evidence_directory=evidence,
        runner=cluster,
    )

    assert result["absent"] is True
    assert len(delete_calls) == 2
    assert cluster.deleted == set(cluster.manifests)


def test_unaccepted_delete_with_client_error_retries_preconditioned_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    delete_calls: list[dict] = []
    ambiguous = True
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_INTERVAL_SECONDS", 0)

    class UnacceptedThenSuccessfulClient(_FakeDeleteClient):
        def delete(self, **arguments) -> None:
            nonlocal ambiguous
            delete_calls.append(arguments)
            if ambiguous:
                ambiguous = False
                raise TimeoutError("private-delete-timeout")
            super().delete(**arguments)

    monkeypatch.setattr(
        MODULE,
        "_load_job_delete_client",
        lambda **arguments: UnacceptedThenSuccessfulClient(arguments["runner"]),
    )

    result = MODULE._cleanup_and_verify_backend(
        locator=LOCAL_LOCATOR,
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=target,
        kubeconfig=kubeconfig,
        context=CONTEXT,
        run_id=RUN_ID,
        evidence_directory=evidence,
        runner=cluster,
    )

    assert result["absent"] is True
    assert len(delete_calls) == 3
    assert delete_calls[0]["uid"] == delete_calls[1]["uid"] == "job-uid"
    assert cluster.deleted == set(cluster.manifests)


def test_foreign_transaction_job_fails_immediately_without_delete_or_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, image, resources, kubeconfig, evidence = _orchestration_inputs(tmp_path)
    target = MODULE._load_cleanup_target_binding(
        locator=LOCAL_LOCATOR,
        run_id=RUN_ID,
        snapshot_binding=_cleanup_binding(),
    )
    cluster = _FakeAttestorCluster(image=image)
    identity_queries = 0
    monkeypatch.setattr(MODULE, "JOB_RECONCILE_INTERVAL_SECONDS", 0)

    def runner(command: list[str]) -> object:
        nonlocal identity_queries
        if "create" in command:
            cluster(command)
            return MODULE.CommandResult(b"invalid-json", b"", 0)
        if (
            "get" in command
            and command[command.index("get") + 1] == "job"
            and "--ignore-not-found=true" in command
            and cluster.manifests
        ):
            identity_queries += 1
            cluster.commands.append(command)
            manifest = next(iter(cluster.manifests.values()))
            foreign, _ = _runtime_objects(manifest, image)
            foreign["metadata"]["annotations"][
                "platform.aileron.dev/job-transaction-token"
            ] = "foreign-token"
            return MODULE.CommandResult(_canonical(foreign), b"", 0)
        return cluster(command)

    with pytest.raises(MODULE.BackendAttestorError, match="cleanup identity"):
        MODULE._cleanup_and_verify_backend(
            locator=LOCAL_LOCATOR,
            profile=profile,
            image=image,
            execution_resources=resources,
            cleanup_targets=target,
            kubeconfig=kubeconfig,
            context=CONTEXT,
            run_id=RUN_ID,
            evidence_directory=evidence,
            runner=runner,
        )

    assert identity_queries == 1
    assert not any("delete" in command for command in cluster.commands)


def test_foreground_job_delete_polls_through_terminating_workload() -> None:
    job_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal job_queries
        if command == ["get", "job"]:
            job_queries += 1
            if job_queries < 3:
                return MODULE.CommandResult(
                    _canonical(
                        {
                            "metadata": {
                                "uid": "job-uid",
                                "deletionTimestamp": "2026-08-10T00:00:00Z",
                            }
                        }
                    ),
                    b"",
                    0,
                )
            return MODULE.CommandResult(b"", b"", 0)
        items = [] if job_queries >= 3 else [{"metadata": {"uid": "pod-uid"}}]
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "PodList", "items": items}),
            b"",
            0,
        )

    MODULE._poll_owned_workload_absent(
        runner=runner,
        job_command=["get", "job"],
        controller_pods_command=["get", "controller-pods"],
        job_name_pods_command=["get", "job-name-pods"],
        all_pods_command=["get", "all-pods"],
        expected_job_uid="job-uid",
        expected_job_name="attestor-job",
        sleeper=lambda _seconds: None,
    )
    assert job_queries == 4


def test_foreground_job_delete_times_out_when_owned_workload_never_disappears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "JOB_DELETE_POLL_ATTEMPTS", 3)

    def runner(command: list[str]) -> object:
        if command == ["get", "job"]:
            return MODULE.CommandResult(
                _canonical({"metadata": {"uid": "job-uid"}}), b"", 0
            )
        return MODULE.CommandResult(
            _canonical(
                {
                    "apiVersion": "v1",
                    "kind": "PodList",
                    "items": [{"metadata": {"uid": "pod-uid"}}],
                }
            ),
            b"",
            0,
        )

    with pytest.raises(MODULE.BackendAttestorError, match="did not complete"):
        MODULE._poll_owned_workload_absent(
            runner=runner,
            job_command=["get", "job"],
            controller_pods_command=["get", "controller-pods"],
            job_name_pods_command=["get", "job-name-pods"],
            all_pods_command=["get", "all-pods"],
            expected_job_uid="job-uid",
            expected_job_name="attestor-job",
            sleeper=lambda _seconds: None,
        )


def test_foreground_job_delete_rejects_replacement_after_empty_pod_query() -> None:
    job_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal job_queries
        if command == ["get", "job"]:
            job_queries += 1
            if job_queries == 1:
                return MODULE.CommandResult(b"", b"", 0)
            return MODULE.CommandResult(
                _canonical({"metadata": {"uid": "replacement-job-uid"}}),
                b"",
                0,
            )
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "PodList", "items": []}),
            b"",
            0,
        )

    with pytest.raises(MODULE.BackendAttestorError, match="replaced during deletion"):
        MODULE._poll_owned_workload_absent(
            runner=runner,
            job_command=["get", "job"],
            controller_pods_command=["get", "controller-pods"],
            job_name_pods_command=["get", "job-name-pods"],
            all_pods_command=["get", "all-pods"],
            expected_job_uid="job-uid",
            expected_job_name="attestor-job",
            sleeper=lambda _seconds: None,
        )


def test_foreground_job_delete_retries_invalid_job_json_before_absence() -> None:
    job_queries = 0

    def runner(command: list[str]) -> object:
        nonlocal job_queries
        if command == ["get", "job"]:
            job_queries += 1
            if job_queries == 1:
                return MODULE.CommandResult(b"invalid-json", b"", 0)
            return MODULE.CommandResult(b"", b"", 0)
        return MODULE.CommandResult(
            _canonical({"apiVersion": "v1", "kind": "PodList", "items": []}),
            b"",
            0,
        )

    MODULE._poll_owned_workload_absent(
        runner=runner,
        job_command=["get", "job"],
        controller_pods_command=["get", "controller-pods"],
        job_name_pods_command=["get", "job-name-pods"],
        all_pods_command=["get", "all-pods"],
        expected_job_uid="job-uid",
        expected_job_name="attestor-job",
        sleeper=lambda _seconds: None,
    )

    assert job_queries == 3


@pytest.mark.parametrize("root_kind", ("List", "PodList"))
def test_runtime_identity_accepts_portable_pod_inventory_root_kinds(
    tmp_path: Path,
    root_kind: str,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    pods["kind"] = root_kind

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance["podUid"] == "pod-uid"


def test_runtime_identity_rejects_arbitrary_pod_inventory_root_kind(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    pods["kind"] = "ArbitraryList"

    with pytest.raises(
        MODULE.BackendAttestorError, match="must have one owned Pod"
    ):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


def test_runtime_identity_requires_exact_job_owner_pod_spec_and_image_id(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance == {
        "jobUid": "job-uid",
        "podName": pods["items"][0]["metadata"]["name"],
        "podUid": "pod-uid",
        "imageId": "docker-pullable://" + IMAGE,
    }

    pods["items"][0]["status"]["containerStatuses"][0]["imageID"] = IMAGE
    containerd_provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )
    assert containerd_provenance["imageId"] == IMAGE

    pods["items"][0]["status"]["containerStatuses"][0]["imageID"] = (
        "docker-pullable://" + RUNTIME_IMAGE
    )
    runtime_provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )
    assert runtime_provenance["imageId"] == "docker-pullable://" + RUNTIME_IMAGE

    runtime_digest = RUNTIME_IMAGE.rsplit("@", 1)[1]
    pods["items"][0]["status"]["containerStatuses"][0]["imageID"] = (
        f"docker-pullable://attacker.invalid/unrelated@{runtime_digest}"
    )
    with pytest.raises(MODULE.BackendAttestorError, match="provenance is invalid"):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


def test_runtime_identity_accepts_rke2_digest_only_status_image(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    pods["items"][0]["status"]["containerStatuses"][0]["image"] = (
        "sha256:" + "a" * 64
    )

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance["imageId"] == "docker-pullable://" + IMAGE


def test_runtime_identity_accepts_kubernetes_omitted_false_pod_defaults(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    for document in (job["spec"]["template"], pods["items"][0]):
        for key in ("hostIPC", "hostNetwork", "hostPID"):
            document["spec"].pop(key)

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance["jobUid"] == "job-uid"


def test_runtime_identity_accepts_rke2_omitted_false_volume_mount_read_only(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path, action="cleanup")
    job, pods = _runtime_objects(manifest, image)
    for document in (job["spec"]["template"], pods["items"][0]):
        volume_mount = document["spec"]["containers"][0]["volumeMounts"][0]
        assert volume_mount.pop("readOnly") is False

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance["jobUid"] == "job-uid"


def test_runtime_identity_accepts_omitted_false_nfs_volume_read_only(
    tmp_path: Path,
) -> None:
    manifest, _, image, _ = _build_nfs_manifest(tmp_path, action="cleanup")
    job, pods = _runtime_objects(manifest, image)
    for document in (job["spec"]["template"], pods["items"][0]):
        nfs_source = document["spec"]["volumes"][0]["nfs"]
        assert nfs_source.pop("readOnly") is False

    provenance = MODULE.validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )

    assert provenance["jobUid"] == "job-uid"


@pytest.mark.parametrize("object_kind", ("job", "pod"))
@pytest.mark.parametrize(
    "actual_read_only",
    (None, False),
    ids=("omitted", "downgraded"),
)
def test_runtime_identity_rejects_omitted_or_downgraded_true_volume_mount_read_only(
    tmp_path: Path, object_kind: str, actual_read_only: bool | None
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    document = (
        job["spec"]["template"]
        if object_kind == "job"
        else pods["items"][0]
    )
    volume_mount = document["spec"]["containers"][0]["volumeMounts"][0]
    if actual_read_only is None:
        volume_mount.pop("readOnly")
    else:
        volume_mount["readOnly"] = actual_read_only

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


@pytest.mark.parametrize("object_kind", ("job", "pod"))
@pytest.mark.parametrize(
    "actual_read_only",
    (None, False),
    ids=("omitted", "downgraded"),
)
def test_runtime_identity_rejects_omitted_or_downgraded_true_nfs_volume_read_only(
    tmp_path: Path, object_kind: str, actual_read_only: bool | None
) -> None:
    manifest, _, image, _ = _build_nfs_manifest(tmp_path, action="verify")
    job, pods = _runtime_objects(manifest, image)
    document = (
        job["spec"]["template"]
        if object_kind == "job"
        else pods["items"][0]
    )
    nfs_source = document["spec"]["volumes"][0]["nfs"]
    if actual_read_only is None:
        nfs_source.pop("readOnly")
    else:
        nfs_source["readOnly"] = actual_read_only

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


@pytest.mark.parametrize(
    "mutation",
    ("extra-volume", "extra-source-key", "path", "server", "name", "non-nfs"),
)
def test_runtime_identity_rejects_unrelated_nfs_volume_drift(
    tmp_path: Path, mutation: str
) -> None:
    manifest, _, image, _ = _build_nfs_manifest(tmp_path, action="verify")
    job, pods = _runtime_objects(manifest, image)
    volumes = job["spec"]["template"]["spec"]["volumes"]
    if mutation == "extra-volume":
        volumes.append(copy.deepcopy(volumes[0]))
    elif mutation == "extra-source-key":
        volumes[0]["nfs"]["unexpected"] = "drift"
    elif mutation == "path":
        volumes[0]["nfs"]["path"] += "/drift"
    elif mutation == "server":
        volumes[0]["nfs"]["server"] = "192.168.50.101"
    elif mutation == "name":
        volumes[0]["name"] = "other"
    else:
        volumes[0].pop("nfs")
        volumes[0]["hostPath"] = {"path": "/var/lib/other"}

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "owner",
        "image",
        "spec",
        "multiple",
        "pod-default",
        "job-default",
        "image-pull-backoff",
    ),
)
def test_runtime_identity_rejects_unowned_wrong_image_or_extra_workload(
    tmp_path: Path, mutation: str
) -> None:
    manifest, _, image, _ = _build_local_manifest(tmp_path)
    job, pods = _runtime_objects(manifest, image)
    if mutation == "owner":
        pods["items"][0]["metadata"]["ownerReferences"][0]["uid"] = "wrong"
    elif mutation == "image":
        pods["items"][0]["status"]["containerStatuses"][0]["imageID"] = (
            "docker-pullable://harbor.rke.soez.tw/library/workspace-manager@sha256:"
            + "f" * 64
        )
    elif mutation == "spec":
        pods["items"][0]["spec"]["containers"].append(
            copy.deepcopy(pods["items"][0]["spec"]["containers"][0])
        )
    elif mutation == "multiple":
        pods["items"].append(copy.deepcopy(pods["items"][0]))
    elif mutation == "pod-default":
        pods["items"][0]["spec"]["hostUsers"] = False
    elif mutation == "job-default":
        job["spec"]["managedBy"] = "unapproved-controller"
    else:
        pods["items"][0]["status"]["phase"] = "Pending"
        pods["items"][0]["status"]["containerStatuses"][0]["state"] = {
            "waiting": {"reason": "ImagePullBackOff"}
        }

    with pytest.raises(MODULE.BackendAttestorError):
        MODULE.validate_attestor_job_identity(
            manifest=manifest, job=job, pods=pods, image=image
        )


def test_repo_contains_schema_and_non_runnable_example_only() -> None:
    assert not (ROOT / "deploy/rke2/backend-execution-profile-rke2-207.json").exists()
    schema = json.loads(
        (ROOT / "deploy/rke2/backend-execution-profile.schema.json").read_text()
    )
    example = json.loads(
        (ROOT / "deploy/rke2/backend-execution-profile.example.json").read_text()
    )
    assert schema["$id"].endswith("backend-execution-profile.schema.json")
    assert example["_comment"].startswith("NON-RUNNABLE")
    assert "REPLACE_WITH" in json.dumps(example)
