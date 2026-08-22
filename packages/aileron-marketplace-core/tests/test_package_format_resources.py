import pytest

from aileron_marketplace_core.package_format_resources import package_format_resource_name_contract


def test_package_format_resource_contract_uses_native_root_documents() -> None:
    claude = package_format_resource_name_contract("claude-native")
    codex = package_format_resource_name_contract("codex-native")

    assert claude.root_document_name == "CLAUDE.md"
    assert claude.root_document_index_name == "agentsMd"
    assert codex.root_document_name == "AGENTS.md"
    assert codex.root_document_index_name == "agentsMd"


def test_target_client_resource_contract_exposes_copy_only_directories() -> None:
    claude_directories = {
        item.source_name
        for item in package_format_resource_name_contract("claude-native").indexed_directories
    }
    codex_directories = {
        item.source_name
        for item in package_format_resource_name_contract("codex-native").indexed_directories
    }

    assert "output-styles" in claude_directories
    assert {"agents", "commands", "rules"} <= codex_directories
    assert "prompts" not in codex_directories


def test_target_client_resource_contract_rejects_unknown_target_client() -> None:
    with pytest.raises(ValueError, match="Unsupported Marketplace package_format"):
        package_format_resource_name_contract("opencode")
