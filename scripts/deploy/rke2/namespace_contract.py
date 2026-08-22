#!/usr/bin/env python3
"""Validate installer-owned Kubernetes Namespace identity and security profiles."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple
from uuid import UUID

NAMESPACE_OWNER_LABEL = "platform.aileron.dev/namespace-owner"
NAMESPACE_OWNER = "aileron-installer"
POD_SECURITY_LABEL_PREFIX = "pod-security.kubernetes.io/"
DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
LABEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[-_.A-Za-z0-9]{0,61}[A-Za-z0-9])?$")
DNS_SUBDOMAIN_PATTERN = re.compile(
    r"^[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?$"
)


class NamespaceProfile(NamedTuple):
    enforce: str
    audit: str
    warn: str


class NamespaceRecord(NamedTuple):
    uid: str
    resource_version: str
    labels: dict[str, str]
    phase: str | None
    deletion_timestamp: str | None


NAMESPACE_PROFILES: dict[str, NamespaceProfile] = {
    "workspace-system": NamespaceProfile("privileged", "restricted", "restricted"),
    "aileron-turn-system": NamespaceProfile(
        "privileged", "restricted", "restricted"
    ),
    "aileron-backend-attestor-system": NamespaceProfile(
        "privileged", "restricted", "restricted"
    ),
    "aileron-identity-system": NamespaceProfile(
        "restricted", "restricted", "restricted"
    ),
    "aileron-acceptance-system": NamespaceProfile(
        "restricted", "restricted", "restricted"
    ),
}


class NamespaceContractError(ValueError):
    """Raised when a Kubernetes Namespace is outside the installation contract."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON object key")
        document[key] = value
    return document


def _reject_nonstandard_constant(_value: str) -> None:
    raise ValueError("non-standard JSON constant")


def load_json_document(raw: bytes | str, description: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        document = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonstandard_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise NamespaceContractError(f"{description} is invalid JSON") from exc
    if not isinstance(document, dict):
        raise NamespaceContractError(f"{description} must be a JSON object")
    return document


def _canonical_nonempty(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def _canonical_label_key(value: str) -> bool:
    prefix, separator, name = value.rpartition("/")
    if not separator:
        name = value
        prefix = ""
    return (
        LABEL_NAME_PATTERN.fullmatch(name) is not None
        and (
            not prefix
            or len(prefix) <= 253
            and DNS_SUBDOMAIN_PATTERN.fullmatch(prefix) is not None
            and all(DNS_LABEL_PATTERN.fullmatch(part) for part in prefix.split("."))
        )
    )


def _canonical_label_value(value: str) -> bool:
    return value == "" or LABEL_NAME_PATTERN.fullmatch(value) is not None


def profile_for(namespace: str) -> NamespaceProfile:
    try:
        return NAMESPACE_PROFILES[namespace]
    except KeyError as exc:
        raise NamespaceContractError(
            f"Kubernetes Namespace profile is not installation-owned: {namespace}"
        ) from exc


def profile_labels(namespace: str) -> dict[str, str]:
    profile = profile_for(namespace)
    return {
        NAMESPACE_OWNER_LABEL: NAMESPACE_OWNER,
        "pod-security.kubernetes.io/enforce": profile.enforce,
        "pod-security.kubernetes.io/audit": profile.audit,
        "pod-security.kubernetes.io/warn": profile.warn,
    }


def profile_matches(namespace: str, labels: Mapping[str, str]) -> bool:
    expected = profile_labels(namespace)
    expected_psa_keys = {
        key for key in expected if key.startswith(POD_SECURITY_LABEL_PREFIX)
    }
    observed_psa_keys = {
        key for key in labels if key.startswith(POD_SECURITY_LABEL_PREFIX)
    }
    return observed_psa_keys == expected_psa_keys and all(
        labels.get(key) == value for key, value in expected.items()
    )


def labels_with_exact_profile(
    namespace: str, labels: Mapping[str, str]
) -> dict[str, str]:
    retained = {
        key: value
        for key, value in labels.items()
        if not key.startswith(POD_SECURITY_LABEL_PREFIX)
    }
    retained.update(profile_labels(namespace))
    return retained


def namespace_inventory(document: dict[str, Any]) -> dict[str, NamespaceRecord]:
    items = document.get("items")
    if not isinstance(items, list):
        raise NamespaceContractError(
            "Kubernetes Namespace inventory items must be an array"
        )
    result: dict[str, NamespaceRecord] = {}
    seen_uids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("metadata"), dict):
            raise NamespaceContractError(
                "Kubernetes Namespace metadata must be an object"
            )
        if item.get("apiVersion") != "v1" or item.get("kind") != "Namespace":
            raise NamespaceContractError("Kubernetes Namespace record is invalid")
        metadata = item["metadata"]
        name = metadata.get("name")
        uid = metadata.get("uid")
        resource_version = metadata.get("resourceVersion")
        labels = metadata.get("labels", {})
        status = item.get("status", {})
        deletion_timestamp = metadata.get("deletionTimestamp")
        if (
            not _canonical_nonempty(name)
            or len(name) > 63
            or DNS_LABEL_PATTERN.fullmatch(name) is None
        ):
            raise NamespaceContractError("Kubernetes Namespace name is invalid")
        if not _canonical_nonempty(uid):
            raise NamespaceContractError(
                f"Kubernetes Namespace UID is invalid: {name}"
            )
        if not _canonical_nonempty(resource_version):
            raise NamespaceContractError(
                f"Kubernetes Namespace resourceVersion is invalid: {name}"
            )
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ) or any(
            not _canonical_label_key(key) or not _canonical_label_value(value)
            for key, value in labels.items()
        ):
            raise NamespaceContractError(
                "Kubernetes Namespace labels must be a string object"
            )
        if not isinstance(status, dict):
            raise NamespaceContractError(
                "Kubernetes Namespace status must be an object"
            )
        phase = status.get("phase")
        if phase is not None and not isinstance(phase, str):
            raise NamespaceContractError(
                f"Kubernetes Namespace phase is invalid: {name}"
            )
        if deletion_timestamp is not None and not isinstance(
            deletion_timestamp, str
        ):
            raise NamespaceContractError(
                f"Kubernetes Namespace deletion timestamp is invalid: {name}"
            )
        if name in result:
            raise NamespaceContractError(
                f"Kubernetes Namespace inventory duplicates {name}"
            )
        if uid in seen_uids:
            raise NamespaceContractError(
                f"Kubernetes Namespace inventory duplicates UID {uid}"
            )
        seen_uids.add(uid)
        result[name] = NamespaceRecord(
            uid=uid,
            resource_version=resource_version,
            labels=dict(labels),
            phase=phase,
            deletion_timestamp=deletion_timestamp,
        )
    return result


def namespace_record(document: dict[str, Any], *, expected_name: str) -> NamespaceRecord:
    if document.get("apiVersion") != "v1" or document.get("kind") != "Namespace":
        raise NamespaceContractError(
            f"Kubernetes Namespace record is invalid: {expected_name}"
        )
    inventory = namespace_inventory({"items": [document]})
    if set(inventory) != {expected_name}:
        raise NamespaceContractError(
            f"Kubernetes Namespace identity is invalid: {expected_name}"
        )
    return inventory[expected_name]


def validate_namespace_record(
    namespace: str,
    record: NamespaceRecord,
    *,
    expected_uid: str | None = None,
    require_canonical_uid: bool = False,
    require_profile: bool = True,
) -> NamespaceRecord:
    if expected_uid is not None and record.uid != expected_uid:
        raise NamespaceContractError(
            f"Kubernetes Namespace identity changed: {namespace}"
        )
    if require_canonical_uid:
        try:
            parsed_uid = UUID(record.uid)
        except ValueError as exc:
            raise NamespaceContractError(
                f"Kubernetes Namespace UID is invalid: {namespace}"
            ) from exc
        if str(parsed_uid) != record.uid:
            raise NamespaceContractError(
                f"Kubernetes Namespace UID is invalid: {namespace}"
            )
    if record.deletion_timestamp is not None or record.phase != "Active":
        raise NamespaceContractError(
            f"Kubernetes Namespace must be exactly Active: {namespace}"
        )
    if record.labels.get(NAMESPACE_OWNER_LABEL) != NAMESPACE_OWNER:
        raise NamespaceContractError(
            f"Kubernetes Namespace owner is invalid: {namespace}"
        )
    if require_profile and not profile_matches(namespace, record.labels):
        raise NamespaceContractError(
            f"Kubernetes Namespace profile is invalid: {namespace}"
        )
    return record


def validate_namespace_document(
    document: dict[str, Any],
    *,
    namespace: str,
    expected_uid: str | None = None,
    require_canonical_uid: bool = False,
    require_profile: bool = True,
) -> NamespaceRecord:
    return validate_namespace_record(
        namespace,
        namespace_record(document, expected_name=namespace),
        expected_uid=expected_uid,
        require_canonical_uid=require_canonical_uid,
        require_profile=require_profile,
    )


def validate_namespace_json(
    raw: bytes | str,
    *,
    namespace: str,
    expected_uid: str | None = None,
    require_canonical_uid: bool = False,
    require_profile: bool = True,
) -> NamespaceRecord:
    return validate_namespace_document(
        load_json_document(raw, f"Kubernetes Namespace {namespace}"),
        namespace=namespace,
        expected_uid=expected_uid,
        require_canonical_uid=require_canonical_uid,
        require_profile=require_profile,
    )


def _run_kubectl(command: list[str]) -> bytes:
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError as exc:
        raise NamespaceContractError(
            "Kubernetes Namespace validation command is unavailable"
        ) from exc
    if result.returncode != 0:
        raise NamespaceContractError("Kubernetes Namespace query failed")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("validate", nargs="?")
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", choices=sorted(NAMESPACE_PROFILES), required=True)
    parser.add_argument("--expected-uid", required=True)
    arguments = parser.parse_args()
    if arguments.validate not in (None, "validate"):
        parser.error("only the validate action is supported")
    if not arguments.kubeconfig.is_absolute():
        parser.error("kubeconfig must use an absolute path")
    if not arguments.context or arguments.context != arguments.context.strip():
        parser.error("an exact Kubernetes context is required")
    try:
        raw = _run_kubectl(
            [
                "kubectl",
                "--kubeconfig",
                str(arguments.kubeconfig),
                "--context",
                arguments.context,
                "get",
                "namespace",
                arguments.namespace,
                "--output=json",
            ]
        )
        validate_namespace_json(
            raw,
            namespace=arguments.namespace,
            expected_uid=arguments.expected_uid,
        )
    except NamespaceContractError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
