"""OpenSpec module exports."""

from __future__ import annotations

from .dependencies import get_openspec_service
from .router import router

__all__ = ["router", "get_openspec_service"]
