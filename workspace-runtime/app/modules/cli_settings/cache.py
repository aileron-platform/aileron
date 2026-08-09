"""Small process-local caches for agent settings discovery."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

DEFAULT_AGENT_SETTINGS_CACHE_TTL_SECONDS = 300.0
DEFAULT_AGENT_SETTINGS_CACHE_MAX_ENTRIES = 128


@dataclass(frozen=True)
class _CacheEntry(Generic[V]):
    value: V
    expires_at: float


class ProcessTTLCache(Generic[K, V]):
    """Bounded cache-aside store with one loader per cold key."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_AGENT_SETTINGS_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_AGENT_SETTINGS_CACHE_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._in_flight: dict[tuple[int, K], Future[V]] = {}
        self._epochs: dict[K, int] = {}
        self._lock = threading.Lock()

    def get_or_load(
        self,
        key: K,
        loader: Callable[[], V],
        *,
        cache_if: Callable[[V], bool] | None = None,
    ) -> V:
        """Return a warm value or load once; loader failures are never cached."""

        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self._entries.move_to_end(key)
                return entry.value
            if self._entries.pop(key, None) is not None:
                self._prune_epoch(key)

            epoch = self._epochs.get(key, 0)
            in_flight_key = (epoch, key)
            future = self._in_flight.get(in_flight_key)
            if future is None:
                future = Future()
                self._in_flight[in_flight_key] = future
                leader = True
            else:
                leader = False

        if not leader:
            return future.result()

        try:
            value = loader()
        except BaseException as exc:
            future.set_exception(exc)
            raise
        else:
            if cache_if is None or cache_if(value):
                with self._lock:
                    if self._epochs.get(key, 0) == epoch:
                        self._entries[key] = _CacheEntry(
                            value=value,
                            expires_at=self._clock() + self._ttl_seconds,
                        )
                        self._entries.move_to_end(key)
                        while len(self._entries) > self._max_entries:
                            evicted_key, _ = self._entries.popitem(last=False)
                            self._prune_epoch(evicted_key)
            future.set_result(value)
            return value
        finally:
            with self._lock:
                if self._in_flight.get(in_flight_key) is future:
                    self._in_flight.pop(in_flight_key, None)
                self._prune_epoch(key)

    def clear(self, predicate: Callable[[K], bool] | None = None) -> None:
        """Clear all completed entries or only matching keys."""

        with self._lock:
            known_keys = set(self._entries)
            known_keys.update(key for _, key in self._in_flight)
            matching_keys = (
                known_keys
                if predicate is None
                else {key for key in known_keys if predicate(key)}
            )
            for key in matching_keys:
                self._entries.pop(key, None)
                self._epochs[key] = self._epochs.get(key, 0) + 1
                self._prune_epoch(key)

    def _prune_epoch(self, key: K) -> None:
        if key in self._entries:
            return
        if any(in_flight_key == key for _, in_flight_key in self._in_flight):
            return
        self._epochs.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


__all__ = [
    "DEFAULT_AGENT_SETTINGS_CACHE_MAX_ENTRIES",
    "DEFAULT_AGENT_SETTINGS_CACHE_TTL_SECONDS",
    "ProcessTTLCache",
]
