"""Draw.io service availability checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx

from app.config.settings import Settings


DrawioUnavailableReason = Literal["DISABLED", "UNREACHABLE"]


@dataclass(frozen=True)
class DrawioAvailability:
    available: bool
    reason: DrawioUnavailableReason | None
    checked_at: datetime


_cached_availability: DrawioAvailability | None = None


def clear_drawio_availability_cache() -> None:
    """Reset the in-memory availability cache."""
    global _cached_availability
    _cached_availability = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_disabled(settings: Settings) -> bool:
    return not settings.DRAWIO_ENABLED or not settings.DRAWIO_EXTERNAL_URL.strip()


async def get_drawio_availability(
    settings: Settings,
    *,
    force_refresh: bool = False,
) -> DrawioAvailability:
    """Return Draw.io availability using settings and a short-lived health cache."""
    global _cached_availability

    checked_at = _now()
    if _is_disabled(settings):
        availability = DrawioAvailability(
            available=False,
            reason="DISABLED",
            checked_at=checked_at,
        )
        _cached_availability = availability
        return availability

    ttl_seconds = max(settings.DRAWIO_HEALTHCHECK_TTL_SECONDS, 0)
    if not force_refresh and _cached_availability is not None:
        expires_at = _cached_availability.checked_at + timedelta(seconds=ttl_seconds)
        if checked_at < expires_at:
            return _cached_availability

    try:
        timeout = httpx.Timeout(settings.DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(settings.DRAWIO_INTERNAL_URL)
            if not 200 <= response.status_code < 300:
                raise RuntimeError(
                    f"Draw.io health check returned {response.status_code}"
                )
            response.raise_for_status()
    except Exception:
        availability = DrawioAvailability(
            available=False,
            reason="UNREACHABLE",
            checked_at=checked_at,
        )
    else:
        availability = DrawioAvailability(
            available=True,
            reason=None,
            checked_at=checked_at,
        )

    _cached_availability = availability
    return availability
