from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.gate import MarketplaceProviderGate
from app.modules.marketplace_operations.state import MarketplaceMutationStore


def test_generation_persists_without_installation_state(tmp_path: Path) -> None:
    root = tmp_path / "marketplace"
    gate = MarketplaceProviderGate(MarketplaceMutationStore(root))

    assert gate.generation("codex") == 0
    assert gate.advance_generation("codex") == 1
    assert gate.advance_generation("claude-code") == 1

    restarted = MarketplaceProviderGate(MarketplaceMutationStore(root))
    assert restarted.generation("codex") == 1
    assert restarted.generation("claude-code") == 1
    state = (root / "provider-cache-generation.json").read_text(encoding="utf-8")
    assert "quarantined" not in state
    assert "unsafe" not in state
    assert "operation" not in state.casefold()


def test_concurrent_generation_advances_are_not_lost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = MarketplaceProviderGate(MarketplaceMutationStore(tmp_path / "marketplace"))
    original_write = gate._write_state

    def delayed_write(state) -> None:
        time.sleep(0.002)
        original_write(state)

    monkeypatch.setattr(gate, "_write_state", delayed_write)
    providers = ["codex" if index % 2 == 0 else "claude-code" for index in range(24)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(gate.advance_generation, providers))

    assert gate.generation("codex") == 12
    assert gate.generation("claude-code") == 12


def test_settings_mutation_holds_provider_lock_and_advances_once(
    tmp_path: Path,
) -> None:
    gate = MarketplaceProviderGate(MarketplaceMutationStore(tmp_path / "marketplace"))

    with gate.settings_mutation_scope("codex"):
        result, generation = gate.run_settings_mutation(
            "codex",
            lambda: "written",
        )
        assert (
            gate.complete_settings_mutation(
                "codex",
                previous_generation=0,
            )
            == 1
        )

    assert result == "written"
    assert generation == 1
    assert gate.generation("codex") == 1


def test_invalid_provider_is_rejected(tmp_path: Path) -> None:
    gate = MarketplaceProviderGate(MarketplaceMutationStore(tmp_path / "marketplace"))

    with pytest.raises(MarketplaceOperationError) as exc_info:
        gate.generation("unknown")

    assert exc_info.value.code == "marketplace.install.provider_invalid"
