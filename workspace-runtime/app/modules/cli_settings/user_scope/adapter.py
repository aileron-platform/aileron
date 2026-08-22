"""Target client adapter seam for Marketplace user-copy profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from aileron_marketplace_core import (
    PackageSourceError,
    decode_json_pointer as decode_core_json_pointer,
    validate_logical_target_locator,
    validate_source_locator,
    validate_wire_identity,
)

from .models import UserScopeAgent


class UserCopyTargetKind(str, Enum):
    """Runtime target shapes supported by the materializer."""

    FILE = "file"
    DIRECTORY = "directory"
    CONFIG_ENTRY = "config-entry"


class UserCopyOperation(str, Enum):
    """Deterministic operation exposed by a materialization plan."""

    CREATE = "create"
    MERGE = "merge"


class StructuredDocumentKind(str, Enum):
    """Structured document codecs supported by user-copy."""

    JSON = "json"
    TOML = "toml"


class StructuredEntryMode(str, Enum):
    """Exact structured entry mutation modes."""

    MAPPING_ENTRY = "mapping-entry"
    LIST_ENTRY = "list-entry"


@dataclass(frozen=True)
class CoreProfileResource:
    """Runtime-owned view of one shared-core profile resource."""

    resource_type: str
    resource_id: str
    source_kind: str
    source_locator: str
    target_resource: str
    copy_semantics: str
    relative_target: str | None
    json_pointer: str | None


@dataclass(frozen=True)
class ResolvedUserCopyTarget:
    """Typed target_client target produced without package-defined paths."""

    agent: UserScopeAgent
    target_kind: UserCopyTargetKind
    operation: UserCopyOperation
    runtime_path: Path
    logical_locator: str
    normalized_identity: str
    structured_document: StructuredDocumentKind | None = None
    structured_entry_mode: StructuredEntryMode | None = None
    structured_parent: tuple[str, ...] = ()
    structured_entry_id: str | None = None


class TargetClientUserScopeAdapter(Protocol):
    """Target client target adapter contract consumed by the planner."""

    @property
    def target_client(self) -> str:
        """Return the canonical target_client identifier."""

    @property
    def agent(self) -> UserScopeAgent:
        """Return the user-scope agent whose paths are targeted."""

    @property
    def placeholder_tokens(self) -> tuple[str, ...]:
        """Return target_client-owned package-root placeholder tokens."""

    def resolve_target(
        self,
        resource: CoreProfileResource,
        *,
        source_value: Any | None,
        source_digest: str | None = None,
    ) -> ResolvedUserCopyTarget:
        """Resolve one validated core profile resource to a runtime target."""


class UserCopyAdapterError(ValueError):
    """A profile resource cannot be mapped to a safe target_client target."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def enum_value(value: Any) -> str:
    """Adapt shared-core enums through one explicit compatibility seam."""

    raw = getattr(value, "value", value)
    if not isinstance(raw, str) or not raw:
        raise UserCopyAdapterError("profile-contract-invalid", repr(value))
    return raw


def validate_sha256_digest(value: str) -> str:
    """Return one canonical lowercase SHA-256 digest or reject it."""

    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise UserCopyAdapterError("source-reference-invalid", str(value))
    return value


def normalize_package_locator(value: str) -> PurePosixPath:
    """Validate a package-relative logical source or target locator."""

    try:
        canonical = validate_source_locator(value)
    except PackageSourceError as exc:
        raise UserCopyAdapterError(
            "source-reference-invalid",
            value,
        ) from exc
    return PurePosixPath(canonical)


def safe_relative_target(
    value: str | None,
    *,
    expected_suffix: str | None = None,
) -> PurePosixPath:
    """Validate a profile-derived relative target below a typed root."""

    if value is None:
        raise UserCopyAdapterError("relative-target-required", "")
    target = normalize_package_locator(value)
    if expected_suffix is not None and target.suffix != expected_suffix:
        raise UserCopyAdapterError("source-not-allowed", value)
    return target


def resolve_below(root: Path, relative: PurePosixPath) -> Path:
    """Resolve a validated POSIX locator below a typed runtime root."""

    candidate = root.joinpath(*relative.parts)
    try:
        candidate.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise UserCopyAdapterError(
            "target-root-escape",
            relative.as_posix(),
        ) from exc
    return candidate


def logical_child(root_locator: str, relative: PurePosixPath) -> str:
    """Append a relative locator to a sanitized logical user locator."""

    return f"{root_locator.rstrip('/')}/{relative.as_posix()}"


def normalized_file_identity(logical_locator: str) -> str:
    """Return the normalized identity used for duplicate target checks."""

    try:
        validate_logical_target_locator(logical_locator)
        return validate_wire_identity(f"file:{logical_locator}")
    except PackageSourceError as exc:
        raise UserCopyAdapterError(
            "target-root-escape",
            logical_locator,
        ) from exc


def normalized_config_identity(
    logical_locator: str,
    parent: tuple[str, ...],
    entry_id: str,
) -> str:
    """Return a structured entry identity without exposing runtime paths."""

    pointer = "/".join((*parent, entry_id))
    try:
        validate_logical_target_locator(logical_locator)
        return validate_wire_identity(f"config-entry:{logical_locator}#{pointer}")
    except PackageSourceError as exc:
        raise UserCopyAdapterError(
            "target-root-escape",
            logical_locator,
        ) from exc


def decode_json_pointer(pointer: str | None) -> tuple[str, ...]:
    """Decode an RFC 6901 JSON pointer used by the shared-core resolver."""

    try:
        return decode_core_json_pointer(pointer)
    except PackageSourceError as exc:
        raise UserCopyAdapterError(exc.code, pointer or "") from exc


def extract_json_pointer(document: Any, pointer: str | None) -> Any:
    """Extract an exact JSON pointer without fuzzy lookup."""

    current = document
    for part in decode_json_pointer(pointer):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(current):
                current = current[index]
                continue
        raise UserCopyAdapterError(
            "source-reference-invalid",
            pointer or "",
        )
    return current


def canonical_value_digest(value: Any) -> str:
    """Hash a JSON-compatible structured value deterministically."""

    from hashlib import sha256

    try:
        content = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise UserCopyAdapterError(
            "source-document-invalid",
            type(value).__name__,
        ) from exc
    return sha256(content).hexdigest()


def rewrite_known_placeholders(
    value: Any,
    *,
    tokens: tuple[str, ...],
    payload_root: Path | None,
    validate_payload_reference: bool = False,
) -> tuple[Any, bool]:
    """Rewrite only target_client-declared leading placeholder tokens."""

    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        used = False
        for key, child in value.items():
            if any(token in str(key) for token in tokens):
                raise UserCopyAdapterError(
                    "placeholder-reference-invalid",
                    str(key),
                )
            next_value, child_used = rewrite_known_placeholders(
                child,
                tokens=tokens,
                payload_root=payload_root,
                validate_payload_reference=validate_payload_reference,
            )
            rewritten[str(key)] = next_value
            used = used or child_used
        return rewritten, used
    if isinstance(value, list):
        rewritten_items: list[Any] = []
        used = False
        for child in value:
            next_value, child_used = rewrite_known_placeholders(
                child,
                tokens=tokens,
                payload_root=payload_root,
                validate_payload_reference=validate_payload_reference,
            )
            rewritten_items.append(next_value)
            used = used or child_used
        return rewritten_items, used
    if not isinstance(value, str):
        return value, False

    for token in sorted(tokens, key=len, reverse=True):
        if value == token:
            if payload_root is None:
                raise UserCopyAdapterError("dependency-payload-required", token)
            if validate_payload_reference and not payload_root.is_dir():
                raise UserCopyAdapterError(
                    "dependency-payload-reference-invalid",
                    token,
                )
            return str(payload_root), True
        prefix = f"{token}/"
        if value.startswith(prefix):
            if payload_root is None:
                raise UserCopyAdapterError("dependency-payload-required", token)
            suffix = value.removeprefix(prefix)
            relative = normalize_package_locator(suffix)
            candidate = payload_root.joinpath(*relative.parts)
            if validate_payload_reference:
                try:
                    candidate.resolve(strict=True).relative_to(
                        payload_root.resolve(strict=True)
                    )
                except (OSError, ValueError) as exc:
                    raise UserCopyAdapterError(
                        "dependency-payload-reference-invalid",
                        value,
                    ) from exc
            return str(candidate), True
    for token in tokens:
        if token in value:
            raise UserCopyAdapterError("placeholder-reference-invalid", value)
    return value, False
