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


def calculate_duration(start: datetime, end: Optional[datetime] = None) -> int:
    """
    Calculate difference in seconds between two times

    Args:
        start: Start time
        end: End time, use current time if None

    Returns:
        Time difference in seconds, ensure non-negative

    Examples:
        >>> start = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> end = datetime(2025, 1, 1, 12, 5, 30, tzinfo=timezone.utc)
        >>> calculate_duration(start, end)
        330
    """
    if end is None:
        end = utcnow()
    
    start_utc = ensure_utc(start)
    end_utc = ensure_utc(end)
    
    if start_utc is None or end_utc is None:
        return 0
    
    duration = int((end_utc - start_utc).total_seconds())
    return max(0, duration)  # Ensure non-negative


def compare_datetime(dt1: datetime, dt2: datetime) -> int:
    """
    Timezone-safe datetime comparison

    Args:
        dt1: First time
        dt2: Second time

    Returns:
        -1 if dt1 < dt2
         0 if dt1 == dt2
         1 if dt1 > dt2

    Examples:
        >>> dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> dt2 = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        >>> compare_datetime(dt1, dt2)
        -1
    """
    dt1_utc = ensure_utc(dt1)
    dt2_utc = ensure_utc(dt2)
    
    if dt1_utc is None or dt2_utc is None:
        return 0
    
    if dt1_utc < dt2_utc:
        return -1
    elif dt1_utc > dt2_utc:
        return 1
    else:
        return 0


def is_past(dt: datetime) -> bool:
    """
    Check if time is in the past

    Args:
        dt: Time to check

    Returns:
        True if time is in the past

    Examples:
        >>> past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        >>> is_past(past_dt)
        True
    """
    dt_utc = ensure_utc(dt)
    if dt_utc is None:
        return False
    return dt_utc < utcnow()


def is_future(dt: datetime) -> bool:
    """
    Check if time is in the future

    Args:
        dt: Time to check

    Returns:
        True if time is in the future

    Examples:
        >>> future_dt = datetime(2030, 1, 1, tzinfo=timezone.utc)
        >>> is_future(future_dt)
        True
    """
    dt_utc = ensure_utc(dt)
    if dt_utc is None:
        return False
    return dt_utc > utcnow()


__all__ = [
    "ensure_utc",
    "utcnow",
    "calculate_duration",
    "compare_datetime",
    "is_past",
    "is_future",
]

