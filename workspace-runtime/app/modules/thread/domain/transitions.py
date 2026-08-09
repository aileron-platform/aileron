from __future__ import annotations

from dataclasses import dataclass

from app.modules.thread.domain.enums import ThreadStatus


ALLOWED_TRANSITIONS: dict[ThreadStatus, set[ThreadStatus]] = {
    ThreadStatus.DRAFT: {ThreadStatus.QUEUED},
    ThreadStatus.QUEUED: {
        ThreadStatus.BOOTING,
        ThreadStatus.CANCELED,
        ThreadStatus.ERROR,
    },
    ThreadStatus.BOOTING: {
        ThreadStatus.WORKING,
        ThreadStatus.STOPPING,
        ThreadStatus.ERROR,
    },
    ThreadStatus.WORKING: {
        ThreadStatus.STOPPING,
        ThreadStatus.COMPLETE,
        ThreadStatus.ERROR,
    },
    ThreadStatus.STOPPING: {
        ThreadStatus.STOPPED,
        ThreadStatus.CANCELED,
        ThreadStatus.COMPLETE,
        ThreadStatus.ERROR,
    },
    ThreadStatus.COMPLETE: {ThreadStatus.QUEUED},
    ThreadStatus.STOPPED: {ThreadStatus.QUEUED},
    ThreadStatus.ERROR: {ThreadStatus.QUEUED},
    ThreadStatus.CANCELED: {ThreadStatus.QUEUED},
}


@dataclass(frozen=True)
class InvalidThreadTransition(ValueError):
    current: ThreadStatus
    target: ThreadStatus

    def __str__(self) -> str:
        return f"Invalid thread transition: {self.current.value} -> {self.target.value}"


def assert_transition(current: ThreadStatus, target: ThreadStatus) -> None:
    """Raise InvalidThreadTransition when target is not allowed from current."""
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidThreadTransition(current=current, target=target)
