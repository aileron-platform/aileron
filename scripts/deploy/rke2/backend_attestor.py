#!/usr/bin/env python3
"""Build and validate fixed Kubernetes backend cleanup and absence attestors."""

from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import ipaddress
import json
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PROFILE_SCHEMA = "aileron-backend-execution-profile/v1"
PROFILE_BINDING_SCHEMA = "aileron-backend-execution-profile-binding/v1"
EXECUTION_RESOURCES_BINDING_SCHEMA = "aileron-backend-execution-resources-binding/v1"
CLEANUP_TARGET_BINDING_SCHEMA = "aileron-backend-cleanup-target-binding/v1"
BACKEND_ATTESTOR_SNAPSHOT_BINDING_SCHEMA = (
    "aileron-backend-attestor-snapshot-binding/v1"
)
PROFILE_KEYS = {
    "schemaVersion",
    "executionNamespace",
    "namespaceOwner",
    "imagePullSecret",
    "nfsMountRoots",
    "localPathNodes",
}
EXECUTION_NAMESPACE = "aileron-backend-attestor-system"
EXECUTION_NAMESPACE_OWNER = "aileron-installer"
EXECUTION_IMAGE_PULL_SECRET = "harbor-rke-creds"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
LABEL_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9](?:[-_.A-Za-z0-9]{0,61}[A-Za-z0-9])?$")
UID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[-_.A-Za-z0-9]{0,126}[A-Za-z0-9])?$")
PATH_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
IMMUTABLE_IMAGE_PATTERN = re.compile(r"^\S+@sha256:[0-9a-f]{64}$")
KUBERNETES_STATUS_IMAGE_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
KUBERNETES_OMITTED_FALSE_POD_DEFAULTS = frozenset(
    {"hostIPC", "hostNetwork", "hostPID"}
)
NFS_CSI_DRIVER = "nfs.csi.k8s.io"
MAX_PRIVATE_INPUT_BYTES = 1024 * 1024
JOB_DELETE_POLL_ATTEMPTS = 20
JOB_DELETE_POLL_INTERVAL_SECONDS = 0.5
JOB_RECONCILE_ATTEMPTS = 3
JOB_RECONCILE_INTERVAL_SECONDS = 0.5
BACKEND_CLEANUP_TRUST_BOUNDARY = (
    "Kubernetes PersistentVolume inventory, execution Namespace, image pull Secret, "
    "local-path Node identity, and backend deletion are not atomic; exclusive "
    "maintenance-window control is required, and repeated identity and post-delete "
    "checks can detect but cannot recover a concurrent cluster-admin replacement "
    "or rebind."
)
_PROFILE_TOKEN = object()
_IMAGE_TOKEN = object()
_EXECUTION_RESOURCES_TOKEN = object()
_CLEANUP_TARGET_TOKEN = object()
_CLEANUP_AUTHORIZATION_TOKEN = object()
_SIGNED_INPUTS_TOKEN = object()


class BackendAttestorError(RuntimeError):
    """Raised when a backend target or attestor identity is not trustworthy."""


class _JobIdentityConflictError(BackendAttestorError):
    """Raised when an exact-name Job belongs to another transaction."""


class CommandResult(NamedTuple):
    stdout: bytes
    stderr: bytes
    returncode: int


Runner = Callable[[list[str]], CommandResult]


def _load_private_input_module() -> Any:
    path = SCRIPT_DIRECTORY / "private_input.py"
    specification = importlib.util.spec_from_file_location(
        "backend_attestor_private_input", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("private input validator is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input_module()


def _load_local_module(name: str) -> Any:
    path = SCRIPT_DIRECTORY / f"{name}.py"
    specification = importlib.util.spec_from_file_location(
        f"backend_attestor_{name}", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"backend attestor dependency is unavailable: {name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ACCEPTANCE_CLUSTER = _load_local_module("acceptance_cluster")
ACCEPTANCE_SNAPSHOT = _load_local_module("acceptance_snapshot")
ACCEPTANCE_PRIVATE_IO = _load_local_module("acceptance_private_io")
KUBERNETES_REST = _load_local_module("kubernetes_rest")
RUN_ID_PATTERN = ACCEPTANCE_PRIVATE_IO.RUN_ID


class ExecutionProfile:
    """A mode-0600 profile proven equal to one signed snapshot binding."""

    __slots__ = (
        "path",
        "private_root",
        "document",
        "raw_sha256",
        "canonical_sha256",
    )

    def __init__(
        self,
        *,
        path: Path,
        private_root: Path,
        document: dict[str, Any],
        raw_sha256: str,
        canonical_sha256: str,
        _token: object,
    ) -> None:
        if _token is not _PROFILE_TOKEN:
            raise TypeError("ExecutionProfile must be loaded from a snapshot binding")
        self.path = path
        self.private_root = private_root
        self.document = copy.deepcopy(document)
        self.raw_sha256 = raw_sha256
        self.canonical_sha256 = canonical_sha256


class AttestorImage:
    """Workspace Manager identity loaded from the signed release inventory."""

    __slots__ = (
        "path",
        "private_root",
        "immutable_image",
        "runtime_immutable_image",
        "source_commit",
        "inventory_sha256",
        "_key",
        "_context",
        "_cluster_uid",
        "_installation_identity_sha256",
    )

    def __init__(
        self,
        *,
        path: Path,
        private_root: Path,
        immutable_image: str,
        runtime_immutable_image: str,
        source_commit: str,
        inventory_sha256: str,
        key: bytes,
        context: str,
        cluster_uid: str,
        installation_identity_sha256: str,
        _token: object,
    ) -> None:
        if _token is not _IMAGE_TOKEN:
            raise TypeError("AttestorImage must be loaded from a signed inventory")
        self.path = path
        self.private_root = private_root
        self.immutable_image = immutable_image
        self.runtime_immutable_image = runtime_immutable_image
        self.source_commit = source_commit
        self.inventory_sha256 = inventory_sha256
        self._key = key
        self._context = context
        self._cluster_uid = cluster_uid
        self._installation_identity_sha256 = installation_identity_sha256


class ExecutionResources:
    """Execution Namespace and pull Secret identities bound by the snapshot."""

    __slots__ = ("binding",)

    def __init__(self, *, binding: dict[str, Any], _token: object) -> None:
        if _token is not _EXECUTION_RESOURCES_TOKEN:
            raise TypeError("ExecutionResources must be loaded from a snapshot binding")
        self.binding = copy.deepcopy(binding)


class CleanupTargetBinding:
    """Exact Kubernetes resource target sets loaded from the signed snapshot."""

    __slots__ = (
        "snapshot_sha256",
        "run_id",
        "locator_sha256",
        "namespaces",
        "persistent_volume_claims",
        "persistent_volume_name",
        "persistent_volume_uid",
        "locator",
    )

    def __init__(
        self,
        *,
        snapshot_sha256: str,
        run_id: str,
        locator_digest: str,
        namespaces: tuple[str, ...],
        persistent_volume_claims: tuple[tuple[str, str], ...],
        persistent_volume_name: str,
        persistent_volume_uid: str,
        locator: dict[str, Any],
        _token: object,
    ) -> None:
        if _token is not _CLEANUP_TARGET_TOKEN:
            raise TypeError("CleanupTargetBinding must be loaded from a snapshot")
        self.snapshot_sha256 = snapshot_sha256
        self.run_id = run_id
        self.locator_sha256 = locator_digest
        self.namespaces = namespaces
        self.persistent_volume_claims = persistent_volume_claims
        self.persistent_volume_name = persistent_volume_name
        self.persistent_volume_uid = persistent_volume_uid
        self.locator = copy.deepcopy(locator)


class CleanupAuthorization:
    """A short-lived proof that every signed Kubernetes target is absent."""

    __slots__ = (
        "snapshot_sha256",
        "run_id",
        "locator_sha256",
        "kubeconfig",
        "context",
        "profile_raw_sha256",
        "profile_canonical_sha256",
        "binding",
        "used",
    )

    def __init__(
        self,
        *,
        binding: CleanupTargetBinding,
        profile: ExecutionProfile,
        kubeconfig: Path,
        context: str,
        _token: object,
    ) -> None:
        if _token is not _CLEANUP_AUTHORIZATION_TOKEN:
            raise TypeError("CleanupAuthorization must come from live absence queries")
        self.snapshot_sha256 = binding.snapshot_sha256
        self.run_id = binding.run_id
        self.locator_sha256 = binding.locator_sha256
        self.kubeconfig = kubeconfig
        self.context = context
        self.profile_raw_sha256 = profile.raw_sha256
        self.profile_canonical_sha256 = profile.canonical_sha256
        self.binding = binding
        self.used = False


class SignedBackendAttestorInputs:
    """All destructive backend inputs derived from one live-trusted snapshot."""

    __slots__ = (
        "profile",
        "image",
        "execution_resources",
        "cleanup_targets",
        "snapshot_sha256",
        "run_id",
        "commit",
        "context",
        "kubeconfig",
        "private_root",
    )

    def __init__(
        self,
        *,
        profile: ExecutionProfile,
        image: AttestorImage,
        execution_resources: ExecutionResources,
        cleanup_targets: tuple[CleanupTargetBinding, ...],
        snapshot_sha256: str,
        run_id: str,
        commit: str,
        context: str,
        kubeconfig: Path,
        private_root: Path,
        _token: object,
    ) -> None:
        if _token is not _SIGNED_INPUTS_TOKEN:
            raise TypeError(
                "SignedBackendAttestorInputs must come from live cluster trust"
            )
        self.profile = profile
        self.image = image
        self.execution_resources = execution_resources
        self.cleanup_targets = cleanup_targets
        self.snapshot_sha256 = snapshot_sha256
        self.run_id = run_id
        self.commit = commit
        self.context = context
        self.kubeconfig = kubeconfig
        self.private_root = private_root


def _canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def locator_sha256(locator: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(locator)).hexdigest()


def _required_dns_label(value: Any, description: str) -> str:
    if not isinstance(value, str) or DNS_LABEL_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{description} is invalid")
    return value


def _required_dns_subdomain(value: Any, description: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 253
        or any(
            DNS_LABEL_PATTERN.fullmatch(segment) is None for segment in value.split(".")
        )
    ):
        raise ValueError(f"{description} is invalid")
    return value


def _required_label_value(value: Any, description: str) -> str:
    if not isinstance(value, str) or LABEL_VALUE_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{description} is invalid")
    return value


def _required_uid(value: Any, description: str) -> str:
    if not isinstance(value, str) or UID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{description} is invalid")
    return value


def _absolute_path(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise ValueError(f"{description} is invalid")
    path = PurePosixPath(value)
    if str(path) != value.rstrip("/") or any(
        part in {"", ".", ".."} or PATH_COMPONENT_PATTERN.fullmatch(part) is None
        for part in path.parts[1:]
    ):
        raise ValueError(f"{description} is invalid")
    return str(path)


def _strict_relative_path(target: str, root: str) -> str | None:
    try:
        relative = PurePosixPath(target).relative_to(PurePosixPath(root))
    except ValueError:
        return None
    if str(relative) in {"", "."}:
        return None
    return str(relative)


def _assert_disjoint_roots(roots: list[str], description: str) -> None:
    for index, root in enumerate(roots):
        for other in roots[index + 1 :]:
            if (
                root == other
                or _strict_relative_path(root, other) is not None
                or _strict_relative_path(other, root) is not None
            ):
                raise ValueError(f"{description} roots overlap")


def _validate_profile(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != PROFILE_KEYS:
        raise ValueError("backend execution profile shape is invalid")
    if document.get("schemaVersion") != PROFILE_SCHEMA:
        raise ValueError("backend execution profile schema is invalid")
    _required_dns_label(document.get("executionNamespace"), "execution namespace")
    _required_label_value(document.get("namespaceOwner"), "namespace owner")
    _required_dns_subdomain(document.get("imagePullSecret"), "image pull Secret")
    if (
        document["executionNamespace"] != EXECUTION_NAMESPACE
        or document["namespaceOwner"] != EXECUTION_NAMESPACE_OWNER
        or document["imagePullSecret"] != EXECUTION_IMAGE_PULL_SECRET
    ):
        raise ValueError("backend execution profile identity is not fixed")
    nfs_roots = document.get("nfsMountRoots")
    local_nodes = document.get("localPathNodes")
    if not isinstance(nfs_roots, list) or not isinstance(local_nodes, list):
        raise ValueError("backend execution profile roots must be arrays")

    normalized_nfs: list[dict[str, str]] = []
    for item in nfs_roots:
        if not isinstance(item, dict) or set(item) != {"server", "path"}:
            raise ValueError("NFS execution root is malformed")
        server = item.get("server")
        if not isinstance(server, str):
            raise ValueError("NFS execution server is invalid")
        try:
            parsed_ip = ipaddress.ip_address(server)
        except ValueError as exc:
            raise ValueError(
                "NFS execution server must use a pinned IP address"
            ) from exc
        if not isinstance(parsed_ip, ipaddress.IPv4Address) or str(parsed_ip) != server:
            raise ValueError("NFS execution server must use a canonical pinned IPv4")
        normalized_nfs.append(
            {"server": server, "path": _absolute_path(item.get("path"), "NFS root")}
        )

    normalized_nodes: list[dict[str, Any]] = []
    for item in local_nodes:
        if not isinstance(item, dict) or set(item) != {
            "hostname",
            "nodeUid",
            "mountRoots",
        }:
            raise ValueError("local-path execution node is malformed")
        hostname = _required_dns_subdomain(item.get("hostname"), "local-path hostname")
        node_uid = _required_uid(item.get("nodeUid"), "local-path Node UID")
        mount_roots = item.get("mountRoots")
        if not isinstance(mount_roots, list) or not mount_roots:
            raise ValueError("local-path mount roots must be a non-empty array")
        normalized_roots = [
            _absolute_path(root, "local-path root") for root in mount_roots
        ]
        _assert_disjoint_roots(normalized_roots, "local-path")
        normalized_nodes.append(
            {
                "hostname": hostname,
                "nodeUid": node_uid,
                "mountRoots": normalized_roots,
            }
        )

    if not normalized_nfs and not normalized_nodes:
        raise ValueError("backend execution profile has no approved backend")
    nfs_by_server: dict[str, list[str]] = {}
    for root in normalized_nfs:
        nfs_by_server.setdefault(root["server"], []).append(root["path"])
    for roots in nfs_by_server.values():
        _assert_disjoint_roots(roots, "NFS")
    hostnames = [item["hostname"] for item in normalized_nodes]
    node_uids = [item["nodeUid"] for item in normalized_nodes]
    if len(hostnames) != len(set(hostnames)) or len(node_uids) != len(set(node_uids)):
        raise ValueError("local-path execution Nodes must have unique identities")
    normalized = {
        **document,
        "nfsMountRoots": normalized_nfs,
        "localPathNodes": normalized_nodes,
    }
    if normalized != document:
        raise ValueError("backend execution profile is not canonical")
    return normalized


def inspect_execution_profile(
    path: Path, *, private_root: Path
) -> dict[str, Any]:
    """Return the exact material which the signed reset snapshot must bind."""

    raw = PRIVATE_INPUT.read_private_bytes(
        path,
        "backend execution profile",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("backend execution profile is invalid JSON") from exc
    document = _validate_profile(document)
    canonical = _canonical(document)
    if raw != canonical + b"\n":
        raise ValueError("backend execution profile is not canonical serialized JSON")
    return {
        "schemaVersion": PROFILE_BINDING_SCHEMA,
        "rawSha256": hashlib.sha256(raw).hexdigest(),
        "canonicalSha256": hashlib.sha256(canonical).hexdigest(),
        "profile": document,
    }


def _validate_execution_profile_binding_document(
    binding: Any,
) -> dict[str, Any]:
    if not isinstance(binding, Mapping):
        raise ValueError("backend execution profile snapshot binding is invalid")
    normalized = copy.deepcopy(dict(binding))
    if (
        set(normalized)
        != {"schemaVersion", "rawSha256", "canonicalSha256", "profile"}
        or normalized.get("schemaVersion") != PROFILE_BINDING_SCHEMA
        or DIGEST_PATTERN.fullmatch(normalized.get("rawSha256", "")) is None
        or DIGEST_PATTERN.fullmatch(normalized.get("canonicalSha256", "")) is None
    ):
        raise ValueError("backend execution profile snapshot binding is invalid")
    try:
        profile = _validate_profile(normalized.get("profile"))
    except ValueError as exc:
        raise ValueError(
            "backend execution profile snapshot binding is invalid"
        ) from exc
    canonical = _canonical(profile)
    if (
        hashlib.sha256(canonical).hexdigest() != normalized["canonicalSha256"]
        or hashlib.sha256(canonical + b"\n").hexdigest() != normalized["rawSha256"]
    ):
        raise ValueError("backend execution profile snapshot binding is invalid")
    return normalized


def _load_execution_profile(
    *,
    path: Path,
    snapshot_binding: Mapping[str, Any],
    private_root: Path,
) -> ExecutionProfile:
    """Load only a profile exactly equal to its signed snapshot binding."""

    expected = _validate_execution_profile_binding_document(snapshot_binding)
    observed = inspect_execution_profile(path, private_root=private_root)
    if expected != observed:
        raise ValueError("backend execution profile snapshot binding does not match")
    return ExecutionProfile(
        path=path,
        private_root=private_root,
        document=observed["profile"],
        raw_sha256=observed["rawSha256"],
        canonical_sha256=observed["canonicalSha256"],
        _token=_PROFILE_TOKEN,
    )


def _profile_binding(profile: ExecutionProfile) -> dict[str, Any]:
    if not isinstance(profile, ExecutionProfile):
        raise ValueError("snapshot-bound backend execution profile is required")
    return {
        "schemaVersion": PROFILE_BINDING_SCHEMA,
        "rawSha256": profile.raw_sha256,
        "canonicalSha256": profile.canonical_sha256,
        "profile": profile.document,
    }


def _revalidate_profile(profile: ExecutionProfile) -> ExecutionProfile:
    return _load_execution_profile(
        path=profile.path,
        snapshot_binding=_profile_binding(profile),
        private_root=profile.private_root,
    )


def _validate_execution_resource_binding_document(
    *, profile_document: dict[str, Any], snapshot_binding: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(snapshot_binding, Mapping):
        raise ValueError("backend execution resource snapshot binding is invalid")
    binding = copy.deepcopy(dict(snapshot_binding))
    if (
        set(binding) != {"schemaVersion", "namespace", "imagePullSecret"}
        or binding.get("schemaVersion") != EXECUTION_RESOURCES_BINDING_SCHEMA
    ):
        raise ValueError("backend execution resource snapshot binding is invalid")
    namespace = binding.get("namespace")
    secret = binding.get("imagePullSecret")
    if (
        not isinstance(namespace, dict)
        or set(namespace) != {"name", "uid", "owner", "phase", "podSecurityLabels"}
        or namespace.get("name") != profile_document["executionNamespace"]
        or namespace.get("owner") != profile_document["namespaceOwner"]
        or namespace.get("phase") != "Active"
        or not isinstance(secret, dict)
        or set(secret)
        != {"namespace", "name", "uid", "owner", "dataKeys", "dataSha256"}
        or secret.get("namespace") != namespace.get("name")
        or secret.get("name") != profile_document["imagePullSecret"]
        or secret.get("owner") != EXECUTION_NAMESPACE_OWNER
        or secret.get("dataKeys") != [".dockerconfigjson"]
    ):
        raise ValueError("backend execution resource snapshot binding is invalid")
    _required_uid(namespace.get("uid"), "execution Namespace UID")
    _required_label_value(namespace.get("owner"), "execution Namespace owner")
    _required_uid(secret.get("uid"), "image pull Secret UID")
    if DIGEST_PATTERN.fullmatch(secret.get("dataSha256", "")) is None:
        raise ValueError("image pull Secret data digest is invalid")
    pod_security = namespace.get("podSecurityLabels")
    expected_pod_security = {
        "pod-security.kubernetes.io/enforce": "privileged",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
    if pod_security != expected_pod_security:
        raise ValueError("execution Namespace Pod Security binding is invalid")
    return binding


def _load_execution_resource_binding(
    *, profile: ExecutionProfile, snapshot_binding: Mapping[str, Any]
) -> ExecutionResources:
    """Load exact execution resource identities from a signed snapshot field."""

    trusted_profile = _revalidate_profile(profile)
    binding = _validate_execution_resource_binding_document(
        profile_document=trusted_profile.document,
        snapshot_binding=snapshot_binding,
    )
    return ExecutionResources(binding=binding, _token=_EXECUTION_RESOURCES_TOKEN)


def validate_backend_attestor_snapshot_binding(binding: Any) -> dict[str, Any]:
    """Return one deep-copied canonical binding for snapshot write and load."""

    if not isinstance(binding, Mapping):
        raise ValueError("signed backend attestor binding is invalid")
    normalized = copy.deepcopy(dict(binding))
    if (
        set(normalized)
        != {
            "schemaVersion",
            "executionProfile",
            "executionResources",
            "imageInventorySha256",
        }
        or normalized.get("schemaVersion")
        != BACKEND_ATTESTOR_SNAPSHOT_BINDING_SCHEMA
        or DIGEST_PATTERN.fullmatch(normalized.get("imageInventorySha256", "")) is None
    ):
        raise ValueError("signed backend attestor binding is invalid")
    profile_binding = _validate_execution_profile_binding_document(
        normalized["executionProfile"]
    )
    resources_binding = _validate_execution_resource_binding_document(
        profile_document=profile_binding["profile"],
        snapshot_binding=normalized["executionResources"],
    )
    canonical = {
        "schemaVersion": BACKEND_ATTESTOR_SNAPSHOT_BINDING_SCHEMA,
        "executionProfile": profile_binding,
        "executionResources": resources_binding,
        "imageInventorySha256": normalized["imageInventorySha256"],
    }
    if canonical != normalized:
        raise ValueError("signed backend attestor binding is not canonical")
    return canonical


def _revalidate_execution_resources(
    profile: ExecutionProfile, resources: ExecutionResources
) -> ExecutionResources:
    if not isinstance(resources, ExecutionResources):
        raise ValueError("snapshot-bound execution resources are required")
    return _load_execution_resource_binding(
        profile=profile, snapshot_binding=resources.binding
    )


def _load_cleanup_target_binding(
    *,
    locator: dict[str, Any],
    run_id: str,
    snapshot_binding: Mapping[str, Any],
) -> CleanupTargetBinding:
    """Load exact post-reset resource targets from a signed snapshot field."""

    if not isinstance(snapshot_binding, Mapping):
        raise ValueError("backend cleanup target snapshot binding is invalid")
    binding = copy.deepcopy(dict(snapshot_binding))
    if (
        set(binding)
        != {
            "schemaVersion",
            "snapshotSha256",
            "runId",
            "locatorSha256",
            "namespaces",
            "persistentVolumeClaims",
            "persistentVolume",
        }
        or binding.get("schemaVersion") != CLEANUP_TARGET_BINDING_SCHEMA
    ):
        raise ValueError("backend cleanup target snapshot binding is invalid")
    locator_digest = locator_sha256(locator)
    if (
        RUN_ID_PATTERN.fullmatch(run_id) is None
        or binding.get("runId") != run_id
        or binding.get("locatorSha256") != locator_digest
        or DIGEST_PATTERN.fullmatch(binding.get("snapshotSha256", "")) is None
    ):
        raise ValueError("backend cleanup target snapshot identity is invalid")
    namespaces = binding.get("namespaces")
    claims = binding.get("persistentVolumeClaims")
    volume = binding.get("persistentVolume")
    if (
        not isinstance(namespaces, list)
        or not isinstance(claims, list)
        or not isinstance(volume, dict)
        or not namespaces
        or set(volume) != {"name", "uid"}
    ):
        raise ValueError("backend cleanup target sets are invalid")
    normalized_namespaces = tuple(
        _required_dns_label(name, "cleanup Namespace") for name in namespaces
    )
    normalized_volume_name = _required_dns_subdomain(
        volume.get("name"), "cleanup PersistentVolume"
    )
    normalized_volume_uid = _required_uid(
        volume.get("uid"), "cleanup PersistentVolume UID"
    )
    normalized_claims: list[tuple[str, str]] = []
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"namespace", "name"}:
            raise ValueError("cleanup PersistentVolumeClaim target is invalid")
        normalized_claims.append(
            (
                _required_dns_label(claim.get("namespace"), "cleanup claim Namespace"),
                _required_dns_subdomain(
                    claim.get("name"), "cleanup PersistentVolumeClaim"
                ),
            )
        )
    if (
        len(normalized_namespaces) != len(set(normalized_namespaces))
        or len(normalized_claims) != len(set(normalized_claims))
    ):
        raise ValueError("backend cleanup target sets contain duplicates")
    return CleanupTargetBinding(
        snapshot_sha256=binding["snapshotSha256"],
        run_id=run_id,
        locator_digest=locator_digest,
        namespaces=normalized_namespaces,
        persistent_volume_claims=tuple(normalized_claims),
        persistent_volume_name=normalized_volume_name,
        persistent_volume_uid=normalized_volume_uid,
        locator=locator,
        _token=_CLEANUP_TARGET_TOKEN,
    )


def _load_acceptance_release_module():
    path = SCRIPT_DIRECTORY / "acceptance_release.py"
    specification = importlib.util.spec_from_file_location(
        "backend_attestor_acceptance_release", path
    )
    if specification is None or specification.loader is None:
        raise BackendAttestorError("signed image inventory validator is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_attestor_image(
    *,
    path: Path,
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
    private_root: Path,
) -> AttestorImage:
    """Load the sole Workspace Manager identity from a signed image inventory."""

    before = PRIVATE_INPUT.read_private_bytes(
        path,
        "signed image inventory",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )
    release = _load_acceptance_release_module()
    try:
        image = release.load_workspace_manager_image(
            path=path,
            key=key,
            context=context,
            commit=commit,
            cluster_uid=cluster_uid,
            installation_identity_sha256=installation_identity_sha256,
            private_root=private_root,
        )
    except release.AcceptanceReleaseError as exc:
        raise BackendAttestorError(str(exc)) from exc
    after = PRIVATE_INPUT.read_private_bytes(
        path,
        "signed image inventory",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )
    if before != after:
        raise BackendAttestorError("signed image inventory changed while loading")
    immutable_image = image.get("immutableImage")
    runtime_immutable_image = image.get("runtimeImmutableImage")
    source_commit = image.get("revision")
    if (
        not isinstance(immutable_image, str)
        or IMMUTABLE_IMAGE_PATTERN.fullmatch(immutable_image) is None
        or not isinstance(runtime_immutable_image, str)
        or IMMUTABLE_IMAGE_PATTERN.fullmatch(runtime_immutable_image) is None
        or runtime_immutable_image.rsplit("@", 1)[0]
        != immutable_image.rsplit("@", 1)[0]
        or runtime_immutable_image == immutable_image
        or not isinstance(source_commit, str)
        or SHA_PATTERN.fullmatch(source_commit) is None
    ):
        raise BackendAttestorError("signed Workspace Manager image is invalid")
    return AttestorImage(
        path=path,
        private_root=private_root,
        immutable_image=immutable_image,
        runtime_immutable_image=runtime_immutable_image,
        source_commit=source_commit,
        inventory_sha256=hashlib.sha256(before).hexdigest(),
        key=bytes(key),
        context=context,
        cluster_uid=cluster_uid,
        installation_identity_sha256=installation_identity_sha256,
        _token=_IMAGE_TOKEN,
    )


def _revalidate_image(image: AttestorImage) -> AttestorImage:
    if not isinstance(image, AttestorImage):
        raise ValueError("signed Workspace Manager image identity is required")
    observed = _load_attestor_image(
        path=image.path,
        key=image._key,
        context=image._context,
        commit=image.source_commit,
        cluster_uid=image._cluster_uid,
        installation_identity_sha256=image._installation_identity_sha256,
        private_root=image.private_root,
    )
    if (
        observed.inventory_sha256 != image.inventory_sha256
        or observed.immutable_image != image.immutable_image
        or observed.runtime_immutable_image != image.runtime_immutable_image
        or observed.source_commit != image.source_commit
    ):
        raise BackendAttestorError("signed image inventory identity changed")
    return observed


def _nfs_csi_locator(volume_handle: Any) -> tuple[str, str]:
    if not isinstance(volume_handle, str):
        raise ValueError("NFS CSI volumeHandle is invalid")
    parts = volume_handle.split("#")
    if len(parts) == 3:
        server, share, subdirectory = parts
    elif len(parts) == 5:
        server, share, subdirectory, volume_id, on_delete = parts
        if (
            not volume_id
            or PATH_COMPONENT_PATTERN.fullmatch(volume_id) is None
            or on_delete not in {"", "delete", "retain"}
        ):
            raise ValueError("NFS CSI volumeHandle suffix is invalid")
    else:
        raise ValueError("NFS CSI volumeHandle segment count is invalid")
    share_path = _absolute_path(f"/{share.lstrip('/')}", "NFS CSI share")
    subdirectory_path = _absolute_path(
        f"/{subdirectory.lstrip('/')}", "NFS CSI subdirectory"
    ).lstrip("/")
    return server, f"{share_path}/{subdirectory_path}"


def _nfs_target(
    *, server: Any, path: Any, backend: str, document: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(server, str):
        raise ValueError("backend NFS server is invalid")
    target_path = _absolute_path(path, "backend NFS path")
    matches: list[tuple[dict[str, str], str]] = []
    for root in document["nfsMountRoots"]:
        relative = (
            _strict_relative_path(target_path, root["path"])
            if root["server"] == server
            else None
        )
        if relative is not None:
            matches.append((root, relative))
    if len(matches) != 1:
        raise ValueError("backend NFS target is not under one approved mount root")
    root, relative = matches[0]
    return {
        "backend": backend,
        "mount": {"type": "nfs", "server": server, "path": root["path"]},
        "relativePath": relative,
    }


def _resolve_backend_target(
    locator: dict[str, Any], document: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(locator, dict):
        raise ValueError("backend locator must be an object")
    locator_type = locator.get("type")
    if locator_type == "nfs" and set(locator) == {"type", "server", "path"}:
        return _nfs_target(
            server=locator["server"],
            path=locator["path"],
            backend="nfs",
            document=document,
        )
    if locator_type == "csi" and set(locator) == {
        "type",
        "driver",
        "volumeHandle",
    }:
        if locator.get("driver") != NFS_CSI_DRIVER:
            raise ValueError("backend CSI driver is unsupported")
        server, path = _nfs_csi_locator(locator.get("volumeHandle"))
        return _nfs_target(
            server=server,
            path=path,
            backend=f"csi:{NFS_CSI_DRIVER}",
            document=document,
        )
    if locator_type == "localPath" and set(locator) == {
        "type",
        "node",
        "path",
        "volumeSource",
    }:
        node = locator.get("node")
        if (
            not isinstance(node, str)
            or _required_dns_subdomain(node, "local-path backend Node") != node
            or locator.get("volumeSource") not in {"local", "hostPath"}
        ):
            raise ValueError("local-path backend identity is invalid")
        nodes = [
            item for item in document["localPathNodes"] if item["hostname"] == node
        ]
        if len(nodes) != 1:
            raise ValueError("local-path backend Node is not approved")
        approved_node = nodes[0]
        target_path = _absolute_path(locator.get("path"), "local-path backend path")
        matches = [
            (root, relative)
            for root in approved_node["mountRoots"]
            if (relative := _strict_relative_path(target_path, root)) is not None
        ]
        if len(matches) != 1:
            raise ValueError(
                "local-path backend target is not under one approved mount root"
            )
        root, relative = matches[0]
        return {
            "backend": "localPath",
            "mount": {
                "type": "localPath",
                "node": approved_node["hostname"],
                "nodeUid": approved_node["nodeUid"],
                "path": root,
            },
            "relativePath": relative,
        }
    raise ValueError("backend locator type is unsupported")


def resolve_backend_target(
    locator: dict[str, Any], *, profile: ExecutionProfile
) -> dict[str, Any]:
    trusted = _revalidate_profile(profile)
    return _resolve_backend_target(locator, trusted.document)


def _subprocess_runner(command: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(
            command, capture_output=True, check=False, timeout=360
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackendAttestorError("backend attestor command transport failed") from exc
    return CommandResult(completed.stdout, completed.stderr, completed.returncode)


def _run_checked(runner: Runner, command: list[str], description: str) -> CommandResult:
    try:
        result = runner(command)
    except Exception as exc:
        raise BackendAttestorError(f"{description} transport failed") from exc
    if (
        not hasattr(result, "stdout")
        or not hasattr(result, "stderr")
        or not hasattr(result, "returncode")
        or not isinstance(result.stdout, bytes)
        or not isinstance(result.stderr, bytes)
        or result.returncode != 0
    ):
        raise BackendAttestorError(f"{description} failed")
    return CommandResult(bytes(result.stdout), bytes(result.stderr), result.returncode)


def _validate_kubeconfig(path: Path, *, private_root: Path) -> None:
    PRIVATE_INPUT.read_private_bytes(
        path,
        "pinned kubeconfig",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )


def _validate_context(context: Any) -> str:
    if (
        not isinstance(context, str)
        or not context
        or len(context) > 253
        or any(character.isspace() or ord(character) < 32 for character in context)
    ):
        raise ValueError("pinned Kubernetes context is invalid")
    return context


def _kubectl_prefix(
    kubeconfig: Path, context: str, *, request_timeout: str = "30s"
) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        f"--request-timeout={request_timeout}",
    ]


def _parse_list(result: CommandResult, description: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(f"{description} returned invalid JSON") from exc
    items = document.get("items") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "v1"
        or document.get("kind")
        not in {
            "List",
            "NamespaceList",
            "PersistentVolumeList",
            "PersistentVolumeClaimList",
            "PodList",
        }
        or not isinstance(items, list)
        or any(not isinstance(item, dict) for item in items)
    ):
        raise BackendAttestorError(f"{description} returned an invalid resource list")
    return items


def _live_local_node(spec: dict[str, Any]) -> str:
    node_affinity = spec.get("nodeAffinity")
    required = (
        node_affinity.get("required") if isinstance(node_affinity, dict) else None
    )
    terms = required.get("nodeSelectorTerms") if isinstance(required, dict) else None
    nodes: set[str] = set()
    if isinstance(terms, list):
        for term in terms:
            expressions = (
                term.get("matchExpressions") if isinstance(term, dict) else None
            )
            if not isinstance(expressions, list):
                continue
            for expression in expressions:
                if (
                    not isinstance(expression, dict)
                    or expression.get("key") != "kubernetes.io/hostname"
                    or expression.get("operator") != "In"
                ):
                    continue
                values = expression.get("values")
                if isinstance(values, list):
                    nodes.update(
                        value for value in values if isinstance(value, str) and value
                    )
    if len(nodes) != 1:
        raise BackendAttestorError(
            "live local-path PersistentVolume has no exact owning Node"
        )
    node = next(iter(nodes))
    try:
        return _required_dns_subdomain(node, "live local-path Node")
    except ValueError as exc:
        raise BackendAttestorError(str(exc)) from exc


def _physical_backend_target(
    locator: dict[str, Any], profile: ExecutionProfile
) -> tuple[str, ...]:
    locator_type = locator.get("type") if isinstance(locator, dict) else None
    try:
        if locator_type == "nfs" and set(locator) == {"type", "server", "path"}:
            server = locator.get("server")
            if (
                not isinstance(server, str)
                or not server
                or any(
                    character.isspace() or character == "\x00" for character in server
                )
            ):
                raise ValueError("NFS backend server is invalid")
            return (
                "nfs",
                server,
                _absolute_path(locator.get("path"), "NFS backend path"),
            )
        if locator_type == "csi" and set(locator) == {
            "type",
            "driver",
            "volumeHandle",
        }:
            if locator.get("driver") != NFS_CSI_DRIVER:
                raise ValueError("backend CSI driver is unsupported")
            server, path = _nfs_csi_locator(locator.get("volumeHandle"))
            return ("nfs", server, path)
        if locator_type == "localPath" and set(locator) == {
            "type",
            "node",
            "path",
            "volumeSource",
        }:
            node = _required_dns_subdomain(
                locator.get("node"), "local-path backend Node"
            )
            if locator.get("volumeSource") not in {"local", "hostPath"}:
                raise ValueError("local-path volume source is invalid")
            path = _absolute_path(locator.get("path"), "local-path backend path")
            matches = [
                item
                for item in profile.document["localPathNodes"]
                if item["hostname"] == node
            ]
            node_uid = matches[0]["nodeUid"] if len(matches) == 1 else "unapproved"
            return ("localPath", node, node_uid, path)
    except ValueError as exc:
        raise BackendAttestorError(str(exc)) from exc
    raise BackendAttestorError("backend locator has no comparable physical target")


def _physical_targets_overlap(
    left: tuple[str, ...], right: tuple[str, ...]
) -> bool:
    if not left or not right or left[0] != right[0]:
        return False
    if left[0] == "nfs":
        if left[:2] != right[:2]:
            return False
        left_path = PurePosixPath(left[2])
        right_path = PurePosixPath(right[2])
    elif left[0] == "localPath":
        if left[:3] != right[:3]:
            return False
        left_path = PurePosixPath(left[3])
        right_path = PurePosixPath(right[3])
    else:
        raise BackendAttestorError("backend physical target type is unsupported")
    return (
        left_path == right_path
        or left_path in right_path.parents
        or right_path in left_path.parents
    )


def _attestor_job_name(*, action: str, locator_digest: str, run_id: str) -> str:
    run_digest = hashlib.sha256(run_id.encode()).hexdigest()
    return f"aileron-backend-{action}-{locator_digest[:12]}-{run_digest[:8]}"


def validate_cleanup_target_set(
    *, bindings: list[CleanupTargetBinding], profile: ExecutionProfile
) -> None:
    """Reject ambiguous signed target sets which share physical backend trees."""

    trusted_profile = _revalidate_profile(profile)
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("snapshot cleanup backend targets must be a non-empty array")
    first = bindings[0]
    if not isinstance(first, CleanupTargetBinding):
        raise ValueError("snapshot-bound backend cleanup targets are required")
    observed: list[tuple[str, ...]] = []
    job_names: set[str] = set()
    for binding in bindings:
        if (
            not isinstance(binding, CleanupTargetBinding)
            or binding.snapshot_sha256 != first.snapshot_sha256
            or binding.run_id != first.run_id
            or binding.locator_sha256 != locator_sha256(binding.locator)
        ):
            raise ValueError("snapshot cleanup backend target identity is inconsistent")
        target = _physical_backend_target(binding.locator, trusted_profile)
        if any(_physical_targets_overlap(target, other) for other in observed):
            raise ValueError("snapshot cleanup backend targets overlap")
        for action in ("cleanup", "verify"):
            name = _attestor_job_name(
                action=action,
                locator_digest=binding.locator_sha256,
                run_id=binding.run_id,
            )
            if name in job_names:
                raise ValueError("snapshot cleanup backend Job names collide")
            job_names.add(name)
        observed.append(target)


def _cleanup_targets_from_signed_inventory(
    *,
    inventory: Any,
    snapshot_sha256: str,
    run_id: str,
    profile: ExecutionProfile,
) -> tuple[CleanupTargetBinding, ...]:
    if not isinstance(inventory, dict):
        raise BackendAttestorError("signed reset inventory is invalid")
    namespaces = inventory.get("namespaces")
    resources = inventory.get("resources")
    persistent_volumes = inventory.get("persistentVolumes")
    if not all(isinstance(value, list) for value in (namespaces, resources, persistent_volumes)):
        raise BackendAttestorError("signed reset inventory target sets are invalid")
    try:
        namespace_names = sorted(
            {
                _required_dns_label(item.get("name"), "cleanup Namespace")
                for item in namespaces
                if isinstance(item, dict)
            }
        )
        if len(namespace_names) != len(namespaces):
            raise ValueError("cleanup Namespace target set is invalid")
        claims = sorted(
            {
                (
                    _required_dns_label(
                        item.get("namespace"), "cleanup claim Namespace"
                    ),
                    _required_dns_subdomain(
                        item.get("name"), "cleanup PersistentVolumeClaim"
                    ),
                )
                for item in resources
                if isinstance(item, dict)
                and item.get("apiVersion") == "v1"
                and item.get("kind") == "PersistentVolumeClaim"
            }
        )
    except ValueError as exc:
        raise BackendAttestorError(str(exc)) from exc
    volume_identities: set[tuple[str, str]] = set()
    binding_documents: list[tuple[str, str, dict[str, Any]]] = []
    for persistent_volume in persistent_volumes:
        if (
            not isinstance(persistent_volume, dict)
            or persistent_volume.get("apiVersion") != "v1"
            or persistent_volume.get("kind") != "PersistentVolume"
        ):
            raise BackendAttestorError(
                "signed reset PersistentVolume target is invalid"
            )
        try:
            volume_name = _required_dns_subdomain(
                persistent_volume.get("name"), "cleanup PersistentVolume"
            )
            volume_uid = _required_uid(
                persistent_volume.get("uid"), "cleanup PersistentVolume UID"
            )
        except ValueError as exc:
            raise BackendAttestorError(str(exc)) from exc
        identity = (volume_name, volume_uid)
        if identity in volume_identities:
            raise BackendAttestorError(
                "signed reset PersistentVolume targets contain duplicates"
            )
        volume_identities.add(identity)
        locator = persistent_volume.get("backendLocator")
        if not isinstance(locator, dict):
            raise BackendAttestorError(
                "signed reset PersistentVolume backend locator is invalid"
            )
        binding_documents.append((volume_name, volume_uid, copy.deepcopy(locator)))
    bindings = tuple(
        _load_cleanup_target_binding(
            locator=locator,
            run_id=run_id,
            snapshot_binding={
                "schemaVersion": CLEANUP_TARGET_BINDING_SCHEMA,
                "snapshotSha256": snapshot_sha256,
                "runId": run_id,
                "locatorSha256": locator_sha256(locator),
                "namespaces": namespace_names,
                "persistentVolumeClaims": [
                    {"namespace": namespace, "name": name}
                    for namespace, name in claims
                ],
                "persistentVolume": {"name": volume_name, "uid": volume_uid},
            },
        )
        for volume_name, volume_uid, locator in sorted(
            binding_documents, key=lambda item: (item[0], item[1])
        )
    )
    if bindings:
        validate_cleanup_target_set(bindings=list(bindings), profile=profile)
    return bindings


def _load_signed_backend_attestor_inputs(
    *,
    context: str,
    commit: str,
    expected_run_id: str,
    expected_snapshot_sha256: str,
    _trust_loader: Callable[..., Any] | None = None,
    _snapshot_loader: Callable[..., dict[str, Any]] | None = None,
) -> SignedBackendAttestorInputs:
    """Load every destructive input from live cluster trust and one snapshot."""

    context = _validate_context(context)
    if (
        SHA_PATTERN.fullmatch(commit) is None
        or RUN_ID_PATTERN.fullmatch(expected_run_id) is None
        or DIGEST_PATTERN.fullmatch(expected_snapshot_sha256) is None
    ):
        raise ValueError("backend attestor signed snapshot identity is invalid")
    private_root = PRIVATE_INPUT.private_root_path()
    acceptance_directory = (
        private_root / "evidence" / commit / expected_run_id
    )
    image_inventory_path = (
        private_root / "install" / commit / "signed-image-inventory.json"
    )
    execution_profile_path = (
        acceptance_directory / "backend-execution-profile.json"
    )
    kubeconfig = (
        private_root
        / "reset"
        / commit
        / expected_run_id
        / f"reset-kubeconfig-{expected_run_id}.flattened.json"
    )
    _validate_kubeconfig(kubeconfig, private_root=private_root)
    trust_loader = _trust_loader or ACCEPTANCE_CLUSTER.load_cluster_acceptance_key
    snapshot_loader = _snapshot_loader or ACCEPTANCE_SNAPSHOT.load_reset_snapshot
    try:
        trust = trust_loader(context=context, kubeconfig=kubeconfig)
        key = trust.key
        cluster_uid = trust.cluster_uid
        installation_identity_sha256 = trust.installation_identity_sha256
        snapshot = snapshot_loader(
            directory=acceptance_directory,
            private_root=private_root,
            key=key,
            context=context,
            commit=commit,
            cluster_uid=cluster_uid,
            installation_identity_sha256=installation_identity_sha256,
            expected_run_id=expected_run_id,
            expected_snapshot_sha256=expected_snapshot_sha256,
        )
    except Exception as exc:
        raise BackendAttestorError(
            "backend attestor signed snapshot trust validation failed"
        ) from exc
    if (
        not isinstance(key, bytes)
        or len(key) != 32
        or not isinstance(snapshot, dict)
        or snapshot.get("runId") != expected_run_id
        or snapshot.get("commit") != commit
        or snapshot.get("context") != context
        or snapshot.get("clusterUid") != cluster_uid
        or snapshot.get("installationIdentitySha256")
        != installation_identity_sha256
    ):
        raise BackendAttestorError("backend attestor signed snapshot identity is invalid")
    try:
        binding = validate_backend_attestor_snapshot_binding(
            snapshot.get("backendAttestor")
        )
    except ValueError as exc:
        raise BackendAttestorError(str(exc)) from exc
    profile = _load_execution_profile(
        path=execution_profile_path,
        snapshot_binding=binding["executionProfile"],
        private_root=private_root,
    )
    resources = _load_execution_resource_binding(
        profile=profile,
        snapshot_binding=binding["executionResources"],
    )
    image_inventory = PRIVATE_INPUT.read_private_bytes(
        image_inventory_path,
        "signed image inventory",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )
    if hashlib.sha256(image_inventory).hexdigest() != binding["imageInventorySha256"]:
        raise BackendAttestorError(
            "signed backend attestor image inventory does not match the reset snapshot"
        )
    image = _load_attestor_image(
        path=image_inventory_path,
        key=key,
        context=context,
        commit=commit,
        cluster_uid=cluster_uid,
        installation_identity_sha256=installation_identity_sha256,
        private_root=private_root,
    )
    cleanup_targets = _cleanup_targets_from_signed_inventory(
        inventory=snapshot.get("inventory"),
        snapshot_sha256=expected_snapshot_sha256,
        run_id=expected_run_id,
        profile=profile,
    )
    return SignedBackendAttestorInputs(
        profile=profile,
        image=image,
        execution_resources=resources,
        cleanup_targets=cleanup_targets,
        snapshot_sha256=expected_snapshot_sha256,
        run_id=expected_run_id,
        commit=commit,
        context=context,
        kubeconfig=kubeconfig,
        private_root=private_root,
        _token=_SIGNED_INPUTS_TOKEN,
    )


def load_signed_backend_attestor_inputs(
    *,
    context: str,
    commit: str,
    expected_run_id: str,
    expected_snapshot_sha256: str,
) -> SignedBackendAttestorInputs:
    """Load destructive inputs through the fixed live-trust verification path."""

    return _load_signed_backend_attestor_inputs(
        context=context,
        commit=commit,
        expected_run_id=expected_run_id,
        expected_snapshot_sha256=expected_snapshot_sha256,
    )


def _live_pv_physical_target(
    item: dict[str, Any], profile: ExecutionProfile
) -> tuple[str, ...] | None:
    metadata = item.get("metadata")
    spec = item.get("spec")
    if (
        item.get("apiVersion") != "v1"
        or item.get("kind") != "PersistentVolume"
        or not isinstance(metadata, dict)
        or not isinstance(metadata.get("name"), str)
        or not isinstance(metadata.get("uid"), str)
        or not metadata.get("uid")
        or not isinstance(spec, dict)
    ):
        raise BackendAttestorError(
            "authoritative PersistentVolume inventory has invalid identity"
        )
    locators: list[dict[str, Any]] = []
    nfs = spec.get("nfs")
    if isinstance(nfs, dict):
        locators.append(
            {
                "type": "nfs",
                "server": nfs.get("server"),
                "path": nfs.get("path"),
            }
        )
    csi = spec.get("csi")
    if isinstance(csi, dict) and csi.get("driver") == NFS_CSI_DRIVER:
        locators.append(
            {
                "type": "csi",
                "driver": NFS_CSI_DRIVER,
                "volumeHandle": csi.get("volumeHandle"),
            }
        )
    for source in ("local", "hostPath"):
        volume = spec.get(source)
        if isinstance(volume, dict):
            locators.append(
                {
                    "type": "localPath",
                    "node": _live_local_node(spec),
                    "path": volume.get("path"),
                    "volumeSource": source,
                }
            )
    if not locators:
        return None
    if len(locators) != 1:
        raise BackendAttestorError(
            "live PersistentVolume has multiple comparable backend targets"
        )
    return _physical_backend_target(locators[0], profile)


def _authorize_backend_cleanup(
    *,
    binding: CleanupTargetBinding,
    profile: ExecutionProfile,
    kubeconfig: Path,
    context: str,
    runner: Runner = _subprocess_runner,
) -> CleanupAuthorization:
    """Prove targets absent under the documented non-atomic maintenance boundary."""

    if not isinstance(binding, CleanupTargetBinding):
        raise ValueError("snapshot-bound backend cleanup targets are required")
    trusted_profile = _revalidate_profile(profile)
    _validate_kubeconfig(kubeconfig, private_root=profile.private_root)
    context = _validate_context(context)
    prefix = _kubectl_prefix(kubeconfig, context)
    commands = (
        ("Namespace", [*prefix, "get", "namespaces", "--output=json"]),
        (
            "PersistentVolumeClaim",
            [
                *prefix,
                "get",
                "persistentvolumeclaims",
                "--all-namespaces",
                "--output=json",
            ],
        ),
        (
            "PersistentVolume",
            [*prefix, "get", "persistentvolumes", "--output=json"],
        ),
    )
    observed: dict[str, set[Any]] = {}
    live_persistent_volumes: list[dict[str, Any]] = []
    for kind, command in commands:
        result = _run_checked(runner, command, f"authoritative {kind} absence query")
        items = _parse_list(result, f"authoritative {kind} absence query")
        if kind == "PersistentVolume":
            live_persistent_volumes = items
        identities: set[Any] = set()
        for item in items:
            metadata = item.get("metadata")
            if not isinstance(metadata, dict) or not isinstance(
                metadata.get("name"), str
            ):
                raise BackendAttestorError(
                    f"authoritative {kind} absence query returned invalid identity"
                )
            if kind == "PersistentVolumeClaim":
                namespace = metadata.get("namespace")
                if not isinstance(namespace, str):
                    raise BackendAttestorError(
                        "authoritative PersistentVolumeClaim absence query returned "
                        "invalid identity"
                    )
                identities.add((namespace, metadata["name"]))
            else:
                identities.add(metadata["name"])
        observed[kind] = identities
    remaining = {
        "Namespace": set(binding.namespaces) & observed["Namespace"],
        "PersistentVolumeClaim": set(binding.persistent_volume_claims)
        & observed["PersistentVolumeClaim"],
        "PersistentVolume": {binding.persistent_volume_name}
        & observed["PersistentVolume"],
    }
    if any(remaining.values()):
        raise BackendAttestorError("signed Kubernetes cleanup target still exists")
    cleanup_target = _physical_backend_target(binding.locator, trusted_profile)
    for persistent_volume in live_persistent_volumes:
        live_target = _live_pv_physical_target(persistent_volume, trusted_profile)
        if live_target is not None and _physical_targets_overlap(
            live_target, cleanup_target
        ):
            raise BackendAttestorError(
                "backend cleanup target overlaps or was rebound by a live "
                "PersistentVolume"
            )
    return CleanupAuthorization(
        binding=binding,
        profile=trusted_profile,
        kubeconfig=kubeconfig,
        context=context,
        _token=_CLEANUP_AUTHORIZATION_TOKEN,
    )


def _validate_cleanup_authorization(
    *,
    authorization: CleanupAuthorization | None,
    locator: dict[str, Any],
    run_id: str,
    kubeconfig: Path,
    context: str,
    profile: ExecutionProfile,
) -> None:
    if (
        not isinstance(authorization, CleanupAuthorization)
        or authorization.locator_sha256 != locator_sha256(locator)
        or authorization.run_id != run_id
        or authorization.kubeconfig != kubeconfig
        or authorization.context != context
        or authorization.profile_raw_sha256 != profile.raw_sha256
        or authorization.profile_canonical_sha256 != profile.canonical_sha256
        or authorization.used
    ):
        raise BackendAttestorError(
            "live signed-target cleanup authorization is required"
        )
    authorization.used = True


def inspect_execution_resources(
    *,
    execution_profile_path: Path,
    kubeconfig: Path,
    context: str,
    private_root: Path,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Capture the exact live Namespace and pull Secret binding for signing."""

    profile_binding = inspect_execution_profile(
        execution_profile_path, private_root=private_root
    )
    profile = _load_execution_profile(
        path=execution_profile_path,
        snapshot_binding=profile_binding,
        private_root=private_root,
    )
    _validate_kubeconfig(kubeconfig, private_root=private_root)
    context = _validate_context(context)
    prefix = _kubectl_prefix(kubeconfig, context)
    namespace_name = profile.document["executionNamespace"]
    secret_name = profile.document["imagePullSecret"]
    namespace_result = _run_checked(
        runner,
        [*prefix, "get", "namespace", namespace_name, "--output=json"],
        "execution Namespace identity query",
    )
    secret_result = _run_checked(
        runner,
        [
            *prefix,
            "--namespace",
            namespace_name,
            "get",
            "secret",
            secret_name,
            "--output=json",
        ],
        "image pull Secret identity query",
    )
    try:
        namespace = json.loads(namespace_result.stdout)
        secret = json.loads(secret_result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "execution resource identity is invalid JSON"
        ) from exc
    namespace_metadata = namespace.get("metadata") if isinstance(namespace, dict) else None
    namespace_status = namespace.get("status") if isinstance(namespace, dict) else None
    namespace_labels = (
        namespace_metadata.get("labels")
        if isinstance(namespace_metadata, dict)
        else None
    )
    secret_metadata = secret.get("metadata") if isinstance(secret, dict) else None
    secret_labels = (
        secret_metadata.get("labels") if isinstance(secret_metadata, dict) else None
    )
    secret_data = secret.get("data") if isinstance(secret, dict) else None
    pod_security = (
        {
            key: value
            for key, value in namespace_labels.items()
            if isinstance(key, str) and key.startswith("pod-security.kubernetes.io/")
        }
        if isinstance(namespace_labels, dict)
        else None
    )
    if (
        namespace.get("apiVersion") != "v1"
        or namespace.get("kind") != "Namespace"
        or not isinstance(namespace_metadata, dict)
        or namespace_metadata.get("name") != namespace_name
        or namespace_metadata.get("deletionTimestamp") is not None
        or not isinstance(namespace_status, dict)
        or namespace_status.get("phase") != "Active"
        or not isinstance(namespace_labels, dict)
        or namespace_labels.get("platform.aileron.dev/namespace-owner")
        != profile.document["namespaceOwner"]
        or secret.get("apiVersion") != "v1"
        or secret.get("kind") != "Secret"
        or secret.get("type") != "kubernetes.io/dockerconfigjson"
        or not isinstance(secret_metadata, dict)
        or secret_metadata.get("namespace") != namespace_name
        or secret_metadata.get("name") != secret_name
        or secret_metadata.get("deletionTimestamp") is not None
        or not isinstance(secret_labels, dict)
        or secret_labels.get("platform.aileron.dev/secret-owner")
        != EXECUTION_NAMESPACE_OWNER
        or not isinstance(secret_data, dict)
        or set(secret_data) != {".dockerconfigjson"}
        or not isinstance(secret_data.get(".dockerconfigjson"), str)
    ):
        raise BackendAttestorError("execution resource identity is invalid")
    candidate = {
        "schemaVersion": EXECUTION_RESOURCES_BINDING_SCHEMA,
        "namespace": {
            "name": namespace_name,
            "uid": namespace_metadata.get("uid"),
            "owner": profile.document["namespaceOwner"],
            "phase": "Active",
            "podSecurityLabels": pod_security,
        },
        "imagePullSecret": {
            "namespace": namespace_name,
            "name": secret_name,
            "uid": secret_metadata.get("uid"),
            "owner": EXECUTION_NAMESPACE_OWNER,
            "dataKeys": [".dockerconfigjson"],
            "dataSha256": hashlib.sha256(_canonical(secret_data)).hexdigest(),
        },
    }
    try:
        return _validate_execution_resource_binding_document(
            profile_document=profile.document,
            snapshot_binding=candidate,
        )
    except ValueError as exc:
        raise BackendAttestorError(str(exc)) from exc


def _validate_live_execution_resources(
    *,
    resources: ExecutionResources,
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> None:
    binding = resources.binding
    namespace_binding = binding["namespace"]
    secret_binding = binding["imagePullSecret"]
    prefix = _kubectl_prefix(kubeconfig, context)
    namespace_command = [
        *prefix,
        "get",
        "namespace",
        namespace_binding["name"],
        "--output=json",
    ]
    secret_command = [
        *prefix,
        "--namespace",
        namespace_binding["name"],
        "get",
        "secret",
        secret_binding["name"],
        "--output=json",
    ]
    namespace_result = _run_checked(
        runner, namespace_command, "execution Namespace identity query"
    )
    secret_result = _run_checked(
        runner, secret_command, "image pull Secret identity query"
    )
    try:
        namespace = json.loads(namespace_result.stdout)
        secret = json.loads(secret_result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "execution resource identity is invalid JSON"
        ) from exc
    namespace_metadata = (
        namespace.get("metadata") if isinstance(namespace, dict) else None
    )
    namespace_status = namespace.get("status") if isinstance(namespace, dict) else None
    namespace_labels = (
        namespace_metadata.get("labels")
        if isinstance(namespace_metadata, dict)
        else None
    )
    expected_labels = {
        "platform.aileron.dev/namespace-owner": namespace_binding["owner"],
        **namespace_binding["podSecurityLabels"],
    }
    observed_pod_security = (
        {
            key: value
            for key, value in namespace_labels.items()
            if isinstance(key, str) and key.startswith("pod-security.kubernetes.io/")
        }
        if isinstance(namespace_labels, dict)
        else None
    )
    if (
        namespace.get("apiVersion") != "v1"
        or namespace.get("kind") != "Namespace"
        or not isinstance(namespace_metadata, dict)
        or namespace_metadata.get("name") != namespace_binding["name"]
        or namespace_metadata.get("uid") != namespace_binding["uid"]
        or namespace_metadata.get("deletionTimestamp") is not None
        or not isinstance(namespace_status, dict)
        or namespace_status.get("phase") != "Active"
        or not isinstance(namespace_labels, dict)
        or any(
            namespace_labels.get(key) != value for key, value in expected_labels.items()
        )
        or observed_pod_security != namespace_binding["podSecurityLabels"]
    ):
        raise BackendAttestorError(
            "execution Namespace identity does not match the snapshot"
        )
    secret_metadata = secret.get("metadata") if isinstance(secret, dict) else None
    secret_labels = (
        secret_metadata.get("labels") if isinstance(secret_metadata, dict) else None
    )
    secret_data = secret.get("data") if isinstance(secret, dict) else None
    if (
        secret.get("apiVersion") != "v1"
        or secret.get("kind") != "Secret"
        or secret.get("type") != "kubernetes.io/dockerconfigjson"
        or not isinstance(secret_metadata, dict)
        or secret_metadata.get("namespace") != secret_binding["namespace"]
        or secret_metadata.get("name") != secret_binding["name"]
        or secret_metadata.get("uid") != secret_binding["uid"]
        or secret_metadata.get("deletionTimestamp") is not None
        or not isinstance(secret_labels, dict)
        or secret_labels.get("platform.aileron.dev/secret-owner")
        != secret_binding["owner"]
        or not isinstance(secret_data, dict)
        or set(secret_data) != {".dockerconfigjson"}
        or not isinstance(secret_data.get(".dockerconfigjson"), str)
        or hashlib.sha256(_canonical(secret_data)).hexdigest()
        != secret_binding["dataSha256"]
    ):
        raise BackendAttestorError(
            "image pull Secret identity does not match the snapshot"
        )


def _validate_live_node(
    *,
    mount: dict[str, Any],
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> None:
    command = [
        *_kubectl_prefix(kubeconfig, context),
        "get",
        "node",
        mount["node"],
        "--output=json",
    ]
    result = _run_checked(runner, command, "live Node identity query")
    try:
        node = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError("live Node identity is invalid JSON") from exc
    metadata = node.get("metadata") if isinstance(node, dict) else None
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    if (
        node.get("apiVersion") != "v1"
        or node.get("kind") != "Node"
        or not isinstance(metadata, dict)
        or metadata.get("name") != mount["node"]
        or metadata.get("uid") != mount["nodeUid"]
        or not isinstance(labels, dict)
        or labels.get("kubernetes.io/hostname") != mount["node"]
        or labels.get("kubernetes.io/os") != "linux"
        or labels.get("kubernetes.io/arch") != "amd64"
        or metadata.get("deletionTimestamp") is not None
    ):
        raise BackendAttestorError("live Node identity does not match the profile")


def _validate_attestor_execution_identity(
    *,
    locator: dict[str, Any],
    profile: ExecutionProfile,
    execution_resources: ExecutionResources,
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> dict[str, Any]:
    trusted_profile = _revalidate_profile(profile)
    trusted_resources = _revalidate_execution_resources(
        trusted_profile, execution_resources
    )
    _validate_live_execution_resources(
        resources=trusted_resources,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    target = _resolve_backend_target(locator, trusted_profile.document)
    mount = target["mount"]
    if mount["type"] == "localPath":
        _validate_live_node(
            mount=mount, kubeconfig=kubeconfig, context=context, runner=runner
        )
    return target


def build_attestor_job_manifest(
    *,
    action: str,
    locator: dict[str, Any],
    profile: ExecutionProfile,
    image: AttestorImage,
    execution_resources: ExecutionResources,
    kubeconfig: Path,
    context: str,
    run_id: str,
    runner: Runner = _subprocess_runner,
    cleanup_authorization: CleanupAuthorization | None = None,
) -> dict[str, Any]:
    trusted_profile = _revalidate_profile(profile)
    trusted_image = _revalidate_image(image)
    _validate_kubeconfig(kubeconfig, private_root=profile.private_root)
    context = _validate_context(context)
    if action not in {"cleanup", "verify"} or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("backend attestor identity is invalid")
    if action == "cleanup":
        _validate_cleanup_authorization(
            authorization=cleanup_authorization,
            locator=locator,
            run_id=run_id,
            kubeconfig=kubeconfig,
            context=context,
            profile=trusted_profile,
        )
    elif cleanup_authorization is not None:
        raise ValueError("verify attestor must not carry cleanup authorization")
    target = _validate_attestor_execution_identity(
        locator=locator,
        profile=trusted_profile,
        execution_resources=execution_resources,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    trusted_resources = _revalidate_execution_resources(
        trusted_profile, execution_resources
    )
    mount = target["mount"]
    locator_digest = locator_sha256(locator)
    name = _attestor_job_name(
        action=action, locator_digest=locator_digest, run_id=run_id
    )
    labels = {
        "platform.aileron.dev/backend-action": action,
        "platform.aileron.dev/backend-locator": locator_digest[:16],
        "platform.aileron.dev/acceptance-run-id": run_id,
        "platform.aileron.dev/source-commit": trusted_image.source_commit,
    }
    annotations = {
        "platform.aileron.dev/backend-locator-sha256": locator_digest,
        "platform.aileron.dev/backend-profile-raw-sha256": trusted_profile.raw_sha256,
        "platform.aileron.dev/backend-profile-canonical-sha256": (
            trusted_profile.canonical_sha256
        ),
        "platform.aileron.dev/image-inventory-sha256": (trusted_image.inventory_sha256),
        "platform.aileron.dev/runtime-immutable-image": (
            trusted_image.runtime_immutable_image
        ),
        "platform.aileron.dev/execution-namespace-uid": trusted_resources.binding[
            "namespace"
        ]["uid"],
        "platform.aileron.dev/image-pull-secret-uid": trusted_resources.binding[
            "imagePullSecret"
        ]["uid"],
        "platform.aileron.dev/image-pull-secret-data-sha256": (
            trusted_resources.binding["imagePullSecret"]["dataSha256"]
        ),
        "platform.aileron.dev/job-transaction-token": hmac.new(
            trusted_image._key,
            b"aileron-backend-attestor-job/v1\0"
            + _canonical(
                {
                    "action": action,
                    "context": context,
                    "locatorSha256": locator_digest,
                    "name": name,
                    "namespace": trusted_resources.binding["namespace"]["name"],
                    "runId": run_id,
                }
            ),
            hashlib.sha256,
        ).hexdigest(),
    }
    if mount["type"] == "localPath":
        annotations["platform.aileron.dev/backend-node-uid"] = mount["nodeUid"]
    read_only = action == "verify"
    if mount["type"] == "localPath":
        volume = {
            "name": "backend",
            "hostPath": {"path": mount["path"], "type": "Directory"},
        }
    else:
        volume = {
            "name": "backend",
            "nfs": {
                "server": mount["server"],
                "path": mount["path"],
                "readOnly": read_only,
            },
        }
    capabilities: dict[str, Any] = {"drop": ["ALL"]}
    if action == "cleanup":
        capabilities["add"] = ["DAC_OVERRIDE"]
    container = {
        "name": "backend-attestor",
        "image": trusted_image.immutable_image,
        "imagePullPolicy": "IfNotPresent",
        "command": [
            "/workspace-manager/.venv/bin/python",
            "/workspace-manager/scripts/backend_storage_probe.py",
        ],
        "args": [
            "--action",
            action,
            "--mount-root",
            "/backend",
            "--relative-path",
            target["relativePath"],
            "--locator-sha256",
            locator_digest,
            "--profile-raw-sha256",
            trusted_profile.raw_sha256,
            "--profile-canonical-sha256",
            trusted_profile.canonical_sha256,
            "--run-id",
            run_id,
        ],
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": capabilities,
            "runAsUser": 0,
            "runAsGroup": 0,
        },
        "resources": {
            "requests": {"cpu": "10m", "memory": "32Mi"},
            "limits": {"cpu": "500m", "memory": "128Mi"},
        },
        "terminationMessagePath": "/dev/termination-log",
        "terminationMessagePolicy": "File",
        "volumeMounts": [
            {"name": "backend", "mountPath": "/backend", "readOnly": read_only}
        ],
    }
    pod_spec: dict[str, Any] = {
        "serviceAccountName": "default",
        "automountServiceAccountToken": False,
        "restartPolicy": "Never",
        "terminationGracePeriodSeconds": 30,
        "dnsPolicy": "ClusterFirst",
        "schedulerName": "default-scheduler",
        "enableServiceLinks": False,
        "hostNetwork": False,
        "hostPID": False,
        "hostIPC": False,
        "imagePullSecrets": [{"name": trusted_profile.document["imagePullSecret"]}],
        "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
        "containers": [container],
        "volumes": [volume],
        "nodeSelector": {
            "kubernetes.io/os": "linux",
            "kubernetes.io/arch": "amd64",
        },
    }
    if mount["type"] == "localPath":
        pod_spec["nodeSelector"]["kubernetes.io/hostname"] = mount["node"]
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": trusted_profile.document["executionNamespace"],
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "parallelism": 1,
            "completions": 1,
            "completionMode": "NonIndexed",
            "suspend": False,
            "backoffLimit": 0,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {"labels": labels, "annotations": annotations},
                "spec": pod_spec,
            },
        },
    }


def _expected_platform_metadata(actual: Any, expected: dict[str, str]) -> bool:
    if not isinstance(actual, dict):
        return False
    platform = {
        key: value
        for key, value in actual.items()
        if isinstance(key, str) and key.startswith("platform.aileron.dev/")
    }
    return platform == expected


def _volume_mounts_match(actual: Any, expected: Any) -> bool:
    """Compare volume mounts with Kubernetes' readOnly:false omission only."""

    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if len(actual) != len(expected):
        return False
    for actual_mount, expected_mount in zip(actual, expected):
        if not isinstance(actual_mount, dict) or not isinstance(expected_mount, dict):
            return False
        if set(actual_mount) - set(expected_mount):
            return False
        for key, expected_value in expected_mount.items():
            if key not in actual_mount:
                if key != "readOnly" or expected_value is not False:
                    return False
                continue
            if key == "readOnly":
                if actual_mount[key] is not expected_value:
                    return False
            elif actual_mount[key] != expected_value:
                return False
    return True


def _nfs_volume_source_match(actual: Any, expected: Any) -> bool:
    """Compare an NFS volume source with Kubernetes' readOnly:false omission only."""

    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if set(actual) - set(expected):
        return False
    for key, expected_value in expected.items():
        if key not in actual:
            if key != "readOnly" or expected_value is not False:
                return False
            continue
        if key == "readOnly":
            if actual[key] is not expected_value:
                return False
        elif actual[key] != expected_value:
            return False
    return True


def _volumes_match(actual: Any, expected: Any) -> bool:
    """Compare pod volumes exactly except for an NFS readOnly:false omission."""

    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if len(actual) != len(expected):
        return False
    for actual_volume, expected_volume in zip(actual, expected):
        if not isinstance(actual_volume, dict) or not isinstance(expected_volume, dict):
            return False
        if set(actual_volume) != set(expected_volume):
            return False
        for key, expected_value in expected_volume.items():
            if key == "nfs":
                if not _nfs_volume_source_match(actual_volume[key], expected_value):
                    return False
            elif actual_volume[key] != expected_value:
                return False
    return True


def _container_specs_match(actual: Any, expected: Any) -> bool:
    """Compare containers exactly except for the scoped volume-mount default."""

    if not isinstance(actual, list) or not isinstance(expected, list):
        return False
    if len(actual) != len(expected):
        return False
    for actual_container, expected_container in zip(actual, expected):
        if not isinstance(actual_container, dict) or not isinstance(
            expected_container, dict
        ):
            return False
        if set(actual_container) != set(expected_container):
            return False
        for key, expected_value in expected_container.items():
            if key == "volumeMounts":
                if not _volume_mounts_match(actual_container[key], expected_value):
                    return False
            elif actual_container[key] != expected_value:
                return False
    return True


def _pod_spec_matches(
    actual: Any, expected: dict[str, Any], *, runtime_pod: bool
) -> bool:
    if not isinstance(actual, dict):
        return False
    for key, value in expected.items():
        if key not in actual:
            if key not in KUBERNETES_OMITTED_FALSE_POD_DEFAULTS or value is not False:
                return False
            continue
        if key == "containers":
            if not _container_specs_match(actual[key], value):
                return False
        elif key == "volumes":
            if not _volumes_match(actual[key], value):
                return False
        elif actual[key] != value:
            return False
    allowed_extra = {
        "serviceAccount",
        "preemptionPolicy",
        "priority",
    }
    if runtime_pod:
        allowed_extra.update({"nodeName", "tolerations"})
    if set(actual) - set(expected) - allowed_extra:
        return False
    if actual.get("serviceAccount", "default") != "default":
        return False
    if actual.get("preemptionPolicy", "PreemptLowerPriority") != "PreemptLowerPriority":
        return False
    if actual.get("priority", 0) != 0:
        return False
    if not runtime_pod:
        return True
    node_name = actual.get("nodeName")
    if not isinstance(node_name, str):
        return False
    expected_hostname = expected.get("nodeSelector", {}).get("kubernetes.io/hostname")
    if expected_hostname is not None:
        if node_name != expected_hostname:
            return False
    else:
        try:
            _required_dns_subdomain(node_name, "runtime Pod Node")
        except ValueError:
            return False
    default_tolerations = [
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
    ]
    return actual.get("tolerations", default_tolerations) == default_tolerations


def _controller_labels_match(
    actual: Any,
    *,
    expected_platform: dict[str, str],
    job_uid: str,
    job_name: str,
) -> bool:
    if not isinstance(actual, dict) or not _expected_platform_metadata(
        actual, expected_platform
    ):
        return False
    required = {
        "batch.kubernetes.io/controller-uid": job_uid,
        "batch.kubernetes.io/job-name": job_name,
    }
    if any(actual.get(key) != value for key, value in required.items()):
        return False
    allowed = {
        *expected_platform,
        *required,
        "controller-uid",
        "job-name",
    }
    if set(actual) - allowed:
        return False
    return (
        actual.get("controller-uid", job_uid) == job_uid
        and actual.get("job-name", job_name) == job_name
    )


def _validate_job_cleanup_identity(
    *, manifest: dict[str, Any], job: Any
) -> tuple[str, str]:
    """Return cleanup preconditions for this transaction-owned Job."""

    expected_metadata = manifest.get("metadata")
    metadata = job.get("metadata") if isinstance(job, dict) else None
    expected_labels = (
        expected_metadata.get("labels") if isinstance(expected_metadata, dict) else None
    )
    expected_annotations = (
        expected_metadata.get("annotations")
        if isinstance(expected_metadata, dict)
        else None
    )
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    uid = metadata.get("uid") if isinstance(metadata, dict) else None
    resource_version = (
        metadata.get("resourceVersion") if isinstance(metadata, dict) else None
    )
    transaction_key = "platform.aileron.dev/job-transaction-token"
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(expected_labels, dict)
        or not isinstance(expected_annotations, dict)
        or not isinstance(metadata, dict)
        or not isinstance(labels, dict)
        or not isinstance(annotations, dict)
        or job.get("apiVersion") != "batch/v1"
        or job.get("kind") != "Job"
        or metadata.get("name") != expected_metadata.get("name")
        or metadata.get("namespace") != expected_metadata.get("namespace")
        or not isinstance(uid, str)
        or not uid
        or not isinstance(resource_version, str)
        or not resource_version
        or any(labels.get(key) != value for key, value in expected_labels.items())
        or annotations.get(transaction_key)
        != expected_annotations.get(transaction_key)
    ):
        raise BackendAttestorError(
            "backend attestor Job cleanup identity is invalid"
        )
    return uid, resource_version


def _validate_created_job_identity(
    *, manifest: dict[str, Any], job: Any
) -> tuple[str, str]:
    """Return UID/resourceVersion only for the exact Job created from manifest."""

    expected_metadata = manifest.get("metadata")
    expected_spec = manifest.get("spec")
    metadata = job.get("metadata") if isinstance(job, dict) else None
    spec = job.get("spec") if isinstance(job, dict) else None
    uid, resource_version = _validate_job_cleanup_identity(
        manifest=manifest, job=job
    )
    expected_template = (
        expected_spec.get("template") if isinstance(expected_spec, dict) else None
    )
    template = spec.get("template") if isinstance(spec, dict) else None
    allowed_defaults = {"selector", "manualSelector", "podReplacementPolicy"}
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(expected_spec, dict)
        or not isinstance(expected_template, dict)
        or not isinstance(metadata, dict)
        or not isinstance(spec, dict)
        or not isinstance(template, dict)
        or job.get("apiVersion") != "batch/v1"
        or job.get("kind") != "Job"
        or metadata.get("name") != expected_metadata.get("name")
        or metadata.get("namespace") != expected_metadata.get("namespace")
        or not _expected_platform_metadata(
            metadata.get("labels"), expected_metadata.get("labels", {})
        )
        or not _expected_platform_metadata(
            metadata.get("annotations"), expected_metadata.get("annotations", {})
        )
        or set(spec) - set(expected_spec) - allowed_defaults
        or any(
            spec.get(key) != value
            for key, value in expected_spec.items()
            if key != "template"
        )
        or set(template) != {"metadata", "spec"}
        or not _controller_labels_match(
            template.get("metadata", {}).get("labels"),
            expected_platform=expected_template.get("metadata", {}).get("labels", {}),
            job_uid=uid,
            job_name=expected_metadata.get("name"),
        )
        or not _expected_platform_metadata(
            template.get("metadata", {}).get("annotations"),
            expected_template.get("metadata", {}).get("annotations", {}),
        )
        or not _pod_spec_matches(
            template.get("spec"), expected_template.get("spec", {}), runtime_pod=False
        )
    ):
        raise BackendAttestorError("backend attestor created Job identity is invalid")
    return uid, resource_version


def validate_attestor_job_identity(
    *,
    manifest: dict[str, Any],
    job: dict[str, Any],
    pods: dict[str, Any],
    image: AttestorImage,
) -> dict[str, str]:
    """Prove one completed Job, one owned Pod, and the signed image digest."""

    trusted_image = _revalidate_image(image)
    if not isinstance(manifest, dict) or not isinstance(job, dict):
        raise BackendAttestorError("backend attestor Job identity is invalid")
    _validate_created_job_identity(manifest=manifest, job=job)
    expected_metadata = manifest.get("metadata")
    job_metadata = job.get("metadata")
    job_uid = job_metadata.get("uid") if isinstance(job_metadata, dict) else None
    expected_spec = manifest.get("spec")
    job_spec = job.get("spec")
    expected_template = (
        expected_spec.get("template") if isinstance(expected_spec, dict) else None
    )
    job_template = job_spec.get("template") if isinstance(job_spec, dict) else None
    expected_job_keys = set(expected_spec) if isinstance(expected_spec, dict) else set()
    allowed_job_defaults = {"selector", "manualSelector", "podReplacementPolicy"}
    selector = job_spec.get("selector") if isinstance(job_spec, dict) else None
    selector_labels = (
        selector.get("matchLabels") if isinstance(selector, dict) else None
    )
    status = job.get("status")
    conditions = status.get("conditions") if isinstance(status, dict) else None
    complete = isinstance(conditions, list) and any(
        isinstance(item, dict)
        and item.get("type") == "Complete"
        and item.get("status") == "True"
        for item in conditions
    )
    if (
        not isinstance(expected_metadata, dict)
        or not isinstance(job_metadata, dict)
        or job.get("apiVersion") != "batch/v1"
        or job.get("kind") != "Job"
        or job_metadata.get("name") != expected_metadata.get("name")
        or job_metadata.get("namespace") != expected_metadata.get("namespace")
        or not isinstance(job_uid, str)
        or not job_uid
        or not _expected_platform_metadata(
            job_metadata.get("labels"), expected_metadata.get("labels", {})
        )
        or not _expected_platform_metadata(
            job_metadata.get("annotations"), expected_metadata.get("annotations", {})
        )
        or not isinstance(expected_spec, dict)
        or not isinstance(job_spec, dict)
        or set(job_spec) - expected_job_keys - allowed_job_defaults
        or any(
            job_spec.get(key) != value
            for key, value in expected_spec.items()
            if key != "template"
        )
        or job_spec.get("manualSelector", False) is not False
        or job_spec.get("podReplacementPolicy", "TerminatingOrFailed")
        not in {"TerminatingOrFailed", "Failed"}
        or not isinstance(selector_labels, dict)
        or selector_labels != {"batch.kubernetes.io/controller-uid": job_uid}
        or not isinstance(expected_template, dict)
        or not isinstance(job_template, dict)
        or set(job_template) != {"metadata", "spec"}
        or not _controller_labels_match(
            job_template.get("metadata", {}).get("labels"),
            expected_platform=expected_template.get("metadata", {}).get("labels", {}),
            job_uid=job_uid,
            job_name=expected_metadata.get("name"),
        )
        or not _expected_platform_metadata(
            job_template.get("metadata", {}).get("annotations"),
            expected_template.get("metadata", {}).get("annotations", {}),
        )
        or not _pod_spec_matches(
            job_template.get("spec"),
            expected_template.get("spec", {}),
            runtime_pod=False,
        )
        or not isinstance(status, dict)
        or status.get("succeeded") != 1
        or status.get("failed", 0) != 0
        or status.get("active", 0) != 0
        or not complete
    ):
        raise BackendAttestorError("backend attestor Job identity is invalid")
    items = pods.get("items") if isinstance(pods, dict) else None
    if (
        pods.get("apiVersion") != "v1"
        or pods.get("kind") not in {"List", "PodList"}
        or not isinstance(items, list)
        or len(items) != 1
    ):
        raise BackendAttestorError("backend attestor must have one owned Pod")
    pod = items[0]
    pod_metadata = pod.get("metadata") if isinstance(pod, dict) else None
    owner_references = (
        pod_metadata.get("ownerReferences") if isinstance(pod_metadata, dict) else None
    )
    expected_template = expected_spec["template"]
    if (
        pod.get("apiVersion") != "v1"
        or pod.get("kind") != "Pod"
        or not isinstance(pod_metadata, dict)
        or pod_metadata.get("namespace") != expected_metadata.get("namespace")
        or not isinstance(pod_metadata.get("name"), str)
        or not isinstance(pod_metadata.get("uid"), str)
        or not pod_metadata.get("uid")
        or not _controller_labels_match(
            pod_metadata.get("labels"),
            expected_platform=expected_template["metadata"]["labels"],
            job_uid=job_uid,
            job_name=expected_metadata.get("name"),
        )
        or not _expected_platform_metadata(
            pod_metadata.get("annotations"),
            expected_template["metadata"]["annotations"],
        )
        or not isinstance(owner_references, list)
        or len(owner_references) != 1
        or owner_references[0].get("apiVersion") != "batch/v1"
        or owner_references[0].get("kind") != "Job"
        or owner_references[0].get("name") != expected_metadata.get("name")
        or owner_references[0].get("uid") != job_uid
        or owner_references[0].get("controller") is not True
        or not _pod_spec_matches(
            pod.get("spec"), expected_template["spec"], runtime_pod=True
        )
    ):
        raise BackendAttestorError("backend attestor Pod ownership or spec is invalid")
    pod_status = pod.get("status")
    statuses = (
        pod_status.get("containerStatuses") if isinstance(pod_status, dict) else None
    )
    if not isinstance(statuses, list) or len(statuses) != 1:
        raise BackendAttestorError("backend attestor container provenance is invalid")
    container_status = statuses[0]
    terminated = (
        container_status.get("state", {}).get("terminated")
        if isinstance(container_status, dict)
        else None
    )
    runtime_image_id = container_status.get("imageID")
    if (
        pod_status.get("phase") != "Succeeded"
        or container_status.get("name") != "backend-attestor"
        or not _container_status_image_matches_requested(
            container_status.get("image"), trusted_image.immutable_image
        )
        or not _runtime_image_id_matches(
            runtime_image_id,
            (
                trusted_image.immutable_image,
                trusted_image.runtime_immutable_image,
            ),
        )
        or not isinstance(terminated, dict)
        or terminated.get("exitCode") != 0
        or pod_status.get("initContainerStatuses") not in (None, [])
    ):
        raise BackendAttestorError("backend attestor container provenance is invalid")
    return {
        "jobUid": job_uid,
        "podName": pod_metadata["name"],
        "podUid": pod_metadata["uid"],
        "imageId": runtime_image_id,
    }


def _runtime_image_id_matches(
    value: Any, immutable_images: tuple[str, str]
) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
        or not isinstance(immutable_images, tuple)
        or len(immutable_images) != 2
    ):
        return False
    allowed_digests: set[str] = set()
    repositories: set[str] = set()
    for immutable_image in immutable_images:
        if not isinstance(immutable_image, str):
            return False
        repository, separator, digest = immutable_image.rpartition("@")
        if (
            not separator
            or not repository
            or DIGEST_PATTERN.fullmatch(digest.removeprefix("sha256:")) is None
        ):
            return False
        repositories.add(repository)
        allowed_digests.add(digest)
    if len(repositories) != 1 or len(allowed_digests) != 2:
        return False
    match = re.fullmatch(
        r"(?:[a-z][a-z0-9+.-]*://)?"
        r"(?P<repository>[^\s@]+)@(?P<digest>sha256:[0-9a-f]{64})",
        value,
    )
    return bool(
        match
        and match.group("repository") in repositories
        and match.group("digest") in allowed_digests
    )


def _container_status_image_matches_requested(value: Any, requested_image: str) -> bool:
    """Accept digest-only Kubernetes status images with exact Pod provenance."""

    return value == requested_image or (
        isinstance(value, str)
        and KUBERNETES_STATUS_IMAGE_PATTERN.fullmatch(value) is not None
    )


def _validate_evidence_directory(path: Path, *, private_root: Path) -> None:
    PRIVATE_INPUT.validate_private_directory(
        path,
        "backend attestor evidence directory",
        private_root=private_root,
    )


def _write_private_manifest(
    path: Path, document: dict[str, Any], *, private_root: Path
) -> str:
    content = _canonical(document) + b"\n"
    PRIVATE_INPUT.write_private_snapshot(
        destination=path,
        content=content,
        description="backend attestor manifest",
        private_root=private_root,
        allow_existing_exact=True,
    )
    return hashlib.sha256(content).hexdigest()


def validate_probe_observation(
    *, manifest: dict[str, Any], raw: bytes
) -> dict[str, Any]:
    """Validate the fixed probe's exact typed output against the Job manifest."""

    try:
        observation = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "backend attestor probe returned invalid JSON"
        ) from exc
    expected_keys = {
        "schemaVersion",
        "action",
        "runId",
        "locatorSha256",
        "profileRawSha256",
        "profileCanonicalSha256",
        "state",
        "cleanupPerformed",
        "checkedAt",
    }
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    action = (
        labels.get("platform.aileron.dev/backend-action")
        if isinstance(labels, dict)
        else None
    )
    checked_at = observation.get("checkedAt") if isinstance(observation, dict) else None
    try:
        parsed_time = datetime.fromisoformat(checked_at.removesuffix("Z") + "+00:00")
    except (AttributeError, ValueError) as exc:
        raise BackendAttestorError(
            "backend attestor probe timestamp is invalid"
        ) from exc
    if (
        not isinstance(observation, dict)
        or set(observation) != expected_keys
        or not isinstance(labels, dict)
        or not isinstance(annotations, dict)
        or observation.get("schemaVersion") != "aileron-backend-storage-probe/v1"
        or observation.get("action") != action
        or observation.get("runId")
        != labels.get("platform.aileron.dev/acceptance-run-id")
        or observation.get("locatorSha256")
        != annotations.get("platform.aileron.dev/backend-locator-sha256")
        or observation.get("profileRawSha256")
        != annotations.get("platform.aileron.dev/backend-profile-raw-sha256")
        or observation.get("profileCanonicalSha256")
        != annotations.get("platform.aileron.dev/backend-profile-canonical-sha256")
        or observation.get("state") not in {"present", "absent"}
        or not isinstance(observation.get("cleanupPerformed"), bool)
        or (action == "verify" and observation.get("cleanupPerformed") is not False)
        or (action == "cleanup" and observation.get("state") != "absent")
        or not isinstance(checked_at, str)
        or not checked_at.endswith("Z")
        or parsed_time.utcoffset() is None
    ):
        raise BackendAttestorError("backend attestor probe identity is invalid")
    return observation


def _job_selector(manifest: dict[str, Any]) -> str:
    metadata = manifest["metadata"]
    labels = metadata["labels"]
    return ",".join(
        (
            f"job-name={metadata['name']}",
            (
                "platform.aileron.dev/acceptance-run-id="
                f"{labels['platform.aileron.dev/acceptance-run-id']}"
            ),
            (
                "platform.aileron.dev/backend-locator="
                f"{labels['platform.aileron.dev/backend-locator']}"
            ),
        )
    )


def _ensure_job_absent(result: CommandResult, description: str) -> None:
    if result.stdout.strip():
        raise BackendAttestorError(f"{description} still exists")


def _load_job_delete_client(
    *,
    kubeconfig: Path,
    context: str,
    credential_directory: Path,
    private_root: Path,
    runner: Runner,
) -> Any:
    del runner
    return KUBERNETES_REST.load_kubernetes_delete_client(
        kubeconfig=kubeconfig,
        context=context,
        credential_directory=credential_directory,
        private_root=private_root,
    )


def _job_absence_state(
    result: CommandResult, *, expected_job_uid: str | None
) -> bool:
    if not result.stdout.strip():
        return True
    try:
        job = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "backend attestor deleting Job identity is invalid JSON"
        ) from exc
    metadata = job.get("metadata") if isinstance(job, dict) else None
    if (
        not isinstance(metadata, dict)
        or expected_job_uid is None
        or metadata.get("uid") != expected_job_uid
    ):
        raise _JobIdentityConflictError(
            "backend attestor Job was replaced during deletion"
        )
    return False


def _run_reconciled_job_query(
    *,
    runner: Runner,
    command: list[str],
    description: str,
    state_reader: Callable[[CommandResult], Any],
    sleeper: Callable[[float], None] | None = None,
) -> Any:
    """Reconcile an exact-name Job query through its validated identity state."""

    sleep = sleeper or time.sleep
    last_error: BackendAttestorError | None = None
    for attempt in range(JOB_RECONCILE_ATTEMPTS):
        try:
            result = _run_checked(runner, command, description)
            return state_reader(result)
        except _JobIdentityConflictError:
            raise
        except BackendAttestorError as exc:
            last_error = exc
        if attempt + 1 < JOB_RECONCILE_ATTEMPTS:
            sleep(JOB_RECONCILE_INTERVAL_SECONDS)
    error = "backend attestor Job cleanup reconciliation did not converge"
    if last_error is not None:
        error = f"{error}: {last_error}"
    raise BackendAttestorError(error) from last_error


def _cleanup_job_identity_state(
    result: CommandResult, *, manifest: dict[str, Any]
) -> tuple[str, str] | None:
    if not result.stdout.strip():
        return None
    try:
        job = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "backend attestor Job deletion identity is invalid JSON"
        ) from exc
    if not isinstance(job, dict):
        raise BackendAttestorError(
            "backend attestor Job deletion identity has an invalid shape"
        )
    metadata = job.get("metadata")
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("uid"), str)
        or not metadata.get("uid")
        or not isinstance(metadata.get("resourceVersion"), str)
        or not metadata.get("resourceVersion")
        or not isinstance(metadata.get("labels"), dict)
        or not isinstance(metadata.get("annotations"), dict)
    ):
        raise BackendAttestorError(
            "backend attestor Job deletion identity has an invalid shape"
        )
    try:
        return _validate_job_cleanup_identity(manifest=manifest, job=job)
    except BackendAttestorError as exc:
        raise _JobIdentityConflictError(str(exc)) from exc


def _pod_matches_job_identity(
    pod: dict[str, Any], *, expected_job_uid: str | None, expected_job_name: str
) -> bool:
    """Match an owned Pod even when every mutable Pod label has drifted."""

    metadata = pod.get("metadata")
    if not isinstance(metadata, dict):
        raise BackendAttestorError(
            "backend attestor Pod inventory identity is invalid"
        )
    labels = metadata.get("labels", {})
    owner_references = metadata.get("ownerReferences", [])
    if not isinstance(labels, dict) or not isinstance(owner_references, list):
        raise BackendAttestorError(
            "backend attestor Pod inventory identity is invalid"
        )
    if labels.get("batch.kubernetes.io/job-name") == expected_job_name:
        return True
    if (
        expected_job_uid is not None
        and labels.get("batch.kubernetes.io/controller-uid") == expected_job_uid
    ):
        return True
    for owner in owner_references:
        if not isinstance(owner, dict):
            raise BackendAttestorError(
                "backend attestor Pod inventory identity is invalid"
            )
        if (
            owner.get("apiVersion") == "batch/v1"
            and owner.get("kind") == "Job"
            and owner.get("name") == expected_job_name
            and owner.get("controller") is True
            and (
                expected_job_uid is None
                or owner.get("uid") == expected_job_uid
            )
        ):
            return True
    return False


def _poll_owned_workload_absent(
    *,
    runner: Runner,
    job_command: list[str],
    controller_pods_command: list[str] | None,
    job_name_pods_command: list[str],
    all_pods_command: list[str],
    expected_job_uid: str | None,
    expected_job_name: str,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    sleep = sleeper or time.sleep
    for attempt in range(JOB_DELETE_POLL_ATTEMPTS):
        job_absent_before = _run_reconciled_job_query(
            runner=runner,
            command=job_command,
            description="backend attestor Job final absence query",
            state_reader=lambda result: _job_absence_state(
                result, expected_job_uid=expected_job_uid
            ),
            sleeper=sleeper,
        )
        controller_pods: list[dict[str, Any]] = []
        if controller_pods_command is not None:
            controller_result = _run_checked(
                runner,
                controller_pods_command,
                "backend attestor controller UID Pod final absence query",
            )
            controller_pods = _parse_list(
                controller_result,
                "backend attestor controller UID Pod absence query",
            )
        job_name_result = _run_checked(
            runner,
            job_name_pods_command,
            "backend attestor exact Job name Pod final absence query",
        )
        job_name_pods = _parse_list(
            job_name_result,
            "backend attestor exact Job name Pod absence query",
        )
        all_pods_result = _run_checked(
            runner,
            all_pods_command,
            "backend attestor namespace Pod final inventory query",
        )
        owned_inventory_pods = [
            pod
            for pod in _parse_list(
                all_pods_result, "backend attestor namespace Pod inventory query"
            )
            if _pod_matches_job_identity(
                pod,
                expected_job_uid=expected_job_uid,
                expected_job_name=expected_job_name,
            )
        ]
        job_absent_after = _run_reconciled_job_query(
            runner=runner,
            command=job_command,
            description="backend attestor Job final absence confirmation",
            state_reader=lambda result: _job_absence_state(
                result, expected_job_uid=expected_job_uid
            ),
            sleeper=sleeper,
        )
        if (
            job_absent_before
            and not controller_pods
            and not job_name_pods
            and not owned_inventory_pods
            and job_absent_after
        ):
            return
        if attempt + 1 < JOB_DELETE_POLL_ATTEMPTS:
            sleep(JOB_DELETE_POLL_INTERVAL_SECONDS)
    raise BackendAttestorError(
        "backend attestor Job or Pod deletion did not complete"
    )


def _safe_execution_error(error: Exception) -> str:
    if isinstance(error, BackendAttestorError):
        return str(error)
    return f"unexpected {type(error).__name__}"


def _reconcile_attestor_job_cleanup(
    *,
    runner: Runner,
    job_command: list[str],
    job_name_pods_command: list[str],
    all_pods_command: list[str],
    prefix: list[str],
    manifest: dict[str, Any],
    delete_client: Any,
    expected_job_uid: str | None,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Converge an ambiguous Job delete through exact identity observations."""

    sleep = sleeper or time.sleep
    metadata = manifest["metadata"]
    name = metadata["name"]
    namespace = metadata["namespace"]
    failures: list[dict[str, Any]] = []
    current_expected_uid = expected_job_uid
    for attempt in range(JOB_RECONCILE_ATTEMPTS):
        try:
            result = _run_checked(
                runner, job_command, "backend attestor Job deletion identity query"
            )
            current_identity = _cleanup_job_identity_state(
                result, manifest=manifest
            )
        except _JobIdentityConflictError:
            raise
        except BackendAttestorError as exc:
            failures.append(
                {
                    "attempt": attempt + 1,
                    "phase": "identityQuery",
                    "error": _safe_execution_error(exc),
                }
            )
            if attempt + 1 < JOB_RECONCILE_ATTEMPTS:
                sleep(JOB_RECONCILE_INTERVAL_SECONDS)
            continue

        if current_identity is None:
            controller_pods_command = (
                [
                    *prefix,
                    "get",
                    "pods",
                    "--selector",
                    (
                        "batch.kubernetes.io/controller-uid="
                        f"{current_expected_uid}"
                    ),
                    "--output=json",
                ]
                if current_expected_uid is not None
                else None
            )
            _poll_owned_workload_absent(
                runner=runner,
                job_command=job_command,
                controller_pods_command=controller_pods_command,
                job_name_pods_command=job_name_pods_command,
                all_pods_command=all_pods_command,
                expected_job_uid=current_expected_uid,
                expected_job_name=name,
                sleeper=sleeper,
            )
            return

        current_uid, current_resource_version = current_identity
        if (
            current_expected_uid is not None
            and current_uid != current_expected_uid
        ):
            raise _JobIdentityConflictError(
                "backend attestor Job was replaced before deletion"
            )
        current_expected_uid = current_uid
        try:
            delete_client.delete(
                api_version="batch/v1",
                resource="jobs",
                namespace=namespace,
                name=name,
                uid=current_uid,
                resource_version=current_resource_version,
            )
        except Exception:  # noqa: BLE001 - DELETE failure has an ambiguous outcome.
            failures.append(
                {
                    "attempt": attempt + 1,
                    "phase": "delete",
                    "error": "backend attestor preconditioned Job delete outcome is ambiguous",
                }
            )
            continue

        controller_pods_command = [
            *prefix,
            "get",
            "pods",
            "--selector",
            f"batch.kubernetes.io/controller-uid={current_uid}",
            "--output=json",
        ]
        _poll_owned_workload_absent(
            runner=runner,
            job_command=job_command,
            controller_pods_command=controller_pods_command,
            job_name_pods_command=job_name_pods_command,
            all_pods_command=all_pods_command,
            expected_job_uid=current_uid,
            expected_job_name=name,
            sleeper=sleeper,
        )
        return

    if not failures:
        failures.append(
            {
                "attempt": JOB_RECONCILE_ATTEMPTS,
                "phase": "confirmation",
                "error": "backend attestor Job cleanup confirmation was not observed",
            }
        )
    raise BackendAttestorError(
        "backend attestor Job cleanup transaction did not converge: "
        + json.dumps(failures, separators=(",", ":"), sort_keys=True)
    )


def _validate_attestor_runtime_results(
    *,
    manifest: dict[str, Any],
    image: AttestorImage,
    job_result: CommandResult,
    pods_result: CommandResult,
) -> dict[str, Any]:
    try:
        job = json.loads(job_result.stdout)
        pods = json.loads(pods_result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError(
            "backend attestor runtime identity is invalid JSON"
        ) from exc
    return validate_attestor_job_identity(
        manifest=manifest, job=job, pods=pods, image=image
    )


def _execute_attestor_job(
    *,
    action: str,
    locator: dict[str, Any],
    profile: ExecutionProfile,
    image: AttestorImage,
    execution_resources: ExecutionResources,
    kubeconfig: Path,
    context: str,
    run_id: str,
    evidence_directory: Path,
    runner: Runner = _subprocess_runner,
    cleanup_authorization: CleanupAuthorization | None = None,
) -> dict[str, Any]:
    """Run one fixed Job and prove its result, provenance, and final deletion."""

    _validate_evidence_directory(
        evidence_directory, private_root=profile.private_root
    )
    manifest = build_attestor_job_manifest(
        action=action,
        locator=locator,
        profile=profile,
        image=image,
        execution_resources=execution_resources,
        kubeconfig=kubeconfig,
        context=context,
        run_id=run_id,
        runner=runner,
        cleanup_authorization=cleanup_authorization,
    )
    namespace = manifest["metadata"]["namespace"]
    name = manifest["metadata"]["name"]
    selector = _job_selector(manifest)
    manifest_path = evidence_directory / f"{name}.json"
    manifest_sha256 = _write_private_manifest(
        manifest_path, manifest, private_root=profile.private_root
    )
    prefix = [*_kubectl_prefix(kubeconfig, context), "--namespace", namespace]
    wait_prefix = [
        *_kubectl_prefix(kubeconfig, context, request_timeout="310s"),
        "--namespace",
        namespace,
    ]
    preflight_command = [
        *prefix,
        "get",
        "job",
        name,
        "--ignore-not-found=true",
        "--output=json",
    ]
    preflight = _run_checked(
        runner, preflight_command, "backend attestor Job preflight query"
    )
    _ensure_job_absent(preflight, "backend attestor Job before create")
    if action == "cleanup":
        if not isinstance(cleanup_authorization, CleanupAuthorization):
            raise BackendAttestorError(
                "backend cleanup authorization disappeared before create"
            )
        _authorize_backend_cleanup(
            binding=cleanup_authorization.binding,
            profile=profile,
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
        )
    _validate_attestor_execution_identity(
        locator=locator,
        profile=profile,
        execution_resources=execution_resources,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    create_command = [
        *prefix,
        "create",
        "--filename",
        str(manifest_path),
        "--output=json",
    ]
    wait_command = [
        *wait_prefix,
        "wait",
        "--for=condition=complete",
        f"job/{name}",
        "--timeout=5m",
    ]
    job_command = [*prefix, "get", "job", name, "--output=json"]
    pods_command = [
        *prefix,
        "get",
        "pods",
        "--selector",
        selector,
        "--output=json",
    ]
    absent_job_command = [
        *prefix,
        "get",
        "job",
        name,
        "--ignore-not-found=true",
        "--output=json",
    ]
    job_name_pods_command = [
        *prefix,
        "get",
        "pods",
        "--selector",
        f"batch.kubernetes.io/job-name={name}",
        "--output=json",
    ]
    all_pods_command = [*prefix, "get", "pods", "--output=json"]
    delete_client = _load_job_delete_client(
        kubeconfig=kubeconfig,
        context=context,
        credential_directory=evidence_directory,
        private_root=profile.private_root,
        runner=runner,
    )
    create_attempted = False
    created_uid: str | None = None
    primary_error: Exception | None = None
    cleanup_errors: list[str] = []
    result_document: dict[str, Any] | None = None
    try:
        create_attempted = True
        create_result = _run_checked(
            runner, create_command, "backend attestor Job create"
        )
        try:
            create_response = json.loads(create_result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendAttestorError(
                "backend attestor create response identity is invalid JSON"
            ) from exc
        created_uid, _ = _validate_job_cleanup_identity(
            manifest=manifest, job=create_response
        )
        _validate_created_job_identity(manifest=manifest, job=create_response)
        created_result = _run_checked(
            runner, job_command, "backend attestor created Job identity query"
        )
        try:
            created_job = json.loads(created_result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendAttestorError(
                "backend attestor created Job identity is invalid JSON"
            ) from exc
        reread_uid, _ = _validate_created_job_identity(
            manifest=manifest, job=created_job
        )
        if reread_uid != created_uid:
            raise BackendAttestorError(
                "backend attestor Job changed identity after create"
            )
        _run_checked(runner, wait_command, "backend attestor Job wait")
        job_result = _run_checked(
            runner, job_command, "backend attestor Job identity query"
        )
        pods_result = _run_checked(
            runner, pods_command, "backend attestor Pod identity query"
        )
        provenance = _validate_attestor_runtime_results(
            manifest=manifest,
            image=image,
            job_result=job_result,
            pods_result=pods_result,
        )
        if provenance["jobUid"] != created_uid:
            raise BackendAttestorError(
                "backend attestor Job changed identity during execution"
            )
        pre_logs_job_result = _run_checked(
            runner, job_command, "backend attestor pre-logs Job identity query"
        )
        pre_logs_pods_result = _run_checked(
            runner, pods_command, "backend attestor pre-logs Pod identity query"
        )
        pre_logs_provenance = _validate_attestor_runtime_results(
            manifest=manifest,
            image=image,
            job_result=pre_logs_job_result,
            pods_result=pre_logs_pods_result,
        )
        if pre_logs_provenance != provenance:
            raise BackendAttestorError(
                "backend attestor runtime identity changed before logs"
            )
        logs_command = [
            *prefix,
            "logs",
            f"pod/{provenance['podName']}",
            "--container=backend-attestor",
        ]
        logs_result = _run_checked(runner, logs_command, "backend attestor probe logs")
        post_logs_job_result = _run_checked(
            runner, job_command, "backend attestor post-logs Job identity query"
        )
        post_logs_pods_result = _run_checked(
            runner, pods_command, "backend attestor post-logs Pod identity query"
        )
        post_logs_provenance = _validate_attestor_runtime_results(
            manifest=manifest,
            image=image,
            job_result=post_logs_job_result,
            pods_result=post_logs_pods_result,
        )
        if post_logs_provenance != provenance:
            raise BackendAttestorError(
                "backend attestor runtime identity changed while reading logs"
            )
        observation = validate_probe_observation(
            manifest=manifest, raw=logs_result.stdout
        )
        _validate_attestor_execution_identity(
            locator=locator,
            profile=profile,
            execution_resources=execution_resources,
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
        )
        result_document = {
            "schemaVersion": "aileron-backend-attestor-result/v1",
            "action": action,
            "runId": run_id,
            "locatorSha256": locator_sha256(locator),
            "manifestPath": str(manifest_path),
            "manifestSha256": manifest_sha256,
            "profileRawSha256": profile.raw_sha256,
            "profileCanonicalSha256": profile.canonical_sha256,
            "imageInventorySha256": image.inventory_sha256,
            "provenance": provenance,
            "observation": observation,
        }
    except Exception as exc:  # noqa: BLE001 - transaction must aggregate all failures.
        primary_error = exc
    finally:
        if create_attempted:
            try:
                _reconcile_attestor_job_cleanup(
                    runner=runner,
                    job_command=absent_job_command,
                    job_name_pods_command=job_name_pods_command,
                    all_pods_command=all_pods_command,
                    prefix=prefix,
                    manifest=manifest,
                    delete_client=delete_client,
                    expected_job_uid=created_uid,
                )
            except Exception as exc:  # noqa: BLE001 - cleanup must preserve primary.
                cleanup_errors.append(_safe_execution_error(exc))
    if primary_error is not None or cleanup_errors:
        failures = []
        if primary_error is not None:
            failures.append(
                {"phase": "primary", "error": _safe_execution_error(primary_error)}
            )
        failures.extend(
            {"phase": "finalCleanup", "error": error} for error in cleanup_errors
        )
        raise BackendAttestorError(
            "backend attestor execution failed: "
            + json.dumps(failures, separators=(",", ":"), sort_keys=True)
        )
    if result_document is None:
        raise BackendAttestorError("backend attestor produced no result")
    return result_document


def _cleanup_and_verify_backend(
    *,
    locator: dict[str, Any],
    profile: ExecutionProfile,
    image: AttestorImage,
    execution_resources: ExecutionResources,
    cleanup_targets: CleanupTargetBinding,
    kubeconfig: Path,
    context: str,
    run_id: str,
    evidence_directory: Path,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Run cleanup and verification with pre/post non-atomic PV collision gates."""

    authorization = _authorize_backend_cleanup(
        binding=cleanup_targets,
        profile=profile,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    cleanup_result = _execute_attestor_job(
        action="cleanup",
        locator=locator,
        profile=profile,
        image=image,
        execution_resources=execution_resources,
        kubeconfig=kubeconfig,
        context=context,
        run_id=run_id,
        evidence_directory=evidence_directory,
        runner=runner,
        cleanup_authorization=authorization,
    )
    _authorize_backend_cleanup(
        binding=cleanup_targets,
        profile=profile,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    verification_result = _execute_attestor_job(
        action="verify",
        locator=locator,
        profile=profile,
        image=image,
        execution_resources=execution_resources,
        kubeconfig=kubeconfig,
        context=context,
        run_id=run_id,
        evidence_directory=evidence_directory,
        runner=runner,
    )
    _authorize_backend_cleanup(
        binding=cleanup_targets,
        profile=profile,
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    if verification_result["observation"]["state"] != "absent":
        raise BackendAttestorError("backend verification remained present")
    return {
        "schemaVersion": "aileron-backend-attestation/v1",
        "runId": run_id,
        "locatorSha256": locator_sha256(locator),
        "snapshotSha256": cleanup_targets.snapshot_sha256,
        "cleanup": cleanup_result,
        "verification": verification_result,
        "absent": True,
        "trustBoundary": {
            "atomicWithPersistentVolumeInventory": False,
            "exclusiveOperationalControlRequired": True,
            "postDeleteCollisionChecks": True,
            "description": BACKEND_CLEANUP_TRUST_BOUNDARY,
        },
    }


def _execute_signed_backend_cleanup_target(
    inputs: SignedBackendAttestorInputs,
    *,
    persistent_volume_name: str,
    persistent_volume_uid: str,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Execute one target selected only by its signed PV identity."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    _validate_signed_backend_cleanup_preconditions(inputs, runner=runner)
    targets = list(inputs.cleanup_targets)
    matches = [
        target
        for target in targets
        if target.persistent_volume_name == persistent_volume_name
        and target.persistent_volume_uid == persistent_volume_uid
    ]
    if len(matches) != 1:
        raise BackendAttestorError("signed PersistentVolume cleanup target is invalid")
    target = matches[0]
    evidence_directory = (
        inputs.private_root / "reset" / inputs.commit / inputs.run_id
    )
    attestation = _cleanup_and_verify_backend(
        locator=target.locator,
        profile=inputs.profile,
        image=inputs.image,
        execution_resources=inputs.execution_resources,
        cleanup_targets=target,
        kubeconfig=inputs.kubeconfig,
        context=inputs.context,
        run_id=inputs.run_id,
        evidence_directory=evidence_directory,
        runner=runner,
    )
    return {
        "persistentVolume": {
            "name": target.persistent_volume_name,
            "uid": target.persistent_volume_uid,
        },
        "locatorSha256": target.locator_sha256,
        "cleanupResultSha256": hashlib.sha256(
            _canonical(attestation["cleanup"])
        ).hexdigest(),
        "verificationResultSha256": hashlib.sha256(
            _canonical(attestation["verification"])
        ).hexdigest(),
        "attestation": attestation,
    }


def execute_signed_backend_cleanup_target(
    inputs: SignedBackendAttestorInputs,
    *,
    persistent_volume_name: str,
    persistent_volume_uid: str,
) -> dict[str, Any]:
    """Resume one cleanup target without accepting a raw backend locator."""

    return _execute_signed_backend_cleanup_target(
        inputs,
        persistent_volume_name=persistent_volume_name,
        persistent_volume_uid=persistent_volume_uid,
    )


def _validate_signed_backend_cleanup_preconditions(
    inputs: SignedBackendAttestorInputs,
    *,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Validate every deterministic and live prerequisite before any cleanup."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    profile = _revalidate_profile(inputs.profile)
    image = _revalidate_image(inputs.image)
    resources = _revalidate_execution_resources(profile, inputs.execution_resources)
    _validate_kubeconfig(inputs.kubeconfig, private_root=inputs.private_root)
    context = _validate_context(inputs.context)
    targets = list(inputs.cleanup_targets)
    if targets:
        validate_cleanup_target_set(bindings=targets, profile=profile)
    for target in targets:
        _validate_attestor_execution_identity(
            locator=target.locator,
            profile=profile,
            execution_resources=resources,
            kubeconfig=inputs.kubeconfig,
            context=context,
            runner=runner,
        )
    return {
        "schemaVersion": "aileron-backend-cleanup-preconditions/v1",
        "runId": inputs.run_id,
        "snapshotSha256": inputs.snapshot_sha256,
        "profileRawSha256": profile.raw_sha256,
        "profileCanonicalSha256": profile.canonical_sha256,
        "imageInventorySha256": image.inventory_sha256,
        "targetCount": len(targets),
        "ready": True,
    }


def validate_signed_backend_cleanup_preconditions(
    inputs: SignedBackendAttestorInputs,
) -> dict[str, Any]:
    """Fail before deletion unless every signed target can execute safely."""

    return _validate_signed_backend_cleanup_preconditions(inputs)


def _validate_attestor_result_document(
    *,
    result: Any,
    action: str,
    locator_digest: str,
    run_id: str,
    evidence_directory: Path,
    private_root: Path,
) -> dict[str, Any]:
    expected_keys = {
        "schemaVersion",
        "action",
        "runId",
        "locatorSha256",
        "manifestPath",
        "manifestSha256",
        "profileRawSha256",
        "profileCanonicalSha256",
        "imageInventorySha256",
        "provenance",
        "observation",
    }
    manifest_path = evidence_directory / (
        _attestor_job_name(
            action=action, locator_digest=locator_digest, run_id=run_id
        )
        + ".json"
    )
    if (
        not isinstance(result, dict)
        or set(result) != expected_keys
        or result.get("schemaVersion") != "aileron-backend-attestor-result/v1"
        or result.get("action") != action
        or result.get("runId") != run_id
        or result.get("locatorSha256") != locator_digest
        or result.get("manifestPath") != str(manifest_path)
        or DIGEST_PATTERN.fullmatch(result.get("manifestSha256", "")) is None
        or DIGEST_PATTERN.fullmatch(result.get("profileRawSha256", "")) is None
        or DIGEST_PATTERN.fullmatch(result.get("profileCanonicalSha256", "")) is None
        or DIGEST_PATTERN.fullmatch(result.get("imageInventorySha256", "")) is None
    ):
        raise BackendAttestorError("backend attestor evidence result is invalid")
    raw_manifest = PRIVATE_INPUT.read_private_bytes(
        manifest_path,
        f"backend {action} manifest evidence",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=private_root,
    )
    if hashlib.sha256(raw_manifest).hexdigest() != result["manifestSha256"]:
        raise BackendAttestorError("backend attestor manifest digest does not match")
    try:
        manifest = json.loads(raw_manifest)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError("backend attestor manifest is invalid JSON") from exc
    if raw_manifest != _canonical(manifest) + b"\n":
        raise BackendAttestorError("backend attestor manifest is not canonical")
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    labels = metadata.get("labels") if isinstance(metadata, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    containers = (
        manifest.get("spec", {}).get("template", {}).get("spec", {}).get("containers")
        if isinstance(manifest, dict)
        else None
    )
    if (
        not isinstance(labels, dict)
        or not isinstance(annotations, dict)
        or labels.get("platform.aileron.dev/backend-action") != action
        or labels.get("platform.aileron.dev/acceptance-run-id") != run_id
        or annotations.get("platform.aileron.dev/backend-locator-sha256")
        != locator_digest
        or annotations.get("platform.aileron.dev/backend-profile-raw-sha256")
        != result["profileRawSha256"]
        or annotations.get("platform.aileron.dev/backend-profile-canonical-sha256")
        != result["profileCanonicalSha256"]
        or annotations.get("platform.aileron.dev/image-inventory-sha256")
        != result["imageInventorySha256"]
        or not isinstance(containers, list)
        or len(containers) != 1
        or not isinstance(containers[0], dict)
    ):
        raise BackendAttestorError("backend attestor manifest identity is invalid")
    provenance = result.get("provenance")
    immutable_image = str(containers[0].get("image"))
    runtime_immutable_image = annotations.get(
        "platform.aileron.dev/runtime-immutable-image"
    )
    if (
        not isinstance(runtime_immutable_image, str)
        or IMMUTABLE_IMAGE_PATTERN.fullmatch(runtime_immutable_image) is None
        or runtime_immutable_image.rsplit("@", 1)[0]
        != immutable_image.rsplit("@", 1)[0]
        or runtime_immutable_image == immutable_image
        or not isinstance(provenance, dict)
        or set(provenance) != {"jobUid", "podName", "podUid", "imageId"}
        or any(
            not isinstance(provenance.get(key), str) or not provenance[key]
            for key in ("jobUid", "podName", "podUid")
        )
        or not _runtime_image_id_matches(
            provenance.get("imageId"),
            (immutable_image, runtime_immutable_image),
        )
    ):
        raise BackendAttestorError("backend attestor provenance is invalid")
    observation = validate_probe_observation(
        manifest=manifest,
        raw=_canonical(result.get("observation")),
    )
    if (
        observation.get("state") != "absent"
        or action == "verify"
        and observation.get("cleanupPerformed") is not False
    ):
        raise BackendAttestorError("backend attestor absence evidence is invalid")
    return copy.deepcopy(result)


def validate_backend_attestation(
    document: Any,
    *,
    locator: dict[str, Any],
    run_id: str,
    snapshot_sha256: str,
    evidence_directory: Path,
) -> dict[str, Any]:
    """Validate one complete cleanup and read-only verification attestation."""

    private_root = PRIVATE_INPUT.private_root_path()
    PRIVATE_INPUT.validate_private_directory(
        evidence_directory,
        "backend attestor evidence directory",
        private_root=private_root,
    )
    locator_digest = locator_sha256(locator)
    if (
        RUN_ID_PATTERN.fullmatch(run_id) is None
        or DIGEST_PATTERN.fullmatch(snapshot_sha256) is None
        or not isinstance(document, dict)
        or set(document)
        != {
            "schemaVersion",
            "runId",
            "locatorSha256",
            "snapshotSha256",
            "cleanup",
            "verification",
            "absent",
            "trustBoundary",
        }
        or document.get("schemaVersion") != "aileron-backend-attestation/v1"
        or document.get("runId") != run_id
        or document.get("locatorSha256") != locator_digest
        or document.get("snapshotSha256") != snapshot_sha256
        or document.get("absent") is not True
        or document.get("trustBoundary")
        != {
            "atomicWithPersistentVolumeInventory": False,
            "exclusiveOperationalControlRequired": True,
            "postDeleteCollisionChecks": True,
            "description": BACKEND_CLEANUP_TRUST_BOUNDARY,
        }
    ):
        raise BackendAttestorError("backend attestation evidence is invalid")
    cleanup = _validate_attestor_result_document(
        result=document["cleanup"],
        action="cleanup",
        locator_digest=locator_digest,
        run_id=run_id,
        evidence_directory=evidence_directory,
        private_root=private_root,
    )
    verification = _validate_attestor_result_document(
        result=document["verification"],
        action="verify",
        locator_digest=locator_digest,
        run_id=run_id,
        evidence_directory=evidence_directory,
        private_root=private_root,
    )
    for identity_key in (
        "profileRawSha256",
        "profileCanonicalSha256",
        "imageInventorySha256",
    ):
        if cleanup[identity_key] != verification[identity_key]:
            raise BackendAttestorError("backend attestation identity changed")
    return copy.deepcopy(document)


def validate_backend_cleanup_results(
    document: Any,
    *,
    inputs: SignedBackendAttestorInputs,
) -> dict[str, Any]:
    """Validate the canonical reset aggregate against all live-trusted inputs."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    expected_keys = {
        "schemaVersion",
        "commit",
        "runId",
        "snapshotSha256",
        "profileRawSha256",
        "profileCanonicalSha256",
        "imageInventorySha256",
        "results",
        "allAbsent",
    }
    if (
        not isinstance(document, dict)
        or set(document) != expected_keys
        or document.get("schemaVersion") != "aileron-backend-cleanup-results/v1"
        or document.get("commit") != inputs.commit
        or document.get("runId") != inputs.run_id
        or document.get("snapshotSha256") != inputs.snapshot_sha256
        or document.get("profileRawSha256") != inputs.profile.raw_sha256
        or document.get("profileCanonicalSha256")
        != inputs.profile.canonical_sha256
        or document.get("imageInventorySha256") != inputs.image.inventory_sha256
        or document.get("allAbsent") is not True
        or not isinstance(document.get("results"), list)
    ):
        raise BackendAttestorError("backend cleanup aggregate identity is invalid")
    targets = list(inputs.cleanup_targets)
    if targets:
        validate_cleanup_target_set(bindings=targets, profile=inputs.profile)
    expected_targets = {
        (
            target.persistent_volume_name,
            target.persistent_volume_uid,
            target.locator_sha256,
        ): target
        for target in targets
    }
    if len(expected_targets) != len(targets):
        raise BackendAttestorError("signed backend target identity is ambiguous")
    expected_order = [
        (
            target.persistent_volume_name,
            target.persistent_volume_uid,
            target.locator_sha256,
        )
        for target in targets
    ]
    observed_targets: set[tuple[str, str, str]] = set()
    for index, result in enumerate(document["results"]):
        if not isinstance(result, dict) or not isinstance(
            result.get("persistentVolume"), dict
        ):
            raise BackendAttestorError("backend cleanup aggregate result is invalid")
        identity = (
            result["persistentVolume"].get("name"),
            result["persistentVolume"].get("uid"),
            result.get("locatorSha256"),
        )
        target = expected_targets.get(identity)
        if (
            target is None
            or identity in observed_targets
            or index >= len(expected_order)
            or identity != expected_order[index]
        ):
            raise BackendAttestorError("backend cleanup aggregate target is invalid")
        validate_backend_cleanup_target_result(
            result,
            inputs=inputs,
            persistent_volume_name=target.persistent_volume_name,
            persistent_volume_uid=target.persistent_volume_uid,
        )
        observed_targets.add(identity)
    if observed_targets != set(expected_targets):
        raise BackendAttestorError("backend cleanup aggregate target set is incomplete")
    return copy.deepcopy(document)


def validate_backend_cleanup_target_result(
    result: Any,
    *,
    inputs: SignedBackendAttestorInputs,
    persistent_volume_name: str,
    persistent_volume_uid: str,
) -> dict[str, Any]:
    """Validate one journaled target result against its sole signed PV."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    targets = list(inputs.cleanup_targets)
    if targets:
        validate_cleanup_target_set(bindings=targets, profile=inputs.profile)
    matches = [
        target
        for target in targets
        if target.persistent_volume_name == persistent_volume_name
        and target.persistent_volume_uid == persistent_volume_uid
    ]
    if len(matches) != 1:
        raise BackendAttestorError("signed PersistentVolume cleanup target is invalid")
    target = matches[0]
    if (
        not isinstance(result, dict)
        or set(result)
        != {
            "persistentVolume",
            "locatorSha256",
            "cleanupResultSha256",
            "verificationResultSha256",
            "attestation",
        }
        or result.get("persistentVolume")
        != {
            "name": target.persistent_volume_name,
            "uid": target.persistent_volume_uid,
        }
        or result.get("locatorSha256") != target.locator_sha256
    ):
        raise BackendAttestorError("backend cleanup target result is invalid")
    evidence_directory = (
        inputs.private_root / "reset" / inputs.commit / inputs.run_id
    )
    attestation = validate_backend_attestation(
        result.get("attestation"),
        locator=target.locator,
        run_id=inputs.run_id,
        snapshot_sha256=inputs.snapshot_sha256,
        evidence_directory=evidence_directory,
    )
    if (
        result.get("cleanupResultSha256")
        != hashlib.sha256(_canonical(attestation["cleanup"])).hexdigest()
        or result.get("verificationResultSha256")
        != hashlib.sha256(_canonical(attestation["verification"])).hexdigest()
    ):
        raise BackendAttestorError(
            "backend cleanup target result digest does not match"
        )
    return copy.deepcopy(result)


def load_backend_cleanup_results(
    inputs: SignedBackendAttestorInputs,
) -> dict[str, Any]:
    """Load the sole canonical write-once reset aggregate."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    path = (
        inputs.private_root
        / "reset"
        / inputs.commit
        / inputs.run_id
        / "backend-cleanup-results.json"
    )
    raw = PRIVATE_INPUT.read_private_bytes(
        path,
        "backend cleanup aggregate",
        maximum_size=MAX_PRIVATE_INPUT_BYTES,
        private_root=inputs.private_root,
    )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAttestorError("backend cleanup aggregate is invalid JSON") from exc
    if raw != _canonical(document) + b"\n":
        raise BackendAttestorError("backend cleanup aggregate is not canonical")
    return validate_backend_cleanup_results(document, inputs=inputs)


def _verify_signed_backend_absence(
    inputs: SignedBackendAttestorInputs,
    *,
    runner: Runner = _subprocess_runner,
) -> dict[str, Any]:
    """Run only read-only verify Jobs after validating the reset aggregate."""

    aggregate = load_backend_cleanup_results(inputs)
    acceptance_directory = (
        inputs.private_root / "evidence" / inputs.commit / inputs.run_id
    )
    targets = list(inputs.cleanup_targets)
    if targets:
        validate_cleanup_target_set(bindings=targets, profile=inputs.profile)
    verifications: list[dict[str, Any]] = []
    for target in targets:
        result = _execute_attestor_job(
            action="verify",
            locator=target.locator,
            profile=inputs.profile,
            image=inputs.image,
            execution_resources=inputs.execution_resources,
            kubeconfig=inputs.kubeconfig,
            context=inputs.context,
            run_id=inputs.run_id,
            evidence_directory=acceptance_directory,
            runner=runner,
        )
        if result["observation"]["state"] != "absent":
            raise BackendAttestorError("post-reset backend verification remained present")
        verifications.append(
            {
                "persistentVolume": {
                    "name": target.persistent_volume_name,
                    "uid": target.persistent_volume_uid,
                },
                "locatorSha256": target.locator_sha256,
                "verificationResultSha256": hashlib.sha256(
                    _canonical(result)
                ).hexdigest(),
                "verification": result,
            }
        )
    document = {
        "schemaVersion": "aileron-backend-post-reset-verification/v1",
        "commit": inputs.commit,
        "runId": inputs.run_id,
        "snapshotSha256": inputs.snapshot_sha256,
        "backendCleanupResultsSha256": hashlib.sha256(
            _canonical(aggregate) + b"\n"
        ).hexdigest(),
        "verifications": verifications,
        "allAbsent": all(
            item["verification"]["observation"]["state"] == "absent"
            for item in verifications
        ),
    }
    return validate_backend_post_reset_verification(document, inputs=inputs)


def validate_backend_post_reset_verification(
    document: Any,
    *,
    inputs: SignedBackendAttestorInputs,
) -> dict[str, Any]:
    """Validate post-reset read-only evidence and every referenced manifest."""

    if not isinstance(inputs, SignedBackendAttestorInputs):
        raise ValueError("live-trusted signed backend inputs are required")
    aggregate = load_backend_cleanup_results(inputs)
    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "schemaVersion",
            "commit",
            "runId",
            "snapshotSha256",
            "backendCleanupResultsSha256",
            "verifications",
            "allAbsent",
        }
        or document.get("schemaVersion")
        != "aileron-backend-post-reset-verification/v1"
        or document.get("commit") != inputs.commit
        or document.get("runId") != inputs.run_id
        or document.get("snapshotSha256") != inputs.snapshot_sha256
        or document.get("backendCleanupResultsSha256")
        != hashlib.sha256(_canonical(aggregate) + b"\n").hexdigest()
        or document.get("allAbsent") is not True
        or not isinstance(document.get("verifications"), list)
        or len(document["verifications"]) != len(inputs.cleanup_targets)
    ):
        raise BackendAttestorError(
            "backend post-reset verification identity is invalid"
        )
    evidence_directory = (
        inputs.private_root / "evidence" / inputs.commit / inputs.run_id
    )
    for target, item in zip(inputs.cleanup_targets, document["verifications"]):
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "persistentVolume",
                "locatorSha256",
                "verificationResultSha256",
                "verification",
            }
            or item.get("persistentVolume")
            != {
                "name": target.persistent_volume_name,
                "uid": target.persistent_volume_uid,
            }
            or item.get("locatorSha256") != target.locator_sha256
        ):
            raise BackendAttestorError(
                "backend post-reset verification target is invalid"
            )
        verification = _validate_attestor_result_document(
            result=item.get("verification"),
            action="verify",
            locator_digest=target.locator_sha256,
            run_id=inputs.run_id,
            evidence_directory=evidence_directory,
            private_root=inputs.private_root,
        )
        if (
            item.get("verificationResultSha256")
            != hashlib.sha256(_canonical(verification)).hexdigest()
            or verification.get("profileRawSha256") != inputs.profile.raw_sha256
            or verification.get("profileCanonicalSha256")
            != inputs.profile.canonical_sha256
            or verification.get("imageInventorySha256")
            != inputs.image.inventory_sha256
        ):
            raise BackendAttestorError(
                "backend post-reset verification digest is invalid"
            )
    return copy.deepcopy(document)


def verify_signed_backend_absence(
    inputs: SignedBackendAttestorInputs,
) -> dict[str, Any]:
    """Independently verify backend absence without exposing a cleanup surface."""

    return _verify_signed_backend_absence(inputs)
