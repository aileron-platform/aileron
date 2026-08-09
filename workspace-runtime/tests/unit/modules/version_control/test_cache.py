from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.version_control.cache import (
    CacheKeys,
    GitCache,
    GitCacheInvalidator,
    WorkspaceGitCacheEffects,
    create_git_cache,
)


def test_process_local_cache_round_trip_and_parameter_isolation() -> None:
    cache = GitCache(ttl=60)

    assert cache.set("workspace-1", CacheKeys.STATUS, {"clean": True}, branch="main")
    assert cache.get("workspace-1", CacheKeys.STATUS, branch="main") == {"clean": True}
    assert cache.get("workspace-1", CacheKeys.STATUS, branch="feature") is None
    assert cache.get("workspace-2", CacheKeys.STATUS, branch="main") is None


def test_cache_expiration_uses_monotonic_clock() -> None:
    cache = GitCache(ttl=10)
    with patch(
        "app.modules.version_control.cache.time.monotonic",
        side_effect=[100.0, 109.0, 111.0],
    ):
        assert cache.set("workspace-1", CacheKeys.STATUS, {"clean": True})
        assert cache.get("workspace-1", CacheKeys.STATUS) == {"clean": True}
        assert cache.get("workspace-1", CacheKeys.STATUS) is None


def test_cache_is_bounded_and_evicts_earliest_expiry() -> None:
    cache = GitCache(ttl=60, max_entries=2)
    with patch(
        "app.modules.version_control.cache.time.monotonic",
        side_effect=[100.0, 101.0, 102.0, 103.0, 103.0, 103.0],
    ):
        cache.set("workspace-1", CacheKeys.STATUS, {"value": 1}, ttl=10)
        cache.set("workspace-1", CacheKeys.BRANCHES, {"value": 2}, ttl=20)
        cache.set("workspace-1", CacheKeys.COMMITS, {"value": 3}, ttl=30)
        assert cache.get("workspace-1", CacheKeys.STATUS) is None
        assert cache.get("workspace-1", CacheKeys.BRANCHES) == {"value": 2}
        assert cache.get("workspace-1", CacheKeys.COMMITS) == {"value": 3}


def test_cache_invalidation_is_scoped_by_workspace_and_effect() -> None:
    cache = GitCache()
    cache.set("workspace-1", CacheKeys.STATUS, {"value": 1})
    cache.set("workspace-1", CacheKeys.COMMITS, {"value": 2})
    cache.set("workspace-2", CacheKeys.STATUS, {"value": 3})

    invalidator = GitCacheInvalidator(cache)
    assert invalidator.invalidate_effects("workspace-1", [CacheKeys.STATUS]) == 1
    assert cache.get("workspace-1", CacheKeys.STATUS) is None
    assert cache.get("workspace-1", CacheKeys.COMMITS) == {"value": 2}
    assert cache.get("workspace-2", CacheKeys.STATUS) == {"value": 3}


def test_operation_effects_are_deduplicated_and_clear_all_reports_count() -> None:
    cache = GitCache()
    cache.set("workspace-1", CacheKeys.STATUS, {"value": 1})
    cache.set("workspace-1", CacheKeys.CHANGES, {"value": 2})
    invalidator = GitCacheInvalidator(cache)

    effects = WorkspaceGitCacheEffects.for_operation("stage")
    assert invalidator.invalidate_effects("workspace-1", effects + effects) == 2
    cache.set("workspace-1", CacheKeys.STATUS, {"value": 3})
    assert cache.clear_all() == 1
    assert cache.clear_all() == 0


def test_disabled_cache_is_a_noop() -> None:
    cache = create_git_cache(enabled=False)

    assert cache.set("workspace-1", CacheKeys.STATUS, {"clean": True}) is False
    assert cache.get("workspace-1", CacheKeys.STATUS) is None
    assert cache.invalidate_all("workspace-1") == 0
    assert cache.get_stats("workspace-1") == {
        "enabled": False,
        "total_keys": 0,
        "memory_usage": 0,
    }


@pytest.mark.parametrize("ttl,max_entries", [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_cache_rejects_non_positive_limits(ttl: int, max_entries: int) -> None:
    with pytest.raises(ValueError):
        GitCache(ttl=ttl, max_entries=max_entries)
