"""Tests for datetime utilities"""

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.utils.datetime_utils import (
    ensure_utc,
    utcnow,
    calculate_duration,
    compare_datetime,
    is_past,
    is_future,
    to_local_timezone,
    from_local_timezone,
)


class TestDatetimeUtils:
    """Test cases for datetime utility functions"""

    def test_ensure_utc_none(self):
        """Test ensure_utc with None"""
        result = ensure_utc(None)
        assert result is None

    def test_ensure_utc_naive(self):
        """Test ensure_utc with naive datetime"""
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        result = ensure_utc(naive_dt)
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.hour == 12

    def test_ensure_utc_aware(self):
        """Test ensure_utc with timezone-aware datetime"""
        aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
        result = ensure_utc(aware_dt)
        assert result.tzinfo == timezone.utc
        # Taipei is UTC+8, so 12:00 in Taipei = 04:00 UTC
        assert result.hour == 4

    def test_utcnow(self):
        """Test utcnow returns current UTC time"""
        result = utcnow()
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        # Should be close to now
        assert (datetime.now(timezone.utc) - result).total_seconds() < 1

    def test_calculate_duration_with_end(self):
        """Test calculating duration between two datetimes"""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 5, 30, tzinfo=timezone.utc)
        result = calculate_duration(start, end)
        assert result == 330  # 5 minutes 30 seconds

    def test_calculate_duration_without_end(self):
        """Test calculating duration from start to now"""
        start = datetime.now(timezone.utc)
        result = calculate_duration(start)
        assert result >= 0
        assert result < 5  # Should be very small

    def test_calculate_duration_negative(self):
        """Test calculating duration returns non-negative even if end < start"""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        result = calculate_duration(start, end)
        assert result == 0  # Should return 0 for negative duration

    def test_calculate_duration_with_none(self):
        """Test calculate_duration with None values"""
        result = calculate_duration(None, None)
        assert result == 0

    def test_compare_datetime_less_than(self):
        """Test comparing two datetimes where first is earlier"""
        dt1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        result = compare_datetime(dt1, dt2)
        assert result == -1

    def test_compare_datetime_equal(self):
        """Test comparing two equal datetimes"""
        dt1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compare_datetime(dt1, dt2)
        assert result == 0

    def test_compare_datetime_greater_than(self):
        """Test comparing two datetimes where first is later"""
        dt1 = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compare_datetime(dt1, dt2)
        assert result == 1

    def test_compare_datetime_with_none(self):
        """Test comparing with None values"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = compare_datetime(dt, None)
        assert result == 0

    def test_is_past_true(self):
        """Test is_past with past datetime"""
        past_dt = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert is_past(past_dt) is True

    def test_is_past_false(self):
        """Test is_past with future datetime"""
        future_dt = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert is_past(future_dt) is False

    def test_is_past_none(self):
        """Test is_past with None"""
        assert is_past(None) is False

    def test_is_future_true(self):
        """Test is_future with future datetime"""
        future_dt = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert is_future(future_dt) is True

    def test_is_future_false(self):
        """Test is_future with past datetime"""
        past_dt = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert is_future(past_dt) is False

    def test_is_future_none(self):
        """Test is_future with None"""
        assert is_future(None) is False

    def test_to_local_timezone(self):
        """Test converting UTC to local timezone"""
        utc_dt = datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
        local_dt = to_local_timezone(utc_dt, "Asia/Taipei")
        # UTC+8 means 04:00 UTC = 12:00 Taipei
        assert local_dt.hour == 12

    def test_to_local_timezone_invalid_tz(self):
        """Test to_local_timezone with invalid timezone"""
        utc_dt = datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
        result = to_local_timezone(utc_dt, "Invalid/Timezone")
        # Should return UTC datetime on error
        assert result.tzinfo == timezone.utc

    def test_to_local_timezone_none(self):
        """Test to_local_timezone with None"""
        result = to_local_timezone(None)
        assert result is None

    def test_from_local_timezone_naive(self):
        """Test converting naive local time to UTC"""
        local_dt = datetime(2024, 1, 1, 12, 0, 0)
        utc_dt = from_local_timezone(local_dt, "Asia/Taipei")
        # 12:00 Taipei = 04:00 UTC
        assert utc_dt.hour == 4
        assert utc_dt.tzinfo == timezone.utc

    def test_from_local_timezone_aware(self):
        """Test converting aware local time to UTC"""
        local_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
        utc_dt = from_local_timezone(local_dt, "Asia/Taipei")
        # 12:00 Taipei = 04:00 UTC
        assert utc_dt.hour == 4
        assert utc_dt.tzinfo == timezone.utc

    def test_from_local_timezone_invalid_tz(self):
        """Test from_local_timezone with invalid timezone"""
        local_dt = datetime(2024, 1, 1, 12, 0, 0)
        result = from_local_timezone(local_dt, "Invalid/Timezone")
        # Should return UTC datetime on error
        assert result.tzinfo == timezone.utc
