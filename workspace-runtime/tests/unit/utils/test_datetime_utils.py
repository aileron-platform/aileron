"""Tests for datetime_utils module"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest

from app.utils.datetime_utils import (
    ensure_utc,
    utcnow,
    calculate_duration,
    compare_datetime,
    is_past,
    is_future,
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


class TestCalculateDuration:
    """Tests for calculate_duration function"""

    def test_calculate_duration_with_both_times(self):
        """Test calculate_duration with start and end times"""
        start = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, 12, 5, 30, tzinfo=timezone.utc)

        result = calculate_duration(start, end)
        assert result == 330  # 5 minutes 30 seconds

    def test_calculate_duration_without_end_time(self):
        """Test calculate_duration defaults to current time when end is None"""
        start = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch('app.utils.datetime_utils.utcnow') as mock_utcnow:
            mock_now = datetime(2025, 1, 1, 12, 10, 0, tzinfo=timezone.utc)
            mock_utcnow.return_value = mock_now

            result = calculate_duration(start, None)
            assert result == 600  # 10 minutes

    def test_calculate_duration_with_naive_datetimes(self):
        """Test calculate_duration handles naive datetimes"""
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 5, 0)

        result = calculate_duration(start, end)
        assert result == 300  # 5 minutes

    def test_calculate_duration_with_none_start(self):
        """Test calculate_duration returns 0 when start is None"""
        end = datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        result = calculate_duration(None, end)
        assert result == 0

    def test_calculate_duration_with_negative_duration(self):
        """Test calculate_duration returns 0 for negative duration"""
        start = datetime(2025, 1, 1, 12, 10, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = calculate_duration(start, end)
        assert result == 0  # Ensures non-negative

    def test_calculate_duration_with_zero_duration(self):
        """Test calculate_duration returns 0 for same start and end"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = calculate_duration(dt, dt)
        assert result == 0


class TestCompareDatetime:
    """Tests for compare_datetime function"""

    def test_compare_datetime_less_than(self):
        """Test compare_datetime returns -1 when dt1 < dt2"""
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

        result = compare_datetime(dt1, dt2)
        assert result == -1

    def test_compare_datetime_greater_than(self):
        """Test compare_datetime returns 1 when dt1 > dt2"""
        dt1 = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = compare_datetime(dt1, dt2)
        assert result == 1

    def test_compare_datetime_equal(self):
        """Test compare_datetime returns 0 when dt1 == dt2"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = compare_datetime(dt, dt)
        assert result == 0

    def test_compare_datetime_with_naive_datetimes(self):
        """Test compare_datetime handles naive datetimes"""
        dt1 = datetime(2025, 1, 1, 12, 0, 0)
        dt2 = datetime(2025, 1, 1, 13, 0, 0)

        result = compare_datetime(dt1, dt2)
        assert result == -1

    def test_compare_datetime_with_different_timezones(self):
        """Test compare_datetime handles different timezones"""
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # UTC+8, same moment in time
        other_tz = timezone(timedelta(hours=8))
        dt2 = datetime(2025, 1, 1, 20, 0, 0, tzinfo=other_tz)

        result = compare_datetime(dt1, dt2)
        assert result == 0

    def test_compare_datetime_with_none_dt1(self):
        """Test compare_datetime returns 0 when dt1 is None"""
        dt2 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = compare_datetime(None, dt2)
        assert result == 0

    def test_compare_datetime_with_none_dt2(self):
        """Test compare_datetime returns 0 when dt2 is None"""
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = compare_datetime(dt1, None)
        assert result == 0


class TestIsPast:
    """Tests for is_past function"""

    def test_is_past_with_past_datetime(self):
        """Test is_past returns True for past datetime"""
        past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)

        result = is_past(past_dt)
        assert result is True

    def test_is_past_with_future_datetime(self):
        """Test is_past returns False for future datetime"""
        future_dt = datetime(2030, 1, 1, tzinfo=timezone.utc)

        result = is_past(future_dt)
        assert result is False

    def test_is_past_with_current_datetime(self):
        """Test is_past with datetime very close to current time"""
        with patch('app.utils.datetime_utils.utcnow') as mock_utcnow:
            current_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_utcnow.return_value = current_dt

            # Same time should not be past
            result = is_past(current_dt)
            assert result is False

    def test_is_past_with_naive_datetime(self):
        """Test is_past handles naive datetime"""
        past_dt = datetime(2020, 1, 1)

        result = is_past(past_dt)
        assert result is True

    def test_is_past_with_none(self):
        """Test is_past returns False when datetime is None"""
        result = is_past(None)
        assert result is False


class TestIsFuture:
    """Tests for is_future function"""

    def test_is_future_with_future_datetime(self):
        """Test is_future returns True for future datetime"""
        future_dt = datetime(2030, 1, 1, tzinfo=timezone.utc)

        result = is_future(future_dt)
        assert result is True

    def test_is_future_with_past_datetime(self):
        """Test is_future returns False for past datetime"""
        past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)

        result = is_future(past_dt)
        assert result is False

    def test_is_future_with_current_datetime(self):
        """Test is_future with datetime very close to current time"""
        with patch('app.utils.datetime_utils.utcnow') as mock_utcnow:
            current_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_utcnow.return_value = current_dt

            # Same time should not be future
            result = is_future(current_dt)
            assert result is False

    def test_is_future_with_naive_datetime(self):
        """Test is_future handles naive datetime"""
        future_dt = datetime(2030, 1, 1)

        result = is_future(future_dt)
        assert result is True

    def test_is_future_with_none(self):
        """Test is_future returns False when datetime is None"""
        result = is_future(None)
        assert result is False
