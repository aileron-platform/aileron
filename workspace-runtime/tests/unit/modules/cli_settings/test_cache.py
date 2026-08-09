from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.modules.cli_settings.cache import ProcessTTLCache


def test_cache_reuses_warm_value_and_manual_clear_reloads() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache()
    calls = 0

    def load() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_load("key", load) == 1
    assert cache.get_or_load("key", load) == 1
    cache.clear(lambda key: key == "key")
    assert cache.get_or_load("key", load) == 2


def test_cache_shares_one_concurrent_loader() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache()
    entered = Event()
    release = Event()
    calls = 0

    def load() -> int:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=2)
        return 7

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_load, "key", load)
        assert entered.wait(timeout=2)
        second = executor.submit(cache.get_or_load, "key", load)
        release.set()
        assert first.result() == 7
        assert second.result() == 7
    assert calls == 1


def test_cache_does_not_store_loader_errors_or_rejected_values() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache()
    calls = 0

    def fail() -> int:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        cache.get_or_load("error", fail)
    with pytest.raises(RuntimeError, match="boom"):
        cache.get_or_load("error", fail)
    assert calls == 2

    assert cache.get_or_load("rejected", lambda: 0, cache_if=bool) == 0
    assert cache.get_or_load("rejected", lambda: 1, cache_if=bool) == 1


def test_cache_evicts_oldest_entry_at_bound() -> None:
    cache: ProcessTTLCache[str, str] = ProcessTTLCache(max_entries=2)
    cache.get_or_load("a", lambda: "a")
    cache.get_or_load("b", lambda: "b")
    cache.get_or_load("c", lambda: "c")
    assert len(cache) == 2
    assert cache.get_or_load("a", lambda: "reloaded") == "reloaded"


def test_cache_reloads_expired_entry() -> None:
    now = 0.0
    cache: ProcessTTLCache[str, int] = ProcessTTLCache(
        ttl_seconds=5,
        clock=lambda: now,
    )
    calls = 0

    def load() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_load("key", load) == 1
    now = 6.0
    assert cache.get_or_load("key", load) == 2


def test_clear_bypasses_an_older_in_flight_loader() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache()
    entered = Event()
    release = Event()

    def slow_load() -> int:
        entered.set()
        assert release.wait(timeout=2)
        return 1

    with ThreadPoolExecutor(max_workers=1) as executor:
        old = executor.submit(cache.get_or_load, "key", slow_load)
        assert entered.wait(timeout=2)
        cache.clear(lambda key: key == "key")
        assert cache.get_or_load("key", lambda: 2) == 2
        release.set()
        assert old.result() == 1

    assert cache.get_or_load("key", lambda: 3) == 2


def test_scoped_clear_keeps_unrelated_in_flight_single_flight() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache()
    entered_loader = Event()
    entered_request = Event()
    unexpected_loader = Event()
    release = Event()

    def slow_load() -> int:
        entered_loader.set()
        assert release.wait(timeout=2)
        return 7

    def join_existing_load() -> int:
        entered_request.set()
        return cache.get_or_load(
            "unrelated",
            lambda: (unexpected_loader.set(), 8)[1],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get_or_load, "unrelated", slow_load)
        assert entered_loader.wait(timeout=2)
        cache.get_or_load("target", lambda: 1)
        cache.clear(lambda key: key == "target")
        second = executor.submit(join_existing_load)
        assert entered_request.wait(timeout=2)
        assert not unexpected_loader.is_set()
        release.set()
        assert first.result() == 7
        assert second.result() == 7


def test_lru_eviction_prunes_epoch_left_by_in_flight_refresh() -> None:
    cache: ProcessTTLCache[str, int] = ProcessTTLCache(max_entries=1)
    entered = Event()
    release = Event()

    def old_load() -> int:
        entered.set()
        assert release.wait(timeout=2)
        return 1

    with ThreadPoolExecutor(max_workers=1) as executor:
        old = executor.submit(cache.get_or_load, "refreshed", old_load)
        assert entered.wait(timeout=2)
        cache.clear(lambda key: key == "refreshed")
        assert cache.get_or_load("refreshed", lambda: 2) == 2
        release.set()
        assert old.result() == 1

    assert len(cache._epochs) == 1
    cache.get_or_load("replacement", lambda: 3)

    assert len(cache) == 1
    assert cache._epochs == {}


def test_expired_entry_prunes_epoch_left_by_in_flight_refresh() -> None:
    now = 0.0
    cache: ProcessTTLCache[str, int] = ProcessTTLCache(
        ttl_seconds=5,
        clock=lambda: now,
    )
    entered = Event()
    release = Event()

    def old_load() -> int:
        entered.set()
        assert release.wait(timeout=2)
        return 1

    with ThreadPoolExecutor(max_workers=1) as executor:
        old = executor.submit(cache.get_or_load, "refreshed", old_load)
        assert entered.wait(timeout=2)
        cache.clear(lambda key: key == "refreshed")
        assert cache.get_or_load("refreshed", lambda: 2) == 2
        release.set()
        assert old.result() == 1

    assert len(cache._epochs) == 1
    now = 6.0
    assert cache.get_or_load("refreshed", lambda: 3) == 3

    assert len(cache) == 1
    assert cache._epochs == {}
