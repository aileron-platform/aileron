"""Target client mutation serialization and cache generation."""

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
_settings_lock_target_client: ContextVar[str | None] = ContextVar(
    "marketplace_settings_lock_target_client",
    default=None,
)


class MarketplaceTargetClientGate:
    """Expose only a shared mutation lock and cache generation."""

    def __init__(self, store: MarketplaceMutationStore) -> None:
        self._store = store
        self._state_path = store.root / "target-client-cache-generation.json"

    def run_settings_mutation(
        self,
        target_client: str,
        mutation: Callable[[], T],
    ) -> tuple[T, int]:
        """Run one settings mutation and advance its cache generation."""

        if _settings_lock_target_client.get() == target_client:
            result = mutation()
            return result, self.advance_generation(target_client)
        with self.settings_mutation_scope(target_client):
            result = mutation()
            return result, self.advance_generation(target_client)

    @contextmanager
    def settings_mutation_scope(self, target_client: str) -> Iterator[None]:
        """Serialize one public target_client settings request."""

        current = _settings_lock_target_client.get()
        if current == target_client:
            yield
            return
        if current is not None:
            raise MarketplaceOperationError(
                "marketplace.install.target_client_invalid",
                http_status=409,
            )
        with self._store.target_client_lock(
            target_client=target_client,
        ):
            token = _settings_lock_target_client.set(target_client)
            try:
                yield
            finally:
                _settings_lock_target_client.reset(token)

    def complete_settings_mutation(
        self,
        target_client: str,
        *,
        previous_generation: int,
    ) -> int:
        """Advance once for a successful public mutation request."""

        if _settings_lock_target_client.get() != target_client:
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=409,
            )
        current = self.generation(target_client)
        if current != previous_generation:
            return current
        return self.advance_generation(target_client)

    def advance_generation(self, target_client: str) -> int:
        """Advance target_client cache invalidation after a mutation attempt."""

        with self._mutation_lock():
            state = self._read_state()
            client_state = self._ensure_target_client(state, target_client)
            client_state["generation"] = int(client_state["generation"]) + 1
            self._write_state(state)
            return int(client_state["generation"])

    def generation(self, target_client: str) -> int:
        """Read the current target_client cache generation."""

        with self._mutation_lock():
            return int(
                self._ensure_target_client(
                    self._read_state(),
                    target_client,
                )["generation"]
            )

    def _read_state(self) -> dict[str, Any]:
        self._store.ensure()
        if not self._state_path.exists():
            return {"stateVersion": 1, "targetClients": {}}
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
            or not isinstance(state.get("targetClients"), dict)
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
        lock_path = self._store.locks_root / "target-client-cache-generation.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            os.chmod(lock_path, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _ensure_target_client(
        state: dict[str, Any],
        target_client: str,
    ) -> dict[str, Any]:
        if target_client not in {"claude-code", "codex"}:
            raise MarketplaceOperationError(
                "marketplace.install.target_client_invalid",
                http_status=422,
            )
        target_clients = state.setdefault("targetClients", {})
        client_state = target_clients.setdefault(target_client, {"generation": 0})
        if (
            not isinstance(client_state, dict)
            or type(client_state.get("generation")) is not int
            or int(client_state["generation"]) < 0
        ):
            raise MarketplaceOperationError(
                "marketplace.install.runtime_state_missing",
                http_status=503,
            )
        return cast(dict[str, Any], client_state)


@lru_cache
def get_marketplace_target_client_gate() -> MarketplaceTargetClientGate:
    settings = get_settings()
    store = MarketplaceMutationStore(Path(settings.MARKETPLACE_OPERATION_JOURNAL_DIR))
    return MarketplaceTargetClientGate(store)


__all__ = ["MarketplaceTargetClientGate", "get_marketplace_target_client_gate"]
