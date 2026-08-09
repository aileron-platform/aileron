"""Knowledge base domain errors."""

from __future__ import annotations


class KnowledgeBaseError(ValueError):
    """Knowledge base base error."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "KB_INVALID_REQUEST",
        params: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


__all__ = ["KnowledgeBaseError"]
