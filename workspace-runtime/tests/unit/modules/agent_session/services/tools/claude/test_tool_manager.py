from __future__ import annotations

from app.modules.agent_session.services.tools.claude import tool_manager as tm_module


def test_claude_tool_manager_creates_and_caches_singleton(monkeypatch) -> None:
    created = []

    class FakeClaudeTool:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.api_key = kwargs.get("api_key")

    monkeypatch.setattr(tm_module, "ClaudeTool", FakeClaudeTool)
    monkeypatch.setattr(tm_module.os, "getenv", lambda key: "api-key" if key == "ANTHROPIC_API_KEY" else None)

    manager = tm_module.ClaudeToolManager()
    manager.reset()

    tool1 = manager.get_tool()
    tool2 = manager.get_tool()

    assert tool1 is tool2
    assert len(created) == 1
    assert created[0]["api_key"] == "api-key"
    assert manager.get_existing_tool() is tool1


def test_get_claude_tool_manager_returns_singleton() -> None:
    tm_module._claude_tool_manager = None
    manager1 = tm_module.get_claude_tool_manager()
    manager2 = tm_module.get_claude_tool_manager()

    assert manager1 is manager2
