"""Provider mutation serialization and cache generation."""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar, cast

from app.config.settings import get_settings

from .errors import MarketplaceOperationError
from .state import MarketplaceMutationStore, write_json_atomic

T = TypeVar("T")
_settings_lock_provider: ContextVar[str | None] = ContextVar(
    "marketplace_settings_lock_provider",
    default=None,
)


class MarketplaceProviderGate:
    """Expose only a shared mutation lock and cache generation."""

    def __init__(self, store: MarketplaceMutationStore) -> None:
        self._store = store
        self._state_path = store.root / "provider-cache-generation.json"

    def run_settings_mutation(
        self,
        provider: str,
        mutation: Callable[[], T],
    ) -> tuple[T, int]:
        """Run one settings mutation and advance its cache generation."""

        if _settings_lock_provider.get() == provider:
            result = mutation()
            return result, self.advance_generation(provider)
        with self.settings_mutation_scope(provider):
            result = mutation()
            return result, self.advance_generation(provider)

    @contextmanager
    def settings_mutation_scope(self, provider: str) -> Iterator[None]:
        """Serialize one public provider settings request."""

        current = _settings_lock_provider.get()
        if current == provider:
            yield
            return
        if current is not None:
            raise MarketplaceOperationError(
                "marketplace.install.provider_invalid",
                http_status=409,
            )
        with self._store.provider_lock(
            provider=provider,
        ):
            token = _settings_lock_provider.set(provider)
            try:
                yield
            finally:
                _settings_lock_provider.reset(token)

    def complete_settings_mutation(
        self,
        provider: str,
        *,
        previous_generation: int,
    ) -> int:
        """Advance once for a successful public mutation request."""

        if _settings_lock_provider.get() != provider:
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=409,
            )
        current = self.generation(provider)
        if current != previous_generation:
            return current
        return self.advance_generation(provider)

    def advance_generation(self, provider: str) -> int:
        """Advance provider cache invalidation after a mutation attempt."""

        with self._mutation_lock():
            state = self._read_state()
            provider_state = self._ensure_provider(state, provider)
            provider_state["generation"] = int(provider_state["generation"]) + 1
            self._write_state(state)
            return int(provider_state["generation"])

    def generation(self, provider: str) -> int:
        """Read the current provider cache generation."""

        with self._mutation_lock():
            return int(
                self._ensure_provider(
                    self._read_state(),
                    provider,
                )["generation"]
            )

    def _read_state(self) -> dict[str, Any]:
        self._store.ensure()
        if not self._state_path.exists():
            return {"stateVersion": 1, "providers": {}}
        if self._state_path.is_symlink() or not self._state_path.is_file():
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=503,
            )
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=503,
            ) from exc
        if (
            not isinstance(state, dict)
            or state.get("stateVersion") != 1
            or not isinstance(state.get("providers"), dict)
        ):
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=503,
            )
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        write_json_atomic(self._state_path, state)

    @contextmanager
    def _mutation_lock(self) -> Iterator[None]:
        """Serialize the cache generation document across processes."""

        self._store.ensure()
        lock_path = self._store.locks_root / "provider-cache-generation.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            os.chmod(lock_path, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _ensure_provider(
        state: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        if provider not in {"claude-code", "codex"}:
            raise MarketplaceOperationError(
                "marketplace.install.provider_invalid",
                http_status=422,
            )
        providers = state.setdefault("providers", {})
        provider_state = providers.setdefault(provider, {"generation": 0})
        if (
            not isinstance(provider_state, dict)
            or type(provider_state.get("generation")) is not int
            or int(provider_state["generation"]) < 0
        ):
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=503,
            )
        return cast(dict[str, Any], provider_state)


@lru_cache
def get_marketplace_provider_gate() -> MarketplaceProviderGate:
    settings = get_settings()
    store = MarketplaceMutationStore(Path(settings.MARKETPLACE_OPERATION_JOURNAL_DIR))
    return MarketplaceProviderGate(store)


__all__ = ["MarketplaceProviderGate", "get_marketplace_provider_gate"]
