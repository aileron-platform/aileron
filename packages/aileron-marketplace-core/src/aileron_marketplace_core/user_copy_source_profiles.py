"""Package-format-owned source profiles for Marketplace User Copy."""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol
from urllib.parse import urlparse

from .package_tree import PackageTreeError, package_tree_digest
from .resource_resolution import (
    PackageSourceError,
    normalize_source_locator,
    read_package_json_object,
    validate_wire_identity,
)
from .user_copy_profiles import (
    UserCopyResourceType,
    UserCopySourceKind,
    build_native_user_copy_source_preview,
)


class PluginPackageFormat(str, Enum):
    """Canonical package grammars understood by Marketplace."""

    CODEX_NATIVE = "codex-native"
    CLAUDE_NATIVE = "claude-native"
    AGENT_PLUGIN_V1 = "agent-plugin/1.0.0"


class TargetClient(str, Enum):
    """Canonical Agent clients that can receive Marketplace delivery."""

    CODEX = "codex"
    CLAUDE_CODE = "claude-code"


@dataclass(frozen=True)
class PluginReleaseIdentity:
    """One immutable catalog release used as User Copy provenance."""

    catalog_plugin_id: str
    revision: str

    def __post_init__(self) -> None:
        validate_wire_identity(self.catalog_plugin_id)
        if len(self.revision) != 64 or any(
            character not in "0123456789abcdef" for character in self.revision
        ):
            raise ValueError("release-revision-invalid")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "catalogPluginId": self.catalog_plugin_id,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class UserCopyDependencyReference:
    """One package-relative dependency referenced by a source resource."""

    source_locator: str
    source_kind: Literal["file", "directory"]
    source_digest: str

    def __post_init__(self) -> None:
        if normalize_source_locator(self.source_locator) != self.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )
        if len(self.source_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.source_digest
        ):
            raise ValueError("source-digest-invalid")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "sourceLocator": self.source_locator,
            "sourceKind": self.source_kind,
            "sourceDigest": self.source_digest,
        }


@dataclass(frozen=True)
class UserCopySourceDiagnostic:
    """One package-format extraction diagnostic."""

    code: str
    source_locator: str
    resource_type: str | None = None
    resource_id: str | None = None

    def canonical_dict(self) -> dict[str, str]:
        result = {
            "code": validate_wire_identity(self.code),
            "sourceLocator": normalize_source_locator(self.source_locator),
        }
        if self.resource_type is not None:
            result["resourceType"] = validate_wire_identity(self.resource_type)
        if self.resource_id is not None:
            result["resourceId"] = validate_wire_identity(self.resource_id)
        return result


@dataclass(frozen=True)
class UserCopySourceResource:
    """A source-only resource with no target projection semantics."""

    resource_type: UserCopyResourceType
    resource_id: str
    source_locator: str
    source_kind: UserCopySourceKind
    source_digest: str
    source_json_pointer: str | None = None
    structured_value: Any | None = None
    dependency_references: tuple[UserCopyDependencyReference, ...] = ()

    def __post_init__(self) -> None:
        validate_wire_identity(self.resource_id)
        if normalize_source_locator(self.source_locator) != self.source_locator:
            raise PackageSourceError(
                "source-reference-invalid",
                self.source_locator,
            )
        if len(self.source_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.source_digest
        ):
            raise ValueError("source-digest-invalid")

    def canonical_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "resourceType": self.resource_type.value,
            "resourceId": self.resource_id,
            "sourceKind": self.source_kind.value,
            "sourceLocator": self.source_locator,
            "sourceDigest": self.source_digest,
            "dependencyReferences": [
                reference.canonical_dict() for reference in self.dependency_references
            ],
        }
        if self.structured_value is not None:
            result["structuredValue"] = self.structured_value
        if self.source_json_pointer is not None:
            result["sourceJsonPointer"] = self.source_json_pointer
        return result


@dataclass(frozen=True)
class UserCopySourceProfile:
    """Canonical source profile produced by one package-format extractor."""

    package_format: PluginPackageFormat
    release_identity: PluginReleaseIdentity
    resources: tuple[UserCopySourceResource, ...]
    diagnostics: tuple[UserCopySourceDiagnostic, ...] = ()
    profile_version: int = 2

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "profileVersion": self.profile_version,
            "packageFormat": self.package_format.value,
            "releaseIdentity": self.release_identity.canonical_dict(),
            "resources": [resource.canonical_dict() for resource in self.resources],
            "diagnostics": [
                diagnostic.canonical_dict() for diagnostic in self.diagnostics
            ],
        }

    @property
    def profile_digest(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


class PackageFormatUserCopyExtractor(Protocol):
    """Package-format seam for source-only User Copy discovery."""

    @property
    def package_format(self) -> PluginPackageFormat:
        """Return the exact package grammar implemented by this adapter."""

    def extract(
        self,
        package_root: Path,
        *,
        release: PluginReleaseIdentity,
    ) -> UserCopySourceProfile:
        """Return one deterministic source-only profile."""


_AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_AGENT_PLUGIN_MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
_AGENT_PLUGIN_NAME = re.compile(
    r"^(?=.{1,64}$)(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$"
)
_MANIFEST_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)


class AgentPluginV1UserCopyExtractor:
    """Extract the portable Agent Plugins 1.0.0 interoperability floor."""

    package_format = PluginPackageFormat.AGENT_PLUGIN_V1

    def extract(
        self,
        package_root: Path,
        *,
        release: PluginReleaseIdentity,
    ) -> UserCopySourceProfile:
        _validate_package_root(package_root, validate_tree=False)
        manifest = read_package_json_object(package_root, package_root / "plugin.json")
        _validate_agent_plugin_manifest(manifest)
        resources: list[UserCopySourceResource] = []
        diagnostics = _manifest_diagnostics(manifest)
        diagnostics.extend(_agent_plugin_nonportable_diagnostics(package_root))
        resources.extend(_agent_plugin_mcp_resources(package_root, diagnostics))
        resources.extend(_agent_plugin_skill_resources(package_root, diagnostics))
        resources.sort(
            key=lambda resource: (
                resource.resource_type.value,
                resource.resource_id.casefold(),
                resource.source_locator,
            )
        )
        diagnostics.sort(
            key=lambda diagnostic: (
                diagnostic.code,
                diagnostic.source_locator,
                diagnostic.resource_id or "",
            )
        )
        return UserCopySourceProfile(
            package_format=self.package_format,
            release_identity=release,
            resources=tuple(resources),
            diagnostics=tuple(diagnostics),
        )


class NativeUserCopyExtractor:
    """Adapt a native package grammar to the neutral source profile seam."""

    def __init__(self, package_format: PluginPackageFormat) -> None:
        if package_format not in {
            PluginPackageFormat.CODEX_NATIVE,
            PluginPackageFormat.CLAUDE_NATIVE,
        }:
            raise ValueError("native-package-format-required")
        self._package_format = package_format

    @property
    def package_format(self) -> PluginPackageFormat:
        return self._package_format

    def extract(
        self,
        package_root: Path,
        *,
        release: PluginReleaseIdentity,
    ) -> UserCopySourceProfile:
        _validate_package_root(package_root)
        native_name = (
            "codex-native"
            if self.package_format is PluginPackageFormat.CODEX_NATIVE
            else "claude-native"
        )
        preview = build_native_user_copy_source_preview(native_name, package_root)
        resources = []
        for resource in preview["resources"]:
            resources.append(
                UserCopySourceResource(
                    resource_type=UserCopyResourceType(resource["resourceType"]),
                    resource_id=resource["resourceId"],
                    source_locator=resource["sourceLocator"],
                    source_kind=UserCopySourceKind(resource["sourceKind"]),
                    source_digest=resource["sourceDigest"],
                    source_json_pointer=resource["sourceJsonPointer"],
                    structured_value=_neutralize_native_payload_template(
                        resource["structuredValue"]
                    ),
                    dependency_references=tuple(
                        UserCopyDependencyReference(
                            source_locator=item["sourceLocator"],
                            source_kind=item["sourceKind"],
                            source_digest=item["sourceDigest"],
                        )
                        for item in resource["dependencyReferences"]
                    ),
                )
            )
        resources.sort(
            key=lambda item: (
                item.resource_type.value,
                item.resource_id.casefold(),
                item.source_locator,
            )
        )
        diagnostics = tuple(
            UserCopySourceDiagnostic(
                code=item["code"],
                source_locator=item["sourceLocator"],
                resource_type=item["resourceType"],
            )
            for item in preview["diagnostics"]
        )
        return UserCopySourceProfile(
            package_format=self.package_format,
            release_identity=release,
            resources=tuple(resources),
            diagnostics=diagnostics,
        )


def extract_user_copy_source_profile(
    package_format: PluginPackageFormat | str,
    package_root: Path,
    *,
    release: PluginReleaseIdentity,
) -> UserCopySourceProfile:
    """Extract one package through the exact registered format adapter."""

    resolved = PluginPackageFormat(package_format)
    if resolved is PluginPackageFormat.AGENT_PLUGIN_V1:
        return AgentPluginV1UserCopyExtractor().extract(
            package_root,
            release=release,
        )
    return NativeUserCopyExtractor(resolved).extract(
        package_root,
        release=release,
    )


def _validate_package_root(
    package_root: Path,
    *,
    validate_tree: bool = True,
) -> None:
    if package_root.is_symlink() or not package_root.is_dir():
        raise PackageSourceError("source-reference-invalid", ".")
    if not validate_tree:
        return
    try:
        package_tree_digest(package_root)
    except (OSError, PackageTreeError) as exc:
        raise PackageSourceError("source-reference-invalid", ".") from exc


def _validate_agent_plugin_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("$schema") != _AGENT_PLUGIN_SCHEMA:
        raise PackageSourceError("manifest-schema-unsupported", "plugin.json")
    name = manifest.get("name")
    if not isinstance(name, str) or _AGENT_PLUGIN_NAME.fullmatch(name) is None:
        raise PackageSourceError("manifest-invalid", "plugin.json")
    for field, value in manifest.items():
        if field not in _MANIFEST_FIELDS:
            continue
        if field in {"$schema", "name"}:
            continue
        if field == "extensions":
            if isinstance(value, dict) and any(
                not isinstance(extension, dict) for extension in value.values()
            ):
                raise PackageSourceError("manifest-invalid", "plugin.json")
            continue
        if field == "author" and value is not None:
            if (
                not isinstance(value, dict)
                or set(value) - {"name", "email", "url"}
                or any(not isinstance(item, str) for item in value.values())
            ):
                raise PackageSourceError("manifest-invalid", "plugin.json")
            continue
        if (
            field == "keywords"
            and value is not None
            and not (
                isinstance(value, list) and all(isinstance(item, str) for item in value)
            )
        ):
            raise PackageSourceError("manifest-invalid", "plugin.json")
        if (
            field not in {"author", "keywords"}
            and value is not None
            and not isinstance(value, str)
        ):
            raise PackageSourceError("manifest-invalid", "plugin.json")


def _manifest_diagnostics(
    manifest: Mapping[str, Any],
) -> list[UserCopySourceDiagnostic]:
    diagnostics = [
        UserCopySourceDiagnostic(
            code="manifest-field-ignored",
            source_locator="plugin.json",
            resource_id=field,
        )
        for field in sorted(set(manifest) - _MANIFEST_FIELDS)
    ]
    extensions = manifest.get("extensions")
    if "extensions" in manifest and not isinstance(extensions, dict):
        diagnostics.append(
            UserCopySourceDiagnostic(
                code="manifest-extensions-ignored",
                source_locator="plugin.json",
            )
        )
    elif isinstance(extensions, dict):
        diagnostics.extend(
            UserCopySourceDiagnostic(
                code="extension-unsupported",
                source_locator="plugin.json",
                resource_type="extension",
                resource_id=namespace,
            )
            for namespace in sorted(extensions)
        )
    return diagnostics


def _agent_plugin_nonportable_diagnostics(
    package_root: Path,
) -> list[UserCopySourceDiagnostic]:
    return [
        UserCopySourceDiagnostic(
            code="nonportable-component-unsupported",
            source_locator=name,
            resource_type="component",
            resource_id=name,
        )
        for name in ("agents", "commands", "hooks")
        if (package_root / name).exists()
    ]


def _agent_plugin_skill_resources(
    package_root: Path,
    diagnostics: list[UserCopySourceDiagnostic],
) -> list[UserCopySourceResource]:
    skills_root = package_root / "skills"
    if not skills_root.exists():
        return []
    if skills_root.is_symlink() or not skills_root.is_dir():
        diagnostics.append(
            UserCopySourceDiagnostic(
                code="skills-component-invalid",
                source_locator="skills",
                resource_type="skill",
            )
        )
        return []
    resources: list[UserCopySourceResource] = []
    for child in sorted(skills_root.iterdir(), key=lambda path: path.name):
        locator = child.relative_to(package_root).as_posix()
        skill_file = child / "SKILL.md"
        if (
            child.is_symlink()
            or not child.is_dir()
            or skill_file.is_symlink()
            or not skill_file.is_file()
        ):
            diagnostics.append(
                UserCopySourceDiagnostic(
                    code="skill-invalid",
                    source_locator=locator,
                    resource_type="skill",
                    resource_id=child.name,
                )
            )
            continue
        try:
            digest = _dependency_directory_digest(child)
        except (OSError, PackageSourceError):
            diagnostics.append(
                UserCopySourceDiagnostic(
                    code="skill-invalid",
                    source_locator=locator,
                    resource_type="skill",
                    resource_id=child.name,
                )
            )
            continue
        resources.append(
            UserCopySourceResource(
                resource_type=UserCopyResourceType.SKILL,
                resource_id=child.name,
                source_locator=locator,
                source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                source_digest=digest,
            )
        )
    return resources


def _agent_plugin_mcp_resources(
    package_root: Path,
    diagnostics: list[UserCopySourceDiagnostic],
) -> list[UserCopySourceResource]:
    path = package_root / "mcp.json"
    if not path.exists():
        return []
    try:
        document = read_package_json_object(package_root, path)
    except PackageSourceError:
        diagnostics.append(
            UserCopySourceDiagnostic(
                code="mcp-component-invalid",
                source_locator="mcp.json",
                resource_type="mcp",
            )
        )
        return []
    if (
        set(document) - {"$schema", "mcpServers"}
        or document.get("$schema") != _AGENT_PLUGIN_MCP_SCHEMA
        or not isinstance(document.get("mcpServers"), dict)
    ):
        diagnostics.append(
            UserCopySourceDiagnostic(
                code="mcp-component-invalid",
                source_locator="mcp.json",
                resource_type="mcp",
            )
        )
        return []
    resources: list[UserCopySourceResource] = []
    for name, value in sorted(document["mcpServers"].items()):
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(value, dict)
            or not _valid_agent_plugin_mcp_entry(package_root, value)
        ):
            diagnostics.append(
                UserCopySourceDiagnostic(
                    code="mcp-entry-invalid",
                    source_locator="mcp.json",
                    resource_type="mcp",
                    resource_id=str(name),
                )
            )
            continue
        normalized_value = _normalize_agent_plugin_mcp_entry(value)
        try:
            dependencies = _agent_plugin_dependency_references(
                package_root,
                normalized_value,
            )
        except PackageSourceError:
            diagnostics.append(
                UserCopySourceDiagnostic(
                    code="mcp-dependency-invalid",
                    source_locator="mcp.json",
                    resource_type="mcp",
                    resource_id=name,
                )
            )
            continue
        encoded = json.dumps(
            normalized_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        resources.append(
            UserCopySourceResource(
                resource_type=UserCopyResourceType.MCP,
                resource_id=name,
                source_locator="mcp.json",
                source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                source_digest=sha256(encoded).hexdigest(),
                source_json_pointer=f"/mcpServers/{_json_pointer_escape(name)}",
                structured_value=normalized_value,
                dependency_references=dependencies,
            )
        )
    return resources


def _valid_agent_plugin_mcp_entry(
    package_root: Path,
    value: Mapping[str, Any],
) -> bool:
    transport = value.get("type")
    if transport == "stdio":
        if set(value) - {"type", "command", "args", "env", "cwd"}:
            return False
        command = value.get("command")
        if (
            not isinstance(command, str)
            or not command
            or any(character.isspace() for character in command)
            or ("/" in command and not command.startswith("./"))
            or ("\\" in command)
        ):
            return False
        if command.startswith("./") and not _valid_package_relative_reference(
            package_root,
            command[2:],
        ):
            return False
        args = value.get("args")
        if args is not None and not (
            isinstance(args, list) and all(isinstance(item, str) for item in args)
        ):
            return False
        env = value.get("env")
        if env is not None and not (
            isinstance(env, dict)
            and not ({"PLUGIN_ROOT", "PLUGIN_DATA"} & set(env))
            and all(
                isinstance(key, str) and isinstance(item, str)
                for key, item in env.items()
            )
        ):
            return False
        cwd = value.get("cwd")
        if cwd is not None and not _valid_agent_plugin_cwd(package_root, cwd):
            return False
        return True
    if transport not in {"streamable-http", "sse"}:
        return False
    if set(value) - {"type", "url", "headers"}:
        return False
    url = value.get("url")
    if not isinstance(url, str) or not _valid_agent_plugin_remote_url(url):
        return False
    headers = value.get("headers")
    return headers is None or (
        isinstance(headers, dict)
        and all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in headers.items()
        )
    )


def _valid_agent_plugin_cwd(package_root: Path, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if value.startswith("./"):
        return _valid_package_relative_reference(package_root, value[2:])
    return (
        value == "${PLUGIN_ROOT}"
        or value.startswith("${PLUGIN_ROOT}/")
        or (value == "${PLUGIN_DATA}" or value.startswith("${PLUGIN_DATA}/"))
    )


def _valid_agent_plugin_remote_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme == "https" and bool(parsed.netloc):
        return True
    return parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1",
        "::1",
        "localhost",
    }


def _valid_package_relative_reference(package_root: Path, locator: str) -> bool:
    try:
        normalized = normalize_source_locator(locator)
        resolved = (package_root / normalized).resolve(strict=True)
        resolved.relative_to(package_root.resolve(strict=True))
    except (OSError, PackageSourceError, RuntimeError, ValueError):
        return False
    return not (package_root / normalized).is_symlink()


def _normalize_agent_plugin_mcp_entry(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    for field in ("command", "cwd"):
        item = normalized.get(field)
        if isinstance(item, str) and item.startswith("./"):
            normalized[field] = f"${{PLUGIN_ROOT}}/{item[2:]}"
    return normalized


def _agent_plugin_dependency_references(
    package_root: Path,
    value: Any,
) -> tuple[UserCopyDependencyReference, ...]:
    locators: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, str):
            for match in re.finditer(r"\$\{PLUGIN_ROOT\}/([^\s\"']+)", item):
                locator = normalize_source_locator(match.group(1))
                locators.add(locator)
            return
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    references = []
    resolved_root = package_root.resolve(strict=True)
    for locator in sorted(locators):
        path = package_root.joinpath(*Path(locator).parts)
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PackageSourceError("source-reference-invalid", locator) from exc
        if path.is_symlink():
            raise PackageSourceError("source-reference-invalid", locator)
        if path.is_file():
            source_kind: Literal["file", "directory"] = "file"
            digest = _dependency_file_digest(path)
        elif path.is_dir():
            source_kind = "directory"
            digest = _dependency_directory_digest(path)
        else:
            raise PackageSourceError("source-reference-invalid", locator)
        references.append(
            UserCopyDependencyReference(
                source_locator=locator,
                source_kind=source_kind,
                source_digest=digest,
            )
        )
    return tuple(references)


def _dependency_file_digest(path: Path) -> str:
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


def _dependency_directory_digest(root: Path) -> str:
    digest = sha256()
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_symlink():
            raise PackageSourceError("source-reference-invalid", relative.decode())
        if path.is_dir():
            entry_type = b"directory"
            mode = 0o700
            content = b""
        elif path.is_file():
            entry_type = b"file"
            source_mode = stat.S_IMODE(path.stat().st_mode)
            mode = 0o700 if source_mode & 0o111 else 0o600
            content = path.read_bytes()
        else:
            raise PackageSourceError("source-reference-invalid", relative.decode())
        for component in (
            entry_type,
            f"{mode:o}".encode("ascii"),
            relative,
            content,
        ):
            digest.update(len(component).to_bytes(8, "big"))
            digest.update(component)
    return digest.hexdigest()


def _json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _neutralize_native_payload_template(value: Any) -> Any:
    """Replace the legacy preview sentinel with source-neutral PLUGIN_ROOT."""

    sentinel = "__AILERON_USER_COPY_PAYLOAD_ROOT__"
    if isinstance(value, str):
        return value.replace(sentinel, "${PLUGIN_ROOT}")
    if isinstance(value, list):
        return [_neutralize_native_payload_template(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _neutralize_native_payload_template(item)
            for key, item in value.items()
        }
    return value
