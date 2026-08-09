"""Correlation ID middleware tests."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.request_id import CORRELATION_ID_HEADER, RequestIDMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/state")
    async def read_state(request: Request) -> dict[str, str]:
        return {
            "correlation_id": request.state.correlation_id,
            "request_id": request.state.request_id,
        }

    return TestClient(app)


def test_valid_incoming_correlation_id_is_reused() -> None:
    correlation_id = "11111111-1111-4111-8111-111111111111"

    with _client() as client:
        response = client.get(
            "/state",
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    assert response.status_code == 200
    assert response.json() == {
        "correlation_id": correlation_id,
        "request_id": correlation_id,
    }
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id


def test_missing_correlation_id_generates_uuid4() -> None:
    with _client() as client:
        response = client.get("/state")

    generated = UUID(response.headers[CORRELATION_ID_HEADER])
    assert generated.version == 4
    assert response.json()["correlation_id"] == str(generated)
    assert response.json()["request_id"] == str(generated)


def test_invalid_correlation_id_is_replaced_with_uuid4() -> None:
    with _client() as client:
        response = client.get(
            "/state",
            headers={CORRELATION_ID_HEADER: "not-a-uuid"},
        )

    generated = UUID(response.headers[CORRELATION_ID_HEADER])
    assert generated.version == 4
    assert str(generated) != "not-a-uuid"
    assert response.json()["correlation_id"] == str(generated)
