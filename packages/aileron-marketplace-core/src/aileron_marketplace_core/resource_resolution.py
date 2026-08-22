from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

MAX_USER_COPY_WIRE_FIELD_LENGTH = 1024


@dataclass(frozen=True)
class ResourceResolutionDiagnostic:
    code: str
    source_locator: str


@dataclass(frozen=True)
class PluginResourceOwner:
    file_path: str
    json_pointer: str
    standalone_file: bool


class PackageSourceError(ValueError):
    def __init__(self, code: str, source_locator: str) -> None:
        super().__init__(f"{code}: {source_locator}")
        self.code = code
        self.source_locator = source_locator


def json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def decode_json_pointer(
    pointer: str | None,
    *,
    source_locator: str | None = None,
) -> tuple[str, ...]:
    """Decode one RFC 6901 pointer and reject non-canonical escapes."""

    if pointer is None or pointer == "":
        return ()
    error_locator = source_locator if source_locator is not None else pointer
    if not pointer.startswith("/"):
        raise PackageSourceError("source-reference-invalid", error_locator)
    decoded: list[str] = []
    for raw_token in pointer.removeprefix("/").split("/"):
        index = 0
        while index < len(raw_token):
            if raw_token[index] != "~":
                index += 1
                continue
            if index + 1 >= len(raw_token) or raw_token[index + 1] not in {
                "0",
                "1",
            }:
                raise PackageSourceError(
                    "source-reference-invalid",
                    error_locator,
                )
            index += 2
        decoded.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tuple(decoded)


def package_relative_locator(package_root: Path, path: Path) -> str:
    try:
        return path.relative_to(package_root).as_posix()
    except ValueError as exc:
        raise PackageSourceError("source-reference-invalid", str(path)) from exc


def normalize_source_locator(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_USER_COPY_WIRE_FIELD_LENGTH
        or any(character in value for character in ("\x00", "\n", "\r", "\\"))
        or ":" in value.split("/", 1)[0]
    ):
        raise PackageSourceError("source-reference-invalid", value)
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or any(part == ".." for part in posix_path.parts)
    ):
        raise PackageSourceError("source-reference-invalid", value)
    return posix_path.as_posix()


def validate_source_locator(value: str) -> str:
    """Validate one canonical package-relative locator crossing the wire."""

    normalized = normalize_source_locator(value)
    if (
        normalized != value
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise PackageSourceError("source-reference-invalid", value)
    return value


def validate_logical_target_locator(value: str) -> str:
    """Validate one canonical sanitized user-scope target locator."""

    if not isinstance(value, str):
        raise PackageSourceError("source-reference-invalid", value)
    path_part, separator, fragment = value.partition("#")
    relative = ""
    for prefix in ("~/", "$CODEX_HOME/", "$CLAUDE_CONFIG_DIR/"):
        if path_part.startswith(prefix):
            relative = path_part.removeprefix(prefix)
            break
    if (
        not value
        or len(value) > MAX_USER_COPY_WIRE_FIELD_LENGTH
        or not relative
        or value.count("#") > 1
        or any(character in value for character in ("\x00", "\n", "\r", "\\"))
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or ":" in relative.split("/", 1)[0]
        or (separator and not fragment)
        or (
            separator
            and any(
                part in {"", ".", ".."}
                for part in fragment.removeprefix("/").split("/")
            )
        )
    ):
        raise PackageSourceError("source-reference-invalid", value)
    return value


def validate_wire_identity(value: str) -> str:
    """Validate one bounded identity crossing the Marketplace wire."""

    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_USER_COPY_WIRE_FIELD_LENGTH
        or any(character in value for character in ("\x00", "\n", "\r"))
    ):
        raise PackageSourceError("source-reference-invalid", value)
    return value


def resolve_package_source(
    package_root: Path,
    value: str,
    *,
    expected_suffixes: tuple[str, ...] = (),
    require_file: bool = True,
) -> Path:
    locator = normalize_source_locator(value)
    candidate = package_root / locator
    resolved_root = package_root.resolve(strict=True)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise PackageSourceError("source-reference-invalid", locator) from exc
    if expected_suffixes and candidate.suffix not in expected_suffixes:
        raise PackageSourceError("source-not-allowed", locator)
    if not candidate.exists():
        raise PackageSourceError("source-missing", locator)
    if require_file and not candidate.is_file():
        raise PackageSourceError("source-not-allowed", locator)
    if not require_file and not candidate.is_dir():
        raise PackageSourceError("source-not-allowed", locator)
    return candidate


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageSourceError("source-document-invalid", str(path)) from exc
    if not isinstance(data, dict):
        raise PackageSourceError("source-document-invalid", str(path))
    return data


def read_package_json_object(
    package_root: Path,
    path: Path,
) -> dict[str, Any]:
    locator = package_relative_locator(package_root, path)
    try:
        return read_json_object(path)
    except PackageSourceError as exc:
        raise PackageSourceError(exc.code, locator) from exc


def mcp_server_map(
    data: dict[str, Any],
    *,
    source_locator: str,
) -> tuple[str, dict[str, Any]]:
    if "mcpServers" in data and "mcp_servers" in data:
        raise PackageSourceError("source-document-invalid", source_locator)
    for key in ("mcpServers", "mcp_servers"):
        if key not in data:
            continue
        servers = data[key]
        if not isinstance(servers, dict):
            raise PackageSourceError("source-document-invalid", source_locator)
        if not all(isinstance(value, dict) for value in servers.values()):
            raise PackageSourceError("source-document-invalid", source_locator)
        return key, servers
    if not data or all(isinstance(value, dict) for value in data.values()):
        return "", data
    raise PackageSourceError("source-document-invalid", source_locator)


def hook_map(
    data: dict[str, Any],
    *,
    source_locator: str,
) -> tuple[str, dict[str, Any]]:
    if "hooks" in data:
        hooks = data["hooks"]
        if not isinstance(hooks, dict):
            raise PackageSourceError("source-document-invalid", source_locator)
        pointer_prefix = "/hooks"
    else:
        hooks = data
        pointer_prefix = ""
    if not all(
        isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries)
        for entries in hooks.values()
    ):
        raise PackageSourceError("source-document-invalid", source_locator)
    return pointer_prefix, hooks


def manifest_reference_values(
    value: Any,
    *,
    source_locator: str,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise PackageSourceError("source-document-invalid", source_locator)


def validate_inline_mcp_servers(
    servers: dict[str, Any],
    *,
    source_locator: str,
) -> None:
    if not all(isinstance(value, dict) for value in servers.values()):
        raise PackageSourceError("source-document-invalid", source_locator)


def validate_inline_hooks(
    hooks: dict[str, Any],
    *,
    source_locator: str,
) -> None:
    if not all(
        isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries)
        for entries in hooks.values()
    ):
        raise PackageSourceError("source-document-invalid", source_locator)


def mcp_owners_from_document(
    package_root: Path,
    path: Path,
) -> dict[str, PluginResourceOwner]:
    locator = package_relative_locator(package_root, path)
    data = read_package_json_object(package_root, path)
    key, servers = mcp_server_map(data, source_locator=locator)
    pointer_prefix = f"/{key}" if key else ""
    return {
        str(name): PluginResourceOwner(
            file_path=locator,
            json_pointer=f"{pointer_prefix}/{json_pointer_escape(str(name))}",
            standalone_file=True,
        )
        for name in sorted(servers)
    }


def hook_owners_from_document(
    package_root: Path,
    path: Path,
) -> tuple[PluginResourceOwner, ...]:
    locator = package_relative_locator(package_root, path)
    data = read_package_json_object(package_root, path)
    prefix, hooks = hook_map(data, source_locator=locator)
    owners: list[PluginResourceOwner] = []
    for event_name in sorted(hooks):
        entries = hooks[event_name]
        for index in range(len(entries)):
            owners.append(
                PluginResourceOwner(
                    file_path=locator,
                    json_pointer=(
                        f"{prefix}/{json_pointer_escape(str(event_name))}/{index}"
                    ),
                    standalone_file=True,
                )
            )
    return tuple(owners)


def read_plugin_resource_owner(
    package_root: Path,
    owner: PluginResourceOwner,
) -> Any:
    """Read the value identified by a canonical plugin resource owner."""

    path = resolve_package_source(
        package_root,
        owner.file_path,
        expected_suffixes=(".json",),
    )
    value: Any = read_package_json_object(package_root, path)
    if not owner.json_pointer:
        return value
    for token in decode_json_pointer(
        owner.json_pointer,
        source_locator=owner.file_path,
    ):
        if isinstance(value, dict) and token in value:
            value = value[token]
            continue
        if isinstance(value, list):
            try:
                index = int(token)
            except ValueError as exc:
                raise PackageSourceError(
                    "source-reference-invalid",
                    owner.file_path,
                ) from exc
            if 0 <= index < len(value):
                value = value[index]
                continue
        raise PackageSourceError("source-reference-invalid", owner.file_path)
    return value
