#!/usr/bin/env python3
"""Render immutable release inventory into exact Helm value overrides."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

import yaml

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_IMAGE_CONTRACT = SCRIPT_DIRECTORY / "image-release-contract.json"
DEFAULT_VALUES_CONTRACT = SCRIPT_DIRECTORY / "release-values-contract.json"


def _load_release_inventory_module() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_release_inventory", SCRIPT_DIRECTORY / "release_inventory.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("release inventory validator is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


RELEASE_INVENTORY = _load_release_inventory_module()


class RenderedReleaseValues:
    def __init__(
        self,
        *,
        core_path: Path,
        identity_path: Path | None,
        published_images: dict[str, str],
    ) -> None:
        self.core_path = core_path
        self.identity_path = identity_path
        self.published_images = published_images


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is unreadable or invalid") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{description} must be a JSON object")
    return document


def _validate_values_contract(
    contract: dict[str, Any], image_contract: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    if contract.get("contractVersion") != "aileron-release-values/v1":
        raise ValueError("release values contract version is unsupported")
    components = contract.get("components")
    if not isinstance(components, dict):
        raise ValueError("release values component mapping is invalid")
    expected_components = set(image_contract["workloadComponents"])
    if set(components) != expected_components:
        raise ValueError(
            "release values component mapping does not match workload components"
        )

    destinations: set[tuple[str, tuple[str, ...]]] = set()
    for component, mappings in components.items():
        if not isinstance(mappings, list) or not mappings:
            raise ValueError(f"release values mapping is empty: {component}")
        for mapping in mappings:
            if not isinstance(mapping, dict):
                raise ValueError(f"release values mapping is invalid: {component}")
            target = mapping.get("target")
            path = mapping.get("path")
            if (
                target not in {"core", "identity"}
                or not isinstance(path, list)
                or not path
                or any(not isinstance(segment, str) or not segment for segment in path)
            ):
                raise ValueError(f"release values mapping is invalid: {component}")
            destination = (target, tuple(path))
            if destination in destinations:
                raise ValueError(
                    "release values destination is mapped by multiple components"
                )
            destinations.add(destination)
    return components


def _set_path(document: dict[str, Any], path: list[str], value: dict[str, str]) -> None:
    cursor = document
    for segment in path[:-1]:
        existing = cursor.setdefault(segment, {})
        if not isinstance(existing, dict):
            raise ValueError("release values path conflicts with profile values")
        cursor = existing
    leaf = path[-1]
    if leaf in cursor:
        raise ValueError("release values destination conflicts with profile values")
    cursor[leaf] = value


def _private_json_write(path: Path, document: dict[str, Any]) -> None:
    content = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path.replace(path)
            path.chmod(0o600)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def _profile(contract: dict[str, Any], name: str) -> dict[str, Any]:
    home_lab = contract.get("homeLab")
    if not isinstance(home_lab, dict) or not isinstance(home_lab.get(name), dict):
        raise ValueError(f"HomeLab {name} release values profile is invalid")
    return json.loads(json.dumps(home_lab[name]))


def _merge_values(target: dict[str, Any], overlay: dict[str, Any]) -> None:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_values(target[key], value)
        else:
            target[key] = json.loads(json.dumps(value))


def _data_service_values(
    path: Path | None,
    *,
    description: str,
    allowed: dict[str, Any],
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{description} is unreadable or invalid") from exc
    if not isinstance(document, dict) or not document:
        raise ValueError(f"{description} must be a non-empty object")

    def validate(value: Any, contract: Any) -> None:
        if contract is True:
            return
        if not isinstance(value, dict) or not isinstance(contract, dict):
            raise ValueError(f"{description} contains a forbidden value")
        if not set(value).issubset(contract):
            raise ValueError(f"{description} contains a forbidden field")
        for key, child in value.items():
            validate(child, contract[key])

    validate(document, allowed)
    return document


CORE_DATA_SERVICE_VALUES = {
    "postgres": {"enabled": True},
    "platformDatabase": {
        "revision": True,
        "caSecretName": True,
        "caSecretKey": True,
        "ciliumEgress": {
            "kind": True,
            "values": True,
            "namespace": True,
            "podLabels": True,
        },
    },
    "redis": {
        "enabled": True,
        "connections": {
            name: {
                "revision": True,
                "urlSecretName": True,
                "urlSecretKey": True,
                "caSecretName": True,
                "caSecretKey": True,
            }
            for name in ("general", "jobQueue", "jobResult")
        },
    },
}
IDENTITY_DATA_SERVICE_VALUES = {
    "postgres": {
        "enabled": True,
        "jdbcUrl": True,
        "revision": True,
        "caSecretName": True,
        "caSecretKey": True,
    },
    "networkPolicy": {
        "externalDatabaseEgress": {
            "mode": True,
            "namespaceLabels": True,
            "podLabels": True,
            "cidr": True,
        }
    },
}


def omitted_published_components(
    core_data_service_values_path: Path | None,
) -> frozenset[str]:
    core_data_services = _data_service_values(
        core_data_service_values_path,
        description="Core data-service values",
        allowed=CORE_DATA_SERVICE_VALUES,
    )
    if (
        core_data_services is not None
        and core_data_services.get("redis", {}).get("enabled") is False
    ):
        return frozenset({"platform-redis"})
    return frozenset()


def render_release_values(
    *,
    inventory_path: Path,
    expected_commit: str,
    expected_registry: str,
    expected_project: str,
    identity_mode: str,
    output_directory: Path,
    image_contract_path: Path = DEFAULT_IMAGE_CONTRACT,
    values_contract_path: Path = DEFAULT_VALUES_CONTRACT,
    external_oidc: dict[str, str] | None = None,
    core_data_service_values_path: Path | None = None,
    identity_data_service_values_path: Path | None = None,
) -> RenderedReleaseValues:
    """Validate the full inventory and render only mode-selected workload values."""

    if identity_mode == "bundledKeycloak":
        if external_oidc is not None:
            raise ValueError(
                "bundledKeycloak mode must not provide external OIDC values"
            )
    elif identity_mode == "externalOidc":
        if (
            not isinstance(external_oidc, dict)
            or set(external_oidc) != {"issuerUrl", "clientId"}
            or any(
                not value or value != value.strip() for value in external_oidc.values()
            )
        ):
            raise ValueError("external OIDC issuer URL and client ID are required")
        issuer = urlparse(external_oidc["issuerUrl"])
        if (
            issuer.scheme != "https"
            or not issuer.netloc
            or issuer.username is not None
            or issuer.password is not None
            or issuer.fragment
        ):
            raise ValueError("external OIDC issuer URL must be a public HTTPS URL")
    else:
        raise ValueError("identity mode must be bundledKeycloak or externalOidc")

    image_contract = RELEASE_INVENTORY.load_contract(image_contract_path)
    values_contract = _load_json(values_contract_path, "release values contract")
    mappings = _validate_values_contract(values_contract, image_contract)
    try:
        rows = inventory_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("published image inventory is unreadable") from exc
    core = _profile(values_contract, "core")
    identity = _profile(values_contract, "identity")
    core_data_services = _data_service_values(
        core_data_service_values_path,
        description="Core data-service values",
        allowed=CORE_DATA_SERVICE_VALUES,
    )
    identity_data_services = _data_service_values(
        identity_data_service_values_path,
        description="Identity data-service values",
        allowed=IDENTITY_DATA_SERVICE_VALUES,
    )
    if core_data_services is not None:
        _merge_values(core, core_data_services)
    omitted_components = omitted_published_components(
        core_data_service_values_path
    )
    inventory = RELEASE_INVENTORY.validate_published_inventory(
        rows,
        contract=image_contract,
        expected_commit=expected_commit,
        expected_registry=expected_registry,
        expected_project=expected_project,
        omitted_components=omitted_components,
    )
    published_images = {item["component"]: item["immutableImage"] for item in inventory}

    if identity_data_services is not None:
        if identity_mode != "bundledKeycloak":
            raise ValueError(
                "Identity data-service values require bundledKeycloak mode"
            )
        _merge_values(identity, identity_data_services)
    if identity_mode == "externalOidc":
        core["oidc"]["issuerUrl"] = external_oidc["issuerUrl"]
        core["oidc"]["clientId"] = external_oidc["clientId"]

    targets = {"core": core, "identity": identity}
    for component, component_mappings in mappings.items():
        if component in omitted_components:
            continue
        repository, digest = published_images[component].rsplit("@", 1)
        for mapping in component_mappings:
            if mapping["target"] == "identity" and identity_mode == "externalOidc":
                continue
            value = {"repository": repository, "digest": digest}
            if mapping["target"] == "core":
                value["tag"] = ""
            _set_path(targets[mapping["target"]], mapping["path"], value)

    if output_directory.exists():
        output_metadata = os.lstat(output_directory)
        if (
            not stat.S_ISDIR(output_metadata.st_mode)
            or stat.S_IMODE(output_metadata.st_mode) != 0o700
            or output_metadata.st_uid != os.geteuid()
        ):
            raise ValueError(
                "release values output directory must be owner-controlled mode 0700"
            )
        allowed = {"core-values.json", "identity-values.json"}
        entries = list(output_directory.iterdir())
        if any(path.name not in allowed for path in entries):
            raise ValueError(
                "release values output directory contains unexpected entries"
            )
        for path in entries:
            metadata = os.lstat(path)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.geteuid()
                or metadata.st_nlink != 1
            ):
                raise ValueError(
                    "release values output files must be owner-controlled mode 0600 regular files"
                )
        if (
            identity_mode == "externalOidc"
            and (output_directory / "identity-values.json").exists()
        ):
            raise ValueError(
                "externalOidc output must not reuse bundled Identity values"
            )
    else:
        output_directory.mkdir(mode=0o700, parents=True)
    output_directory.chmod(0o700)

    core_path = output_directory / "core-values.json"
    _private_json_write(core_path, core)
    identity_path = None
    if identity_mode == "bundledKeycloak":
        identity_path = output_directory / "identity-values.json"
        _private_json_write(identity_path, identity)
    return RenderedReleaseValues(
        core_path=core_path,
        identity_path=identity_path,
        published_images=published_images,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--identity-mode", choices=("bundledKeycloak", "externalOidc"), required=True
    )
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--image-contract", type=Path, default=DEFAULT_IMAGE_CONTRACT)
    parser.add_argument("--values-contract", type=Path, default=DEFAULT_VALUES_CONTRACT)
    parser.add_argument("--external-oidc-issuer-url")
    parser.add_argument("--external-oidc-client-id")
    parser.add_argument("--core-data-service-values", type=Path)
    parser.add_argument("--identity-data-service-values", type=Path)
    arguments = parser.parse_args()
    external_oidc = None
    if arguments.identity_mode == "externalOidc":
        external_oidc = {
            "issuerUrl": arguments.external_oidc_issuer_url or "",
            "clientId": arguments.external_oidc_client_id or "",
        }
    try:
        result = render_release_values(
            inventory_path=arguments.inventory,
            expected_commit=arguments.expected_commit,
            expected_registry=arguments.registry,
            expected_project=arguments.project,
            identity_mode=arguments.identity_mode,
            output_directory=arguments.output_directory,
            image_contract_path=arguments.image_contract,
            values_contract_path=arguments.values_contract,
            external_oidc=external_oidc,
            core_data_service_values_path=arguments.core_data_service_values,
            identity_data_service_values_path=arguments.identity_data_service_values,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"core_values={result.core_path}")
    if result.identity_path is not None:
        print(f"identity_values={result.identity_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
