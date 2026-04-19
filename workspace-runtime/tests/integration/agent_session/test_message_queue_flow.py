from __future__ import annotations

import asyncio
import time
import uuid
from threading import Event

import pytest
from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.execution_service import ExecutionService
from app.modules.agent_session.repositories.sqlalchemy_models import Base as AgentSessionBase
from app.modules.agent_session.services.tools.base.tool_interface import ITool
from app.modules.agent_session.services.tools.base.types import TaskResult, ToolCapabilities, ToolType


class FakeQueueFlowTool(ITool):
    def __init__(self) -> None:
        self.first_started = Event()
        self.first_release = Event()

    @property
    def tool_type(self) -> ToolType:
        return ToolType.CLAUDE_CODE

    @property
    def name(self) -> str:
        return "fake-queue-flow"

    def get_capabilities(self) -> ToolCapabilities:
        return ToolCapabilities(streaming=True)

    async def check_installed(self) -> bool:
        return True

    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: str | None = None,
        permission_mode=None,
        streaming_callbacks=None,
    ) -> TaskResult:
        message_id = f"assistant-{prompt}"

        if streaming_callbacks:
            await streaming_callbacks.on_stream_start(message_id)
            await streaming_callbacks.on_stream_chunk(message_id, f"{prompt}-chunk")

        if prompt == "first":
            self.first_started.set()
            released = await asyncio.to_thread(self.first_release.wait, 5)
            if not released:
                raise TimeoutError("first prompt was not released")

        if streaming_callbacks:
            await streaming_callbacks.on_stream_end(message_id)

        return TaskResult(
            user_message_id=f"user-{prompt}",
            assistant_message_ids=[message_id],
            raw_sdk_response={
                "type": "claude",
                "response": {
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                    }
                },
            },
        )


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture(autouse=True)
def ensure_agent_session_schema() -> None:
    database_url = get_settings().DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    engine = create_engine(database_url)
    AgentSessionBase.metadata.create_all(bind=engine)
    yield
    AgentSessionBase.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.integration
def test_message_queue_end_to_end_flow(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_tool = FakeQueueFlowTool()
    dispatching_finalize_entered = Event()
    dispatching_finalize_release = Event()

    monkeypatch.setattr(ExecutionService, "get_tool", lambda self, tool_type: fake_tool)
    original_finalize_dispatching = MessageService.finalize_dispatching_message

    async def delayed_finalize_dispatching(self, message_id: str) -> bool:
        dispatching_finalize_entered.set()
        released = await asyncio.to_thread(dispatching_finalize_release.wait, 5)
        if not released:
            raise TimeoutError("dispatching finalize was not released")
        return await original_finalize_dispatching(self, message_id)

    monkeypatch.setattr(
        MessageService,
        "finalize_dispatching_message",
        delayed_finalize_dispatching,
    )
    session_id: str | None = None
    try:
        workspace_id = f"ws-queue-{uuid.uuid4().hex[:8]}"
        create_response = client.post(
            "/api/v1/agent-sessions",
            json={
                "workspace_id": workspace_id,
                "agentic_tool": "claude-code",
            },
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        first_response = client.post(
            f"/api/v1/agent-sessions/{session_id}/prompt",
            json={"prompt": "first", "stream": True},
        )
        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["status"] == "running"
        assert wait_until(fake_tool.first_started.is_set), "first task did not start"

        second_response = client.post(
            f"/api/v1/agent-sessions/{session_id}/prompt",
            json={"prompt": "second", "stream": True},
        )
        assert second_response.status_code == 200
        second_payload = second_response.json()
        assert second_payload["status"] == "queued"
        second_message_id = second_payload["message_id"]

        third_response = client.post(
            f"/api/v1/agent-sessions/{session_id}/prompt",
            json={"prompt": "third", "stream": True},
        )
        assert third_response.status_code == 200
        third_payload = third_response.json()
        assert third_payload["status"] == "queued"
        third_message_id = third_payload["message_id"]

        queued_response = client.get(f"/api/v1/agent-sessions/{session_id}/queued-messages")
        assert queued_response.status_code == 200
        queued_payload = queued_response.json()
        queued_ids = [message["message_id"] for message in queued_payload["messages"]]
        assert queued_payload["count"] == 2
        assert second_message_id in queued_ids
        assert third_message_id in queued_ids

        delete_third = client.delete(
            f"/api/v1/agent-sessions/{session_id}/messages/{third_message_id}"
        )
        assert delete_third.status_code == 204

        queued_after_delete = client.get(f"/api/v1/agent-sessions/{session_id}/queued-messages")
        assert queued_after_delete.status_code == 200
        assert queued_after_delete.json()["count"] == 1
        assert queued_after_delete.json()["messages"][0]["message_id"] == second_message_id

        fake_tool.first_release.set()
        assert wait_until(
            dispatching_finalize_entered.is_set
        ), "second task did not reach dispatching finalize stage"

        delete_claimed = client.delete(
            f"/api/v1/agent-sessions/{session_id}/messages/{second_message_id}"
        )
        assert delete_claimed.status_code == 409
        assert "already being processed" in delete_claimed.json()["detail"]

        assert wait_until(
            lambda: client.get(f"/api/v1/agent-sessions/{session_id}/queued-messages").json()["count"] == 0
        ), "queue was not drained after second prompt was claimed"

        dispatching_finalize_release.set()

        def both_tasks_completed() -> bool:
            tasks_response = client.get(f"/api/v1/agent-sessions/{session_id}/tasks")
            if tasks_response.status_code != 200:
                return False
            items = tasks_response.json()["items"]
            statuses = [item["status"] for item in items]
            return len(items) == 2 and statuses.count("completed") == 2

        assert wait_until(both_tasks_completed), "expected both running and queued prompts to complete"
    finally:
        fake_tool.first_release.set()
        dispatching_finalize_release.set()
        if session_id:
            ExecutionService.cleanup_execution_lock(session_id)
            ExecutionService.cleanup_session_lock(session_id)
