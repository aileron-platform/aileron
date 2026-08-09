from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import get_settings
from app.database.session import get_async_db
from app.main import app
from app.modules.thread.persistence_models import (
    ThreadMessageModel,
    ThreadModel,
    ThreadToolResultContentModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)
from app.modules.thread.router import get_thread_service
from app.modules.thread.capabilities_store import (
    CapabilitiesStore,
    RuntimeCapabilitiesModel,
)
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.thread.lifecycle import ThreadService


@dataclass
class FlowRunner:
    requests: list[AgentExecutionRequest] = field(default_factory=list)
    callbacks: dict[str, Callable[[AgentEvent], Awaitable[None]]] = field(
        default_factory=dict
    )
    stopped: list[str] = field(default_factory=list)
    reserved: list[str] = field(default_factory=list)

    def reserve(self) -> str:
        execution_id = f"session-{len(self.reserved) + 1}"
        self.reserved.append(execution_id)
        return execution_id

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: Callable[[AgentEvent], Awaitable[None]],
        execution_id: str,
    ) -> None:
        assert execution_id in self.reserved
        self.requests.append(request)
        self.callbacks[execution_id] = on_event

    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)

    def is_alive(self, execution_id: str) -> bool:
        return True

    async def destroy_thread(self, thread_id: str) -> None:
        return None

    async def dispatch(self, execution_id: str, event: AgentEvent) -> None:
        await self.callbacks[execution_id](event)


class FlowSink:
    async def emit(
        self,
        user_id: str | None,
        workspace_id: str,
        thread_id: str,
        type_: str,
        status: str | None = None,
        **_event_data: Any,
    ) -> None:
        return None


class FlowExecutionGrantVerifier:
    def verify(self, grant: str, *, action: str):
        assert grant == "user-a"
        return type("Claims", (), {"subject": "user-a", "actions": (action,)})()


THREAD_FLOW_TABLES = (
    RuntimeCapabilitiesModel.__table__,
    ThreadModel.__table__,
    ThreadTurnModel.__table__,
    ThreadTurnExecutionModel.__table__,
    ThreadMessageModel.__table__,
    ThreadToolResultContentModel.__table__,
)


@pytest.fixture
async def flow_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ThreadModel.metadata.drop_all(
                sync_connection,
                tables=THREAD_FLOW_TABLES,
                checkfirst=True,
            )
        )
        await connection.run_sync(
            lambda sync_connection: ThreadModel.metadata.create_all(
                sync_connection,
                tables=THREAD_FLOW_TABLES,
            )
        )

    factory = async_sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ThreadModel.metadata.drop_all(
                sync_connection,
                tables=THREAD_FLOW_TABLES,
                checkfirst=True,
            )
        )


@asynccontextmanager
async def flow_client(
    session: AsyncSession,
    service: ThreadService,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield session
        await session.commit()

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_thread_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    with patch(
        "app.middleware.auth.get_execution_grant_verifier",
        return_value=FlowExecutionGrantVerifier(),
    ):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.pop(get_thread_service, None)
    app.dependency_overrides.pop(get_async_db, None)


@pytest.mark.asyncio
async def test_automation_create_or_get_persists_only_the_empty_thread_link(
    flow_session: AsyncSession,
) -> None:
    service = ThreadService(
        flow_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
        runner=FlowRunner(),
    )

    created = await service.create_or_get_automation_thread(
        automation_job_id="job-a",
        automation_execution_id="execution-a",
        user_id="principal-a",
        git_context_id="worktree:automation--job-a",
        agentic_tool="codex",
        model="gpt-5.6-sol",
        agent_mode=None,
    )
    await flow_session.commit()
    retried = await service.create_or_get_automation_thread(
        automation_job_id="job-a",
        automation_execution_id="execution-a",
        user_id="principal-a",
        git_context_id="worktree:automation--job-a",
        agentic_tool="codex",
        model="gpt-5.6-sol",
        agent_mode=None,
    )

    assert retried.id == created.id
    assert created.origin == "automation"
    assert created.user_id == "principal-a"
    assert created.automation_job_id == "job-a"
    assert created.automation_execution_id == "execution-a"
    assert created.git_context_id == "worktree:automation--job-a"
    assert created.agentic_tool == "codex"
    assert created.model == "gpt-5.6-sol"
    assert created.claude_mode is None
    assert created.draft_message is None

    message_rows = await flow_session.execute(select(ThreadMessageModel))
    assert message_rows.scalars().all() == []

    rows = await flow_session.execute(select(ThreadModel))
    threads = rows.scalars().all()
    assert len(threads) == 1
    assert not hasattr(threads[0], "agent_config")


@pytest.mark.asyncio
async def test_thread_http_flow_rebuilds_from_database_and_preserves_list_contract(
    flow_session: AsyncSession,
) -> None:
    capabilities = {
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8"],
                "default_model": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            }
        ],
        "default_tool": "claude",
    }
    await CapabilitiesStore().put(
        flow_session, get_settings().AILERON_WORKSPACE_ID, capabilities
    )
    await flow_session.commit()
    runner = FlowRunner()
    sink = FlowSink()
    service = ThreadService(
        flow_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
        runner=runner,
        invalidation_sink=sink,
    )
    headers = {"Authorization": "Bearer user-a"}

    async with flow_client(flow_session, service) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers=headers,
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        assert draft_response.status_code == 201
        thread_id = draft_response.json()["id"]

        submitted = await client.post(
            f"/api/v1/threads/{thread_id}/submit",
            headers=headers,
            json={"text": "Inspect the workspace", "attachments": []},
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "queued"
        patched = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers=headers,
            json={"model": "claude-opus-4-8"},
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "queued"

        await runner.dispatch(
            runner.reserved[-1],
            AgentEvent(
                type="agent_text",
                content={"parts": [{"type": "text", "text": "Working"}]},
                usage={"input_tokens": 1200},
            ),
        )
        refreshed_working = await client.get(
            f"/api/v1/threads/{thread_id}", headers=headers
        )
        assert refreshed_working.json()["status"] == "working"
        assert refreshed_working.json()["contextTokens"] == 1200

        await runner.dispatch(runner.reserved[-1], AgentEvent(type="complete"))
        detail_response = await client.get(
            f"/api/v1/threads/{thread_id}", headers=headers
        )
        detail = detail_response.json()
        assert detail["status"] == "complete"
        timeline_response = await client.get(
            f"/api/v1/threads/{thread_id}/timeline", headers=headers
        )
        assert timeline_response.status_code == 200
        assert [item["type"] for item in timeline_response.json()["items"]] == [
            "user",
            "agent_text",
        ]

        list_response = await client.get(
            "/api/v1/threads?archived=false", headers=headers
        )
        item = list_response.json()["items"][0]
        assert item["id"] == thread_id
        assert "messages" not in item
        assert "queuedMessages" not in item
        assert "draftMessage" not in item

        follow_up = await client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers=headers,
            json={"text": "Continue", "attachments": []},
        )
        assert follow_up.json()["status"] == "queued"
        await runner.dispatch(
            runner.reserved[-1],
            AgentEvent(
                type="error", error_code="agent_failed", error_info={"exit_code": 1}
            ),
        )
        retried = await client.post(
            f"/api/v1/threads/{thread_id}/retry", headers=headers
        )
        assert retried.json()["status"] == "queued"

        canceled = await client.post(
            f"/api/v1/threads/{thread_id}/cancel", headers=headers
        )
        assert canceled.json()["status"] == "canceled"
        archived = await client.post(
            f"/api/v1/threads/{thread_id}/archive", headers=headers
        )
        assert archived.json()["archived"] is True
        assert len(runner.requests) == 3
