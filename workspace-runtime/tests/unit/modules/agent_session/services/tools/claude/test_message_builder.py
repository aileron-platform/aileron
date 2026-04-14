from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.services.tools.base.types import TokenUsage
from app.modules.agent_session.services.tools.claude import message_builder


async def test_create_user_message_normalizes_string_content() -> None:
    message_service = AsyncMock()
    message_service.create_message.return_value = SimpleNamespace(
        id="msg-1",
        session_id="session-1",
        task_id="task-1",
        type=MessageType.USER,
        role=MessageRole.USER,
        index=1,
        content="hello",
        created_at=datetime(2026, 3, 28, tzinfo=UTC),
    )

    payload = await message_builder.create_user_message(
        session_id="session-1",
        prompt="hello",
        task_id="task-1",
        index=1,
        message_service=message_service,
    )

    assert payload["content_blocks"] == [{"type": "text", "text": "hello"}]
    create_input = message_service.create_message.await_args.args[0]
    assert create_input.content == [{"type": "text", "text": "hello"}]


async def test_create_assistant_message_includes_metadata_and_tokens() -> None:
    message_service = AsyncMock()
    message_service.create_message.return_value = SimpleNamespace(id="assistant-1")

    message_id = await message_builder.create_assistant_message(
        session_id="session-1",
        message_id="ignored-id",
        content=[{"type": "text", "text": "done"}],
        tool_uses=[{"id": "tool-1"}],
        task_id="task-1",
        index=2,
        resolved_model="claude-3",
        message_service=message_service,
        parent_tool_use_id="parent-1",
        token_usage=TokenUsage(input=10, output=20, cache_read=3, cache_creation=4),
    )

    assert message_id == "assistant-1"
    create_input = message_service.create_message.await_args.args[0]
    assert create_input.metadata == {
        "source": "claude-sdk",
        "model": "claude-3",
        "tokens": {"input": 10, "output": 20, "cache_read": 3, "cache_creation": 4},
        "parent_tool_use_id": "parent-1",
    }


async def test_create_tool_result_and_system_message_metadata() -> None:
    message_service = AsyncMock()
    message_service.create_message.side_effect = [
        SimpleNamespace(id="tool-result-1"),
        SimpleNamespace(id="system-1"),
    ]

    tool_result_id = await message_builder.create_tool_result_message(
        session_id="session-1",
        content=[{"type": "tool_result", "content": "ok"}],
        task_id="task-1",
        index=3,
        message_service=message_service,
    )
    system_id = await message_builder.create_system_message(
        session_id="session-1",
        content=[{"type": "text", "text": "system"}],
        task_id=None,
        index=4,
        resolved_model=None,
        message_service=message_service,
    )

    assert tool_result_id == "tool-result-1"
    assert system_id == "system-1"
    tool_input = message_service.create_message.await_args_list[0].args[0]
    system_input = message_service.create_message.await_args_list[1].args[0]
    assert tool_input.metadata == {"source": "claude-sdk", "is_tool_result": True}
    assert system_input.metadata == {"source": "claude-sdk"}
