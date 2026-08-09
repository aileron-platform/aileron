from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.modules.automation.runner import AutomationRunner


@dataclass
class BlockingClaimClient:
    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)
    runner_id: UUID | None = None
    request_id: UUID | None = None

    async def reconcile_restart(self, *, new_runner_instance_id: UUID) -> None:
        self.runner_id = new_runner_instance_id

    async def claim(self, *, runner_instance_id: UUID, claim_request_id: UUID):
        self.runner_id = runner_instance_id
        self.request_id = claim_request_id
        self.entered.set()
        await self.release.wait()
        return None

    async def complete(self, **kwargs):  # pragma: no cover - no claim
        raise AssertionError("unexpected completion")


@pytest.mark.asyncio
async def test_pending_claim_is_registered_before_http_and_can_be_cancelled() -> None:
    client = BlockingClaimClient()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=client,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
        poll_interval_seconds=0.01,
    )

    await runner.start()
    await asyncio.wait_for(client.entered.wait(), timeout=1)
    assert client.runner_id is not None and client.request_id is not None

    await runner.cancel_execution(
        execution_id="execution-known-by-manager",
        runner_instance_id=client.runner_id,
        claim_request_id=client.request_id,
    )

    pending = runner._pending[(client.runner_id, client.request_id)]
    assert pending.cancel_event.is_set()
    client.release.set()
    await runner.shutdown()


@pytest.mark.asyncio
async def test_cancel_with_wrong_claim_identity_is_rejected() -> None:
    client = BlockingClaimClient()
    runner = AutomationRunner(
        runner_instance_id=uuid4(),
        workspace_id="workspace-1",
        control_plane=client,
        worktree_service=object(),
        session_factory=lambda: None,
        agent_runner=object(),
    )
    await runner.start()
    await asyncio.wait_for(client.entered.wait(), timeout=1)

    with pytest.raises(LookupError, match="execution_not_owned"):
        await runner.cancel_execution(
            execution_id="other",
            runner_instance_id=uuid4(),
            claim_request_id=uuid4(),
        )

    client.release.set()
    await runner.shutdown()
