"""Process-local admission state for one Runtime generation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeDrainingError(Exception):
    """Raised when a new Runtime action is attempted after drain begins."""

    error_code: str = "WORKSPACE_RUNTIME_DRAINING"


class RuntimeAdmissionState:
    """Close local entry points before terminating a Runtime generation."""

    def __init__(self) -> None:
        self._draining = False
        self._drain_attempt_id: str | None = None
        self._lock = asyncio.Lock()

    @property
    def is_draining(self) -> bool:
        return self._draining

    def require_accepting(self) -> None:
        if self._draining:
            raise RuntimeDrainingError()

    async def begin_drain(self, drain_attempt_id: str) -> bool:
        """Start one immutable drain attempt and reject conflicting attempts."""

        async with self._lock:
            if self._drain_attempt_id is None:
                self._drain_attempt_id = drain_attempt_id
                self._draining = True
                return True
            if self._drain_attempt_id != drain_attempt_id:
                raise RuntimeDrainingError("WORKSPACE_RUNTIME_DRAIN_ATTEMPT_MISMATCH")
            return False


_runtime_admission_state = RuntimeAdmissionState()


def get_runtime_admission_state() -> RuntimeAdmissionState:
    return _runtime_admission_state


__all__ = [
    "RuntimeAdmissionState",
    "RuntimeDrainingError",
    "get_runtime_admission_state",
]
