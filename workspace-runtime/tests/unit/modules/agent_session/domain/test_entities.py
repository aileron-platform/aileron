"""Entities 單元測試."""

from __future__ import annotations

from datetime import datetime

from app.modules.agent_session.domain.entities import AgentSession, Message, Task
from app.modules.agent_session.domain.enums import (
    AgentSessionStatus,
    AgenticTool,
    MessageRole,
    MessageType,
    TaskStatus,
)
from app.modules.agent_session.domain.value_objects import ModelConfig


class TestAgentSession:
    def test_create_session(self) -> None:
        now = datetime.utcnow()
        session = AgentSession(
            id="test-session-123",
            workspace_id="workspace-456",
            created_at=now,
        )

        assert session.id == "test-session-123"
        assert session.workspace_id == "workspace-456"
        assert session.status == AgentSessionStatus.IDLE
        assert session.agentic_tool == AgenticTool.CLAUDE_CODE
        assert session.archived is False
        assert session.ready_for_prompt is False

    def test_session_to_data_blob(self) -> None:
        session = AgentSession(
            id="session-blob",
            workspace_id="ws-blob",
            created_at=datetime.utcnow(),
            model_settings=ModelConfig(mode="alias", model="claude-sonnet"),
            context_window_limit=200000,
            message_count=5,
        )

        blob = session.to_data_blob()

        assert blob["model_config"]["model"] == "claude-sonnet"
        assert blob["message_count"] == 5
        assert blob["context_window_limit"] == 200000

    def test_session_from_db_row(self) -> None:
        now = datetime.utcnow()
        session = AgentSession.from_db_row(
            {
                "session_id": "db-session",
                "workspace_id": "db-ws",
                "created_at": now,
                "updated_at": None,
                "created_by": "db-user",
                "status": "running",
                "agentic_tool": "claude-code",
                "archived": False,
                "archived_reason": None,
                "ready_for_prompt": True,
                "data": {
                    "model_config": {
                        "mode": "alias",
                        "model": "claude-sonnet",
                    },
                    "message_count": 3,
                },
            }
        )

        assert session.id == "db-session"
        assert session.status == AgentSessionStatus.RUNNING
        assert session.model_settings is not None
        assert session.model_settings.model == "claude-sonnet"
        assert session.message_count == 3


class TestTask:
    def test_task_state_transitions(self) -> None:
        task = Task(id="task-trans", session_id="session-trans", created_at=datetime.utcnow())

        assert task.can_transition_to(TaskStatus.RUNNING) is True
        assert task.can_transition_to(TaskStatus.COMPLETED) is False

        task.status = TaskStatus.RUNNING
        assert task.can_transition_to(TaskStatus.AWAITING_PERMISSION) is True
        assert task.can_transition_to(TaskStatus.STOPPING) is True
        assert task.can_transition_to(TaskStatus.COMPLETED) is True
        assert task.can_transition_to(TaskStatus.CREATED) is False

        task.status = TaskStatus.COMPLETED
        assert task.can_transition_to(TaskStatus.RUNNING) is False

    def test_task_from_db_row(self) -> None:
        task = Task.from_db_row(
            {
                "task_id": "db-task",
                "session_id": "db-session",
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "status": "running",
                "created_by": "db-user",
                "data": {
                    "full_prompt": "Test prompt",
                    "tool_use_count": 2,
                },
            }
        )

        assert task.id == "db-task"
        assert task.status == TaskStatus.RUNNING
        assert task.full_prompt == "Test prompt"
        assert task.tool_use_count == 2


class TestMessage:
    def test_message_from_db_row(self) -> None:
        message = Message.from_db_row(
            {
                "message_id": "db-msg",
                "session_id": "db-session",
                "task_id": "db-task",
                "created_at": datetime.utcnow(),
                "type": "assistant",
                "role": "assistant",
                "index": 1,
                "status": None,
                "data": {
                    "content": [{"type": "text", "text": "Hello"}],
                    "metadata": {"source": "test"},
                },
            }
        )

        assert message.id == "db-msg"
        assert message.type == MessageType.ASSISTANT
        assert message.role == MessageRole.ASSISTANT
        assert message.content == [{"type": "text", "text": "Hello"}]
        assert message.metadata == {"source": "test"}

    def test_message_get_content_canvas(self) -> None:
        message = Message(
            id="msg-1",
            session_id="session-1",
            created_at=datetime.utcnow(),
            content=[{"type": "text", "text": "Hello world"}],
        )

        assert message.get_content_canvas() == "Hello world"
