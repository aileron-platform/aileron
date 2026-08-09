"""Tests for datetime_utils module"""

from datetime import datetime, timezone, timedelta

from app.core.timestamps import (
    ensure_utc,
    utcnow,
)


class TestEnsureUtc:
    """Tests for ensure_utc function"""

    def test_ensure_utc_with_none(self):
        """Test ensure_utc returns None when input is None"""
        result = ensure_utc(None)
        assert result is None

    def test_ensure_utc_with_naive_datetime(self):
        """Test ensure_utc adds UTC timezone to naive datetime"""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        result = ensure_utc(naive_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0
        assert result.second == 0

    def test_ensure_utc_with_aware_datetime_utc(self):
        """Test ensure_utc preserves UTC datetime"""
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_utc(aware_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result == aware_dt

    def test_ensure_utc_with_aware_datetime_other_timezone(self):
        """Test ensure_utc converts other timezone to UTC"""
        # UTC+8 timezone
        other_tz = timezone(timedelta(hours=8))
        aware_dt = datetime(2025, 1, 1, 20, 0, 0, tzinfo=other_tz)
        result = ensure_utc(aware_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        # 20:00 UTC+8 should be 12:00 UTC
        assert result.hour == 12


class TestUtcnow:
    """Tests for utcnow function"""

    def test_utcnow_returns_aware_datetime(self):
        """Test utcnow returns timezone-aware datetime"""
        result = utcnow()

        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_utcnow_returns_current_time(self):
        """Test utcnow returns current time within reasonable range"""
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)

        assert before <= result <= after
