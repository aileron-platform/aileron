"""Enums 單元測試."""

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
    """AgentSessionStatus 測試."""

    def test_values(self):
        """測試所有狀態值."""
        assert AgentSessionStatus.IDLE.value == "idle"
        assert AgentSessionStatus.RUNNING.value == "running"
        assert AgentSessionStatus.AWAITING_PERMISSION.value == "awaiting_permission"
        assert AgentSessionStatus.COMPLETED.value == "completed"
        assert AgentSessionStatus.FAILED.value == "failed"

    def test_membership(self):
        """測試成員檢查."""
        assert "idle" in [s.value for s in AgentSessionStatus]
        assert "invalid" not in [s.value for s in AgentSessionStatus]


class TestTaskStatus:
    """TaskStatus 測試."""

    def test_values(self):
        """測試所有狀態值."""
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.STOPPING.value == "stopping"
        assert TaskStatus.AWAITING_PERMISSION.value == "awaiting_permission"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.STOPPED.value == "stopped"

    def test_terminal_states(self):
        """測試終止狀態."""
        terminal = TaskStatus.terminal_states()
        assert TaskStatus.COMPLETED in terminal
        assert TaskStatus.FAILED in terminal
        assert TaskStatus.STOPPED in terminal
        assert TaskStatus.RUNNING not in terminal
        assert TaskStatus.CREATED not in terminal

    def test_is_terminal(self):
        """測試 is_terminal 屬性."""
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.FAILED.is_terminal is True
        assert TaskStatus.STOPPED.is_terminal is True
        assert TaskStatus.RUNNING.is_terminal is False
        assert TaskStatus.CREATED.is_terminal is False
        assert TaskStatus.AWAITING_PERMISSION.is_terminal is False

    def test_active_states(self):
        """測試活躍狀態 (非終止狀態)."""
        # is_active 是 not is_terminal，所以所有非終止狀態都是 active
        assert TaskStatus.RUNNING.is_active is True
        assert TaskStatus.AWAITING_PERMISSION.is_active is True
        assert TaskStatus.STOPPING.is_active is True
        assert TaskStatus.CREATED.is_active is True  # CREATED 也是非終止狀態
        assert TaskStatus.COMPLETED.is_active is False
        assert TaskStatus.FAILED.is_active is False
        assert TaskStatus.STOPPED.is_active is False

    def test_is_active(self):
        """測試 is_active 屬性."""
        assert TaskStatus.RUNNING.is_active is True
        assert TaskStatus.AWAITING_PERMISSION.is_active is True
        assert TaskStatus.STOPPING.is_active is True
        assert TaskStatus.CREATED.is_active is True
        assert TaskStatus.COMPLETED.is_active is False


class TestAgenticTool:
    """AgenticTool 測試."""

    def test_values(self):
        """測試所有工具值."""
        assert AgenticTool.CLAUDE_CODE.value == "claude-code"
        assert AgenticTool.CODEX.value == "codex"
        assert AgenticTool.GEMINI.value == "gemini"
        assert AgenticTool.OPENCODE.value == "opencode"

    def test_from_string(self):
        """測試從字串轉換."""
        assert AgenticTool("claude-code") == AgenticTool.CLAUDE_CODE
        assert AgenticTool("codex") == AgenticTool.CODEX

    def test_invalid_tool(self):
        """測試無效工具."""
        with pytest.raises(ValueError):
            AgenticTool("invalid-tool")


class TestMessageType:
    """MessageType 測試."""

    def test_values(self):
        """測試所有類型值."""
        assert MessageType.USER.value == "user"
        assert MessageType.ASSISTANT.value == "assistant"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.FILE_HISTORY_SNAPSHOT.value == "file-history-snapshot"
        assert MessageType.PERMISSION_REQUEST.value == "permission_request"


class TestContentBlockType:
    """ContentBlockType 測試."""

    def test_values(self):
        """測試所有區塊類型."""
        assert ContentBlockType.TEXT.value == "text"
        assert ContentBlockType.IMAGE.value == "image"
        assert ContentBlockType.TOOL_USE.value == "tool_use"
        assert ContentBlockType.TOOL_RESULT.value == "tool_result"
        assert ContentBlockType.THINKING.value == "thinking"
        assert ContentBlockType.SYSTEM_STATUS.value == "system_status"
        assert ContentBlockType.SYSTEM_COMPLETE.value == "system_complete"


class TestPermissionEnums:
    """Permission 相關列舉測試."""

    def test_permission_mode(self):
        """測試 PermissionMode (Claude SDK 原生模式)."""
        assert PermissionMode.DEFAULT.value == "default"
        assert PermissionMode.ACCEPT_EDITS.value == "acceptEdits"
        assert PermissionMode.BYPASS_PERMISSIONS.value == "bypassPermissions"
        assert PermissionMode.PLAN.value == "plan"
        assert PermissionMode.DONT_ASK.value == "dontAsk"
        assert PermissionMode.AUTO.value == "auto"

    def test_permission_scope(self):
        """測試 PermissionScope."""
        assert PermissionScope.ONCE.value == "once"
        assert PermissionScope.PROJECT.value == "project"
        assert PermissionScope.USER.value == "user"
        assert PermissionScope.LOCAL.value == "local"

    def test_permission_status(self):
        """測試 PermissionStatus."""
        assert PermissionStatus.PENDING.value == "pending"
        assert PermissionStatus.APPROVED.value == "approved"
        assert PermissionStatus.DENIED.value == "denied"
