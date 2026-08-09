"""CORS middleware behavior tests."""

from __future__ import annotations


def test_error_responses_include_cors_headers(authenticated_client) -> None:
    """Browser clients must be able to read API error responses across origins."""
    client, _ = authenticated_client
    response = client.post(
        "/api/v1/workspaces",
        headers={"Origin": "https://aileron.test"},
        json={},
    )

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "https://aileron.test"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_requests_include_cors_headers(test_app) -> None:
    """Browser preflight requests must be handled before auth and routing."""
    client, _ = test_app

    response = client.options(
        "/api/v1/workspaces",
        headers={
            "Origin": "https://aileron.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://aileron.test"
    assert "POST" in response.headers["access-control-allow-methods"]
