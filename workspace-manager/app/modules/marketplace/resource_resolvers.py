from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from aileron_marketplace_core import (
    PackageSourceError,
    PluginResourceOwner,
    read_plugin_resource_owner,
    resolve_claude_plugin_resources,
    resolve_codex_plugin_resources,
)

from app.modules.marketplace.models import MarketplaceProvider


@dataclass(frozen=True)
class MarketplaceResourceOwner:
    file_path: str
    json_pointer: str | None
    standalone_file: bool


@dataclass(frozen=True)
class MarketplaceMcpOwnerBinding:
    """One MCP server name and its canonical provider-native owner."""

    name: str
    owner: MarketplaceResourceOwner


def _provider_resolved_mcp_owners(
    package_root: Path,
    provider: MarketplaceProvider,
) -> tuple[MarketplaceMcpOwnerBinding, ...]:
    resources = (
        resolve_claude_plugin_resources(package_root)
        if provider == "claude-code"
        else resolve_codex_plugin_resources(package_root)
    )
    return tuple(
        MarketplaceMcpOwnerBinding(
            name=name,
            owner=MarketplaceResourceOwner(
                file_path=owner.file_path,
                json_pointer=owner.json_pointer,
                standalone_file=owner.standalone_file,
            ),
        )
        for name, owner in sorted(resources.mcp_servers.items())
    )


def resolve_mcp_owners(
    package_root: Path,
    provider: MarketplaceProvider,
) -> tuple[MarketplaceMcpOwnerBinding, ...]:
    """Resolve the canonical provider-native owner for each MCP server name."""

    return _provider_resolved_mcp_owners(package_root, provider)


def resolve_mcp_owner(
    package_root: Path,
    provider: MarketplaceProvider,
    server_name: str,
    *,
    owner_file_path: str,
) -> MarketplaceResourceOwner | None:
    """Resolve one canonical MCP owner fenced by its exact source file."""

    matches = [
        binding.owner
        for binding in resolve_mcp_owners(package_root, provider)
        if binding.name == server_name and binding.owner.file_path == owner_file_path
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def resolve_hook_sources(
    package_root: Path,
    provider: MarketplaceProvider,
) -> tuple[tuple[PluginResourceOwner, ...], tuple[dict[str, str], ...]]:
    """Resolve every provider-native hooks source without flattening them."""

    resources = (
        resolve_claude_plugin_resources(package_root)
        if provider == "claude-code"
        else resolve_codex_plugin_resources(package_root)
    )
    owners = tuple(resources.hook_sources)
    diagnostics = tuple(
        {
            "code": item.code,
            "sourceLocator": item.source_locator,
        }
        for item in resources.diagnostics
    )
    return owners, diagnostics


def hook_source_id(owner: PluginResourceOwner) -> str:
    return f"{owner.file_path}#{owner.json_pointer}"


def read_hook_source(
    package_root: Path,
    owner: PluginResourceOwner,
) -> tuple[str, dict[str, Any], Any]:
    """Return raw source text, full JSON document, and its hook value."""

    path = package_root / owner.file_path
    raw_content = path.read_text(encoding="utf-8")
    document = json.loads(raw_content)
    if not isinstance(document, dict):
        raise PackageSourceError("source-document-invalid", owner.file_path)
    value = read_plugin_resource_owner(package_root, owner)
    if not isinstance(value, dict):
        raise PackageSourceError("source-document-invalid", owner.file_path)
    return raw_content, document, value
