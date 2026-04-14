"""日期時間工具函數

統一處理時區轉換、時間計算等操作，確保整個系統的時區一致性。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    確保 datetime 是 UTC timezone-aware
    
    Args:
        dt: 輸入的 datetime 對象，可能是 naive 或 aware
        
    Returns:
        UTC timezone-aware 的 datetime，如果輸入為 None 則返回 None
        
    Examples:
        >>> naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> ensure_utc(naive_dt)
        datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        >>> aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
        >>> ensure_utc(aware_dt)
        datetime(2025, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Naive datetime，假設為 UTC
        return dt.replace(tzinfo=timezone.utc)
    
    # Aware datetime，轉換為 UTC
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    """
    返回當前 UTC 時間（timezone-aware）
    
    Returns:
        當前 UTC 時間
        
    Examples:
        >>> now = utcnow()
        >>> now.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)


def calculate_duration(start: datetime, end: Optional[datetime] = None) -> int:
    """
    計算兩個時間的秒數差異
    
    Args:
        start: 開始時間
        end: 結束時間，如果為 None 則使用當前時間
        
    Returns:
        時間差（秒），確保非負數
        
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
    return max(0, duration)  # 確保非負數


def compare_datetime(dt1: datetime, dt2: datetime) -> int:
    """
    比較兩個 datetime 對象
    
    Args:
        dt1: 第一個 datetime
        dt2: 第二個 datetime
        
    Returns:
        -1 如果 dt1 < dt2
         0 如果 dt1 == dt2
         1 如果 dt1 > dt2
         
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
    檢查給定時間是否已過去
    
    Args:
        dt: 要檢查的時間
        
    Returns:
        True 如果時間已過去，False 否則
        
    Examples:
        >>> past_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        >>> is_past(past_dt)
        True
    """
    dt_utc = ensure_utc(dt)
    if dt_utc is None:
        return False
    
    return dt_utc <= utcnow()


def is_future(dt: datetime) -> bool:
    """
    檢查給定時間是否在未來
    
    Args:
        dt: 要檢查的時間
        
    Returns:
        True 如果時間在未來，False 否則
        
    Examples:
        >>> future_dt = datetime(2030, 1, 1, tzinfo=timezone.utc)
        >>> is_future(future_dt)
        True
    """
    dt_utc = ensure_utc(dt)
    if dt_utc is None:
        return False
    
    return dt_utc > utcnow()


def to_local_timezone(dt: datetime, tz_name: str = "Asia/Taipei") -> datetime:
    """
    將 UTC 時間轉換為指定時區的本地時間
    
    Args:
        dt: UTC 時間
        tz_name: 時區名稱，預設為 Asia/Taipei
        
    Returns:
        本地時區的 datetime
        
    Examples:
        >>> utc_dt = datetime(2025, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
        >>> local_dt = to_local_timezone(utc_dt, "Asia/Taipei")
        >>> local_dt.hour
        12
    """
    dt_utc = ensure_utc(dt)
    if dt_utc is None:
        return dt
    
    try:
        local_tz = ZoneInfo(tz_name)
        return dt_utc.astimezone(local_tz)
    except Exception:
        # 如果時區無效，返回 UTC
        return dt_utc


def from_local_timezone(dt: datetime, tz_name: str = "Asia/Taipei") -> datetime:
    """
    將本地時區的時間轉換為 UTC
    
    Args:
        dt: 本地時間（可能是 naive 或 aware）
        tz_name: 時區名稱，預設為 Asia/Taipei
        
    Returns:
        UTC 時間
        
    Examples:
        >>> local_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> utc_dt = from_local_timezone(local_dt, "Asia/Taipei")
        >>> utc_dt.hour
        4
    """
    try:
        local_tz = ZoneInfo(tz_name)
        
        if dt.tzinfo is None:
            # Naive datetime，加上本地時區
            dt_with_tz = dt.replace(tzinfo=local_tz)
        else:
            # Aware datetime，先轉換到本地時區
            dt_with_tz = dt.astimezone(local_tz)
        
        # 轉換為 UTC
        return dt_with_tz.astimezone(timezone.utc)
    except Exception:
        # 如果時區無效，假設輸入已經是 UTC
        return ensure_utc(dt) or dt


__all__ = [
    "ensure_utc",
    "utcnow",
    "calculate_duration",
    "compare_datetime",
    "is_past",
    "is_future",
    "to_local_timezone",
    "from_local_timezone",
]

