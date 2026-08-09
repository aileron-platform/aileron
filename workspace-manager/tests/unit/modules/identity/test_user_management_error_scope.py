"""User management error handlers must not change unrelated API contracts."""

from __future__ import annotations

import json

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.main import (
    admin_management_http_error_handler,
    admin_management_validation_error_handler,
)


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "root_path": "",
            "scheme": "http",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


@pytest.mark.asyncio
async def test_validation_handler_preserves_unrelated_fastapi_envelope() -> None:
    response = await admin_management_validation_error_handler(
        _request("/api/v1/workspaces"),
        RequestValidationError(
            [
                {
                    "type": "missing",
                    "loc": ("query", "workspaceId"),
                    "msg": "Field required",
                    "input": None,
                }
            ]
        ),
    )

    body = json.loads(response.body)
    assert response.status_code == 422
    assert "detail" in body
    assert "errorCode" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workspaces/example",
        "/api/v1/admin/users-export",
        "/api/v1/admin/user-groups-export",
    ],
)
async def test_http_handler_preserves_routes_outside_exact_management_prefix(
    path: str,
) -> None:
    response = await admin_management_http_error_handler(
        _request(path),
        StarletteHTTPException(status_code=418, detail="teapot"),
    )

    assert response.status_code == 418
    assert json.loads(response.body) == {"detail": "teapot"}
