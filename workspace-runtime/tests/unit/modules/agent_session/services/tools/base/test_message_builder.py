from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.agent_session.domain.enums import MessageRole, MessageType
from app.modules.agent_session.services.tools.base import message_builder
from app.modules.agent_session.services.tools.base.types import TokenUsage


def _message(
    message_id: str,
    message_type,
    role,
    content,
    index: int = 1,
    task_id: str | None = "task-1",
):
    return SimpleNamespace(
        id=message_id,
        session_id="session-1",
        task_id=task_id,
        type=message_type,
        role=role,
        index=index,
        content=content,
        created_at=datetime(2026, 3, 28, tzinfo=UTC),
    )


async def test_create_user_message_for_claude_and_acp() -> None:
    for source in ("claude-sdk", "acp"):
        message_service = AsyncMock()
        message_service.create_message.return_value = _message(
            "msg-1",
            MessageType.USER,
            MessageRole.USER,
            "hello",
        )

        payload = await message_builder.create_user_message(
            session_id="session-1",
            prompt="hello",
            task_id="task-1",
            index=1,
            message_service=message_service,
            source=source,
        )

        assert payload["content_blocks"] == [{"type": "text", "text": "hello"}]
        create_input = message_service.create_message.await_args.args[0]
        assert create_input.metadata == {"source": source}


async def test_create_assistant_message_for_claude_and_acp() -> None:
    for source in ("claude-sdk", "acp"):
        message_service = AsyncMock()
        message_service.create_message.return_value = _message(
            "assistant-1",
            MessageType.ASSISTANT,
            MessageRole.ASSISTANT,
            [{"type": "text", "text": "done"}],
            index=2,
        )

        payload = await message_builder.create_assistant_message(
            session_id="session-1",
            content=[{"type": "text", "text": "done"}],
            tool_uses=[{"id": "tool-1", "name": "search", "input": {}}],
            task_id="task-1",
            index=2,
            resolved_model="model-1",
            message_service=message_service,
            source=source,
            parent_tool_use_id="parent-1",
            token_usage=TokenUsage(input=10, output=20, cache_read=3, cache_creation=4),
            metadata={"stop_reason": "end"},
        )

        assert payload["message_id"] == "assistant-1"
        create_input = message_service.create_message.await_args.args[0]
        assert create_input.metadata == {
            "source": source,
            "stop_reason": "end",
            "model": "model-1",
            "tokens": {"input": 10, "output": 20, "cache_read": 3, "cache_creation": 4},
            "parent_tool_use_id": "parent-1",
        }
        assert len(create_input.tool_uses) == 1


async def test_create_tool_result_message_for_claude_and_acp() -> None:
    for source in ("claude-sdk", "acp"):
        message_service = AsyncMock()
        message_service.create_message.return_value = _message(
            "tool-result-1",
            MessageType.USER,
            MessageRole.USER,
            [{"type": "tool_result", "content": "ok"}],
            index=3,
        )

        payload = await message_builder.create_tool_result_message(
            session_id="session-1",
            content=[{"type": "tool_result", "content": "ok"}],
            task_id="task-1",
            index=3,
            message_service=message_service,
            source=source,
        )

        assert payload["message_id"] == "tool-result-1"
        create_input = message_service.create_message.await_args.args[0]
        assert create_input.metadata == {"source": source, "is_tool_result": True}


async def test_create_system_message_for_claude_and_acp() -> None:
    for source in ("claude-sdk", "acp"):
        message_service = AsyncMock()
        message_service.create_message.return_value = _message(
            "system-1",
            MessageType.SYSTEM,
            MessageRole.SYSTEM,
            [{"type": "text", "text": "system"}],
            index=4,
            task_id=None,
        )

        payload = await message_builder.create_system_message(
            session_id="session-1",
            content=[{"type": "text", "text": "system"}],
            task_id=None,
            index=4,
            resolved_model="model-1",
            message_service=message_service,
            source=source,
        )

        assert payload["message_id"] == "system-1"
        create_input = message_service.create_message.await_args.args[0]
        assert create_input.metadata == {"source": source, "model": "model-1"}
