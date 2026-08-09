"""Stable capacity governance errors."""

from dataclasses import dataclass


@dataclass
class PlatformResourceError(Exception):
    error_code: str
    http_status: int
