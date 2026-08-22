#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NamedTuple

import yaml

WORKLOAD_KINDS = {"DaemonSet", "Deployment", "Job", "StatefulSet"}
CORE_CAPACITY_WORKLOAD_KINDS = WORKLOAD_KINDS
DYNAMIC_IMAGE_KEYS = (
    "RUNTIME_K8S_IMAGE",
    "RUNTIME_K8S_BROWSER_IMAGE",
    "RUNTIME_K8S_CANVAS_IMAGE",
)
DYNAMIC_RESOURCE_KEYS = (
    "RUNTIME_K8S_RUNTIME_RESOURCES",
    "RUNTIME_K8S_BROWSER_RESOURCES",
    "RUNTIME_K8S_CANVAS_RESOURCES",
)
EXECUTION_PLANE_COMPONENTS = ("runtime", "browser", "canvas")
with Path(__file__).with_name("image-release-contract.json").open(
    encoding="utf-8"
) as _image_release_contract_stream:
    _image_release_contract = json.load(_image_release_contract_stream)
REQUIRED_WORKLOAD_IMAGE_COMPONENTS = tuple(
    _image_release_contract["workloadComponents"]
)
OPTIONAL_WORKLOAD_IMAGE_COMPONENTS = frozenset(
    _image_release_contract["optionalPublishedComponents"]
)
QUANTITY_PATTERN = re.compile(r"^(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<suffix>[A-Za-z]*)$")
GO_DURATION_PATTERN = re.compile(r"^(?P<value>[1-9][0-9]*)(?P<unit>ms|s|m)$")
DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
IMAGE_PULL_SECRET_OWNER_ANNOTATION = "platform.aileron.dev/image-pull-secret-owner"
IMAGE_PULL_SECRET_SOURCE_ANNOTATION = "platform.aileron.dev/image-pull-secret-source"
IMAGE_PULL_SECRET_OWNER_LABEL = "platform.aileron.dev/image-pull-secret-owner"
IMAGE_PULL_SECRET_MANAGED_BY = "aileron-rke2-deployer"
NAMESPACE_OWNER_LABEL = "platform.aileron.dev/namespace-owner"
POD_SECURITY_ENFORCE_LABEL = "pod-security.kubernetes.io/enforce"
MEMORY_MULTIPLIERS = {
    "": 1,
    "k": 1_000,
    "K": 1_000,
    "M": 1_000_000,
    "G": 1_000_000_000,
    "T": 1_000_000_000_000,
    "P": 1_000_000_000_000_000,
    "E": 1_000_000_000_000_000_000,
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
}


class Toleration(NamedTuple):
    key: str
    operator: str
    value: str
    effect: str
    toleration_seconds: int | None


class PlannedCoreWorkload(NamedTuple):
    kind: str
    namespace: str
    name: str
    selector: tuple[tuple[str, str], ...]
    node_selector: tuple[tuple[str, str], ...]
    tolerations: tuple[Toleration, ...]
    update_strategy: str
    replicas: int
    rollout_surge: int
    cpu: int
    memory: int

    @property
    def identity(self) -> str:
        return f"{self.kind}/{self.namespace}/{self.name}"

    @property
    def capacity_replicas(self) -> int:
        return self.replicas + self.rollout_surge


class CurrentCorePod(NamedTuple):
    node_name: str
    cpu: int
    memory: int
    terminating: bool


def load_documents(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [
            document
            for document in yaml.safe_load_all(stream)
            if isinstance(document, dict)
        ]


def load_json_document(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def _is_helm_hook(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata")
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    return (
        isinstance(annotations, dict)
        and isinstance(annotations.get("helm.sh/hook"), str)
        and bool(annotations["helm.sh/hook"])
    )


def _canonical_manifest_documents(
    path: Path,
    *,
    document_class: str,
) -> list[str]:
    if document_class not in {"all", "release", "hooks"}:
        raise ValueError("manifest document class is invalid")
    documents = load_documents(path)
    if document_class == "release":
        documents = [document for document in documents if not _is_helm_hook(document)]
    elif document_class == "hooks":
        documents = [document for document in documents if _is_helm_hook(document)]
    return sorted(
        json.dumps(document, separators=(",", ":"), sort_keys=True)
        for document in documents
    )


def assert_equivalent_manifests(
    candidate: Path,
    live: Path,
    *,
    document_class: str = "all",
) -> None:
    """Assert that two manifest streams contain the same Kubernetes objects."""

    candidate_documents = _canonical_manifest_documents(
        candidate,
        document_class=document_class,
    )
    live_documents = _canonical_manifest_documents(
        live,
        document_class=document_class,
    )
    if not candidate_documents or candidate_documents != live_documents:
        raise ValueError("live Identity manifest does not match the planned snapshot")


def image_inventory(documents: list[dict[str, Any]]) -> list[str]:
    images: set[str] = set()
    platform_config_found = False
    for document in documents:
        kind = document.get("kind")
        if kind in WORKLOAD_KINDS or kind == "CronJob":
            spec = document.get("spec", {})
            if kind == "CronJob":
                spec = spec.get("jobTemplate", {}).get("spec", {})
            pod_spec = spec.get("template", {}).get("spec", {})
            for container_key in (
                "containers",
                "initContainers",
                "ephemeralContainers",
            ):
                for container in pod_spec.get(container_key, []):
                    image = container.get("image")
                    if isinstance(image, str) and image:
                        images.add(image)

        if kind == "ConfigMap" and str(
            document.get("metadata", {}).get("name", "")
        ).endswith("-platform-config"):
            platform_config_found = True
            data = document.get("data", {})
            missing = [
                key
                for key in DYNAMIC_IMAGE_KEYS
                if not isinstance(data.get(key), str) or not data[key]
            ]
            if missing:
                raise ValueError(
                    "platform config is missing dynamic images: "
                    + ", ".join(sorted(missing))
                )
            for key in DYNAMIC_IMAGE_KEYS:
                image = data[key]
                images.add(image)
    if not platform_config_found:
        raise ValueError("rendered manifests are missing the platform config")
    return sorted(images)


def _image_component(image: str) -> str:
    repository = image.split("@", 1)[0]
    last_slash = repository.rfind("/")
    last_colon = repository.rfind(":")
    if last_colon > last_slash:
        repository = repository[:last_colon]
    return repository.rsplit("/", 1)[-1]


def validate_identity_manifest_selection(
    *,
    identity_mode: str,
    additional_manifest_count: int,
) -> None:
    if identity_mode == "bundledKeycloak":
        if additional_manifest_count != 1:
            raise ValueError(
                "bundledKeycloak identity mode requires exactly one "
                "additional Identity manifest"
            )
    elif identity_mode == "externalOidc":
        if additional_manifest_count != 0:
            raise ValueError(
                "externalOidc identity mode must not include an Identity manifest"
            )
    else:
        raise ValueError("identity mode must be bundledKeycloak or externalOidc")


def named_workload_image_inventory(
    documents: list[dict[str, Any]],
    *,
    identity_mode: str,
) -> dict[str, str]:
    inventory: dict[str, str] = {}
    if identity_mode == "bundledKeycloak":
        required_components = REQUIRED_WORKLOAD_IMAGE_COMPONENTS
    elif identity_mode == "externalOidc":
        required_components = tuple(
            component
            for component in REQUIRED_WORKLOAD_IMAGE_COMPONENTS
            if component != "platform-keycloak"
        )
    else:
        raise ValueError("identity mode must be bundledKeycloak or externalOidc")
    allowed_components = set(required_components)
    for image in image_inventory(documents):
        component = _image_component(image)
        if component not in allowed_components:
            raise ValueError(
                f"rendered workload image component is not allowlisted: {component}"
            )
        existing = inventory.get(component)
        if existing is not None and existing != image:
            raise ValueError(
                "rendered workload component has multiple immutable references: "
                f"{component}"
            )
        inventory[component] = image

    actual_components = set(inventory)
    required_component_sets = (
        allowed_components,
        allowed_components - OPTIONAL_WORKLOAD_IMAGE_COMPONENTS,
    )
    if actual_components not in required_component_sets:
        missing = sorted(
            min(
                required_component_sets,
                key=lambda candidate: len(candidate - actual_components),
            )
            - actual_components
        )
        unexpected = sorted(actual_components - allowed_components)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        raise ValueError(
            "rendered named workload image inventory is incomplete: "
            + " ".join(details)
        )
    return {
        component: inventory[component]
        for component in required_components
        if component in inventory
    }


def _require_dns_subdomain(value: Any, *, description: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 253
        or any(
            len(label) > 63 or DNS_LABEL_PATTERN.fullmatch(label) is None
            for label in value.split(".")
        )
    ):
        raise ValueError(f"{description} must be a DNS subdomain")
    return value


def image_pull_secret_inventory(
    documents: list[dict[str, Any]],
    default_namespace: str,
) -> list[tuple[str, str]]:
    default_namespace = _require_dns_subdomain(
        default_namespace,
        description="default workload namespace",
    )
    inventory: set[tuple[str, str]] = set()
    namespace_secret_names: dict[str, tuple[str, ...]] = {}
    workload_count = 0
    for document in documents:
        kind = document.get("kind")
        if kind not in WORKLOAD_KINDS and kind != "CronJob":
            continue
        workload_count += 1
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("rendered workload metadata must be an object")
        namespace_value = (
            metadata["namespace"] if "namespace" in metadata else default_namespace
        )
        namespace = _require_dns_subdomain(
            namespace_value,
            description="rendered workload namespace",
        )
        spec = document.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("rendered workload spec must be an object")
        if kind == "CronJob":
            job_template = spec.get("jobTemplate")
            if not isinstance(job_template, dict):
                raise ValueError("rendered CronJob jobTemplate must be an object")
            spec = job_template.get("spec")
            if not isinstance(spec, dict):
                raise ValueError("rendered CronJob Job spec must be an object")
        template = spec.get("template")
        if not isinstance(template, dict):
            raise ValueError("rendered workload Pod template must be an object")
        pod_spec = template.get("spec")
        if not isinstance(pod_spec, dict):
            raise ValueError("rendered workload Pod spec must be an object")
        pull_secrets = pod_spec.get("imagePullSecrets")
        if not isinstance(pull_secrets, list) or not pull_secrets:
            raise ValueError(
                "every rendered workload must use at least one image pull Secret"
            )

        names: list[str] = []
        for pull_secret in pull_secrets:
            if not isinstance(pull_secret, dict):
                raise ValueError("rendered image pull Secret entry must be an object")
            name = _require_dns_subdomain(
                pull_secret.get("name"),
                description="rendered image pull Secret name",
            )
            names.append(name)
        if len(set(names)) != len(names):
            raise ValueError("rendered image pull Secret inventory contains duplicates")
        secret_names = tuple(names)
        existing_names = namespace_secret_names.get(namespace)
        if existing_names is None:
            namespace_secret_names[namespace] = secret_names
        elif existing_names != secret_names:
            raise ValueError(
                "rendered workloads in one namespace must use an identical "
                "image pull Secret inventory"
            )
        inventory.update((namespace, name) for name in names)

    if workload_count == 0:
        raise ValueError("rendered manifests do not contain workloads")
    if not inventory:
        raise ValueError("rendered manifests do not contain image pull Secrets")
    return sorted(inventory)


def namespace_inventory(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    namespaces: dict[str, dict[str, Any]] = {}
    for document in documents:
        if document.get("kind") != "Namespace":
            continue
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("rendered Namespace metadata must be an object")
        name = _require_dns_subdomain(
            metadata.get("name"),
            description="rendered Namespace name",
        )
        if name in namespaces:
            raise ValueError(f"rendered manifests duplicate Namespace: {name}")
        labels = metadata.get("labels", {})
        annotations = metadata.get("annotations", {})
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise ValueError("rendered Namespace labels must be a string object")
        if not isinstance(annotations, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in annotations.items()
        ):
            raise ValueError("rendered Namespace annotations must be a string object")
        namespaces[name] = {
            "name": name,
            "labels": labels,
            "annotations": annotations,
        }
    return [namespaces[name] for name in sorted(namespaces)]


def validate_privileged_namespace_evidence(
    documents: list[dict[str, Any]],
    *,
    namespace: str,
    owner_marker: str,
) -> None:
    namespace = _require_dns_subdomain(
        namespace,
        description="privileged namespace evidence name",
    )
    if not isinstance(owner_marker, str) or not owner_marker:
        raise ValueError("privileged namespace evidence owner marker is required")
    if len(documents) != 1 or documents[0].get("kind") != "Namespace":
        raise ValueError(
            "privileged namespace evidence must contain exactly one Namespace"
        )
    metadata = documents[0].get("metadata")
    if not isinstance(metadata, dict) or metadata.get("name") != namespace:
        raise ValueError("privileged namespace evidence name does not match")
    labels = metadata.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("privileged namespace evidence labels are invalid")
    if labels.get(NAMESPACE_OWNER_LABEL) != owner_marker:
        raise ValueError("privileged namespace evidence owner does not match")
    if labels.get(POD_SECURITY_ENFORCE_LABEL) != "privileged":
        raise ValueError("privileged namespace evidence PSA enforce level is invalid")


def ingress_tls_secret_for_host(
    documents: list[dict[str, Any]],
    *,
    default_namespace: str,
    host: str,
) -> tuple[str, str]:
    default_namespace = _require_dns_subdomain(
        default_namespace,
        description="default Ingress namespace",
    )
    host = _require_dns_subdomain(
        host,
        description="Ingress TLS host",
    )
    matching_ingresses = 0
    matches: set[tuple[str, str]] = set()
    for document in documents:
        if document.get("kind") != "Ingress":
            continue
        metadata = document.get("metadata")
        spec = document.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise ValueError("rendered Ingress metadata and spec must be objects")
        rules = spec.get("rules")
        if not isinstance(rules, list):
            raise ValueError("rendered Ingress rules must be an array")
        rule_hosts = {
            rule.get("host")
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("host"), str)
        }
        if host not in rule_hosts:
            continue
        matching_ingresses += 1
        namespace_value = (
            metadata["namespace"] if "namespace" in metadata else default_namespace
        )
        namespace = _require_dns_subdomain(
            namespace_value,
            description="rendered Ingress namespace",
        )
        tls_entries = spec.get("tls")
        if not isinstance(tls_entries, list) or not tls_entries:
            raise ValueError("rendered frontend Ingress must declare TLS")
        for tls_entry in tls_entries:
            if not isinstance(tls_entry, dict):
                raise ValueError("rendered Ingress TLS entry must be an object")
            tls_hosts = tls_entry.get("hosts")
            if not isinstance(tls_hosts, list) or any(
                not isinstance(tls_host, str) for tls_host in tls_hosts
            ):
                raise ValueError("rendered Ingress TLS hosts must be an array")
            if host not in tls_hosts:
                continue
            secret_name = _require_dns_subdomain(
                tls_entry.get("secretName"),
                description="rendered Ingress TLS Secret name",
            )
            matches.add((namespace, secret_name))
    if matching_ingresses != 1:
        raise ValueError("rendered manifests must contain exactly one frontend Ingress")
    if len(matches) != 1:
        raise ValueError(
            "rendered frontend Ingress must map its host to exactly one TLS Secret"
        )
    return next(iter(matches))


def _docker_config_auths(
    secret: dict[str, Any],
    *,
    namespace: str,
    name: str,
) -> dict[str, Any]:
    metadata = secret.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("namespace") != namespace
        or metadata.get("name") != name
    ):
        raise ValueError("image pull Secret identity does not match the workload")
    if secret.get("type") != "kubernetes.io/dockerconfigjson":
        raise ValueError("image pull Secret has the wrong Kubernetes type")
    data = secret.get("data")
    if not isinstance(data, dict):
        raise ValueError("image pull Secret data must be an object")
    encoded_config = data.get(".dockerconfigjson")
    if not isinstance(encoded_config, str) or not encoded_config:
        raise ValueError("image pull Secret is missing .dockerconfigjson")
    try:
        decoded_config = base64.b64decode(encoded_config, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            "image pull Secret contains invalid base64 Docker config data"
        ) from exc
    try:
        docker_config = json.loads(decoded_config)
    except json.JSONDecodeError as exc:
        raise ValueError("image pull Secret Docker config is invalid JSON") from exc
    if not isinstance(docker_config, dict) or not isinstance(
        docker_config.get("auths"),
        dict,
    ):
        raise ValueError("image pull Secret Docker config auths must be an object")
    return docker_config["auths"]


def _normalized_registry_auth(registry_auth: Any) -> dict[str, str] | None:
    if not isinstance(registry_auth, dict) or not registry_auth:
        return None
    encoded_auth = registry_auth.get("auth")
    if isinstance(encoded_auth, str) and encoded_auth:
        try:
            decoded_auth = base64.b64decode(
                encoded_auth,
                validate=True,
            ).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            pass
        else:
            username, separator, password = decoded_auth.partition(":")
            if separator and username and password:
                canonical_auth = base64.b64encode(
                    f"{username}:{password}".encode("utf-8")
                ).decode("ascii")
                return {"auth": canonical_auth}
    username = registry_auth.get("username")
    password = registry_auth.get("password")
    if (
        isinstance(username, str)
        and bool(username)
        and isinstance(password, str)
        and bool(password)
    ):
        encoded_credentials = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        return {"auth": encoded_credentials}
    return None


def _usable_registry_auth(registry_auth: Any) -> bool:
    return _normalized_registry_auth(registry_auth) is not None


def image_pull_secret_has_registry_auth(
    secret: dict[str, Any],
    *,
    namespace: str,
    name: str,
    registry: str,
) -> bool:
    auths = _docker_config_auths(
        secret,
        namespace=namespace,
        name=name,
    )
    return _usable_registry_auth(auths.get(registry))


def reconciled_image_pull_secret(
    secret: dict[str, Any],
    *,
    source_namespace: str,
    target_namespace: str,
    name: str,
    registry: str,
    owner_marker: str,
) -> dict[str, Any]:
    target_namespace = _require_dns_subdomain(
        target_namespace,
        description="target workload namespace",
    )
    if not isinstance(owner_marker, str) or not owner_marker:
        raise ValueError("image pull Secret owner marker must be non-empty")
    auths = _docker_config_auths(
        secret,
        namespace=source_namespace,
        name=name,
    )
    registry_auth = _normalized_registry_auth(auths.get(registry))
    if registry_auth is None:
        raise ValueError(
            "source image pull Secret does not contain usable registry credentials"
        )
    sanitized_config = json.dumps(
        {"auths": {registry: registry_auth}},
        separators=(",", ":"),
        sort_keys=True,
    )
    encoded_config = base64.b64encode(sanitized_config.encode("utf-8")).decode("ascii")
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "namespace": target_namespace,
            "name": name,
            "labels": {
                "app.kubernetes.io/managed-by": IMAGE_PULL_SECRET_MANAGED_BY,
                IMAGE_PULL_SECRET_OWNER_LABEL: owner_marker,
            },
            "annotations": {
                IMAGE_PULL_SECRET_OWNER_ANNOTATION: owner_marker,
                IMAGE_PULL_SECRET_SOURCE_ANNOTATION: (f"{source_namespace}/{name}"),
            },
        },
        "type": "kubernetes.io/dockerconfigjson",
        "data": {".dockerconfigjson": encoded_config},
    }


def _platform_config(documents: list[dict[str, Any]]) -> dict[str, Any]:
    for document in documents:
        if document.get("kind") == "ConfigMap" and str(
            document.get("metadata", {}).get("name", "")
        ).endswith("-platform-config"):
            data = document.get("data")
            if isinstance(data, dict):
                return data
            raise ValueError("platform config data must be an object")
    raise ValueError("rendered manifests are missing the platform config")


def _quantity_parts(quantity: Any, resource_name: str) -> tuple[Decimal, str]:
    if not isinstance(quantity, str) or not quantity:
        raise ValueError(f"{resource_name} must be a non-empty Kubernetes quantity")
    match = QUANTITY_PATTERN.fullmatch(quantity)
    if match is None:
        raise ValueError(f"unsupported {resource_name} quantity: {quantity}")
    try:
        value = Decimal(match.group("value"))
    except InvalidOperation as exc:
        raise ValueError(f"unsupported {resource_name} quantity: {quantity}") from exc
    return value, match.group("suffix")


def cpu_millicores(quantity: Any) -> int:
    value, suffix = _quantity_parts(quantity, "cpu")
    multipliers = {
        "": Decimal(1000),
        "m": Decimal(1),
        "u": Decimal("0.001"),
        "n": Decimal("0.000001"),
        "k": Decimal(1_000_000),
        "K": Decimal(1_000_000),
        "M": Decimal(1_000_000_000),
    }
    multiplier = multipliers.get(suffix)
    if multiplier is None:
        raise ValueError(f"unsupported cpu quantity: {quantity}")
    return int((value * multiplier).to_integral_value(rounding=ROUND_CEILING))


def memory_bytes(quantity: Any) -> int:
    value, suffix = _quantity_parts(quantity, "memory")
    multiplier = MEMORY_MULTIPLIERS.get(suffix)
    if multiplier is None:
        raise ValueError(f"unsupported memory quantity: {quantity}")
    return int((value * Decimal(multiplier)).to_integral_value(rounding=ROUND_CEILING))


def _resource_request(resources: Any) -> tuple[int, int]:
    if not isinstance(resources, dict):
        return 0, 0
    requests = resources.get("requests")
    if not isinstance(requests, dict):
        return 0, 0
    cpu = cpu_millicores(requests["cpu"]) if "cpu" in requests else 0
    memory = memory_bytes(requests["memory"]) if "memory" in requests else 0
    return cpu, memory


def execution_plane_component_requests(
    documents: list[dict[str, Any]],
) -> list[tuple[str, int, int]]:
    data = _platform_config(documents)
    components: list[tuple[str, int, int]] = []
    if len(EXECUTION_PLANE_COMPONENTS) != len(DYNAMIC_RESOURCE_KEYS):
        raise ValueError("execution plane component resource keys are inconsistent")
    for component, key in zip(EXECUTION_PLANE_COMPONENTS, DYNAMIC_RESOURCE_KEYS):
        raw_resources = data.get(key)
        if not isinstance(raw_resources, str) or not raw_resources:
            raise ValueError(f"platform config is missing dynamic resources: {key}")
        try:
            resources = json.loads(raw_resources)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"platform config dynamic resources are invalid JSON: {key}"
            ) from exc
        if not isinstance(resources, dict):
            raise ValueError(
                f"platform config dynamic resources must be an object: {key}"
            )
        requests = resources.get("requests")
        limits = resources.get("limits")
        if not isinstance(requests, dict) or not isinstance(limits, dict):
            raise ValueError(
                f"platform config dynamic resources require requests and limits: {key}"
            )
        for resource_name in ("cpu", "memory"):
            if resource_name not in requests or resource_name not in limits:
                raise ValueError(
                    "platform config dynamic resources require cpu and memory "
                    f"requests and limits: {key}"
                )
        request_cpu, request_memory = _resource_request(resources)
        limit_cpu = cpu_millicores(limits["cpu"])
        limit_memory = memory_bytes(limits["memory"])
        if request_cpu > limit_cpu or request_memory > limit_memory:
            raise ValueError(
                f"platform config dynamic resource request exceeds limit: {key}"
            )
        components.append((component, request_cpu, request_memory))
    return components


def _string_map(value: Any, *, description: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be an object")
    normalized: list[tuple[str, str]] = []
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise ValueError(f"{description} must contain non-empty string entries")
        normalized.append((key, item))
    return tuple(sorted(normalized))


def _tolerations(value: Any, *, description: str) -> tuple[Toleration, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{description} must be an array")
    normalized: list[Toleration] = []
    allowed_keys = {"key", "operator", "value", "effect", "tolerationSeconds"}
    for item in value:
        if not isinstance(item, dict) or not set(item).issubset(allowed_keys):
            raise ValueError(f"{description} contains an invalid toleration")
        key = item.get("key", "")
        operator = item.get("operator", "Equal")
        toleration_value = item.get("value", "")
        effect = item.get("effect", "")
        toleration_seconds = item.get("tolerationSeconds")
        if (
            not isinstance(key, str)
            or not isinstance(operator, str)
            or operator not in {"Equal", "Exists"}
            or not isinstance(toleration_value, str)
            or not isinstance(effect, str)
            or effect not in {"", "NoSchedule", "PreferNoSchedule", "NoExecute"}
            or (operator == "Equal" and not key)
            or (operator == "Exists" and toleration_value)
            or (
                toleration_seconds is not None
                and (
                    isinstance(toleration_seconds, bool)
                    or not isinstance(toleration_seconds, int)
                    or toleration_seconds < 0
                    or effect != "NoExecute"
                )
            )
        ):
            raise ValueError(f"{description} contains an invalid toleration")
        normalized.append(
            Toleration(
                key=key,
                operator=operator,
                value=toleration_value,
                effect=effect,
                toleration_seconds=toleration_seconds,
            )
        )
    return tuple(normalized)


def _scaled_int_or_percent(value: Any, replicas: int, *, description: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{description} is invalid")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"{description} is invalid")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{description} is invalid")
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    percentage = re.fullmatch(r"([0-9]+)%", value)
    if percentage is None:
        raise ValueError(f"{description} is invalid")
    return (replicas * int(percentage.group(1)) + 99) // 100


def _deployment_rollout_strategy(
    spec: dict[str, Any],
    *,
    replicas: int,
    deployment_mode: str,
    name: str,
) -> tuple[str, int]:
    if deployment_mode == "clean-install":
        return "clean-install", 0
    strategy = spec.get("strategy", {})
    if not isinstance(strategy, dict):
        raise ValueError(f"rendered Core Deployment strategy is invalid: {name}")
    strategy_type = strategy.get("type", "RollingUpdate")
    if strategy_type == "Recreate":
        if strategy.get("rollingUpdate") is not None:
            raise ValueError(f"rendered Core Deployment strategy is invalid: {name}")
        return strategy_type, 0
    if strategy_type != "RollingUpdate":
        raise ValueError(f"rendered Core Deployment strategy is invalid: {name}")
    rolling_update = strategy.get("rollingUpdate", {})
    if not isinstance(rolling_update, dict):
        raise ValueError(f"rendered Core Deployment strategy is invalid: {name}")
    return (
        strategy_type,
        _scaled_int_or_percent(
            rolling_update.get("maxSurge", "25%"),
            replicas,
            description=f"rendered Core Deployment maxSurge for {name}",
        ),
    )


def _statefulset_update_strategy(spec: dict[str, Any], *, name: str) -> str:
    strategy = spec.get("updateStrategy", {})
    if not isinstance(strategy, dict):
        raise ValueError(f"rendered Core StatefulSet strategy is invalid: {name}")
    strategy_type = strategy.get("type", "RollingUpdate")
    if strategy_type not in {"RollingUpdate", "OnDelete"}:
        raise ValueError(f"rendered Core StatefulSet strategy is invalid: {name}")
    return strategy_type


def _validate_modeled_scheduling_constraints(
    pod_spec: dict[str, Any],
    *,
    name: str,
) -> None:
    unsupported = []
    if pod_spec.get("affinity") is not None and pod_spec.get("affinity") != {}:
        unsupported.append("affinity")
    if (
        pod_spec.get("topologySpreadConstraints") is not None
        and pod_spec.get("topologySpreadConstraints") != []
    ):
        unsupported.append("topologySpreadConstraints")
    if pod_spec.get("nodeName") not in (None, ""):
        unsupported.append("nodeName")
    if pod_spec.get("schedulerName") not in (None, "", "default-scheduler"):
        unsupported.append("schedulerName")
    if (
        pod_spec.get("schedulingGates") is not None
        and pod_spec.get("schedulingGates") != []
    ):
        unsupported.append("schedulingGates")
    if pod_spec.get("runtimeClassName") not in (None, ""):
        unsupported.append("runtimeClassName")
    if unsupported:
        raise ValueError(
            "rendered Core workload uses unsupported scheduling constraints: "
            f"{name}:" + ",".join(unsupported)
        )


def planned_core_workloads(
    documents: list[dict[str, Any]],
    *,
    default_namespace: str,
    deployment_mode: str,
) -> list[PlannedCoreWorkload]:
    """Return the peak schedulable Core footprint from the rendered release."""

    default_namespace = _require_dns_subdomain(
        default_namespace,
        description="default workload namespace",
    )
    if deployment_mode not in {"clean-install", "upgrade"}:
        raise ValueError("Core deployment mode is invalid")
    workloads: list[PlannedCoreWorkload] = []
    identities: set[tuple[str, str, str]] = set()
    for document in documents:
        kind = document.get("kind")
        if kind not in CORE_CAPACITY_WORKLOAD_KINDS:
            continue
        metadata = document.get("metadata")
        spec = document.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise ValueError("rendered Core workload metadata and spec must be objects")
        name = _require_dns_subdomain(
            metadata.get("name"),
            description="rendered Core workload name",
        )
        namespace = _require_dns_subdomain(
            metadata.get("namespace", default_namespace),
            description="rendered Core workload namespace",
        )
        identity = (kind, namespace, name)
        if identity in identities:
            raise ValueError(
                "rendered manifests contain a duplicate Core workload: "
                f"{kind}/{namespace}/{name}"
            )
        identities.add(identity)

        template = spec.get("template")
        if not isinstance(template, dict):
            raise ValueError(f"rendered Core workload Pod template is invalid: {name}")
        template_metadata = template.get("metadata", {})
        if not isinstance(template_metadata, dict):
            raise ValueError(f"rendered Core workload Pod metadata is invalid: {name}")
        if kind == "Job":
            match_labels = _string_map(
                template_metadata.get("labels", {}),
                description=f"rendered Core workload labels for {name}",
            )
        else:
            selector = spec.get("selector")
            if not isinstance(selector, dict):
                raise ValueError(f"rendered Core workload selector is invalid: {name}")
            match_labels = _string_map(
                selector.get("matchLabels"),
                description=f"rendered Core workload selector for {name}",
            )
        if not match_labels:
            raise ValueError(f"rendered Core workload selector is empty: {name}")
        pod_spec = template.get("spec")
        if not isinstance(pod_spec, dict):
            raise ValueError(f"rendered Core workload Pod spec is invalid: {name}")
        _validate_modeled_scheduling_constraints(pod_spec, name=name)
        node_selector = _string_map(
            pod_spec.get("nodeSelector", {}),
            description=f"rendered Core workload nodeSelector for {name}",
        )
        tolerations = _tolerations(
            pod_spec.get("tolerations", []),
            description=f"rendered Core workload tolerations for {name}",
        )
        cpu, memory = _pod_requests(template)
        if kind == "DaemonSet":
            replicas_value = 0
        elif kind == "Job":
            replicas_value = (
                0 if spec.get("suspend") is True else spec.get("parallelism", 1)
            )
        else:
            replicas_value = spec.get("replicas", 1)
        if (
            isinstance(replicas_value, bool)
            or not isinstance(replicas_value, int)
            or replicas_value < 0
        ):
            raise ValueError(f"rendered Core workload replicas are invalid: {name}")
        update_strategy = kind
        rollout_surge = 0
        if kind == "Deployment":
            update_strategy, rollout_surge = _deployment_rollout_strategy(
                spec,
                replicas=replicas_value,
                deployment_mode=deployment_mode,
                name=name,
            )
        elif kind == "StatefulSet":
            update_strategy = _statefulset_update_strategy(spec, name=name)
        elif kind == "DaemonSet":
            update_strategy = spec.get("updateStrategy", {})
            if not isinstance(update_strategy, dict):
                raise ValueError(f"rendered Core DaemonSet strategy is invalid: {name}")
            strategy_type = update_strategy.get("type", "RollingUpdate")
            if strategy_type not in {"RollingUpdate", "OnDelete"}:
                raise ValueError(f"rendered Core DaemonSet strategy is invalid: {name}")
            rolling_update = update_strategy.get("rollingUpdate", {})
            if (
                not isinstance(rolling_update, dict)
                or _scaled_int_or_percent(
                    rolling_update.get("maxSurge", 0),
                    1,
                    description=f"rendered Core DaemonSet maxSurge for {name}",
                )
                != 0
            ):
                raise ValueError(
                    f"rendered Core DaemonSet maxSurge is unsupported: {name}"
                )
            update_strategy = strategy_type
        workloads.append(
            PlannedCoreWorkload(
                kind=kind,
                namespace=namespace,
                name=name,
                selector=match_labels,
                node_selector=node_selector,
                tolerations=tolerations,
                update_strategy=update_strategy,
                replicas=replicas_value,
                rollout_surge=rollout_surge,
                cpu=cpu,
                memory=memory,
            )
        )
    return workloads


def _pod_requests(pod: dict[str, Any]) -> tuple[int, int]:
    spec = pod.get("spec")
    if not isinstance(spec, dict):
        return 0, 0

    regular_cpu = 0
    regular_memory = 0
    for container in spec.get("containers", []):
        if not isinstance(container, dict):
            continue
        cpu, memory = _resource_request(container.get("resources"))
        regular_cpu += cpu
        regular_memory += memory

    init_cpu = 0
    init_memory = 0
    for container in spec.get("initContainers", []):
        if not isinstance(container, dict):
            continue
        cpu, memory = _resource_request(container.get("resources"))
        init_cpu = max(init_cpu, cpu)
        init_memory = max(init_memory, memory)

    overhead_cpu, overhead_memory = _resource_request(
        {"requests": spec.get("overhead", {})}
    )
    return (
        max(regular_cpu, init_cpu) + overhead_cpu,
        max(regular_memory, init_memory) + overhead_memory,
    )


def _node_ready(node: dict[str, Any]) -> bool:
    conditions = node.get("status", {}).get("conditions", [])
    return any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in conditions
        if isinstance(condition, dict)
    )


def _node_is_capacity_candidate(node: dict[str, Any]) -> bool:
    metadata = node.get("metadata", {})
    spec = node.get("spec", {})
    if metadata.get("labels", {}).get("kubernetes.io/arch") != "amd64":
        return False
    if spec.get("unschedulable", False) or not _node_ready(node):
        return False
    return True


def _node_matches_selector(
    node: dict[str, Any],
    selector: tuple[tuple[str, str], ...],
) -> bool:
    labels = node.get("metadata", {}).get("labels", {})
    return isinstance(labels, dict) and all(
        labels.get(key) == value for key, value in selector
    )


def _toleration_matches_taint(toleration: Toleration, taint: dict[str, Any]) -> bool:
    taint_key = taint.get("key")
    taint_value = taint.get("value", "")
    taint_effect = taint.get("effect", "")
    if (
        not isinstance(taint_key, str)
        or not taint_key
        or not isinstance(taint_value, str)
        or not isinstance(taint_effect, str)
    ):
        return False
    if toleration.effect and toleration.effect != taint_effect:
        return False
    if taint_effect == "NoExecute" and toleration.toleration_seconds is not None:
        return False
    if toleration.operator == "Exists":
        return not toleration.key or toleration.key == taint_key
    return toleration.key == taint_key and toleration.value == taint_value


def _node_accepts_workload(
    node: dict[str, Any],
    *,
    node_selector: tuple[tuple[str, str], ...],
    tolerations: tuple[Toleration, ...],
) -> bool:
    if not _node_is_capacity_candidate(node) or not _node_matches_selector(
        node, node_selector
    ):
        return False
    taints = node.get("spec", {}).get("taints", [])
    if not isinstance(taints, list):
        return False
    return all(
        taint.get("effect") not in {"NoSchedule", "NoExecute"}
        or any(
            _toleration_matches_taint(toleration, taint) for toleration in tolerations
        )
        for taint in taints
        if isinstance(taint, dict)
    )


def _format_memory(value: int) -> str:
    gibibyte = 1024**3
    mebibyte = 1024**2
    if value % gibibyte == 0:
        return f"{value // gibibyte}Gi"
    return f"{value // mebibyte}Mi"


def _matching_current_core_workload(
    pod: dict[str, Any],
    workloads: list[PlannedCoreWorkload],
) -> PlannedCoreWorkload | None:
    metadata = pod.get("metadata")
    if not isinstance(metadata, dict):
        return None
    namespace = metadata.get("namespace")
    labels = metadata.get("labels")
    if not isinstance(namespace, str) or not isinstance(labels, dict):
        return None
    matches = [
        workload
        for workload in workloads
        if (
            namespace == workload.namespace
            and all(labels.get(key) == value for key, value in workload.selector)
        )
    ]
    if len(matches) > 1:
        raise ValueError("current Core Pod matches multiple rendered workloads")
    return matches[0] if matches else None


def _assign_execution_plane_components(
    components: list[tuple[str, int, int]],
    available: dict[str, tuple[int, int]],
    *,
    allowed_nodes: dict[str, frozenset[str]] | None = None,
) -> dict[str, str] | None:
    remaining = dict(available)
    assignment: dict[str, str] = {}
    ordered_components = sorted(
        components,
        key=lambda item: (-item[2], -item[1]),
    )
    node_names = sorted(remaining)

    def assign(index: int) -> bool:
        if index == len(ordered_components):
            return True
        component, required_cpu, required_memory = ordered_components[index]
        previous_capacities: set[tuple[int, int]] = set()
        for node_name in node_names:
            component_allowed_nodes = (
                allowed_nodes.get(component) if allowed_nodes is not None else None
            )
            if (
                component_allowed_nodes is not None
                and node_name not in component_allowed_nodes
            ):
                continue
            available_cpu, available_memory = remaining[node_name]
            capacity = (available_cpu, available_memory)
            if allowed_nodes is None and capacity in previous_capacities:
                continue
            if allowed_nodes is None:
                previous_capacities.add(capacity)
            if available_cpu < required_cpu or available_memory < required_memory:
                continue
            remaining[node_name] = (
                available_cpu - required_cpu,
                available_memory - required_memory,
            )
            assignment[component] = node_name
            if assign(index + 1):
                return True
            assignment.pop(component)
            remaining[node_name] = capacity
        return False

    return assignment if assign(0) else None


def _format_component_requests(
    components: list[tuple[str, int, int]],
) -> str:
    return ",".join(
        f"{name}={cpu}m/{_format_memory(memory)}" for name, cpu, memory in components
    )


def _validate_upgrade_existing_plus_surge(
    components: list[tuple[str, int, int]],
    workloads: list[PlannedCoreWorkload],
    current_core_pods: dict[str, list[CurrentCorePod]],
    eligible_nodes: dict[str, dict[str, Any]],
    candidates: dict[str, tuple[int, int]],
) -> str:
    phase_components = list(components)
    execution_plane_nodes = frozenset(
        node_name
        for node_name, node in eligible_nodes.items()
        if _node_accepts_workload(node, node_selector=(), tolerations=())
    )
    allowed_nodes: dict[str, frozenset[str]] = {
        component: execution_plane_nodes for component in EXECUTION_PLANE_COMPONENTS
    }
    additions: list[str] = []
    for workload in workloads:
        current_pods = current_core_pods.get(workload.identity, [])
        additional_replicas = 0
        if (
            workload.kind == "Deployment"
            and workload.update_strategy == "RollingUpdate"
        ):
            active_current_count = sum(
                not current_pod.terminating for current_pod in current_pods
            )
            additional_replicas = max(
                0,
                workload.capacity_replicas - active_current_count,
            )
        elif workload.kind == "StatefulSet":
            active_current_count = sum(
                not current_pod.terminating for current_pod in current_pods
            )
            additional_replicas = max(
                0,
                workload.replicas - active_current_count,
            )
        elif workload.kind == "Job":
            additional_replicas = workload.replicas
        matching_node_names = frozenset(
            node_name
            for node_name, node in eligible_nodes.items()
            if _node_accepts_workload(
                node,
                node_selector=workload.node_selector,
                tolerations=workload.tolerations,
            )
        )
        if workload.kind == "DaemonSet":
            active_current_nodes = {
                current_pod.node_name
                for current_pod in current_pods
                if not current_pod.terminating
            }
            missing_node_names = sorted(matching_node_names - active_current_nodes)
            if missing_node_names:
                additions.append(
                    f"{workload.identity}=nodes({','.join(missing_node_names)})"
                )
            for node_name in missing_node_names:
                component_name = f"transition:{workload.identity}:{node_name}"
                phase_components.append((component_name, workload.cpu, workload.memory))
                allowed_nodes[component_name] = frozenset({node_name})
            continue
        if additional_replicas == 0:
            continue
        additions.append(f"{workload.identity}={additional_replicas}x")
        for replica_index in range(additional_replicas):
            component_name = f"transition:{workload.identity}:{replica_index}"
            phase_components.append((component_name, workload.cpu, workload.memory))
            allowed_nodes[component_name] = matching_node_names

    assignment = _assign_execution_plane_components(
        phase_components,
        candidates,
        allowed_nodes=allowed_nodes,
    )
    candidate_summary = (
        ",".join(
            f"{node_name}={cpu}m/{_format_memory(memory)}"
            for node_name, (cpu, memory) in sorted(candidates.items())
        )
        if candidates
        else "none"
    )
    additions_summary = ",".join(additions) if additions else "none"
    if assignment is None:
        raise ValueError(
            "no feasible cross-node assignment for one Workspace during "
            "upgrade existing-Core-plus-surge phase; "
            f"components={_format_component_requests(components)} "
            f"available={candidate_summary} "
            f"transition-additional={additions_summary}"
        )
    assignment_summary = ",".join(
        f"{component}:{assignment[component]}"
        for component in EXECUTION_PLANE_COMPONENTS
    )
    return (
        f"assignment={assignment_summary} available={candidate_summary} "
        f"additional={additions_summary}"
    )


def validate_execution_plane_capacity(
    documents: list[dict[str, Any]],
    nodes: dict[str, Any],
    pods: dict[str, Any],
    *,
    default_namespace: str = "default",
    deployment_mode: str = "clean-install",
) -> str:
    components = execution_plane_component_requests(documents)
    required_cpu = sum(component[1] for component in components)
    required_memory = sum(component[2] for component in components)
    core_workloads = planned_core_workloads(
        documents,
        default_namespace=default_namespace,
        deployment_mode=deployment_mode,
    )
    assigned: dict[str, tuple[int, int]] = {}
    assigned_with_current_core: dict[str, tuple[int, int]] = {}
    current_core_pods: dict[str, list[CurrentCorePod]] = {}
    for pod in pods.get("items", []):
        if not isinstance(pod, dict):
            continue
        if pod.get("status", {}).get("phase") in {"Succeeded", "Failed"}:
            continue
        node_name = pod.get("spec", {}).get("nodeName")
        if not isinstance(node_name, str) or not node_name:
            continue
        pod_cpu, pod_memory = _pod_requests(pod)
        all_current_cpu, all_current_memory = assigned_with_current_core.get(
            node_name,
            (0, 0),
        )
        assigned_with_current_core[node_name] = (
            all_current_cpu + pod_cpu,
            all_current_memory + pod_memory,
        )
        current_workload = _matching_current_core_workload(pod, core_workloads)
        if deployment_mode == "upgrade" and current_workload is not None:
            current_core_pods.setdefault(current_workload.identity, []).append(
                CurrentCorePod(
                    node_name=node_name,
                    cpu=pod_cpu,
                    memory=pod_memory,
                    terminating=bool(pod.get("metadata", {}).get("deletionTimestamp")),
                )
            )
            continue
        current_cpu, current_memory = assigned.get(node_name, (0, 0))
        assigned[node_name] = (
            current_cpu + pod_cpu,
            current_memory + pod_memory,
        )

    candidates: dict[str, tuple[int, int]] = {}
    transition_candidates: dict[str, tuple[int, int]] = {}
    candidate_summaries: list[str] = []
    eligible_nodes: dict[str, dict[str, Any]] = {}
    for node in nodes.get("items", []):
        if not isinstance(node, dict) or not _node_is_capacity_candidate(node):
            continue
        node_name = str(node.get("metadata", {}).get("name", ""))
        if not node_name:
            continue
        allocatable = node.get("status", {}).get("allocatable", {})
        if not isinstance(allocatable, dict):
            continue
        if "cpu" not in allocatable or "memory" not in allocatable:
            continue
        allocatable_cpu = cpu_millicores(allocatable["cpu"])
        allocatable_memory = memory_bytes(allocatable["memory"])
        requested_cpu, requested_memory = assigned.get(node_name, (0, 0))
        available_cpu = max(0, allocatable_cpu - requested_cpu)
        available_memory = max(0, allocatable_memory - requested_memory)
        candidate_summaries.append(
            f"{node_name}={available_cpu}m/{_format_memory(available_memory)}"
        )
        candidates[node_name] = (available_cpu, available_memory)
        transition_cpu, transition_memory = assigned_with_current_core.get(
            node_name,
            (0, 0),
        )
        transition_candidates[node_name] = (
            max(0, allocatable_cpu - transition_cpu),
            max(0, allocatable_memory - transition_memory),
        )
        eligible_nodes[node_name] = node

    upgrade_transition_summary = ""
    if deployment_mode == "upgrade":
        upgrade_transition_summary = _validate_upgrade_existing_plus_surge(
            components,
            core_workloads,
            current_core_pods,
            eligible_nodes,
            transition_candidates,
        )

    capacity_components = list(components)
    execution_plane_nodes = frozenset(
        node_name
        for node_name, node in eligible_nodes.items()
        if _node_accepts_workload(node, node_selector=(), tolerations=())
    )
    allowed_nodes: dict[str, frozenset[str]] = {
        component: execution_plane_nodes for component in EXECUTION_PLANE_COMPONENTS
    }
    planned_core_cpu = 0
    planned_core_memory = 0
    planned_core_summaries: list[str] = []
    fixed_failures: list[str] = []
    for workload in core_workloads:
        matching_node_names = sorted(
            node_name
            for node_name, node in eligible_nodes.items()
            if _node_accepts_workload(
                node,
                node_selector=workload.node_selector,
                tolerations=workload.tolerations,
            )
        )
        if workload.kind == "DaemonSet":
            planned_core_summaries.append(
                f"{workload.identity}=each({len(matching_node_names)})x"
                f"{workload.cpu}m/{_format_memory(workload.memory)}"
            )
            if not matching_node_names:
                fixed_failures.append(f"{workload.identity}@no-eligible-node")
            planned_core_cpu += workload.cpu * len(matching_node_names)
            planned_core_memory += workload.memory * len(matching_node_names)
            for node_name in matching_node_names:
                available_cpu, available_memory = candidates[node_name]
                if available_cpu < workload.cpu or available_memory < workload.memory:
                    fixed_failures.append(f"{workload.identity}@{node_name}")
                candidates[node_name] = (
                    max(0, available_cpu - workload.cpu),
                    max(0, available_memory - workload.memory),
                )
            continue

        replica_summary = f"{workload.capacity_replicas}x"
        if workload.rollout_surge:
            replica_summary = f"peak({workload.replicas}+{workload.rollout_surge})x"
        planned_core_summaries.append(
            f"{workload.identity}={replica_summary}"
            f"{workload.cpu}m/{_format_memory(workload.memory)}"
        )
        planned_core_cpu += workload.cpu * workload.capacity_replicas
        planned_core_memory += workload.memory * workload.capacity_replicas
        for replica_index in range(workload.capacity_replicas):
            component_name = f"core:{workload.identity}:{replica_index}"
            capacity_components.append((component_name, workload.cpu, workload.memory))
            allowed_nodes[component_name] = frozenset(matching_node_names)

    assignment = (
        None
        if fixed_failures
        else _assign_execution_plane_components(
            capacity_components,
            candidates,
            allowed_nodes=allowed_nodes,
        )
    )
    component_summary = _format_component_requests(components)
    candidate_summary = (
        ",".join(sorted(candidate_summaries)) if candidate_summaries else "none"
    )
    planned_core_summary = (
        ",".join(planned_core_summaries) if planned_core_summaries else "none"
    )
    planned_core_details = ""
    if core_workloads:
        planned_core_details = (
            f" planned-core-required={planned_core_cpu}m/"
            f"{_format_memory(planned_core_memory)}"
            f" planned-core={planned_core_summary}"
        )
    if assignment is not None:
        assignment_summary = ",".join(
            f"{component}:{assignment[component]}"
            for component in EXECUTION_PLANE_COMPONENTS
        )
        result = (
            f"assignment={assignment_summary} required={required_cpu}m/"
            f"{_format_memory(required_memory)} components={component_summary} "
            f"available={candidate_summary}"
            f"{planned_core_details}"
        )
        if upgrade_transition_summary:
            result += f" upgrade-transition={upgrade_transition_summary}"
        return result

    unplaceable = [
        f"{name}={cpu}m/{_format_memory(memory)}"
        for name, cpu, memory in components
        if not any(
            node_name in allowed_nodes[name]
            and available_cpu >= cpu
            and available_memory >= memory
            for node_name, (available_cpu, available_memory) in candidates.items()
        )
    ]
    unplaceable_summary = ",".join(unplaceable) if unplaceable else "none"
    planned_unplaceable = list(fixed_failures)
    for name, cpu, memory in capacity_components[len(components) :]:
        component_allowed_nodes = allowed_nodes[name]
        if not any(
            node_name in component_allowed_nodes
            and available_cpu >= cpu
            and available_memory >= memory
            for node_name, (available_cpu, available_memory) in candidates.items()
        ):
            planned_unplaceable.append(name)
    planned_unplaceable_summary = (
        ",".join(planned_unplaceable) if planned_unplaceable else "none"
    )
    raise ValueError(
        "no feasible cross-node assignment for Core and one Workspace "
        "execution-plane; "
        f"required={required_cpu}m/{_format_memory(required_memory)} "
        f"components={component_summary} available={candidate_summary} "
        f"unplaceable={unplaceable_summary}; "
        f"planned-core-required={planned_core_cpu}m/"
        f"{_format_memory(planned_core_memory)} "
        f"planned-core={planned_core_summary} "
        f"planned-unplaceable={planned_unplaceable_summary}; "
        "free CPU/memory on eligible nodes or add a schedulable Ready amd64 node"
    )


def turn_enabled(documents: list[dict[str, Any]]) -> bool:
    for document in documents:
        if document.get("kind") != "Deployment":
            continue
        if not str(document.get("metadata", {}).get("name", "")).endswith(
            "-workspace-operator"
        ):
            continue
        containers = (
            document.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        return any(
            variable.get("name") == "TURN_ICE_SERVERS_SECRET_NAME"
            for container in containers
            for variable in container.get("env", [])
        )
    return False


def turn_provider(documents: list[dict[str, Any]]) -> str:
    for document in documents:
        if document.get("kind") != "DaemonSet":
            continue
        if str(document.get("metadata", {}).get("name", "")).endswith("-coturn"):
            return "builtin"
    return "external" if turn_enabled(documents) else "disabled"


def turn_server_host(documents: list[dict[str, Any]]) -> str:
    for document in documents:
        if document.get("kind") != "Deployment":
            continue
        if not str(document.get("metadata", {}).get("name", "")).endswith(
            "-workspace-operator"
        ):
            continue
        containers = (
            document.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        for container in containers:
            for variable in container.get("env", []):
                if variable.get("name") != "TURN_REACHABILITY_PROFILE_JSON":
                    continue
                try:
                    profile = json.loads(variable.get("value", ""))
                    urls = profile["frontend"]["urls"]
                except (KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        "rendered TURN reachability profile is invalid"
                    ) from exc
                if not isinstance(urls, list) or len(urls) != 1:
                    raise ValueError(
                        "rendered TURN reachability profile requires one frontend URL"
                    )
                value = urls[0]
                if not isinstance(value, str) or not value.startswith(
                    ("turn:", "turns:")
                ):
                    raise ValueError(
                        "rendered TURN reachability profile frontend URL is invalid"
                    )
                authority = value.split(":", 1)[1].split("?", 1)[0]
                if authority.startswith("["):
                    return authority.split("]", 1)[0][1:]
                return authority.rsplit(":", 1)[0]
    raise ValueError("rendered manifests are missing the TURN reachability profile")


def _is_restricted_connectivity_host_agent(
    kind: Any,
    name: str,
    metadata: dict[str, Any],
    pod_spec: dict[str, Any],
) -> bool:
    if (
        kind != "DaemonSet"
        or not name.endswith("-connectivity-host-agent")
        or metadata.get("labels", {}).get("app.kubernetes.io/component")
        != "connectivity-external-agent"
        or pod_spec.get("automountServiceAccountToken") is not False
        or pod_spec.get("dnsPolicy") != "ClusterFirstWithHostNet"
        or pod_spec.get("hostPID", False)
        or pod_spec.get("hostIPC", False)
    ):
        return False
    containers = pod_spec.get("containers", [])
    if not isinstance(containers, list) or len(containers) != 1:
        return False
    container = containers[0]
    security_context = container.get("securityContext", {})
    return (
        container.get("name") == "agent"
        and "--mode=connectivity-external-agent" in container.get("args", [])
        and security_context.get("privileged", False) is False
        and security_context.get("allowPrivilegeEscalation") is False
        and security_context.get("readOnlyRootFilesystem") is True
        and security_context.get("runAsNonRoot") is True
        and security_context.get("capabilities", {}).get("drop") == ["ALL"]
    )


def validate_network_security(documents: list[dict[str, Any]]) -> None:
    privileged_namespaces = {
        document.get("metadata", {}).get("name")
        for document in documents
        if document.get("kind") == "Namespace"
        and document.get("metadata", {})
        .get("labels", {})
        .get("pod-security.kubernetes.io/enforce")
        == "privileged"
    }
    for document in documents:
        kind = document.get("kind")
        if kind not in WORKLOAD_KINDS and kind != "CronJob":
            continue
        spec = document.get("spec", {})
        if kind == "CronJob":
            spec = spec.get("jobTemplate", {}).get("spec", {})
        pod_spec = spec.get("template", {}).get("spec", {})
        if not pod_spec.get("hostNetwork", False):
            continue
        name = str(document.get("metadata", {}).get("name", ""))
        metadata = document.get("metadata", {})
        namespace = metadata.get("namespace")
        coturn_allowed = (
            kind != "DaemonSet"
            or not name.endswith("-coturn")
            or namespace not in privileged_namespaces
        ) is False
        host_agent_allowed = _is_restricted_connectivity_host_agent(
            kind,
            name,
            metadata,
            pod_spec,
        )
        if not coturn_allowed and not host_agent_allowed:
            raise ValueError(
                f"unauthorized hostNetwork workload: {kind}/{namespace}/{name}"
            )


def _go_duration_milliseconds(value: Any) -> int:
    if not isinstance(value, str):
        raise ValueError("firewall attestor duration must be a string")
    match = GO_DURATION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid firewall attestor duration: {value}")
    multiplier = {"ms": 1, "s": 1000, "m": 60_000}[match.group("unit")]
    return int(match.group("value")) * multiplier


def validate_firewall_attestor(documents: list[dict[str, Any]]) -> None:
    daemonsets = [
        document
        for document in documents
        if document.get("kind") == "DaemonSet"
        and str(document.get("metadata", {}).get("name", "")).endswith(
            "-workspace-firewall-attestor"
        )
    ]
    if not daemonsets:
        return
    if len(daemonsets) != 1:
        raise ValueError("rendered manifests require exactly one firewall attestor")
    daemonset = daemonsets[0]
    pod_spec = daemonset.get("spec", {}).get("template", {}).get("spec", {})
    containers = [
        container
        for container in pod_spec.get("containers", [])
        if container.get("name") == "firewall-attestor"
    ]
    if len(containers) != 1:
        raise ValueError("firewall attestor container is missing")
    container = containers[0]
    args = container.get("args", [])
    argument_values = {
        argument.split("=", 1)[0]: argument.split("=", 1)[1]
        for argument in args
        if isinstance(argument, str) and "=" in argument
    }
    socket_path = argument_values.get("--cilium-socket-path")
    poll_interval = argument_values.get("--firewall-attestor-poll-interval")
    max_age = argument_values.get("--firewall-attestation-max-age")
    if not isinstance(socket_path, str) or not socket_path.endswith(".sock"):
        raise ValueError("firewall attestor Cilium socket path is invalid")
    if _go_duration_milliseconds(max_age) <= _go_duration_milliseconds(poll_interval):
        raise ValueError(
            "firewall attestation max age must exceed its polling interval"
        )
    mounts = [
        mount
        for mount in container.get("volumeMounts", [])
        if mount.get("name") == "cilium-run"
    ]
    volumes = [
        volume
        for volume in pod_spec.get("volumes", [])
        if volume.get("name") == "cilium-run"
    ]
    if (
        len(mounts) != 1
        or mounts[0].get("mountPath") != socket_path
        or mounts[0].get("readOnly") is not True
        or len(volumes) != 1
        or volumes[0].get("hostPath", {}).get("path") != socket_path
        or volumes[0].get("hostPath", {}).get("type") != "Socket"
    ):
        raise ValueError(
            "firewall attestor must mount only the Cilium socket read-only"
        )
    requests = container.get("resources", {}).get("requests")
    limits = container.get("resources", {}).get("limits")
    if not isinstance(requests, dict) or not isinstance(limits, dict):
        raise ValueError("firewall attestor resources require requests and limits")
    request_cpu, request_memory = _resource_request(container.get("resources"))
    if (
        request_cpu <= 0
        or request_memory <= 0
        or request_cpu > cpu_millicores(limits.get("cpu"))
        or request_memory > memory_bytes(limits.get("memory"))
    ):
        raise ValueError("firewall attestor resource requests are invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "named-images",
            "image-pull-secrets",
            "namespaces",
            "validate-privileged-namespace",
            "ingress-tls-secret",
            "build-image-pull-secret",
            "validate-image-pull-secret",
            "turn-enabled",
            "turn-provider",
            "turn-server-host",
            "validate-firewall-attestor",
            "validate-network-security",
            "validate-execution-plane-capacity",
            "assert-equivalent-manifests",
        ),
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("nodes", type=Path, nargs="?")
    parser.add_argument("pods", type=Path, nargs="?")
    parser.add_argument("--default-namespace")
    parser.add_argument(
        "--deployment-mode",
        choices=("clean-install", "upgrade"),
    )
    parser.add_argument("--namespace")
    parser.add_argument("--name")
    parser.add_argument("--registry")
    parser.add_argument("--target-namespace")
    parser.add_argument("--owner-marker")
    parser.add_argument("--host")
    parser.add_argument(
        "--document-class",
        choices=("all", "release", "hooks"),
        default="all",
    )
    parser.add_argument(
        "--identity-mode",
        choices=("bundledKeycloak", "externalOidc"),
    )
    parser.add_argument(
        "--additional-manifest",
        action="append",
        type=Path,
        default=[],
    )
    arguments = parser.parse_args()
    documents = load_documents(arguments.manifest)
    for additional_manifest in arguments.additional_manifest:
        documents.extend(load_documents(additional_manifest))

    try:
        if arguments.action == "named-images":
            if arguments.identity_mode is None:
                raise ValueError("named-images requires --identity-mode")
            validate_identity_manifest_selection(
                identity_mode=arguments.identity_mode,
                additional_manifest_count=len(arguments.additional_manifest),
            )
            for component, image in named_workload_image_inventory(
                documents,
                identity_mode=arguments.identity_mode,
            ).items():
                print(f"{component}\t{image}")
        elif arguments.action == "image-pull-secrets":
            if arguments.default_namespace is None:
                raise ValueError("image-pull-secrets requires --default-namespace")
            for namespace, secret_name in image_pull_secret_inventory(
                documents,
                arguments.default_namespace,
            ):
                print(f"{namespace}\t{secret_name}")
        elif arguments.action == "namespaces":
            print(
                json.dumps(
                    namespace_inventory(documents),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
        elif arguments.action == "ingress-tls-secret":
            if arguments.default_namespace is None or arguments.host is None:
                raise ValueError(
                    "ingress-tls-secret requires --default-namespace and --host"
                )
            tls_namespace, tls_secret_name = ingress_tls_secret_for_host(
                documents,
                default_namespace=arguments.default_namespace,
                host=arguments.host,
            )
            print(f"{tls_namespace}\t{tls_secret_name}")
        elif arguments.action == "validate-privileged-namespace":
            if arguments.namespace is None or arguments.owner_marker is None:
                raise ValueError(
                    "validate-privileged-namespace requires --namespace and "
                    "--owner-marker"
                )
            validate_privileged_namespace_evidence(
                documents,
                namespace=arguments.namespace,
                owner_marker=arguments.owner_marker,
            )
            print("passed")
        elif arguments.action == "build-image-pull-secret":
            if (
                arguments.namespace is None
                or arguments.target_namespace is None
                or arguments.name is None
                or arguments.registry is None
                or arguments.owner_marker is None
            ):
                raise ValueError(
                    "build-image-pull-secret requires --namespace, "
                    "--target-namespace, --name, --registry, and --owner-marker"
                )
            if len(documents) != 1:
                raise ValueError(
                    "build-image-pull-secret requires exactly one source Secret"
                )
            print(
                json.dumps(
                    reconciled_image_pull_secret(
                        documents[0],
                        source_namespace=arguments.namespace,
                        target_namespace=arguments.target_namespace,
                        name=arguments.name,
                        registry=arguments.registry,
                        owner_marker=arguments.owner_marker,
                    ),
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
        elif arguments.action == "validate-image-pull-secret":
            if (
                arguments.namespace is None
                or arguments.name is None
                or arguments.registry is None
            ):
                raise ValueError(
                    "validate-image-pull-secret requires --namespace, --name, "
                    "and --registry"
                )
            if len(documents) != 1:
                raise ValueError(
                    "validate-image-pull-secret requires exactly one Secret"
                )
            has_registry_auth = image_pull_secret_has_registry_auth(
                documents[0],
                namespace=arguments.namespace,
                name=arguments.name,
                registry=arguments.registry,
            )
            print("true" if has_registry_auth else "false")
        elif arguments.action == "turn-enabled":
            print("true" if turn_enabled(documents) else "false")
        elif arguments.action == "turn-provider":
            print(turn_provider(documents))
        elif arguments.action == "turn-server-host":
            print(turn_server_host(documents))
        elif arguments.action == "validate-execution-plane-capacity":
            if (
                arguments.nodes is None
                or arguments.pods is None
                or arguments.default_namespace is None
                or arguments.deployment_mode is None
            ):
                raise ValueError(
                    "validate-execution-plane-capacity requires nodes and pods JSON "
                    "and --default-namespace and --deployment-mode"
                )
            print(
                validate_execution_plane_capacity(
                    documents,
                    load_json_document(arguments.nodes),
                    load_json_document(arguments.pods),
                    default_namespace=arguments.default_namespace,
                    deployment_mode=arguments.deployment_mode,
                )
            )
        elif arguments.action == "assert-equivalent-manifests":
            if arguments.nodes is None:
                raise ValueError(
                    "assert-equivalent-manifests requires the live manifest"
                )
            assert_equivalent_manifests(
                arguments.manifest,
                arguments.nodes,
                document_class=arguments.document_class,
            )
            print("passed")
        elif arguments.action == "validate-firewall-attestor":
            validate_firewall_attestor(documents)
            print("passed")
        else:
            validate_network_security(documents)
            print("passed")
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
