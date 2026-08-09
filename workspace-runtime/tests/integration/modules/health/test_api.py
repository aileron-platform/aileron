"""Workspace Runtime health API integration tests."""

from __future__ import annotations


def test_health_reports_process_local_runtime_state(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "workspace-runtime"
    assert payload["runtime_status"] == "running"
    assert payload["updated"] is False
    assert payload["workspace_id"]
    assert "terminal_service" in payload
    assert "database" not in payload
