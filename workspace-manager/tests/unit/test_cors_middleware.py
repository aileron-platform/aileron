"""CORS middleware behavior tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_error_responses_include_cors_headers(test_app) -> None:
    """Browser clients must be able to read API error responses across origins."""
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/workspaces/",
            headers={"Origin": "http://localhost:8082"},
            json={"name": "cors-test"},
        )

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:8082"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_requests_include_cors_headers(test_app) -> None:
    """Browser preflight requests must be handled before auth and routing."""
    client, _ = test_app

    response = client.options(
        "/api/v1/workspaces/",
        headers={
            "Origin": "http://localhost:8082",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8082"
    assert "POST" in response.headers["access-control-allow-methods"]
