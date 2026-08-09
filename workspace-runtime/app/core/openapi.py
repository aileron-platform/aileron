"""Workspace Runtime OpenAPI common definitions."""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, Field


OpenAPIResponses: TypeAlias = dict[int | str, dict[str, Any]]


class APIErrorDetail(BaseModel):
    """Standard API error content."""

    error: str | None = Field(default=None, description="Error type")
    message: str | None = Field(default=None, description="Error message")
    detail: str | dict | None = Field(
        default=None, description="Detailed error content"
    )
    request_id: str | None = Field(default=None, description="Request tracking ID")
    error_code: str | None = Field(
        default=None, description="Machine-readable error code"
    )
    status_code: int | None = Field(default=None, description="HTTP status code")


COMMON_ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: {
        "model": APIErrorDetail,
        "description": "Request format error or invalid parameters.",
    },
    401: {
        "model": APIErrorDetail,
        "description": "No valid authentication information provided.",
    },
    403: {
        "model": APIErrorDetail,
        "description": "Current user does not have permission.",
    },
    404: {"model": APIErrorDetail, "description": "Specified resource does not exist."},
    409: {
        "model": APIErrorDetail,
        "description": "Resource state conflict, operation cannot be completed.",
    },
    422: {"description": "Request data validation failed."},
    500: {"model": APIErrorDetail, "description": "Internal server error."},
    503: {"model": APIErrorDetail, "description": "Service temporarily unavailable."},
}


def build_responses(*status_codes: int) -> OpenAPIResponses:
    """Select common OpenAPI error responses by status code."""

    return {
        status_code: COMMON_ERROR_RESPONSES[status_code]
        for status_code in status_codes
        if status_code in COMMON_ERROR_RESPONSES
    }
