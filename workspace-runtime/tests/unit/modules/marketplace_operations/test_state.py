from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.marketplace_operations.state import MarketplaceMutationStore


def test_provider_state_root_identity_is_stable_across_restart(
    tmp_path: Path,
) -> None:
    root = tmp_path / "marketplace"

    first = MarketplaceMutationStore(root).provider_state_root_id
    second = MarketplaceMutationStore(root).provider_state_root_id

    assert first == second
    assert first.startswith("psr_")
    assert len(first) == 68
    assert (root / "identity.json").stat().st_mode & 0o777 == 0o600


def test_provider_state_root_identity_is_atomically_published(
    tmp_path: Path,
) -> None:
    root = tmp_path / "marketplace"
    workers = 16
    barrier = threading.Barrier(workers)

    def read_identity(_index: int) -> str:
        barrier.wait()
        return MarketplaceMutationStore(root).provider_state_root_id

    with ThreadPoolExecutor(max_workers=workers) as executor:
        identities = list(executor.map(read_identity, range(workers)))

    assert len(set(identities)) == 1


def test_provider_identity_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "marketplace"
    root.mkdir()
    target = tmp_path / "outside-identity.json"
    target.write_text(
        (f'{{"identityVersion":1,"providerStateRootId":"psr_{"a" * 64}"}}'),
        encoding="utf-8",
    )
    (root / "identity.json").symlink_to(target)

    with pytest.raises(MarketplaceOperationError):
        _ = MarketplaceMutationStore(root).provider_state_root_id


def test_provider_lock_serializes_only_the_same_provider(
    tmp_path: Path,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "marketplace")
    codex_acquired = threading.Event()
    claude_acquired = threading.Event()

    def acquire(provider: str, event: threading.Event) -> None:
        with store.provider_lock(provider=provider):
            event.set()

    with store.provider_lock(provider="codex"):
        codex_thread = threading.Thread(
            target=acquire,
            args=("codex", codex_acquired),
        )
        claude_thread = threading.Thread(
            target=acquire,
            args=("claude-code", claude_acquired),
        )
        codex_thread.start()
        claude_thread.start()
        assert codex_acquired.wait(0.1) is False
        assert claude_acquired.wait(1) is True

    assert codex_acquired.wait(1) is True
    codex_thread.join(timeout=1)
    claude_thread.join(timeout=1)


def test_provider_lock_file_contains_no_operation_metadata(tmp_path: Path) -> None:
    store = MarketplaceMutationStore(tmp_path / "marketplace")

    with store.provider_lock(provider="codex"):
        lock_path = next(store.locks_root.glob("*.lock"))
        assert lock_path.read_text(encoding="utf-8") == ""
        assert lock_path.stat().st_mode & 0o777 == 0o600

    assert lock_path.read_text(encoding="utf-8") == ""
    assert lock_path.stat().st_mode & 0o777 == 0o600
