"""Unified timezone handling utility module

This module provides consistent datetime handling functions, ensuring the entire application uses timezone-aware datetime.

Design principles:
1. All datetime unified use UTC timezone-aware
2. Avoid using deprecated datetime.utcnow()
3. Provide timezone-safe comparison and calculation functions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is UTC timezone-aware

    Args:
        dt: Input datetime object, can be naive or aware

    Returns:
        UTC timezone-aware datetime, or None if input is None

    Examples:
        >>> naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> ensure_utc(naive_dt)
        datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        >>> aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> ensure_utc(aware_dt)
        datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime, assume as UTC
        return dt.replace(tzinfo=timezone.utc)

    # Aware datetime, convert to UTC
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    """
    Return current UTC time (timezone-aware)

    Replace deprecated datetime.utcnow()

    Returns:
        Current UTC time

    Examples:
        >>> now = utcnow()
        >>> now.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)


__all__ = [
    "ensure_utc",
    "utcnow",
]
