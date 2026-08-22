from __future__ import annotations

import threading
from pathlib import Path

from app.modules.marketplace_operations.state import MarketplaceMutationStore


def test_target_client_lock_serializes_only_the_same_target_client(
    tmp_path: Path,
) -> None:
    store = MarketplaceMutationStore(tmp_path / "marketplace")
    codex_acquired = threading.Event()
    claude_acquired = threading.Event()

    def acquire(target_client: str, event: threading.Event) -> None:
        with store.target_client_lock(target_client=target_client):
            event.set()

    with store.target_client_lock(target_client="codex"):
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


def test_target_client_lock_file_contains_no_operation_metadata(tmp_path: Path) -> None:
    store = MarketplaceMutationStore(tmp_path / "marketplace")

    with store.target_client_lock(target_client="codex"):
        lock_path = next(store.locks_root.glob("*.lock"))
        assert lock_path.read_text(encoding="utf-8") == ""
        assert lock_path.stat().st_mode & 0o777 == 0o600

    assert lock_path.read_text(encoding="utf-8") == ""
    assert lock_path.stat().st_mode & 0o777 == 0o600
