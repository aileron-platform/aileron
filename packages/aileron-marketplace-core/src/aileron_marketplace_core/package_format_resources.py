from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NativePackageFormatName = Literal["claude-native", "codex-native"]


@dataclass(frozen=True)
class IndexedResourceDirectory:
    source_name: str
    index_name: str


@dataclass(frozen=True)
class PackageFormatResourceNameContract:
    package_format: NativePackageFormatName
    root_document_name: str
    root_document_index_name: str
    plugin_manifest_path: str
    indexed_directories: tuple[IndexedResourceDirectory, ...]


_CONTRACTS: dict[str, PackageFormatResourceNameContract] = {
    "claude-native": PackageFormatResourceNameContract(
        package_format="claude-native",
        root_document_name="CLAUDE.md",
        root_document_index_name="agentsMd",
        plugin_manifest_path=".claude-plugin/plugin.json",
        indexed_directories=(
            IndexedResourceDirectory("skills", "skills"),
            IndexedResourceDirectory("commands", "commands"),
            IndexedResourceDirectory("agents", "agents"),
            IndexedResourceDirectory("hooks", "hooks"),
            IndexedResourceDirectory("policies", "policies"),
            IndexedResourceDirectory("output-styles", "output-style"),
        ),
    ),
    "codex-native": PackageFormatResourceNameContract(
        package_format="codex-native",
        root_document_name="AGENTS.md",
        root_document_index_name="agentsMd",
        plugin_manifest_path=".codex-plugin/plugin.json",
        indexed_directories=(
            IndexedResourceDirectory("skills", "skills"),
            IndexedResourceDirectory("agents", "agents"),
            IndexedResourceDirectory("hooks", "hooks"),
            IndexedResourceDirectory("policies", "policies"),
            IndexedResourceDirectory("apps", "apps"),
            IndexedResourceDirectory("commands", "commands"),
            IndexedResourceDirectory("rules", "rules"),
        ),
    ),
}


def package_format_resource_name_contract(package_format: str) -> PackageFormatResourceNameContract:
    contract = _CONTRACTS.get(package_format)
    if contract is None:
        raise ValueError(f"Unsupported Marketplace package_format: {package_format}")
    return contract
