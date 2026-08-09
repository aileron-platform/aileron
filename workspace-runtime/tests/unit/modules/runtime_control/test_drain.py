from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.manager_assertion import (
    ManagerAssertionConflict,
    ManagerAssertionInvalid,
    RuntimeDrainClaims,
)
from app.modules.runtime_control.drain import (
    RuntimeDrainConflict,
    RuntimeDrainService,
    RuntimeDrainTimeout,
)
from app.modules.runtime_control.state import get_runtime_admission_state

router_module = importlib.import_module("app.modules.internal.router")


def app_client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1")
    return TestClient(app)


def test_drain_does_not_accept_shared_internal_token(monkeypatch) -> None:
    verifier = Mock()
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )

    response = app_client().post(
        "/api/v1/internal/runtime/drain",
        headers={"X-Internal-Token": "test-internal-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"errorCode": "RUNTIME_ASSERTION_MISSING"}
    verifier.verify_runtime_drain.assert_not_called()


def test_valid_assertion_drains_without_returning_claims(monkeypatch) -> None:
    claims = SimpleNamespace(drain_attempt_id="attempt-a")
    verifier = Mock()
    verifier.verify_runtime_drain.return_value = claims
    drain_service = SimpleNamespace(drain=AsyncMock())
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )
    monkeypatch.setattr(
        router_module, "get_runtime_drain_service", lambda: drain_service
    )

    response = app_client().post(
        "/api/v1/internal/runtime/drain",
        headers={"Authorization": "Bearer signed.assertion.value"},
    )

    assert response.status_code == 204
    assert response.content == b""
    verifier.verify_runtime_drain.assert_called_once_with("signed.assertion.value")
    drain_service.drain.assert_awaited_once()


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [
        (ManagerAssertionInvalid("RUNTIME_ASSERTION_REPLAYED"), 401),
        (ManagerAssertionConflict("WORKSPACE_RUNTIME_INSTANCE_MISMATCH"), 409),
        (RuntimeDrainConflict("WORKSPACE_RUNTIME_DRAIN_ATTEMPT_MISMATCH"), 409),
        (RuntimeDrainTimeout(), 504),
    ],
)
def test_drain_errors_are_code_only(monkeypatch, failure, status_code) -> None:
    verifier = Mock()
    verifier.verify_runtime_drain.side_effect = failure
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )

    response = app_client().post(
        "/api/v1/internal/runtime/drain",
        headers={"Authorization": "Bearer secret-assertion"},
    )

    assert response.status_code == status_code
    assert response.json() == {"errorCode": failure.error_code}
    assert "secret-assertion" not in response.text


def test_cleanup_failure_is_code_only_timeout(monkeypatch) -> None:
    verifier = Mock()
    verifier.verify_runtime_drain.return_value = SimpleNamespace(
        drain_attempt_id="attempt-a"
    )
    drain_service = SimpleNamespace(
        drain=AsyncMock(side_effect=RuntimeError("sensitive cleanup detail"))
    )
    monkeypatch.setattr(
        router_module, "get_manager_assertion_verifier", lambda: verifier
    )
    monkeypatch.setattr(
        router_module, "get_runtime_drain_service", lambda: drain_service
    )

    response = app_client().post(
        "/api/v1/internal/runtime/drain",
        headers={"Authorization": "Bearer secret-assertion"},
    )

    assert response.status_code == 504
    assert response.json() == {"errorCode": "WORKSPACE_RUNTIME_DRAIN_INCOMPLETE"}
    assert "sensitive" not in response.text
    assert "secret-assertion" not in response.text


def claims(attempt: str, *, deadline_offset: int = 10) -> RuntimeDrainClaims:
    now = int(datetime.now(timezone.utc).timestamp())
    return RuntimeDrainClaims(
        workspace_id="workspace-a",
        expected_runtime_instance_id="instance-a",
        expected_mounted_revision=7,
        target_revision=8,
        drain_attempt_id=attempt,
        deadline=now + deadline_offset,
        job_id="job-a",
        issued_at=now,
        expires_at=now + deadline_offset,
        jti=f"jti-{attempt}",
    )


@pytest.mark.asyncio
async def test_drain_service_closes_all_actor_surfaces(monkeypatch) -> None:
    admission = get_runtime_admission_state()
    service = RuntimeDrainService()
    connections = SimpleNamespace(close_all=AsyncMock())
    relay = SimpleNamespace(full_drain=AsyncMock())
    automation = SimpleNamespace(drain=AsyncMock())
    drain_agents = AsyncMock()
    monkeypatch.setattr(
        "app.modules.thread.invalidation_emitter.get_thread_connection_manager",
        lambda: connections,
    )
    monkeypatch.setattr(
        "app.modules.client_browser_relay.relay.get_relay_service",
        lambda: relay,
    )
    monkeypatch.setattr(
        "app.modules.thread.agent_runner_factory.drain_agent_runners",
        drain_agents,
    )

    await service.drain(claims("attempt-a"), automation_runner=automation)
    await service.drain(claims("attempt-a"), automation_runner=automation)

    assert admission.is_draining is True
    connections.close_all.assert_awaited_once()
    relay.full_drain.assert_awaited_once()
    drain_agents.assert_awaited_once()
    automation.drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_drain_service_attempts_every_surface_before_reporting_failure(
    monkeypatch,
) -> None:
    service = RuntimeDrainService()
    connections = SimpleNamespace(
        close_all=AsyncMock(side_effect=RuntimeError("close failed"))
    )
    relay = SimpleNamespace(full_drain=AsyncMock())
    automation = SimpleNamespace(drain=AsyncMock())
    drain_agents = AsyncMock()
    monkeypatch.setattr(
        "app.modules.thread.invalidation_emitter.get_thread_connection_manager",
        lambda: connections,
    )
    monkeypatch.setattr(
        "app.modules.client_browser_relay.relay.get_relay_service",
        lambda: relay,
    )
    monkeypatch.setattr(
        "app.modules.thread.agent_runner_factory.drain_agent_runners",
        drain_agents,
    )

    with pytest.raises(RuntimeError, match="runtime_drain_cleanup_failed"):
        await service.drain(claims("attempt-a"), automation_runner=automation)

    connections.close_all.assert_awaited_once()
    relay.full_drain.assert_awaited_once()
    drain_agents.assert_awaited_once()
    automation.drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_drain_service_rejects_new_attempt_and_expired_deadline() -> None:
    service = RuntimeDrainService()

    with pytest.raises(RuntimeDrainTimeout):
        await service.drain(claims("attempt-a", deadline_offset=0))
    with pytest.raises(RuntimeDrainConflict):
        await service.drain(claims("attempt-b"))
