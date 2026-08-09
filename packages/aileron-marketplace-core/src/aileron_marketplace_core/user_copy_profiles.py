from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from .claude_resources import resolve_claude_plugin_resources
from .codex_resources import resolve_codex_plugin_resources
from .package_tree import PackageTreeError, package_tree_digest
from .provider_resources import MarketplaceProviderName, provider_resource_name_contract
from .resource_resolution import (
    PackageSourceError,
    decode_json_pointer,
    normalize_source_locator,
    read_package_json_object,
    resolve_package_source,
    validate_wire_identity,
)

USER_COPY_PROFILE_VERSION = 1
USER_COPY_PAYLOAD_ROOT_SENTINEL = "__AILERON_USER_COPY_PAYLOAD_ROOT__"
_MAX_STRUCTURED_TEMPLATE_BYTES = 256 * 1024
_MAX_STRUCTURED_TEMPLATE_DEPTH = 32
_MAX_STRUCTURED_TEMPLATE_NODES = 2_000
_MAX_STRUCTURED_TEMPLATE_STRING_BYTES = 16 * 1024
_MAX_USER_COPY_FIELD_LENGTH = 1024
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class UserCopyResourceType(str, Enum):
    INSTRUCTIONS = "instructions"
    SKILL = "skill"
    SUBAGENT = "subagent"
    COMMAND = "command"
    OUTPUT_STYLE = "output-style"
    PROMPT = "prompt"
    RULE = "rule"
    MCP = "mcp"
    HOOK = "hook"


class UserCopyTargetResource(str, Enum):
    AGENTS_MD = "agents_md"
    CLAUDE_MD = "claude_md"
    SKILLS = "skills"
    SUBAGENTS = "subagents"
    COMMANDS = "commands"
    OUTPUT_STYLES = "output_styles"
    PROMPTS = "prompts"
    RULES = "rules"
    MCP = "mcp"
    HOOKS = "hooks"


class UserCopySourceKind(str, Enum):
    PLUGIN_COMPONENT = "plugin-component"
    COPY_CONVENTION = "copy-convention"


class UserCopyDependencyPayloadKind(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class UserCopySemantics(str, Enum):
    CREATE_FILE = "create-file"
    CREATE_DIRECTORY = "create-directory"
    MERGE_CONFIG_ENTRY = "merge-config-entry"


class UserCopyBlockReason(str, Enum):
    SOURCE_NOT_ALLOWED = "source-not-allowed"
    SOURCE_REFERENCE_INVALID = "source-reference-invalid"
    SOURCE_DOCUMENT_INVALID = "source-document-invalid"
    SOURCE_MISSING = "source-missing"
    DUPLICATE_RESOURCE_ID = "duplicate-resource-id"
    UNSUPPORTED_RESOURCE = "unsupported-resource"


@dataclass(frozen=True)
class UserCopySourceRule:
    resource_type: UserCopyResourceType
    source_pattern: str


@dataclass(frozen=True)
class UserCopyDependencyPayload:
    """One exact package-relative dependency copied to stable user scope."""

    source_locator: str
    source_kind: UserCopyDependencyPayloadKind
    content_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, UserCopyDependencyPayloadKind):
            raise TypeError(
                "source_kind must be UserCopyDependencyPayloadKind"
            )
        if normalize_source_locator(self.source_locator) != self.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )
        if (
            not isinstance(self.content_digest, str)
            or len(self.content_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.content_digest
            )
        ):
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )

    def canonical_dict(self) -> dict[str, str]:
        return {
            "sourceLocator": self.source_locator,
            "sourceKind": self.source_kind.value,
            "contentDigest": self.content_digest,
        }


USER_COPY_SOURCE_ALLOWLIST: dict[
    MarketplaceProviderName,
    tuple[UserCopySourceRule, ...],
] = {
    "claude-code": (
        UserCopySourceRule(UserCopyResourceType.INSTRUCTIONS, "CLAUDE.md"),
        UserCopySourceRule(UserCopyResourceType.SKILL, "skills/<stable-id>/**"),
        UserCopySourceRule(UserCopyResourceType.SUBAGENT, "agents/**/*.md"),
        UserCopySourceRule(UserCopyResourceType.COMMAND, "commands/**/*.md"),
        UserCopySourceRule(
            UserCopyResourceType.OUTPUT_STYLE,
            "output-styles/**/*.md",
        ),
        UserCopySourceRule(
            UserCopyResourceType.MCP,
            "canonical-claude-mcp-owner",
        ),
        UserCopySourceRule(
            UserCopyResourceType.HOOK,
            "canonical-claude-hook-owner",
        ),
    ),
    "codex": (
        UserCopySourceRule(UserCopyResourceType.INSTRUCTIONS, "AGENTS.md"),
        UserCopySourceRule(UserCopyResourceType.SKILL, "skills/<stable-id>/**"),
        UserCopySourceRule(UserCopyResourceType.SUBAGENT, "agents/*.toml"),
        UserCopySourceRule(UserCopyResourceType.PROMPT, "prompts/**/*.md"),
        UserCopySourceRule(UserCopyResourceType.RULE, "rules/*.rules"),
        UserCopySourceRule(
            UserCopyResourceType.MCP,
            "canonical-codex-mcp-owner",
        ),
        UserCopySourceRule(
            UserCopyResourceType.HOOK,
            "canonical-codex-hook-owner",
        ),
    ),
}


@dataclass(frozen=True)
class UserCopyResource:
    resource_type: UserCopyResourceType
    resource_id: str
    source_kind: UserCopySourceKind
    source_locator: str
    target_resource: UserCopyTargetResource
    copy_semantics: UserCopySemantics
    relative_target: str | None = None
    json_pointer: str | None = None

    def __post_init__(self) -> None:
        typed_fields = (
            (self.resource_type, UserCopyResourceType, "resource_type"),
            (self.source_kind, UserCopySourceKind, "source_kind"),
            (self.target_resource, UserCopyTargetResource, "target_resource"),
            (self.copy_semantics, UserCopySemantics, "copy_semantics"),
        )
        for value, enum_type, field_name in typed_fields:
            if not isinstance(value, enum_type):
                raise TypeError(f"{field_name} must be {enum_type.__name__}")
        validate_wire_identity(self.resource_id)
        if normalize_source_locator(self.source_locator) != self.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )
        if (
            self.relative_target is not None
            and normalize_source_locator(self.relative_target)
            != self.relative_target
        ):
            raise PackageSourceError(
                "source-reference-invalid",
                self.relative_target,
            )

    def canonical_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "resourceType": self.resource_type.value,
            "resourceId": self.resource_id,
            "sourceKind": self.source_kind.value,
            "sourceLocator": self.source_locator,
            "targetResource": self.target_resource.value,
            "copySemantics": self.copy_semantics.value,
        }
        if self.relative_target is not None:
            result["relativeTarget"] = self.relative_target
        if self.json_pointer is not None:
            result["jsonPointer"] = self.json_pointer
        return result


@dataclass(frozen=True)
class BlockedUserCopyResource:
    resource_type: str
    source_locator: str
    reason: UserCopyBlockReason

    def __post_init__(self) -> None:
        validate_wire_identity(self.resource_type)
        if normalize_source_locator(self.source_locator) != self.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )
        if not isinstance(self.reason, UserCopyBlockReason):
            raise TypeError("reason must be UserCopyBlockReason")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "resourceType": self.resource_type,
            "sourceLocator": self.source_locator,
            "reason": self.reason.value,
        }


@dataclass(frozen=True)
class UserCopyProfile:
    provider: MarketplaceProviderName
    resources: tuple[UserCopyResource, ...]
    blocked_resources: tuple[BlockedUserCopyResource, ...] = ()
    profile_version: int = USER_COPY_PROFILE_VERSION

    @property
    def compatible(self) -> bool:
        return bool(self.resources) and not self.blocked_resources

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "profileVersion": self.profile_version,
            "provider": self.provider,
            "resources": [resource.canonical_dict() for resource in self.resources],
            "blockedResources": [
                resource.canonical_dict() for resource in self.blocked_resources
            ],
        }

    @property
    def profile_digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UserCopySourceSnapshot:
    """Validated profile, preview, and tree digest for one immutable source."""

    profile: UserCopyProfile
    preview: dict[str, Any]
    package_tree_digest: str


def build_user_copy_profile_preview(
    package_root: Path,
    profile: UserCopyProfile,
) -> dict[str, Any]:
    """Build sanitized source proofs for read-only Runtime preflight.

    The preview carries only bounded structured templates with an opaque payload
    root sentinel. Runtime apply rebuilds exact values and proofs from the
    authenticated sparse ZIP snapshot.
    """

    resolved_profile = resolve_user_copy_profile(profile.provider, package_root)
    if resolved_profile.profile_digest != profile.profile_digest:
        raise PackageSourceError("source-profile-mismatch", ".")
    return _build_user_copy_profile_preview(package_root, profile)


def _build_user_copy_profile_preview(
    package_root: Path,
    profile: UserCopyProfile,
) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    dependency_payloads: list[UserCopyDependencyPayload] = []
    for resource in profile.resources:
        source_path = resolve_package_source(
            package_root,
            resource.source_locator,
            require_file=(
                resource.copy_semantics is not UserCopySemantics.CREATE_DIRECTORY
            ),
        )
        source_value: Any | None = None
        if resource.copy_semantics is UserCopySemantics.MERGE_CONFIG_ENTRY:
            source_value = _structured_source_value(
                package_root,
                source_path,
                resource.json_pointer,
            )
        proof = resource.canonical_dict()
        proof["sourceDigest"] = _user_copy_source_digest(
            source_path,
            resource.copy_semantics,
            source_value,
        )
        payload_required = False
        payload_projectable = True
        resource_payloads: tuple[UserCopyDependencyPayload, ...] = ()
        if resource.copy_semantics is UserCopySemantics.MERGE_CONFIG_ENTRY:
            (
                payload_required,
                payload_projectable,
                resource_payloads,
            ) = _inspect_dependency_payloads(
                source_value,
                provider=profile.provider,
                package_root=package_root,
            )
        proof["dependencyPayloadRequired"] = payload_required
        proof["dependencyPayloadProjectable"] = payload_projectable
        if resource.copy_semantics is UserCopySemantics.MERGE_CONFIG_ENTRY:
            proof["structuredValueType"] = _json_value_type(source_value)
        if payload_required and payload_projectable:
            proof["structuredValueTemplate"] = _structured_value_template(
                source_value,
                provider=profile.provider,
            )
        resources.append(proof)
        dependency_payloads.extend(resource_payloads)

    return {
        "profileVersion": profile.profile_version,
        "provider": profile.provider,
        "profileDigest": profile.profile_digest,
        "resources": resources,
        "dependencyPayloads": [
            payload.canonical_dict()
            for payload in _canonical_dependency_payloads(dependency_payloads)
        ],
        "blockedResources": [
            resource.canonical_dict() for resource in profile.blocked_resources
        ],
    }


def user_copy_source_digest_from_preview(
    preview: Mapping[str, Any],
) -> str:
    """Hash the canonical user-copy source proof shared by Manager and Runtime."""

    try:
        profile_version = preview["profileVersion"]
        provider = preview["provider"]
        profile_digest = preview["profileDigest"]
        raw_resources = preview["resources"]
        raw_dependency_payloads = preview["dependencyPayloads"]
        raw_blocked = preview.get("blockedResources", [])
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageSourceError("source-profile-mismatch", ".") from exc
    if (
        type(profile_version) is not int
        or profile_version != USER_COPY_PROFILE_VERSION
        or not isinstance(provider, str)
        or provider not in {"claude-code", "codex"}
        or not isinstance(profile_digest, str)
        or len(profile_digest) != 64
        or any(character not in "0123456789abcdef" for character in profile_digest)
        or not isinstance(raw_resources, list)
        or not isinstance(raw_dependency_payloads, list)
        or not isinstance(raw_blocked, list)
    ):
        raise PackageSourceError("source-profile-mismatch", ".")

    resources: list[dict[str, Any]] = []
    template_payload_locators: set[str] = set()
    for raw in raw_resources:
        if not isinstance(raw, Mapping):
            raise PackageSourceError("source-profile-mismatch", ".")
        source_digest = raw.get("sourceDigest")
        dependency_required = raw.get("dependencyPayloadRequired")
        dependency_projectable = raw.get("dependencyPayloadProjectable")
        if (
            not isinstance(source_digest, str)
            or len(source_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in source_digest
            )
            or type(dependency_required) is not bool
            or type(dependency_projectable) is not bool
        ):
            raise PackageSourceError("source-profile-mismatch", ".")
        try:
            resource_type = raw["resourceType"]
            resource_id = raw["resourceId"]
            source_kind = raw["sourceKind"]
            source_locator = raw["sourceLocator"]
            try:
                validate_wire_identity(resource_id)
                canonical_source_locator = normalize_source_locator(
                    source_locator
                )
            except PackageSourceError as exc:
                raise PackageSourceError(
                    "source-profile-mismatch",
                    ".",
                ) from exc
            if (
                not isinstance(resource_type, str)
                or resource_type
                not in {
                    "instructions",
                    "skill",
                    "subagent",
                    "command",
                    "output-style",
                    "prompt",
                    "rule",
                    "mcp",
                    "hook",
                }
                or not isinstance(resource_id, str)
                or not 1 <= len(resource_id) <= _MAX_USER_COPY_FIELD_LENGTH
                or source_kind
                not in {"plugin-component", "copy-convention"}
                or not isinstance(source_locator, str)
                or len(source_locator) > _MAX_USER_COPY_FIELD_LENGTH
                or canonical_source_locator != source_locator
            ):
                raise PackageSourceError("source-profile-mismatch", ".")
            resources.append(
                {
                    "resourceType": resource_type,
                    "resourceId": resource_id,
                    "sourceKind": source_kind,
                    "sourceLocator": source_locator,
                    "sourceDigest": source_digest,
                    "dependencyPayloadRequired": dependency_required,
                    "dependencyPayloadProjectable": dependency_projectable,
                }
            )
            structured_value_type = raw.get("structuredValueType")
            if structured_value_type is not None:
                if structured_value_type not in {
                    "object",
                    "array",
                    "string",
                    "number",
                    "boolean",
                    "null",
                }:
                    raise PackageSourceError("source-profile-mismatch", ".")
                resources[-1]["structuredValueType"] = structured_value_type
            template_present = "structuredValueTemplate" in raw
            structured_value_template = raw.get("structuredValueTemplate")
            if template_present:
                if not dependency_required or not dependency_projectable:
                    raise PackageSourceError("source-profile-mismatch", ".")
                _validate_structured_template(structured_value_template)
                if (
                    _json_value_type(structured_value_template)
                    != structured_value_type
                    or not _contains_payload_sentinel(
                        structured_value_template
                    )
                ):
                    raise PackageSourceError("source-profile-mismatch", ".")
                resources[-1]["structuredValueTemplate"] = (
                    structured_value_template
                )
                template_payload_locators.update(
                    _template_payload_locators(structured_value_template)
                )
            elif dependency_required and dependency_projectable:
                raise PackageSourceError("source-profile-mismatch", ".")
        except KeyError as exc:
            raise PackageSourceError("source-profile-mismatch", ".") from exc

    dependency_payloads: list[dict[str, str]] = []
    for raw in raw_dependency_payloads:
        if (
            not isinstance(raw, Mapping)
            or set(raw)
            != {"sourceLocator", "sourceKind", "contentDigest"}
            or raw.get("sourceKind") not in {"file", "directory"}
        ):
            raise PackageSourceError("source-profile-mismatch", ".")
        source_locator = raw.get("sourceLocator")
        content_digest = raw.get("contentDigest")
        try:
            canonical_source_locator = normalize_source_locator(
                source_locator
            )
        except PackageSourceError as exc:
            raise PackageSourceError(
                "source-profile-mismatch",
                ".",
            ) from exc
        if (
            not isinstance(source_locator, str)
            or len(source_locator) > _MAX_USER_COPY_FIELD_LENGTH
            or canonical_source_locator != source_locator
            or not isinstance(content_digest, str)
            or len(content_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in content_digest
            )
        ):
            raise PackageSourceError("source-profile-mismatch", ".")
        dependency_payloads.append(
            {
                "sourceLocator": source_locator,
                "sourceKind": raw["sourceKind"],
                "contentDigest": content_digest,
            }
        )
    if dependency_payloads != sorted(
        dependency_payloads,
        key=lambda item: (item["sourceLocator"], item["sourceKind"]),
    ) or len(
        {item["sourceLocator"].casefold() for item in dependency_payloads}
    ) != len(
        dependency_payloads
    ):
        raise PackageSourceError("source-profile-mismatch", ".")
    if not _dependency_payload_coverage_valid(
        template_payload_locators,
        dependency_payloads,
    ):
        raise PackageSourceError("source-profile-mismatch", ".")

    blocked: list[dict[str, str]] = []
    for raw in raw_blocked:
        if not isinstance(raw, Mapping) or set(raw) != {
            "resourceType",
            "sourceLocator",
            "reason",
        }:
            raise PackageSourceError("source-profile-mismatch", ".")
        try:
            resource_type = raw["resourceType"]
            source_locator = raw["sourceLocator"]
            reason = raw["reason"]
            validate_wire_identity(resource_type)
            canonical_source_locator = normalize_source_locator(
                source_locator
            )
            if (
                canonical_source_locator != source_locator
                or reason
                not in {
                    "source-not-allowed",
                    "source-reference-invalid",
                    "source-document-invalid",
                    "source-missing",
                    "duplicate-resource-id",
                    "unsupported-resource",
                }
            ):
                raise PackageSourceError("source-profile-mismatch", ".")
            blocked.append(
                {
                    "resourceType": resource_type,
                    "sourceLocator": source_locator,
                    "reason": reason,
                }
            )
        except (KeyError, PackageSourceError) as exc:
            raise PackageSourceError("source-profile-mismatch", ".") from exc

    payload = {
        "digestAlgorithm": "user-copy-source-sha256-v1",
        "profileVersion": profile_version,
        "provider": provider,
        "profileDigest": profile_digest,
        "resources": sorted(
            resources,
            key=lambda item: (
                item["resourceType"],
                item["resourceId"],
                item["sourceLocator"],
            ),
        ),
        "dependencyPayloads": dependency_payloads,
        "blockedResources": sorted(
            blocked,
            key=lambda item: (
                item["resourceType"],
                item["sourceLocator"],
                item["reason"],
            ),
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _json_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    raise PackageSourceError("source-document-invalid", type(value).__name__)


def _structured_source_value(
    package_root: Path,
    source_path: Path,
    pointer: str | None,
) -> Any:
    document = read_package_json_object(package_root, source_path)
    current: Any = document
    for part in decode_json_pointer(pointer):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(current):
                current = current[index]
                continue
        raise PackageSourceError(
            "source-reference-invalid",
            f"{source_path.relative_to(package_root).as_posix()}#{pointer or ''}",
        )
    return current


def _user_copy_source_digest(
    source_path: Path,
    semantics: UserCopySemantics,
    source_value: Any | None,
) -> str:
    if semantics is UserCopySemantics.CREATE_DIRECTORY:
        return _directory_tree_digest(source_path)
    if semantics is UserCopySemantics.MERGE_CONFIG_ENTRY:
        try:
            encoded = json.dumps(
                source_value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise PackageSourceError(
                "source-document-invalid",
                source_path.name,
            ) from exc
        return sha256(encoded).hexdigest()
    try:
        return sha256(source_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PackageSourceError(
            "source-reference-invalid",
            source_path.name,
        ) from exc


def _directory_tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise PackageSourceError("source-not-allowed", root.name)
    digest = sha256()
    entries = sorted(
        root.rglob("*"),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in entries:
        try:
            relative = path.relative_to(root).as_posix().encode("utf-8")
            path_stat = path.lstat()
            if path.is_symlink():
                raise PackageSourceError(
                    "source-reference-invalid",
                    relative.decode("utf-8", errors="replace"),
                )
            elif path.is_dir():
                entry_type = b"directory"
                mode = 0o700
                content = b""
            elif path.is_file():
                entry_type = b"file"
                source_mode = stat.S_IMODE(path_stat.st_mode)
                mode = 0o700 if source_mode & 0o111 else 0o600
                content = path.read_bytes()
            else:
                raise PackageSourceError(
                    "source-not-allowed",
                    relative.decode("utf-8", errors="replace"),
                )
        except OSError as exc:
            raise PackageSourceError(
                "source-reference-invalid",
                str(path),
            ) from exc
        for field in (
            entry_type,
            f"{mode:o}".encode("ascii"),
            relative,
            content,
        ):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def resolve_user_copy_dependency_payloads(
    package_root: Path,
    profile: UserCopyProfile,
) -> tuple[UserCopyDependencyPayload, ...]:
    """Resolve the canonical safe dependency closure referenced by a profile."""

    resolved_profile = resolve_user_copy_profile(profile.provider, package_root)
    if resolved_profile.profile_digest != profile.profile_digest:
        raise PackageSourceError("source-profile-mismatch", ".")
    return _resolve_user_copy_dependency_payloads(package_root, profile)


def _resolve_user_copy_dependency_payloads(
    package_root: Path,
    profile: UserCopyProfile,
) -> tuple[UserCopyDependencyPayload, ...]:
    payloads: list[UserCopyDependencyPayload] = []
    for resource in profile.resources:
        if resource.copy_semantics is not UserCopySemantics.MERGE_CONFIG_ENTRY:
            continue
        source_path = resolve_package_source(
            package_root,
            resource.source_locator,
        )
        source_value = _structured_source_value(
            package_root,
            source_path,
            resource.json_pointer,
        )
        _required, _projectable, resource_payloads = _inspect_dependency_payloads(
            source_value,
            provider=profile.provider,
            package_root=package_root,
        )
        payloads.extend(resource_payloads)
    return _canonical_dependency_payloads(payloads)


def _inspect_dependency_payloads(
    value: Any,
    *,
    provider: MarketplaceProviderName,
    package_root: Path,
) -> tuple[bool, bool, tuple[UserCopyDependencyPayload, ...]]:
    tokens = (
        ("${CLAUDE_PLUGIN_ROOT}",)
        if provider == "claude-code"
        else ("PLUGIN_ROOT", "${PLUGIN_ROOT}", "${CODEX_PLUGIN_ROOT}")
    )
    required = False
    projectable = True
    locators: list[str] = []

    def visit(current: Any) -> None:
        nonlocal required, projectable
        if isinstance(current, dict):
            for key, child in current.items():
                if any(token in str(key) for token in tokens):
                    required = True
                    projectable = False
                visit(child)
            return
        if isinstance(current, list):
            for child in current:
                visit(child)
            return
        if not isinstance(current, str):
            return

        matching_tokens = [token for token in tokens if token in current]
        if not matching_tokens:
            return
        required = True
        for token in sorted(tokens, key=len, reverse=True):
            prefix = f"{token}/"
            if not current.startswith(prefix):
                continue
            suffix = current.removeprefix(prefix)
            try:
                locator = normalize_source_locator(suffix)
            except PackageSourceError:
                projectable = False
                return
            if (
                locator != suffix
                or suffix.endswith("/")
                or "//" in suffix
                or len(locator) > _MAX_USER_COPY_FIELD_LENGTH
                or any(other in suffix for other in tokens)
            ):
                projectable = False
                return
            candidate = package_root.joinpath(*locator.split("/"))
            try:
                resolved_root = package_root.resolve(strict=True)
                resolved_candidate = candidate.resolve(strict=True)
                resolved_candidate.relative_to(resolved_root)
                relative_parts = Path(locator).parts
                path = package_root
                for part in relative_parts:
                    path = path / part
                    if path.is_symlink():
                        raise ValueError("dependency path contains a symlink")
                if candidate.is_dir() and any(
                    child.is_symlink() for child in candidate.rglob("*")
                ):
                    raise ValueError("dependency directory contains a symlink")
                if not candidate.is_file() and not candidate.is_dir():
                    raise ValueError("dependency source is not a file or directory")
            except (OSError, ValueError):
                projectable = False
                return
            locators.append(locator)
            return
        projectable = False

    visit(value)
    payloads: list[UserCopyDependencyPayload] = []
    unique_locators = set(locators)
    if len({locator.casefold() for locator in unique_locators}) != len(
        unique_locators
    ):
        projectable = False
    if projectable:
        for locator in sorted(unique_locators):
            candidate = package_root.joinpath(*Path(locator).parts)
            source_kind = (
                UserCopyDependencyPayloadKind.DIRECTORY
                if candidate.is_dir()
                else UserCopyDependencyPayloadKind.FILE
            )
            content_digest = (
                _directory_tree_digest(candidate)
                if source_kind is UserCopyDependencyPayloadKind.DIRECTORY
                else _dependency_file_digest(candidate)
            )
            payloads.append(
                UserCopyDependencyPayload(
                    source_locator=locator,
                    source_kind=source_kind,
                    content_digest=content_digest,
                )
            )
    return (
        required,
        projectable,
        _canonical_dependency_payloads(payloads),
    )


def _structured_value_template(
    value: Any,
    *,
    provider: MarketplaceProviderName,
) -> Any:
    """Replace exact provider root prefixes with one transport-safe sentinel."""

    tokens = (
        ("${CLAUDE_PLUGIN_ROOT}",)
        if provider == "claude-code"
        else ("PLUGIN_ROOT", "${PLUGIN_ROOT}", "${CODEX_PLUGIN_ROOT}")
    )

    def rewrite(current: Any) -> Any:
        if isinstance(current, dict):
            return {str(key): rewrite(child) for key, child in current.items()}
        if isinstance(current, list):
            return [rewrite(child) for child in current]
        if not isinstance(current, str):
            return current
        if USER_COPY_PAYLOAD_ROOT_SENTINEL in current:
            raise PackageSourceError("source-reference-invalid", current)
        for token in sorted(tokens, key=len, reverse=True):
            prefix = f"{token}/"
            if current.startswith(prefix):
                return (
                    f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/"
                    f"{current.removeprefix(prefix)}"
                )
        return current

    template = rewrite(value)
    _validate_structured_template(template)
    return template


def _validate_structured_template(value: Any) -> None:
    """Enforce deterministic bounds for the internal structured template."""

    node_count = 0

    def visit(current: Any, depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if (
            depth > _MAX_STRUCTURED_TEMPLATE_DEPTH
            or node_count > _MAX_STRUCTURED_TEMPLATE_NODES
        ):
            raise PackageSourceError("source-document-invalid", ".")
        if isinstance(current, dict):
            for key, child in current.items():
                if (
                    not isinstance(key, str)
                    or USER_COPY_PAYLOAD_ROOT_SENTINEL in key
                    or len(key.encode("utf-8"))
                    > _MAX_STRUCTURED_TEMPLATE_STRING_BYTES
                ):
                    raise PackageSourceError("source-document-invalid", ".")
                visit(child, depth + 1)
            return
        if isinstance(current, list):
            for child in current:
                visit(child, depth + 1)
            return
        if isinstance(current, str):
            if (
                len(current.encode("utf-8"))
                > _MAX_STRUCTURED_TEMPLATE_STRING_BYTES
            ):
                raise PackageSourceError("source-document-invalid", ".")
            if USER_COPY_PAYLOAD_ROOT_SENTINEL in current and (
                not current.startswith(f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/")
                or current.count(USER_COPY_PAYLOAD_ROOT_SENTINEL) != 1
            ):
                raise PackageSourceError("source-reference-invalid", current)
            return
        if current is None or type(current) in {bool, int, float}:
            return
        raise PackageSourceError("source-document-invalid", ".")

    visit(value, 0)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PackageSourceError("source-document-invalid", ".") from exc
    if len(encoded) > _MAX_STRUCTURED_TEMPLATE_BYTES:
        raise PackageSourceError("source-document-invalid", ".")


def _contains_payload_sentinel(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_payload_sentinel(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_payload_sentinel(child) for child in value)
    return (
        isinstance(value, str)
        and value.startswith(f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/")
    )


def _template_payload_locators(value: Any) -> set[str]:
    locators: set[str] = set()

    def visit(current: Any) -> None:
        if isinstance(current, dict):
            if any(
                USER_COPY_PAYLOAD_ROOT_SENTINEL in str(key)
                for key in current
            ):
                raise PackageSourceError("source-profile-mismatch", ".")
            for child in current.values():
                visit(child)
            return
        if isinstance(current, list):
            for child in current:
                visit(child)
            return
        if (
            not isinstance(current, str)
            or USER_COPY_PAYLOAD_ROOT_SENTINEL not in current
        ):
            return
        prefix = f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/"
        if not current.startswith(prefix):
            raise PackageSourceError("source-profile-mismatch", ".")
        suffix = current.removeprefix(prefix)
        try:
            locator = normalize_source_locator(suffix)
        except PackageSourceError as exc:
            raise PackageSourceError("source-profile-mismatch", ".") from exc
        if (
            locator != suffix
            or len(locator) > _MAX_USER_COPY_FIELD_LENGTH
            or USER_COPY_PAYLOAD_ROOT_SENTINEL in suffix
        ):
            raise PackageSourceError("source-profile-mismatch", ".")
        locators.add(locator)

    visit(value)
    return locators


def _dependency_payload_coverage_valid(
    referenced_locators: set[str],
    dependency_payloads: list[dict[str, str]],
) -> bool:
    if bool(referenced_locators) != bool(dependency_payloads):
        return False

    def payload_covers(
        payload: Mapping[str, str],
        referenced: str,
    ) -> bool:
        locator = payload["sourceLocator"]
        return referenced == locator or (
            payload["sourceKind"] == "directory"
            and referenced.startswith(f"{locator}/")
        )

    return all(
        any(payload_covers(payload, referenced) for payload in dependency_payloads)
        for referenced in referenced_locators
    ) and all(
        any(payload_covers(payload, referenced) for referenced in referenced_locators)
        for payload in dependency_payloads
    )


def _canonical_dependency_payloads(
    payloads: list[UserCopyDependencyPayload]
    | tuple[UserCopyDependencyPayload, ...],
) -> tuple[UserCopyDependencyPayload, ...]:
    """Deduplicate exact paths and collapse children covered by a directory."""

    by_locator: dict[str, UserCopyDependencyPayload] = {}
    folded: dict[str, str] = {}
    for payload in sorted(
        payloads,
        key=lambda item: (item.source_locator, item.source_kind.value),
    ):
        previous = folded.get(payload.source_locator.casefold())
        if previous is not None and previous != payload.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                payload.source_locator,
            )
        folded[payload.source_locator.casefold()] = payload.source_locator
        existing = by_locator.get(payload.source_locator)
        if existing is not None and existing != payload:
            raise PackageSourceError(
                "source-reference-invalid",
                payload.source_locator,
            )
        by_locator[payload.source_locator] = payload

    result: list[UserCopyDependencyPayload] = []
    for payload in sorted(
        by_locator.values(),
        key=lambda item: (len(Path(item.source_locator).parts), item.source_locator),
    ):
        if any(
            parent.source_kind is UserCopyDependencyPayloadKind.DIRECTORY
            and payload.source_locator.startswith(f"{parent.source_locator}/")
            for parent in result
        ):
            continue
        result.append(payload)
    return tuple(
        sorted(
            result,
            key=lambda item: (item.source_locator, item.source_kind.value),
        )
    )


def _dependency_file_digest(path: Path) -> str:
    """Hash normalized executable mode and exact bytes for one payload file."""

    source_mode = stat.S_IMODE(path.stat().st_mode)
    normalized_mode = 0o700 if source_mode & 0o111 else 0o600
    digest = sha256()
    for component in (
        b"file",
        f"{normalized_mode:o}".encode("ascii"),
        path.read_bytes(),
    ):
        digest.update(len(component).to_bytes(8, "big"))
        digest.update(component)
    return digest.hexdigest()


def user_copy_source_allowlist(
    provider: MarketplaceProviderName,
) -> tuple[UserCopySourceRule, ...]:
    return USER_COPY_SOURCE_ALLOWLIST[provider]


def _resource_sort_key(resource: UserCopyResource) -> tuple[str, str, str, str]:
    return (
        resource.resource_type.value,
        resource.resource_id,
        resource.source_locator,
        resource.json_pointer or "",
    )


def _blocked_sort_key(
    resource: BlockedUserCopyResource,
) -> tuple[str, str, str]:
    return (
        resource.resource_type,
        resource.source_locator,
        resource.reason.value,
    )


def _block(
    blocked: list[BlockedUserCopyResource],
    resource_type: str,
    locator: str,
    reason: str,
) -> None:
    try:
        canonical_locator = normalize_source_locator(locator)
        if canonical_locator != locator:
            raise PackageSourceError("source-reference-invalid", locator)
    except PackageSourceError:
        locator_digest = sha256(locator.encode("utf-8")).hexdigest()
        locator = f"invalid-source/{locator_digest}"
    blocked.append(
        BlockedUserCopyResource(
            resource_type=resource_type,
            source_locator=locator,
            reason=UserCopyBlockReason(reason),
        )
    )


def _read_manifest(
    provider: MarketplaceProviderName,
    package_root: Path,
) -> dict[str, Any]:
    manifest_path = (
        package_root / provider_resource_name_contract(provider).plugin_manifest_path
    )
    if not manifest_path.exists():
        return {}
    try:
        return read_package_json_object(package_root, manifest_path)
    except PackageSourceError:
        return {}


def _add_root_instructions(
    provider: MarketplaceProviderName,
    package_root: Path,
    resources: list[UserCopyResource],
) -> None:
    contract = provider_resource_name_contract(provider)
    source = package_root / contract.root_document_name
    if not source.is_file():
        return
    resources.append(
        UserCopyResource(
            resource_type=UserCopyResourceType.INSTRUCTIONS,
            resource_id="root-instructions",
            source_kind=UserCopySourceKind.COPY_CONVENTION,
            source_locator=contract.root_document_name,
            target_resource=(
                UserCopyTargetResource.AGENTS_MD
                if provider == "codex"
                else UserCopyTargetResource.CLAUDE_MD
            ),
            copy_semantics=UserCopySemantics.CREATE_FILE,
        )
    )


def _add_skills(
    provider: MarketplaceProviderName,
    package_root: Path,
    manifest: dict[str, Any],
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> None:
    if provider == "claude-code" and "skills" in manifest:
        resolved = resolve_claude_plugin_resources(package_root)
        roots = sorted(
            {
                item.resource_root_locator
                for item in resolved.file_resources
                if item.resource_type == "skill"
            }
        )
        for locator in roots:
            parts = locator.split("/")
            resource_id = parts[-1]
            if not _STABLE_ID.fullmatch(resource_id):
                _block(blocked, "skill", locator, "source-not-allowed")
                continue
            resources.append(
                UserCopyResource(
                    resource_type=UserCopyResourceType.SKILL,
                    resource_id=resource_id,
                    source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                    source_locator=locator,
                    target_resource=UserCopyTargetResource.SKILLS,
                    relative_target=resource_id,
                    copy_semantics=UserCopySemantics.CREATE_DIRECTORY,
                )
            )
        return

    root = package_root / "skills"
    if not root.exists():
        return
    if not root.is_dir():
        _block(blocked, "skill", "skills", "source-not-allowed")
        return
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        locator = child.relative_to(package_root).as_posix()
        if not child.is_dir() or not _STABLE_ID.fullmatch(child.name):
            _block(blocked, "skill", locator, "source-not-allowed")
            continue
        if not (child / "SKILL.md").is_file():
            _block(blocked, "skill", locator, "source-not-allowed")
            continue
        resources.append(
            UserCopyResource(
                resource_type=UserCopyResourceType.SKILL,
                resource_id=child.name,
                source_kind=UserCopySourceKind.COPY_CONVENTION,
                source_locator=locator,
                target_resource=UserCopyTargetResource.SKILLS,
                relative_target=child.name,
                copy_semantics=UserCopySemantics.CREATE_DIRECTORY,
            )
        )


def _add_markdown_resources(
    package_root: Path,
    *,
    directory_name: str,
    resource_type: UserCopyResourceType,
    target_resource: UserCopyTargetResource,
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> None:
    root = package_root / directory_name
    if not root.exists():
        return
    if not root.is_dir():
        _block(blocked, resource_type.value, directory_name, "source-not-allowed")
        return
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        locator = path.relative_to(package_root).as_posix()
        if path.suffix != ".md":
            _block(blocked, resource_type.value, locator, "source-not-allowed")
            continue
        relative_target = path.relative_to(root).as_posix()
        resources.append(
            UserCopyResource(
                resource_type=resource_type,
                resource_id=relative_target.removesuffix(".md"),
                source_kind=UserCopySourceKind.COPY_CONVENTION,
                source_locator=locator,
                target_resource=target_resource,
                relative_target=relative_target,
                copy_semantics=UserCopySemantics.CREATE_FILE,
            )
        )


def _add_codex_subagents(
    package_root: Path,
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> None:
    root = package_root / "agents"
    if not root.exists():
        return
    if not root.is_dir():
        _block(blocked, "subagent", "agents", "source-not-allowed")
        return
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        locator = path.relative_to(package_root).as_posix()
        if path.parent != root or path.suffix != ".toml":
            _block(blocked, "subagent", locator, "source-not-allowed")
            continue
        resources.append(
            UserCopyResource(
                resource_type=UserCopyResourceType.SUBAGENT,
                resource_id=path.stem,
                source_kind=UserCopySourceKind.COPY_CONVENTION,
                source_locator=locator,
                target_resource=UserCopyTargetResource.SUBAGENTS,
                relative_target=path.name,
                copy_semantics=UserCopySemantics.CREATE_FILE,
            )
        )


def _add_codex_rules(
    package_root: Path,
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> None:
    root = package_root / "rules"
    if not root.exists():
        return
    if not root.is_dir():
        _block(blocked, "rule", "rules", "source-not-allowed")
        return
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        locator = path.relative_to(package_root).as_posix()
        if path.parent != root or path.suffix != ".rules":
            _block(blocked, "rule", locator, "source-not-allowed")
            continue
        resources.append(
            UserCopyResource(
                resource_type=UserCopyResourceType.RULE,
                resource_id=path.stem,
                source_kind=UserCopySourceKind.COPY_CONVENTION,
                source_locator=locator,
                target_resource=UserCopyTargetResource.RULES,
                relative_target=path.name,
                copy_semantics=UserCopySemantics.CREATE_FILE,
            )
        )


def _add_structured_resources(
    provider: MarketplaceProviderName,
    package_root: Path,
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> None:
    resolved = (
        resolve_codex_plugin_resources(package_root)
        if provider == "codex"
        else resolve_claude_plugin_resources(package_root)
    )
    for diagnostic in resolved.diagnostics:
        _block(blocked, "structured", diagnostic.source_locator, diagnostic.code)
    for name, owner in sorted(resolved.mcp_servers.items()):
        resources.append(
            UserCopyResource(
                resource_type=UserCopyResourceType.MCP,
                resource_id=name,
                source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                source_locator=owner.file_path,
                target_resource=UserCopyTargetResource.MCP,
                json_pointer=owner.json_pointer,
                copy_semantics=UserCopySemantics.MERGE_CONFIG_ENTRY,
            )
        )
    for owner in resolved.hook_entries:
        resources.append(
            UserCopyResource(
                resource_type=UserCopyResourceType.HOOK,
                resource_id=(f"{owner.file_path}#{owner.json_pointer or '/'}"),
                source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                source_locator=owner.file_path,
                target_resource=UserCopyTargetResource.HOOKS,
                json_pointer=owner.json_pointer,
                copy_semantics=UserCopySemantics.MERGE_CONFIG_ENTRY,
            )
        )


def _add_unsupported_components(
    provider: MarketplaceProviderName,
    package_root: Path,
    manifest: dict[str, Any],
    blocked: list[BlockedUserCopyResource],
) -> None:
    if provider == "claude-code":
        keys = {
            "lspServers": "lsp",
            "lsp_servers": "lsp",
            "settings": "settings",
            "themes": "themes",
            "monitors": "monitors",
            "channels": "channels",
        }
        paths = {
            ".lsp.json": "lsp",
            "settings.json": "settings",
            "themes": "themes",
            "monitors": "monitors",
            "channels": "channels",
        }
    else:
        keys = {
            "apps": "apps",
            "connectors": "apps",
            "settings": "settings",
            "config": "settings",
        }
        paths = {
            "apps": "apps",
            "requirements.toml": "managed-requirements",
            "config.toml": "settings",
        }
    for key, resource_type in keys.items():
        value = manifest.get(key)
        if value not in (None, {}, [], ""):
            manifest_path = provider_resource_name_contract(
                provider
            ).plugin_manifest_path
            _block(
                blocked,
                resource_type,
                f"{manifest_path}#/{key}",
                "unsupported-resource",
            )
    for locator, resource_type in paths.items():
        path = package_root / locator
        if path.exists():
            _block(blocked, resource_type, locator, "unsupported-resource")


def _deduplicate(
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> tuple[UserCopyResource, ...]:
    unique: dict[tuple[str, str], UserCopyResource] = {}
    for resource in sorted(resources, key=_resource_sort_key):
        identity = (
            resource.resource_type.value,
            resource.resource_id.casefold(),
        )
        if identity in unique:
            _block(
                blocked,
                resource.resource_type.value,
                resource.source_locator,
                "duplicate-resource-id",
            )
            continue
        unique[identity] = resource
    return tuple(sorted(unique.values(), key=_resource_sort_key))


def _bounded_resources(
    resources: list[UserCopyResource],
    blocked: list[BlockedUserCopyResource],
) -> list[UserCopyResource]:
    bounded: list[UserCopyResource] = []
    for resource in resources:
        if (
            len(resource.resource_id) > _MAX_USER_COPY_FIELD_LENGTH
            or len(resource.source_locator) > _MAX_USER_COPY_FIELD_LENGTH
            or (
                resource.relative_target is not None
                and len(resource.relative_target) > _MAX_USER_COPY_FIELD_LENGTH
            )
            or (
                resource.json_pointer is not None
                and len(resource.json_pointer) > _MAX_USER_COPY_FIELD_LENGTH
            )
        ):
            _block(
                blocked,
                resource.resource_type.value,
                resource.source_locator,
                "source-not-allowed",
            )
            continue
        bounded.append(resource)
    return bounded


def resolve_user_copy_profile(
    provider: MarketplaceProviderName,
    package_root: Path,
) -> UserCopyProfile:
    provider_resource_name_contract(provider)
    blocked: list[BlockedUserCopyResource] = []
    try:
        package_tree_digest(package_root)
    except (OSError, PackageTreeError):
        _block(
            blocked,
            "package",
            ".",
            "source-reference-invalid",
        )
        return UserCopyProfile(
            provider=provider,
            resources=(),
            blocked_resources=tuple(sorted(blocked, key=_blocked_sort_key)),
        )
    return _resolve_user_copy_profile(provider, package_root)


def resolve_user_copy_profile_with_dependency_payloads(
    provider: MarketplaceProviderName,
    package_root: Path,
) -> tuple[UserCopyProfile, tuple[UserCopyDependencyPayload, ...]]:
    """Resolve one validated profile and its dependency closure in one pass."""

    profile = resolve_user_copy_profile(provider, package_root)
    return profile, _resolve_user_copy_dependency_payloads(package_root, profile)


def build_user_copy_source_snapshot(
    provider: MarketplaceProviderName,
    package_root: Path,
) -> UserCopySourceSnapshot:
    """Build one immutable source snapshot without repeated tree validation."""

    provider_resource_name_contract(provider)
    tree_digest = package_tree_digest(package_root)
    profile = _resolve_user_copy_profile(provider, package_root)
    return UserCopySourceSnapshot(
        profile=profile,
        preview=_build_user_copy_profile_preview(package_root, profile),
        package_tree_digest=tree_digest,
    )


def _resolve_user_copy_profile(
    provider: MarketplaceProviderName,
    package_root: Path,
) -> UserCopyProfile:
    resources: list[UserCopyResource] = []
    blocked: list[BlockedUserCopyResource] = []
    manifest = _read_manifest(provider, package_root)
    _add_root_instructions(provider, package_root, resources)
    _add_skills(provider, package_root, manifest, resources, blocked)
    if provider == "claude-code":
        _add_markdown_resources(
            package_root,
            directory_name="agents",
            resource_type=UserCopyResourceType.SUBAGENT,
            target_resource=UserCopyTargetResource.SUBAGENTS,
            resources=resources,
            blocked=blocked,
        )
        _add_markdown_resources(
            package_root,
            directory_name="commands",
            resource_type=UserCopyResourceType.COMMAND,
            target_resource=UserCopyTargetResource.COMMANDS,
            resources=resources,
            blocked=blocked,
        )
        _add_markdown_resources(
            package_root,
            directory_name="output-styles",
            resource_type=UserCopyResourceType.OUTPUT_STYLE,
            target_resource=UserCopyTargetResource.OUTPUT_STYLES,
            resources=resources,
            blocked=blocked,
        )
    else:
        _add_codex_subagents(package_root, resources, blocked)
        _add_markdown_resources(
            package_root,
            directory_name="prompts",
            resource_type=UserCopyResourceType.PROMPT,
            target_resource=UserCopyTargetResource.PROMPTS,
            resources=resources,
            blocked=blocked,
        )
        _add_codex_rules(package_root, resources, blocked)
    _add_structured_resources(provider, package_root, resources, blocked)
    _add_unsupported_components(provider, package_root, manifest, blocked)
    deduplicated = _deduplicate(_bounded_resources(resources, blocked), blocked)
    return UserCopyProfile(
        provider=provider,
        resources=deduplicated,
        blocked_resources=tuple(sorted(set(blocked), key=_blocked_sort_key)),
    )
