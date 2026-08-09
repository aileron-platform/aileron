from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MarketplaceProviderName = Literal["claude-code", "codex"]


@dataclass(frozen=True)
class IndexedResourceDirectory:
    source_name: str
    index_name: str


@dataclass(frozen=True)
class ProviderResourceNameContract:
    provider: MarketplaceProviderName
    root_document_name: str
    root_document_index_name: str
    plugin_manifest_path: str
    indexed_directories: tuple[IndexedResourceDirectory, ...]


_CONTRACTS: dict[str, ProviderResourceNameContract] = {
    "claude-code": ProviderResourceNameContract(
        provider="claude-code",
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
    "codex": ProviderResourceNameContract(
        provider="codex",
        root_document_name="AGENTS.md",
        root_document_index_name="agentsMd",
        plugin_manifest_path=".codex-plugin/plugin.json",
        indexed_directories=(
            IndexedResourceDirectory("skills", "skills"),
            IndexedResourceDirectory("agents", "agents"),
            IndexedResourceDirectory("hooks", "hooks"),
            IndexedResourceDirectory("policies", "policies"),
            IndexedResourceDirectory("apps", "apps"),
            IndexedResourceDirectory("prompts", "prompts"),
            IndexedResourceDirectory("rules", "rules"),
        ),
    ),
}


def provider_resource_name_contract(provider: str) -> ProviderResourceNameContract:
    contract = _CONTRACTS.get(provider)
    if contract is None:
        raise ValueError(f"Unsupported Marketplace provider: {provider}")
    return contract
