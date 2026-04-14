"""統一的時區處理工具模組

此模組提供一致的 datetime 處理函數，確保整個應用程式使用 timezone-aware datetime。

設計原則：
1. 所有 datetime 統一使用 UTC timezone-aware
2. 避免使用已棄用的 datetime.utcnow()
3. 提供時區安全的比較和計算函數
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


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
        
        >>> aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        >>> ensure_utc(aware_dt)
        datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
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
    
    替代已棄用的 datetime.utcnow()
    
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
    時區安全的 datetime 比較
    
    Args:
        dt1: 第一個時間
        dt2: 第二個時間
        
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
    檢查時間是否在過去
    
    Args:
        dt: 要檢查的時間
        
    Returns:
        True 如果時間在過去
        
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
    檢查時間是否在未來
    
    Args:
        dt: 要檢查的時間
        
    Returns:
        True 如果時間在未來
        
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

