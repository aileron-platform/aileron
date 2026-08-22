"""Closed HomeLab soak query, snapshot, and cadence contract."""

from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, NamedTuple

SOAK_DURATION_SECONDS = 1800
SOAK_SAMPLE_INTERVAL_SECONDS = 60
SOAK_MAXIMUM_SAMPLE_GAP_SECONDS = 75
SOAK_MINIMUM_SAMPLES = 31
SOAK_MAXIMUM_CLOCK_DRIFT_MILLISECONDS = 2000
WORKSPACE_NAMESPACE = "workspace-system"
MANAGED_NAMESPACES = {
    "aileron-identity-system",
    "aileron-turn-system",
    WORKSPACE_NAMESPACE,
}
SERVICE_COMPONENTS = ("runtime", "browser", "canvas")
TARGET_WORKSPACE_CONTROLLER_COMPONENTS = (
    "workspace-runtime",
    "workspace-browser",
    "workspace-canvas",
)
WORKSPACE_COMPONENT_ANNOTATIONS = {
    "aileron.io/component-revision",
    "aileron.io/component-instance-id",
    "aileron.io/runtime-instance-id",
    "aileron.io/runtime-access-revision",
    "aileron.io/knowledge-base-mount-revision",
    "aileron.io/browser-credential-revision",
    "aileron.io/browser-credential-key-id",
    "aileron.io/browser-credential-algorithm",
}
FIXED_CONTROLLER_DESCRIPTORS = {
    ("aileron-identity-system", "aileron-identity-keycloak"): (
        "Deployment",
        "aileron-identity-keycloak",
    ),
    ("aileron-identity-system", "aileron-identity-postgres"): (
        "Deployment",
        "aileron-identity-postgres",
    ),
    ("aileron-turn-system", "aileron-coturn"): ("DaemonSet", "coturn"),
    (WORKSPACE_NAMESPACE, "aileron-frontend"): ("Deployment", "frontend"),
    (WORKSPACE_NAMESPACE, "aileron-workspace-manager"): (
        "Deployment",
        "workspace-manager",
    ),
    (WORKSPACE_NAMESPACE, "aileron-workspace-operator"): (
        "Deployment",
        "workspace-operator",
    ),
    (WORKSPACE_NAMESPACE, "aileron-postgres"): ("StatefulSet", "postgres"),
    (WORKSPACE_NAMESPACE, "aileron-redis"): ("StatefulSet", "redis"),
    (WORKSPACE_NAMESPACE, "aileron-workspace-firewall-attestor"): (
        "DaemonSet",
        "workspace-firewall-attestor",
    ),
    (WORKSPACE_NAMESPACE, "aileron-connectivity-evidence-gateway"): (
        "Deployment",
        "connectivity-evidence-gateway",
    ),
    (WORKSPACE_NAMESPACE, "aileron-connectivity-host-agent"): (
        "DaemonSet",
        "connectivity-external-agent",
    ),
}
SERVICE_PORTS = {
    "runtime": [
        {"name": "http", "port": 3002, "protocol": "TCP", "targetPort": 3002},
        {
            "name": "terminal",
            "port": 3004,
            "protocol": "TCP",
            "targetPort": 3004,
        },
    ],
    "browser": [
        {
            "name": "webrtc",
            "port": 6080,
            "protocol": "TCP",
            "targetPort": 6080,
        },
        {"name": "cdp", "port": 9223, "protocol": "TCP", "targetPort": 9223},
        {
            "name": "connectivity-evidence",
            "port": 8082,
            "protocol": "TCP",
            "targetPort": 8082,
        },
    ],
    "canvas": [
        {"name": "http", "port": 3003, "protocol": "TCP", "targetPort": 3003},
        {"name": "api", "port": 3013, "protocol": "TCP", "targetPort": 3013},
    ],
}
ENDPOINT_SLICE_MANAGED_BY = "endpointslice-controller.k8s.io"
ENDPOINT_SLICE_SERVICE_NAME_LABEL = "kubernetes.io/service-name"
ENDPOINT_SLICE_MANAGED_BY_LABEL = "endpointslice.kubernetes.io/managed-by"
ENDPOINT_SLICE_TRIGGER_ANNOTATION = "endpoints.kubernetes.io/last-change-trigger-time"
BROWSER_CONTAINER_NAME = "browser"
BROWSER_READINESS_SCRIPT = """exec >/dev/null 2>&1
browser_config=/tmp/aileron-browser/neko.generated.yaml
[ -f "${browser_config}" ] &&
[ ! -L "${browser_config}" ] &&
[ "$(stat -c '%a:%u' "${browser_config}")" = "600:$(id -u)" ] &&
awk '
/^[^[:space:]#]/ {
  if ($0 !~ /^[A-Za-z_][A-Za-z0-9_-]*:[[:space:]]*$/) {
    noncanonical_top_level_lines++
    next
  }
  section = $0
  sub(/:[[:space:]]*$/, "", section)
  managed_nested = 0
  if (section == "member") member_sections++
  if (section == "webrtc") webrtc_sections++
  next
}
(section == "member" || section == "webrtc") {
  if ($0 ~ /^[[:space:]]*$/ || $0 ~ /^[[:space:]]*#/) next
  if ($0 ~ /^  [^[:space:]]/) {
    if ($0 !~ /^  [A-Za-z_][A-Za-z0-9_-]*:([[:space:]]|$)/) {
      noncanonical_managed_children++
      next
    }
    managed_nested = $0 ~ /^  [A-Za-z_][A-Za-z0-9_-]*:[[:space:]]*(#.*)?$/
  } else if ($0 ~ /^    / && managed_nested) {
    next
  } else {
    noncanonical_managed_children++
    next
  }
}
section == "member" && /^  provider:[[:space:]]*/ {
  member_providers++
  if ($0 ~ /^  provider:[[:space:]]*multiuser[[:space:]]*$/) valid_member_providers++
}
section == "webrtc" && /^  icelite:[[:space:]]*/ {
  webrtc_icelite_values++
  if ($0 ~ /^  icelite:[[:space:]]*false[[:space:]]*$/) valid_webrtc_icelite_values++
}
END {
  valid = member_sections == 1 && webrtc_sections == 1 &&
    member_providers == 1 && valid_member_providers == 1 &&
    webrtc_icelite_values == 1 && valid_webrtc_icelite_values == 1 &&
    noncanonical_top_level_lines == 0 && noncanonical_managed_children == 0
  exit valid ? 0 : 1
}
' "${browser_config}" &&
curl --fail --silent --max-time 1 http://127.0.0.1:6080/health &&
curl --fail --silent --max-time 1 http://127.0.0.1:9223/json/version"""
BROWSER_READINESS_COMMAND = ("/bin/sh", "-ec", BROWSER_READINESS_SCRIPT)
BROWSER_READINESS_PROBE_LENGTH = 1731
BROWSER_READINESS_PROBE_SHA256 = (
    "83e6cbe28dc5bde234c4a36ca6a3a872d437b54e62c25a077356dd8c7d41d082"
)
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^run-[a-z0-9][a-z0-9-]{6,57}[a-z0-9]$")
IMMUTABLE_IMAGE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$"
)
UUID_VALUE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
KUBERNETES_SAFE_HASH = re.compile(r"^[bcdfghjklmnpqrstvwxz2456789]+$")
RUNTIME_IMAGE_ID = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://)?"
    r"[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:([0-9a-f]{64})$"
)
KUBERNETES_STATUS_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
RUNTIME_CONTAINER_ID = re.compile(r"^containerd://[0-9a-f]{64}$")
UTC_RFC3339 = re.compile(
    r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"
    r"T(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]{1,9}))?Z$"
)


class SoakValidationError(ValueError):
    """Raised when a fixed soak policy or live snapshot is invalid."""


def _container_status_image_matches_spec(value: Any, spec_image: str) -> bool:
    """Accept digest-only Kubernetes status images with a pinned Pod spec."""

    return value == spec_image or (
        isinstance(value, str) and KUBERNETES_STATUS_IMAGE.fullmatch(value) is not None
    )


def _kubernetes_generated_name_matches(
    metadata: Any, *, expected_generate_name: str
) -> bool:
    if not isinstance(metadata, dict):
        return False
    generate_name = metadata.get("generateName")
    name = metadata.get("name")
    if not isinstance(generate_name, str) or generate_name != expected_generate_name:
        return False
    effective_base = generate_name[:58]
    suffix = (
        name[len(effective_base) :]
        if isinstance(name, str) and name.startswith(effective_base)
        else None
    )
    return (
        isinstance(suffix, str)
        and len(suffix) == 5
        and KUBERNETES_SAFE_HASH.fullmatch(suffix) is not None
    )


def release_image_runtime_pairs(
    release_images: Any,
) -> dict[str, frozenset[str]]:
    """Project a verified signed inventory onto index-to-runtime digest pairs."""

    if not isinstance(release_images, list) or len(release_images) not in {10, 11}:
        raise SoakValidationError("soak signed image inventory is invalid")
    pairs: dict[str, frozenset[str]] = {}
    for image in release_images:
        if not isinstance(image, dict):
            raise SoakValidationError("soak signed image inventory is invalid")
        immutable_image = image.get("immutableImage")
        runtime_image = image.get("runtimeImmutableImage")
        if (
            not isinstance(immutable_image, str)
            or IMMUTABLE_IMAGE.fullmatch(immutable_image) is None
            or not isinstance(runtime_image, str)
            or IMMUTABLE_IMAGE.fullmatch(runtime_image) is None
            or immutable_image == runtime_image
            or immutable_image.rsplit("@", 1)[0] != runtime_image.rsplit("@", 1)[0]
            or immutable_image in pairs
        ):
            raise SoakValidationError("soak signed image inventory is invalid")
        pairs[immutable_image] = frozenset(
            {
                immutable_image.rsplit("@sha256:", 1)[1],
                runtime_image.rsplit("@sha256:", 1)[1],
            }
        )
    return pairs


def _validated_image_runtime_pairs(
    image_runtime_pairs: Any,
) -> Mapping[str, frozenset[str]]:
    if not isinstance(image_runtime_pairs, Mapping) or len(image_runtime_pairs) not in {
        10,
        11,
    }:
        raise SoakValidationError("soak signed image runtime mapping is invalid")
    for immutable_image, allowed_digests in image_runtime_pairs.items():
        index_digest = (
            immutable_image.rsplit("@sha256:", 1)[1]
            if isinstance(immutable_image, str)
            and IMMUTABLE_IMAGE.fullmatch(immutable_image) is not None
            else None
        )
        if (
            not isinstance(allowed_digests, frozenset)
            or len(allowed_digests) != 2
            or index_digest not in allowed_digests
            or any(
                not isinstance(digest, str) or IMAGE_DIGEST.fullmatch(digest) is None
                for digest in allowed_digests
            )
        ):
            raise SoakValidationError("soak signed image runtime mapping is invalid")
    return image_runtime_pairs


class SoakPolicy(NamedTuple):
    duration_seconds: int
    sample_interval_seconds: int
    maximum_sample_gap_seconds: int
    minimum_samples: int
    maximum_clock_drift_milliseconds: int


class _WorkspaceIdentity(NamedTuple):
    name: str
    uid: str
    workspace_id: str
    owner_id: str
    runtime_instance_id: str
    document: dict[str, Any]


class _WorkspaceServiceAccount(NamedTuple):
    document: dict[str, Any]
    workspace: _WorkspaceIdentity
    namespace: str
    name: str
    uid: str
    image_pull_secrets: list[dict[str, str]]


def validate_policy(contract: dict[str, Any]) -> SoakPolicy:
    """Return the only production soak policy."""

    values = (
        contract.get("minimumSoakSeconds"),
        contract.get("soakSampleIntervalSeconds"),
        contract.get("maximumSoakSampleGapSeconds"),
        contract.get("minimumSoakSamples"),
        contract.get("maximumSoakClockDriftMilliseconds"),
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise SoakValidationError("soak policy is invalid")
    policy = SoakPolicy(*values)
    expected = SoakPolicy(
        SOAK_DURATION_SECONDS,
        SOAK_SAMPLE_INTERVAL_SECONDS,
        SOAK_MAXIMUM_SAMPLE_GAP_SECONDS,
        SOAK_MINIMUM_SAMPLES,
        SOAK_MAXIMUM_CLOCK_DRIFT_MILLISECONDS,
    )
    if policy != expected:
        raise SoakValidationError("soak policy is unsupported")
    return policy


def build_query_commands(
    *, kubeconfig: str, context: str, workspace_id: str, identity_mode: str
) -> dict[str, list[str]]:
    """Build the fixed nine-query observation set for both identity modes."""

    if not all(
        isinstance(value, str) and value
        for value in (kubeconfig, context, workspace_id)
    ) or identity_mode not in {"bundledKeycloak", "externalOidc"}:
        raise SoakValidationError("soak query identity is invalid")
    prefix = [
        "kubectl",
        "--kubeconfig",
        kubeconfig,
        "--context",
        context,
        "--request-timeout=10s",
    ]

    def pod_list(namespace: str) -> list[str]:
        return [
            *prefix,
            "get",
            "pods",
            "--all-namespaces",
            "--field-selector",
            f"metadata.namespace={namespace}",
            "--output=json",
        ]

    return {
        "identityPods": pod_list("aileron-identity-system"),
        "turnPods": pod_list("aileron-turn-system"),
        "workspacePods": pod_list(WORKSPACE_NAMESPACE),
        "workspace": [
            *prefix,
            "get",
            "workspaces.platform.aileron.io",
            "--namespace",
            WORKSPACE_NAMESPACE,
            "--output=json",
        ],
        "workspaceServiceAccounts": [
            *prefix,
            "get",
            "serviceaccounts",
            "--namespace",
            WORKSPACE_NAMESPACE,
            "--output=json",
        ],
        "services": [
            *prefix,
            "get",
            "services",
            "--namespace",
            WORKSPACE_NAMESPACE,
            "--output=json",
        ],
        "endpointSlices": [
            *prefix,
            "get",
            "endpointslices.discovery.k8s.io",
            "--namespace",
            WORKSPACE_NAMESPACE,
            "--output=json",
        ],
        "browserPods": [
            *prefix,
            "get",
            "pods",
            "--all-namespaces",
            "--field-selector",
            f"metadata.namespace={WORKSPACE_NAMESPACE}",
            "--selector",
            (
                f"aileron.io/workspace-id={workspace_id},"
                "aileron.io/component=workspace-browser"
            ),
            "--output=json",
        ],
        "controllers": [
            *prefix,
            "get",
            (
                "deployments.apps,statefulsets.apps,daemonsets.apps,"
                "replicasets.apps,controllerrevisions.apps,jobs.batch"
            ),
            "--all-namespaces",
            "--output=json",
        ],
    }


def _canonical_digest(value: Any) -> str:
    try:
        raw = json.dumps(
            value, allow_nan=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SoakValidationError("soak snapshot is not canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _workspace_status_digest(status: dict[str, Any]) -> str:
    canonical_status = copy.deepcopy(status)
    browser_connectivity = canonical_status.get("browserConnectivity")
    if isinstance(browser_connectivity, dict):
        for field in (
            "acceptedAt",
            "expiresAt",
            "backendAcceptedAt",
            "backendExpiresAt",
            "frontendAcceptedAt",
            "frontendExpiresAt",
        ):
            browser_connectivity.pop(field, None)
    return _canonical_digest(canonical_status)


def _same_unordered_unique_items(left: Any, right: Any) -> bool:
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    left_digests = [_canonical_digest(item) for item in left]
    right_digests = [_canonical_digest(item) for item in right]
    return (
        len(left_digests) == len(set(left_digests))
        and len(right_digests) == len(set(right_digests))
        and sorted(left_digests) == sorted(right_digests)
    )


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _positive_integer(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _nonnegative_integer(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _utc_rfc3339(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = UTC_RFC3339.fullmatch(value)
    if match is None:
        return False
    try:
        datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second")),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return False
    return True


def _exact_owner(
    metadata: dict[str, Any], expected: tuple[str, str, str, str] | None
) -> None:
    references = metadata.get("ownerReferences", [])
    if expected is None:
        if references != []:
            raise SoakValidationError("soak owner reference is invalid")
        return
    api_version, kind, name, uid = expected
    if references != [
        {
            "apiVersion": api_version,
            "kind": kind,
            "name": name,
            "uid": uid,
            "controller": True,
            "blockOwnerDeletion": True,
        }
    ]:
        raise SoakValidationError("soak owner reference is invalid")


def _list_items(
    document: Any,
    *,
    source: str,
    allowed_gvks: set[tuple[str, str]],
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or document.get("apiVersion") != "v1"
        or document.get("kind") != "List"
        or not isinstance(document.get("items"), list)
    ):
        raise SoakValidationError(f"soak {source} root List is invalid")
    result: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str, str]] = set()
    uids: set[str] = set()
    for item in document["items"]:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        item_namespace = (
            metadata.get("namespace") if isinstance(metadata, dict) else None
        )
        name = metadata.get("name") if isinstance(metadata, dict) else None
        uid = metadata.get("uid") if isinstance(metadata, dict) else None
        identity = (
            item.get("apiVersion") if isinstance(item, dict) else "",
            item.get("kind") if isinstance(item, dict) else "",
            item_namespace,
            name,
        )
        if (
            not isinstance(item, dict)
            or (item.get("apiVersion"), item.get("kind")) not in allowed_gvks
            or not isinstance(metadata, dict)
            or not _nonempty(item_namespace)
            or not _nonempty(name)
            or not _nonempty(uid)
            or (namespace is not None and item_namespace != namespace)
            or identity in identities
            or uid in uids
        ):
            raise SoakValidationError(f"soak {source} item identity is invalid")
        identities.add(identity)
        uids.add(uid)
        result.append(item)
    return result


def _labels(value: Any, *, message: str) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or not value
        or any(not _nonempty(key) or not _nonempty(item) for key, item in value.items())
    ):
        raise SoakValidationError(message)
    return value


def _workspace_labels(workspace: _WorkspaceIdentity, component: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/part-of": "aileron",
        "aileron.io/workspace-id": workspace.workspace_id,
        "aileron.io/owner-id": workspace.owner_id,
        "aileron.io/component": component,
        "aileron.io/firewall-group": (
            "browser" if component == "workspace-browser" else "workspace"
        ),
    }


def _workspace_inventory(
    document: Any, *, target_workspace_id: str
) -> tuple[dict[str, _WorkspaceIdentity], _WorkspaceIdentity, dict[str, Any]]:
    items = _list_items(
        document,
        source="Workspace",
        allowed_gvks={("platform.aileron.io/v1alpha1", "Workspace")},
        namespace=WORKSPACE_NAMESPACE,
    )
    by_uid: dict[str, _WorkspaceIdentity] = {}
    by_id: dict[str, _WorkspaceIdentity] = {}
    target_snapshot: dict[str, Any] | None = None
    target: _WorkspaceIdentity | None = None
    for item in items:
        metadata = item["metadata"]
        spec = item.get("spec")
        if (
            not isinstance(spec, dict)
            or "deletionTimestamp" in metadata
            or not _nonempty(metadata.get("name"))
            or not _nonempty(metadata.get("uid"))
            or not _positive_integer(metadata.get("generation"))
            or not _nonempty(spec.get("workspaceId"))
            or not _nonempty(spec.get("ownerId"))
            or metadata["name"] != f"workspace-{spec['workspaceId']}"
        ):
            raise SoakValidationError("soak Workspace identity is invalid")
        _exact_owner(metadata, None)
        runtime = spec.get("runtime")
        browser = spec.get("browser")
        canvas = spec.get("canvas")
        if (
            not isinstance(runtime, dict)
            or not isinstance(runtime.get("instanceId"), str)
            or UUID_VALUE.fullmatch(runtime["instanceId"]) is None
            or runtime.get("desiredState") not in {"Running", "Stopped"}
            or not _positive_integer(runtime.get("revision"))
            or not _nonnegative_integer(runtime.get("mountRevision"))
            or not _nonnegative_integer(runtime.get("accessRevision"))
            or not isinstance(runtime.get("image"), str)
            or IMMUTABLE_IMAGE.fullmatch(runtime["image"]) is None
            or not isinstance(browser, dict)
            or not isinstance(browser.get("enabled"), bool)
            or browser.get("desiredState") not in {"Running", "Stopped"}
            or not isinstance(browser.get("instanceId"), str)
            or UUID_VALUE.fullmatch(browser["instanceId"]) is None
            or not _positive_integer(browser.get("revision"))
            or not isinstance(browser.get("image"), str)
            or IMMUTABLE_IMAGE.fullmatch(browser["image"]) is None
            or not _positive_integer(browser.get("credentialRevision"))
            or not _nonempty(browser.get("credentialKeyId"))
            or browser.get("credentialAlgorithm") != "hkdf-sha256-v1"
            or not isinstance(canvas, dict)
            or not isinstance(canvas.get("enabled"), bool)
            or canvas.get("desiredState") not in {"Running", "Stopped"}
            or not isinstance(canvas.get("instanceId"), str)
            or UUID_VALUE.fullmatch(canvas["instanceId"]) is None
            or not _positive_integer(canvas.get("revision"))
            or not isinstance(canvas.get("image"), str)
            or IMMUTABLE_IMAGE.fullmatch(canvas["image"]) is None
        ):
            raise SoakValidationError("soak Workspace runtime identity is invalid")
        identity = _WorkspaceIdentity(
            metadata["name"],
            metadata["uid"],
            spec["workspaceId"],
            spec["ownerId"],
            runtime["instanceId"],
            item,
        )
        if identity.uid in by_uid or identity.workspace_id in by_id:
            raise SoakValidationError("soak Workspace inventory is ambiguous")
        by_uid[identity.uid] = identity
        by_id[identity.workspace_id] = identity
        if identity.workspace_id != target_workspace_id:
            continue
        status = item.get("status")
        generation = metadata.get("generation")
        components = status.get("components") if isinstance(status, dict) else None
        component_specs = [spec.get(name) for name in SERVICE_COMPONENTS]
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
            or not isinstance(status, dict)
            or status.get("observedGeneration") != generation
            or status.get("phase") != "Running"
            or not isinstance(components, dict)
            or any(
                not isinstance(component_spec, dict)
                or component_spec.get("desiredState") != "Running"
                for component_spec in component_specs
            )
            or spec.get("browser", {}).get("enabled") is not True
            or spec.get("canvas", {}).get("enabled") is not True
            or any(
                not isinstance(components.get(name), dict)
                or components[name].get("phase") != "Running"
                or components[name].get("ready") is not True
                for name in SERVICE_COMPONENTS
            )
        ):
            raise SoakValidationError("soak target Workspace is not Running")
        target = identity
        target_snapshot = {
            "name": identity.name,
            "namespace": WORKSPACE_NAMESPACE,
            "uid": identity.uid,
            "generation": generation,
            "observedGeneration": generation,
            "specSha256": _canonical_digest(spec),
            "statusSha256": _workspace_status_digest(status),
        }
    if target is None or target_snapshot is None:
        raise SoakValidationError("soak target Workspace is missing")
    return by_uid, target, target_snapshot


def _workspace_service_account_inventory(
    items: list[dict[str, Any]],
    *,
    workspaces: dict[str, _WorkspaceIdentity],
    target: _WorkspaceIdentity,
) -> tuple[dict[str, _WorkspaceServiceAccount], list[dict[str, Any]]]:
    expected_by_name = {
        f"workspace-workload-{workspace.workspace_id}": workspace
        for workspace in workspaces.values()
    }
    by_workspace_uid: dict[str, _WorkspaceServiceAccount] = {}
    target_snapshots: list[dict[str, Any]] = []
    for document in items:
        metadata = document["metadata"]
        name = metadata["name"]
        labels_value = metadata.get("labels")
        references = metadata.get("ownerReferences", [])
        owner_uid_value = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        owner_uid = owner_uid_value if _nonempty(owner_uid_value) else None
        expected_workspace = expected_by_name.get(name)
        claims_workspace = (
            expected_workspace is not None
            or name.startswith("workspace-workload-")
            or owner_uid in workspaces
            or (
                isinstance(references, list)
                and any(
                    isinstance(reference, dict) and reference.get("kind") == "Workspace"
                    for reference in references
                )
            )
            or (
                isinstance(labels_value, dict)
                and (
                    "aileron.io/workspace-id" in labels_value
                    or labels_value.get("aileron.io/component") == "workspace-workload"
                )
            )
        )
        if not claims_workspace:
            continue
        if expected_workspace is None:
            raise SoakValidationError(
                "soak Workspace ServiceAccount identity is invalid"
            )
        labels = _labels(
            labels_value,
            message="soak Workspace ServiceAccount labels are invalid",
        )
        image_pull_secrets = document.get("imagePullSecrets", [])
        legacy_secrets = document.get("secrets", [])
        if (
            document.get("apiVersion") != "v1"
            or document.get("kind") != "ServiceAccount"
            or metadata.get("namespace") != WORKSPACE_NAMESPACE
            or "deletionTimestamp" in metadata
            or labels != _workspace_labels(expected_workspace, "workspace-workload")
            or document.get("automountServiceAccountToken") is not False
            or not isinstance(image_pull_secrets, list)
            or not isinstance(legacy_secrets, list)
            or legacy_secrets
        ):
            raise SoakValidationError(
                "soak Workspace ServiceAccount projection is invalid"
            )
        pull_secret_names: set[str] = set()
        for reference in image_pull_secrets:
            if (
                not isinstance(reference, dict)
                or set(reference) != {"name"}
                or not _nonempty(reference.get("name"))
                or reference["name"] in pull_secret_names
            ):
                raise SoakValidationError(
                    "soak Workspace ServiceAccount imagePullSecrets are invalid"
                )
            pull_secret_names.add(reference["name"])
        _exact_owner(
            metadata,
            (
                "platform.aileron.io/v1alpha1",
                "Workspace",
                expected_workspace.name,
                expected_workspace.uid,
            ),
        )
        if expected_workspace.uid in by_workspace_uid:
            raise SoakValidationError(
                "soak Workspace ServiceAccount inventory is ambiguous"
            )
        projection = {
            "labels": labels,
            "ownerReferences": metadata.get("ownerReferences", []),
            "automountServiceAccountToken": False,
            "imagePullSecrets": image_pull_secrets,
            "secrets": legacy_secrets,
        }
        state = _WorkspaceServiceAccount(
            document,
            expected_workspace,
            metadata["namespace"],
            name,
            metadata["uid"],
            copy.deepcopy(image_pull_secrets),
        )
        by_workspace_uid[expected_workspace.uid] = state
        if expected_workspace.uid == target.uid:
            target_snapshots.append(
                {
                    "namespace": state.namespace,
                    "name": state.name,
                    "uid": state.uid,
                    "workspaceId": expected_workspace.workspace_id,
                    "projectionSha256": _canonical_digest(projection),
                }
            )
    if set(by_workspace_uid) != set(workspaces):
        raise SoakValidationError(
            "soak Workspace ServiceAccount inventory is incomplete"
        )
    return by_workspace_uid, target_snapshots


class _ControllerState(NamedTuple):
    document: dict[str, Any]
    namespace: str
    name: str
    uid: str
    kind: str
    component: str
    workspace: _WorkspaceIdentity | None
    include: bool
    labels: dict[str, str]
    selector: dict[str, str]
    template_labels: dict[str, str]
    desired: int
    pod_revision: str | None


def _selector_labels(spec: Any, *, message: str) -> dict[str, str]:
    selector = spec.get("selector") if isinstance(spec, dict) else None
    if (
        not isinstance(selector, dict)
        or set(selector) != {"matchLabels"}
        or not isinstance(selector.get("matchLabels"), dict)
    ):
        raise SoakValidationError(message)
    return _labels(selector["matchLabels"], message=message)


def _labels_match(selector: Mapping[str, str], labels: Mapping[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in selector.items())


def _validate_images(template_spec: Any, *, message: str) -> None:
    if not isinstance(template_spec, dict) or template_spec.get("ephemeralContainers"):
        raise SoakValidationError(message)
    containers = template_spec.get("containers")
    init_containers = template_spec.get("initContainers", [])
    if (
        not isinstance(containers, list)
        or not containers
        or not isinstance(init_containers, list)
    ):
        raise SoakValidationError(message)
    names: set[str] = set()
    for container in [*containers, *init_containers]:
        if (
            not isinstance(container, dict)
            or not _nonempty(container.get("name"))
            or container["name"] in names
            or not isinstance(container.get("image"), str)
            or IMMUTABLE_IMAGE.fullmatch(container["image"]) is None
        ):
            raise SoakValidationError(message)
        names.add(container["name"])


def _replica_count(document: dict[str, Any], *, allow_zero: bool) -> int:
    kind = document["kind"]
    metadata = document["metadata"]
    spec = document.get("spec")
    status = document.get("status")
    if (
        not isinstance(spec, dict)
        or not isinstance(status, dict)
        or status.get("observedGeneration") != metadata.get("generation")
    ):
        raise SoakValidationError("soak controller replica status is invalid")
    if kind == "DaemonSet":
        desired = status.get("desiredNumberScheduled")
        fields = (
            "currentNumberScheduled",
            "numberReady",
            "updatedNumberScheduled",
            "numberAvailable",
        )
        unavailable = status.get("numberUnavailable", 0)
        misscheduled = status.get("numberMisscheduled")
    else:
        desired = spec.get("replicas")
        if kind == "Deployment":
            fields = (
                "replicas",
                "readyReplicas",
                "updatedReplicas",
                "availableReplicas",
            )
        elif kind == "StatefulSet":
            fields = (
                "replicas",
                "currentReplicas",
                "readyReplicas",
                "updatedReplicas",
                "availableReplicas",
            )
            if not _nonempty(status.get("currentRevision")) or status.get(
                "currentRevision"
            ) != status.get("updateRevision"):
                raise SoakValidationError(
                    "soak StatefulSet revision status is incomplete"
                )
        elif kind == "ReplicaSet":
            fields = (
                "replicas",
                "fullyLabeledReplicas",
                "readyReplicas",
                "availableReplicas",
            )
        else:
            raise SoakValidationError("soak controller kind is invalid")
        unavailable = status.get("unavailableReplicas", 0)
        misscheduled = 0
    minimum = 0 if allow_zero else 1
    if (
        isinstance(desired, bool)
        or not isinstance(desired, int)
        or desired < minimum
        or unavailable != 0
        or isinstance(misscheduled, bool)
        or misscheduled != 0
        or any(status.get(field, 0) != desired for field in fields)
    ):
        raise SoakValidationError("soak controller replica status is incomplete")
    return desired


def _workspace_component_desired(workspace: _WorkspaceIdentity, component: str) -> int:
    key = component.removeprefix("workspace-")
    value = workspace.document.get("spec", {}).get(key)
    if not isinstance(value, dict):
        raise SoakValidationError("soak Workspace component spec is invalid")
    if key in {"browser", "canvas"} and value.get("enabled") is not True:
        return 0
    return 1 if value.get("desiredState") == "Running" else 0


def _workspace_component_annotations(
    workspace: _WorkspaceIdentity, component: str
) -> dict[str, str]:
    key = component.removeprefix("workspace-")
    component_spec = workspace.document["spec"][key]
    annotations = {
        "aileron.io/component-revision": str(component_spec["revision"]),
        "aileron.io/component-instance-id": component_spec["instanceId"],
    }
    if key == "runtime":
        annotations.update(
            {
                "aileron.io/runtime-instance-id": component_spec["instanceId"],
                "aileron.io/runtime-access-revision": str(
                    component_spec["accessRevision"]
                ),
                "aileron.io/knowledge-base-mount-revision": str(
                    component_spec["mountRevision"]
                ),
            }
        )
    elif key == "browser":
        annotations.update(
            {
                "aileron.io/browser-credential-revision": str(
                    component_spec["credentialRevision"]
                ),
                "aileron.io/browser-credential-key-id": component_spec[
                    "credentialKeyId"
                ],
                "aileron.io/browser-credential-algorithm": component_spec[
                    "credentialAlgorithm"
                ],
            }
        )
    return annotations


def _workspace_component_annotation_projection(
    annotations: Any,
) -> dict[str, str] | None:
    if not isinstance(annotations, dict):
        return None
    return {
        key: value
        for key, value in annotations.items()
        if key in WORKSPACE_COMPONENT_ANNOTATIONS
    }


def _validate_workspace_status_bindings(
    *,
    workspaces: Mapping[str, _WorkspaceIdentity],
    validated_pods: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    pod_uids: dict[tuple[str, str], list[str]] = {}
    for _, snapshot in validated_pods:
        workspace_id = snapshot.get("workspaceId")
        component = snapshot.get("component")
        pod_uid = snapshot.get("podUid")
        if workspace_id is None:
            continue
        if (
            not _nonempty(workspace_id)
            or not _nonempty(component)
            or not _nonempty(pod_uid)
        ):
            raise SoakValidationError("soak Workspace Pod status identity is invalid")
        pod_uids.setdefault((workspace_id, component), []).append(pod_uid)

    for workspace in workspaces.values():
        metadata = workspace.document["metadata"]
        spec = workspace.document["spec"]
        status = workspace.document.get("status")
        components = status.get("components") if isinstance(status, dict) else None
        if (
            not isinstance(status, dict)
            or not _positive_integer(status.get("observedGeneration"))
            or status.get("observedGeneration") != metadata.get("generation")
            or not isinstance(components, dict)
        ):
            raise SoakValidationError("soak Workspace status is stale or incomplete")
        for key in SERVICE_COMPONENTS:
            component = f"workspace-{key}"
            desired = _workspace_component_desired(workspace, component)
            component_spec = spec[key]
            component_status = components.get(key)
            matching_pod_uids = pod_uids.get((workspace.workspace_id, component), [])
            if not isinstance(component_status, dict):
                raise SoakValidationError(
                    "soak Workspace component status is incomplete"
                )
            if desired == 1:
                if (
                    len(matching_pod_uids) != 1
                    or component_status.get("phase") != "Running"
                    or component_status.get("ready") is not True
                    or component_status.get("observedInstanceId")
                    != component_spec.get("instanceId")
                    or not _positive_integer(component_status.get("observedRevision"))
                    or component_status.get("observedRevision")
                    != component_spec.get("revision")
                    or component_status.get("podUid") != matching_pod_uids[0]
                ):
                    raise SoakValidationError(
                        "soak Workspace component status does not bind its running Pod"
                    )
                if key == "runtime" and (
                    component_status.get("terminalReady") is not True
                    or not _nonnegative_integer(
                        component_status.get("mountObservedRevision")
                    )
                    or component_status.get("mountObservedRevision")
                    != component_spec.get("mountRevision")
                    or not _nonnegative_integer(
                        component_status.get("lastKnownGoodMountRevision")
                    )
                    or component_status.get("lastKnownGoodMountRevision")
                    != component_spec.get("mountRevision")
                    or not _nonnegative_integer(
                        component_status.get("accessObservedRevision")
                    )
                    or component_status.get("accessObservedRevision")
                    != component_spec.get("accessRevision")
                ):
                    raise SoakValidationError(
                        "soak Runtime status revision fence is incomplete"
                    )
                if key == "browser" and (
                    not _positive_integer(
                        component_status.get("credentialObservedRevision")
                    )
                    or component_status.get("credentialObservedRevision")
                    != component_spec.get("credentialRevision")
                    or component_status.get("credentialObservedKeyId")
                    != component_spec.get("credentialKeyId")
                    or component_status.get("credentialObservedAlgorithm")
                    != component_spec.get("credentialAlgorithm")
                ):
                    raise SoakValidationError(
                        "soak Browser credential status is incomplete"
                    )
                continue

            expected_phase = (
                "Disabled"
                if key in {"browser", "canvas"}
                and component_spec.get("enabled") is False
                else "Stopped"
            )
            expected_reason = f"{key.capitalize()}{expected_phase}"
            if (
                matching_pod_uids
                or component_status.get("phase") != expected_phase
                or component_status.get("ready") is not False
                or isinstance(component_status.get("observedRevision"), bool)
                or not isinstance(component_status.get("observedRevision"), int)
                or component_status.get("observedRevision") != 0
                or "observedInstanceId" in component_status
                or "podUid" in component_status
                or "terminalReady" in component_status
                or component_status.get("reason") != expected_reason
            ):
                raise SoakValidationError(
                    "soak stopped Workspace component status is not cleared"
                )
            if key == "runtime":
                revision_fields = (
                    component_status.get("mountObservedRevision"),
                    component_status.get("lastKnownGoodMountRevision"),
                    component_status.get("accessObservedRevision"),
                )
                if any(not _nonnegative_integer(value) for value in revision_fields):
                    raise SoakValidationError(
                        "soak stopped Runtime revision status is invalid"
                    )
            elif (
                isinstance(component_status.get("credentialObservedRevision"), bool)
                or not isinstance(
                    component_status.get("credentialObservedRevision"), int
                )
                or component_status.get("credentialObservedRevision") != 0
                or "credentialObservedKeyId" in component_status
                or "credentialObservedAlgorithm" in component_status
            ):
                raise SoakValidationError(
                    "soak stopped optional component credential status is not cleared"
                )
        desired_components = {
            key: _workspace_component_desired(workspace, f"workspace-{key}")
            for key in SERVICE_COMPONENTS
        }
        required_status_keys = ["runtime"] + [
            key for key in ("browser", "canvas") if spec[key].get("enabled") is True
        ]
        expected_workspace_phase = (
            "Stopped"
            if all(value == 0 for value in desired_components.values())
            else (
                "Running"
                if all(
                    components[key].get("phase") == "Running"
                    for key in required_status_keys
                )
                else "Reconciling"
            )
        )
        if status.get("phase") != expected_workspace_phase:
            raise SoakValidationError("soak Workspace phase is inconsistent")


def _validate_fixed_controller_labels(
    *,
    state_namespace: str,
    state_name: str,
    component: str,
    labels: dict[str, str],
    selector: dict[str, str],
    template_labels: dict[str, str],
) -> None:
    if state_namespace == "aileron-identity-system":
        if (
            set(labels)
            != {
                "app.kubernetes.io/part-of",
                "app.kubernetes.io/managed-by",
                "helm.sh/chart",
            }
            or labels.get("app.kubernetes.io/part-of") != "aileron-identity"
            or labels.get("app.kubernetes.io/managed-by") != "Helm"
            or not _nonempty(labels.get("helm.sh/chart"))
            or selector != {"app.kubernetes.io/name": state_name}
            or template_labels
            != {
                "app.kubernetes.io/name": state_name,
                "app.kubernetes.io/part-of": "aileron-identity",
            }
        ):
            raise SoakValidationError("soak fixed controller labels are invalid")
        return
    expected_metadata_keys = {
        "helm.sh/chart",
        "app.kubernetes.io/name",
        "app.kubernetes.io/instance",
        "app.kubernetes.io/version",
        "app.kubernetes.io/managed-by",
        "app.kubernetes.io/part-of",
    }
    components_with_metadata_label = {
        "coturn",
        "workspace-firewall-attestor",
        "connectivity-evidence-gateway",
        "connectivity-external-agent",
    }
    if component in components_with_metadata_label:
        expected_metadata_keys.add("app.kubernetes.io/component")
    expected_selector = {
        "app.kubernetes.io/name": "aileron",
        "app.kubernetes.io/instance": "aileron",
        "app.kubernetes.io/component": component,
    }
    expected_template = dict(expected_selector)
    if component not in {
        "connectivity-evidence-gateway",
        "connectivity-external-agent",
    }:
        expected_template["app.kubernetes.io/part-of"] = "aileron"
    if (
        set(labels) != expected_metadata_keys
        or labels.get("app.kubernetes.io/name") != "aileron"
        or labels.get("app.kubernetes.io/instance") != "aileron"
        or labels.get("app.kubernetes.io/managed-by") != "Helm"
        or labels.get("app.kubernetes.io/part-of") != "aileron"
        or not _nonempty(labels.get("helm.sh/chart"))
        or not _nonempty(labels.get("app.kubernetes.io/version"))
        or (
            component in components_with_metadata_label
            and labels.get("app.kubernetes.io/component") != component
        )
        or selector != expected_selector
        or template_labels != expected_template
    ):
        raise SoakValidationError("soak fixed controller labels are invalid")


def _controller_state(
    document: dict[str, Any],
    *,
    component: str,
    workspace: _WorkspaceIdentity | None,
    include: bool,
) -> tuple[_ControllerState, dict[str, Any]]:
    metadata = document["metadata"]
    spec = document.get("spec")
    template = spec.get("template") if isinstance(spec, dict) else None
    template_metadata = template.get("metadata") if isinstance(template, dict) else None
    template_spec = template.get("spec") if isinstance(template, dict) else None
    if (
        document.get("apiVersion") != "apps/v1"
        or document.get("kind") not in {"Deployment", "StatefulSet", "DaemonSet"}
        or "deletionTimestamp" in metadata
        or not _nonempty(metadata.get("name"))
        or not _nonempty(metadata.get("namespace"))
        or not _nonempty(metadata.get("uid"))
        or isinstance(metadata.get("generation"), bool)
        or not isinstance(metadata.get("generation"), int)
        or metadata["generation"] < 1
        or not isinstance(spec, dict)
        or not isinstance(template_metadata, dict)
        or not isinstance(template_spec, dict)
    ):
        raise SoakValidationError("soak controller identity is invalid")
    labels = _labels(
        metadata.get("labels"), message="soak controller labels are invalid"
    )
    selector = _selector_labels(spec, message="soak controller selector is invalid")
    template_labels = _labels(
        template_metadata.get("labels"),
        message="soak controller template labels are invalid",
    )
    if not _labels_match(selector, template_labels):
        raise SoakValidationError(
            "soak controller selector does not select its template"
        )
    _validate_images(template_spec, message="soak controller image contract is invalid")
    if workspace is None:
        _exact_owner(metadata, None)
        _validate_fixed_controller_labels(
            state_namespace=metadata["namespace"],
            state_name=metadata["name"],
            component=component,
            labels=labels,
            selector=selector,
            template_labels=template_labels,
        )
        desired = _replica_count(document, allow_zero=False)
    else:
        _exact_owner(
            metadata,
            (
                "platform.aileron.io/v1alpha1",
                "Workspace",
                workspace.name,
                workspace.uid,
            ),
        )
        expected_labels = _workspace_labels(workspace, component)
        expected_template_labels = dict(expected_labels)
        if component == "workspace-runtime":
            expected_template_labels["aileron.io/runtime-instance-id"] = (
                workspace.runtime_instance_id
            )
        expected_annotations = _workspace_component_annotations(workspace, component)
        component_key = component.removeprefix("workspace-")
        component_spec = workspace.document["spec"][component_key]
        containers = template_spec.get("containers")
        canonical_container_name = {
            "runtime": "runtime",
            "browser": "browser",
            "canvas": "canvas",
        }[component_key]
        canonical_containers = (
            [
                item
                for item in containers
                if isinstance(item, dict)
                and item.get("name") == canonical_container_name
            ]
            if isinstance(containers, list)
            else []
        )
        if (
            labels != expected_labels
            or selector != expected_labels
            or template_labels != expected_template_labels
            or template_spec.get("serviceAccountName")
            != f"workspace-workload-{workspace.workspace_id}"
            or "imagePullSecrets" in template_spec
            or _workspace_component_annotation_projection(metadata.get("annotations"))
            != expected_annotations
            or _workspace_component_annotation_projection(
                template_metadata.get("annotations")
            )
            != expected_annotations
            or len(canonical_containers) != 1
            or canonical_containers[0].get("image") != component_spec.get("image")
        ):
            raise SoakValidationError("soak Workspace controller projection is invalid")
        if component_key == "runtime":
            init_containers = template_spec.get("initContainers")
            if (
                not isinstance(init_containers, list)
                or len(init_containers) != 1
                or not isinstance(init_containers[0], dict)
                or init_containers[0].get("name") != "runtime-home-initializer"
                or init_containers[0].get("image") != component_spec.get("image")
            ):
                raise SoakValidationError(
                    "soak Runtime initializer projection is invalid"
                )
        expected_desired = _workspace_component_desired(workspace, component)
        desired = _replica_count(document, allow_zero=True)
        if desired != expected_desired:
            raise SoakValidationError("soak Workspace controller replicas are invalid")
    state = _ControllerState(
        document,
        metadata["namespace"],
        metadata["name"],
        metadata["uid"],
        document["kind"],
        component,
        workspace,
        include,
        labels,
        selector,
        template_labels,
        desired,
        None,
    )
    snapshot = {
        "namespace": state.namespace,
        "kind": state.kind,
        "name": state.name,
        "uid": state.uid,
        "component": component,
        "workspaceId": workspace.workspace_id if workspace is not None else None,
        "replicas": desired,
        "generation": metadata["generation"],
        "observedGeneration": metadata["generation"],
        "labelsSha256": _canonical_digest(labels),
        "selectorSha256": _canonical_digest(spec["selector"]),
        "templateLabelsSha256": _canonical_digest(template_labels),
        "specSha256": _canonical_digest(spec),
        "statusSha256": _canonical_digest(document["status"]),
    }
    return state, snapshot


def _bind_controller_revisions(
    revisions: list[dict[str, Any]],
    *,
    states: dict[str, _ControllerState],
) -> list[dict[str, Any]]:
    revision_owners = {
        uid: state
        for uid, state in states.items()
        if state.kind in {"StatefulSet", "DaemonSet"}
    }
    current_bindings: dict[str, list[str]] = {uid: [] for uid in revision_owners}
    snapshots: list[dict[str, Any]] = []
    for document in revisions:
        metadata = document.get("metadata")
        references = (
            metadata.get("ownerReferences") if isinstance(metadata, dict) else None
        )
        owner_uid = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        owner = revision_owners.get(owner_uid)
        data = document.get("data") if isinstance(document, dict) else None
        data_spec = data.get("spec") if isinstance(data, dict) else None
        revision_template = (
            data_spec.get("template") if isinstance(data_spec, dict) else None
        )
        template_metadata = (
            revision_template.get("metadata")
            if isinstance(revision_template, dict)
            else None
        )
        template_spec = (
            revision_template.get("spec")
            if isinstance(revision_template, dict)
            else None
        )
        revision_number = (
            document.get("revision") if isinstance(document, dict) else None
        )
        if (
            not isinstance(metadata, dict)
            or owner is None
            or document.get("apiVersion") != "apps/v1"
            or document.get("kind") != "ControllerRevision"
            or "deletionTimestamp" in metadata
            or metadata.get("namespace") != owner.namespace
            or isinstance(revision_number, bool)
            or not isinstance(revision_number, int)
            or revision_number < 1
            or not isinstance(data, dict)
            or set(data) != {"spec"}
            or not isinstance(data_spec, dict)
            or set(data_spec) != {"template"}
            or not isinstance(revision_template, dict)
            or revision_template.get("$patch") != "replace"
            or not isinstance(template_metadata, dict)
            or not isinstance(template_spec, dict)
        ):
            raise SoakValidationError("soak ControllerRevision identity is invalid")
        _exact_owner(
            metadata,
            ("apps/v1", owner.kind, owner.name, owner.uid),
        )
        revision_labels = _labels(
            metadata.get("labels"),
            message="soak ControllerRevision labels are invalid",
        )
        revision_template_labels = _labels(
            template_metadata.get("labels"),
            message="soak ControllerRevision template labels are invalid",
        )
        if not _labels_match(owner.selector, revision_template_labels):
            raise SoakValidationError(
                "soak ControllerRevision template selector is invalid"
            )
        _validate_images(
            template_spec,
            message="soak ControllerRevision image contract is invalid",
        )
        hash_label = (
            "controller.kubernetes.io/hash"
            if owner.kind == "StatefulSet"
            else "controller-revision-hash"
        )
        revision_hash = revision_labels.get(hash_label)
        if (
            not isinstance(revision_hash, str)
            or KUBERNETES_SAFE_HASH.fullmatch(revision_hash) is None
            or metadata.get("name") != f"{owner.name}-{revision_hash}"
            or revision_labels
            != {**revision_template_labels, hash_label: revision_hash}
        ):
            raise SoakValidationError("soak ControllerRevision hash is invalid")
        expected_template = copy.deepcopy(owner.document["spec"]["template"])
        expected_template["$patch"] = "replace"
        is_current_data = data == {"spec": {"template": expected_template}}
        if owner.kind == "StatefulSet":
            current_revision = owner.document["status"]["currentRevision"]
            is_current = metadata["name"] == current_revision
            if is_current != is_current_data:
                raise SoakValidationError(
                    "soak StatefulSet ControllerRevision is not current"
                )
            binding = metadata["name"]
        else:
            is_current = is_current_data
            binding = revision_hash
        if is_current:
            current_bindings[owner.uid].append(binding)
        snapshots.append(
            {
                "namespace": owner.namespace,
                "name": metadata["name"],
                "uid": metadata["uid"],
                "ownerKind": owner.kind,
                "ownerName": owner.name,
                "ownerUid": owner.uid,
                "revision": revision_number,
                "current": is_current,
                "labelsSha256": _canonical_digest(revision_labels),
                "dataSha256": _canonical_digest(data),
            }
        )
    if any(len(bindings) != 1 for bindings in current_bindings.values()):
        raise SoakValidationError(
            "soak current ControllerRevision inventory is incomplete"
        )
    for uid, bindings in current_bindings.items():
        states[uid] = states[uid]._replace(pod_revision=bindings[0])
    return snapshots


def _managed_controllers(
    items: list[dict[str, Any]],
    *,
    workspaces: dict[str, _WorkspaceIdentity],
    target: _WorkspaceIdentity,
    identity_mode: str,
) -> tuple[
    dict[str, _ControllerState],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    manager = next(
        (
            item
            for item in items
            if item.get("kind") == "Deployment"
            and item.get("metadata", {}).get("namespace") == WORKSPACE_NAMESPACE
            and item.get("metadata", {}).get("name") == "aileron-workspace-manager"
        ),
        None,
    )
    if manager is None:
        raise SoakValidationError("soak Workspace Manager controller is missing")
    manager_annotations = (
        manager.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    if not isinstance(manager_annotations, dict):
        raise SoakValidationError("soak Workspace Manager annotations are invalid")
    core_postgres_external = "aileron.io/platform-database-revision" in (
        manager_annotations
    )
    redis_revision_annotations = {
        "aileron.io/redis-general-revision",
        "aileron.io/redis-job-queue-revision",
        "aileron.io/redis-job-result-revision",
    }
    present_redis_revisions = redis_revision_annotations & set(manager_annotations)
    if (
        present_redis_revisions
        and present_redis_revisions != redis_revision_annotations
    ):
        raise SoakValidationError("soak Redis revision contract is incomplete")
    core_redis_external = present_redis_revisions == redis_revision_annotations

    identity_postgres_external = False
    if identity_mode == "bundledKeycloak":
        keycloak = next(
            (
                item
                for item in items
                if item.get("kind") == "Deployment"
                and item.get("metadata", {}).get("namespace")
                == "aileron-identity-system"
                and item.get("metadata", {}).get("name") == "aileron-identity-keycloak"
            ),
            None,
        )
        if keycloak is None:
            raise SoakValidationError("soak Identity controller is missing")
        identity_annotations = (
            keycloak.get("spec", {})
            .get("template", {})
            .get("metadata", {})
            .get("annotations", {})
        )
        if not isinstance(identity_annotations, dict):
            raise SoakValidationError("soak Identity annotations are invalid")
        identity_postgres_external = (
            "aileron.io/identity-database-revision" in identity_annotations
        )

    expected_fixed = {
        identity: descriptor
        for identity, descriptor in FIXED_CONTROLLER_DESCRIPTORS.items()
        if (
            (
                identity_mode == "bundledKeycloak"
                or identity[0] != "aileron-identity-system"
            )
            and not (
                identity == ("aileron-identity-system", "aileron-identity-postgres")
                and identity_postgres_external
            )
            and not (
                identity == (WORKSPACE_NAMESPACE, "aileron-postgres")
                and core_postgres_external
            )
            and not (
                identity == (WORKSPACE_NAMESPACE, "aileron-redis")
                and core_redis_external
            )
        )
    }
    found_fixed: set[tuple[str, str]] = set()
    states: dict[str, _ControllerState] = {}
    snapshots: list[dict[str, Any]] = []
    replica_sets: list[dict[str, Any]] = []
    controller_revisions: list[dict[str, Any]] = []
    for document in items:
        kind = document["kind"]
        metadata = document["metadata"]
        namespace = metadata["namespace"]
        if kind == "ControllerRevision":
            if namespace in MANAGED_NAMESPACES:
                controller_revisions.append(document)
            continue
        if kind == "Job":
            if namespace in MANAGED_NAMESPACES:
                raise SoakValidationError("soak managed namespace contains a Job")
            continue
        if kind == "ReplicaSet":
            if namespace in MANAGED_NAMESPACES:
                replica_sets.append(document)
            continue
        if namespace not in MANAGED_NAMESPACES:
            continue
        identity = (namespace, metadata.get("name"))
        fixed_descriptor = expected_fixed.get(identity)
        workspace: _WorkspaceIdentity | None = None
        component: str | None = None
        include = False
        if fixed_descriptor is not None:
            expected_kind, component = fixed_descriptor
            if kind != expected_kind:
                raise SoakValidationError("soak fixed controller kind is invalid")
            found_fixed.add(identity)
            include = True
        else:
            references = metadata.get("ownerReferences")
            owner_uid = (
                references[0].get("uid")
                if isinstance(references, list)
                and len(references) == 1
                and isinstance(references[0], dict)
                else None
            )
            workspace = workspaces.get(owner_uid)
            if workspace is None or namespace != WORKSPACE_NAMESPACE:
                raise SoakValidationError("soak managed controller is not owned")
            matches = [
                item
                for item in TARGET_WORKSPACE_CONTROLLER_COMPONENTS
                if metadata.get("name") == f"{item}-{workspace.workspace_id}"
            ]
            if len(matches) != 1 or kind != "Deployment":
                raise SoakValidationError("soak Workspace controller name is invalid")
            component = matches[0]
            include = workspace.uid == target.uid
        state, snapshot = _controller_state(
            document,
            component=component,
            workspace=workspace,
            include=include,
        )
        if state.uid in states:
            raise SoakValidationError("soak controller UID is ambiguous")
        states[state.uid] = state
        if include:
            snapshots.append(snapshot)
    if found_fixed != set(expected_fixed):
        raise SoakValidationError("soak fixed controller inventory is incomplete")
    for workspace in workspaces.values():
        observed_components = {
            state.component
            for state in states.values()
            if state.workspace is not None and state.workspace.uid == workspace.uid
        }
        required_components = {
            component
            for component in TARGET_WORKSPACE_CONTROLLER_COMPONENTS
            if _workspace_component_desired(workspace, component) == 1
        }
        if not required_components.issubset(observed_components):
            raise SoakValidationError(
                "soak running Workspace controller inventory is incomplete"
            )

    replica_states: dict[str, _ControllerState] = {}
    replica_snapshots: list[dict[str, Any]] = []
    by_deployment: dict[str, list[_ControllerState]] = {
        state.uid: [] for state in states.values() if state.kind == "Deployment"
    }
    for document in replica_sets:
        metadata = document["metadata"]
        references = metadata.get("ownerReferences")
        owner_uid = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        deployment = states.get(owner_uid)
        if deployment is None or deployment.kind != "Deployment":
            raise SoakValidationError("soak ReplicaSet ownership is invalid")
        _exact_owner(
            metadata,
            ("apps/v1", "Deployment", deployment.name, deployment.uid),
        )
        if (
            document.get("apiVersion") != "apps/v1"
            or metadata.get("namespace") != deployment.namespace
            or "deletionTimestamp" in metadata
            or not _nonempty(metadata.get("uid"))
            or not metadata.get("name", "").startswith(f"{deployment.name}-")
            or isinstance(metadata.get("generation"), bool)
            or not isinstance(metadata.get("generation"), int)
            or metadata["generation"] < 1
        ):
            raise SoakValidationError("soak ReplicaSet identity is invalid")
        spec = document.get("spec")
        template = spec.get("template") if isinstance(spec, dict) else None
        template_metadata = (
            template.get("metadata") if isinstance(template, dict) else None
        )
        template_spec = template.get("spec") if isinstance(template, dict) else None
        labels = _labels(
            metadata.get("labels"), message="soak ReplicaSet labels are invalid"
        )
        selector = _selector_labels(spec, message="soak ReplicaSet selector is invalid")
        template_labels = _labels(
            (
                template_metadata.get("labels")
                if isinstance(template_metadata, dict)
                else None
            ),
            message="soak ReplicaSet template labels are invalid",
        )
        hash_value = labels.get("pod-template-hash")
        desired = _replica_count(document, allow_zero=True)
        expected_template_labels = dict(deployment.template_labels)
        if _nonempty(hash_value):
            expected_template_labels["pod-template-hash"] = hash_value
        expected_selector = dict(deployment.selector)
        if _nonempty(hash_value):
            expected_selector["pod-template-hash"] = hash_value
        deployment_template_metadata = deployment.document["spec"]["template"].get(
            "metadata"
        )
        expected_template_metadata = (
            dict(deployment_template_metadata)
            if isinstance(deployment_template_metadata, dict)
            else {}
        )
        expected_template_metadata["labels"] = expected_template_labels
        common_invalid = (
            not isinstance(hash_value, str)
            or KUBERNETES_SAFE_HASH.fullmatch(hash_value) is None
            or metadata.get("name") != f"{deployment.name}-{hash_value}"
            or selector != expected_selector
            or labels != template_labels
            or not _labels_match(selector, template_labels)
            or not isinstance(template_spec, dict)
            or not isinstance(template_metadata, dict)
            or not set(template_metadata).issubset(
                {"labels", "annotations", "creationTimestamp"}
            )
            or (
                "creationTimestamp" in template_metadata
                and template_metadata["creationTimestamp"] is not None
            )
            or (
                "annotations" in template_metadata
                and (
                    not isinstance(template_metadata["annotations"], dict)
                    or any(
                        not isinstance(key, str) or not isinstance(value, str)
                        for key, value in template_metadata["annotations"].items()
                    )
                )
            )
        )
        active_template_invalid = desired > 0 and (
            labels != expected_template_labels
            or template_labels != expected_template_labels
            or template_metadata != expected_template_metadata
            or _canonical_digest(template_spec)
            != _canonical_digest(deployment.document["spec"]["template"]["spec"])
        )
        if common_invalid or active_template_invalid:
            raise SoakValidationError(
                "soak ReplicaSet differs beyond pod-template-hash"
            )
        _validate_images(
            template_spec, message="soak ReplicaSet image contract is invalid"
        )
        state = _ControllerState(
            document,
            metadata["namespace"],
            metadata["name"],
            metadata["uid"],
            "ReplicaSet",
            deployment.component,
            deployment.workspace,
            deployment.include,
            labels,
            selector,
            template_labels,
            desired,
            None,
        )
        if state.uid in states or state.uid in replica_states:
            raise SoakValidationError("soak ReplicaSet UID is ambiguous")
        replica_states[state.uid] = state
        by_deployment[deployment.uid].append(state)
        if state.include:
            replica_snapshots.append(
                {
                    "namespace": state.namespace,
                    "kind": state.kind,
                    "name": state.name,
                    "uid": state.uid,
                    "component": state.component,
                    "workspaceId": (
                        state.workspace.workspace_id
                        if state.workspace is not None
                        else None
                    ),
                    "replicas": desired,
                    "generation": metadata["generation"],
                    "observedGeneration": metadata["generation"],
                    "labelsSha256": _canonical_digest(labels),
                    "selectorSha256": _canonical_digest(spec["selector"]),
                    "templateLabelsSha256": _canonical_digest(template_labels),
                    "specSha256": _canonical_digest(spec),
                    "statusSha256": _canonical_digest(document["status"]),
                }
            )
    for deployment_uid, replicas in by_deployment.items():
        desired = states[deployment_uid].desired
        if sum(item.desired for item in replicas) != desired or sum(
            item.desired > 0 for item in replicas
        ) != (1 if desired > 0 else 0):
            raise SoakValidationError("soak Deployment ReplicaSet closure is invalid")
    states.update(replica_states)
    snapshots.extend(replica_snapshots)
    revision_snapshots = _bind_controller_revisions(
        controller_revisions,
        states=states,
    )
    return states, snapshots, revision_snapshots


def _pod_spec_matches_owner_template(
    *,
    pod_spec: dict[str, Any],
    template_spec: Any,
    owner_document: dict[str, Any],
    pod_name: str,
    service_account: _WorkspaceServiceAccount | None,
) -> bool:
    if not isinstance(template_spec, dict):
        return False
    actual = copy.deepcopy(pod_spec)
    expected = copy.deepcopy(template_spec)
    actual_node_name = actual.get("nodeName")
    if not _nonempty(actual_node_name):
        return False
    if "nodeName" not in expected:
        del actual["nodeName"]
    owner_kind = owner_document.get("kind")

    def same_unordered(left: list[Any], right: list[Any]) -> bool:
        return sorted(_canonical_digest(item) for item in left) == sorted(
            _canonical_digest(item) for item in right
        )

    def normalize_pod_only_defaults(
        actual_containers: Any, expected_containers: Any
    ) -> bool:
        if (
            not isinstance(actual_containers, list)
            or not isinstance(expected_containers, list)
            or len(actual_containers) != len(expected_containers)
        ):
            return False
        for actual_container, expected_container in zip(
            actual_containers, expected_containers
        ):
            if (
                not isinstance(actual_container, dict)
                or not isinstance(expected_container, dict)
                or actual_container.get("name") != expected_container.get("name")
            ):
                return False
            actual_ports = actual_container.get("ports", [])
            expected_ports = expected_container.get("ports", [])
            if (
                template_spec.get("hostNetwork") is True
                and isinstance(actual_ports, list)
                and isinstance(expected_ports, list)
                and len(actual_ports) == len(expected_ports)
            ):
                for actual_port, expected_port in zip(actual_ports, expected_ports):
                    if (
                        isinstance(actual_port, dict)
                        and isinstance(expected_port, dict)
                        and "hostPort" not in expected_port
                        and actual_port.get("hostPort")
                        == expected_port.get("containerPort")
                    ):
                        del actual_port["hostPort"]
            expected_resources = expected_container.get("resources")
            actual_resources = actual_container.get("resources")
            if not isinstance(expected_resources, dict) or not isinstance(
                actual_resources, dict
            ):
                continue
            limits = expected_resources.get("limits")
            expected_requests = expected_resources.get("requests", {})
            actual_requests = actual_resources.get("requests")
            if (
                isinstance(limits, dict)
                and isinstance(expected_requests, dict)
                and isinstance(actual_requests, dict)
            ):
                for resource_name, limit in limits.items():
                    if (
                        resource_name not in expected_requests
                        and actual_requests.get(resource_name) == limit
                    ):
                        del actual_requests[resource_name]
                if not actual_requests and "requests" not in expected_resources:
                    del actual_resources["requests"]
        return True

    if not all(
        normalize_pod_only_defaults(actual.get(kind, []), expected.get(kind, []))
        for kind in ("containers", "initContainers")
    ):
        return False

    actual_service_account_name = actual.get("serviceAccountName")
    if service_account is not None:
        if (
            expected.get("serviceAccountName") != service_account.name
            or actual_service_account_name != service_account.name
            or "imagePullSecrets" in expected
        ):
            return False
        if service_account.image_pull_secrets:
            if actual.get("imagePullSecrets") != service_account.image_pull_secrets:
                return False
            del actual["imagePullSecrets"]
        elif "imagePullSecrets" in actual:
            if actual["imagePullSecrets"] != []:
                return False
            del actual["imagePullSecrets"]
    if (
        "serviceAccount" not in expected
        and _nonempty(actual.get("serviceAccount"))
        and actual["serviceAccount"] == actual_service_account_name
    ):
        del actual["serviceAccount"]
    if (
        "serviceAccountName" not in expected
        and actual.get("serviceAccountName") == "default"
    ):
        del actual["serviceAccountName"]
    if "priority" not in expected and actual.get("priority") == 0:
        del actual["priority"]
    if (
        "preemptionPolicy" not in expected
        and actual.get("preemptionPolicy") == "PreemptLowerPriority"
    ):
        del actual["preemptionPolicy"]
    if (
        "enableServiceLinks" not in expected
        and actual.get("enableServiceLinks") is True
    ):
        del actual["enableServiceLinks"]

    expected_tolerations = expected.get("tolerations", [])
    actual_tolerations = actual.get("tolerations", [])
    if not isinstance(expected_tolerations, list) or not isinstance(
        actual_tolerations, list
    ):
        return False
    default_no_execute_tolerations = [
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
    daemon_tolerations = [
        {
            "effect": "NoExecute",
            "key": "node.kubernetes.io/not-ready",
            "operator": "Exists",
        },
        {
            "effect": "NoExecute",
            "key": "node.kubernetes.io/unreachable",
            "operator": "Exists",
        },
        {
            "effect": "NoSchedule",
            "key": "node.kubernetes.io/disk-pressure",
            "operator": "Exists",
        },
        {
            "effect": "NoSchedule",
            "key": "node.kubernetes.io/memory-pressure",
            "operator": "Exists",
        },
        {
            "effect": "NoSchedule",
            "key": "node.kubernetes.io/pid-pressure",
            "operator": "Exists",
        },
        {
            "effect": "NoSchedule",
            "key": "node.kubernetes.io/unschedulable",
            "operator": "Exists",
        },
    ]
    if expected.get("hostNetwork") is True:
        daemon_tolerations.append(
            {
                "effect": "NoSchedule",
                "key": "node.kubernetes.io/network-unavailable",
                "operator": "Exists",
            }
        )
    if owner_kind == "DaemonSet":
        injected_tolerations = copy.deepcopy(expected_tolerations)
        for default in daemon_tolerations:
            matches = [
                index
                for index, current in enumerate(injected_tolerations)
                if isinstance(current, dict)
                and current.get("key") == default["key"]
                and current.get("effect") == default["effect"]
            ]
            if len(matches) > 1:
                return False
            if matches:
                injected_tolerations[matches[0]] = copy.deepcopy(default)
            else:
                injected_tolerations.append(copy.deepcopy(default))
        if not same_unordered(actual_tolerations, expected_tolerations):
            if not same_unordered(actual_tolerations, injected_tolerations):
                return False
    else:
        remaining_tolerations = copy.deepcopy(actual_tolerations)
        for expected_toleration in expected_tolerations:
            matches = [
                index
                for index, current in enumerate(remaining_tolerations)
                if current == expected_toleration
            ]
            if not matches:
                return False
            del remaining_tolerations[matches[0]]
        allowed_default_digests = {
            _canonical_digest(item) for item in default_no_execute_tolerations
        }
        remaining_digests = [_canonical_digest(item) for item in remaining_tolerations]
        if any(
            item not in allowed_default_digests for item in remaining_digests
        ) or len(remaining_digests) != len(set(remaining_digests)):
            return False
    if "tolerations" in expected:
        actual["tolerations"] = copy.deepcopy(expected_tolerations)
    else:
        actual.pop("tolerations", None)

    if owner_kind == "StatefulSet":
        owner_spec = owner_document.get("spec")
        if not isinstance(owner_spec, dict):
            return False
        service_name = owner_spec.get("serviceName")
        if "hostname" not in expected and actual.get("hostname") == pod_name:
            del actual["hostname"]
        if (
            "subdomain" not in expected
            and _nonempty(service_name)
            and actual.get("subdomain") == service_name
        ):
            del actual["subdomain"]
        claim_templates = owner_spec.get("volumeClaimTemplates", [])
        if not isinstance(claim_templates, list):
            return False
        expected_volumes = expected.get("volumes", [])
        actual_volumes = actual.get("volumes", [])
        if not isinstance(expected_volumes, list) or not isinstance(
            actual_volumes, list
        ):
            return False
        expected_volumes_by_name = {
            volume.get("name"): volume
            for volume in expected_volumes
            if isinstance(volume, dict) and _nonempty(volume.get("name"))
        }
        if len(expected_volumes_by_name) != len(expected_volumes):
            return False
        claim_names: set[str] = set()
        for claim_template in claim_templates:
            claim_metadata = (
                claim_template.get("metadata")
                if isinstance(claim_template, dict)
                else None
            )
            claim_name = (
                claim_metadata.get("name") if isinstance(claim_metadata, dict) else None
            )
            if not _nonempty(claim_name) or claim_name in claim_names:
                return False
            claim_names.add(claim_name)
            expected_claim_volume = {
                "name": claim_name,
                "persistentVolumeClaim": {
                    "claimName": f"{claim_name}-{pod_name}",
                },
            }
            expected_claim_volume_with_default = copy.deepcopy(expected_claim_volume)
            expected_claim_volume_with_default["persistentVolumeClaim"][
                "readOnly"
            ] = False
            matches = [
                index
                for index, volume in enumerate(actual_volumes)
                if volume in (expected_claim_volume, expected_claim_volume_with_default)
            ]
            if len(matches) != 1:
                return False
            index = matches[0]
            original_template_volume = expected_volumes_by_name.get(claim_name)
            if original_template_volume is None:
                del actual_volumes[index]
            else:
                actual_volumes[index] = copy.deepcopy(original_template_volume)
        if same_unordered(actual_volumes, expected_volumes):
            if "volumes" in expected:
                actual["volumes"] = copy.deepcopy(expected_volumes)
            else:
                actual.pop("volumes", None)

    if owner_kind == "DaemonSet":
        expected_affinity = expected.get("affinity")
        injected_affinity = (
            copy.deepcopy(expected_affinity)
            if isinstance(expected_affinity, dict)
            else {}
        )
        node_affinity = injected_affinity.setdefault("nodeAffinity", {})
        if not isinstance(node_affinity, dict):
            return False
        node_affinity["requiredDuringSchedulingIgnoredDuringExecution"] = {
            "nodeSelectorTerms": [
                {
                    "matchFields": [
                        {
                            "key": "metadata.name",
                            "operator": "In",
                            "values": [actual_node_name],
                        }
                    ]
                }
            ]
        }
        if actual.get("affinity") == injected_affinity:
            if "affinity" in expected:
                actual["affinity"] = copy.deepcopy(expected_affinity)
            else:
                del actual["affinity"]

    if actual == expected:
        return True
    if not isinstance(actual.get("containers"), list) or not isinstance(
        actual.get("initContainers", []), list
    ):
        return False
    expected_volumes = expected.get("volumes", [])
    pod_volumes = actual.get("volumes", [])
    if not isinstance(expected_volumes, list) or not isinstance(pod_volumes, list):
        return False
    if expected.get("automountServiceAccountToken") is False:
        return False
    projection_indexes = [
        index
        for index, volume in enumerate(pod_volumes)
        if isinstance(volume, dict)
        and isinstance(volume.get("name"), str)
        and re.fullmatch(r"kube-api-access-[a-z0-9]{5}", volume["name"]) is not None
        and volume not in expected_volumes
    ]
    if len(projection_indexes) != 1:
        return False
    projection_index = projection_indexes[0]
    projection = pod_volumes[projection_index]
    projection_name = projection["name"]
    if projection != {
        "name": projection_name,
        "projected": {
            "defaultMode": 420,
            "sources": [
                {
                    "serviceAccountToken": {
                        "expirationSeconds": 3607,
                        "path": "token",
                    }
                },
                {
                    "configMap": {
                        "items": [{"key": "ca.crt", "path": "ca.crt"}],
                        "name": "kube-root-ca.crt",
                    }
                },
                {
                    "downwardAPI": {
                        "items": [
                            {
                                "fieldRef": {
                                    "apiVersion": "v1",
                                    "fieldPath": "metadata.namespace",
                                },
                                "path": "namespace",
                            }
                        ]
                    }
                },
            ],
        },
    }:
        return False
    del pod_volumes[projection_index]
    if not same_unordered(pod_volumes, expected_volumes):
        return False
    if "volumes" in expected:
        actual["volumes"] = copy.deepcopy(expected_volumes)
    else:
        del actual["volumes"]
    service_account_mount = {
        "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
        "name": projection_name,
        "readOnly": True,
    }
    for collection_name in ("containers", "initContainers"):
        actual_collection = actual.get(collection_name, [])
        expected_collection = expected.get(collection_name, [])
        for container, expected_container in zip(
            actual_collection, expected_collection
        ):
            if not isinstance(container, dict):
                return False
            mounts = container.get("volumeMounts")
            if not isinstance(mounts, list):
                return False
            indexes = [
                index
                for index, mount in enumerate(mounts)
                if mount == service_account_mount
            ]
            if len(indexes) != 1:
                return False
            del mounts[indexes[0]]
            expected_mounts = expected_container.get("volumeMounts", [])
            if mounts != expected_mounts:
                return False
            if "volumeMounts" in expected_container:
                container["volumeMounts"] = copy.deepcopy(expected_mounts)
            else:
                del container["volumeMounts"]
    return actual == expected


def _runtime_container_snapshots(
    *,
    spec: dict[str, Any],
    status: dict[str, Any],
    image_runtime_pairs: Mapping[str, frozenset[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    containers = spec.get("containers")
    init_containers = spec.get("initContainers", [])
    statuses = status.get("containerStatuses")
    init_statuses = status.get("initContainerStatuses", [])
    if (
        not isinstance(containers, list)
        or not containers
        or not isinstance(init_containers, list)
        or not isinstance(statuses, list)
        or not isinstance(init_statuses, list)
    ):
        raise SoakValidationError("soak Pod container set is invalid")

    def by_name(values: list[Any], message: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for value in values:
            if (
                not isinstance(value, dict)
                or not _nonempty(value.get("name"))
                or value["name"] in result
            ):
                raise SoakValidationError(message)
            result[value["name"]] = value
        return result

    specs = by_name(containers, "soak main container spec is invalid")
    runtime = by_name(statuses, "soak main container status is invalid")
    init_specs = by_name(init_containers, "soak init container spec is invalid")
    init_runtime = by_name(init_statuses, "soak init container status is invalid")
    if set(specs) != set(runtime) or set(init_specs) != set(init_runtime):
        raise SoakValidationError("soak Pod container runtime binding is invalid")

    main_snapshots: list[dict[str, Any]] = []
    for name in sorted(specs):
        container = specs[name]
        observed = runtime[name]
        state = observed.get("state")
        running = state.get("running") if isinstance(state, dict) else None
        restart_count = observed.get("restartCount")
        image = container.get("image")
        image_id = observed.get("imageID")
        image_id_match = (
            RUNTIME_IMAGE_ID.fullmatch(image_id) if isinstance(image_id, str) else None
        )
        image_id_repository = (
            image_id.rsplit("://", 1)[-1].rsplit("@sha256:", 1)[0]
            if image_id_match is not None
            else None
        )
        allowed_image_digests = (
            image_runtime_pairs.get(image) if isinstance(image, str) else None
        )
        if (
            not isinstance(image, str)
            or IMMUTABLE_IMAGE.fullmatch(image) is None
            or not _container_status_image_matches_spec(observed.get("image"), image)
            or image_id_match is None
            or image_id_repository != image.rsplit("@sha256:", 1)[0]
            or not isinstance(allowed_image_digests, frozenset)
            or image_id_match.group(1) not in allowed_image_digests
            or not isinstance(observed.get("containerID"), str)
            or RUNTIME_CONTAINER_ID.fullmatch(observed["containerID"]) is None
            or isinstance(restart_count, bool)
            or not isinstance(restart_count, int)
            or restart_count < 0
            or observed.get("ready") is not True
            or observed.get("started") is not True
            or not isinstance(state, dict)
            or set(state) != {"running"}
            or not isinstance(running, dict)
            or not _utc_rfc3339(running.get("startedAt"))
        ):
            raise SoakValidationError("soak main container runtime identity is invalid")
        main_snapshots.append(
            {
                "name": name,
                "specImage": image,
                "statusImage": observed["image"],
                "imageID": image_id,
                "containerID": observed["containerID"],
                "restartCount": restart_count,
                "runningStartedAt": running["startedAt"],
                "started": True,
                "ready": True,
            }
        )

    init_snapshots: list[dict[str, Any]] = []
    for name in sorted(init_specs):
        container = init_specs[name]
        observed = init_runtime[name]
        state = observed.get("state")
        terminated = state.get("terminated") if isinstance(state, dict) else None
        image = container.get("image")
        image_id = observed.get("imageID")
        image_id_match = (
            RUNTIME_IMAGE_ID.fullmatch(image_id) if isinstance(image_id, str) else None
        )
        image_id_repository = (
            image_id.rsplit("://", 1)[-1].rsplit("@sha256:", 1)[0]
            if image_id_match is not None
            else None
        )
        allowed_image_digests = (
            image_runtime_pairs.get(image) if isinstance(image, str) else None
        )
        if (
            not isinstance(image, str)
            or IMMUTABLE_IMAGE.fullmatch(image) is None
            or not _container_status_image_matches_spec(observed.get("image"), image)
            or image_id_match is None
            or image_id_repository != image.rsplit("@sha256:", 1)[0]
            or not isinstance(allowed_image_digests, frozenset)
            or image_id_match.group(1) not in allowed_image_digests
            or not isinstance(observed.get("containerID"), str)
            or RUNTIME_CONTAINER_ID.fullmatch(observed["containerID"]) is None
            or observed.get("restartCount") != 0
            or not isinstance(state, dict)
            or set(state) != {"terminated"}
            or not isinstance(terminated, dict)
            or terminated.get("exitCode") != 0
            or terminated.get("reason") != "Completed"
            or not _utc_rfc3339(terminated.get("startedAt"))
            or not _utc_rfc3339(terminated.get("finishedAt"))
        ):
            raise SoakValidationError("soak init container completion is invalid")
        init_snapshots.append(
            {
                "name": name,
                "specImage": image,
                "statusImage": observed["image"],
                "imageID": image_id,
                "containerID": observed["containerID"],
                "restartCount": 0,
                "exitCode": 0,
                "reason": "Completed",
                "startedAt": terminated["startedAt"],
                "finishedAt": terminated["finishedAt"],
            }
        )
    return main_snapshots, init_snapshots


def _running_pod_snapshot(
    document: dict[str, Any],
    *,
    owner: _ControllerState,
    image_runtime_pairs: Mapping[str, frozenset[str]],
    service_accounts: Mapping[str, _WorkspaceServiceAccount],
) -> dict[str, Any]:
    metadata = document["metadata"]
    spec = document.get("spec")
    status = document.get("status")
    labels = metadata.get("labels")
    conditions = status.get("conditions") if isinstance(status, dict) else None
    ready_conditions = (
        [
            item
            for item in conditions
            if isinstance(item, dict) and item.get("type") == "Ready"
        ]
        if isinstance(conditions, list)
        else []
    )
    pod_ip = status.get("podIP") if isinstance(status, dict) else None
    host_ip = status.get("hostIP") if isinstance(status, dict) else None
    try:
        parsed_pod_ip = ipaddress.ip_address(pod_ip)
        pod_ip_is_canonical_ipv4 = (
            parsed_pod_ip.version == 4 and str(parsed_pod_ip) == pod_ip
        )
    except (TypeError, ValueError):
        pod_ip_is_canonical_ipv4 = False
    try:
        parsed_host_ip = ipaddress.ip_address(host_ip)
        host_ip_is_canonical_ipv4 = (
            parsed_host_ip.version == 4 and str(parsed_host_ip) == host_ip
        )
    except (TypeError, ValueError):
        host_ip_is_canonical_ipv4 = False
    generated_prefix = f"{owner.name}-"
    owner_template_spec = owner.document["spec"]["template"]["spec"]
    host_network = spec.get("hostNetwork") is True if isinstance(spec, dict) else False
    owner_host_network = owner_template_spec.get("hostNetwork") is True
    if (
        document.get("apiVersion") != "v1"
        or document.get("kind") != "Pod"
        or "deletionTimestamp" in metadata
        or not _nonempty(metadata.get("name"))
        or not _nonempty(metadata.get("uid"))
        or metadata.get("namespace") != owner.namespace
        or not isinstance(spec, dict)
        or not _nonempty(spec.get("nodeName"))
        or host_network != owner_host_network
        or spec.get("ephemeralContainers")
        or not isinstance(status, dict)
        or status.get("ephemeralContainerStatuses")
        or status.get("phase") != "Running"
        or not pod_ip_is_canonical_ipv4
        or status.get("podIPs") != [{"ip": pod_ip}]
        or not host_ip_is_canonical_ipv4
        or status.get("hostIPs") != [{"ip": host_ip}]
        or (host_network and pod_ip != host_ip)
        or not isinstance(conditions, list)
        or len(ready_conditions) != 1
        or ready_conditions[0].get("status") != "True"
        or (
            owner.kind in {"ReplicaSet", "DaemonSet"}
            and not _kubernetes_generated_name_matches(
                metadata,
                expected_generate_name=generated_prefix,
            )
        )
    ):
        raise SoakValidationError("soak Pod lifecycle is invalid")
    labels = _labels(labels, message="soak Pod labels are invalid")
    expected_labels = dict(owner.template_labels)
    if owner.kind == "StatefulSet":
        match = re.fullmatch(rf"{re.escape(owner.name)}-([0-9]+)", metadata["name"])
        ordinal = match.group(1) if match is not None else None
        if (
            ordinal is None
            or str(int(ordinal)) != ordinal
            or not _nonempty(owner.pod_revision)
        ):
            raise SoakValidationError("soak StatefulSet Pod identity is invalid")
        expected_labels.update(
            {
                "controller-revision-hash": owner.pod_revision,
                "statefulset.kubernetes.io/pod-name": metadata["name"],
                "apps.kubernetes.io/pod-index": ordinal,
            }
        )
    elif owner.kind == "DaemonSet":
        if not _nonempty(owner.pod_revision) or not _nonempty(spec.get("nodeName")):
            raise SoakValidationError("soak DaemonSet Pod revision is invalid")
        expected_labels.update(
            {
                "controller-revision-hash": owner.pod_revision,
                "pod-template-generation": str(
                    owner.document["metadata"]["generation"]
                ),
            }
        )
    if labels != expected_labels:
        raise SoakValidationError("soak Pod labels differ from its owner projection")
    template_metadata = owner.document["spec"]["template"].get("metadata")
    expected_annotations = (
        template_metadata.get("annotations", {})
        if isinstance(template_metadata, dict)
        else None
    )
    actual_annotations = metadata.get("annotations", {})
    if (
        not isinstance(expected_annotations, dict)
        or not isinstance(actual_annotations, dict)
        or actual_annotations != expected_annotations
    ):
        raise SoakValidationError(
            "soak Pod annotations differ from its owner projection"
        )
    _exact_owner(metadata, ("apps/v1", owner.kind, owner.name, owner.uid))
    service_account = (
        service_accounts.get(owner.workspace.uid)
        if owner.workspace is not None
        else None
    )
    if not _pod_spec_matches_owner_template(
        pod_spec=spec,
        template_spec=owner.document["spec"]["template"]["spec"],
        owner_document=owner.document,
        pod_name=metadata["name"],
        service_account=service_account,
    ):
        raise SoakValidationError("soak Pod spec differs from owner template")
    main, init = _runtime_container_snapshots(
        spec=spec,
        status=status,
        image_runtime_pairs=image_runtime_pairs,
    )
    snapshot = {
        "namespace": metadata["namespace"],
        "podName": metadata["name"],
        "podUid": metadata["uid"],
        "podIP": pod_ip,
        "hostIP": host_ip,
        "nodeName": spec["nodeName"],
        "hostNetwork": host_network,
        "component": owner.component,
        "workspaceId": owner.workspace.workspace_id if owner.workspace else None,
        "ownerKind": owner.kind,
        "ownerName": owner.name,
        "ownerUid": owner.uid,
        "labelsSha256": _canonical_digest(labels),
        "specSha256": _canonical_digest(spec),
        "statusSha256": _canonical_digest(status),
        "containers": main,
        "initContainers": init,
    }
    return snapshot


def _pod_inventory(
    pods: list[dict[str, Any]],
    *,
    controllers: dict[str, _ControllerState],
    target: _WorkspaceIdentity,
    image_runtime_pairs: Mapping[str, frozenset[str]],
    service_accounts: Mapping[str, _WorkspaceServiceAccount],
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    list[tuple[dict[str, Any], dict[str, Any]]],
]:
    expected = {
        uid: state.desired
        for uid, state in controllers.items()
        if state.kind != "Deployment"
    }
    observed = {uid: 0 for uid in expected}
    snapshots: list[dict[str, Any]] = []
    validated_pods: list[tuple[dict[str, Any], dict[str, Any]]] = []
    target_pods: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {
        component: [] for component in TARGET_WORKSPACE_CONTROLLER_COMPONENTS
    }
    pod_uids: set[str] = set()
    pod_ip_owners: dict[str, tuple[bool, str]] = {}
    host_network_ip_by_node: dict[str, str] = {}
    host_ip_by_node: dict[str, str] = {}
    stateful_ordinals: dict[str, set[int]] = {
        uid: set() for uid, state in controllers.items() if state.kind == "StatefulSet"
    }
    daemon_nodes: dict[str, set[str]] = {
        uid: set() for uid, state in controllers.items() if state.kind == "DaemonSet"
    }
    for document in pods:
        metadata = document["metadata"]
        references = metadata.get("ownerReferences")
        owner_uid = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        if not _nonempty(metadata.get("uid")) or metadata["uid"] in pod_uids:
            raise SoakValidationError("soak Pod UID is ambiguous")
        pod_uids.add(metadata["uid"])
        owner = controllers.get(owner_uid)
        if owner is None or owner.kind == "Deployment":
            raise SoakValidationError("soak Pod ownership is invalid")
        snapshot = _running_pod_snapshot(
            document,
            owner=owner,
            image_runtime_pairs=image_runtime_pairs,
            service_accounts=service_accounts,
        )
        pod_ip = snapshot["podIP"]
        node_name = snapshot["nodeName"]
        host_network = snapshot["hostNetwork"]
        host_ip = snapshot["hostIP"]
        existing_host_ip = host_ip_by_node.get(node_name)
        if existing_host_ip not in {None, host_ip}:
            raise SoakValidationError("soak Pod node host IP is inconsistent")
        host_ip_by_node[node_name] = host_ip
        existing_ip_owner = pod_ip_owners.get(pod_ip)
        if host_network:
            existing_node_ip = host_network_ip_by_node.get(node_name)
            if existing_node_ip not in {None, pod_ip} or existing_ip_owner not in {
                None,
                (True, node_name),
            }:
                raise SoakValidationError("soak host-network Pod IP is inconsistent")
            host_network_ip_by_node[node_name] = pod_ip
            pod_ip_owners[pod_ip] = (True, node_name)
        else:
            if existing_ip_owner is not None:
                raise SoakValidationError("soak Pod IP is ambiguous")
            pod_ip_owners[pod_ip] = (False, node_name)
        if owner.kind == "StatefulSet":
            ordinal = int(
                document["metadata"]["labels"]["apps.kubernetes.io/pod-index"]
            )
            if ordinal in stateful_ordinals[owner.uid]:
                raise SoakValidationError("soak StatefulSet Pod ordinal is ambiguous")
            stateful_ordinals[owner.uid].add(ordinal)
        elif owner.kind == "DaemonSet":
            node_name = document["spec"]["nodeName"]
            if node_name in daemon_nodes[owner.uid]:
                raise SoakValidationError("soak DaemonSet Pod node is ambiguous")
            daemon_nodes[owner.uid].add(node_name)
        validated_pods.append((document, snapshot))
        observed[owner_uid] += 1
        if owner.include:
            snapshots.append(snapshot)
        if owner.workspace is not None and owner.workspace.uid == target.uid:
            target_pods[owner.component].append((document, snapshot))
    if observed != expected:
        raise SoakValidationError("soak Pod owner closure is incomplete")
    for uid, observed_ordinals in stateful_ordinals.items():
        state = controllers[uid]
        ordinals = state.document["spec"].get("ordinals")
        if ordinals is None:
            start = 0
        elif (
            isinstance(ordinals, dict)
            and set(ordinals) == {"start"}
            and not isinstance(ordinals.get("start"), bool)
            and isinstance(ordinals.get("start"), int)
            and ordinals["start"] >= 0
        ):
            start = ordinals["start"]
        else:
            raise SoakValidationError("soak StatefulSet ordinal policy is invalid")
        if observed_ordinals != set(range(start, start + state.desired)):
            raise SoakValidationError("soak StatefulSet Pod ordinal closure is invalid")
    if any(len(daemon_nodes[uid]) != controllers[uid].desired for uid in daemon_nodes):
        raise SoakValidationError("soak DaemonSet Pod node closure is invalid")
    return snapshots, target_pods, validated_pods


def _service_snapshots(
    services: list[dict[str, Any]],
    endpoint_slices: list[dict[str, Any]],
    *,
    workspaces: dict[str, _WorkspaceIdentity],
    target: _WorkspaceIdentity,
    target_pods: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    validated_pods: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    snapshots_by_service_uid: dict[str, dict[str, Any]] = {}
    managed_services: dict[str, dict[str, Any]] = {}
    found_by_workspace: dict[str, set[str]] = {
        workspace.uid: set() for workspace in workspaces.values()
    }
    managed_cluster_ips: set[str] = set()
    canonical_names = {
        f"workspace-{component}-{workspace.workspace_id}": (workspace, component)
        for workspace in workspaces.values()
        for component in SERVICE_COMPONENTS
    }
    for document in services:
        metadata = document["metadata"]
        references = metadata.get("ownerReferences", [])
        owner_uid = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        claimed = canonical_names.get(metadata.get("name"))
        labels_value = metadata.get("labels")
        claims_workspace = isinstance(labels_value, dict) and (
            "aileron.io/workspace-id" in labels_value
            or str(labels_value.get("aileron.io/component", "")).startswith(
                "workspace-"
            )
        )
        workspace = workspaces.get(owner_uid)
        if workspace is None:
            if (
                claimed is not None
                or claims_workspace
                or (
                    isinstance(references, list)
                    and any(
                        isinstance(item, dict) and item.get("kind") == "Workspace"
                        for item in references
                    )
                )
            ):
                raise SoakValidationError("soak Workspace Service ownership is invalid")
            continue
        matches = [
            component
            for component in SERVICE_COMPONENTS
            if metadata.get("name") == f"workspace-{component}-{workspace.workspace_id}"
        ]
        if len(matches) != 1:
            raise SoakValidationError("soak Workspace Service name is invalid")
        component = matches[0]
        spec = document.get("spec")
        labels = _labels(labels_value, message="soak Service labels are invalid")
        expected_labels = _workspace_labels(workspace, f"workspace-{component}")
        expected_selector = dict(expected_labels)
        if component == "runtime":
            expected_selector["aileron.io/runtime-instance-id"] = (
                workspace.runtime_instance_id
            )
        expected_spec_keys = {
            "clusterIP",
            "clusterIPs",
            "internalTrafficPolicy",
            "ipFamilies",
            "ipFamilyPolicy",
            "ports",
            "selector",
            "sessionAffinity",
            "type",
        }
        if (
            document.get("apiVersion") != "v1"
            or document.get("kind") != "Service"
            or "deletionTimestamp" in metadata
            or not _nonempty(metadata.get("uid"))
            or not isinstance(spec, dict)
            or labels != expected_labels
            or set(spec) != expected_spec_keys
            or spec.get("selector") != expected_selector
            or spec.get("type") != "ClusterIP"
            or spec.get("ports") != SERVICE_PORTS[component]
            or spec.get("internalTrafficPolicy") != "Cluster"
            or spec.get("ipFamilies") != ["IPv4"]
            or spec.get("ipFamilyPolicy") != "SingleStack"
            or spec.get("sessionAffinity") != "None"
        ):
            raise SoakValidationError("soak Workspace Service contract is invalid")
        _exact_owner(
            metadata,
            (
                "platform.aileron.io/v1alpha1",
                "Workspace",
                workspace.name,
                workspace.uid,
            ),
        )
        cluster_ip = spec.get("clusterIP")
        cluster_ips = spec.get("clusterIPs")
        try:
            if (
                not isinstance(cluster_ips, list)
                or len(cluster_ips) != 1
                or cluster_ips[0] != cluster_ip
                or any(not isinstance(value, str) for value in cluster_ips)
            ):
                raise ValueError("invalid ClusterIPs")
            parsed_addresses = [ipaddress.ip_address(value) for value in cluster_ips]
            if any(address.version != 4 for address in parsed_addresses):
                raise ValueError("ClusterIP family mismatch")
            if any(value in managed_cluster_ips for value in cluster_ips):
                raise ValueError("duplicate managed ClusterIP")
        except (TypeError, ValueError) as exc:
            raise SoakValidationError("soak Service ClusterIP is invalid") from exc
        managed_cluster_ips.update(cluster_ips)
        selected_pods = [
            entry
            for entry in validated_pods
            if entry[0]["metadata"]["namespace"] == metadata["namespace"]
            and _labels_match(expected_selector, entry[0]["metadata"]["labels"])
        ]
        expected_pods = [
            entry
            for entry in validated_pods
            if entry[1]["workspaceId"] == workspace.workspace_id
            and entry[1]["component"] == f"workspace-{component}"
        ]
        expected_count = _workspace_component_desired(
            workspace, f"workspace-{component}"
        )
        if len(expected_pods) != expected_count or {
            entry[1]["podUid"] for entry in selected_pods
        } != {entry[1]["podUid"] for entry in expected_pods}:
            raise SoakValidationError(
                "soak Service selector does not select its exact component Pod"
            )
        managed_services[metadata["uid"]] = {
            "document": document,
            "workspace": workspace,
            "component": component,
            "expectedPods": expected_pods,
        }
        found_by_workspace[workspace.uid].add(component)
        if workspace.uid != target.uid:
            continue
        pod_entries = target_pods[f"workspace-{component}"]
        if len(pod_entries) != 1 or not _labels_match(
            expected_selector, pod_entries[0][0]["metadata"]["labels"]
        ):
            raise SoakValidationError(
                "soak Service selector does not select target Pod"
            )
        snapshot = {
            "component": component,
            "name": metadata["name"],
            "namespace": WORKSPACE_NAMESPACE,
            "uid": metadata["uid"],
            "clusterIPs": cluster_ips,
            "dnsName": (f"{metadata['name']}.{WORKSPACE_NAMESPACE}.svc.cluster.local"),
            "labelsSha256": _canonical_digest(labels),
            "selectorSha256": _canonical_digest(spec["selector"]),
            "specSha256": _canonical_digest(spec),
        }
        snapshots.append(snapshot)
        snapshots_by_service_uid[metadata["uid"]] = snapshot
    for workspace in workspaces.values():
        required_components = {
            component
            for component in SERVICE_COMPONENTS
            if _workspace_component_desired(workspace, f"workspace-{component}") == 1
        }
        if not required_components.issubset(found_by_workspace[workspace.uid]):
            raise SoakValidationError(
                "soak running Workspace Service inventory is incomplete"
            )
    slices_by_service_uid: dict[str, list[dict[str, Any]]] = {
        uid: [] for uid in managed_services
    }
    bound_pod_uids_by_service_uid: dict[str, set[str]] = {
        uid: set() for uid in managed_services
    }
    for document in endpoint_slices:
        metadata = document["metadata"]
        labels_value = metadata.get("labels")
        labels = labels_value if isinstance(labels_value, dict) else {}
        references = metadata.get("ownerReferences", [])
        owner_uid = (
            references[0].get("uid")
            if isinstance(references, list)
            and len(references) == 1
            and isinstance(references[0], dict)
            else None
        )
        service_name = labels.get(ENDPOINT_SLICE_SERVICE_NAME_LABEL)
        service_state = managed_services.get(owner_uid)
        claimed = canonical_names.get(service_name)
        claims_workspace = "aileron.io/workspace-id" in labels or str(
            labels.get("aileron.io/component", "")
        ).startswith("workspace-")
        if service_state is None:
            if claimed is not None or claims_workspace:
                raise SoakValidationError(
                    "soak Workspace EndpointSlice ownership is invalid"
                )
            continue
        service = service_state["document"]
        service_metadata = service["metadata"]
        service_spec = service["spec"]
        expected_labels = {
            **service_metadata["labels"],
            ENDPOINT_SLICE_SERVICE_NAME_LABEL: service_metadata["name"],
            ENDPOINT_SLICE_MANAGED_BY_LABEL: ENDPOINT_SLICE_MANAGED_BY,
        }
        name_prefix = f"{service_metadata['name']}-"
        name = metadata.get("name")
        annotations = metadata.get("annotations", {})
        if (
            document.get("apiVersion") != "discovery.k8s.io/v1"
            or document.get("kind") != "EndpointSlice"
            or set(document)
            != {"apiVersion", "kind", "metadata", "addressType", "endpoints", "ports"}
            or "deletionTimestamp" in metadata
            or metadata.get("namespace") != service_metadata["namespace"]
            or not _kubernetes_generated_name_matches(
                metadata,
                expected_generate_name=name_prefix,
            )
            or not _nonempty(metadata.get("uid"))
            or labels != expected_labels
            or not isinstance(annotations, dict)
            or not set(annotations).issubset({ENDPOINT_SLICE_TRIGGER_ANNOTATION})
            or (
                ENDPOINT_SLICE_TRIGGER_ANNOTATION in annotations
                and not _utc_rfc3339(annotations[ENDPOINT_SLICE_TRIGGER_ANNOTATION])
            )
            or document.get("addressType") != "IPv4"
            or not isinstance(document.get("endpoints"), list)
            or not isinstance(document.get("ports"), list)
        ):
            raise SoakValidationError(
                "soak Workspace EndpointSlice contract is invalid"
            )
        _exact_owner(
            metadata,
            (
                "v1",
                "Service",
                service_metadata["name"],
                service_metadata["uid"],
            ),
        )
        expected_pods = service_state["expectedPods"]
        expected_ports = [
            {
                "name": port["name"],
                "port": port["targetPort"],
                "protocol": port["protocol"],
            }
            for port in service_spec["ports"]
        ]
        if expected_pods:
            if not _same_unordered_unique_items(document["ports"], expected_ports):
                raise SoakValidationError(
                    "soak Workspace EndpointSlice ports are invalid"
                )
        elif document["ports"] != []:
            raise SoakValidationError(
                "soak empty Workspace EndpointSlice ports are invalid"
            )
        endpoints_by_pod_uid: dict[str, dict[str, Any]] = {}
        for endpoint in document["endpoints"]:
            target_reference = (
                endpoint.get("targetRef") if isinstance(endpoint, dict) else None
            )
            pod_uid = (
                target_reference.get("uid")
                if isinstance(target_reference, dict)
                else None
            )
            if not _nonempty(pod_uid) or pod_uid in endpoints_by_pod_uid:
                raise SoakValidationError(
                    "soak Workspace EndpointSlice Pod binding is ambiguous"
                )
            endpoints_by_pod_uid[pod_uid] = endpoint
        expected_pods_by_uid = {entry[1]["podUid"]: entry for entry in expected_pods}
        if not set(endpoints_by_pod_uid).issubset(expected_pods_by_uid):
            raise SoakValidationError(
                "soak Workspace EndpointSlice endpoint closure is invalid"
            )
        for pod_uid, endpoint in endpoints_by_pod_uid.items():
            pod, pod_snapshot = expected_pods_by_uid[pod_uid]
            allowed_keys = {
                "addresses",
                "conditions",
                "hints",
                "nodeName",
                "targetRef",
                "zone",
            }
            endpoint_keys = set(endpoint)
            if (
                not {"addresses", "conditions", "nodeName", "targetRef"}.issubset(
                    endpoint_keys
                )
                or not endpoint_keys.issubset(allowed_keys)
                or endpoint.get("addresses") != [pod_snapshot["podIP"]]
                or endpoint.get("conditions")
                != {"ready": True, "serving": True, "terminating": False}
                or endpoint.get("nodeName") != pod["spec"]["nodeName"]
                or endpoint.get("targetRef")
                != {
                    "kind": "Pod",
                    "namespace": pod["metadata"]["namespace"],
                    "name": pod["metadata"]["name"],
                    "uid": pod_uid,
                }
                or ("zone" in endpoint and not _nonempty(endpoint["zone"]))
                or (
                    "hints" in endpoint
                    and (
                        not isinstance(endpoint["hints"], dict)
                        or set(endpoint["hints"]) != {"forZones"}
                        or not isinstance(endpoint["hints"].get("forZones"), list)
                        or not endpoint["hints"]["forZones"]
                        or any(
                            not isinstance(zone, dict)
                            or set(zone) != {"name"}
                            or not _nonempty(zone.get("name"))
                            for zone in endpoint["hints"]["forZones"]
                        )
                    )
                )
            ):
                raise SoakValidationError(
                    "soak Workspace EndpointSlice endpoint is invalid"
                )
        already_bound = bound_pod_uids_by_service_uid[service_metadata["uid"]]
        if already_bound.intersection(endpoints_by_pod_uid):
            raise SoakValidationError(
                "soak Workspace EndpointSlice Pod binding is duplicated"
            )
        already_bound.update(endpoints_by_pod_uid)
        if expected_pods and not endpoints_by_pod_uid:
            raise SoakValidationError(
                "soak Workspace EndpointSlice contains an empty stale slice"
            )
        slices_by_service_uid[service_metadata["uid"]].append(document)
        canonical_ports = sorted(
            copy.deepcopy(document["ports"]),
            key=_canonical_digest,
        )
        snapshot = snapshots_by_service_uid.get(service_metadata["uid"])
        if snapshot is not None:
            snapshot.setdefault("endpointSlices", []).append(
                {
                    "name": name,
                    "uid": metadata["uid"],
                    "sha256": _canonical_digest(
                        {
                            "addressType": document["addressType"],
                            "labels": labels,
                            "ports": canonical_ports,
                            "endpoints": document["endpoints"],
                        }
                    ),
                }
            )
    for service_uid, items in slices_by_service_uid.items():
        expected_uids = {
            entry[1]["podUid"]
            for entry in managed_services[service_uid]["expectedPods"]
        }
        if (
            not items
            or bound_pod_uids_by_service_uid[service_uid] != expected_uids
            or (not expected_uids and len(items) != 1)
        ):
            raise SoakValidationError(
                "soak Workspace Service EndpointSlice closure is invalid"
            )
    for snapshot in snapshots:
        snapshot["endpointSlices"].sort(key=lambda item: item["name"])
    return sorted(
        snapshots, key=lambda item: SERVICE_COMPONENTS.index(item["component"])
    )


def _browser_readiness_snapshot(
    items: list[dict[str, Any]],
    *,
    controllers: dict[str, _ControllerState],
    target: _WorkspaceIdentity,
    target_pods: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    image_runtime_pairs: Mapping[str, frozenset[str]],
    service_accounts: Mapping[str, _WorkspaceServiceAccount],
) -> dict[str, Any]:
    authoritative = target_pods["workspace-browser"]
    if len(authoritative) != 1 or len(items) != 1:
        raise SoakValidationError("soak Browser Pod identity is ambiguous")
    pod, pod_snapshot = authoritative[0]
    secondary = items[0]
    secondary_metadata = secondary["metadata"]
    references = secondary_metadata.get("ownerReferences")
    owner_uid = (
        references[0].get("uid")
        if isinstance(references, list)
        and len(references) == 1
        and isinstance(references[0], dict)
        else None
    )
    owner = controllers.get(owner_uid)
    if (
        owner is None
        or owner.workspace is None
        or owner.workspace.uid != target.uid
        or owner.component != "workspace-browser"
    ):
        raise SoakValidationError("soak Browser secondary Pod ownership is invalid")
    secondary_snapshot = _running_pod_snapshot(
        secondary,
        owner=owner,
        image_runtime_pairs=image_runtime_pairs,
        service_accounts=service_accounts,
    )
    if secondary_snapshot != pod_snapshot:
        raise SoakValidationError("soak Browser raw sources do not match")
    spec = pod.get("spec")
    containers = spec.get("containers") if isinstance(spec, dict) else None
    browser_containers = (
        [
            item
            for item in containers
            if isinstance(item, dict) and item.get("name") == BROWSER_CONTAINER_NAME
        ]
        if isinstance(containers, list)
        else []
    )
    runtime_containers = [
        item
        for item in pod_snapshot["containers"]
        if item.get("name") == BROWSER_CONTAINER_NAME
    ]
    if (
        len(BROWSER_READINESS_SCRIPT) != BROWSER_READINESS_PROBE_LENGTH
        or hashlib.sha256(BROWSER_READINESS_SCRIPT.encode("utf-8")).hexdigest()
        != BROWSER_READINESS_PROBE_SHA256
    ):
        raise SoakValidationError("soak Browser readiness probe identity is invalid")
    if len(browser_containers) != 1 or len(runtime_containers) != 1:
        raise SoakValidationError("soak Browser container identity is invalid")
    probe = browser_containers[0].get("readinessProbe")
    if (
        not isinstance(probe, dict)
        or set(probe)
        != {
            "exec",
            "periodSeconds",
            "timeoutSeconds",
            "failureThreshold",
            "successThreshold",
        }
        or probe.get("exec") != {"command": list(BROWSER_READINESS_COMMAND)}
        or probe.get("periodSeconds") != 5
        or probe.get("timeoutSeconds") != 2
        or probe.get("failureThreshold") != 3
        or probe.get("successThreshold") != 1
    ):
        raise SoakValidationError("soak Browser readiness probe is invalid")
    runtime = runtime_containers[0]
    return {
        "podName": pod_snapshot["podName"],
        "podUid": pod_snapshot["podUid"],
        "containerName": BROWSER_CONTAINER_NAME,
        "image": runtime["statusImage"],
        "imageID": runtime["imageID"],
        "containerID": runtime["containerID"],
        "restartCount": runtime["restartCount"],
        "runningStartedAt": runtime["runningStartedAt"],
        "started": True,
        "ready": True,
        "probeCommand": list(BROWSER_READINESS_COMMAND),
        "probeLength": BROWSER_READINESS_PROBE_LENGTH,
        "probeSha256": BROWSER_READINESS_PROBE_SHA256,
        "periodSeconds": 5,
        "timeoutSeconds": 2,
        "failureThreshold": 3,
        "successThreshold": 1,
    }


def snapshot_sample(
    query_documents: Mapping[str, Any],
    *,
    workspace_id: str,
    identity_mode: str,
    commit: str,
    deployment_run_id: str,
    image_runtime_pairs: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    """Validate all nine raw query documents and return one sealed snapshot."""

    expected_sources = {
        "identityPods",
        "turnPods",
        "workspacePods",
        "workspace",
        "workspaceServiceAccounts",
        "services",
        "endpointSlices",
        "browserPods",
        "controllers",
    }
    if (
        not isinstance(query_documents, Mapping)
        or set(query_documents) != expected_sources
        or not _nonempty(workspace_id)
        or identity_mode not in {"bundledKeycloak", "externalOidc"}
        or not isinstance(commit, str)
        or COMMIT_SHA.fullmatch(commit) is None
        or not isinstance(deployment_run_id, str)
        or RUN_ID.fullmatch(deployment_run_id) is None
    ):
        raise SoakValidationError("soak sample identity is invalid")
    validated_image_runtime_pairs = _validated_image_runtime_pairs(image_runtime_pairs)
    identity_pods = _list_items(
        query_documents["identityPods"],
        source="Identity Pod",
        allowed_gvks={("v1", "Pod")},
        namespace="aileron-identity-system",
    )
    turn_pods = _list_items(
        query_documents["turnPods"],
        source="TURN Pod",
        allowed_gvks={("v1", "Pod")},
        namespace="aileron-turn-system",
    )
    workspace_pods = _list_items(
        query_documents["workspacePods"],
        source="Workspace Pod",
        allowed_gvks={("v1", "Pod")},
        namespace=WORKSPACE_NAMESPACE,
    )
    browser_pods = _list_items(
        query_documents["browserPods"],
        source="Browser Pod",
        allowed_gvks={("v1", "Pod")},
        namespace=WORKSPACE_NAMESPACE,
    )
    services = _list_items(
        query_documents["services"],
        source="Service",
        allowed_gvks={("v1", "Service")},
        namespace=WORKSPACE_NAMESPACE,
    )
    endpoint_slices = _list_items(
        query_documents["endpointSlices"],
        source="EndpointSlice",
        allowed_gvks={("discovery.k8s.io/v1", "EndpointSlice")},
        namespace=WORKSPACE_NAMESPACE,
    )
    workspace_service_account_items = _list_items(
        query_documents["workspaceServiceAccounts"],
        source="Workspace ServiceAccount",
        allowed_gvks={("v1", "ServiceAccount")},
        namespace=WORKSPACE_NAMESPACE,
    )
    controller_items = _list_items(
        query_documents["controllers"],
        source="controller",
        allowed_gvks={
            ("apps/v1", "Deployment"),
            ("apps/v1", "StatefulSet"),
            ("apps/v1", "DaemonSet"),
            ("apps/v1", "ReplicaSet"),
            ("apps/v1", "ControllerRevision"),
            ("batch/v1", "Job"),
        },
    )
    if identity_mode == "externalOidc" and (
        identity_pods
        or any(
            item["metadata"]["namespace"] == "aileron-identity-system"
            for item in controller_items
        )
    ):
        raise SoakValidationError(
            "external OIDC soak contains bundled Identity resources"
        )
    workspaces, target, workspace_snapshot = _workspace_inventory(
        query_documents["workspace"], target_workspace_id=workspace_id
    )
    service_accounts, service_account_snapshots = _workspace_service_account_inventory(
        workspace_service_account_items,
        workspaces=workspaces,
        target=target,
    )
    controllers, controller_snapshots, revision_snapshots = _managed_controllers(
        controller_items,
        workspaces=workspaces,
        target=target,
        identity_mode=identity_mode,
    )
    pod_snapshots, target_pods, validated_pods = _pod_inventory(
        [*identity_pods, *turn_pods, *workspace_pods],
        controllers=controllers,
        target=target,
        image_runtime_pairs=validated_image_runtime_pairs,
        service_accounts=service_accounts,
    )
    _validate_workspace_status_bindings(
        workspaces=workspaces,
        validated_pods=validated_pods,
    )
    service_snapshots = _service_snapshots(
        services,
        endpoint_slices,
        workspaces=workspaces,
        target=target,
        target_pods=target_pods,
        validated_pods=validated_pods,
    )
    browser_snapshot = _browser_readiness_snapshot(
        browser_pods,
        controllers=controllers,
        target=target,
        target_pods=target_pods,
        image_runtime_pairs=validated_image_runtime_pairs,
        service_accounts=service_accounts,
    )
    payload = {
        "controllers": sorted(
            controller_snapshots,
            key=lambda item: (item["namespace"], item["kind"], item["name"]),
        ),
        "controllerRevisions": sorted(
            revision_snapshots,
            key=lambda item: (item["namespace"], item["ownerKind"], item["name"]),
        ),
        "pods": sorted(
            pod_snapshots, key=lambda item: (item["namespace"], item["podName"])
        ),
        "workspace": workspace_snapshot,
        "serviceAccounts": sorted(
            service_account_snapshots,
            key=lambda item: (item["namespace"], item["name"]),
        ),
        "services": service_snapshots,
        "browserReadiness": browser_snapshot,
    }
    return {**payload, "sha256": _canonical_digest(payload)}


def validate_cadence(
    *,
    started: datetime,
    finished: datetime,
    sample_times: Sequence[datetime],
    sample_elapsed_milliseconds: Sequence[int],
    monotonic_duration_milliseconds: int,
    policy: SoakPolicy,
) -> None:
    """Validate monotonic cadence and bounded wall-clock audit drift."""

    if (
        not isinstance(started, datetime)
        or not isinstance(finished, datetime)
        or isinstance(monotonic_duration_milliseconds, bool)
        or not isinstance(monotonic_duration_milliseconds, int)
        or monotonic_duration_milliseconds < policy.duration_seconds * 1000
        or len(sample_times) != policy.minimum_samples
        or len(sample_elapsed_milliseconds) != len(sample_times)
        or any(not isinstance(value, datetime) for value in sample_times)
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not math.isfinite(value)
            or value < 0
            for value in sample_elapsed_milliseconds
        )
    ):
        raise SoakValidationError("soak cadence wall clock or sample count is invalid")
    if (
        not sample_times
        or sample_times[0] < started
        or sample_times[-1] > finished
        or any(
            sample_times[index] <= sample_times[index - 1]
            for index in range(1, len(sample_times))
        )
        or any(
            sample_elapsed_milliseconds[index] <= sample_elapsed_milliseconds[index - 1]
            for index in range(1, len(sample_elapsed_milliseconds))
        )
        or sample_elapsed_milliseconds[-1] > monotonic_duration_milliseconds
    ):
        raise SoakValidationError("soak cadence timestamps are not increasing")
    monotonic_points = [
        0,
        *sample_elapsed_milliseconds,
        monotonic_duration_milliseconds,
    ]
    if any(
        monotonic_points[index] - monotonic_points[index - 1]
        > policy.maximum_sample_gap_seconds * 1000
        for index in range(1, len(monotonic_points))
    ):
        raise SoakValidationError("soak cadence gap exceeds policy")
    wall_points = [started, *sample_times, finished]
    for previous_wall, current_wall, previous_elapsed, current_elapsed in zip(
        wall_points,
        wall_points[1:],
        monotonic_points,
        monotonic_points[1:],
    ):
        wall_step_milliseconds = round(
            (current_wall - previous_wall).total_seconds() * 1000
        )
        monotonic_step_milliseconds = current_elapsed - previous_elapsed
        if (
            wall_step_milliseconds < 0
            or abs(wall_step_milliseconds - monotonic_step_milliseconds)
            > policy.maximum_clock_drift_milliseconds
        ):
            raise SoakValidationError("soak wall and monotonic clock drift is invalid")
    cumulative_wall_milliseconds = [
        round((sample_time - started).total_seconds() * 1000)
        for sample_time in sample_times
    ]
    cumulative_wall_milliseconds.append(
        round((finished - started).total_seconds() * 1000)
    )
    cumulative_monotonic_milliseconds = [
        *sample_elapsed_milliseconds,
        monotonic_duration_milliseconds,
    ]
    if any(
        wall_elapsed < 0
        or abs(wall_elapsed - monotonic_elapsed)
        > policy.maximum_clock_drift_milliseconds
        for wall_elapsed, monotonic_elapsed in zip(
            cumulative_wall_milliseconds,
            cumulative_monotonic_milliseconds,
        )
    ):
        raise SoakValidationError("soak wall and monotonic clock drift is invalid")
