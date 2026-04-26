"""Workspace Manager OpenAPI common definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    """Standard API error content."""

    error: str | None = Field(default=None, description="Error type")
    message: str | None = Field(default=None, description="Error message")
    detail: str | dict | None = Field(default=None, description="Detailed error content")
    request_id: str | None = Field(default=None, description="Request tracking ID")
    error_code: str | None = Field(default=None, description="Machine-readable error code")
    status_code: int | None = Field(default=None, description="HTTP status code")


COMMON_ERROR_RESPONSES = {
    400: {"model": APIErrorDetail, "description": "Request format error or invalid parameters."},
    401: {"model": APIErrorDetail, "description": "No valid authentication information provided."},
    403: {"model": APIErrorDetail, "description": "Current user does not have operation permission."},
    404: {"model": APIErrorDetail, "description": "Specified resource does not exist."},
    409: {"model": APIErrorDetail, "description": "Resource state conflict, cannot complete operation."},
    413: {"model": APIErrorDetail, "description": "Request content exceeds allowed size limit."},
    422: {"description": "Request data validation failed."},
    500: {"model": APIErrorDetail, "description": "Server internal error."},
    502: {"model": APIErrorDetail, "description": "Upstream service response error."},
    503: {"model": APIErrorDetail, "description": "Service temporarily unavailable."},
}


def build_responses(
    *status_codes: int,
    model: type[BaseModel] | None = None,
    descriptions: dict[int, str] | None = None,
    examples: dict[int, dict[str, Any]] | None = None,
) -> dict[int, dict]:
    """Select common OpenAPI error responses by status code."""

    responses: dict[int, dict] = {}
    for status_code in status_codes:
        if status_code not in COMMON_ERROR_RESPONSES:
            continue
        response = dict(COMMON_ERROR_RESPONSES[status_code])
        if model is not None and status_code != 422:
            response["model"] = model
        if descriptions and status_code in descriptions:
            response["description"] = descriptions[status_code]
        if examples and status_code in examples:
            response["content"] = {"application/json": {"examples": examples[status_code]}}
        responses[status_code] = response
    return responses
