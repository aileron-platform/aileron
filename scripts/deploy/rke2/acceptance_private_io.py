#!/usr/bin/env python3
"""Apply the installer-owned private I/O contract to acceptance artifacts."""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, NamedTuple

SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def _load_private_input() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_private_input",
        SCRIPT_DIRECTORY / "private_input.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("acceptance private I/O dependency is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input()
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^run-[a-z0-9][a-z0-9-]{6,57}[a-z0-9]$")
RAW_KUBECONFIG_NAME = "kubeconfig.raw"
FLATTENED_KUBECONFIG_NAME = "kubeconfig"


class CanonicalKubeconfig(NamedTuple):
    path: Path
    selected_identity_sha256: str


def canonical_json(value: Any) -> bytes:
    """Serialize one deterministic JSON value without non-standard numbers."""

    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def load_json_object(
    content: bytes,
    description: str,
    *,
    error_type: type[Exception],
    require_canonical: bool,
) -> dict[str, Any]:
    """Load strict UTF-8 JSON, rejecting duplicate keys at every depth."""

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError("duplicate JSON object key")
            document[key] = value
        return document

    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-standard JSON number: {value}")

    try:
        text = content.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise error_type(f"{description} is invalid JSON") from exc
    if not isinstance(document, dict):
        raise error_type(f"{description} must be an object")
    try:
        canonical = canonical_json(document) + b"\n"
    except (TypeError, ValueError) as exc:
        raise error_type(f"{description} is invalid JSON") from exc
    if require_canonical and content != canonical:
        raise error_type(f"{description} is not canonical JSON")
    return document


def evidence_directory(
    *,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
    error_type: type[Exception],
) -> Path:
    """Derive the sole private directory for one commit-bound deployment run."""

    if (
        FULL_SHA.fullmatch(commit) is None
        or RUN_ID.fullmatch(deployment_run_id) is None
    ):
        raise error_type("acceptance evidence identity is invalid")
    try:
        root = PRIVATE_INPUT.private_root_path(private_root)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc
    return root / "evidence" / commit / deployment_run_id


def _create_private_child(
    *,
    parent: Path,
    name: str,
    private_root: Path,
    error_type: type[Exception],
) -> Path:
    destination = parent / name
    try:
        parent_descriptor = os.open(
            parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
    except OSError as exc:
        raise error_type("acceptance evidence parent directory is unavailable") from exc
    created = False
    try:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
            created = True
        except FileExistsError:
            pass
        PRIVATE_INPUT.validate_private_directory(
            destination,
            "acceptance evidence directory",
            private_root=private_root,
        )
        if created:
            os.fsync(parent_descriptor)
    except (OSError, PRIVATE_INPUT.PrivateInputError) as exc:
        if created:
            try:
                os.rmdir(name, dir_fd=parent_descriptor)
            except OSError:
                pass
        raise error_type("acceptance evidence directory cannot be created") from exc
    finally:
        os.close(parent_descriptor)
    return destination


def ensure_evidence_directory(
    *,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
    error_type: type[Exception],
) -> Path:
    """Create and fsync the fixed owner-only directory hierarchy for one run."""

    expected = evidence_directory(
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=error_type,
    )
    current = private_root
    for component in ("evidence", commit, deployment_run_id):
        current = _create_private_child(
            parent=current,
            name=component,
            private_root=private_root,
            error_type=error_type,
        )
    if current != expected:
        raise error_type("acceptance evidence directory identity is invalid")
    return current


def validate_evidence_directory(
    path: Path,
    *,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
    error_type: type[Exception],
) -> Path:
    """Validate one existing directory against its exact commit and run identity."""

    expected = evidence_directory(
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=error_type,
    )
    if path != expected:
        raise error_type("acceptance evidence directory identity does not match")
    return validate_private_directory(
        path,
        "acceptance evidence directory",
        private_root=private_root,
        error_type=error_type,
    )


def read_private_bytes(
    path: Path,
    description: str,
    *,
    private_root: Path,
    error_type: type[Exception],
    maximum_size: int,
    require_nonempty: bool = False,
) -> bytes:
    """Read one acceptance artifact through the canonical stable-read gate."""

    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=private_root,
            require_nonempty=require_nonempty,
            maximum_size=maximum_size,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc


def write_private_snapshot(
    *,
    destination: Path,
    content: bytes,
    description: str,
    private_root: Path,
    error_type: type[Exception],
    allow_existing_exact: bool = False,
) -> Path:
    """Write one acceptance artifact through the canonical durable-write gate."""

    try:
        return PRIVATE_INPUT.write_private_snapshot(
            destination=destination,
            content=content,
            description=description,
            private_root=private_root,
            allow_existing_exact=allow_existing_exact,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc


def validate_private_directory(
    path: Path,
    description: str,
    *,
    private_root: Path,
    error_type: type[Exception],
) -> Path:
    """Validate an installer-owned acceptance directory and all of its parents."""

    try:
        return PRIVATE_INPUT.validate_private_directory(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc


def validate_canonical_kubeconfig(
    *,
    directory: Path,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
    context: str,
    error_type: type[Exception],
) -> CanonicalKubeconfig:
    """Validate the fixed raw/flattened identity pair for one acceptance run."""

    validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=error_type,
    )
    raw_path = directory / RAW_KUBECONFIG_NAME
    flattened_path = directory / FLATTENED_KUBECONFIG_NAME
    try:
        raw_identity = PRIVATE_INPUT.validate_self_contained_kubeconfig(
            read_private_bytes(
                raw_path,
                "raw acceptance kubeconfig snapshot",
                private_root=private_root,
                error_type=error_type,
                maximum_size=4 * 1024 * 1024,
                require_nonempty=True,
            ),
            expected_context=context,
            description="raw acceptance kubeconfig snapshot",
            require_minified=False,
        )
        flattened_identity = PRIVATE_INPUT.validate_self_contained_kubeconfig(
            read_private_bytes(
                flattened_path,
                "flattened acceptance kubeconfig snapshot",
                private_root=private_root,
                error_type=error_type,
                maximum_size=4 * 1024 * 1024,
                require_nonempty=True,
            ),
            expected_context=context,
            description="flattened acceptance kubeconfig snapshot",
            require_minified=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc
    if raw_identity != flattened_identity:
        raise error_type("flattened kubeconfig selected identity changed")
    return CanonicalKubeconfig(flattened_path, flattened_identity)


def snapshot_canonical_kubeconfig(
    *,
    source: Path,
    directory: Path,
    private_root: Path,
    commit: str,
    deployment_run_id: str,
    context: str,
    runner: Any,
    error_type: type[Exception],
) -> CanonicalKubeconfig:
    """Create or exactly resume the run-bound raw and flattened snapshots."""

    validate_evidence_directory(
        directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        error_type=error_type,
    )
    try:
        PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=source,
            raw_destination=directory / RAW_KUBECONFIG_NAME,
            flattened_destination=directory / FLATTENED_KUBECONFIG_NAME,
            context=context,
            runner=runner,
            private_root=private_root,
            allow_existing_exact=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise error_type(str(exc)) from exc
    return validate_canonical_kubeconfig(
        directory=directory,
        private_root=private_root,
        commit=commit,
        deployment_run_id=deployment_run_id,
        context=context,
        error_type=error_type,
    )
