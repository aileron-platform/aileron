from concurrent.futures import ThreadPoolExecutor
from datetime import timezone

import pytest

from aileron_git_core import GitOperationInProgressError, OperationKind, OperationManager
from aileron_git_core.contracts import LockScope, LockScopeKeys, VersionControlOperation


def test_same_thread_blocking_reentrant_is_allowed() -> None:
    manager = OperationManager()
    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        with manager.acquire(key="workspace:1", kind=OperationKind.REMOTE):
            with manager.acquire(key="workspace:1", kind=OperationKind.WORKING_TREE):
                assert True


def test_blocking_operation_from_different_thread_conflicts() -> None:
    manager = OperationManager()

    def write_operation() -> None:
        with manager.acquire(key="workspace:1", kind=OperationKind.REMOTE):
            pass

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(write_operation).result(timeout=1)


def test_nested_blocking_context_does_not_release_outer_lock() -> None:
    manager = OperationManager()

    def remote_operation() -> None:
        with manager.acquire(key="workspace:1", kind=OperationKind.REMOTE):
            pass

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        with manager.acquire(key="workspace:1", kind=OperationKind.WORKING_TREE):
            pass
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(remote_operation).result(timeout=1)


def test_reentrant_read_inside_blocking_operation_is_allowed() -> None:
    manager = OperationManager()
    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        with manager.acquire(key="workspace:1", kind=OperationKind.READ):
            assert True


def test_read_from_different_thread_is_allowed_during_write() -> None:
    manager = OperationManager()

    def read_operation() -> bool:
        with manager.acquire(key="workspace:1", kind=OperationKind.READ):
            return True

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(read_operation).result(timeout=1) is True


def test_blocking_operation_metadata_is_visible_while_active() -> None:
    manager = OperationManager()

    with manager.acquire(
        key="workspace:1:primary",
        kind=OperationKind.WORKING_TREE,
        operation_name="checkout",
        cache_effects=["status", "changes"],
    ):
        active = manager.active_operation("workspace:1:primary")

    assert active is not None
    assert active.key == "workspace:1:primary"
    assert active.kind == OperationKind.WORKING_TREE
    assert active.operation_name == "checkout"
    assert active.blocking is True
    assert active.cache_effects == ("status", "changes")
    assert active.started_at.tzinfo == timezone.utc
    assert manager.active_operation("workspace:1:primary") is None


def test_blocking_operation_releases_after_exception() -> None:
    manager = OperationManager()

    with pytest.raises(RuntimeError, match="boom"):
        with manager.acquire(key="workspace:1", kind=OperationKind.WRITE, operation_name="stage"):
            raise RuntimeError("boom")

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE, operation_name="commit"):
        assert manager.active_operation("workspace:1") is not None


def test_different_keys_can_block_in_parallel() -> None:
    manager = OperationManager()

    def write_other_key() -> bool:
        with manager.acquire(key="workspace:2", kind=OperationKind.WRITE, operation_name="stage"):
            return True

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE, operation_name="stage"):
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(write_other_key).result(timeout=1) is True


def test_is_blocking_active_ignores_read_operations() -> None:
    manager = OperationManager()

    with manager.acquire(key="workspace:1", kind=OperationKind.READ, operation_name="status"):
        assert manager.is_blocking_active("workspace:1") is False


def test_operation_metadata_uses_kind_as_default_name() -> None:
    manager = OperationManager()

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE):
        active = manager.active_operation("workspace:1")

    assert active is not None
    assert active.operation_name == OperationKind.WRITE.value


def test_operation_metadata_cache_effects_are_immutable() -> None:
    manager = OperationManager()

    with manager.acquire(key="workspace:1", kind=OperationKind.WRITE, cache_effects=["status"]):
        active = manager.active_operation("workspace:1")

    assert active is not None
    with pytest.raises(AttributeError):
        active.cache_effects.append("changes")


def test_file_write_barrier_blocks_working_tree_operation_from_other_thread() -> None:
    manager = OperationManager()

    def pull_operation() -> None:
        with manager.acquire(key="workspace:1", kind=OperationKind.WORKING_TREE):
            pass

    with manager.acquire_file_write_barrier("workspace:1"):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(pull_operation).result(timeout=1)


def test_working_tree_operation_blocks_file_write_from_other_thread() -> None:
    manager = OperationManager()

    def write_file() -> None:
        with manager.acquire_file_write_barrier("workspace:1"):
            pass

    with manager.acquire(key="workspace:1", kind=OperationKind.WORKING_TREE):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(write_file).result(timeout=1)


def test_file_write_barrier_allows_remote_operation() -> None:
    manager = OperationManager()

    def fetch_operation() -> bool:
        with manager.acquire(key="workspace:1", kind=OperationKind.REMOTE):
            return True

    with manager.acquire_file_write_barrier("workspace:1"):
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(fetch_operation).result(timeout=1) is True


def test_target_only_operations_can_run_on_different_working_trees() -> None:
    manager = OperationManager()
    first = LockScopeKeys("repository:1", "repository:1:primary")
    second = LockScopeKeys("repository:1", "repository:1:feature")

    def stage_other_target() -> bool:
        with manager.acquire_scoped(second, VersionControlOperation.CHANGES_STAGE_ALL):
            return True

    with manager.acquire_scoped(first, VersionControlOperation.CHANGES_STAGE_ALL):
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(stage_other_target).result(timeout=1) is True


def test_common_operations_conflict_across_working_trees() -> None:
    manager = OperationManager()
    first = LockScopeKeys("repository:1", "repository:1:primary")
    second = LockScopeKeys("repository:1", "repository:1:feature")

    def fetch_other_target() -> None:
        with manager.acquire_scoped(second, VersionControlOperation.REMOTE_FETCH):
            pass

    with manager.acquire_scoped(first, VersionControlOperation.REMOTE_FETCH):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError) as raised:
                executor.submit(fetch_other_target).result(timeout=1)

    assert raised.value.blocking_scope == LockScope.COMMON_REPOSITORY


def test_both_scope_operation_acquires_common_before_target() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    def switch_branch() -> None:
        with manager.acquire_scoped(keys, VersionControlOperation.BRANCH_SWITCH):
            pass

    with manager.acquire_scoped(keys, VersionControlOperation.REMOTE_FETCH):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(switch_branch).result(timeout=1)

    with manager.acquire_scoped(keys, VersionControlOperation.CHANGES_STAGE_ALL):
        assert manager.active_operation(keys.working_tree_target) is not None


def test_both_scope_operation_releases_every_scope_after_failure() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    with pytest.raises(RuntimeError, match="boom"):
        with manager.acquire_scoped(keys, VersionControlOperation.COMMIT_CREATE):
            raise RuntimeError("boom")

    assert manager.active_operation(keys.common_repository) is None
    assert manager.active_operation(keys.working_tree_target) is None


def test_scoped_status_exposes_actor_operation_and_real_blocking_scope() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    with manager.acquire_scoped(
        keys,
        VersionControlOperation.REMOTE_FETCH,
        actor_display_name="Taylor",
    ):
        active = manager.active_operation(keys.common_repository)

    assert active is not None
    assert active.operation_name == "remote.fetch"
    assert active.actor_display_name == "Taylor"
    assert active.blocking_scope == LockScope.COMMON_REPOSITORY


def test_scoped_read_rejects_half_complete_target_mutation() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    def read_status() -> None:
        with manager.acquire_read_scoped(keys):
            pass

    with manager.acquire_scoped(keys, VersionControlOperation.CHANGES_STAGE_ALL):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError) as raised:
                executor.submit(read_status).result(timeout=1)

    assert raised.value.blocking_scope == LockScope.WORKING_TREE_TARGET


def test_scoped_mutation_does_not_start_while_read_snapshot_is_active() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    def stage_all() -> None:
        with manager.acquire_scoped(keys, VersionControlOperation.CHANGES_STAGE_ALL):
            pass

    with manager.acquire_read_scoped(keys):
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pytest.raises(GitOperationInProgressError):
                executor.submit(stage_all).result(timeout=1)


def test_cancellable_operation_exposes_progress_and_cancel_request() -> None:
    manager = OperationManager()
    keys = LockScopeKeys("repository:1", "repository:1:primary")

    with manager.acquire_scoped(keys, VersionControlOperation.LFS_SNAPSHOT_CONVERT):
        manager.update_progress(
            keys.working_tree_target,
            current=2,
            total=5,
            phase="renormalizing",
        )
        assert manager.request_cancel(keys.working_tree_target) is True
        active = manager.active_operation(keys.working_tree_target)

    assert active is not None
    assert active.progress_current == 2
    assert active.progress_total == 5
    assert active.phase == "renormalizing"
    assert active.cancellable is True
    assert active.cancel_requested is True
