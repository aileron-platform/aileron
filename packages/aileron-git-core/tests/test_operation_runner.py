from pathlib import Path
from typing import Callable

import pytest

from aileron_git_core import OperationKind, OperationManager, run_operation
from aileron_git_core import operation_runner


def test_read_operation_runs_callback_without_stale_lock_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = OperationManager()

    def fail_recovery(*args: object, **kwargs: object) -> None:
        raise AssertionError("read operations must not use stale lock recovery")

    monkeypatch.setattr(operation_runner, "with_stale_lock_recovery", fail_recovery)

    result = run_operation(
        manager,
        key="workspace:1",
        kind=OperationKind.READ,
        operation_name="status",
        repo_root=Path("/workspace"),
        callback=lambda: "ok",
    )

    assert result == "ok"
    assert manager.active_operation("workspace:1") is None


def test_mutating_operation_uses_shared_lock_and_stale_lock_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = OperationManager()
    observed: dict[str, object] = {}

    def recover(
        repo_root: Path,
        callback: Callable[[], str],
        *,
        threshold_seconds: int,
    ) -> str:
        observed["repo_root"] = repo_root
        observed["threshold"] = threshold_seconds
        active = manager.active_operation("workspace:1")
        observed["operation_name"] = active.operation_name if active else None
        return callback()

    monkeypatch.setattr(operation_runner, "with_stale_lock_recovery", recover)

    result = run_operation(
        manager,
        key="workspace:1",
        kind=OperationKind.WORKING_TREE,
        operation_name="checkout",
        repo_root=Path("/workspace"),
        callback=lambda: "done",
        cache_effects=("status", "changes"),
        stale_threshold_seconds=17,
    )

    assert result == "done"
    assert observed == {
        "repo_root": Path("/workspace"),
        "threshold": 17,
        "operation_name": "checkout",
    }
    assert manager.active_operation("workspace:1") is None


def test_operation_releases_lock_when_callback_fails() -> None:
    manager = OperationManager()

    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_operation(
            manager,
            key="workspace:1",
            kind=OperationKind.READ,
            operation_name="status",
            repo_root=Path("/workspace"),
            callback=fail,
        )

    assert manager.active_operation("workspace:1") is None
