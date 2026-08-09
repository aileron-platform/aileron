"""Shared API error response models."""

from pydantic import Field

from app.core.pydantic import CamelModel


class ApiErrorDetail(CamelModel):
    error_code: str = Field(..., alias="errorCode")
    message: str
    details: dict = Field(default_factory=dict)


class ApiErrorResponse(CamelModel):
    detail: ApiErrorDetail


def authorization_error_detail(
    error_code: str,
    message: str,
    *,
    details: dict | None = None,
) -> dict:
    """Build the stable authorization error detail used by HTTP adapters."""

    return {
        "errorCode": error_code,
        "message": message,
        "details": details or {},
    }


__all__ = [
    "ApiErrorDetail",
    "ApiErrorResponse",
    "authorization_error_detail",
]
