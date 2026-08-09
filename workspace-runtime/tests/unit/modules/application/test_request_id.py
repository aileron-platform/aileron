from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.request_id import RequestIDMiddleware


def test_request_id_middleware_sets_state_and_response_header() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    client = TestClient(app)
    response = client.get("/ping")

    assert response.status_code == 200
    request_id = response.json()["request_id"]
    assert response.headers["X-Request-ID"] == request_id
    assert str(UUID(request_id)) == request_id
