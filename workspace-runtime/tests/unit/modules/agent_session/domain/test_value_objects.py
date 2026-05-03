"""Value Objects unit tests."""

import pytest
from app.modules.agent_session.domain.value_objects import (
    PermissionConfig,
    CodexPermissionConfig,
    ModelConfig,
    MessageRange,
    ToolUse,
    PermissionRequestContent,
    TokenUsage,
    ContextWindowStatus,
    ToolCapabilities,
    TOOL_CAPABILITIES,
    get_tool_capabilities,
)
from app.modules.agent_session.domain.enums import (
    PermissionMode,
    PermissionScope,
    PermissionStatus,
    CodexSandboxMode,
    CodexApprovalPolicy,
)


class TestPermissionConfig:
    """PermissionConfig tests."""

    def test_default_config(self):
        """Test default configuration."""
        config = PermissionConfig()

        assert config.mode == PermissionMode.DEFAULT
        assert config.codex is None

    def test_custom_config(self):
        """Test custom configuration."""
        codex_config = CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.RELAXED,
            approval_policy=CodexApprovalPolicy.AUTO,
        )
        config = PermissionConfig(
            mode=PermissionMode.ACCEPT_EDITS,
            codex=codex_config,
        )

        assert config.mode == PermissionMode.ACCEPT_EDITS
        assert config.codex is not None
        assert config.codex.sandbox_mode == CodexSandboxMode.RELAXED

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = PermissionConfig(mode=PermissionMode.BYPASS_PERMISSIONS)

        d = config.to_dict()

        assert d["mode"] == "bypassPermissions"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "mode": "acceptEdits",
        }

        config = PermissionConfig.from_dict(data)

        assert config.mode == PermissionMode.ACCEPT_EDITS

    def test_codex_config_omits_network_access(self):
        """Test Codex permission config does not expose network access."""
        config = PermissionConfig.from_dict(
            {
                "mode": "default",
                "codex": {
                    "sandboxMode": "relaxed",
                    "approvalPolicy": "manual",
                },
            }
        )

        assert config.codex is not None
        assert config.to_dict()["codex"] == {
            "sandboxMode": "relaxed",
            "approvalPolicy": "manual",
        }


class TestModelConfig:
    """ModelConfig tests."""

    def test_default_config(self):
        """Test default configuration."""
        config = ModelConfig()

        assert config.mode == "alias"
        assert config.model == ""

    def test_custom_config(self):
        """Test custom configuration."""
        config = ModelConfig(
            mode="exact",
            model="claude-3-5-sonnet-20241022",
            thinking_mode="auto",
            provider="anthropic",
        )

        assert config.mode == "exact"
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.thinking_mode == "auto"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ModelConfig(
            mode="alias",
            model="claude-sonnet",
            thinking_mode="manual",
        )

        d = config.to_dict()

        assert d["mode"] == "alias"
        assert d["model"] == "claude-sonnet"
        assert d["thinkingMode"] == "manual"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "mode": "exact",
            "model": "gemini-pro",
            "thinkingMode": "auto",
        }

        config = ModelConfig.from_dict(data)

        assert config.mode == "exact"
        assert config.model == "gemini-pro"
        assert config.thinking_mode == "auto"


class TestTokenUsage:
    """TokenUsage tests."""

    def test_basic_usage(self):
        """Test basic usage."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )

        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.total_tokens == 1500

    def test_with_cache(self):
        """Test usage with cache."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=300,
        )

        assert usage.cache_creation_input_tokens == 200
        assert usage.cache_read_input_tokens == 300

    def test_to_dict(self):
        """Test conversion to dictionary."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        d = usage.to_dict()

        assert d["input_tokens"] == 100
        assert d["output_tokens"] == 50
        assert d["total_tokens"] == 150

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "input_tokens": 2000,
            "output_tokens": 1000,
            "total_tokens": 3000,
            "cache_read_input_tokens": 500,
        }

        usage = TokenUsage.from_dict(data)

        assert usage.input_tokens == 2000
        assert usage.cache_read_input_tokens == 500


class TestContextWindowStatus:
    """ContextWindowStatus tests."""

    def test_basic_status(self):
        """Test basic status."""
        status = ContextWindowStatus(
            current_usage=50000,
            limit=200000,
            usage_percentage=25.0,
            needs_compaction=False,
        )

        assert status.current_usage == 50000
        assert status.limit == 200000
        assert status.usage_percentage == 25.0
        assert status.needs_compaction is False

    def test_from_usage(self):
        """Test creation from usage."""
        status = ContextWindowStatus.from_usage(
            current_usage=170000,
            limit=200000,
        )

        assert status.current_usage == 170000
        assert status.usage_percentage == 85.0
        assert status.needs_compaction is True  # > 80%

    def test_needs_compaction_threshold(self):
        """Test compaction threshold."""
        # Below 80%, no compaction needed
        status1 = ContextWindowStatus.from_usage(
            current_usage=140000,
            limit=200000,
        )
        assert status1.needs_compaction is False  # 70%

        # At or above 80%, compaction needed
        status2 = ContextWindowStatus.from_usage(
            current_usage=160000,
            limit=200000,
        )
        assert status2.needs_compaction is True  # 80%


class TestToolCapabilities:
    """ToolCapabilities tests."""

    def test_claude_code_capabilities(self):
        """Test Claude Code capabilities."""
        caps = get_tool_capabilities("claude-code")

        assert caps is not None
        assert caps.name == "Claude Code"
        assert caps.streaming is True
        assert caps.thinking is True
        assert caps.multimodal is True
        assert caps.max_context_window == 200000
        assert caps.prompt_caching is True
        assert "read_file" in caps.built_in_tools

    def test_gemini_capabilities(self):
        """Test Gemini capabilities."""
        caps = get_tool_capabilities("gemini")

        assert caps is not None
        assert caps.name == "Gemini"
        assert caps.max_context_window == 1000000
        assert caps.multimodal is True
        assert caps.thinking is False

    def test_codex_capabilities(self):
        """Test Codex capabilities."""
        caps = get_tool_capabilities("codex")

        assert caps is not None
        assert caps.name == "Codex"
        assert caps.streaming is True
        assert caps.thinking is False
        assert caps.multimodal is False

    def test_opencode_capabilities(self):
        """Test OpenCode capabilities."""
        caps = get_tool_capabilities("opencode")

        assert caps is not None
        assert caps.name == "OpenCode"
        assert caps.local_execution is True
        assert caps.streaming is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        caps = ToolCapabilities(
            name="Test Tool",
            streaming=True,
            thinking=False,
            max_context_window=100000,
        )

        d = caps.to_dict()

        assert d["name"] == "Test Tool"
        assert d["streaming"] is True
        assert d["max_context_window"] == 100000


class TestMessageRange:
    """MessageRange tests."""

    def test_basic_range(self):
        """Test basic range."""
        range_obj = MessageRange(
            start_index=0,
            end_index=10,
            start_timestamp="2024-01-01T00:00:00Z",
        )

        assert range_obj.start_index == 0
        assert range_obj.end_index == 10

    def test_to_dict(self):
        """Test conversion to dictionary."""
        range_obj = MessageRange(
            start_index=5,
            end_index=15,
            start_timestamp="2024-01-01T00:00:00Z",
            end_timestamp="2024-01-01T01:00:00Z",
        )

        d = range_obj.to_dict()

        assert d["start_index"] == 5
        assert d["end_index"] == 15
        assert d["start_timestamp"] == "2024-01-01T00:00:00Z"
        assert d["end_timestamp"] == "2024-01-01T01:00:00Z"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "start_index": 0,
            "end_index": 5,
            "start_timestamp": "2024-01-01T00:00:00Z",
        }

        range_obj = MessageRange.from_dict(data)

        assert range_obj is not None
        assert range_obj.start_index == 0
        assert range_obj.end_index == 5


class TestToolUse:
    """ToolUse tests."""

    def test_basic_tool_use(self):
        """Test basic tool use."""
        tool_use = ToolUse(
            id="toolu_123",
            name="read_file",
            input={"path": "/test.txt"},
        )

        assert tool_use.id == "toolu_123"
        assert tool_use.name == "read_file"
        assert tool_use.input["path"] == "/test.txt"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        tool_use = ToolUse(
            id="toolu_456",
            name="bash",
            input={"command": "ls"},
        )

        d = tool_use.to_dict()

        assert d["id"] == "toolu_456"
        assert d["name"] == "bash"
        assert d["input"]["command"] == "ls"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "toolu_789",
            "name": "write_file",
            "input": {"path": "/output.txt", "content": "Hello"},
        }

        tool_use = ToolUse.from_dict(data)

        assert tool_use.id == "toolu_789"
        assert tool_use.name == "write_file"


class TestPermissionRequestContent:
    """PermissionRequestContent tests."""

    def test_basic_request(self):
        """Test basic request."""
        request = PermissionRequestContent(
            request_id="req-123",
            tool_name="write_file",
            tool_input={"path": "/output.txt", "content": "Hello"},
        )

        assert request.request_id == "req-123"
        assert request.tool_name == "write_file"
        assert request.status == PermissionStatus.PENDING

    def test_with_decision(self):
        """Test request with decision."""
        request = PermissionRequestContent(
            request_id="req-456",
            tool_name="bash",
            tool_input={"command": "rm -rf"},
            status=PermissionStatus.DENIED,
            scope=PermissionScope.ONCE,
            approved_at="2024-01-01T00:00:00Z",
        )

        assert request.status == PermissionStatus.DENIED
        assert request.scope == PermissionScope.ONCE

    def test_to_dict(self):
        """Test conversion to dictionary."""
        request = PermissionRequestContent(
            request_id="req-789",
            tool_name="read_file",
            tool_input={"path": "/secret.txt"},
            status=PermissionStatus.APPROVED,
        )

        d = request.to_dict()

        assert d["request_id"] == "req-789"
        assert d["tool_name"] == "read_file"
        assert d["status"] == "approved"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "request_id": "req-abc",
            "tool_name": "bash",
            "tool_input": {"command": "echo hello"},
            "status": "pending",
        }

        request = PermissionRequestContent.from_dict(data)

        assert request.request_id == "req-abc"
        assert request.status == PermissionStatus.PENDING
