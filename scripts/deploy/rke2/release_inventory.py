#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_REFERENCE_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
REGISTRY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*(?::[0-9]{1,5})?$")
PROJECT_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
OCI_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"


def load_contract(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        contract = json.load(stream)
    if not isinstance(contract, dict):
        raise ValueError("image release contract must be a JSON object")
    published = contract.get("publishedComponents")
    workloads = contract.get("workloadComponents")
    evidence = contract.get("buildEvidenceComponents")
    optional = contract.get("optionalPublishedComponents")
    for value, description in (
        (published, "publishedComponents"),
        (workloads, "workloadComponents"),
        (evidence, "buildEvidenceComponents"),
    ):
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item for item in value)
            or len(set(value)) != len(value)
        ):
            raise ValueError(f"{description} must be a unique non-empty string array")
    if set(published) != set(workloads).union(evidence):
        raise ValueError(
            "publishedComponents must equal workloadComponents plus "
            "buildEvidenceComponents"
        )
    if set(workloads).intersection(evidence):
        raise ValueError("workload and build evidence components must be disjoint")
    if (
        not isinstance(optional, list)
        or len(set(optional)) != len(optional)
        or any(not isinstance(item, str) or not item for item in optional)
        or not set(optional).issubset(published)
    ):
        raise ValueError(
            "optionalPublishedComponents must be a unique published-component array"
        )
    return contract


def validate_published_inventory(
    rows: list[str],
    *,
    contract: dict[str, Any],
    expected_commit: str,
    expected_registry: str,
    expected_project: str,
    omitted_components: frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    if FULL_SHA_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected commit must be a full lowercase Git SHA")
    if REGISTRY_PATTERN.fullmatch(expected_registry) is None:
        raise ValueError(
            "expected registry must be an exact hostname with optional port"
        )
    if PROJECT_PATTERN.fullmatch(expected_project) is None:
        raise ValueError("expected project must use valid lowercase registry syntax")
    inventory: dict[str, dict[str, str]] = {}
    for line_number, row in enumerate(rows, start=1):
        columns = row.rstrip("\n").split("\t")
        if len(columns) != 6 or any(not value for value in columns):
            raise ValueError(f"published inventory row {line_number} is malformed")
        (
            component,
            revision,
            platform,
            tagged_image,
            immutable_image,
            runtime_immutable_image,
        ) = columns
        if component in inventory:
            raise ValueError(f"published inventory duplicates component: {component}")
        if revision != expected_commit:
            raise ValueError(
                f"published inventory revision mismatch for component: {component}"
            )
        if platform != "linux/amd64":
            raise ValueError(
                f"published inventory platform mismatch for component: {component}"
            )
        expected_repository = f"{expected_registry}/{expected_project}/{component}"
        if tagged_image != f"{expected_repository}:git-{expected_commit}":
            raise ValueError(
                f"published inventory repository or tag mismatch for component: {component}"
            )
        if DIGEST_REFERENCE_PATTERN.fullmatch(immutable_image) is None:
            raise ValueError(
                f"published inventory digest is invalid for component: {component}"
            )
        if immutable_image.rsplit("@", 1)[0] != expected_repository:
            raise ValueError(
                f"published inventory repository mismatch for component: {component}"
            )
        if DIGEST_REFERENCE_PATTERN.fullmatch(runtime_immutable_image) is None:
            raise ValueError(
                "published inventory runtime digest is invalid for component: "
                f"{component}"
            )
        if (
            runtime_immutable_image.rsplit("@", 1)[0] != tagged_image.rsplit(":", 1)[0]
            or runtime_immutable_image == immutable_image
        ):
            raise ValueError(
                "published inventory runtime repository or digest is invalid for "
                f"component: {component}"
            )
        inventory[component] = {
            "component": component,
            "revision": revision,
            "platform": platform,
            "taggedImage": tagged_image,
            "immutableImage": immutable_image,
            "runtimeImmutableImage": runtime_immutable_image,
        }

    optional_components = set(contract["optionalPublishedComponents"])
    if not omitted_components.issubset(optional_components):
        raise ValueError("published inventory omission is not allowlisted")
    all_components = set(contract["publishedComponents"])
    expected_components = all_components - omitted_components
    actual_components = set(inventory)
    if not expected_components.issubset(
        actual_components
    ) or not actual_components.issubset(all_components):
        missing = ",".join(sorted(expected_components - actual_components))
        unexpected = ",".join(sorted(actual_components - all_components))
        raise ValueError(
            "published inventory component mismatch: "
            f"missing={missing or 'none'} unexpected={unexpected or 'none'}"
        )
    return [
        inventory[name] for name in contract["publishedComponents"] if name in inventory
    ]


def validate_remote_image_document(document: Any, *, image: dict[str, str]) -> None:
    tagged_image = image["taggedImage"]
    immutable_image = image["immutableImage"]
    runtime_immutable_image = image["runtimeImmutableImage"]
    expected_index_digest = immutable_image.rsplit("@", 1)[1]
    expected_runtime_digest = runtime_immutable_image.rsplit("@", 1)[1]
    image_config = document.get("image") if isinstance(document, dict) else None
    config = image_config.get("config") if isinstance(image_config, dict) else None
    labels = config.get("Labels") if isinstance(config, dict) else None
    manifest = document.get("manifest") if isinstance(document, dict) else None
    manifests = manifest.get("manifests") if isinstance(manifest, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("name") != tagged_image
        or not isinstance(image_config, dict)
        or image_config.get("os") != "linux"
        or image_config.get("architecture") != "amd64"
        or not isinstance(labels, dict)
        or labels.get("org.opencontainers.image.revision") != image["revision"]
        or not isinstance(manifest, dict)
        or manifest.get("mediaType") != OCI_INDEX_MEDIA_TYPE
        or manifest.get("digest") != expected_index_digest
        or not isinstance(manifests, list)
        or not manifests
    ):
        raise ValueError(
            f"remote image provenance is invalid for component: {image['component']}"
        )

    runtime_manifests = []
    for item in manifests:
        platform = item.get("platform") if isinstance(item, dict) else None
        digest = item.get("digest") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or item.get("mediaType") != OCI_MANIFEST_MEDIA_TYPE
            or not isinstance(digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            or not isinstance(platform, dict)
        ):
            raise ValueError(
                "remote image manifest inventory is invalid for component: "
                f"{image['component']}"
            )
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            runtime_manifests.append(item)
            continue
        annotations = item.get("annotations")
        if (
            platform.get("os") != "unknown"
            or platform.get("architecture") != "unknown"
            or not isinstance(annotations, dict)
            or annotations.get("vnd.docker.reference.type") != "attestation-manifest"
            or annotations.get("vnd.docker.reference.digest") != expected_runtime_digest
        ):
            raise ValueError(
                "remote image platform inventory is invalid for component: "
                f"{image['component']}"
            )
    if (
        len(runtime_manifests) != 1
        or runtime_manifests[0].get("digest") != expected_runtime_digest
    ):
        raise ValueError(
            "remote linux/amd64 image digest is invalid for component: "
            f"{image['component']}"
        )


def verify_remote_published_inventory(
    images: list[dict[str, str]],
    *,
    inspect: Callable[[str], str],
) -> None:
    for image in images:
        try:
            raw_document = inspect(image["taggedImage"])
            document = json.loads(raw_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "remote image document is invalid JSON for component: "
                f"{image['component']}"
            ) from exc
        validate_remote_image_document(document, image=image)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-registry", required=True)
    parser.add_argument("--expected-project", required=True)
    parser.add_argument("--omit-component", action="append", default=[])
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(__file__).with_name("image-release-contract.json"),
    )
    arguments = parser.parse_args()
    contract = load_contract(arguments.contract)
    with arguments.inventory.open(encoding="utf-8") as stream:
        inventory = validate_published_inventory(
            stream.readlines(),
            contract=contract,
            expected_commit=arguments.expected_commit,
            expected_registry=arguments.expected_registry,
            expected_project=arguments.expected_project,
            omitted_components=frozenset(arguments.omit_component),
        )
    print(json.dumps(inventory, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
