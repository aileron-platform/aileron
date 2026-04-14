from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.services.tools.acp import message_builder


async def test_create_user_message_normalizes_string_content() -> None:
    message_service = AsyncMock()
    created_message = SimpleNamespace(
        id="msg-1",
        session_id="session-1",
        task_id="task-1",
        type=MessageType.USER,
        role=MessageRole.USER,
        index=3,
        content="hello",
        created_at=datetime(2026, 3, 28, tzinfo=UTC),
    )
    message_service.create_message.return_value = created_message

    payload = await message_builder.create_user_message(
        session_id="session-1",
        prompt="hello",
        task_id="task-1",
        index=3,
        message_service=message_service,
    )

    assert payload == {
        "message_id": "msg-1",
        "session_id": "session-1",
        "task_id": "task-1",
        "type": "user",
        "role": "user",
        "index": 3,
        "content_blocks": [{"type": "text", "text": "hello"}],
        "created_at": "2026-03-28T00:00:00+00:00",
    }
    create_input = message_service.create_message.await_args.args[0]
    assert create_input.session_id == "session-1"
    assert create_input.content == [{"type": "text", "text": "hello"}]


async def test_create_assistant_message_preserves_list_content_and_merges_metadata() -> None:
    message_service = AsyncMock()
    created_message = SimpleNamespace(
        id="msg-2",
        session_id="session-1",
        task_id=None,
        type="assistant",
        role="assistant",
        index=4,
        content=[{"type": "text", "text": "done"}],
        created_at=None,
    )
    message_service.create_message.return_value = created_message

    payload = await message_builder.create_assistant_message(
        session_id="session-1",
        content=[{"type": "text", "text": "done"}],
        task_id=None,
        index=4,
        message_service=message_service,
        tool_uses=[{"id": "tool-1", "name": "search", "input": {}}],
        metadata={"foo": "bar"},
    )

    assert payload == {
        "message_id": "msg-2",
        "session_id": "session-1",
        "task_id": None,
        "type": "assistant",
        "role": "assistant",
        "index": 4,
        "content_blocks": [{"type": "text", "text": "done"}],
        "created_at": None,
    }
    create_input = message_service.create_message.await_args.args[0]
    assert create_input.metadata == {"source": "acp", "foo": "bar"}
    assert len(create_input.tool_uses) == 1
    assert create_input.tool_uses[0].id == "tool-1"
