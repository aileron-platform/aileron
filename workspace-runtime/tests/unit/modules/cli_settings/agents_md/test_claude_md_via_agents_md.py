from __future__ import annotations

from pathlib import Path

from app.modules.cli_settings.agents_md.models import AgentsMdScope, AgentsMdUpdateRequest
from app.modules.cli_settings.agents_md.service import (
    AgentsMdService,
    AgentsMdTool,
    get_agents_md_config,
)


def _service(tool: AgentsMdTool) -> AgentsMdService:
    return AgentsMdService(get_agents_md_config(tool))


def test_claude_project_writes_workspace_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.agents_md.service.get_workspace_path", lambda: str(tmp_path))

    _service(AgentsMdTool.CLAUDE).update_document(
        "workspace-1",
        AgentsMdUpdateRequest(scope=AgentsMdScope.PROJECT, content="# Claude"),
    )

    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# Claude"
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()


def test_claude_user_writes_claude_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    service = _service(AgentsMdTool.CLAUDE)

    service.update_document(
        "workspace-1",
        AgentsMdUpdateRequest(scope=AgentsMdScope.USER, content="# User Claude"),
    )

    assert (tmp_path / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == "# User Claude"


def test_project_paths_for_non_claude_tools(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.agents_md.service.get_workspace_path", lambda: str(tmp_path))

    cases = [
        (AgentsMdTool.GEMINI, "GEMINI.md"),
        (AgentsMdTool.CODEX, "AGENTS.md"),
        (AgentsMdTool.OPENCODE, "AGENTS.md"),
    ]
    for tool, file_name in cases:
        _service(tool).update_document(
            "workspace-1",
            AgentsMdUpdateRequest(scope=AgentsMdScope.PROJECT, content=tool.value),
        )
        assert (tmp_path / file_name).read_text(encoding="utf-8") == tool.value


def test_user_paths_for_non_claude_tools(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cases = [
        (AgentsMdTool.CODEX, tmp_path / ".codex" / "AGENTS.md"),
        (AgentsMdTool.OPENCODE, tmp_path / ".config" / "opencode" / "AGENTS.md"),
    ]
    for tool, expected_path in cases:
        _service(tool).update_document(
            "workspace-1",
            AgentsMdUpdateRequest(scope=AgentsMdScope.USER, content=tool.value),
        )
        assert expected_path.read_text(encoding="utf-8") == tool.value
