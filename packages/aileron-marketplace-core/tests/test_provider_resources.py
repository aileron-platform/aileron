import pytest

from aileron_marketplace_core.provider_resources import provider_resource_name_contract


def test_provider_resource_contract_uses_native_root_documents() -> None:
    claude = provider_resource_name_contract("claude-code")
    codex = provider_resource_name_contract("codex")

    assert claude.root_document_name == "CLAUDE.md"
    assert claude.root_document_index_name == "agentsMd"
    assert codex.root_document_name == "AGENTS.md"
    assert codex.root_document_index_name == "agentsMd"


def test_provider_resource_contract_exposes_copy_only_directories() -> None:
    claude_directories = {
        item.source_name
        for item in provider_resource_name_contract("claude-code").indexed_directories
    }
    codex_directories = {
        item.source_name
        for item in provider_resource_name_contract("codex").indexed_directories
    }

    assert "output-styles" in claude_directories
    assert {"agents", "prompts", "rules"} <= codex_directories


def test_provider_resource_contract_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported Marketplace provider"):
        provider_resource_name_contract("opencode")
