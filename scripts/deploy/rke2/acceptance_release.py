#!/usr/bin/env python3
"""Sign and verify the exact release inventory used by acceptance Jobs."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
CONTRACT_PATH = SCRIPT_DIRECTORY / "image-release-contract.json"
SCHEMA_VERSION = "aileron-signed-image-inventory/v2"
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


class AcceptanceReleaseError(RuntimeError):
    """Raised when a signed image inventory is incomplete or untrusted."""


def _load_private_io() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_release_private_io",
        SCRIPT_DIRECTORY / "acceptance_private_io.py",
    )
    if specification is None or specification.loader is None:
        raise AcceptanceReleaseError("acceptance private I/O is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_IO = _load_private_io()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


class _DuplicateKeyError(ValueError):
    """Internal marker for a non-unique JSON object member."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateKeyError("duplicate JSON object key")
        document[key] = value
    return document


def _component_sets() -> tuple[list[str], set[str]]:
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceReleaseError("image release contract is unavailable") from exc
    components = document.get("publishedComponents")
    optional = document.get("optionalPublishedComponents")
    if (
        not isinstance(components, list)
        or len(components) != 11
        or not isinstance(optional, list)
        or set(optional) != {"platform-redis"}
    ):
        raise AcceptanceReleaseError(
            "image release contract component sets are invalid"
        )
    return components, set(optional)


def _validate_images(images: Any, commit: str) -> None:
    components, optional = _component_sets()
    if not isinstance(images, list):
        raise AcceptanceReleaseError("signed image inventory must be an image array")
    observed = []
    for image in images:
        if (
            not isinstance(image, dict)
            or set(image)
            != {
                "component",
                "revision",
                "platform",
                "taggedImage",
                "immutableImage",
                "runtimeImmutableImage",
            }
            or image.get("revision") != commit
            or image.get("platform") != "linux/amd64"
            or not isinstance(image.get("immutableImage"), str)
            or IMAGE.fullmatch(image["immutableImage"]) is None
            or not isinstance(image.get("runtimeImmutableImage"), str)
            or IMAGE.fullmatch(image["runtimeImmutableImage"]) is None
            or not isinstance(image.get("taggedImage"), str)
            or not image["taggedImage"].endswith(f":git-{commit}")
            or image["immutableImage"].rsplit("@", 1)[0]
            != image["taggedImage"].rsplit(":", 1)[0]
            or image["runtimeImmutableImage"].rsplit("@", 1)[0]
            != image["taggedImage"].rsplit(":", 1)[0]
            or image["runtimeImmutableImage"] == image["immutableImage"]
        ):
            raise AcceptanceReleaseError("signed image inventory entry is invalid")
        observed.append(image["component"])
    observed_set = set(observed)
    if observed_set not in (
        set(components),
        set(components) - optional,
    ) or observed != [
        component for component in components if component in observed_set
    ]:
        raise AcceptanceReleaseError(
            "signed image inventory components do not match the release contract"
        )


def write_signed_image_inventory(
    *,
    path: Path,
    private_root: Path,
    images: list[dict[str, str]],
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
) -> Path:
    """Write an installation-bound immutable image inventory envelope."""

    if (
        len(key) != 32
        or SHA.fullmatch(commit) is None
        or DIGEST.fullmatch(installation_identity_sha256) is None
        or not context
        or not cluster_uid
    ):
        raise AcceptanceReleaseError("signed image inventory identity is invalid")
    _validate_images(images, commit)
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "commit": commit,
        "clusterUid": cluster_uid,
        "context": context,
        "installationIdentitySha256": installation_identity_sha256,
        "images": images,
    }
    document["signature"] = hmac.new(
        key, _canonical(document), hashlib.sha256
    ).hexdigest()
    return PRIVATE_IO.write_private_snapshot(
        destination=path,
        content=_canonical(document) + b"\n",
        description="signed image inventory",
        private_root=private_root,
        error_type=AcceptanceReleaseError,
    )


def load_signed_image_inventory(
    *,
    path: Path,
    private_root: Path,
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
) -> list[dict[str, str]]:
    """Return the exact installation-bound current release image set."""

    raw = PRIVATE_IO.read_private_bytes(
        path,
        "signed image inventory",
        private_root=private_root,
        error_type=AcceptanceReleaseError,
        maximum_size=1024 * 1024,
    )
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError) as exc:
        raise AcceptanceReleaseError("signed image inventory is invalid JSON") from exc
    if raw != _canonical(document) + b"\n":
        raise AcceptanceReleaseError("signed image inventory is not canonical JSON")
    if not isinstance(document, dict) or set(document) != {
        "schemaVersion",
        "commit",
        "clusterUid",
        "context",
        "installationIdentitySha256",
        "images",
        "signature",
    }:
        raise AcceptanceReleaseError("signed image inventory shape is invalid")
    signature = document.get("signature")
    unsigned = dict(document)
    unsigned.pop("signature", None)
    expected = hmac.new(key, _canonical(unsigned), hashlib.sha256).hexdigest()
    if (
        not isinstance(signature, str)
        or DIGEST.fullmatch(signature) is None
        or not hmac.compare_digest(signature, expected)
    ):
        raise AcceptanceReleaseError("signed image inventory signature does not match")
    if (
        document["schemaVersion"] != SCHEMA_VERSION
        or document["commit"] != commit
        or document["clusterUid"] != cluster_uid
        or document["context"] != context
        or document["installationIdentitySha256"] != installation_identity_sha256
    ):
        raise AcceptanceReleaseError("signed image inventory identity does not match")
    _validate_images(document["images"], commit)
    return document["images"]


def load_matching_signed_image_inventory(
    *,
    path: Path,
    private_root: Path,
    expected_images: list[dict[str, str]],
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
) -> list[dict[str, str]]:
    """Load a signed envelope only when it exactly matches its source inventory."""

    _validate_images(expected_images, commit)
    signed_images = load_signed_image_inventory(
        path=path,
        private_root=private_root,
        key=key,
        context=context,
        commit=commit,
        cluster_uid=cluster_uid,
        installation_identity_sha256=installation_identity_sha256,
    )
    if signed_images != expected_images:
        raise AcceptanceReleaseError(
            "signed image inventory does not match published inventory"
        )
    return signed_images


def load_workspace_manager_image(
    *,
    path: Path,
    private_root: Path,
    key: bytes,
    context: str,
    commit: str,
    cluster_uid: str,
    installation_identity_sha256: str,
) -> dict[str, str]:
    """Return the sole current-release Workspace Manager immutable image."""

    images = load_signed_image_inventory(
        path=path,
        private_root=private_root,
        key=key,
        context=context,
        commit=commit,
        cluster_uid=cluster_uid,
        installation_identity_sha256=installation_identity_sha256,
    )
    matches = [image for image in images if image["component"] == "workspace-manager"]
    if len(matches) != 1:
        raise AcceptanceReleaseError(
            "signed image inventory has no exact Workspace Manager image"
        )
    return matches[0]
