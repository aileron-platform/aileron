from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.modules.automation.control_plane_client import (
    AutomationControlPlaneClient,
    ControlPlaneConflict,
)
from app.modules.automation.schemas import (
    AutomationAgentConfigSnapshot,
    CompletionRequest,
)


def _claim_payload(*, runner_id, request_id) -> dict[str, object]:
    return {
        "executionId": "execution-1",
        "jobId": "job-1",
        "workspaceId": "workspace-1",
        "trigger": "manual",
        "scheduledFor": datetime.now(timezone.utc).isoformat(),
        "principalUserId": "user-1",
        "prompt": "Run the task",
        "agenticTool": "claude",
        "model": "claude-opus-4-8",
        "agentConfig": {"mode": "execute", "permissionMode": "bypassPermissions"},
        "worktreeKey": "automation/job-1",
        "runnerInstanceId": str(runner_id),
        "claimRequestId": str(request_id),
        "cancelRequestedAt": None,
    }


def test_agent_config_snapshot_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AutomationAgentConfigSnapshot.model_validate(
            {"mode": "execute", "permissionMode": "bypassPermissions", "unsafe": True}
        )


@pytest.mark.asyncio
async def test_claim_retries_same_identity_and_sends_internal_headers() -> None:
    runner_id = uuid4()
    request_id = uuid4()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("response lost", request=request)
        return httpx.Response(
            200, json=_claim_payload(runner_id=runner_id, request_id=request_id)
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AutomationControlPlaneClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            runtime_instance_id="runtime-generation-1",
            workspace_id="workspace-1",
            http_client=http,
            retry_delays=(0,),
        )
        claim = await client.claim(
            runner_instance_id=runner_id, claim_request_id=request_id
        )

    assert claim is not None and claim.execution_id == "execution-1"
    assert len(requests) == 2
    assert {json.loads(request.content)["claimRequestId"] for request in requests} == {
        str(request_id)
    }
    assert all(
        request.headers["Authorization"] == "Bearer scoped-token"
        for request in requests
    )
    assert all("X-Internal-Token" not in request.headers for request in requests)
    assert all(
        request.headers["X-Workspace-ID"] == "workspace-1" for request in requests
    )
    assert all(
        request.headers["X-Runtime-Instance-ID"] == "runtime-generation-1"
        for request in requests
    )


@pytest.mark.asyncio
async def test_no_work_returns_none() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(204))
    ) as http:
        client = AutomationControlPlaneClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            runtime_instance_id="runtime-generation-1",
            workspace_id="workspace-1",
            http_client=http,
        )
        assert (
            await client.claim(runner_instance_id=uuid4(), claim_request_id=uuid4())
            is None
        )


@pytest.mark.asyncio
async def test_completion_transport_retry_is_byte_equivalent() -> None:
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        if len(bodies) == 1:
            raise httpx.ReadTimeout("response lost", request=request)
        return httpx.Response(200, json={"status": "success"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AutomationControlPlaneClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            runtime_instance_id="runtime-generation-1",
            workspace_id="workspace-1",
            http_client=http,
            retry_delays=(0,),
        )
        result = await client.complete(
            execution_id="execution-1",
            payload=CompletionRequest(
                runnerInstanceId=uuid4(), claimRequestId=uuid4(), status="success"
            ),
        )

    assert result.status == "success"
    assert len(bodies) == 2 and bodies[0] == bodies[1]


@pytest.mark.asyncio
async def test_completion_preserves_conflict_code_for_runner() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                409,
                json={
                    "detail": {"code": "execution_cancel_requested"},
                    "status": "running",
                },
            )
        )
    ) as http:
        client = AutomationControlPlaneClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            runtime_instance_id="runtime-generation-1",
            workspace_id="workspace-1",
            http_client=http,
        )
        with pytest.raises(ControlPlaneConflict) as error:
            await client.complete(
                execution_id="execution-1",
                payload=CompletionRequest(
                    runnerInstanceId=uuid4(), claimRequestId=uuid4(), status="success"
                ),
            )

    assert error.value.code == "execution_cancel_requested"


@pytest.mark.asyncio
async def test_interrupt_stops_transport_retry_during_runtime_shutdown() -> None:
    requested = asyncio.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        requested.set()
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AutomationControlPlaneClient(
            manager_url="http://manager",
            runtime_control_token="scoped-token",
            runtime_instance_id="runtime-generation-1",
            workspace_id="workspace-1",
            http_client=http,
            retry_delays=(60,),
        )
        task = asyncio.create_task(
            client.claim(runner_instance_id=uuid4(), claim_request_id=uuid4())
        )
        await requested.wait()
        client.interrupt()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.1)
