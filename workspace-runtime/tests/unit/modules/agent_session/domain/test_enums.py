"""Enums unit tests."""

import pytest
from app.modules.agent_session.domain.enums import (
    AgenticTool,
    AgentSessionStatus,
    ArchivedReason,
    ContentBlockType,
    MessageRole,
    MessageStatus,
    MessageType,
    PermissionMode,
    PermissionScope,
    PermissionStatus,
    TaskStatus,
)


class TestAgentSessionStatus:
    """AgentSessionStatus tests."""

    def test_values(self):
        """Test all status values."""
        assert AgentSessionStatus.IDLE.value == "idle"
        assert AgentSessionStatus.RUNNING.value == "running"
        assert AgentSessionStatus.AWAITING_PERMISSION.value == "awaiting_permission"
        assert AgentSessionStatus.COMPLETED.value == "completed"
        assert AgentSessionStatus.FAILED.value == "failed"

    def test_membership(self):
        """Test member checking."""
        assert "idle" in [s.value for s in AgentSessionStatus]
        assert "invalid" not in [s.value for s in AgentSessionStatus]


class TestTaskStatus:
    """TaskStatus tests."""

    def test_values(self):
        """Test all status values."""
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.STOPPING.value == "stopping"
        assert TaskStatus.AWAITING_PERMISSION.value == "awaiting_permission"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.STOPPED.value == "stopped"

    def test_terminal_states(self):
        """Test terminal states."""
        terminal = TaskStatus.terminal_states()
        assert TaskStatus.COMPLETED in terminal
        assert TaskStatus.FAILED in terminal
        assert TaskStatus.STOPPED in terminal
        assert TaskStatus.RUNNING not in terminal
        assert TaskStatus.CREATED not in terminal

    def test_is_terminal(self):
        """Test is_terminal property."""
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.FAILED.is_terminal is True
        assert TaskStatus.STOPPED.is_terminal is True
        assert TaskStatus.RUNNING.is_terminal is False
        assert TaskStatus.CREATED.is_terminal is False
        assert TaskStatus.AWAITING_PERMISSION.is_terminal is False

    def test_active_states(self):
        """Test active states (non-terminal states)."""
        # is_active is not is_terminal, so all non-terminal states are active
        assert TaskStatus.RUNNING.is_active is True
        assert TaskStatus.AWAITING_PERMISSION.is_active is True
        assert TaskStatus.STOPPING.is_active is True
        assert TaskStatus.CREATED.is_active is True  # CREATED is also non-terminal
        assert TaskStatus.COMPLETED.is_active is False
        assert TaskStatus.FAILED.is_active is False
        assert TaskStatus.STOPPED.is_active is False

    def test_is_active(self):
        """Test is_active property."""
        assert TaskStatus.RUNNING.is_active is True
        assert TaskStatus.AWAITING_PERMISSION.is_active is True
        assert TaskStatus.STOPPING.is_active is True
        assert TaskStatus.CREATED.is_active is True
        assert TaskStatus.COMPLETED.is_active is False


class TestAgenticTool:
    """AgenticTool tests."""

    def test_values(self):
        """Test all tool values."""
        assert AgenticTool.CLAUDE_CODE.value == "claude-code"
        assert AgenticTool.CODEX.value == "codex"
        assert AgenticTool.GEMINI.value == "gemini"
        assert AgenticTool.OPENCODE.value == "opencode"

    def test_from_string(self):
        """Test conversion from string."""
        assert AgenticTool("claude-code") == AgenticTool.CLAUDE_CODE
        assert AgenticTool("codex") == AgenticTool.CODEX

    def test_invalid_tool(self):
        """Test invalid tool."""
        with pytest.raises(ValueError):
            AgenticTool("invalid-tool")


class TestMessageType:
    """MessageType tests."""

    def test_values(self):
        """Test all type values."""
        assert MessageType.USER.value == "user"
        assert MessageType.ASSISTANT.value == "assistant"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.FILE_HISTORY_SNAPSHOT.value == "file-history-snapshot"
        assert MessageType.PERMISSION_REQUEST.value == "permission_request"


class TestContentBlockType:
    """ContentBlockType tests."""

    def test_values(self):
        """Test all block types."""
        assert ContentBlockType.TEXT.value == "text"
        assert ContentBlockType.IMAGE.value == "image"
        assert ContentBlockType.TOOL_USE.value == "tool_use"
        assert ContentBlockType.TOOL_RESULT.value == "tool_result"
        assert ContentBlockType.THINKING.value == "thinking"
        assert ContentBlockType.SYSTEM_STATUS.value == "system_status"
        assert ContentBlockType.SYSTEM_COMPLETE.value == "system_complete"


class TestPermissionEnums:
    """Permission-related enum tests."""

    def test_permission_mode(self):
        """Test PermissionMode (Claude SDK native modes)."""
        assert PermissionMode.DEFAULT.value == "default"
        assert PermissionMode.ACCEPT_EDITS.value == "acceptEdits"
        assert PermissionMode.BYPASS_PERMISSIONS.value == "bypassPermissions"
        assert PermissionMode.PLAN.value == "plan"
        assert PermissionMode.DONT_ASK.value == "dontAsk"
        assert PermissionMode.AUTO.value == "auto"

    def test_permission_scope(self):
        """Test PermissionScope."""
        assert PermissionScope.ONCE.value == "once"
        assert PermissionScope.PROJECT.value == "project"
        assert PermissionScope.USER.value == "user"
        assert PermissionScope.LOCAL.value == "local"

    def test_permission_status(self):
        """Test PermissionStatus."""
        assert PermissionStatus.PENDING.value == "pending"
        assert PermissionStatus.APPROVED.value == "approved"
        assert PermissionStatus.DENIED.value == "denied"
