from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.schemas.message import MessageCreate, MessageQuery, ToolUseCreate
from app.modules.agent_session.services.message_service import MessageService, MessageServiceError


@pytest.fixture
def message_service() -> MessageService:
    repo = Mock()
    repo.get_next_index = AsyncMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_session = AsyncMock()
    repo.count = AsyncMock()
    repo.find_by_task = AsyncMock()
    repo.find_by_range = AsyncMock()
    repo.create_bulk = AsyncMock()
    repo.delete = AsyncMock()
    repo.find_permission_request = AsyncMock()
    repo.update = AsyncMock()
    repo.create_queued = AsyncMock()
    repo.count_queued = AsyncMock()
    repo.find_queued = AsyncMock()
    repo.delete_queued = AsyncMock()
    repo.to_entity = Mock()

    session_repo = Mock()
    session_repo.increment_message_count = AsyncMock()
    session_repo.find_by_id = AsyncMock()
    session_repo.update = AsyncMock()
    session_repo.to_entity = Mock()
    emitter = AsyncMock()
    return MessageService(
        db=AsyncMock(),
        message_repo=repo,
        session_repo=session_repo,
        emitter=emitter,
    )


@pytest.mark.asyncio
async def test_create_message_serializes_tool_uses_and_updates_first_title(
    message_service: MessageService,
) -> None:
    entity = SimpleNamespace(message_id="msg-1")
    message_service.message_repo.get_next_index.return_value = 0
    message_service.message_repo.create.return_value = SimpleNamespace()
    message_service.message_repo.to_entity.return_value = entity
    message_service._update_session_title_from_first_message = AsyncMock()

    result = await message_service.create_message(
        MessageCreate(
            session_id="session-1",
            task_id="task-1",
            type=MessageType.USER,
            role=MessageRole.USER,
            content="hello\x00world",
            tool_uses=[ToolUseCreate(id="tool-1", name="bash", input={"cmd": "pwd"})],
            metadata={"source": "ui"},
            parent_tool_use_id="parent-1",
        )
    )

    assert result is entity
    payload = message_service.message_repo.create.await_args.args[0]
    assert payload["session_id"] == "session-1"
    assert payload["task_id"] == "task-1"
    assert payload["content_preview"] == "hello\x00world"
    assert '"tool_uses"' in payload["data"]
    assert "\\u0000" in payload["data"]
    message_service.session_repo.increment_message_count.assert_awaited_once_with("session-1")
    message_service._update_session_title_from_first_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_messages_requires_session_id(message_service: MessageService) -> None:
    with pytest.raises(MessageServiceError, match="session_id is required"):
        await message_service.find_messages(MessageQuery())


@pytest.mark.asyncio
async def test_find_messages_builds_filters_and_returns_entities(
    message_service: MessageService,
) -> None:
    model = SimpleNamespace(message_id="m1")
    entity = SimpleNamespace(id="m1")
    message_service.message_repo.find_by_session.return_value = [model]
    message_service.message_repo.count.return_value = 3
    message_service.message_repo.to_entity.return_value = entity

    messages, total = await message_service.find_messages(
        MessageQuery(session_id="session-1", task_id="task-1", type=MessageType.ASSISTANT, limit=10, offset=5)
    )

    assert messages == [entity]
    assert total == 3
    message_service.message_repo.find_by_session.assert_awaited_once_with(
        session_id="session-1",
        task_id="task-1",
        message_type=MessageType.ASSISTANT,
        limit=10,
        offset=5,
    )
    message_service.message_repo.count.assert_awaited_once_with(
        {"session_id": "session-1", "status": None, "task_id": "task-1", "type": "assistant"}
    )


@pytest.mark.asyncio
async def test_create_bulk_empty_returns_empty_list(message_service: MessageService) -> None:
    assert await message_service.create_bulk([]) == []


@pytest.mark.asyncio
async def test_create_permission_request_and_update_permission_request(
    message_service: MessageService,
) -> None:
    created_entity = SimpleNamespace(id="perm-1")
    updated_entity = SimpleNamespace(id="perm-1", status="approved")
    model = SimpleNamespace(message_id="perm-1", data='{"content":{"status":"pending"}}')
    message_service.message_repo.get_next_index.return_value = 4
    message_service.message_repo.create.return_value = SimpleNamespace()
    message_service.message_repo.to_entity.side_effect = [created_entity, updated_entity]
    message_service.message_repo.find_permission_request.return_value = model
    message_service.message_repo.update.return_value = SimpleNamespace()

    created = await message_service.create_permission_request(
        session_id="session-1",
        task_id="task-1",
        request_id="req-1",
        tool_name="bash",
        tool_input={"cmd": "ls"},
        tool_use_id="tool-1",
        decision_type="permission",
        options=[{"option_id": "allow", "kind": "allow_once"}],
        raw_tool_call={"raw": True},
        tool_call_id="call-1",
    )
    updated = await message_service.update_permission_request(
        session_id="session-1",
        request_id="req-1",
        status="approved",
        scope="session",
        approved_by="user-1",
        decision_type="permission",
        outcome="selected",
        option_id="allow",
        reason="ok",
        decision_content="accepted",
    )

    assert created is created_entity
    assert updated is updated_entity
    created_payload = message_service.message_repo.create.await_args.args[0]
    assert created_payload["type"] == "permission_request"
    assert created_payload["role"] == "system"
    update_payload = message_service.message_repo.update.await_args.args[1]
    assert '"approved"' in update_payload["data"]
    assert '"scope": "session"' in update_payload["data"]
    assert '"content": "accepted"' in update_payload["data"]


@pytest.mark.asyncio
async def test_update_permission_request_returns_none_when_message_missing(
    message_service: MessageService,
) -> None:
    message_service.message_repo.find_permission_request.return_value = None

    result = await message_service.update_permission_request(
        session_id="session-1",
        request_id="req-1",
        status="denied",
    )

    assert result is None


@pytest.mark.asyncio
async def test_queue_methods_delegate_to_repository(message_service: MessageService) -> None:
    queued_model = SimpleNamespace()
    queued_entity = SimpleNamespace(id="queued-1")
    message_service.message_repo.create_queued.return_value = queued_model
    message_service.message_repo.find_queued.return_value = [queued_model]
    message_service.message_repo.count_queued.return_value = 2
    message_service.message_repo.delete_queued.return_value = True
    message_service.message_repo.to_entity.return_value = queued_entity

    created = await message_service.create_queued_message(
        session_id="session-1",
        prompt="queued prompt",
        metadata={"source": "ui"},
        queued_by_user_id="user-1",
    )
    total = await message_service.count_queued_messages("session-1")
    messages = await message_service.get_queued_messages("session-1")
    deleted = await message_service.delete_queued_message("queued-1")

    assert created is queued_entity
    assert total == 2
    assert messages == [queued_entity]
    assert deleted is True
    queued_metadata = message_service.message_repo.create_queued.await_args.kwargs["metadata"]
    assert queued_metadata["source"] == "ui"
    assert queued_metadata["queued_by_user_id"] == "user-1"
    assert "queued_at" in queued_metadata


def test_json_helpers_and_content_preview(message_service: MessageService) -> None:
    assert message_service._json_dumps({"text": "a\x00b"}) == '{"text": "a\\u0000b"}'
    assert message_service._json_loads(None) == {}
    assert message_service._json_loads("not-json") == {}
    assert message_service._get_content_preview("hello world") == "hello world"
    assert message_service._get_content_preview([{"type": "text", "text": "from block"}]) == "from block"
    assert message_service._get_content_preview({"request_id": "req-1", "tool_name": "bash"}) == "Permission request: bash"
    assert message_service._get_content_preview({"text": "inline"}) == "inline"
    assert message_service._get_content_preview({"other": "x"}) == ""


@pytest.mark.asyncio
async def test_update_session_title_from_first_message_handles_truncation_and_bad_data(
    message_service: MessageService,
) -> None:
    session_model = SimpleNamespace(data="{bad json")
    session_entity = SimpleNamespace(title=None, workspace_id="workspace-1")
    message_service.session_repo.find_by_id.return_value = session_model
    message_service.session_repo.to_entity.return_value = session_entity

    await message_service._update_session_title_from_first_message(
        "session-1",
        " line one\nline two " * 5,
        max_length=20,
    )

    message_service.session_repo.update.assert_awaited_once()
    title_payload = message_service.session_repo.update.await_args.args[1]["data"]
    assert "line one line two" in title_payload
    message_service.emitter.emit_session_patched.assert_awaited_once_with(
        "session-1",
        {"session_id": "session-1", "title": "line one line two...", "workspace_id": "workspace-1"},
    )


@pytest.mark.asyncio
async def test_update_session_title_from_first_message_skips_when_session_missing_or_has_title(
    message_service: MessageService,
) -> None:
    message_service.session_repo.find_by_id.return_value = None
    await message_service._update_session_title_from_first_message("session-1", "hello")
    message_service.session_repo.update.assert_not_awaited()

    message_service.session_repo.find_by_id.return_value = SimpleNamespace(data="{}")
    message_service.session_repo.to_entity.return_value = SimpleNamespace(title="existing", workspace_id="ws")
    await message_service._update_session_title_from_first_message("session-1", "hello")
    message_service.session_repo.update.assert_not_awaited()
