"""Graceful, process-wide cleanup after a signed Runtime drain command."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.modules.auth.manager_assertion import RuntimeDrainClaims
from app.modules.runtime_control.state import (
    RuntimeDrainingError,
    get_runtime_admission_state,
)


@dataclass(frozen=True)
class RuntimeDrainConflict(Exception):
    error_code: str


@dataclass(frozen=True)
class RuntimeDrainTimeout(Exception):
    error_code: str = "WORKSPACE_RUNTIME_DRAIN_TIMEOUT"


class RuntimeDrainService:
    """Reject new work, then close every actor-owned local execution surface."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._completed_attempt_id: str | None = None

    async def drain(
        self,
        claims: RuntimeDrainClaims,
        *,
        automation_runner: Any | None = None,
    ) -> None:
        async with self._lock:
            try:
                await get_runtime_admission_state().begin_drain(claims.drain_attempt_id)
            except RuntimeDrainingError as exc:
                raise RuntimeDrainConflict(exc.error_code) from exc

            if self._completed_attempt_id == claims.drain_attempt_id:
                return
            remaining = claims.deadline - int(datetime.now(timezone.utc).timestamp())
            if remaining <= 0:
                raise RuntimeDrainTimeout()
            try:
                await asyncio.wait_for(
                    self._close_all_surfaces(automation_runner),
                    timeout=remaining,
                )
            except TimeoutError:
                raise RuntimeDrainTimeout() from None
            self._completed_attempt_id = claims.drain_attempt_id

    @staticmethod
    async def _close_all_surfaces(automation_runner: Any | None) -> None:
        from app.modules.client_browser_relay.relay import get_relay_service
        from app.modules.thread.agent_runner_factory import (
            drain_agent_runners,
        )
        from app.modules.thread.invalidation_emitter import (
            get_thread_connection_manager,
        )

        cleanup = [
            get_thread_connection_manager().close_all(),
            drain_agent_runners(),
            get_relay_service().full_drain(),
        ]
        if automation_runner is not None:
            cleanup.append(automation_runner.drain())
        results = await asyncio.gather(*cleanup, return_exceptions=True)
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            raise RuntimeError("runtime_drain_cleanup_failed")


_runtime_drain_service = RuntimeDrainService()


def get_runtime_drain_service() -> RuntimeDrainService:
    return _runtime_drain_service


__all__ = [
    "RuntimeDrainConflict",
    "RuntimeDrainService",
    "RuntimeDrainTimeout",
    "get_runtime_drain_service",
]
