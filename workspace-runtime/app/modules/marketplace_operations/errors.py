"""Stable Marketplace operation failures."""

from __future__ import annotations


class MarketplaceOperationError(RuntimeError):
    """A sanitized operation failure safe for the internal API."""

    def __init__(self, code: str, *, http_status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
