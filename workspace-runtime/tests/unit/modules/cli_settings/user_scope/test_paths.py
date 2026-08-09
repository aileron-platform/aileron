from __future__ import annotations

from pathlib import Path

import pytest

from app.core.revision import compute_revision
from app.modules.cli_settings.agents_md.models import (
    AgentsMdScope,
    AgentsMdUpdateRequest,
)
from app.modules.cli_settings.agents_md.documents import (
    AgentsMdService,
    AgentsMdTool,
    get_agents_md_config,
)
from app.modules.cli_settings.mcp.configuration import McpTool, get_mcp_tool_config
from app.modules.cli_settings.skills.config import SkillTool, get_skill_config
from app.modules.cli_settings.slash_commands.config import (
    SlashCommandTool,
    get_slash_command_config,
)
from app.modules.cli_settings.subagents.config import (
    SubagentTool,
    get_subagent_config,
)
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import (
    UserScopePathResolver,
    logical_runtime_locator,
    runtime_user_home,
)


@pytest.mark.parametrize(
    ("agent", "resource", "relative_path"),
    [
        (
            UserScopeAgent.CLAUDE_CODE,
            UserScopeResource.INSTRUCTIONS,
            ".claude/CLAUDE.md",
        ),
        (
            UserScopeAgent.CLAUDE_CODE,
            UserScopeResource.MCP,
            ".claude.json",
        ),
        (
            UserScopeAgent.CLAUDE_CODE,
            UserScopeResource.OUTPUT_STYLES,
            ".claude/output-styles",
        ),
        (
            UserScopeAgent.CODEX,
            UserScopeResource.INSTRUCTIONS,
            ".codex/AGENTS.md",
        ),
        (
            UserScopeAgent.CODEX,
            UserScopeResource.SETTINGS,
            ".codex/config.toml",
        ),
        (
            UserScopeAgent.CODEX,
            UserScopeResource.PROMPTS,
            ".codex/prompts",
        ),
        (
            UserScopeAgent.CODEX,
            UserScopeResource.RULES,
            ".codex/rules",
        ),
        (
            UserScopeAgent.OPENCODE,
            UserScopeResource.INSTRUCTIONS,
            ".config/opencode/AGENTS.md",
        ),
        (
            UserScopeAgent.OPENCODE,
            UserScopeResource.MCP,
            ".config/opencode/opencode.json",
        ),
        (
            UserScopeAgent.OPENCODE,
            UserScopeResource.SUBAGENTS,
            ".config/opencode/agents",
        ),
    ],
)
def test_resolves_runtime_path_and_logical_locator(
    agent: UserScopeAgent,
    resource: UserScopeResource,
    relative_path: str,
) -> None:
    resolver = UserScopePathResolver(user_home=Path("/home/developer"))

    location = resolver.resolve(agent, resource)

    assert location.runtime_path == Path("/home/developer") / relative_path
    assert location.logical_locator == f"~/{relative_path}"
    assert location.agent == agent
    assert location.resource == resource


def test_resolves_agent_roots_from_the_same_runtime_home() -> None:
    resolver = UserScopePathResolver(user_home=Path("/home/developer"))

    assert resolver.resolve_root(UserScopeAgent.CLAUDE_CODE).runtime_path == Path(
        "/home/developer/.claude"
    )
    assert resolver.resolve_root(UserScopeAgent.CODEX).runtime_path == Path(
        "/home/developer/.codex"
    )
    assert resolver.resolve_root(UserScopeAgent.OPENCODE).runtime_path == Path(
        "/home/developer/.config/opencode"
    )


def test_rejects_unsupported_agent_resource_pair() -> None:
    resolver = UserScopePathResolver(user_home=Path("/home/developer"))

    with pytest.raises(
        ValueError,
        match="Unsupported user-scope resource: opencode/hooks",
    ):
        resolver.resolve(UserScopeAgent.OPENCODE, UserScopeResource.HOOKS)


def test_runtime_user_home_uses_standard_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/home/developer")

    assert runtime_user_home() == Path("/home/developer")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (Path("/home/developer/.claude/CLAUDE.md"), "~/.claude/CLAUDE.md"),
        (Path("/workspace/.codex/config.toml"), "./.codex/config.toml"),
        (Path("/home/developer/.codex"), "~/.codex"),
        (Path("/private/provider/root"), None),
        (Path("plugins/demo"), "plugins/demo"),
        (Path("../escape"), None),
    ],
)
def test_logical_runtime_locator_hides_runtime_roots(
    path: Path,
    expected: str | None,
) -> None:
    assert (
        logical_runtime_locator(
            path,
            user_home=Path("/home/developer"),
            workspace_root=Path("/workspace"),
            preferred_roots=((Path("/home/developer/.codex"), "~/.codex"),),
        )
        == expected
    )


def test_existing_cli_settings_configs_share_the_runtime_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/home/developer")

    assert get_agents_md_config(AgentsMdTool.CLAUDE).user_root == Path(
        "/home/developer/.claude"
    )
    assert get_agents_md_config(AgentsMdTool.CODEX).user_root == Path(
        "/home/developer/.codex"
    )
    assert get_agents_md_config(AgentsMdTool.OPENCODE).user_root == Path(
        "/home/developer/.config/opencode"
    )
    assert get_skill_config(SkillTool.CLAUDE).user_root == Path(
        "/home/developer/.claude/skills"
    )
    assert get_skill_config(SkillTool.CODEX).user_root == Path(
        "/home/developer/.codex/skills"
    )
    assert get_skill_config(SkillTool.OPENCODE).user_root == Path(
        "/home/developer/.config/opencode/skills"
    )
    assert get_slash_command_config(SlashCommandTool.CODEX).user_root == Path(
        "/home/developer/.codex/prompts"
    )
    assert get_slash_command_config(SlashCommandTool.OPENCODE).user_root == Path(
        "/home/developer/.config/opencode/commands"
    )
    assert get_subagent_config(SubagentTool.CLAUDE).user_root == Path(
        "/home/developer/.claude/agents"
    )
    assert get_subagent_config(SubagentTool.OPENCODE).user_root == Path(
        "/home/developer/.config/opencode/agents"
    )
    assert get_mcp_tool_config(McpTool.CODEX).user_file_path == Path(
        "/home/developer/.codex/config.toml"
    )
    assert get_mcp_tool_config(McpTool.OPENCODE).user_file_path == Path(
        "/home/developer/.config/opencode/opencode.json"
    )


def test_codex_agents_md_service_reads_and_writes_the_runtime_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(runtime_home))
    service = AgentsMdService(get_agents_md_config(AgentsMdTool.CODEX))

    initial = service.get_document("workspace-1", AgentsMdScope.USER)
    response = service.update_document(
        "workspace-1",
        AgentsMdUpdateRequest(
            scope=AgentsMdScope.USER,
            content="# Runtime instructions",
            revision=initial.revision,
        ),
    )

    target = runtime_home / ".codex" / "AGENTS.md"
    assert target.read_text(encoding="utf-8") == "# Runtime instructions"
    assert service.get_document("workspace-1", AgentsMdScope.USER).content == (
        "# Runtime instructions"
    )
    assert response.revision == compute_revision("# Runtime instructions")
