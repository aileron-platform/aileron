from __future__ import annotations

import pytest

from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.domain.transitions import (
    InvalidThreadTransition,
    assert_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ThreadStatus.DRAFT, ThreadStatus.QUEUED),
        (ThreadStatus.QUEUED, ThreadStatus.BOOTING),
        (ThreadStatus.QUEUED, ThreadStatus.CANCELED),
        (ThreadStatus.BOOTING, ThreadStatus.WORKING),
        (ThreadStatus.BOOTING, ThreadStatus.STOPPING),
        (ThreadStatus.WORKING, ThreadStatus.COMPLETE),
        (ThreadStatus.WORKING, ThreadStatus.ERROR),
        (ThreadStatus.STOPPING, ThreadStatus.STOPPED),
        (ThreadStatus.STOPPING, ThreadStatus.COMPLETE),
        (ThreadStatus.COMPLETE, ThreadStatus.QUEUED),
        (ThreadStatus.STOPPED, ThreadStatus.QUEUED),
        (ThreadStatus.ERROR, ThreadStatus.QUEUED),
        (ThreadStatus.CANCELED, ThreadStatus.QUEUED),
    ],
)
def test_assert_transition_allows_valid_edges(
    current: ThreadStatus,
    target: ThreadStatus,
) -> None:
    assert_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ThreadStatus.DRAFT, ThreadStatus.WORKING),
        (ThreadStatus.QUEUED, ThreadStatus.COMPLETE),
        (ThreadStatus.COMPLETE, ThreadStatus.WORKING),
        (ThreadStatus.ERROR, ThreadStatus.COMPLETE),
        (ThreadStatus.CANCELED, ThreadStatus.ERROR),
    ],
)
def test_assert_transition_rejects_invalid_edges(
    current: ThreadStatus,
    target: ThreadStatus,
) -> None:
    with pytest.raises(InvalidThreadTransition) as exc_info:
        assert_transition(current, target)

    assert exc_info.value.current == current
    assert exc_info.value.target == target
