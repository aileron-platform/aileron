from __future__ import annotations

from app.modules.agent_session.services.tools.acp import tool_manager as tm_module
from app.modules.agent_session.services.tools.base.types import ToolType


def test_acp_tool_manager_creates_caches_and_updates_workspace(monkeypatch) -> None:
    created = []

    class FakeConnectionManager:
        pass

    class FakeAcpTool:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.tool_type = kwargs["tool_type"]
            self.workspace_service = kwargs.get("workspace_service")
            self.connection_manager = kwargs.get("connection_manager")

    monkeypatch.setattr(tm_module, "AcpConnectionManager", FakeConnectionManager)
    monkeypatch.setattr(tm_module, "AcpTool", FakeAcpTool)

    manager = tm_module.AcpToolManager()
    manager.reset()

    tool1 = manager.get_tool(ToolType.CODEX)
    tool2 = manager.get_tool(ToolType.CODEX, workspace_service="workspace-2")

    assert tool1 is tool2
    assert len(created) == 1
    assert created[0]["tool_type"] == ToolType.CODEX
    assert isinstance(created[0]["connection_manager"], FakeConnectionManager)
    assert tool2.workspace_service == "workspace-2"
    assert manager.get_existing_tool(ToolType.CODEX) is tool1
    assert manager.get_existing_tool(ToolType.OPENCODE) is None


def test_acp_tool_manager_reset_replaces_connection_manager(monkeypatch) -> None:
    created_managers = []

    class FakeConnectionManager:
        def __init__(self):
            created_managers.append(self)

    monkeypatch.setattr(tm_module, "AcpConnectionManager", FakeConnectionManager)

    manager = tm_module.AcpToolManager()
    manager.reset()
    first_manager = manager._connection_manager
    manager._tools["codex"] = "tool"

    manager.reset()

    assert manager._tools == {}
    assert manager._connection_manager is not first_manager
    assert len(created_managers) >= 2


def test_get_acp_tool_manager_returns_singleton() -> None:
    tm_module.AcpToolManager._instance = None

    manager1 = tm_module.get_acp_tool_manager()
    manager2 = tm_module.get_acp_tool_manager()

    assert manager1 is manager2
