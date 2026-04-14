"""Value Objects 單元測試."""

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
    """PermissionConfig 測試."""

    def test_default_config(self):
        """測試預設配置."""
        config = PermissionConfig()

        assert config.mode == PermissionMode.DEFAULT
        assert config.codex is None

    def test_custom_config(self):
        """測試自訂配置."""
        codex_config = CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.RELAXED,
            approval_policy=CodexApprovalPolicy.AUTO,
            network_access=True,
        )
        config = PermissionConfig(
            mode=PermissionMode.ACCEPT_EDITS,
            codex=codex_config,
        )

        assert config.mode == PermissionMode.ACCEPT_EDITS
        assert config.codex is not None
        assert config.codex.sandbox_mode == CodexSandboxMode.RELAXED

    def test_to_dict(self):
        """測試轉換為字典."""
        config = PermissionConfig(mode=PermissionMode.BYPASS_PERMISSIONS)

        d = config.to_dict()

        assert d["mode"] == "bypassPermissions"

    def test_from_dict(self):
        """測試從字典建立."""
        data = {
            "mode": "acceptEdits",
        }

        config = PermissionConfig.from_dict(data)

        assert config.mode == PermissionMode.ACCEPT_EDITS


class TestModelConfig:
    """ModelConfig 測試."""

    def test_default_config(self):
        """測試預設配置."""
        config = ModelConfig()

        assert config.mode == "alias"
        assert config.model == ""

    def test_custom_config(self):
        """測試自訂配置."""
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
        """測試轉換為字典."""
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
        """測試從字典建立."""
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
    """TokenUsage 測試."""

    def test_basic_usage(self):
        """測試基本用量."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )

        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.total_tokens == 1500

    def test_with_cache(self):
        """測試帶快取的用量."""
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
        """測試轉換為字典."""
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
        """測試從字典建立."""
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
    """ContextWindowStatus 測試."""

    def test_basic_status(self):
        """測試基本狀態."""
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
        """測試從使用量建立."""
        status = ContextWindowStatus.from_usage(
            current_usage=170000,
            limit=200000,
        )

        assert status.current_usage == 170000
        assert status.usage_percentage == 85.0
        assert status.needs_compaction is True  # > 80%

    def test_needs_compaction_threshold(self):
        """測試壓縮閾值."""
        # 低於 80%，不需要壓縮
        status1 = ContextWindowStatus.from_usage(
            current_usage=140000,
            limit=200000,
        )
        assert status1.needs_compaction is False  # 70%

        # 等於或超過 80%，需要壓縮
        status2 = ContextWindowStatus.from_usage(
            current_usage=160000,
            limit=200000,
        )
        assert status2.needs_compaction is True  # 80%


class TestToolCapabilities:
    """ToolCapabilities 測試."""

    def test_claude_code_capabilities(self):
        """測試 Claude Code 能力."""
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
        """測試 Gemini 能力."""
        caps = get_tool_capabilities("gemini")

        assert caps is not None
        assert caps.name == "Gemini"
        assert caps.max_context_window == 1000000
        assert caps.multimodal is True
        assert caps.thinking is False

    def test_codex_capabilities(self):
        """測試 Codex 能力."""
        caps = get_tool_capabilities("codex")

        assert caps is not None
        assert caps.name == "Codex"
        assert caps.streaming is True
        assert caps.thinking is False
        assert caps.multimodal is False

    def test_opencode_capabilities(self):
        """測試 OpenCode 能力."""
        caps = get_tool_capabilities("opencode")

        assert caps is not None
        assert caps.name == "OpenCode"
        assert caps.local_execution is True
        assert caps.streaming is False

    def test_to_dict(self):
        """測試轉換為字典."""
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
    """MessageRange 測試."""

    def test_basic_range(self):
        """測試基本範圍."""
        range_obj = MessageRange(
            start_index=0,
            end_index=10,
            start_timestamp="2024-01-01T00:00:00Z",
        )

        assert range_obj.start_index == 0
        assert range_obj.end_index == 10

    def test_to_dict(self):
        """測試轉換為字典."""
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
        """測試從字典建立."""
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
    """ToolUse 測試."""

    def test_basic_tool_use(self):
        """測試基本工具使用."""
        tool_use = ToolUse(
            id="toolu_123",
            name="read_file",
            input={"path": "/test.txt"},
        )

        assert tool_use.id == "toolu_123"
        assert tool_use.name == "read_file"
        assert tool_use.input["path"] == "/test.txt"

    def test_to_dict(self):
        """測試轉換為字典."""
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
        """測試從字典建立."""
        data = {
            "id": "toolu_789",
            "name": "write_file",
            "input": {"path": "/output.txt", "content": "Hello"},
        }

        tool_use = ToolUse.from_dict(data)

        assert tool_use.id == "toolu_789"
        assert tool_use.name == "write_file"


class TestPermissionRequestContent:
    """PermissionRequestContent 測試."""

    def test_basic_request(self):
        """測試基本請求."""
        request = PermissionRequestContent(
            request_id="req-123",
            tool_name="write_file",
            tool_input={"path": "/output.txt", "content": "Hello"},
        )

        assert request.request_id == "req-123"
        assert request.tool_name == "write_file"
        assert request.status == PermissionStatus.PENDING

    def test_with_decision(self):
        """測試帶決策的請求."""
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
        """測試轉換為字典."""
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
        """測試從字典建立."""
        data = {
            "request_id": "req-abc",
            "tool_name": "bash",
            "tool_input": {"command": "echo hello"},
            "status": "pending",
        }

        request = PermissionRequestContent.from_dict(data)

        assert request.request_id == "req-abc"
        assert request.status == PermissionStatus.PENDING
