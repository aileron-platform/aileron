from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import get_settings
from app.database.session import get_async_db
from app.main import app
from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.domain.tool_names import QUESTION_TOOL_NAME
from app.modules.thread.persistence_models import ThreadMessageModel, ThreadModel
from app.modules.thread.message_repository import (
    ThreadMessageRepository,
)
from app.modules.thread.repository import ThreadRepository
from app.modules.thread.turn_repository import ThreadTurnRepository
from app.modules.thread.capabilities_store import (
    CapabilitiesStore,
    RuntimeCapabilitiesModel,
)
from app.modules.thread.router import (
    get_thread_attachment_service,
    get_thread_service,
)
from app.modules.thread.attachments import (
    ThreadAttachmentService,
)
from app.modules.thread.execution import (
    AgentEvent,
    AgentExecutionRequest,
)
from app.modules.thread.lifecycle import ThreadService
from tests.unit.modules.thread.db_fixture import (
    drop_thread_tables,
    reset_thread_tables,
)
from app.modules.auth.execution_grant import ExecutionGrantInvalid


def make_capabilities() -> dict:
    return {
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8", "claude-sonnet-5"],
                "default_model": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            },
            {
                "id": "codex",
                "models": ["gpt-5.6-sol"],
                "default_model": "gpt-5.6-sol",
                "context_window": 200000,
            },
        ],
        "default_tool": "claude",
    }


def make_fallback_capabilities() -> dict:
    return {
        "default_tool": "codex",
        "tools": [
            {
                "id": "codex",
                "models": ["gpt-custom"],
                "default_model": "gpt-custom",
                "modes": None,
                "default_mode": None,
                "context_window": 200000,
            },
            {
                "id": "claude",
                "models": ["claude-opus-4-8"],
                "default_model": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            },
            {
                "id": "opencode",
                "models": ["opencode-oss"],
                "default_model": "opencode-oss",
                "modes": None,
                "default_mode": None,
                "context_window": 128000,
            },
        ],
    }


@pytest.fixture
async def thread_api_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as conn:
        await reset_thread_tables(conn)

    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as conn:
        await drop_thread_tables(conn)


class StubExecutionGrantVerifier:
    def verify(self, grant: str, *, action: str):
        if grant == "signed-grant-without-agent-action":
            raise ExecutionGrantInvalid("WORKSPACE_EXECUTION_GRANT_ACTION_FORBIDDEN")
        if grant not in {"user-a", "user-b"}:
            raise ExecutionGrantInvalid()
        return type("Claims", (), {"subject": grant, "actions": (action,)})()


class RecordingRunner:
    def __init__(self) -> None:
        self.requests: list[AgentExecutionRequest] = []
        self.reserved: list[str] = []
        self.stopped: list[str] = []

    def reserve(self) -> str:
        # A fresh RecordingRunner is instantiated per request (see
        # `override_service`), so ids must be globally unique rather than
        # derived from this instance's own reservation count.
        execution_id = f"session-{uuid4().hex}"
        self.reserved.append(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self.reserved.append(execution_id)

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event,
        execution_id: str,
    ) -> None:
        assert execution_id in self.reserved
        self.requests.append(request)

    async def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)

    async def wait(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return execution_id not in self.stopped

    async def destroy_thread(self, thread_id: str) -> None:
        return None

    async def dispatch(self, execution_id: str, event: AgentEvent) -> None:
        return None


@asynccontextmanager
async def api_client(session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield session
        await session.commit()

    def override_service(
        db: AsyncSession = Depends(get_async_db),
    ) -> ThreadService:
        attachment_override = app.dependency_overrides.get(
            get_thread_attachment_service
        )
        attachment_service = (
            attachment_override()
            if attachment_override is not None
            else get_thread_attachment_service()
        )
        return ThreadService(
            db,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
            runner=RecordingRunner(),
            attachment_service=attachment_service,
        )

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_thread_service] = override_service
    transport = httpx.ASGITransport(app=app)
    with (
        patch(
            "app.middleware.auth.get_execution_grant_verifier",
            return_value=StubExecutionGrantVerifier(),
        ),
    ):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.pop(get_thread_service, None)
    app.dependency_overrides.pop(get_async_db, None)


@asynccontextmanager
async def automation_api_client(
    session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with api_client(session) as client:
        yield client


@asynccontextmanager
async def api_client_with_managed_transaction(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    runner: RecordingRunner,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session.begin():
            yield session

    def override_service(
        db: AsyncSession = Depends(get_async_db),
    ) -> ThreadService:
        return ThreadService(
            db,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
            runner=runner,
            event_session_factory=session_factory,
        )

    app.dependency_overrides[get_async_db] = override_db
    app.dependency_overrides[get_thread_service] = override_service
    transport = httpx.ASGITransport(app=app)
    with (
        patch(
            "app.middleware.auth.get_execution_grant_verifier",
            return_value=StubExecutionGrantVerifier(),
        ),
    ):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.pop(get_thread_service, None)
    app.dependency_overrides.pop(get_async_db, None)


@asynccontextmanager
async def api_client_with_attachment_storage(
    session: AsyncSession,
    storage_root,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides[get_thread_attachment_service] = (
        lambda: ThreadAttachmentService(
            storage_root=storage_root,
        )
    )
    async with api_client(session) as client:
        yield client
    app.dependency_overrides.pop(get_thread_attachment_service, None)


async def put_capabilities(
    session: AsyncSession,
    capabilities: dict | None = None,
) -> None:
    await CapabilitiesStore().put(
        session,
        get_settings().AILERON_WORKSPACE_ID,
        capabilities or make_capabilities(),
    )
    await session.commit()


@pytest.mark.asyncio
async def test_automation_lookup_is_not_captured_by_thread_id_route(
    thread_api_session: AsyncSession,
) -> None:
    async with automation_api_client(thread_api_session) as client:
        response = await client.get(
            "/api/v1/threads/by-automation-execution/missing",
            headers={"Authorization": "Bearer user-a"},
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "automation_thread_not_found"


@pytest.mark.asyncio
async def test_workspace_viewer_can_lookup_another_creators_automation_thread(
    thread_api_session: AsyncSession,
) -> None:
    service = ThreadService(
        thread_api_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
        runner=RecordingRunner(),
    )
    created = await service.create_or_get_automation_thread(
        automation_job_id="job-a",
        automation_execution_id="execution-viewable",
        user_id="user-a",
        git_context_id="worktree:automation--job-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        agent_mode="execute",
    )

    async with automation_api_client(thread_api_session) as client:
        response = await client.get(
            "/api/v1/threads/by-automation-execution/execution-viewable",
            headers={"Authorization": "Bearer user-b"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == created.id
    assert response.json()["userId"] == "user-a"
    assert response.json()["automationJobId"] == "job-a"
    assert response.json()["automationExecutionId"] == "execution-viewable"
    assert "messages" not in response.json()


@pytest.mark.asyncio
async def test_grant_without_agent_action_cannot_lookup_automation_thread(
    thread_api_session: AsyncSession,
) -> None:
    await ThreadService(
        thread_api_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
        runner=RecordingRunner(),
    ).create_or_get_automation_thread(
        automation_job_id="job-a",
        automation_execution_id="execution-private",
        user_id="user-a",
        git_context_id="worktree:automation--job-a",
        agentic_tool="claude",
        model="claude-opus-4-8",
        agent_mode="execute",
    )

    async with automation_api_client(thread_api_session) as client:
        response = await client.get(
            "/api/v1/threads/by-automation-execution/execution-private",
            headers={"Authorization": "Bearer signed-grant-without-agent-action"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == (
        "WORKSPACE_EXECUTION_GRANT_ACTION_FORBIDDEN"
    )


@pytest.mark.asyncio
async def test_other_runtime_workspace_automation_thread_is_not_visible(
    thread_api_session: AsyncSession,
) -> None:
    await ThreadRepository(thread_api_session, workspace_id="workspace-other").create(
        ThreadModel(
            id="other-workspace-thread",
            workspace_id="workspace-other",
            user_id="user-a",
            origin="automation",
            title="",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=ThreadStatus.DRAFT.value,
            queued_messages=[],
            draft_message=None,
            archived=False,
            automation_job_id="job-other",
            automation_execution_id="execution-other",
        )
    )

    async with automation_api_client(thread_api_session) as client:
        response = await client.get(
            "/api/v1/threads/by-automation-execution/execution-other",
            headers={"Authorization": "Bearer user-b"},
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "automation_thread_not_found"


@pytest.mark.asyncio
async def test_thread_draft_list_detail_and_archive(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        assert draft_response.status_code == 201
        draft = draft_response.json()
        assert draft["status"] == "draft"
        assert draft["agenticTool"] == "claude"
        assert draft["title"] == "aiChat.thread.untitled"

        patch_response = await client.patch(
            f"/api/v1/threads/{draft['id']}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"draftMessage": {"text": "hello", "attachments": []}},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["draftMessage"] == {
            "text": "hello",
            "attachments": [],
        }

        list_response = await client.get(
            "/api/v1/threads",
            headers={"Authorization": "Bearer user-a"},
        )
        assert list_response.status_code == 200
        item = list_response.json()["items"][0]
        assert item["id"] == draft["id"]
        assert item["title"] == "aiChat.thread.untitled"
        assert "messages" not in item
        assert "queuedMessages" not in item
        assert "draftMessage" not in item

        detail_response = await client.get(
            f"/api/v1/threads/{draft['id']}",
            headers={"Authorization": "Bearer user-a"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["draftMessage"] == {"text": "hello", "attachments": []}
        assert "messages" not in detail

        archive_response = await client.post(
            f"/api/v1/threads/{draft['id']}/archive",
            headers={"Authorization": "Bearer user-a"},
        )
        assert archive_response.status_code == 200
        assert archive_response.json()["archived"] is True


@pytest.mark.asyncio
async def test_thread_api_enforces_user_privacy_and_automation_workspace_access(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        user_thread_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        user_thread_id = user_thread_response.json()["id"]
        automation_thread = await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).create(
            ThreadModel(
                id="automation-thread",
                workspace_id=get_settings().AILERON_WORKSPACE_ID,
                user_id="user-a",
                origin="automation",
                title="automation",
                agentic_tool="claude",
                model="claude-opus-4-8",
                claude_mode="execute",
                status=ThreadStatus.COMPLETE.value,
                queued_messages=[],
                draft_message=None,
                archived=False,
            )
        )
        await thread_api_session.commit()

        user_b_list = await client.get(
            "/api/v1/threads",
            headers={"Authorization": "Bearer user-b"},
        )
        assert user_b_list.status_code == 200
        assert user_b_list.json()["items"] == []

        user_b_private_get = await client.get(
            f"/api/v1/threads/{user_thread_id}",
            headers={"Authorization": "Bearer user-b"},
        )
        assert user_b_private_get.status_code == 404

        user_b_automation_get = await client.get(
            f"/api/v1/threads/{automation_thread.id}",
            headers={"Authorization": "Bearer user-b"},
        )
        assert user_b_automation_get.status_code == 200


@pytest.mark.asyncio
async def test_thread_api_deletes_thread_and_removes_it_from_list(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]
        delete_response = await client.delete(
            f"/api/v1/threads/{thread_id}",
            headers={"Authorization": "Bearer user-a"},
        )

        assert delete_response.status_code == 204

        list_response = await client.get(
            "/api/v1/threads",
            headers={"Authorization": "Bearer user-a"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["items"] == []
        messages = await thread_api_session.execute(
            select(ThreadMessageModel).where(ThreadMessageModel.thread_id == thread_id)
        )
        assert messages.scalars().all() == []


@pytest.mark.asyncio
async def test_thread_api_rejects_delete_for_running_thread(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        def mark_working(thread: ThreadModel) -> None:
            thread.status = ThreadStatus.WORKING.value

        await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).locked_update(thread_id, mark_working)
        await thread_api_session.commit()

        response = await client.delete(
            f"/api/v1/threads/{thread_id}",
            headers={"Authorization": "Bearer user-a"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "thread_running",
            "error_info": {"thread_id": thread_id},
        }


@pytest.mark.asyncio
async def test_thread_api_treats_automation_thread_delete_as_not_found(
    thread_api_session: AsyncSession,
) -> None:
    automation_thread = await ThreadRepository(
        thread_api_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
    ).create(
        ThreadModel(
            id="automation-thread",
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
            user_id="automation-owner",
            origin="automation",
            title="automation",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=ThreadStatus.COMPLETE.value,
            queued_messages=[],
            draft_message=None,
            archived=False,
        )
    )
    await thread_api_session.commit()

    async with api_client(thread_api_session) as client:
        response = await client.delete(
            f"/api/v1/threads/{automation_thread.id}",
            headers={"Authorization": "Bearer user-a"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "thread_not_found",
        "error_info": {"thread_id": automation_thread.id},
    }
    assert await thread_api_session.get(ThreadModel, automation_thread.id) is not None


@pytest.mark.asyncio
async def test_thread_api_rejects_locked_draft_patch(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        def mark_queued(thread: ThreadModel) -> None:
            thread.status = ThreadStatus.QUEUED.value

        await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).locked_update(thread_id, mark_queued)
        await thread_api_session.commit()

        response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"draftMessage": {"text": "locked", "attachments": []}},
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "thread_locked",
            "error_info": {"thread_id": thread_id},
        }


@pytest.mark.asyncio
async def test_thread_api_updates_locked_thread_model_and_mode(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        def mark_queued(thread: ThreadModel) -> None:
            thread.status = ThreadStatus.QUEUED.value

        await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).locked_update(thread_id, mark_queued)
        await thread_api_session.commit()

        response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"model": "claude-sonnet-5", "claudeMode": "plan"},
        )

        assert response.status_code == 200
        assert response.json()["agenticTool"] == "claude"
        assert response.json()["model"] == "claude-sonnet-5"
        assert response.json()["claudeMode"] == "plan"


@pytest.mark.asyncio
async def test_thread_api_rejects_locked_thread_agent_switch(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        def mark_queued(thread: ThreadModel) -> None:
            thread.status = ThreadStatus.QUEUED.value

        await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).locked_update(thread_id, mark_queued)
        await thread_api_session.commit()

        response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"agenticTool": "codex", "model": "gpt-5.6-sol", "claudeMode": None},
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "thread_locked",
            "error_info": {"thread_id": thread_id},
        }


@pytest.mark.asyncio
async def test_thread_api_removes_queued_message_by_id(
    thread_api_session: AsyncSession,
) -> None:
    thread = await ThreadRepository(
        thread_api_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
    ).create(
        ThreadModel(
            id="thread-with-queue",
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
            user_id="user-a",
            origin="user",
            title="queued",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=ThreadStatus.WORKING.value,
            queued_messages=[
                {"id": "queued-a", "text": "first queued", "attachments": []},
                {"id": "queued-b", "text": "second queued", "attachments": []},
            ],
            draft_message=None,
            archived=False,
        )
    )
    await thread_api_session.commit()

    async with api_client(thread_api_session) as client:
        response = await client.delete(
            f"/api/v1/threads/{thread.id}/queued-messages/queued-a",
            headers={"Authorization": "Bearer user-a"},
        )

        assert response.status_code == 200
        assert response.json()["queuedMessages"] == [
            {"id": "queued-b", "text": "second queued", "attachments": []}
        ]

        missing = await client.delete(
            f"/api/v1/threads/{thread.id}/queued-messages/missing",
            headers={"Authorization": "Bearer user-a"},
        )

        assert missing.status_code == 404
        assert missing.json() == {
            "error_code": "queued_message_not_found",
            "error_info": {"queued_message_id": "missing"},
        }


@pytest.mark.asyncio
async def test_thread_api_stop_dequeues_next_message_over_http(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        headers = {"Authorization": "Bearer user-a"}
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers=headers,
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        submitted = await client.post(
            f"/api/v1/threads/{thread_id}/submit",
            headers=headers,
            json={"text": "first", "attachments": []},
        )
        assert submitted.json()["status"] == "queued"
        first_execution_id = submitted.json()["activeTurnExecutionId"]

        await client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers=headers,
            json={"text": "second", "attachments": []},
        )
        await client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers=headers,
            json={"text": "third", "attachments": []},
        )

        response = await client.post(
            f"/api/v1/threads/{thread_id}/stop", headers=headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert [message["text"] for message in body["queuedMessages"]] == ["third"]
        assert body["activeTurnExecutionId"] != first_execution_id


@pytest.mark.asyncio
async def test_thread_api_stop_rejects_non_running_thread(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        headers = {"Authorization": "Bearer user-a"}
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers=headers,
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        response = await client.post(
            f"/api/v1/threads/{thread_id}/stop", headers=headers
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "invalid_state",
            "error_info": {"thread_id": thread_id},
        }


@pytest.mark.asyncio
async def test_thread_api_patches_draft_settings_and_message(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        model_response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"model": "claude-sonnet-5"},
        )

        assert model_response.status_code == 200
        assert model_response.json()["agenticTool"] == "claude"
        assert model_response.json()["model"] == "claude-sonnet-5"
        assert model_response.json()["claudeMode"] == "execute"

        switched_response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "codex",
                "model": "gpt-5.6-sol",
                "claudeMode": None,
                "draftMessage": {
                    "text": "Use Codex",
                    "attachments": [
                        {
                            "attachmentId": "123e4567-e89b-12d3-a456-426614174000",
                        }
                    ],
                },
            },
        )

        assert switched_response.status_code == 200
        assert switched_response.json()["agenticTool"] == "codex"
        assert switched_response.json()["model"] == "gpt-5.6-sol"
        assert switched_response.json()["claudeMode"] is None
        assert switched_response.json()["draftMessage"] == {
            "text": "Use Codex",
            "attachments": [
                {
                    "attachmentId": "123e4567-e89b-12d3-a456-426614174000",
                }
            ],
        }

        cleared_response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"draftMessage": None},
        )

        assert cleared_response.status_code == 200
        assert cleared_response.json()["draftMessage"] is None


@pytest.mark.asyncio
async def test_thread_api_updates_completed_thread_model_and_mode(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        def mark_complete(thread: ThreadModel) -> None:
            thread.status = ThreadStatus.COMPLETE.value

        await ThreadRepository(
            thread_api_session,
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
        ).locked_update(thread_id, mark_complete)
        await thread_api_session.commit()

        response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"model": "claude-sonnet-5", "claudeMode": "plan"},
        )

        assert response.status_code == 200
        assert response.json()["agenticTool"] == "claude"
        assert response.json()["model"] == "claude-sonnet-5"
        assert response.json()["claudeMode"] == "plan"


@pytest.mark.asyncio
async def test_thread_api_patch_draft_model_falls_back_instead_of_rejecting(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        response = await client.patch(
            f"/api/v1/threads/{thread_id}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"model": "missing-model"},
        )

        assert response.status_code == 200
        assert response.json()["model"] == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_submit_draft_falls_back_to_allowed_default_model(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "codex",
                "model": "gpt-5.6-sol",
                "claudeMode": None,
            },
        )
        assert draft_response.status_code == 201
        thread_id = draft_response.json()["id"]

        await put_capabilities(thread_api_session, make_fallback_capabilities())

        response = await client.post(
            f"/api/v1/threads/{thread_id}/submit",
            headers={"Authorization": "Bearer user-a"},
            json={"text": "hello", "attachments": []},
        )

        assert response.status_code == 200
        assert response.json()["model"] == "gpt-custom"


@pytest.mark.asyncio
async def test_answer_question_returns_detail_after_managed_transaction_submit(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)
    session_factory = async_sessionmaker(
        thread_api_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    runner = RecordingRunner()
    thread = await ThreadRepository(
        thread_api_session,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
    ).create(
        ThreadModel(
            id="answer-managed-transaction-thread",
            workspace_id=get_settings().AILERON_WORKSPACE_ID,
            user_id="user-a",
            origin="user",
            title="question",
            agentic_tool="claude",
            model="claude-opus-4-8",
            claude_mode="execute",
            status=ThreadStatus.COMPLETE.value,
            queued_messages=[],
            draft_message=None,
            archived=False,
        )
    )
    message_repo = ThreadMessageRepository(thread_api_session)
    turn_repo = ThreadTurnRepository(thread_api_session)
    turn = await turn_repo.create_turn(
        thread=thread,
        turn_id="answer-turn",
        status="running",
    )
    execution = await turn_repo.create_execution(
        thread=thread,
        turn=turn,
        execution_id="answer-execution",
        agentic_tool="claude",
        status="running",
    )
    question = await message_repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_call",
        {
            "name": QUESTION_TOOL_NAME,
            "parameters": {
                "id": "demo-form",
                "title": "Demo",
                "questions": [
                    {
                        "id": "choice",
                        "type": "radio",
                        "label": "Pick one",
                        "options": ["A", "B"],
                    }
                ],
            },
        },
        source_event_key="question",
        tool_call_key="question-call",
    )
    await message_repo.append(
        thread.id,
        turn.id,
        execution.id,
        "tool_result",
        {
            "isError": False,
            "preview": '{"ok":true}',
            "byteLength": 11,
            "lineCount": None,
            "truncated": False,
            "mediaType": "application/json",
        },
        source_event_key="question-delivered",
        parent_tool_use_id=question.id,
        result_kind="provider_result",
    )
    await turn_repo.finish(
        thread=thread,
        turn=turn,
        execution=execution,
        status="complete",
    )
    await thread_api_session.commit()

    async with api_client_with_managed_transaction(
        thread_api_session,
        session_factory,
        runner,
    ) as client:
        response = await client.post(
            f"/api/v1/threads/{thread.id}/questions/{question.id}/answer",
            headers={"Authorization": "Bearer user-a"},
            json={"answers": {"choice": "A"}, "text": "[form answers - demo-form]"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == thread.id
    assert body["status"] == "queued"
    assert runner.requests[0].thread_id == thread.id
    assert "messages" not in body
    assert body["changedItemIds"] == [str(question.id)]
    assert body["turns"][0]["id"] == turn.id
    assert body["executions"]


@pytest.mark.asyncio
async def test_thread_api_post_message_falls_back_to_allowed_default_model(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "codex",
                "model": "gpt-5.6-sol",
                "claudeMode": None,
            },
        )
        thread_id = draft_response.json()["id"]
        submit_response = await client.post(
            f"/api/v1/threads/{thread_id}/submit",
            headers={"Authorization": "Bearer user-a"},
            json={"text": "first", "attachments": []},
        )
        assert submit_response.status_code == 200

        await put_capabilities(thread_api_session, make_fallback_capabilities())

        response = await client.post(
            f"/api/v1/threads/{thread_id}/messages",
            headers={"Authorization": "Bearer user-a"},
            json={"text": "second", "attachments": []},
        )

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-custom"

    persisted = await thread_api_session.get(ThreadModel, thread_id)
    assert persisted is not None
    assert persisted.model == "gpt-custom"


@pytest.mark.asyncio
async def test_thread_api_rejects_invalid_brand_new_draft_selection(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "missing-model",
                "claudeMode": "execute",
            },
        )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_tool_selection"


@pytest.mark.asyncio
async def test_thread_api_rejects_legacy_draft_message_shape(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )

        response = await client.patch(
            f"/api/v1/threads/{draft_response.json()['id']}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"text": "legacy", "attachments": []},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_thread_api_rejects_draft_selection_change_without_capabilities(
    thread_api_session: AsyncSession,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client(thread_api_session) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        snapshot = await thread_api_session.get(
            RuntimeCapabilitiesModel,
            get_settings().AILERON_WORKSPACE_ID,
        )
        assert snapshot is not None
        await thread_api_session.delete(snapshot)
        await thread_api_session.commit()

        response = await client.patch(
            f"/api/v1/threads/{draft_response.json()['id']}/draft",
            headers={"Authorization": "Bearer user-a"},
            json={"model": "claude-sonnet-5"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "capabilities_unavailable",
            "error_info": {"workspace_id": get_settings().AILERON_WORKSPACE_ID},
        }


@pytest.mark.asyncio
async def test_thread_api_rejects_draft_when_capabilities_missing(
    thread_api_session: AsyncSession,
) -> None:
    async with api_client(thread_api_session) as client:
        response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "error_code": "capabilities_unavailable",
            "error_info": {"workspace_id": get_settings().AILERON_WORKSPACE_ID},
        }


@pytest.mark.asyncio
async def test_thread_api_uploads_and_deletes_thread_attachment(
    thread_api_session: AsyncSession,
    tmp_path,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client_with_attachment_storage(
        thread_api_session, tmp_path
    ) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]

        upload_response = await client.post(
            f"/api/v1/threads/{thread_id}/attachments",
            headers={"Authorization": "Bearer user-a"},
            files={"file": ("screen.png", b"image", "image/png")},
        )

        assert upload_response.status_code == 201
        uploaded = upload_response.json()
        assert uploaded == {
            "attachmentId": uploaded["attachmentId"],
            "kind": "image",
            "name": "screen.png",
            "mimeType": "image/png",
            "size": 5,
        }

        delete_response = await client.delete(
            f"/api/v1/threads/{thread_id}/attachments/{uploaded['attachmentId']}",
            headers={"Authorization": "Bearer user-a"},
        )

        assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_thread_api_lists_thread_attachments(
    thread_api_session: AsyncSession,
    tmp_path,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client_with_attachment_storage(
        thread_api_session, tmp_path
    ) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )
        thread_id = draft_response.json()["id"]
        first_upload = await client.post(
            f"/api/v1/threads/{thread_id}/attachments",
            headers={"Authorization": "Bearer user-a"},
            files={"file": ("screen.png", b"image", "image/png")},
        )
        second_upload = await client.post(
            f"/api/v1/threads/{thread_id}/attachments",
            headers={"Authorization": "Bearer user-a"},
            files={"file": ("notes.txt", b"notes", "text/plain")},
        )

        response = await client.get(
            f"/api/v1/threads/{thread_id}/attachments",
            headers={"Authorization": "Bearer user-a"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "items": [
                first_upload.json(),
                second_upload.json(),
            ],
            "total": 2,
        }


@pytest.mark.asyncio
async def test_thread_api_rejects_attachment_upload_for_missing_thread(
    thread_api_session: AsyncSession,
    tmp_path,
) -> None:
    async with api_client_with_attachment_storage(
        thread_api_session, tmp_path
    ) as client:
        response = await client.post(
            "/api/v1/threads/missing-thread/attachments",
            headers={"Authorization": "Bearer user-a"},
            files={"file": ("screen.png", b"image", "image/png")},
        )

        assert response.status_code == 404
        assert response.json() == {
            "error_code": "thread_not_found",
            "error_info": {"thread_id": "missing-thread"},
        }


@pytest.mark.asyncio
async def test_thread_api_rejects_unsupported_attachment_type(
    thread_api_session: AsyncSession,
    tmp_path,
) -> None:
    await put_capabilities(thread_api_session)

    async with api_client_with_attachment_storage(
        thread_api_session, tmp_path
    ) as client:
        draft_response = await client.post(
            "/api/v1/threads/draft",
            headers={"Authorization": "Bearer user-a"},
            json={
                "agenticTool": "claude",
                "model": "claude-opus-4-8",
                "claudeMode": "execute",
            },
        )

        response = await client.post(
            f"/api/v1/threads/{draft_response.json()['id']}/attachments",
            headers={"Authorization": "Bearer user-a"},
            files={"file": ("archive.zip", b"zip", "application/zip")},
        )

        assert response.status_code == 400
        assert response.json() == {
            "error_code": "unsupported-type",
            "error_info": {},
        }
