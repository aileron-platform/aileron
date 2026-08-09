#!/usr/bin/env python3
"""Validate the repository Platform Configuration Contract."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit

import jsonschema
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIRECTORY = REPOSITORY_ROOT / "contracts/platform-configuration"
SCHEMA_PATH = CONTRACT_DIRECTORY / "schema.json"
CONTRACT_PATH = CONTRACT_DIRECTORY / "contract.json"
VECTORS_SCHEMA_PATH = CONTRACT_DIRECTORY / "conformance-vectors.schema.json"
VECTORS_PATH = CONTRACT_DIRECTORY / "conformance-vectors.json"
ENV_EXAMPLE_PATH = REPOSITORY_ROOT / ".env.example"
ROOT_COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.yml"
HELM_VALUES_PATH = REPOSITORY_ROOT / "helm/aileron/values.yaml"

ORIGIN_DIAGNOSTIC = (
    "platformPublicOrigin: must be an exact origin without path, query, "
    "fragment, credentials, or trailing slash"
)
FORBIDDEN_ALIASES = {
    "ALLOWED_ORIGINS",
    "FRONTEND_ORIGIN",
    "FRONTEND_PUBLIC_URL",
    "OIDC_DISCOVERY_URL",
    "OIDC_POST_LOGOUT_REDIRECT_URI",
    "OIDC_REDIRECT_URI",
    "PUBLIC_FRONTEND_HOST",
    "PUBLIC_FRONTEND_URL",
    "PUBLIC_WORKSPACE_MANAGER_URL",
    "VITE_API_BASE_URL",
    "VITE_FRONTEND_PUBLIC_URL",
}
SECRET_NAME_PATTERN = re.compile(
    r"(?:^|_)(?:API_KEY|CREDENTIAL|PASSWORD|PRIVATE_KEY|SECRET|TOKEN)(?:_|$)"
)
INTERPOLATION_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)[^}]*\}")
TEMPLATE_INPUT_PATTERN = re.compile(r"\{([a-z][A-Za-z0-9]*)\}")
PROCESS_OPTION_PATTERN = re.compile(r"--([A-Za-z][A-Za-z0-9_-]*)=")
PROCESS_ASSIGNMENT_PATTERN = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9_]*)=")
PARITY_SAMPLE_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    documents = yaml.safe_load_all(path.read_text(encoding="utf-8"))
    return [document for document in documents if isinstance(document, dict)]


def merge_mappings(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_mappings(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def mapping_value(document: Any, mapping_path: str) -> Any:
    current = document
    for segment in mapping_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(mapping_path)
        current = current[segment]
    return current


def validate_platform_public_origin(value: object) -> list[str]:
    if not isinstance(value, str):
        return [ORIGIN_DIAGNOSTIC]
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        return [ORIGIN_DIAGNOSTIC]
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or (port is not None and not 1 <= port <= 65535)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return [ORIGIN_DIAGNOSTIC]
    return []


def format_schema_error(prefix: str, error: jsonschema.ValidationError) -> str:
    location = ".".join(str(item) for item in error.absolute_path)
    suffix = f" at {location}" if location else ""
    return f"{prefix}: {error.message}{suffix}"


def validate_json_schema(document: Any, schema: Any, prefix: str) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    return [format_schema_error(prefix, error) for error in errors]


def validate_schema_definition(schema: Any, prefix: str) -> list[str]:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as error:
        return [format_schema_error(prefix, error)]
    return []


def validate_contract_data(contract: dict[str, Any]) -> list[str]:
    diagnostics = validate_json_schema(contract, load_json(SCHEMA_PATH), "contract schema")
    if diagnostics:
        return diagnostics

    seen_logical_names: set[str] = set()
    seen_compose_inputs: set[str] = set()
    seen_helm_values_paths: set[str] = set()
    known_inputs: set[str] = set()
    for item in contract["installationInputs"]:
        logical_name = item["logicalName"]
        compose_input = item["mapping"]["composeInput"]
        if logical_name in seen_logical_names:
            diagnostics.append(f"duplicate installation owner: {logical_name}")
        if compose_input in seen_compose_inputs:
            diagnostics.append(f"duplicate Compose input owner: {compose_input}")
        seen_logical_names.add(logical_name)
        seen_compose_inputs.add(compose_input)
        known_inputs.add(compose_input)
        helm_values_path = item["mapping"].get("helmValuesPath")
        if helm_values_path is not None:
            if helm_values_path in seen_helm_values_paths:
                diagnostics.append(f"duplicate Helm values owner: {helm_values_path}")
            seen_helm_values_paths.add(helm_values_path)

    seen_secret_logical_names: set[str] = set()
    seen_secret_mappings: set[tuple[str, str]] = set()
    for item in contract["helmSecretReferences"]:
        logical_name = item["logicalName"]
        mapping = item["mapping"]
        mapping_key = (
            mapping["secretNameValuesPath"],
            mapping["secretKeyValuesPath"],
        )
        if logical_name in seen_secret_logical_names or logical_name in seen_logical_names:
            diagnostics.append(f"duplicate installation owner: {logical_name}")
        if mapping_key in seen_secret_mappings:
            diagnostics.append(
                "duplicate Helm Secret reference owner: "
                f"{mapping_key[0]} + {mapping_key[1]}"
            )
        seen_secret_logical_names.add(logical_name)
        seen_secret_mappings.add(mapping_key)

    seen_derived_logical_names: set[str] = set()
    for item in contract["derivedLogicalOutputs"]:
        logical_name = item["logicalName"]
        if logical_name in seen_derived_logical_names:
            diagnostics.append(f"duplicate derived logical output: {logical_name}")
        seen_derived_logical_names.add(logical_name)
        expected_inputs = set(item["inputs"])
        for adapter in ("compose", "helm"):
            template = item["mapping"][f"{adapter}Template"]
            actual_inputs = set(TEMPLATE_INPUT_PATTERN.findall(template))
            if actual_inputs != expected_inputs:
                diagnostics.append(
                    f"invalid {adapter} derived inputs: {logical_name}"
                )

    seen_outputs: set[tuple[str, str]] = set()
    expected_disposition = {
        "input": "keep-input",
        "derived": "keep-derived-output",
        "fixed": "keep-derived-output",
        "secret-reference": "replace-with-secret-reference",
        "third-party-adapter": "keep-derived-output",
    }
    for item in contract["composeOutputs"]:
        key = (item["service"], item["name"])
        if key in seen_outputs:
            diagnostics.append(f"duplicate Compose output owner: {key[0]}.{key[1]}")
        seen_outputs.add(key)

        source_input = item.get("sourceInput")
        if source_input is not None and source_input not in known_inputs:
            diagnostics.append(
                f"unknown Compose source input: {key[0]}.{key[1]} -> {source_input}"
            )
        expected = expected_disposition[item["sourceKind"]]
        if item["disposition"] != expected:
            diagnostics.append(
                f"invalid disposition: {key[0]}.{key[1]} must use {expected}"
            )

    helm_adapter = contract["helmAdapter"]
    chart_path = REPOSITORY_ROOT / helm_adapter["chartPath"]
    if not chart_path.is_dir():
        diagnostics.append(f"missing Helm chart path: {helm_adapter['chartPath']}")
    for values_path in helm_adapter["valuesFiles"]:
        if not (REPOSITORY_ROOT / values_path).is_file():
            diagnostics.append(f"missing Helm values file: {values_path}")

    seen_deployments: set[tuple[str, str]] = set()
    classified_environment: set[tuple[str, str, str]] = set()
    for deployment in helm_adapter["deployments"]:
        deployment_key = (deployment["nameSuffix"], deployment["container"])
        if deployment_key in seen_deployments:
            diagnostics.append(
                "duplicate Helm Deployment owner: "
                f"{deployment_key[0]}.{deployment_key[1]}"
            )
        seen_deployments.add(deployment_key)
        environment = deployment["environment"]
        for source_kind in ("configMap", "literal", "secretFile"):
            for name in environment[source_kind]:
                key = (*deployment_key, name)
                if key in classified_environment:
                    diagnostics.append(
                        "duplicate Helm environment classification: "
                        f"{deployment_key[0]}.{deployment_key[1]}.{name}"
                    )
                classified_environment.add(key)
        for field_reference in environment["fieldRef"]:
            name = field_reference["name"]
            key = (*deployment_key, name)
            if key in classified_environment:
                diagnostics.append(
                    "duplicate Helm environment classification: "
                    f"{deployment_key[0]}.{deployment_key[1]}.{name}"
                )
            classified_environment.add(key)

    secret_logical_names = {
        item["logicalName"] for item in contract["helmSecretReferences"]
    }
    seen_secret_files: set[tuple[str, str, str]] = set()
    for secret_file in helm_adapter["secretFiles"]:
        deployment_key = (
            secret_file["deploymentSuffix"],
            secret_file["container"],
        )
        environment_key = (*deployment_key, secret_file["environmentName"])
        secret_file_key = (*deployment_key, secret_file["path"])
        if deployment_key not in seen_deployments:
            diagnostics.append(
                "unknown Helm Secret file Deployment: "
                f"{deployment_key[0]}.{deployment_key[1]}"
            )
        if environment_key not in classified_environment:
            diagnostics.append(
                "unknown Helm Secret file environment: "
                f"{deployment_key[0]}.{deployment_key[1]}."
                f"{secret_file['environmentName']}"
            )
        if secret_file["logicalName"] not in secret_logical_names:
            diagnostics.append(
                "unknown Helm Secret logical name: "
                f"{secret_file['logicalName']}"
            )
        if secret_file_key in seen_secret_files:
            diagnostics.append(
                "duplicate Helm Secret file classification: "
                f"{deployment_key[0]}.{deployment_key[1]}.{secret_file['path']}"
            )
        seen_secret_files.add(secret_file_key)

    seen_fixture_outputs: set[tuple[str, str, str]] = set()
    for item in contract["testFixtureOutputs"]:
        key = (item["path"], item["service"], item["name"])
        if not (REPOSITORY_ROOT / item["path"]).is_file():
            diagnostics.append(f"missing test fixture path: {item['path']}")
        if key in seen_fixture_outputs:
            diagnostics.append(
                f"duplicate test fixture output owner: {key[0]}:{key[1]}.{key[2]}"
            )
        seen_fixture_outputs.add(key)
    return diagnostics


def has_mapping_path(document: Any, mapping_path: str) -> bool:
    current = document
    for segment in mapping_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def validate_helm_mappings(contract: dict[str, Any]) -> list[str]:
    values = load_yaml(HELM_VALUES_PATH)
    diagnostics: list[str] = []
    for item in contract["installationInputs"]:
        mapping_path = item["mapping"].get("helmValuesPath")
        if mapping_path is not None and not has_mapping_path(values, mapping_path):
            diagnostics.append(
                f"unknown Helm values mapping: {item['logicalName']} -> {mapping_path}"
            )
    for item in contract["helmSecretReferences"]:
        for mapping_name in ("secretNameValuesPath", "secretKeyValuesPath"):
            mapping_path = item["mapping"][mapping_name]
            if not has_mapping_path(values, mapping_path):
                diagnostics.append(
                    "unknown Helm Secret values mapping: "
                    f"{item['logicalName']} -> {mapping_path}"
                )
    return diagnostics


def helm_effective_values(contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    adapter = contract["helmAdapter"]
    diagnostics: list[str] = []
    try:
        values = load_yaml(HELM_VALUES_PATH)
    except (OSError, yaml.YAMLError) as error:
        return {}, [f"invalid Helm default values: {error}"]
    if not isinstance(values, dict):
        return {}, ["Helm default values must be a mapping"]
    for relative_path in adapter["valuesFiles"]:
        path = REPOSITORY_ROOT / relative_path
        try:
            override = load_yaml(path)
        except (OSError, yaml.YAMLError) as error:
            diagnostics.append(f"invalid Helm values file: {relative_path}: {error}")
            continue
        if not isinstance(override, dict):
            diagnostics.append(f"Helm values file must be a mapping: {relative_path}")
            continue
        values = merge_mappings(values, override)
    return values, diagnostics


def render_helm_adapter(
    contract: dict[str, Any],
    chart_path: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    adapter = contract["helmAdapter"]
    values, diagnostics = helm_effective_values(contract)
    if diagnostics:
        return [], values, diagnostics
    command = [
        "helm",
        "template",
        adapter["releaseName"],
        str(chart_path or REPOSITORY_ROOT / adapter["chartPath"]),
        "--namespace",
        adapter["namespace"],
    ]
    for values_path in adapter["valuesFiles"]:
        command.extend(["--values", str(REPOSITORY_ROOT / values_path)])
    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return [], values, [f"Helm template unavailable: {error}"]
    if result.returncode != 0:
        message = result.stderr.strip().splitlines()
        detail = message[-1] if message else f"exit code {result.returncode}"
        return [], values, [f"Helm template invalid: {detail}"]
    try:
        documents = [
            document
            for document in yaml.safe_load_all(result.stdout)
            if isinstance(document, dict)
        ]
    except yaml.YAMLError as error:
        return [], values, [f"Helm template returned invalid YAML: {error}"]
    return documents, values, []


def find_rendered_document(
    documents: list[dict[str, Any]], kind: str, name_suffix: str
) -> tuple[dict[str, Any] | None, list[str]]:
    matches = [
        document
        for document in documents
        if document.get("kind") == kind
        and str(document.get("metadata", {}).get("name", "")).endswith(name_suffix)
    ]
    if len(matches) == 1:
        return matches[0], []
    return None, [
        f"Helm render must contain exactly one {kind} ending {name_suffix}; "
        f"found {len(matches)}"
    ]


def rendered_pod_specs(
    documents: list[dict[str, Any]],
) -> Iterable[tuple[str, dict[str, Any]]]:
    for document in documents:
        kind = document.get("kind")
        specification = document.get("spec", {})
        if kind in {"Deployment", "DaemonSet", "StatefulSet", "Job"}:
            pod_spec = specification.get("template", {}).get("spec")
        elif kind == "CronJob":
            pod_spec = (
                specification.get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec")
            )
        else:
            continue
        if isinstance(pod_spec, dict):
            name = str(document.get("metadata", {}).get("name", "<unknown>"))
            yield f"{kind}/{name}", pod_spec


def validate_no_secret_environment(
    documents: list[dict[str, Any]],
) -> list[str]:
    diagnostics: list[str] = []
    for workload, pod_spec in rendered_pod_specs(documents):
        containers = list(pod_spec.get("initContainers", [])) + list(
            pod_spec.get("containers", [])
        )
        for container in containers:
            container_name = container.get("name", "<unknown>")
            for source in container.get("envFrom", []):
                if "secretRef" in source:
                    diagnostics.append(
                        "Helm plaintext Secret environment source: "
                        f"{workload}.{container_name}.envFrom.secretRef"
                    )
            for environment in container.get("env", []):
                if "secretKeyRef" in environment.get("valueFrom", {}):
                    diagnostics.append(
                        "Helm plaintext Secret environment source: "
                        f"{workload}.{container_name}.{environment.get('name', '<unknown>')}"
                    )
    return diagnostics


def validate_no_secret_process_arguments(
    documents: list[dict[str, Any]],
) -> list[str]:
    diagnostics: list[str] = []
    for workload, pod_spec in rendered_pod_specs(documents):
        containers = list(pod_spec.get("initContainers", [])) + list(
            pod_spec.get("containers", [])
        )
        for container in containers:
            container_name = str(container.get("name", "<unknown>"))
            diagnostics.extend(
                lint_process_arguments(
                    f"{workload}.{container_name}",
                    container,
                )
            )
    return diagnostics


def container_environment(
    container: dict[str, Any], deployment_suffix: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    environment: dict[str, dict[str, Any]] = {}
    diagnostics: list[str] = []
    for entry in container.get("env", []):
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            diagnostics.append(f"invalid Helm environment entry: {deployment_suffix}")
            continue
        if name in environment:
            diagnostics.append(
                f"duplicate Helm environment: {deployment_suffix}.{name}"
            )
        environment[name] = entry
    return environment, diagnostics


def validate_helm_environment(
    deployment_suffix: str,
    container: dict[str, Any],
    expected: dict[str, Any],
    platform_config_map_name: str,
    platform_config_map_keys: set[str],
) -> list[str]:
    actual, diagnostics = container_environment(container, deployment_suffix)
    expected_field_refs = {
        item["name"]: item["fieldPath"] for item in expected["fieldRef"]
    }
    expected_names = (
        set(expected["configMap"])
        | set(expected["literal"])
        | set(expected["secretFile"])
        | set(expected_field_refs)
    )
    for name in sorted(actual.keys() - expected_names):
        diagnostics.append(
            "unknown Helm output: Deployment."
            f"{deployment_suffix.removeprefix('-')}.{container.get('name', '<unknown>')}."
            f"environment.{name}"
        )
    for name in sorted(expected_names - actual.keys()):
        diagnostics.append(
            "missing classified Helm output: Deployment."
            f"{deployment_suffix.removeprefix('-')}.{container.get('name', '<unknown>')}."
            f"environment.{name}"
        )

    for name in sorted(set(expected["configMap"]) & actual.keys()):
        reference = actual[name].get("valueFrom", {}).get("configMapKeyRef")
        if not isinstance(reference, dict):
            diagnostics.append(
                f"invalid Helm environment source kind: {deployment_suffix}.{name} "
                "must use configMapKeyRef"
            )
            continue
        if reference.get("name") != platform_config_map_name:
            diagnostics.append(
                f"invalid Helm ConfigMap source: {deployment_suffix}.{name}"
            )
        if reference.get("key") != name or name not in platform_config_map_keys:
            diagnostics.append(
                f"invalid Helm ConfigMap key: {deployment_suffix}.{name}"
            )

    for name in sorted(set(expected["literal"]) & actual.keys()):
        entry = actual[name]
        if "value" not in entry or "valueFrom" in entry:
            diagnostics.append(
                f"invalid Helm environment source kind: {deployment_suffix}.{name} "
                "must use literal value"
            )

    for name in sorted(set(expected["secretFile"]) & actual.keys()):
        entry = actual[name]
        if "value" not in entry or "valueFrom" in entry:
            diagnostics.append(
                f"invalid Helm environment source kind: {deployment_suffix}.{name} "
                "must use a Secret file path"
            )
        elif not isinstance(entry["value"], str) or not entry["value"].startswith("/"):
            diagnostics.append(
                f"invalid Helm Secret file reference: {deployment_suffix}.{name}"
            )

    for name, field_path in sorted(expected_field_refs.items()):
        if name not in actual:
            continue
        reference = actual[name].get("valueFrom", {}).get("fieldRef")
        if not isinstance(reference, dict) or reference.get("fieldPath") != field_path:
            diagnostics.append(
                f"invalid Helm fieldRef source: {deployment_suffix}.{name}"
            )
    return diagnostics


def secret_volume_files(
    deployment_suffix: str,
    container: dict[str, Any],
    pod_spec: dict[str, Any],
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    diagnostics: list[str] = []
    files: dict[str, tuple[str, str]] = {}
    volumes = {
        volume.get("name"): volume
        for volume in pod_spec.get("volumes", [])
        if isinstance(volume, dict)
    }
    for mount in container.get("volumeMounts", []):
        volume = volumes.get(mount.get("name"), {})
        secret_sources: list[dict[str, Any]] = []
        if isinstance(volume.get("secret"), dict):
            secret_sources.append(volume["secret"])
        projected = volume.get("projected")
        if isinstance(projected, dict):
            secret_sources.extend(
                source["secret"]
                for source in projected.get("sources", [])
                if isinstance(source, dict) and isinstance(source.get("secret"), dict)
            )
        if not secret_sources:
            continue
        if mount.get("readOnly") is not True:
            diagnostics.append(
                f"Helm Secret volume must be read-only: {deployment_suffix}."
                f"{container.get('name', '<unknown>')}.{mount.get('name', '<unknown>')}"
            )
        for source in secret_sources:
            secret_name = source.get("secretName", source.get("name"))
            items = source.get("items")
            if not isinstance(secret_name, str) or not isinstance(items, list) or not items:
                diagnostics.append(
                    f"unclassified whole Helm Secret volume: {deployment_suffix}."
                    f"{container.get('name', '<unknown>')}.{mount.get('name', '<unknown>')}"
                )
                continue
            for item in items:
                key = item.get("key")
                relative_path = item.get("path")
                if not isinstance(key, str) or not isinstance(relative_path, str):
                    diagnostics.append(
                        f"invalid Helm Secret volume item: {deployment_suffix}."
                        f"{container.get('name', '<unknown>')}"
                    )
                    continue
                if mount.get("subPath"):
                    path = str(PurePosixPath(str(mount.get("mountPath", ""))))
                else:
                    path = str(
                        PurePosixPath(str(mount.get("mountPath", "")))
                        / relative_path
                    )
                if path in files:
                    diagnostics.append(
                        f"duplicate Helm Secret file: {deployment_suffix}."
                        f"{container.get('name', '<unknown>')}.{path}"
                    )
                files[path] = (secret_name, key)
    return files, diagnostics


def resolve_environment_value(
    entry: dict[str, Any], config_maps: dict[str, dict[str, Any]]
) -> str | None:
    if isinstance(entry.get("value"), str):
        return entry["value"]
    reference = entry.get("valueFrom", {}).get("configMapKeyRef")
    if not isinstance(reference, dict):
        return None
    data = config_maps.get(str(reference.get("name")), {})
    value = data.get(reference.get("key"))
    return value if isinstance(value, str) else None


def validate_helm_rendered_documents(
    documents: list[dict[str, Any]],
    contract: dict[str, Any],
    effective_values: dict[str, Any],
) -> list[str]:
    adapter = contract["helmAdapter"]
    diagnostics = validate_no_secret_environment(documents)
    diagnostics.extend(validate_no_secret_process_arguments(documents))
    for document in documents:
        if document.get("kind") == "Secret":
            name = document.get("metadata", {}).get("name", "<unknown>")
            diagnostics.append(f"Helm adapter must not render Secret: {name}")

    config_map_contract = adapter["platformConfigMap"]
    platform_config_map, config_map_diagnostics = find_rendered_document(
        documents, "ConfigMap", config_map_contract["nameSuffix"]
    )
    diagnostics.extend(config_map_diagnostics)
    if platform_config_map is None:
        return diagnostics
    platform_config_map_name = str(platform_config_map["metadata"]["name"])
    platform_config_map_data = platform_config_map.get("data", {})
    if not isinstance(platform_config_map_data, dict):
        diagnostics.append("Helm platform ConfigMap data must be a mapping")
        return diagnostics
    actual_config_map_keys = set(platform_config_map_data)
    expected_config_map_keys = set(config_map_contract["keys"])
    for key in sorted(actual_config_map_keys - expected_config_map_keys):
        diagnostics.append(f"unknown Helm platform ConfigMap output: {key}")
    for key in sorted(expected_config_map_keys - actual_config_map_keys):
        diagnostics.append(f"missing Helm platform ConfigMap output: {key}")

    config_maps = {
        str(document.get("metadata", {}).get("name")): document.get("data", {})
        for document in documents
        if document.get("kind") == "ConfigMap"
        and isinstance(document.get("data", {}), dict)
    }
    rendered_deployments: dict[
        tuple[str, str], tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = {}
    for deployment_contract in adapter["deployments"]:
        suffix = deployment_contract["nameSuffix"]
        deployment, deployment_diagnostics = find_rendered_document(
            documents, "Deployment", suffix
        )
        diagnostics.extend(deployment_diagnostics)
        if deployment is None:
            continue
        pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
        containers = [
            container
            for container in pod_spec.get("containers", [])
            if container.get("name") == deployment_contract["container"]
        ]
        if len(containers) != 1:
            diagnostics.append(
                f"Helm render must contain exactly one container "
                f"{suffix}.{deployment_contract['container']}; found {len(containers)}"
            )
            continue
        container = containers[0]
        diagnostics.extend(
            validate_helm_environment(
                suffix,
                container,
                deployment_contract["environment"],
                platform_config_map_name,
                actual_config_map_keys,
            )
        )
        rendered_deployments[(suffix, deployment_contract["container"])] = (
            deployment,
            pod_spec,
            container,
        )

    secret_references = {
        item["logicalName"]: item for item in contract["helmSecretReferences"]
    }
    expected_secret_files = {
        (item["deploymentSuffix"], item["container"], item["path"]): item
        for item in adapter["secretFiles"]
    }
    actual_secret_files: dict[tuple[str, str, str], tuple[str, str]] = {}
    for (suffix, container_name), (_, pod_spec, container) in rendered_deployments.items():
        files, file_diagnostics = secret_volume_files(suffix, container, pod_spec)
        diagnostics.extend(file_diagnostics)
        for path, source in files.items():
            actual_secret_files[(suffix, container_name, path)] = source

    for key in sorted(actual_secret_files.keys() - expected_secret_files.keys()):
        diagnostics.append(
            f"unknown Helm Secret file output: {key[0]}.{key[1]}.{key[2]}"
        )
    for key in sorted(expected_secret_files.keys() - actual_secret_files.keys()):
        diagnostics.append(
            f"missing classified Helm Secret file output: {key[0]}.{key[1]}.{key[2]}"
        )

    for key in sorted(actual_secret_files.keys() & expected_secret_files.keys()):
        expected = expected_secret_files[key]
        deployment = rendered_deployments.get((key[0], key[1]))
        if deployment is None:
            continue
        environment, environment_diagnostics = container_environment(
            deployment[2], key[0]
        )
        diagnostics.extend(environment_diagnostics)
        entry = environment.get(expected["environmentName"])
        resolved_path = (
            resolve_environment_value(entry, config_maps)
            if isinstance(entry, dict)
            else None
        )
        if resolved_path != expected["path"]:
            diagnostics.append(
                f"invalid Helm Secret file environment path: {key[0]}."
                f"{key[1]}.{expected['environmentName']}"
            )
        reference = secret_references[expected["logicalName"]]["mapping"]
        try:
            expected_source = (
                str(mapping_value(effective_values, reference["secretNameValuesPath"])),
                str(mapping_value(effective_values, reference["secretKeyValuesPath"])),
            )
        except KeyError as error:
            diagnostics.append(f"missing effective Helm Secret value: {error.args[0]}")
            continue
        if actual_secret_files[key] != expected_source:
            diagnostics.append(
                f"invalid Helm Secret source: {key[0]}.{key[1]}.{key[2]}"
            )
    return diagnostics


def validate_helm_adapter(
    contract: dict[str, Any], chart_path: Path | None = None
) -> list[str]:
    documents, effective_values, diagnostics = render_helm_adapter(contract, chart_path)
    if diagnostics:
        return diagnostics
    return validate_helm_rendered_documents(documents, contract, effective_values)


def derive_adapter_outputs(
    contract: dict[str, Any],
    adapter: str,
    logical_inputs: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    outputs: dict[str, str] = {}
    diagnostics: list[str] = []
    for item in contract["derivedLogicalOutputs"]:
        missing_inputs = sorted(set(item["inputs"]) - logical_inputs.keys())
        if missing_inputs:
            diagnostics.append(
                f"missing derived logical input: {item['logicalName']} -> "
                + ", ".join(missing_inputs)
            )
            continue
        template = item["mapping"][f"{adapter}Template"]
        outputs[item["logicalName"]] = template.format_map(logical_inputs)
    return outputs, diagnostics


def normalize_adapter_parity(
    contract: dict[str, Any],
    platform_public_origin: str,
    workspace_id: str,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    diagnostics = validate_platform_public_origin(platform_public_origin)
    logical_inputs = {
        "platformPublicOrigin": platform_public_origin,
        "workspaceId": workspace_id,
    }
    compose, compose_diagnostics = derive_adapter_outputs(
        contract, "compose", logical_inputs
    )
    helm, helm_diagnostics = derive_adapter_outputs(contract, "helm", logical_inputs)
    diagnostics.extend(compose_diagnostics)
    diagnostics.extend(helm_diagnostics)
    for logical_name in sorted(compose.keys() | helm.keys()):
        if compose.get(logical_name) != helm.get(logical_name):
            diagnostics.append(f"adapter parity mismatch: {logical_name}")
    return {"compose": compose, "helm": helm}, diagnostics


def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    diagnostics: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            diagnostics.append(f"invalid .env entry at {path}:{line_number}")
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            diagnostics.append(f"invalid .env name at {path}:{line_number}: {name}")
            continue
        if name in values:
            diagnostics.append(f"duplicate .env input: {name}")
        values[name] = value
    return values, diagnostics


def validate_env_inputs(path: Path, contract: dict[str, Any]) -> list[str]:
    values, diagnostics = parse_env_file(path)
    inputs = {
        item["mapping"]["composeInput"]: item for item in contract["installationInputs"]
    }
    for name in sorted(values.keys() - inputs.keys()):
        diagnostics.append(f"unknown or derived .env input: {name}")
    for name, item in sorted(inputs.items()):
        if item["required"] and name not in values:
            diagnostics.append(f"missing required .env input: {name}")
    return diagnostics


def normalize_environment(service: str, raw_environment: Any) -> tuple[dict[str, Any], list[str]]:
    diagnostics: list[str] = []
    if raw_environment is None:
        return {}, diagnostics
    if isinstance(raw_environment, dict):
        return raw_environment, diagnostics
    if not isinstance(raw_environment, list):
        return {}, [f"invalid Compose environment: {service}"]

    environment: dict[str, Any] = {}
    for entry in raw_environment:
        if not isinstance(entry, str):
            diagnostics.append(f"invalid Compose environment entry: {service}")
            continue
        if "=" in entry:
            name, value = entry.split("=", 1)
        else:
            name, value = entry, None
        if name in environment:
            diagnostics.append(f"duplicate Compose environment: {service}.{name}")
        environment[name] = value
    return environment, diagnostics


def is_secret_name(name: str) -> bool:
    if name.endswith("_REVISION") or "TOKEN_LIFETIME" in name:
        return False
    return bool(SECRET_NAME_PATTERN.search(name))


def is_file_reference_name(name: str) -> bool:
    return name == "PGPASSFILE" or name.endswith("_FILE")


def normalize_process_argument_name(name: str) -> str:
    return name.upper().replace("-", "_")


def process_argument_scalars(configuration: dict[str, Any]) -> Iterable[str]:
    for field in ("command", "args"):
        value = configuration.get(field)
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield item


def lint_process_arguments(owner: str, configuration: dict[str, Any]) -> list[str]:
    diagnostics: list[str] = []
    names: set[str] = set()
    for scalar in process_argument_scalars(configuration):
        names.update(
            normalize_process_argument_name(match.group(1))
            for match in PROCESS_OPTION_PATTERN.finditer(scalar)
        )
        names.update(
            normalize_process_argument_name(match.group(1))
            for match in PROCESS_ASSIGNMENT_PATTERN.finditer(scalar)
        )
        names.update(interpolation_names(scalar))
    for name in sorted(names):
        if is_secret_name(name) and not is_file_reference_name(name):
            diagnostics.append(f"plaintext Secret process argument: {owner}.{name}")
    return diagnostics


def interpolation_names(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return set(INTERPOLATION_PATTERN.findall(value))


def lint_environment(
    service: str,
    environment: dict[str, Any],
    allowed_plaintext_secrets: set[tuple[str, str]],
) -> list[str]:
    diagnostics: list[str] = []
    for name, value in environment.items():
        if name in FORBIDDEN_ALIASES:
            diagnostics.append(f"forbidden alias: {name}")
        if value is None and is_secret_name(name):
            diagnostics.append(f"host secret pass-through: {name}")
            continue

        sources = interpolation_names(value)
        if is_secret_name(name) and name in sources:
            diagnostics.append(f"host secret pass-through: {name}")
            continue
        if (
            is_secret_name(name)
            and not is_file_reference_name(name)
            and (service, name) not in allowed_plaintext_secrets
        ):
            diagnostics.append(f"plaintext secret environment: {name}")
        if is_file_reference_name(name) and (not isinstance(value, str) or not value.strip()):
            diagnostics.append(f"empty secret file reference: {service}.{name}")
    return diagnostics


def compose_services(document: Any, path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        return {}, [f"Compose document must define services: {path}"]
    return document["services"], []


def lint_compose_file(
    path: Path,
    allowed_plaintext_secrets: set[tuple[str, str]] | None = None,
) -> list[str]:
    try:
        document = load_yaml(path)
    except (OSError, yaml.YAMLError) as error:
        return [f"invalid Compose YAML: {path}: {error}"]
    services, diagnostics = compose_services(document, path)
    for service, configuration in services.items():
        if not isinstance(configuration, dict):
            diagnostics.append(f"invalid Compose service: {path}:{service}")
            continue
        environment, environment_diagnostics = normalize_environment(
            service, configuration.get("environment")
        )
        diagnostics.extend(environment_diagnostics)
        diagnostics.extend(
            lint_environment(service, environment, allowed_plaintext_secrets or set())
        )
        diagnostics.extend(lint_process_arguments(service, configuration))
    relative_path = path.relative_to(REPOSITORY_ROOT)
    return [f"{relative_path}: {diagnostic}" for diagnostic in diagnostics]


def walk_scalars(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_scalars(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_scalars(item)
    elif isinstance(value, str):
        yield value


def validate_root_compose(path: Path, contract: dict[str, Any]) -> list[str]:
    document = load_yaml(path)
    services, diagnostics = compose_services(document, path)
    if diagnostics:
        return diagnostics

    known_inputs = {
        item["mapping"]["composeInput"] for item in contract["installationInputs"]
    }
    for scalar in walk_scalars(document):
        for source in sorted(interpolation_names(scalar) - known_inputs):
            diagnostics.append(f"unknown Compose interpolation input: {source}")

    actual: dict[tuple[str, str], Any] = {}
    for service, configuration in services.items():
        environment, environment_diagnostics = normalize_environment(
            service, configuration.get("environment")
        )
        diagnostics.extend(environment_diagnostics)
        diagnostics.extend(lint_environment(service, environment, set()))
        for name, value in environment.items():
            actual[(service, name)] = value

    expected = {
        (item["service"], item["name"]): item for item in contract["composeOutputs"]
    }
    for service, name in sorted(actual.keys() - expected.keys()):
        diagnostics.append(f"unknown Compose output: {service}.{name}")
    for service, name in sorted(expected.keys() - actual.keys()):
        diagnostics.append(f"missing classified Compose output: {service}.{name}")

    for key in sorted(actual.keys() & expected.keys()):
        value = actual[key]
        metadata = expected[key]
        sources = interpolation_names(value)
        source_kind = metadata["sourceKind"]
        if source_kind == "input" and sources != {metadata["sourceInput"]}:
            diagnostics.append(
                f"invalid input mapping: {key[0]}.{key[1]} must map only "
                f"{metadata['sourceInput']}"
            )
        if source_kind in {"fixed", "third-party-adapter"} and sources:
            diagnostics.append(f"overrideable fixed Compose output: {key[0]}.{key[1]}")
        if source_kind == "secret-reference":
            if not is_file_reference_name(key[1]):
                diagnostics.append(f"secret output is not file-only: {key[0]}.{key[1]}")
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(f"empty secret file reference: {key[0]}.{key[1]}")
    return diagnostics


def repository_compose_files() -> list[Path]:
    paths: set[Path] = set()
    generated_directories = {
        ".cache",
        ".docusaurus",
        ".git",
        ".venv",
        ".worktrees",
        "build",
        "coverage",
        "dist",
        "node_modules",
    }
    for root, directories, filenames in REPOSITORY_ROOT.walk():
        directories[:] = [
            directory
            for directory in directories
            if directory not in generated_directories
        ]
        for filename in filenames:
            if re.fullmatch(r"docker-compose.*\.ya?ml", filename):
                paths.add(root / filename)
    return sorted(paths)


def validate_product_secret_fixtures(root: Path) -> list[str]:
    diagnostics: list[str] = []
    if not root.exists():
        return [f"product Secret fixture root does not exist: {root}"]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative_path = path.relative_to(root)
        except ValueError:
            continue
        parts = relative_path.parts
        if not any(
            parts[index : index + 2] == ("tests", "fixtures")
            for index in range(max(0, len(parts) - 1))
        ):
            continue
        fixture_name = normalize_process_argument_name(path.name)
        if is_secret_name(fixture_name):
            diagnostics.append(
                f"persistent product Secret fixture: {relative_path.as_posix()}"
            )
    return diagnostics


def validate_compose_config() -> list[str]:
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ENV_EXAMPLE_PATH),
        "--file",
        str(ROOT_COMPOSE_PATH),
        "--profile",
        "local-oidc",
        "config",
        "--quiet",
    ]
    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    message = result.stderr.strip().splitlines()
    detail = message[-1] if message else f"exit code {result.returncode}"
    return [f"Compose config invalid: {detail}"]


def validate_repository(include_compose_config: bool = True) -> list[str]:
    contract = load_json(CONTRACT_PATH)
    vectors = load_json(VECTORS_PATH)
    diagnostics = validate_schema_definition(load_json(SCHEMA_PATH), "contract schema")
    diagnostics.extend(
        validate_schema_definition(load_json(VECTORS_SCHEMA_PATH), "vectors schema")
    )
    diagnostics.extend(validate_contract_data(contract))
    diagnostics.extend(validate_helm_mappings(contract))
    diagnostics.extend(validate_helm_adapter(contract))
    _, parity_diagnostics = normalize_adapter_parity(
        contract,
        "https://platform.example.test:8443",
        PARITY_SAMPLE_WORKSPACE_ID,
    )
    diagnostics.extend(parity_diagnostics)
    diagnostics.extend(
        validate_json_schema(vectors, load_json(VECTORS_SCHEMA_PATH), "vectors schema")
    )
    diagnostics.extend(validate_env_inputs(ENV_EXAMPLE_PATH, contract))
    diagnostics.extend(validate_root_compose(ROOT_COMPOSE_PATH, contract))

    fixture_outputs: dict[str, set[tuple[str, str]]] = {}
    for item in contract["testFixtureOutputs"]:
        fixture_outputs.setdefault(item["path"], set()).add(
            (item["service"], item["name"])
        )
    for path in repository_compose_files():
        relative_path = str(path.relative_to(REPOSITORY_ROOT))
        diagnostics.extend(
            lint_compose_file(path, fixture_outputs.get(relative_path, set()))
        )
    diagnostics.extend(validate_product_secret_fixtures(REPOSITORY_ROOT))
    if include_compose_config:
        diagnostics.extend(validate_compose_config())
    return sorted(set(diagnostics))


def evaluate_vector(vector: dict[str, Any]) -> list[str]:
    kind = vector["kind"]
    if kind == "origin":
        return validate_platform_public_origin(vector.get("value"))
    if kind == "repository-contract":
        contract = load_json(CONTRACT_PATH)
        _, parity_diagnostics = normalize_adapter_parity(
            contract,
            "https://platform.example.test:8443",
            PARITY_SAMPLE_WORKSPACE_ID,
        )
        return (
            validate_contract_data(contract)
            + validate_helm_mappings(contract)
            + parity_diagnostics
        )
    if kind == "contract-mutation":
        contract = copy.deepcopy(load_json(CONTRACT_PATH))
        if vector["mutation"] == "duplicate-first-output":
            contract["composeOutputs"].append(copy.deepcopy(contract["composeOutputs"][0]))
            return validate_contract_data(contract)
        if vector["mutation"] == "restore-old-oidc-helm-mapping":
            oidc_issuer = next(
                item
                for item in contract["installationInputs"]
                if item["logicalName"] == "oidcIssuerUrl"
            )
            oidc_issuer["mapping"]["helmValuesPath"] = "workspaceManager.oidc.issuerUrl"
            return validate_contract_data(contract) + validate_helm_mappings(contract)
        if vector["mutation"] == "diverge-helm-derived-callback":
            callback = next(
                item
                for item in contract["derivedLogicalOutputs"]
                if item["logicalName"] == "oidcCallbackUrl"
            )
            callback["mapping"]["helmTemplate"] = (
                "{platformPublicOrigin}/oauth2/callback"
            )
            _, parity_diagnostics = normalize_adapter_parity(
                contract,
                "https://platform.example.test:8443",
                PARITY_SAMPLE_WORKSPACE_ID,
            )
            return validate_contract_data(contract) + parity_diagnostics
        if vector["mutation"] == "missing-test-fixture-path":
            missing_fixture = copy.deepcopy(contract["testFixtureOutputs"][0])
            missing_fixture["path"] = (
                "scripts/test/platform-configuration/fixtures/missing-compose.yml"
            )
            contract["testFixtureOutputs"].append(missing_fixture)
            return validate_contract_data(contract)
        return [f"unknown contract mutation: {vector['mutation']}"]
    fixture = REPOSITORY_ROOT / vector["fixture"]
    if kind == "compose-fixture":
        return lint_compose_file(fixture)
    if kind == "env-fixture":
        return validate_env_inputs(fixture, load_json(CONTRACT_PATH))
    return [f"unknown vector kind: {kind}"]


def print_diagnostics(diagnostics: Iterable[str]) -> None:
    for diagnostic in diagnostics:
        print(diagnostic, file=sys.stderr)


def validate_vector(vector_id: str) -> int:
    vectors_document = load_json(VECTORS_PATH)
    vectors_schema = load_json(VECTORS_SCHEMA_PATH)
    schema_diagnostics = validate_schema_definition(vectors_schema, "vectors schema")
    schema_diagnostics.extend(
        validate_json_schema(vectors_document, vectors_schema, "vectors schema")
    )
    if schema_diagnostics:
        print_diagnostics(schema_diagnostics)
        return 1

    vector = next(
        (item for item in vectors_document["vectors"] if item["id"] == vector_id), None
    )
    if vector is None:
        print(f"unknown vector: {vector_id}", file=sys.stderr)
        return 2

    diagnostics = evaluate_vector(vector)
    if diagnostics:
        print_diagnostics(diagnostics)
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate platform configuration contracts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    vector_parser = subparsers.add_parser("validate-vector")
    vector_parser.add_argument("--vector", required=True)

    repository_parser = subparsers.add_parser("validate-repository")
    repository_parser.add_argument("--skip-compose-config", action="store_true")

    fixture_parser = subparsers.add_parser("validate-product-secret-fixtures")
    fixture_parser.add_argument("--root", type=Path, required=True)

    helm_parser = subparsers.add_parser("validate-helm-adapter")
    helm_parser.add_argument("--chart-path", type=Path)

    parity_parser = subparsers.add_parser("validate-parity")
    parity_parser.add_argument("--origin", required=True)
    parity_parser.add_argument("--workspace-id", required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if arguments.command == "validate-vector":
        return validate_vector(arguments.vector)
    if arguments.command == "validate-repository":
        diagnostics = validate_repository(
            include_compose_config=not arguments.skip_compose_config
        )
        if diagnostics:
            print_diagnostics(diagnostics)
            return 1
        return 0
    if arguments.command == "validate-product-secret-fixtures":
        diagnostics = validate_product_secret_fixtures(arguments.root)
        if diagnostics:
            print_diagnostics(diagnostics)
            return 1
        return 0
    if arguments.command == "validate-helm-adapter":
        diagnostics = validate_helm_adapter(
            load_json(CONTRACT_PATH), arguments.chart_path
        )
        if diagnostics:
            print_diagnostics(diagnostics)
            return 1
        return 0
    if arguments.command == "validate-parity":
        normalized, diagnostics = normalize_adapter_parity(
            load_json(CONTRACT_PATH),
            arguments.origin,
            arguments.workspace_id,
        )
        if diagnostics:
            print_diagnostics(diagnostics)
            return 1
        print(json.dumps(normalized, ensure_ascii=False, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
