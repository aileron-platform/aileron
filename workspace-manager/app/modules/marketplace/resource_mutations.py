from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from aileron_marketplace_core import (
    PackageSourceError,
    decode_json_pointer,
    json_pointer_escape,
)
from aileron_marketplace_core.provider_resources import (
    provider_resource_name_contract,
)
from aileron_marketplace_core.resource_resolution import (
    manifest_reference_values,
    mcp_server_map,
    package_relative_locator,
    read_package_json_object,
    resolve_package_source,
    validate_inline_mcp_servers,
)

from app.modules.marketplace.models import MarketplaceProvider
from app.modules.marketplace.resource_resolvers import MarketplaceResourceOwner

DOCUMENT_RESOURCE_ROOTS: dict[MarketplaceProvider, dict[str, str]] = {
    "claude-code": {
        "commands": "commands",
        "subagents": "agents",
        "output-styles": "output-styles",
        "policies": "policies",
    },
    "codex": {
        "commands": "prompts",
        "subagents": "agents",
        "output-styles": "output-styles",
        "policies": "policies",
    },
}


def validate_package_relative_path(path: str) -> PurePosixPath:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or not str(candidate):
        raise ValueError("marketplace.package.path_escape")
    return candidate


def load_root_document_path(provider: str, package_path: Path) -> Path:
    contract = provider_resource_name_contract(provider)
    return package_path / contract.root_document_name


def document_resource_root(
    provider: MarketplaceProvider,
    resource_type: str,
) -> str:
    try:
        return DOCUMENT_RESOURCE_ROOTS[provider][resource_type]
    except KeyError as exc:
        raise ValueError("marketplace.resource.unsupported_type") from exc


def canonical_entry_fingerprint(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def patch_json_entry(data: dict[str, Any], pointer: str, value: Any) -> dict[str, Any]:
    patched = copy.deepcopy(data)
    parts = decode_json_pointer(pointer)
    if not parts:
        if not isinstance(value, dict):
            raise ValueError("marketplace.resource.invalid_json_root")
        return value
    cursor: Any = patched
    for part in parts[:-1]:
        if part not in cursor:
            cursor[part] = {}
        if not isinstance(cursor[part], dict):
            raise ValueError("marketplace.resource.invalid_json_root")
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return patched


def remove_json_entry(data: dict[str, Any], pointer: str) -> dict[str, Any]:
    """Remove one RFC 6901 entry without assuming its containing map name."""

    patched = copy.deepcopy(data)
    parts = decode_json_pointer(pointer)
    if not parts:
        raise ValueError("marketplace.resource.invalid_json_root")
    cursor: Any = patched
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            raise ValueError("marketplace.resource.invalid_json_root")
        cursor = cursor[part]
    final = parts[-1]
    if isinstance(cursor, dict) and final in cursor:
        del cursor[final]
        return patched
    raise ValueError("marketplace.resource.invalid_json_root")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def get_json_entry(data: dict[str, Any], pointer: str | None) -> Any:
    if not pointer:
        return data
    cursor: Any = data
    for part in decode_json_pointer(pointer):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def default_mcp_owner(
    package_path: Path,
    server_name: str,
    provider: MarketplaceProvider,
) -> MarketplaceResourceOwner:
    escaped_name = json_pointer_escape(server_name)
    contract = provider_resource_name_contract(provider)
    manifest_path = package_path / contract.plugin_manifest_path
    try:
        manifest = (
            read_package_json_object(package_path, manifest_path)
            if manifest_path.is_file()
            else {}
        )
        if "mcpServers" in manifest and "mcp_servers" in manifest:
            raise ValueError("marketplace.resource.invalid_json_root")
        key = "mcpServers" if "mcpServers" in manifest else "mcp_servers"
        raw_value = manifest.get(key)
        if isinstance(raw_value, dict):
            validate_inline_mcp_servers(
                raw_value,
                source_locator=f"{contract.plugin_manifest_path}#/{key}",
            )
            return MarketplaceResourceOwner(
                file_path=manifest_path.relative_to(package_path).as_posix(),
                json_pointer=f"/{key}/{escaped_name}",
                standalone_file=False,
            )
        references = manifest_reference_values(
            raw_value,
            source_locator=f"{contract.plugin_manifest_path}#/{key}",
        )
        if raw_value is not None and not references:
            raise ValueError("marketplace.resource.invalid_json_root")
        if references:
            candidate = resolve_package_source(
                package_path,
                references[0],
                expected_suffixes=(".json",),
            )
            return MarketplaceResourceOwner(
                file_path=candidate.relative_to(package_path).as_posix(),
                json_pointer=_strict_mcp_document_pointer(
                    package_path,
                    candidate,
                    escaped_name,
                ),
                standalone_file=True,
            )
    except (OSError, json.JSONDecodeError, PackageSourceError) as exc:
        raise ValueError("marketplace.resource.invalid_json_root") from exc

    candidate = package_path / ".mcp.json"
    if candidate.exists():
        try:
            return MarketplaceResourceOwner(
                file_path=".mcp.json",
                json_pointer=_strict_mcp_document_pointer(
                    package_path,
                    candidate,
                    escaped_name,
                ),
                standalone_file=True,
            )
        except (OSError, json.JSONDecodeError, PackageSourceError) as exc:
            raise ValueError("marketplace.resource.invalid_json_root") from exc
    return MarketplaceResourceOwner(
        file_path=".mcp.json",
        json_pointer=(
            f"/{escaped_name}"
            if provider == "claude-code"
            else f"/mcpServers/{escaped_name}"
        ),
        standalone_file=True,
    )


def _strict_mcp_document_pointer(
    package_path: Path,
    document_path: Path,
    escaped_name: str,
) -> str:
    locator = package_relative_locator(package_path, document_path)
    data = read_package_json_object(package_path, document_path)
    key, _servers = mcp_server_map(
        data,
        source_locator=locator,
    )
    return f"/{key}/{escaped_name}" if key else f"/{escaped_name}"
